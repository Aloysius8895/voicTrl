// Screenshots, checks and a demo video of the built app, for design review.
//
//   npm run build && npm run render          -> design-review/*.png, demo.webm, render-report.json
//   npm run render -- --serve                -> only serve the built app at http://127.0.0.1:5310
//
// Uses the local Chrome through playwright-core. Every request that leaves 127.0.0.1 is blocked
// and counted, so the report also proves the app makes no outside calls.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright-core";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "design-review");
const serveOnly = process.argv.includes("--serve");
const port = serveOnly ? 5310 : 5321;
const base = `http://127.0.0.1:${port}`;
const CHROME = [
	"C:/Program Files/Google/Chrome/Application/chrome.exe",
	"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
].find((p) => existsSync(p));

if (!existsSync(join(root, "dist", "index.html"))) {
	console.error("dist/ is missing: run `npm run build` first");
	process.exit(1);
}

const server = spawn(process.execPath, [join(root, "node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
	cwd: root,
	stdio: serveOnly ? "inherit" : "pipe",
});
process.on("exit", () => server.kill());

async function waitForServer() {
	for (let i = 0; i < 80; i++) {
		try {
			if ((await fetch(base)).ok) return;
		} catch {}
		await new Promise((r) => setTimeout(r, 250));
	}
	throw new Error(`preview server did not start on ${base}`);
}

await waitForServer();
if (serveOnly) {
	console.log(`\n  voicTrl sample app: ${base}\n  Press Ctrl+C to stop.\n`);
	await new Promise(() => {});
}

if (!CHROME) throw new Error("Google Chrome not found");
// Clear the previous run's output, but keep the hand-written README.
mkdirSync(out, { recursive: true });
for (const f of readdirSync(out)) {
	if (f !== "README.md") rmSync(join(out, f), { recursive: true, force: true });
}

const checks = [];
const shots = [];
const blocked = [];
const errors = [];
const check = (ok, what) => {
	checks.push({ ok: Boolean(ok), what });
	console.log(`${ok ? "PASS" : "FAIL"}  ${what}`);
};

const browser = await chromium.launch({ executablePath: CHROME });
const MOBILE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const DESKTOP = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };

async function open(device, query, extra = {}) {
	const context = await browser.newContext({ ...device, ...extra });
	await context.route("**/*", (route) => {
		const url = route.request().url();
		if (url.startsWith(base) || url.startsWith("data:") || url.startsWith("blob:")) return route.continue();
		blocked.push(url);
		return route.abort();
	});
	const page = await context.newPage();
	page.on("pageerror", (e) => errors.push(`${query}: ${e.message}`));
	page.on("console", (m) => m.type() === "error" && errors.push(`${query}: ${m.text()}`));
	await page.goto(`${base}/${query}`, { waitUntil: "networkidle" });
	await page.evaluate(() => document.fonts.ready);
	return { context, page };
}

async function shot(page, name, note, { at, fullPage = false } = {}) {
	if (at) {
		await page.locator(at).first().evaluate((el) => el.scrollIntoView({ block: "start", behavior: "instant" }));
		await page.waitForTimeout(150);
	}
	await page.screenshot({ path: join(out, `${name}.png`), fullPage, animations: "disabled" });
	shots.push({ file: `${name}.png`, note });
}

async function noSideScroll(page, label) {
	const { sw, w } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: window.innerWidth }));
	check(sw <= w, `${label}: no sideways scroll at ${w}px (page is ${sw}px wide)`);
}

// ── Phone, one screen per moment of the sample run ──────────────────────────
{
	const { context, page } = await open(MOBILE, "?scene=idle");
	await noSideScroll(page, "phone idle");
	check(await page.evaluate(() => document.fonts.check('600 16px "Urbanist Variable"')), "Urbanist font loaded from the app itself");
	check(await page.getByRole("button", { name: "Call your assistant" }).isVisible(), "idle: the call button is on the first screen");
	await shot(page, "01-phone-idle", "Before the call: one big call button");
	await shot(page, "02-phone-idle-task", "Before the call: empty task, with an example of what to say", { at: "#task" });
	const small = await page.evaluate(() =>
		[...document.querySelectorAll("button, a.pill")]
			.filter((b) => b.offsetParent !== null)
			.map((b) => ({ t: b.textContent?.trim() || b.getAttribute("aria-label"), h: b.getBoundingClientRect().height }))
			.filter((b) => b.h < 44),
	);
	check(small.length === 0, `phone: every button is at least 44px tall${small.length ? ` (too small: ${JSON.stringify(small)})` : ""}`);
	await context.close();
}

for (const [scene, name, note, at] of [
	["listening", "03-phone-listening", "On the call: the assistant listens, last two lines as subtitles", null],
	["waking", "04-phone-waking", "Step 2 running: the tool the assistant picked and its progress", "#task"],
	["building", "05-phone-building", "Step 4 running: Claude Code builds the page on Laptop B", '.step[data-state="executing"]'],
	["confirm", "06-phone-confirm", "Last step waits for you: Confirm or Cancel", '.step[data-state="needs-you"]'],
	["confirm", "07-phone-devices", "Devices: both laptops online, one thing needs you", "#devices"],
]) {
	const { context, page } = await open(MOBILE, `?scene=${scene}`);
	await noSideScroll(page, `phone ${scene}`);
	await shot(page, name, note, { at });
	if (scene === "building") {
		check((await page.locator('.step[data-state="executing"]').count()) === 1, "building: exactly one step is executing");
		check(await page.getByText("buildOnDevice").isVisible(), "building: the tool name is shown");
	}
	if (scene === "confirm" && name.includes("confirm")) {
		await page.getByRole("button", { name: "Confirm" }).click();
		await page.waitForTimeout(150);
		check(await page.locator(".task .panel-head .chip", { hasText: "Done" }).isVisible(), "confirm: pressing Confirm finishes the task");
	}
	await context.close();
}

