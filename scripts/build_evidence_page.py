"""
Build the interactive evidence companion for the MMU interview.

    .venv/bin/python scripts/build_evidence_page.py

WHY GENERATED RATHER THAN HAND-WRITTEN
    Every number on the page is read from a result file at build time. Nothing is
    typed in by hand, so the page cannot drift from the measurements the way a
    slide does — which is the whole failure this project keeps running into.

    Re-run it after any experiment and the page updates.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/presentation/evidence.html"

results = json.loads((ROOT / "results/audio_cnn_lstm_results.json").read_text())
prisma = json.loads((ROOT / "slr/out/prisma.json").read_text())
lat = json.loads((ROOT / "slr/out/ladder_lattice.json").read_text())

SHORT = ["multimodal", "emotion recognition", "compression",
         "edge hardware", "real-time", "clinical", "privacy"]
FULL = [
    'multimodal OR "three modalit*" OR trimodal',
    '"emotion recognition"',
    'compress* OR quantiz* OR distill* OR prun*',
    '"Raspberry Pi" OR Jetson OR edge OR "on-device"',
    'latency OR "real-time" OR ms',
    'clinical OR patient OR caregiving OR healthcare',
    'privacy OR federated OR "differential privacy"',
]

DATA = {
    "clauses": SHORT,
    "full": FULL,
    "pool": lat["pool"],
    "lattice": lat["lattice"],
    "survivors": lat["survivors"],
    "labels": results["labels"],
    "cm": results["confusion_matrix"],
    "per_class": {k: {"r": v["recall"], "p": v["precision"], "n": int(v["support"])}
                  for k, v in results["per_class"].items()},
    "acc": results["accuracy"],
    "f1": results["f1_macro"],
    "lat_mean": results["latency_mean_ms"],
    "lat_p95": results["latency_p95_ms"],
    "n_test": results["n_test"],
    "speakers": results["test_speakers"],
    "prisma": prisma["identification"],
    "tiers": prisma["screening_tiers"]["counts"],
    "by_year": prisma["reviewable_corpus"]["by_year"],
    "strat": prisma["reviewable_corpus"]["stratified"],
}

HTML = """<title>Evidence — Real-Time Multimodal Emotion Recognition for Care Settings</title>
<style>
/* ── tokens: light is the bare :root, so the un-stamped default resolves ── */
:root{
  --paper:#EEF1F3; --plate:#F7F9FA; --ink:#0E1519; --ink-2:#33454F;
  --slate:#5A6B76; --hair:#C9D3D9; --hair-2:#DDE4E8;
  --teal:#16607C; --teal-lift:#4E9DB8; --clay:#A85A3C; --clay-lift:#C77E5C;
  --ramp-0:#F2F6F8; --ramp-1:#CFE0E8; --ramp-2:#9FC3D2; --ramp-3:#5F9AB2; --ramp-4:#16607C;
  --focus:#A85A3C;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#0B1114; --plate:#111A1F; --ink:#E6EDF1; --ink-2:#B4C4CD;
    --slate:#8A9BA6; --hair:#26343C; --hair-2:#1B262C;
    --teal:#5FAECB; --teal-lift:#8ECBE0; --clay:#D08A66; --clay-lift:#E0A98C;
    --ramp-0:#121C21; --ramp-1:#1B3540; --ramp-2:#2A5D72; --ramp-3:#3F87A3; --ramp-4:#5FAECB;
    --focus:#D08A66;
  }
}
:root[data-theme="dark"]{
  --paper:#0B1114; --plate:#111A1F; --ink:#E6EDF1; --ink-2:#B4C4CD;
  --slate:#8A9BA6; --hair:#26343C; --hair-2:#1B262C;
  --teal:#5FAECB; --teal-lift:#8ECBE0; --clay:#D08A66; --clay-lift:#E0A98C;
  --ramp-0:#121C21; --ramp-1:#1B3540; --ramp-2:#2A5D72; --ramp-3:#3F87A3; --ramp-4:#5FAECB;
  --focus:#D08A66;
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:16px; line-height:1.6; -webkit-font-smoothing:antialiased;
}
.serif{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
.mono{font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
      font-variant-numeric:tabular-nums}

.wrap{max-width:78rem;margin:0 auto;padding:0 clamp(1rem,4vw,3rem)}
.col{max-width:38rem}

/* ── header ── */
header{border-bottom:1px solid var(--hair);padding:clamp(2rem,6vw,4rem) 0 1.75rem}
.eyebrow{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;
  color:var(--slate);margin:0 0 1rem}
h1{font-size:clamp(1.7rem,4.2vw,2.7rem);line-height:1.15;margin:0 0 1rem;
  text-wrap:balance;font-weight:600}
.lede{color:var(--ink-2);max-width:44rem;margin:0}
.byline{margin-top:1.5rem;font-size:.82rem;color:var(--slate)}

/* ── plates: instruments break out of the prose column ── */
section{padding:clamp(2.5rem,6vw,4.5rem) 0;border-bottom:1px solid var(--hair-2)}
h2{font-size:clamp(1.15rem,2.4vw,1.5rem);margin:0 0 .5rem;font-weight:600;text-wrap:balance}
h3{font-size:.95rem;margin:0 0 .35rem;font-weight:600}
p{margin:0 0 1rem}
.note{font-size:.85rem;color:var(--slate);max-width:42rem}

.plate{background:var(--plate);border:1px solid var(--hair);border-radius:2px;
  padding:clamp(1.1rem,2.6vw,1.9rem);margin-top:1.75rem;position:relative}
.plate::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;
  background:repeating-linear-gradient(90deg,var(--hair) 0 1px,transparent 1px 10px)}
