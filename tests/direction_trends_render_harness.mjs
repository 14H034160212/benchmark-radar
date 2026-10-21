// Run the Trends direction table's production render code against a small DOM
// stub: the weekly bars (printed for the Python seed to match), the seeded
// note and controls when the catalog fails, and binding before it loads.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}

class Node {
  constructor(tag) {
    this.tag = tag;
    this.attrs = [];
    this.children = [];
    this.dataset = {};
    this.listeners = {};
    this.textContent = "";
    this.disabled = false;
    this.value = "";
  }
  setAttribute(key, value) {
    this.attrs.push([key, String(value)]);
  }
  append(...children) {
    this.children.push(...children);
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  serialize() {
    const attrs = this.attrs.map(([key, value]) => ` ${key}="${value}"`).join("");
    const inner = this.children.length ? this.children.map((child) => child.serialize()).join("") : this.textContent;
    return `<${this.tag}${attrs}>${inner}</${this.tag}>`;
  }
}
const nodes = new Map();
const byId = (id) => {
  if (!nodes.has(id)) nodes.set(id, new Node(id === "direction-trends-body" ? "tbody" : "div"));
  return nodes.get(id);
};
globalThis.document = { createElementNS: (_ns, tag) => new Node(tag), addEventListener() {} };

let releaseIndex;
const state = { data: {}, view: "trends" };
const env = {
  state, byId,
  t: (key, params) => Object.entries(params || {}).reduce((text, [k, v]) => text.replaceAll(`{${k}}`, String(v)), key),
  formatDate: (value) => value,
  loadBenchmarkIndex: () => new Promise((resolve) => { releaseIndex = resolve; }),
  DIRECTION_TREND_WINDOWS: [30, 60, 90],
};
const { directionSparkline, directionFocusChart, renderDirectionTrends } = new Function(
  ...Object.keys(env),
  `${fn("directionTrendNote")}\n${fn("directionSparkline")}\n${fn("directionFocusChart")}\n${fn("initDirectionTrends")}\n${fn("renderDirectionTrends")}\nreturn { directionSparkline, directionFocusChart, renderDirectionTrends };`,
)(...Object.values(env));

// The seeded window selector works while the catalog is still loading.
byId("direction-trends-body").children = [new Node("tr")];
Object.assign(byId("direction-trends-note").dataset, { anchor: "2026-10-14", window: "30", comparable: "1", since: "2026-05-18" });
byId("direction-trends-note").textContent = "seeded English text";
renderDirectionTrends();
assert.equal(byId("direction-trends-window").listeners.change.length, 1);

// The catalog fails: the seeded caveats stay, the failure is added, and the
// controls that can no longer change anything are disabled.
releaseIndex(null);
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(byId("direction-trends-note").textContent,
  // Rebuilt from the seeded facts through t(), so it follows the reader's
  // language; the seeded English text is not reused.
  "New benchmark records by release date, 30 days to 2026-10-14. The latest days are still filling in as new papers are collected. "
  + "A record counts in every direction it is filed under, so rows overlap and do not add up to a total. The benchmark catalog could not be loaded.");
assert.equal(byId("direction-trends-window").disabled, true);
assert.equal(byId("direction-trends-group").disabled, true);
// Rendering again does not repeat the failure.
renderDirectionTrends();
assert.equal(byId("direction-trends-note").textContent.match(/could not be loaded/g).length, 1);

// Reached through the app with no seed, a failed catalog still leaves the
// section visible with the failure stated.
nodes.clear();
state.benchmarkIndexLoaded = true;
state.benchmarkIndex = null;
renderDirectionTrends();
assert.equal(byId("direction-trends").hidden, false);
assert.equal(byId("direction-trends-note").textContent, "The benchmark catalog could not be loaded.");

// The bars, serialized for test_direction_trends.py to compare with the seed.
const cases = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify({
  sparklines: cases.map((weekly) => directionSparkline(weekly).serialize()),
  focusCharts: cases.map((weekly) => directionFocusChart(weekly).serialize()),
}));
