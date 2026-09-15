#!/usr/bin/env python3
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from generator import (  # noqa: E402
    final_inventory,
    infer_platform,
    run_command_with_progress,
    scan_licenses,
    statement_for,
)


class GeneratorTest(unittest.TestCase):
    def test_inventory_hashes_regular_and_symlink_files_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib").mkdir()
            payload = b"payload"
            (root / "lib" / "ext.so").write_bytes(payload)
            (root / "lib" / "alias.so").symlink_to("ext.so")
            (root / "outside").symlink_to("/tmp", target_is_directory=True)
            output = final_inventory(root)
        records = {record["name"]: record for record in output["files"]}
        self.assertEqual(records["lib/ext.so"]["value"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(records["lib/alias.so"]["kind"], "symlink")
        self.assertNotEqual(records["lib/alias.so"]["value"], records["lib/ext.so"]["value"])
        self.assertEqual(records["outside"]["kind"], "symlink")

    def test_platform_comes_from_builder_package_architecture(self):
        document = {"packages": [{"externalRefs": [{
            "referenceType": "purl",
            "referenceLocator": "pkg:deb/debian/base@1?arch=amd64&distro=debian-12.15",
        }]}]}
        self.assertEqual(infer_platform(document), "linux/amd64")

    def test_platform_ambiguity_is_rejected(self):
        document = {"packages": [{"externalRefs": [
            {"referenceType": "purl", "referenceLocator": "pkg:deb/debian/a@1?arch=amd64"},
            {"referenceType": "purl", "referenceLocator": "pkg:deb/debian/b@1?arch=arm64"},
        ]}]}
        with self.assertRaises(RuntimeError):
            infer_platform(document)

    def test_output_is_an_spdx_intoto_statement(self):
        predicate = {"SPDXID": "SPDXRef-DOCUMENT", "name": "demo"}
        statement = statement_for(predicate)
        self.assertEqual(statement["_type"], "https://in-toto.io/Statement/v1")
        self.assertEqual(statement["predicateType"], "https://spdx.dev/Document")
        self.assertEqual(statement["predicate"], predicate)
        self.assertEqual(statement["subject"], [])

    def test_long_running_scanner_reports_a_heartbeat(self):
        messages = []

        class FakeProcess:
            returncode = 0

            def __init__(self):
                self.calls = 0

            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(["scanner"], timeout)
                return "", ""

        with patch("generator.subprocess.Popen", return_value=FakeProcess()), patch(
            "generator.progress", side_effect=messages.append
        ):
            result = run_command_with_progress(["scanner"], "test scanner")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(messages[0], "test scanner started")
        self.assertTrue(any("test scanner still running" in message for message in messages))
        self.assertTrue(any("test scanner complete" in message for message in messages))

    def test_license_files_are_split_before_scancode_and_paths_are_collapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "licenses").mkdir()
            (root / "licenses" / "copyright").write_text("license text")
            temporary = root / "temporary"
            temporary.mkdir()
            commands = []

            def fake_csplit(command, **_kwargs):
                commands.append(command)
                prefix = Path(command[command.index("-f") + 1])
                prefix.with_name("license-00").write_text("license text")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            def fake_scancode(command, **_kwargs):
                output = Path(command[command.index("--json") + 1])
                output.write_text(json.dumps({
                    "files": [{
                        "type": "file",
                        "path": "licenses/copyright/license-00",
                        "license_detections": [{
                            "matches": [{"from_file": "licenses/copyright/license-00"}],
                            "license_expression_spdx": "MIT",
                        }],
                    }],
                }))
                class FakeProcess:
                    returncode = 0
                    stdout = io.StringIO("Scanned: licenses/copyright/license-00\n")

                    def wait(self):
                        return 0

                return FakeProcess()

            with patch("generator.shutil.which", return_value="scancode"), patch(
                "generator.subprocess.run", side_effect=fake_csplit
            ), patch(
                "generator.subprocess.Popen", side_effect=fake_scancode
            ):
                report = scan_licenses(root, temporary)

        self.assertEqual(report["files"][0]["path"], "licenses/copyright")
        self.assertEqual(
            report["files"][0]["license_detections"][0]["matches"][0]["from_file"],
            "licenses/copyright",
        )
        split_command = next(command for command in commands if command[0] == "csplit")
        self.assertIn("/^License:/", split_command)
        self.assertIn("{*}", split_command)

    def test_scancode_counts_unique_completion_events_and_preserves_failure(self):
        for exit_code in (0, 1):
            with self.subTest(exit_code=exit_code):
                messages = []
                command = [sys.executable, "-c", (
                    "import sys; "
                    "print('Setup plugins...', file=sys.stderr); "
                    "print('Scanned: /licenses/a', file=sys.stderr); "
                    "print('Scanned: /licenses/a', file=sys.stderr); "
                    "print('Scanned: /licenses/b', file=sys.stderr); "
                    "print('scan diagnostic', file=sys.stderr); "
                    f"sys.exit({exit_code})"
                )]
                with patch("generator.progress", side_effect=messages.append):
                    if exit_code:
                        with self.assertRaisesRegex(RuntimeError, "scan diagnostic"):
                            run_command_with_progress(command, "ScanCode", license_chunks=1200)
                    else:
                        run_command_with_progress(command, "ScanCode", license_chunks=1200)
                self.assertIn("ScanCode: 2 of 1,200 license chunks scanned", messages)
                self.assertFalse(any("still running" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
