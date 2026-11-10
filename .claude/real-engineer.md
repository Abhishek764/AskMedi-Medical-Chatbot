# Real Engineer Playbook — Matt Pocock Skills × AskMedi v2

How to use [mattpocock/skills](https://github.com/mattpocock/skills) ("Skills For Real Engineers")
on this repo, from research to deployment. Baseline of the current code: [v1-README.md](v1-README.md).

> Status: plugin **`mattpocock-skills` v1.3.1 is already installed** (`claude-plugins-official`).
> Update: auto. Reinstall: `claude plugin install mattpocock-skills@claude-plugins-official`.

---

## 0. Mental model (read first)

Matt's thesis: agents fail in four ways. Each has a fix.

| Failure | Fix | Skills |
|---|---|---|
| Agent built the wrong thing | Get interviewed until there's **shared understanding** | `/grill-with-docs`, `/grill-me` |
| Agent is verbose and vague | **Shared language**: `GLOSSARY.md` + ADRs | `domain-modeling` (via grill-with-docs) |
| Code doesn't work | **Feedback loops**: tests first, a real debug loop | `tdd`, `diagnosing-bugs` |
| Codebase turns into a ball of mud | **Deep modules**, specs, regular architecture review | `/to-spec`, `/improve-codebase-architecture`, `codebase-design` |

Two kinds of skill:

- **User-invoked** (you type `/name`; the agent never starts these itself): `ask-matt`, `setup-matt-pocock-skills`, `grill-with-docs`, `grill-me`, `triage`, `improve-codebase-architecture`, `to-spec`, `to-tickets`, `implement`, `implement-spec`, `wayfinder`, `retro`, `handoff`, `teach`, `to-questionnaire`, `wait-what`.
- **Model-invoked** (the agent reaches for these itself, or you ask): `tdd`, `diagnosing-bugs`, `research`, `prototype`, `domain-modeling`, `codebase-design`, `code-review`, `pr`, `wizard`, `grilling`, `writing-for-agents`.

Not sure which one to use? Type **`/ask-matt <your situation>`**. It routes you.

### Main flow (idea → ship)

```
/setup-matt-pocock-skills   (once per repo)
        │
/grill-with-docs ──► GLOSSARY.md + docs/adr/*      ◄── /research (cited notes)
        │   (questions only code can answer? → /handoff → /prototype → /handoff back)
        │
   multi-session build?
     ├─ no  → /implement (same context)
     └─ yes → /to-spec → GitHub issue (ready-for-agent)
                 └─ /to-tickets → vertical-slice issues with "blocked by" edges
                        ├─ /implement #N   (one per ticket, /clear between)
                        └─ /implement-spec (all tickets, worktrees, integration branch)
                               (each uses tdd → code-review)
        │
     pr (PR body: Summary / Evidence / Merge Danger)
        │
     /retro  (improve the agent's environment, not the code)

Side doors:   /triage (incoming issues)   diagnosing-bugs (broken/slow)
              /wayfinder (too big for one session)   /improve-codebase-architecture (every few days)
```

**Rule:** keep `/grill-with-docs` → `/to-spec` → `/to-tickets` in **one context window**. Don't `/clear` in the middle.

---

## Phase 0 — Set up the repo (once, about 15 min)

1. **`/setup-matt-pocock-skills`**
   - Issue tracker → **GitHub** (`origin` = `Abhishek764/AskMedi-Medical-Chatbot`; `gh` is logged in).
   - Triage labels → accept the defaults (`bug`, `enhancement`, `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). It creates them with `gh label create`.
   - Domain docs → single context (not a monorepo). Root `GLOSSARY.md`, ADRs in `docs/adr/`.
   - Writes: a `## Agent skills` block in `CLAUDE.md` (there is no `CLAUDE.md` yet, so it gets created) and `docs/agents/{issue-tracker,domain,triage-labels}.md`.
2. **Write `CLAUDE.md` well.** Ask the agent to use the `writing-for-agents` skill. Put in: how to run tests (`python -m pytest -q`), the dev server (`python wsgi.py`), the two test seams (see Phase 4), and "never commit `.env`".
3. **Guardrails (optional).** The plugin's `misc/git-guardrails-claude-code` adds a hook that blocks `git push`, `reset --hard`, and similar commands. `misc/setup-pre-commit` is **Husky/JS only**, so don't use it here. For Python, ask for the `pre-commit` framework with `ruff` + `pytest` instead.

Commit the result: `chore: configure agent skills`.

---

## Phase 1 — Research (what's true out there?)

Use **`research`** whenever a decision depends on facts outside this repo. It runs as a background agent, reads **primary sources only** (official docs, source code, specs), and writes **one cited Markdown file** into the repo. Suggested location: `docs/research/`.

Research questions v2 needs answered:

| Prompt | Why |
|---|---|
| "research: LangChain 0.3 → current migration — `create_history_aware_retriever`, `create_retrieval_chain`, deprecated `langchain.document_loaders` / `langchain.embeddings` paths" | `src/helper.py` + `app/chat/rag.py` use deprecated APIs |
| "research: hosted embedding options (OpenAI `text-embedding-3-small`, Pinecone integrated inference) vs in-process MiniLM — dims, cost, latency, re-index needed?" | torch in the web process is causing RAM and cold-start problems on Render 512 MB |
| "research: Pinecone idempotent upsert with stable vector IDs + namespaces; deleting stray vectors" | `store_index.py` duplicates vectors; the index may hold the notebook's "youtube" doc |
| "research: RAG evaluation for medical QA — faithfulness/groundedness metrics, ragas vs custom LLM-judge" | v1 has no quality signal |
| "research: Flask SSE under gunicorn gthread vs FastAPI async streaming on Render" | Framework decision |
| "research: Flask-Limiter with Redis on Render (Key Value)" | `memory://` limits are per worker |

**Too big or foggy?** Use **`/wayfinder`**. v2 might be more than one session can hold (new corpus, eval, framework change). Wayfinder creates a `wayfinder:map` issue (Destination / Decisions so far / Fog of war / Out of scope) plus child tickets typed `research` / `prototype` / `grilling` / `task`. Resolve **one ticket per session**. When the fog clears, it hands off to `/to-spec`.

**Learning a new concept?** **`/teach RAG evaluation`** sets up a lesson workspace with `MISSION.md`, lessons, and learning records. Run it in a **separate folder**, not this repo.

**Need an answer from someone else** (a doctor, a reviewer)? **`/to-questionnaire`** writes `to-questionnaire-<slug>.md` for them to fill in, e.g. "Which guardrail behaviours are clinically required?"

---

## Phase 2 — System design (decide, and write it down)

### 2a. `/grill-with-docs` — the core design session

Start: `/grill-with-docs I want to plan AskMedi v2. Read .claude/v1-README.md first.`

It asks questions in **rounds**, each with a recommended answer (`❓ Q1 … ➡ recommended`). Reply "yes" to accept. Facts come from code and research; **you make the decisions**. Along the way it:

- Builds **`GLOSSARY.md`** with canonical terms. Expected AskMedi terms: *Conversation*, *Turn*, *Question* vs *Standalone Question* (the rewritten follow-up), *Chunk*, *Source* / *Citation*, *Corpus*, *Guardrail*, *Refusal*, *Ingestion*. Glossary only, no implementation details.
- Writes **ADRs** in `docs/adr/NNNN-slug.md`, but only for decisions that are hard to reverse, surprising, **and** a real trade-off. Likely v2 ADRs:
  - `0001-render-is-the-only-deploy-target` (delete the AWS Dockerfile/Action path)
  - `0002-hosted-embeddings-over-in-process-minilm` (forces a re-index: 384 dims → new dims)
  - `0003-keep-flask-sync-sse` *or* `0003-move-to-fastapi`
  - `0004-redis-for-rate-limits`
  - `0005-page-level-citations`

### 2b. `codebase-design` — vocabulary for module boundaries

Terms: **module, interface, depth, seam, adapter, leverage, locality**. Key rules:
- *Depth is a property of the interface.* A small interface hiding lots of behaviour is good.
- *The interface is the test surface.*
- *One adapter = hypothetical seam. Two adapters = real seam.*

Applied to AskMedi:
- `stream_answer(question, history)` is already a **deep module**: the web layer knows nothing about LangChain or Pinecone. Keep that interface stable in v2 and swap the inside.
- A real seam appears when there are **two adapters**, e.g. a Pinecone retriever plus an in-memory fake retriever for evals and tests. Then a `Retriever` interface earns its place. With only one, don't add it.
- Candidate new deep module: an `ingest(corpus_dir) -> IngestReport` module. It would replace `store_index.py` and be idempotent, with stable IDs and page metadata.

### 2c. `/improve-codebase-architecture` — health scan (now, then every few days)

It scans for shallow modules, scattered logic, and untested areas, then opens an **HTML report in your temp dir** (not the repo). Each candidate has Problem / Solution / Before-After and a `Strong` / `Worth exploring` / `Speculative` badge. Pick one, and it grills you on it.
Likely hits here: dead root `templates/` + `static/`; `store_index.py` scripting at module level; `src/` vs `app/` split; prompts as bare strings with no tests.

### 2d. `prototype` — answer a question with code, then throw it away

- **Logic prototype:** one HTML file showing chunk size 500 vs 1000 and k=3 vs 5 against sample questions. You see retrieval results before committing to a re-index.
- **UI prototype:** several radically different chat layouts on one route, switched by `?variant=` (citations panel, source preview, 👍/👎).
- Rules: throwaway, kept on a `prototype/<name>` branch, never merged. Fold the decision into real code afterwards.

### Draft v2 target (input for grilling, not decided)

```
Browser ─► Flask (or FastAPI)  ─┬─ auth / conversations (Postgres + Alembic migrations)
                                ├─ chat: stream_answer()  ◄── deep module
                                │      ├─ Retriever (Pinecone, namespaced, stable IDs)
                                │      ├─ Embedder (hosted API — no torch in web)
                                │      └─ LLM (OpenAI, model from config)
                                ├─ rate limit store: Redis (Render Key Value)
                                └─ telemetry: latency, tokens, feedback 👍/👎
Offline: ingest CLI (idempotent) · eval CLI (golden Q&A set → faithfulness score) · CI gate
```

---

## Phase 3 — Planning (turn decisions into work)

Same context window as the grilling session:

1. **`/to-spec`** writes a GitHub issue with Problem, Solution, a long list of **User Stories**, Implementation Decisions (no file paths), **Testing Decisions**, and Out of Scope. Labelled `ready-for-agent`. It confirms the **test seams** with you first; prefer the existing ones (see Phase 4).
2. **`/to-tickets #<spec>`** splits it into **tracer-bullet vertical slices**. Each slice goes UI → API → DB → RAG end to end, fits one context window, and has explicit `Blocked by` edges. It quizzes you on granularity before publishing. Wide refactors are done expand → contract.

Example slicing for v2 (ordered by dependencies):

| # | Ticket | Blocked by |
|---|---|---|
| 01 | Delete dead v0 files + stale AWS Docker/Action; CI runs pytest on PRs | — |
| 02 | Fail fast if `SECRET_KEY` missing in prod; Alembic baseline migration | 01 |
| 03 | Idempotent ingest CLI: stable IDs, page metadata, honours `PINECONE_INDEX` | 01 |
| 04 | Page-level citations in SSE `done` event + UI | 03 |
| 05 | Hosted embeddings + re-index (per ADR-0002) | 03 |
| 06 | Golden-set eval CLI + CI gate on faithfulness | 03 |
| 07 | Redis rate limits + limit `/register` | 02 |
| 08 | 👍/👎 feedback persisted per message | 02 |

**Don't run `/triage` on tickets created by `/to-tickets`.** They are already `ready-for-agent`.

---

## Phase 4 — Implementation

### Choose a driver
- **`/implement #12`**: one ticket in the current session. It calls `tdd` at the agreed seams, type-checks and runs single test files often, runs the full suite at the end, calls `code-review`, then commits. **`/clear` between tickets.**
- **`/implement-spec #<spec>`**: runs all tickets as a task graph. One fresh sub-agent per ready ticket, each in its own **git worktree and branch**. A merger agent merges into an **integration branch**. Newly unblocked tickets start next. At the end, `code-review` runs on the whole branch. Best for 4+ independent tickets.

### `tdd` in this repo
Rules: tests go through **public interfaces only**, **red before green**, **one slice at a time** (no writing every test first). Expected values come from an independent source, not from the code. Refactoring happens in `code-review`, not inside the loop.

Seams that already work, so reuse them:
1. **HTTP seam:** Flask test client against the full app (`tests/conftest.py` → `client`, `auth_client`).
2. **AI seam:** `monkeypatch.setattr(chat_routes, "stream_answer", fake)` yields `("token", …)` / `("done", {...})`.

New seams to agree on in `/to-spec`:
3. **Ingest seam:** `ingest(dir) -> report`, tested with a tiny 2-page PDF fixture and a fake vector store.
4. **Eval seam:** `evaluate(golden_set, answer_fn) -> scores`. It runs against the real chain only in a separate CI job that has the secrets.

Add `pytest` to a `requirements-dev.txt`. It's missing today.

### `diagnosing-bugs` when something breaks
Its key idea is to **build a fast, deterministic pass/fail loop first**. Then: reproduce and minimise → 3–5 ranked falsifiable hypotheses → instrument one variable at a time, tagging logs `[DEBUG-<id>]` → write a regression test at a seam **before** the fix → fix → remove debug logs, and name the winning hypothesis in the commit.
Likely AskMedi cases: slow first request (embedding cold start), SSE not flushing behind a proxy, a follow-up question retrieving the wrong chunks (check the standalone-question rewrite), Postgres `postgres://` URL problems.
It redacts secrets as `<REDACTED>` first. Don't paste `.env` contents.

---

## Phase 5 — Review and PR

- **`code-review`** (runs automatically inside `/implement`, or call it with "review since main"). Two parallel reviewers, reported side by side:
  - **Standards:** your `CLAUDE.md` / `CONTRIBUTING.md` plus Fowler smells (Duplicated Code, Feature Envy, Primitive Obsession, …).
  - **Spec:** does the diff do what the issue asked?
- **`pr`** writes the PR body:
  - `## Summary`: the smallest visual (call tree, Mermaid, file tree).
  - `## Evidence`: before/after; screenshots are best, then test output.
  - `## Merge Danger`: **Door** (one-way or two-way) + **Blast Radius**.
  AskMedi example: "re-index to new embedding dims" = **one-way door**, blast radius = every answer. "Add 👍/👎" = two-way door.

---

## Phase 6 — Deployment

The skills don't deploy for you. They make the human steps safe and repeatable.

1. **`wizard`** generates an interactive bash script for the steps **only you can do** (dashboards, secrets). It reads `.env.example`, `render.yaml`, and `.github/workflows/*`, then confirms the stages with you. Example prompt:
   > "wizard: walk me through deploying AskMedi v2 — create Pinecone index (new dims), set Render env vars OPENAI_API_KEY/PINECONE_API_KEY, create Render Key Value for Redis, add GitHub Actions secrets for the eval job, run the ingest CLI once."

   Output: a script using `open_url`, `ask_secret`, `write_env`, `set_secret`. It is checked with `bash -n` and shellcheck, never run end to end by the agent. Run it in Git Bash on Windows.
2. **Deploy pipeline** (make it a ticket, built with `/implement`):
   - PR → GitHub Action: `pytest` (+ ruff). Optional eval job when the `rag` label is set.
   - `main` → Render autodeploy from the blueprint. `preDeployCommand: flask --app wsgi db upgrade` once Alembic exists.
   - Delete `Dockerfile` + `cicd.yaml`, or rewrite them deliberately. Record the choice in ADR-0001.
3. **Re-index is a one-way door.** Use a new Pinecone index or namespace, run ingest, run eval, then switch `PINECONE_INDEX` with an env var change. Rollback = flip the env var back.

---

## Phase 7 — Operate and improve

| Situation | Skill |
|---|---|
| New GitHub issues / user bug reports / external PRs | **`/triage`** (e.g. "show me anything that needs my attention", "move #42 to ready-for-agent"). Gives each a category + state, reproduces bugs, writes an agent brief, records rejected ideas in `.out-of-scope/`. |
| Prod bug, slow answers | **`diagnosing-bugs`** → afterwards **`/retro`** |
| No good seam to test the bug | **`/improve-codebase-architecture`** |
| Session ended, work unfinished | **`/handoff <what next session does>`** writes a doc in `%TEMP%` with suggested skills; secrets redacted |
| Agent's explanation made no sense | **`/wait-what`** re-pitches it simply, in glossary terms |
| After any session | **`/retro`** suggests environment fixes, worst first. Mechanical mistakes → lint/hook/CI; judgement calls → `CODING_STANDARDS.md` |

---

## Day-one script for v2 (copy and paste in order)

```text
1. /setup-matt-pocock-skills
2. research: <each row of the Phase 1 table>          (background; results in docs/research/)
3. /grill-with-docs Plan AskMedi v2. Read .claude/v1-README.md and docs/research/.
4. /to-spec
5. /to-tickets #<spec issue>
6. /clear
7. /implement #<ticket 01>     → review → commit   (/clear, repeat per ticket)
   or /implement-spec #<spec>
8. "write the PR body"  (pr skill)
9. wizard: deploy steps
10. /retro
Every few days: /improve-codebase-architecture
```

## Cheat sheet

| I want to… | Use |
|---|---|
| Know which skill to use | `/ask-matt` |
| Stress-test an idea (with docs) | `/grill-with-docs` (`/grill-me` outside a repo) |
| Gather facts with citations | `research` |
| Try something before committing | `prototype` |
| Plan something huge | `/wayfinder` |
| Write the spec | `/to-spec` |
| Break into tickets | `/to-tickets` |
| Build | `/implement` / `/implement-spec` (+ `tdd`) |
| Debug | `diagnosing-bugs` |
| Review | `code-review` |
| PR body | `pr` |
| Human-only setup steps | `wizard` |
| Handle incoming issues | `/triage` |
| Refactor safely | `/improve-codebase-architecture` + `codebase-design` |
| Improve the agent's setup | `/retro`, `writing-for-agents` |
| Continue tomorrow | `/handoff` |

## Gotchas

- A user-invoked skill can call model-invoked skills, but never another user-invoked one. Chain them by hand.
- `GLOSSARY.md` must stay pure vocabulary. Implementation notes go in ADRs or code.
- Tests must use agreed seams. Don't test LangChain internals; test `stream_answer`'s contract.
- `misc/setup-pre-commit` targets JS (Husky/Prettier). Not for this Python repo.
- Windows: `wizard` scripts are bash, so run them in Git Bash. `handoff` writes to `%TEMP%`.
- Never paste real keys into a chat. `.env` is gitignored; keep it that way.
