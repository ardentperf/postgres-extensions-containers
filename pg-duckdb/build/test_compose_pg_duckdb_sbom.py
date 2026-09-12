import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import compose_pg_duckdb_sbom as composer  # noqa: E402


def base_document():
    return {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "pg-duckdb-multi-platform-sbom",
        "documentNamespace": "https://example.test/sbom",
        "packages": [{
            "SPDXID": "SPDXRef-Package-extension-payload",
            "name": "pg-duckdb-extension-artifacts",
            "supplier": "NOASSERTION",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "MIT",
            "versionInfo": "v1.1.1",
        }],
        "files": [],
        "relationships": [{
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-extension-payload",
        }],
        "annotations": [{
            "spdxElementId": "SPDXRef-DOCUMENT",
            "annotationType": "OTHER",
            "annotator": "Tool: test",
            "annotationDate": "2026-09-11T00:00:00Z",
            "comment": composer.COMPOSITION_NAMESPACE + " " + json.dumps({"neutral": True}),
        }],
        "hasExtractedLicensingInfos": [],
    }


def manifest(platform, license_path):
    checksum = hashlib.sha256(license_path.read_bytes()).hexdigest()

    def component(component_id, identity, name, parent, release, classification="compiled source", base=False):
        return {
            "id": component_id,
            "spdxId": "SPDXRef-" + platform.replace("/", "-") + "-" + component_id,
            "identity": identity,
            "name": name,
            "repository": "https://github.com/duckdb/" + name,
            "sourceRoot": component_id,
            "parent": parent,
            "releaseVersion": release,
            "sourceTag": "v1.1.1" if component_id == "pg_duckdb" else None,
            "revision": "a" * 40,
            "sourceFingerprint": "b" * 64,
            "versionEvidence": {"status": "verified"},
            "licenseExpression": "MIT",
            "license": {"files": [{
                "sourcePath": str(license_path),
                "path": "/licenses/test/LICENSE",
                "sha256": checksum,
            }]},
            "classification": classification,
            "target": "test",
            "platform": platform,
            "shipped": classification != "build/test-only",
            "baseProvided": base,
            "evidence": {"sourceRoot": component_id},
        }

    root = component("pg_duckdb", "github.com/duckdb/pg_duckdb", "pg_duckdb", None, "1.1.0")
    duckdb = component("duckdb", "github.com/duckdb/duckdb", "duckdb", "pg_duckdb", "v1.4.3")
    return {
        "schemaVersion": composer.MANIFEST_SCHEMA,
        "extension": {"name": "pg_duckdb"},
        "build": {
            "platform": platform,
            "recipeSha256": "c" * 64,
            "buildEvidenceSha256": "d" * 64,
            "runtimeEvidenceSha256": "e" * 64,
        },
        "components": [root, duckdb],
        "downloads": [{"identity": "github.com/duckdb/duckdb-httpfs", "revision": "f" * 40}],
        "coverage": {"records": [{"identity": root["identity"], "status": "included"}]},
        "evidence": {"sourcePins": [{"identity": root["identity"], "revision": root["revision"]}]},
    }


class ComposerTest(unittest.TestCase):
    def test_spdx_relationships_and_license_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            license_path = directory / "LICENSE"
            license_path.write_text("MIT full text\n", encoding="utf-8")
            manifest_path = directory / "manifest.json"
            manifest_path.write_text(json.dumps(manifest("linux/amd64", license_path)), encoding="utf-8")
            result = composer.compose(
                base_document(),
                [("linux/amd64", manifest_path, composer.read_json(manifest_path))],
                extension_name="pg-duckdb",
                evidence_roots=[directory],
            )
            names = {package["name"] for package in result["packages"]}
            self.assertIn("pg_duckdb", names)
            self.assertIn("duckdb", names)
            self.assertTrue(any(rel["relationshipType"] == "CONTAINS" for rel in result["relationships"]))
            ids = {package["SPDXID"] for package in result["packages"]} | {"SPDXRef-DOCUMENT"}
            ids.update(file["SPDXID"] for file in result["files"])
            for relationship in result["relationships"]:
                self.assertIn(relationship["spdxElementId"], ids)
                self.assertIn(relationship["relatedSpdxElement"], ids)
            annotation = result["annotations"][0]["comment"]
            self.assertIn("pgDuckdb", annotation)
            self.assertIn("neutral", annotation)

    def test_platforms_are_preserved_and_composition_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            license_path = directory / "LICENSE"
            license_path.write_text("MIT\n", encoding="utf-8")
            paths = []
            records = []
            for platform in ("linux/amd64", "linux/arm64"):
                path = directory / (platform.replace("/", "-") + ".json")
                path.write_text(json.dumps(manifest(platform, license_path)), encoding="utf-8")
                paths.append(path)
                records.append((platform, path, composer.read_json(path)))
            first = composer.compose(base_document(), records, extension_name="pg-duckdb", evidence_roots=[directory])
            source_packages = [
                package for package in first["packages"]
                if package["name"] in {"pg_duckdb", "duckdb"}
            ]
            self.assertEqual(len(source_packages), 4)
            second = composer.compose(first, records, extension_name="pg-duckdb", evidence_roots=[directory])
            self.assertEqual(first, second)

    def test_invalid_duplicate_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            license_path = directory / "LICENSE"
            license_path.write_text("MIT\n", encoding="utf-8")
            value = manifest("linux/amd64", license_path)
            duplicate = dict(value["components"][1])
            duplicate["id"] = "duplicate"
            duplicate["spdxId"] = "SPDXRef-duplicate"
            value["components"].append(duplicate)
            path = directory / "manifest.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate.*identity"):
                composer.compose(
                    base_document(),
                    [("linux/amd64", path, composer.read_json(path))],
                    extension_name="pg-duckdb",
                )


if __name__ == "__main__":
    unittest.main()
