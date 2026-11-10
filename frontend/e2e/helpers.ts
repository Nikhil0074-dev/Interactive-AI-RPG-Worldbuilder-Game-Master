import { expect, Page } from "@playwright/test";
import path from "path";

export const SHOTS = path.resolve(__dirname, "../../docs/screenshots");
export const shot = async (page: Page, name: string, fullPage = false) => {
  await page.waitForTimeout(500);   // let fade-in animations settle
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage });
};

export async function playerHeaders(page: Page) {
  await page.goto("/");
  const id = await page.evaluate(() => {
    let v = localStorage.getItem("rpg_player_id");
    if (!v) { v = "p-" + crypto.randomUUID(); localStorage.setItem("rpg_player_id", v); }
    return v;
  });
  return { "X-Player-Id": id };
}

/** Creates a fully started campaign through the real API (fast path for tests that are not about the wizard). */
export async function startCampaign(page: Page, cls = "warrior", name = "The Shattered Crown") {
  const h = await playerHeaders(page);
  const cfg = { world_name: name, genre: "dark_fantasy", tone: "mysterious", difficulty: "normal", combat_enabled: true, magic_level: "high",
                party_size: "solo", art_style: "painterly_fantasy", setting: "An ancient kingdom where magic is powered by memories." };
  const { id } = await (await page.request.post("/api/campaigns", { headers: h, data: cfg })).json();
  expect((await page.request.post(`/api/campaigns/${id}/world`, { headers: h })).ok()).toBeTruthy();
  const r = await page.request.post(`/api/campaigns/${id}/character`, { headers: h, data: { name: "Aria", char_class: cls, background: "Exiled cartographer" } });
  expect(r.ok()).toBeTruthy();
  await page.goto(`/campaigns/${id}`);
  await expect(page.getByTestId("location-name")).toBeVisible();
  return { id, headers: h };
}

export const act = (page: Page, label: string | RegExp) => page.getByRole("button", { name: label }).first();
export async function doAction(page: Page, label: string | RegExp) {
  const before = await page.getByTestId("narration").count();
  await act(page, label).click();
  await expect(page.getByTestId("narration").nth(before)).toBeVisible({ timeout: 15_000 });
}
