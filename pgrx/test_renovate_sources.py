#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent
SOURCE_RES = (
    re.compile(
        r"#\s*renovate:\s*datasource=github-tags\s+depName=(?P<depName>\S+)\s+versioning=semver\s*\n"
        r"\s*RUN\s+curl\s+--fail\s+--location\s+--silent\s+--show-error\s+"
        r'"https://github\.com/[^/]+/[^/]+/archive/(?P<digest>[a-f0-9]{40})\.tar\.gz"'
        r"\s+-o\s+/tmp/source\.tar\.gz\s+#\s+v(?P<tag>\S+)"
    ),
)


class RenovateSourceTest(unittest.TestCase):
    def test_all_initial_targets_use_the_expected_source_shape(self):
        expected = {
            "pg-search": ("paradedb/paradedb", "v0.25.6"),
            "pg-parquet": ("CrunchyData/pg_parquet", "v0.5.1"),
            "pg-graphql": ("supabase/pg_graphql", "v1.6.2"),
            "pg-jsonschema": ("supabase/pg_jsonschema", "v0.3.4"),
            "pg-session-jwt": ("neondatabase/pg_session_jwt", "v0.5.0"),
        }
        for target, (repository, tag) in expected.items():
            content = (ROOT / target / "Dockerfile").read_text(encoding="utf-8")
            if target == "pg-jsonschema":
                self.assertIn(
                    "ADD https://github.com/supabase/pg_jsonschema/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz",
                    content,
                )
                continue
            if target == "pg-session-jwt":
                self.assertIn(
                    "ADD https://github.com/neondatabase/pg_session_jwt/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz",
                    content,
                )
                continue
            if target == "pg-parquet":
                self.assertIn(
                    "ADD https://github.com/CrunchyData/pg_parquet/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz",
                    content,
                )
                continue
            if target == "pg-graphql":
                self.assertIn(
                    "ADD https://github.com/supabase/pg_graphql/archive/${EXT_VERSION}.tar.gz /tmp/source.tar.gz",
                    content,
                )
                continue
            match = None
            for source_re in SOURCE_RES:
                match = source_re.search(content)
                if match is not None:
                    break
            self.assertIsNotNone(match, target)
            assert match is not None
            self.assertEqual(match.group("depName"), repository)
            self.assertEqual(match.group("tag"), tag.removeprefix("v"))
            if "digest" in match.groupdict():
                self.assertEqual(len(match.group("digest")), 40)
                self.assertNotRegex(match.group(0), r"archive/(?:main|master|v\d[^/]+)\.tar\.gz")
            else:
                self.assertEqual(match.group("archiveTag"), match.group("tag"))

    def test_hcl_catalog_versions_match_source_comments(self):
        for target in ("pg-search", "pg-parquet", "pg-graphql", "pg-jsonschema", "pg-session-jwt"):
            dockerfile = (ROOT / target / "Dockerfile").read_text(encoding="utf-8")
            metadata = (ROOT / target / "metadata.hcl").read_text(encoding="utf-8")
            if target == "pg-jsonschema":
                self.assertIn('package = "v0.3.4"', metadata)
                self.assertIn('sql     = "0.3.4"', metadata)
                continue
            if target == "pg-session-jwt":
                self.assertIn('package = "v0.5.0"', metadata)
                self.assertIn('sql     = "0.5.0"', metadata)
                continue
            if target == "pg-parquet":
                self.assertIn('package = "v0.5.1"', metadata)
                self.assertIn('sql     = "0.5.1"', metadata)
                continue
            if target == "pg-graphql":
                self.assertIn('package = "v1.6.2"', metadata)
                self.assertIn('sql     = "1.6.2"', metadata)
                continue
            version = re.search(r"#\s+v(\d+\.\d+\.\d+)", dockerfile).group(1)
            package_version = version
            self.assertIn(f'package = "{package_version}"', metadata)
            self.assertIn(f'sql     = "{version}"', metadata)


if __name__ == "__main__":
    unittest.main()
