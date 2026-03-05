metadata = {
  name                     = "pg-partman"
  sql_name                 = "pg_partman"
  image_name               = "pg-partman"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = ["pg_partman_bgw"]
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-partman
      "18" = "5.4.2-1.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-partman
      "18" = "5.4.2-1.pgdg13+1"
    }
  }
}
