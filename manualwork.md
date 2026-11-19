# Manual work — what only you can do

Everything else is built and committed. Do these in order; each step says how long it takes,
exactly what to type or click, and how to know it worked. Commands run in **Git Bash** or
**PowerShell** from the repository folder unless a step says otherwise.

| # | Task | Time | Why it matters |
|---|---|---|---|
| 1 | Review the eval questions | 45 min | Makes the retrieval numbers trustworthy enough to quote |
| 2 | Run the app and click through it | 20 min | Confirms the website works end to end on your machine |
| 3 | Build the insurance policy library | 5 min | Needed before the policy demo page shows anything |
| 4 | Rotate Gemini key; add OpenAI key later | 5 min | Better-written answers; unlocks the answer-quality evals |
| 5 | (Optional) Add a commercial specimen policy | 20 min | Makes the Outmarket demo closer to their product |
| 6 | Record the 2-minute Loom demo | 30 min | Goes in your email |
| 7 | Put the real numbers in your email | 10 min | Only quote what the tools measured |
| 8 | Open and merge the pull request | 10 min | Makes v2 the main version on GitHub |
| 9 | Clinician review | external | Required before real users get medicine suggestions |
| 10 | Deploy free (Hugging Face Space + Neon + Qdrant Cloud) | 30 min | Turns "production-grade" into "in production" |
| 11 | Turn on Logfire + LangSmith tracing, make yourself admin | 15 min | Lets you open any answer and see every step |

---

## 1. Review the eval questions (45 min)

The test questions were written by code (`v2_corpus.jsonl`) and by me (`v2_hard.jsonl`). A person
must check them before you quote numbers from them.

1. Open `evals/golden/v2_hard.jsonl` in VS Code. Each line is one question.
2. For each line, ask yourself: *would a real person ask this, and is `expect_docs` the right
   document?* You can check a document id in `data/corpus/manifest.csv` (search for it).
3. If the line is good, change `"reviewed": false` to `"reviewed": true`.
   If the expected document is wrong, fix `expect_docs`. If the question is bad, delete the line.
4. Add 10–20 questions of your own in the same format, written the way your friends or family
   would ask (spelling mistakes are fine). Set `"reviewed": true` on them.
5. Do the same for at least 50 lines of `evals/golden/v2_corpus.jsonl`.
6. Re-run the comparison on reviewed rows only (stop the API server first, see step 3 note):

   ```bash
   cd backend
   uv run python -m app.eval_ablation --golden ../evals/golden/v2_hard.jsonl --reviewed-only
   uv run python -m app.eval_ablation --reviewed-only
   ```

   Results land in `evals/results/v2/ablation-hard-reviewed.md` and `ablation-reviewed.md`.
7. Commit: `git add evals && git commit -m "test(evals): review golden questions"`.

**Done when:** the reviewed ablation files exist. Quote those numbers, not the unreviewed ones.

## 2. Run the app and click through it (20 min)

1. Terminal 1 (backend):

   ```bash
   cd backend
   uv sync --extra local
   uv run uvicorn app.main:create_app --factory --port 8000
   ```

   Wait for `Application startup complete`. The first start downloads two small models (about 150 MB).
2. Terminal 2 (website):

   ```bash
   cd web
   npm install
   npm run dev
   ```

3. Open http://localhost:5173 and check each item:
   - [ ] Create an account (tick both boxes). You land on the chat.
   - [ ] Ask "What are the symptoms of dengue?" — answer with numbered citations; click a number.
   - [ ] Ask "Write me a Python function" — polite refusal.
   - [ ] Ask "I have a headache, what medicine can I take?" — 3 question cards, then medicine cards with label directions.
     Try answering "A child" once: it should say to ask a pharmacist.
   - [ ] Ask "I have crushing chest pain right now" — emergency card with a call button.
   - [ ] Click 👍 on an answer; open **Settings** and download your data.
   - [ ] Open **Policy demo** in the sidebar (after step 3) and click **Compare exclusions**.
4. If anything looks wrong, note what you clicked and what happened, and paste it to me.

**Note:** the local vector database allows one program at a time. Stop the backend (Ctrl+C)
before running any `python -m app.ingest`, `app.policies` or `app.eval_*` command.

## 3. Build the insurance policy library (5 min)

Stop the backend first, then:

```bash
cd backend
uv run python -m app.policies build
```

It downloads the three FEMA flood policy forms from govinfo.gov (public domain), parses them,
saves them to `data/policies/`, and indexes them. **Done when** it prints three lines like
`sfip-general-property: 10 sections, … chunks indexed`. Then commit the parsed policies:

