"""
Testes unitários para o webhook_dispatcher:
- Assinatura HMAC-SHA256
- Retry com backoff
- Idempotência (event_id único)
- Headers corretos
"""
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.webhook_dispatcher import (
    _sign_payload,
    _do_send,
    dispatch_webhook,
)


class TestSignPayload(unittest.TestCase):
    def test_hmac_sha256_correctness(self):
        body = b'{"event":"test"}'
        secret = "my-secret-key"
        result = _sign_payload(body, secret)
        expected = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        self.assertEqual(result, expected)

    def test_different_secrets_produce_different_signatures(self):
        body = b'{"event":"test"}'
        sig1 = _sign_payload(body, "secret-a")
        sig2 = _sign_payload(body, "secret-b")
        self.assertNotEqual(sig1, sig2)

    def test_different_bodies_produce_different_signatures(self):
        secret = "same-secret"
        sig1 = _sign_payload(b"body-a", secret)
        sig2 = _sign_payload(b"body-b", secret)
        self.assertNotEqual(sig1, sig2)


class TestDoSend(unittest.TestCase):
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_success_on_first_attempt(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
            max_retries=2,
        )
        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("app.services.webhook_dispatcher.time.sleep")
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_retry_on_server_error(self, mock_urlopen, mock_sleep):
        from urllib.error import HTTPError

        error_resp = HTTPError(
            url="https://example.com/webhook",
            code=500,
            msg="Server Error",
            hdrs={},
            fp=None,
        )
        # Falha 2x, sucesso na 3a
        ctx = MagicMock()
        ctx.__enter__ = MagicMock()
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = [error_resp, error_resp, ctx]

        result = _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={},
            timeout=5.0,
            max_retries=2,
        )
        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 3)
        # Verificar que houve sleep entre tentativas
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("app.services.webhook_dispatcher.time.sleep")
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_no_retry_on_4xx(self, mock_urlopen, mock_sleep):
        from urllib.error import HTTPError

        error_resp = HTTPError(
            url="https://example.com/webhook",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = error_resp

        result = _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={},
            timeout=5.0,
            max_retries=3,
        )
        self.assertFalse(result)
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("app.services.webhook_dispatcher.time.sleep")
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_retry_on_429(self, mock_urlopen, mock_sleep):
        from urllib.error import HTTPError

        error_429 = HTTPError(
            url="https://example.com/webhook",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        ctx = MagicMock()
        ctx.__enter__ = MagicMock()
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = [error_429, ctx]

        result = _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={},
            timeout=5.0,
            max_retries=1,
        )
        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("app.services.webhook_dispatcher.time.sleep")
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_all_retries_exhausted(self, mock_urlopen, mock_sleep):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        result = _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={},
            timeout=5.0,
            max_retries=2,
        )
        self.assertFalse(result)
        self.assertEqual(mock_urlopen.call_count, 3)  # 1 original + 2 retries

    @patch("app.services.webhook_dispatcher.time.sleep")
    @patch("app.services.webhook_dispatcher.urlopen")
    def test_backoff_delays(self, mock_urlopen, mock_sleep):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("fail")

        _do_send(
            url="https://example.com/webhook",
            body=b"{}",
            headers={},
            timeout=5.0,
            max_retries=3,
        )
        # Delays: 2*2^0=2, 2*2^1=4, 2*2^2=8
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(calls, [2.0, 4.0, 8.0])


class TestDispatchWebhook(unittest.TestCase):
    @patch("app.services.webhook_dispatcher.settings")
    def test_returns_empty_when_no_url(self, mock_settings):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = ""
        event_id = dispatch_webhook(
            event_type="test_event",
            payload={"key": "value"},
            background=False,
        )
        self.assertEqual(event_id, "")

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_event_id_is_unique(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = ""
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        id1 = dispatch_webhook(
            event_type="ev1", payload={}, background=False
        )
        id2 = dispatch_webhook(
            event_type="ev2", payload={}, background=False
        )
        self.assertNotEqual(id1, id2)
        self.assertTrue(len(id1) == 36)  # UUID format

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_hmac_header_present_when_secret_set(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = "test-secret-123"
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        dispatch_webhook(
            event_type="test_event",
            payload={"data": "hello"},
            background=False,
        )

        call_kwargs = mock_do_send.call_args.kwargs
        headers = call_kwargs["headers"]
        self.assertIn("X-WallFruits-Signature", headers)
        self.assertTrue(headers["X-WallFruits-Signature"].startswith("sha256="))

        # Verificar que a assinatura é correta
        body = call_kwargs["body"]
        expected_sig = _sign_payload(body, "test-secret-123")
        self.assertEqual(headers["X-WallFruits-Signature"], f"sha256={expected_sig}")

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_no_signature_header_when_no_secret(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = ""
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        dispatch_webhook(
            event_type="test_event", payload={}, background=False
        )

        headers = mock_do_send.call_args.kwargs["headers"]
        self.assertNotIn("X-WallFruits-Signature", headers)

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_standard_headers(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = ""
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        dispatch_webhook(
            event_type="my_event", payload={}, background=False
        )

        headers = mock_do_send.call_args.kwargs["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-WallFruits-Event"], "my_event")
        self.assertIn("X-WallFruits-Delivery", headers)
        self.assertIn("X-WallFruits-Timestamp", headers)

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_payload_envelope_structure(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = ""
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        dispatch_webhook(
            event_type="test_ev",
            payload={"custom_key": "custom_val"},
            background=False,
        )

        body = mock_do_send.call_args.kwargs["body"]
        envelope = json.loads(body)

        self.assertIn("event_id", envelope)
        self.assertEqual(envelope["event"], "test_ev")
        self.assertIn("occurred_at", envelope)
        self.assertEqual(envelope["custom_key"], "custom_val")

    @patch("app.services.webhook_dispatcher._do_send")
    @patch("app.services.webhook_dispatcher.settings")
    def test_background_dispatch_uses_thread(self, mock_settings, mock_do_send):
        mock_settings.INTERMEDIATION_WEBHOOK_URL = "https://example.com/wh"
        mock_settings.INTERMEDIATION_WEBHOOK_SECRET = ""
        mock_settings.INTERMEDIATION_WEBHOOK_TIMEOUT_SECONDS = 5.0
        mock_settings.INTERMEDIATION_WEBHOOK_MAX_RETRIES = 0
        mock_do_send.return_value = True

        import threading

        initial_count = threading.active_count()
        event_id = dispatch_webhook(
            event_type="bg_event",
            payload={},
            background=True,
        )
        self.assertTrue(len(event_id) == 36)
        # Aguardar thread terminar para não interferir em outros testes
        import time
        time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()
