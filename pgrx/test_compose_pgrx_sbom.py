#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("compose_pgrx_sbom.py")
spec = importlib.util.spec_from_file_location("compose_pgrx_sbom", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class PgrxCompositionTest(unittest.TestCase):
    def test_merges_cargo_packages_edges_license_text_and_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dockerfile = root / "Dockerfile"
            dockerfile.write_text("FROM scratch\n", encoding="utf-8")
            cyclonedx = root / "cyclonedx.json"
            cyclonedx.write_text(json.dumps({
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "metadata": {"component": {
                    "bom-ref": "pkg:cargo/example@1.0.0",
                    "name": "example",
                    "version": "1.0.0",
                    "purl": "pkg:cargo/example@1.0.0",
                    "licenses": [{"license": {"id": "MIT"}}],
                }},
                "components": [{
                    "bom-ref": "pkg:cargo/serde@1.0.0",
                    "name": "serde",
                    "version": "1.0.0",
                    "purl": "pkg:cargo/serde@1.0.0",
                    "licenses": [{"license": {"id": "MIT"}}],
                }, {
                    "bom-ref": "pkg:cargo/serde-json@1.0.0",
                    "name": "serde-json",
                    "version": "1.0.0",
                    "purl": "pkg:cargo/serde-json@1.0.0",
                    "licenses": [{"license": {"id": "MIT"}}],
                }],
                "dependencies": [{
                    "ref": "pkg:cargo/example@1.0.0",
                    "dependsOn": ["pkg:cargo/serde-json@1.0.0"],
                }, {
                    "ref": "pkg:cargo/serde-json@1.0.0",
                    "dependsOn": ["pkg:cargo/serde@1.0.0"],
                }],
            }), encoding="utf-8")
            about = root / "cargo-about.json"
            about.write_text(json.dumps({
                "crates": [{"name": "serde", "version": "1.0.0", "license": "MIT"}],
                "licenses": [{"id": "MIT", "name": "MIT License", "text": "full MIT text"}],
            }), encoding="utf-8")
            metadata = root / "pgrx-build.json"
            metadata.write_text(json.dumps({
                "source": {
                    "archiveUrl": "https://github.com/example/example/archive/abc.tar.gz",
                    "commit": "abc",
                    "tag": "v1.0.0",
                    "archiveSha256": "archive",
                    "cargoLockSha256": "lock",
                },
                "cargo": {"package": "example", "features": ["pg18"]},
                "reports": {
                    "cyclonedxSha256": hashlib.sha256(cyclonedx.read_bytes()).hexdigest(),
                    "cargoAboutSha256": hashlib.sha256(about.read_bytes()).hexdigest(),
                },
            }), encoding="utf-8")
            document = {
                "spdxVersion": "SPDX-2.3",
                "SPDXID": "SPDXRef-DOCUMENT",
                "name": "example-multi-platform-sbom",
                "packages": [],
                "files": [],
                "relationships": [],
                "annotations": [{
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "annotationType": "OTHER",
                    "comment": module.COMPOSITION_NAMESPACE + " " + json.dumps({"image": {}}),
                }],
            }
            output = module.enrich(
                document,
                [("linux/amd64", cyclonedx, about, metadata)],
                extension_name="example",
                dockerfile=dockerfile,
                wrapper_revision="revision",
            )

            self.assertEqual(
                {package["name"] for package in output["packages"]},
                {"example", "serde", "serde-json"},
            )
            self.assertTrue(any(
                relationship["relationshipType"] == "DEPENDENCY_OF"
                for relationship in output["relationships"]
            ))
            self.assertEqual(len(output["hasExtractedLicensingInfos"]), 1)
            self.assertIn("pgrx", json.loads(
                output["annotations"][0]["comment"].split(" ", 1)[1]
            ))

    def test_rejects_report_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (("cyclonedx.json", {"bomFormat": "CycloneDX", "specVersion": "1.5"}),
                                  ("cargo-about.json", {"crates": [], "licenses": []}),
                                  ("Dockerfile", "FROM scratch\n")):
                path = root / name
                path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"source": {}, "cargo": {}, "reports": {"cyclonedxSha256": "wrong"}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.enrich(
                    {"SPDXID": "SPDXRef-DOCUMENT", "packages": [], "files": [], "relationships": [], "annotations": [{"spdxElementId": "SPDXRef-DOCUMENT", "annotationType": "OTHER", "comment": module.COMPOSITION_NAMESPACE + " {}"}]},
                    [("linux/amd64", root / "cyclonedx.json", root / "cargo-about.json", metadata)],
                    extension_name="example", dockerfile=root / "Dockerfile", wrapper_revision="revision",
                )


if __name__ == "__main__":
    unittest.main()
