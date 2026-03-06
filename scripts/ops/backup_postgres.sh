#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-backups}"
mkdir -p "${OUTPUT_DIR}"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
FILE_PATH="${OUTPUT_DIR}/evalforge_${TIMESTAMP}.dump"

pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="${FILE_PATH}" \
  "${PGDATABASE}"

echo "Backup created: ${FILE_PATH}"
