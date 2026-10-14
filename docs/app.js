const FIRST_YEAR = 2001;
const LAST_YEAR = 2024;
const NO_SHARE = "#dedad0";
const RAMP = ["#fee8c8", "#fdbb84", "#fc8d59", "#e34a33", "#b30000"];
const COUNTRY_VIEW = {
  ALL: { center: [3.5, 7.5], zoom: 3.6 },
  GHA: { center: [-1.2, 7.9], zoom: 5.6 },
  CIV: { center: [-5.5, 7.6], zoom: 5.5 },
  CMR: { center: [12.6, 5.9], zoom: 4.9 },
};

const MIN_FOREST_HA = 1000; // areas with less forest than this are not ranked or coloured by share
const state = { level: "regions", country: "ALL", from: FIRST_YEAR, to: LAST_YEAR, metric: "pct", selected: null };
const data = { regions: null, districts: null };

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 0) => Number(n).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: d });

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  for (const k of kids) e.append(k);
  return e;
}

function lossInRange(loss) {
  let s = 0;
  for (let y = state.from; y <= state.to; y++) s += loss[y - FIRST_YEAR];
  return s;
}

function annotate(fc) {
  for (const f of fc.features) {
    const p = f.properties;
    const lossArr = typeof p.loss === "string" ? JSON.parse(p.loss) : p.loss;
    p._loss = lossArr;
    p.lossHa = lossInRange(lossArr);
    p.pct = p.forest2000_ha >= MIN_FOREST_HA ? (100 * p.lossHa) / p.forest2000_ha : null;
    p.v = state.metric === "pct" ? (p.pct === null ? -1 : p.pct) : p.lossHa;
  }
}

function visibleFeatures() {
  const fc = data[state.level];
  return fc.features.filter((f) => state.country === "ALL" || f.properties.iso === state.country);
}

function breaks(values) {
  const v = values.filter((x) => x > 0).sort((a, b) => a - b);
  if (v.length < 5) return [];
  const q = (p) => v[Math.min(v.length - 1, Math.floor(p * v.length))];
  const raw = [q(0.2), q(0.4), q(0.6), q(0.8)];
  return [...new Set(raw)].filter((x) => x > 0);
}

const map = new maplibregl.Map({
  container: "map",
  style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  center: COUNTRY_VIEW.ALL.center,
  zoom: COUNTRY_VIEW.ALL.zoom,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

let mapReady = false;

function fillExpression(b) {
  const base = !b.length ? RAMP[2] : null;
  if (!b.length) return ["case", ["<", ["get", "v"], 0], NO_SHARE, base];
  const expr = ["step", ["get", "v"], RAMP[0]];
  b.forEach((x, i) => expr.push(x, RAMP[i + 1]));
  return ["case", ["<", ["get", "v"], 0], NO_SHARE, expr];
}

function refresh() {
  const fc = data[state.level];
  annotate(fc);
  const feats = visibleFeatures();
  const b = breaks(feats.map((f) => f.properties.v));
  if (mapReady) {
    map.getSource("areas").setData({ type: "FeatureCollection", features: feats });
    map.setPaintProperty("areas-fill", "fill-color", fillExpression(b));
  }
  renderLegend(b);
  renderCards(feats);
  renderChart(feats);
  renderTable(feats);
}

function renderLegend(b) {
  const box = $("legend");
  box.replaceChildren();
  const unit = state.metric === "pct" ? "%" : " ha";
  const d = state.metric === "pct" ? 1 : 0;
  const edges = [0, ...b];
  if (!b.length) {
    box.append(el("span", {}, el("i", { style: `background:${RAMP[2]}` }), "Too few areas to classify"));
    return;
  }
  edges.forEach((lo, i) => {
    const hi = edges[i + 1];
    const label = hi === undefined ? `${fmt(lo, d)}${unit} and above` : `${fmt(lo, d)} to ${fmt(hi, d)}${unit}`;
    box.append(el("span", {}, el("i", { style: `background:${RAMP[i]}` }), label));
  });
  if (state.metric === "pct") box.append(el("span", {}, el("i", { style: `background:${NO_SHARE}` }), `Under ${fmt(MIN_FOREST_HA)} ha of forest: share not shown`));
}

function totals(feats) {
  let forest = 0, loss = 0;
  const yearly = new Array(LAST_YEAR - FIRST_YEAR + 1).fill(0);
  for (const f of feats) {
    forest += f.properties.forest2000_ha;
    loss += f.properties.lossHa;
    f.properties._loss.forEach((x, i) => (yearly[i] += x));
  }
  return { forest, loss, yearly };
}

function renderCards(feats) {
  const t = totals(state.selected ? [state.selected] : feats);
  const pct = t.forest > 0 ? (100 * t.loss) / t.forest : 0;
  const card = (n, l) => el("div", { class: "card" }, el("div", { class: "n" }, n), el("div", { class: "l" }, l));
  $("cards").replaceChildren(
    card(fmt(t.forest / 1000, 0) + " k", "ha forest in 2000"),
    card(fmt(t.loss / 1000, 1) + " k", `ha lost ${state.from}-${state.to}`),
    card(fmt(pct, 1) + "%", "of 2000 forest")
  );
}

function renderChart(feats) {
  const sel = state.selected;
  const t = totals(sel ? [sel] : feats);
  $("chart-title").textContent = sel
    ? `Annual loss: ${sel.properties.name}, ${sel.properties.country}`
    : `Annual loss: ${state.country === "ALL" ? "all three countries" : feats[0]?.properties.country ?? ""}`;
  const W = 330, H = 130, padL = 34, padB = 16, padT = 6;
  const max = Math.max(...t.yearly, 1);
  const n = t.yearly.length;
  const bw = (W - padL) / n;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Bar chart of annual tree cover loss in hectares");
  const add = (tag, attrs, text) => {
    const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    svg.append(e);
    return e;
  };
  t.yearly.forEach((v, i) => {
    const y = FIRST_YEAR + i;
    const h = ((H - padB - padT) * v) / max;
    const r = add("rect", { x: padL + i * bw + 0.5, y: H - padB - h, width: Math.max(bw - 1, 1), height: h,
      class: "bar" + (y >= state.from && y <= state.to ? " in" : "") });
    r.append(Object.assign(document.createElementNS("http://www.w3.org/2000/svg", "title"), { textContent: `${y}: ${fmt(v)} ha` }));
  });
  add("text", { x: 0, y: padT + 8, class: "axis" }, fmt(max / 1000, max >= 10000 ? 0 : 1) + " k ha");
  add("text", { x: 0, y: H - padB, class: "axis" }, "0");
  [FIRST_YEAR, 2010, 2020, LAST_YEAR].forEach((y) =>
    add("text", { x: y === LAST_YEAR ? W - 1 : padL + (y - FIRST_YEAR) * bw, y: H - 3, class: "axis", "text-anchor": y === LAST_YEAR ? "end" : "start" }, String(y)));
  $("chart").replaceChildren(svg);
}

function renderTable(feats) {
  const ranked = state.metric === "pct" ? feats.filter((f) => f.properties.pct !== null) : feats;
  const sorted = [...ranked].sort((a, b) => b.properties.v - a.properties.v).slice(0, 10);
  const head = el("tr", {},
    el("th", {}, "Area"),
    el("th", {}, "Country"),
    el("th", { class: "num" }, state.metric === "pct" ? "% lost" : "ha lost"));
  const rows = sorted.map((f) => {
    const p = f.properties;
    const tr = el("tr", { class: "row" + (state.selected === f ? " active" : ""), tabindex: "0" },
      el("td", {}, p.name),
      el("td", {}, p.country),
      el("td", { class: "num" }, state.metric === "pct" ? fmt(p.pct, 1) + "%" : fmt(p.lossHa)));
    const pick = () => select(f);
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    return tr;
  });
  $("detail-title").textContent = `Top 10 areas, ${state.from}-${state.to}`;
  $("detail").replaceChildren(
    el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows)),
    el("p", { class: "hint" }, "Select a row or an area on the map to see its own chart. Select the same area again to clear." + (state.metric === "pct" ? ` Areas with under ${fmt(MIN_FOREST_HA)} ha of forest in 2000 are left out of the share ranking.` : ""))
  );
}

