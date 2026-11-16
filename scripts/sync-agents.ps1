#Requires -Version 5.1
<#
  sync-agents.ps1 - apply _agent canon (skills, subagents, commands) to every agent manifest.
  Reads _agent\agents\*.json. Idempotent, never deletes a real directory it does not own.

  -Mode copy      (default) copy skills into the agent skills dir, keep a .canon-hash marker.
  -Mode junction  legacy: Windows junctions from agent skills dir to skills-src.

  MCP is only reported unless -ApplyMcp is passed.
#>
param(
  [switch]$ApplyMcp,
  [ValidateSet('copy', 'junction')][string]$Mode = 'copy'
)

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

function Get-TreeHash([string]$dir) {
  $files = Get-ChildItem $dir -Recurse -File -Force | Sort-Object FullName
  $sb = New-Object System.Text.StringBuilder
  $root = (Resolve-Path $dir).Path.TrimEnd('\')
  foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length)
    $h = (Get-FileHash $f.FullName -Algorithm SHA256).Hash
    [void]$sb.Append($rel.ToLower()).Append('|').Append($h).Append("`n")
  }
  $bytes = [Text.Encoding]::UTF8.GetBytes($sb.ToString())
  $sha = [Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '') }
  finally { $sha.Dispose() }
}

function Is-Reparse([string]$p) {
  $item = Get-Item $p -Force
  return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Remove-Junction([string]$p, [string]$label) {
  cmd /c rmdir "`"$p`""
  if (Test-Path $p) { Write-Host ('  FAILED to remove junction: ' + $label) -ForegroundColor Red; return $false }
  Write-Host ('  UNLINK ' + $label) -ForegroundColor Green
  return $true
}

function Sync-SkillCopy([string]$src, [string]$dst, [string]$label) {
  $canon = Get-TreeHash $src
  $marker = Join-Path $dst '.canon-hash'
  if (Test-Path $dst) {
    if (Is-Reparse $dst) {
      if (-not (Remove-Junction $dst $label)) { return 'failed' }
    } elseif (-not (Test-Path $marker)) {
      Write-Host ('  SKIP foreign dir (no .canon-hash): ' + $label) -ForegroundColor Yellow
      return 'foreign'
    } else {
      $old = (Get-Content $marker -Raw).Trim()
      if ($old -eq $canon) { return 'same' }
      Remove-Item $dst -Recurse -Force
      Write-Host ('  UPDATE ' + $label) -ForegroundColor Green
    }
  }
  New-Item -ItemType Directory -Path $dst -Force | Out-Null
  Copy-Item (Join-Path $src '*') $dst -Recurse -Force
  Set-Content -Path $marker -Value $canon -Encoding ASCII
  if (-not (Test-Path $marker)) { return 'failed' }
  return 'copied'
}

function Link-Skill([string]$link, [string]$target, [string]$label) {
  if (-not (Test-Path (Join-Path $target 'SKILL.md'))) {
    Write-Host ('  MISSING SOURCE ' + $label) -ForegroundColor Red
    return $false
  }
  if (Test-Path $link) {
    if (Is-Reparse $link) { return $false }
    Write-Host ('  SKIP real dir, not junction: ' + $label) -ForegroundColor Yellow
    return $false
  }
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  return $true
}

if (-not (Test-Path $agentsDir)) { throw "no agents dir: $agentsDir" }
Write-Host ('mode: ' + $Mode) -ForegroundColor DarkGray

foreach ($mf in (Get-ChildItem $agentsDir -Filter *.json | Sort-Object Name)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  Write-Host ''
  Write-Host ('=== ' + $cfg.name + ' (' + $cfg.id + ')') -ForegroundColor Cyan
  if (-not $cfg.enabled) { Write-Host '  disabled, skip' -ForegroundColor DarkGray; continue }

  $skillsDir = Expand-Home $cfg.skills_dir
  $subDir = Expand-Home $cfg.subagents_dir
  $cmdDir = Expand-Home $cfg.commands_dir

  if ($skillsDir) {
    Ensure-Dir $skillsDir
    Write-Host ('  skills -> ' + $skillsDir)
    $counts = @{}
    foreach ($s in (Get-ChildItem $skillsSrc -Directory | Sort-Object Name)) {
      $dst = Join-Path $skillsDir $s.Name
      if ($Mode -eq 'junction') {
        $r = 'junction'
        if (Link-Skill -link $dst -target $s.FullName -label $s.Name) { Write-Host ('  LINK ' + $s.Name) -ForegroundColor Green }
      } else {
        $r = Sync-SkillCopy -src $s.FullName -dst $dst -label $s.Name
      }
      $counts[$r] = 1 + ($counts[$r] -as [int])
    }
    ($counts.GetEnumerator() | Sort-Object Name | ForEach-Object { $_.Name + '=' + $_.Value }) -join ' '
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
        if ($old -eq $new) { $need = $false } else { Copy-Item $dst ($dst + '.bak') -Force }
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
$enabled = [ordered]@{}
foreach ($p in $registry.servers.PSObject.Properties) {
  if (-not $p.Value.enabled) { continue }
  $entry = [ordered]@{ type = $p.Value.type }
  if ($p.Value.command) { $entry.command = $p.Value.command }
  if ($p.Value.args) { $entry.args = @($p.Value.args) }
  if ($p.Value.url) { $entry.url = $p.Value.url }
  if ($p.Value.env) { $entry.environment = $p.Value.env }
  $enabled[$p.Name] = $entry
}
Write-Host ('  enabled servers: ' + (($enabled.Keys) -join ', '))

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
