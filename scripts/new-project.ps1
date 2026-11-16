#Requires -Version 5.1
<#
  new-project.ps1 - create a project from templates\project.
  Usage:
    powershell -File scripts\new-project.ps1 -Name my-app -Kind service
    powershell -File scripts\new-project.ps1 -Name my-site -Kind static -Remote https://github.com/user/my-site.git
#>
param(
  [Parameter(Mandatory = $true)][string]$Name,
  [ValidateSet('static', 'service')][string]$Kind = 'static',
  [string]$Remote = '',
  [string]$Root = ''
)

$ErrorActionPreference = 'Stop'
$agentRoot = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = Split-Path -Parent $agentRoot }
$target = Join-Path (Join-Path $Root 'projects') $Name
$tpl = Join-Path $agentRoot 'templates\project'

if ($Name -notmatch '^[a-z0-9][a-z0-9-]{1,40}$') { throw 'Name must be lowercase latin with dashes: my-app' }
if (Test-Path $target) { throw "already exists: $target" }
if (-not (Test-Path $tpl)) { throw "template missing: $tpl" }

New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item (Join-Path $tpl '*') $target -Recurse -Force

$dirs = @('scripts', 'tests', 'data', 'scripts\_scratch')
if ($Kind -eq 'static') { $dirs += @('site', 'prototype') }
else { $dirs += @('app', 'web', 'deploy', 'out', 'tests\fixtures') }
foreach ($d in $dirs) {
  $p = Join-Path $target $d
  if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
  $keep = Join-Path $p '.gitkeep'
  if (-not (Get-ChildItem $p -Force | Select-Object -First 1)) { Set-Content -Path $keep -Value '' -Encoding ASCII }
}

$date = (Get-Date).ToString('yyyy-MM-dd')
Get-ChildItem $target -Recurse -File | Where-Object { $_.Extension -in @('.md', '.txt', '.json', '.yml') } | ForEach-Object {
  $text = Get-Content $_.FullName -Raw -Encoding UTF8
  $text = $text.Replace('__NAME__', $Name).Replace('__KIND__', $Kind).Replace('__DATE__', $date)
  Set-Content -Path $_.FullName -Value $text -Encoding UTF8 -NoNewline
}

$git = (Get-Command git -ErrorAction SilentlyContinue)
if (-not $git) { $cand = 'C:\Program Files\Git\cmd\git.exe'; if (Test-Path $cand) { $git = $cand } }
if (-not $git) { throw 'git not found: install Git or add it to PATH' }

& $git -C $target init -b main | Out-Null
& $git -C $target add -A | Out-Null
& $git -C $target commit -m ("init: " + $Name + " (" + $Kind + " from template)") | Out-Null

if ($Remote) {
  & $git -C $target remote add origin $Remote
  Write-Host ('pushing to ' + $Remote)
  & $git -C $target push -u origin main
}

Write-Host ("created: " + $target) -ForegroundColor Green
Write-Host 'next: fill docs\HANDOFF.md, then work in the project' -ForegroundColor DarkGray
