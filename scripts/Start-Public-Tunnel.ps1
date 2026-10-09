[CmdletBinding()]
param(
    [int]$Port = 8765,
    [ValidateSet("srv.us", "localhost.run", "serveo.net")]
    [string]$Provider = "srv.us",
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "work\public-demo"
$pidFile = Join-Path $logDir "tunnel.pid"
$urlFile = Join-Path $logDir "tunnel.url"
$outLog = Join-Path $logDir "tunnel.out.log"
$errLog = Join-Path $logDir "tunnel.err.log"
$srvKeyFile = Join-Path $logDir "srv-us-ed25519"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Get-TrackedTunnelProcess {
    if (-not (Test-Path -LiteralPath $pidFile)) {
        return $null
    }

    $trackedPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $trackedPid) {
        return $null
    }

    $process = Get-Process -Id ([int]$trackedPid) -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq "ssh") {
        return $process
    }

    return $null
}

function Get-TunnelUrls {
    param([string]$Text)

    if (-not $Text) {
        return @()
    }

    return @(
        [regex]::Matches(
            $Text,
            "https://[a-z0-9.-]+(?:lhr\.life|localhost\.run|serveo\.net|serveousercontent\.com|srv\.us)",
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
        ) |
            ForEach-Object { $_.Value.TrimEnd(".") } |
            Select-Object -Unique
    )
}

function Stop-TrackedTunnel {
    $process = Get-TrackedTunnelProcess
    if ($process) {
        Stop-Process -Id $process.Id
        $process.WaitForExit(5000) | Out-Null
        Write-Host "已停止公网隧道：PID $($process.Id)。"
    }
    else {
        Write-Host "没有由本项目脚本启动的公网隧道。"
    }

    Remove-Item -LiteralPath $pidFile, $urlFile -Force -ErrorAction SilentlyContinue
}

if ($Stop) {
    Stop-TrackedTunnel
    exit 0
}

$tracked = Get-TrackedTunnelProcess
if ($tracked) {
    $url = if (Test-Path -LiteralPath $urlFile) {
        (Get-Content -LiteralPath $urlFile | Select-Object -First 1).Trim()
    }
    else {
        ""
    }

    if ($url) {
        try {
            $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 10
            if ($health.ok -eq $true -and $health.public_demo -eq $true) {
                Write-Host "公网隧道已在运行：PID $($tracked.Id)，$url"
                $health | ConvertTo-Json -Depth 4
                exit 0
            }
        }
        catch {
            # Fall through to restart the stale tunnel.
        }
    }

    $logText = @(
        Get-Content -LiteralPath $outLog -Raw -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $errLog -Raw -ErrorAction SilentlyContinue
    ) -join "`n"
    $urls = @(Get-TunnelUrls $logText)
    [array]::Reverse($urls)
    foreach ($candidate in $urls) {
        try {
            $health = Invoke-RestMethod -Uri "$candidate/api/health" -TimeoutSec 10
            if ($health.ok -eq $true -and $health.public_demo -eq $true) {
                Set-Content -LiteralPath $urlFile -Value $candidate
                Write-Host "公网隧道已在运行：PID $($tracked.Id)，$candidate"
                $health | ConvertTo-Json -Depth 4
                exit 0
            }
        }
        catch {
            # Try the next tunnel address observed in the log.
        }
    }

    Write-Host "已记录的隧道地址不可用，准备重启隧道。"
    Stop-TrackedTunnel
}

$localHealthUrl = "http://127.0.0.1:${Port}/api/health"
try {
    Invoke-RestMethod -Uri $localHealthUrl -TimeoutSec 5 | Out-Null
}
catch {
    throw "本地服务不可用，请先运行 scripts\Start-Public-Demo.ps1。"
}

$ssh = (Get-Command ssh -ErrorAction Stop).Source
$arguments = @(
    "-T",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "ExitOnForwardFailure=yes"
)

switch ($Provider) {
    "srv.us" {
        if (-not (Test-Path -LiteralPath $srvKeyFile)) {
            $keygen = (Get-Command ssh-keygen -ErrorAction Stop).Source
            & $keygen -q -t ed25519 -N "" -C "opc-public-demo" -f $srvKeyFile
            if ($LASTEXITCODE -ne 0) {
                throw "无法为 srv.us 生成临时 SSH 密钥。"
            }
        }

        $arguments += @(
            "-i", $srvKeyFile,
            "-o", "IdentitiesOnly=yes",
            "-R", "1:127.0.0.1:$Port",
            "srv.us"
        )
    }
    "localhost.run" {
        $arguments += @("-R", "80:127.0.0.1:$Port", "nokey@localhost.run")
    }
    "serveo.net" {
        $arguments += @("-R", "80:127.0.0.1:$Port", "serveo.net")
    }
}

Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue
$process = Start-Process `
    -FilePath $ssh `
    -ArgumentList $arguments `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru

$url = $null
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($process.HasExited) {
        break
    }

    $text = @(
        Get-Content -LiteralPath $outLog -Raw -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $errLog -Raw -ErrorAction SilentlyContinue
    ) -join "`n"
    $urls = @(Get-TunnelUrls $text)
    if ($urls.Count -gt 0) {
        $url = $urls[-1]
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $url) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id
    }
    $errorText = Get-Content -LiteralPath $errLog -Raw -ErrorAction SilentlyContinue
    throw "未能从隧道输出中解析 HTTPS 地址。`n$errorText"
}

$health = $null
for ($attempt = 0; $attempt -lt 80; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 10
        if ($health.ok -eq $true -and $health.public_demo -eq $true) {
            break
        }
        $health = $null
    }
    catch {
        $health = $null
    }
    Start-Sleep -Milliseconds 750
}

if (-not $health) {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
    throw "隧道已启动，但公网健康检查失败：$url"
}

Set-Content -LiteralPath $pidFile -Value $process.Id
Set-Content -LiteralPath $urlFile -Value $url
Write-Host "公网隧道已启动：PID $($process.Id)，$url"
$health | ConvertTo-Json -Depth 4
