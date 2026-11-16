#Requires -Version 5.1
<#
  mcp-sync.ps1 - push mcp-servers.json into agent configs (opencode format only for now).
  Without -Apply prints the diff and writes nothing.
#>
param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$agentRoot = Split-Path -Parent $PSScriptRoot
$registryPath = Join-Path $agentRoot 'mcp\mcp-servers.json'
$agentsDir = Join-Path $agentRoot 'agents'

if (-not (Test-Path $registryPath)) { throw "registry missing: $registryPath" }
$registry = Get-Content $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json

$enabled = [ordered]@{}
foreach ($p in $registry.servers.PSObject.Properties) {
  $s = $p.Value
  if (-not $s.enabled) { continue }
  $entry = [ordered]@{ type = $s.type }
  if ($s.command) { $entry.command = $s.command }
  if ($s.args) { $entry.args = @($s.args) }
  if ($s.url) { $entry.url = $s.url }
  if ($s.env) { $entry.environment = $s.env }
  $enabled[$p.Name] = $entry
}

Write-Host '=== MCP SYNC ===' -ForegroundColor DarkGray
Write-Host ('enabled: ' + (($enabled.Keys) -join ', '))

foreach ($mf in (Get-ChildItem $agentsDir -Filter *.json | Sort-Object Name)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if (-not $cfg.enabled) { continue }
  Write-Host ''
  Write-Host ('--- ' + $cfg.id + ' (' + $cfg.mcp_format + ')')
  if ($cfg.mcp_format -ne 'opencode') { Write-Host '  format not implemented, skip' -ForegroundColor Yellow; continue }

  $path = $cfg.mcp_config
  if ($path.StartsWith('~')) { $path = Join-Path $env:USERPROFILE ($path.Substring(1).TrimStart('\', '/')) }
  if (-not (Test-Path $path)) { Write-Host ('  config not found: ' + $path) -ForegroundColor Yellow; continue }

  $json = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
  $current = @()
  if ($json.PSObject.Properties.Name -contains 'mcp') { $current = @($json.mcp.PSObject.Properties.Name) }
  Write-Host ('  now:  ' + (($current | Sort-Object) -join ', '))
  Write-Host ('  want: ' + (($enabled.Keys | Sort-Object) -join ', '))

  if (-not $Apply) { Write-Host '  dry run (use -Apply to write)' -ForegroundColor DarkGray; continue }

  Copy-Item $path ($path + '.bak') -Force
  $json | Add-Member -NotePropertyName mcp -NotePropertyValue $enabled -Force
  $json | ConvertTo-Json -Depth 20 | Set-Content $path -Encoding UTF8
  Write-Host ('  WRITE ' + $path + ' (backup .bak)') -ForegroundColor Green
}
