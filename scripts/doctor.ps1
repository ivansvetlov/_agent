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
foreach ($mf in (Get-ChildItem (Join-Path $agentRoot 'agents') -Filter *.json | Sort-Object Name)) {
  $cfg = Get-Content $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  if (-not $cfg.enabled) { Write-Host ('  SKIP  ' + $cfg.id + ' (disabled)') -ForegroundColor DarkGray; continue }
  if (-not $cfg.skills_dir) { Write-Host ('  N/A   ' + $cfg.id + ' (skills_dir null)') -ForegroundColor DarkGray; continue }
  $skillsDir = $cfg.skills_dir
  if ($skillsDir.StartsWith('~')) { $skillsDir = Join-Path $env:USERPROFILE ($skillsDir.Substring(1).TrimStart('\', '/')) }
  if (-not (Test-Path $skillsDir)) { Warn ($cfg.id + ': skills dir missing -> ' + $skillsDir); return }
  $bound = 0; $broken = 0
  foreach ($s in $skills) {
    $link = Join-Path $skillsDir $s.Name
    if (-not (Test-Path $link)) { continue }
    $bound++
    if (-not (Test-Path (Join-Path $link 'SKILL.md'))) { $broken++ }
  }
  if ($broken -eq 0) { Pass ($cfg.id + ': ' + $bound + '/' + $skills.Count + ' skills bound, all resolve') }
  else { Fail ($cfg.id + ': ' + $broken + ' broken junctions') }
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
