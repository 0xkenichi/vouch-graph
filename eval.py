"""Track 1 evaluation: does Vouch Graph get sharper the more it's used?

A synthetic community of 40 people. Each person has a hidden true delivery rate per skill; their bios
claim skills (some honestly, some inflated). Every round, 12 tasks arrive ("who can do <skill>?").
Each method picks one person; the hire succeeds or fails according to the hidden rate (seeded, so runs
are reproducible). Vouch Graph writes every outcome back into the graph as a versioned SHIPPED fact and
WORKED_WITH edges; the next round's walk uses them. The profile-search baseline reads bios only.

Metric: hire success rate per round (share of tasks the chosen person actually delivered).
Also reported: best-possible rate (an oracle that knows the hidden rates).
"""
import asyncio, json, logging, os, random, sys
from pathlib import Path

from selfgraph import HydraDBStore, KuzuStore, SelfGraph

logging.getLogger("selfgraph").setLevel(logging.ERROR)
HERE = Path(__file__).parent
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
SKILLS = ["yoruba hosting", "translation", "dune dashboards", "discord bots", "technical writing", "event logistics"]
ROUNDS, TASKS, N = int(os.environ.get("ROUNDS", 10)), 12, 40
rng = random.Random(int(os.environ.get('SEED', 7)))

NAMES = ["Ada", "Bisi", "Chidi", "Dayo", "Ebuka", "Femi", "Gbenga", "Halima", "Ife", "Jide", "Kemi", "Lola", "Musa", "Nkem", "Obi", "Pelumi",
         "Qudus", "Rotimi", "Sade", "Tobi", "Uche", "Victor", "Wale", "Xavier", "Yemi", "Zainab", "Amara", "Bola", "Chioma", "Damola",
         "Efe", "Funmi", "Gozie", "Hauwa", "Ikenna", "Jumoke", "Kunle", "Lade", "Mide", "Nneka"]

def make_world():
    people = []
    for i, name in enumerate(NAMES[:N]):
        real = rng.sample(SKILLS, rng.choice([1, 2]))
        rate = {s: (rng.uniform(0.75, 0.97) if s in real else rng.uniform(0.05, 0.3)) for s in SKILLS}
        loud = rng.random() < 0.35  # loud bios claim extra skills they don't have, in big words
        claimed = real + (rng.sample([s for s in SKILLS if s not in real], 2) if loud else [])
        if loud:
            bio = f"World-class {', '.join(claimed)} expert. 10x results, 100+ projects, trusted by top DAOs. DM for collabs."
        elif rng.random() < 0.5:   # many good contributors write thin or generic bios
            bio = f"Does {real[0]}" + (f" and some {real[1]}" if len(real) > 1 else "") + "."
        else:
            bio = rng.choice(["Contributor. Happy to help.", "Builder in Lagos.", "Here to ship.", "Community member since 2024."])
        people.append({"id": f"person:{name.lower()}", "name": name, "rate": rate, "claimed": claimed, "bio": bio, "loud": loud})
    return people

def tok(s): return set(w for w in s.lower().replace(",", " ").replace(".", " ").split() if len(w) > 2)

def bio_pick(people, skill):
    q = tok(skill)
    return max(people, key=lambda p: (len(q & tok(p["bio"])), p["name"]))

async def graph_pick(graph, people, skill, by_id):
    res = await graph.retrieve(f"who has delivered {skill} work", depth=2, k=40, max_nodes=400)
    rels = [r if isinstance(r, dict) else r.model_dump() for r in (res.subgraph["relations"] if isinstance(res.subgraph, dict) else res.subgraph.relations)]
    score = {}
    for r in rels:
        props = r.get("properties") or {}
        if r["type"] == "SHIPPED" and props.get("skill") == skill:
            score.setdefault(r["from_entity"], [0, 0])
            score[r["from_entity"]][0] += 1 if props.get("outcome") == "delivered" else 0
            score[r["from_entity"]][1] += 1
    claims = {r["from_entity"] for r in rels if r["type"] == "CLAIMS" and r["to_entity"] == f"skill:{skill.replace(' ', '-')}"}
    def value(p):
        d, n = score.get(p["id"], (0, 0))
        prior = 0.6 if p["id"] in claims else 0.1          # a claim is a weak prior, evidence overrides it
        return ((d + prior * 2) / (n + 2), -n)              # smoothed delivery rate; prefer less-tried on ties (explore)
    return max(people, key=value)

