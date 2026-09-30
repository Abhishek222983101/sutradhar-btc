SUTRADHAR — AIR-GAPPED INSTALL
================================

Requirements: Linux, Docker with Compose v2. No internet access is required after the images are built/loaded once.

INSTALL
  ./deploy/scripts/install.sh
  (builds images, starts the stack, creates a bootstrap admin account, prints its one-time password)

VERIFY (proves the install is correct and provably offline)
  ./deploy/scripts/selfcheck.sh

BACKUP / RESTORE
  ./deploy/scripts/backup.sh                          # writes backups/sutradhar-backup-<timestamp>.tar.gz
  ./deploy/scripts/restore.sh backups/<file>.tar.gz    # stops, restores, restarts, verifies

UPGRADE (after pulling new source)
  ./deploy/scripts/upgrade.sh                          # backs up first, then rebuilds and restarts

UNINSTALL
  ./deploy/scripts/uninstall.sh                 # stops the stack, keeps your data
  ./deploy/scripts/uninstall.sh --purge-data    # also deletes all data — irreversible

The web console is at http://127.0.0.1:8080 (set WEB_PORT to change the port). The API sits on an internal
Docker network with no route to the internet — the offline guard blocks any accidental outbound call in code,
and the network topology blocks it at the infrastructure level too, so it is proven both ways.

Everything in this system uses synthetic, generated data. No real Bitcoin traffic or seized data is included
or required.
