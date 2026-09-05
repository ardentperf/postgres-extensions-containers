#!/usr/bin/env python3
"""Verify a composed SBOM against a BuildKit local-export filesystem."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def normalized_name(name: str) -> str:
    name = name.lstrip("/")
    if not name or name == "." or name.startswith("../") or "/../" in name:
        raise ValueError(f"invalid filesystem path {name!r}")
    return name


def buildkit_subjects(document: dict[str, Any], path: Path) -> dict[str, str]:
    subjects = document.get("subject")
    if not isinstance(subjects, list) or not subjects:
        raise ValueError(f"{path}: expected a non-empty BuildKit subject array")

    result: dict[str, str] = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            raise ValueError(f"{path}: every subject must be an object")
        name = subject.get("name")
        digests = subject.get("digest")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}: every subject needs a name")
        if not isinstance(digests, dict) or not digests:
            raise ValueError(f"{path}: subject {name!r} needs a digest")
        value = digests.get("sha256")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{path}: subject {name!r} needs a sha256 digest")
        name = normalized_name(name)
        if name in result:
            raise ValueError(f"{path}: duplicate subject {name!r}")
        result[name] = value.lower()
    return result


def exported_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        # The local exporter places these attestation artifacts beside the
        # final root filesystem. They are not files in the scratch image.
        if len(Path(name).parts) == 1 and (
            name == "provenance.json"
            or name.endswith(".dockerbuild")
            or name.startswith("sbom") and name.endswith(".spdx.json")
        ):
            continue
        if name in result:
            raise ValueError(f"duplicate exported file {name!r}")
        result[name] = path
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spdx_checksum(file_record: dict[str, Any]) -> str:
    checksums = file_record.get("checksums")
    if not isinstance(checksums, list):
        raise ValueError(f"file {file_record.get('fileName')!r} has no checksums")
    for checksum in checksums:
        if (
            isinstance(checksum, dict)
            and checksum.get("algorithm", "").upper() == "SHA256"
            and isinstance(checksum.get("checksumValue"), str)
        ):
            return checksum["checksumValue"].lower()
    raise ValueError(f"file {file_record.get('fileName')!r} has no SHA256 checksum")


def verify(root: Path, builder_path: Path, composed_path: Path) -> tuple[int, int]:
    builder = read_json(builder_path)
    subjects = buildkit_subjects(builder, builder_path)
    actual = exported_files(root)
    if set(actual) != set(subjects):
        missing = sorted(set(subjects) - set(actual))
        extra = sorted(set(actual) - set(subjects))
        raise ValueError(f"filesystem/subject mismatch: missing={missing}, extra={extra}")

    composed = read_json(composed_path)
    packages = composed.get("packages")
    files = composed.get("files")
    relationships = composed.get("relationships")
    document_id = composed.get("SPDXID")
    if not isinstance(packages, list) or not isinstance(files, list):
        raise ValueError(f"{composed_path}: SPDX document has invalid packages/files")
    if not isinstance(relationships, list) or not isinstance(document_id, str):
        raise ValueError(f"{composed_path}: SPDX document has invalid relationships/document ID")

    package_ids = {
        package["SPDXID"]
        for package in packages
        if isinstance(package, dict) and isinstance(package.get("SPDXID"), str)
    }
    file_by_name: dict[str, dict[str, Any]] = {}
    file_ids: set[str] = set()
    for file_record in files:
        if not isinstance(file_record, dict):
            raise ValueError(f"{composed_path}: file records must be objects")
        file_id = file_record.get("SPDXID")
        name = file_record.get("fileName")
        if not isinstance(file_id, str) or not isinstance(name, str):
            raise ValueError(f"{composed_path}: every file needs SPDXID and fileName")
        name = normalized_name(name)
        if name in file_by_name or file_id in file_ids:
            raise ValueError(f"{composed_path}: duplicate file {name!r} or {file_id!r}")
        file_by_name[name] = file_record
        file_ids.add(file_id)

    if set(file_by_name) != set(subjects):
        raise ValueError(
            "composed SPDX/subject mismatch: "
            f"missing={sorted(set(subjects) - set(file_by_name))}, "
            f"extra={sorted(set(file_by_name) - set(subjects))}"
        )

    for name, file_record in file_by_name.items():
        expected = subjects[name]
        actual_digest = sha256(actual[name])
        recorded_digest = spdx_checksum(file_record)
        if actual_digest != expected or recorded_digest != actual_digest:
            raise ValueError(
                f"checksum mismatch for {name}: "
                f"subject={expected}, SPDX={recorded_digest}, filesystem={actual_digest}"
            )

    package_owners: defaultdict[str, set[str]] = defaultdict(set)
    known_ids = package_ids | file_ids | {document_id}
    for relationship in relationships:
        if not isinstance(relationship, dict):
            raise ValueError(f"{composed_path}: relationship records must be objects")
        element_id = relationship.get("spdxElementId")
        related_id = relationship.get("relatedSpdxElement")
        if element_id not in known_ids or related_id not in known_ids:
            raise ValueError(
                f"{composed_path}: dangling relationship {element_id!r} -> {related_id!r}"
            )
        if (
            relationship.get("relationshipType") == "CONTAINS"
            and related_id in file_ids
            and element_id in package_ids
        ):
            package_owners[related_id].add(element_id)

    for file_id in file_ids:
        if not package_owners[file_id]:
            raise ValueError(f"{composed_path}: file {file_id} has no package owner")

    synthetic_packages = [
        package.get("SPDXID")
        for package in packages
        if isinstance(package, dict) and package.get("primaryPackagePurpose") == "FILE"
    ]
    if synthetic_packages:
        raise ValueError(f"{composed_path}: synthetic root packages remain: {synthetic_packages}")

    return len(files), len(packages)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a composed SPDX document against a BuildKit local export"
    )
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--builder-sbom", type=Path, required=True)
    parser.add_argument("--composed-sbom", type=Path, required=True)
    args = parser.parse_args()

    try:
        file_count, package_count = verify(
            args.rootfs,
            args.builder_sbom,
            args.composed_sbom,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"verify_local_sbom.py: {error}", file=sys.stderr)
        return 1
    print(f"verified {file_count} files and {package_count} packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
