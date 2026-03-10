"""
Serviço de e-mail via Resend.
Todos os envios são no-op quando EMAIL_ENABLED=false (dev/test).
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("email_service")


def _get_client():
    import resend
    resend.api_key = settings.RESEND_API_KEY
    return resend


def _send(*, to: str, subject: str, html: str) -> bool:
    if not settings.EMAIL_ENABLED:
        logger.info("EMAIL_ENABLED=false — e-mail '%s' para <%s> não enviado.", subject, to)
        return True
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY não configurada — e-mail não enviado.")
        return False
    try:
        resend = _get_client()
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info("E-mail '%s' enviado para <%s>", subject, to)
        return True
    except Exception as exc:
        logger.error("Falha ao enviar e-mail para <%s>: %s", to, exc)
        return False


# ── Templates ───────────────────────────────────────────────────────

def _base_html(title: str, body: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
  .container {{ max-width: 580px; margin: 40px auto; background: #fff;
                border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  h1 {{ color: #2d6a2d; margin-top: 0; }}
  .btn {{ display: inline-block; padding: 14px 28px; background: #2d6a2d;
          color: #fff !important; text-decoration: none; border-radius: 6px;
          font-weight: bold; margin: 20px 0; }}
  .footer {{ margin-top: 32px; font-size: 12px; color: #aaa; }}
</style>
</head>
<body>
<div class="container">
  {body}
  <div class="footer">WallFruits &mdash; Marketplace de Frutas e Hortaliças<br>
  Este e-mail foi enviado automaticamente, não responda.</div>
</div>
</body>
</html>"""


def send_welcome_email(*, to: str, name: str) -> bool:
    body = f"""
    <h1>Bem-vindo ao WallFruits, {name}! 🍊</h1>
    <p>Sua conta foi criada com sucesso. Você já pode acessar o marketplace e
    começar a negociar frutas com produtores de todo o Brasil.</p>
    <a class="btn" href="{settings.FRONTEND_URL}">Acessar marketplace</a>
    <p>Se tiver dúvidas, entre em contato conosco.</p>
    """
    return _send(to=to, subject="Bem-vindo ao WallFruits! 🍊", html=_base_html("Bem-vindo", body))


def send_password_reset_email(*, to: str, name: str, reset_url: str) -> bool:
    body = f"""
    <h1>Redefinição de senha</h1>
    <p>Olá, {name}! Recebemos uma solicitação para redefinir a senha da sua conta.</p>
    <a class="btn" href="{reset_url}">Redefinir minha senha</a>
    <p>Este link expira em <strong>1 hora</strong>.</p>
    <p>Se você não solicitou a redefinição, ignore este e-mail. Sua senha permanece a mesma.</p>
    """
    return _send(to=to, subject="Redefinição de senha – WallFruits", html=_base_html("Redefinição de senha", body))


def send_email_verification(*, to: str, name: str, verify_url: str) -> bool:
    body = f"""
    <h1>Confirme seu e-mail</h1>
    <p>Olá, {name}! Clique no botão abaixo para confirmar seu endereço de e-mail.</p>
    <a class="btn" href="{verify_url}">Confirmar e-mail</a>
    <p>Este link expira em <strong>24 horas</strong>.</p>
    """
    return _send(to=to, subject="Confirme seu e-mail – WallFruits", html=_base_html("Confirmação de e-mail", body))


def send_negotiation_notification(
    *,
    to: str,
    name: str,
    subject: str,
    message: str,
    action_url: Optional[str] = None,
    action_label: str = "Ver negociação",
) -> bool:
    action_html = f'<a class="btn" href="{action_url}">{action_label}</a>' if action_url else ""
    body = f"""
    <h1>{subject}</h1>
    <p>Olá, {name}!</p>
    <p>{message}</p>
    {action_html}
    """
    return _send(to=to, subject=f"{subject} – WallFruits", html=_base_html(subject, body))


def send_subscription_confirmation(*, to: str, name: str, plan: str, amount: str) -> bool:
    body = f"""
    <h1>Assinatura confirmada ✅</h1>
    <p>Olá, {name}! Sua assinatura do plano <strong>{plan}</strong> foi ativada com sucesso.</p>
    <p>Valor cobrado: <strong>R$ {amount}</strong></p>
    <a class="btn" href="{settings.FRONTEND_URL}/dashboard">Ver meu painel</a>
    """
    return _send(to=to, subject=f"Assinatura {plan} confirmada – WallFruits", html=_base_html("Assinatura confirmada", body))
