# 公网部署

## 当前边界

当前 Web 服务仍是单机 MVP，尚未提供登录、权限、正式用户配额、文件加密和审计。
公网演示模式已经提供按 IP 限流、并发限制、签名下载链接和结果过期清理，但它是
短时展示合成样本的隔离层，不替代正式安全能力，也不能用于接收真实用户文档。

推荐按三阶段推进：

1. 临时演示：`localhost.run`、Cloudflare Tunnel 或 ngrok 映射本机服务。
2. 容器验证：在 Docker 中运行并在本机反向代理后验收。
3. 正式公网：云服务器运行 Compose，Caddy 自动申请 HTTPS 证书。

## 临时演示

推荐直接使用项目脚本启动公网演示模式：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Demo.ps1
```

也可以手动启动同样的参数：

```powershell
python -m opc_agent.web `
  --host 127.0.0.1 `
  --port 8765 `
  --public-demo `
  --output-ttl-seconds 3600 `
  --max-runs-per-window 12 `
  --max-concurrent-runs 2
```

也可以用环境变量启用同样的边界：

```dotenv
OPC_PUBLIC_DEMO=true
OPC_PUBLIC_ALLOW_MODEL=false
OPC_OUTPUT_TTL_SECONDS=3600
OPC_MAX_RUNS_PER_WINDOW=12
OPC_MAX_RUNS_PER_DAY=6
OPC_GLOBAL_RUNS_PER_DAY=30
OPC_MAX_CONCURRENT_RUNS=2
OPC_MAX_UPLOAD_MB=15
OPC_MAX_INPUT_CHARS=20000
OPC_MAX_OUTPUT_TOKENS=1600
```

演示模式默认只允许 `mock` Provider。要启用在线模型，必须同时设置
`OPC_PUBLIC_ALLOW_MODEL=true`、配置 Provider、模型和 API Key，并在页面勾选
隐私安全确认；否则服务会拒绝启动或拒绝提交。下载链接使用随机密钥签名，页面
和健康接口会明确返回 `public_demo=true`。这些措施用于降低公开演示风险，不代表
服务已经达到接收真实用户文档的安全等级。

本项目已经提供后台 HTTPS 隧道脚本，默认使用 `srv.us`；也可以传入
`-Provider localhost.run` 或 `-Provider serveo.net` 切换服务商。脚本会为
`srv.us` 在 `work/public-demo/` 生成仅用于演示的临时 SSH 密钥，并把 PID、URL
和日志写入同一目录：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1
```

停止隧道：

```powershell
pwsh -NoProfile -File .\scripts\Start-Public-Tunnel.ps1 -Stop
```

也可以使用 Cloudflare Tunnel：

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

或使用 ngrok：

```powershell
ngrok http 8765
```

这种方式只适合短时演示。本机关机后地址失效，且不得上传真实用户文档。

2026-10-02 已通过临时 HTTPS 隧道完成首次公网合成样本验收。2026-10-05 完成
公网演示加固后的复验：本地服务以 `public_demo=true` 启动，通过 `srv.us` 建立
HTTPS 隧道；公网首页、健康接口、申请函合成样本提交、报告生成和签名下载均返回
成功。本次验收仍只使用仓库内合成文本，没有提交真实用户文档，临时隧道地址随本机
或 SSH 会话关闭而失效，不作为稳定交付地址。

## PythonAnywhere 固定部署

PythonAnywhere 适合当前标准库 WSGI 版本。应用入口为
`deploy/pythonanywhere_wsgi.py`，底层适配器为 `opc_agent/wsgi.py`。部署时把入口
文件复制到 PythonAnywhere 的 `/var/www/<domain>_wsgi.py`，并将项目放到
`~/opc-youth-document-agent`、运行数据放到 `~/opc-youth-data`。

该入口作为独立根站运行：

```text
https://<username>.pythonanywhere.com/
```

在线服务配置只从项目私有 `.env` 读取，不写入 WSGI 文件、仓库或镜像。公网
参数由入口固定为：

- 未配置在线服务时使用 `mock` 本地规则
- 上传上限 15 MB，输入上限 20,000 字符，输出上限 1,600 tokens
- 单 IP 每分钟 12 次、每日 6 次，全站每日 30 次
- 最多 2 个并发任务
- 结果保留 1 小时后自动清理

Web 界面会显示隐私安全提示，要求用户确认已脱敏；成功提交后确认框会自动复位。
提交内容会离开本站处理，本站只控制生成结果的保留时间，不能控制外部服务处理期间
的数据留存。健康接口只返回 `provider=online`，不公开厂商、模型或接口地址。额度
不足或在线服务异常时，页面会明确提示后台在线服务正在维护，并回退到本地规则。
不得用该演示链路接收真实证件、合同、简历、票据或其他敏感信息。

