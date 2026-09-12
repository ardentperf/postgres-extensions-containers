import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import collect_dependencies as collector  # noqa: E402


REVISION = "a" * 40


def recipe(component_id="root", identity=None, source_root=".", **extra):
    value = {
        "id": component_id,
        "identity": identity or f"example.test/{component_id}",
        "repository": "https://example.test/source",
        "sourceRoot": source_root,
        "parent": None,
        "releaseVersion": {
            "path": "pg_duckdb.control" if source_root == "." else "VERSION",
            "pattern": "default_version\\s*=\\s*'(?P<version>[0-9.]+)'"
            if source_root == "."
            else "VERSION=(?P<version>[0-9.]+)",
        },
        "revisionEvidence": ["REVISION" if source_root == "." else "../REVISION"],
        "licensePaths": ["LICENSE"],
        "licenseExpression": "MIT",
        "classification": "compiled source",
        "target": "test",
        "required": True,
    }
    value.update(extra)
    return value


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        (self.root / "pg_duckdb.control").write_text(
            "default_version = '1.1.0'\n", encoding="utf-8"
        )
        (self.root / "REVISION").write_text(REVISION + "\n", encoding="utf-8")
        (self.root / "LICENSE").write_text("MIT license text\n", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "include").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_recipe(self, recipes, **extra):
        path = Path(self.temp.name) / "dependencies.json"
        data = {
            "schemaVersion": "test-recipe-v1",
            "extension": {"name": "pg_duckdb", "tag": "v1.1.1"},
            "recipes": recipes,
            **extra,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def collect(self, recipes, *, platform="linux/amd64", **recipe_data):
        build_evidence = recipe_data.pop("build_evidence", None)
        recipe_path = self.write_recipe(recipes, **recipe_data)
        output = Path(self.temp.name) / platform.replace("/", "-")
        build_evidence_path = None
        if build_evidence is not None:
            build_evidence_path = Path(self.temp.name) / "build-evidence.json"
            build_evidence_path.write_text(json.dumps(build_evidence), encoding="utf-8")
        return collector.collect_dependencies(
            self.root,
            recipe_path=recipe_path,
            output_dir=output,
            source_tag="v1.1.1",
            platform=platform,
            build_evidence_path=build_evidence_path,
        )

    def test_real_version_pattern_and_platform_specific_ids(self):
        amd = self.collect([recipe()])
        arm = self.collect([recipe()], platform="linux/arm64")
        self.assertEqual(amd["components"][0]["releaseVersion"], "1.1.0")
        self.assertNotEqual(amd["components"][0]["spdxId"], arm["components"][0]["spdxId"])
        self.assertEqual(amd["coverage"]["included"], 1)

    def test_release_version_can_be_recorded_by_parent_build_recipe(self):
        (self.root / "Makefile").write_text("DUCKDB_VERSION = v1.4.3\n", encoding="utf-8")
        duckdb = self.root / "third_party" / "duckdb"
        duckdb.mkdir(parents=True)
        (duckdb / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (duckdb / "REVISION").write_text(REVISION + "\n", encoding="utf-8")
        manifest = self.collect([
            recipe(
                "duckdb",
                identity="github.com/duckdb/duckdb",
                source_root="third_party/duckdb",
                parent="root",
                releaseVersion={
                    "paths": ["Makefile", "../../Makefile"],
                    "pattern": "DUCKDB_VERSION\\s*=\\s*(?P<version>v?[0-9.]+)",
                },
                revisionEvidence=["REVISION"],
            )
        ])
        self.assertEqual(manifest["components"][0]["releaseVersion"], "v1.4.3")
        self.assertEqual(manifest["components"][0]["versionEvidence"]["paths"], ["../../Makefile"])

    def test_missing_version_fails_without_snapshot_approval(self):
        (self.root / "pg_duckdb.control").write_text("comment = 'missing'\n", encoding="utf-8")
        with self.assertRaisesRegex(collector.DependencyError, "release version is missing"):
            self.collect([recipe()])

    def test_generated_duckdb_version_accepts_cmake_override_evidence(self):
        build = self.root / "third_party" / "duckdb" / "build" / "release"
        build.mkdir(parents=True)
        (build / "CMakeCache.txt").write_text(
            "OVERRIDE_GIT_DESCRIBE:STRING=v1.4.3\n", encoding="utf-8"
        )
        self.assertEqual(
            collector._generated_duckdb_version(self.root),
            {
                "version": "v1.4.3",
                "paths": [str(build / "CMakeCache.txt")],
            },
        )

    def test_reviewed_snapshot_fallback_is_explicit(self):
        (self.root / "pg_duckdb.control").write_text("comment = 'snapshot'\n", encoding="utf-8")
        manifest = self.collect([recipe(allowSnapshot=True)])
        component = manifest["components"][0]
        self.assertIsNone(component["releaseVersion"])
        self.assertIn("reviewed snapshot", component["versionEvidence"]["status"])

    def test_unexpected_download_and_pin_mismatch_fail(self):
        config = self.root / "third_party"
        config.mkdir()
        (config / "pg_duckdb_extensions.cmake").write_text(
            "duckdb_extension_load(httpfs\n"
            "  GIT_URL https://example.test/httpfs\n"
            "  GIT_TAG bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n)\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(collector.DependencyError, "unclassified build download"):
            self.collect([recipe()])
        expected = {
            "identity": "example.test/httpfs",
            "url": "https://example.test/httpfs",
            "revision": "c" * 40,
            "recipe": "httpfs",
        }
        with self.assertRaisesRegex(collector.DependencyError, "download pin mismatch"):
            self.collect([recipe()], downloads=[expected])

    def test_missing_license_and_unknown_build_root_fail(self):
        (self.root / "LICENSE").unlink()
        with self.assertRaisesRegex(collector.DependencyError, "no complete license"):
            self.collect([recipe()])
        (self.root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (self.root / "src" / "VERSION").write_text("VERSION=1.0.0\n", encoding="utf-8")
        with self.assertRaisesRegex(collector.DependencyError, "unknown dependency root"):
            self.collect(
                [recipe(sourceRoot="src", releaseVersion={"path": "VERSION", "pattern": "VERSION=(?P<version>[0-9.]+)"})],
                policies={"requiredRoots": []},
                build_evidence={"dependencyRoots": ["unknown"]},
            )

    def test_header_only_and_build_only_are_covered_without_shipped_claims(self):
        include = self.root / "include"
        (include / "VERSION").write_text("VERSION=2.0.0\n", encoding="utf-8")
        (include / "REVISION").write_text(REVISION + "\n", encoding="utf-8")
        (include / "LICENSE").write_text("header license\n", encoding="utf-8")
        test_root = self.root / "test"
        test_root.mkdir()
        (test_root / "VERSION").write_text("VERSION=0.0.1\n", encoding="utf-8")
        (test_root / "LICENSE").write_text("test license\n", encoding="utf-8")
        records = [
            recipe(),
            recipe(
                "headers",
                source_root="include",
                classification="used headers",
                parent="root",
                releaseVersion={"path": "VERSION", "pattern": "VERSION=(?P<version>[0-9.]+)"},
                revisionEvidence=["REVISION"],
            ),
            recipe(
                "tests",
                source_root="test",
                classification="build/test-only",
                parent="root",
                releaseVersion={"path": "VERSION", "pattern": "VERSION=(?P<version>[0-9.]+)"},
                revisionEvidence=["../REVISION"],
            ),
        ]
        manifest = self.collect(records)
        by_id = {component["id"]: component for component in manifest["components"]}
        self.assertTrue(by_id["headers"]["shipped"])
        self.assertFalse(by_id["tests"]["shipped"])
        self.assertEqual(manifest["coverage"]["excluded"], 1)

    def test_duplicate_identity_fails(self):
        with self.assertRaisesRegex(collector.DependencyError, "duplicate component identity"):
            self.collect([recipe(), recipe("other", identity="example.test/root", source_root="include")])


if __name__ == "__main__":
    unittest.main()
