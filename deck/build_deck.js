// Final executive deck (10 slides + 2 appendix) from deck/deck_data.json.
// Run:  python deck/deck_data.py && node deck/build_deck.js
// Needs pptxgenjs (npm i pptxgenjs). Optional: APPLY_THEME=<path to an
// applyTheme module> also writes the palette and fonts into the theme.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "deck_data.json")));
const OUT = path.join(__dirname, "Weather_Ready_Divvy_Final.pptx");

const THEME = {
  name: "Weather-Ready Divvy", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B2A30", lt1: "FFFFFF", dk2: "0F2A33", lt2: "EEF3F4",
    accent1: "2A7F8E", accent2: "E4572E", accent3: "8FA9AE", accent4: "F2B134",
    accent5: "5C6B70", accent6: "C9D6D9", hlink: "2A7F8E", folHlink: "5C6B70" },
};
const H = THEME.colors;                  // hex, for hex-only chart options
const MEMBER = H.accent1, CASUAL = H.accent2, GREY = H.accent3, AMBER = H.accent4;

const pct = (x, d = 0) => `${(100 * x).toFixed(d)}%`;
const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(100 * x).toFixed(0)}%`;
const k = (x) => `${(x / 1000).toFixed(1)}k`;
const M = (x) => `${(x / 1e6).toFixed(2)}M`;
const usd = (x) => `${x < 0 ? "−" : "+"}$${(Math.abs(x) / 1000).toFixed(1)}k`;
const sens = Object.fromEntries(D.sensitivity.map((r) => [r.rider_type, r]));
const T = D.metrics.total, roi = D.roi, sc = roi.scenarios;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";               // 10 x 5.625 in, as the Week 4 deck
pres.title = "Weather-Ready Divvy: final executive briefing";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
// Hex colours (so the deck rebuilds the same without the theme step); the
// optional APPLY_THEME step also writes them into the deck's theme.
const C = { text1: H.dk1, text2: H.dk2, background1: H.lt1, background2: H.lt2,
  accent1: H.accent1, accent2: H.accent2, accent3: H.accent3, accent4: H.accent4,
  accent5: H.accent5, accent6: H.accent6 };

// ------------------------------------------------------------ layouts ----
const footer = (dark) => [
  { text: { text: "Weather-Ready Divvy  ·  Final briefing", options: {
    x: 0.5, y: 5.25, w: 6, h: 0.25, fontSize: 9, margin: 0,
    color: dark ? C.accent6 : C.accent5 } } },
];
pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 1.0,
      w: 9, h: 0.9, fontSize: 44, bold: true, color: C.background1,
      fontFace: THEME.headFontFace, valign: "bottom", align: "left", margin: 0 },
      text: "Title" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: C.background1 },
  objects: [
    ...footer(false),
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28,
      w: 9, h: 0.55, fontSize: 30, bold: true, color: C.text2,
      fontFace: THEME.headFontFace, valign: "top", align: "left", margin: 0 },
      text: "Title" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.5, y: 0.86,
      w: 9, h: 0.36, fontSize: 15, italic: true, color: C.accent1,
      valign: "top", margin: 0 }, text: "Takeaway" } },
  ],
  slideNumber: { x: 9.1, y: 5.25, w: 0.4, h: 0.25, fontSize: 9,
    color: C.accent5, align: "right" },
});
pres.defineSlideMaster({
  title: "DECISION_DARK", background: { color: C.text2 },
  objects: [
    ...footer(true),
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28,
      w: 9, h: 0.55, fontSize: 30, bold: true, color: C.background1,
      fontFace: THEME.headFontFace, valign: "top", align: "left", margin: 0 },
      text: "Title" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.5, y: 0.86,
      w: 9, h: 0.36, fontSize: 15, italic: true, color: C.accent4,
      valign: "top", margin: 0 }, text: "Takeaway" } },
  ],
  slideNumber: { x: 9.1, y: 5.25, w: 0.4, h: 0.25, fontSize: 9,
    color: C.accent6, align: "right" },
});

// -------------------------------------------------------------- helpers ----
let n = 0;
const id = (s) => `${s}-${++n}`;
function content(section, title, takeaway, master = "CONTENT") {
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addText(takeaway, { placeholder: "body" });
  return s;
}
function txt(s, text, o) {
  s.addText(text, { isTextBox: true, margin: 0, valign: "top", fontSize: 14,
    color: C.text1, objectName: id("text"), ...o });
}
function panel(s, x, y, w, h, fill = C.background2) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
    fill: { color: fill }, line: { color: fill }, objectName: id("panel") });
}
function stat(s, x, y, w, big, label, color = C.accent2, dark = false, size = 26) {
  txt(s, big, { x, y, w, h: 0.5, fontSize: size, bold: true, color,
    fontFace: THEME.headFontFace });
  txt(s, label, { x, y: y + 0.5, w, h: 0.5, fontSize: 11,
    color: dark ? C.accent6 : C.accent5 });
}
function card(s, x, y, w, h, head, body, headColor = C.accent2) {
  panel(s, x, y, w, h);
  txt(s, head, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 0.4, fontSize: 18,
    bold: true, color: headColor, fontFace: THEME.headFontFace });
  txt(s, body, { x: x + 0.15, y: y + 0.52, w: w - 0.3, h: h - 0.6,
    fontSize: 11, color: C.text1 });
}
// A clearly marked slot for a teammate's visual (dashed frame + brief name)
function slot(s, x, y, w, h, label, detail) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
    fill: { color: C.background2 }, line: { color: C.accent3, width: 1.5,
      dashType: "dash" }, objectName: id("visual-slot") });
  txt(s, label, { x: x + 0.3, y: y + h / 2 - 0.45, w: w - 0.6, h: 0.4,
    fontSize: 16, bold: true, color: C.accent5, align: "center" });
  txt(s, detail, { x: x + 0.3, y: y + h / 2, w: w - 0.6, h: 0.6,
    fontSize: 11, color: C.accent5, align: "center" });
}
const axis = {   // one look for every chart in the deck
  catAxisLabelColor: H.accent5, valAxisLabelColor: H.accent5,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  dataLabelFontFace: "+mn-lt", dataLabelFontSize: 9, dataLabelColor: H.dk1,
  titleFontFace: "+mn-lt", titleFontSize: 11, titleColor: H.dk1,
  legendFontFace: "+mn-lt", legendFontSize: 10, legendColor: H.accent5,
  valGridLine: { color: "E3E9EA", size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false,
};

// ========================================================= ACT I ========
pres.addSection({ title: "Act I · Context" });
{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Act I · Context" });
  s.addText("Weather-Ready Divvy", { placeholder: "title" });
  txt(s, "Putting bikes, trucks and staff where the weather sends riders", {
    x: 0.5, y: 1.95, w: 9, h: 0.4, fontSize: 18, color: C.accent6 });
  txt(s, [
    { text: "Thesis  ", options: { bold: true, color: C.accent4 } },
    { text: `Casual riders react to the weather about twice as strongly as members (${signed(sens.casual.pct_per_10f)} vs ${signed(sens.member.pct_per_10f)} per +10°F). A fixed rebalancing schedule leaves bikes in the wrong place on the best and worst days; a weather forecast cuts daily planning error by ${pct(1 - T.mape_model / T.mape_baseline)}.`,
      options: { color: C.background1 } },
  ], { x: 0.5, y: 2.55, w: 8.6, h: 0.9, fontSize: 15 });
  stat(s, 0.5, 3.7, 2.6, M(D.total_rides), "clean rides, Sep 2024 – Sep 2026", C.accent4, true);
  stat(s, 3.4, 3.7, 2.8, `${signed(sens.casual.pct_per_10f)} vs ${signed(sens.member.pct_per_10f)}`, "casual vs member rides per +10°F", C.accent4, true);
  stat(s, 6.5, 3.7, 3.0, `${pct(T.mape_model, 1)} vs ${pct(T.mape_baseline, 1)}`, "forecast error vs same-day-last-year", C.accent4, true);
  txt(s, "Divvy Operations Advisory  ·  Data Visualization Strategies & Techniques  ·  Final briefing, December 2026",
    { x: 0.5, y: 5.1, w: 9, h: 0.3, fontSize: 9, color: C.accent6 });
  s.addNotes(`Hook (under a minute): same city, same bikes, two kinds of demand. Members ride in any weather; casual riders show up only when it is warm and dry. Today Divvy plans trucks and staff as if demand were steady. We show the gap, prove it with ${M(D.total_rides)} rides and two years of Midway weather, and hand you two tools: a monitor (Tableau) and a forecast you can steer (Streamlit). The ask at the end: approve a warm-season pilot at 20 lakefront stations.`);
}
{
  const s = content("Act I · Context", "The decision, the KPIs, the hypotheses",
    "When and where should Divvy add bikes, trucks and staff ahead of the weather?");
  panel(s, 0.5, 1.4, 4.2, 1.5);
  txt(s, "H2 · HEADLINE", { x: 0.7, y: 1.52, w: 2.5, h: 0.25, fontSize: 10, bold: true, color: C.accent2 });
  txt(s, "SUPPORTED", { x: 3.3, y: 1.52, w: 1.2, h: 0.25, fontSize: 10, bold: true, color: C.accent1, align: "right" });
  txt(s, "Casual riders react far more to weather than members, so a fixed rebalancing schedule misses on both good and bad days.",
    { x: 0.7, y: 1.82, w: 3.8, h: 1.0, fontSize: 13 });
  panel(s, 0.5, 3.1, 4.2, 1.5);
  txt(s, "H1 · TEST", { x: 0.7, y: 3.22, w: 2.5, h: 0.25, fontSize: 10, bold: true, color: C.accent2 });
  txt(s, "SUPPORTED", { x: 3.3, y: 3.22, w: 1.2, h: 0.25, fontSize: 10, bold: true, color: C.accent1, align: "right" });
  txt(s, "A weather-driven daily forecast beats “same day last year” on forecast error (MAPE) on unseen days.",
    { x: 0.7, y: 3.52, w: 3.8, h: 1.0, fontSize: 13 });
  const kpis = [
    ["Daily rides", `${k(D.last12_avg_daily)} a day over the last 12 months; ${pct(D.last12_casual_share)} casual`],
    ["Weather sensitivity", `${signed(sens.casual.pct_per_10f)} casual vs ${signed(sens.member.pct_per_10f)} member per +10°F (H2)`],
    ["Forecast error", `MAPE ${pct(T.mape_model, 1)} model vs ${pct(T.mape_baseline, 1)} baseline (H1)`],
    ["Station stress", `rides per dock per day: median ${D.median_stress}, busiest ${D.max_stress}`],
    ["Dockless share", `${pct(D.dockless_share, 1)} of rides start away from a station`],
  ];
  kpis.forEach(([h, b], i) => {
    const y = 1.4 + i * 0.66;
    s.addShape(pres.shapes.OVAL, { x: 5.1, y: y + 0.04, w: 0.42, h: 0.42,
      fill: { color: i === 1 ? C.accent2 : C.accent1 }, line: { color: C.background1 }, objectName: id("kpi-dot") });
    txt(s, String(i + 1), { x: 5.1, y: y + 0.1, w: 0.42, h: 0.3, fontSize: 13, bold: true, color: C.background1, align: "center" });
    txt(s, h, { x: 5.7, y, w: 3.8, h: 0.28, fontSize: 14, bold: true, color: C.text2 });
    txt(s, b, { x: 5.7, y: y + 0.28, w: 3.8, h: 0.3, fontSize: 11, color: C.accent5 });
  });
  s.addNotes("Problem statement: Divvy operations sets truck shifts and rebalancing routes on a fixed weekly rhythm. Five KPIs decide whether that works over time; KPI 2 (coral) is the headline. Both hypotheses are supported, and the rest of the talk shows how we know.");
}

// ========================================================= ACT II =======
pres.addSection({ title: "Act II · Emotion" });
{
  const s = content("Act II · Emotion", "Sources, provenance and data traps",
    "Five sources, one consistent dataset, after defusing the traps in the raw data");
  const head = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  const rows = [
    ["Divvy trip files", "12.5M trips, 25 monthly zips", "Sep 24 – Sep 26"],
    ["NOAA Midway (GHCN-Daily)", "temp, rain, snow depth, wind", "daily"],
    ["Divvy GBFS station feed", "2,082 stations, dock capacity", "2026-11-26"],
    ["Chicago community areas", "77 boundary polygons", "static"],
    ["US federal holidays", "24 holidays, observed dates", "any year"],
  ];
  s.addTable([[head("Source"), head("Provides"), head("Coverage")], ...rows], {
    x: 0.5, y: 1.4, w: 4.6, colW: [1.75, 1.85, 1.0], fontSize: 10, color: C.text1,
    border: { type: "solid", pt: 0.5, color: "D5DEE0" }, rowH: 0.3, margin: 0.05,
    objectName: id("sources") });
  const months = Object.keys(D.chi_share);
  s.addChart(pres.charts.BAR, [
    { name: "Legacy IDs (516, TA1308000012…)", labels: months.map((m) => `${m.slice(4)}/${m.slice(2, 4)}`), values: months.map((m) => 100 - D.chi_share[m]) },
    { name: "New CHI##### IDs", labels: months.map((m) => `${m.slice(4)}/${m.slice(2, 4)}`), values: months.map((m) => D.chi_share[m]) },
  ], { x: 5.3, y: 1.3, w: 4.2, h: 2.2, barDir: "col", barGrouping: "percentStacked", barGapWidthPct: 20,
    chartColors: [GREY, MEMBER], showTitle: true, title: "Station ID format per monthly file (%)",
    showLegend: true, legendPos: "b", catAxisLabelFrequency: 3, valAxisHidden: true, ...axis,
    objectName: id("id-switch") });
  const traps = [
    ["Jun 2025", "Station IDs re-keyed: legacy IDs never match today's feed"],
    ["202601", "The Jan 2026 zip holds a CSV named Jan 2025"],
    ["144k", "E-scooters in Sep 2024 only: a different product"],
    [pct(D.dockless_share, 1), "Rides with no start station; GPS rounded ~1 km"],
  ];
  traps.forEach(([h, b], i) => card(s, 0.5 + i * 2.3, 3.72, 2.15, 1.3, h, b));
  s.addNotes("Audit method: every trap was found by profiling each file, not by accident. The Jun 2025 ID switch is the one that would have broken station capacity: none of the pre-June IDs match the live feed. Also flagged: dock capacity is a 2026-11-26 snapshot applied to past rides, station names change for the same ID (CHI01747 was 'Streeter Dr & Grand Ave', now 'Navy Pier'), and Midway does not report average temperature or snowfall in this window.");
}
{
  const s = content("Act II · Emotion", "Data hygiene and transformation",
    "A reproducible engine turns 12.5M noisy rows into five decision tables");
  const steps = [["Ingest", "zip by zip, month check"], ["Adapt", "any Divvy format → 13 columns"],
    ["Clean", "drop false starts, > 24 h, scooters"], ["Match", "trips → docks: ID, name, 150 m"],
    ["Join", "weather, holidays, areas"], ["Publish", "KPI tables, DVC, lineage"]];
  steps.forEach(([h, b], i) => {
    const x = 0.5 + i * 1.5;
    s.addShape(pres.shapes.CHEVRON, { x, y: 1.4, w: 1.45, h: 0.5, fill: { color: i === 3 ? C.accent2 : C.accent1 },
      line: { color: C.background1 }, objectName: id("step") });
    txt(s, h, { x: x + 0.2, y: 1.52, w: 1.1, h: 0.3, fontSize: 12, bold: true, color: C.background1, align: "center" });
    txt(s, b, { x, y: 1.98, w: 1.42, h: 0.45, fontSize: 9.5, color: C.accent5, align: "center" });
  });
  const q = D.quality, dur = q.too_short + q.too_long_or_negative;
  s.addChart(pres.charts.BAR, [{ name: "rows removed (thousands)", labels: ["Under 1 minute", "E-scooters", "Over 24 h / negative"],
    values: [q.too_short, q.scooters_dropped, q.too_long_or_negative].map((v) => +(v / 1000).toFixed(1)) }],
  { x: 0.5, y: 2.6, w: 4.4, h: 1.9, barDir: "bar", chartColors: [GREY], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0\"k\"", showTitle: true, title: `${M(q.rows_raw)} raw rows → ${M(q.rows_clean)} clean rides: rows removed`,
    showLegend: false, valAxisHidden: true, catAxisOrientation: "maxMin", ...axis, valGridLine: { style: "none" }, objectName: id("removed") });
  txt(s, `No duplicate ride IDs. ${pct(dur / q.rows_raw, 1)} removed for duration, ${pct(q.scooters_dropped / q.rows_raw, 1)} as a different product.`,
    { x: 0.5, y: 4.6, w: 4.4, h: 0.5, fontSize: 10, color: C.accent5 });
  const mm = D.match;
  s.addChart(pres.charts.BAR, [{ name: "share of station trip-ends", labels: ["Station ID", "Station name", "Nearest dock ≤150 m", "Unmatched"],
    values: [mm.id, mm.name, mm.coords, mm.unmatched].map((v) => +(100 * v).toFixed(1)) }],
  { x: 5.2, y: 2.6, w: 4.3, h: 1.9, barDir: "bar", chartColors: [MEMBER, MEMBER, MEMBER, CASUAL], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.0\"%\"", showTitle: true, title: `${pct(1 - mm.unmatched, 1)} of station trips matched to a dock with capacity`,
    showLegend: false, valAxisHidden: true, catAxisOrientation: "maxMin", ...axis, valGridLine: { style: "none" }, objectName: id("match") });
  txt(s, "Imputation: average temp = (max + min) / 2; snow depth = 0 Apr–Oct, when Midway doesn't measure it.",
    { x: 5.2, y: 4.6, w: 4.3, h: 0.5, fontSize: 10, color: C.accent5 });
  s.addNotes(`Six steps, one command (dvc repro). The adapter means older Divvy files (2013-2019 quarterly formats) can be added without touching downstream code; it is unit-tested on a 2019 sample. Before/after: ${M(q.rows_raw)} raw rows → ${M(q.rows_clean)} clean rides. Station matching is the hard join: before June 2025, ${pct(D.match_era.legacy.name, 1)} of trips match by name because the IDs changed; after, ${pct(D.match_era.chi.id, 1)} match by ID.`);
}
{
  const s = content("Act II · Emotion", "Empirical signals: two riders, two weathers",
    "Trigger: a warm, dry day. Mechanism: casual riders arrive. Impact: the wrong docks run dry.");
  const labels = D.band.labels.map((l) => l.replace("F", "°F"));
  s.addChart(pres.charts.BAR, [
    { name: "Member", labels, values: D.band.member }, { name: "Casual", labels, values: D.band.casual },
  ], { x: 0.5, y: 1.35, w: 4.5, h: 2.75, barDir: "col", barGapWidthPct: 40, chartColors: [MEMBER, CASUAL],
    showTitle: true, title: "Average rides per day by temperature", showLegend: true, legendPos: "t",
    valAxisLabelFormatCode: "#,##0", ...axis, objectName: id("temp-bands") });
  s.addChart(pres.charts.BAR, [
    { name: "Member", labels, values: D.rain_drop.member.map((v) => +(100 * v).toFixed(0)) },
    { name: "Casual", labels, values: D.rain_drop.casual.map((v) => +(100 * v).toFixed(0)) },
  ], { x: 5.1, y: 1.35, w: 4.4, h: 2.75, barDir: "col", barGapWidthPct: 40, chartColors: [MEMBER, CASUAL],
    showTitle: true, title: "Rides lost on rain days vs dry days, same temperature (%)", showLegend: true, legendPos: "t",
    showValue: true, dataLabelPosition: "outEnd", valAxisHidden: true, ...axis, valGridLine: { style: "none" }, objectName: id("rain") });
  stat(s, 0.5, 4.25, 2.2, `${D.band_ratio.casual}x vs ${D.band_ratio.member}x`, "casual vs member, warmest vs coldest days", C.accent2, false, 20);
  stat(s, 2.85, 4.25, 2.2, `${signed(sens.casual.pct_per_10f)} vs ${signed(sens.member.pct_per_10f)}`, "per +10°F, same weekday and rain", C.accent2, false, 20);
  stat(s, 5.2, 4.25, 2.2, `${signed(sens.casual.pct_rain_day)} vs ${signed(sens.member.pct_rain_day)}`, "on a rain day (≥ 0.1 in)", C.accent2, false, 20);
  stat(s, 7.55, 4.25, 1.95, `r = ${D.corr_temp}`, "temperature vs daily rides", C.accent1, false, 20);
  s.addNotes(`Two charts, then two numbers (Tufte's 2+2). Left: from the coldest to the warmest days casual rides rise ${D.band_ratio.casual}x, members ${D.band_ratio.member}x — that includes the season. Holding the calendar fixed (regression, KPI 2), +10°F adds ${signed(sens.casual.pct_per_10f)} casual vs ${signed(sens.member.pct_per_10f)} member rides. Right: rain hurts casual riders more at every temperature. Operational impact: the lakefront tourist docks swing hardest.`);
}
{
  const s = content("Act II · Emotion", "Analytics architecture and technology stack",
    "From raw files to two visual endpoints, rebuilt by one command");
  const stages = [
    ["Collect", "Divvy trip zips\nNOAA Midway\nGBFS stations\nCommunity areas\nHolidays", GREY],
    ["Feature store", "Python pipeline\n(pandas, pyarrow)\nparquet + CSV tables\nDVC stages\nOpenLineage log", MEMBER],
    ["Models", "KPI 2: log-linear OLS\nH1: regression forecast\nbaseline: same day\nlast year\nLightGBM benchmark", MEMBER],
    ["Visual endpoints", "Tableau: monitor\n(System A)\nStreamlit: what-if\nforecast (System B)", CASUAL],
  ];
  stages.forEach(([h, b, col], i) => {
    const x = 0.5 + i * 2.32;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.4, w: 2.0, h: 0.45, rectRadius: 0.08, fill: { color: col }, line: { color: col }, objectName: id("stage") });
    txt(s, h, { x, y: 1.48, w: 2.0, h: 0.3, fontSize: 13, bold: true, color: C.background1, align: "center" });
    panel(s, x, 1.95, 2.0, 1.45);
    txt(s, b, { x: x + 0.15, y: 2.03, w: 1.75, h: 1.35, fontSize: 11 });
    if (i < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.04, y: 2.5, w: 0.24, h: 0.3, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: id("arrow") });
  });
  const why = [
    ["Reproducible", "dvc repro rebuilds every table from the raw files; each step logs its inputs, schema and row counts."],
    ["Right-sized", `760 daily rows suit an interpretable regression. LightGBM scored ${pct(D.lgbm.total.mape_lgbm, 1)} vs ${pct(D.lgbm.total.mape_linear, 1)}, so it adds nothing.`],
    ["Two jobs, two tools", "Tableau for at-a-glance monitoring; Streamlit for inputs and live model inference."],
  ];
  why.forEach(([h, b], i) => card(s, 0.5 + i * 3.07, 3.6, 2.9, 1.45, h, b, C.accent1));
  s.addNotes("Why this stack over alternatives: a warehouse or Spark would be over-engineering for 12M rows that aggregate to 760 days; plain notebooks would not be reproducible. DVC plus OpenLineage gives auditable provenance at zero infrastructure cost. Tableau is the operations team's monitoring tool; Streamlit lets an analyst steer the model with tomorrow's forecast.");
}

