from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from jobs.harness.validation import (
    ArtifactCheck,
    VALID_ARTIFACT_VALIDATORS,
    ensure_artifact_check,
    inspect_structure_file,
    validate_artifact_bytes,
)
from model_types import get_submittable_model_types


MANIFEST_PATH = Path(settings.BASE_DIR) / "harness" / "cases.yaml"
FIXTURE_ROOT = Path(settings.BASE_DIR) / "harness" / "fixtures"

TRANSPORT_ALIASES = {
    "direct": "executor",
    "materialize_only": "prepare_only",
}
VALID_TRANSPORTS = {"web", "api", "executor", "prepare_only"}


@dataclass(frozen=True)
class HarnessCase:
    id: str
    tier: str
    model_key: str
    transport: str
    fields: dict[str, Any]
    files: dict[str, str]
    artifact_checks: list[ArtifactCheck]
    timeout_sec: int
    requires: list[str]

    @property
    def expected_outputs(self) -> list[str | list[str]]:
        expected: list[str | list[str]] = []
        for check in self.artifact_checks:
            if len(check.patterns) == 1:
                expected.append(check.patterns[0])
            else:
                expected.append(list(check.patterns))
        return expected


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _normalize_transport(transport: str) -> str:
    return TRANSPORT_ALIASES.get(transport, transport)


def _artifact_checks_from_item(item: dict[str, Any]) -> list[ArtifactCheck]:
    raw_checks = item.get("artifact_checks")
    if raw_checks is None:
        raw_checks = [
            {"patterns": requirement, "validator": "text_nonempty"}
            for requirement in item.get("expected_outputs", [])
        ]
    return [ensure_artifact_check(check) for check in raw_checks]


@lru_cache(maxsize=1)
def load_cases() -> list[HarnessCase]:
    manifest = _read_yaml(MANIFEST_PATH)
    raw_cases = manifest.get("cases", [])
    cases = [
        HarnessCase(
            id=item["id"],
            tier=item["tier"],
            model_key=item["model_key"],
            transport=_normalize_transport(item["transport"]),
            fields=item.get("fields", {}),
            files=item.get("files", {}),
            artifact_checks=_artifact_checks_from_item(item),
            timeout_sec=int(item.get("timeout_sec", 900)),
            requires=list(item.get("requires", [])),
        )
        for item in raw_cases
    ]
    _validate_cases(cases)
    return cases


def _validate_cases(cases: list[HarnessCase]) -> None:
    seen_ids: set[str] = set()
    for case in cases:
        if case.id in seen_ids:
            raise ValueError(f"Duplicate harness case id: {case.id}")
        seen_ids.add(case.id)
        if case.transport not in VALID_TRANSPORTS:
            raise ValueError(f"Invalid transport {case.transport!r} for {case.id}")
        if case.tier not in {"smoke", "extended"}:
            raise ValueError(f"Invalid tier {case.tier!r} for {case.id}")

        for index, check in enumerate(case.artifact_checks, start=1):
            if not check.patterns:
                raise ValueError(
                    f"Artifact check {index} for {case.id} must define at least one pattern"
                )
            if check.validator not in VALID_ARTIFACT_VALIDATORS:
                raise ValueError(
                    f"Artifact check {index} for {case.id} uses unknown validator {check.validator!r}"
                )
            if check.min_size_bytes < 1:
                raise ValueError(
                    f"Artifact check {index} for {case.id} must use min_size_bytes >= 1"
                )

    model_keys = {model_type.key for model_type in get_submittable_model_types()}
    for case in cases:
        if case.model_key not in model_keys:
            raise ValueError(f"Unknown model key {case.model_key!r} in harness manifest")

    for model_key in model_keys:
        smoke_cases = [
            case
            for case in cases
            if case.model_key == model_key and case.tier == "smoke"
        ]
        if len(smoke_cases) != 1:
            raise ValueError(
                f"Expected exactly one smoke case for {model_key}, found {len(smoke_cases)}"
            )
        if not smoke_cases[0].artifact_checks:
            raise ValueError(
                f"Smoke case {smoke_cases[0].id} must define at least one artifact_check"
            )

    _validate_case_fixtures(cases)


def get_case(case_id: str) -> HarnessCase:
    for case in load_cases():
        if case.id == case_id:
            return case
    raise KeyError(case_id)


def select_cases(*, tier: str, case_id: str | None = None) -> list[HarnessCase]:
    if case_id:
        case = get_case(case_id)
        if tier == "smoke" and case.tier != "smoke":
            raise ValueError(f"Case {case_id} is not a smoke case")
        return [case]

    cases = [case for case in load_cases() if case.tier == "smoke"]
    if tier == "extended":
        cases.extend(case for case in load_cases() if case.tier == "extended")
    return cases


def fixture_path(relative_path: str) -> Path:
    path = FIXTURE_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Missing harness fixture: {relative_path}")
    return path


