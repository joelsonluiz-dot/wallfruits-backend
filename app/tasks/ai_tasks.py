from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.ai.risk_alert import RiskAlertAI


@celery_app.task(name="ai.run_risk_scan")
def run_risk_scan(user_id: int) -> dict:
    db = SessionLocal()
    try:
        service = RiskAlertAI(db)
        alerts = service.run_for_user(user_id=user_id)
        return {"user_id": user_id, "alerts": alerts, "count": len(alerts)}
    finally:
        db.close()
