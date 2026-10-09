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
OPC_OUTPUT_TTL_SECONDS=3600
OPC_MAX_RUNS_PER_WINDOW=12
OPC_MAX_CONCURRENT_RUNS=2
OPC_MAX_UPLOAD_MB=15
```

演示模式会强制使用 `mock` Provider；配置 `openai` 时服务会拒绝启动。下载链接使用
随机密钥签名，页面和健康接口会明确返回 `public_demo=true`。这些措施用于降低公开
演示风险，不代表服务已经达到接收真实用户文档的安全等级。

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
OPENAI_API_KEY=
OPC_BIND_ADDRESS=127.0.0.1
OPC_BIND_PORT=8765
OPC_SITE_ADDRESS=你的域名
```

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
