// I11: the built web bundle must not reference any external host (allow-list: the W3C namespaces React embeds).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ALLOWED = [/^https:\/\/github\.com\/Abhishek222983101\/sutradhar-btc(\/blob\/main\/docs\/EVAL\.md)?$/, /^https?:\/\/www\.w3\.org\//, /^https?:\/\/reactjs\.org\//, /^https?:\/\/react\.dev\//];
if (process.env.VITE_API_BASE_URL) ALLOWED.push(new RegExp("^" + process.env.VITE_API_BASE_URL.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")));
const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : [join(d, f)]));
const bad = [];
for (const file of walk("dist").filter((f) => /\.(js|css|html)$/.test(f))) {
  for (const url of readFileSync(file, "utf8").match(/https?:\/\/[^\s"'`)<>\\]+/g) ?? []) {
    if (!ALLOWED.some((re) => re.test(url))) bad.push(`${file}: ${url}`);
  }
}
if (bad.length) { console.error("external URLs in bundle:\n" + [...new Set(bad)].join("\n")); process.exit(1); }
console.log("no external URLs in the built bundle");
