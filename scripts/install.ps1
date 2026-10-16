# Career Agent installer for Windows (PowerShell, no administrator rights needed).
#
#   From a checkout:   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#   From a source:     $env:CAREER_AGENT_SOURCE = "git+https://.../career-agent.git"; .\install.ps1
#   With an AI SDK:    $env:CAREER_AGENT_EXTRAS = "claude"   (claude | openai | gemini | all-ai)
$ErrorActionPreference = "Stop"

$arch = if ([Environment]::Is64BitOperatingSystem) { if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" } } else { "x86" }
Write-Host "Installing Career Agent for Windows ($arch)..."

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv (Python package manager) not found; installing it for this user."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

$repo = Split-Path -Parent $PSScriptRoot
if ($env:CAREER_AGENT_SOURCE) { $source = $env:CAREER_AGENT_SOURCE }
elseif (Test-Path (Join-Path $repo "pyproject.toml")) { $source = $repo }
else { throw "Set CAREER_AGENT_SOURCE to a git URL, wheel or folder to install from." }

if ($env:CAREER_AGENT_EXTRAS) {
    if ($source -like "git+*") { $spec = "career-agent[$($env:CAREER_AGENT_EXTRAS)] @ $source" }
    else { $spec = "$source[$($env:CAREER_AGENT_EXTRAS)]" }
} else { $spec = $source }

uv tool install --python 3.12 --force "$spec"
if (-not (Get-Command career -ErrorAction SilentlyContinue)) { $env:Path = "$(uv tool dir --bin);$env:Path" }
career version
Write-Host "Data folder: $(if ($env:CAREER_AGENT_HOME) { $env:CAREER_AGENT_HOME } else { "$env:USERPROFILE\.career-agent" })"
career setup
