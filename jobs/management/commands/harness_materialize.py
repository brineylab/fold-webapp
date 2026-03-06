from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from jobs.harness import materialize_case, verify_materialized_case


class Command(BaseCommand):
    help = "Prepare or verify a direct-run harness case."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, help="Harness run identifier.")
        parser.add_argument("--case", required=True, help="Harness case id.")
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Verify a previously materialized case instead of preparing it.",
        )
        parser.add_argument(
            "--exit-code",
            type=int,
            default=0,
            help="Exit code from the direct execution when used with --verify.",
        )
        parser.add_argument(
            "--materialized-only",
            action="store_true",
            help="Record a successful materialization-only result without checking outputs.",
        )

    def handle(self, *args, **options):
        run_id = options["run_id"]
        case_id = options["case"]

        try:
            if options["verify"]:
                payload = verify_materialized_case(
                    run_id,
                    case_id,
                    exit_code=options["exit_code"],
                    materialized_only=options["materialized_only"],
                )
            else:
                payload = materialize_case(run_id, case_id).__dict__
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(payload, sort_keys=True))
