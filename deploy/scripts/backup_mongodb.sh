#!/usr/bin/env bash
# Automated MongoDB Backup Script (Bash)
set -euo pipefail

MONGO_URI="${MONGO_URI:-mongodb://mongodb:27017}"
DB_NAME="${DB_NAME:-deep_research_ai}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="${DB_NAME}_backup_${TIMESTAMP}.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

echo "Starting MongoDB backup for database: ${DB_NAME}..."
echo "Target archive: ${ARCHIVE_PATH}"

if command -v mongodump >/dev/null 2>&1; then
    mongodump --uri="${MONGO_URI}" --db="${DB_NAME}" --gzip --archive="${ARCHIVE_PATH}"
    echo "Backup completed successfully: $(ls -lh "${ARCHIVE_PATH}" | awk '{print $5}')"
else
    echo "Warning: mongodump not found on host. Use containerized mongodump if running inside Docker."
fi

echo "Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "${DB_NAME}_backup_*.gz" -type f -mtime +"${RETENTION_DAYS}" -delete

echo "Backup operation finished."
