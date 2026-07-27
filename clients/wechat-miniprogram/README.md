# 行前微信小程序

该目录是一个可直接导入微信开发者工具的原生小程序工程。当前公开配置使用
`touristappid`；正式 AppID 只能写入 Git 已忽略的 `project.private.config.json`，不得提交到
仓库。

## 已实现页面

- **建议**：结论优先的时间线、证据卡片、风险偏好、托运行李和提醒预览；
- **行程**：确认/修改合成航班、机场、航站楼、起飞时间、合成出发地和偏好；
- **设置**：固定阿里云入口、本机调试入口、AppID/request 域名和能力契约诊断；
- **隐私与边界**：说明数据最小化、运行内存、不开放的真实数据/提醒/预约能力。

小程序与 Web 共用 `/api/v1` 合约，生产 API 为
`https://metro.9m-zx.com/mobility`。客户端不会计算权威出发时间，也不会保存模型密钥、
AppSecret、数据库密码、令牌或真实行程。

## 开发

```bash
npm run check
npm test
```

用微信开发者工具导入本目录，点击“编译”。默认会直接调用阿里云合成 API。

本机调试可以在“设置”页选择 `http://127.0.0.1:8000`，并只在未跟踪的开发者工具本地设置中
临时关闭域名校验。真机、体验版和正式版本必须：

1. 使用本项目独立 AppID，不能复用客流智能体 AppID；
2. 把 `https://metro.9m-zx.com` 配置为 request 合法域名；
3. 保持 `project.config.json` 的 `urlCheck: true`；
4. 恢复“阿里云正式入口”并运行连接检查；
5. 完成 Android/iPhone 冷启动、网络切换和失败路径验收。

行程只保存在 `App.globalData`。Storage 只允许保存
`{ configVersion, environment }`，退出小程序后不会保留航班或地址。

正式上传流程及仍受门禁约束的内容见
[`../../docs/wechat_miniprogram.md`](../../docs/wechat_miniprogram.md)。
