# Upstream Sync Commit Review

Generated and reviewed locally on 2026-09-02. This is the first checked-in sync review record. The comparison tip is the second parent of the downstream merge.

- Mirror checked: `origin/main` at `4a2d94443c59626884bde23c6dc700448500c6f1` (`cnpg-extensions/postgres-extensions-containers`)
- Upstream checked: `upstream/main` at `011b3fc72455574a6b87043f14c220f6b4cca160`
- Last recorded upstream merge: `7b6ba6a07f45e559f232e70b542e82123ec875d9`
- Downstream merge commit: `324a6b7a9392060baf2c5c8c10d0a2ae66a0f0e0`
- Upstream commits reviewed: 75
- Detailed non-dependency commits: 18
- Pure dependency chore commits consolidated below: 57

## Review rules

`Touches mirror files?` is `Yes` when at least one exact changed path exists in the mirror at the checked mirror ref. A `No` result means the commit only adds or changes paths absent from the mirror. Extension directories are grouped in the path column. Pure `chore(deps)` commits are omitted from the detailed sections and summarized separately below.

## Consolidated dependency-only updates

57 of the 75 upstream commits are pure dependency chores (`chore(deps):`). They are intentionally filtered out of the detailed review sections. Do not replay these bot commits individually; review the final cumulative value in each shared file and take only the pins relevant to the mirror.

| Dependency area | Commits | Recommendation |
| --- | ---: | --- |
| CI/action pins | 17 | Use the final cumulative action/tool pins in the shared workflows; do not replay intermediate bot updates. |
| kubectl image | 11 | Update the shared Taskfile to the final upstream v1.36.4 pin if adopting the tool updates. |
| psql test image | 11 | Update shared `test/check-extension.yaml` to the final v18.6 pin; skip extension-only test files. |
| registry image | 2 | Update the shared registry pin to the final digest if adopting the CI changes. |
| Dagger | 1 | Update the shared Dagger engine/CLI references to the final v0.21.9 value where applicable. |
| CNPG smoke-test version | 1 | Update the shared smoke-test default to CNPG 1.30 if that test matrix is adopted. |
| TimescaleDB package | 8 | Exclude — extension-specific package updates are intentionally omitted. |
| pgvector package | 4 | Exclude — extension-specific package updates are intentionally omitted. |
| PostGIS package | 1 | Exclude — extension-specific package updates are intentionally omitted. |
| wal2json package | 1 | Exclude — extension-specific package updates are intentionally omitted. |

Final upstream shared values observed during this review include CNPG `1.30`, kubectl `1.36.4`, psql `18.6`, Dagger `v0.21.9`, registry `3.1.1`, and the corresponding upstream-pinned digests. Take these as review targets, not as an instruction to mirror extension package versions.

## Detailed review: commits planned for adoption

These are the substantive upstream commits we plan to adopt or adapt, subject to normal conflict resolution and validation.

