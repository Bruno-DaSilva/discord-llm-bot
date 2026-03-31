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
