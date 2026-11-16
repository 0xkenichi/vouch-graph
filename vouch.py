"""Vouch Graph: find contributors by who they've actually shipped with, not how well they describe themselves.

Built on HydraDB's open-source SelfGraph (versioned knowledge graph), running locally on its embedded store.
- People, skills and work are entities; SHIPPED / WORKED_WITH / CLAIMS relations carry outcomes and event times.
- Bios are inserted as text passages: that's what a profile search (vector store) sees.
- The agent walks the graph from the question's seeds, and code computes trust paths from you.
- Every hire outcome is written back as a new versioned fact, so the next run ranks differently,
  and `as_of` shows what the graph would have said before.
"""
import asyncio, json, logging, math, os, re, sys
logging.getLogger("selfgraph").setLevel(logging.ERROR)
from collections import Counter
from pathlib import Path

from selfgraph import KuzuStore, SelfGraph

HERE = Path(__file__).parent
DATA = json.loads((HERE / "data.json").read_text())
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
STORE = os.environ.get("VOUCH_STORE", str(HERE / "vouch.kuzu"))
PEOPLE = {p["id"]: p for p in DATA["people"]}
YOU = "p_" + DATA["you"]
OUTCOME = {"delivered": 3, "delivered late": 1, "no-show": -4}

def pid(p): return f"person:{PEOPLE[p]['name'].lower()}"
def wid(w): return f"work:{w['id']}"

SKILLS = {"yoruba": ["yoruba"], "onboarding": ["onboarding", "newcomer"], "hosting": ["host", "hosted", "space", "call", "meetup"],
          "translation": ["translat"], "writing": ["article", "wrote", "explainer"], "dev": ["bot", "built"], "data": ["dashboard", "queries"]}
def skills_in(text):
    t = text.lower()
    return sorted({s for s, keys in SKILLS.items() if any(k in t for k in keys)})

def work_facts(w):
    text = f"{w['title']}. {w['roles']}."
    ents = [{"id": wid(w), "type": "Work", "name": w["title"], "properties": {"outcome": w["outcome"], "when": w["when"], "proof": w.get("proof", "")}}]
    rels = []
    for s in skills_in(text):
        ents.append({"id": f"skill:{s}", "type": "Skill", "name": s})
        rels.append({"from_entity": wid(w), "type": "NEEDED", "to_entity": f"skill:{s}"})
    for p in w["people"]:
        rels.append({"from_entity": pid(p), "type": "SHIPPED", "to_entity": wid(w), "properties": {"outcome": w["outcome"]}, "event_time": w["when"]})
        for q in w["people"]:
            if q != p:
                rels.append({"from_entity": pid(p), "type": "WORKED_WITH", "to_entity": pid(q), "properties": {"on": w["title"], "outcome": w["outcome"]}, "event_time": w["when"]})
    return {"entities": ents, "relations": rels}

async def setup(graph):
    ents = [{"id": pid(p), "type": "Person", "name": v["name"], "properties": {"bio": v["bio"]}} for p, v in PEOPLE.items()]
    rels = []
    for p, v in PEOPLE.items():
        for s in skills_in(v["bio"]):
            ents.append({"id": f"skill:{s}", "type": "Skill", "name": s})
            rels.append({"from_entity": pid(p), "type": "CLAIMS", "to_entity": f"skill:{s}", "event_time": "2026-09-01"})
    await graph.insert.facts({"entities": ents, "relations": rels}, event_time="2026-09-01")
    for p, v in PEOPLE.items():  # bios as passages: what a profile search reads
        await graph.insert.text(f"{v['name']}: {v['bio']}", source_id=f"bio:{p}", event_time="2026-09-01")
    for w in DATA["work"]:
        await graph.insert.facts(work_facts(w), source_id=f"work:{w['id']}", event_time=w["when"])

def bio_search(question):
    """What a vector store over profiles returns: cosine similarity of words, bio vs question."""
    tok = lambda s: Counter(re.findall(r"[a-z]+", s.lower()))
    q = tok(question)
    def cos(a, b):
        dot = sum(a[k] * b.get(k, 0) for k in a); na = math.sqrt(sum(v * v for v in a.values())); nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0
    return sorted(((cos(q, tok(v["bio"])), v["name"], v["bio"]) for v in PEOPLE.values()), reverse=True)[:3]

