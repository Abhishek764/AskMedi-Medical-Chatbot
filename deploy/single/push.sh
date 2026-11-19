#!/usr/bin/env bash
# Assemble the Hugging Face Space repo from this repository and push it.
#   HF_TOKEN=hf_xxx HF_SPACE=<user>/askmedi bash deploy/single/push.sh
# The Space must already exist (Docker SDK). Secrets are set in the Space settings, not here.
set -euo pipefail

: "${HF_TOKEN:?set HF_TOKEN (write token from https://huggingface.co/settings/tokens)}"
: "${HF_SPACE:?set HF_SPACE, e.g. yourname/askmedi}"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

cd "$repo_root"
mkdir -p "$work/backend" "$work/web"
cp deploy/single/Dockerfile deploy/single/README.md "$work/"
# Tracked files only: no .env, venv, local databases or node_modules.
git archive HEAD backend/pyproject.toml backend/uv.lock backend/alembic.ini \
  backend/app backend/migrations | (cd "$work" && tar -x)
git archive HEAD web | (cd "$work" && tar -x)
git archive HEAD data/policies | (cd "$work" && tar -x)
printf 'node_modules\n' > "$work/.dockerignore"

cd "$work"
git init -q -b main
git add -A
git -c user.name="deploy" -c user.email="deploy@localhost" commit -q -m "Deploy $(git -C "$repo_root" rev-parse --short HEAD)"
# Token goes through a credential helper that reads the environment, never the URL or argv.
git -c credential.helper= \
  -c credential.helper='!f() { echo username=hf; echo "password=${HF_TOKEN}"; }; f' \
  push -q --force "https://huggingface.co/spaces/${HF_SPACE}" main
echo "Pushed. Build log: https://huggingface.co/spaces/${HF_SPACE}?logs=build"
