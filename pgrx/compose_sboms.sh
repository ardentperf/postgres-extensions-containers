#!/usr/bin/env bash
set -Eeuo pipefail

# Run the neutral PR 61 filesystem/ScanCode composition first. The alternate
# Bake file is the only build-system input the shared wrapper needs.
./scripts/compose_sboms.sh --bake-file docker-bake-pgrx.hcl

working_directory="${RUNNER_TEMP}/extension-sbom"
bake_definition="${working_directory}/bake.json"
mapfile -t bake_targets < <(jq -r '.target | keys[]' "${bake_definition}")
test "${#bake_targets[@]}" -gt 0

platform_spec="${BUILD_PLATFORMS:-linux/amd64 linux/arm64}"
read -r -a platforms <<< "${platform_spec}"
test "${#platforms[@]}" -gt 0
for platform in "${platforms[@]}"; do
  case "${platform}" in
    linux/amd64|linux/arm64) ;;
    *)
      echo "unsupported build platform: ${platform}" >&2
      exit 2
      ;;
  esac
done

for bake_target in "${bake_targets[@]}"; do
  cyclonedx_paths=()
  about_paths=()

  for platform in "${platforms[@]}"; do
    output_directory="${working_directory}/pgrx-${bake_target}-${platform//\//-}"
    mkdir -p "${output_directory}"

    # Export only the named pgrx-sbom stage. The builder root is deliberately
    # not exported because it contains source, Cargo registry, and toolchains.
    docker buildx bake -f docker-bake-pgrx.hcl -f "${EXTENSION_NAME}/metadata.hcl" "${bake_target}" \
      --set "${bake_target}.platform=${platform}" \
      --set "${bake_target}.dockerfile=${EXTENSION_NAME}/.sbom.Dockerfile" \
      --set "${bake_target}.target=pgrx-sbom" \
      --set "${bake_target}.output=type=local,dest=${output_directory}" \
      --progress plain

    report_root="${output_directory}/pgrx-sbom"
    cyclonedx="${report_root}/cyclonedx.json"
    about="${report_root}/cargo-about.json"
    test -s "${cyclonedx}"
    test -s "${about}"

    runtime_directory="${working_directory}/${bake_target}-${platform//\//-}"
    find "${runtime_directory}/lib" -maxdepth 1 -type f -name '*.so' -print -quit | grep -q .
    find "${runtime_directory}/share/extension" -maxdepth 1 -type f -name '*.control' -print -quit | grep -q .
    find "${runtime_directory}/share/extension" -maxdepth 1 -type f -name '*.sql' -print -quit | grep -q .
    test -d "${runtime_directory}/licenses/rust"
    if [[ -d "${runtime_directory}/system" ]]; then
      test -d "${runtime_directory}/licenses/system"
    fi

    cyclonedx_paths+=("${cyclonedx}")
    about_paths+=("${about}")
  done

  predicate="${working_directory}/predicates/${bake_target}/extension-sbom.spdx.json"
  test -s "${predicate}"
  compose_args=(
    ./pgrx/compose_pgrx_sbom.py
    --spdx "${predicate}"
    --output "${predicate}"
    --extension-name "${EXTENSION_NAME}"
  )
  for index in "${!platforms[@]}"; do
    compose_args+=(
      --cargo-cyclonedx "${cyclonedx_paths[$index]}"
      --cargo-about "${about_paths[$index]}"
      --platform "${platforms[$index]}"
    )
  done
  "${compose_args[@]}"
  jq -e --arg namespace "${COMPOSITION_NAMESPACE:-https://github.com/cnpg-extensions/postgres-extensions-containers/sbom-composition/v1}" '
    .spdxVersion == "SPDX-2.3" and
    any((.annotations // [])[]; .spdxElementId == "SPDXRef-DOCUMENT" and
      .annotationType == "OTHER" and (.comment | startswith($namespace + " ")) and
      (.comment | contains("pgrx"))) and
    ([.packages[]? | select((.SPDXID // "") | startswith("SPDXRef-Cargo-"))] | length > 0) and
    ([.relationships[]? | select(
      .relationshipType == "DEPENDENCY_OF" and
      ((.spdxElementId // "") | startswith("SPDXRef-Cargo-")) and
      ((.relatedSpdxElement // "") | startswith("SPDXRef-Cargo-"))
    )] | length > 0)
  ' "${predicate}" >/dev/null
done
