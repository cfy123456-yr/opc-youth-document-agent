[CmdletBinding()]
param(
    [switch]$SkipPublicSamples
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Invoke-ProjectStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name 失败，退出码：$LASTEXITCODE"
    }
}

Write-Host "检查项目：$projectRoot"

Invoke-ProjectStep "Python 编译检查" {
    python -m compileall -q opc_agent tests
}

Invoke-ProjectStep "单元测试" {
    python -m unittest discover -s tests -v
}

Invoke-ProjectStep "离线评测" {
    python -m opc_agent eval --dataset evals/cases.jsonl
}

if (-not $SkipPublicSamples) {
    Invoke-ProjectStep "公开样本清单校验" {
        python -m opc_agent samples validate `
            --manifest samples/public/manifest.csv
    }

    Invoke-ProjectStep "公开样本回归评测" {
        python -m opc_agent samples eval `
            --manifest samples/public/manifest.csv `
            --reports-dir reports/public
    }
}

Invoke-ProjectStep "Git 空白字符检查" {
    git diff --check
}

$ruffVersion = python -m ruff --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Invoke-ProjectStep "Ruff 静态检查" {
        python -m ruff check opc_agent tests
    }
}
else {
    Write-Warning "未安装 Ruff，已跳过静态检查。安装开发依赖后会自动启用。"
}

Write-Host "`n项目质量检查通过。" -ForegroundColor Green
