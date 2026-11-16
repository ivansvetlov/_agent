#Requires -Version 5.1
<#
  doctor.ps1 - health check of the workspace. Read-only.
  Checks: projects are git repos with remote, docs/HANDOFF.md present,
  skill junctions of every enabled agent resolve, canon dirs non-empty.
  Exit code 1 if any FAIL.
#>
$ErrorActionPreference = 'Continue'
$agentRoot = Split-Path -Parent $PSScriptRoot
$ws = Split-Path -Parent $agentRoot
$fail = 0
$warn = 0

function Pass([string]$m) { Write-Host ('  PASS  ' + $m) -ForegroundColor Green }
function Fail([string]$m) { Write-Host ('  FAIL  ' + $m) -ForegroundColor Red; $script:fail++ }
function Warn([string]$m) { Write-Host ('  WARN  ' + $m) -ForegroundColor Yellow; $script:warn++ }

Write-Host '=== WORKSPACE DOCTOR ===' -ForegroundColor DarkGray
Write-Host ''
Write-Host '[1] root' -ForegroundColor Cyan
if (Test-Path (Join-Path $ws 'AGENTS.md')) { Pass 'workspace AGENTS.md' } else { Fail 'workspace AGENTS.md missing' }
if (Test-Path (Join-Path $ws 'projects')) { Pass 'projects dir' } else { Fail 'projects dir missing' }

Write-Host ''
Write-Host '[2] projects' -ForegroundColor Cyan
Get-ChildItem (Join-Path $ws 'projects') -Directory -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
  $p = $_.FullName
  $gitDir = Join-Path $p '.git'
  if (-not (Test-Path $gitDir)) { Fail ($_.Name + ': not a git repo'); return }
  $cfgPath = Join-Path $gitDir 'config'
  $cfgText = ''
  if (Test-Path $cfgPath) { $cfgText = Get-Content $cfgPath -Raw -ErrorAction SilentlyContinue }
  if ($cfgText -match '\[remote "origin"\]') { Pass ($_.Name + ': remote origin') }
  else { Fail ($_.Name + ': no remote origin (not protected against disk loss)') }
  if ((Test-Path (Join-Path $p 'docs\HANDOFF.md')) -or (Test-Path (Join-Path $p 'docs\AGENT_HANDOFF.md'))) {
    Pass ($_.Name + ': handoff doc')
  } else { Warn ($_.Name + ': no docs/HANDOFF.md') }
}

Write-Host ''
Write-Host '[3] canon' -ForegroundColor Cyan
$skills = Get-ChildItem (Join-Path $agentRoot 'skills-src') -Directory -ErrorAction SilentlyContinue
if ($skills) { Pass ('skills-src: ' + $skills.Count + ' skills') } else { Fail 'skills-src empty' }
$subs = Get-ChildItem (Join-Path $agentRoot 'subagents-src') -Directory -ErrorAction SilentlyContinue
if ($subs) { Pass ('subagents-src: ' + $subs.Count + ' subagents') } else { Warn 'subagents-src empty' }
foreach ($s in $skills) {
  if (-not (Test-Path (Join-Path $s.FullName 'SKILL.md'))) { Fail ('skill without SKILL.md: ' + $s.Name) }
}

Write-Host ''
Write-Host '[4] agent bindings' -ForegroundColor Cyan
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
foreach ($mf in (Get-ChildItem (Join-Path $agentRoot 'agents') -Filter *.json | Sort-Object Name)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if (-not $cfg.enabled) { Write-Host ('  SKIP  ' + $cfg.id + ' (disabled)') -ForegroundColor DarkGray; continue }
  if (-not $cfg.skills_dir) { Write-Host ('  N/A   ' + $cfg.id + ' (skills_dir null)') -ForegroundColor DarkGray; continue }
  $skillsDir = $cfg.skills_dir
  if ($skillsDir.StartsWith('~')) { $skillsDir = Join-Path $env:USERPROFILE ($skillsDir.Substring(1).TrimStart('\', '/')) }
  if (-not (Test-Path $skillsDir)) { Warn ($cfg.id + ': skills dir missing -> ' + $skillsDir); return }
  $copied = 0; $linked = 0; $drift = 0; $missing = 0; $foreign = 0
  foreach ($s in $skills) {
    $dst = Join-Path $skillsDir $s.Name
    if (-not (Test-Path $dst)) { $missing++; continue }
    $item = Get-Item $dst -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $linked++; continue }
    $marker = Join-Path $dst '.canon-hash'
    if (-not (Test-Path $marker)) { $foreign++; continue }
    if ((Get-Content $marker -Raw).Trim() -eq (Get-TreeHash $s.FullName)) { $copied++ } else { $drift++ }
  }
  $parts = @()
  if ($copied) { $parts += ($copied -as [string]) + ' copies in sync' }
  if ($linked) { $parts += ($linked -as [string]) + ' junctions' }
  if ($drift) { $parts += ($drift -as [string]) + ' DRIFT' }
  if ($missing) { $parts += ($missing -as [string]) + ' not bound' }
  if ($foreign) { $parts += ($foreign -as [string]) + ' foreign dirs' }
  $msg = $cfg.id + ': ' + ($parts -join ', ')
  if ($drift -gt 0 -or $missing -gt 0) { Fail $msg }
  elseif ($linked -gt 0 -or $foreign -gt 0) { Warn $msg }
  else { Pass $msg }
}

Write-Host ''
Write-Host '[5] notes' -ForegroundColor Cyan
foreach ($f in @('docs\state-of-workspace.md', 'docs\ADR-006-agents.md')) {
  if (Test-Path (Join-Path $agentRoot $f)) { Pass $f } else { Warn ('missing ' + $f) }
}

Write-Host ''
if ($fail -eq 0) { Write-Host ('=== OK (' + $warn + ' warnings) ===') -ForegroundColor Green; exit 0 }
Write-Host ('=== ' + $fail + ' FAIL, ' + $warn + ' WARN ===') -ForegroundColor Red
exit 1
