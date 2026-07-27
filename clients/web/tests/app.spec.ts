import { expect, test } from "@playwright/test"

test("shows the complete verified departure workflow", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: /明天去机场/ })).toBeVisible()
  await expect(page.getByText("确定性核验通过")).toBeVisible()
  await expect(page.locator(".leave-time").getByText("05:42", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "每一分钟都有依据" })).toBeVisible()
  await expect(page.getByText("8 项证据").or(page.getByText("证据受限问答"))).toBeVisible()
  await expect(page.getByRole("heading", { name: "每个来源的状态都可见" })).toBeVisible()
})

test("parses imported text but requires explicit confirmation", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "解析为待确认行程" }).click()
  await expect(page.getByText("CONFIRMATION REQUIRED")).toBeVisible()
  await expect(page.getByRole("heading", { name: "CA1832" })).toBeVisible()
  await page.getByRole("button", { name: /带入表单并逐项确认/ }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(page.getByLabel("航班号")).toHaveValue("CA1832")
  await expect(page.getByLabel("出发机场")).toHaveValue("HGH")
})

test("recalculates and produces reminder and action proposals", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "编辑" }).click()
  await page.getByLabel("风险偏好").selectOption("very_cautious")
  await page.getByRole("button", { name: "确认并生成建议" }).click()
  await expect(page.getByText("非常稳妥方案", { exact: false })).toBeVisible()
  await expect(page.locator(".leave-time").getByText("05:20", { exact: true })).toBeVisible()

  await page.getByRole("button", { name: "预览提醒" }).click()
  await expect(page.getByRole("button", { name: "下载日历提醒" })).toBeVisible()
  await page.getByRole("button", { name: "生成操作提案" }).click()
  await expect(page.getByRole("link", { name: /确认并打开官方地图/ })).toHaveAttribute(
    "href",
    /uri\.amap\.com/,
  )
})
