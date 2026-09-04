#!/usr/bin/env python3

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_sbom import compose  # noqa: E402


def checksum(value):
    return [{"algorithm": "SHA256", "checksumValue": value}]


def package(spdxid, name, version, purl):
    return {
        "SPDXID": spdxid,
        "copyrightText": "NOASSERTION",
        "downloadLocation": "NOASSERTION",
        "externalRefs": [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceLocator": purl,
            "referenceType": "purl",
        }],
        "filesAnalyzed": True,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "name": name,
        "supplier": "NOASSERTION",
        "versionInfo": version,
    }


def builder_document(subjects):
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": "https://spdx.dev/Document",
        "subject": subjects,
        "predicate": {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "builder",
            "packages": [
                {
                    "SPDXID": "SPDXRef-DocumentRoot-Directory-sbom",
                    "name": "sbom",
                    "supplier": "NOASSERTION",
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "licenseConcluded": "NOASSERTION",
                    "licenseDeclared": "NOASSERTION",
                    "copyrightText": "NOASSERTION",
                    "primaryPackagePurpose": "FILE",
                },
                package("SPDXRef-Package-base", "base", "1", "pkg:generic/base@1"),
                package("SPDXRef-Package-extension", "extension", "2", "pkg:generic/extension@2"),
                package("SPDXRef-Package-build-only", "build-only", "3", "pkg:generic/build-only@3"),
            ],
            "files": [
                {"SPDXID": "SPDXRef-File-base", "fileName": "usr/lib/base.so", "checksums": checksum("base")},
                {"SPDXID": "SPDXRef-File-extension", "fileName": "usr/lib/postgresql/ext.so", "checksums": checksum("extension")},
                {"SPDXID": "SPDXRef-File-build-only", "fileName": "usr/bin/cc", "checksums": checksum("build-only")},
            ],
            "relationships": [
                {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-DocumentRoot-Directory-sbom"},
                {"spdxElementId": "SPDXRef-DocumentRoot-Directory-sbom", "relationshipType": "CONTAINS", "relatedSpdxElement": "SPDXRef-Package-extension"},
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
        self.assertNotIn(("CONTAINS", "SPDXRef-DocumentRoot-Directory-sbom", "SPDXRef-Package-extension"), relationships)
        self.assertNotIn("usr/bin/cc", json.dumps(output))

    def test_unmatched_final_file_is_attributed_to_extension(self):
        output = compose(builder_document([
            {"name": "missing", "digest": {"sha256": "missing"}},
        ]))
        self.assertEqual([package["name"] for package in output["packages"]], ["extension-payload"])
        self.assertEqual(output["files"][0]["fileName"], "missing")

    def test_registry_image_subject_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "image subject"):
            compose(builder_document([
                {"name": "pkg:docker/example@latest", "digest": {"sha256": "image"}},
            ]))


if __name__ == "__main__":
    unittest.main()
