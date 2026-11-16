#Requires -Version 5.1
<#
  sync-agents.ps1 - apply _agent canon (skills, subagents, commands) to every agent manifest.
  Reads _agent\agents\*.json. Idempotent, never deletes a real directory.
  MCP is only reported unless -ApplyMcp is passed.
#>
param([switch]$ApplyMcp)

$ErrorActionPreference = 'Stop'
$agentRoot = Split-Path -Parent $PSScriptRoot
$agentsDir = Join-Path $agentRoot 'agents'
$skillsSrc = Join-Path $agentRoot 'skills-src'
$subagentsSrc = Join-Path $agentRoot 'subagents-src'
$commandsRoot = Join-Path $agentRoot 'commands'
$mcpFile = Join-Path $agentRoot 'mcp\mcp-servers.json'

function Expand-Home([string]$p) {
  if (-not $p) { return $null }
  if ($p.StartsWith('~')) {
    $rest = $p.Substring(1).TrimStart('\', '/')
    return (Join-Path $env:USERPROFILE $rest)
  }
  return $p
}

function Ensure-Dir([string]$p) {
  if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

function Link-Skill([string]$link, [string]$target, [string]$label) {
  if (-not (Test-Path (Join-Path $target 'SKILL.md'))) {
    Write-Host ("  MISSING SOURCE " + $label) -ForegroundColor Red
    return $false
  }
  if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    Write-Host ("  SKIP real dir, not junction: " + $label) -ForegroundColor Yellow
    return $false
  }
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Write-Host ("  LINK " + $label) -ForegroundColor Green
  return $true
}

if (-not (Test-Path $agentsDir)) { throw "no agents dir: $agentsDir" }

foreach ($mf in (Get-ChildItem $agentsDir -Filter *.json | Sort-Object Name)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  Write-Host ''
  Write-Host ("=== " + $cfg.name + " (" + $cfg.id + ")") -ForegroundColor Cyan
  if (-not $cfg.enabled) { Write-Host '  disabled, skip' -ForegroundColor DarkGray; continue }

  $skillsDir = Expand-Home $cfg.skills_dir
  $subDir = Expand-Home $cfg.subagents_dir
  $cmdDir = Expand-Home $cfg.commands_dir

  if ($skillsDir) {
    Ensure-Dir $skillsDir
    Write-Host ('  skills -> ' + $skillsDir)
    $n = 0
    foreach ($s in (Get-ChildItem $skillsSrc -Directory | Sort-Object Name)) {
      if (Link-Skill -link (Join-Path $skillsDir $s.Name) -target $s.FullName -label $s.Name) { $n++ }
    }
    if ($n -eq 0) { Write-Host '  skills already bound' -ForegroundColor DarkGray }
  } else {
    Write-Host '  skills_dir: null (agent installs skills itself)' -ForegroundColor Yellow
  }

  if ($subDir) {
    Ensure-Dir $subDir
    Write-Host ('  subagents -> ' + $subDir)
    foreach ($a in (Get-ChildItem $subagentsSrc -Directory | Sort-Object Name)) {
      $src = Join-Path $a.FullName 'agent.md'
      if (-not (Test-Path $src)) { continue }
      $dst = Join-Path $subDir ($a.Name + '.md')
      $need = $true
      if (Test-Path $dst) {
        $old = Get-Content $dst -Raw -Encoding UTF8
        $new = Get-Content $src -Raw -Encoding UTF8
        if ($old -eq $new) { $need = $false }
        else { Copy-Item $dst ($dst + '.bak') -Force }
      }
      if ($need) {
        Copy-Item $src $dst -Force
        Write-Host ('  COPY ' + $a.Name + '.md') -ForegroundColor Green
      }
    }
  }

  if ($cmdDir -and (Test-Path (Join-Path $commandsRoot $cfg.id))) {
    Ensure-Dir $cmdDir
    Write-Host ('  commands -> ' + $cmdDir)
    foreach ($c in (Get-ChildItem (Join-Path $commandsRoot $cfg.id) -Recurse -File -Filter *.md)) {
      Copy-Item $c.FullName (Join-Path $cmdDir $c.Name) -Force
      Write-Host ('  COPY command ' + $c.Name) -ForegroundColor Green
    }
  }
}

# --- MCP: report by default, apply with -ApplyMcp
Write-Host ''
Write-Host '=== MCP' -ForegroundColor Cyan
if (-not (Test-Path $mcpFile)) { Write-Host '  registry missing, skip'; exit 0 }
$registry = Get-Content $mcpFile -Raw -Encoding UTF8 | ConvertFrom-Json
$enabled = @{}
foreach ($p in $registry.servers.PSObject.Properties) {
  if ($p.Value.enabled) {
    $enabled[$p.Name] = [ordered]@{ type = $p.Value.type }
    if ($p.Value.command) { $enabled[$p.Name].command = $p.Value.command }
    if ($p.Value.args) { $enabled[$p.Name].args = $p.Value.args }
    if ($p.Value.url) { $enabled[$p.Name].url = $p.Value.url }
    if ($p.Value.env) { $enabled[$p.Name].environment = $p.Value.env }
  }
}
$names = ($enabled.Keys | Sort-Object) -join ', '
Write-Host ('  enabled servers: ' + $names)

if (-not $ApplyMcp) {
  Write-Host '  (dry run: pass -ApplyMcp to write into agent configs)' -ForegroundColor DarkGray
  exit 0
}

foreach ($mf in (Get-ChildItem $agentsDir -Filter *.json)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if (-not $cfg.enabled) { continue }
  if ($cfg.mcp_format -ne 'opencode') {
    Write-Host ('  ' + $cfg.id + ': mcp_format ' + $cfg.mcp_format + ' not implemented, skip') -ForegroundColor Yellow
    continue
  }
  $path = Expand-Home $cfg.mcp_config
  if (-not (Test-Path $path)) { Write-Host ('  ' + $cfg.id + ': config not found, skip') -ForegroundColor Yellow; continue }
  Copy-Item $path ($path + '.bak') -Force
  $json = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
  $json | Add-Member -NotePropertyName mcp -NotePropertyValue $enabled -Force
  $json | ConvertTo-Json -Depth 20 | Set-Content $path -Encoding UTF8
  Write-Host ('  WRITE ' + $path + ' (backup: .bak)') -ForegroundColor Green
}
