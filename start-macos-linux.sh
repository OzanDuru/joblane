#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
# Local settings persist across terminal sessions. Keep this file private.
if [ -f ./config.local.sh ]; then . ./config.local.sh; fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m playwright install chromium
fi
.venv/bin/python run.py init
exec .venv/bin/python run.py serve --open
