# 青年文书智能助手

一个本地优先、任务驱动的文书 Agent，覆盖青年在求职、签约和在岗阶段的四类任务：

- 简历优化
- 申请书函润色
- 合同风险审阅
- 票据和报销整理

项目默认使用本地规则运行，不需要 API Key。配置模型 Provider 后，可以在本地规则之上增加语义分析和改写能力。

## 当前状态

- 四条本地工作流和任务路由已经实现。
- 本地 Web 工作台已经实现，可粘贴文本或上传文件并下载结果。
- 42 项单元测试通过。
- 12/12 条离线路由与关键词评测通过。
- 已建立 20 份公开许可与合成回归集，四类各 5 份；当前自动回归 20/20 通过。
- 已建立真实样本清单、人工基线模板和批量评测入口。
- 样本评测支持 `real`、`public`、`synthetic` 三种证据类型，只有 `real` 计入决策门 C。
- 样本评测会单列自动路由验证覆盖率；只有 `task=auto` 才计入路由通过率。
- 图片版 DOCX 会抽取内嵌图片并尝试 OCR；OCR 不可用时明确提示，不再按空文档继续分析。
- Docker Compose 已在本机完成镜像构建、容器启动和健康检查；云服务器尚未实跑。
- 新增公网演示模式：强制本地规则、按 IP 限流、限制并发、签名下载链接和结果自动清理。
- 默认 `mock` Provider 已验证，OpenAI 在线调用尚未真实验证。
- 合同和票据结果必须人工复核，不能直接作为法律或财务结论。
- 当前没有登录、云端存储、自动提交和正式法律意见能力。

当前项目阶段是“真实样本验收”。正式真实用户样本仍为 0/20，决策门 C 未通过；
公开和合成样本只用于技术回归，不能替代真实用户文档。下一批必须完成的工作见
`docs/real-sample-acceptance.md`。

## 为什么先做 Agent

当前市场上已经存在大量单点工具，但没有一个项目围绕中国青年的完整文书周期，把事实约束、隐私、文件解析、人工确认和结果导出串成统一流程。

因此第一版采用：

- 一个任务路由
- 四个独立工作流
- 统一的文件、结果和评测模型
- 本地优先，模型可选
- 高风险结果必须人工复核

不采用过早的多 Agent 编排。

## 快速开始

环境要求：Python 3.11 或更高版本。

```powershell
python -m opc_agent doctor
```

分析简历：

```powershell
python -m opc_agent run `
  --task resume `
  --input examples/resume.txt `
  --goal-file examples/job_description.txt
```

自动识别并处理：

```powershell
python -m opc_agent run `
  --task auto `
  --input examples/contract.txt
```

直接传入文本：

```powershell
python -m opc_agent run `
  --task letter `
  --text "尊敬的老师：我觉得我想申请助学金，然后我会认真学习。谢谢老师。"
```

运行离线评测：

```powershell
python -m opc_agent eval --dataset evals/cases.jsonl
```

校验真实样本清单：

```powershell
python -m opc_agent samples validate
```

运行真实样本评测并生成报告：

```powershell
python -m opc_agent samples eval
```

运行公开许可与合成回归集：

```powershell
python -m opc_agent samples validate `
  --manifest samples/public/manifest.csv
python -m opc_agent samples eval `
  --manifest samples/public/manifest.csv `
  --reports-dir reports/public
```

真实样本登记表使用 `samples/manifest.local.csv`，样本正文和人工基线放在
`samples/private/`，默认都不进入 Git。报告写入 `reports/`。公开回归样本的来源、
许可证和派生说明见 `samples/public/README.md`。

启动本地 Web 工作台：

```powershell
python -m opc_agent.web --port 8765 --open
```

浏览器会打开 `http://127.0.0.1:8765/`。页面支持选择任务、自动路由、粘贴文本、上传文件、载入示例、查看结构化结果和下载报告。服务默认只监听本机。

## 输出

每次运行会在 `outputs/<时间>-<任务>/` 下生成：

- `report.md`
- `result.json`
- 票据任务额外生成 `receipts.csv`

通过 Web 工作台运行时，结果默认写入 `outputs/web/<时间>-<任务>/`。

## 接入模型

安装可选依赖：

```powershell
pip install -e ".[openai]"
```

设置环境变量：

```powershell
$env:OPC_PROVIDER = "openai"
$env:OPC_MODEL = "<your-model>"
$env:OPENAI_API_KEY = "<your-api-key>"
```

然后按相同命令运行。当前构建环境无法访问 OpenAI 官方文档站点，因此在线接口适配器保持最薄实现，尚未进行真实模型调用验证。默认的 `mock` 模式不受影响。

## 文档解析

基础模式支持 TXT、Markdown、JSON 和 CSV。

安装文档解析依赖：

```powershell
pip install -e ".[documents]"
```

安装 OCR 依赖：

```powershell
pip install -e ".[ocr]"
```

解析器优先尝试 MarkItDown，DOCX 回退到 python-docx，PDF 回退到 pypdf，图片使用
PaddleOCR。图片版 DOCX 也会抽取内嵌图片并尝试 OCR；未安装 OCR 依赖时会明确提示。

## 测试

```powershell
python -m unittest discover -s tests -v
```

运行完整项目质量门：

```powershell
pwsh -NoProfile -File .\scripts\Test-Project.ps1
```

该脚本依次执行编译检查、单元测试、离线评测和公开样本回归；安装 Ruff 后还会执行
静态检查。开发依赖可通过 `pip install -e ".[dev]"` 安装。

安装为 Python 包后，也可以使用两个命令入口：

```powershell
opc-agent doctor
opc-agent-web --port 8765 --open
```

## 公网部署

项目提供非 root Docker 镜像、Compose 持久卷和可选 Caddy HTTPS 代理。默认仍只
绑定 `127.0.0.1`，不会直接把本地文件处理服务暴露到公网。

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

需要短时公开演示时，使用项目脚本启动演示模式：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Demo.ps1
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1
```

演示模式会强制使用 `mock` 本地规则，默认 15 MB 上传上限、单 IP 每分钟 12 次运行、
最多 2 个并发任务；运行结果默认 1 小时后自动删除，下载链接使用进程内签名，不能
通过猜测路径访问。页面会显示公开演示提示。隧道脚本默认使用 `srv.us`，
也可以传入 `-Provider localhost.run` 或 `-Provider serveo.net` 切换服务商；
并把 PID、临时 HTTPS 地址和日志写入 `work/public-demo/`；停止隧道时运行：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1 -Stop
```

公网部署前先运行：

```powershell
.\scripts\Test-Deployment.ps1
```

完整流程、云服务器端口和 Caddy 配置见 `docs/deployment.md`。公网演示层仍不提供
登录、权限、正式配额、文件加密和审计，因此不得接收真实用户文档。

## 使用边界

- 简历和申请函不得编造事实。
- 合同分析不构成法律意见。
- 票据结果必须与原票据核对。
- 文件默认保存在本地，接入云端模型前需要评估隐私和合规。
- 生成结果必须由用户确认后才能对外提交。
- 当前 Web 服务面向本地单人使用，不提供账户、权限、云同步或多人协作。
