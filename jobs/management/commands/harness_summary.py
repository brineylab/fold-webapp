from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from jobs.harness import reports_dir_local, summarize_run


class Command(BaseCommand):
    help = "Write harness summary.json and summary.md for a completed run."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, help="Harness run identifier.")

    def handle(self, *args, **options):
        run_id = options["run_id"]
        try:
            summary = summarize_run(run_id)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        reports_dir = reports_dir_local(run_id)
        summary_json = reports_dir / "summary.json"
        summary_md = reports_dir / "summary.md"

        summary_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        lines = [
            f"# Harness Summary ({summary['run_id']})",
            "",
            f"- Tier: `{summary['tier']}`",
            f"- Phase: `{summary['phase']}`",
            f"- Base URL: `{summary['base_url']}`",
            f"- Overall result: `{'PASS' if summary['ok'] else 'FAIL'}`",
            "",
        ]

        if summary["direct_reports"]:
            lines.append("## Direct / Materialize")
            lines.append("")
            for report in summary["direct_reports"]:
                lines.append(
                    f"- `{report['case_id']}`: `{'PASS' if report.get('ok') else 'FAIL'}` ({report.get('phase')})"
                )
            lines.append("")

        if summary["http_report"] is not None:
            lines.append("## HTTP")
            lines.append("")
            lines.append(
                f"- HTTP phase: `{'PASS' if summary['http_report'].get('ok') else 'FAIL'}`"
            )
            for item in summary["http_report"].get("submission_checks", []):
                lines.append(
                    f"- `{item['case_id']}`: `{'PASS' if item.get('ok') else 'FAIL'}`"
                )
            lines.append("")

        if summary["failed_items"]:
            lines.append("## Failures")
            lines.append("")
            for item in summary["failed_items"]:
                lines.append(f"- `{item}`")
            lines.append("")

        summary_md.write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write(str(summary_md))
