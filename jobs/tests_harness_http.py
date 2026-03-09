from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

from jobs.harness import get_case
from jobs.management.commands.harness_http import Command


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        content: bytes = b"",
        json_data=None,
        headers=None,
    ):
        self.status_code = status_code
        self.text = text
        self.content = content
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self, detail_text: str):
        self.detail_text = detail_text

    def get(self, url, timeout=30):
        return _FakeResponse(status_code=200, text=self.detail_text)


class HarnessHTTPCommandTests(SimpleTestCase):
    def test_submission_case_reports_validated_archive(self):
        command = Command()
        case = get_case("smoke-protein-mpnn")
        report = {"submission_checks": [], "errors": []}
        job_id = "00000000-0000-0000-0000-000000000111"
        archive_bytes = self._make_zip(
            {
                "seqs/sample_1.fa": b">designed\nACDEFGHIK\n",
                "backbones/sample_1.pdb": b"ATOM      1  CA  ALA A   1\n",
            }
        )

        command._submit_api_case = lambda *args, **kwargs: _FakeResponse(
            status_code=201,
            json_data={"job": {"id": job_id}},
        )
        command._poll_job = lambda *args, **kwargs: {
            "job": {
                "status": "COMPLETED",
                "output_files": [{"name": "results.zip", "size": len(archive_bytes)}],
            }
        }
        command._api_get = lambda requests, base_url, path, api_key: _FakeResponse(
            status_code=200,
            content=archive_bytes,
        )

        command._run_submission_case(
            object(),
            _FakeSession("results.zip"),
            "http://example.test/",
            {"api_key": "token"},
            case,
            report,
        )

        case_report = report["submission_checks"][0]
        self.assertTrue(case_report["ok"])
        self.assertEqual(case_report["validated_downloads"], ["results.zip"])
        self.assertEqual(case_report["artifact_reports"][0]["validated_file"], "results.zip")

    def test_submission_case_reports_invalid_archive_contents(self):
        command = Command()
        case = get_case("smoke-protein-mpnn")
        report = {"submission_checks": [], "errors": []}
        job_id = "00000000-0000-0000-0000-000000000222"
        archive_bytes = self._make_zip(
            {"backbones/sample_1.pdb": b"ATOM      1  CA  ALA A   1\n"}
        )

        command._submit_api_case = lambda *args, **kwargs: _FakeResponse(
            status_code=201,
            json_data={"job": {"id": job_id}},
        )
        command._poll_job = lambda *args, **kwargs: {
            "job": {
                "status": "COMPLETED",
                "output_files": [{"name": "results.zip", "size": len(archive_bytes)}],
            }
        }
        command._api_get = lambda requests, base_url, path, api_key: _FakeResponse(
            status_code=200,
            content=archive_bytes,
        )

        command._run_submission_case(
            object(),
            _FakeSession("results.zip"),
            "http://example.test/",
            {"api_key": "token"},
            case,
            report,
        )

        case_report = report["submission_checks"][0]
        self.assertFalse(case_report["ok"])
        self.assertIn("Missing required archive member", "\n".join(case_report["errors"]))

    def _make_zip(self, members: dict[str, bytes]) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
            with zipfile.ZipFile(handle.name, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            return Path(handle.name).read_bytes()
