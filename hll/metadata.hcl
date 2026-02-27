# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  name                     = "hll"
  sql_name                 = "hll"
  image_name               = "hll"
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false

  versions = {
    trixie = {
        // renovate: suite=trixie-pgdg depName=postgresql-18-hll
        "18" = "2.19-2.pgdg13+2"
    }
    bookworm = {
        // renovate: suite=bookworm-pgdg depName=postgresql-18-hll
        "18" = "2.19-2.pgdg12+2"
    }
  }
}