```bash
git add data/policies && git commit -m "feat(data): add parsed FEMA flood policy forms"
```

## 4. Answer writer: Gemini now, OpenAI later (5 min)

Already done: `backend/.env` has `LLM_PROVIDER=auto` and your Gemini free-tier key, so answers
are written by `gemini-3.1-flash-lite` today. If Gemini fails or hits its rate limit, the app
falls back to extractive answers (copied source sentences) on its own.

1. **Rotate the Gemini key.** It was pasted in chat. Make a new one at
   https://aistudio.google.com/apikey, delete the old one, and put the new one in `backend/.env`
   as `GEMINI_API_KEY=...`.
2. Free-tier prompts may be used by Google to improve its products. Test with sample
   questions only, never real patients' messages.
3. When you have OpenAI credit: create a key at https://platform.openai.com/api-keys, set a
   spending limit (Settings → Limits, e.g. $10/month), and add it to `backend/.env`:

   ```
   OPENAI_API_KEY=sk-...your key...
   ```

   Leave `LLM_PROVIDER=auto`. OpenAI becomes primary and Gemini its fallback, with no code change.
4. **Never commit `.env`.** Check with `git status`: `.env` must not appear.
5. Restart the backend. Check which model is live: `curl http://127.0.0.1:8000/readyz` shows
   `"llm": {"models": [...]}` (dev only).
6. Re-run the evals and compare with the free-mode results:

   ```bash
   cd backend
   uv run python -m app.eval_run run
   ```

## 5. (Optional) Add a commercial specimen policy (20 min)

Insurers publish "specimen" policy PDFs (search: `"commercial general liability" specimen policy pdf`
or `"business owners policy" specimen pdf`). These are copyrighted.

- Use them **only on your machine for the demo**. Don't commit the PDF or publish the parsed text.
- Save the PDF to `data/raw/policies/` (already gitignored), then:

  ```bash
  cd backend
  uv run python -m app.policies add ../data/raw/policies/acme-cgl.pdf --id acme-cgl --title "Acme CGL specimen" --form "Commercial General Liability"
  ```

- Check the printout: it should list sections and a non-zero number of exclusion clauses. If it
  finds 0, send me the printout; the generic parser may need a heading rule for that insurer.
- Add `data/policies/acme-cgl.json` to `.git/info/exclude` so it never gets committed.

## 6. Record the 2-minute Loom (30 min)

Install Loom (https://www.loom.com), share your browser window, and follow this script:

| Time | Show | Say (roughly) |
|---|---|---|
| 0:00 | Landing page | "AskMedi answers health questions only from licensed sources and cites every sentence, or it refuses." |
| 0:15 | Ask "What are the symptoms of dengue?", click a citation | "Hybrid search: BM25 plus dense vectors, reranked. Each sentence links to the exact source section." |
| 0:35 | Ask "What is the capital of France?" then "I have chest pain right now" | "Out of scope is refused. Emergencies get a call button, never chat." |
| 0:55 | Headache → 3 questions → medicine cards | "Doses are copied from FDA labels; no model writes a dose. Blood thinners remove ibuprofen, with the reason." |
| 1:20 | Policy demo → Compare exclusions → expand a cell → ask "Is landslide damage covered?" | "Same retrieval on insurance policies: exclusions compared clause by clause with page numbers." |
| 1:45 | GitHub Actions run (eval job summary) and `evals/results/v2/ablation.md` | "Every pull request runs the eval gate; it fails if recall or safety drops." |

## 7. Put the real numbers in your email (10 min)

Open `evals/results/v2/ablation-hard-reviewed.md` (after step 1) and copy the Recall@5 for
**Dense only** and for **Hybrid + rerank** into the email. Use this sentence only if hybrid is
actually higher on the reviewed set:

> On hand-written questions that use lay terms and brand names, hybrid retrieval with reranking
> moved recall@5 from **X** (dense only) to **Y**.

If dense only is as good or better, say that instead. It's an honest finding and a better
interview story ("I measured it, and the extra stage only helped for X").

## 8. Open and merge the pull request (10 min)

1. Go to https://github.com/Abhishek764/AskMedi-Medical-Chatbot/pull/new/v2/backend
2. Title: `AskMedi v2: FastAPI + React RAG with evals, safety and policy demo`.
3. Create the pull request and wait for the checks: **backend / test**, **backend / eval**,
   **web / build** must all be green. If the eval job fails, open its summary and send it to me.
4. Click **Merge pull request**. `main` now holds v2.

## 9. Clinician review (external)

Send a doctor or pharmacist:
- `docs/security-analysis.md` §2 (crisis protocol) and §8 (medicine check),
- `backend/app/triage/symptoms.py` (warning signs per symptom) and `engine.py` (`EXCLUSIONS`),
- `backend/app/guards/resources.py` (helpline numbers and crisis wording).

Ask them to mark anything unsafe or missing. Each change becomes a row in
`backend/tests/test_triage.py` or `test_guards.py`; send me their notes and I'll implement them.

## 10. Deploy for free (about 30 min)

Free stack: **Hugging Face Space** (Docker, 16 GB RAM: runs the API, local models and the
website in one container), **Neon** Postgres (created: project `askmedi`, us-east-1),
**Qdrant Cloud** free cluster, Gemini free key. Render's free plan (512 MB) is too small:
the embedding model plus reranker need about 620 MB.

1. **Qdrant Cloud:** copy the **full** API key from https://cloud.qdrant.io (Data Access
   Control → API keys). In `backend/.env` paste it into `QDRANT_API_KEY=` and remove the
   leading `# ` from `QDRANT_URL` and `QDRANT_API_KEY`. Then copy the local index (corpus and
   policies, nothing re-embedded):

   ```bash
   cd backend
   uv run --no-sync python scripts/copy_index.py
   ```

