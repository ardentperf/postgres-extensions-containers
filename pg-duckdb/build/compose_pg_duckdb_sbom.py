#!/usr/bin/env python3
"""Merge pg_duckdb source and runtime evidence into a neutral SPDX document.

``scripts/compose_sbom.py`` owns final-image files, Debian ownership, and the
document namespace.  This merger only adds verified pg_duckdb/DuckDB source
components, connects them to the shipped extension payload, and records the
per-platform evidence used to make those claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform as host_platform
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


MANIFEST_SCHEMA = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "pg-duckdb-manifest/v1"
)
COMPOSITION_NAMESPACE = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "sbom-composition/v1"
)
SPDX_DOCUMENT = "SPDXRef-DOCUMENT"
NOASSERTION = "NOASSERTION"
LICENSE_TOKEN = re.compile(r"LicenseRef-[A-Za-z0-9][A-Za-z0-9.-]*")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-") or "unknown"


def _license_expression(value: Any) -> str:
    expression = str(value or NOASSERTION)
    if expression == "NONE" or not expression:
        raise ValueError("manifest contains an empty license expression")
    return expression


def validate_manifest(manifest: dict[str, Any], path: Path, platform: str) -> None:
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA:
        raise ValueError(f"{path}: unsupported pg_duckdb manifest schema")
    if not platform:
        raise ValueError(f"{path}: platform is required")
    build = manifest.get("build")
    if not isinstance(build, dict) or build.get("platform") != platform:
        raise ValueError(f"{path}: manifest platform does not match {platform}")
    components = manifest.get("components")
    if not isinstance(components, list):
        raise ValueError(f"{path}: components must be a list")
    ids: set[str] = set()
    identities: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError(f"{path}: component records must be objects")
        component_id = str(component.get("spdxId") or "")
        identity = str(component.get("identity") or "")
        revision = str(component.get("revision") or "")
        if not component_id or component_id in ids:
            raise ValueError(f"{path}: duplicate or missing component SPDX ID")
        if not identity or identity in identities:
            raise ValueError(f"{path}: duplicate or missing component identity {identity!r}")
        if not revision:
            raise ValueError(f"{path}: {identity} has no exact source revision")
        classification = str(component.get("classification") or "")
        if classification not in {
            "compiled source",
            "used headers",
            "runtime shared library",
            "build/test-only",
            "unused source",
            "optional runtime download",
        }:
            raise ValueError(f"{path}: {identity} has unknown classification {classification!r}")
        release_version = component.get("releaseVersion")
        if release_version is None:
            status = str(component.get("versionEvidence", {}).get("status") or "")
            if "unresolved" not in status and classification != "runtime shared library":
                raise ValueError(f"{path}: {identity} has no release version or reviewed fallback")
        _license_expression(component.get("licenseExpression"))
        license_record = component.get("license")
        if not isinstance(license_record, dict) or not isinstance(license_record.get("files"), list):
            raise ValueError(f"{path}: {identity} has no license evidence list")
        for license_file in license_record["files"]:
            if not isinstance(license_file, dict) or not str(license_file.get("path", "")).startswith("/"):
                raise ValueError(f"{path}: {identity} has an invalid license evidence path")
            checksum = str(license_file.get("sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError(f"{path}: {identity} has an invalid license checksum")
        ids.add(component_id)
        identities.add(identity)
    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict) or not isinstance(coverage.get("records"), list):
        raise ValueError(f"{path}: coverage report is missing")
    for download in manifest.get("downloads", []) or []:
        if not isinstance(download, dict) or not download.get("identity") or not download.get("revision"):
            raise ValueError(f"{path}: unpinned runtime/build download")


def _source_purl(component: dict[str, Any]) -> str | None:
    repository = str(component.get("repository") or "")
    match = re.search(r"github\.com/([^/]+)/([^/#]+)", repository)
    if not match:
        purl = str(component.get("evidence", {}).get("packagePurl") or "")
        return purl or None
    if component.get("id") == "pg_duckdb":
        version = str(component.get("sourceTag") or component.get("revision") or "")
    else:
        version = str(component.get("releaseVersion") or component.get("revision") or "")
    if not version:
        return None
    return f"pkg:github/{match.group(1)}/{match.group(2).removesuffix('.git')}@{version}"


def _license_evidence_text(
    license_file: dict[str, Any], evidence_roots: Iterable[Path]
) -> str:
    source_path = str(license_file.get("sourcePath") or "")
    image_path = str(license_file.get("path") or "")
    candidates = []
    if source_path:
        candidates.append(Path(source_path))
    if image_path:
        candidates.extend(root / image_path.lstrip("/") for root in evidence_roots)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return f"Full license text is packaged at {image_path}."


def _package_from_component(component: dict[str, Any]) -> dict[str, Any]:
    version = str(component.get("releaseVersion") or component.get("revision") or NOASSERTION)
    package: dict[str, Any] = {
        "SPDXID": component["spdxId"],
        "copyrightText": NOASSERTION,
        "downloadLocation": str(component.get("repository") or NOASSERTION),
        "filesAnalyzed": False,
        "licenseConcluded": NOASSERTION,
        "licenseDeclared": _license_expression(component.get("licenseExpression")),
        "name": str(component.get("name") or component["id"]),
        "supplier": NOASSERTION,
        "versionInfo": version,
        "packageComment": (
            f"pg_duckdb source evidence: root={component.get('sourceRoot')}; "
            f"classification={component.get('classification')}; "
            f"revision={component.get('revision')}"
        ),
    }
    purl = _source_purl(component)
    if purl:
        package["externalRefs"] = [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceLocator": purl,
            "referenceType": "purl",
        }]
    if component.get("baseProvided"):
        package["packageComment"] += "; base-image runtime requirement"
    return package


def _relationship_key(relationship: dict[str, Any]) -> str:
    return json.dumps(relationship, sort_keys=True, separators=(",", ":"))


def _add_relationship(
    relationships: list[dict[str, Any]], seen: set[str], relationship: dict[str, Any]
) -> None:
    if relationship["spdxElementId"] == relationship["relatedSpdxElement"]:
        return
    key = _relationship_key(relationship)
    if key not in seen:
        relationships.append(relationship)
        seen.add(key)


def _existing_package_for_component(
    component: dict[str, Any], packages: list[dict[str, Any]]
) -> str | None:
    # Source components retain platform-specific IDs so the aggregate does
    # not erase a platform distinction. Debian runtime records are reconciled
    # with neutral composer package records by their purl.
    if component.get("classification") != "runtime shared library":
        return None
    purl = _source_purl(component)
    if not purl:
        purl = str(component.get("evidence", {}).get("packagePurl") or "")
    if not purl:
        return None
    for package in packages:
        for reference in package.get("externalRefs", []) or []:
            if reference.get("referenceType") == "purl" and reference.get("referenceLocator") == purl:
                return str(package.get("SPDXID"))
    return None


def _payload_package_id(document: dict[str, Any], extension_name: str) -> str:
    packages = document.get("packages", [])
    preferred = {
        "SPDXRef-Package-extension-payload",
        f"SPDXRef-Package-{extension_name}-extension-artifacts",
    }
    for package in packages:
        if package.get("SPDXID") in preferred:
            return str(package["SPDXID"])
    for package in packages:
        if package.get("name") in {extension_name, f"{extension_name}-extension-artifacts"}:
            return str(package["SPDXID"])
    raise ValueError(f"neutral SPDX document has no {extension_name} payload package")


def _merge_license_infos(
    document: dict[str, Any], components: list[dict[str, Any]], evidence_roots: Iterable[Path]
) -> None:
    records = {
        str(item.get("licenseId")): item
        for item in document.get("hasExtractedLicensingInfos", [])
        if isinstance(item, dict) and item.get("licenseId")
    }
    for component in components:
        expression = str(component.get("licenseExpression") or NOASSERTION)
        license_files = component.get("license", {}).get("files", [])
        for license_id in LICENSE_TOKEN.findall(expression):
            text = "\n\n".join(
                _license_evidence_text(item, evidence_roots) for item in license_files
            ) or NOASSERTION
            records.setdefault(license_id, {
                "extractedText": text,
                "licenseId": license_id,
                "name": license_id,
            })
    document["hasExtractedLicensingInfos"] = [records[key] for key in sorted(records)]


def _update_annotation(
    document: dict[str, Any],
    manifests: list[tuple[str, Path, dict[str, Any]]],
    extension_name: str,
) -> None:
    annotation = None
    for candidate in document.get("annotations", []) or []:
        if (
            candidate.get("spdxElementId") == SPDX_DOCUMENT
            and candidate.get("annotationType") == "OTHER"
            and str(candidate.get("comment", "")).startswith(COMPOSITION_NAMESPACE + " ")
        ):
            annotation = candidate
            break
    if annotation is None:
        raise ValueError("existing PR 61 composition annotation was not found")
    raw = str(annotation["comment"])[len(COMPOSITION_NAMESPACE) + 1 :]
    try:
        composition = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("existing composition annotation is not JSON") from error
    evidence_records = []
    source_pins = []
    for platform, path, manifest in manifests:
        evidence_records.append({
            "platform": platform,
            "manifestSha256": sha256_file(path),
            "recipeSha256": manifest["build"].get("recipeSha256"),
            "buildEvidenceSha256": manifest["build"].get("buildEvidenceSha256"),
            "buildInputsSha256": manifest["build"].get("buildInputsSha256"),
            "runtimeEvidenceSha256": manifest["build"].get("runtimeEvidenceSha256"),
            "buildInputs": manifest["build"].get("buildInputs", {}),
        })
        source_pins.extend(manifest.get("evidence", {}).get("sourcePins", []))
    composition["pgDuckdb"] = {
        "schemaVersion": MANIFEST_SCHEMA,
        "extension": extension_name,
        "manifests": sorted(evidence_records, key=lambda item: item["platform"]),
        "sourcePins": sorted(
            source_pins,
            key=lambda item: (str(item.get("identity")), str(item.get("revision")), str(item.get("sourceFingerprint"))),
        ),
        "downloads": [
            json.loads(value)
            for value in sorted({
                json.dumps(download, sort_keys=True, separators=(",", ":"))
                for _, _, manifest in manifests
                for download in manifest.get("downloads", [])
            })
        ],
        "composer": {
            "python": host_platform.python_version(),
            "scriptSha256": sha256_file(Path(__file__)),
        },
    }
    # Keep the annotation compact and deterministic so the exact predicate
    # bytes remain reproducible for the same image evidence.
    annotation["comment"] = COMPOSITION_NAMESPACE + " " + json.dumps(
        composition, sort_keys=True, separators=(",", ":")
    )


def compose(
    document: dict[str, Any],
    manifests: list[tuple[str, Path, dict[str, Any]]],
    *,
    extension_name: str,
    evidence_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    if not manifests:
        raise ValueError("at least one pg_duckdb manifest is required")
    platforms = [platform for platform, _, _ in manifests]
    if len(set(platforms)) != len(platforms):
        raise ValueError("pg_duckdb manifest platforms must be unique")
    output = deepcopy(document)
    payload_id = _payload_package_id(output, extension_name)
    packages = output.setdefault("packages", [])
    package_by_id = {
        str(package["SPDXID"]): package
        for package in packages
        if package.get("SPDXID")
    }
    component_to_package: dict[tuple[str, str], str] = {}
    included_components: list[dict[str, Any]] = []
    all_components: list[dict[str, Any]] = []
    for platform, path, manifest in manifests:
        validate_manifest(manifest, path, platform)
        for component in manifest["components"]:
            all_components.append(component)
            if not component.get("shipped", False):
                continue
            existing_id = _existing_package_for_component(component, packages)
            package_id = existing_id or str(component["spdxId"])
            if package_id not in package_by_id:
                package = _package_from_component(component)
                package["SPDXID"] = package_id
                packages.append(package)
                package_by_id[package_id] = package
            component_to_package[(platform, str(component["id"]))] = package_id
            included_components.append(component)

    relationships = output.setdefault("relationships", [])
    relationship_seen = {_relationship_key(item) for item in relationships}
    for platform, _, manifest in manifests:
        local_map = {
            str(component["id"]): component_to_package[(platform, str(component["id"]))]
            for component in manifest["components"]
            if component.get("shipped", False)
            and (platform, str(component["id"])) in component_to_package
        }
        for component in manifest["components"]:
            component_id = str(component.get("id"))
            package_id = local_map.get(component_id)
            if not package_id:
                continue
            _add_relationship(
                relationships,
                relationship_seen,
                {
                    "spdxElementId": package_id,
                    "relationshipType": "DEPENDENCY_OF",
                    "relatedSpdxElement": payload_id,
                },
            )
            parent = component.get("parent")
            if parent and str(parent) in local_map:
                _add_relationship(
                    relationships,
                    relationship_seen,
                    {
                        "spdxElementId": local_map[str(parent)],
                        "relationshipType": "CONTAINS",
                        "relatedSpdxElement": package_id,
                    },
                )
            if component.get("baseProvided"):
                _add_relationship(
                    relationships,
                    relationship_seen,
                    {
                        "spdxElementId": package_id,
                        "relationshipType": "RUNTIME_DEPENDENCY_OF",
                        "relatedSpdxElement": payload_id,
                    },
                )

    for package_id in sorted(set(component_to_package.values())):
        if not any(
            relationship.get("spdxElementId") == SPDX_DOCUMENT
            and relationship.get("relationshipType") == "DESCRIBES"
            and relationship.get("relatedSpdxElement") == package_id
            for relationship in relationships
        ):
            _add_relationship(
                relationships,
                relationship_seen,
                {
                    "spdxElementId": SPDX_DOCUMENT,
                    "relationshipType": "DESCRIBES",
                    "relatedSpdxElement": package_id,
                },
            )
    _merge_license_infos(output, all_components, evidence_roots)
    _update_annotation(output, manifests, extension_name)

    known_ids = {SPDX_DOCUMENT}
    known_ids.update(str(package.get("SPDXID")) for package in output.get("packages", []))
    known_ids.update(str(record.get("SPDXID")) for record in output.get("files", []))
    for relationship in relationships:
        if relationship.get("spdxElementId") not in known_ids or relationship.get("relatedSpdxElement") not in known_ids:
            raise ValueError(f"dangling SPDX relationship: {relationship}")
    packages.sort(key=lambda item: str(item.get("SPDXID")))
    output["relationships"] = sorted(relationships, key=_relationship_key)
    output["hasExtractedLicensingInfos"] = sorted(
        output.get("hasExtractedLicensingInfos", []),
        key=lambda item: str(item.get("licenseId")),
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spdx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extension-name", required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--platform", action="append", required=True)
    parser.add_argument("--evidence-root", type=Path, action="append", default=[])
    args = parser.parse_args()
    if len(args.manifest) != len(args.platform):
        parser.error("--manifest and --platform must have the same number of values")
    records = []
    for platform, path in zip(args.platform, args.manifest):
        records.append((platform, path, read_json(path)))
    try:
        output = compose(
            read_json(args.spdx),
            records,
            extension_name=args.extension_name,
            evidence_roots=args.evidence_root,
        )
    except ValueError as error:
        print(f"compose_pg_duckdb_sbom: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"enriched {len(output.get('packages', []))} packages and "
        f"{len(output.get('relationships', []))} relationships",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