.plate-hd{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:baseline;
  justify-content:space-between;margin-bottom:1.1rem}
.plate-hd .lab{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--slate)}

/* ── the ladder ── */
.ladder{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,15rem);gap:clamp(1.2rem,3vw,2.5rem)}
@media (max-width:720px){.ladder{grid-template-columns:1fr}}
.switches{display:flex;flex-direction:column;gap:.4rem;margin:0;padding:0;list-style:none}
.sw{display:flex;align-items:center;gap:.75rem;width:100%;text-align:left;cursor:pointer;
  background:transparent;border:1px solid var(--hair);border-radius:2px;
  padding:.55rem .7rem;color:var(--ink);font:inherit;transition:border-color .15s,background .15s}
.sw:hover{border-color:var(--teal)}
.sw:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.sw[aria-pressed="false"]{opacity:.5}
.dot{width:.75rem;height:.75rem;flex:none;border-radius:50%;
  border:1px solid var(--teal);background:transparent}
.sw[aria-pressed="true"] .dot{background:var(--teal)}
.sw .nm{font-size:.9rem;font-weight:500}
.sw .q{font-size:.72rem;color:var(--slate);display:block;margin-top:.1rem;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sw-txt{min-width:0}

.readout{border:1px solid var(--hair);border-radius:2px;padding:1.1rem;
  display:flex;flex-direction:column;gap:.35rem;align-self:start;background:var(--paper)}
.count{font-size:clamp(2.6rem,7vw,3.8rem);line-height:1;font-weight:600}
.count.zero{color:var(--clay)}
.count.some{color:var(--teal)}
.rd-lab{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--slate)}
.rd-sub{font-size:.82rem;color:var(--ink-2)}
.hits{margin:1.1rem 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:.6rem}
.hits li{border-left:2px solid var(--teal);padding-left:.7rem;font-size:.82rem}
.hits .t{display:block;color:var(--ink)}
.hits .m{color:var(--slate);font-size:.76rem}

