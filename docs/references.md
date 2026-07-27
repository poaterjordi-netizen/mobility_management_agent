# 参考基线与官方资料

检索日期：2026-07-27。外部平台能力、价格、配额和条款在实施前需要再次核验。

## 1. 本地客流智能体基线

参考仓库：

```text
/Users/xiaobosun/software/metro-passenger-flow-agent
remote: https://github.com/poaterjordi-netizen/passenger_flow_agent
baseline commit: 13aaa26
branch: main
```

重点参考：

- `README.md`
- `AGENTS.md`
- `docs/architecture.md`
- `docs/assistant_architecture.md`
- `docs/web_and_deployment.md`
- `docs/mobile_miniprogram.md`
- `docs/threat_model.md`
- `.github/workflows/`
- `src/metro_agent/assistant/`
- `clients/web/`
- `clients/wechat-miniprogram/`

构建经验记录：

```text
/Users/xiaobosun/work/项目/济南/1.py
/Users/xiaobosun/work/项目/济南/2.py
/Users/xiaobosun/work/项目/济南/3.py
/Users/xiaobosun/work/项目/济南/4.py
/Users/xiaobosun/work/项目/济南/5.py
```

本计划从这些材料提炼出：

- 大模型与确定性执行分离；
- 统一契约、证据和核验；
- 合成 → shadow → promotion gate；
- 本地 → 固定入口 → 小程序分层验收；
- Git/秘密/生产数据边界；
- 健康检查不能代替真实 session/任务验收；
- 云端 staging 与 7×24 生产必须明确区分。

未把上述脚本、真实资源标识、IP、AppID、账号或私有配置复制到新仓库。

## 2. OpenAI

- [GPT-5.6 官方模型指导](https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6)
- [Responses API 工具使用](https://developers.openai.com/api/docs/guides/tools)
- [Responses API 迁移](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [安全最佳实践](https://developers.openai.com/api/docs/guides/safety-best-practices)

采用结论：

- `gpt-5.6-sol` 作为质量优先基线；
- 工具型多轮 Agent 使用 Responses API；
- 推理强度显式设置并在代表性任务比较；
- 新的 Pro、多 Agent、Programmatic Tool Calling 不自动启用；
- 稳定 Schema、工具语义和评测优先于模型字符串。

## 3. 阿里云

- [阿里云百炼 SDK 与 OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/install-sdk/)
- [ECS 监控与日志](https://help.aliyun.com/zh/ecs/user-guide/monitoring-and-logging)
- [日志服务 SLS](https://help.aliyun.com/zh/sls/)

采用结论：

- Provider 层保留 OpenAI-compatible 适配；
- 云端使用 ECS/CMS/SLS 做系统与应用观测；
- 本机 Hermes 只作开发/shadow，不作云端生产依赖。

## 4. 地图与出行数据

- [高德路径规划 2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)
- [高德 Web Service 概述](https://lbs.amap.com/api/webservice/summary)
- [高德 MCP Server](https://lbs.amap.com/api/mcp-server/summary)
- [高德 URI API](https://lbs.amap.com/api/uri-api/summary)

采用结论：

- 服务器申请并持有 Web Service Key；
- 路线 API 产生可审计的距离/时长/路径证据；
- URI/官方入口用于用户点击后跳转；
- MCP 可做原型，但生产仍通过 ToolRegistry 和来源政策包装。

## 5. 移动平台

- [Android NotificationListenerService](https://developer.android.com/reference/android/service/notification/NotificationListenerService)
- [Android 通知权限](https://developer.android.com/develop/ui/compose/notifications/notification-permission)
- [Apple App Extensions](https://developer.apple.com/documentation/technologyoverviews/app-extensions)
- [Apple Share Extension 指南](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/Share.html)

采用结论：

- Android 原生 App 才可能在用户授权下监听通知；
- iOS 采用系统 Extension/Share 路径，不假设任意读取其他 App；
- Web/小程序阶段以用户主动导入和服务器数据为主。

## 6. 中国法律与监管

- [中华人民共和国个人信息保护法](https://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html)
- [个人信息保护政策法规问答（2026年1月）](https://www.cac.gov.cn/2026-01/09/c_1769688003183197.htm)
- [生成式人工智能服务管理暂行办法](https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)
- [移动互联网应用程序信息服务管理规定](https://www.cac.gov.cn/2022-06/14/c_1656821626455324.htm)
- [数据出境安全评估办法](https://www.cac.gov.cn/2022-07/07/c_1658811536396503.htm)
- [数据出境安全评估申报指南（第三版）](https://www.cac.gov.cn/2025-06/27/c_1752652339765002.htm)

采用结论：

- 精确位置和连续轨迹按敏感个人信息处理；
- 境外模型调用默认拒绝并单独评估；
- 小程序/App 上线前完成隐私影响评估、同意、撤回、删除、投诉和合规适用性判断。
