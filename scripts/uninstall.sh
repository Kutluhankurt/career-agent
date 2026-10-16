#!/usr/bin/env sh
# Removes Career Agent. Your data in ~/.career-agent is kept unless you pass --purge.
set -eu
if command -v career >/dev/null 2>&1; then
  career stop || true
  career autostart off || true
fi
uv tool uninstall career-agent 2>/dev/null || true
if [ "${1:-}" = "--purge" ]; then
  rm -rf "${CAREER_AGENT_HOME:-$HOME/.career-agent}"
  echo "Removed Career Agent and all its data."
else
  echo "Removed Career Agent. Your data is still in ${CAREER_AGENT_HOME:-$HOME/.career-agent} (use --purge to delete it)."
fi
echo "Stored API keys stay in your keychain under 'career-agent'; remove them with your keychain app if you like."
