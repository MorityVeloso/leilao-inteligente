#!/bin/bash
# Upload all gemini_cache to Supabase Storage
set -e
source /Users/mority/Dev/Projects/leilao-inteligente/.env

BASE="/Users/mority/Dev/Projects/leilao-inteligente/data/gemini_cache"
BUCKET="gemini-cache"
COUNT=0
TOTAL=$(find "$BASE" -name "*.json" | wc -l | tr -d ' ')

echo "Uploading $TOTAL cache files to Supabase Storage..."

find "$BASE" -name "*.json" | while read -r file; do
  NAME=$(basename "$file")

  curl -s -o /dev/null -w "" \
    -X POST "${SUPABASE_URL}/storage/v1/object/${BUCKET}/${NAME}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "x-upsert: true" \
    --data-binary "@${file}"

  COUNT=$((COUNT + 1))
  if [ $((COUNT % 500)) -eq 0 ]; then
    echo "  uploaded: $COUNT / $TOTAL"
  fi
done

echo "Done! $TOTAL cache files uploaded."
