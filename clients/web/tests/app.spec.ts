import { expect, test } from "@playwright/test"

test("shows a verified synthetic departure recommendation", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "明天去机场， 应该几点出发？" })).toBeVisible()
  await expect(page.getByText("确定性核验通过")).toBeVisible()
  await expect(page.locator(".leave-time").getByText("05:15", { exact: true })).toBeVisible()
  await expect(page.getByText("合成数据 · 框架版")).toBeVisible()
})

test("recalculates after changing risk preference", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "调整行程" }).click()
  await page.getByLabel("风险偏好").selectOption("very_cautious")
  await page.getByRole("button", { name: "生成新建议" }).click()
  await expect(page.getByText("非常稳妥方案")).toBeVisible()
  await expect(page.locator(".leave-time").getByText("04:50", { exact: true })).toBeVisible()
})
