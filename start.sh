#!/usr/bin/env bash
set -euo pipefail

# Source .env to read GITHUB_APP_PRIVATE_KEY_PATH for the volume mount
set -a; source .env; set +a

docker run --rm \
  --env-file .env \
  -v "${GITHUB_APP_PRIVATE_KEY_PATH}:/run/secrets/github_app_key.pem:ro" \
  -e GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github_app_key.pem \
  discord-bot
