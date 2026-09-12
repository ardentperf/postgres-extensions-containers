#!/usr/bin/env bash
set -Eeuo pipefail

extension_so="${1:?path to pg_duckdb.so is required}"
base_libraries="${2:?pristine base library list is required}"
output_root="${3:?runtime output directory is required}"
system_dir="${output_root}/system"
license_dir="${output_root}/licenses/system"
state_file="${output_root}/runtime-state.tsv"

test -s "${extension_so}"
test -s "${base_libraries}"
mkdir -p "${system_dir}" "${license_dir}"
: > "${state_file}"

declare -a queue=()
mapfile -t queue < <(
  readelf -d "${extension_so}" | sed -n 's/.*(NEEDED).*\[\([^]]*\)\].*/\1/p'
)
declare -A visited=()

resolve_library() {
  local soname="$1"
  ldconfig -p | awk -v wanted="${soname}" '$1 == wanted {print $NF; exit}'
}

copy_library_aliases() {
  local soname="$1"
  local resolved="$2"
  local alias
  while IFS= read -r alias; do
    [ -n "${alias}" ] || continue
    if [ -L "${alias}" ] || [ "$(readlink -f "${alias}")" = "${resolved}" ]; then
      cp -a "${alias}" "${system_dir}/"
    fi
  done < <(ldconfig -p | awk -v wanted="${soname}" '$1 == wanted {print $NF}')
  cp -a "${resolved}" "${system_dir}/"
}

while ((${#queue[@]})); do
  soname="${queue[0]}"
  queue=("${queue[@]:1}")
  [ -n "${soname}" ] || continue
  case "${soname}" in
    linux-vdso.*|ld-linux*.so.*) continue ;;
  esac
  resolved_path="$(resolve_library "${soname}" || true)"
  if [ -z "${resolved_path}" ] || [ ! -e "${resolved_path}" ]; then
    echo "cannot resolve runtime library ${soname}" >&2
    exit 2
  fi
  resolved_path="$(readlink -f "${resolved_path}")"
  if [ "${visited[${resolved_path}]+yes}" = yes ]; then
    continue
  fi
  visited["${resolved_path}"]=1

  base_provided=false
  if grep -Fxq "${resolved_path}" "${base_libraries}"; then
    base_provided=true
  else
    copy_library_aliases "${soname}" "${resolved_path}"
  fi
  mapfile -t child_sonames < <(
    readelf -d "${resolved_path}" | sed -n 's/.*(NEEDED).*\[\([^]]*\)\].*/\1/p'
  )
  queue+=("${child_sonames[@]}")

  # dpkg-query normally resolves the canonical file directly.  Keep a
  # package-file-list fallback for images where ldconfig canonicalizes a
  # multiarch library path differently from the pathname in dpkg's database.
  package_spec="$(dpkg-query -S -- "${resolved_path}" 2>/dev/null | awk -F ': ' 'NR == 1 {print $1}' || true)"
  if [ -z "${package_spec}" ]; then
    package_paths=("${resolved_path}")
    case "${resolved_path}" in
      /usr/lib/*) package_paths+=("/${resolved_path#/usr/}") ;;
      /lib/*) package_paths+=("/usr/${resolved_path#/}") ;;
    esac
    while IFS= read -r candidate; do
      for package_path in "${package_paths[@]}"; do
        if dpkg-query -L "${candidate}" 2>/dev/null | grep -Fqx -- "${package_path}"; then
          package_spec="${candidate}"
          break 2
        fi
      done
    done < <(dpkg-query -W -f='${binary:Package}\n' 2>/dev/null | sort -u)
  fi
  if [ -z "${package_spec}" ]; then
    echo "no Debian package owns runtime library ${resolved_path}" >&2
    exit 2
  fi
  package="${package_spec%%:*}"
  version="$(dpkg-query -W -f='${Version}' "${package_spec}")"
  architecture="$(dpkg-query -W -f='${Architecture}' "${package_spec}")"
  purl="pkg:deb/debian/${package}@${version}?arch=${architecture}"
  license_paths=""
  if [ "${base_provided}" = false ]; then
    package_license_dir="${license_dir}/${package}"
    mkdir -p "${package_license_dir}"
    while IFS= read -r license_path; do
      [ -n "${license_path}" ] || continue
      destination="${package_license_dir}/$(basename "${license_path}")"
      cp -a "${license_path}" "${destination}"
      if [ -n "${license_paths}" ]; then license_paths+=","; fi
      license_paths+="${destination}"
    done < <(
      find "/usr/share/doc/${package}" -maxdepth 1 -type f \
        \( -iname 'copyright*' -o -iname 'license*' \) -print 2>/dev/null | sort
    )
    if [ -z "${license_paths}" ]; then
      echo "no Debian license evidence for copied package ${package}" >&2
      exit 2
    fi
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${soname}" "${resolved_path}" "${package}" "${version}" \
    "${architecture}" "${purl}" "${base_provided}" "${license_paths}" >> "${state_file}"
done

if ldd "${extension_so}" | grep -q 'not found'; then
  echo "ldd reports an unresolved extension dependency" >&2
  exit 2
fi

python3 - "${state_file}" "${output_root}/runtime-libraries.json" "${output_root}" <<'PY'
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

state_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
output_root = Path(sys.argv[3])
groups = defaultdict(lambda: {
    "sonames": set(),
    "resolvedPath": "",
    "package": {},
    "baseProvided": True,
    "fileChecksums": [],
    "licensePaths": set(),
})
for line in state_path.read_text(encoding="utf-8").splitlines():
    fields = line.split("\t")
    if len(fields) != 8:
        raise SystemExit(f"invalid runtime state line: {line!r}")
    soname, resolved, package, version, architecture, purl, base, licenses = fields
    key = (package, version, architecture)
    record = groups[key]
    record["sonames"].add(soname)
    record["resolvedPath"] = resolved
    record["baseProvided"] = record["baseProvided"] and base == "true"
    record["package"] = {
        "name": package,
        "version": version,
        "architecture": architecture,
        "purl": purl,
    }
    for license_path in filter(None, licenses.split(",")):
        record["licensePaths"].add(license_path)
    if not record["baseProvided"]:
        candidate = output_root / "system" / Path(resolved).name
        if candidate.is_file():
            record["fileChecksums"].append({
                "path": "/system/" + candidate.name,
                "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            })
for record in groups.values():
    record["sonames"] = sorted(record["sonames"])
    record["licensePaths"] = sorted(record["licensePaths"])
    record["fileChecksums"] = sorted(record["fileChecksums"], key=lambda item: item["path"])
output = {
    "schemaVersion": "https://github.com/cnpg-extensions/postgres-extensions-containers/pg-duckdb-runtime/v1",
    "extension": "pg_duckdb",
    "libraries": sorted(groups.values(), key=lambda item: item["package"]["name"]),
}
output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

rm -f "${state_file}"
