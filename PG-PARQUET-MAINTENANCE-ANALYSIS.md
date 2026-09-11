# pg_parquet maintenance and dependency analysis

Audit date: 2026-09-07 UTC

Upstream: [CrunchyData/pg_parquet](https://github.com/CrunchyData/pg_parquet)

Source snapshot: [`44f7eb8777275829c19bde19441046c551b692ea`](https://github.com/CrunchyData/pg_parquet/commit/44f7eb8777275829c19bde19441046c551b692ea), the tip of the default `main` branch

## Bottom line

`pg_parquet` is a reasonably sized extension that two experienced Rust/PostgreSQL engineers could plausibly maintain, but it is not merely a thin wrapper over one stable library API. Its 8.7 KLOC of production Rust owns PostgreSQL `COPY` interception, PostgreSQL-to-Arrow conversion in both directions, raw PostgreSQL memory and destination-receiver integration, asynchronous object-store access, cloud authentication, Parquet metadata UDFs, and compatibility across PostgreSQL 14-18.

The historical project bus factor is effectively one. Aykut Bozkurt authored about 87% of commits on `main`, owns 99.6% of currently blamed Rust lines, and merged 61 of the repository's 67 merged pull requests. David Christensen (`pgguru`) is a meaningful secondary release/fix contributor and merged the other six PRs, but the visible history does not show a broad maintenance team.

Dependency maintenance was frequent while development was active: `Cargo.lock` was touched 26 times from October 2024 through October 2025. The median 13.1-day interval describes only the 25 completed intervals in that active period. It does **not** include the subsequent 314.6-day no-update interval through this audit date. There have been no `Cargo.lock` changes, and no commits at all on `main`, after October 27, 2025.

A new release tag is not the only official way to obtain a newer lockfile: the current tip of `main` is an official, CI-tested dependency update made 26 days after the latest release, v0.5.1. However, a new tag is the only upstream mechanism visible here for obtaining a new immutable, versioned release. The project explicitly says it does not support long-term release branches or backporting. An old tag can be rebuilt locally with a modified lockfile, but that is a downstream fork/build rather than an upstream update to that release.

## Scope and methodology

This analysis separates the extension's own source from Cargo dependencies. Unlike `pg_duckdb`, `pg_parquet` does not vendor Arrow, Parquet, pgrx, or its cloud clients into the source tree.

- Branch and tag claims were checked against all current upstream refs, not just a shallow/default-branch checkout.
- Lockfile cadence uses committer timestamps from `git log main -- Cargo.lock`.
- LOC uses `cloc` 2.04. “Code” excludes blank and comment lines.
- Complexity uses Lizard 1.24.0 and excludes `src/pgrx_tests`.
- Authorship uses non-merge commit authors and line-level `git blame`. GitHub contributor identities with multiple Git author spellings were combined where clearly identical.
- “Maintainer” and “bus factor” are inferences from public contribution, merge, release, and blame history. They do not prove who currently has repository permissions or an employment obligation.
- Registry “latest” versions are a freshness signal, not a claim that an upgrade is source-compatible.

## Repository activity and the October 2025 cutoff

The default branch is unquestionably `main`, and its tip remains the October 27, 2025 commit [`Update deps (#167)`](https://github.com/CrunchyData/pg_parquet/pull/167). A fresh fetch of all heads and tags found no newer mainline commit.

GitHub reports a later repository `pushed_at` timestamp because Aykut pushed unmerged topic-branch work:

| Branch | Last commit | Purpose | Lockfile versus `main` |
| --- | --- | --- | --- |
| `aykut/debian-image` | 2025-11-02 | Debian/AlmaLinux image work | Identical |
| `aykut/infer-columns` | 2025-11-07 | Infer columns from a Parquet URI | Identical |
| `aykut/geoparquet` | 2025-11-09 | Additional GeoParquet metadata | Identical |

These branches descend from the current main tip. They show some work after October, but no dependency update and no newer official mainline build. The other upstream heads are older topic branches, `pgguru/pg13`, and `release/0.3`. See the current [branch list](https://github.com/CrunchyData/pg_parquet/branches/all).

The final main commit's [CI run](https://github.com/CrunchyData/pg_parquet/actions/runs/18835172101) passed across the configured matrix. The workflow only runs on pushes and pull requests; it has no scheduled build. Consequently, that success verifies the October 2025 dependency set, not continued compatibility in September 2026.

## First-party size

At the audited main commit:

| Surface | Files | Code LOC | Physical lines | Notes |
| --- | ---: | ---: | ---: | --- |
| Production Rust | 92 | 8,695 | 11,094 | Excludes `src/pgrx_tests` |
| Rust tests | 12 | 5,986 | 7,421 | In-process pgrx tests |
| Extension SQL | 12 tracked | 116 | 143 | Most upgrade files are one-line includes; current definition is 106 physical lines |

Tests are unusually substantial relative to production code: test code is about 69% of production code LOC. That lowers takeover risk, although many tests exercise PostgreSQL and external object stores rather than isolated Rust functions.

The largest production modules by code LOC are:

| Module | Code LOC | Responsibility |
| --- | ---: | --- |
| `arrow_parquet/schema_parser.rs` | 578 | PostgreSQL/Arrow/Parquet schema mapping |
| `parquet_copy_hook/copy_utils.rs` | 554 | Parse, validate, and classify PostgreSQL COPY statements/options |
| `parquet_udfs/stats.rs` | 471 | Convert Parquet statistics to PostgreSQL-facing values |
| `arrow_parquet/arrow_to_pg.rs` | 335 | Arrow arrays to PostgreSQL datums/rows |
| `parquet_copy_hook/copy_to_dest_receiver.rs` | 334 | PostgreSQL `DestReceiver`, memory contexts, row batching |
| `arrow_parquet/parquet_reader.rs` | 316 | Async Parquet/object-store reads |
| `arrow_parquet/uri_utils.rs` | 306 | URI handling and COPY/program/stdin/stdout integration |
| `type_compat/pg_arrow_type_conversions.rs` | 284 | PostgreSQL and Arrow type semantics |

This is a moderate codebase, not a tiny glue crate. The work is concentrated in exactly the boundaries where correctness bugs tend to matter: types, ownership, query hooks, memory lifetimes, privileges, and cloud I/O.

## First-party complexity and risk

Lizard recognized 420 production functions over 8,735 NLOC, with average cyclomatic complexity 2.8. Nine functions exceeded CCN 15. The largest hotspots were:

| Function | CCN | NLOC | Area |
| --- | ---: | ---: | --- |
| `stats_min_value_to_pg_str` | 33 | 102 | Typed statistics conversion |
| `stats_max_value_to_pg_str` | 33 | 102 | Typed statistics conversion |
| `to_arrow_list_array` | 27 | 93 | PostgreSQL arrays to Arrow |
| `to_pg_array_datum` | 26 | 142 | Arrow arrays to PostgreSQL arrays |
| `to_arrow_primitive_array` | 26 | 76 | PostgreSQL scalar conversion |
| `to_pg_nonarray_datum` | 25 | 124 | Arrow scalar conversion |

Those scores mostly reflect explicit type dispatch, but that dispatch is real maintenance surface: numeric precision/scale, dates and time zones, arrays, composites, maps, JSON/JSONB, UUID, bytea, OID, PostGIS geometry, nullability, field IDs, fallback-to-text behavior, and coercion rules all need round-trip correctness.

The pgrx abstraction does not eliminate low-level PostgreSQL work:

- Production source contains 282 `unsafe` tokens, including 271 unsafe blocks or unsafe functions across 25 files.
- It contains 54 explicit `pg_sys::` paths and 72 raw-pointer type occurrences.
- It installs a `ProcessUtility_hook`, chains any previous hook, constructs a custom `DestReceiver`, manages PostgreSQL memory contexts, checks permissions, calls version-dependent parse/rewrite and permission APIs, and bridges PostgreSQL's error mechanism.
- Compatibility code has explicit pre-PG15, pre-PG16, and pre-PG18 branches; Cargo features build PostgreSQL 14 through 18.
- Async object-store operations run on a current-thread Tokio runtime inside each PostgreSQL backend.

The architectural layers are:

1. Detect and validate `COPY ... FORMAT parquet` in a PostgreSQL utility hook.
2. Convert PostgreSQL tuple descriptors and datums into Arrow schemas and arrays, or perform the inverse conversion on read.
3. Let the Apache Arrow/Parquet crates encode, decode, stream, compress, and expose metadata.
4. Route local, HTTP, S3, Azure, and GCS paths through `object_store` plus cloud-specific credential/configuration code.
5. Expose metadata, schema, file-list, and statistics functions to SQL.

Arrow and Parquet do the format-heavy work, and `object_store` does much of the remote I/O, so maintainers do not need to own those implementations. They do need to own every semantic and unsafe boundary around them.

## Direct dependencies

The audited [`Cargo.toml`](https://github.com/CrunchyData/pg_parquet/blob/44f7eb8777275829c19bde19441046c551b692ea/Cargo.toml) declares 19 runtime dependencies, one development dependency, and one build dependency. The lockfile contains 444 package records representing 407 unique package names, so this is not a small dependency graph.

### Runtime dependencies

| Dependency | Declared constraint | Locked | Latest stable on 2026-09-07 | Why first-party code uses it |
| --- | --- | --- | --- | --- |
| `arrow` | `57` | 57.0.0 | 59.3.0 | Arrays, buffers, record batches, data types |
| `arrow-cast` | `57` | 57.0.0 | 59.3.0 | Schema compatibility and value casts |
| `arrow-schema` | `57` | 57.0.0 | 59.3.0 | Schemas and canonical JSON/UUID extension types |
| `parquet` | `57` | 57.0.0 | 59.3.0 | Async reader/writer, metadata, statistics, compression |
| `pgrx` | `=0.16.1` | 0.16.1 | 0.19.2 | PostgreSQL extension framework and low-level server FFI |
| `object_store` | `=0.12.2` | 0.12.2 | 0.14.1 | S3, Azure, GCS, HTTP, and local object I/O |
| `aws-config` | `1` | 1.8.8 | 1.12.0 | AWS credential-provider chain |
| `aws-credential-types` | `1` | 1.2.8 | 1.3.0 | Resolve and pass AWS credentials |
| `azure_storage` | `0.21` | 0.21.0 | 0.21.0 | Parse Azure connection strings/protocols |
| `tokio` | `1` | 1.48.0 | 1.53.1 | Current-thread async runtime |
| `futures` | `0.3` | 0.3.31 | 0.3.34 | Consume async streams |
| `glob` | `0.3` | 0.3.3 | 0.3.4 | URI/file-pattern matching |
| `url` | `2` | 2.5.7 | 2.5.8 | URI parsing and construction |
| `home` | `0.5` | 0.5.12 | 0.5.12 | Locate user-level Azure configuration |
| `libc` | `0.2` | 0.2.177 | 0.2.189 | `FILE`, file descriptor, pipe/program FFI |
| `once_cell` | `1` | 1.21.3 | 1.21.4 | Cached optional PostgreSQL type information |
| `serde` | `1` | 1.0.228 | 1.0.229 | Field-ID and GeoParquet metadata serialization |
| `serde_json` | `1` | 1.0.145 | 1.0.151 | JSON/JSONB and metadata conversion |
| `rust-ini` | `0.21` | 0.21.3 | 0.21.3 | INI-format cloud configuration |

The latest-version data comes from the official [crates.io registry](https://crates.io/). Sixteen of the 19 direct runtime crates have a newer stable release than the lockfile. Major-version differences such as Arrow/Parquet 57→59, object_store 0.12→0.14, and pgrx 0.16→0.19 require testing and may require source changes; this table does not treat them as automatic upgrades.

`pgrx-tests = =0.16.1` is the only direct development dependency. `cfg_aliases = 0.2` is the only direct build dependency. Python test tooling in `Pipfile.lock`, PostgreSQL packages, PostGIS, pgaudit, cloud emulators/CLIs, and compiler/system libraries add CI and packaging dependencies but are not direct Rust-library dependencies of the extension.

## How dependency updates behaved historically

The key direct APIs were not static during the project's active 13 months:

- Arrow and Parquet moved 53→54→55→56→57.
- pgrx moved 0.12.5→0.12.6→0.12.8→0.12.9→0.13.1→0.14.1→0.15.0→0.16.0→0.16.1.
- `object_store` moved 0.11→0.12 and was then pinned exactly to 0.12.2.

Lockfile-touching commits were a mixture of deliberate dependency maintenance, release preparation, and feature work that introduced or resolved packages. There were 26 such commits from October 2, 2024 through October 27, 2025:

| Measure | Result |
| --- | ---: |
| Completed intervals | 25 |
| Median interval | 13.1 days |
| Mean interval | 15.6 days |
| Longest completed interval | 76.9 days |
| Gap from last update to audit date | 314.6 days |

The 13.1-day median is therefore a description of the 2024-2025 active period. It is not a statement that updates continued every two weeks. If the current censored gap is mechanically inserted as one more interval, the median changes only to 13.5 days because a single high observation barely changes a median; the mean rises to about 27.1 days. Neither statistic should obscure the more useful fact: dependency maintenance stopped for more than ten months.

The last release, [v0.5.1](https://github.com/CrunchyData/pg_parquet/releases/tag/v0.5.1), locks Arrow/Parquet 56 and pgrx 0.16.0. The subsequent main commit moves them to Arrow/Parquet 57 and pgrx 0.16.1. That update was not mechanical: in addition to 725 changed lockfile lines, it changed 291 lines of production Rust, primarily Parquet schema handling. Major dependency upgrades can therefore be meaningful adapter work even in this relatively focused extension.

The full source history is visible on GitHub's [`Cargo.lock` history](https://github.com/CrunchyData/pg_parquet/commits/main/Cargo.lock).

## Maintainers and bus factor

Public GitHub contributor enumeration reports seven contributors. The 95-commit linear `main` history breaks down approximately as follows after combining Aykut's two author identities:

| Contributor | Main commits | Share |
| --- | ---: | ---: |
| Aykut Bozkurt | 83 | 87.4% |
| David Christensen | 6 | 6.3% |
| Marco Slot | 2 | 2.1% |
| Four one-commit contributors | 4 | 4.2% |

Current line ownership is even more concentrated. Of 18,515 physical Rust lines, including tests, `git blame` assigns 18,449 (99.64%) to Aykut, 56 to David, and 10 to another contributor.

All 67 merged PRs were merged by two accounts: Aykut merged 61 and David (`pgguru`) merged six. Aykut authored 14 of the last 20 main commits; David authored four; two external contributors authored one each. The [contributors graph](https://github.com/CrunchyData/pg_parquet/graphs/contributors) supports the same conclusion.

There is no `MAINTAINERS`, `CODEOWNERS`, or governance document defining a larger team. Crunchy Data's organizational ownership and David's release work are positive signals, but the implementation knowledge visible in source history is overwhelmingly concentrated in one person.

## Releases, tags, and maintenance branches

### Release policy

The project's [`CONTRIBUTING.md`](https://github.com/CrunchyData/pg_parquet/blob/main/CONTRIBUTING.md#release) is unusually explicit:

- ongoing development goes to `main`;
- code committed to `main` should be considered stable;
- releases use semantic versioning;
- release preparation runs `cargo update`;
- long-term release branches/backporting are not supported.

That policy answers most of the distribution questions.

### Are release tags moved?

There is no evidence that a published tag has been moved. The 12 current tags resolve to plausible release commits, and the nine GitHub release records align with their release chronology. However, the repository's current Git object graph cannot prove that a ref was never force-updated in the past.

Only `v0.1.1` is an annotated tag, and its tag object contains a PGP signature (this audit did not establish signer-key trust). The other 11 are lightweight tags and therefore have no tag-object signature. Lightweight tag refs leave no immutable audit trail if an administrator moves them, so the defensible conclusion is “no observed evidence of movement,” not “movement is impossible.”

### Are major or minor maintenance branches maintained?

No general maintenance-branch scheme exists.

- `release/0.3` split from v0.3.1, received one bug-fix backport plus a version bump to v0.3.2, and stopped on April 18, 2025. It is now 34 main commits behind and has only those two branch-only commits. Its lockfile change was the root package version, not a dependency refresh.
- `pgguru/pg13` is an old PostgreSQL 13 experiment, not a maintained semver release line.
- No `release/0.4`, `release/0.5`, major-version, or minor-version maintenance branches exist.

The one `release/0.3` branch shows that a short-lived stabilization branch was used once, but it does not contradict the published no-backport policy.

### Is a new release tag the only official way to get an updated lockfile?

No, if “official” means upstream-owned and tested source. The strongest counterexample is the current `main`: v0.5.1 was tagged on October 1, 2025, and upstream committed a newer `Cargo.lock` on October 27 without a new tag. The project says mainline commits should be stable, and CI passed that commit.

Yes, in practice, if “official” means a new immutable release version/artifact. The post-release main snapshot still declares package version `0.5.1`; upstream has not published it as a distinct release. Consumers selecting v0.5.1 continue to receive the v0.5.1 tag's older lockfile.

### Can an older release receive only a dependency rebuild?

Not through a documented upstream channel today.

- Rebuilding the same tag normally reuses its exact `Cargo.lock`. Rust dependencies are generally compiled into the extension, so a rebuild alone does not silently select newer locked crate versions.
- A downstream can check out an old tag, run a targeted `cargo update -p ... --precise ...` when semver constraints allow it, edit a direct pin when necessary, test the full PostgreSQL/cloud matrix, and publish its own package. That keeps the extension feature version old but creates downstream source and binary provenance.
- Upstream could do the same on a maintenance branch and issue a patch tag, but its policy says such branches/backports are not currently supported.
- Rebuilding against refreshed OS/compiler packages can update dynamically linked system components, but it does not update Arrow, Parquet, pgrx, or the other Cargo-locked Rust crates.

## Practical maintenance-cost estimate

### What is relatively cheap

- Cargo gives deterministic dependency resolution, targeted updates, metadata, advisories, formatting, and lint tooling.
- Arrow/Parquet, Tokio, serde, and the cloud SDKs are actively maintained upstream.
- The extension delegates Parquet encoding/decoding and most object-store protocol work instead of implementing them.
- The test suite is large and the last active CI matrix covered PostgreSQL 14-18 on x86-64 and ARM64.
- Most scalar conversion modules are small and regular.

### What is not cheap

- The PostgreSQL hook, `DestReceiver`, raw-pointer, memory-context, and error-boundary code requires PostgreSQL backend expertise, not only ordinary Rust experience.
- Arrow/Parquet and pgrx had frequent major/minor updates during the active period. Both are adapter-defining APIs, and `object_store` is deliberately pinned exactly.
- Five PostgreSQL majors, two architectures, pgaudit coexistence, PostGIS behavior, local/program/stdin/stdout COPY paths, and four classes of object store make the validation matrix much larger than the production LOC suggests.
- Cloud credentials and emulators add operational failure modes. Tests that require live or emulated services are more expensive to reproduce than unit tests.
- There is no currently exercised release/backport process and no scheduled CI to detect ecosystem drift.

For planning rather than estimation-by-contract, a compatible patch-level lock refresh might take roughly half a day to two engineer-days including CI review. A pgrx, Arrow/Parquet, `object_store`, or PostgreSQL-major migration is more plausibly several days and can extend beyond a week when semantics or packaging change. After this ten-month gap, bringing all three main adapter dependencies current should be treated as a small migration project, not as one `cargo update` command.

A quiet, no-new-feature maintenance posture could plausibly fit around 0.1-0.25 FTE after catch-up if CI, packaging, security triage, and release authority are already available. Two people should share ownership even if the average workload is lower than one full-time engineer. A single volunteer can probably keep it building, but that reproduces the historical bus-factor and review problem.

## Takeover assessment

The favorable version of the thesis is partly right: `pg_parquet` is narrower than a query-engine integration, much of the heavy lifting belongs to healthy upstream Rust projects, and 8.7 KLOC with a 6.0 KLOC test suite is tractable for one or two motivated contributors.

The overly optimistic version is wrong: the extension is not simple glue over a stable API. It is a PostgreSQL/Arrow semantic adapter with substantial unsafe FFI and hook code, while its three defining dependency families—pgrx, Arrow/Parquet, and `object_store`—have all moved since maintenance stopped.

The most credible takeover model is therefore:

1. Two named maintainers, at least one comfortable with PostgreSQL backend internals and one with Rust/Arrow/cloud I/O; these can be the same person initially, but should not remain so.
2. First restore scheduled CI and dependency/security visibility without changing the release.
3. Refresh v0.5.1-era dependencies in staged groups and preserve a downstream lockfile/package for any old-release security rebuild.
4. Document whether downstream maintenance will support an `0.5.x` branch, because upstream does not.
5. Require review for unsafe/FFI, permission, and type-conversion changes.

With that structure, the repository is a realistic community-maintenance candidate. Without it, its modest size masks a high-consequence single-owner boundary layer.

## Primary source links

- [Repository and README](https://github.com/CrunchyData/pg_parquet)
- [Audited main commit](https://github.com/CrunchyData/pg_parquet/tree/44f7eb8777275829c19bde19441046c551b692ea)
- [Cargo manifest](https://github.com/CrunchyData/pg_parquet/blob/44f7eb8777275829c19bde19441046c551b692ea/Cargo.toml)
- [`Cargo.lock` history](https://github.com/CrunchyData/pg_parquet/commits/main/Cargo.lock)
- [Contribution and release policy](https://github.com/CrunchyData/pg_parquet/blob/main/CONTRIBUTING.md)
- [Branches](https://github.com/CrunchyData/pg_parquet/branches/all)
- [Tags and releases](https://github.com/CrunchyData/pg_parquet/releases)
- [Contributors](https://github.com/CrunchyData/pg_parquet/graphs/contributors)
- [CI workflow](https://github.com/CrunchyData/pg_parquet/blob/main/.github/workflows/ci.yml)
- [crates.io registry](https://crates.io/)
