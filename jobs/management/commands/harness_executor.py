from __future__ import annotations

import json
from argparse import SUPPRESS

from django.core.management.base import BaseCommand, CommandError

from jobs.harness import prepare_executor_case, verify_prepared_case


class Command(BaseCommand):
    help = "Prepare or verify an executor harness case."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, help="Harness run identifier.")
        parser.add_argument("--case", required=True, help="Harness case id.")
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Verify a previously prepared case instead of preparing it.",
        )
        parser.add_argument(
            "--exit-code",
            type=int,
            default=0,
            help="Exit code from the executor run when used with --verify.",
        )
        parser.add_argument(
            "--prepare-only",
            dest="prepare_only",
            action="store_true",
            help="Record a successful prepare-only result without checking outputs.",
        )
        parser.add_argument(
            "--materialized-only",
            dest="prepare_only",
            action="store_true",
            help=SUPPRESS,
        )

    def handle(self, *args, **options):
        run_id = options["run_id"]
        case_id = options["case"]

        try:
            if options["verify"]:
                payload = verify_prepared_case(
                    run_id,
                    case_id,
                    exit_code=options["exit_code"],
                    prepare_only=options["prepare_only"],
                )
            else:
                payload = prepare_executor_case(run_id, case_id).__dict__
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(payload, sort_keys=True))