async def ask(graph, question, label, as_of=None):
    res = await graph.retrieve(question, depth=3, k=20, max_nodes=200, as_of=as_of)
    rels = res.subgraph["relations"] if isinstance(res.subgraph, dict) else res.subgraph.relations
    R = [r if isinstance(r, dict) else r.model_dump() for r in rels]
    names = {}
    ents = res.subgraph["entities"] if isinstance(res.subgraph, dict) else res.subgraph.entities
    for e in ents:
        e = e if isinstance(e, dict) else e.model_dump()
        names[e["id"]] = e.get("name")
    want = set(skills_in(question))
    you = pid(YOU)
    # what each person shipped, and which skills that work needed (from the walked subgraph)
    needed = {}
    for r in R:
        if r["type"] == "NEEDED": needed.setdefault(r["from_entity"], set()).add(r["to_entity"].split(":", 1)[1])
    shipped = {}
    for r in R:
        if r["type"] == "SHIPPED":
            shipped.setdefault(r["from_entity"], []).append((r["to_entity"], (r.get("properties") or {}).get("outcome")))
    worked = {}
    for r in R:
        if r["type"] == "WORKED_WITH" and OUTCOME.get((r.get("properties") or {}).get("outcome"), 0) > 0:
            worked.setdefault(r["from_entity"], {})[r["to_entity"]] = (r.get("properties") or {}).get("on")
    hop1 = worked.get(you, {})
    cands = []
    for person, items in shipped.items():
        if person == you: continue
        score, evidence = 0, []
        for w, outcome in items:
            fit = len(want & needed.get(w, set()))
            score += OUTCOME.get(outcome, 0) * (2 * fit if fit else 0.5)
            evidence.append({"work": names.get(w, w), "outcome": outcome, "skills": sorted(needed.get(w, set()))})
        path = None
        if person in hop1: path = f"You → {names.get(person)} (shipped \"{hop1[person]}\" together)"
        else:
            for mid, on in hop1.items():
                if person in worked.get(mid, {}):
                    path = f"You → {names.get(mid)} (\"{on}\") → {names.get(person)} (\"{worked[mid][person]}\")"; break
        if path: score += 3
        score = round(score, 1)
        cands.append({"name": names.get(person, person), "score": score, "path": path, "shipped": evidence})
    cands.sort(key=lambda c: -c["score"])
    out = {"label": label, "question": question, "as_of": as_of,
           "bio_search": [{"name": n, "bio": b, "similarity": round(s, 3)} for s, n, b in bio_search(question)],
           "graph": {"seeds": [s if isinstance(s, dict) else s.model_dump() for s in res.seeds][:5], "relations_walked": len(R), "context": res.context[:1500]},
           "ranked": cands}
    (OUT / f"{label}.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[{label}]{' as of ' + as_of if as_of else ''}  {len(R)} relations walked")
    print(f"  profile search says: {out['bio_search'][0]['name']}  ({out['bio_search'][0]['bio'][:70]})")
    pick = out['bio_search'][0]['name']
    hit = next((c for c in cands if c['name'] == pick), None)
    print(f"  in the graph, {pick}: " + (", ".join(f"{e['work']} ({e['outcome']})" for e in hit['shipped']) + f", score {hit['score']}" if hit else "no shipped work found"))
    for i, c in enumerate(cands[:4], 1):
        print(f"  {i}. {c['name']} ({c['score']})  {c['path'] or 'no trust path'}")
    return out

async def outcome(graph):
    w = DATA["new_outcome"]
    print(f"\nwriting back an outcome: {w['title']} → {w['outcome']}")
    await graph.insert.facts(work_facts(w), source_id=f"work:{w['id']}", event_time=w["when"])

async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    async with SelfGraph(store=KuzuStore(STORE)) as graph:
        q = DATA["questions"][0]
        if cmd in ("setup", "demo"): await setup(graph)
        if cmd in ("ask", "demo"): await ask(graph, q, "run1")
        if cmd in ("outcome", "demo"): await outcome(graph)
        if cmd == "demo":
            await ask(graph, q, "run2")
            await ask(graph, q, "run2_as_of_oct", as_of="2026-10-31")

asyncio.run(main())
