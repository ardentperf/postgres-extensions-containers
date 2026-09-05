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


def predicate_from(document: dict[str, Any], path: Path) -> dict[str, Any]:
    predicate = document.get("predicate")
    if not isinstance(predicate, dict):
        raise ValueError(f"{path}: expected a BuildKit attestation with an SPDX predicate")
    return predicate


def checksum_key(algorithm: str, value: str) -> tuple[str, str]:
    return algorithm.lower(), value.lower()


def synthetic_package(package: dict[str, Any]) -> bool:
    """Identify the scanner's document-root package, not a real dependency."""

    return package.get("primaryPackagePurpose") == "FILE"


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
    if candidate_parts == final_parts:
        return 0, 0

    common_suffix = 0
    for candidate_part, final_part in zip(reversed(candidate_parts), reversed(final_parts)):
        if candidate_part != final_part:
            break
        common_suffix += 1
    if common_suffix > 1:
        return 1, -common_suffix
    if common_suffix == 1:
        return 2, 0
    return 3, 0


def is_license_path(name: str) -> bool:
    return name.lstrip("/").startswith("licenses/")


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

    builder = predicate_from(builder_document, builder_path)
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
        and not synthetic_package(package)
    }

    all_package_ids = {
        package["SPDXID"]
        for package in packages
        if isinstance(package, dict) and isinstance(package.get("SPDXID"), str)
    }
    package_ids = set(builder_packages)
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
    final_ids: set[str] = set()
    for final_record in final:
        candidates = by_checksum.get(
            checksum_key(final_record["algorithm"], final_record["value"]), []
        )
        if not candidates:
            output_record = extension_file(final_record)
            composed_files.append(output_record)
            final_ids.add(output_record["SPDXID"])
            continue

        # BuildKit can emit the same file twice: once at the final image path
        # without package ownership and once at its builder path with a
        # CONTAINS relationship. Prefer the owned copy so a copied system
        # library is not incorrectly attributed to extension-payload.
        owned_candidates = [
            record for record in candidates if record["SPDXID"] in owned_source_file_ids
        ]
        candidates = owned_candidates or candidates
        best_score = min(path_score(record["fileName"], final_record["name"]) for record in candidates)
        selected = [
            record for record in candidates
            if path_score(record["fileName"], final_record["name"]) == best_score
        ]
        selected.sort(key=lambda record: record["SPDXID"])
        source_names = {record["fileName"].lstrip("/") for record in selected}
        if len(source_names) > 1 or (
            best_score[0] == 2 and is_license_path(final_record["name"])
        ):
            # Identical bytes do not prove that different source paths are the
            # same file. License destinations also encode the package name, so
            # a basename-only match to another source package is not evidence.
            output_record = extension_file(final_record)
            composed_files.append(output_record)
            final_ids.add(output_record["SPDXID"])
            continue

        source = selected[0]
        new_id = file_id(final_record["name"], final_record["algorithm"], final_record["value"])
        output_record = copy.deepcopy(source)
        output_record["SPDXID"] = new_id
        output_record["fileName"] = final_record["name"]
        composed_files.append(output_record)
        final_ids.add(new_id)
        for record in selected:
            # Preserve all owners of this one source file, while excluding
            # owners of other files that merely share its checksum.
            source_to_final[record["SPDXID"]].add(new_id)

    # A final file can be the only evidence that a copied system library is
    # part of the extension payload. Retain its package owner when present;
    # otherwise attribute the file to the extension itself.
    owned_final_ids: set[str] = set()
    for source_file_id, package_ids_for_file in owners_by_source_file.items():
        final_ids_for_source = source_to_final.get(source_file_id)
        if not final_ids_for_source:
            continue
        retained_package_ids.update(package_ids_for_file)
        owned_final_ids.update(final_ids_for_source)

    extension_file_ids = final_ids - owned_final_ids

    # BuildKit uses DEPENDENCY_OF with the dependency as the subject and the
    # dependent package as the related element. Handle the inverse SPDX form
    # too, so the composer remains usable with other SPDX producers.
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
            # The builder relationship points at a file that was not copied
            # into the final image. Do not leave a dangling file reference.
            continue
        if (
            (element_id in all_package_ids and element_id not in retained_package_ids)
            or (related_id in all_package_ids and related_id not in retained_package_ids)
        ):
            # The relationship points at the scanner's synthetic root package
            # or at a package that does not own a final-image file or provide a
            # dependency of one. It is outside the composed SPDX document.
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
