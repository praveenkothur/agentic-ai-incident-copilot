import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import csv
import json

from app.diagnosis import diagnose

DATASET = PROJECT_ROOT / "experiments/dataset/diagnosis/development_scenarios.json"
RESULTS_DIR = PROJECT_ROOT / "experiments/results/b1"
CSV_PATH = RESULTS_DIR / "development_diagnosis_results.csv"
SUMMARY_PATH = RESULTS_DIR / "development_diagnosis_summary.json"

ACTION_TO_CLASS = {
    "Review and simulate rollback to the previous known-good release": "payment_timeout",
    "Collect dependency and application telemetry before remediation": "http_5xx",
    "Continue investigation; do not remediate": "insufficient_evidence",
}

data = json.loads(DATASET.read_text(encoding="utf-8"))
rows = []
errors = []

for item in data:
    expected = item["expected_class"]

    try:
        prediction = diagnose(item["evidence"])
        action = prediction.get("recommended_action")
        predicted = ACTION_TO_CLASS.get(action, "unknown")

        rows.append({
            "scenario_id": item["scenario_id"],
            "expected_class": expected,
            "predicted_class": predicted,
            "match": predicted == expected,
            "confidence": prediction.get("confidence"),
            "expected_action": item["expected_recommended_action"],
            "predicted_action": action,
            "likely_root_cause": prediction.get("likely_root_cause"),
        })
    except Exception as exc:
        errors.append({"scenario_id": item["scenario_id"], "error": str(exc)})
        rows.append({
            "scenario_id": item["scenario_id"],
            "expected_class": expected,
            "predicted_class": "error",
            "match": False,
            "confidence": None,
            "expected_action": item["expected_recommended_action"],
            "predicted_action": None,
            "likely_root_cause": None,
        })

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

with CSV_PATH.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

labels = ["payment_timeout", "http_5xx", "insufficient_evidence"]
predicted_labels = labels + ["unknown", "error"]

confusion = {
    actual: {predicted: 0 for predicted in predicted_labels}
    for actual in labels
}

for row in rows:
    confusion[row["expected_class"]][row["predicted_class"]] += 1

metrics = {}
for label in labels:
    tp = sum(r["expected_class"] == label and r["predicted_class"] == label for r in rows)
    fp = sum(r["expected_class"] != label and r["predicted_class"] == label for r in rows)
    fn = sum(r["expected_class"] == label and r["predicted_class"] != label for r in rows)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    metrics[label] = {
        "support": sum(r["expected_class"] == label for r in rows),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }

correct = sum(r["match"] for r in rows)
total = len(rows)

summary = {
    "dataset": str(DATASET),
    "dataset_type": "synthetic development dataset",
    "total_scenarios": total,
    "correct_predictions": correct,
    "incorrect_predictions": total - correct,
    "accuracy": round(correct / total, 4) if total else 0,
    "macro_precision": round(sum(m["precision"] for m in metrics.values()) / len(labels), 4),
    "macro_recall": round(sum(m["recall"] for m in metrics.values()) / len(labels), 4),
    "macro_f1": round(sum(m["f1"] for m in metrics.values()) / len(labels), 4),
    "per_class_metrics": metrics,
    "confusion_matrix": confusion,
    "execution_errors": errors,
    "interpretation": "Synthetic development results only; labels require independent review.",
}

SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("\nDEVELOPMENT BENCHMARK")
print("---------------------")
print(f"Scenarios: {total}")
print(f"Correct: {correct}")
print(f"Incorrect: {total - correct}")
print(f"Accuracy: {summary['accuracy']:.2%}")
print(f"Macro precision: {summary['macro_precision']:.4f}")
print(f"Macro recall: {summary['macro_recall']:.4f}")
print(f"Macro F1: {summary['macro_f1']:.4f}")
print(f"Execution errors: {len(errors)}")

print("\nMISMATCHES")
for row in rows:
    if not row["match"]:
        print(f"{row['scenario_id']}: expected={row['expected_class']}, predicted={row['predicted_class']}")

print("\nCONFUSION MATRIX")
print(json.dumps(confusion, indent=2))

print("\nFILES")
print(CSV_PATH)
print(SUMMARY_PATH)
