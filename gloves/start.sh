#!/bin/sh
# Sign Talk gloves: run ./start.sh. First run sets everything up (about a minute).
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  echo "Setting up for the first time: installing uv, a small Python manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"
fi
exec uv run --python 3.12 signtalk-gloves run --name "$(hostname)" "$@"
