[CmdletBinding()]
param(
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$root = if ($ProjectRoot) {
    (Resolve-Path -LiteralPath $ProjectRoot).Path
} else {
    (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
}

Set-Location -LiteralPath $root

python -m opc_agent samples validate
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python -m opc_agent samples eval
exit $LASTEXITCODE
