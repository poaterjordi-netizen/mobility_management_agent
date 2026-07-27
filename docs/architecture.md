# 系统架构

## 0. v0.4.1 已落地架构

0.4.0 在既有确定性闭环上加入 `JsonHttpClient` 公共来源边界：固定 HTTPS 主机、大小与超时
限制、TTL 缓存、有限重试和熔断。Open-Meteo、AviationWeather.gov 与 adsb.lol 通过独立
适配器归一化；ADS-B 和 METAR 只作为补充证据，不可覆盖用户确认的计划时间或确定性约束。

0.4.1 将高德 V5 驾车路线纳入同一 allowlist/缓存/熔断边界，解析推荐路线 ETA、距离与 TMC
路况分段。实时路线被限制在预计离家前 3 小时，P50 表示当前推荐路线 ETA，P90 是决策
引擎的确定性保守上界，不冒充供应商统计分位数。未来路径规划高级接口未获企业权限时保持
禁用。Key 只通过阿里云 root-only 环境文件注入。

当前实现是无状态模块化单体，不依赖数据库：

```text
React Web / 微信小程序
        │ HTTPS + OpenAPI
        ▼
FastAPI
  ├─ intake: 文本 / ICS / 本地 OCR → TripCandidate
  ├─ integrations: Flight / Airport / Route / Weather / Disruption
  ├─ decision: 纯函数 + Evidence + Verifier
  ├─ assistant: 确定性模板 / 可选 Responses API
  ├─ reminders: T-24 + ICS/VALARM
  ├─ actions: 高德官方 URI 提案
  └─ privacy: 无状态导出/删除语义
```

机场流程来自 `config/airports.json`；实时高德、获权航班和模型通过服务端配置与用户同意
门禁启用。原始截图、住址和票务敏感字段不发送给模型。持久化、身份、worker/Outbox 是未来
多用户订阅消息阶段的独立扩展，不是当前核心闭环的隐式依赖。

## 1. 总体结构

```text
React Web / 微信小程序 / 未来原生 App
                    │
             HTTPS / OpenAPI
                    ▼
┌─────────────────────────────────────────────┐
│ FastAPI                                    │
│ Trip / Sources / Decision / Reminder / Privacy │
└───────────────────┬─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│ MobilityAssistantService                    │
│ Build context → Compute → Verify → Explain │
└───────┬──────────────┬──────────────┬────────┘
        ▼              ▼              ▼
  LLMProvider     ToolRegistry    TraceStore
  语义/表达        受控事实工具      可回放轨迹
        │              │
        │      ┌───────┴────────────────────┐
        │      ▼                            ▼
        │  外部适配器                   领域服务
        │  航班/机场/地图/天气/事件      决策/提醒/冲突/质量
        │      │                            │
        └──────┴──────────► EvidencePacket ◄┘
                                  │
                                  ▼
                              Verifier
                                  │
                                  ▼
                          Answer / ActionProposal
```

## 2. 责任分离

| 模块 | 负责 | 不负责 |
| --- | --- | --- |
| `assistant/provider.py` | 结构化语义和证据表达 | 查实时数据、算出发时刻、执行动作 |
| `assistant/orchestrator.py` | 状态机、依赖、超时、降级、轨迹 | 直接访问供应商 SDK |
| `assistant/tool_registry.py` | 工具白名单和参数 Schema | 接受任意函数名或自由 URL |
| `integrations/*` | 调用单一外部来源并规范化 | 跨来源做最终决策 |
| `quality/*` | 新鲜度、完整性、冲突、可信度 | 用低可信来源补齐事实 |
| `decision/*` | 时序约束、分位数、缓冲和情景 | 写自然语言结论 |
| `evidence/*` | 来源、时间、hash、lineage、coverage | 创造事实 |
| `verifier/*` | 核对数字、引用、状态、动作权限 | 代替用户确认 |
| `reminders/*` | 幂等调度、Outbox、重试 | 绕过平台授权发送 |
| 客户端 | 输入、确认、展示、反馈 | 持有秘密、直连数据库、计算权威时间 |

## 3. 推荐代码结构

```text
mobility-management-agent/
├── clients/
│   ├── web/
│   └── wechat-miniprogram/       # P4 合成闭环与运行诊断已实现
├── config/
│   ├── capabilities.json
│   ├── source_policies.json
│   └── promotion_gates.json
├── docs/
├── evals/
│   ├── decision_accuracy/
│   ├── itinerary_extraction/
│   └── reliability/
├── examples/
│   └── synthetic_data/
├── infra/
│   ├── aliyun/
│   ├── nginx/
│   └── systemd/
├── schemas/
├── scripts/
├── src/mobility_agent/
│   ├── api/
│   ├── assistant/
│   ├── decision/
│   ├── domain/
│   ├── evidence/
│   ├── integrations/
│   ├── quality/
│   ├── reminders/
│   ├── repositories/
│   ├── security/
│   └── verifier/
└── tests/
```

首版保持模块化单体，不拆微服务。只有当独立伸缩、团队边界或故障隔离有实证需要时才拆。

微信小程序当前包含建议、行程确认、设置/连通性诊断和隐私边界四个页面。行程状态只存在于
`App.globalData`，退出运行后清除；客户端不计算权威时间，只向同一 FastAPI 合约提交经校验的
`TripInput`，再展示服务端 `DecisionResponse`。

## 4. 稳定数据契约

### `TripCandidate`

OCR、文本、日历或手工输入产生的候选，不可直接触发提醒：

```json
{
  "source_ref": "upload:...",
  "flight_number": "CA1234",
  "departure_local_date": "2026-08-01",
  "scheduled_departure": "2026-08-01T09:20:00+08:00",
  "origin_airport_iata": "PEK",
  "terminal": "T3",
  "field_confidence": {},
  "needs_user_confirmation": true
}
```