async def run(store_factory):
    people = make_world(); by_id = {p["id"]: p for p in people}
    async with SelfGraph(store=store_factory(), namespace=f"vouch-eval-s{os.environ.get('SEED', 7)}-{os.getpid()}") as graph:
        ents = [{"id": p["id"], "type": "Person", "name": p["name"], "properties": {"bio": p["bio"]}} for p in people]
        ents += [{"id": f"skill:{s.replace(' ', '-')}", "type": "Skill", "name": s} for s in SKILLS]
        rels = [{"from_entity": p["id"], "type": "CLAIMS", "to_entity": f"skill:{s.replace(' ', '-')}"} for p in people for s in p["claimed"]]
        await graph.insert.facts({"entities": ents, "relations": rels}, event_time="2026-09-01")
        curve = []
        for rnd in range(1, ROUNDS + 1):
            tasks = [rng.choice(SKILLS) for _ in range(TASKS)]
            ok = {"graph": 0, "bio": 0, "oracle": 0}
            facts = {"entities": [], "relations": []}
            for t, skill in enumerate(tasks):
                roll = rng.random()
                g = await graph_pick(graph, people, skill, by_id)
                b = bio_pick(people, skill)
                o = max(people, key=lambda p: p["rate"][skill])
                ok["graph"] += roll < g["rate"][skill]; ok["bio"] += roll < b["rate"][skill]; ok["oracle"] += roll < o["rate"][skill]
                outcome = "delivered" if roll < g["rate"][skill] else "no-show"
                wid = f"work:r{rnd}-t{t}"
                facts["entities"].append({"id": wid, "type": "Work", "name": f"{skill} task, round {rnd} #{t}", "properties": {"skill": skill, "outcome": outcome}})
                facts["relations"].append({"from_entity": g["id"], "type": "SHIPPED", "to_entity": wid, "properties": {"skill": skill, "outcome": outcome}})
                facts["relations"].append({"from_entity": wid, "type": "NEEDED", "to_entity": f"skill:{skill.replace(' ', '-')}"})
            await graph.insert.facts(facts, event_time=f"2026-11-{rnd:02d}")   # write back: the graph learns
            row = {"round": rnd, **{k: round(v / TASKS, 3) for k, v in ok.items()}}
            curve.append(row); print(row, flush=True)
    return curve

def main():
    uri = os.environ.get("HYDRADB_URI")
    path = str(HERE / f"eval{os.environ.get('SEED', 7)}.kuzu")
    if not uri and os.path.exists(path):
        import shutil; shutil.rmtree(path, ignore_errors=True)
    factory = (lambda: HydraDBStore(uri, auth=("neo4j", os.environ.get("HYDRADB_TOKEN", "")), database="default")) if uri else (lambda: KuzuStore(path))
    curve = asyncio.run(run(factory))
    first = sum(r["graph"] for r in curve[:2]) / 2; last = sum(r["graph"] for r in curve[-2:]) / 2
    base = sum(r["bio"] for r in curve) / len(curve)
    summary = {"store": "HydraDB" if uri else "Kuzu (embedded)", "rounds": ROUNDS, "tasks_per_round": TASKS, "people": N,
               "baseline_profile_search_mean": round(base, 3), "vouch_first_two_rounds": round(first, 3), "vouch_last_two_rounds": round(last, 3),
               "oracle_mean": round(sum(r["oracle"] for r in curve) / len(curve), 3), "curve": curve}
    (OUT / f"eval_seed{os.environ.get('SEED', 7)}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "curve"}, indent=2))

main()
