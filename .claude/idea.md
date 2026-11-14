# Idea — Scale AskMedi RAG to ~1,000 Documents + Research Papers

**Goal:** grow the corpus from 1 PDF to about **1,000 trusted documents**, a mix of consumer health content, drug labels, and peer-reviewed research papers. Every answer must stay **cite-or-refuse**.
Related: [v2-plan.md](v2-plan.md) (rev 2: M4 corpus, M5 retrieval, M6 guardrails), [security-analysis.md](security-analysis.md), [v1-README.md](v1-README.md).

> Licence facts below come from the official pages, read 2026-11-11. They are **not legal advice**. Rows marked ⚠️ could not be verified (page blocked) and must be checked by hand in a browser before use.

---

## 1. The licence rule (decide first)

AskMedi on the Play Store may be **commercial** (ads, paid tier, a company behind it). That decides which sources are allowed.

- ✅ **Allowed for commercial use:** public domain, CC0, CC BY, CC BY-SA (with share-alike on adaptations).
- ❌ **Exclude:** anything **NC** (non-commercial) and **ND** (no-derivatives, because chunking and summarising count as adaptation).
- Enforce it **in code**: the ingest pipeline rejects any document whose `licence` is not on an allowlist, and a test proves it.

### ⚠️ Existing `data/Medical_book.pdf`
Its licence is **unknown**. Large medical encyclopedias are usually copyrighted. Verify its origin and rights before a public or commercial release, or remove it from the production index.

---

## 2. Sources (verified)

