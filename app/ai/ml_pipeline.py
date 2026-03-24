from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

ML_LIBS_AVAILABLE = True
from sqlalchemy.orm import Session

from app.models.ai_models import UserBehaviorLog


MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


def _load_ml_libs() -> dict[str, Any] | None:
    global ML_LIBS_AVAILABLE

    try:
        libs = {
            "joblib": importlib.import_module("joblib"),
            "pd": importlib.import_module("pandas"),
            "RandomForestClassifier": getattr(importlib.import_module("sklearn.ensemble"), "RandomForestClassifier"),
            "RandomForestRegressor": getattr(importlib.import_module("sklearn.ensemble"), "RandomForestRegressor"),
            "train_test_split": getattr(importlib.import_module("sklearn.model_selection"), "train_test_split"),
            "Pipeline": getattr(importlib.import_module("sklearn.pipeline"), "Pipeline"),
            "StandardScaler": getattr(importlib.import_module("sklearn.preprocessing"), "StandardScaler"),
        }
        return libs
    except Exception:
        ML_LIBS_AVAILABLE = False
        return None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _build_behavior_dataframe(db: Session) -> Any:
    libs = _load_ml_libs()
    if not ML_LIBS_AVAILABLE or libs is None:
        return None

    rows = db.query(UserBehaviorLog).all()
    data = []
    for row in rows:
        meta = row.meta_json or {}
        data.append(
            {
                "user_id": row.user_id,
                "event_type": row.event_type,
                "contact_hour": _to_float(meta.get("contact_hour"), 9.0),
                "response_time_hours": _to_float(meta.get("response_time_hours"), 6.0),
                "discount_pct": _to_float(meta.get("discount_pct"), 0.0),
                "deal_closed": 1.0 if bool(meta.get("deal_closed", False)) else 0.0,
                "service_duration_days": _to_float(meta.get("service_duration_days"), 4.0),
                "inactive_days": _to_float(meta.get("inactive_days"), 0.0),
                "became_inactive": 1.0 if bool(meta.get("became_inactive", False)) else 0.0,
            }
        )

    return libs["pd"].DataFrame(data)


def train_models(db: Session) -> dict[str, Any]:
    libs = _load_ml_libs()
    if not ML_LIBS_AVAILABLE or libs is None:
        return {
            "trained": False,
            "reason": "dependencias_ml_ausentes",
            "hint": "Instale requirements.txt para habilitar treino supervisionado",
        }

    df = _build_behavior_dataframe(db)
    if df is None:
        return {
            "trained": False,
            "reason": "dataframe_indisponivel",
        }

    results: dict[str, Any] = {"rows": int(len(df))}

    if len(df) < 25:
        # Evita overfitting com pouco dado; mantém heurística ativa.
        return {**results, "trained": False, "reason": "dados_insuficientes"}

    features = ["contact_hour", "response_time_hours", "discount_pct", "inactive_days"]

    # Modelo 1: probabilidade de fechamento.
    x_close = df[features]
    y_close = df["deal_closed"]
    x_train, x_test, y_train, y_test = libs["train_test_split"](
        x_close, y_close, test_size=0.2, random_state=42
    )

    close_pipe = libs["Pipeline"](
        [
            ("scaler", libs["StandardScaler"]()),
            ("model", libs["RandomForestClassifier"](n_estimators=160, random_state=42)),
        ]
    )
    close_pipe.fit(x_train, y_train)
    close_score = close_pipe.score(x_test, y_test)
    libs["joblib"].dump(close_pipe, MODEL_DIR / "deal_success_model.joblib")

    # Modelo 2: duração estimada do serviço.
    x_dur = df[features]
    y_dur = df["service_duration_days"]
    x_train2, x_test2, y_train2, y_test2 = libs["train_test_split"](
        x_dur, y_dur, test_size=0.2, random_state=42
    )

    dur_pipe = libs["Pipeline"](
        [
            ("scaler", libs["StandardScaler"]()),
            ("model", libs["RandomForestRegressor"](n_estimators=180, random_state=42)),
        ]
    )
    dur_pipe.fit(x_train2, y_train2)
    dur_score = dur_pipe.score(x_test2, y_test2)
    libs["joblib"].dump(dur_pipe, MODEL_DIR / "service_duration_model.joblib")

    # Modelo 3: risco de inatividade.
    x_eng = df[features]
    y_eng = df["became_inactive"]
    x_train3, x_test3, y_train3, y_test3 = libs["train_test_split"](
        x_eng, y_eng, test_size=0.2, random_state=42
    )

    eng_pipe = libs["Pipeline"](
        [
            ("scaler", libs["StandardScaler"]()),
            ("model", libs["RandomForestClassifier"](n_estimators=140, random_state=42)),
        ]
    )
    eng_pipe.fit(x_train3, y_train3)
    eng_score = eng_pipe.score(x_test3, y_test3)
    libs["joblib"].dump(eng_pipe, MODEL_DIR / "engagement_risk_model.joblib")

    return {
        **results,
        "trained": True,
        "deal_success_accuracy": float(close_score),
        "service_duration_r2": float(dur_score),
        "engagement_accuracy": float(eng_score),
    }


def _load_model(filename: str):
    libs = _load_ml_libs()
    if not ML_LIBS_AVAILABLE or libs is None:
        return None

    path = MODEL_DIR / filename
    if not path.exists():
        return None
    return libs["joblib"].load(path)


def predict_with_fallback(module: str, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    features = [
        [
            _to_float(payload.get("contact_hour"), 9.0),
            _to_float(payload.get("response_time_hours"), 6.0),
            _to_float(payload.get("discount_pct"), 0.0),
            _to_float(payload.get("inactive_days"), 0.0),
        ]
    ]

    if module == "negotiation":
        model = _load_model("deal_success_model.joblib")
        if model is not None:
            proba = float(model.predict_proba(features)[0][1])
            return {"close_probability": proba}, min(0.98, 0.65 + proba * 0.3)

        # Heurística de fallback para garantir resposta de baixa latência.
        response_bonus = max(0.0, 1.0 - _to_float(payload.get("response_time_hours"), 6.0) / 24.0)
        discount_bonus = min(_to_float(payload.get("discount_pct"), 0.0) / 20.0, 0.4)
        proba = max(0.05, min(0.95, 0.35 + response_bonus * 0.4 + discount_bonus * 0.25))
        return {"close_probability": float(proba)}, 0.58

    if module == "service_duration":
        model = _load_model("service_duration_model.joblib")
        if model is not None:
            days = float(model.predict(features)[0])
            return {"estimated_days": max(1.0, days)}, 0.74

        base = 3.0 + _to_float(payload.get("complexity"), 1.0) * 2.0
        return {"estimated_days": float(max(1.0, base))}, 0.55

    if module == "engagement":
        model = _load_model("engagement_risk_model.joblib")
        if model is not None:
            proba = float(model.predict_proba(features)[0][1])
            return {"inactive_risk": proba}, 0.72

        inactive_days = _to_float(payload.get("inactive_days"), 0.0)
        risk = max(0.02, min(0.98, inactive_days / 45.0))
        return {"inactive_risk": float(risk)}, 0.52

    return {"message": "modulo_nao_suportado"}, 0.0
