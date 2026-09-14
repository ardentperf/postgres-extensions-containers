# pg_jsonschema

`pg_jsonschema` is built from the upstream pgrx release archive and packaged as
a CloudNativePG extension image for PostgreSQL 18 on bookworm and trixie.

The source commit, matching `cargo-pgrx` version, Cargo commands, and the
runtime payload contract are intentionally visible in [Dockerfile](Dockerfile).
The Dockerfile emits CycloneDX and cargo-about reports through the named
`pgrx-sbom` stage; the workflow combines those reports with the final-image
filesystem SBOM.

The catalog/image source version is `0.3.4`.
