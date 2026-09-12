#!/usr/bin/env python3
"""Collect auditable dependency evidence for the pg_duckdb image.

The collector intentionally has a small, target-specific input format.  The
recipe describes identities and the places where a release records its
version; the build supplies the resolved source checkouts and runtime
library evidence.  This keeps source attribution separate from the neutral
filesystem SBOM composer.

The public ``collect_dependencies`` function is also used by the fixture
tests.  It fails closed for missing roots, ambiguous versions, unapproved
downloads, mismatched pins, missing license text, and duplicate identities.
An explicitly reviewed ``allowSnapshot`` recipe is the only way to represent
a source tree that has no independent release version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA = (
    "https://github.com/cnpg-extensions/postgres-extensions-containers/"
    "pg-duckdb-manifest/v1"
)
ALLOWED_CLASSIFICATIONS = {
    "compiled source",
    "used headers",
    "runtime shared library",
    "build/test-only",
    "unused source",
    "optional runtime download",
}
LICENSE_NAMES = ("LICENSE", "COPYING", "NOTICE")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class DependencyError(ValueError):
    """Raised when the build evidence cannot be attributed safely."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DependencyError(f"cannot read JSON evidence {path}: {error}") from error
    if not isinstance(value, dict):
        raise DependencyError(f"{path}: expected a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-") or "unknown"


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise DependencyError(f"path {path} is outside source root {root}") from error


def run_git(root: Path, *args: str) -> str | None:
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    value = result.stdout.strip()
    return value or None


def source_revision(root: Path, recipe: dict[str, Any]) -> str | None:
    current = root
    while True:
        revision = run_git(current, "rev-parse", "HEAD")
        if revision:
            return revision
        if current.parent == current:
            break
        current = current.parent
    for candidate in recipe.get("revisionEvidence", []):
        path = root / str(candidate)
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
    return None


def fingerprint(root: Path) -> str:
    """Hash paths and contents while excluding generated/build metadata."""

    digest = hashlib.sha256()
    ignored_parts = {".git", "build", "__pycache__", ".pytest_cache", "pg-duckdb-runtime", "pg-duckdb-sbom"}
    entries: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in ignored_parts for part in parts):
            continue
        if path.name.startswith("pg-duckdb-"):
            continue
        entries.append(path)
    for path in sorted(entries, key=lambda item: item.relative_to(root).as_posix()):
        name = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _version_matches(path: Path, pattern: str) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise DependencyError(f"cannot read version evidence {path}: {error}") from error
    try:
        matches = list(re.finditer(pattern, content, flags=re.MULTILINE))
    except re.error as error:
        raise DependencyError(f"invalid version pattern {pattern!r}: {error}") from error
    values: list[str] = []
    for match in matches:
        try:
            value = match.group("version")
        except IndexError:
            value = match.group(1) if match.groups() else match.group(0)
        if value not in values:
            values.append(value)
    return values


