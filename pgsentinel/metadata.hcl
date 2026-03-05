metadata = {
  name                     = "pgsentinel"
  sql_name                 = "pgsentinel"
  image_name               = "pgsentinel"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = ["pg_stat_statements", "pgsentinel"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-pgsentinel
      "18" = "1.4.0-1.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-pgsentinel
      "18" = "1.4.0-1.pgdg13+1"
    }
  }
}
