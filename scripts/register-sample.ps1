[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$SampleId,

    [Parameter(Mandatory)]
    [ValidateSet('auto', 'resume', 'letter', 'contract', 'receipt')]
    [string]$Task,

    [Parameter(Mandatory)]
    [ValidateSet('resume', 'letter', 'contract', 'receipt')]
    [string]$ExpectedTask,

    [Parameter(Mandatory)]
    [string]$SourcePath,

    [string]$GoalPath,
    [string[]]$RequiredTerms = @(),
    [string[]]$ForbiddenTerms = @(),
    [string[]]$ExpectedFindingTitles = @(),
    [int]$MinFindings = 0,
    [ValidateSet('real', 'public', 'synthetic')]
    [string]$EvidenceType = 'real',
    [string]$Notes = "",
    [switch]$ConsentConfirmed,
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'

if (-not $ConsentConfirmed) {
    throw '请先确认样本可以合法用于测试，再添加 -ConsentConfirmed。'
}

$root = if ($ProjectRoot) {
    (Resolve-Path -LiteralPath $ProjectRoot).Path
} else {
    (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
}
$manifestPath = Join-Path $root 'samples\manifest.local.csv'
$privateDir = Join-Path $root 'samples\private'
$baselineDir = Join-Path $privateDir 'baselines'

$manifestDir = Split-Path -Parent $manifestPath
New-Item -ItemType Directory -Force -Path $manifestDir | Out-Null
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Set-Content -LiteralPath $manifestPath `
        -Value 'sample_id,task,path,expected_task,goal_path,baseline_path,evidence_type,consent_confirmed,notes' `
        -Encoding utf8
}
if (Get-ChildItem -LiteralPath $privateDir -Filter "$SampleId.*" -ErrorAction SilentlyContinue) {
    throw "样本编号已存在：$SampleId"
}

$manifestText = Get-Content -LiteralPath $manifestPath -Raw
if ($manifestText -match "(?m)^$([regex]::Escape($SampleId)),") {
    throw "样本编号已登记：$SampleId"
}

$source = (Resolve-Path -LiteralPath $SourcePath).Path
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "样本文件不存在：$SourcePath"
}

New-Item -ItemType Directory -Force -Path $privateDir, $baselineDir | Out-Null

$sampleExtension = [System.IO.Path]::GetExtension($source)
if (-not $sampleExtension) {
    $sampleExtension = '.txt'
}
$sampleRelative = "samples/private/$SampleId$sampleExtension"
$sampleTarget = Join-Path $privateDir "$SampleId$sampleExtension"
Copy-Item -LiteralPath $source -Destination $sampleTarget

$goalRelative = ''
if ($GoalPath) {
    $goalSource = (Resolve-Path -LiteralPath $GoalPath).Path
    if (-not (Test-Path -LiteralPath $goalSource -PathType Leaf)) {
        throw "目标文件不存在：$GoalPath"
    }
    $goalExtension = [System.IO.Path]::GetExtension($goalSource)
    if (-not $goalExtension) {
        $goalExtension = '.txt'
    }
    $goalRelative = "samples/private/$SampleId-goal$goalExtension"
    Copy-Item -LiteralPath $goalSource -Destination (Join-Path $privateDir "$SampleId-goal$goalExtension")
}

$baselineRelative = "samples/private/baselines/$SampleId.json"
$baseline = [ordered]@{
    sample_id = $SampleId
    task = $ExpectedTask
    goal = ''
    required_terms = @($RequiredTerms)
    forbidden_terms = @($ForbiddenTerms)
    expected_finding_titles = @($ExpectedFindingTitles)
    min_findings = $MinFindings
    human_notes = $Notes
}
$baseline |
    ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $baselineDir "$SampleId.json") -Encoding utf8

function ConvertTo-CsvField {
    param([string]$Value)

    $text = [string]$Value
    if ($text.IndexOfAny([char[]]",`r`n") -ge 0) {
        return '"' + $text.Replace('"', '""') + '"'
    }
    return $text
}

$fields = @(
    $SampleId,
    $Task,
    $sampleRelative,
    $ExpectedTask,
    $goalRelative,
    $baselineRelative,
    $EvidenceType,
    'yes',
    $Notes
)
$row = ($fields | ForEach-Object { ConvertTo-CsvField $_ }) -join ','
Add-Content -LiteralPath $manifestPath -Value $row -Encoding utf8

Write-Host "已登记样本：$SampleId"
Write-Host "样本文件：$sampleRelative"
Write-Host "人工基线：$baselineRelative"
Write-Host ''
Write-Host '下一步运行：'
Write-Host 'python -m opc_agent samples validate'
Write-Host 'python -m opc_agent samples eval'
