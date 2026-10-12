from pathlib import Path

from benchmarks.phase3_holdout import render_markdown, run_holdout


def test_phase3_holdout_is_fixed_reproducible_and_honest_about_errors():
    first = run_holdout()
    second = run_holdout()

    assert first == second
    assert first.evaluated_cases == 20
    assert first.metrics.true_positives == 10
    assert first.metrics.false_positives == 2
    assert first.metrics.true_negatives == 8
    assert first.metrics.false_negatives == 0
    assert first.metrics.precision == 10 / 12
    assert first.metrics.recall == 1.0
    assert first.metrics.false_positive_rate == 0.2
    assert "confirmed malware" in first.positive_class
    assert "synthetic" in first.limitation.lower()


def test_checked_in_phase3_holdout_report_matches_runner():
    checked_in = Path(__file__).parents[1] / "benchmarks" / "phase3_holdout_report.md"
    assert checked_in.read_text(encoding="utf-8") == render_markdown(run_holdout())
