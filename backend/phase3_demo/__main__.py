from __future__ import annotations

import argparse
import asyncio
import json

from phase3_demo.runner import ScenarioReport, run_all_scenarios, run_scenario
from phase3_demo.scenarios import SCENARIOS


def render_markdown(reports: list[ScenarioReport]) -> str:
    lines = [
        "# Provenyx Phase 3 synthetic attack simulation",
        "",
        "> Safe offline demonstration: fixtures are synthetic, and package code is never installed or executed.",
        "",
    ]
    for report in reports:
        lines.extend(
            [
                f"## {report.title} (`{report.scenario}`)",
                "",
                report.description,
                "",
                f"- Before: {len(report.baseline.dependencies)} release(s), {report.baseline.finding_count} finding(s)",
                f"- After: {len(report.modified.dependencies)} release(s), {report.modified.finding_count} finding(s)",
                f"- Added: {', '.join(report.changes.added) or 'none'}",
                f"- Removed: {', '.join(report.changes.removed) or 'none'}",
                f"- Updated: {_updates(report)}",
                f"- Trust gate (`fail_on=medium`): **{report.gate_verdict.upper()}**",
                "",
                "### New findings",
                "",
            ]
        )
        if not report.new_findings:
            lines.append("No new security findings. A clean result is not a guarantee of safety.")
        for finding in report.new_findings:
            lines.extend(
                [
                    f"- **{finding.title}** — `{finding.rule_id}` on `{finding.package}@{finding.version}` "
                    f"({finding.severity}, confidence {finding.confidence}, priority {finding.priority_score}/100)",
                    f"  - Why investigate: {finding.threat_explanation.why_it_may_be_risky if finding.threat_explanation else finding.explanation}",
                    f"  - Path: {' -> '.join(finding.blast_radius.shortest_path) if finding.blast_radius and finding.blast_radius.shortest_path else 'not available'}",
                    f"  - Action: {finding.remediation[0].action if finding.remediation else 'Review the evidence.'}",
                ]
            )
        lines.extend(["", "### Limitations", ""])
        lines.extend(f"- {limitation}" for limitation in report.analysis_limitations)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _updates(report: ScenarioReport) -> str:
    return ", ".join(
        f"{change.name} ({'/'.join(change.from_versions)} -> {'/'.join(change.to_versions)})"
        for change in report.changes.updated
    ) or "none"


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run safe, offline Provenyx Phase 3 attack simulations")
    parser.add_argument("--scenario", choices=("all", *SCENARIOS.keys()), default="transitive-dependency-compromise")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    reports = await run_all_scenarios() if args.scenario == "all" else [await run_scenario(args.scenario)]
    if args.format == "json":
        print(json.dumps([report.model_dump(mode="json") for report in reports], indent=2, sort_keys=True))
    else:
        print(render_markdown(reports), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
