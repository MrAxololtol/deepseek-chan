#!/usr/bin/env bash
# DeepSeek-chan installer (development / clone install).
#
#   ./scripts/install.sh            install the package + opencode plugin
#   ./scripts/install.sh --no-plugin
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install_plugin=1
for arg in "$@"; do
  [[ "$arg" == "--no-plugin" ]] && install_plugin=0
done

echo "==> Installing deepseek-chan from $here"
if command -v pipx >/dev/null 2>&1; then
  pipx install --force "$here"
else
  python3 -m pip install --user --upgrade "$here"
fi

if [[ "$install_plugin" == "1" ]]; then
  echo "==> Installing opencode plugin"
  if command -v deepseek-chan >/dev/null 2>&1; then
    deepseek-chan install-plugin
  else
    python3 -m deepseek_chan install-plugin
  fi
fi

echo
echo "Done. Restart opencode, then run:  deepseek-chan run"
echo "Try it now with:                   deepseek-chan --demo"
