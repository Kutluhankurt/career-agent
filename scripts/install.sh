#!/usr/bin/env sh
# Career Agent installer for macOS and Linux.
#
#   From a checkout:   ./scripts/install.sh
#   From a source:     CAREER_AGENT_SOURCE="git+https://…/career-agent.git" sh install.sh
#   With an AI SDK:    CAREER_AGENT_EXTRAS="claude" ./scripts/install.sh   (claude | openai | gemini | all-ai)
#
# Installs the `career` command for the current user (no root needed) with uv,
# then starts the first-run setup.
set -eu

say() { printf '%s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

OS=$(uname -s)
ARCH=$(uname -m)
case "$OS" in
  Linux) PLATFORM=linux ;;
  Darwin) PLATFORM=macos ;;
  *) fail "Unsupported system: $OS. On Windows use scripts/install.ps1." ;;
esac
case "$ARCH" in
  x86_64|amd64) ARCH=x64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) fail "Unsupported CPU architecture: $ARCH" ;;
esac
say "Installing Career Agent for $PLATFORM ($ARCH)…"

if ! command -v uv >/dev/null 2>&1; then
  say "uv (Python package manager) not found; installing it for this user."
  command -v curl >/dev/null 2>&1 || fail "curl is required to install uv. Install curl, or install uv from https://docs.astral.sh/uv/."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"; export PATH
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")
if [ -n "${CAREER_AGENT_SOURCE:-}" ]; then
  SOURCE="$CAREER_AGENT_SOURCE"
elif [ -f "$REPO_DIR/pyproject.toml" ]; then
  SOURCE="$REPO_DIR"
else
  fail "Set CAREER_AGENT_SOURCE to a git URL, wheel or folder to install from."
fi
if [ -n "${CAREER_AGENT_EXTRAS:-}" ]; then
  case "$SOURCE" in
    git+*) SPEC="career-agent[${CAREER_AGENT_EXTRAS}] @ $SOURCE" ;;
    *) SPEC="${SOURCE}[${CAREER_AGENT_EXTRAS}]" ;;
  esac
else
  SPEC="$SOURCE"
fi

if [ "$PLATFORM" = linux ] && ! command -v xprop >/dev/null 2>&1; then
  say "Note: 'xprop' is missing; window tracking needs it (Debian/Ubuntu: sudo apt install x11-utils)."
fi

uv tool install --python 3.12 --force "$SPEC"
command -v career >/dev/null 2>&1 || PATH="$(uv tool dir --bin):$PATH"
say ""
career version
say "Data folder: ${CAREER_AGENT_HOME:-~/.career-agent}"
if [ -t 0 ]; then
  career setup
else
  say "Next: run 'career setup', then 'career start'."
fi
