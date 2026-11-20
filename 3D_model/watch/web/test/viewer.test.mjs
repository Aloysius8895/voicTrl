// Opens index.html in headless Chrome, the way a person double-clicks it, and checks what they would see.
// Needs playwright-core and a Chromium build; both paths can be overridden with PLAYWRIGHT_CORE and CHROME_PATH.
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const local = process.env.LOCALAPPDATA ?? "";
const { chromium } = createRequire(import.meta.url)(
  process.env.PLAYWRIGHT_CORE ?? path.join(local, "hairline-look", "node_modules", "playwright-core"),
);
const chrome =
  process.env.CHROME_PATH ?? path.join(local, "ms-playwright", "chromium-1223", "chrome-win64", "chrome.exe");
const pageUrl = pathToFileURL(path.join(here, "..", "index.html")).href;
const shots = path.join(here, "shots");

let browser;
let page;
const problems = [];

before(async () => {
  mkdirSync(shots, { recursive: true });
  browser = await chromium.launch({ executablePath: chrome, headless: true, args: ["--ignore-gpu-blocklist"] });
  page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on("pageerror", (error) => problems.push(String(error)));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.setDefaultTimeout(5000);
  await page.goto(pageUrl);
  await page.waitForFunction(() => window.watchViewer?.ready === true, null, { timeout: 30000 });
});

after(async () => {
  await browser?.close();
});

test("the page shows the whole watch without errors", async () => {
  const parts = await page.evaluate(() => window.watchViewer.parts());
  assert.equal(parts.length, 48, "Blender reports 48 mesh objects in the WATCH collection");
  for (const name of ["SM_case", "SM_glass", "SM_display_screen", "SM_core_pcb", "SM_base_pcb", "SM_cradle", "SM_strap"]) {
    assert.ok(parts.includes(name), `${name} is in the scene`);
  }
  await page.screenshot({ path: path.join(shots, "assembled.png") });
  assert.deepEqual(problems, []);
});

// How far a part sits from its assembled place, in millimetres, in the model's own axes (z = out of the screen).
const offsets = (names) =>
  page.evaluate((list) => Object.fromEntries(list.map((n) => [n, window.watchViewer.offsetMm(n)])), names);

function assertNear(actual, expected, label) {
  for (let i = 0; i < 3; i++) {
    assert.ok(Math.abs(actual[i] - expected[i]) < 0.01, `${label}: got [${actual}], expected [${expected}]`);
  }
}

test("the explode slider takes the watch apart and puts it back", async () => {
  const names = ["SM_glass", "SM_core_pcb", "SM_btn_function", "SM_screw_1", "SM_strap"];
  await page.locator("#explode").fill("1");
  const apart = await offsets(names);
  // distances from blender/spec.py (EX). The button rides on the case (22 up) and moves 8 outwards.
  assertNear(apart.SM_glass, [0, 0, 52], "glass");
  assertNear(apart.SM_core_pcb, [0, 0, 0], "CoreBoard stays put");
  assertNear(apart.SM_btn_function, [8, 0, 22], "Function button");
  assertNear(apart.SM_screw_1, [0, 0, -38], "screw");
  assertNear(apart.SM_strap, [0, 0, -76], "strap");
  await page.screenshot({ path: path.join(shots, "apart.png") });

  await page.locator("#explode").fill("0");
  const together = await offsets(names);
  for (const name of names) assertNear(together[name], [0, 0, 0], `${name} back in place`);
  assert.deepEqual(problems, []);
});

test("clicking a part says what it is, clicking empty space clears it", async () => {
  const box = await page.locator("#stage canvas").boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2); // the middle of the view is the screen glass
  assert.equal(await page.locator("#part-name").textContent(), "盖板玻璃");
  assert.equal(await page.locator("#part-id").textContent(), "SM_glass");
  await page.screenshot({ path: path.join(shots, "picked.png") });

  await page.mouse.click(box.x + 30, box.y + box.height / 2);
  assert.equal(await page.locator("#part").isHidden(), true);
  assert.deepEqual(problems, []);
});

test("the strap switch hides our cradle and strap, leaving the module", async () => {
  const shown = (name) => page.evaluate((n) => window.watchViewer.isShown(n), name);
  await page.locator("#wearable").uncheck();
  for (const name of ["SM_cradle", "SM_strap", "SM_buckle", "SM_strap_keeper"]) {
    assert.equal(await shown(name), false, `${name} is hidden`);
  }
  assert.equal(await shown("SM_case"), true);
  assert.equal(await shown("SM_base_marks_white"), true, "the back markings stay");
  await page.locator("#wearable").check();
  assert.equal(await shown("SM_strap"), true);
  assert.deepEqual(problems, []);
});
