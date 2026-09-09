#!/usr/bin/env python3
"""Enrich the PR 61 filesystem SPDX document with pgrx Cargo evidence.

The input is already the composed final-image SPDX predicate. This merger
adds Cargo packages and dependency relationships from CycloneDX, connects
license text/evidence from cargo-about through valid SPDX fields, and extends
the existing document-level composition annotation with reproducible pgrx
build evidence. Raw Cargo reports remain optional diagnostics after this
program finishes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


COMPOSITION_NAMESPACE = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "sbom-composition/v1"
)
PGRX_NAMESPACE = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "pgrx-enrichment/v1"
)
SPDX_DOCUMENT = "SPDXRef-DOCUMENT"
NOASSERTION = "NOASSERTION"


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-") or "unknown"


def component_ref(component: dict[str, Any]) -> str:
    return str(component.get("bom-ref") or component.get("purl") or "")


def component_name(component: dict[str, Any], ref: str) -> str:
    if component.get("name"):
        return str(component["name"])
    if ref.startswith("pkg:"):
        return ref.split("@", 1)[0].rsplit("/", 1)[-1]
    return ref or "unknown-cargo-component"


def component_version(component: dict[str, Any], ref: str) -> str:
    if component.get("version"):
        return str(component["version"])
    if "@" in ref:
        return ref.rsplit("@", 1)[-1]
    return NOASSERTION


def license_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        if isinstance(value.get("expression"), str):
            return value["expression"]
        license_record = value.get("license")
        if isinstance(license_record, dict):
            return license_value(license_record)
        if isinstance(value.get("id"), str):
            return value["id"]
        if isinstance(value.get("name"), str):
            return value["name"]
    return None


def component_license(component: dict[str, Any]) -> str:
    values: list[str] = []
    for entry in component.get("licenses", []) or []:
        value = license_value(entry)
        if value and value not in values:
            values.append(value)
    return " AND ".join(values) if values else NOASSERTION


def about_crate_key(crate: dict[str, Any]) -> tuple[str, str]:
    name = str(crate.get("name") or "")
    version = str(crate.get("version") or "")
    if name and version:
        return name, version
    identifier = str(crate.get("id") or "")
    match = re.match(r"(.+?)\s+(\d+[^ ]*)\s+\(", identifier)
    if match:
        return match.group(1), match.group(2)
    return name, version


def about_license_records(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in report.get("licenses", []) or []:
        if not isinstance(record, dict):
            continue
        identifiers = [record.get("id"), record.get("name"), record.get("license")]
        for identifier in identifiers:
            if identifier:
                records[str(identifier)] = record
    return records


def cargo_package_id(purl: str, name: str, version: str) -> str:
    identity = purl or f"{name}@{version}"
    return "SPDXRef-Cargo-" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def cargo_package(
    component: dict[str, Any],
    crate: dict[str, Any] | None,
    license_records: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    ref = component_ref(component)
    name = component_name(component, ref)
    version = component_version(component, ref)
    purl = str(component.get("purl") or (ref if ref.startswith("pkg:") else ""))
    package_id = cargo_package_id(purl, name, version)
    declared = component_license(component)
    if declared == NOASSERTION and crate:
        declared = str(crate.get("license") or NOASSERTION)

    package: dict[str, Any] = {
        "SPDXID": package_id,
        "copyrightText": str((crate or {}).get("copyright") or NOASSERTION),
        "downloadLocation": purl or str((crate or {}).get("source") or NOASSERTION),
        "filesAnalyzed": False,
        "licenseConcluded": NOASSERTION,
        "licenseDeclared": declared,
        "name": name,
        "supplier": "NOASSERTION",
        "versionInfo": version,
    }
    if purl:
        package["externalRefs"] = [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceLocator": purl,
            "referenceType": "purl",
        }]

    external_refs = component.get("externalReferences", []) or []
    for reference in external_refs:
        if not isinstance(reference, dict) or not reference.get("url"):
            continue
        package.setdefault("externalRefs", []).append({
            "referenceCategory": "OTHER",
            "referenceLocator": str(reference["url"]),
            "referenceType": str(reference.get("type") or "source"),
        })

    if crate:
        repository = crate.get("repository") or crate.get("repository_url")
        if repository and not any(
            ref.get("referenceLocator") == repository
            for ref in package.get("externalRefs", [])
        ):
            package.setdefault("externalRefs", []).append({
                "referenceCategory": "OTHER",
                "referenceLocator": str(repository),
                "referenceType": "vcs",
            })
        license_id = str(crate.get("license") or "")
        evidence = license_records.get(license_id)
        if evidence and evidence.get("text"):
            evidence_id = "LicenseRef-CargoAbout-" + hashlib.sha256(
                (license_id + "\0" + str(evidence["text"])).encode()
            ).hexdigest()[:24]
            package["licenseComments"] = (
                f"cargo-about full-text license evidence: {evidence_id}"
            )
            package["attributionTexts"] = [
                f"cargo-about license: {license_id}",
            ]
            package["_cargoEvidence"] = {
                "id": evidence_id,
                "name": str(evidence.get("name") or license_id),
                "text": str(evidence["text"]),
            }
    return package, ref


def parse_components(
    cyclonedx: dict[str, Any],
    about: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    if cyclonedx.get("bomFormat") != "CycloneDX":
        raise ValueError("CycloneDX report does not declare bomFormat=CycloneDX")
    if str(cyclonedx.get("specVersion")) != "1.5":
        raise ValueError("CycloneDX report must use specVersion 1.5")

    crates = {
        about_crate_key(crate): crate
        for crate in about.get("crates", []) or []
        if isinstance(crate, dict) and about_crate_key(crate) != ("", "")
    }
    license_records = about_license_records(about)
    packages: dict[str, dict[str, Any]] = {}
    ref_to_package: dict[str, str] = {}
    evidence: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    metadata_component = cyclonedx.get("metadata", {}).get("component")
    if isinstance(metadata_component, dict):
        components.append(metadata_component)
    components.extend(
        component
        for component in cyclonedx.get("components", []) or []
        if isinstance(component, dict)
    )
    seen_refs: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = component_ref(component)
        if ref and ref in seen_refs:
            continue
        if ref:
            seen_refs.add(ref)
        name = component_name(component, ref)
        version = component_version(component, ref)
        crate = crates.get((name, version))
        package, ref = cargo_package(component, crate, license_records)
        packages[package["SPDXID"]] = package
        if ref:
            ref_to_package[ref] = package["SPDXID"]
        if "_cargoEvidence" in package:
            evidence.append(package.pop("_cargoEvidence"))

    return packages, ref_to_package, evidence


def dependency_relationships(
    cyclonedx: dict[str, Any],
    ref_to_package: dict[str, str],
) -> list[dict[str, str]]:
    relationships: list[dict[str, str]] = []
    for dependency in cyclonedx.get("dependencies", []) or []:
        if not isinstance(dependency, dict):
            continue
        parent = ref_to_package.get(str(dependency.get("ref") or ""))
        if not parent:
            continue
        for child_ref in dependency.get("dependsOn", []) or []:
            child = ref_to_package.get(str(child_ref))
            if not child or child == parent:
                continue
            relationships.append({
                "spdxElementId": child,
                "relationshipType": "DEPENDENCY_OF",
                "relatedSpdxElement": parent,
            })
    return relationships


def merge_license_evidence(
    document: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> None:
    existing = {
        item["licenseId"]: item
        for item in document.get("hasExtractedLicensingInfos", [])
        if isinstance(item, dict) and item.get("licenseId")
    }
    for item in evidence:
        existing.setdefault(item["id"], {
            "extractedText": item["text"],
            "licenseId": item["id"],
            "name": item["name"],
        })
    document["hasExtractedLicensingInfos"] = [
        existing[key] for key in sorted(existing)
    ]


def update_composition_annotation(
    document: dict[str, Any],
    enrichment: dict[str, Any],
) -> None:
    annotations = document.get("annotations", [])
    for annotation in annotations:
        if (
            annotation.get("spdxElementId") != SPDX_DOCUMENT
            or annotation.get("annotationType") != "OTHER"
            or not str(annotation.get("comment", "")).startswith(COMPOSITION_NAMESPACE + " ")
        ):
            continue
        raw = str(annotation["comment"])[len(COMPOSITION_NAMESPACE) + 1:]
        try:
            composition = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("existing composition annotation is not JSON") from error
        composition["pgrx"] = enrichment
        annotation["comment"] = COMPOSITION_NAMESPACE + " " + json.dumps(
            composition, sort_keys=True, separators=(",", ":")
        )
        return
    raise ValueError("existing PR 61 composition annotation was not found")


def enrich(
    document: dict[str, Any],
    reports: list[tuple[str, Path, Path, Path]],
    *,
    extension_name: str,
    dockerfile: Path,
    wrapper_revision: str,
) -> dict[str, Any]:
    if len({platform for platform, *_ in reports}) != len(reports):
        raise ValueError("pgrx report platforms must be unique")

    output = deepcopy(document)
    package_by_id = {
        package["SPDXID"]: package
        for package in output.get("packages", [])
        if package.get("SPDXID")
    }
    relationship_keys = {
        json.dumps(relationship, sort_keys=True, separators=(",", ":"))
        for relationship in output.get("relationships", [])
    }
    enrichment_reports: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []

    for platform, cyclonedx_path, about_path, metadata_path in reports:
        cyclonedx = read_json(cyclonedx_path)
        about = read_json(about_path)
        metadata = read_json(metadata_path)
        packages, refs, evidence = parse_components(cyclonedx, about)
        all_evidence.extend(evidence)
        for package_id, package in packages.items():
            existing = package_by_id.get(package_id)
            if existing is None:
                package_by_id[package_id] = package
                output.setdefault("packages", []).append(package)
            elif package.get("licenseComments") and not existing.get("licenseComments"):
                existing["licenseComments"] = package["licenseComments"]
                existing["attributionTexts"] = package.get("attributionTexts", [])
        for relationship in dependency_relationships(cyclonedx, refs):
            key = json.dumps(relationship, sort_keys=True, separators=(",", ":"))
            if key not in relationship_keys:
                relationship_keys.add(key)
                output.setdefault("relationships", []).append(relationship)

        source = metadata.get("source", {})
        cargo = metadata.get("cargo", {})
        reports_metadata = metadata.get("reports", {})
        actual_cyclonedx_sha = sha256_file(cyclonedx_path)
        actual_about_sha = sha256_file(about_path)
        if reports_metadata.get("cyclonedxSha256") not in {None, actual_cyclonedx_sha}:
            raise ValueError(f"{metadata_path}: CycloneDX hash does not match report")
        if reports_metadata.get("cargoAboutSha256") not in {None, actual_about_sha}:
            raise ValueError(f"{metadata_path}: cargo-about hash does not match report")
        sources.append(source)
        enrichment_reports.append({
            "platform": platform,
            "cyclonedxSha256": actual_cyclonedx_sha,
            "cargoAboutSha256": actual_about_sha,
            "cargoLockSha256": source.get("cargoLockSha256"),
            "sourceArchiveSha256": source.get("archiveSha256"),
            "sourceCommit": source.get("commit"),
        })

    if not sources:
        raise ValueError("at least one pgrx report is required")
    source_keys = {
        json.dumps({key: value for key, value in source.items() if key != "platform"}, sort_keys=True)
        for source in sources
    }
    if len(source_keys) != 1:
        raise ValueError("pgrx platforms disagree about source archive or Cargo.lock")

    for package in output.get("packages", []):
        if package.get("SPDXID", "").startswith("SPDXRef-Cargo-"):
            if not any(
                relationship.get("spdxElementId") == SPDX_DOCUMENT
                and relationship.get("relatedSpdxElement") == package["SPDXID"]
                and relationship.get("relationshipType") == "DESCRIBES"
                for relationship in output.get("relationships", [])
            ):
                output.setdefault("relationships", []).append({
                    "spdxElementId": SPDX_DOCUMENT,
                    "relationshipType": "DESCRIBES",
                    "relatedSpdxElement": package["SPDXID"],
                })

    merge_license_evidence(output, all_evidence)
    enrichment = {
        "schemaVersion": PGRX_NAMESPACE,
        "extension": extension_name,
        "source": deepcopy(sources[0]),
        "cargoReports": sorted(enrichment_reports, key=lambda value: value["platform"]),
        "buildSelection": {
            "cargo": read_json(reports[0][3]).get("cargo", {}),
            "dockerfile": str(dockerfile),
            "dockerfileSha256": sha256_file(dockerfile),
        },
        "wrapper": {
            "revision": wrapper_revision,
            "relationship": {
                "filesystemComposition": COMPOSITION_NAMESPACE,
                "cargoLicenseEnrichment": PGRX_NAMESPACE,
            },
        },
    }
    update_composition_annotation(output, enrichment)
    output["packages"].sort(key=lambda package: package["SPDXID"])
    output["relationships"] = sorted(
        output.get("relationships", []),
        key=lambda relationship: json.dumps(relationship, sort_keys=True),
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spdx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extension-name", required=True)
    parser.add_argument("--cargo-cyclonedx", type=Path, action="append", required=True)
    parser.add_argument("--cargo-about", type=Path, action="append", required=True)
    parser.add_argument("--pgrx-metadata", type=Path, action="append", required=True)
    parser.add_argument("--platform", action="append", required=True)
    parser.add_argument("--dockerfile", type=Path, required=True)
    parser.add_argument("--wrapper-revision", required=True)
    args = parser.parse_args()

    paths = [args.cargo_cyclonedx, args.cargo_about, args.pgrx_metadata, args.platform]
    if len({len(value) for value in paths}) != 1:
        parser.error("Cargo reports, metadata, and platforms must have the same number of values")
    reports = list(zip(args.platform, args.cargo_cyclonedx, args.cargo_about, args.pgrx_metadata))
    result = enrich(
        read_json(args.spdx),
        reports,
        extension_name=args.extension_name,
        dockerfile=args.dockerfile,
        wrapper_revision=args.wrapper_revision,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        f"enriched {len(result.get('packages', []))} packages and "
        f"{len(result.get('relationships', []))} relationships",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
