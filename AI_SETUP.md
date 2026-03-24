# WallFruits AI - Execucao de Servicos

## 1) Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2) Configurar ambiente

No arquivo `.env`, revise:

```env
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LLM_PROVIDER=openai
AI_LOW_LATENCY_MODE=true
```

## 3) Subir backend

```bash
uvicorn app.main:app --reload
```

## 3.1) Rodar migration formal (Alembic)

```bash
alembic upgrade head
```

## 4) Subir worker de background (Celery)

```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

## 5) Endpoints AI

- `GET /api/ai/suggestions`
- `POST /api/ai/predict`
- `POST /api/ai/chat`
- `POST /api/ai/recommendations`
- `POST /api/ai/train`

## 6) WebSocket realtime

- URL: `/ws/notifications/{user_id}`
- Mensagens enviadas automaticamente quando o rule engine executa automacoes ao fechar negociacoes.

## 7) Melhorar acuracia de ML

1. Logar eventos em `user_behavior_logs` com `meta_json` rico: horario de contato, tempo de resposta, desconto e desfecho.
2. Rodar `POST /api/ai/train` periodicamente (ex: cron diario).
3. Monitorar metricas retornadas e ajustar features / hiperparametros.

## 8) Integracao de clima

O Smart Scheduling usa Open-Meteo em `app/ai/weather_client.py`.
Pode ser trocado por provedor pago sem alterar o contrato dos servicos de agenda.

## 9) OpenAI com fallback local

- Chat e recomendações usam OpenAI quando `OPENAI_API_KEY` estiver configurada.
- Sem chave/API, o sistema cai automaticamente para heurísticas locais sem interromper a operação.