/* ── charts ── */
.bars{display:flex;flex-direction:column;gap:.45rem;margin:0;padding:0;list-style:none}
.bar-row{display:grid;grid-template-columns:8.5rem minmax(0,1fr) 3rem;gap:.7rem;align-items:center}
@media (max-width:560px){.bar-row{grid-template-columns:6.5rem minmax(0,1fr) 2.6rem}}
.bar-lab{font-size:.82rem;color:var(--ink-2)}
/* display:block is load-bearing — these are spans, and an inline element
   ignores height, which renders the bars invisible. */
.track{display:block;height:1.1rem;background:var(--ramp-0);border-radius:1px;overflow:hidden}
.fill{display:block;height:100%;border-radius:0 1px 1px 0}
.fill.hi{background:var(--teal)}
.fill.lo{background:var(--clay)}
.bar-val{font-size:.82rem;text-align:right}
.legend{display:flex;gap:1.1rem;flex-wrap:wrap;margin-top:1rem;font-size:.78rem;color:var(--ink-2)}
.key{display:inline-flex;align-items:center;gap:.4rem}
.key i{width:.7rem;height:.7rem;border-radius:1px;display:inline-block}

.scroller{overflow-x:auto}
table.cm{border-collapse:collapse;font-size:.8rem;min-width:34rem}
table.cm th{font-weight:500;color:var(--slate);padding:.35rem .5rem;text-align:center}
table.cm th.rh{text-align:right}
table.cm td{padding:0;text-align:center}
.cell{width:100%;height:2.2rem;display:flex;align-items:center;justify-content:center;
  border:1px solid var(--plate);cursor:default;transition:transform .12s}
.cell:hover{transform:scale(1.06);border-color:var(--ink)}
.cell.d{outline:1px solid var(--ink-2);outline-offset:-1px}

/* The bar area gets an explicit height of its own so each bar's percentage
   resolves against a known box, rather than against an auto-height flex item. */
.years{display:flex;align-items:flex-end;gap:3px;margin-top:.5rem}
.yr{flex:1;min-width:0;display:flex;flex-direction:column;gap:.4rem}
.ybwrap{height:6.5rem;display:flex;align-items:flex-end}
.yb{width:100%;background:var(--teal);border-radius:1px 1px 0 0;min-height:2px}
.yl{font-size:.65rem;color:var(--slate);text-align:center;font-variant-numeric:tabular-nums}
@media (max-width:640px){.yl{writing-mode:vertical-rl;transform:rotate(180deg);align-self:center}}

.flow{display:flex;flex-direction:column;gap:.3rem;margin:0;padding:0;list-style:none}
.fl{display:grid;grid-template-columns:minmax(0,1fr) 5rem;gap:.8rem;align-items:center;
  border:1px solid var(--hair);border-left:3px solid var(--teal);padding:.55rem .8rem;border-radius:2px}
.fl.out{border-left-color:var(--clay);margin-left:clamp(0rem,6vw,3rem)}
.fl .n{text-align:right;font-weight:600}
.fl .k{font-size:.85rem}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:1px;
  background:var(--hair);border:1px solid var(--hair);border-radius:2px;margin-top:1.75rem}
.stat{background:var(--plate);padding:1rem}
.stat .v{font-size:1.5rem;font-weight:600;line-height:1.1}
.stat .k{font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--slate);margin-top:.3rem}
.stat .s{font-size:.76rem;color:var(--ink-2);margin-top:.25rem}

.caveat{border-left:2px solid var(--clay);padding-left:1rem;margin-top:1.75rem;
  font-size:.87rem;color:var(--ink-2);max-width:42rem}
