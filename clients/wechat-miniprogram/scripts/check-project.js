const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..")
const project = JSON.parse(fs.readFileSync(path.join(root, "project.config.json"), "utf8"))
const app = JSON.parse(
  fs.readFileSync(path.join(root, project.miniprogramRoot, "app.json"), "utf8"),
)

const requiredPageFiles = [".js", ".json", ".wxml", ".wxss"]
const missing = []

if (project.miniprogramRoot !== "miniprogram/") {
  throw new Error("project.config.json must isolate source under miniprogram/")
}
if (project.setting.urlCheck !== true) {
  throw new Error("request-domain validation must stay enabled in the committed project")
}
if (!Array.isArray(app.pages) || app.pages.length < 4) {
  throw new Error("Complete Mini Program must declare suggestion, trip, settings, and about pages")
}

for (const page of app.pages) {
  if (!/^pages\/[a-z-]+\/[a-z-]+$/.test(page)) {
    throw new Error(`Invalid Mini Program page path: ${page}`)
  }
  for (const extension of requiredPageFiles) {
    const candidate = path.join(root, project.miniprogramRoot, `${page}${extension}`)
    if (!fs.existsSync(candidate)) missing.push(candidate)
  }
  JSON.parse(
    fs.readFileSync(path.join(root, project.miniprogramRoot, `${page}.json`), "utf8"),
  )
}

if (project.appid !== "touristappid") {
  throw new Error("Framework repository must not contain a real WeChat AppID")
}
if (missing.length) {
  throw new Error(`Missing Mini Program files:\n${missing.join("\n")}`)
}

const declaredPages = new Set(app.pages)
for (const tab of (app.tabBar && app.tabBar.list) || []) {
  if (!declaredPages.has(tab.pagePath)) {
    throw new Error(`tabBar page is not declared: ${tab.pagePath}`)
  }
}

const sourceRoot = path.join(root, project.miniprogramRoot)
const configSource = fs.readFileSync(path.join(sourceRoot, "config.js"), "utf8")
if (!configSource.includes("https://metro.9m-zx.com/mobility")) {
  throw new Error("Production API must use the fixed Alibaba Cloud HTTPS ingress")
}
if (!configSource.includes('dataScope: "mixed"')) {
  throw new Error("Runtime config must declare the mixed-source capability boundary")
}

const forbidden = [
  /appsecret\s*[:=]\s*["'][^"']+/i,
  /(?:access[_-]?token|password|private[_-]?key)\s*[:=]\s*["'][^"']{8,}/i,
  /BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY/,
]
const storageWriters = []
for (const candidate of fs.readdirSync(sourceRoot, { recursive: true })) {
  const fullPath = path.join(sourceRoot, candidate)
  if (!fs.statSync(fullPath).isFile()) continue
  const source = fs.readFileSync(fullPath, "utf8")
  if (/wx\.setStorage(?:Sync)?\s*\(/.test(source)) {
    storageWriters.push(path.relative(sourceRoot, fullPath))
  }
  for (const pattern of forbidden) {
    if (pattern.test(source)) {
      throw new Error(`Possible secret material in ${path.relative(root, fullPath)}`)
    }
  }
}
if (storageWriters.join(",") !== "config.js") {
  throw new Error(
    `Only config.js may write non-sensitive runtime settings; found: ${storageWriters.join(",")}`,
  )
}

console.log(
  `Mini Program structure OK: ${app.pages.length} pages, strict domains, governed mixed-source boundary`,
)
