# 行前微信小程序

可直接导入微信开发者工具的原生小程序工程。公共配置使用 `touristappid`；正式 AppID 只写入
Git 忽略的 `project.private.config.json`。

## v0.3.0 功能

- 短信/通知、ICS 和截图 OCR 行程导入；
- 候选字段、遮盖项、警告和强制用户确认；
- 航班、机场、目的地、时间、出发地、坐标、行李、无障碍和风险偏好编辑；
- 对实时地图与模型解释分别授权；
- 可核验出发时间、道路/机场/天气上下文、分钟分项与 8 类证据；
- T-24 提醒预览和复制；
- 高德官方链接参数预览、二次确认和复制；
- 证据受限问答；
- 数据来源、能力、AppID 和 request 合法域名诊断；
- 会话清除和完整隐私边界说明。

小程序与 Web 共用 `/api/v1`，生产 API 为
`https://metro.9m-zx.com/mobility`。客户端不持有模型密钥、AppSecret、数据库密码或访问
令牌；行程只存在于 `App.globalData`，Storage 只保存版本化的环境枚举。

## 开发与发布前检查

```bash
npm run check
npm test
```

真机、体验版和正式版本必须：

1. 使用本项目独立 AppID；
2. 将 `https://metro.9m-zx.com` 配置为 request 合法域名；
3. 保持 `project.config.json` 的 `urlCheck: true`；
4. 恢复“阿里云正式入口”并运行连接/数据源检查；
5. 完成短信、ICS、截图、提醒、地图二次确认、删除和失败路径验收；
6. Android 与 iPhone 各完成一次冷启动。

微信订阅消息真实投递需要平台模板、AppSecret、一次性用户订阅授权和服务端幂等 Outbox；
这些条件不齐备时，产品使用 T-24 日历/复制提醒，不声称已经发送订阅消息。

完整操作见 [`../../docs/wechat_miniprogram.md`](../../docs/wechat_miniprogram.md)。