function select(f) {
  const same = state.selected && f && state.selected.properties.name === f.properties.name
    && state.selected.properties.iso === f.properties.iso;
  state.selected = same ? null : f;
  const feats = visibleFeatures();
  renderCards(feats);
  renderChart(feats);
  renderTable(feats);
  if (mapReady) {
    map.setFilter("areas-selected", state.selected
      ? ["all", ["==", ["get", "name"], state.selected.properties.name], ["==", ["get", "iso"], state.selected.properties.iso]]
      : ["==", ["get", "name"], ""]);
  }
}

function setView() {
  const v = COUNTRY_VIEW[state.country];
  map.easeTo({ center: v.center, zoom: v.zoom, duration: 600 });
}

function initControls() {
  for (const id of ["from", "to"]) {
    const s = $(id);
    for (let y = FIRST_YEAR; y <= LAST_YEAR; y++) s.append(new Option(y, y));
  }
  $("from").value = state.from;
  $("to").value = state.to;
  $("level").addEventListener("change", (e) => { state.level = e.target.value; state.selected = null; refresh(); select(null); });
  $("country").addEventListener("change", (e) => { state.country = e.target.value; state.selected = null; refresh(); setView(); select(null); });
  $("metric").addEventListener("change", (e) => { state.metric = e.target.value; refresh(); });
  const range = () => {
    let a = +$("from").value, b = +$("to").value;
    if (a > b) { [a, b] = [b, a]; $("from").value = a; $("to").value = b; }
    state.from = a; state.to = b; refresh();
  };
  $("from").addEventListener("change", range);
  $("to").addEventListener("change", range);
}

async function load() {
  const [regions, districts] = await Promise.all([
    fetch("data/regions.geojson").then((r) => r.json()),
    fetch("data/districts.geojson").then((r) => r.json()),
  ]);
  data.regions = regions;
  data.districts = districts;
  initControls();
  refresh();
}

map.on("load", () => {
  map.addSource("areas", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "areas-fill", type: "fill", source: "areas", paint: { "fill-color": RAMP[2], "fill-opacity": 0.82 } });
  map.addLayer({ id: "areas-line", type: "line", source: "areas", paint: { "line-color": "#ffffff", "line-width": 0.7 } });
  map.addLayer({ id: "areas-selected", type: "line", source: "areas", filter: ["==", ["get", "name"], ""],
    paint: { "line-color": "#1f2a24", "line-width": 2.4 } });
  map.on("click", "areas-fill", (e) => {
    const hit = e.features[0];
    if (!hit) return;
    const p = hit.properties;
    const f = visibleFeatures().find((x) => x.properties.name === p.name && x.properties.iso === p.iso);
    if (f) select(f);
  });
  map.on("mouseenter", "areas-fill", () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", "areas-fill", () => (map.getCanvas().style.cursor = ""));
  mapReady = true;
  if (data.regions) refresh();
});

load().catch((err) => {
  $("detail").replaceChildren(el("p", { class: "hint" }, "Could not load the data files: " + err.message));
});
