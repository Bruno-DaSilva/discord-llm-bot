#!/usr/bin/env bash
set -euo pipefail

docker run --rm --env-file .env discord-bot