def resolve_case_fields(case: HarnessCase) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in case.fields.items():
        if isinstance(value, dict) and "fixture_text" in value:
            resolved[key] = fixture_path(value["fixture_text"]).read_text(
                encoding="utf-8"
            )
        else:
            resolved[key] = value
    return resolved


def submission_data_from_fields(fields: dict[str, Any]) -> dict[str, str]:
    data: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                data[key] = "on"
            continue
        if isinstance(value, (dict, list)):
            data[key] = json.dumps(value)
        else:
            data[key] = str(value)
    return data


def upload_files_for_case(case: HarnessCase) -> dict[str, SimpleUploadedFile]:
    uploads: dict[str, SimpleUploadedFile] = {}
    for field_name, relative_path in case.files.items():
        path = fixture_path(relative_path)
        uploads[field_name] = SimpleUploadedFile(path.name, path.read_bytes())
    return uploads


def api_payload_for_case(case: HarnessCase) -> dict[str, Any]:
    payload = resolve_case_fields(case)
    payload["model"] = case.model_key
    if "name" not in payload:
        payload["name"] = f"Harness {case.id}"
    return payload


def _validate_case_fixtures(cases: list[HarnessCase]) -> None:
    structure_cache: dict[str, dict[str, Any]] = {}

    for case in cases:
        for value in case.fields.values():
            if isinstance(value, dict) and "fixture_text" in value:
                relative_path = value["fixture_text"]
                path = fixture_path(relative_path)
                _validate_fixture_content(relative_path, path)

        for relative_path in case.files.values():
            path = fixture_path(relative_path)
            _validate_fixture_content(relative_path, path)

        _validate_case_semantics(case, structure_cache)


def _validate_fixture_content(relative_path: str, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".fa", ".fasta"}:
        errors = validate_artifact_bytes(
            path.name,
            path.read_bytes(),
            validator="fasta",
        )
    elif suffix == ".json":
        errors = validate_artifact_bytes(
            path.name,
            path.read_bytes(),
            validator="json",
        )
    elif suffix == ".csv":
        errors = validate_artifact_bytes(
            path.name,
            path.read_bytes(),
            validator="csv",
        )
    elif suffix in {".pdb", ".cif", ".mmcif"}:
        errors = validate_artifact_bytes(
            path.name,
            path.read_bytes(),
            validator="structure_file",
        )
    elif suffix in {".yaml", ".yml"}:
        try:
            with path.open("r", encoding="utf-8") as handle:
                yaml.safe_load(handle)
            errors = []
        except yaml.YAMLError as exc:
            errors = [f"Invalid YAML: {exc}"]
    else:
        errors = []

    if errors:
        raise ValueError(f"Invalid harness fixture {relative_path}: {errors[0]}")


def _validate_case_semantics(
    case: HarnessCase,
    structure_cache: dict[str, dict[str, Any]],
) -> None:
    if case.model_key == "bindcraft":
        info = _structure_info(case.files["pdb_file"], structure_cache)
        chain = str(case.fields.get("target_chain", "A")).strip()
        _ensure_chain(case.id, info, chain, "target_chain")
        hotspots = _parse_integer_list(str(case.fields.get("hotspot_residues", "")))
        _ensure_residues(case.id, info, chain, hotspots, "hotspot_residues")
        return

    if case.model_key == "protein_mpnn":
        info = _structure_info(case.files["pdb_file"], structure_cache)
        for chain in _parse_chain_list(str(case.fields.get("chains_to_design", ""))):
            _ensure_chain(case.id, info, chain, "chains_to_design")
        fixed_residues = _parse_integer_list(str(case.fields.get("fixed_residues", "")), separators=" ")
        if fixed_residues:
            target_chains = _parse_chain_list(str(case.fields.get("chains_to_design", ""))) or ["A"]
            for chain in target_chains:
                _ensure_residues(case.id, info, chain, fixed_residues, "fixed_residues")
        return

    if case.model_key == "ligand_mpnn":
        info = _structure_info(case.files["pdb_file"], structure_cache)
        if not info["ligands"]:
            raise ValueError(f"{case.id}: ligand_mpnn fixture must include at least one ligand")
        for chain in _parse_chain_list(str(case.fields.get("chains_to_design", ""))):
            _ensure_chain(case.id, info, chain, "chains_to_design")
        fixed_residues = _parse_integer_list(str(case.fields.get("fixed_residues", "")), separators=" ")
        if fixed_residues:
            target_chains = _parse_chain_list(str(case.fields.get("chains_to_design", ""))) or ["A"]
            for chain in target_chains:
                _ensure_residues(case.id, info, chain, fixed_residues, "fixed_residues")
        return

    if case.model_key == "boltzgen":
        protocol = str(case.fields.get("protocol", "protein-anything"))
        if protocol != "yaml_upload":
            info = _structure_info(case.files["target_file"], structure_cache)
            for chain in _parse_chain_list(str(case.fields.get("target_chains", "A"))):
                _ensure_chain(case.id, info, chain, "target_chains")
        return

    if case.model_key != "rfdiffusion3":
        return

    mode = str(case.fields.get("mode", "unconditional"))
    if mode == "protein_binder":
        info = _structure_info(case.files["target_pdb"], structure_cache)
        chain = str(case.fields.get("target_chain", "A")).strip()
        _ensure_chain(case.id, info, chain, "target_chain")
        refs = _parse_chain_residue_refs(str(case.fields.get("hotspot_residues", "")))
        _ensure_named_residues(case.id, info, refs, "hotspot_residues")
        return

    if mode == "small_molecule_binder":
        info = _structure_info(case.files["sm_target_pdb"], structure_cache)
        _ensure_ligand(
            case.id,
            info,
            str(case.fields.get("sm_ligand_name", "")).strip(),
            "sm_ligand_name",
        )
        return

    if mode == "nucleic_acid_binder":
        info = _structure_info(case.files["na_target_pdb"], structure_cache)
        chain = str(case.fields.get("na_target_chain", "B")).strip()
        _ensure_chain(case.id, info, chain, "na_target_chain")
        if chain not in info["nucleic_acid_chains"]:
            raise ValueError(
                f"{case.id}: chain {chain!r} referenced by na_target_chain is not a nucleic acid chain"
            )
        return

    if mode == "enzyme":
        info = _structure_info(case.files["enzyme_target_pdb"], structure_cache)
        _ensure_ligand(
            case.id,
            info,
            str(case.fields.get("enzyme_ligand_name", "")).strip(),
            "enzyme_ligand_name",
        )
        refs = _parse_chain_residue_refs(
            str(case.fields.get("enzyme_catalytic_residues", ""))
        )
        _ensure_named_residues(case.id, info, refs, "enzyme_catalytic_residues")
        return

    if mode == "motif":
        info = _structure_info(case.files["motif_input_pdb"], structure_cache)
        refs = _parse_contig_refs(str(case.fields.get("motif_contig", "")))
        _ensure_named_residues(case.id, info, refs, "motif_contig")
        return

    if mode == "partial":
        info = _structure_info(case.files["partial_input_pdb"], structure_cache)
        refs = _parse_contig_refs(str(case.fields.get("partial_contig", "")))
        _ensure_named_residues(case.id, info, refs, "partial_contig")


