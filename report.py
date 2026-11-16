"""Builds out/report.html from the demo runs: profile search vs Vouch Graph, before and after a written-back outcome."""
import html, json
from pathlib import Path

OUT = Path(__file__).parent / "out"
runs = {n: json.loads((OUT / f"{n}.json").read_text()) for n in ("run1", "run2", "run2_as_of_oct")}
e = html.escape

def ranked(r, n=3):
    rows = []
    for i, c in enumerate(r["ranked"][:n], 1):
        shipped = "; ".join(f"{s['work']} ({s['outcome']})" for s in c["shipped"])
        rows.append(f"""<li><div class="top"><b>{i}. {e(c['name'])}</b><span class="score">{c['score']}</span></div>
<div class="path">{e(c['path'] or 'no trust path')}</div><div class="ev">{e(shipped)}</div></li>""")
    return "<ol class='rank'>" + "".join(rows) + "</ol>"

r1, r2, ro = runs["run1"], runs["run2"], runs["run2_as_of_oct"]
bio = r1["bio_search"][0]
tunde = next((c for c in r1["ranked"] if c["name"] == bio["name"]), None)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vouch Graph demo</title><style>
:root{{--bg:#0e0f12;--card:#17191d;--line:#2a2d33;--fg:#eceae6;--mute:#9a978f;--acc:#7dd3fc;--bad:#fca5a5;--ok:#86efac}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 Inter,system-ui,sans-serif}}
.w{{max-width:1100px;margin:0 auto;padding:36px 20px 60px}}h1{{font-size:34px;margin:0 0 6px;letter-spacing:-.02em}}.sub{{color:var(--mute)}}
.q{{margin:22px 0;padding:14px 18px;border:1px solid var(--line);border-radius:12px;background:var(--card);font-size:18px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}h2{{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:0 0 12px}}
.pick{{font-size:24px;font-weight:700}}.bad{{color:var(--bad)}}.ok{{color:var(--ok)}}.mono{{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--mute)}}
.rank{{list-style:none;padding:0;margin:0}}.rank li{{border-top:1px solid var(--line);padding:10px 0}}.rank li:first-child{{border-top:0}}
.top{{display:flex;justify-content:space-between}}.score{{font-family:ui-monospace,Menlo,monospace;color:var(--acc)}}.path{{color:var(--acc);font-size:14px}}.ev{{color:var(--mute);font-size:13px}}
.step{{margin-top:26px}}</style></head><body><div class="w">
<h1>Vouch Graph</h1><div class="sub">Find contributors by who they've actually shipped with. Built on HydraDB's open-source SelfGraph, running locally. Sample data: a made-up Lagos builders community.</div>
<div class="q">“{e(r1['question'])}”</div>
<div class="grid">
<div class="card"><h2>Profile search (a vector store over bios)</h2>
<div class="pick bad">{e(bio['name'])}</div><p>“{e(bio['bio'])}”</p>
<p class="mono">In the graph: {e('; '.join(f"{s['work']} ({s['outcome']})" for s in tunde['shipped'])) if tunde else 'no shipped work'}</p></div>
<div class="card"><h2>Vouch Graph: walking who shipped with whom</h2>{ranked(r1)}
<p class="mono">{r1['graph']['relations_walked']} relations walked by SelfGraph retrieve; trust paths computed from you</p></div>
</div>
<div class="step"><h2>Then a hire happens and its outcome is written back</h2>
<div class="grid"><div class="card"><h2>Today, after the write-back</h2>{ranked(r2)}</div>
<div class="card"><h2>Same question, <code>as_of</code> 31 Oct (versioned facts)</h2>{ranked(ro)}</div></div></div>
<p class="sub" style="margin-top:26px">The answer is a path through people who delivered work with people you already trust. Text similarity between a bio and a question can't produce that.</p>
</div></body></html>"""
(OUT / "report.html").write_text(page)
print("wrote out/report.html")
