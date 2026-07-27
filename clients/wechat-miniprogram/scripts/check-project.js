const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..")
const project = JSON.parse(fs.readFileSync(path.join(root, "project.config.json"), "utf8"))
const app = JSON.parse(
  fs.readFileSync(path.join(root, project.miniprogramRoot, "app.json"), "utf8"),
)

const requiredPageFiles = [".js", ".json", ".wxml", ".wxss"]
const missing = []

for (const page of app.pages) {
  for (const extension of requiredPageFiles) {
    const candidate = path.join(root, project.miniprogramRoot, `${page}${extension}`)
    if (!fs.existsSync(candidate)) missing.push(candidate)
  }
}

if (project.appid !== "touristappid") {
  throw new Error("Framework repository must not contain a real WeChat AppID")
}
if (missing.length) {
  throw new Error(`Missing Mini Program files:\n${missing.join("\n")}`)
}

console.log(`Mini Program structure OK: ${app.pages.length} page(s), synthetic framework`)
