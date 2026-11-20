#!/usr/bin/env bash
#
# SnapSumbong API — deployment bootstrap for the EC2 host.
#
#   1. Reads every parameter under /prod/backend/ from AWS Systems Manager
#      Parameter Store (authenticated via the EC2 instance profile — no keys).
#   2. Writes them to ./.env (mode 600) for docker compose interpolation and
#      for the web container (env_file).
#
# Usage:
#   ./fetch-env.sh          refresh .env
#
# Environment overrides:
#   PARAMETER_PATH   default: /prod/backend/
#   AWS_REGION       defaults to `aws configure get region`
#
# NOTE: Parameter values must be single-line (no tabs/newlines) and should not
# contain "$" (docker compose interpolates .env values into docker-compose.yml).

set -euo pipefail

PARAMETER_PATH="${PARAMETER_PATH:-/prod/backend/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/.env"

# Variables the app cannot start without (see config/settings/env.py) plus the
# ones docker-compose.yml needs for interpolation.
# required for Django or docker-compose
REQUIRED_VARS=(
    DJANGO_SECRET_KEY
    JWT_SECRET_KEY
    DEBUG
    SECURE_SSL_REDIRECT
    ALLOWED_HOSTS
    TRUSTED_ORIGINS
    COOKIE_DOMAIN
    DB_NAME
    DB_USER
    DB_PASSWORD
    DB_HOST
    DB_PORT
    CLOUDINARY_CLOUD_NAME
    CLOUDINARY_API_KEY
    CLOUDINARY_API_SECRET
    RESEND_API_KEY
    DEFAULT_FROM_EMAIL
    DOMAIN
    CERT_EMAIL
)

command -v aws >/dev/null 2>&1 || { echo "ERROR: AWS CLI not found — install AWS CLI v2." >&2; exit 1; }

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [ -z "$REGION" ]; then
    REGION="$(aws configure get region 2>/dev/null || true)"
fi
if [ -z "$REGION" ]; then
    echo "ERROR: AWS region unknown — set AWS_REGION or run 'aws configure set region <region>'." >&2
    exit 1
fi

echo "Fetching parameters from ${PARAMETER_PATH} (region: ${REGION})..."
PARAMS="$(aws ssm get-parameters-by-path \
    --path "$PARAMETER_PATH" \
    --recursive \
    --with-decryption \
    --region "$REGION" \
    --query 'Parameters[].[Name,Value]' \
    --output text)"

if [ -z "$PARAMS" ]; then
    echo "ERROR: no parameters found under ${PARAMETER_PATH}" >&2
    exit 1
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

# /prod/backend/FOO -> line "FOO=bar"
while IFS=$'\t' read -r name value; do
    [ -n "${name:-}" ] || continue
    printf '%s=%s\n' "${name##*/}" "$value" >>"$TMP_FILE"
done <<<"$PARAMS"

# --- validate --------------------------------------------------------------
MISSING=()
for key in "${REQUIRED_VARS[@]}"; do
    grep -qE "^${key}=..*" "$TMP_FILE" || MISSING+=("$key")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "ERROR: missing/empty required parameters under ${PARAMETER_PATH}:" >&2
    printf '  - %s\n' "${MISSING[@]}" >&2
    echo "Add them in the AWS console (Parameter Store) and re-run this script." >&2
    exit 1
fi

cp "$TMP_FILE" "$OUTPUT_FILE"
chmod 600 "$OUTPUT_FILE"
echo "Wrote $(grep -c . "$TMP_FILE") variables to ${OUTPUT_FILE}"
