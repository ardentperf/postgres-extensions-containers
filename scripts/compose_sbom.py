#!/usr/bin/env python3
"""Compose an SPDX predicate with builder packages and final-image files.

BuildKit's SBOM attestation for a multi-stage build contains two useful but
different views of the result: the selected builder stage is represented by
the SPDX predicate, while the attestation subject identifies the files in the
final image.  This module keeps the package inventory from the builder and
uses the final subjects to trim the file inventory and its relationships.
"""

from __future__ import annotations

import argparse
import copy
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


def predicate_from(document: dict[str, Any], path: Path) -> dict[str, Any]:
    predicate = document.get("predicate")
    if predicate is not None:
        if not isinstance(predicate, dict):
            raise ValueError(f"{path}: predicate must be a JSON object")
        return predicate
    if "spdxVersion" in document:
        return document
    raise ValueError(f"{path}: expected an in-toto statement or SPDX document")


def checksum_key(algorithm: str, value: str) -> tuple[str, str]:
    return algorithm.lower(), value.lower()


def final_files(document: dict[str, Any], path: Path) -> list[dict[str, str]]:
    """Return final file names and checksums from an attestation or SPDX doc."""

    subjects = document.get("subject")
    if subjects is not None:
        if not isinstance(subjects, list):
            raise ValueError(f"{path}: subject must be a JSON array")
        files: list[dict[str, str]] = []
        for subject in subjects:
            if not isinstance(subject, dict):
                raise ValueError(f"{path}: every subject must be an object")
            name = subject.get("name")
            digests = subject.get("digest")
            if not isinstance(name, str) or not name:
                raise ValueError(f"{path}: every subject needs a name")
            if not isinstance(digests, dict) or not digests:
                raise ValueError(f"{path}: subject {name!r} needs a digest")
            # BuildKit emits one digest. Prefer SHA256 if a producer emits more
            # than one so matching remains stable across SPDX producers.
            algorithm = "sha256" if "sha256" in digests else next(iter(digests))
            value = digests.get(algorithm)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{path}: subject {name!r} has an invalid digest")
            files.append({"name": name.lstrip("/"), "algorithm": algorithm, "value": value})
        if not files:
            raise ValueError(f"{path}: final image has no file subjects")
        return files

    predicate = predicate_from(document, path)
    records = predicate.get("files")
    if not isinstance(records, list):
        raise ValueError(f"{path}: expected subject or SPDX files")

    files = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{path}: every SPDX file must be an object")
        name = record.get("fileName")
        checksums = record.get("checksums")
        if not isinstance(name, str) or not name or not isinstance(checksums, list):
            raise ValueError(f"{path}: every SPDX file needs fileName and checksums")
        for checksum in checksums:
            if not isinstance(checksum, dict):
                continue
            algorithm = checksum.get("algorithm")
            value = checksum.get("checksumValue")
            if isinstance(algorithm, str) and isinstance(value, str) and value:
                files.append({
                    "name": name.lstrip("/"),
                    "algorithm": algorithm,
                    "value": value,
                })
                break
        else:
            raise ValueError(f"{path}: SPDX file {name!r} has no usable checksum")
    if not files:
        raise ValueError(f"{path}: final image has no SPDX files")
    return files


def path_score(candidate: str, final_name: str) -> int:
    candidate = candidate.lstrip("/")
    final_name = final_name.lstrip("/")
    if candidate == final_name:
        return 0
    if candidate.endswith(f"/{final_name}"):
        return 1
    if candidate.rsplit("/", 1)[-1] == final_name.rsplit("/", 1)[-1]:
        return 2
    return 3


def file_id(name: str, algorithm: str, value: str) -> str:
    identity = f"{name}\0{algorithm.lower()}:{value.lower()}".encode()
    return f"SPDXRef-File-final-{hashlib.sha256(identity).hexdigest()[:24]}"


