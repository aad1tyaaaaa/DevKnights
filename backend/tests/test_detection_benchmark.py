from pathlib import Path

from benchmarks.detection_benchmark import render_markdown, run_benchmark


def test_benchmark_is_reproducible_and_metrics_match_case_outcomes():
    first = run_benchmark()
    second = run_benchmark()
    assert first == second
    metrics = first.metrics
    assert metrics.true_positives + metrics.false_negatives == sum(
        case.expected_indicator for case in first.cases
    )
    assert metrics.true_negatives + metrics.false_positives == sum(
        not case.expected_indicator for case in first.cases
    )
    assert 0 <= metrics.precision <= 1
    assert 0 <= metrics.recall <= 1
    assert 0 <= metrics.f1_score <= 1
    assert 0 <= metrics.false_positive_rate <= 1


def test_benchmark_discloses_ground_truth_and_independence_limitation():
    report = run_benchmark()
    markdown = render_markdown(report)
    assert "investigation indicator" in report.ground_truth_definition
    assert "not an independent real-world malware corpus" in report.limitation
    assert "confirmed malware" in report.ground_truth_definition
    assert "| TP | FP | TN | FN |" in markdown
    checked_in = Path(__file__).parents[1] / "benchmarks" / "report.md"
    assert checked_in.read_text(encoding="utf-8") == markdown
