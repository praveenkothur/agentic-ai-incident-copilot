
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.diagnosis import diagnose


DATASET = ROOT / "experiments" / "dataset" / "incident_scenarios.json"
RESULTS_DIR = ROOT / "experiments" / "results"

ACTION_TO_CLASS = {
    "Review and simulate rollback to the previous known-good release":
        "payment_dependency_timeout",

    "Collect dependency and application telemetry before remediation":
        "http_5xx_unconfirmed",

    "Continue investigation; do not remediate":
        "insufficient_evidence",
}


def load_dataset():
    with DATASET.open("r", encoding="utf-8") as file:
        scenarios = json.load(file)

    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Dataset must contain a non-empty JSON list.")

    return scenarios


def calculate_metrics(rows):
    classes = sorted(ACTION_TO_CLASS.values())

    total = len(rows)
    correct = sum(row["correct"] for row in rows)

    class_metrics = {}

    for category in classes:
        tp = sum(
            row["ground_truth_class"] == category
            and row["predicted_class"] == category
            for row in rows
        )

        fp = sum(
            row["ground_truth_class"] != category
            and row["predicted_class"] == category
            for row in rows
        )

        fn = sum(
            row["ground_truth_class"] == category
            and row["predicted_class"] != category
            for row in rows
        )

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        class_metrics[category] = {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        }

    return {
        "scenario_count": total,
        "correct_predictions": correct,
        "incorrect_predictions": total - correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro_precision": round(
            mean(item["precision"] for item in class_metrics.values()), 4
        ),
        "macro_recall": round(
            mean(item["recall"] for item in class_metrics.values()), 4
        ),
        "macro_f1": round(
            mean(item["f1_score"] for item in class_metrics.values()), 4
        ),
        "per_class_metrics": class_metrics,
    }


def run_experiment(repeats):
    scenarios = load_dataset()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    print("\nB1: Deterministic Diagnosis Without LLM")
    print("=" * 55)

    for scenario in scenarios:
        latencies = []
        predictions = []
        actions = []
        confidences = []

        for _ in range(repeats):
            start = perf_counter_ns()

            diagnosis = diagnose(scenario["evidence"])

            elapsed_ms = (
                perf_counter_ns() - start
            ) / 1_000_000

            predicted_action = diagnosis["recommended_action"]
            predicted_class = ACTION_TO_CLASS.get(
                predicted_action, "unknown"
            )

            latencies.append(elapsed_ms)
            predictions.append(predicted_class)
            actions.append(predicted_action)
            confidences.append(diagnosis["confidence"])

        predicted_class = Counter(predictions).most_common(1)[0][0]
        expected_class = scenario["ground_truth_class"]

        correct = predicted_class == expected_class

        row = {
            "scenario_id": scenario["scenario_id"],
            "ground_truth_class": expected_class,
            "predicted_class": predicted_class,
            "correct": correct,
            "expected_action": scenario["expected_recommended_action"],
            "predicted_action": Counter(actions).most_common(1)[0][0],
            "confidence": round(mean(confidences), 4),
            "runs": repeats,
            "mean_latency_ms": round(mean(latencies), 4),
            "min_latency_ms": round(min(latencies), 4),
            "max_latency_ms": round(max(latencies), 4),
        }

        results.append(row)

        status = "PASS" if correct else "FAIL"

        print(
            f"{scenario['scenario_id']}: {status} | "
            f"Predicted={predicted_class} | "
            f"Latency={row['mean_latency_ms']} ms"
        )

    metrics = calculate_metrics(results)

    summary = {
        "experiment": "B1",
        "name": "Deterministic Diagnosis Without LLM",
        "dataset": str(DATASET.relative_to(ROOT)),
        "repeats_per_scenario": repeats,
        "evaluation_type": "synthetic rule-based benchmark",
        "metrics": metrics,
        "mean_latency_ms": round(
            mean(row["mean_latency_ms"] for row in results), 4
        ),
        "limitations": [
            "Synthetic scenarios only.",
            "Ground-truth labels are assigned from scenario definitions.",
            "Results do not establish real-world diagnostic accuracy.",
            "Repeated runs are not independent incident samples.",
        ],
    }

    csv_path = RESULTS_DIR / "b1_deterministic_results.csv"
    json_path = RESULTS_DIR / "b1_deterministic_summary.json"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0].keys()),
        )
        writer.writeheader()
        writer.writerows(results)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print("\n" + "=" * 55)
    print("EXPERIMENT SUMMARY")
    print("=" * 55)
    print(f"Scenarios: {metrics['scenario_count']}")
    print(f"Correct: {metrics['correct_predictions']}")
    print(f"Incorrect: {metrics['incorrect_predictions']}")
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"Macro precision: {metrics['macro_precision']:.2%}")
    print(f"Macro recall: {metrics['macro_recall']:.2%}")
    print(f"Macro F1: {metrics['macro_f1']:.2%}")
    print(f"Mean latency: {summary['mean_latency_ms']} ms")

    print("\nGenerated files:")
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run B1 deterministic diagnosis experiment."
    )

    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of executions per scenario.",
    )

    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1.")

    run_experiment(args.repeats)