| Audit order | Date | Upstream commit | Subject | Touches mirror files? | Mirror paths / paths absent from mirror | Adoption note |
| ---: | --- | --- | --- | :---: | --- | --- |
| 1 | 2026-06-16 | [552cb96e190b9e25ea16897f4f2b626822bfd026](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/552cb96e190b9e25ea16897f4f2b626822bfd026) | ci: run Go unit tests for the maintenance module (#238) | Yes | mirror: `dagger/maintenance/dagger.json`<br>`dagger/maintenance/go.mod`<br>`dagger/maintenance/go.sum`<br>absent: `.github/workflows/test.yml` | Adopt — add/adapt the maintenance unit-test workflow and Dagger module updates. |
| 3 | 2026-07-02 | [be1c8dd1f8fcc139fd086eda9c571399a76bb787](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/be1c8dd1f8fcc139fd086eda9c571399a76bb787) | fix: set output to cacheonly when running bake --check (#262) | Yes | mirror: `Taskfile.yml` | Adopt — merge the shared `bake --check` fix. |
| 4 | 2026-07-08 | [9755a49bdb19aaef02df236cd8b4a59396e7a925](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/9755a49bdb19aaef02df236cd8b4a59396e7a925) | feat: derive build matrix from distros and PG versions in extension's metadata (#251) | Yes | mirror: `.github/workflows/bake_targets.yml`<br>`BUILD.md`<br>`Taskfile.yml`<br>`dagger/maintenance/dagger.json`<br>`dagger/maintenance/go.mod`<br>`dagger/maintenance/go.sum`<br>`dagger/maintenance/main.go`<br>`dagger/maintenance/parse.go`<br>`docker-bake.hcl`<br>`postgis/* (1)`<br>absent: `dagger/maintenance/parse_test.go` | Adopt — merge the shared metadata-driven matrix and maintenance refactor; validate downstream metadata pairs. |
| 7 | 2026-07-14 | [72c2850a9e5b977c51d1e5276897f4b1bcbbe952](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/72c2850a9e5b977c51d1e5276897f4b1bcbbe952) | ci: automate smoke-test cnpg matrix (#274) | Yes | mirror: `.github/workflows/bake_targets.yml`<br>`Taskfile.yml` | Adopt — merge the dynamic CNPG smoke-test matrix. |
| 8 | 2026-07-15 | [3a13c62ada62f4826d26a1b4ab788afc1df31bd7](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/3a13c62ada62f4826d26a1b4ab788afc1df31bd7) | chore: quote CNPG_RELEASE_DEFAULT (#282) | Yes | mirror: `Taskfile.yml` | Adopt — keep the shared Taskfile fix with the current CNPG release pin. |
| 16 | 2026-08-18 | [4cb1bd8cb47a8f028ba720ceedd46c7860613c32](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/4cb1bd8cb47a8f028ba720ceedd46c7860613c32) | chore: add SECURITY-INSIGHTS.yml (#307) | Yes | mirror: `.github/PULL_REQUEST_TEMPLATE/new_extension.md`<br>`CONTRIBUTING_NEW_EXTENSION.md`<br>absent: `SECURITY-INSIGHTS.yml` | Adopt/adapt — add the security metadata and contributor checklist while preserving downstream identity and ownership. |

## Detailed review: commits not relevant to this mirror

These commits are intentionally excluded. They either update extensions that are not mirrored here, fix extension-specific behavior, add upstream-only extensions, or change upstream ownership policy.

**CODEOWNERS policy:** CNPG Extensions has its own `CODEOWNERS` file and ownership model. Do not copy upstream `CODEOWNERS` changes or upstream component-owner/account assignments. Preserve and review downstream ownership independently.

| Audit order | Date | Upstream commit | Subject | Touches mirror files? | Mirror paths / paths absent from mirror | Exclusion note |
| ---: | --- | --- | --- | :---: | --- | --- |
| 2 | 2026-06-17 | [ac3d13a23cdcef5cd27f8d37a50d122d1b528158](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/ac3d13a23cdcef5cd27f8d37a50d122d1b528158) | chore: update postgis OS libraries (#239) | No | absent: `postgis/* (2)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |
| 5 | 2026-07-13 | [f47540c10434cb867dde58199ea0d8bf40619ce8](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/f47540c10434cb867dde58199ea0d8bf40619ce8) | chore: update postgis OS libraries (#263) | No | absent: `postgis/* (2)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |
| 6 | 2026-07-13 | [38d9417a4dfecdaa716735b2e50da229ed3bb928](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/38d9417a4dfecdaa716735b2e50da229ed3bb928) | feat: add pg_ivm extension (#49) | Yes | mirror: `CODEOWNERS`<br>`README.md`<br>absent: `pg-ivm/* (10)` | Exclude — do not add the upstream extension or copy its mixed README/ownership/security changes. |
| 9 | 2026-07-20 | [8b779fff856a2c66c52e4192e6d2c7058a5c1fd9](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/8b779fff856a2c66c52e4192e6d2c7058a5c1fd9) | chore: update postgis OS libraries (#289) | No | absent: `postgis/* (1)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |
| 10 | 2026-07-22 | [f0eb97fc5f69048218ea6da670d1a416d306b043](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/f0eb97fc5f69048218ea6da670d1a416d306b043) | chore: add Gabriele Fedi as a component owner (#292) | Yes | mirror: `CODEOWNERS` | Exclude — CNPG Extensions has its own CODEOWNERS; do not copy upstream ownership changes. |
| 11 | 2026-07-23 | [cacac01ea2306d8602ad5a76f71372c54ab115f5](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/cacac01ea2306d8602ad5a76f71372c54ab115f5) | chore: expand account names in CODEOWNERS file (#288) | Yes | mirror: `CODEOWNERS` | Exclude — CNPG Extensions has its own CODEOWNERS; do not copy upstream ownership changes. |
| 12 | 2026-07-24 | [d5709b0362a875e099f672687f011ead1b5f4ae2](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/d5709b0362a875e099f672687f011ead1b5f4ae2) | chore: update postgis OS libraries (#291) | No | absent: `postgis/* (1)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |
| 13 | 2026-07-27 | [560a829c4b7f266f55a0e787918d049099fd6116](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/560a829c4b7f266f55a0e787918d049099fd6116) | fix(PostGIS): strip `$libdir/` prefix from extension SQL scripts (#293) | Yes | mirror: `postgis/* (1)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |
| 14 | 2026-08-05 | [f06c545b3f85dbe25c3bd24a73f6c05830c54b4b](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/f06c545b3f85dbe25c3bd24a73f6c05830c54b4b) | chore: sync CODEOWNERS with cnpg-infra policy (#306) | Yes | mirror: `CODEOWNERS` | Exclude — CNPG Extensions has its own CODEOWNERS; do not copy upstream ownership changes. |
| 15 | 2026-08-18 | [c8a992f553d7f69d1eb338cb021eccf2edffe1e4](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/c8a992f553d7f69d1eb338cb021eccf2edffe1e4) | fix: add `wal2json` to `output_plugin_libraries` for PG 18.6+ (#319) | No | absent: `wal2json/* (2)` | Exclude — extension-specific metadata fix; intentionally do not mirror it. |
| 17 | 2026-08-19 | [f111f59c3d57fe2c14eb03e9374da0f38f88c61b](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/f111f59c3d57fe2c14eb03e9374da0f38f88c61b) | feat: add `pgrouting` container image (#299) | Yes | mirror: `README.md`<br>absent: `SECURITY-INSIGHTS.yml`<br>`pgrouting/* (10)` | Exclude — do not add the upstream extension or copy its mixed README/ownership/security changes. |
| 18 | 2026-08-24 | [1fe50c79116afa459455075a05505b24f83a8791](https://github.com/cloudnative-pg/postgres-extensions-containers/commit/1fe50c79116afa459455075a05505b24f83a8791) | chore: update postgis OS libraries (#302) | No | absent: `postgis/* (2)` | Exclude — extension-specific PostGIS change; inspect only if the downstream copy has the same issue. |

## Merge resolution

- Preserved the mirror's complete 19-extension set; no upstream-only
  extensions or extension-specific updates were added.
- Kept downstream `CODEOWNERS` and `README.md`, including the mirror's
  branding.
- Adapted `SECURITY-INSIGHTS.yml` to the mirror repository and image names.
- Adopted the shared maintenance/build-matrix, workflow, smoke-test, and
  contributor/security changes identified in the planned-adoption table.
- Kept `dagger/maintenance/dagger.json` at the upstream module declaration
  `v0.21.7`; the shared workflow and Taskfile pins use the reviewed `v0.21.9`
  CLI/tool value.

## Validation

- `DAGGER_SESSION_PORT=1 DAGGER_SESSION_TOKEN=test go test ./...` passed after
  generating the Dagger client with v0.21.9.
- `act -j unit-test -W .github/workflows/test.yml --network bridge
  -P ubuntu-24.04=catthehacker/ubuntu:act-latest` passed.
- `BUILDX_BUILDER=cnpg-walreplay-builder PATH=/tmp/dagger-sync-bin:$PATH task checks:all`
  passed for all 19 mirror extension targets. The default Docker driver was
  unable to process attestations, so the existing Docker-container builder was
  used for this lint-only check.

## Bottom line

Adopt the shared maintenance/build-matrix refactor, Dagger unit-test workflow, `bake --check` fix, dynamic CNPG smoke matrix, current CNPG Taskfile fix, and adapted security/contributor metadata. Keep extension-specific updates, upstream-only extensions, and all upstream CODEOWNERS changes out of the mirror. Dependency-only chores are consolidated above.
