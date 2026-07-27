# 阿里云托管与 GitHub 工程方案

## 1. 资源复用原则

按用户要求复用客流智能体所在的阿里云账号、北京地域、现有 VPC、已备案域名和工程经验，
但不共享业务身份、数据库账号、端口、运行目录、日志或秘密。

参考资源只用别名登记：

| 资源 | 本项目用途 | 边界 |
| --- | --- | --- |
| 既有 Web ECS（2 vCPU / 4 GB） | P3 低流量 staging | 容量测试通过才共机 |
| 既有北京 VPC | 内网通信 | 新安全组规则最小化 |
| 既有数据库 ECS | P2/P3 shadow 的独立数据库 | 不使用 `metroflow` 或其账号 |
| `9m-zx.com` 已备案域名 | 新子域名 | 建议 `mobility.9m-zx.com` |
| 同一 GitHub 账号 | 新私有仓库 | 不复制历史秘密或真实数据 |

实例 ID、公网 IP、SSH 公钥、证书材料和安全组 ID 不进入 Git，存放在项目外受限部署清单。

## 2. 为什么不原样复制“Mac 反向隧道”

客流智能体的固定入口 + Mac Hermes 是有效的 shadow/演示方案，但本项目的云网页阶段目标
是“网页与 API 真正在阿里云可用”。因此：

- 本地 P1/P2 可以使用 Hermes 或本机模型 Provider 做 shadow；
- P3 前端、API、worker 和持久化全部运行在阿里云；
- 云端模型必须使用经批准的服务器 API/企业模型平台；
- Mac 关机、用户退出或家庭网络断开不能使云网页失效；
- 反向隧道只保留为诊断/开发工具，不是主链路。

## 3. P3 staging 拓扑

```text
用户浏览器 / 微信（P4）
  → HTTPS mobility.9m-zx.com
  → ECS Nginx
      ├── /            Web 静态文件
      ├── /api/        FastAPI
      ├── /health      分层健康
      └── /uploads     预签名 OSS 流程，不直通本地文件
  → Docker Compose
      ├── web
      ├── api
      └── worker
  → VPC 内数据库（独立库/账号）
  → 独立 OSS bucket
  → 外部批准 API：地图/航班/天气/模型
  → SLS/CMS
```

Nginx 对上传、普通 API 和模型消息使用独立限制。长请求尽量改成异步 run + polling/SSE，
不复制 180 秒同步超时作为常规体验。

## 4. 容量门禁

在既有 Web ECS 共机前，连续观察客流项目 7 天并压测新栈。建议门槛：

- 现有 CPU p95 < 60%；
- 可用内存稳态 > 1 GiB；
- 根盘/日志盘剩余 > 30%；
- 新栈 20 并发核心 API 不触发 OOM；
- 两项目有独立 Compose project、systemd unit、端口和 health；
- 停止/回滚新项目不会重启客流项目；
- SLS/CMS 能按项目区分告警。

若不满足，新增 ECS，而不是牺牲客流项目稳定性。2 vCPU / 4 GB 不承担本地大模型推理。

## 5. 数据库

staging：

- 独立数据库名；
- 独立迁移账号和运行账号；
- 运行账号只获得所需表权限；
- TLS、私网、无公网 3306；
- 每日备份和恢复演练；
- 真实截图/住址不进入通用查询表。

生产候选：

- 优先迁移到 RDS MySQL；
- 加密存储、备份、时间点恢复；
- 主从/多可用区由 SLO 决定；
- KMS/Secrets Manager + RAM 角色注入秘密；
- 数据生命周期和删除任务可审计。

模型绝不选择表名或生成 SQL。所有仓储通过固定 Repository 方法和参数化查询。

## 6. GitHub 仓库与分支

推荐：

```text
remote:  poaterjordi-netizen/mobility_management_agent
default: main
branch:  codex/<issue-number>-<short-name>
release: v0.x.y
```

保护 `main`：

