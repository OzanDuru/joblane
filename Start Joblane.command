#!/bin/sh
cd "$(dirname "$0")" || exit 1
sh ./start-macos-linux.sh
result=$?
if [ "$result" -ne 0 ]; then
  printf '\nJoblane could not start. Read the error above. Press Return to close.\n'
  read -r answer
fi
exit "$result"
