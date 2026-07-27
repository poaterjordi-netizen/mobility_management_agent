# Mobility Management Agent

面向机场出行场景的、可审计的个人出行智能管家。项目按以下顺序交付：

1. 本地网页；
2. 阿里云网页；
3. 微信小程序；
4. 在前三阶段通过验收后，再决定是否开发原生手机 App。

当前状态：**规划基线（2026-07-27）**。本仓库目前只保存产品、架构、数据、合规、
评测和交付计划，不包含网页、小程序或 App 的业务实现。

## 已确定的技术方向

- 单仓库：Python 3.11+ / FastAPI 后端，React / TypeScript / Vite 前端；
- 延续客流智能体的受控 Agent 架构：结构化语义、工具白名单、EvidencePacket、
  Verifier、Trace Store、FakeProvider 和真实模型 shadow；
- `gpt-5.6-sol` 作为第一阶段质量基线，但核心出发时刻由确定性代码计算；
- 本地先行，阿里云使用与客流智能体相同账号、地域和既有基础资源，采用独立域名、
  独立容器、独立数据库/账号和独立日志；
- 不抓取第三方 App 私有页面，不保存第三方账号密码，不让模型自由调用 SQL 或直接下单；
- 网约车预约在早期只生成可解释建议和官方跳转，任何付费动作都必须由用户确认。

## 计划导航

- [总计划](MASTER_PLAN.md)
- [产品范围与用户旅程](docs/product_scope.md)
- [系统架构](docs/architecture.md)
- [数据与外部集成](docs/data_integrations.md)
- [出发时刻决策引擎](docs/decision_engine.md)
- [阿里云与 GitHub 工程方案](docs/cloud_devops.md)
- [安全、隐私与合规](docs/security_compliance.md)
- [评测与验收](docs/evaluation_acceptance.md)
- [实施 Backlog](docs/backlog.md)
- [风险登记册](docs/risk_register.md)
- [参考基线与资料](docs/references.md)

## 下一步

只有在项目负责人确认本计划中的范围、首批机场、数据来源和云端模型数据出域策略后，
才进入 P0 工程基线和 P1 本地网页开发。
