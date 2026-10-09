[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "检查项目：$projectRoot"

if (-not $SkipTests) {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "单元测试失败。"
    }

    python -m opc_agent eval --dataset evals/cases.jsonl
    if ($LASTEXITCODE -ne 0) {
        throw "离线评测失败。"
    }

    python -m opc_agent samples validate `
        --manifest samples/public/manifest.csv
    if ($LASTEXITCODE -ne 0) {
        throw "公开样本清单校验失败。"
    }

    python -m opc_agent samples eval `
        --manifest samples/public/manifest.csv `
        --reports-dir reports/public
    if ($LASTEXITCODE -ne 0) {
        throw "公开样本评测失败。"
    }
}

$requiredIgnored = @(
    ".env",
    "samples/manifest.local.csv",
    "reports/real-sample-report.json"
)
foreach ($path in $requiredIgnored) {
    git check-ignore -q -- $path
    if ($LASTEXITCODE -ne 0) {
        throw "敏感路径未被 Git 忽略：$path"
    }
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Docker 已安装但守护进程未运行，已跳过 Compose 和镜像构建检查。"
    }
    else {
        docker compose config --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose 配置检查失败。"
        }
        docker compose build --check
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose 镜像构建检查失败。"
        }
        Write-Host "Docker Compose 配置和镜像构建检查通过。"
    }
}
else {
    Write-Warning "未检测到 Docker，已跳过 Compose 配置和镜像构建检查。"
}

git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "Git 空白字符检查失败。"
}

Write-Host "部署前检查完成。"
