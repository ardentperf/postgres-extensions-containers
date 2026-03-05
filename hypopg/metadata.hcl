metadata = {
  name                     = "hypopg"
  sql_name                 = "hypopg"
  image_name               = "hypopg"
  licenses                 = ["PostgreSQL"]
  shared_preload_libraries = []
  extension_control_path   = []
  dynamic_library_path     = []
  ld_library_path          = []
  auto_update_os_libs      = false
  required_extensions      = []
  create_extension         = true

  versions = {
    bookworm = {
      // renovate: suite=bookworm-pgdg depName=postgresql-18-hypopg
      "18" = "1.4.2-2.pgdg12+1"
    }
    trixie = {
      // renovate: suite=trixie-pgdg depName=postgresql-18-hypopg
      "18" = "1.4.2-2.pgdg13+1"
    }
  }
}
