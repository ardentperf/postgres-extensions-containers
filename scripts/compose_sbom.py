#!/usr/bin/env python3
"""Compose an SPDX predicate with final-image packages and files.

BuildKit's SBOM attestation for a multi-stage build contains two useful but
different views of the result: the selected builder stage is represented by
the SPDX predicate, while the attestation subject identifies the files in the
final image. This module keeps packages that own final-image files, adds their
referenced dependencies, and uses the final subjects to trim the file
inventory and its relationships.
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


DEPENDENCY_RELATIONSHIP_TYPES = {
    "DEPENDENCY_OF",
    "DEPENDS_ON",
}

EXTENSION_PACKAGE_ID = "SPDXRef-Package-extension-payload"


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def checksum_key(algorithm: str, value: str) -> tuple[str, str]:
    return algorithm.lower(), value.lower()


def final_files(document: dict[str, Any], path: Path) -> list[dict[str, str]]:
    """Return final file names and checksums from a BuildKit attestation."""

    subjects = document.get("subject")
    if not isinstance(subjects, list):
        raise ValueError(f"{path}: expected a BuildKit attestation with a subject array")

    files: list[dict[str, str]] = []
    for subject in subjects:
        if not isinstance(subject, dict):
            raise ValueError(f"{path}: every subject must be an object")
        name = subject.get("name")
        digests = subject.get("digest")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}: every subject needs a name")
        if name.startswith("pkg:"):
            raise ValueError(
                f"{path}: subject {name!r} is an image subject; use a local-export SBOM"
            )
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


def path_score(candidate: str, final_name: str) -> tuple[int, int]:
    """Prefer an exact path, then the longest shared path suffix."""

    candidate_parts = tuple(part for part in candidate.lstrip("/").split("/") if part)
    final_parts = tuple(part for part in final_name.lstrip("/").split("/") if part)
    common_suffix = 0
    for candidate_part, final_part in zip(reversed(candidate_parts), reversed(final_parts)):
        if candidate_part != final_part:
            break
        common_suffix += 1
    return common_suffix, int(candidate_parts == final_parts)


def file_id(name: str, algorithm: str, value: str) -> str:
    identity = f"{name}\0{algorithm.lower()}:{value.lower()}".encode()
    return f"SPDXRef-File-final-{hashlib.sha256(identity).hexdigest()[:24]}"


def extension_package() -> dict[str, Any]:
    return {
        "SPDXID": EXTENSION_PACKAGE_ID,
        "copyrightText": "NOASSERTION",
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": True,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "name": "extension-payload",
        "supplier": "NOASSERTION",
        "versionInfo": "NOASSERTION",
    }


def extension_file(final_record: dict[str, str]) -> dict[str, Any]:
    return {
        "SPDXID": file_id(final_record["name"], final_record["algorithm"], final_record["value"]),
        "checksums": [{
            "algorithm": final_record["algorithm"].upper(),
            "checksumValue": final_record["value"],
        }],
        "copyrightText": "NOASSERTION",
        "fileName": final_record["name"],
        "licenseConcluded": "NOASSERTION",
        "licenseInfoInFiles": ["NOASSERTION"],
    }


def compose(builder_document: dict[str, Any], *,
            builder_path: Path = Path("builder")) -> dict[str, Any]:
    """Return a raw SPDX predicate composed from a builder attestation."""

    builder = builder_document.get("predicate")
    if not isinstance(builder, dict):
        raise ValueError(f"{builder_path}: expected a BuildKit attestation with an SPDX predicate")
    if "subject" not in builder_document:
        raise ValueError(f"{builder_path}: builder attestation has no final-image subjects")
    final = final_files(builder_document, builder_path)
    builder_records = builder.get("files")
    relationships = builder.get("relationships")
    packages = builder.get("packages")
    if not isinstance(builder_records, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no files array")
    if not isinstance(relationships, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no relationships array")
    if not isinstance(packages, list):
        raise ValueError(f"{builder_path}: SPDX predicate has no packages array")

    builder_packages = {
        package["SPDXID"]: package
        for package in packages
        if isinstance(package, dict)
        and isinstance(package.get("SPDXID"), str)
        and package.get("primaryPackagePurpose") != "FILE"
    }

    all_package_ids = {
        package["SPDXID"]
        for package in packages
        if isinstance(package, dict) and isinstance(package.get("SPDXID"), str)
    }
    package_ids = set(builder_packages)
    package_ids_by_name: defaultdict[str, set[str]] = defaultdict(set)
    for package_id, package in builder_packages.items():
        if isinstance(package.get("name"), str):
            package_ids_by_name[package["name"]].add(package_id)
    retained_package_ids: set[str] = set()
    owners_by_source_file: defaultdict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        if relationship.get("relationshipType") != "CONTAINS":
            continue
        package_id = relationship.get("spdxElementId")
        source_file_id = relationship.get("relatedSpdxElement")
        if package_id in package_ids and isinstance(source_file_id, str):
            owners_by_source_file[source_file_id].add(package_id)
    owned_source_file_ids = set(owners_by_source_file)

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
    direct_final_owners: defaultdict[str, set[str]] = defaultdict(set)
    final_ids: set[str] = set()

    def add_synthetic_file(record: dict[str, str], owner: str | None = None) -> None:
        output_record = extension_file(record)
        composed_files.append(output_record)
        final_ids.add(output_record["SPDXID"])
        if owner is not None:
            retained_package_ids.add(owner)
            direct_final_owners[output_record["SPDXID"]].add(owner)

    for final_record in final:
        final_name = final_record["name"].lstrip("/")
        license_parts = final_name.split("/", 2)
        if license_parts[0] == "licenses" and len(license_parts) > 1:
            owners = package_ids_by_name.get(license_parts[1], set())
            add_synthetic_file(final_record, next(iter(owners)) if len(owners) == 1 else None)
            continue

        candidates = by_checksum.get(
            checksum_key(final_record["algorithm"], final_record["value"]), []
        )
        if not candidates:
            add_synthetic_file(final_record)
            continue

        owned_candidates = [
            record for record in candidates if record["SPDXID"] in owned_source_file_ids
        ]
        candidates = owned_candidates or candidates
        best_score = max(path_score(record["fileName"], final_name) for record in candidates)
        selected = [
            record for record in candidates
            if path_score(record["fileName"], final_name) == best_score
        ]
        selected.sort(key=lambda record: record["SPDXID"])
        source_names = {record["fileName"].lstrip("/") for record in selected}
        if len(source_names) > 1:
            add_synthetic_file(final_record)
            continue

        source = selected[0]
        new_id = file_id(final_record["name"], final_record["algorithm"], final_record["value"])
        output_record = copy.deepcopy(source)
        output_record["SPDXID"] = new_id
        output_record["fileName"] = final_record["name"]
        composed_files.append(output_record)
        final_ids.add(new_id)
        for record in selected:
            source_to_final[record["SPDXID"]].add(new_id)

    owned_final_ids: set[str] = set(direct_final_owners)
    for source_file_id, package_ids_for_file in owners_by_source_file.items():
        final_ids_for_source = source_to_final.get(source_file_id)
        if not final_ids_for_source:
            continue
        retained_package_ids.update(package_ids_for_file)
        owned_final_ids.update(final_ids_for_source)

    extension_file_ids = final_ids - owned_final_ids

    dependencies: defaultdict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        relationship_type = relationship.get("relationshipType")
        element_id = relationship.get("spdxElementId")
        related_id = relationship.get("relatedSpdxElement")
        if relationship_type in DEPENDENCY_RELATIONSHIP_TYPES:
            if element_id in package_ids and related_id in package_ids:
                if relationship_type == "DEPENDS_ON":
                    dependencies[element_id].add(related_id)
                else:
                    dependencies[related_id].add(element_id)

    pending_packages = list(retained_package_ids)
    while pending_packages:
        package_id = pending_packages.pop()
        for dependency_id in dependencies[package_id]:
            if dependency_id not in retained_package_ids:
                retained_package_ids.add(dependency_id)
                pending_packages.append(dependency_id)

    if extension_file_ids:
        retained_package_ids.add(EXTENSION_PACKAGE_ID)

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
            continue
        if (
            (element_id in all_package_ids and element_id not in retained_package_ids)
            or (related_id in all_package_ids and related_id not in retained_package_ids)
        ):
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

    composed_relationships.extend(
        {
            "spdxElementId": package_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": file_id_value,
        }
        for file_id_value, package_ids_for_file in direct_final_owners.items()
        for package_id in sorted(package_ids_for_file)
    )

    output = copy.deepcopy(builder)
    output["packages"] = [
        package for package in packages
        if isinstance(package, dict) and package.get("SPDXID") in retained_package_ids
    ]
    if extension_file_ids:
        output["packages"].append(extension_package())
    output["files"] = composed_files
    output["relationships"] = composed_relationships
    described_ids = {
        relationship["relatedSpdxElement"]
        for relationship in composed_relationships
        if relationship.get("spdxElementId") == output["SPDXID"]
        and relationship.get("relationshipType") == "DESCRIBES"
    }
    for package_id in sorted(retained_package_ids):
        if package_id not in described_ids:
            output["relationships"].append({
                "spdxElementId": output["SPDXID"],
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package_id,
            })
    if extension_file_ids:
        output["relationships"].extend(
            {
                "spdxElementId": EXTENSION_PACKAGE_ID,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_id_value,
            }
            for file_id_value in sorted(extension_file_ids)
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose final-image package owners and files from builder SPDX data"
    )
    parser.add_argument("--builder-sbom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        output = compose(
            read_json(args.builder_sbom),
            builder_path=args.builder_sbom,
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
