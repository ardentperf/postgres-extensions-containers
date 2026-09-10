# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright © contributors to CNPG Extensions.
# SPDX-License-Identifier: Apache-2.0

ARG BASE=ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie
FROM $BASE AS builder

ARG PG_MAJOR
ARG EXT_VERSION

USER 0

RUN apt-get update && \
	apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-mobilitydb=${EXT_VERSION}"

RUN set -eu && \
	. /etc/os-release && \
	mkdir -p /licenses && \
	if [ "$VERSION_CODENAME" = trixie ]; then \
		for copyright in \
			/usr/share/doc/libnghttp3-9/copyright \
			/usr/share/doc/libngtcp2*/copyright \
			/usr/share/doc/libsharpyuv0/copyright; do \
			package="${copyright%/copyright}"; package="${package##*/}"; \
			mkdir -p "/licenses/$package" && cp -a "$copyright" "/licenses/$package/"; \
		done; \
	fi

FROM scratch
ARG PG_MAJOR

# Licenses
COPY --from=builder /licenses /licenses/
COPY --parents --from=builder /usr/share/doc/./liblerc4/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libbrotli1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libcurl*-gnutls/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libdeflate0/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libgeos3.*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libgsl[0-9]*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libgslcblas0/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libjbig0/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libjpeg62-turbo/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libjson-c5/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libnghttp2-14/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libproj25/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libpsl5*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./librtmp1/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libssh2-1*/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libtiff6/copyright /licenses/
COPY --parents --from=builder /usr/share/doc/./libwebp7/copyright /licenses/
COPY --from=builder /usr/share/doc/postgresql-${PG_MAJOR}-mobilitydb/copyright /licenses/postgresql-${PG_MAJOR}-mobilitydb/

# Libraries
COPY --from=builder /usr/lib/postgresql/${PG_MAJOR}/lib/libMobilityDB-1.3.so /lib/

# System libs
COPY --from=builder /lib/*-linux-gnu/libLerc.so.4 /system/
COPY --from=builder /lib/*-linux-gnu/libbrotlicommon.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libbrotlidec.so.1 /system/
COPY --from=builder /lib/*-linux-gnu/libcurl-gnutls.so.4 /system/
COPY --from=builder /lib/*-linux-gnu/libdeflate.so.0 /system/
COPY --from=builder /lib/*-linux-gnu/libgeos.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libgsl.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libgslcblas.so.0 /system/
COPY --from=builder /lib/*-linux-gnu/libjbig.so.0 /system/
COPY --from=builder /lib/*-linux-gnu/libjpeg.so.62 /system/
COPY --from=builder /lib/*-linux-gnu/libjson-c.so.5 /system/
# These globs cover distro-specific transitive libcurl dependencies.
COPY --from=builder /lib/*-linux-gnu/libngh*.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libngt*.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libproj.so.25 /system/
COPY --from=builder /lib/*-linux-gnu/libpsl.so.5 /system/
COPY --from=builder /lib/*-linux-gnu/librtmp.so.1 /system/
# libsharpyuv is present on trixie; libssh2 is present on both distros.
COPY --from=builder /lib/*-linux-gnu/libsh*.so.* /system/
COPY --from=builder /lib/*-linux-gnu/libtiff.so.6 /system/
COPY --from=builder /lib/*-linux-gnu/libwebp.so.7 /system/

# Share
COPY --from=builder /usr/share/postgresql/${PG_MAJOR}/extension/mobilitydb* /share/extension/

USER 65532:65532