部署后的检查：

```text
GET /
GET /api/health
GET /api/examples?task=letter
POST /api/run
GET /api/download?token=...
```

健康接口应返回 `ok=true`、`public_demo=true` 和
`provider=online`；公开在线模式下同时返回 `online_model=true`、`model=""`，
不会暴露具体服务信息。公开链路只使用仓库内合成样本验证，不接收真实证件、合同、
简历或票据。若在线服务或公网链路异常，应立即把入口切回 `provider=mock`
或关闭在线模型后 reload。

## Docker 本地验证

复制环境变量模板并保持默认的本机绑定：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

检查服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

默认端口只绑定 `127.0.0.1`，不会直接暴露到公网。运行数据保存在 Docker 命名卷
`opc_data` 中，真实样本不应进入镜像。

当前环境已经使用 Docker Desktop 4.93.0、Engine 29.8.1 和 Compose v5.5.1
完成一次实跑：镜像构建成功，宿主机 `127.0.0.1:8765` 正常映射到容器 `8080`，
容器状态为 `healthy`，健康接口返回：

```json
{"ok": true, "provider": "mock", "model": ""}
```

部分中国大陆网络无法直连 Docker Hub。遇到
`registry-1.docker.io` 连接超时时，可以只从 AWS Public ECR 拉取 Docker 官方
Python 基础镜像，并在本机按项目原有标签标记；不要使用来源不明的镜像站：

```powershell
docker pull public.ecr.aws/docker/library/python:3.11-slim
docker tag public.ecr.aws/docker/library/python:3.11-slim python:3.11-slim
docker compose up -d --build
```

保留容器并停止服务：

```powershell
docker compose stop
```

删除容器和网络，保留数据卷：

```powershell
docker compose down
```

## 云服务器公开部署

建议使用 Ubuntu 24.04、2 核 4 GB 起步的云服务器，并提前准备域名。中国大陆服务器
和域名需要完成 ICP 备案。

服务器安全组至少限制：

- `22`：仅允许管理 IP。
- `80`、`443`：对公网开放。
- `8765`：不要对公网开放；Compose 默认只绑定本机。

在服务器安装 Docker 后，把项目放到非公开目录，并在 `.env` 设置：

```dotenv
OPC_PROVIDER=mock
OPC_MODEL=
OPC_BASE_URL=
OPC_API_KEY=
OPENAI_API_KEY=
OPC_BIND_ADDRESS=127.0.0.1
OPC_BIND_PORT=8765
OPC_SITE_ADDRESS=你的域名
```

如果只在受控环境使用在线模型，可将 `OPC_PROVIDER` 改为
`openai-compatible`，填写服务商提供的 `OPC_BASE_URL`、`OPC_MODEL` 和
`OPC_API_KEY`。不要把真实密钥写入 Git、镜像或公开演示页面。

先验证 HTTP 应用：

```bash
docker compose up -d --build
curl http://127.0.0.1:8765/api/health
```

再启用 Caddy：

```bash
docker compose --profile public up -d
```

Caddy 会自动申请和续期 HTTPS 证书，并把公网请求转发给应用。DNS 的 `A` 或
`AAAA` 记录必须先指向服务器，且 `80`、`443` 端口可访问。

更新版本：

```bash
git pull --ff-only
docker compose up -d --build
docker compose --profile public up -d
```

## 上线前检查

在源码目录运行：

```powershell
.\scripts\Test-Deployment.ps1
```

检查项包括单元测试、离线评测、公开样本回归、敏感文件忽略规则、Docker Compose
配置和镜像构建检查。本机未安装 Docker 或守护进程未启动时，脚本会明确跳过容器
相关检查。

上线前还必须人工确认：

- 只使用公开示例或已授权、已脱敏的文档。
- `.env`、API Key、真实样本、运行报告和云服务器凭据没有进入 Git 或镜像。
- 公网入口只允许必要的 Provider，并确认每 IP/全站每日额度、输入上限、超时和
  结果清理已经生效。
- 域名、备案、隐私政策、用户授权和数据留存期限已经确定。
- 日志不会记录上传正文、API Key 或可识别个人信息。
- 有备份、回滚、监控和文件清理方案。

## 正式内测前仍需开发

- 登录、会话、角色和访问控制。
- 上传限流、用户配额和防滥用。
- 文件加密、定期删除和数据导出。
- 错误监控、审计日志和告警。
- 正式数据库与对象存储。
- FastAPI、Uvicorn 或同类生产级服务替换标准库 HTTP Server。