| Source | Licence (from official page) | Access | Limits | Use in AskMedi |
|---|---|---|---|---|
| **PMC Open Access Subset** (research papers) | **Per article.** "License terms vary." Commercial-OK filter: CC0 / CC BY / CC BY-SA (**drop CC BY-ND**). The old `oa_comm`/`oa_noncomm` folders were removed Aug 2026; licence is now in per-article metadata. | AWS S3 `s3://pmc-oa-opendata` (us-east-1, `--no-sign-request`), daily inventory CSV; also OAI-PMH, E-utilities, BioC API. **Bulk scraping by other means is prohibited.** | no key for S3 | **Main research-paper source.** Full text as JATS XML. |
| **MedlinePlus** health topics | Web service "free of charge and does not require registration or licensing". **Health topic summaries are public domain.** **A.D.A.M. encyclopedia, ASHP drug monographs, and most images are copyrighted, so exclude them.** Attribution: "Source: MedlinePlus, National Library of Medicine". No logo, no implied endorsement. | `https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term=…` (`rettype=topic`); full XML file at medlineplus.gov/xml.html | **85 req/min per IP**, cache 12–24 h | **Consumer explanations** (plain language) |
| **openFDA drug labels** | **CC0**: "even for commercial purposes, all without asking permission". Attribution not required. Disclaimer: "Do not rely on openFDA to make decisions regarding medical care." | `https://api.fda.gov/drug/label.json`; SPL bulk downloads | ⚠️ limits not found on the pages read | **Drug facts**: indications, warnings, side effects. **Dosing sections are blocked by the output guard** (strict mode). |
| **CDC** pages | Mostly public domain, **with conditions**: attribute ("Source: CDC"), no-endorsement disclaimer, "may not change the substantive content", note that it's free on cdc.gov. Third-party and contractor content excluded. | No API; CDC asks you to link rather than re-post | — | Public-health topics. **Quote verbatim with a link; don't paraphrase.** |
| **MedQuAD** | **CC BY 4.0**. 47,457 QA pairs from 12 NIH sites. Answers from A.D.A.M./MedlinePlus drug/herbal were removed for copyright. Cite Ben Abacha & Demner-Fushman, BMC Bioinformatics 2019. | GitHub `abachaa/MedQuAD` (XML) | — | **Eval set** (golden Q&A seed) plus a corpus supplement |
| **PubMedQA** | Code MIT; **dataset licence not stated** | GitHub `pubmedqa/pubmedqa` | — | **Eval only, internal** (research-question reasoning). Don't ship it as content. |
| **medRxiv** preprints | Per-record `license` field; terms page doesn't state a global licence | `https://api.medrxiv.org/details/medrxiv/<from>/<to>/<cursor>/json` (100 per page) | ⚠️ not stated | **Avoid at launch.** Preprints aren't peer reviewed, which is risky for medical answers. Maybe later, labelled "preprint". |
| **Semantic Scholar** | Data **CC BY-NC or ODC-BY** per dataset; API terms forbid repackaging/redistributing | API (key: 1 RPS intro) | — | **Discovery only** (find papers, citation counts). Fetch the text itself from PMC OA. |
| **WHO** | Mostly **CC BY-NC-SA 3.0 IGO**: "Permission is required for commercial uses" | IRIS | — | ❌ Commercial: no (unless permission). OK only if AskMedi stays non-commercial. |
| StatPearls (NCBI Bookshelf) | ⚠️ unverified (page blocked by captcha) | — | — | Check by hand. Commonly reported as NC-ND, which would make it ❌. |
| OpenStax Anatomy & Physiology 2e | ⚠️ unverified (page didn't render) | — | — | Check by hand. If CC BY, it's ✅ and great for anatomy basics. |
| Europe PMC REST | ⚠️ unverified (403) | — | — | Alternative to PMC; same per-article licences |
| NICE guidelines | ⚠️ unverified (403) | — | — | UK guidelines; usually need a licence. Check by hand. |

---

## 3. Proposed ~1,000-document mix (commercial-safe)

| Bucket | Count | Source | Selection |
|---|---|---|---|
| Consumer health topics | ~300 | MedlinePlus summaries (public-domain part only) | Top conditions by search volume; English |
| Drug labels | ~150 | openFDA | Most-prescribed generics; strip or flag dosing sections |
| Public-health pages | ~50 | CDC | Vaccines, infectious disease, prevention. Verbatim plus link. |
| Research papers | ~450 | PMC OA (CC0/CC BY/CC BY-SA) | `review[pt]` / systematic reviews / guidelines, **last 10 years**, journals with impact or citation threshold (via Semantic Scholar counts), English, topics matching the consumer buckets |
| Anatomy basics | ~50 chapters | OpenStax (if licence verified) | Body systems |
| **Total** | **~1,000** | | |

Why mostly reviews: reviews summarise the evidence, while single studies can contradict each other and mislead a chatbot.

### Size and cost (rough; check current prices)
- Papers ~450 × ~8k tokens ≈ 3.6M · consumer/labels/CDC ~500 × ~2k ≈ 1M · anatomy ≈ 0.5M → **about 5M tokens**.
- Parent sections → **about 7–9k parents**; child chunks (~300 tokens) → **about 30–80k vectors**.
- Hosted embedding (e.g. `text-embedding-3-small`) for 5M tokens → around a few dollars or less (look up current pricing). Qdrant at about 9k (parent) or 30–80k (child) vectors is small.
- Takeaway: one-time cost is negligible. The real costs are **LLM calls per answer** and **reranking**.

---

## 4. Ingestion pipeline at scale

```
sources.yaml (what to fetch)
   │
fetch ──► raw/ (immutable, versioned, gitignored; S3/R2 in prod)
   │
normalize ──► Document{id, source, url, title, authors, journal, year,
   │                    doi/pmcid, licence, doc_type, section, lang, fetched_at, sha256}
licence gate ──► reject not-on-allowlist (logged in report)
   │
parse:  PMC → JATS XML (sections, drop references/acknowledgements; tables → text)
        MedlinePlus → XML summary · openFDA → JSON label sections · CDC → HTML main content
        user PDFs → layout-aware parser (PyMuPDF / docling / unstructured — research)
   │
dedupe: exact (sha256) + near-dup (MinHash) across sources
   │
chunk:  section-aware parent–child (child ~250–400 tok, parent ≤1.5k), contextual header (see v2-plan §4.2)
   │
embed (hosted) + BM25 sparse ──► upsert Qdrant collection `corpus-vN`, id = hash(doc_id, section_path, child_index)
   │                metadata: doc_type, year, licence, source, section, page/para, title
record in Postgres `documents` + `chunks` tables (status, version, hash) → resumable, idempotent
   │
ingest report: counts by source/licence/doc_type, rejects, dupes, failures
```

- **Resumable and idempotent:** re-running changes nothing unless a source hash changed.
- **Corpus versions:** `corpus-v1`, `corpus-v2`, … Evals run against a new collection before the env var flips (see v2-plan §8).
- **Refresh:** a monthly Render cron job re-fetches MedlinePlus/openFDA, adds new PMC reviews, and **removes withdrawn or retracted papers** (check the PMC retraction notices; research how).
- Runs offline/CLI and as a worker, **never inside the web request path**.

---

## 5. Retrieval changes for a mixed corpus

- **Two evidence tiers:** consumer (MedlinePlus/CDC/openFDA) for "what is / symptoms / side effects"; research (PMC) for "does X work / evidence / study". Classify the question, then use a metadata filter or boost by `doc_type`.
- **Hybrid search** (dense + BM25) matters more now: drug names, gene names, and abbreviations need exact-term matching.
- **Rerank** the top ~30 down to 5 with a cross-encoder or hosted reranker.
- **Recency boost** for papers; show the year in citations.
- **Citation format:**
  - Paper: `Smith et al., Lancet 2022 · PMC1234567 · CC BY`
  - Consumer: `MedlinePlus (NLM) — Asthma`
  - Label: `FDA label — Metformin (openFDA)`
- **Conflicting evidence:** if retrieved chunks disagree, the answer must say so ("Evidence is mixed…") instead of picking one side. Add an eval slice for this.
- **Research answers in plain language,** with a "this summarises research, not advice for you" line, and still refuse personal treatment advice.

---

## 6. Eval impact

New golden slices (add to the v2-plan §5 set):
- **Paper-grounded questions** (~60): the gold answer cites a specific PMC article and section.
- **Consumer questions** (~60): from MedQuAD (CC BY), mapped to the MedlinePlus docs in the corpus.
- **Conflicting-evidence** (~20): expect "mixed evidence" wording.
- **Recency** (~15): newer review should beat older.
- **Licence leakage test** (unit, not LLM): no chunk in the index has a licence outside the allowlist.
- Track **recall@k per doc_type**: research retrieval usually lags consumer and needs separate tuning.

---

## 7. Where this fits in v2

- Becomes **M4 "Corpus 1k + ingestion"** in v2-plan rev 2, after the backend core (M3) and alongside retrieval v2 (M5). Rough estimate 6–8 days.
- Skills flow:
  - `research` → verify the ⚠️ rows, retraction handling, PDF/JATS parsers, current embedding and reranker pricing.
  - `/grill-with-docs` → corpus scope, commercial vs non-commercial, consumer vs research tiers. ADRs: *0009 corpus sources & licence allowlist*, corpus versioning via Qdrant collections (part of *0010*), reviews over single studies.
  - `prototype` → logic prototype comparing retrieval on 50 papers: section-aware vs naive chunking, with and without rerank.
  - `/to-spec` → `/to-tickets` → `/implement` (tdd seam: `ingest(sources) -> IngestReport` with a fake fetcher and a fake vector store).
  - `wizard` → AWS CLI for the PMC S3 bucket, Semantic Scholar key, Qdrant collection, Render cron.

## 8. Open questions
1. Is AskMedi **commercial**? If not, WHO and StatPearls-type sources open up (NC).
2. Languages: English only, or Hindi and others? MedlinePlus has Spanish; translation affects licences (adaptation).
3. Which specialties first? (Pick 10–20 top conditions so 1k docs give depth, not thin coverage.)
4. Can users upload their own documents? (That brings privacy issues and a separate per-user collection. Recommend **not** in v2.)
5. Who reviews corpus quality: a clinician spot-check of 50 random chunks before launch?
6. Keep or drop `Medical_book.pdf` after the licence check?
