from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote, urljoin

from django.core.management.base import BaseCommand

from console.models import RunnerConfig, SiteSettings
from console.services.quota import get_user_quota
from jobs.harness import (
    api_payload_for_case,
    get_case,
    read_json,
    reports_dir_local,
    run_root_local,
    select_cases,
    upload_files_for_case,
    write_json,
)
from model_types import get_submittable_model_types


class Command(BaseCommand):
    help = "Run HTTP and API validation checks against the deployed app."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, help="Harness run identifier.")
        parser.add_argument(
            "--tier",
            choices=["smoke", "extended"],
            default="smoke",
            help="Harness tier to run.",
        )
        parser.add_argument("--case", default="", help="Optional single case id.")
        parser.add_argument(
            "--base-url",
            default="http://localhost:8000",
            help="Base URL for the deployed web app.",
        )

    def handle(self, *args, **options):
        import requests

        run_id = options["run_id"]
        tier = options["tier"]
        case_id = options["case"] or None
        base_url = options["base_url"].rstrip("/") + "/"
        prepare = read_json(run_root_local(run_id) / "prepare.json")
        cases = [
            case
            for case in select_cases(tier=tier, case_id=case_id)
            if case.tier == "smoke" and case.transport in {"web", "api"}
        ]

        report: dict[str, Any] = {
            "phase": "http",
            "run_id": run_id,
            "ok": True,
            "base_url": base_url.rstrip("/"),
            "checks": [],
            "submission_checks": [],
            "errors": [],
        }

        admin_meta = prepare["users"]["admin"]
        limited_meta = prepare["users"]["limited"]
        session = requests.Session()

        try:
            self._run_preflight(requests, session, base_url, admin_meta, report)
            self._run_negative_checks(requests, base_url, admin_meta, limited_meta, report)
            for case in cases:
                self._run_submission_case(
                    requests,
                    session,
                    base_url,
                    admin_meta,
                    case,
                    report,
                )
        finally:
            session.close()

        report["ok"] = not report["errors"]
        report_path = reports_dir_local(run_id) / "http.json"
        write_json(report_path, report)
        self.stdout.write(str(report_path))

    def _run_preflight(self, requests, session, base_url: str, admin_meta: dict[str, str], report: dict[str, Any]) -> None:
        model_types = get_submittable_model_types()
        login_page = session.get(urljoin(base_url, "login/"), timeout=30)
        self._record_check(
            report,
            "login-page",
            login_page.status_code == 200 and "csrfmiddlewaretoken" in login_page.text,
            {"status_code": login_page.status_code},
        )

        csrf_token = self._extract_csrf_token(login_page.text)
        login_response = session.post(
            urljoin(base_url, "login/"),
            data={
                "username": admin_meta["username"],
                "password": admin_meta["password"],
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": urljoin(base_url, "login/")},
            timeout=30,
            allow_redirects=True,
        )
        self._record_check(
            report,
            "login-session",
            login_response.status_code == 200 and "Logout" in login_response.text,
            {"status_code": login_response.status_code},
        )

        model_page = session.get(urljoin(base_url, "jobs/new/"), timeout=30)
        self._record_check(
            report,
            "model-selection-page",
            model_page.status_code == 200,
            {"status_code": model_page.status_code},
        )
        for model_type in model_types:
            page_ok = (
                model_type.name in model_page.text
                or f"model={model_type.key}" in model_page.text
            )
            self._record_check(
                report,
                f"model-listed:{model_type.key}",
                page_ok,
                {},
            )

        for model_type in model_types:
            submit_page = session.get(
                urljoin(base_url, f"jobs/new/?model={model_type.key}"),
                timeout=30,
            )
            form = model_type.get_form()
            expected_fields = list(form.fields.keys())
            missing_fields = [
                field_name
                for field_name in expected_fields
                if f'name="{field_name}"' not in submit_page.text
            ]
            self._record_check(
                report,
                f"submit-form:{model_type.key}",
                submit_page.status_code == 200 and not missing_fields,
                {
                    "status_code": submit_page.status_code,
                    "missing_fields": missing_fields,
                },
            )

        api_models = self._api_get(
            requests,
            base_url,
            "api/v1/models/",
            admin_meta["api_key"],
        )
        returned_models = sorted(model["key"] for model in api_models.json()["models"])
        expected_models = sorted(model_type.key for model_type in model_types)
        self._record_check(
            report,
            "api-model-list",
            api_models.status_code == 200 and returned_models == expected_models,
            {
                "status_code": api_models.status_code,
                "returned_models": returned_models,
            },
        )

    def _run_negative_checks(
        self,
        requests,
        base_url: str,
        admin_meta: dict[str, str],
        limited_meta: dict[str, str],
        report: dict[str, Any],
    ) -> None:
        bad_key = self._api_get(requests, base_url, "api/v1/models/", "not-a-real-key")
        self._record_check(
            report,
            "invalid-api-key",
            bad_key.status_code == 401,
            {"status_code": bad_key.status_code},
        )

        unknown_model = requests.post(
            urljoin(base_url, "api/v1/jobs/"),
            headers={
                "Authorization": f"Bearer {admin_meta['api_key']}",
                "Content-Type": "application/json",
            },
            data='{"model": "does-not-exist"}',
            timeout=30,
        )
        self._record_check(
            report,
            "unknown-model",
            unknown_model.status_code == 400,
            {"status_code": unknown_model.status_code},
        )

        malformed_json = requests.post(
            urljoin(base_url, "api/v1/jobs/"),
            headers={
                "Authorization": f"Bearer {admin_meta['api_key']}",
                "Content-Type": "application/json",
            },
            data='{"model": "boltz2"',
            timeout=30,
        )
        self._record_check(
            report,
            "malformed-json",
            malformed_json.status_code == 400,
            {"status_code": malformed_json.status_code},
        )

        site_settings = SiteSettings.get_settings()
        original_maintenance = site_settings.maintenance_mode
        original_message = site_settings.maintenance_message
        try:
            site_settings.maintenance_mode = True
            site_settings.maintenance_message = "Harness maintenance mode"
            site_settings.save()
            maintenance_response = requests.post(
                urljoin(base_url, "api/v1/jobs/"),
                headers={
                    "Authorization": f"Bearer {admin_meta['api_key']}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(api_payload_for_case(get_case("smoke-boltz2"))),
                timeout=30,
            )
            body = maintenance_response.json()
            self._record_check(
                report,
                "maintenance-rejection",
                maintenance_response.status_code == 400
                and "Harness maintenance mode" in body.get("error", ""),
                {"status_code": maintenance_response.status_code, "body": body},
            )
        finally:
            site_settings.maintenance_mode = original_maintenance
            site_settings.maintenance_message = original_message
            site_settings.save()

        config = RunnerConfig.get_config("boltz-2")
        original_enabled = config.enabled
        original_reason = config.disabled_reason
        try:
            config.enabled = False
            config.disabled_reason = "Harness disabled runner"
            config.save()
            disabled_response = requests.post(
                urljoin(base_url, "api/v1/jobs/"),
                headers={
                    "Authorization": f"Bearer {admin_meta['api_key']}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(api_payload_for_case(get_case("smoke-boltz2"))),
                timeout=30,
            )
            body = disabled_response.json()
            self._record_check(
                report,
                "disabled-runner-rejection",
                disabled_response.status_code == 400
                and "Runner is disabled" in body.get("error", ""),
                {"status_code": disabled_response.status_code, "body": body},
            )
        finally:
            config.enabled = original_enabled
            config.disabled_reason = original_reason
            config.save()

        limited_user = self._load_user(limited_meta["username"])
        quota = get_user_quota(limited_user)
        original_jobs_per_day = quota.jobs_per_day
        try:
            quota.jobs_per_day = 0
            quota.save(update_fields=["jobs_per_day"])
            limited_response = requests.post(
                urljoin(base_url, "api/v1/jobs/"),
                headers={
                    "Authorization": f"Bearer {limited_meta['api_key']}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(api_payload_for_case(get_case("smoke-boltz2"))),
                timeout=30,
            )
            body = limited_response.json()
            self._record_check(
                report,
                "quota-rejection",
                limited_response.status_code == 400
                and "maximum number of jobs per day" in body.get("error", ""),
                {"status_code": limited_response.status_code, "body": body},
            )
        finally:
            quota.jobs_per_day = original_jobs_per_day
            quota.save(update_fields=["jobs_per_day"])

    def _run_submission_case(
        self,
        requests,
        session,
        base_url: str,
        admin_meta: dict[str, str],
        case,
        report: dict[str, Any],
    ) -> None:
        if case.transport == "web":
            submission = self._submit_web_case(session, base_url, case)
        else:
            submission = self._submit_api_case(requests, base_url, admin_meta["api_key"], case)

        case_report: dict[str, Any] = {
            "case_id": case.id,
            "transport": case.transport,
            "status_code": submission.status_code,
            "ok": False,
            "job_id": None,
            "errors": [],
        }
        if submission.status_code not in {200, 201, 302}:
            case_report["errors"].append(
                f"Submission failed with HTTP {submission.status_code}"
            )
            report["submission_checks"].append(case_report)
            report["errors"].extend(
                f"{case.id}: {error}" for error in case_report["errors"]
            )
            return

        job_id = self._extract_job_id(submission)
        case_report["job_id"] = job_id
        if not job_id:
            case_report["errors"].append("Could not determine job id from submission response")
            report["submission_checks"].append(case_report)
            report["errors"].extend(
                f"{case.id}: {error}" for error in case_report["errors"]
            )
            return

        job_detail = self._poll_job(
            requests,
            base_url,
            admin_meta["api_key"],
            job_id,
            case.timeout_sec,
        )
        job_data = job_detail.get("job", {})
        if job_data.get("status") != "COMPLETED":
            case_report["errors"].append(
                f"Job finished with status {job_data.get('status')}: {job_data.get('error_message', '')}"
            )
            report["submission_checks"].append(case_report)
            report["errors"].extend(
                f"{case.id}: {error}" for error in case_report["errors"]
            )
            return

        output_files = [item["name"] for item in job_data.get("output_files", [])]
        matched_outputs, output_errors = self._match_expected_outputs(output_files, case.expected_outputs)
        case_report["matched_outputs"] = matched_outputs
        case_report["output_files"] = output_files
        case_report["errors"].extend(output_errors)

        downloaded = self._download_primary_output(
            requests,
            base_url,
            admin_meta["api_key"],
            job_id,
            output_files,
        )
        case_report["downloaded_file"] = downloaded
        if not downloaded:
            case_report["errors"].append("Could not download a primary output file")

        detail_page = session.get(urljoin(base_url, f"jobs/{job_id}/"), timeout=30)
        case_report["detail_page_ok"] = detail_page.status_code == 200
        if detail_page.status_code != 200:
            case_report["errors"].append(f"Detail page returned {detail_page.status_code}")
        elif output_files and not any(filename in detail_page.text for filename in output_files):
            case_report["errors"].append("Detail page did not render output filenames")

        log_errors = self._check_output_logs(
            requests,
            base_url,
            admin_meta["api_key"],
            job_id,
            output_files,
        )
        case_report["errors"].extend(log_errors)

        case_report["ok"] = not case_report["errors"]
        report["submission_checks"].append(case_report)
        if not case_report["ok"]:
            report["errors"].extend(
                f"{case.id}: {error}" for error in case_report["errors"]
            )

    def _submit_api_case(self, requests, base_url: str, api_key: str, case):
        payload = api_payload_for_case(case)
        files = upload_files_for_case(case)
        if files:
            multipart_files = {
                field_name: (upload.name, upload.read())
                for field_name, upload in files.items()
            }
            return requests.post(
                urljoin(base_url, "api/v1/jobs/"),
                headers={"Authorization": f"Bearer {api_key}"},
                data={"data": json.dumps(payload)},
                files=multipart_files,
                timeout=60,
            )
        return requests.post(
            urljoin(base_url, "api/v1/jobs/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=60,
        )

    def _submit_web_case(self, session, base_url: str, case):
        form_page = session.get(
            urljoin(base_url, f"jobs/new/?model={case.model_key}"),
            timeout=30,
        )
        csrf_token = self._extract_csrf_token(form_page.text)
        fields = api_payload_for_case(case)
        post_data = {
            key: value
            for key, value in fields.items()
            if key not in {"model"}
        }
        uploads = upload_files_for_case(case)
        multipart_files = {
            field_name: (upload.name, upload.read())
            for field_name, upload in uploads.items()
        }
        post_data["model"] = case.model_key
        post_data["csrfmiddlewaretoken"] = csrf_token
        return session.post(
            urljoin(base_url, "jobs/new/"),
            data=post_data,
            files=multipart_files,
            headers={"Referer": urljoin(base_url, f"jobs/new/?model={case.model_key}")},
            timeout=60,
            allow_redirects=False,
        )

    def _poll_job(
        self,
        requests,
        base_url: str,
        api_key: str,
        job_id: str,
        timeout_sec: int,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            response = self._api_get(
                requests,
                base_url,
                f"api/v1/jobs/{job_id}/",
                api_key,
            )
            payload = response.json()
            status = payload.get("job", {}).get("status")
            if status in {"COMPLETED", "FAILED"}:
                return payload
            time.sleep(5)
        return {"job": {"status": "TIMEOUT", "error_message": "Harness poll timeout"}}

    def _download_primary_output(
        self,
        requests,
        base_url: str,
        api_key: str,
        job_id: str,
        output_files: list[str],
    ) -> str | None:
        for filename in output_files:
            response = self._api_get(
                requests,
                base_url,
                f"api/v1/jobs/{job_id}/download/{quote(filename, safe='/')}",
                api_key,
            )
            if response.status_code == 200 and response.content:
                return filename
        return None

    def _check_output_logs(
        self,
        requests,
        base_url: str,
        api_key: str,
        job_id: str,
        output_files: list[str],
    ) -> list[str]:
        errors: list[str] = []
        for filename in output_files:
            if not filename.endswith((".log", ".out", ".err", ".txt")):
                continue
            response = self._api_get(
                requests,
                base_url,
                f"api/v1/jobs/{job_id}/download/{quote(filename, safe='/')}",
                api_key,
            )
            if response.status_code != 200:
                continue
            text = response.text.lower()
            if "traceback" in text:
                errors.append(f"Traceback found in output log {filename}")
        return errors

    def _api_get(self, requests, base_url: str, path: str, api_key: str):
        return requests.get(
            urljoin(base_url, path),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

    def _extract_csrf_token(self, html: str) -> str:
        match = re.search(
            r'name="csrfmiddlewaretoken"\s+value="([^"]+)"',
            html,
        )
        if not match:
            raise RuntimeError("Could not locate csrfmiddlewaretoken in response")
        return match.group(1)

    def _extract_job_id(self, response) -> str:
        if response.status_code == 201:
            return response.json().get("job", {}).get("id", "")
        location = response.headers.get("Location", "")
        match = re.search(r"/jobs/([0-9a-f-]+)/", location)
        return match.group(1) if match else ""

    def _match_expected_outputs(
        self,
        output_files: list[str],
        expected_outputs: list[str | list[str]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        from jobs.harness import _iter_expected_matches

        return _iter_expected_matches(output_files, expected_outputs)

    def _record_check(self, report: dict[str, Any], name: str, ok: bool, details: dict[str, Any]) -> None:
        report["checks"].append({"name": name, "ok": ok, "details": details})
        if not ok:
            report["errors"].append(name)

    def _load_user(self, username: str):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.get(username=username)
