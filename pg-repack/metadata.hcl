metadata = {
  name                     = "pg-repack"
  sql_name                 = "pg_repack"
  image_name               = "pg-repack"
  licenses                 = ["BSD-3-Clause"]
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-repack
      "18" = "1.5.3-1.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-repack
      "18" = "1.5.3-1.pgdg13+1"
    }
  }
}