def _structure_info(
    relative_path: str,
    structure_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cached = structure_cache.get(relative_path)
    if cached is not None:
        return cached
    path = fixture_path(relative_path)
    info = inspect_structure_file(path)
    structure_cache[relative_path] = info
    return info


def _parse_chain_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_integer_list(value: str, separators: str = ",") -> list[int]:
    if not value.strip():
        return []
    if separators == " ":
        tokens = value.split()
    else:
        splitter = f"[{re.escape(separators)}]+"
        tokens = re.split(splitter, value)
    result = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        result.append(int(token))
    return result


def _parse_chain_residue_refs(value: str) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        match = re.fullmatch(r"([A-Za-z0-9])(\d+)", token)
        if not match:
            raise ValueError(f"Invalid chain residue reference: {token!r}")
        refs.append((match.group(1), int(match.group(2))))
    return refs


def _parse_contig_refs(value: str) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for token in value.split(","):
        token = token.strip()
        if not token or token[0].isdigit():
            continue
        match = re.fullmatch(r"([A-Za-z0-9])(\d+)(?:-(\d+))?", token)
        if not match:
            raise ValueError(f"Invalid contig token: {token!r}")
        chain = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3) or start)
        refs.extend((chain, residue) for residue in range(start, end + 1))
    return refs


def _ensure_chain(
    case_id: str,
    info: dict[str, Any],
    chain: str,
    field_name: str,
) -> None:
    if chain not in info["chains"]:
        raise ValueError(f"{case_id}: chain {chain!r} referenced by {field_name} is missing")


def _ensure_residues(
    case_id: str,
    info: dict[str, Any],
    chain: str,
    residues: list[int],
    field_name: str,
) -> None:
    if not residues:
        return
    _ensure_chain(case_id, info, chain, field_name)
    chain_residues = info["chains"][chain]["atom_residues"]
    missing = sorted(residue for residue in residues if residue not in chain_residues)
    if missing:
        raise ValueError(
            f"{case_id}: residues {missing} referenced by {field_name} are missing from chain {chain}"
        )


def _ensure_named_residues(
    case_id: str,
    info: dict[str, Any],
    refs: list[tuple[str, int]],
    field_name: str,
) -> None:
    grouped: dict[str, list[int]] = {}
    for chain, residue in refs:
        grouped.setdefault(chain, []).append(residue)
    for chain, residues in grouped.items():
        _ensure_residues(case_id, info, chain, residues, field_name)


def _ensure_ligand(
    case_id: str,
    info: dict[str, Any],
    ligand_name: str,
    field_name: str,
) -> None:
    if ligand_name not in info["ligands"]:
        raise ValueError(
            f"{case_id}: ligand {ligand_name!r} referenced by {field_name} is missing"
        )