// ======================================================== ACT III =======
pres.addSection({ title: "Act III · Evidence" });
{
  const s = content("Act III · Evidence", "Macro monitor: where the system strains",
    "Tableau System A: KPIs first, then where, then why");
  slot(s, 0.5, 1.35, 6.1, 3.7, "Brief 2 visual + Tableau dashboard", "Paste the dashboard screenshot here (PNG, 1920 px wide)");
  const pts = [
    ["Cognitive hierarchy", "KPI bullet graphs on top; map and station detail below."],
    ["Pre-attentive colour", "Coral = casual, teal = member; everything else grey."],
    ["Responsive filters", "Date, rider type, temperature band, rain/dry."],
  ];
  pts.forEach(([h, b], i) => {
    txt(s, h, { x: 6.9, y: 1.4 + i * 1.2, w: 2.6, h: 0.3, fontSize: 14, bold: true, color: C.text2 });
    txt(s, b, { x: 6.9, y: 1.72 + i * 1.2, w: 2.6, h: 0.7, fontSize: 12, color: C.accent5 });
  });
  s.addNotes(`Live demo 1 (Tableau, 2 min): set temperature band to 80°F+ and weekend; the lakefront community areas light up. Median docked station sees ${D.median_stress} rides per dock per day; the busiest sees ${D.max_stress}. Caveat on screen: capacity is today's snapshot.`);
}
{
  const s = content("Act III · Evidence", "Decision engine: steer the forecast",
    `Streamlit System B: tomorrow's weather in, bikes and trucks out — ${pct(1 - T.mape_model / T.mape_baseline)} less error`);
  slot(s, 0.5, 1.35, 4.5, 3.7, "Brief 1 visual", "Casual vs member weather response (PNG, 1920 px wide)");
  stat(s, 5.3, 1.35, 2.1, pct(T.mape_model, 1), "model error (MAPE), Jun–Sep 2026", C.accent1);
  stat(s, 7.45, 1.35, 2.1, pct(T.mape_baseline, 1), "same day last year", C.accent3);
  const MON = { "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep" };
  const ho = D.holdout, lab = ho.date.map((d) => (d.slice(8) === "01" ? MON[d.slice(5, 7)] : " "));
  s.addChart(pres.charts.LINE, [
    { name: "Actual", labels: lab, values: ho.total_actual },
    { name: "Model", labels: lab, values: ho.total_model },
    { name: "Same day last year", labels: lab, values: ho.total_baseline },
  ], { x: 5.2, y: 2.45, w: 4.3, h: 2.6, chartColors: [H.dk1, MEMBER, GREY], lineSize: 1.5, lineDataSymbol: "none",
    showTitle: true, title: "Total rides per day on 122 unseen days", showLegend: true, legendPos: "t",
    catAxisLabelFrequency: 1, valAxisLabelFormatCode: "#,##0", ...axis, objectName: id("holdout") });
  s.addNotes(`Live demo 2 (Streamlit, 3 min): pick a Saturday in June, slide temperature from 60 to 85°F, then add 0.5 in of rain; casual rides swing far more than member rides, and the station tab lists where to stage bikes. H1: trained before June 2026, tested on 122 days it never saw: MAPE ${pct(T.mape_model, 1)} vs ${pct(T.mape_baseline, 1)} for same-day-last-year (casual ${pct(D.metrics.casual.mape_model, 1)} vs ${pct(D.metrics.casual.mape_baseline, 1)}).`);
}
{
  const s = content("Act III · Evidence", "Value creation, risk and ROI",
    `A lakefront pilot pays back if it lifts bike availability by ≥ ${pct(roi.break_even_availability_gain, 1)} on warm weekends`);
  const names = ["Low", "Base", "High"], keys = ["low", "base", "high"];
  s.addChart(pres.charts.BAR, [
    { name: "Extra revenue", labels: names, values: keys.map((x) => sc[x].revenue_usd / 1000) },
    { name: "Extra truck cost", labels: names, values: keys.map((x) => sc[x].cost_usd / 1000) },
  ], { x: 0.5, y: 1.35, w: 4.6, h: 2.3, barDir: "col", barGapWidthPct: 50, chartColors: [MEMBER, GREY],
    showTitle: true, title: `One summer, ${roi.target_days} warm weekend days, 20 stations ($k)`, showLegend: true, legendPos: "t",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisHidden: true, ...axis, valGridLine: { style: "none" }, objectName: id("roi") });
  stat(s, 0.5, 3.8, 1.5, usd(sc.low.net_usd), "net, low", C.accent5);
  stat(s, 2.05, 3.8, 1.5, usd(sc.base.net_usd), "net, base", C.accent1);
  stat(s, 3.6, 3.8, 1.5, usd(sc.high.net_usd), "net, high", C.accent1);
  txt(s, `Assumptions (model/roi.py): $${roi.single_ride_price_usd} per casual ride at 2026 prices, 50–90% realised; +10% availability → +12% rides (Kabra et al., Management Science); $75 per truck-hour.`,
    { x: 0.5, y: 4.62, w: 4.7, h: 0.45, fontSize: 10, color: C.accent5 });
  slot(s, 5.4, 1.35, 4.1, 3.7, "Brief 3 visual", "When the forecast misses, and what it costs (PNG, 1920 px wide)");
  s.addNotes(`Assumptions (model/roi.py, all editable): 2026 Divvy single-ride prices ($1 unlock, $0.20/min classic, $0.44/min e-bike → $${roi.single_ride_price_usd} per average casual ride, 50-90% realised for pass holders); +10% availability → +12% rides (Kabra, Belavina & Girotra, Management Science); one extra truck shift (6-10 h at $75/h) per warm weekend day. Honest read: the value hinges on the availability gain, which public data cannot measure — so the pilot measures it. Upside not counted: trucks freed on cold, rainy days, and converting warm-weekend casual riders into members.`);
}
{
  const s = content("Act III · Evidence", "Roadmap, governance and the decision gate",
    "Measure first, pilot in summer, scale only if the numbers clear the bar", "DECISION_DARK");
  const phases = [
    ["Jan – Mar 2027", "Build", "Daily forecast job; log live dock status to measure empty/full minutes"],
    ["Apr 2027", "Baseline", "Measure availability at 20 pilot + 20 control stations"],
    ["May – Sep", "Pilot", "Forecast-triggered truck shift on each warm weekend day"],
    ["Oct 2027", "Gate", `Scale if availability +${pct(roi.break_even_availability_gain, 1)} and MAPE < 20%`],
  ];
  s.addShape(pres.shapes.LINE, { x: 0.7, y: 1.72, w: 8.6, h: 0, line: { color: C.accent3, width: 2 }, objectName: id("timeline") });
  phases.forEach(([when, h, b], i) => {
    const x = 0.5 + i * 2.3;
    s.addShape(pres.shapes.OVAL, { x: x + 0.1, y: 1.6, w: 0.24, h: 0.24, fill: { color: i === 3 ? C.accent4 : C.accent1 }, line: { color: C.text2 }, objectName: id("milestone") });
    txt(s, when, { x, y: 1.95, w: 2.1, h: 0.25, fontSize: 11, color: C.accent6 });
    txt(s, h, { x, y: 2.2, w: 2.1, h: 0.35, fontSize: 16, bold: true, color: C.background1, fontFace: THEME.headFontFace });
    txt(s, b, { x, y: 2.55, w: 2.1, h: 0.7, fontSize: 11, color: C.accent6 });
  });
  txt(s, "QA / QC: monthly pipeline run with a quality log per file  ·  weekly dated GBFS snapshot  ·  alert if forecast error > 20% for 7 days",
    { x: 0.5, y: 3.35, w: 9, h: 0.3, fontSize: 11, color: C.accent6 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.8, w: 9, h: 1.25, rectRadius: 0.08, fill: { color: C.accent4 }, line: { color: C.accent4 }, objectName: id("gate") });
  txt(s, "THE DECISION TODAY", { x: 0.75, y: 3.92, w: 4, h: 0.25, fontSize: 11, bold: true, color: C.text2 });
  txt(s, `Approve a May–Sep 2027 pilot at the 20 busiest casual stations: one extra truck shift on each forecast warm weekend day (about $${(sc.base.cost_usd / 1000).toFixed(0)}k), plus dock-status logging to measure the gain.`,
    { x: 0.75, y: 4.2, w: 8.5, h: 0.8, fontSize: 15, bold: true, color: C.text2 });
  s.addNotes("Close on the ask, then stop talking. Phased gates keep risk low: nothing scales unless the measured availability gain clears break-even and the forecast stays accurate. Governance is automated: the same pipeline, quality log and lineage that built this deck run monthly.");
}

