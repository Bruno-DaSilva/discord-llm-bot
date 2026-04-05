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
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp example.env .env   # fill in your secrets
```

## Run

```bash
# Local
.venv/bin/python bot.py

# Docker
docker build -t discord-issue-bot .
docker run --env-file .env discord-issue-bot
```

## Test

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=src
```

## Architecture

See [doc/ARCHITECTURE.md](doc/ARCHITECTURE.md) for the pipeline design.