{
	const { context, page } = await open(MOBILE, "?scene=done&tab=evidence");
	await noSideScroll(page, "phone done");
	await shot(page, "08-phone-evidence", "Evidence of the run: wake times, file hash, run code", { at: "#devices" });
	check((await page.locator(".tile--evidence:not([data-empty])").count()) === 4, "done: all four pieces of evidence are filled in");
	await shot(page, "09-phone-done", "All five steps done", { at: "#task" });
	await shot(page, "10-phone-full-page", "The whole page on a phone, after the run", { fullPage: true });
	await context.close();
}

// ── Phone, live: press Call, hang up ─────────────────────────────────────────
{
	const { context, page } = await open(MOBILE, "");
	await page.getByRole("button", { name: "Call your assistant" }).click();
	await page.getByRole("button", { name: "Hang up" }).waitFor({ timeout: 4000 });
	check(true, "live: pressing Call starts the call (Hang up appears)");
	await page.waitForTimeout(1600);
	await page.getByRole("button", { name: "Hang up" }).click();
	check(await page.getByRole("button", { name: "Call again" }).isVisible(), "live: Hang up ends the call and offers Call again");
	await context.close();
}

// ── Wide screen ──────────────────────────────────────────────────────────────
for (const [scene, name, note, at] of [
	["idle", "11-desktop-idle", "Wide screen, before the call", null],
	["building", "12-desktop-building", "Wide screen: call, steps and devices side by side", ".board"],
	["confirm", "13-desktop-confirm", "Wide screen: waiting for your confirmation", ".board"],
]) {
	const { context, page } = await open(DESKTOP, `?scene=${scene}`);
	await noSideScroll(page, `desktop ${scene}`);
	await shot(page, name, note, { at });
	if (scene === "building") {
		const tops = await page.evaluate(() => ["#call", "#task", "#devices"].map((s) => Math.round(document.querySelector(s).getBoundingClientRect().top)));
		check(new Set(tops).size === 1, `desktop: the three panels sit side by side (tops ${tops.join(", ")})`);
	}
	await context.close();
}

// ── Installable app ──────────────────────────────────────────────────────────
{
	const { context, page } = await open(MOBILE, "");
	const manifest = await page.evaluate(async () => {
		const href = document.querySelector('link[rel="manifest"]')?.getAttribute("href");
		return href ? (await fetch(href)).json() : null;
	});
	check(manifest?.name === "voicTrl" && manifest?.display === "standalone", "PWA: manifest says voicTrl, full screen");
	check(manifest?.icons?.some((i) => i.sizes === "512x512"), "PWA: has a 512px icon");
	const sw = await page.evaluate(() => Promise.race([navigator.serviceWorker.ready.then(() => true), new Promise((r) => setTimeout(() => r(false), 6000))]));
	check(sw, "PWA: service worker is running (works offline after the first visit)");
	await context.close();
}

// ── Demo video: one whole sample run on a phone ──────────────────────────────
{
	const videoDir = join(out, "_video");
	const { context, page } = await open(MOBILE, "", { recordVideo: { dir: videoDir, size: { width: 390, height: 844 } } });
	await page.waitForTimeout(800);
	await page.getByRole("button", { name: "Call your assistant" }).click();
	await page.waitForTimeout(9500);
	await page.locator("#task").evaluate((el) => el.scrollIntoView({ block: "start", behavior: "smooth" }));
	await page.waitForTimeout(13000);
	await page.locator('.step[data-state="executing"]').first().evaluate((el) => el.scrollIntoView({ block: "center", behavior: "smooth" }));
	await page.getByRole("button", { name: "Confirm" }).waitFor({ timeout: 40000 });
	await page.locator('.step[data-state="needs-you"]').evaluate((el) => el.scrollIntoView({ block: "center", behavior: "smooth" }));
	await page.waitForTimeout(2500);
	await page.getByRole("button", { name: "Confirm" }).click();
	await page.waitForTimeout(1500);
	await page.locator("#devices").evaluate((el) => el.scrollIntoView({ block: "start", behavior: "smooth" }));
	await page.waitForTimeout(1200);
	await page.getByRole("tab", { name: /Evidence/ }).click();
	await page.waitForTimeout(2500);
	await context.close();
	const file = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
	renameSync(join(videoDir, file), join(out, "demo.webm"));
	rmSync(videoDir, { recursive: true, force: true });
	shots.push({ file: "demo.webm", note: "One whole sample run on a phone (about 45 s)" });
	check(true, "video: recorded a whole sample run");
}

await browser.close();
check(blocked.length === 0, `no requests left this computer${blocked.length ? `: ${[...new Set(blocked)].join(", ")}` : ""}`);
check(errors.length === 0, `no errors in the page${errors.length ? `: ${errors.join(" | ")}` : ""}`);

const failed = checks.filter((c) => !c.ok).length;
writeFileSync(join(out, "render-report.json"), JSON.stringify({ when: new Date().toISOString(), passed: checks.length - failed, failed, checks, shots }, null, 2));
console.log(`\n${checks.length - failed}/${checks.length} checks passed. Output: ${out}`);
server.kill();
process.exit(failed ? 1 : 0);
