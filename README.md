# Mobility Management Agent · 行前

面向机场出行的、证据可核验的个人出行管家。它回答一个具体问题：
“为了按时登机，我应该几点离开出发地？”

`v0.3.0` 已完成本地网页、阿里云网页/API 和微信小程序的功能闭环；按既定范围不开发原生
App。默认无状态、不持久化个人行程，未配置的商业来源会明确降级，不由大模型编造。

## 已实现

- 文本/短信、ICS 日历、PNG/JPEG 截图 OCR 和手工行程导入；
- 航班时间窗、6 个机场的版本化流程、道路 P50/P90、机场公开天气和用户事件信号；
- 值机/登机硬约束、行李、无障碍、风险偏好和来源不确定性的确定性决策；
- 每个分钟分项的 Evidence、来源状态、完整性、置信度和 Verifier 重算；
- `gpt-5.6-sol` 兼容 Provider（仅在服务端密钥、策略和用户同意同时满足时解释证据）；
- T-24 提醒预览与标准 ICS/VALARM 日历文件；
- 高德官方 URI 地图/叫车提案，必须再次确认，不自动下单或付款；
- 证据受限问答、隐私导出、会话删除语义；
- React 网页与原生微信小程序共用 FastAPI/OpenAPI；
- Docker Compose、阿里云 Nginx/部署脚本、GitHub Actions 和安全检查。

## 运行边界

- 不逆向或抓取携程、航旅纵横、航空公司或社交 App 的私有页面；
- 不收集第三方密码、Cookie、AppSecret 或客户端 API Key；
- 不持久化行程、精确坐标、OCR 图片或问答内容；
- 不用模型计算/修改权威出发时刻，也不用模型记忆补齐实时事实；
- 不自动预约、付款、退改签或接受平台协议；
- 实时高德路线和航班动态只有在服务端配置获权接口后启用；
- 微信订阅消息投递仍需模板、AppSecret、用户授权和幂等 Outbox；当前用日历提醒完成可用闭环。

## 本地启动

### Docker

```bash
docker compose up --build
```

打开 [http://127.0.0.1:18081/mobility/](http://127.0.0.1:18081/mobility/)。

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

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

可选的实时/模型能力只通过环境变量启用，示例见 [`.env.example`](.env.example)。密钥不能进入
Git 或客户端。

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

用微信开发者工具导入 `clients/wechat-miniprogram`。公共
[`project.config.json`](clients/wechat-miniprogram/project.config.json) 固定
`touristappid`；正式 AppID 仅存在于 Git 忽略的 `project.private.config.json`。

正式身份为独立产品 AppID，生产 API 为：

```text
https://metro.9m-zx.com/mobility
```

微信公众平台的 `request` 合法域名应配置为 `https://metro.9m-zx.com`（不含路径）。
完整上传与验收说明见 [小程序文档](docs/wechat_miniprogram.md)。

## 阿里云

公网入口：

```text
https://metro.9m-zx.com/mobility/
```

服务器部署：

```bash
sudo bash infra/aliyun/deploy.sh main
bash scripts/smoke_cloud.sh
```

该产品复用既有 ECS 和 HTTPS 入口，但使用独立目录、Compose project、容器/服务和回环端口
18081/18082，不复用客流智能体的小程序身份或业务数据。

## 目录

```text
clients/web/                 React 网页
clients/wechat-miniprogram/  微信小程序
src/mobility_agent/          API、导入、来源、决策、提醒与动作
config/                      机场配置、能力和晋级门禁
tests/                       后端回归测试
infra/                       Docker 与阿里云部署
docs/                        产品、架构、数据、合规和实施经验
```

本仓库公开可见，但未授予开源许可证；真实凭据、真实行程、个人数据和微信正式配置不得提交。
