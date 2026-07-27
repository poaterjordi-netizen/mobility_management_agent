# 0.4.0 真实数据调试记录

记录日期：2026-07-27（Asia/Shanghai）

## 已执行

- 后端 `22 passed`，覆盖公共 HTTP allowlist、缓存、ADS-B 单位/时间戳/空间绑定、METAR、官方通告；
- Ruff 全仓通过；
- Web Biome、TypeScript、生产构建通过；
- Playwright 3 条完整纵向流程通过；
- 微信小程序结构检查和 12 项 Node 测试通过；
- OpenAPI 与 TypeScript 类型重新生成；
- `scripts/check_live_sources.py` 完成真实联网只读诊断。
- `npm audit --omit=dev` 为 0；开发期 `openapi-typescript` 的 Redocly 1.x 依赖仍报告 4 个
  DoS 类高危告警，仅处理仓库内受信任的 OpenAPI 文件，等待上游兼容升级，不进入生产镜像。

## 真实联网观测

2026-07-27 15:24 中国标准时间：

- AviationWeather.gov 返回 `ZBAA` 07:00Z 的 VFR METAR，温度 34°C、风速 10 kt；
- adsb.lol 返回上海浦东周边 250 海里 36 架航空器；
- 样例呼号 `CCA1506`、`CCA4228`、`CCA755`、`CCA8333`；
- 对随机样例呼号再次查询可返回经纬度、高度、地速、航向和最近信号时间。

联网结果不进入单元测试 fixture，也不包含个人行程。普通 CI 不调用真实供应商，以避免配额、
网络和供应商波动造成不稳定。

## 已知边界

- 没有获权的航班计划/登机口商业接口，因此计划时间仍由用户确认，值机/登机采用保守规则；
- 没有高德 Web Service Key，因此真实路线 ETA 和拥堵尚未启用；
- ADS-B 是当前航空器遥测，不能用于未来航班时刻表；
- METAR 是机场当前观测，未来时段由 Open-Meteo 预报承担；
- 官方交通通告当前采用人工审核的版本化登记，不做任意网页抓取；
- 微信订阅消息仍未配置模板/AppSecret，使用日历/复制预览；
- 不开发原生 App。
