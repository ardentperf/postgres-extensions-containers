#!/usr/bin/env python3

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_sbom import compose  # noqa: E402


def checksum(value):
    return [{"algorithm": "SHA256", "checksumValue": value}]


def builder_document():
    return {
        "_type": "https://in-toto.io/Statement/v0.1",
        "predicateType": "https://spdx.dev/Document",
        "subject": [],
        "predicate": {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "builder",
            "packages": [
                {"SPDXID": "SPDXRef-Package-base", "name": "base", "versionInfo": "1"},
                {"SPDXID": "SPDXRef-Package-extension", "name": "extension", "versionInfo": "2"},
            ],
            "files": [
                {"SPDXID": "SPDXRef-File-base", "fileName": "usr/lib/base.so", "checksums": checksum("base")},
                {"SPDXID": "SPDXRef-File-extension", "fileName": "usr/lib/postgresql/ext.so", "checksums": checksum("extension")},
                {"SPDXID": "SPDXRef-File-build-only", "fileName": "usr/bin/cc", "checksums": checksum("build-only")},
            ],
            "relationships": [
                {"spdxElementId": "SPDXRef-Package-base", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-base"},
                {"spdxElementId": "SPDXRef-Package-extension", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-extension"},
                {"spdxElementId": "SPDXRef-Package-extension", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": "SPDXRef-Package-base"},
                {"spdxElementId": "SPDXRef-Package-base", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-File-build-only"},
            ],
        },
    }


class ComposeSbomTest(unittest.TestCase):
    def test_subjects_replace_builder_files_and_keep_packages(self):
        final_document = {
            "_type": "https://in-toto.io/Statement/v0.1",
            "predicateType": "https://spdx.dev/Document",
            "subject": [
                {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
                {"name": "system/base.so", "digest": {"sha256": "base"}},
            ],
            "predicate": {"spdxVersion": "SPDX-2.3", "files": []},
        }

        output = compose(builder_document(), final_document)

        self.assertEqual([package["name"] for package in output["packages"]], ["base", "extension"])
        self.assertEqual(
            [file["fileName"] for file in output["files"]],
            ["lib/ext.so", "system/base.so"],
        )
        relationships = {
            (rel["relationshipType"], rel["spdxElementId"], rel["relatedSpdxElement"])
            for rel in output["relationships"]
        }
        self.assertIn(("DEPENDS_ON", "SPDXRef-Package-extension", "SPDXRef-Package-base"), relationships)
        self.assertEqual(sum(rel["relationshipType"] == "CONTAINS" for rel in output["relationships"]), 2)
        self.assertNotIn("usr/bin/cc", json.dumps(output))

    def test_missing_final_file_fails(self):
        final_document = {
            "subject": [{"name": "missing", "digest": {"sha256": "missing"}}]
        }
        with self.assertRaisesRegex(ValueError, "not found"):
            compose(builder_document(), final_document)


if __name__ == "__main__":
    unittest.main()
