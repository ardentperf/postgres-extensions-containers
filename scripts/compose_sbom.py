#!/usr/bin/env python3
"""See README.md#sbom-scope for the composition rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence


EXTENSION_PACKAGE_ID = "SPDXRef-Package-extension-payload"
COMPOSITION_NAMESPACE = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "sbom-composition/v1"
)
COMPOSER_VERSION = "1.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"provenance manifest missing {name}")
    return value


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"provenance manifest missing {name}")
    return value


def validate_provenance_manifest(
    manifest: dict[str, Any],
    *,
    builder_path: Path | None = None,
    builder_paths: Sequence[tuple[str, Path]] | None = None,
) -> None:
    """Validate the generic manifest used for composition provenance.

    The manifest is deliberately independent of any particular image builder.
    Its required fields cover the inputs and identity needed to explain this
    post-build composition step.  The builder hash is checked here when the
    manifest came from the CLI, where the source file is available.
    """

    if not isinstance(manifest, dict):
        raise ValueError("provenance manifest must contain a JSON object")
    if manifest.get("schemaVersion") != COMPOSITION_NAMESPACE:
        raise ValueError(
            f"provenance manifest schemaVersion must be {COMPOSITION_NAMESPACE!r}"
        )

    annotation_date = _required_string(manifest.get("annotationDate"), "annotationDate")
    timestamp_text = (
        annotation_date[:-1] + "+00:00"
        if annotation_date.endswith("Z")
        else annotation_date
    )
    try:
        parsed_date = datetime.fromisoformat(timestamp_text)
    except ValueError as error:
        raise ValueError(
            "provenance manifest annotationDate must be an ISO-8601 timestamp"
        ) from error
    if parsed_date.tzinfo is None or parsed_date.utcoffset() != timedelta(0):
        raise ValueError("provenance manifest annotationDate must be a UTC timestamp")

    if builder_path is not None and builder_paths is not None:
        raise ValueError("provenance validation accepts one builder path shape")

    inputs = _required_mapping(manifest.get("inputs"), "inputs")
    builder_digests: dict[str, str] = {}
    if "builderSboms" in inputs:
        builder_records = inputs["builderSboms"]
        if not isinstance(builder_records, list) or not builder_records:
            raise ValueError("provenance manifest inputs.builderSboms must be a non-empty list")
        for index, input_record_value in enumerate(builder_records):
            input_record = _required_mapping(
                input_record_value, f"inputs.builderSboms[{index}]"
            )
            platform = _required_string(
                input_record.get("platform"),
                f"inputs.builderSboms[{index}].platform",
            )
            if platform in builder_digests:
                raise ValueError(
                    f"provenance manifest contains duplicate builder platform {platform!r}"
                )
            digest = _required_string(
                input_record.get("sha256"),
                f"inputs.builderSboms[{index}].sha256",
            )
            if not SHA256_PATTERN.fullmatch(digest):
                raise ValueError(
                    f"provenance manifest inputs.builderSboms[{index}].sha256 must be a SHA-256 hex digest"
                )
            builder_digests[platform] = digest
    elif isinstance(manifest.get("image"), dict) and "platforms" in manifest["image"]:
        raise ValueError("provenance manifest missing inputs.builderSboms")
    else:
        input_record = _required_mapping(inputs.get("builderSbom"), "inputs.builderSbom")
        digest = _required_string(input_record.get("sha256"), "inputs.builderSbom.sha256")
        if not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(
                "provenance manifest inputs.builderSbom.sha256 must be a SHA-256 hex digest"
            )
    build_definition = _required_mapping(
        inputs.get("buildDefinition"), "inputs.buildDefinition"
    )
    build_definition_digest = _required_string(
        build_definition.get("sha256"), "inputs.buildDefinition.sha256"
    )
    if not SHA256_PATTERN.fullmatch(build_definition_digest):
        raise ValueError(
            "provenance manifest inputs.buildDefinition.sha256 must be a SHA-256 hex digest"
        )

    image = _required_mapping(manifest.get("image"), "image")
    for field in ("sourceCommit", "target"):
        _required_string(image.get(field), f"image.{field}")
    if "platforms" in image:
        platform_records = image["platforms"]
        if not isinstance(platform_records, list) or not platform_records:
            raise ValueError("provenance manifest image.platforms must be a non-empty list")
        image_platforms: set[str] = set()
        for index, platform_record_value in enumerate(platform_records):
            platform_record = _required_mapping(
                platform_record_value, f"image.platforms[{index}]"
            )
            platform = _required_string(
                platform_record.get("platform"),
                f"image.platforms[{index}].platform",
            )
            if platform in image_platforms:
                raise ValueError(
                    f"provenance manifest contains duplicate image platform {platform!r}"
                )
            image_platforms.add(platform)
            manifest_digest = _required_string(
                platform_record.get("manifestDigest"),
                f"image.platforms[{index}].manifestDigest",
            )
            if not DIGEST_PATTERN.fullmatch(manifest_digest):
                raise ValueError(
                    f"provenance manifest image.platforms[{index}].manifestDigest must be a SHA-256 digest"
                )
        index_digest = _required_string(image.get("indexDigest"), "image.indexDigest")
        if not DIGEST_PATTERN.fullmatch(index_digest):
            raise ValueError(
                "provenance manifest image.indexDigest must be a SHA-256 digest"
            )
        if builder_digests and set(builder_digests) != image_platforms:
            raise ValueError(
                "provenance manifest builder and image platform sets do not match"
            )
    else:
        for field in ("platform", "manifestDigest"):
            _required_string(image.get(field), f"image.{field}")
        if not DIGEST_PATTERN.fullmatch(image["manifestDigest"]):
            raise ValueError(
                "provenance manifest image.manifestDigest must be a SHA-256 digest"
            )

    composer = _required_mapping(manifest.get("composer"), "composer")
    for field in ("revision", "command", "interpreter"):
        _required_string(composer.get(field), f"composer.{field}")
    tool_versions = _required_mapping(composer.get("toolVersions"), "composer.toolVersions")
    if not tool_versions or any(
        not isinstance(name, str)
        or not name
        or not isinstance(version, str)
        or not version
        for name, version in tool_versions.items()
    ):
        raise ValueError("provenance manifest composer.toolVersions must contain tool versions")

    workflow = _required_mapping(manifest.get("workflow"), "workflow")
    for field in ("repository", "name", "ref", "runId", "runAttempt"):
        _required_string(workflow.get(field), f"workflow.{field}")

    if builder_path is not None:
        if not builder_path.is_file():
            raise ValueError(f"provenance builder SBOM is missing: {builder_path}")
        actual_digest = sha256_file(builder_path)
        expected_digest = manifest["inputs"]["builderSbom"]["sha256"]
        if actual_digest != expected_digest:
            raise ValueError(
                "provenance manifest builder SBOM hash does not match "
                f"{builder_path}"
            )
    if builder_paths is not None:
        if "builderSboms" not in inputs:
            raise ValueError(
                "provenance manifest must use inputs.builderSboms for aggregate validation"
            )
        provided_platforms = {platform for platform, _ in builder_paths}
        if provided_platforms != set(builder_digests):
            raise ValueError(
                "provenance builder paths and manifest platform sets do not match"
            )
        for platform, path in builder_paths:
            if not path.is_file():
                raise ValueError(f"provenance builder SBOM is missing: {path}")
            actual_digest = sha256_file(path)
            expected_digest = builder_digests[platform]
            if actual_digest != expected_digest:
                raise ValueError(
                    "provenance manifest builder SBOM hash does not match "
                    f"{path} ({platform})"
                )


def _provenance_input(
    provenance_manifest: dict[str, Any] | Path | str,
) -> tuple[dict[str, Any], Path | None]:
    if isinstance(provenance_manifest, (Path, str)):
        path = Path(provenance_manifest)
        return read_json(path), path
    return provenance_manifest, None


def provenance_annotation(
    provenance_manifest: dict[str, Any] | Path | str,
    *,
    builder_path: Path | None = None,
    builder_paths: Sequence[tuple[str, Path]] | None = None,
) -> dict[str, Any]:
    """Build the deterministic SPDX annotation for a composition manifest."""

    manifest, manifest_path = _provenance_input(provenance_manifest)
    validate_provenance_manifest(
        manifest,
        builder_path=builder_path if manifest_path is not None else None,
        builder_paths=builder_paths,
    )
    canonical_manifest = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "annotationDate": manifest["annotationDate"],
        "annotationType": "OTHER",
        "annotator": f"Tool: compose_sbom.py - {COMPOSER_VERSION}",
        "comment": f"{COMPOSITION_NAMESPACE} {canonical_manifest}",
        "spdxElementId": "SPDXRef-DOCUMENT",
    }


def checksum_key(algorithm: str, value: str) -> tuple[str, str]:
    return algorithm.lower(), value.lower()


def final_files(document: dict[str, Any], path: Path) -> list[dict[str, str]]:
    """Return final file names and checksums from a BuildKit attestation."""

    files: list[dict[str, str]] = []
    for subject in document["subject"]:
        name = subject["name"]
        if name.startswith("pkg:"):
            raise ValueError(
                f"{path}: subject {name!r} is an image subject; use a local-export SBOM"
            )
        files.append({
            "name": name.lstrip("/"),
            "algorithm": "sha256",
            "value": subject["digest"]["sha256"],
        })
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


def extension_package(extension_name: str) -> dict[str, Any]:
    return {
        "SPDXID": EXTENSION_PACKAGE_ID,
        "copyrightText": "NOASSERTION",
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": True,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "name": f"{extension_name}-extension-artifacts",
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
            extension_name: str,
            builder_path: Path = Path("builder"),
            provenance_manifest: dict[str, Any] | Path | str | None = None,
            ) -> dict[str, Any]:
    """Return a raw SPDX predicate composed from a builder attestation."""

    builder = builder_document["predicate"]
    final = final_files(builder_document, builder_path)
    builder_records = builder["files"]
    relationships = builder["relationships"]
    packages = builder["packages"]

    builder_packages = {
        package["SPDXID"]: package
        for package in packages
        if package.get("primaryPackagePurpose") != "FILE"
    }

    all_package_ids = {package["SPDXID"] for package in packages}
    package_ids = set(builder_packages)
    package_ids_by_name: defaultdict[str, set[str]] = defaultdict(set)
    for package_id, package in builder_packages.items():
        package_ids_by_name[package["name"]].add(package_id)
    retained_package_ids: set[str] = set()
    owners_by_source_file: defaultdict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        if relationship["relationshipType"] != "CONTAINS":
            continue
        package_id = relationship["spdxElementId"]
        source_file_id = relationship["relatedSpdxElement"]
        if package_id in package_ids:
            owners_by_source_file[source_file_id].add(package_id)

    by_checksum: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    all_file_ids = {record["SPDXID"] for record in builder_records}
    for record in builder_records:
        for checksum in record["checksums"]:
            by_checksum[checksum_key(
                checksum["algorithm"], checksum["checksumValue"]
            )].append(record)

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
            record for record in candidates if record["SPDXID"] in owners_by_source_file
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
        output_record = source.copy()
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

    if extension_file_ids:
        retained_package_ids.add(EXTENSION_PACKAGE_ID)

    def endpoint_replacements(endpoint: str) -> set[str]:
        return source_to_final.get(endpoint, {endpoint})

    composed_relationships: list[dict[str, Any]] = []
    seen_relationships: set[str] = set()
    for relationship in relationships:
        element_id = relationship["spdxElementId"]
        related_id = relationship["relatedSpdxElement"]
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
            composed_relationships.append(relationship.copy())
            continue

        element_ids = endpoint_replacements(element_id)
        related_ids = endpoint_replacements(related_id)
        for new_element_id in element_ids:
            for new_related_id in related_ids:
                replacement = relationship.copy()
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

    output = builder.copy()
    output["packages"] = [
        package for package in packages
        if package["SPDXID"] in retained_package_ids
    ]
    if extension_file_ids:
        output["packages"].append(extension_package(extension_name))
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
    if provenance_manifest is not None:
        annotation = provenance_annotation(
            provenance_manifest,
            builder_path=builder_path,
        )
        annotations = output.get("annotations", [])
        if not isinstance(annotations, list):
            raise ValueError("SPDX annotations must be a list")
        annotations = [
            existing
            for existing in annotations
            if not (
                isinstance(existing, dict)
                and existing.get("spdxElementId") == "SPDXRef-DOCUMENT"
                and existing.get("annotationType") == "OTHER"
                and isinstance(existing.get("comment"), str)
                and existing["comment"].startswith(f"{COMPOSITION_NAMESPACE} ")
            )
        ]
        annotations.append(annotation)
        output["annotations"] = annotations
    return output


def aggregate(
    composed_documents: Sequence[tuple[str, dict[str, Any]]],
    *,
    extension_name: str,
    provenance_manifest: dict[str, Any] | Path | str | None = None,
    builder_paths: Sequence[tuple[str, Path]] | None = None,
) -> dict[str, Any]:
    """Merge composed SPDX documents into one multi-platform document.

    The aggregate intentionally treats platform-specific entities as separate
    inputs, while deduplicating identical package and file records. This keeps
    the document useful to generic SPDX consumers without claiming that every
    package is present on every platform.
    """

    if not composed_documents:
        raise ValueError("aggregate requires at least one composed SPDX document")

    if any(not isinstance(platform, str) or not platform for platform, _ in composed_documents):
        raise ValueError("aggregate platforms must be non-empty strings")
    if len({platform for platform, _ in composed_documents}) != len(composed_documents):
        raise ValueError("aggregate platforms must be unique")
    ordered_documents = sorted(composed_documents, key=lambda item: item[0])
    output = deepcopy(ordered_documents[0][1])
    output["name"] = f"{extension_name}-multi-platform-sbom"
    output["packages"] = []
    output["files"] = []
    output["relationships"] = []
    output.pop("annotations", None)

    entities: dict[tuple[str, str], str] = {}
    used_ids: set[str] = set()
    relationships: dict[str, dict[str, Any]] = {}
    annotations: dict[str, dict[str, Any]] = {}

    def entity_key(entity: dict[str, Any]) -> str:
        value = deepcopy(entity)
        value.pop("SPDXID", None)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def aggregate_id(platform: str, original_id: str) -> str:
        platform_id = re.sub(r"[^A-Za-z0-9.-]+", "-", platform).strip("-")
        original_suffix = original_id.removeprefix("SPDXRef-")
        original_suffix = re.sub(r"[^A-Za-z0-9.-]+", "-", original_suffix).strip("-")
        candidate = f"SPDXRef-{platform_id}-{original_suffix}"
        suffix = 2
        while candidate in used_ids:
            candidate = f"SPDXRef-{platform_id}-{original_suffix}-{suffix}"
            suffix += 1
        return candidate

    for platform, document in ordered_documents:
        if not isinstance(document, dict):
            raise ValueError(f"aggregate input for {platform!r} must be a JSON object")
        id_map = {"SPDXRef-DOCUMENT": "SPDXRef-DOCUMENT"}
        for entity_type in ("packages", "files"):
            records = document.get(entity_type, [])
            if not isinstance(records, list):
                raise ValueError(f"aggregate {entity_type} must be a list")
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("SPDXID"), str):
                    raise ValueError(f"aggregate {entity_type} contains an invalid record")
                original_id = record["SPDXID"]
                key = (entity_type, entity_key(record))
                if key not in entities:
                    new_id = aggregate_id(platform, original_id)
                    entities[key] = new_id
                    used_ids.add(new_id)
                    merged_record = deepcopy(record)
                    merged_record["SPDXID"] = new_id
                    output[entity_type].append(merged_record)
                id_map[original_id] = entities[key]

        def map_id(identifier: str) -> str:
            if identifier in id_map:
                return id_map[identifier]
            if identifier == "SPDXRef-DOCUMENT":
                return identifier
            mapped = aggregate_id(platform, identifier)
            used_ids.add(mapped)
            id_map[identifier] = mapped
            return mapped

        for relationship in document.get("relationships", []):
            if not isinstance(relationship, dict):
                raise ValueError("aggregate relationships contains an invalid record")
            mapped = deepcopy(relationship)
            mapped["spdxElementId"] = map_id(relationship["spdxElementId"])
            mapped["relatedSpdxElement"] = map_id(relationship["relatedSpdxElement"])
            identity = json.dumps(mapped, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            relationships[identity] = mapped

        for annotation in document.get("annotations", []):
            if not isinstance(annotation, dict):
                raise ValueError("aggregate annotations contains an invalid record")
            mapped = deepcopy(annotation)
            if isinstance(mapped.get("spdxElementId"), str):
                mapped["spdxElementId"] = map_id(mapped["spdxElementId"])
            identity = json.dumps(mapped, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            annotations[identity] = mapped

    output["packages"].sort(key=lambda record: record["SPDXID"])
    output["files"].sort(key=lambda record: record["SPDXID"])
    output["relationships"] = [relationships[key] for key in sorted(relationships)]
    if annotations:
        output["annotations"] = [annotations[key] for key in sorted(annotations)]
    if provenance_manifest is not None:
        manifest, _ = _provenance_input(provenance_manifest)
        output["annotations"] = [
            annotation
            for annotation in output.get("annotations", [])
            if not (
                isinstance(annotation, dict)
                and annotation.get("spdxElementId") == "SPDXRef-DOCUMENT"
                and annotation.get("annotationType") == "OTHER"
                and isinstance(annotation.get("comment"), str)
                and annotation["comment"].startswith(f"{COMPOSITION_NAMESPACE} ")
            )
        ]
        annotation = provenance_annotation(
            provenance_manifest,
            builder_paths=builder_paths,
        )
        index_digest = manifest["image"].get("indexDigest")
        if index_digest:
            safe_extension_name = re.sub(r"[^A-Za-z0-9.-]+", "-", extension_name).strip("-")
            output["documentNamespace"] = (
                f"{COMPOSITION_NAMESPACE}/documents/{safe_extension_name}/"
                f"{index_digest.replace(':', '-')}"
            )
        output["annotations"].append(annotation)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose final-image package owners and files from builder SPDX data"
    )
    parser.add_argument(
        "--builder-sbom",
        type=Path,
        action="append",
        help="Builder-stage SBOM, repeat once per aggregate platform",
    )
    parser.add_argument(
        "--aggregate-from",
        type=Path,
        action="append",
        help="Composed SPDX document to include in a multi-platform aggregate",
    )
    parser.add_argument(
        "--platform",
        action="append",
        help="Platform corresponding to each --aggregate-from input",
    )
    parser.add_argument("--extension-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provenance-manifest",
        type=Path,
        help="JSON manifest to embed as a signed SPDX composition annotation",
    )
    args = parser.parse_args()

    builder_sboms = args.builder_sbom or []
    aggregate_inputs = args.aggregate_from or []
    platforms = args.platform or []
    if aggregate_inputs:
        if len(aggregate_inputs) != len(platforms):
            parser.error("--aggregate-from and --platform must have the same number of values")
        if len(aggregate_inputs) != len(builder_sboms):
            parser.error("aggregate mode requires one --builder-sbom per --aggregate-from")
        output = aggregate(
            [
                (platform, read_json(path))
                for platform, path in zip(platforms, aggregate_inputs)
            ],
            extension_name=args.extension_name,
            provenance_manifest=args.provenance_manifest,
            builder_paths=list(zip(platforms, builder_sboms)),
        )
    else:
        if len(builder_sboms) != 1:
            parser.error("single-document mode requires exactly one --builder-sbom")
        output = compose(
            read_json(builder_sboms[0]),
            extension_name=args.extension_name,
            builder_path=builder_sboms[0],
            provenance_manifest=args.provenance_manifest,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
