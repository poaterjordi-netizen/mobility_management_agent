import { expect, test } from "@playwright/test"

test("shows the complete verified departure workflow", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: /明天去机场/ })).toBeVisible()
  await expect(page.getByText("现在还没有使用任何演示行程代替你的输入")).toBeVisible()
  await page.getByRole("button", { name: "直接查看这条测试建议" }).click()
  await expect(page.getByText("确定性核验通过")).toBeVisible()
  await expect(page.getByRole("heading", { name: "北京交通大学 → 大连理工大学完整旅程" })).toBeVisible()
  await expect(page.getByText("00:43–00:58")).toBeVisible()
  await expect(page.getByRole("heading", { name: "每一分钟都有依据" })).toBeVisible()
  await expect(page.getByText("8 项证据").or(page.getByText("证据受限问答"))).toBeVisible()
  await expect(page.getByRole("heading", { name: "每个来源的状态都可见" })).toBeVisible()
})

test("parses imported text but requires explicit confirmation", async ({ page }) => {
  await page.goto("/")
  await page.getByPlaceholder("例如：北京交通大学（海淀校区）").fill("杭州市滨江区")
  await page
    .getByPlaceholder(/例如：【国航】/)
    .fill("CA1832 杭州萧山机场 T4 → 北京首都机场，2026/8/1 09:20 起飞")
  await page.getByRole("button", { name: "解析航班通知" }).click()
  await expect(page.getByText("STEP 3 · CONFIRM")).toBeVisible()
  await expect(page.getByRole("heading", { name: "CA1832" })).toBeVisible()
  await expect(page.getByText("现在还没有使用任何演示行程代替你的输入")).toBeVisible()
  await page.getByRole("button", { name: /确认识别结果并生成建议/ }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(page.getByLabel("航班号")).toHaveValue("CA1832")
  await expect(page.getByLabel("出发机场", { exact: true })).toHaveValue("HGH")
  await expect(page.getByRole("textbox", { name: /^出发地/ })).toHaveValue("杭州市滨江区")
})

test("recalculates and produces reminder and action proposals", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "直接查看这条测试建议" }).click()
  await page.getByRole("button", { name: "编辑" }).click()
  await page.getByLabel("风险偏好").selectOption("very_cautious")
  await page.getByRole("button", { name: "确认并生成建议" }).click()
  await expect(page.getByText("非常稳妥方案", { exact: false })).toBeVisible()

  await page.getByRole("button", { name: "预览提醒" }).click()
  await expect(page.getByRole("button", { name: "下载日历提醒" })).toBeVisible()
  await page.getByRole("button", { name: "生成操作提案" }).click()
  await expect(page.getByRole("link", { name: /确认并打开官方地图/ })).toHaveAttribute(
    "href",
    /uri\.amap\.com/,
  )
})
