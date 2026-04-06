Ansible playbook for deploying the Discord issue bot in a VM.

## Expected vault variables

Create an ansible-vault file (or pass via `--extra-vars`) providing the
following variables — the playbook will refuse to render without them:

- `container_image` — e.g. `ghcr.io/<owner>/discord-bot:latest`
- `github_actions_ssh_key` — the public SSH key used by the Deploy workflow
- `discord_bot_token`
- `discord_app_id`
- `gemini_api_key`
- `github_app_id`
- `github_app_installation_id`
- `github_app_private_key` — full PEM contents of the GitHub App private key (multiline)
TODO(p2004a): setup vault in-repo
## Run

```bash
cd infra
ansible-playbook playbook.yml --ask-vault-pass
```