2. **Hugging Face:** sign up at https://huggingface.co → *New Space* → name `askmedi`,
   SDK **Docker** (blank template), hardware *CPU basic (free)*, Public.
3. Create a **write** token at https://huggingface.co/settings/tokens.
4. Space → *Settings* → *Variables and secrets*: add each line of `backend/.env.space`
   (gitignored; already holds the Neon URL, a fresh JWT secret and the Gemini key) as a
   **secret**, filling in `QDRANT_URL`, `QDRANT_API_KEY` and your username in `CORS_ORIGINS`.
5. Push the code (from Git Bash, repo root):

   ```bash
   HF_TOKEN=hf_xxx HF_SPACE=<your-hf-username>/askmedi bash deploy/hf/push.sh
   ```

   The build takes about 10 minutes. Open `https://<your-hf-username>-askmedi.hf.space`
   directly: the huggingface.co page frames the app, which the security headers block.
6. Promote yourself to admin for `/admin`: run `python -m app.admin promote <email>` with
   `DATABASE_URL` from `backend/.env.space`.
7. Load test, then paste me the output:

   ```bash
   cd backend
   uv run python scripts/loadtest.py --base https://<your-hf-username>-askmedi.hf.space --users 20 --rps 5 --duration 60
   ```

Limits: the Space sleeps after 48 h without visitors (first request then waits ~1 min);
rate limits and quotas live in memory and reset when it restarts; Gemini free tier is slow
at peak times (answers fall back to extractive). The paid path is still `render.yaml`.

Before letting real users in: privacy policy, terms of use and a medical disclaimer page
(a lawyer should look at these, especially for showing medicine doses in India).

## 11. Turn on tracing and the dashboard (15 min)

Everything is built; it only needs your accounts. Full reference: `docs/OBSERVABILITY.md`.

1. **Make yourself admin** (sign up in the web app first, with your own email):

   ```bash
   cd backend
   uv run python -m app.admin promote YOUR-EMAIL
   ```

   Sign out and in again. A **Dashboard** link appears under your email in the chat sidebar
   (or open http://localhost:5173/admin).
2. **Pydantic Logfire** (free tier): sign in at https://logfire.pydantic.dev, create a project
   called `askmedi`, then *Settings → Write tokens → New token*. Paste it in `backend/.env`:
   `LOGFIRE_TOKEN=...`
3. **LangSmith** (free developer plan): sign in at https://smith.langchain.com, then
   *Settings → API Keys → Create API key*. Paste it in `backend/.env`:
   `LANGSMITH_API_KEY=...` (leave `LANGSMITH_PROJECT=askmedi`).
4. Restart the backend and ask one question. Within a minute you should see a trace named
   `answer` in both tools, with the steps `input_guard → retrieve → generate → llm … → verify`.
5. Leave `TRACE_CONTENT=false` unless you are testing with made-up questions: with `true`
   the question and answer text are sent to these services.
6. (Optional) Grafana: install/start Docker Desktop, then
   `docker compose -f deploy/observability/docker-compose.yml up -d` and open
   http://localhost:3001.