// ======================================================= APPENDIX =======
pres.addSection({ title: "Appendix" });
{
  const s = content("Appendix", "Appendix A · Methodological defense", "Model specification, holdout test and benchmark");
  txt(s, [
    { text: "Forecast (H1)", options: { bold: true, breakLine: true } },
    { text: "One linear regression per rider type on log(1 + daily rides); total = casual + member.", options: { bullet: true, breakLine: true } },
    { text: "Features: temperature and its square, precipitation, rain day, snow depth, wind, weekday, month, trend, holidays split warm/cold season.", options: { bullet: true, breakLine: true } },
    { text: `Train ${D.metrics.train_days} days before Jun 2026; test ${D.metrics.test_days} days, Jun–Sep 2026.`, options: { bullet: true, breakLine: true } },
    { text: "Weather sensitivity (KPI 2)", options: { bold: true, breakLine: true } },
    { text: "log(rides) ~ temperature + rain day + weekend + holiday + trend; effect = exp(β) − 1.", options: { bullet: true, breakLine: true } },
    { text: `R² ${sens.casual.r2} casual, ${sens.member.r2} member. One average slope; flattens above 80°F.`, options: { bullet: true } },
  ], { x: 0.5, y: 1.4, w: 4.5, h: 3.6, fontSize: 12, paraSpaceAfter: 4 });
  const head = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  const row = (lab, r) => [lab, pct(D.metrics[r].mape_model, 1), pct(D.metrics[r].mape_baseline, 1), pct(D.lgbm[r].mape_lgbm, 1)];
  s.addTable([[head("Holdout MAPE"), head("Regression"), head("Last year"), head("LightGBM")],
    row("Casual", "casual"), row("Member", "member"), row("Total", "total")], {
    x: 5.3, y: 1.4, w: 4.2, colW: [1.2, 1.0, 1.0, 1.0], fontSize: 11, color: C.text1, align: "center",
    border: { type: "solid", pt: 0.5, color: "D5DEE0" }, rowH: 0.34, objectName: id("mape") });
  const srow = (r) => [r.rider_type[0].toUpperCase() + r.rider_type.slice(1), signed(r.pct_per_10f), signed(r.pct_rain_day), signed(r.pct_weekend), signed(r.pct_holiday)];
  s.addTable([[head("KPI 2"), head("+10°F"), head("Rain"), head("Weekend"), head("Holiday")], ...D.sensitivity.map(srow)], {
    x: 5.3, y: 3.15, w: 4.2, colW: [0.9, 0.8, 0.8, 0.85, 0.85], fontSize: 11, color: C.text1, align: "center",
    border: { type: "solid", pt: 0.5, color: "D5DEE0" }, rowH: 0.34, objectName: id("sens") });
  s.addNotes("If asked why not a fancier model: LightGBM with the same features matches but does not beat the regression on total rides, and it cannot be explained to an operations lead. Known miss: Juneteenth is under-forecast because there are only two summers of holidays to learn from.");
}
{
  const s = content("Appendix", "Appendix B · Data audit and limitations", "What the numbers can and can't support");
  const head = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  const e = D.match_era, r1 = (lab, x) => [lab, pct(x.id || 0, 1), pct(x.name || 0, 1), pct(x.coords || 0, 1), pct(x.unmatched || 0, 1)];
  s.addTable([[head("Station match"), head("ID"), head("Name"), head("≤150 m"), head("None")],
    r1("Before Jun 2025", e.legacy), r1("From Jun 2025", e.chi), r1("All trips", D.match)], {
    x: 0.5, y: 1.4, w: 4.4, colW: [1.4, 0.75, 0.75, 0.75, 0.75], fontSize: 11, color: C.text1, align: "center",
    border: { type: "solid", pt: 0.5, color: "D5DEE0" }, rowH: 0.34, objectName: id("match-era") });
  txt(s, "Reproduce: pip install -r requirements.txt · cp config.local.example.yaml config.local.yaml · dvc repro · python model/forecast.py · streamlit run app/app.py",
    { x: 0.5, y: 3.0, w: 4.4, h: 0.9, fontSize: 11, color: C.accent5, fontFace: "Courier New" });
  txt(s, [
    { text: "Dock capacity is a 2026-11-26 snapshot applied to past rides.", options: { bullet: true, breakLine: true } },
    { text: "Station names change for one ID; some removed docks fold into a neighbour within 150 m.", options: { bullet: true, breakLine: true } },
    { text: "Dockless GPS is rounded to ~1 km, so community areas near boundaries can be off.", options: { bullet: true, breakLine: true } },
    { text: "Public trip data never shows a rider who found an empty dock: lost demand is assumed, not observed.", options: { bullet: true, breakLine: true } },
    { text: "ROI uses list prices and an assumed truck-hour cost; it is a range, not a budget.", options: { bullet: true, breakLine: true } },
    { text: "Two years of data: summer holidays and extreme heat have few examples.", options: { bullet: true } },
  ], { x: 5.2, y: 1.4, w: 4.3, h: 3.6, fontSize: 12, paraSpaceAfter: 6 });
  s.addNotes("Use this slide for Q&A on data quality. Every limitation here is also logged in the README data notes and in the pipeline's quality tables.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  const theme = process.env.APPLY_THEME;
  if (theme) await require(theme).applyTheme(OUT, THEME);
  console.log("wrote", path.relative(process.cwd(), OUT));
})();
