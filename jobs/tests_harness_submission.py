from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from api.models import APIKey
from console.services.quota import get_user_quota
from jobs.harness import (
    api_payload_for_case,
    load_cases,
    resolve_case_fields,
    submission_data_from_fields,
    upload_files_for_case,
)
from jobs.models import Job
from jobs.services import _sanitize_payload_for_storage
from model_types import get_model_type


class SmokeCaseSubmissionParityTests(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.harness_dir = self.tmpdir / "harness"
        self.harness_dir.mkdir(parents=True, exist_ok=True)
        self.user = User.objects.create_user(
            username="harness-submit",
            password="testpass",
        )
        quota = get_user_quota(self.user)
        quota.api_enabled = True
        quota.jobs_per_day = 1000
        quota.max_queued_jobs = 100
        quota.save()
        self.api_key = APIKey.objects.create(user=self.user, label="harness")
        self.web_client = Client()
        self.web_client.force_login(self.user)
        self.api_client = Client()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_smoke_cases_submit_equivalently_via_web_and_api(self):
        smoke_cases = [case for case in load_cases() if case.tier == "smoke"]

        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
            ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
        ):
            for case in smoke_cases:
                with self.subTest(case=case.id):
                    expected = self._expected_submission(case)
                    web_job = self._submit_web_case(case)
                    api_job = self._submit_api_case(case)

                    self._assert_job_matches_expected(web_job, case, expected)
                    self._assert_job_matches_expected(api_job, case, expected)
                    self.assertEqual(web_job.runner, api_job.runner)
                    self.assertEqual(web_job.params, api_job.params)
                    self.assertEqual(web_job.input_payload, api_job.input_payload)

    def _expected_submission(self, case):
        model_type = get_model_type(case.model_key)
        fields = resolve_case_fields(case)
        uploads = upload_files_for_case(case)
        form = model_type.get_form(submission_data_from_fields(fields), uploads)
        self.assertTrue(form.is_valid(), form.errors)
        model_type.validate(form.cleaned_data)
        input_payload = model_type.normalize_inputs(form.cleaned_data)

        return {
            "runner": model_type.resolve_runner_key(form.cleaned_data),
            "sequences": input_payload.get("sequences", ""),
            "params": input_payload.get("params", {}),
            "storage_payload": _sanitize_payload_for_storage(input_payload),
            "input_files": sorted(input_payload.get("files", {}).keys()),
        }

    def _submit_web_case(self, case):
        existing_ids = set(Job.objects.values_list("id", flat=True))
        payload = submission_data_from_fields(resolve_case_fields(case))
        payload["model"] = case.model_key
        payload.update(upload_files_for_case(case))

        response = self.web_client.post(reverse("job_submit"), data=payload)

        self.assertEqual(response.status_code, 302, case.id)
        return Job.objects.exclude(id__in=existing_ids).get()

    def _submit_api_case(self, case):
        existing_ids = set(Job.objects.values_list("id", flat=True))
        payload = api_payload_for_case(case)
        uploads = upload_files_for_case(case)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.api_key.key}"}

        if uploads:
            multipart = {"data": json.dumps(payload)}
            multipart.update(uploads)
            response = self.api_client.post(
                reverse("api:job_create"),
                data=multipart,
                **headers,
            )
        else:
            response = self.api_client.post(
                reverse("api:job_create"),
                data=json.dumps(payload),
                content_type="application/json",
                **headers,
            )

        self.assertEqual(response.status_code, 201, case.id)
        return Job.objects.exclude(id__in=existing_ids).get()

    def _assert_job_matches_expected(self, job, case, expected):
        self.assertEqual(job.model_key, case.model_key)
        self.assertEqual(job.runner, expected["runner"])
        self.assertEqual(job.sequences, expected["sequences"])
        self.assertEqual(job.params, expected["params"])
        self.assertEqual(job.input_payload, expected["storage_payload"])

        if expected["sequences"]:
            self.assertTrue((job.workdir / "input" / "sequences.fasta").exists())
        for filename in expected["input_files"]:
            self.assertTrue((job.workdir / "input" / filename).exists(), filename)
