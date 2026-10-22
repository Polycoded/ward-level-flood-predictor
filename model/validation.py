import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

VALIDATION_PATH = Path("data/processed/validation_metrics.json")


def load_validation_metrics() -> Dict[str, Any]:
    if VALIDATION_PATH.exists():
        with open(VALIDATION_PATH) as f:
            return json.load(f)
    return {}


def validate_against_historical(
    predictions: pd.DataFrame,
    actual_flooded_wards: list,
    top_k: int = 20
) -> Dict[str, Any]:
    predicted_top = set(predictions.head(top_k)["ward_id"].tolist())
    actual_set = set(actual_flooded_wards)
    
    true_positives = len(predicted_top & actual_set)
    false_positives = len(predicted_top - actual_set)
    false_negatives = len(actual_set - predicted_top)
    
    precision = true_positives / top_k if top_k > 0 else 0
    recall = true_positives / len(actual_set) if len(actual_set) > 0 else 0
    fpr = false_positives / (len(predictions) - len(actual_set)) if len(predictions) > len(actual_set) else 0
    
    return {
        "precision_at_20": round(precision, 4),
        "recall": round(recall, 4),
        "false_positive_rate": round(fpr, 4),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "total_flooded_wards": len(actual_set),
        "total_wards": len(predictions),
        "event_date": "2023-12-04",
        "notes": "Validation against Dec 2023 Chennai floods using Sentinel-1 SAR and news reports"
    }


def save_validation_metrics(metrics: Dict[str, Any]) -> None:
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(VALIDATION_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Validation metrics saved", path=str(VALIDATION_PATH))