[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$BindAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "work\public-demo"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$healthUrl = "http://${BindAddress}:${Port}/api/health"
try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.ok -eq $true -and $health.public_demo -eq $true) {
        Write-Host "公网演示服务已在运行：PID 状态未知，端口 $Port。"
        $health | ConvertTo-Json -Depth 4
        exit 0
    }

    throw "端口 $Port 已被非公开演示实例占用，请先停止该实例或改用其他端口。"
}
catch {
    if ($_.Exception.Message -like "端口 * 已被非公开演示实例占用*") {
        throw
    }
    # No healthy public-demo instance is running on the requested port.
}

$env:OPC_PUBLIC_DEMO = "true"
$env:OPC_OUTPUT_TTL_SECONDS = "3600"
$env:OPC_MAX_RUNS_PER_WINDOW = "12"
$env:OPC_MAX_CONCURRENT_RUNS = "2"
$env:OPC_MAX_UPLOAD_MB = "15"

$python = (Get-Command python -ErrorAction Stop).Source
$process = Start-Process `
    -FilePath $python `
    -ArgumentList @(
        "-m",
        "opc_agent.web",
        "--host",
        $BindAddress,
        "--port",
        "$Port"
    ) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "app.out.log") `
    -RedirectStandardError (Join-Path $logDir "app.err.log") `
    -PassThru

$health = $null
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        break
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $health) {
    Get-Content -LiteralPath (Join-Path $logDir "app.err.log") -Tail 40
    throw "公网演示服务启动失败。"
}

Set-Content -LiteralPath (Join-Path $logDir "app.pid") -Value $process.Id
Write-Host "公网演示服务已启动：PID $($process.Id)，端口 $Port。"
$health | ConvertTo-Json -Depth 4
