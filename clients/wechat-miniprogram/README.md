# 微信小程序框架

该目录可直接由微信开发者工具导入。当前使用 `touristappid`，仅支持本地预览；正式上传前必须在微信公众平台注册独立小程序并替换 `project.config.json` 中的 `appid`。

## 当前边界

- 仅展示合成航班和确定性出发建议；
- 与 Web 共用 `/api/v1` 合约；
- 默认生产 API 为 `https://metro.9m-zx.com/mobility`；
- 不读取微信、携程、航旅纵横等私有数据；
- 不预约车辆、不付款、不保存行程。

## 开发

```bash
npm run check
npm test
```

如果需要连接另一套服务，在微信开发者工具的本地设置中临时关闭域名校验，并修改 `miniprogram/config.js`。真机及正式版本必须在微信公众平台配置 HTTPS request 合法域名。
