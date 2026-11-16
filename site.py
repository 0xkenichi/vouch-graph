"""Builds docs/index.html: the hosted demo page (learning curve + the worked example), from out/*.json."""
import html, json
from pathlib import Path
H = Path(__file__).parent; e = html.escape
ev = json.loads((H/"out/eval.json").read_text()); r1 = json.loads((H/"out/run1.json").read_text()); r2 = json.loads((H/"out/run2.json").read_text()); ro = json.loads((H/"out/run2_as_of_oct.json").read_text())
W, Hh, P = 760, 300, 44
xs = lambda i: P + i * (W - 2*P) / (len(ev["curve"]) - 1); ys = lambda v: Hh - P - v * (Hh - 2*P)
def line(k, col, dash=""):
    pts = " ".join(f"{xs(i):.1f},{ys(c[k]):.1f}" for i, c in enumerate(ev["curve"]))
    dots = "".join(f'<circle cx="{xs(i):.1f}" cy="{ys(c[k]):.1f}" r="3.5" fill="{col}"><title>round {c["round"]}: {round(c[k]*100)}%</title></circle>' for i, c in enumerate(ev["curve"]))
    return f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5" {dash}/>' + dots
grid = "".join(f'<line x1="{P}" x2="{W-P}" y1="{ys(v)}" y2="{ys(v)}" stroke="var(--line)"/><text x="{P-8}" y="{ys(v)+4}" text-anchor="end">{int(v*100)}%</text>' for v in (0, .25, .5, .75, 1))
xl = "".join(f'<text x="{xs(i)}" y="{Hh-P+18}" text-anchor="middle">{c["round"]}</text>' for i, c in enumerate(ev["curve"]))
chart = f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Hire success by round">{grid}{xl}<text x="{W/2}" y="{Hh-6}" text-anchor="middle">round</text>{line("oracle","var(--mute)",'stroke-dasharray="4 4"')}{line("bio","var(--bad)")}{line("graph","var(--acc)")}</svg>'
def ranked(r):
    return "".join(f'<li><b>{i}. {e(c["name"])}</b> <span class="s">{c["score"]}</span><div class="p">{e(c["path"] or "no trust path")}</div></li>' for i, c in enumerate(r["ranked"][:3], 1))
bio = r1["bio_search"][0]
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vouch Graph</title><meta name="description" content="Find contributors by who they've actually shipped with. Built on HydraDB SelfGraph.">
<style>:root{{--bg:#0e0f12;--card:#17191d;--line:#2a2d33;--fg:#eceae6;--mute:#8f8c85;--acc:#7dd3fc;--bad:#fca5a5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Inter,system-ui,sans-serif}}a{{color:var(--acc)}}
.w{{max-width:1000px;margin:0 auto;padding:40px 16px 64px}}h1{{font-size:clamp(34px,6vw,54px);margin:0;letter-spacing:-.03em}}.lead{{font-size:20px;color:#cfccc5;max-width:720px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}}h2{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute);margin:0 0 10px}}
svg{{width:100%;height:auto}}svg text{{fill:var(--mute);font:12px ui-monospace,Menlo,monospace}}.legend span{{margin-right:16px;font-size:14px}}.k{{display:inline-block;width:14px;height:3px;vertical-align:middle;margin-right:6px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:14px}}.stat b{{display:block;font:600 28px ui-monospace,Menlo,monospace}}.stat span{{color:var(--mute);font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}ol{{list-style:none;padding:0;margin:0}}li{{padding:8px 0;border-top:1px solid var(--line)}}li:first-child{{border-top:0}}
.s{{float:right;font-family:ui-monospace,Menlo,monospace;color:var(--acc)}}.p{{color:var(--acc);font-size:14px}}.bad{{color:var(--bad)}}.mono{{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--mute)}}</style></head>
<body><div class="w"><h1>Vouch Graph</h1><p class="lead">Find contributors by who they've actually shipped with, not by who has the loudest bio. A versioned knowledge graph of who delivered what, with whom, that gets sharper with every hire.</p>
<p><a href="https://github.com/0xkenichi/vouch-graph">Code</a> · <a href="https://youtu.be/Lbn-1gEQjpU">Demo video</a> · running on the open-source HydraDB engine (v0.4.0, via SelfGraph) · by <a href="https://0xkenichi.github.io">Kenichi</a></p>
<div class="card"><h2>Does it get sharper the more it's used?</h2>
<div class="legend"><span><i class="k" style="background:var(--acc)"></i>Vouch Graph (writes every outcome back)</span><span><i class="k" style="background:var(--bad)"></i>Profile search baseline</span><span><i class="k" style="background:var(--mute)"></i>Oracle (knows the truth)</span></div>
{chart}
<div class="stats"><div class="stat"><b>{round(ev['vouch_round1']*100)}%</b><span>Vouch Graph, round 1 (cold start)</span></div><div class="stat"><b>{round(ev['vouch_last3']*100)}%</b><span>Vouch Graph, rounds 8–10</span></div><div class="stat"><b>{round(ev['baseline_mean']*100)}%</b><span>profile search, all rounds</span></div><div class="stat"><b>{round(ev['oracle_mean']*100)}%</b><span>best possible</span></div></div>
<p class="mono">Metric: hire success rate, the share of tasks where the chosen person actually delivered. {ev['seeds']} simulated communities × {ev['people']} people × {ev['tasks_per_round']} tasks per round. Hidden true delivery rates; 35% of bios inflated. Outcomes come from the hidden rates, never from the method. Graph store: {ev['store']} engine v0.4.0 run locally (Docker), accessed over Bolt with SelfGraph's HydraDBStore. Reproduce: <code>HYDRADB_URI=bolt://127.0.0.1:7687 python eval.py</code>.</p></div>
<div class="card"><h2>A worked example</h2><p>“{e(r1['question'])}”</p>
<div class="grid"><div><h2>Profile search picks</h2><p class="bad"><b>{e(bio['name'])}</b>: “{e(bio['bio'])}”</p><p class="mono">In the graph: one no-show.</p></div><div><h2>Vouch Graph</h2><ol>{ranked(r1)}</ol></div></div>
<div class="grid" style="margin-top:12px"><div><h2>After Bisi's outcome is written back</h2><ol>{ranked(r2)}</ol></div><div><h2>Same question, as_of 31 Oct</h2><ol>{ranked(ro)}</ol></div></div></div>
<div class="card"><h2>Who it's for</h2><p>DAO ops leads, grant programs and ambassador programs that hire contributors every month. Seed it from what they already have (payout lists, GitHub co-commits, event rosters). Sold per community per month: contributor search with receipts. The trust path is what a lead can defend when someone asks “why them?”.</p></div>
</div></body></html>"""
(H/"docs").mkdir(exist_ok=True); (H/"docs/index.html").write_text(page); print("wrote docs/index.html")
