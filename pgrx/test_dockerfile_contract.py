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
                dockerfile = (ROOT / target / "Dockerfile").read_text(encoding="utf-8")
                self.assertIn(
                    f'cyclonedx_file="{report_path}"',
                    dockerfile,
                )
                self.assertNotIn(
                    'find /workspace/source -type f -name pgrx.json',
                    dockerfile,
                )


if __name__ == "__main__":
    unittest.main()
