# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  name                     = "pgsentinel"
  sql_name                 = "pgsentinel"
  image_name               = "pgsentinel"
  shared_preload_libraries = ["pgsentinel"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false

  versions = {
    trixie = {
        // renovate: suite=trixie-pgdg depName=postgresql-18-pgsentinel
        "18" = "1.3.1-1.pgdg13+1"
    }
    bookworm = {
        // renovate: suite=bookworm-pgdg depName=postgresql-18-pgsentinel
        "18" = "1.3.1-1.pgdg12+1"
    }
  }
}
