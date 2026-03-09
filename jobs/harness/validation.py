from __future__ import annotations

import csv
import fnmatch
import gzip
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from django.core.exceptions import ValidationError

from model_types.parsers import parse_fasta_batch


VALID_ARTIFACT_VALIDATORS = {
    "csv",
    "fasta",
    "json",
    "structure_file",
    "text_nonempty",
    "zip_members",
}

NUCLEIC_ACID_RESNAMES = {
    "A",
    "C",
    "G",
    "U",
    "DA",
    "DC",
    "DG",
    "DT",
}


@dataclass(frozen=True)
class ArtifactCheck:
    patterns: list[str]
    validator: str = "text_nonempty"
    min_size_bytes: int = 1
    required_members: list[str | list[str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "patterns": list(self.patterns),
            "validator": self.validator,
            "min_size_bytes": self.min_size_bytes,
            "required_members": [
                list(item) if isinstance(item, list) else item
                for item in self.required_members
            ],
        }


def ensure_artifact_check(value: ArtifactCheck | dict[str, Any]) -> ArtifactCheck:
    if isinstance(value, ArtifactCheck):
        return value
    return ArtifactCheck(
        patterns=list(value.get("patterns", [])),
        validator=value.get("validator", "text_nonempty"),
        min_size_bytes=int(value.get("min_size_bytes", 1)),
        required_members=list(value.get("required_members", [])),
    )


def output_matches_patterns(file_name: str, patterns: list[str]) -> bool:
    expanded_patterns = set(patterns)
    expanded_patterns.update(
        pattern[3:] for pattern in patterns if pattern.startswith("**/")
    )
    return any(fnmatch.fnmatch(file_name, pattern) for pattern in expanded_patterns)


def matching_output_files(
    output_files: list[dict[str, Any]],
    patterns: list[str],
) -> list[dict[str, Any]]:
    return [
        item
        for item in output_files
        if output_matches_patterns(item["name"], patterns)
    ]


def format_requirement(requirement: str | list[str]) -> str:
    patterns = requirement if isinstance(requirement, list) else [requirement]
    return ", ".join(patterns)


def iter_expected_matches(
    file_names: list[str],
    expected_outputs: list[str | list[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    matches: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, requirement in enumerate(expected_outputs, start=1):
        patterns = requirement if isinstance(requirement, list) else [requirement]
        matched = [
            name for name in file_names if output_matches_patterns(name, patterns)
        ]
        if not matched:
            errors.append(
                f"Missing expected output requirement {index}: {format_requirement(requirement)}"
            )
        matches.append({"patterns": patterns, "matched": matched})
    return matches, errors


def validate_artifact_bytes(
    name: str,
    content: bytes,
    *,
    validator: str,
    required_members: list[str | list[str]] | None = None,
) -> list[str]:
    required_members = required_members or []
    if validator == "text_nonempty":
        return _validate_text_nonempty(content)
    if validator == "json":
        return _validate_json(content)
    if validator == "csv":
        return _validate_csv(content)
    if validator == "fasta":
        return _validate_fasta(content)
    if validator == "structure_file":
        return _validate_structure_file(name, content)
    if validator == "zip_members":
        return _validate_zip_members(content, required_members)
    return [f"Unknown artifact validator: {validator}"]


def validate_artifact_path(path: Path, check: ArtifactCheck) -> list[str]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        return [f"Could not read {path.name}: {exc}"]
    return validate_artifact_bytes(
        path.name,
        content,
        validator=check.validator,
        required_members=check.required_members,
    )


def evaluate_artifact_checks(
    output_files: list[dict[str, Any]],
    artifact_checks: list[ArtifactCheck | dict[str, Any]],
    validate_candidate: Callable[[dict[str, Any], ArtifactCheck], list[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    reports: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, raw_check in enumerate(artifact_checks, start=1):
        check = ensure_artifact_check(raw_check)
        report = {
            **check.as_dict(),
            "ok": False,
            "matched": [],
            "validated_file": None,
            "validated_size_bytes": None,
            "errors": [],
            "candidate_results": [],
        }
        candidates = matching_output_files(output_files, check.patterns)
        report["matched"] = [
            {
                "name": candidate["name"],
                "size_bytes": int(candidate.get("size", 0)),
            }
            for candidate in candidates
        ]
        if not candidates:
            report["errors"].append(
                f"Missing artifact check {index}: {format_requirement(check.patterns)}"
            )
            reports.append(report)
            errors.extend(report["errors"])
            continue

        for candidate in candidates:
            size_bytes = int(candidate.get("size", 0))
            candidate_errors: list[str] = []
            if size_bytes < check.min_size_bytes:
                candidate_errors.append(
                    f"{candidate['name']} smaller than minimum size {check.min_size_bytes} bytes"
                )
            else:
                candidate_errors.extend(validate_candidate(candidate, check))

            candidate_report = {
                "name": candidate["name"],
                "size_bytes": size_bytes,
                "ok": not candidate_errors,
                "errors": candidate_errors,
            }
            report["candidate_results"].append(candidate_report)
            if candidate_report["ok"] and report["validated_file"] is None:
                report["ok"] = True
                report["validated_file"] = candidate["name"]
                report["validated_size_bytes"] = size_bytes

        if not report["ok"]:
            for candidate_report in report["candidate_results"]:
                report["errors"].extend(candidate_report["errors"])
            if not report["errors"]:
                report["errors"].append(
                    f"No valid artifact matched {format_requirement(check.patterns)}"
                )
            errors.extend(report["errors"])

        reports.append(report)

    return reports, errors


def inspect_structure_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8", errors="ignore")
    if suffix not in {".pdb", ".cif", ".mmcif"}:
        raise ValueError(f"Unsupported structure fixture format: {path.name}")
    if suffix in {".cif", ".mmcif"}:
        raise ValueError(
            f"Semantic fixture validation currently supports only PDB inputs: {path.name}"
        )
    return _parse_pdb_structure(text)


def _validate_text_nonempty(content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="ignore")
    if not text.strip():
        return ["File is empty or whitespace only"]
    return []


def _validate_json(content: bytes) -> list[str]:
    text_errors = _validate_text_nonempty(content)
    if text_errors:
        return text_errors
    try:
        json.loads(content.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"Invalid JSON: {exc}"]
    return []


def _validate_csv(content: bytes) -> list[str]:
    text_errors = _validate_text_nonempty(content)
    if text_errors:
        return text_errors

    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return [f"CSV is not valid UTF-8: {exc}"]

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ["CSV contains no rows"]
    if not any(cell.strip() for cell in rows[0]):
        return ["CSV header row is empty"]
    if len(rows) < 2:
        return ["CSV must contain at least one data row"]
    if not any(any(cell.strip() for cell in row) for row in rows[1:]):
        return ["CSV data rows are empty"]
    return []


def _validate_fasta(content: bytes) -> list[str]:
    text_errors = _validate_text_nonempty(content)
    if text_errors:
        return text_errors

    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return [f"FASTA is not valid UTF-8: {exc}"]

    try:
        entries = parse_fasta_batch(text)
    except (ValidationError, ValueError) as exc:
        return [f"Invalid FASTA: {exc}"]

    if not entries:
        return ["FASTA contains no sequences"]
    return []


def _validate_structure_file(name: str, content: bytes) -> list[str]:
    lower_name = name.lower()
    if lower_name.endswith(".gz"):
        try:
            content = gzip.decompress(content)
        except OSError as exc:
            return [f"Invalid gzip-compressed structure file: {exc}"]
        name = name[:-3]

    text_errors = _validate_text_nonempty(content)
    if text_errors:
        return text_errors

    text = content.decode("utf-8", errors="ignore")
    lower_name = name.lower()
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ["Structure file contains no records"]

    if lower_name.endswith((".cif", ".mmcif")) or text.lstrip().startswith("data_"):
        if not any(line.startswith("data_") for line in lines):
            return ["mmCIF file is missing a data_ block"]
        if not (
            any("_atom_site." in line for line in lines)
            or any(line.startswith(("ATOM", "HETATM")) for line in lines)
        ):
            return ["mmCIF file does not contain atom records"]
        return []

    if not any(line.startswith(("ATOM", "HETATM")) for line in lines):
        return ["PDB file does not contain ATOM or HETATM records"]
    return []


def _validate_zip_members(
    content: bytes,
    required_members: list[str | list[str]],
) -> list[str]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        return [f"Invalid zip archive: {exc}"]

    errors: list[str] = []
    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if not members:
            return ["Zip archive contains no files"]

        for index, requirement in enumerate(required_members, start=1):
            patterns = requirement if isinstance(requirement, list) else [requirement]
            matches = [
                info
                for info in members
                if output_matches_patterns(info.filename, patterns)
            ]
            if not matches:
                errors.append(
                    f"Missing required archive member {index}: {format_requirement(requirement)}"
                )
                continue

            matched_ok = False
            match_errors: list[str] = []
            for info in matches:
                if info.file_size < 1:
                    match_errors.append(f"{info.filename} is empty inside archive")
                    continue

                member_validator = _archive_member_validator(info.filename)
                if member_validator is None:
                    matched_ok = True
                    break

                member_errors = validate_artifact_bytes(
                    info.filename,
                    archive.read(info),
                    validator=member_validator,
                    required_members=[],
                )
                if member_errors:
                    match_errors.extend(
                        f"{info.filename}: {message}" for message in member_errors
                    )
                    continue

                matched_ok = True
                break

            if not matched_ok:
                errors.extend(match_errors or [
                    f"Archive members for {format_requirement(requirement)} did not validate"
                ])

    return errors


def _archive_member_validator(name: str) -> str | None:
    lower_name = name.lower()
    if lower_name.endswith(".gz"):
        lower_name = lower_name[:-3]
    if lower_name.endswith((".fa", ".fasta")):
        return "fasta"
    if lower_name.endswith(".json"):
        return "json"
    if lower_name.endswith(".csv"):
        return "csv"
    if lower_name.endswith((".pdb", ".cif", ".mmcif")):
        return "structure_file"
    if lower_name.endswith((".txt", ".log", ".out", ".err")):
        return "text_nonempty"
    return None


def _parse_pdb_structure(text: str) -> dict[str, Any]:
    chains: dict[str, dict[str, Any]] = {}
    ligands: set[str] = set()

    for raw_line in text.splitlines():
        if not raw_line.startswith(("ATOM", "HETATM")):
            continue

        record = raw_line[:6].strip()
        resname = raw_line[17:20].strip()
        chain = (raw_line[21:22].strip() or "_")
        residue_token = raw_line[22:26].strip()
        try:
            residue_number = int(residue_token)
        except ValueError:
            continue

        chain_info = chains.setdefault(
            chain,
            {
                "atom_residues": set(),
                "hetero_residues": set(),
                "polymer_resnames": set(),
            },
        )
        if record == "ATOM":
            chain_info["atom_residues"].add(residue_number)
            chain_info["polymer_resnames"].add(resname)
        else:
            chain_info["hetero_residues"].add(residue_number)
            ligands.add(resname)

    nucleic_acid_chains = {
        chain
        for chain, info in chains.items()
        if info["polymer_resnames"] & NUCLEIC_ACID_RESNAMES
    }
    return {
        "chains": chains,
        "ligands": ligands,
        "nucleic_acid_chains": nucleic_acid_chains,
    }