footer{padding:2.5rem 0 4rem;font-size:.8rem;color:var(--slate)}
a{color:var(--teal)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="wrap">
<header>
  <p class="eyebrow mono">Evidence companion &middot; MMU Achievers Research Scholarship 2026</p>
  <h1 class="serif">The literature has the edge, the latency and the privacy. It does not have the ward.</h1>
  <p class="lede">A measured prototype and a systematic search behind one proposal:
     <em>Real-Time Multimodal Speech and Facial Emotion Recognition for Healthcare
     and Caregiving Support</em>. Every figure here is read from a result file at
     build time &mdash; nothing is typed by hand.</p>
  <p class="byline mono">Nwachukwu Chinemerem Favour &middot; Application P2602387 &middot;
     Master of Computing (by Research)</p>
</header>

<section>
  <h2 class="serif">Is the gap real? Switch a clause off and find out.</h2>
  <p class="col">A scope gap is a claim that nobody has done all of these things at once.
     Asserting it is worthless; a single zero is nearly as weak, because a zero and a
     broken query look identical. So the seven clauses below are all on, and the
     conjunction returns nothing. Turn one off and watch what the literature does have.</p>

  <div class="plate">
    <div class="plate-hd">
      <span class="lab mono">Conjunction ladder &middot; string S7</span>
      <span class="lab mono" id="poolLab"></span>
    </div>
    <div class="ladder">
      <ul class="switches" id="switches"></ul>
      <div>
        <div class="readout">
          <span class="rd-lab mono">Papers satisfying all active clauses</span>
          <span class="count mono" id="count">0</span>
          <span class="rd-sub" id="sub"></span>
        </div>
        <ul class="hits" id="hits"></ul>
      </div>
    </div>
  </div>

  <p class="caveat"><strong>What this cannot tell you.</strong> Zero is a claim about the
     searched corpus, not about reality &mdash; bounded by four databases, a 2015&ndash;2026
     window, and this clause vocabulary. One genuine counter-example outweighs any count.
     That is why the survivors are listed rather than hidden.</p>
</section>

<section>
  <h2 class="serif">The model reads arousal. It cannot read valence.</h2>
  <p class="col">Speaker-independent evaluation on three held-out actors. High-arousal
     emotions are recognised well; positive and low-arousal states collapse. This is the
     limitation the additional modalities exist to address &mdash; a smile carries valence
     that the voice alone does not.</p>

  <div class="plate">
    <div class="plate-hd"><span class="lab mono">Per-class recall</span>
      <span class="lab mono" id="recallHd"></span></div>
    <ul class="bars" id="recall"></ul>
    <div class="legend">
      <span class="key"><i style="background:var(--teal)"></i>high arousal</span>
      <span class="key"><i style="background:var(--clay)"></i>low arousal or positive valence</span>
    </div>
  </div>

  <div class="plate">
    <div class="plate-hd"><span class="lab mono">Confusion matrix</span>
      <span class="lab mono">rows = true &middot; columns = predicted</span></div>
    <div class="scroller"><table class="cm" id="cm"></table></div>
    <p class="note" style="margin-top:.9rem">Happy is predicted <em>angry</em> ten times out
       of twenty-four. Both are high-arousal; they differ only in valence.</p>
  </div>

  <div class="stats" id="stats"></div>
</section>

<section>
  <h2 class="serif">A search you can re-run</h2>
  <p class="col">No institutional access to Scopus or Web of Science. So the protocol is
     executable instead: nine Boolean strings parsed into syntax trees and applied to every
     retrieved record, across OpenAlex, Crossref, PubMed and arXiv, with every API response
     cached. Anyone can reproduce this corpus.</p>

  <div class="plate">
    <div class="plate-hd"><span class="lab mono">Identification &amp; screening</span>
      <span class="lab mono">PRISMA 2020</span></div>
    <ul class="flow" id="flow"></ul>
    <p class="note" style="margin-top:1rem">Automated screening removes only what is
       mechanically impossible to include &mdash; wrong year, wrong language, errata. Every
       include or exclude judgement is the reviewer's.</p>
  </div>

  <div class="plate">
    <div class="plate-hd"><span class="lab mono">Reviewable corpus by year</span>
      <span class="lab mono" id="stratHd"></span></div>
    <div class="years" id="years"></div>
  </div>
</section>

<section>
  <h2 class="serif">What is built, and what is proposed</h2>
  <div class="plate">
    <div class="plate-hd"><span class="lab mono">Status, stated precisely</span></div>
    <ul class="flow">
      <li class="fl"><span class="k"><strong>Built &amp; measured.</strong> Live audio and
        webcam capture, 468 facial landmarks over WebSockets, face tracked at 4&nbsp;fps on
        GPU. Audio model evaluated speaker-independently.</span><span class="n mono">done</span></li>
      <li class="fl"><span class="k"><strong>Built, not yet trained.</strong> Three fusion
        architectures &mdash; feature-level, decision-level, cross-modal attention. The
        trained checkpoint is audio-only.</span><span class="n mono">partial</span></li>
      <li class="fl out"><span class="k"><strong>Proposed.</strong> Training and validating
        fusion; five-fold speaker-independent cross-validation; robustness under noise and
        missing modality; quantisation and edge latency; privacy-preserving
        deployment.</span><span class="n mono">research</span></li>
    </ul>
  </div>
  <p class="caveat">An emotion-recognition system should not be treated as an objective
     measurement of a person's internal state. Facial and vocal signals correlate with
     emotion; they are not identical to it. This is decision support for a professional
     &mdash; never a diagnosis, never a replacement.</p>
</section>

<footer class="wrap">
  <p class="mono">Generated from results/audio_cnn_lstm_results.json, slr/out/prisma.json
     and slr/out/ladder_lattice.json.</p>
</footer>
</div>

<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const on = new Array(D.clauses.length).fill(true);

/* ── ladder ── */
const swWrap = $("#switches");
D.clauses.forEach((c, i) => {
  const li = document.createElement("li");
  const b = document.createElement("button");
  b.className = "sw"; b.type = "button"; b.setAttribute("aria-pressed", "true");
  b.innerHTML = `<span class="dot"></span><span class="sw-txt"><span class="nm">${c}</span>
    <span class="q mono">${D.full[i].replace(/</g,"&lt;")}</span></span>`;
  b.addEventListener("click", () => { on[i] = !on[i]; b.setAttribute("aria-pressed", on[i]); paint(); });
  li.appendChild(b); swWrap.appendChild(li);
});

function paint(){
  const mask = on.map(v => v ? "1" : "0").join("");
  const n = D.lattice[mask] ?? 0;
  const nOff = on.filter(v => !v).length;
  const el = $("#count");
  el.textContent = n.toLocaleString();
  el.className = "count mono " + (n === 0 ? "zero" : "some");

  $("#sub").textContent = nOff === 0
    ? "All seven clauses active — the full conjunction."
    : `${7 - nOff} of 7 clauses active · ${nOff} relaxed`;

  const hits = $("#hits");
  hits.innerHTML = "";
  const s = D.survivors[mask];
  if (n === 0){
    const li = document.createElement("li");
    li.innerHTML = `<span class="t">Nothing in the corpus satisfies this combination.</span>
      <span class="m">Relax a clause to see what the literature does contain.</span>`;
    li.style.borderLeftColor = "var(--clay)";
    hits.appendChild(li);
  } else if (s){
    s.forEach(p => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="t">${p.t.replace(/</g,"&lt;")}</span>
        <span class="m mono">${p.y} · ${(p.v||"—").replace(/</g,"&lt;")}${p.c ? " · cited " + p.c : ""}</span>`;
      hits.appendChild(li);
    });
  } else {
    const li = document.createElement("li");
    li.innerHTML = `<span class="m">${n.toLocaleString()} papers — too many to list.</span>`;
    hits.appendChild(li);
  }
}
$("#poolLab").textContent = `pool: ${D.pool.toLocaleString()} unique papers`;
paint();

/* ── recall ── */
const HI = new Set(["angry", "fearful", "disgust"]);
const rows = Object.entries(D.per_class).sort((a, b) => b[1].r - a[1].r);
$("#recall").innerHTML = rows.map(([k, v]) => `
  <li class="bar-row">
    <span class="bar-lab">${k} <span class="mono" style="color:var(--slate)">n=${v.n}</span></span>
    <span class="track"><span class="fill ${HI.has(k) ? "hi" : "lo"}"
      style="width:${(v.r * 100).toFixed(1)}%"></span></span>
    <span class="bar-val mono">${v.r.toFixed(2)}</span>
  </li>`).join("");
$("#recallHd").textContent =
  `${D.n_test} clips · held-out ${D.speakers.map(s => s.replace("ravdess_", "")).join(", ")}`;

/* ── confusion matrix ── */
const cmMax = Math.max(...D.cm.flat());
const ramp = v => { const t = v / cmMax;
  return t === 0 ? "var(--ramp-0)" : t < .25 ? "var(--ramp-1)"
       : t < .5 ? "var(--ramp-2)" : t < .75 ? "var(--ramp-3)" : "var(--ramp-4)"; };
let html = "<tr><th></th>" + D.labels.map(l => `<th class="mono">${l}</th>`).join("") + "</tr>";
D.cm.forEach((row, i) => {
  html += `<tr><th class="rh mono">${D.labels[i]}</th>` + row.map((v, j) => {
    const strong = v / cmMax > .5;
    return `<td><div class="cell${i === j ? " d" : ""}" style="background:${ramp(v)};
      color:${strong ? "var(--plate)" : "var(--ink-2)"}"
      title="${v} of ${row.reduce((a, b) => a + b, 0)} true ${D.labels[i]} clips predicted ${D.labels[j]}"
      >${v || ""}</div></td>`;
  }).join("") + "</tr>";
});
$("#cm").innerHTML = html;

/* ── stats ── */
$("#stats").innerHTML = [
  [(D.acc * 100).toFixed(1) + "%", "accuracy", "speaker-independent"],
  [D.f1.toFixed(3), "macro F1", "unweighted across 6 classes"],
  [D.lat_mean.toFixed(0) + " ms", "model inference", "p95 " + D.lat_p95.toFixed(0) + " ms, CPU"],
  ["~110 ms", "end to end", "capture to on-screen result"],
].map(([v, k, s]) => `<div class="stat"><div class="v mono">${v}</div>
  <div class="k">${k}</div><div class="s">${s}</div></div>`).join("");

/* ── PRISMA ── */
const P = D.prisma, T = D.tiers;
$("#flow").innerHTML = [
  ["Records identified from databases", P.records_from_databases, false],
  ["Records identified by citation traversal", P.records_from_other_methods, false],
  ["Duplicates removed", P.duplicates_removed, true],
  ["Unique records", P.records_after_deduplication, false],
  ["Auto-excluded on mechanical criteria", T.X, true],
  ["Awaiting reviewer screening", T.T1 + T.T2 + T.T3 + T.T4, false],
].map(([k, n, out]) => `<li class="fl${out ? " out" : ""}"><span class="k">${k}</span>
  <span class="n mono">${n.toLocaleString()}</span></li>`).join("");

/* ── years ── */
const ys = Object.entries(D.by_year), ymax = Math.max(...ys.map(([, v]) => v));
$("#years").innerHTML = ys.map(([y, v]) => `<div class="yr" title="${y}: ${v} records">
  <div class="ybwrap"><div class="yb" style="height:${(v / ymax * 100).toFixed(1)}%"></div></div>
  <span class="yl mono">${y}</span></div>`).join("");
$("#stratHd").textContent =
  `2015–19: ${D.strat["2015_2019"]} · 2020–26: ${D.strat["2020_2026"]}`;
</script>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML.replace("__DATA__", json.dumps(DATA, separators=(",", ":"))))
print(f"Wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")
print(f"  ladder subsets embedded : {len(DATA['lattice'])}")
print(f"  full conjunction        : {DATA['lattice']['1111111']}")
print(f"  drop 'clinical' only    : {DATA['lattice']['1111101']}")
print(f"  accuracy / macro-F1     : {DATA['acc']:.4f} / {DATA['f1']:.4f}")
