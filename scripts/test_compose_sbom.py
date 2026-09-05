#!/usr/bin/env python3
import copy
import hashlib
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_sbom import aggregate, compose  # noqa: E402


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


def provenance_manifest():
    return {
        "schemaVersion": "https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1",
        "annotationDate": "2026-09-05T12:00:00Z",
        "inputs": {
            "builderSbom": {"sha256": "a" * 64},
            "buildDefinition": {"sha256": "b" * 64},
        },
        "image": {
            "sourceCommit": "c" * 40,
            "target": "plr-1.0.0-18-bookworm",
            "platform": "linux/amd64",
            "manifestDigest": "sha256:" + "d" * 64,
        },
        "composer": {
            "revision": "e" * 40,
            "command": "./scripts/compose_sbom.py --builder-sbom builder.json",
            "interpreter": "Python 3.13.0",
            "toolVersions": {
                "python": "Python 3.13.0",
                "jq": "jq-1.7",
            },
        },
        "workflow": {
            "repository": "cnpg-extensions/postgres-extensions-containers",
            "name": "Build, test and publish a target extension",
            "ref": "refs/heads/main",
            "runId": "12345",
            "runAttempt": "1",
            "actor": "octocat",
        },
    }


def aggregate_provenance_manifest():
    return {
        "schemaVersion": "https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1",
        "annotationDate": "2026-09-05T12:00:00Z",
        "inputs": {
            "builderSboms": [
                {"platform": "linux/amd64", "sha256": "a" * 64},
                {"platform": "linux/arm64", "sha256": "b" * 64},
            ],
            "buildDefinition": {"sha256": "c" * 64},
        },
        "image": {
            "sourceCommit": "d" * 40,
            "target": "plr-1.0.0-18-bookworm",
            "platforms": [
                {
                    "platform": "linux/amd64",
                    "manifestDigest": "sha256:" + "e" * 64,
                },
                {
                    "platform": "linux/arm64",
                    "manifestDigest": "sha256:" + "f" * 64,
                },
            ],
            "indexDigest": "sha256:" + "1" * 64,
        },
        "composer": {
            "revision": "2" * 40,
            "command": "./scripts/compose_sbom.py --aggregate-from amd64.json --aggregate-from arm64.json",
            "interpreter": "Python 3.13.0",
            "toolVersions": {
                "python": "Python 3.13.0",
                "jq": "jq-1.7",
                "actionsAttest": "actions/attest@v4",
            },
        },
        "workflow": {
            "repository": "cnpg-extensions/postgres-extensions-containers",
            "name": "Build, test and publish a target extension",
            "ref": "refs/heads/main",
            "runId": "12345",
            "runAttempt": "1",
            "actor": "octocat",
        },
    }


