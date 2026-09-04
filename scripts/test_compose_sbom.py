#!/usr/bin/env python3

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_sbom import compose  # noqa: E402


def checksum(value):
    return [{"algorithm": "SHA256", "checksumValue": value}]


def builder_document(subjects):
    return {
        "_type": "https://in-toto.io/Statement/v0.1",
        "predicateType": "https://spdx.dev/Document",
        "subject": subjects,
        "predicate": {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "builder",
            "packages": [
                {
                    "SPDXID": "SPDXRef-Package-root",
                    "name": "sbom",
                    "primaryPackagePurpose": "FILE",
                },
                {
                    "SPDXID": "SPDXRef-Package-base",
                    "name": "base",
                    "versionInfo": "1",
                    "externalRefs": [{
                        "referenceType": "purl",
                        "referenceLocator": "pkg:generic/base@1",
                    }],
                },
                {
                    "SPDXID": "SPDXRef-Package-extension",
                    "name": "extension",
                    "versionInfo": "2",
                    "externalRefs": [{
                        "referenceType": "purl",
                        "referenceLocator": "pkg:generic/extension@2",
                    }],
                },
                {
                    "SPDXID": "SPDXRef-Package-build-only",
                    "name": "build-only",
                    "versionInfo": "3",
                    "externalRefs": [{
                        "referenceType": "purl",
                        "referenceLocator": "pkg:generic/build-only@3",
                    }],
                },
            ],
            "files": [
                {"SPDXID": "SPDXRef-File-base", "fileName": "usr/lib/base.so", "checksums": checksum("base")},
                {"SPDXID": "SPDXRef-File-extension", "fileName": "usr/lib/postgresql/ext.so", "checksums": checksum("extension")},
                {"SPDXID": "SPDXRef-File-build-only", "fileName": "usr/bin/cc", "checksums": checksum("build-only")},
            ],
            "relationships": [
                {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package-root"},
                {"spdxElementId": "SPDXRef-Package-root", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-Package-extension"},
                {"spdxElementId": "SPDXRef-Package-base", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-base"},
                {"spdxElementId": "SPDXRef-Package-extension", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-extension"},
                {"spdxElementId": "SPDXRef-Package-base", "relationshipType": "DEPENDENCY_OF", "relatedSpdxElement": "SPDXRef-Package-extension"},
                {"spdxElementId": "SPDXRef-Package-base", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-build-only"},
            ],
        },
    }


class ComposeSbomTest(unittest.TestCase):
    def test_final_packages_and_referenced_dependencies_are_retained(self):
        output = compose(builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
            {"name": "generated/artifact", "digest": {"sha256": "generated"}},
        ]))

        self.assertEqual(
            [package["name"] for package in output["packages"]],
            ["base", "extension", "extension-payload"],
        )
        self.assertEqual(
            [file["fileName"] for file in output["files"]],
            ["lib/ext.so", "generated/artifact"],
        )
        relationships = {
            (rel["relationshipType"], rel["spdxElementId"], rel["relatedSpdxElement"])
            for rel in output["relationships"]
        }
        self.assertIn(("DEPENDENCY_OF", "SPDXRef-Package-base", "SPDXRef-Package-extension"), relationships)
        self.assertIn(("CONTAINS", "SPDXRef-Package-extension", output["files"][0]["SPDXID"]), relationships)
        self.assertIn(("CONTAINS", "SPDXRef-Package-extension-payload", output["files"][1]["SPDXID"]), relationships)
        self.assertNotIn(("CONTAINS", "SPDXRef-Package-root", "SPDXRef-Package-extension"), relationships)
        self.assertNotIn("usr/bin/cc", json.dumps(output))

    def test_unmatched_final_file_is_attributed_to_extension(self):
        output = compose(builder_document([
            {"name": "missing", "digest": {"sha256": "missing"}},
        ]))
        self.assertEqual([package["name"] for package in output["packages"]], ["extension-payload"])
        self.assertEqual(output["files"][0]["fileName"], "missing")


if __name__ == "__main__":
    unittest.main()
