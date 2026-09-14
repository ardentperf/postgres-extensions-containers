# pg_duckdb maintenance and dependency analysis

Audit date: 2026-09-07 UTC

Upstream: [duckdb/pg_duckdb](https://github.com/duckdb/pg_duckdb)

Source snapshot: [`ee38d3b540ecea1d93683ba99bdcec5632a21eaf`](https://github.com/duckdb/pg_duckdb/commit/ee38d3b540ecea1d93683ba99bdcec5632a21eaf), the tip of the default `main` branch

## Bottom line

`pg_duckdb` is not simple glue. It is an in-process, bidirectional integration between two database engines. About 11.7 KLOC of non-vendored C/C++ participates in PostgreSQL planning, execution, DDL, transactions, background workers, type conversion, scanning, permissions, error handling, and DuckDB catalog/storage interfaces. It depends on internal APIs on both sides and carries version-specific PostgreSQL source.

Routine DuckDB pin bumps have often been inexpensive: nine of 16 post-import DuckDB submodule updates required no first-party production-code change, and two more changed 15 lines or fewer. The remaining five required 53-950 changed first-party lines, so compatibility work is spiky rather than uniformly cheap. Annual PostgreSQL-major work and cross-engine correctness are the durable costs.

The repository has a much broader contributor base than `pg_parquet`—49 GitHub contributors, 12 with at least five contributions—but current release and merge authority is visibly concentrated. Jelte Fennema-Nio merged every one of the 45 PRs merged after September 7, 2025, merged 96 of the most recently examined 100 merged PRs, created every current GitHub release, and owns about half of current non-vendored C/C++ lines. The observable gatekeeper bus factor is one even though implementation knowledge is distributed among several substantial contributors.

Two experienced PostgreSQL/C++ database engineers can plausibly maintain the project, particularly with support from the active DuckDB ecosystem. One person could keep it building during quiet periods but would be a poor long-term ownership model because failures occur at concurrency, memory, transaction, and internal-API boundaries.

There is no Cargo lockfile equivalent. Reproducible source dependencies are represented by the exact DuckDB Git submodule commit and exact HTTPFS Git commit, plus a logical DuckDB release version. `main` and official nightly main containers can receive these updates without a pg_duckdb release tag. Stable versioned artifacts require a release tag. No major/minor maintenance branches exist, and rebuilding v1.1.1 does not pick up newer DuckDB or HTTPFS code unless a downstream changes the pins and owns the resulting backport.

## Scope and methodology

- All LOC figures use `cloc` 2.04; code excludes comments and blank lines.
- Explicit vendor directories are `src/vendor` and `include/pgduckdb/vendor`.
- The DuckDB Git submodule and its recursively built extensions are excluded from first-party LOC.
- Some adapted PostgreSQL-derived files live outside the explicit vendor directories. They are disclosed separately instead of being silently counted as wholly first-party.
- Complexity uses Lizard 1.24.0 over `src` and `include`, excluding the explicit vendor directories.
- Dependency cadence uses committer timestamps. This matters for the v1.5.4 update: its author timestamp is March 2026, but it was merged/committed on June 19, 2026.
- “Maintainer” and “bus factor” are public-history inferences. They do not prove current write permissions, employment assignments, or private review work.

## First-party versus imported code

At the audited commit:

| Surface | Files | Code LOC | Physical lines | Classification |
| --- | ---: | ---: | ---: | --- |
| Non-vendored production C/C++ and headers | 91 | 11,731 | 16,625 | Working first-party upper bound |
| Explicit PostgreSQL/PgBouncer vendor directories | 11 source/header files | 52,288 | 79,537 | Imported/adapted source; excludes two `.clang-format` files |
| Extension install/upgrade SQL | 6 | 3,154 | 3,990 | First-party SQL plus historical upgrade paths |
| Test Python and regression SQL | 79 | 4,495 | 6,764 | First-party tests |
| Regression expected output | 67 | n/a | 9,426 | Generated/curated golden output |
| DuckDB submodule | n/a | Excluded | Excluded | Third-party source at an exact Git SHA |

The current extension-install path is approximately 1,576 SQL code lines: the 1.0.0 base script plus the 1.0→1.1 and 1.1→1.2 upgrades. The rest of the 3,154 SQL LOC represents older migration routes rather than code every fresh installation executes.

The 11,731 C/C++ LOC is an upper bound because at least three mixed or adapted files sit outside the explicit vendor directories:

| File | Code LOC | Provenance concern |
| --- | ---: | --- |
| `src/pgduckdb_ruleutils.cpp` | 851 | PostgreSQL ruleutils-derived/adapted deparser logic |
| `src/pgduckdb_table_am.cpp` | 423 | PostgreSQL table-access-method integration/adaptation |
| `src/pgduckdb_detoast.cpp` | 144 | PostgreSQL detoast/compression-derived logic |

Removing those entire files gives a conservative 10,313-LOC lower bound for cleanly separated first-party C/C++. That undercounts original integration work inside the adapted files, so the honest first-party range is roughly 10.3-11.7 KLOC. The repository's [`NOTICE`](https://github.com/duckdb/pg_duckdb/blob/main/NOTICE) records PostgreSQL and PgBouncer-derived code.

The explicit vendor total looks enormous because the repository carries six PostgreSQL `ruleutils` copies, one each for PostgreSQL 14 through 19. Those files should not be used to estimate how much novel extension logic maintainers must understand, but they do create recurring import, patch, build, and review cost.

## First-party code concentration

The largest non-vendored files are:

| File | Code LOC | Responsibility |
| --- | ---: | --- |
| `src/pgduckdb_types.cpp` | 1,812 | PostgreSQL↔DuckDB type/value conversion |
| `src/pgduckdb_ddl.cpp` | 1,148 | Intercept, classify, and synchronize DDL |
| `src/pgduckdb_background_worker.cpp` | 930 | MotherDuck/catalog synchronization and worker lifecycle |
| `src/pgduckdb_ruleutils.cpp` | 851 | Translate/deparse PostgreSQL statements for DuckDB |
| `src/scan/postgres_scan.cpp` | 490 | Expose PostgreSQL scans to DuckDB and push filters |
| `src/pgduckdb_table_am.cpp` | 423 | DuckDB-backed PostgreSQL table access method |
| `src/pgduckdb_planner.cpp` | 359 | Planner decisions and query eligibility |
| `src/pgduckdb_hooks.cpp` | 358 | PostgreSQL hook installation and routing |

The top four files contain 4,741 lines, or 40.4% of the non-vendored C/C++ code. This concentration is useful for onboarding but also identifies review bottlenecks: types, DDL, background synchronization, and statement translation dominate the implementation.

## Complexity and correctness surface

Lizard found 536 functions over 11,391 NLOC, with average CCN 3.5. Sixteen functions exceeded CCN 15:

| Function | CCN | NLOC | Why it is complex |
| --- | ---: | ---: | --- |
| `pgduckdb_get_viewdef` | 73 | 378 | PostgreSQL-derived statement/view deparsing |
| `ConvertPostgresToBaseDuckColumnType` | 66 | 115 | PostgreSQL type catalog to DuckDB logical types |
| `DuckdbHandleDDLPre` | 61 | 183 | DDL routing, restrictions, and synchronization |
| `ConvertDuckToPostgresValue` | 51 | 178 | DuckDB values into PostgreSQL slots/datums |
| `ExpressionToString` | 49 | 112 | Convert DuckDB filter expressions to PostgreSQL SQL |
| `ConvertPostgresToDuckValue` | 40 | 176 | PostgreSQL datums into DuckDB vectors |
| `GetPostgresDuckDBType` | 39 | 84 | Reverse type mapping |

Some complexity is naturally type dispatch or imported deparser logic. The more important risk is architectural:

- It installs or participates in planner, executor, explain, logging, utility, transaction, subtransaction, table-AM, and background-worker paths.
- It includes at least 43 distinct DuckDB internal header paths. This is not an integration through only DuckDB's stable C API.
- It relies extensively on PostgreSQL server-internal headers and APIs, not libpq's external client API.
- DuckDB can execute in worker threads while most PostgreSQL backend APIs are not thread-safe. The project has explicit process locks, signal guards, stack guards, and `PostgresFunctionGuard` wrappers.
- PostgreSQL errors use `elog(ERROR)`/`longjmp`, while C++ and DuckDB use exceptions. The contributor guide warns that using the wrong mechanism on the wrong side can cause crashes, memory leaks, or undefined cleanup.
- Type conversion spans decimals, nested types, arrays, enums/domains, timestamps/time zones, JSON, huge integers, unresolved types, and tuple-slot/vector memory ownership.
- The code manually handles PostgreSQL TOAST/PGLZ/LZ4 paths and memory contexts.
- DDL, catalog invalidation, prepared statements, transaction aborts, subtransactions, and MotherDuck catalog synchronization cross engine boundaries.
- Mixed writes are not generally atomic across PostgreSQL and DuckDB. The documented `duckdb.allow_mixed_transactions` override is experimental and can create consistency issues.

The project's own [`CONTRIBUTING.md`](https://github.com/duckdb/pg_duckdb/blob/main/CONTRIBUTING.md#error-handling) is strong evidence that maintainers need database-engine and systems-C++ judgment, not merely build familiarity.

## Direct dependency inventory

### Source-level and link-time dependencies

| Dependency | How it is selected | Direct use and maintenance consequence |
| --- | --- | --- |
| PostgreSQL server 14-19 on `main` (the released README still lists 14-18) | Build target and server development headers | Hooks, planner/query trees, catalogs, snapshots, memory contexts, tuple slots, table AM, transactions, bgworkers, errors; version-specific imported source |
| DuckDB | Exact Git submodule SHA plus `DUCKDB_VERSION` | Embedded engine and broad internal C++ API surface |
| DuckDB HTTPFS | Exact Git commit in CMake | S3/GCS/Azure/HTTP filesystem behavior; built alongside DuckDB |
| DuckDB JSON and ICU extensions | Built-in extension declarations | JSON and collation/time-zone functionality; versions follow the selected DuckDB tree |
| `liblz4` | System link `-llz4` | PostgreSQL datum decompression and DuckDB/build requirements |
| `libcurl` | System link in static-bundle mode | HTTPFS/network transport |
| C++ standard library | `-lstdc++`, and `-lstdc++fs` for GCC 8 | C++ runtime and older compiler compatibility |
| ICU and other DuckDB build dependencies | Inherited/system depending on build | Needed by enabled DuckDB features; not independently pinned by pg_duckdb |

At the audited main commit, the source pins are:

- `DUCKDB_VERSION = v1.5.4`
- DuckDB submodule: [`08e34c447bae34eaee3723cac61f2878b6bdf787`](https://github.com/duckdb/duckdb/tree/08e34c447bae34eaee3723cac61f2878b6bdf787)
- HTTPFS: [`c3f215ab360f04dc3d3d5305fa81849c0121f111`](https://github.com/duckdb/duckdb-httpfs/tree/c3f215ab360f04dc3d3d5305fa81849c0121f111)

The pinning is visible in the [Makefile](https://github.com/duckdb/pg_duckdb/blob/main/Makefile), [submodule tree](https://github.com/duckdb/pg_duckdb/tree/main/third_party), and [extension CMake file](https://github.com/duckdb/pg_duckdb/blob/main/third_party/pg_duckdb_extensions.cmake).

### Optional runtime integrations

These are user-selected runtime dependencies, not code statically owned by this repository:

- MotherDuck is loaded as a DuckDB extension/service when configured. Its released runtime component is not pinned to a Git SHA in this repository.
- Iceberg, Delta, Vortex, and other DuckDB extensions can be installed dynamically. pg_duckdb adds dedicated SQL wrappers/support for some of them, but their release lifecycle belongs to DuckDB's extension system.

Their optional status does not make them free: changes can break SQL wrappers, type handling, extension installation policy, or tests.

### Build and test dependencies

PGXS, a C/C++ compiler, CMake/Ninja, PostgreSQL development packages, Python test tools, clang-format/clang-tidy, Docker, and external test services are substantial operational dependencies. They are distinct from the production library dependency graph.

There is no Dependabot or Renovate configuration in the audited tree.

## Dependency-update cadence

### DuckDB

There are 17 commits touching the DuckDB submodule path: the initial import plus 16 pointer updates.

| Period | Pointer updates after import |
| --- | ---: |
| 2024 | 7 |
| 2025 | 8 |
| 2026 through audit | 1 |

Across the 16 completed update intervals:

| Measure | Result |
| --- | ---: |
| Median interval | 38.6 days |
| Mean interval | 50.9 days |
| Longest interval | 189.0 days |

The latest landed update was [`Bump up duckdb to v1.5.4 (#1025)`](https://github.com/duckdb/pg_duckdb/commit/02899dbbb2ac9ab7b956b5c399a073eb831ee9b8) on June 19, 2026. Its older author date should not be mistaken for the merge date.

For the 11 updates that could be compared directly with an identified upstream DuckDB release, pg_duckdb adopted the release after a median of about 5.8 days; the slowest observed adoption was about 15.4 days. Historically, the project followed DuckDB releases quickly when active.

The amount of adapter work per submodule bump was uneven:

| First-party production change in same commit | Number of 16 updates |
| --- | ---: |
| No non-vendored C/C++ change | 9 |
| Tiny change (15 lines or fewer) | 2 |
| Substantive change (53-950 changed lines) | 5 |

The largest was the August 2024 update at about 950 changed first-party lines. The current v1.5.4 update changed 53 first-party production lines plus substantial tests. A majority of bumps were cheap, but compatibility spikes are material.

As of the audit, upstream DuckDB's latest release is [v1.5.5](https://github.com/duckdb/duckdb/releases/tag/v1.5.5), published July 22, 2026. Main is one DuckDB patch release behind.

### HTTPFS

The exact HTTPFS pin was introduced in March 2025 and changed six more times. The median interval between its seven pin-setting/changing commits was 55.1 days. Six of the seven changes coincided with a DuckDB update or adjacent compatibility work, so HTTPFS should normally be tested as part of the DuckDB bump rather than managed independently.

### PostgreSQL-derived vendor code

`src/vendor` alone was touched by 28 commits: 15 in 2024, 10 in 2025, and three in 2026. Counting the corresponding vendor headers raises this to 33 commits. The activity is not merely bulk imports; older version copies have each accumulated roughly 15-18 modifying commits.

Adding a PostgreSQL major means importing another roughly 12-14K-physical-line `ruleutils` copy, applying pg_duckdb modifications, selecting it at build time, and testing behavioral differences. The June 2026 PG19 work illustrates the three-step pattern: import the unmodified source, apply required changes, then wire PG19 support.

### System packages and container rebuilds

Compiler, curl, LZ4, ICU, OpenSSL, and distro packages are not pinned to exact package versions in this repository. The [Docker workflow](https://github.com/duckdb/pg_duckdb/blob/main/.github/workflows/docker.yaml) rebuilds `main` every day for PostgreSQL 14-18 on amd64 and arm64. The ten most recent scheduled runs through the audit date all succeeded.

This daily rebuild is valuable drift detection and can refresh OS packages in `main` images without changing source pins. It does **not** update DuckDB or HTTPFS, and it does not refresh previously tagged release images.

## Upstream health

The largest dependencies are healthy enough that pg_duckdb maintainers should normally consume fixes rather than become their sole upstream maintainers:

- GitHub's contributor enumeration for [DuckDB](https://github.com/duckdb/duckdb/graphs/contributors) returns about 870 contributors, including 54 with at least 100 contributions and 16 with at least 1,000.
- [duckdb-httpfs](https://github.com/duckdb/duckdb-httpfs) returns 85 contributors, 33 with at least five contributions, and had mainline activity on the audit date.
- PostgreSQL has its established upstream major/minor lifecycle.

The risk is not abandonment of those dependencies. It is that pg_duckdb consumes two fast-moving sets of internal database APIs and must reconcile their semantics in one process.

## Maintainers and bus factor

### Contributor breadth

GitHub reports 49 pg_duckdb contributors. Twelve have at least five contributions. Non-merge Git history has 608 commits; four long-running contributors and their obvious author aliases account for about 77%:

- Jelte Fennema-Nio: 237 commits
- `Y.` / `Y--`: 123 commits
- `mkaruza`: 62 commits in local author history (75 contributions in GitHub's aggregate)
- `Tishj` / Thijs: 47 commits across aliases

This is not a historical one-author codebase.

Current non-vendored C/C++ blame is still concentrated:

| Contributor/combined identity | Approximate share |
| --- | ---: |
| Jelte Fennema-Nio | 50.0% |
| `Y.` | 21.9% |
| `mkaruza` | 8.6% |
| Yuwei Xiao | 5.1% |
| `Tishj` / Thijs combined | 4.5% |

Those five identities cover roughly 90% of the current non-vendored C/C++ physical lines.

### Current gatekeeping

The contribution pool and the release/gatekeeper pool are different:

- All 45 PRs merged from September 7, 2025 through the audit date were merged by Jelte.
- Of the most recently examined 100 merged PRs, 96 were merged by Jelte, three by `Y--`, and one by `mkaruza`.
- Every current GitHub release was published by Jelte.
- Every current tag was created by Jelte.
- No `MAINTAINERS`, `CODEOWNERS`, or public governance roster defines additional release owners.

Therefore the implementation bus factor is several, while the observable review/release bus factor is one. A takeover or continuity plan should prioritize credentials, release procedure, threat model, and reviewer authority as much as source knowledge.

## Releases, tags, and maintenance branches

### Current channels

- Latest stable release: [v1.1.1](https://github.com/duckdb/pg_duckdb/releases/tag/v1.1.1), published December 18, 2025.
- v1.1.1 pins DuckDB v1.4.3, submodule `d1dc88f...`, and HTTPFS `9c7d349...`.
- Current `main` declares extension default version 1.2.0 and pins DuckDB v1.5.4.
- The project documents nightly [`main` Docker images](https://github.com/duckdb/pg_duckdb/blob/main/docker/README.md), rebuilt on the daily schedule.

Thus an official upstream source/container update does not require a release tag, but a stable versioned release does.

### Are release tags moved?

There is no evidence that a release tag has been moved. All seven current tags are annotated tag objects with plausible tagger dates and commit targets. Six have matching GitHub release records; v0.3.0 exists as a tag without a GitHub release object.

The tags inspected are not cryptographically signed. Current refs and Git objects cannot prove that GitHub refs were never force-updated historically, so “no observed evidence” is stronger than an unqualified claim that they were never moved.

### Are major/minor maintenance branches maintained?

No. The [upstream branch list](https://github.com/duckdb/pg_duckdb/branches/all) contains `main` plus feature, experiment, dependency-bump, and contributor work branches. It has no `release/1.0`, `release/1.1`, `1.1.x`, or equivalent stable line.

Branches named `bump-to-duckdb-1.4.4` and `leonardo/bump-duckdb-1.4.4` are old topic branches, not supported release branches. Their existence does not create an official v1.1.x update channel.

### Can an older release receive only a dependency update?

Not through a documented upstream stable channel.

- Rebuilding v1.1.1 from its tag keeps its exact DuckDB and HTTPFS commits. Those source dependencies do not float.
- DuckDB [v1.4.5](https://github.com/duckdb/duckdb/releases/tag/v1.4.5), published in June 2026, contains fixes beyond v1.4.3. v1.1.1 does not receive them merely by rebuilding.
- A downstream can branch from v1.1.1, update DuckDB/HTTPFS pins, make compatibility changes, run the full matrix, and publish a patched package without adopting main's pg_duckdb 1.2 features. This is technically straightforward in concept but becomes a downstream-supported fork.
- Upstream could publish a v1.1.2 patch tag from such a branch. There is no standing branch or public policy indicating it will do so.
- Rebuilding against newer dynamically linked OS libraries can refresh curl/LZ4/ICU/compiler-runtime components. It does not refresh the statically built or submodule-pinned engine code.

## Practical maintenance-cost estimate

### Lower-cost work

- Most historical DuckDB patch/minor bumps needed little or no extension production-code change.
- DuckDB and HTTPFS have active upstream teams and rapid fixes.
- Exact Git pins make source builds reproducible.
- Daily multi-architecture container builds provide unusually good ongoing drift detection.
- The repository has 4.5 KLOC of executable test code plus 9.4K lines of expected output, and tests cover many regressions and boundary cases.
- Several contributors understand major subsystems even though one person currently gates merges.

### High-cost work

- Internal DuckDB C++ APIs and PostgreSQL backend APIs can change without the compatibility guarantees of public client APIs.
- A dependency bump can expand from a pointer change into hundreds of lines of adapter work.
- Every PostgreSQL major adds a large vendor import and version-specific behavior.
- Crashes, longjmp/exception mismatches, lock ordering, signal handling, thread safety, and transaction divergence are high-consequence failure modes.
- Compatibility spans PostgreSQL 14-19 development, two architectures, dynamic DuckDB extensions, cloud filesystems, MotherDuck, and multiple build modes.
- Release and merge knowledge appears concentrated in one person, with no documented maintenance-line process.

For rough planning, an ordinary DuckDB patch bump may be one to three engineer-days including tests and containers when no adapter work is needed. A DuckDB major/minor compatibility event or new PostgreSQL major is more plausibly one to three engineer-weeks, with larger outliers possible. Correctness bugs involving mixed transactions, cancellation, background workers, or threaded PostgreSQL scans can consume similar time regardless of LOC.

A steady-state project with no major feature expansion could plausibly occupy around 0.25-0.5 FTE averaged over a year, but it should be staffed by at least two people who can review each other's database-internals work. Feature development, MotherDuck support, or rapid adoption of every DuckDB release raises that substantially. The workload is bursty: long stretches of small bumps are punctuated by compatibility migrations and difficult production bugs.

## Takeover assessment

The project is maintainable by a small expert team because its genuinely first-party C/C++ surface is around 10-12 KLOC and its upstream dependencies are healthy. The claim that it is “just glue” would nevertheless lead to under-budgeting. This glue implements planner and execution ownership, cross-engine type semantics, catalog synchronization, error translation, transaction constraints, and thread/process safety.

A credible continuity plan should have:

1. Two release-capable maintainers with PostgreSQL backend and modern C++ experience.
2. A documented map of every hook, lock, error boundary, and function callable from DuckDB worker threads.
3. A repeatable dependency-bump checklist covering DuckDB, HTTPFS, dynamic extensions, first-party diffs, and both architectures.
4. An explicit stable-branch policy if old pg_duckdb releases must receive DuckDB security/correctness fixes.
5. A repeatable PostgreSQL-major import procedure for vendor files and local patches.
6. Release credentials and signing/provenance that do not depend on one account.

With those controls, two people can reasonably own it. Without them, the current one-gatekeeper model is a material operational and review risk even though the contributor history is broad.

## Primary source links

- [Repository and README](https://github.com/duckdb/pg_duckdb)
- [Audited main commit](https://github.com/duckdb/pg_duckdb/tree/ee38d3b540ecea1d93683ba99bdcec5632a21eaf)
- [Build and DuckDB pins](https://github.com/duckdb/pg_duckdb/blob/main/Makefile)
- [DuckDB/HTTPFS extension configuration](https://github.com/duckdb/pg_duckdb/blob/main/third_party/pg_duckdb_extensions.cmake)
- [DuckDB submodule update history](https://github.com/duckdb/pg_duckdb/commits/main/third_party/duckdb)
- [PostgreSQL vendor-source history](https://github.com/duckdb/pg_duckdb/commits/main/src/vendor)
- [Source provenance notice](https://github.com/duckdb/pg_duckdb/blob/main/NOTICE)
- [Contributor guide and error-boundary rules](https://github.com/duckdb/pg_duckdb/blob/main/CONTRIBUTING.md)
- [Branches](https://github.com/duckdb/pg_duckdb/branches/all)
- [Tags and releases](https://github.com/duckdb/pg_duckdb/releases)
- [Contributors](https://github.com/duckdb/pg_duckdb/graphs/contributors)
- [Build/test CI](https://github.com/duckdb/pg_duckdb/blob/main/.github/workflows/build_and_test.yaml)
- [Daily Docker workflow](https://github.com/duckdb/pg_duckdb/blob/main/.github/workflows/docker.yaml)
- [Transaction-safety settings](https://github.com/duckdb/pg_duckdb/blob/main/docs/settings.md#duckdballow_mixed_transactions)
