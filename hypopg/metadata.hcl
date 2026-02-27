# SPDX-FileCopyrightText: Copyright © contributors to CloudNativePG, established as CloudNativePG a Series of LF Projects, LLC.
# SPDX-License-Identifier: Apache-2.0
metadata = {
  name                     = "hypopg"
  sql_name                 = "hypopg"
  image_name               = "hypopg"
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false

  versions = {
    trixie = {
        // renovate: suite=trixie-pgdg depName=postgresql-18-hypopg
        "18" = "1.4.2-2.pgdg13+1"
    }
    bookworm = {
        // renovate: suite=bookworm-pgdg depName=postgresql-18-hypopg
        "18" = "1.4.2-2.pgdg12+1"
    }
  }
}
