#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent
SOURCE_RE = re.compile(
    r"#\s*renovate:\s*datasource=github-tags\s+depName=(?P<depName>\S+)\s+versioning=semver\s*\n"
    r"\s*RUN\s+curl\s+--fail\s+--location\s+--silent\s+--show-error\s+"
    r'"https://github\.com/[^/]+/[^/]+/archive/(?P<digest>[a-f0-9]{40})\.tar\.gz"'
    r"\s+-o\s+/tmp/source\.tar\.gz\s+#\s+v(?P<tag>\S+)"
)


class RenovateSourceTest(unittest.TestCase):
    def test_all_initial_targets_use_the_commit_and_tag_shape(self):
        expected = {
            "pg-search": ("paradedb/paradedb", "v0.25.6"),
            "pg-parquet": ("CrunchyData/pg_parquet", "v0.5.1"),
            "pg-graphql": ("supabase/pg_graphql", "v1.6.2"),
            "pg-jsonschema": ("supabase/pg_jsonschema", "v0.3.4"),
            "pg-session-jwt": ("neondatabase/pg_session_jwt", "v0.5.0"),
        }
        for target, (repository, tag) in expected.items():
            content = (ROOT / target / "Dockerfile").read_text(encoding="utf-8")
            match = SOURCE_RE.search(content)
            self.assertIsNotNone(match, target)
            assert match is not None
            self.assertEqual(match.group("depName"), repository)
            self.assertEqual(match.group("tag"), tag.removeprefix("v"))
            self.assertEqual(len(match.group("digest")), 40)
            self.assertNotRegex(match.group(0), r"archive/(?:main|master|v\d[^/]+)\.tar\.gz")

    def test_hcl_catalog_versions_match_source_comments(self):
        for target in ("pg-search", "pg-parquet", "pg-graphql", "pg-jsonschema", "pg-session-jwt"):
            dockerfile = (ROOT / target / "Dockerfile").read_text(encoding="utf-8")
            version = re.search(r"#\s+v(\d+\.\d+\.\d+)", dockerfile).group(1)
            metadata = (ROOT / target / "metadata.hcl").read_text(encoding="utf-8")
            self.assertIn(f'package = "{version}"', metadata)
            self.assertIn(f'sql     = "{version}"', metadata)


if __name__ == "__main__":
    unittest.main()