### `Trip`

用户确认后的领域对象。敏感字段与展示字段分离，所有修改保留版本。

### `SourceObservation`

所有外部事实统一包装：

```json
{
  "observation_id": "obs-...",
  "source_id": "amap-route",
  "source_type": "official_api",
  "observed_at": "2026-08-01T05:00:00+08:00",
  "valid_for": {"start": "...", "end": "..."},
  "fresh_until": "2026-08-01T05:10:00+08:00",
  "scope": {},
  "payload_ref": "sha256:...",
  "completeness": "complete",
  "confidence": 0.92,
  "warnings": []
}
```

### 领域快照

- `FlightSnapshot`
- `AirportProcessSnapshot`
- `RouteSnapshot`
- `WeatherSnapshot`
- `DisruptionSignal`
- `UserPreferenceSnapshot`

它们都由 `SourceObservation` 衍生，不能脱离 lineage。

### `DepartureDecision`

```json
{
  "decision_id": "dec-...",
  "trip_version": 3,
  "recommended_leave_at": "...",
  "latest_reasonable_leave_at": "...",
  "target_terminal_arrival": "...",
  "confidence_band": {"low": "...", "high": "..."},
  "risk_level": "medium",
  "components_minutes": {},
  "binding_constraints": [],
  "evidence_ids": [],
  "assumptions": [],
  "missing_evidence": [],
  "policy_version": "decision-policy-1.0.0"
}
```

### `ActionProposal`

任何外部动作先成为提案：

```json
{
  "action_type": "open_ride_hailing",
  "status": "awaiting_user_confirmation",
  "parameters_preview": {},
  "expires_at": "...",
  "idempotency_key": "...",
  "requires_payment": false
}
```

### `EvidencePacket` 与 `VerificationReport`

延续参考系统的 hash、lineage、scope、completeness、truncation 和策略快照绑定。Verifier
必须复算决定的分项和最终时间，而不只检查模型引用。

## 5. 状态机

```text
RECEIVE
  → PARSE_CANDIDATE
  → CONFIRM_TRIP
  → BUILD_CONTEXT
  → FETCH_SOURCES
  → ASSESS_QUALITY
  → RESOLVE_CONFLICTS
  → COMPUTE_DECISION
  → BUILD_EVIDENCE
  → SYNTHESIZE
  → VERIFY
  → PROPOSE_ACTION
  → RESPOND
```

刷新任务从 `BUILD_CONTEXT` 重入，但绑定最新 `trip_version`。如果行程已删除、提醒被关闭或
任务租约过期，worker 必须停止。一个运行最多允许一次受限补查，不做无限 Agent 循环。

## 6. 外部工具分组

- `trip.*`：解析、确认、版本、删除；
- `flight.*`：计划、动态、航站楼、值机/登机窗口；
- `airport.*`：流程规则、入口/安检/登机口、步行；
- `route.*`：地理编码、驾车路线、ETA、实时交通；
- `weather.*`：当前和预报、预警；
- `events.*`：政府公告、施工、活动、新闻/公共线索；
- `decision.*`：情景、分位数、绑定约束、差异；
- `reminder.*`：预览、排程、取消、投递状态；
- `action.*`：只生成深链/提案，早期没有 `book`。

工具返回必须是结构化 `ToolResult`，包含超时、配额、重试和数据新鲜度。

## 7. API 轮廓

```text
GET    /health
GET    /api/v1/capabilities
POST   /api/v1/trips/candidates
POST   /api/v1/trips
GET    /api/v1/trips
GET    /api/v1/trips/{trip_id}
PATCH  /api/v1/trips/{trip_id}
DELETE /api/v1/trips/{trip_id}
POST   /api/v1/trips/{trip_id}/refresh
GET    /api/v1/trips/{trip_id}/decision
GET    /api/v1/trips/{trip_id}/evidence
POST   /api/v1/trips/{trip_id}/action-proposals
POST   /api/v1/assistant/sessions
POST   /api/v1/assistant/sessions/{id}/messages
GET    /api/v1/runs/{run_id}
GET    /api/v1/runs/{run_id}/events
POST   /api/v1/runs/{run_id}/feedback
GET    /api/v1/privacy/export
DELETE /api/v1/privacy/account
```

生成客户端，不手工维护第二套类型。

## 8. 数据存储边界

逻辑分区：

- `identity`：用户标识与权限；
- `trip`：经确认的行程与版本；
- `observation`：规范化事实和 hash，不默认保存完整第三方响应；
- `decision`：输入快照、参数、结果；
- `reminder`：计划、Outbox、投递；
- `trace`：模型/工具/核验事件的脱敏记录；
- `consent`：授权、撤回和策略版本。

完整住址使用加密字段或只保存地点 token/坐标栅格；普通日志只显示用户别名、城市和 hash。
上传截图独立存储、短期保留、异步删除。

## 9. 降级

| 失败 | 行为 |
| --- | --- |
| 模型不可用 | 继续确定性解析/计算，使用模板解释 |
| 航班动态不可用 | 使用用户确认的计划信息，显著标记 |
| 路线 API 不可用 | 使用最近未过最大 TTL 的快照或拒绝给精确时间 |
| 机场流程缺失 | 使用机场类别的保守策略，并标注低置信度 |
| 社交/事件源不可用 | 不影响核心闭环，只报告该类风险未覆盖 |
| 数据冲突 | 按来源等级和新鲜度裁决；关键字段要求用户确认 |
| 提醒发送失败 | Outbox 有界重试，页面显示失败，不重复轰炸 |
| 数据库/存储失败 | 不产生新建议或动作，返回可追踪错误 |