- Pull Request；
- 至少一名审查者；
- CI 全绿；
- 禁止 force push；
- secret scanning / push protection；
- CodeQL 和 Dependabot；
- 合并前解决所有 review；
- 生产环境需要 GitHub Environment 人工批准。

初始仓库设为 private。代码、合成 fixture 和公开文档完成清理后，另行决定是否开源。

## 7. CI

每个 PR：

1. JSON/YAML/Schema 校验；
2. Python 3.11–3.13 单测；
3. Ruff、覆盖率门槛；
4. 合成 Gold Cases；
5. OpenAPI 客户端再生成且工作树不脏；
6. 前端 lint、typecheck、build；
7. Playwright；
8. Docker Compose build/smoke；
9. CodeQL、依赖和秘密扫描；
10. 文档严格构建。

真实模型、地图、航班 API 不在普通 CI 调用。nightly shadow 使用独立预算和脱敏用例，失败
不泄露响应正文。

## 8. CD

制品流程：

```text
受保护 tag
  → 构建前后端镜像
  → SBOM/漏洞扫描
  → 记录 commit SHA + image digest
  → staging 自动或人工部署
  → smoke + migration check
  → 人工批准
  → production 候选
```

部署不在服务器上直接 `git pull` 后就地构建。回滚使用上一个镜像 digest 和向后兼容数据库
迁移。破坏性 migration 分为 expand/migrate/contract 多次发布。

## 9. 域名、HTTPS 和小程序

- 新子域名单独 Nginx `server`；
- 证书自动续期并告警；
- 只开放 80/443，80 跳转 HTTPS；
- HSTS/CSP/CORS/安全响应头逐步开启；
- 小程序 `request` 合法域名只填写域名，不含路径；
- 必须在严格域名校验和真机冷启动下验收；
- 域名可在浏览器打开不代表微信配置已生效；
- API 错误要区分客户端白名单、DNS/TLS、Nginx、API、供应商和模型。

## 10. 认证与授权

P1：本地单用户开发模式。
P3：邀请制账号、服务端 session、对象级 trip/run/evidence 授权。
P4：`wx.login` code 在服务端交换身份，AppSecret 仅在服务端。

共享 Basic Auth 或静态 Bearer Token只能用于短期 staging，不能作为试点用户身份。

## 11. 秘密与配置

Git 只保存 `.env.example`。禁止提交：

- OpenAI/百炼/高德/航班 API Key；
- 数据库密码和 DSN；
- 微信 AppSecret；
- SSH 私钥、证书私钥；
- 真实 `.env`、服务器 inventory；
- 用户截图和真实 Trace。

配置按环境版本化，但秘密值由 Keychain（本地）或云端 Secret Manager 注入。模型和数据
出域策略包含 provider、model、endpoint hash 的精确绑定。

## 12. 可观测性

三类观测：

- 系统：CPU、内存、磁盘、容器、端口、证书、数据库；
- 依赖：供应商成功率、p95、429、配额、熔断；
- 业务：行程刷新、决策成功、提醒延迟、过期证据、核验失败。

每条请求用 `trace_id`，每个决定用 `decision_id`，每次供应商调用用 `observation_id`。
日志不包含完整地址、票号、原始通知或截图 OCR 全文。

## 13. 备份与灾备

- 数据库每日备份，月度恢复演练；
- OSS lifecycle 和删除队列；
- 配置、Schema、机场数字孪生均在 Git；
- 秘密和云资源清单独立备份；
- 单 ECS staging 接受短时中断，但明确 RTO/RPO；
- 试点前完成 ECS 故障、数据库恢复、供应商全断和模型不可用演练。

## 14. 从零恢复顺序

1. 取得已发布 Git tag 和镜像 digest；
2. 恢复 VPC/ECS/Nginx/DNS/TLS；
3. 恢复数据库与独立账号；
4. 恢复 OSS 和生命周期；
5. 从 Secret Manager 注入运行秘密；
6. 启动 api/worker/web；
7. 验证 health、auth、trip、decision；
8. 验证一个合成行程；
9. 在批准后验证真实供应商；
10. 恢复提醒，避免重复发送旧 Outbox。
