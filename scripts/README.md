# PowerShell 辅助脚本

## 项目质量检查

```powershell
pwsh -NoProfile -File .\scripts\Test-Project.ps1
```

脚本会依次运行编译检查、单元测试、离线评测、公开样本校验和回归评测，并检查
Git 空白字符。安装 Ruff 后会自动追加静态检查；未安装时只给出提示，不影响其余
质量门。

## 登记真实样本

```powershell
.\scripts\register-sample.ps1 `
  -SampleId resume-001 `
  -Task resume `
  -ExpectedTask resume `
  -SourcePath 'D:\脱敏样本\resume-001.docx' `
  -GoalPath 'D:\脱敏样本\resume-001-goal.txt' `
  -RequiredTerms match_score `
  -ForbiddenTerms '未提供的证书' `
  -ExpectedFindingTitles '缺少量化结果' `
  -MinFindings 1 `
  -EvidenceType real `
  -Notes '真实简历脱敏样本' `
  -ConsentConfirmed
```

`Task` 可填写 `auto` 或具体任务。`ExpectedTask` 只能填写
`resume`、`letter`、`contract` 或 `receipt`。`EvidenceType` 可填写
`real`、`public` 或 `synthetic`，默认 `real`；只有 `real` 计入决策门 C。

只有确认样本可以合法用于测试后才能添加 `-ConsentConfirmed`。

## 运行样本验收

```powershell
.\scripts\run-samples.ps1
```

脚本会自动进入项目目录，先校验样本清单，再运行真实样本评测。

## 部署前检查

```powershell
.\scripts\Test-Deployment.ps1
```

脚本会运行单元测试、离线评测、公开回归、敏感路径忽略检查、Docker Compose
配置检查和镜像构建检查。本机未安装 Docker 时会跳过容器相关检查。

## 启停公网演示

启动强制 `mock` 模式的本地服务：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Demo.ps1
```

启动默认 `srv.us` 后台 HTTPS 隧道：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1
```

停止隧道并删除记录的临时地址：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1 -Stop
```

隧道 PID、临时 HTTPS 地址和运行日志写入 `work/public-demo/`。公网演示仍只允许
公开示例或合成样本，不得上传真实用户文档。