def compose(builder_document: dict[str, Any], final_document: dict[str, Any], *,
            builder_path: Path = Path("builder"), final_path: Path = Path("final")) -> dict[str, Any]:
    """Return a raw SPDX predicate composed from builder and final documents."""

    builder = predicate_from(builder_document, builder_path)
    final = final_files(final_document, final_path)
    builder_records = builder.get("files")
    relationships = builder.get("relationships")
    packages = builder.get("packages")
    if not isinstance(builder_records, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no files array")
    if not isinstance(relationships, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no relationships array")
    if not isinstance(packages, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no packages array")

    by_checksum: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    all_file_ids: set[str] = set()
    for record in builder_records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("SPDXID")
        if isinstance(record_id, str):
            all_file_ids.add(record_id)
        name = record.get("fileName")
        checksums = record.get("checksums")
        if not isinstance(name, str) or not isinstance(checksums, list):
            continue
        for checksum in checksums:
            if not isinstance(checksum, dict):
                continue
            algorithm = checksum.get("algorithm")
            value = checksum.get("checksumValue")
            if isinstance(algorithm, str) and isinstance(value, str) and value:
                by_checksum[checksum_key(algorithm, value)].append(record)

    composed_files: list[dict[str, Any]] = []
    source_to_final: defaultdict[str, set[str]] = defaultdict(set)
    missing: list[str] = []
    for final_record in final:
        candidates = by_checksum.get(
            checksum_key(final_record["algorithm"], final_record["value"]), []
        )
        if not candidates:
            missing.append(final_record["name"])
            continue

        best_score = min(path_score(record["fileName"], final_record["name"]) for record in candidates)
        # If identical content occurs in several packages, retain all matching
        # package/file relationships at the best path match. This avoids making
        # package ownership depend on dictionary order.
        selected = [
            record for record in candidates
            if path_score(record["fileName"], final_record["name"]) == best_score
        ]
        selected.sort(key=lambda record: record["SPDXID"])
        source = selected[0]
        new_id = file_id(final_record["name"], final_record["algorithm"], final_record["value"])
        output_record = copy.deepcopy(source)
        output_record["SPDXID"] = new_id
        output_record["fileName"] = final_record["name"]
        composed_files.append(output_record)
        for record in selected:
            source_to_final[record["SPDXID"]].add(new_id)

    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(
            f"{final_path}: {len(missing)} final files were not found in the builder SBOM: {names}"
        )

    def endpoint_replacements(endpoint: Any) -> set[Any]:
        if endpoint not in source_to_final:
            return {endpoint}
        return source_to_final[endpoint]

    composed_relationships: list[dict[str, Any]] = []
    seen_relationships: set[str] = set()
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        element_id = relationship.get("spdxElementId")
        related_id = relationship.get("relatedSpdxElement")
        if (
            (element_id in all_file_ids and element_id not in source_to_final)
            or (related_id in all_file_ids and related_id not in source_to_final)
        ):
            # The builder relationship points at a file that was not copied
            # into the final image. Do not leave a dangling file reference.
            continue
        if element_id not in source_to_final and related_id not in source_to_final:
            composed_relationships.append(copy.deepcopy(relationship))
            continue

        element_ids = endpoint_replacements(element_id)
        related_ids = endpoint_replacements(related_id)
        for new_element_id in element_ids:
            for new_related_id in related_ids:
                replacement = copy.deepcopy(relationship)
                replacement["spdxElementId"] = new_element_id
                replacement["relatedSpdxElement"] = new_related_id
                identity = json.dumps(replacement, sort_keys=True, separators=(",", ":"))
                if identity not in seen_relationships:
                    seen_relationships.add(identity)
                    composed_relationships.append(replacement)

    output = copy.deepcopy(builder)
    output["files"] = composed_files
    output["relationships"] = composed_relationships
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose builder SPDX packages with final-image file subjects"
    )
    parser.add_argument("--builder-sbom", type=Path, required=True)
    parser.add_argument("--final-sbom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        output = compose(
            read_json(args.builder_sbom),
            read_json(args.final_sbom),
            builder_path=args.builder_sbom,
            final_path=args.final_sbom,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as stream:
            json.dump(output, stream, indent=2)
            stream.write("\n")
        print(
            f"composed {len(output['packages'])} packages, "
            f"{len(output['files'])} final files, "
            f"{len(output['relationships'])} relationships",
            file=sys.stderr,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"compose_sbom.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
