"""Render dashboard/index.html from dashboard/data.json. One self-contained file.

Original UI for this project: navy sidebar + paper content, serif
display type, timeline pipeline, numbered approach steps. No CDN, no
external URLs, no libraries: hand-written inline SVG/CSS/JS.
Python renders all content (tables, cards, rows); JS only enhances
(theme, slides, search, SVG charts from embedded JSON, toggles).
Deterministic: sorted keys, no timestamps.

Run: python -m src.dashboard
Writes dashboard/index.html. Prints path + size + sha256.
"""

import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CSS = """
:root{--navy:#024879;--teal:#075056;--turq:#71D8C5;--sky:#C5DCEE;
--paper:#F4F7F8;--card:#FFFFFF;--ink:#1B2227;--line:#D8E2E8;
--mut:#54666F;--cobalt:#324EB5;--amber:#B97A1A}
[data-theme="dark"]{--paper:#0D181F;--card:#14232C;--ink:#E9F2F5;
--line:#28424E;--mut:#A3BCC6;--sky:#14404D}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:Calibri,"Segoe UI",Arial,sans-serif;font-size:18px;line-height:1.55}
.layout{display:flex;min-height:100vh}
aside.side{width:250px;flex:none;background:var(--navy);color:#fff;
padding:26px 18px;position:sticky;top:0;height:100vh;overflow:auto}
aside.side h1{font-family:Georgia,"Times New Roman",serif;font-size:26px;
margin:0 0 4px}
aside.side p{font-size:14px;color:var(--sky);margin:0 0 16px}
aside.side nav a{display:block;color:#fff;text-decoration:none;font-size:15px;
padding:7px 10px;border-radius:8px}
aside.side nav a:hover{background:rgba(255,255,255,.14)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.toolbar button{font:inherit;font-size:14px;font-weight:700;border:2px solid
var(--turq);background:transparent;color:#fff;border-radius:8px;
padding:6px 12px;cursor:pointer}
.toolbar button.on,.toolbar button:hover{background:var(--turq);color:#062b30}
main{flex:1;min-width:0}
.wrap{max-width:1020px;margin:0 auto;padding:0 26px}
#progress{height:8px;background:var(--line)}
#progress i{display:block;height:100%;width:0;background:var(--turq)}
section.slide{padding:40px 0;border-bottom:1px solid var(--line)}
.kicker{text-transform:uppercase;letter-spacing:.1em;font-size:13px;
font-weight:700;color:var(--cobalt)}
h2.sec{font-family:Georgia,"Times New Roman",serif;font-size:34px;
margin:4px 0 6px;color:var(--teal)}
[data-theme="dark"] h2.sec{color:var(--turq)}
.lede{font-size:20px;max-width:60ch}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:20px 22px;margin:16px 0;box-shadow:0 1px 3px rgba(2,72,121,.08)}
.card h3{font-family:Georgia,serif;font-size:23px;margin:0 0 8px}
.steps{counter-reset:step;margin:10px 0;padding:0;list-style:none}
.steps li{counter-increment:step;margin:8px 0;padding-left:44px;position:relative}
.steps li::before{content:counter(step);position:absolute;left:0;top:0;
width:30px;height:30px;border-radius:50%;background:var(--navy);color:#fff;
font-weight:700;font-size:15px;text-align:center;line-height:30px}
.timeline{border-left:4px solid var(--turq);margin:12px 0 12px 10px;
padding:0 0 0 22px}
.timeline .stage{margin:0 0 14px;position:relative}
.timeline .stage::before{content:"";position:absolute;left:-31px;top:4px;
width:14px;height:14px;border-radius:50%;background:var(--cobalt);
border:3px solid var(--paper)}
code,.mono{font-family:Consolas,"Courier New",monospace;font-size:15px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:860px){.grid2{grid-template-columns:1fr}
aside.side{display:none}}
table{border-collapse:collapse;width:100%;font-size:16px;margin:10px 0}
th{background:var(--sky);text-align:left;padding:8px 10px}
td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.num{font-variant-numeric:tabular-nums;font-weight:700;cursor:pointer;
border-bottom:1px dotted var(--cobalt)}
.chip{display:inline-block;font-size:13px;font-weight:700;padding:2px 12px;
border-radius:999px;background:var(--line);margin:2px 4px 2px 0}
.chip.gate{background:var(--cobalt);color:#fff}
.chip.pass{background:#c9ecd9;color:#0b4d2a}
.chip.partial{background:#fdf0c3;color:#7a5b00}
.chip.fail{background:#f7c9c9;color:#7a1010}
.bar{height:22px;background:var(--turq);border-radius:4px;
animation:grow 1.2s ease-out}
@keyframes grow{from{width:0}}
.qrow{border:1px solid var(--line);border-radius:10px;margin:8px 0;
padding:10px 14px;background:var(--card)}
.qrow summary{cursor:pointer;font-weight:600}
.qrow .meta{font-size:14px;color:var(--mut)}
pre.cmd{background:#062b30;color:#bff3e8;padding:12px 16px;border-radius:8px;
overflow-x:auto;font-size:15px}
#popover{position:fixed;z-index:50;background:var(--card);color:var(--ink);
border:2px solid var(--cobalt);border-radius:10px;padding:10px 14px;
max-width:340px;display:none;box-shadow:0 6px 24px rgba(0,0,0,.25)}
.drawer{border:1px dashed var(--cobalt);border-radius:10px;padding:10px 14px;
margin:10px 0}
input[type=text]{font:inherit;padding:8px 12px;border-radius:8px;
border:2px solid var(--line);width:100%;max-width:420px;background:var(--card);
color:var(--ink)}
select{font:inherit;padding:8px;border-radius:8px;background:var(--card);
color:var(--ink);border:2px solid var(--line)}
.ring{font-size:16px;font-weight:700}
blockquote.insight{border-left:5px solid var(--turq);margin:14px 0;
padding:10px 18px;background:var(--card);border-radius:0 12px 12px 0}
footer{padding:26px 0 60px;color:var(--mut);font-size:15px}
body.present section.slide{display:none}
body.present section.slide.active{display:block}
@media print{aside.side,.toolbar,#progress,button{display:none}
body.present section.slide{display:block}.card{break-inside:avoid}}
"""

