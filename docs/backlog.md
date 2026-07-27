# 实施 Backlog

## v0.3.0 交付快照

已完成：`FND-001..006`、`DOM-001..006`、`DEC-001..004/006`、`AGT-001/005`、
`WEB-002..008`、`SRC-001..003/005/006`、`REM-004/005`、`CLD-002/003`、
`WX-001/003/004/006/008` 的代码与自动化部分。

受外部条件保护而非伪实现：

- `SRC-002/004` 的实时调用需要合法服务端 Key/合同接口；
- `REM-001/002/006` 的微信投递需要模板、AppSecret、授权和 Outbox；
- `WX-002` 在当前无状态单用户预览中不需要，开启多用户持久化前必须完成；
- `DEC-005/007`、真实 shadow、校准、身份、持久化和正式试点仍是生产晋级工作；
- 原生 App 保持 out-of-scope。

Issue 编号在创建 GitHub 远端后分配。以下 ID 是稳定的规划 ID。

## EPIC-00 仓库与工程基线

| ID | 工作项 | 验收 |
| --- | --- | --- |
| FND-001 | Python/Node 单仓库骨架 | 本地安装、health、空壳 Web |
| FND-002 | GitHub Actions | Python/前端/容器/文档/安全检查 |
| FND-003 | OpenAPI 生成客户端 | 重新生成后工作树干净 |
| FND-004 | 配置与秘密边界 | `.env.example`、secret scan、无真实值 |
| FND-005 | 合成数据和时钟 | 可固定时间、时区和随机种子 |
| FND-006 | 文档站 | strict build |

## EPIC-01 领域契约

| ID | 工作项 | 验收 |
| --- | --- | --- |
| DOM-001 | TripCandidate/Trip | 用户确认和版本化 |
| DOM-002 | Observation Schema | 来源、新鲜度、scope、hash |
| DOM-003 | 领域快照 | Flight/Airport/Route/Weather/Event |
| DOM-004 | DepartureDecision | 分项、绑定约束、策略版本 |
| DOM-005 | Evidence/Verification | 可重算、lineage、fail closed |
| DOM-006 | ActionProposal | 等级、确认、幂等、过期 |

## EPIC-02 确定性决策

| ID | 工作项 | 验收 |
| --- | --- | --- |
| DEC-001 | 机场时间约束 | 值机/登机/流程三类约束 |
| DEC-002 | 交通与叫车分位数 | 风险偏好映射 |
| DEC-003 | 机场步行/流程预算 | 未知登机口保守分布 |
| DEC-004 | 风险缓冲 | 不重复计算、每项有证据 |
| DEC-005 | 固定点迭代 | 有界、可收敛/保守降级 |
| DEC-006 | Verifier | 重算所有时间和分项 |
| DEC-007 | 20→50 条 Gold Cases | 100% 通过 |

## EPIC-03 Agent

| ID | 工作项 | 验收 |
| --- | --- | --- |
| AGT-001 | Provider 接口 | Fake/Sol/兼容 Provider 可替换 |
| AGT-002 | SemanticFrame/OperationIR | 模型不输出决定时间或 SQL |
| AGT-003 | ToolRegistry | 固定工具与参数白名单 |
| AGT-004 | Orchestrator | 有界状态机、超时和一次补查 |
| AGT-005 | Evidence synthesis | 事实/计算/假设分离 |
| AGT-006 | Trace Store | 脱敏、owner 隔离、可回放 |
| AGT-007 | 模型 A/B | medium/low/模板报告 |

## EPIC-04 本地 Web

| ID | 工作项 | 验收 |
| --- | --- | --- |
| WEB-001 | 首页/行程列表 | 响应式与空状态 |
| WEB-002 | 行程录入/确认 | 关键字段不静默采用 |
| WEB-003 | 截图上传 | 安全检查、OCR、删除 |
| WEB-004 | 决策详情 | 时间线、分项、风险、证据 |
| WEB-005 | 受控问答 | run/events/verifier 可见 |
| WEB-006 | 来源设置 | 状态、新鲜度、故障 |
| WEB-007 | 隐私页 | 导出、删除、授权 |
| WEB-008 | Playwright | 核心与失败路径 |

## EPIC-05 数据适配器

| ID | 工作项 | 验收 |
| --- | --- | --- |
| SRC-001 | Source Registry | 许可、TTL、配额、owner |
| SRC-002 | 高德路线 | 测试 Key、契约、缓存、熔断 |
| SRC-003 | 天气/预警 | 来源对照和极端情况 |
| SRC-004 | 航班来源 PoC | 覆盖/SLA/合同评估 |
| SRC-005 | 机场配置 | 首批 3 个机场 |
| SRC-006 | 公告/活动 | 官方优先、弱信号 |
| SRC-007 | 冲突解析 | 关键字段阻断或解释 |

## EPIC-06 提醒与动作

| ID | 工作项 | 验收 |
| --- | --- | --- |
| REM-001 | 调度 worker | lease、重启恢复 |
| REM-002 | Outbox | 幂等、重试、取消 |
| REM-003 | 变化检测 | 阈值和抑制 |
| REM-004 | 提醒预览 | T-24h 内容和证据 |
| REM-005 | 地图/打车深链 | 用户点击、无自动下单 |
| REM-006 | 投递适配器 | 渠道授权和状态 |

## EPIC-07 阿里云

| ID | 工作项 | 验收 |
| --- | --- | --- |
| CLD-001 | 资源容量盘点 | 不影响客流站点 |
| CLD-002 | 独立 Compose/systemd | 启停和回滚隔离 |
| CLD-003 | Nginx/HTTPS/子域名 | 只开放必要路径 |
| CLD-004 | 独立数据库/账号 | TLS、私网、备份恢复 |
| CLD-005 | OSS | 预签名、加密、生命周期 |
| CLD-006 | Secret Manager | 无长期秘密在镜像/服务器文件 |
| CLD-007 | SLS/CMS | 系统/依赖/业务告警 |
| CLD-008 | CD | digest、审批、smoke、回滚 |

## EPIC-08 微信小程序

| ID | 工作项 | 状态 | 验收 |
| --- | --- | --- | --- |
| WX-001 | 项目骨架/API client | 合成版完成 | 共用后端契约 |
| WX-002 | 微信登录 | 未开始 | 服务端 code 交换与对象授权 |
| WX-003 | 行程/建议/证据 | 合成版完成 | 小屏核心闭环 |
| WX-004 | 上传 | 未开始 | 隐私和生命周期 |
| WX-005 | 订阅消息 | 未开始 | 用户授权、幂等、取消 |
| WX-006 | 合法域名/备案 | 代码完成、平台待配置 | 严格模式 |
| WX-007 | 真机验收 | 待正式 AppID | Android/iPhone 冷启动 |
| WX-008 | 体验版发布 | 待正式 AppID | 版本、run/audit 记录 |

## EPIC-09 试点与 App 决策

| ID | 工作项 | 验收 |
| --- | --- | --- |
| PIL-001 | 试点协议/PIPIA | 用户知情、退出、删除 |
| PIL-002 | 20–50 用户 | 代表性行程和机场 |
| PIL-003 | 校准 | 覆盖率、早到、晚到、噪声 |
| PIL-004 | 成本 | 单建议/MAU 成本 |
| PIL-005 | 数据合作 | 稳定来源和生产权利 |
| PIL-006 | App 技术 Spike | Android 通知、iOS Share |
| PIL-007 | Go/No-Go 报告 | 产品、合规、技术、成本 |
