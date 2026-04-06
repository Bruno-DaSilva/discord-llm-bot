> [!IMPORTANT]
>
> This project was generated via **Claude Code** with the following notes:
> 1. The code for this repo started off heavily "vibe coded" ie. with minimal supervision. As the bot neared completion, more and more time was spent in human-in-the-loop.
> 2. The test suite is almost entirely LLM-generated with minimal review. Though, it was pushed to test as abstractly as reasonable.
> 2. Generation of `docs/` + human review was performed for correctness and conciseness. They should be treated as _mostly_ human-approved by authors.
> 3. All ai-driven commits should be co-authored by Claude to be clear which bits were fully-human changes.
> 4. The underlying implementation has been through multiple iterations of simplification and refactoring. The original implementation had massive 400 line functions and far too much code duplication. I'm pretty happy with the current result.
> 5. This bot was manually tested against a test discord server before release.
>
> Because it's LLM-generated to an almost full extent, the copyright status is unclear; accordingly, no license is defined.
>
> NOTE: this disclosure takes heavy inspiration from https://github.com/p2004a/desync-detector/blob/d5c847a1b09fdf22079e9e8107838bffe9b3374c/README.md?plain=1#L1-L12

# Discord Issue Bot

Discord bot that generates GitHub issues from channel messages using Gemini AI. Invoke `/create-issue` in any channel to fetch recent messages, generate an issue draft, and create it on GitHub.

## Setup

```bash
uv sync
cp example.env .env   # fill in your secrets
```

## Run

```bash
# Local
uv run python -m src.bot

# Docker
docker build -t discord-issue-bot .
docker run --env-file .env \
  -v "$GITHUB_APP_PRIVATE_KEY_PATH:/run/secrets/github_app_key.pem:ro" \
  -e GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github_app_key.pem \
  discord-issue-bot
```

## Test

```bash
uv run pytest
uv run pytest --cov=src
```

## Deployment

Automated via GitHub Actions (`.github/workflows/deploy.yml`) — builds the image
on push to `main`, pushes to `ghcr.io`, and triggers `podman-auto-update` on the
configured host over SSH. See `infra/README.md` for the Ansible playbook that
provisions the target VM.

## Architecture

See [doc/ARCHITECTURE.md](doc/ARCHITECTURE.md) for the pipeline design.
