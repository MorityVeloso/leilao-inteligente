#!/bin/bash
# Upload all lote_frames to Supabase Storage
set -e
source /Users/mority/Dev/Projects/leilao-inteligente/.env

BASE="/Users/mority/Dev/Projects/leilao-inteligente/data/lote_frames"
BUCKET="lote-frames"
UPLOADED=0
FAILED=0
TOTAL=$(find "$BASE" -name "*.jpg" | wc -l | tr -d ' ')

echo "Uploading $TOTAL frames to Supabase Storage..."

find "$BASE" -name "*.jpg" | while read -r file; do
  # Extract relative path: oCo0wC31R14/260/visual_1.jpg
  REL="${file#$BASE/}"

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SUPABASE_URL}/storage/v1/object/${BUCKET}/${REL}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: image/jpeg" \
    -H "x-upsert: true" \
    --data-binary "@${file}")

  if [ "$HTTP_CODE" = "200" ]; then
    UPLOADED=$((UPLOADED + 1))
  else
    FAILED=$((FAILED + 1))
    echo "FAIL ($HTTP_CODE): $REL"
  fi

  if [ $((UPLOADED % 100)) -eq 0 ] && [ $UPLOADED -gt 0 ]; then
    echo "  uploaded: $UPLOADED / $TOTAL"
  fi
done

echo "Done! Uploaded: $UPLOADED, Failed: $FAILED"
