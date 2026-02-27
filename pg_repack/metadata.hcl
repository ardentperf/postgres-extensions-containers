# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  name                     = "pg_repack"
  sql_name                 = "pg_repack"
  image_name               = "pg-repack"
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false

  versions = {
    trixie = {
        // renovate: suite=trixie-pgdg depName=postgresql-18-repack
        "18" = "1.5.3-1.pgdg13+1"
    }
    bookworm = {
        // renovate: suite=bookworm-pgdg depName=postgresql-18-repack
        "18" = "1.5.3-1.pgdg12+1"
    }
  }
}