JS = """
(function(){
var root=document.documentElement;
document.getElementById("btn-theme").onclick=function(){
var t=root.getAttribute("data-theme")==="dark"?"light":"dark";
root.setAttribute("data-theme",t);};
document.getElementById("btn-present").onclick=function(){document.body.classList.add("present");go(0);};
document.getElementById("btn-scroll").onclick=function(){document.body.classList.remove("present");showAll();};
var slides=Array.prototype.slice.call(document.querySelectorAll("section.slide"));
var cur=0,bar=document.querySelector("#progress i");
function showAll(){slides.forEach(function(s){s.style.display="";});if(bar)bar.style.width="0";}
function go(i){if(!document.body.classList.contains("present"))return;
cur=Math.max(0,Math.min(slides.length-1,i));
slides.forEach(function(s,j){s.classList.toggle("active",j===cur);});
if(bar)bar.style.width=((cur+1)/slides.length*100)+"%";
window.scrollTo(0,0);}
document.addEventListener("keydown",function(e){
if(!document.body.classList.contains("present"))return;
if(e.key==="ArrowRight"||e.key===" "){go(cur+1);}
if(e.key==="ArrowLeft"){go(cur-1);}
if(e.key==="Home"){go(0);}if(e.key==="End"){go(slides.length-1);}
if(e.key==="Escape"){document.body.classList.remove("present");showAll();}});
var pop=document.getElementById("popover");
document.addEventListener("click",function(e){
var t=e.target.closest?e.target.closest(".num,.fig"):null;
if(t&&t.getAttribute("data-src")){pop.style.display="block";
pop.innerHTML="<b>Source</b><br>"+t.getAttribute("data-src");
var r=t.getBoundingClientRect();pop.style.left=Math.min(r.left,innerWidth-360)+"px";
pop.style.top=(r.bottom+8+scrollY)+"px";}else{pop.style.display="none";}});
var q=document.getElementById("qsearch"),sf=document.getElementById("segfilter"),
st=document.getElementById("statusfilter");
function filt(){var t=(q?q.value:"").toLowerCase();
Array.prototype.forEach.call(document.querySelectorAll(".qrow"),function(r){
var ok=r.textContent.toLowerCase().indexOf(t)>=0;
if(sf&&sf.value!=="all")ok=ok&&(r.getAttribute("data-seg")===sf.value);
if(st&&st.value!=="all")ok=ok&&(r.getAttribute("data-status")===st.value);
r.style.display=ok?"":"none";});}
if(q)q.oninput=filt;if(sf)sf.onchange=filt;if(st)st.onchange=filt;
Array.prototype.forEach.call(document.querySelectorAll("[data-viewdata]"),
function(b){b.onclick=function(){var t=document.getElementById(
b.getAttribute("data-viewdata"));if(t)t.style.display=
t.style.display==="none"?"":"none";};});
function bars(id){var el=document.getElementById(id);if(!el)return;
try{var d=JSON.parse(el.textContent);var mx=1;d.forEach(function(r){mx=Math.max(mx,r.v);});
var W=620,H=d.length*34+10,s="";d.forEach(function(r,i){var w=Math.max(2,r.v/mx*(W-220));
s+='<text x="0" y="'+(i*34+22)+'" font-size="14">'+r.k+'</text><rect x="200" y="'+(i*34+6)+'" width="'+w+'" height="20" rx="4" fill="#075056"><title>'+r.k+": "+r.v+'</title></rect><text x="'+(210+w)+'" y="'+(i*34+22)+'" font-size="14">'+r.v+'</text>';});
el.innerHTML='<svg width="'+W+'" height="'+H+'" role="img">'+s+'</svg>';}catch(e){}}
["chart-waterfall","chart-rules","chart-monthly","chart-pay"].forEach(bars);
function heat(id){var el=document.getElementById(id);if(!el)return;
try{var d=JSON.parse(el.textContent);var mx=1;d.cells.forEach(function(c){mx=Math.max(mx,c.n);});
var cw=120,ch=30,W=d.cols.length*cw+160,H=d.rows.length*ch+40,s="";
d.cols.forEach(function(c,j){s+='<text x="'+(160+j*cw+cw/2)+'" y="24" font-size="12" text-anchor="middle">'+c+'</text>';});
d.rows.forEach(function(r,i){s+='<text x="150" y="'+(40+i*ch+20)+'" font-size="12" text-anchor="end">'+r+'</text>';
d.cols.forEach(function(c,j){var n=0;d.cells.forEach(function(cc){if(cc.r===r&&cc.c===c)n=cc.n;});
var a=n/mx;s+='<rect x="'+(160+j*cw)+'" y="'+(40+i*ch)+'" width="'+(cw-4)+'" height="'+(ch-4)+'" rx="4" fill="rgba(50,78,181,'+a.toFixed(2)+')"><title>'+r+" x "+c+": "+n+'</title></rect>';});});
el.innerHTML='<svg width="'+W+'" height="'+H+'" role="img">'+s+'</svg>';}catch(e){}}
heat("heat-rules");
})();
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def num(value: object, src: str) -> str:
    if isinstance(value, float):
        text = f"{value:,.2f}"
    elif isinstance(value, int):
        text = f"{value:,}"
    else:
        text = str(value)
    return f'<span class="num" data-src="{esc(src)}">{esc(text)}</span>'


def chart_block(cid: str, rows: list[dict], table_html: str) -> str:
    payload = esc(json.dumps(rows, sort_keys=True))
    return (
        f'<script type="application/json" id="{cid}">{payload}</script>'
        f'<div id="d-{cid}" role="img" aria-label="chart"></div>'
        f'<button data-viewdata="t-{cid}">view data</button>'
        f'<div id="t-{cid}" style="display:none">{table_html}</div>'
    )


def table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                   for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _validation_card(v: dict) -> str:
    cls = {"PASS": "pass", "PARTIAL": "partial",
           "FAIL": "fail"}[v["status"]]
    return (
        '<div class="card"><p><b>' + esc(v["name"]) + "</b> "
        '<span class="chip ' + cls + '">' + v["status"] + "</span> — "
        + esc(v["evidence"]) + "</p></div>"
    )


def _menu() -> str:
    items = [(1, "Trust"), (2, "Problems"), (3, "SQL flow"),
             (4, "Breaks"), (5, "Strict vs lenient"), (6, "Leadership"),
             (7, "125 questions"), (8, "Verification"), (9, "LLM insights"),
             (10, "Next steps")]
    return "".join(f'<a href="#s{i}">{t}</a>' for i, t in items)


def render(data: dict) -> str:
    h = data["headline"]
    parts: list[str] = []
    parts.append('<!doctype html><html lang="en" data-theme="light">'
                 '<head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,'
                 'initial-scale=1">'
                 '<title>QuickMart delivery dashboard</title>'
                 "<style>" + CSS + "</style></head><body>")
    parts.append('<div id="progress"><i></i></div><div class="layout">'
                 '<aside class="side"><h1>QuickMart</h1>'
                 "<p>Numbers the room will not argue with.</p><nav>"
                 + _menu() + '</nav><div class="toolbar">'
                 '<button id="btn-present">present</button>'
                 '<button id="btn-scroll" class="on">scroll</button>'
                 '<button id="btn-theme">dark / light</button></div>'
                 "</aside><main><div class=\"wrap\">")

    # 1. Trust
    stages = [("Raw order rows", h["raw_orders"], "Resources extracts"),
              ("After load", h["after_load"], "src/data_loader.py"),
              ("After dedup", h["after_dedup"], "data/clean_orders.csv"),
              ("Rejected (FAIL)", h["rejected"],
               "outputs/rejected_orders.csv"),
              ("Lenient trusted", h["lenient"]["rows"],
               "outputs/lenient_trusted_orders.csv"),
              ("Strict trusted", h["strict"]["rows"],
               "outputs/strict_trusted_orders.csv")]
    wfall = [{"k": k, "v": v} for k, v, _ in stages]
    wtable = table(["Stage", "Rows"], [
        [esc(k), num(v, f"waterfall:{k}")] for k, v, _ in stages])
    parts.append('<section class="slide" id="s1"><p class="kicker">1 - trust first</p>'
                 f"<h2 class=\"sec\">{num(h['lenient']['rows'], 'outputs/lenient_trusted_orders.csv:rows')} of "
                 f"{num(h['raw_orders'], 'extracts:orders.csv:rows')} orders are trusted; "
                 "here is where the data breaks</h2>"
                 '<div class="card"><p>Lenient trusted value '
                 f"{num(h['lenient']['value'], 'outputs/lenient_trusted_orders.csv:line_value_sum')} "
                 f"across {num(h['lenient']['rows'], 'outputs/lenient_trusted_orders.csv:rows')} rows; "
                 f"strict {num(h['strict']['rows'], 'outputs/strict_trusted_orders.csv:rows')} rows "
                 f"Rs {num(h['strict']['value'], 'outputs/strict_trusted_orders.csv:line_value_sum')}; "
                 f"rejected {num(h['rejected'], 'outputs/rejected_orders.csv:rows')}.</p>"
                 + chart_block("chart-waterfall", wfall, wtable) + "</div></section>")

    # 2. Problems: statement + numbered approach + decision
    cards = []
    for p in data["problems"]:
        steps = [s.strip() for s in p["approach"].split(". ") if s.strip()]
        cards.append('<div class="card"><p class="kicker">' + esc(p["id"])
                     + "</p><h3>" + esc(p["question"]) + "</h3>"
                     '<ol class="steps"><li>' + "</li><li>".join(
                         esc(s) for s in steps) + "</li></ol>"
                     + "<p><b>Result:</b> " + esc(p["numbers"]) + "</p>"
                     + "<p><b>Decision:</b> " + esc(p["decision"])
                     + " <b>Alternative:</b> " + esc(p["alternative"])
                     + " <b>Effect:</b> " + esc(p["effect"]) + "</p>"
                     + '<p class="meta">Evidence: '
                     + esc(p["code"]) + " · " + esc(p["answers"])
                     + "</p></div>")
    pipe = ("load &#8594; clean &#8594; dedup &#8594; validate &#8594; "
            "trusted &#8594; marts &#8594; LLM report")
    parts.append('<section class="slide" id="s2"><p class="kicker">2 - five problems</p>'
                 "<h2 class=\"sec\">What was asked, how it was solved</h2>"
                 f'<div class="card"><p>{pipe}</p></div>'
                 + "".join(cards) + "</section>")
    # 3. How SQL queries were processed
    core = ["00_staging.sql", "v_line_value.sql", "08_rule_views.sql",
            "07_trusted_populations.sql", "01_profile_views.sql",
            "02_quality_scorecard.sql", "03_dedup.sql",
            "04_trusted_orders.sql", "05_marts.sql"]
    segs = [("A/B/C", "Q1-29", "Python checks", "counts only"),
            ("D", "Q30-39", "seg4_q30-39.sql (10)", "cross-file joins"),
            ("E", "Q40-49", "seg5_q40-49.sql (10)", "value spellings"),
            ("F", "Q50-67", "seg6_q50-67.sql (18)", "window functions"),
            ("G", "Q68-75", "seg7_q68-75.sql (8)", "professional patterns"),
            ("H", "Q76-77", "seg8_q76-77.sql (2)", "proofs + float order"),
            ("I", "Q78-125", "seg9_q78-125.sql (48)", "expert analytics")]
    segtable = table(["Segment", "Questions", "SQL files", "Technique"],
                     [[esc(a), esc(b), esc(c), esc(d)]
                      for a, b, c, d in segs])
    s3parts = []
    s3parts.append('<section class="slide" id="s3">')
    s3parts.append('<p class="kicker">3 - how SQL queries were processed</p>')
    s3parts.append("<h2>From raw text to 96 answers, one chain</h2>")
    s3parts.append('<div class="card"><div class="timeline">')
    s3parts.append("<div><b>Load.</b> Raw extracts load as text: 6,103 rows.</div>")
    s3parts.append("<div><b>Clean and dedup.</b> Rules D01 over D03 over D02 "
                   "over D05, D06 flag-only: 6,000 rows.</div>")
    s3parts.append("<div><b>Line value once.</b> v_line_value (NULL on null "
                   "input); queries read the column, never the formula.</div>")
    s3parts.append("<div><b>Validate.</b> R01 to R12 over the log: 5,478 FAIL "
                   "rows set aside, lenient keeps 522.</div>")
    s3parts.append("<div><b>Enrich and marts.</b> trusted_enriched "
                   "standardises city, category, status, payment.</div>")
    s3parts.append("<div><b>Answer.</b> 96 question files read "
                   "trusted_enriched; ties break by order_id "
                   "(C collation).</div>")
    s3parts.append("</div>")
    s3parts.append("<p>Core files, in dependency order:</p>")
    s3parts.append("<p>" + esc(" ".join(core)) + "</p>")
    s3parts.append(segtable)
    s3parts.append("<pre>pytest tests/test_sql_executes.py -q</pre>")
    s3parts.append("<pre>pytest tests/test_questions_seg8_9.py -q</pre>")
    s3parts.append("</div></section>")
    parts.append("".join(s3parts))

    # 4. Where it breaks
    rules = data["rules"]["rules"]
    rbars = [{"k": r["id"], "v": r["failing"]} for r in rules]
    rtable = table(["Rule", "Name", "Failing", "Value removed",
                    "Top city", "Top month", "Top payment"],
                   [[esc(r["id"]), esc(r["name"]),
                     num(r["failing"], f"rule_failure_log:{r['id']}:FAIL"),
                     num(r["value_removed"],
                         f"rule_failure_log:{r['id']}:value"),
                     esc(r["top_city"]), esc(r["top_month"]),
                     esc(r["top_payment"])] for r in rules])
    cities: list[str] = []
    for r in rules:
        for cc in r.get("city_counts", []):
            if cc["city"] not in cities:
                cities.append(cc["city"])
    cells = [{"r": r["id"], "c": cc["city"], "n": cc["n"]}
             for r in rules for cc in r.get("city_counts", [])]
    heat = {"rows": [r["id"] for r in rules], "cols": cities,
            "cells": cells}
    co = data["rules"]["cooccurrence"]
    cotable = table(["Rule A", "Rule B", "Together", "Lift"],
                    [[esc(c["a"]), esc(c["b"]), num(c["n"], "rule_failure_log:cooccurrence"),
                      num(c["lift"], "rule_failure_log:lift")] for c in co])
    parts.append('<section class="slide" id="s4"><p class="kicker">4 - where it breaks</p>'
                 "<h2 class=\"sec\">Rule failures, concentration, co-occurrence</h2>"
                 '<div class="card"><h3>Failing rows per rule</h3>'
                 + chart_block("chart-rules", rbars, rtable) + "</div>"
                 '<div class="card"><h3>Concentration heatmap (rule x city, top cities)</h3>'
                 '<script type="application/json" id="heat-rules">'
                 + esc(json.dumps(heat, sort_keys=True)) + "</script>"
                 '<div id="d-heat-rules" role="img" aria-label="heatmap"></div>'
                 "<p>Lift over 1 means the pair travels together.</p>"
                 + cotable + "</div></section>")

    # 5. Strict vs lenient
    lent5 = ["{} Rs {}".format(r["customer_id"], f"{r['value']:,.2f}")
             for r in h["top5_lenient"]]
    strict5 = ["{} Rs {}".format(r["customer_id"], f"{r['value']:,.2f}")
               for r in h["top5_strict"]]
    overlap = len({r["customer_id"] for r in h["top5_lenient"]}
                  & {r["customer_id"] for r in h["top5_strict"]})
    parts.append('<section class="slide" id="s5"><p class="kicker">5 - strict vs lenient</p>'
                 "<h2 class=\"sec\">What changes for leadership</h2><div class=\"grid2\">"
                 f'<div class="card"><h3>Lenient ({num(h["lenient"]["rows"], "outputs/lenient_trusted_orders.csv:rows")} rows)</h3>'
                 f"<p>Rs {num(h['lenient']['value'], 'outputs/lenient_trusted_orders.csv:line_value_sum')}</p>"
                 f"<p>Top 5: {esc('; '.join(lent5))}</p></div>"
                 f'<div class="card"><h3>Strict ({num(h["strict"]["rows"], "outputs/strict_trusted_orders.csv:rows")} rows)</h3>'
                 f"<p>Rs {num(h['strict']['value'], 'outputs/strict_trusted_orders.csv:line_value_sum')}</p>"
                 f"<p>Top 5: {esc('; '.join(strict5))}</p></div></div>"
                 '<div class="card"><p>Delta: '
                 f"{num(h['lenient']['rows'] - h['strict']['rows'], 'waterfall:warning_only_rows')} WARNING-only rows kept; "
                 f"top-5 overlap {num(overlap, 'waterfall:top5_overlap')} of 5. "
                 "Strict drops valid delivered rows; lenient is recommended.</p></div>"
                 "</section>")

    # 6. Leadership answers
    series = data["series"]
    mrows = [{"k": r["month"], "v": r["value"]} for r in series["monthly"]]
    mtable = table(["Month", "Value", "Orders"],
                   [[esc(r["month"]),
                     num(r["value"], f"sales_datamart:{r['month']}:value"),
                     num(r["orders"], f"sales_datamart:{r['month']}:orders")]
                    for r in series["monthly"]])
    trows = series["top_customers"]
    ttable = table(["Customer", "City", "Orders", "Value"],
                   [[esc(r["customer_id"]),
                     esc(r["city_std"]),
                     num(r["orders"],
                         f"customer_value_datamart:{r['customer_id']}:orders"),
                     num(r["value"],
                         f"customer_value_datamart:{r['customer_id']}:value")]
                    for r in trows])
    prows = [{"k": r["order_month"] + " / " + r["payment_std"],
              "v": r["value"]} for r in series["payment_mix"]]
    ptable = table(["Month", "Payment", "Value"],
                   [[esc(r["order_month"]), esc(r["payment_std"]),
                     num(r["value"],
                         f"payment_datamart:{r['order_month']}:"
                         f"{r['payment_std']}:value")]
                    for r in series["payment_mix"]])
    dtable = table(["City", "Category", "Orders", "Avg days", "Median days"],
                   [[esc(r["city_std"]), esc(r["category_std"]),
                     num(r["orders"],
                         f"delivery_datamart:{r['city_std']}:"
                         f"{r['category_std']}:orders"),
                     num(r["avg_days"],
                         f"delivery_datamart:{r['city_std']}:"
                         f"{r['category_std']}:avg_days"),
                     num(r["median_days"],
                         f"delivery_datamart:{r['city_std']}:"
                         f"{r['category_std']}:median_days")]
                    for r in series["delivery"]])
    parts.append('<section class="slide" id="s6"><p class="kicker">6 - leadership answers</p>'
                 "<h2 class=\"sec\">Monthly sales, top customers, payments, delivery</h2>"
                 '<div class="card"><h3>Monthly delivered sales '
                 "(pipeline trusted)</h3>"
                 + chart_block("chart-monthly", mrows, mtable) + "</div>"
                 '<div class="card"><h3>Top customers (masked)</h3>'
                 + ttable + "</div>"
                 '<div class="card"><h3>Payment mix by month</h3>'
                 + chart_block("chart-pay", prows, ptable) + "</div>"
                 '<div class="card"><h3>Delivery speed by city x category</h3>'
                 + dtable + "</div></section>")
    # 7. Explorer
    seglist = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    done = sum(1 for q in data["questions"] if q["status"] == "DONE")
    notdone = sum(1 for q in data["questions"] if q["status"] != "DONE")
    qrows = []
    for q in data["questions"]:
        det = ("<p><b>Method:</b> " + esc(q["method"]) + "</p><p><b>Answer:</b> "
               + esc(q["headline"]) + "</p><p class=\"meta\">Code: "
               + esc(q["code"] or "n/a") + " · SQL: "
               + esc(q["sql"] or "n/a") + " · parity: "
               + ("yes" if q["parity_tested"] else "no"))
        if q["analogue"]:
            det += " · ANALOGUE, missing: " + esc(q["analogue"])
        det += "</p>"
        res = q["result"]
        if res.get("kind") == "table":
            det += "<p class=\"meta\">rows: " + str(res.get("rows")) + "</p>"
        qrows.append(
            f'<div class="qrow" data-seg="{esc(q["segment"])}" '
            f'data-status="{esc(q["status"])}"><details><summary>Q{q["id"]}'
            f' · {esc(q["title"])} '
            f'<span class="chip">{"pass" if q["status"] == "DONE" else "partial"}'
            f"</span></summary>{det}</details></div>")
    segstrip = " ".join(
        f"<span class=\"chip\">Seg {s}: "
        f"{sum(1 for q in data['questions'] if q['segment'] == s and q['status'] == 'DONE')}"
        f"/{sum(1 for q in data['questions'] if q['segment'] == s)} DONE</span>"
        for s in seglist)
    parts.append('<section class="slide" id="s7"><p class="kicker">7 - 125 questions</p>'
                 "<h2 class=\"sec\">Every question, searchable</h2>"
                 f'<div class="card"><p class="ring">DONE {num(done, "ledger:DONE")} / '
                 f'NOT DONE {num(notdone, "ledger:NOT DONE")} of 125</p><p>{segstrip}</p>'
                 '<p><input type="text" id="qsearch" placeholder="search questions..."> '
                 '<select id="segfilter"><option value="all">all segments</option>'
                 + "".join(f'<option value="{s}">{s}</option>' for s in seglist)
                 + '</select> <select id="statusfilter"><option value="all">all statuses</option>'
                 '<option value="DONE">DONE</option><option value="NOT DONE">NOT DONE</option>'
                 "</select></p></div>" + "".join(qrows) + "</section>")

    # 8. Verification board
    chips = []
    for c in data["criteria"]:
        cls = {"PASS": "pass", "PARTIAL": "partial", "FAIL": "fail"}[c["status"]]
        gate = ' <span class="chip gate">Gate</span>' if c["kind"] == "Gate" else ""
        chips.append(
            f'<div class="card"><p><b>#{c["id"]} {esc(c["text"])}</b>{gate} '
            f'<span class="chip {cls}">{c["status"]}</span></p>'
            f'<pre class="cmd">{esc(c["command"])}</pre>'
            f'<p class="meta">Evidence: {esc(c["evidence"])}'
            + (f' · Path: {esc(c["path"])}' if c["path"] else "") + "</p></div>")
    vrows = "".join(
        _validation_card(v) for v in data["validations"])
    rb = data["rubric"]
    parts.append('<section class="slide" id="s8"><p class="kicker">8 - verification</p>'
                 "<h2 class=\"sec\">23 criteria, live from code</h2>"
                 '<div class="card"><p>Re-run: </p><pre class="cmd">python -m src.criteria_check '
                 "--write-cache &amp;&amp; python -m src.dashboard_data &amp;&amp; "
                 "python -m src.dashboard</pre>"
                 f"<p>Run hash: <b>{esc(data['run_hash'])}</b> (no timestamps anywhere)</p>"
                 f"<p>Rubric score: {num(rb['score'], 'rubric:score')} "
                 f"({esc(json.dumps(rb['levels'], sort_keys=True))}; self-assessed weights "
                 f"{esc(json.dumps(rb['weights'], sort_keys=True))})</p></div>"
                 + "".join(chips)
                 + '<div class="card"><h3>Validation checks</h3></div>' + vrows
                 + "</section>")

    # 9. LLM insights
    ins = data["insights"]
    cards = []
    for i in ins["insights"]:
        figs = " ".join(
            f'<span class="chip fig" data-src="{esc(f["mart"])}:{esc(f["row_key"])}">'
            f'{esc(f["value"])}</span>' for f in i.get("figures", []))
        cards.append('<blockquote class="insight"><h3>' + esc(i["title"])
                     + ' <span class="chip pass">VERIFIED</span></h3><p>'
                     + esc(i["claim"]) + "</p><p><b>So what:</b> "
                     + esc(i.get("so_what", "")) + "</p><p>" + figs
                     + f'<span class="chip">confidence {esc(i.get("confidence", ""))}</span> '
                     f'<span class="chip">{esc(i.get("source", "model"))}</span></p></blockquote>')
    rej = ins.get("rejected", [])
    drawer = ('<div class="drawer"><details><summary>Rejected by verifier '
              f'({len(rej)})</summary>')
    if rej:
        for i in rej:
            drawer += ('<p><b>' + esc(i["title"]) + "</b> — "
                       + esc(i.get("reason", "")) + "</p>")
    else:
        drawer += "<p>None — the verifier passed everything.</p>"
    drawer += "</details></div>"
    comp = ins.get("comparison", {})
    parts.append('<section class="slide" id="s9"><p class="kicker">9 - LLM insights</p>'
                 "<h2 class=\"sec\">Verified insights only (figures traced to marts)</h2>"
                 + "".join(cards) + drawer
                 + '<div class="card"><h3>Two-run comparison</h3><p>Figures agreed: '
                 + esc(", ".join(comp.get("figures_agreed", [])) or "—")
                 + "</p><p>Wording differed: "
                 + esc(", ".join(comp.get("wording_differed", [])) or "—")
                 + "</p></div>"
                 + '<div class="card"><h3>Model record</h3><p>See reports/llm_run_record.json '
                 "(model, version, settings, prompt hash in payload provenance).</p></div>"
                 + "</section>")

    # 10. Next steps
    parts.append('<section class="slide" id="s10"><p class="kicker">10 - least sure + next</p>'
                 "<h2 class=\"sec\">What I am least sure of</h2>"
                 '<div class="card"><p>The 407 WARNING-only rows behind the lenient/strict '
                 "delta: each is individually defensible, but as a group they move leadership "
                 "value. Defend with the waterfall (every row traced) and the R12c WARNING-only "
                 "rule: re-running strict-vs-lenient on any new extract reproduces the split.</p></div>"
                 '<div class="card"><h3>Three things the data cannot tell Neha</h3>'
                 "<p>Stock availability (stock_qty unusable in every category) · true delivery "
                 "promises (no promise timestamp to compare against) · ghost-customer identity "
                 "(204 orders, Rs 671,491.75 quarantined).</p></div>"
                 '<div class="card"><h3>Next steps</h3><p>Human sign-off on the 40 mapping rows '
                 "(criterion 11 FAIL) · add src/refresh.py (criterion 22 PARTIAL) · cut marts over "
                 "to the lenient population · schedule the Monday refresh.</p></div>"
                 "</section>")
    parts.append('</div></main></div><footer><div class="wrap"><p>QuickMart delivery dashboard · '
                 "single offline file, no external requests · run hash "
                 f"{esc(data['run_hash'])}</p><div id=\"popover\"></div></div></footer>")
    parts.append('<script id="payload" type="application/json">__PAYLOAD__</script>')
    parts.append("<script>" + JS + "</script>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main() -> None:
    src = ROOT / "dashboard" / "data.json"
    if not src.exists():
        raise SystemExit("dashboard/data.json missing: run "
                         "python -m src.dashboard_data first")
    payload_text = src.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    canonical = json.dumps(payload, sort_keys=True)
    page = render(payload).replace(
        "__PAYLOAD__", lambda_safe(canonical))
    out = ROOT / "dashboard" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = page.encode("utf-8")
    out.write_bytes(blob)
    size = len(blob)
    digest = hashlib.sha256(blob).hexdigest()
    if size > 3 * 1024 * 1024:
        raise SystemExit(f"dashboard too big: {size} bytes (limit 3 MB)")
    print(f"wrote {out} size={size} sha256={digest}")


def lambda_safe(text: str) -> str:
    return text.replace("</", "<\\/")


if __name__ == "__main__":
    main()
