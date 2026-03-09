from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

from jobs.harness.manifest import fixture_path
from jobs.harness.validation import (
    ArtifactCheck,
    evaluate_artifact_checks,
    inspect_structure_file,
    validate_artifact_bytes,
)


class TestHarnessArtifactValidators(SimpleTestCase):
    def test_text_nonempty_rejects_blank_content(self):
        errors = validate_artifact_bytes(
            "summary.txt",
            b"   \n",
            validator="text_nonempty",
        )
        self.assertEqual(errors, ["File is empty or whitespace only"])

    def test_json_rejects_invalid_document(self):
        errors = validate_artifact_bytes(
            "scores.json",
            b"{not-json}",
            validator="json",
        )
        self.assertTrue(errors)
        self.assertIn("Invalid JSON", errors[0])

    def test_csv_requires_a_data_row(self):
        errors = validate_artifact_bytes(
            "scores.csv",
            b"score,value\n",
            validator="csv",
        )
        self.assertEqual(errors, ["CSV must contain at least one data row"])

    def test_fasta_requires_valid_entries(self):
        errors = validate_artifact_bytes(
            "seqs.fa",
            b"ACDEFG",
            validator="fasta",
        )
        self.assertTrue(errors)
        self.assertIn("Invalid FASTA", errors[0])

    def test_structure_file_accepts_pdb_content(self):
        content = b"ATOM      1  CA  ALA A   1      11.0  13.2  10.3  1.00 20.00           C\n"
        errors = validate_artifact_bytes(
            "model.pdb",
            content,
            validator="structure_file",
        )
        self.assertEqual(errors, [])

    def test_structure_file_accepts_mmcif_content(self):
        content = b"data_test\nloop_\n_atom_site.group_PDB\nATOM\n"
        errors = validate_artifact_bytes(
            "model.cif",
            content,
            validator="structure_file",
        )
        self.assertEqual(errors, [])

    def test_structure_file_accepts_gzipped_mmcif_content(self):
        import gzip

        content = gzip.compress(b"data_test\nloop_\n_atom_site.group_PDB\nATOM\n")
        errors = validate_artifact_bytes(
            "model.cif.gz",
            content,
            validator="structure_file",
        )
        self.assertEqual(errors, [])

    def test_zip_members_validate_required_fasta(self):
        archive_bytes = self._make_zip(
            {
                "seqs/sample_1.fa": b">designed\nACDEFGHIK\n",
                "backbones/sample_1.pdb": b"ATOM      1  CA  ALA A   1\n",
            }
        )
        errors = validate_artifact_bytes(
            "results.zip",
            archive_bytes,
            validator="zip_members",
            required_members=[["seqs/*.fa", "seqs/*.fasta"]],
        )
        self.assertEqual(errors, [])

    def test_zip_members_accept_root_level_fasta(self):
        archive_bytes = self._make_zip(
            {
                "input.fa": b">designed\nACDEFGHIK\n",
                "input_b0_d0.cif": b"data_test\nloop_\n_atom_site.group_PDB\nATOM\n",
            }
        )
        errors = validate_artifact_bytes(
            "results.zip",
            archive_bytes,
            validator="zip_members",
            required_members=[["seqs/*.fa", "seqs/*.fasta", "*.fa", "*.fasta"]],
        )
        self.assertEqual(errors, [])

    def test_zip_members_report_missing_required_member(self):
        archive_bytes = self._make_zip(
            {"backbones/sample_1.pdb": b"ATOM      1  CA  ALA A   1\n"}
        )
        errors = validate_artifact_bytes(
            "results.zip",
            archive_bytes,
            validator="zip_members",
            required_members=[["seqs/*.fa", "seqs/*.fasta"]],
        )
        self.assertTrue(errors)
        self.assertIn("Missing required archive member", errors[0])

    def test_evaluate_artifact_checks_records_candidate_errors(self):
        output_files = [{"name": "results.zip", "size": 16, "payload": b"not-a-zip"}]
        reports, errors = evaluate_artifact_checks(
            output_files,
            [ArtifactCheck(patterns=["results.zip"], validator="zip_members")],
            lambda candidate, check: validate_artifact_bytes(
                candidate["name"],
                candidate["payload"],
                validator=check.validator,
                required_members=check.required_members,
            ),
        )

        self.assertFalse(reports[0]["ok"])
        self.assertTrue(errors)
        self.assertIn("Invalid zip archive", errors[0])

    def test_inspect_structure_file_tracks_ligands_and_nucleic_acids(self):
        ligand_info = inspect_structure_file(fixture_path("common/structures/ligand_complex.pdb"))
        na_info = inspect_structure_file(fixture_path("common/structures/backbone_ab.pdb"))

        self.assertIn("LIG", ligand_info["ligands"])
        self.assertIn("B", na_info["nucleic_acid_chains"])

    def _make_zip(self, members: dict[str, bytes]) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
            with zipfile.ZipFile(handle.name, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            return Path(handle.name).read_bytes()
