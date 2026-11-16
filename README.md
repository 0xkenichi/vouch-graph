# Vouch Graph

**Find contributors by who they've actually shipped with, not by how well they describe themselves.**

Built on HydraDB's open-source SelfGraph for the HydraDB Hackathon. It fits both tracks: a context layer for agents, and a graph that sharpens every run.

## The problem

Communities hire contributors on trust, but that trust lives in people's heads. When a DAO needs someone to host a Yoruba onboarding call, it usually goes to whoever is loudest, or a friend of the lead.

A vector search over profiles makes this worse. It finds the person whose bio best matches the words. Here that's Tunde, "Yoruba native speaker and world-class community host", who didn't show up the last time he was asked.

## What Vouch Graph does

It's built on **HydraDB's open-source [SelfGraph](https://github.com/hydra-db/selfgraph)**, a versioned knowledge graph SDK. It runs locally on SelfGraph's embedded store, so you need no server, no LLM and no paid key.

```
people  ──CLAIMS──▶ skill          (from their own bio: what they say)
people  ──SHIPPED──▶ work ──NEEDED──▶ skill   (what they did, with outcome: delivered / late / no-show)
people  ──WORKED_WITH──▶ people     (who shipped together, with event_time)
bios inserted as text passages      (what a profile search reads)
        │
question ── SelfGraph retrieve(): BM25 seeds from the question, then a BFS walk over current relations
        │
code walks the returned subgraph:
  skill fit of each person's shipped work × outcome (delivered +3, late +1, no-show −4)
  + trust path from you: 1 hop (shipped with you) or 2 hops (shipped with someone who shipped with you)
        │
answer = a ranked list, each with its path:  You → Ngozi ("onboarding calls") → Femi ("Yoruba roadmap translation")
        │
a hire happens → its outcome is inserted as a new versioned fact → the next run ranks differently
retrieve(as_of=...) replays what the graph would have said before
```

**In the sample run** (`out/report.html`):
- **Profile search** (cosine over bios, i.e. a vector store) picks **Tunde**: "Yoruba native speaker and world-class community host…". In the graph, his only record is a **no-show**.
- **Vouch Graph** picks Ngozi and Bisi, each with a trust path from you.
- After Bisi delivers a Yoruba onboarding call and it's written back, Bisi moves to the top.
- `as_of` 31 Oct shows the earlier answer, because nothing is deleted.

**Why it earns its place over a vector store:** the answer *is* the path. It's made of people who delivered work alongside people you already trust, and you can see how that changes over time. Text similarity can't produce it.

## Run it

```bash
python3.12 -m venv .venv && .venv/bin/pip install "selfgraph[kuzu] @ git+https://github.com/hydra-db/selfgraph"
.venv/bin/python vouch.py demo     # build the graph → ask → write back an outcome → ask again → ask as_of 31 Oct
.venv/bin/python report.py         # out/report.html
```

To use your own community, edit `data.json`. Swap `KuzuStore` for `HydraDBStore` to run on a HydraDB server.

## Go-to-market

- **Who it's for:** DAO ops leads, grant programs and ambassador programs that hire contributors every month. Today they hire on vibes.
- **How it's seeded:** from data they already have: payout lists, GitHub co-commits, event rosters and Discord roles.
- **How it's sold:** per community per month, as contributor search with receipts. The trust path is what a lead can defend when someone asks "why them?".

## Author

Kenichi · [0xkenichi.github.io](https://0xkenichi.github.io) · X [@0xKenichi](https://x.com/0xKenichi)
