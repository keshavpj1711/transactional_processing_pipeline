# Transaction Processing Pipeline

A backend service that ingests a CSV of raw financial transactions, processes it
asynchronously, uses a language model to classify uncategorised transactions and
write a narrative summary, flags anomalies, and serves the results through a
polling API.

## What it does

Raw transaction exports are dirty: mixed date formats, inconsistent casing,
currency symbols stuck to amounts, missing categories, duplicate rows, and the
occasional suspiciously large charge. This service turns that into clean,
queryable, auditable data.

A CSV upload becomes a **job**. The job is processed by a background worker in a
fixed order:

1. **Clean** — normalise dates to ISO 8601, strip currency symbols from amounts,
   uppercase status and currency, fill missing categories with `Uncategorised`,
   and remove exact duplicate rows.
2. **Detect anomalies** — flag any amount greater than three times its account's
   median, and any USD transaction at a domestic-only merchant (Swiggy, Ola,
   IRCTC).
3. **Classify** — for rows that arrived without a category, ask the LLM (in
   batches) to assign one of: Food, Shopping, Travel, Transport, Utilities, Cash
   Withdrawal, Entertainment, Other.
4. **Summarise** — a single LLM call produces a narrative summary: spend per
   currency, top merchants, anomaly count, a short narrative, and a risk level.

Every input row is accounted for: `raw rows = clean rows + duplicates removed`,
and the worker refuses to complete a job whose counts don't reconcile.

## Architecture

```
            POST /jobs/upload
client  ───────────────────────▶  FastAPI (api)
   ▲                                  │  create Job(pending), store raw CSV
   │  GET /jobs/{id}/status           │  enqueue task, return job_id (202)
   │  GET /jobs/{id}/results          ▼
   │                               Redis  (Celery broker)
   │                                  │
   │                                  ▼
   └──────────  reads  ──────────  Celery worker
                  │                clean → anomaly → LLM classify → LLM summary
                  ▼                       │
              PostgreSQL  ◀───────────────┘  persist transactions + summary
```

Five services start with one command via Docker Compose: `postgres`, `redis`,
`api`, `worker`, and a one-shot `migrate` service that applies database
migrations before the api and worker start.

| Concern | Choice |
| --- | --- |
| API | FastAPI |
| Async processing | Celery + Redis |
| Storage | PostgreSQL (SQLAlchemy + Alembic) |
| LLM | OpenRouter (OpenAI-compatible), with a deterministic offline stub |
| Packaging | Docker + Docker Compose |

## Running it

```bash
docker compose up --build
```

That is the only required step. With no configuration the service uses a
deterministic stub for the LLM, so the entire flow works offline with no API key.

The API is then available at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`).

### Using a real LLM (optional)

Copy `.env.example` to `.env` and set an OpenRouter key:

```bash
cp .env.example .env
# edit .env: set OPENROUTER_API_KEY and, if you like, LLM_MODEL
```

If `OPENROUTER_API_KEY` is empty (or `USE_STUB_LLM=true`), the stub is used.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/jobs/upload` | Upload a CSV. Returns a `job_id` immediately. |
| `GET` | `/jobs/{job_id}/status` | Job status; includes a summary once completed. |
| `GET` | `/jobs/{job_id}/results` | Cleaned transactions, anomalies, per-category spend, and the narrative summary. |
| `GET` | `/jobs?status=` | List jobs, optionally filtered by status. |

### Example session

Upload the sample file and capture the job id:

```bash
curl -s -X POST http://localhost:8000/jobs/upload \
  -F "file=@tests/fixtures/transactions_sample.csv"
# {"job_id":1,"status":"pending","filename":"transactions_sample.csv"}
```

Poll until the job is complete:

```bash
curl -s http://localhost:8000/jobs/1/status
# {"job_id":1,"status":"completed",
#  "summary":{"row_count_raw":95,"row_count_clean":85,"anomaly_count":5,"risk_level":"high"}}
```

Fetch the full results:

```bash
curl -s http://localhost:8000/jobs/1/results
```

List jobs:

```bash
curl -s "http://localhost:8000/jobs?status=completed"
```

## Data model

- **Job** — one uploaded CSV: filename, status, raw/clean row counts, the raw
  CSV text (so processing is reproducible), timestamps, and any error message.
- **Transaction** — one cleaned row, with anomaly flags and the LLM category
  (kept separate from the original category).
- **JobSummary** — the LLM-generated report for a job.

## Design notes

- **The upload returns immediately.** Cleaning and LLM calls happen in the
  worker, so request latency is never tied to model latency.
- **Cleaning, anomaly detection, and aggregation are pure functions** over data
  frames — no database or queue — so they are easy to test and reuse. The worker
  is the only place that touches the database and the LLM together.
- **The LLM provider is behind an interface.** Swapping providers, or running the
  offline stub, is a configuration change. Classification calls are batched, and
  failures retry with exponential backoff; if a batch still fails, those rows are
  marked and the job continues rather than failing wholesale.
- **Nothing is dropped silently.** Duplicates are removed only when entire rows
  match, so rows with a blank `txn_id` are preserved; the row counts always
  reconcile.

## Tests

```bash
pip install -r requirements.txt
pytest
```

The suite covers the cleaning rules, deduplication and reconciliation, anomaly
detection, LLM response parsing (including malformed output), and the full API
flow with an in-memory database and the stub LLM.

## Scaling notes

At roughly 100x the current volume the first pressure points are: loading whole
CSVs into worker memory, a single Redis instance, Celery prefetching long LLM
tasks onto one worker, the database connection pool, and LLM provider rate
limits. The next iteration would stream/chunk CSV parsing, move raw files to
object storage, partition and index the transactions table, compute the
per-account median with a SQL window function instead of in memory, rate-limit
batched LLM calls on a dedicated queue, and add connection pooling and read
replicas for the read-heavy status/results endpoints.