class ComposeSbomTest(unittest.TestCase):
    def test_provenance_annotation_has_canonical_document_level_structure(self):
        manifest = provenance_manifest()
        output = compose(
            builder_document([
                {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
            ]),
            extension_name="plr",
            provenance_manifest=manifest,
        )

        self.assertEqual(len(output["annotations"]), 1)
        annotation = output["annotations"][0]
        self.assertEqual(annotation["annotationDate"], manifest["annotationDate"])
        self.assertEqual(annotation["annotationType"], "OTHER")
        self.assertEqual(annotation["annotator"], "Tool: compose_sbom.py - 1.0")
        self.assertEqual(annotation["spdxElementId"], "SPDXRef-DOCUMENT")

        namespace, serialized = annotation["comment"].split(" ", 1)
        self.assertEqual(
            namespace,
            "https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1",
        )
        self.assertEqual(json.loads(serialized), manifest)
        self.assertEqual(
            serialized,
            json.dumps(manifest, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, separators=(",", ":")),
        )

    def test_provenance_annotation_is_deterministic(self):
        document = builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
        ])
        manifest = provenance_manifest()

        first = compose(copy.deepcopy(document), extension_name="plr",
                        provenance_manifest=manifest)
        second = compose(copy.deepcopy(document), extension_name="plr",
                         provenance_manifest=manifest)

        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_provenance_manifest_builder_hash_is_checked_when_read_from_file(self):
        document = builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
        ])
        with TemporaryDirectory() as directory:
            builder_path = Path(directory) / "builder.json"
            manifest_path = Path(directory) / "provenance.json"
            builder_path.write_text(json.dumps(document), encoding="utf-8")
            manifest = provenance_manifest()
            manifest["inputs"]["builderSbom"]["sha256"] = hashlib.sha256(
                builder_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            output = compose(
                document,
                extension_name="plr",
                builder_path=builder_path,
                provenance_manifest=manifest_path,
            )
            self.assertIn(
                "https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1",
                output["annotations"][0]["comment"],
            )

            manifest["inputs"]["builderSbom"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "builder SBOM hash"):
                compose(
                    document,
                    extension_name="plr",
                    builder_path=builder_path,
                    provenance_manifest=manifest_path,
                )

    def test_missing_provenance_input_fails_closed(self):
        for missing in ("inputs", "image", "composer", "workflow"):
            with self.subTest(missing=missing):
                manifest = provenance_manifest()
                del manifest[missing]
                with self.assertRaisesRegex(ValueError, "provenance manifest missing"):
                    compose(
                        builder_document([
                            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
                        ]),
                        extension_name="plr",
                        provenance_manifest=manifest,
                    )

        manifest = provenance_manifest()
        del manifest["inputs"]["buildDefinition"]
        with self.assertRaisesRegex(ValueError, "inputs.buildDefinition"):
            compose(
                builder_document([
                    {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
                ]),
                extension_name="plr",
                provenance_manifest=manifest,
            )

        manifest = aggregate_provenance_manifest()
        del manifest["inputs"]["builderSboms"]
        with self.assertRaisesRegex(ValueError, "inputs.builderSboms"):
            aggregate(
                [("linux/amd64", compose(builder_document([
                    {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
                ]), extension_name="plr"))],
                extension_name="plr",
                provenance_manifest=manifest,
            )

    def test_aggregate_merges_platform_documents_and_adds_one_annotation(self):
        amd64 = builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
        ])
        arm64 = builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension-arm64"}},
        ])
        arm64["predicate"]["packages"].append(
            package("SPDXRef-Package-arm-only", "arm-only", "1", "pkg:generic/arm-only@1")
        )
        arm64["predicate"]["files"].append({
            "SPDXID": "SPDXRef-File-arm-only",
            "fileName": "usr/lib/arm-only.so",
            "checksums": checksum("extension-arm64"),
        })
        arm64["predicate"]["relationships"].append({
            "spdxElementId": "SPDXRef-Package-arm-only",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-File-arm-only",
        })
        manifest = aggregate_provenance_manifest()

        output = aggregate(
            [
                ("linux/amd64", compose(amd64, extension_name="plr")),
                ("linux/arm64", compose(arm64, extension_name="plr")),
            ],
            extension_name="plr",
            provenance_manifest=manifest,
        )

        self.assertEqual(output["name"], "plr-multi-platform-sbom")
        self.assertEqual(
            output["documentNamespace"],
            "https://github.com/cnpg-extensions/postgres-extensions-containers/"
            "sbom-composition/v1/documents/plr/sha256-" + "1" * 64,
        )
        self.assertIn("extension", {item["name"] for item in output["packages"]})
        self.assertIn("arm-only", {item["name"] for item in output["packages"]})
        self.assertEqual(len(output["annotations"]), 1)
        annotation = output["annotations"][0]
        self.assertEqual(annotation["spdxElementId"], "SPDXRef-DOCUMENT")
        self.assertEqual(annotation["annotationType"], "OTHER")
        self.assertIn('"builderSboms"', annotation["comment"])
        self.assertIn('"indexDigest":"sha256:' + "1" * 64 + '"', annotation["comment"])

    def test_aggregate_builder_hashes_are_checked_for_each_platform(self):
        documents = [
            builder_document([
                {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
            ]),
            builder_document([
                {"name": "lib/ext.so", "digest": {"sha256": "extension-arm64"}},
            ]),
        ]
        manifest = aggregate_provenance_manifest()
        with TemporaryDirectory() as directory:
            paths = []
            for index, document in enumerate(documents):
                path = Path(directory) / f"builder-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.append(path)
            manifest["inputs"]["builderSboms"][0]["sha256"] = hashlib.sha256(
                paths[0].read_bytes()
            ).hexdigest()
            manifest["inputs"]["builderSboms"][1]["sha256"] = hashlib.sha256(
                paths[1].read_bytes()
            ).hexdigest()
            with self.assertRaisesRegex(ValueError, "builder SBOM hash"):
                aggregate(
                    [
                        ("linux/amd64", compose(documents[0], extension_name="plr")),
                        ("linux/arm64", compose(documents[1], extension_name="plr")),
                    ],
                    extension_name="plr",
                    provenance_manifest=manifest,
                    builder_paths=[("linux/amd64", paths[1]), ("linux/arm64", paths[0])],
                )

    def test_aggregate_annotation_is_deterministic(self):
        manifest = aggregate_provenance_manifest()
        documents = [
            ("linux/amd64", compose(builder_document([
                {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
            ]), extension_name="plr")),
            ("linux/arm64", compose(builder_document([
                {"name": "lib/ext.so", "digest": {"sha256": "extension-arm64"}},
            ]), extension_name="plr")),
        ]
        first = aggregate(documents, extension_name="plr", provenance_manifest=manifest)
        second = aggregate(copy.deepcopy(documents), extension_name="plr", provenance_manifest=manifest)
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_final_packages_are_retained_and_unshipped_packages_are_removed(self):
        output = compose(builder_document([
            {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
            {"name": "generated/artifact", "digest": {"sha256": "generated"}},
        ]), extension_name="plr")

        self.assertEqual(
            [package["name"] for package in output["packages"]],
            ["extension", "plr-extension-artifacts"],
        )
        self.assertEqual(
            [file["fileName"] for file in output["files"]],
            ["lib/ext.so", "generated/artifact"],
        )
        relationships = {
            (rel["relationshipType"], rel["spdxElementId"], rel["relatedSpdxElement"])
            for rel in output["relationships"]
        }
        self.assertIn(("CONTAINS", "SPDXRef-Package-extension", output["files"][0]["SPDXID"]), relationships)
        self.assertIn(("CONTAINS", "SPDXRef-Package-extension-payload", output["files"][1]["SPDXID"]), relationships)
        self.assertNotIn("base", {package["name"] for package in output["packages"]})
        self.assertNotIn(("DEPENDENCY_OF", "SPDXRef-Package-base", "SPDXRef-Package-extension"), relationships)
        self.assertNotIn(("CONTAINS", "SPDXRef-DocumentRoot-Directory-sbom", "SPDXRef-Package-extension"), relationships)
        self.assertNotIn("usr/bin/cc", json.dumps(output))

    def test_duplicate_checksum_prefers_path_and_preserves_same_file_owners(self):
        document = builder_document([
            {"name": "share/libblas3/copyright", "digest": {"sha256": "copyright"}},
        ])
        predicate = document["predicate"]
        predicate["packages"].extend([
            package("SPDXRef-Package-libblas3", "libblas3", "1", "pkg:generic/libblas3@1"),
            package("SPDXRef-Package-liblapack3", "liblapack3", "1", "pkg:generic/liblapack3@1"),
            package("SPDXRef-Package-shared-license", "shared-license", "1", "pkg:generic/shared-license@1"),
        ])
        predicate["files"].extend([
            {
                "SPDXID": "SPDXRef-File-libblas3-copyright",
                "fileName": "usr/share/doc/libblas3/copyright",
                "checksums": checksum("copyright"),
            },
            {
                "SPDXID": "SPDXRef-File-liblapack3-copyright",
                "fileName": "usr/share/doc/liblapack3/copyright",
                "checksums": checksum("copyright"),
            },
        ])
        predicate["relationships"].extend([
            {
                "spdxElementId": "SPDXRef-Package-libblas3",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-File-libblas3-copyright",
            },
            {
                "spdxElementId": "SPDXRef-Package-shared-license",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-File-libblas3-copyright",
            },
            {
                "spdxElementId": "SPDXRef-Package-liblapack3",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-File-liblapack3-copyright",
            },
        ])

        output = compose(document, extension_name="plr")
        package_names = {item["name"] for item in output["packages"]}
        self.assertIn("libblas3", package_names)
        self.assertIn("shared-license", package_names)
        self.assertNotIn("liblapack3", package_names)
        relationships = {
            (rel["relationshipType"], rel["spdxElementId"], rel["relatedSpdxElement"])
            for rel in output["relationships"]
        }
        file_id = output["files"][0]["SPDXID"]
        self.assertIn(("CONTAINS", "SPDXRef-Package-libblas3", file_id), relationships)
        self.assertIn(("CONTAINS", "SPDXRef-Package-shared-license", file_id), relationships)
        self.assertNotIn(("CONTAINS", "SPDXRef-Package-liblapack3", file_id), relationships)

    def test_ambiguous_basename_match_is_extension_owned(self):
        document = builder_document([
            {"name": "share/unknown/copyright", "digest": {"sha256": "copyright"}},
        ])
        predicate = document["predicate"]
        predicate["packages"].extend([
            package("SPDXRef-Package-left", "left", "1", "pkg:generic/left@1"),
            package("SPDXRef-Package-right", "right", "1", "pkg:generic/right@1"),
        ])
        predicate["files"].extend([
            {
                "SPDXID": "SPDXRef-File-left-copyright",
                "fileName": "usr/share/doc/left/copyright",
                "checksums": checksum("copyright"),
            },
            {
                "SPDXID": "SPDXRef-File-right-copyright",
                "fileName": "usr/share/doc/right/copyright",
                "checksums": checksum("copyright"),
            },
        ])
        predicate["relationships"].extend([
            {
                "spdxElementId": "SPDXRef-Package-left",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-File-left-copyright",
            },
            {
                "spdxElementId": "SPDXRef-Package-right",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": "SPDXRef-File-right-copyright",
            },
        ])

        output = compose(document, extension_name="plr")
        self.assertEqual([item["name"] for item in output["packages"]], ["plr-extension-artifacts"])

    def test_license_path_selects_named_package(self):
        document = builder_document([
            {"name": "licenses/libgomp1/copyright", "digest": {"sha256": "copyright"}},
        ])
        predicate = document["predicate"]
        predicate["packages"].extend([
            package("SPDXRef-Package-libgomp1", "libgomp1", "1", "pkg:generic/libgomp1@1"),
            package("SPDXRef-Package-gcc", "gcc-14-base", "1", "pkg:generic/gcc-14-base@1"),
        ])
        predicate["files"].append({
            "SPDXID": "SPDXRef-File-gcc-copyright",
            "fileName": "usr/share/doc/gcc-14-base/copyright",
            "checksums": checksum("copyright"),
        })
        predicate["relationships"].append({
            "spdxElementId": "SPDXRef-Package-gcc",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-File-gcc-copyright",
        })

        output = compose(document, extension_name="plr")
        package_names = {item["name"] for item in output["packages"]}
        self.assertIn("libgomp1", package_names)
        self.assertNotIn("gcc-14-base", package_names)
        relationships = {
            (rel["relationshipType"], rel["spdxElementId"], rel["relatedSpdxElement"])
            for rel in output["relationships"]
        }
        file_id = output["files"][0]["SPDXID"]
        self.assertIn(("CONTAINS", "SPDXRef-Package-libgomp1", file_id), relationships)
        self.assertNotIn(("CONTAINS", "SPDXRef-Package-gcc", file_id), relationships)

    def test_registry_image_subject_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "image subject"):
            compose(builder_document([
                {"name": "pkg:docker/example@latest", "digest": {"sha256": "image"}},
            ]), extension_name="plr")

    def test_malformed_spdx_entries_fail_instead_of_being_skipped(self):
        malformed_entries = {
            "packages": {"name": "broken"},
            "files": {"fileName": "broken", "checksums": []},
            "relationships": {},
        }
        for field, entry in malformed_entries.items():
            with self.subTest(field=field):
                document = builder_document([
                    {"name": "lib/ext.so", "digest": {"sha256": "extension"}},
                ])
                document["predicate"][field].append(entry)
                with self.assertRaises(KeyError):
                    compose(document, extension_name="plr")


if __name__ == "__main__":
    unittest.main()
