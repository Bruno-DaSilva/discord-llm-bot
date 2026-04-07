#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

uv run python -m src.bot
