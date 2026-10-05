import { chromium } from "playwright-core";
import { readdirSync } from "node:fs";

// End-to-end check of the whole judge flow in a real browser (every page, every tab, upload, case exports, sealed-pack
// tampering). Usage:  npm i playwright-core && BASE=https://sutradhar-one-red.vercel.app CHROME=/path/to/chrome node scripts/e2e-judge-flow.mjs
const BASE = process.env.BASE ?? "http://localhost:4173";
const exe = process.env.CHROME ?? "/usr/bin/google-chrome-stable";
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox", "--disable-web-security"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 160)}`); });

const results = [];
async function check(name, fn) {
  const t0 = Date.now();
  try { await fn(); results.push(["PASS", name, Date.now() - t0]); }
  catch (e) { results.push(["FAIL", name, `${e.message.split("\n")[0].slice(0, 220)}`]); await page.screenshot({ path: `fail_${results.length}.png` }).catch(() => {}); }
}
const go = (hash) => page.goto(`${BASE}/#${hash}`).then(() => page.waitForTimeout(300));
const T = { timeout: 60_000 };
const WAKE = { timeout: 180_000 };

await check("home: start the tour lands on the guide", async () => {
  await page.goto(`${BASE}/#/`);
  await page.getByRole("button", { name: /Start the 8-minute tour/ }).click(WAKE);
  await page.waitForURL(/#\/guide/, WAKE);
  await page.getByText(/0 of 8 core checks done/).waitFor(T);
});

await check("console: leads load, first lead selected, 100% grade A", async () => {
  await go("/console");
  await page.locator(".lead").first().waitFor(T);
  if ((await page.locator(".lead").count()) < 10) throw new Error("expected >= 10 leads");
  await page.locator(".big-p").first().waitFor(T);
  const p = await page.locator(".big-p").first().innerText();
  if (p.trim() !== "100%") throw new Error(`score ${p}`);
});

const tab = (name) => page.getByRole("tab", { name, exact: true });
await check("lead tabs: why / what-if / evidence / network / path / timeline / members", async () => {
  await go("/console?lead=bc1q5frsvq");
  await page.locator(".big-p").first().waitFor(T);
  await tab("Why").click(); await page.locator(".contrib").getByText(/About 95% of its funds/).waitFor(T);
  await tab("What-if").click(); await page.getByText(/Resetting|would move from/).first().waitFor(T);
  await tab("Evidence").click(); await page.locator(".tx").first().waitFor(T);
  await page.getByRole("button", { name: "Replay" }).first().click();
  await tab("Network").click(); await page.getByRole("cell", { name: "40.94.238.111" }).waitFor(T);
  await tab("Path to seed").click(); await page.locator(".stat").getByText(/this wallet is itself on the watchlist/).waitFor(T);
  await tab("Timeline & flows").click(); await page.locator("svg.sankey").waitFor(T);
  await tab("Members").click(); await page.locator(".members code").first().waitFor(T);
  if ((await page.locator(".members code").count()) !== 8) throw new Error("expected 8 member addresses");
});

await check("deep link: 3-hop path to a seed is drawn", async () => {
  await go("/console?lead=bc1q9506uy&tab=path");
  await page.locator(".pathnode").first().waitFor(T);
  if ((await page.locator(".pathnode").count()) !== 4) throw new Error("expected 4 path nodes");
  await page.locator(".pathnode.seed").waitFor(T);
});

await check("investigate graph renders", async () => {
  await go("/console?lead=bc1q5frsvq&tab=evidence");
  await page.getByRole("button", { name: /Investigate graph/ }).last().click(T);
  await page.getByRole("heading", { name: "Investigate", exact: true }).waitFor(T);
});

const search = async (q) => {
  const box = page.getByLabel("Search the dataset");
  await box.fill(q);
  return page.getByRole("option");
};
await check("search: IP opens a dossier", async () => {
  await go("/console"); await page.locator(".lead").first().waitFor(T);
  const opts = await search("40.94.238.111"); await opts.first().click(T);
  await page.getByRole("heading", { name: /IP dossier/ }).waitFor(T);
});
await check("search: AS number opens a page and an IP chip drills in", async () => {
  await go("/console"); await page.locator(".lead").first().waitFor(T);
  const opts = await search("AS8075"); await opts.first().click(T);
  await page.getByRole("heading", { name: /AS number dossier/ }).waitFor(T);
  await page.locator(".data-table .chip").first().click();
  await page.getByRole("heading", { name: /IP dossier/ }).waitFor(T);
});
await check("search: transaction prefix opens a lead; address opens a dossier", async () => {
  await go("/console"); await page.locator(".lead").first().waitFor(T);
  let opts = await search("7de132c3ca"); await opts.first().click(T);
  await page.getByRole("tab", { name: "Transaction" }).waitFor(T);
  opts = await search("bc1q64weeskl8vkre5urxq24yfpp2xtf9xpjzlmskq"); await opts.first().click(T);
  await page.getByRole("heading", { name: /Address dossier/ }).waitFor(T);
});
await check("filter: peel chain", async () => {
  await go("/console?filter=CHAIN");
  await page.getByText("Peeling chain of 5 steps").first().waitFor(T);
});

await check("upload: sample CSV is ingested, analysed and shown", async () => {
  await go("/console"); await page.locator(".lead").first().waitFor(T);
  await page.locator('input[type="file"]').setInputFiles(new URL("../public/samples/sutradhar-sample.csv", import.meta.url).pathname);
  await page.getByText(/Done: \d+ leads found/).waitFor({ timeout: 240_000 });
  await page.locator(".lead").first().waitFor(T);
});

await check("cases: create, note, exports with working download", async () => {
  await go("/cases");
  await page.getByLabel("New case title").fill("Peeling-chain investigation");
  await page.getByRole("button", { name: "Create case" }).click();
  await page.getByRole("heading", { name: "Peeling-chain investigation" }).waitFor(T);
  await page.getByLabel("Add a note for the case file").fill("Taint path checked: 3 hops from the seed wallet.");
  await page.getByRole("button", { name: "Add note" }).click();
  await page.getByText("Taint path checked").waitFor(T);
  for (const n of [0, 1, 2, 3]) await page.getByRole("button", { name: "Export", exact: true }).nth(n).click();
  await page.getByText(/sha256 /).first().waitFor(T);
  const [dl] = await Promise.all([page.waitForEvent("download", T), page.getByRole("button", { name: "download" }).first().click()]);
  if (!/\.(zip|graphml|json|csv)$/.test(dl.suggestedFilename())) throw new Error(`download ${dl.suggestedFilename()}`);
});

await check("verify: valid, then file edit caught, then forged manifest caught", async () => {
  await go("/verify");
  await page.getByRole("button", { name: /1\. Build a sample pack/ }).click();
  await page.locator(".verdict.ok").first().waitFor(T);
  await page.getByRole("button", { name: /2\. Edit a file/ }).click();
  await page.getByText(/changed after export/).first().waitFor(T);
  await page.getByRole("button", { name: /3\. Edit the file and forge/ }).click();
  await page.getByText(/seal does not match/).first().waitFor(T);
  const bad = await page.locator(".verdict.bad").count();
  if (bad !== 2) throw new Error(`expected 2 failed verdicts, got ${bad}`);
});

await check("system: air-gapped, refdata intact, audit chain", async () => {
  await go("/system");
  await page.getByText("AIR-GAPPED ✓").waitFor(T);
  await page.getByText("intact").first().waitFor(T);
  await page.getByText(/Intact/).first().waitFor(T);
});
await check("how it works: diagram, models incl. coinjoin", async () => {
  await go("/how-it-works");
  await page.locator("svg.arch").waitFor(T);
  await page.locator(".model-card").first().waitFor(T);
  if ((await page.locator(".model-card").count()) < 3) throw new Error("expected >= 3 model cards");
});
await check("govern: models, chain intact", async () => {
  await go("/govern");
  await page.getByText("Chain intact").waitFor(T);
  await page.locator(".req h3.mono").first().waitFor(T);
});
await check("academy: take the challenge", async () => {
  await go("/academy");
  await page.getByRole("button", { name: "Start" }).click(T);
  const groups = page.locator("fieldset");
  const n = await groups.count();
  for (let i = 0; i < n; i++) await groups.nth(i).locator('input[type="radio"]').first().check();
  await page.getByRole("button", { name: "Submit" }).click();
  await page.locator(".big-p").waitFor(T);
});
await check("tour dock: Next moves to the next step's page", async () => {
  await go("/guide");
  await page.getByRole("button", { name: /Start the tour|Continue the tour/ }).click();
  await page.getByRole("complementary", { name: "Guided tour" }).waitFor(T);
  await page.getByRole("button", { name: /Done, next step/ }).click();
  await page.waitForURL(/tab=why/, T);
});
await check("hindi toggle", async () => {
  await go("/");
  await page.getByRole("button", { name: /हिं/ }).click();
  await page.getByRole("link", { name: "कंसोल" }).waitFor(T);
});

console.log("\n=== RESULTS ===");
for (const [s, n, d] of results) console.log(`${s}  ${n}  ${typeof d === "number" ? `${d}ms` : d}`);
const uniq = [...new Set(errors)].filter((e) => !/favicon|Failed to load resource.*(401|404)/.test(e));
console.log(`\nbrowser errors: ${uniq.length}`); uniq.slice(0, 12).forEach((e) => console.log("  ", e));
await browser.close();
process.exit(results.some((r) => r[0] === "FAIL") ? 1 : 0);
