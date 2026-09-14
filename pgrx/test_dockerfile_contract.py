import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class DockerfileContractTest(unittest.TestCase):
    def test_cyclonedx_report_is_copied_from_the_selected_manifest(self):
        expected = {
            "pg-graphql": "pgrx.json",
            "pg-jsonschema": "pgrx.json",
            "pg-parquet": "pgrx.json",
            "pg-search": "pg_search/pgrx.json",
            "pg-session-jwt": "pgrx.json",
        }
        for target, report_path in expected.items():
            with self.subTest(target=target):
                files = [ROOT / target / "Dockerfile"]
                dockerfile = files[0].read_text(encoding="utf-8")
                helper = ROOT / "pgrx" / "install-pgrx-build-environment.sh"
                if helper.exists() and helper.name in dockerfile:
                    files.append(helper)
                dockerfile = "\n".join(
                    path.read_text(encoding="utf-8") for path in files
                )
                self.assertIn(
                    f'cyclonedx_file="{report_path}"',
                    dockerfile,
                )
                self.assertNotIn(
                    'find /build -type f -name pgrx.json',
                    dockerfile,
                )
                if target == "pg-jsonschema":
                    helper_text = helper.read_text(encoding="utf-8")
                    self.assertNotIn("/build", helper_text)
                    self.assertIn(
                        'source_dir="$(dirname "${lock_file}")"',
                        helper_text,
                    )
                    self.assertIn(
                        'sbom_dir="${source_dir}/pgrx-sbom"',
                        helper_text,
                    )
                    self.assertIn(
                        'license_dir="${source_dir}/pgrx-licenses/rust"',
                        helper_text,
                    )
                    self.assertNotIn("/payload", dockerfile)
                    self.assertIn(
                        "RUN cargo pgrx package \\",
                        dockerfile,
                    )
                    self.assertIn(
                        "COPY --from=builder /build/target/release/pg_jsonschema-pg${PG_MAJOR}/usr/lib/postgresql/${PG_MAJOR}/lib/pg_jsonschema.so /lib/",
                        dockerfile,
                    )
                    self.assertIn(
                        "COPY --from=builder /build/target/release/pg_jsonschema-pg${PG_MAJOR}/usr/share/postgresql/${PG_MAJOR}/extension/pg_jsonschema* /share/extension/",
                        dockerfile,
                    )


if __name__ == "__main__":
    unittest.main()
