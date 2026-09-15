#!/usr/bin/env bash
# MongoDB Restore Script (Bash)
set -euo pipefail

ARCHIVE_PATH="${1:-}"
MONGO_URI="${MONGO_URI:-mongodb://mongodb:27017}"
DB_NAME="${DB_NAME:-deep_research_ai}"
DROP_FLAG="${2:-}"

if [[ -z "${ARCHIVE_PATH}" || ! -f "${ARCHIVE_PATH}" ]]; then
    echo "Error: Please provide a valid backup archive path."
    echo "Usage: $0 /path/to/backup.gz [--drop]"
    exit 1
fi

echo "Restoring database '${DB_NAME}' from '${ARCHIVE_PATH}'..."

if command -v mongorestore >/dev/null 2>&1; then
    mongorestore --uri="${MONGO_URI}" --nsInclude="${DB_NAME}.*" --gzip --archive="${ARCHIVE_PATH}" ${DROP_FLAG}
    echo "Restore completed successfully."
else
    echo "Warning: mongorestore not found on host."
fi
