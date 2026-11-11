# Go-live report template

The go-live report is one self-contained HTML file, `go-live-report.html`, in the root of the developer's project. Build it from the template below:

1. Write the HTML in the code block below to `go-live-report.html` and replace every `{{PLACEHOLDER}}`.
2. Repeat the blocks marked `REPEAT` once per item, and delete the example rows.
3. Keep the structure and styles. Do not add external fonts, scripts, images or links other than docs.velafi.com.
4. HTML-escape everything you insert (`&`, `<`, `>`, `"`, `'`), especially code snippets and error messages.
5. Never insert secrets, tokens, full account numbers or customer personal data.
6. Status classes: `fail`, `warn`, `pass`, `na`, `np` (NOT PROVABLE IN SANDBOX). Always keep the word inside the pill.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VelaFi go-live report: {{PROJECT}}</title>
<style>
:root {
  --bg: #f5f7f8; --surface: #ffffff; --ink: #12202b; --muted: #5a6b78; --line: #dde3e8; --accent: #0b6e6e; --code-bg: #eef2f4;
  --fail: #c0362c; --fail-bg: #fdecea; --fail-line: #f3c4bf;
  --warn: #9a6400; --warn-bg: #fff4dc; --warn-line: #f0d9a3;
  --pass: #1f7a45; --pass-bg: #e6f5ec; --pass-line: #b9e1c8;
  --na: #66727c; --na-bg: #eef1f3; --na-line: #d5dbe0;
  --np: #2f5fa8; --np-bg: #e8effa; --np-line: #c3d4ef;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e161c; --surface: #15212a; --ink: #e6edf2; --muted: #9aabb8; --line: #263540; --accent: #4fc2c2; --code-bg: #1c2a34;
    --fail: #ff8a7f; --fail-bg: #3a1c1a; --fail-line: #6b2d28;
    --warn: #f2c063; --warn-bg: #33270f; --warn-line: #5e4719;
    --pass: #6fd39a; --pass-bg: #13301f; --pass-line: #245638;
    --na: #a7b3bc; --na-bg: #1d2830; --na-line: #34434e;
    --np: #8fb4f0; --np-bg: #182640; --np-line: #2c4470;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 var(--sans); padding: 40px 16px 64px; }
.wrap { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: 36px; }
h1, h2, h3 { margin: 0; line-height: 1.2; letter-spacing: -0.01em; }
h1 { font-size: clamp(26px, 4vw, 36px); }
h2 { font-size: 21px; }
h3 { font-size: 16px; }
p { margin: 0; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: 0.86em; background: var(--code-bg); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }
.eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
.muted { color: var(--muted); }
section { display: flex; flex-direction: column; gap: 14px; }
.head { display: flex; flex-direction: column; gap: 4px; }
.head p { color: var(--muted); max-width: 70ch; }
header { display: flex; flex-direction: column; gap: 10px; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 20px; font-size: 14px; color: var(--muted); }
.meta b { color: var(--ink); font-weight: 600; }

.verdict { display: grid; grid-template-columns: auto 1fr; gap: 16px; align-items: start; border: 1px solid; border-radius: 12px; padding: 20px 22px; }
.verdict .big { font-weight: 700; font-size: 15px; letter-spacing: 0.04em; color: var(--surface); border-radius: 999px; padding: 6px 14px; white-space: nowrap; }
.verdict p { font-size: 16px; }
.verdict p + p { margin-top: 6px; font-size: 14px; color: var(--muted); }
.verdict.fail { background: var(--fail-bg); border-color: var(--fail-line); } .verdict.fail .big { background: var(--fail); }
.verdict.warn { background: var(--warn-bg); border-color: var(--warn-line); } .verdict.warn .big { background: var(--warn); }
.verdict.pass { background: var(--pass-bg); border-color: var(--pass-line); } .verdict.pass .big { background: var(--pass); }

.score { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.tile { border: 1px solid; border-radius: 12px; padding: 16px 18px; display: flex; flex-direction: column; gap: 2px; }
.tile .n { font-size: 38px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.tile .l { font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.tile .d { font-size: 13px; color: var(--muted); }
.tile.fail { background: var(--fail-bg); border-color: var(--fail-line); color: var(--fail); }
.tile.warn { background: var(--warn-bg); border-color: var(--warn-line); color: var(--warn); }
.tile.pass { background: var(--pass-bg); border-color: var(--pass-line); color: var(--pass); }
.tile.na   { background: var(--na-bg);   border-color: var(--na-line);   color: var(--na); }

.pill { display: inline-flex; align-items: center; gap: 6px; border: 1px solid; border-radius: 999px; padding: 2px 10px 2px 8px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em; white-space: nowrap; }
.pill::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.pill.fail { color: var(--fail); background: var(--fail-bg); border-color: var(--fail-line); }
.pill.warn { color: var(--warn); background: var(--warn-bg); border-color: var(--warn-line); }
.pill.pass { color: var(--pass); background: var(--pass-bg); border-color: var(--pass-line); }
.pill.na   { color: var(--na);   background: var(--na-bg);   border-color: var(--na-line); }
.pill.np   { color: var(--np);   background: var(--np-bg);   border-color: var(--np-line); }
.tally { display: flex; flex-wrap: wrap; gap: 6px; }

.cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.card ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
.card h3 { display: flex; align-items: center; gap: 8px; }
.dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.card.edge-fail { border-color: var(--fail-line); border-left: 4px solid var(--fail); }
.card.edge-pass { border-left: 4px solid var(--pass); }
.card.edge-warn { border-left: 4px solid var(--warn); }
.card.edge-np   { border-left: 4px solid var(--np); }
.card.edge-na   { border-left: 4px solid var(--na); }
.row { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.id { font-family: var(--mono); font-size: 13px; font-weight: 600; }
.fix { font-size: 14px; background: var(--bg); border-radius: 8px; padding: 10px 12px; }
.ev { font-size: 13px; color: var(--muted); }
dl.facts { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; font-size: 14px; }
dl.facts dt { color: var(--muted); }
dl.facts dd { margin: 0; min-width: 0; }

.tw { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
table { border-collapse: collapse; width: 100%; min-width: 760px; font-size: 14px; }
th, td { text-align: left; vertical-align: top; padding: 10px 14px; border-top: 1px solid var(--line); }
thead th { border-top: 0; background: var(--bg); color: var(--muted); font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
td.num { font-family: var(--mono); font-size: 13px; color: var(--muted); white-space: nowrap; }
td.res { white-space: nowrap; }

ul.checks { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 20px; font-size: 14px; }
ul.checks li { min-width: 0; }
ul.checks .ev { display: block; }
ul.plain { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
ul.plain li { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.note { font-size: 13px; color: var(--muted); border-top: 1px solid var(--line); padding-top: 16px; }

@media (max-width: 820px) { .score { grid-template-columns: repeat(2, minmax(0, 1fr)); } .cols, .two, ul.checks { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 420px) { .verdict { grid-template-columns: minmax(0, 1fr); } .verdict .big { justify-self: start; } }
@media print { body { background: #fff; padding: 0; } .card, .tw, .verdict, .tile { break-inside: avoid; } }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <span class="eyebrow">VelaFi go-live check</span>
    <h1>Go-live report: {{PROJECT}}</h1>
    <div class="meta">
      <span>Date <b>{{DATE}}</b></span>
      <span>Flows <b>{{FLOWS, e.g. MXN collections (SPEI) · MXN payouts}}</b></span>
      <span>Event types <b>{{EVENT TYPES}}</b></span>
      <span>Code <b>{{MAIN FILES OR FOLDERS, LANGUAGE}}</b></span>
    </div>
  </header>

  <!-- Verdict: class "fail" + NOT READY, "warn" + READY WITH WARNINGS, or "pass" + READY. -->
  <div class="verdict fail">
    <span class="big">NOT READY</span>
    <div>
      <p><b>{{ONE SENTENCE: THE VERDICT AND THE MAIN REASON}}</b> {{ONE SENTENCE: WHAT MUST CHANGE, IN PLAIN WORDS}}</p>
      <p>This review covers your side of the integration only. It cannot check VelaFi's side: the production IP whitelist, production webhooks, limits or channel setup.</p>
    </div>
  </div>

  <!-- Scorecard: counts of the items in the Blocking, Warnings, Passed and Not applicable sections below. -->
  <div class="score">
    <div class="tile fail"><span class="n">{{N}}</span><span class="l">Fail</span><span class="d">Blocks go-live</span></div>
    <div class="tile warn"><span class="n">{{N}}</span><span class="l">Warn</span><span class="d">Fix before scaling</span></div>
    <div class="tile pass"><span class="n">{{N}}</span><span class="l">Pass</span><span class="d">Checked with evidence</span></div>
    <div class="tile na"><span class="n">{{N}}</span><span class="l">N/A</span><span class="d">Not used or not run</span></div>
  </div>

  <!-- Plain-language summary for non-technical readers. Short sentences, no code, no file names. -->
  <section>
    <div class="head"><span class="eyebrow">In plain terms</span><h2>What this review tells you</h2></div>
    <div class="cols">
      <div class="card"><h3><span class="dot" style="background:var(--pass)"></span>Works today</h3><ul><li>{{ITEM}}</li></ul></div>
      <div class="card"><h3><span class="dot" style="background:var(--fail)"></span>Needed before production</h3><ul><li>{{ITEM}}</li></ul></div>
      <div class="card"><h3><span class="dot" style="background:var(--na)"></span>Not covered by this review</h3><ul><li>VelaFi's side: production IP whitelist, production webhooks, limits and channel setup.</li><li>{{ITEM, e.g. failure paths the sandbox did not produce}}</li></ul></div>
    </div>
  </section>

  <section>
    <div class="head"><span class="eyebrow">Checks</span><h2>Self-checks</h2></div>
    <ul class="plain">
      <li><span class="pill pass">PASS</span><span>Credential check (sandbox): {{RESULT LINE}}</span></li>
      <li><span class="pill na">NOT RUN</span><span>Webhook endpoint self-test: {{RESULT OR REASON}}</span></li>
    </ul>
  </section>

  <!-- Flow traces: one card per launching flow (references/flow-trace.md). -->
  <section>
    <div class="head"><span class="eyebrow">Flow trace</span><h2>Each flow, step by step</h2><p>Every step the flow needs, traced through the code from the first call to the final state in your system.</p></div>

    <!-- REPEAT per flow -->
    <div class="card">
      <div class="row"><h3>{{FLOW NAME}}</h3><div class="tally"><span class="pill fail">{{N}} FAIL</span><span class="pill warn">{{N}} WARN</span><span class="pill pass">{{N}} PASS</span><span class="pill na">{{N}} N/A</span></div></div>
      <div class="tw"><table>
        <thead><tr><th>#</th><th>Step</th><th>Code</th><th>What we checked</th><th>Result</th></tr></thead>
        <tbody>
          <!-- REPEAT per step. "What we checked": request, response handling, state and money, in one or two sentences. -->
          <tr><td class="num">1</td><td>{{STEP}}</td><td><code>{{file:line}}</code></td><td>{{FINDING}}</td><td class="res"><span class="pill pass">PASS</span></td></tr>
        </tbody>
      </table></div>
    </div>
  </section>

  <!-- Sandbox runs (references/sandbox-run.md). If the developer skipped it, keep one card with class edge-na and a NOT RUN pill. -->
  <section>
    <div class="head"><span class="eyebrow">Sandbox run</span><h2>{{HEADLINE, e.g. Both flows ran end to end / Not run}}</h2></div>
    <div class="two">
      <!-- REPEAT per flow. Edge and pill: pass, fail, np (NOT PROVABLE IN SANDBOX) or na (NOT RUN). -->
      <div class="card edge-pass">
        <div class="row"><h3>{{FLOW NAME}}</h3><span class="pill pass">PASS</span></div>
        <dl class="facts">
          <dt>Triggered by</dt><dd>{{ROUTE / COMMAND}}</dd>
          <dt>IDs</dt><dd><code>{{clientId, orderId or txId}}</code></dd>
          <dt>Final status</dt><dd>{{STATUS}} after {{MINUTES}}</dd>
          <dt>Your system</dt><dd>{{STATE AND LEDGER CHANGE}}</dd>
          <dt>Duplicate clientId</dt><dd>{{REJECTED AND LOOKED UP / NOT HANDLED / N/A}}</dd>
        </dl>
      </div>
    </div>
    <p class="muted">A sandbox run never proves VelaFi's side of the integration.</p>
  </section>

  <!-- Blocking items. If there are none, replace the cards with one line: "No blocking items." -->
  <section>
    <div class="head"><span class="eyebrow">Blocking</span><h2>Fix these before production</h2></div>
    <div class="two">
      <!-- REPEAT per FAIL -->
      <div class="card edge-fail">
        <div class="row"><h3><span class="id" style="color:var(--fail)">B1</span> {{SHORT TITLE}}</h3><span class="pill fail">FAIL</span></div>
        <p>{{WHY IT MATTERS, IN PLAIN WORDS}}</p>
        <p class="fix"><b>Fix:</b> {{THE FIX}}</p>
        <p class="ev">Evidence: <code>{{file:line}}</code> {{DETAIL}} · <a href="https://docs.velafi.com/{{PATH}}">{{DOC TITLE}}</a></p>
      </div>
    </div>
  </section>

  <section>
    <div class="head"><span class="eyebrow">Warnings</span><h2>Fix before scaling up</h2></div>
    <div class="tw"><table>
      <thead><tr><th>#</th><th>Issue</th><th>Evidence</th><th>Fix</th><th>Doc</th></tr></thead>
      <tbody>
        <!-- REPEAT per WARN. If there are none, one row: "No warnings." -->
        <tr><td class="num" style="color:var(--warn)">W1</td><td><b>{{ISSUE}}</b></td><td><code>{{file:line}}</code> {{DETAIL}}</td><td>{{FIX}}</td><td><a href="https://docs.velafi.com/{{PATH}}">{{DOC}}</a></td></tr>
      </tbody>
    </table></div>
  </section>

  <section>
    <div class="head"><span class="eyebrow">Passed</span><h2>Checked and correct</h2></div>
    <ul class="checks">
      <!-- REPEAT per PASS -->
      <li><span class="pill pass">PASS</span> {{ITEM}}<span class="ev"><code>{{file:line}}</code></span></li>
    </ul>
  </section>

  <section>
    <div class="head"><span class="eyebrow">Not applicable</span><h2>Not used or not run</h2></div>
    <ul class="plain">
      <!-- REPEAT per N/A or not-run item -->
      <li><span class="pill na">N/A</span><span>{{ITEM}}: {{REASON}}</span></li>
    </ul>
  </section>

  <section>
    <div class="head"><span class="eyebrow">Next steps</span><h2>What happens next</h2></div>
    <div class="card"><ul>
      <li>{{OFFER TO FIX THE FAIL ITEMS ONE AT A TIME}}</li>
      <li>Webhooks are not sent in the sandbox, so the first real deliveries arrive in production. After you approve going live, start with low-value transactions.</li>
    </ul></div>
  </section>

  <p class="note">Generated by the <code>velafi-go-live-check</code> agent skill. See <a href="https://docs.velafi.com/docs/developer-tools/agent-skills">VelaFi Agent Skills</a> and the <a href="https://docs.velafi.com/docs/use-cases/go-live-checklist">go-live checklist</a>.</p>

</div>
</body>
</html>
```
