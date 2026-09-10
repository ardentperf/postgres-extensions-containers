# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgsphere=${EXT_VERSION}"

RUN set -eu && \
	. /etc/os-release && \
	mkdir -p /licenses && \
	if [ "$VERSION_CODENAME" = trixie ]; then \
		for copyright in \
			/usr/share/doc/libnghttp3-9/copyright \
			/usr/share/doc/libngtcp2*/copyright; do \
			package="${copyright%/copyright}"; package="${package##*/}"; \
			mkdir -p "/licenses/$package" && cp -a "$copyright" "/licenses/$package/"; \
		done; \
	fi

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /licenses /licenses/
COPY --parents --from=builder /usr/share/doc/./libbrotli1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libcfitsio10*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libcurl*-gnutls/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libgomp1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libhealpix-cxx*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libnghttp2-14/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libpsl5*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./librtmp1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libsharp0/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libssh2-1*/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-pgsphere/copyright /licenses/postgresql-${PG_MAJOR}-pgsphere/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/pg_sphere.so /lib/
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/bitcode/ /lib/bitcode/

# System libs
COPY --from=builder /lib/*-linux-gnu/libbrotlicommon.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libbrotlidec.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libcfitsio.so.10 /system/
COPY --from=builder /lib/*-linux-gnu/libcurl-gnutls.so.4 /system/
COPY --from=builder /lib/*-linux-gnu/libgomp.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libhealpix_cxx.so.* /system/
# These globs cover distro-specific transitive libcurl dependencies.
COPY --from=builder /lib/*-linux-gnu/libngh*.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libngt*.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libpsl.so.5 /system/
COPY --from=builder /lib/*-linux-gnu/librtmp.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libsharp.so.0 /system/
COPY --from=builder /lib/*-linux-gnu/libssh2.so.1 /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/pg_sphere* /share/extension/

USER 65532:65532