def extract_version(root: Path, recipe: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    specification = recipe.get("releaseVersion")
    if not specification:
        return None, {"status": "unresolved; no release version definition"}
    if not isinstance(specification, dict):
        raise DependencyError(f"{recipe.get('id')}: releaseVersion must be an object")
    paths = specification.get("paths") or [specification.get("path")]
    paths = [str(path) for path in paths if path]
    pattern = specification.get("pattern")
    if not paths or not isinstance(pattern, str):
        raise DependencyError(f"{recipe.get('id')}: incomplete releaseVersion evidence")
    values: list[str] = []
    evidence: list[str] = []
    for name in paths:
        path = root / name
        if not path.is_file():
            continue
        found = _version_matches(path, pattern)
        if found:
            evidence.append(name)
            values.extend(value for value in found if value not in values)
    if len(values) > 1:
        raise DependencyError(
            f"{recipe.get('id')}: ambiguous release version evidence: {values}"
        )
    if len(values) == 1:
        return values[0], {"status": "verified", "paths": evidence, "pattern": pattern}
    if recipe.get("allowSnapshot"):
        return None, {
            "status": "unresolved; reviewed snapshot fallback",
            "paths": paths,
            "pattern": pattern,
        }
    raise DependencyError(
        f"{recipe.get('id')}: release version is missing from {paths}; "
        "set allowSnapshot only after reviewing the source"
    )


def _candidate_roots(
    source_root: Path, build_root: Path, recipe: dict[str, Any]
) -> list[Path]:
    names = [recipe.get("sourceRoot"), *(recipe.get("sourceRootAlternatives") or [])]
    candidates: list[Path] = []
    for name in names:
        if not name:
            continue
        for base in (source_root, build_root):
            path = (base / str(name)).resolve()
            if path.is_dir() and path not in candidates:
                candidates.append(path)
    return candidates


def _license_paths(
    root: Path, recipe: dict[str, Any], source_scope: Path | None = None
) -> list[Path]:
    configured = recipe.get("licensePaths")
    paths: list[Path] = []
    if configured:
        for name in configured:
            path = (root / str(name)).resolve()
            if source_scope is not None:
                try:
                    path.relative_to(source_scope.resolve())
                except ValueError:
                    continue
            if path.is_file():
                paths.append(path)
    else:
        for name in LICENSE_NAMES:
            for path in root.glob(f"{name}*"):
                if path.is_file():
                    paths.append(path)
    unique = list(dict.fromkeys(paths))
    if not unique:
        raise DependencyError(f"{recipe.get('id')}: no complete license/notice file found")
    return unique


def _license_expression(recipe: dict[str, Any]) -> str:
    expression = str(recipe.get("licenseExpression") or "NOASSERTION")
    if not expression or expression == "NONE":
        raise DependencyError(f"{recipe.get('id')}: invalid empty license expression")
    # SPDX expressions and LicenseRef identifiers are deliberately validated
    # conservatively.  A full SPDX parser is unnecessary for this target, but
    # accepting arbitrary prose would make the generated document invalid.
    if not re.fullmatch(r"[A-Za-z0-9.+-]+(?:\s+(?:AND|OR|WITH)\s+[A-Za-z0-9.+-]+)*", expression):
        if expression != "NOASSERTION" and not re.fullmatch(
            r"[A-Za-z0-9.+-]+(?:\s+(?:AND|OR|WITH|\(|\))\s*[A-Za-z0-9.+-()]+)*",
            expression,
        ):
            raise DependencyError(f"{recipe.get('id')}: invalid SPDX license expression {expression!r}")
    return expression


def _configured_recipe_by_root(recipes: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for recipe in recipes:
        root = str(recipe.get("sourceRoot") or "")
        if root:
            result[root.rstrip("/")] = recipe
    return result


def _root_is_known(name: str, recipes: list[dict[str, Any]], vendor_root: str) -> bool:
    name = name.strip("/")
    known = [str(recipe.get("sourceRoot") or "").strip("/") for recipe in recipes]
    known.extend(
        str(alternative).strip("/")
        for recipe in recipes
        for alternative in recipe.get("sourceRootAlternatives", []) or []
    )
    known = [value for value in known if value]
    if vendor_root:
        known.append(vendor_root.strip("/"))
    if "." in known:
        return True
    return any(name == value or name.startswith(value + "/") for value in known)


def _validate_build_evidence(
    evidence: dict[str, Any], recipes: list[dict[str, Any]], vendor_root: str
) -> None:
    for field in ("dependencyRoots", "includedSourceRoots", "usedRoots"):
        values = evidence.get(field, []) or []
        if not isinstance(values, list):
            raise DependencyError(f"build evidence field {field} must be a list")
        for value in values:
            if not isinstance(value, str) or not _root_is_known(value, recipes, vendor_root):
                raise DependencyError(f"unknown dependency root used by build: {value!r}")


def _enabled_extensions(source_root: Path) -> list[dict[str, str]]:
    """Resolve the in-tree defaults and target-local DuckDB extensions."""

    paths = [
        source_root / "third_party/duckdb/extension/extension_config.cmake",
        source_root / "third_party/duckdb/extension/extension_config_local.cmake",
        source_root / "third_party/pg_duckdb_extensions.cmake",
    ]
    records: dict[str, dict[str, str]] = {}
    pattern = re.compile(r"duckdb_extension_load\(\s*([A-Za-z0-9_-]+)")
    for path in paths:
        if not path.is_file():
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8", errors="replace")):
            records.setdefault(match.group(1), {
                "name": match.group(1),
                "evidencePath": relative_path(path, source_root),
            })
    return [records[key] for key in sorted(records)]


def _generated_duckdb_version(build_root: Path) -> dict[str, Any] | None:
    build_paths = [
        path
        for path in build_root.rglob("*")
        if path.is_file()
        and path.name in {"CMakeCache.txt", "duckdb_platform_out", "options.hpp"}
        and "third_party/duckdb/build" in path.as_posix()
    ]
    values: list[str] = []
    evidence: list[str] = []
    pattern = re.compile(
        r"(?:DUCKDB_VERSION(?:_NUMBER)?|OVERRIDE_GIT_DESCRIBE|DUCKDB_GIT_DESCRIBE)"
        r"[^=\n]*=\s*[\"']?(?P<version>v?[0-9]+\.[0-9]+\.[0-9]+)"
    )
    for path in sorted(build_paths):
        content = path.read_text(encoding="utf-8", errors="replace")
        matches = [match.group("version") for match in pattern.finditer(content)]
        for value in matches:
            if value not in values:
                values.append(value)
                evidence.append(str(path))
    if len(values) > 1:
        raise DependencyError(f"DuckDB generated build version is ambiguous: {values}")
    if not values:
        return None
    return {"version": values[0], "paths": evidence}


def _source_resolution(build_root: Path, recipe_data: dict[str, Any], source_tag: str) -> dict[str, str]:
    """Read the immutable source-resolution records created before compilation."""

    names = {
        "extensionCommit": "pg-duckdb-release-commit.txt",
        "duckdbCommit": "pg-duckdb-duckdb-commit.txt",
        "sourceTag": "pg-duckdb-source-tag.txt",
        "sourceArchiveSha256": "pg-duckdb-source-archive-sha256.txt",
    }
    result = {}
    for key, filename in names.items():
        path = build_root / filename
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                result[key] = value
    extension = recipe_data.get("extension", {})
    expected_extension_commit = str(extension.get("commit") or "")
    if result.get("extensionCommit") and expected_extension_commit and result["extensionCommit"] != expected_extension_commit:
        raise DependencyError(
            "resolved pg_duckdb commit does not match the dependency recipe: "
            f"{result['extensionCommit']} != {expected_extension_commit}"
        )
    duckdb_recipe = next(
        (recipe for recipe in recipe_data.get("recipes", []) if recipe.get("id") == "duckdb"),
        {},
    )
    expected_duckdb_commit = str(duckdb_recipe.get("revision") or "")
    if result.get("duckdbCommit") and expected_duckdb_commit and result["duckdbCommit"] != expected_duckdb_commit:
        raise DependencyError(
            "resolved DuckDB gitlink does not match the dependency recipe: "
            f"{result['duckdbCommit']} != {expected_duckdb_commit}"
        )
    if result.get("sourceTag") and result["sourceTag"] != source_tag:
        raise DependencyError(
            f"resolved source tag does not match the build input: {result['sourceTag']} != {source_tag}"
        )
    return result


def _download_records(source_root: Path) -> list[dict[str, str]]:
    """Read CMake's explicit Git download declarations.

    pg_duckdb has one target-local extension configuration file.  Looking at
    that file and build evidence captures the network inputs without treating
    every URL in documentation or tests as a build dependency.
    """

    paths = [source_root / "third_party/pg_duckdb_extensions.cmake"]
    records: list[dict[str, str]] = []
    pattern = re.compile(
        r"duckdb_extension_load\(\s*(?P<name>[A-Za-z0-9_-]+)(?P<body>.*?)\n?\)",
        flags=re.DOTALL,
    )
    url_pattern = re.compile(r"GIT_URL\s+(?P<url>\S+)")
    tag_pattern = re.compile(r"GIT_TAG\s+(?P<revision>[0-9a-fA-F]{7,40})")
    for path in paths:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(content):
            url = url_pattern.search(match.group("body"))
            if not url:
                continue
            tag = tag_pattern.search(match.group("body"))
            records.append({
                "name": match.group("name"),
                "url": url.group("url"),
                "revision": tag.group("revision") if tag else "",
                "evidencePath": relative_path(path, source_root),
            })
    return records


def _validate_downloads(
    source_root: Path,
    recipe_data: dict[str, Any],
    build_evidence: dict[str, Any],
) -> list[dict[str, str]]:
    allowed = {}
    for record in recipe_data.get("downloads", []) or []:
        if not isinstance(record, dict):
            raise DependencyError("downloads entries must be objects")
        identity = str(record.get("identity") or record.get("url") or "")
        if identity in allowed:
            raise DependencyError(f"duplicate download identity: {identity}")
        allowed[identity] = record
    discovered = _download_records(source_root)
    discovered.extend(
        item for item in build_evidence.get("downloads", []) or [] if isinstance(item, dict)
    )
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in discovered:
        url = str(record.get("url") or record.get("gitUrl") or "")
        revision = str(record.get("revision") or record.get("gitTag") or "")
        if not url:
            raise DependencyError(f"unclassified build download: {record}")
        matches = [
            item for item in allowed.values()
            if url == str(item.get("url") or "")
            or url.rstrip("/").endswith(str(item.get("url") or "").rstrip("/"))
        ]
        if not matches:
            raise DependencyError(f"unclassified build download: {url}@{revision}")
        expected = matches[0]
        expected_revision = str(expected.get("revision") or "")
        if revision and expected_revision and revision != expected_revision:
            raise DependencyError(
                f"download pin mismatch for {url}: found {revision}, expected {expected_revision}"
            )
        key = (url, revision or expected_revision)
        if key not in seen:
            normalized.append({
                "identity": str(expected.get("identity") or expected.get("url")),
                "url": url,
                "revision": revision or expected_revision,
                "recipe": str(expected.get("recipe") or ""),
                "evidencePath": str(record.get("evidencePath") or "build evidence"),
            })
            seen.add(key)
    return sorted(normalized, key=lambda item: (item["identity"], item["revision"]))


def _component_id(
    identity: str, release_version: str | None, revision: str, platform: str
) -> str:
    material = "\0".join((identity, release_version or "NOASSERTION", revision, platform))
    return "SPDXRef-PgDuckDB-" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _copy_licenses(
    component: dict[str, Any], paths: list[Path], output_dir: Path, namespace: str
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    destination_root = output_dir / "licenses" / namespace
    destination_root.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(paths):
        destination = destination_root / f"{index:02d}-{path.name}"
        shutil.copyfile(path, destination)
        records.append({
            "sourcePath": str(path),
            "path": "/" + destination.relative_to(output_dir).as_posix(),
            "sha256": sha256_file(path),
        })
    return records


def _component_from_recipe(
    recipe: dict[str, Any],
    source_root: Path,
    build_root: Path,
    output_dir: Path,
    platform: str,
    source_tag: str,
    used_roots: set[str],
    build_used_roots: set[str],
    download_revisions: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    roots = _candidate_roots(source_root, build_root, recipe)
    if not roots:
        if recipe.get("required", False):
            raise DependencyError(
                f"{recipe.get('id')}: required source root is missing: "
                f"{recipe.get('sourceRoot')}"
            )
        return (
            {"id": str(recipe.get("id")), "status": "excluded", "reason": "source root absent"},
            {},
        )
    root = roots[0]
    relative_root = relative_path(root, source_root)
    version, version_evidence = extract_version(root, recipe)
    # FetchContent checkouts commonly omit their own .git directory.  For a
    # recipe that explicitly declares a download, the normalized download
    # record is the authoritative revision evidence after pin validation.
    revision = download_revisions.get(str(recipe.get("id"))) or source_revision(root, recipe)
    expected_revision = str(recipe.get("revision") or "")
    if expected_revision:
        if revision is None:
            raise DependencyError(f"{recipe.get('id')}: source revision cannot be resolved")
        if revision != expected_revision:
            raise DependencyError(
                f"{recipe.get('id')}: source revision mismatch: found {revision}, "
                f"expected {expected_revision}"
            )
    if not revision:
        raise DependencyError(
            f"{recipe.get('id')}: no source revision; add a reviewed revision evidence path"
        )
    if source_tag and recipe.get("sourceTag") and source_tag != recipe["sourceTag"]:
        raise DependencyError(
            f"{recipe.get('id')}: source tag mismatch: found {source_tag}, "
            f"expected {recipe['sourceTag']}"
        )
    licenses = _license_paths(root, recipe, source_root)
    classification = str(recipe.get("classification") or "")
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise DependencyError(f"{recipe.get('id')}: unknown classification {classification!r}")
    if str(recipe.get("sourceRoot")) in used_roots:
        # This is a recipe error, rather than a source duplicate.  Different
        # components may share a containing checkout, but cannot declare the
        # same component root twice.
        raise DependencyError(f"duplicate source root recipe: {recipe.get('sourceRoot')}")
    used_roots.add(str(recipe.get("sourceRoot")))
    identity = str(recipe.get("identity") or "")
    if not identity:
        raise DependencyError(f"{recipe.get('id')}: stable identity is required")
    namespace = (
        "pg-duckdb"
        if recipe.get("id") == "pg_duckdb"
        else "duckdb"
        if recipe.get("id") == "duckdb"
        else "third-party/" + clean_id(str(recipe.get("id")))
    )
    component: dict[str, Any] = {
        "id": str(recipe.get("id")),
        "spdxId": _component_id(identity, version, revision, platform),
        "identity": identity,
        "name": str(recipe.get("name") or recipe.get("id")),
        "repository": str(recipe.get("repository") or ""),
        "sourceRoot": relative_root,
        "parent": recipe.get("parent"),
        "releaseVersion": version,
        "sourceTag": recipe.get("sourceTag") or (source_tag if recipe.get("id") == "pg_duckdb" else None),
        "revision": revision,
        "sourceFingerprint": fingerprint(root),
        "versionEvidence": version_evidence,
        "licenseExpression": _license_expression(recipe),
        "license": {"files": _copy_licenses({}, licenses, output_dir, namespace)},
        "classification": classification,
        "target": str(recipe.get("target") or ""),
        "platform": platform,
        "shipped": classification
        not in {"build/test-only", "unused source", "optional runtime download"},
        "evidence": {
            "sourceRoot": relative_root,
            "licensePaths": [relative_path(path, source_root) for path in licenses],
        },
    }
    status = "included" if component["shipped"] else "excluded"
    if relative_root in build_used_roots or any(
        relative_root == value or relative_root.startswith(value.rstrip("/") + "/")
        for value in build_used_roots
    ):
        status = "included"
        component["shipped"] = True
    return component, {
        "id": component["id"],
        "identity": identity,
        "status": status,
        "reason": "included by recipe" if status == "included" else "recipe classification excludes shipped code",
        "sourceRoot": relative_root,
        "revision": revision,
        "releaseVersion": version,
    }


def _runtime_components(
    runtime_evidence: dict[str, Any], output_dir: Path, platform: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    components: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for record in runtime_evidence.get("libraries", []) or []:
        if not isinstance(record, dict):
            raise DependencyError("runtime library evidence entries must be objects")
        package = record.get("package") or {}
        if not isinstance(package, dict) or not package.get("name"):
            raise DependencyError(f"runtime library evidence lacks package identity: {record}")
        name = str(package["name"])
        version = str(package.get("version") or "")
        architecture = str(package.get("architecture") or "")
        if not version or not architecture:
            raise DependencyError(f"runtime package lacks version/architecture: {name}")
        identity = f"debian:{name}:{architecture}"
        revision = f"dpkg:{version}:{architecture}"
        license_paths = [Path(path) for path in package.get("licensePaths", []) or []]
        license_records: list[dict[str, str]] = []
        if license_paths:
            license_records = _copy_licenses(
                {}, [path for path in license_paths if path.is_file()], output_dir, "system/" + clean_id(name)
            )
        component = {
            "id": "debian-" + clean_id(name),
            "spdxId": _component_id(identity, version, revision, platform),
            "identity": identity,
            "name": name,
            "repository": "https://packages.debian.org/",
            "sourceRoot": "system/" + name,
            "parent": "pg_duckdb",
            "releaseVersion": version,
            "sourceTag": None,
            "revision": revision,
            "sourceFingerprint": str(package.get("fileChecksums") or ""),
            "versionEvidence": {"status": "dpkg-query", "path": "runtime-libraries.json"},
            "licenseExpression": str(package.get("licenseExpression") or "NOASSERTION"),
            "license": {"files": license_records},
            "classification": "runtime shared library",
            "target": "runtime-loader",
            "platform": platform,
            "shipped": bool(record.get("shipped", True)),
            "baseProvided": bool(record.get("baseProvided", False)),
            "sonames": sorted(str(value) for value in record.get("sonames", []) or []),
            "fileChecksums": record.get("fileChecksums", []),
            "evidence": {
                "resolvedPath": str(record.get("resolvedPath") or ""),
                "packagePurl": str(package.get("purl") or ""),
                "owner": name,
            },
        }
        components.append(component)
        coverage.append({
            "id": component["id"],
            "identity": identity,
            "status": "included" if component["shipped"] else "excluded",
            "reason": "runtime library closure",
            "sourceRoot": component["sourceRoot"],
            "revision": revision,
            "releaseVersion": version,
        })
    return components, coverage


def collect_dependencies(
    source_root: Path,
    *,
    build_root: Path | None = None,
    recipe_path: Path | None = None,
    output_dir: Path | None = None,
    platform: str = "linux/amd64",
    pg_major: str = "18",
    source_tag: str = "",
    runtime_evidence_path: Path | None = None,
    build_evidence_path: Path | None = None,
    build_inputs_path: Path | None = None,
    require_build_evidence: bool = False,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    build_root = (build_root or source_root).resolve()
    recipe_path = recipe_path or Path(__file__).with_name("dependencies.json")
    recipe_data = read_json(recipe_path)
    recipes = recipe_data.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise DependencyError("recipe must contain a non-empty recipes list")
    if not source_tag:
        source_tag = str(recipe_data.get("extension", {}).get("tag") or "")
    if not source_tag:
        raise DependencyError("source release tag is required")
    if not platform:
        raise DependencyError("build platform is required")
    if output_dir is None:
        output_dir = build_root / "pg-duckdb-sbom"
    output_dir.mkdir(parents=True, exist_ok=True)

    identities: dict[str, str] = {}
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise DependencyError("recipe entries must be objects")
        identity = str(recipe.get("identity") or "")
        recipe_id = str(recipe.get("id") or "")
        if not identity or not recipe_id:
            raise DependencyError("every recipe needs id and stable identity")
        if identity in identities:
            raise DependencyError(
                f"duplicate component identity {identity}: {identities[identity]} and {recipe_id}"
            )
        identities[identity] = recipe_id
    build_evidence: dict[str, Any] = {}
    if build_evidence_path and build_evidence_path.is_file():
        build_evidence = read_json(build_evidence_path)
    elif require_build_evidence:
        raise DependencyError(f"required build evidence is missing: {build_evidence_path}")
    build_inputs: dict[str, Any] = {}
    if build_inputs_path and build_inputs_path.is_file():
        build_inputs = read_json(build_inputs_path)
    elif build_inputs_path:
        raise DependencyError(f"required build input evidence is missing: {build_inputs_path}")
    vendor_root = str(recipe_data.get("vendorDefaults", {}).get("root") or "")
    for required_root in recipe_data.get("policies", {}).get("requiredRoots", []) or []:
        if not (source_root / str(required_root)).exists():
            raise DependencyError(f"required dependency root is missing: {required_root}")
    _validate_build_evidence(build_evidence, recipes, vendor_root)
    downloads = _validate_downloads(source_root, recipe_data, build_evidence)
    download_revisions = {
        str(record["recipe"]): str(record["revision"])
        for record in downloads
        if record.get("recipe") and record.get("revision")
    }
    source_resolution = _source_resolution(build_root, recipe_data, source_tag)
    enabled_extensions = _enabled_extensions(source_root)
    extension_recipes = {
        str(recipe.get("extensionName")): recipe
        for recipe in recipes
        if recipe.get("extensionName")
    }
    for extension in enabled_extensions:
        if extension["name"] not in extension_recipes:
            raise DependencyError(
                f"unclassified enabled DuckDB extension target: {extension['name']}"
            )

    components: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    used_roots: set[str] = set()
    build_used_roots = {
        str(value).strip("/")
        for value in build_evidence.get("usedRoots", []) or []
        if isinstance(value, str)
    }
    recipe_roots = _configured_recipe_by_root(recipes)
    for recipe in recipes:
        component, record = _component_from_recipe(
            recipe,
            source_root,
            build_root,
            output_dir,
            platform,
            source_tag,
            used_roots,
            build_used_roots,
            download_revisions,
        )
        coverage.append(record)
        if component.get("spdxId"):
            components.append(component)

    # Inventory licensed DuckDB vendor directories even when the linker has
    # eliminated every object from one of them.  They remain explicit excluded
    # coverage records, and a future build evidence file can promote one by
    # naming its root in usedRoots.
    vendor_path = source_root / vendor_root
    explicit_roots = set(recipe_roots)
    if vendor_path.is_dir():
        for child in sorted(vendor_path.iterdir()):
            if not child.is_dir() or child.name in {".git", "build"}:
                continue
            child_root = relative_path(child, source_root)
            if any(
                child_root == root or child_root.startswith(root.rstrip("/") + "/")
                for root in explicit_roots
            ):
                continue
            licenses = [
                path
                for name in LICENSE_NAMES
                for path in child.glob(f"{name}*")
                if path.is_file()
            ]
            if not licenses:
                coverage.append({
                    "id": "vendor-" + clean_id(child.name),
                    "identity": f"github.com/duckdb/duckdb/{child_root}",
                    "status": "unresolved",
                    "reason": "vendor has no license evidence and is not explicitly classified",
                    "sourceRoot": child_root,
                })
                continue
            vendor_id = "vendor-" + clean_id(child.name)
            identity = f"github.com/duckdb/duckdb/{child_root}"
            revision = source_revision(child, {"revisionEvidence": []}) or source_revision(
                source_root / "third_party/duckdb", {"revisionEvidence": []}
            )
            if not revision:
                raise DependencyError(f"{identity}: containing repository revision is missing")
            is_used = child_root in set(str(value) for value in build_evidence.get("usedRoots", []) or [])
            component = {
                "id": vendor_id,
                "spdxId": _component_id(identity, None, revision + ":" + fingerprint(child), platform),
                "identity": identity,
                "name": child.name,
                "repository": "https://github.com/duckdb/duckdb",
                "sourceRoot": child_root,
                "parent": "duckdb",
                "releaseVersion": None,
                "sourceTag": source_tag,
                "revision": revision,
                "sourceFingerprint": fingerprint(child),
                "versionEvidence": {
                    "status": "unresolved; reviewed containing-repository snapshot",
                    "containingRepositoryRevision": revision,
                },
                "licenseExpression": "NOASSERTION",
                "license": {
                    "files": _copy_licenses(
                        {}, licenses, output_dir, "third-party/" + clean_id(child.name)
                    )
                },
                "classification": "compiled source" if is_used else "unused source",
                "target": "bundle-library" if is_used else "source inventory",
                "platform": platform,
                "shipped": is_used,
                "evidence": {"sourceRoot": child_root},
            }
            components.append(component)
            coverage.append({
                "id": vendor_id,
                "identity": identity,
                "status": "included" if is_used else "excluded",
                "reason": "named by build evidence" if is_used else "licensed source inventory; no build-use evidence",
                "sourceRoot": child_root,
                "revision": revision,
                "releaseVersion": None,
            })

    runtime_components: list[dict[str, Any]] = []
    runtime_coverage: list[dict[str, Any]] = []
    if runtime_evidence_path and runtime_evidence_path.is_file():
        runtime_evidence = read_json(runtime_evidence_path)
        runtime_components, runtime_coverage = _runtime_components(
            runtime_evidence, output_dir, platform
        )
    components.extend(runtime_components)
    coverage.extend(runtime_coverage)

    component_ids = {str(component["id"]) for component in components}
    if len(component_ids) != len(components):
        raise DependencyError("duplicate component IDs after dependency discovery")
    unresolved = [record for record in coverage if record.get("status") == "unresolved"]
    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA,
        "extension": {
            "name": str(recipe_data.get("extension", {}).get("name") or "pg_duckdb"),
            "repository": str(recipe_data.get("extension", {}).get("repository") or ""),
            "sourceTag": source_tag,
            "sourceCommit": str(recipe_data.get("extension", {}).get("commit") or ""),
            "sqlVersion": str(recipe_data.get("extension", {}).get("sqlVersion") or ""),
        },
        "build": {
            "platform": platform,
            "pgMajor": str(pg_major),
            "target": "DUCKDB_BUILD=ReleaseStatic make install",
            "staticDuckDB": True,
            "enabledExtensions": enabled_extensions,
            "generatedDuckdbVersion": _generated_duckdb_version(build_root),
            "sourceResolution": source_resolution,
            "sourceRoot": str(source_root),
            "recipeSha256": sha256_file(recipe_path),
            "buildEvidenceSha256": sha256_file(build_evidence_path)
            if build_evidence_path and build_evidence_path.is_file()
            else None,
            "buildInputs": build_inputs,
            "buildInputsSha256": sha256_file(build_inputs_path)
            if build_inputs_path and build_inputs_path.is_file()
            else None,
            "runtimeEvidenceSha256": sha256_file(runtime_evidence_path)
            if runtime_evidence_path and runtime_evidence_path.is_file()
            else None,
        },
        "components": sorted(components, key=lambda item: str(item["spdxId"])),
        "downloads": downloads,
        "coverage": {
            "discovered": len(coverage),
            "included": sum(record.get("status") == "included" for record in coverage),
            "excluded": sum(record.get("status") == "excluded" for record in coverage),
            "unresolved": len(unresolved),
            "records": sorted(coverage, key=lambda item: (str(item.get("identity")), str(item.get("id")))),
        },
        "evidence": {
            "recipe": str(recipe_path),
            "buildEvidence": str(build_evidence_path) if build_evidence_path else None,
            "runtimeEvidence": str(runtime_evidence_path) if runtime_evidence_path else None,
            "sourceFingerprint": fingerprint(source_root),
            "sourcePins": [
                {
                    "identity": component["identity"],
                    "sourceTag": component.get("sourceTag"),
                    "releaseVersion": component.get("releaseVersion"),
                    "revision": component.get("revision"),
                    "sourceFingerprint": component.get("sourceFingerprint"),
                }
                for component in sorted(components, key=lambda item: str(item["identity"]))
            ],
        },
    }
    return manifest


def write_outputs(manifest: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "resolved-manifest.json": manifest,
        "coverage.json": {
            "schemaVersion": manifest["schemaVersion"],
            "platform": manifest["build"]["platform"],
            **manifest["coverage"],
        },
        "license-index.json": {
            "schemaVersion": manifest["schemaVersion"],
            "platform": manifest["build"]["platform"],
            "components": [
                {
                    "id": component["id"],
                    "identity": component["identity"],
                    "expression": component["licenseExpression"],
                    "files": component.get("license", {}).get("files", []),
                }
                for component in manifest["components"]
            ],
        },
        "build-source-evidence.json": {
            "schemaVersion": manifest["schemaVersion"],
            "build": manifest["build"],
            "downloads": manifest["downloads"],
            "sourcePins": manifest["evidence"]["sourcePins"],
        },
    }
    for name, value in files.items():
        (output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, default=None)
    parser.add_argument("--recipe", type=Path, default=Path(__file__).with_name("dependencies.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--platform", default=os.environ.get("TARGETPLATFORM", "linux/amd64"))
    parser.add_argument("--pg-major", default=os.environ.get("PG_MAJOR", "18"))
    parser.add_argument("--source-tag", default=os.environ.get("EXT_VERSION", ""))
    parser.add_argument("--runtime-evidence", type=Path, default=None)
    parser.add_argument("--build-evidence", type=Path, default=None)
    parser.add_argument("--build-inputs", type=Path, default=None)
    parser.add_argument("--require-build-evidence", action="store_true")
    args = parser.parse_args()
    try:
        manifest = collect_dependencies(
            args.source_root,
            build_root=args.build_root,
            recipe_path=args.recipe,
            output_dir=args.output_dir,
            platform=args.platform,
            pg_major=args.pg_major,
            source_tag=args.source_tag,
            runtime_evidence_path=args.runtime_evidence,
            build_evidence_path=args.build_evidence,
            build_inputs_path=args.build_inputs,
            require_build_evidence=args.require_build_evidence,
        )
        write_outputs(manifest, args.output_dir)
    except DependencyError as error:
        print(f"collect_dependencies: {error}", file=sys.stderr)
        return 2
    print(
        f"collected {len(manifest['components'])} components; "
        f"{manifest['coverage']['included']} included, "
        f"{manifest['coverage']['excluded']} excluded",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
