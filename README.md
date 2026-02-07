# Real-Time Leaderboard System

A robust, ACID-compliant leaderboard engine for online examination platforms where **N candidates submit answers simultaneously** without data loss or race conditions.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | Python 3.11+, Flask 3.x |
| **ORM** | SQLAlchemy 2.0 (async-ready) |
| **Database** | MySQL 8.0+ (InnoDB — SERIALIZABLE isolation) |
| **Cache** | Redis 7+ via Flask-Caching |
| **Validation** | Marshmallow 3 |
| **Testing** | pytest, threading-based concurrency tests |
| **Production** | Gunicorn, Celery (optional async recalc) |

---

## Architecture Overview

```
┌─────────────┐     POST /scores      ┌──────────────────────┐
│  Candidate   │ ───────────────────▶  │   Flask API Layer    │
│  Browser /   │                       │  (Request Validation)│
│  App Client  │  GET /leaderboard     │                      │
│              │ ◀─────────────────── │                      │
└─────────────┘                       └──────────┬───────────┘
                                                  │
                                      ┌───────────▼───────────┐
                                      │   Scoring Engine       │
                                      │  ┌─────────────────┐   │
                                      │  │ Weighted Calc    │   │
                                      │  │ Optimistic Lock  │   │
                                      │  │ DENSE_RANK()     │   │
                                      │  └─────────────────┘   │
                                      └───────────┬───────────┘
                                                  │
                               ┌──────────────────┼──────────────────┐
                               │                  │                  │
                       ┌───────▼──────┐   ┌───────▼──────┐   ┌──────▼───────┐
                       │  MySQL 8.0   │   │    Redis     │   │  Audit Log   │
                       │  (InnoDB)    │   │   (Cache)    │   │  (Append-    │
                       │  SERIALIZABLE│   │   TTL=5s     │   │   only)      │
                       └──────────────┘   └──────────────┘   └──────────────┘
```

---

## Database Schema (6 Tables)

| Table | Purpose |
|-------|---------|
| `users` | Candidates, admins, moderators |
| `exams` | Exam definitions with configurable weights |
| `exam_sessions` | One row per candidate per exam attempt |
| `module_scores` | Per-module breakdown (coding / quiz / assessment) |
| `leaderboard_snapshot` | Materialised ranked view, updated transactionally |
| `score_audit_log` | Append-only history for traceability |

Full DDL: [`database/schema.sql`](database/schema.sql)

---

## Scoring Algorithm

### Weighted Formula

For each module $m \in \{\text{coding}, \text{quiz}, \text{assessment}\}$:

$$\text{normalised}_m = \frac{\text{raw\_score}_m}{\text{max\_score}_m}$$

$$\text{weighted}_m = \text{normalised}_m \times \text{weight}_m$$

$$\text{Total Score} = \sum_{m} \text{weighted}_m$$

### Default Weights

| Module | Weight |
|--------|--------|
| Coding Challenges | 50% |
| Quiz (MCQ / Boolean) | 30% |
| Online Assessment | 20% |

Weights are **configurable per exam** in the `exams` table and must sum to 100.

### Tie-Breaking Rule

When two candidates have the same Total Score:

$$\text{rank}(A) < \text{rank}(B) \iff \text{total\_time}(A) < \text{total\_time}(B)$$

The candidate with **lower total time** ranks higher. Implemented via:

```sql
DENSE_RANK() OVER (
    ORDER BY total_score DESC,
             total_time_sec ASC
)
```

---

## Concurrency & ACID Guarantees

| Mechanism | Purpose |
|-----------|---------|
| **SERIALIZABLE isolation** | Prevents phantom reads during score writes |
| **SELECT … FOR UPDATE** | Row-level lock on session during module upsert |
| **Optimistic locking** | `version` column detects concurrent modifications |
| **Retry logic** | Up to 3 automatic retries on deadlock/lock-timeout |
| **Atomic transaction** | Score upsert + total recalc + rank refresh in ONE commit |
| **Audit log** | Append-only table records every score mutation |

---

## API Endpoints

### `POST /api/v1/scores` — Submit Module Score

```json
{
  "session_id": 42,
  "module_type": "coding",
  "raw_score": 85.5,
  "max_score": 100,
  "time_spent_sec": 2400,
  "details": {
    "test_cases_passed": 17,
    "test_cases_total": 20,
    "time_complexity_score": 90,
    "efficiency_score": 80
  }
}
```

**Response 200:**
```json
{
  "message": "Score submitted",
  "leaderboard_entry": {
    "rank": 3,
    "total_score": 81.0,
    "weighted_coding": 42.75,
    "weighted_quiz": 27.0,
    "weighted_assessment": 14.0,
    "total_time_sec": 4200
  }
}
```

### `GET /api/v1/leaderboard?exam_id=1&page=1&per_page=50`

```json
{
  "exam_id": 1,
  "exam_title": "Backend Challenge 2026",
  "total_participants": 842,
  "page": 1,
  "per_page": 50,
  "leaderboard": [
    {
      "rank": 1,
      "user_id": 17,
      "username": "alice",
      "full_name": "Alice Chen",
      "total_score": 94.5,
      "total_time_sec": 3200
    }
  ],
  "my_entry": { "rank": 127, "..." : "..." },
  "cached": true
}
```

### `POST /api/v1/sessions` — Start Exam Session

```json
{ "exam_id": 1, "user_id": 42 }
```

### `PATCH /api/v1/sessions/<id>/finish` — Submit Exam

### `POST /api/v1/leaderboard/recalculate` — Admin: Force Recalculation

---

## Project Structure

```
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Environment-based configuration
│   ├── extensions.py        # SQLAlchemy, Redis, Marshmallow
│   ├── models.py            # ORM models (6 tables)
│   ├── schemas.py           # Request/response validation
│   ├── api/
│   │   ├── leaderboard.py   # GET /leaderboard endpoint
│   │   ├── scores.py        # POST /scores endpoint
│   │   └── sessions.py      # Session management
│   └── services/
│       └── scoring_engine.py # Core algorithm + concurrency
├── database/
│   └── schema.sql           # Full DDL
├── tests/
│   ├── test_api.py          # Integration tests
│   └── test_concurrency.py  # Parallel submission stress tests
├── wsgi.py                  # Gunicorn entry point
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your MySQL and Redis credentials

# 3. Create database
mysql -u root -e "CREATE DATABASE leaderboard_db;"
mysql -u root leaderboard_db < database/schema.sql

# 4. Run migrations (or use schema.sql directly)
flask db init
flask db migrate -m "initial"
flask db upgrade

# 5. Start the server
flask run --debug          # development
gunicorn "app:create_app()" -w 4  # production

# 6. Run tests
pytest tests/ -v
```

---

## Performance Considerations

- **Redis caching** on `GET /leaderboard` with 5s TTL — absorbs read spikes during live exams
- **Composite index** `(exam_id, total_score DESC, total_time_sec ASC)` — sorted retrieval without filesort
- **Connection pooling** — 20 base + 40 overflow connections with auto-reconnect
- **Pagination** — prevents full-table scans on large exams (max 200 per page)
- **Materialised leaderboard** — pre-computed ranks avoid expensive window-function queries on every read
