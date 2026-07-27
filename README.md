# Mobility Management Agent · 行前

面向机场出行场景的、可核验的个人出行智能管家框架。它回答一个具体问题：
“为了按时登机，我应该几点离开出发地？”

当前 `v0.2.0` 是可运行的基础版，包含本地网页、FastAPI、确定性决策引擎、证据与核验、
微信小程序工程、Docker Compose 和阿里云部署入口。所有演示数据均为合成数据，不用于
真实出行。

## 已实现

- React / TypeScript / Vite 响应式网页；
- FastAPI API 和自动生成的 OpenAPI 合约；
- 机场流程、道路、叫车等待和风险缓冲的确定性时间计算；
- Evidence + Verifier，确保时间线能由输入和规则重算；
- FakeProvider，未配置模型密钥也能完整运行；
- 可由微信开发者工具导入的四页小程序，包含建议、行程确认、运行诊断与隐私边界；
- 隔离端口的 Docker Compose；
- GitHub Actions：后端、网页 E2E、小程序、容器和仓库安全检查；
- 阿里云 ECS 部署脚本及既有 HTTPS 站点的路径反代片段。

## 系统边界

本版本不会：

- 读取携程、国航、航旅纵横或社交 App 的私有页面；
- 使用真实航班、路况、天气、住址或订单；
- 保存行程；
- 自动预约车辆、付款或发送提醒；
- 让大模型直接计算或覆盖出发时刻。

架构预留的质量基线模型是 `gpt-5.6-sol`，但当前运行 Provider 固定为 `fake`。后续接入
真实模型时，模型只负责意图理解与说明，核心时刻仍由可重放代码计算和核验。

## 本地启动

### Docker（推荐）

```bash
docker compose up --build
```

打开 [http://127.0.0.1:18081/mobility/](http://127.0.0.1:18081/mobility/)。
容器产物按阿里云路径 `/mobility/` 构建；直接访问
[http://127.0.0.1:18081/](http://127.0.0.1:18081/) 也可加载页面。

### 分别启动

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/mobility-agent-api
```

另开终端：

```bash
cd clients/web
npm ci
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。如果该端口被占用：

```bash
MOBILITY_API_PORT=18000 .venv/bin/mobility-agent-api
```

另开终端后：

```bash
cd clients/web
VITE_DEV_PORT=15173 VITE_PROXY_TARGET=http://127.0.0.1:18000 npm run dev
```

## 验证

```bash
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/python scripts/export_openapi.py

cd clients/web
npm run lint
npm run build
npm run test:e2e

cd ../wechat-miniprogram
npm run check
npm test
```

## 微信小程序

用微信开发者工具导入 `clients/wechat-miniprogram`。仓库只提交 `touristappid`，避免泄露或
误用正式 AppID。正式发布需要：

1. 注册独立小程序并填写 AppID；
2. 在公众平台把 `https://metro.9m-zx.com` 配置为 request 合法域名；
3. 完成真机、隐私合规和微信审核；
4. 由有发布权限的微信账号上传。

小程序源代码会随仓库部署到阿里云 ECS，运行时 API 也托管于阿里云；小程序包本身必须由
微信平台发布，不能由阿里云代替。

合成版已经完成：

- 从阿里云加载合成行程并生成经 Verifier 核验的建议；
- 在小程序中确认/修改航班、机场、航站楼、时间、合成出发地、行李和风险偏好；
- 展示建议时间、最晚参考时间、机场到达时间、证据、置信度与策略版本；
- 检查 `health` 和 `capabilities`，诊断 request 合法域名；
- 展示隐私、数据最小化和未开放能力；
- 行程只保存在运行内存，Storage 只保存非敏感环境枚举。

完整操作与发布门禁见 [`docs/wechat_miniprogram.md`](docs/wechat_miniprogram.md)。

## 阿里云

基础版复用客流智能体的阿里云 Web ECS，但使用独立 Compose project、目录和本机端口。
公网入口设计为：

```text
https://metro.9m-zx.com/mobility/
```

服务器部署：

```bash
sudo bash infra/aliyun/deploy.sh main
```

把 `infra/aliyun/mobility-zones.conf` 安装到 Nginx `http` 上下文，并将
`infra/aliyun/mobility-location.conf` 的两个 `location` 加入现有 HTTPS `server`。
先运行 `nginx -t`，再平滑重载。部署脚本依次尝试 Docker Compose、隔离 Docker
容器；若国内镜像源不可用，则使用现有 Python/Node 构建并安装两个受限 systemd 服务。
三种模式统一监听回环端口 18081（网页）和 18082（API）。部署后执行：

```bash
bash scripts/smoke_cloud.sh
```

## 目录

```text
clients/web/                 React 网页
clients/wechat-miniprogram/  微信小程序
src/mobility_agent/          API、Agent 边界、决策与核验
tests/                       后端测试
infra/docker/                容器镜像
infra/aliyun/                ECS 与 Nginx 部署入口
config/                      能力和晋级门禁
docs/                        完整产品、架构、数据、合规与评测计划
```

## 计划文档

- [总计划](MASTER_PLAN.md)
- [产品范围与用户旅程](docs/product_scope.md)
- [系统架构](docs/architecture.md)
- [数据与外部集成](docs/data_integrations.md)
- [出发时刻决策引擎](docs/decision_engine.md)
- [阿里云与 GitHub 工程方案](docs/cloud_devops.md)
- [安全、隐私与合规](docs/security_compliance.md)
- [评测与验收](docs/evaluation_acceptance.md)
- [实施 Backlog](docs/backlog.md)

本仓库公开可见，但未授予开源许可证；真实凭据、真实行程和个人数据不得提交。
