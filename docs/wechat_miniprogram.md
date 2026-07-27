# 微信小程序交付与发布

## 1. 当前交付

版本 `0.4.2` 与 Web 共用完整 API。首页不再自动载入旧演示数据，用户可按“出发地、已订
航班通知、字段确认”三步生成建议，也可一键载入北京交大到大连理工的完整验收行程：

```text
短信 / ICS / 截图
  → TripCandidate（敏感字段遮盖）
  → 用户逐项确认 TripInput
  → 航班 / 机场 / 路线 / 天气 / 事件上下文
  → Decision + Evidence + Verifier
  → 提醒预览 / 地图提案 / 证据问答 / 删除
```

| 页面 | 责任 |
| --- | --- |
| `pages/index/index` | 建议、上下文、分项、证据、提醒、地图提案、问答、清除 |
| `pages/trip/trip` | 文本/ICS/截图导入、候选确认、完整行程与同意设置 |
| `pages/settings/settings` | AppID/request 域名、health/capabilities/source registry |
| `pages/about/about` | 隐私、数据最小化、已开放与禁止能力 |

## 2. 隐私和安全

- 行程、坐标、决定和候选只存在 `App.globalData`，不写入 Storage；
- Storage 只保存 `{configVersion, environment}`；
- API 地址来自固定 allowlist，用户不能输入 URL；
- 截图最大 5 MB，由服务端本地 Tesseract 临时识别，响应后删除；
- 候选始终 `needs_user_confirmation=true`；
- 地图和模型分别需要用户同意，且密钥只在服务端；
- 地图动作先显示参数，再二次确认复制高德官方 URI；
- 不自动下单、付款、抓取其他 App 或收集 AppSecret。

## 3. 本地验证

```bash
cd clients/wechat-miniprogram
npm run check
npm test
find miniprogram scripts tests -name '*.js' -print0 | xargs -0 -n1 node --check
```

开发者工具中至少验证：

1. 首页右上角显示“小程序 v0.4.2”，空会话不会出现旧演示行程；
2. 点击“北京交大 → 首都机场 → 大连 → 大连理工”一键测试，生成完整时间链；
3. 文本和 ICS 生成候选，点击确认后才带入表单；
4. PNG/JPEG 截图走 OCR，非法类型/过大文件显示明确错误；
5. 三档风险、托运行李、无障碍和事件输入会重算；
6. 提醒、地图提案和证据问答完成；
7. 清空会话后运行内存被清理；
8. “问题”面板无项目错误。

## 4. AppID 与合法域名

公共仓库必须保留：

```json
{"appid": "touristappid"}
```

正式 AppID 位于被 `.gitignore` 排除的
`clients/wechat-miniprogram/project.private.config.json`。不得复用客流智能体 AppID。

微信公众平台配置：

```text
request 合法域名：https://metro.9m-zx.com
```

不能包含 `/mobility`。保存后清理开发者工具网络缓存并重新编译，保持 `urlCheck: true`。

## 5. CLI 预览与上传

```bash
WECHAT_CLI=/Applications/wechatwebdevtools.app/Contents/MacOS/cli
PROJECT=/Users/xiaobosun/software/mobility-management-agent/clients/wechat-miniprogram

"$WECHAT_CLI" islogin
"$WECHAT_CLI" cache --clean network --project "$PROJECT" --lang zh
"$WECHAT_CLI" preview \
  --project "$PROJECT" \
  --qr-format image \
  --qr-output /safe/local/path/mobility-v0.4.2-preview.png \
  --lang zh
"$WECHAT_CLI" upload \
  --project "$PROJECT" \
  --version 0.4.2 \
  --desc "三步输入与北京交大到大连理工完整行程建议" \
  --lang zh
```

本产品首次体验版选择和体验成员配置已经完成。按当前公众平台配置，后续版本只需使用官方
CLI 上传，无需对每个版本重复点击“设为体验版”。`0.4.2` 已于 2026-07-27 使用独立
AppID 完成官方 CLI 编译、预览和上传；最终包约 87.0 KB，开发者工具复编译为 0 错误、
0 警告。

## 6. 体验版验收

- iPhone 与 Android 各完成一次冷启动；
- 四个页面均可达；
- request 合法域名严格检查开启；
- 文本、ICS、截图和手工输入路径均通过；
- 422、5xx、超时、OCR 不可用和域名错误均有可理解提示；
- 提醒不会静默发送；地图不会静默打开或下单；
- 退出重进不保留个人行程；
- 上传包、日志和 Git 中无秘密或真实行程。

## 7. 平台依赖能力

真实微信订阅消息不是纯代码能力。启用前必须具备：

- 公众平台审核通过的订阅消息模板；
- 服务端 AppSecret/Access Token 管理；
- 用户单次订阅授权；
- 幂等 Outbox、重试、取消和投递状态；
- 正式隐私保护指引与用户协议。

条件不足时，当前 T-24 ICS/复制提醒是明确、可用且不夸大的降级路径。
