# 微信小程序交付与发布

## 1. 当前交付

版本 `0.2.0` 完成合成数据范围内的小程序闭环：

```text
阿里云 health/capabilities
        ↓
加载或确认 TripInput
        ↓
POST /api/v1/decisions/preview
        ↓
DecisionResponse + Evidence + Verifier
        ↓
建议时间线 / 证据 / 产品边界
```

页面：

| 页面 | 责任 |
| --- | --- |
| `pages/index/index` | 建议、时间线、证据、风险/行李快速调整、提醒预览 |
| `pages/trip/trip` | 合成行程确认、客户端格式校验、提交决策 |
| `pages/settings/settings` | 固定环境选择、AppID/request 域名、health/capabilities 诊断 |
| `pages/about/about` | 隐私、数据最小化、当前/未来能力边界 |

## 2. 隐私和安全边界

- 行程、地址和决定只存在 `App.globalData`，不写入 Storage；
- Storage 只保存版本化的 `production`/`local` 枚举；
- API 主机由代码 allowlist 固定，用户不能输入任意 URL；
- 客户端不包含 AppSecret、访问令牌、数据库/模型/地图密钥；
- 合成出发地输入会在退出小程序后清除；
- 真实行程、微信登录、上传、订阅消息和预约仍未开放。

## 3. 本地验证

```bash
cd clients/wechat-miniprogram
npm run check
npm test
```

微信开发者工具：

1. 导入 `clients/wechat-miniprogram`；
2. 保持基础库与 `project.config.json` 一致；
3. 编译后检查建议页 `05:15` 合成结果；
4. 在行程页提交合成行程，确认回到建议页并重新计算；
5. 在设置页运行连接检查，确认 `synthetic`、`fake` 和计划模型；
6. 打开隐私与边界页；
7. “问题”面板必须为 0；游客模式自身的安全接口告警不计入项目代码错误。

## 4. 私有 AppID 配置

公开仓库必须保留：

```json
{"appid": "touristappid"}
```

正式 AppID 写入被 `.gitignore` 排除的
`clients/wechat-miniprogram/project.private.config.json`。不得复用
`metro-passenger-flow-agent` 的 AppID，因为上传会覆盖另一个产品的开发版本。

## 5. 微信公众平台配置

在本项目独立小程序的“开发管理 → 开发设置 → 服务器域名”中添加：

```text
request 合法域名：https://metro.9m-zx.com
```

域名不包含 `/mobility` 路径。保存后完全关闭并重新进入小程序，再在设置页运行连接检查。
浏览器可访问域名不能替代微信严格域名校验。

## 6. 上传体验版

有上传权限的开发者登录微信开发者工具后：

```bash
/Applications/wechatwebdevtools.app/Contents/MacOS/cli upload \
  --project /absolute/path/to/clients/wechat-miniprogram \
  --version 0.2.0 \
  --desc "合成行程确认、出发建议、证据与运行诊断"
```

上传前必须确认项目使用独立正式 AppID、严格域名检查开启、生产环境已选择。上传完成后在微信
公众平台设为体验版并只添加批准的体验成员。

## 7. 体验版验收

- iPhone 与 Android 各完成一次冷启动；
- 建议、行程、设置和隐私页面均可达；
- 合成行程校验能阻止错误航班号、机场代码、日期和空地址；
- API 成功、超时、5xx、422 和 request 域名未配置均有明确提示；
- 行李和三档风险偏好会触发重新计算；
- 退出并重新进入后不保留行程；
- 无屏幕、日志或上传包包含秘密或真实个人数据。

## 8. 尚未晋级的功能

下列功能需要独立后端、隐私、合规和验收工作，不能因为小程序界面完成而自动开放：

- `wx.login` 服务端身份交换和对象级授权；
- 截图/OCR 上传、删除和生命周期；
- 微信订阅消息模板、用户授权、幂等 Outbox 和取消；
- 真实航班、机场、地图、天气和事件数据；
- 网约车官方入口或预约动作；
- 微信隐私保护指引、用户协议、审核与正式发布。
