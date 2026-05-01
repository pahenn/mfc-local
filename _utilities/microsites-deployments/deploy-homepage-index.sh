#!/bin/bash
set -euo pipefail

# Deploy ONLY index.html from the homepage repo to production, invalidating
# the cache for portal.myfleetcenter.com only.
#
# 1. Upload index.html → s3://myfleetcenter.com/landing-pages/
# 2. Find the CloudFront distribution that fronts portal.myfleetcenter.com
# 3. Invalidate /index.html on that one distribution
#
# Usage: AWS_PROFILE=mfc ./deploy-homepage-index.sh

REPO_DIR="${HOMEPAGE_REPO_DIR:-/Users/pahenn/projects/mfc/myfleetcenter-microsites-homepage}"
PROFILE="${AWS_PROFILE:-mfc}"
BUCKET="myfleetcenter.com"
PREFIX="landing-pages"
ALIAS="portal.myfleetcenter.com"
FILE_PATH="${REPO_DIR}/index.html"

if [ ! -f "$FILE_PATH" ]; then
  echo "Error: $FILE_PATH not found"
  exit 1
fi

echo "Profile: $PROFILE"
echo "Account: $(aws --profile "$PROFILE" sts get-caller-identity --query Account --output text)"
echo "Source:  $FILE_PATH"
echo "Target:  s3://${BUCKET}/${PREFIX}/index.html"
echo "Cache:   ${ALIAS}"
echo
read -rp "Upload index.html? (yes/no): " upload_confirm
[ "$upload_confirm" = "yes" ] || { echo "Cancelled."; exit 0; }

# --- 1. Upload single file (no --delete, nothing else touched) ---
aws --profile "$PROFILE" s3 cp "$FILE_PATH" "s3://${BUCKET}/${PREFIX}/index.html"

# --- 2. Find the distribution whose alias list contains portal.myfleetcenter.com ---
echo
echo "Looking up CloudFront distribution for ${ALIAS}..."
DIST_ID=$(aws --profile "$PROFILE" cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Aliases.Items, \`${ALIAS}\`)].Id | [0]" \
  --output text)

if [ -z "$DIST_ID" ] || [ "$DIST_ID" = "None" ]; then
  echo "No distribution found with alias ${ALIAS}. File is uploaded but cache not invalidated."
  exit 0
fi

echo "Distribution: $DIST_ID"

# --- 3. Invalidate /index.html on that distribution ---
INV_ID=$(aws --profile "$PROFILE" cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/index.html" \
  --query 'Invalidation.Id' --output text)

echo "Invalidation: $INV_ID"
echo
echo "Done."
