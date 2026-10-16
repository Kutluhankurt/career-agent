# Removes Career Agent. Your data in %USERPROFILE%\.career-agent is kept unless you pass -Purge.
param([switch]$Purge)
if (Get-Command career -ErrorAction SilentlyContinue) {
    career stop
    career autostart off
}
uv tool uninstall career-agent
$home_dir = if ($env:CAREER_AGENT_HOME) { $env:CAREER_AGENT_HOME } else { Join-Path $env:USERPROFILE ".career-agent" }
if ($Purge) { Remove-Item -Recurse -Force $home_dir -ErrorAction SilentlyContinue; Write-Host "Removed Career Agent and all its data." }
else { Write-Host "Removed Career Agent. Your data is still in $home_dir (use -Purge to delete it)." }
