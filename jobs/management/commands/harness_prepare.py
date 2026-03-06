from __future__ import annotations

import secrets
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.models import APIKey
from console.services.quota import get_user_quota
from jobs.harness import prepare_run_directories, run_root_local, select_cases, write_json

User = get_user_model()


class Command(BaseCommand):
    help = "Prepare users, API keys, and run metadata for the model validation harness."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, help="Stable identifier for this harness run.")
        parser.add_argument(
            "--tier",
            choices=["smoke", "extended"],
            default="smoke",
            help="Harness tier to prepare.",
        )
        parser.add_argument(
            "--phase",
            choices=["all", "http", "direct", "materialize"],
            default="all",
            help="Harness phase to prepare.",
        )
        parser.add_argument("--case", default="", help="Optional single case id to run.")
        parser.add_argument(
            "--base-url",
            default="http://localhost:8000",
            help="Base URL used by HTTP checks.",
        )

    def handle(self, *args, **options):
        run_id = options["run_id"]
        tier = options["tier"]
        phase = options["phase"]
        case_id = options["case"] or None
        base_url = options["base_url"].rstrip("/")

        try:
            selected = select_cases(tier=tier, case_id=case_id)
        except (KeyError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        directories = prepare_run_directories(run_id)
        admin_user, admin_password, admin_api_key = self._ensure_harness_user(
            username="harness_admin",
            is_staff=True,
            label="harness-admin",
        )
        limited_user, limited_password, limited_api_key = self._ensure_harness_user(
            username="harness_limited",
            is_staff=False,
            label="harness-limited",
        )

        direct_case_ids: list[str] = []
        materialize_case_ids: list[str] = []
        http_case_ids: list[str] = []

        if phase in {"all", "direct"}:
            direct_case_ids = [case.id for case in selected if case.tier == "smoke"]
            if tier == "extended":
                materialize_case_ids = [
                    case.id for case in selected if case.tier == "extended"
                ]
        elif phase == "materialize":
            materialize_case_ids = [case.id for case in selected]

        if phase in {"all", "http"}:
            http_case_ids = [
                case.id
                for case in selected
                if case.transport in {"web", "api"} and case.tier == "smoke"
            ]

        payload = {
            "run_id": run_id,
            "tier": tier,
            "phase": phase,
            "case": case_id,
            "base_url": base_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "directories": directories,
            "users": {
                "admin": {
                    "username": admin_user.username,
                    "password": admin_password,
                    "api_key": admin_api_key,
                },
                "limited": {
                    "username": limited_user.username,
                    "password": limited_password,
                    "api_key": limited_api_key,
                },
            },
            "selected_cases": [
                {
                    "id": case.id,
                    "tier": case.tier,
                    "model_key": case.model_key,
                    "transport": case.transport,
                }
                for case in selected
            ],
            "direct_case_ids": direct_case_ids,
            "materialize_case_ids": materialize_case_ids,
            "http_case_ids": http_case_ids,
        }
        prepare_path = run_root_local(run_id) / "prepare.json"
        write_json(prepare_path, payload)
        self.stdout.write(str(prepare_path))

    def _ensure_harness_user(
        self,
        *,
        username: str,
        is_staff: bool,
        label: str,
    ) -> tuple[User, str, str]:
        password = secrets.token_urlsafe(18)
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": is_staff},
        )
        user.is_staff = is_staff
        user.is_active = True
        user.set_password(password)
        user.save(update_fields=["is_staff", "is_active", "password"])

        quota = get_user_quota(user)
        quota.api_enabled = True
        if not is_staff:
            quota.is_disabled = False
            quota.disabled_reason = ""
        quota.save()

        APIKey.objects.filter(user=user).delete()
        api_key = APIKey.objects.create(user=user, label=label)
        return user, password, api_key.key
