#Requires -Version 5.1
<#
  bootstrap.ps1 - repair and re-bind the agent workspace.
  Order: sync agents (skills, subagents, commands) -> MCP report -> doctor.
  Idempotent. Nothing is deleted; existing real directories are left untouched.
#>
$ErrorActionPreference = 'Continue'
$agentRoot = Split-Path -Parent $PSScriptRoot

Write-Host ''
Write-Host '=== WORKSPACE BOOTSTRAP ===' -ForegroundColor DarkGray

Write-Host ''
Write-Host '[1] sync agents' -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'sync-agents.ps1')

Write-Host ''
Write-Host '[2] mcp status' -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'mcp-sync.ps1')

Write-Host ''
Write-Host '[3] doctor' -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'doctor.ps1')

Write-Host ''
Write-Host '=== DONE ===' -ForegroundColor DarkGray
