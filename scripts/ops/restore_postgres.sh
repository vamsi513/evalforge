#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <dump_file>"
  exit 1
fi

DUMP_FILE="$1"
if [ ! -f "${DUMP_FILE}" ]; then
  echo "Dump file not found: ${DUMP_FILE}"
  exit 1
fi

pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --dbname="${PGDATABASE}" \
  "${DUMP_FILE}"

echo "Restore completed from: ${DUMP_FILE}"
