# AskMedi v2 — Resources Checklist

What you need to add or obtain to build v2 ([v2-plan.md](v2-plan.md)). Check current prices and terms when you sign up; they change.

## 1. Accounts and API keys

| Needed by | Service | Purpose | Notes |
|---|---|---|---|
| M1 | **OpenAI** API | LLM, embeddings, Moderation API, answer evals | Raise the usage tier early: 50k DAU needs millions of tokens per minute at peak |
| M3 | **Render** (staging + prod projects) | API, worker, Postgres, Key Value (Redis), cron | |
| M3 | **Cloudflare** | DNS, proxy, WAF, rate limiting, R2 | Free plan to start; rate-limit rules may need a paid plan |
| M3 | Domain name | API, web, legal pages, email | |
| M3 | Resend or Postmark | Verification and reset emails | Set SPF/DKIM/DMARC |
| M4 | **Qdrant Cloud** | Hybrid dense + BM25 vector search | Free tier is enough for development |
| M4 | AWS CLI (no account needed) | PMC Open Access S3 bucket, `--no-sign-request` | |
| M4 | Semantic Scholar API key (optional) | Citation counts for paper selection | |
| M5 | **Cohere** | Rerank | Trial key for dev; production key before launch |
| M6 | **Anthropic** API | Fallback LLM | |
| M7 | **Langfuse** (cloud or self-host) | LLM traces, cost, eval scores | |
| M7 | **Sentry** | Error and performance tracking (API, web, Flutter) | |
| M8 | Vercel (or Render) | Next.js hosting | |
| M9 | **Google Play Console** | Android release (one-time registration fee) | Identity verification can take days; start early |
| M9 | Firebase | Crashlytics for Flutter | |
| All | GitHub | Repo, issues, Actions, Dependabot, CodeQL | |

## 2. People

- **Clinician reviewer** (doctor or pharmacist): crisis copy, emergency list, safety golden rows, provider-verification rules, 50-chunk corpus spot check.
- **Legal / privacy review** before public launch: privacy policy, terms, medical disclaimer, DPDP consent flow.
- **5–10 beta testers**, including at least one clinician and one non-technical user.

## 3. Data sources (see [corpus-plan.md](corpus-plan.md))

| Source | Use |
|---|---|
| PMC Open Access Subset (CC0 / CC BY / CC BY-SA only) | Research papers |
| MedlinePlus health topics (public-domain summaries) | Consumer health |
| openFDA drug labels (CC0) | Drug facts and label dosing (provider role) |
| CDC pages (verbatim + link) | Public health |
| RxNorm / RxNav API (NLM) | Brand → generic normalisation |
| MeSH (NLM) | Synonym expansion for BM25 |
| MedQuAD (CC BY 4.0) | Golden-set seed questions |
| PubMedQA | Internal eval only |
| OpenAI HealthBench | Eval ideas and rubric style (check licence before use) |

## 4. Docs to read (by milestone)

| Milestone | Read |
|---|---|
| M2 security | OWASP Top 10 for LLM Applications 2025 · OWASP API Security Top 10 2023 · OWASP ASVS · NIST AI RMF + Generative AI Profile (NIST AI 600-1) · WHO guidance on large multi-modal models for health (2024) · OpenAI's Aug 2025 post "Helping people when they need it most" · India DPDP Act 2023 + Rules |
| M3 backend | FastAPI docs (lifespan, dependencies, streaming responses) · SQLAlchemy 2 async · Alembic · Pydantic v2 · arq · Render blueprints (`render.yaml`) |
| M4 ingestion | Docling docs · JATS XML tag library · PMC OA S3 docs · openFDA label API · MedlinePlus web service |
| M5 retrieval | Qdrant hybrid queries (Query API, prefetch, RRF fusion) · Qdrant BM25 with FastEmbed (`Qdrant/bm25`, IDF modifier) · Cohere Rerank docs · Anthropic "Introducing Contextual Retrieval" (2024) · MedCPT paper (biomedical retriever) |
| M6 guardrails | OpenAI Moderation API · Microsoft Presidio · promptfoo red teaming · NLI-based groundedness checks |
| M7 scale | k6 (or Locust) with SSE · Langfuse tracing + evals · Sentry FastAPI/Next.js/Flutter SDKs · Cloudflare WAF and rate-limiting rules |
| M8 web | Next.js App Router · openapi-typescript / openapi-fetch · Playwright · WCAG 2.2 |
| M9 Android | Flutter + Riverpod · Play Console Health apps policy · Data Safety form · account deletion requirement |

## 5. Learning material (Gen AI product engineering)

- Chip Huyen, *AI Engineering* (O'Reilly, 2025): evals, RAG, guardrails, cost.
- Hamel Husain and Shreya Shankar on LLM evals (error analysis, LLM-as-judge done right).
- Eugene Yan, "Patterns for Building LLM-based Systems & Products".
- Anthropic and OpenAI cookbooks: RAG, structured outputs, prompt caching.
- Qdrant articles on hybrid search and sparse vectors.

## 6. Local tooling

uv · Docker Desktop · Node.js LTS + pnpm · Flutter SDK + Android Studio · k6 · promptfoo · pre-commit · AWS CLI · gh CLI.
