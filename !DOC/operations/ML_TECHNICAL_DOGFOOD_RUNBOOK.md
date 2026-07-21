# Dogfood Runbook: `ml_technical` Track — First Founder Session

> Run from project root: `C:\Users\badmaev_es\develop\englishFriend`

## Prerequisites

- Python venv active: `venv\Scripts\activate` (Windows)
- Node.js 18+ installed (for frontend build)
- Docker Desktop running (for PostgreSQL)
- Local Qwen provider accessible at `VLLM_BASE_URL` (default: `http://192.168.0.18:8000/v1`)

## 1. Verify Local Qwen Provider

The provider is vLLM on `192.168.0.18:8000`. Confirm it responds:

```powershell
# From project root:
curl http://192.168.0.18:8000/v1/models
```

Expected: a JSON object with a `data` array containing the `Qwen3.6-35B-A3B-Q5-256K` model.

**Variables to confirm:**
- `VLLM_BASE_URL` — currently `http://192.168.0.18:8000/v1` (owner confirmation)
- `VLLM_API_KEY` - confirm the local value in `.env`; do not copy it into reports or commits
- `VLLM_MODEL` — currently `Qwen3.6-35B-A3B-Q5-256K`
- `VLLM_EXTRA_BODY_JSON` — `{"chat_template_kwargs": {"enable_thinking": false}}` (thinking must be disabled)

If the vLLM host is unavailable, set `LLAMA_CPP_BASE_URL` to the same host with `LLM_PROVIDER=llama_cpp` as fallback.

## 2. Start PostgreSQL

```powershell
# From project root:
docker compose up -d postgres
```

Wait for readiness:

```powershell
# From project root:
docker exec english_friend_postgres pg_isready -U postgres -d english_friend
```

Before starting the API, align `DATABASE_URL` with the actual Compose database. The
checked-in examples currently disagree: Compose creates database `english_friend` with
its local development password, while `.env.example` points to `englishfriend_dev` with
a different password. Do not treat either value as confirmed. Pick one local database
name/password pair and make both configurations match.

## 3. Start the API

```powershell
# From project root (new terminal):
python main.py
```

Verify:

```powershell
curl http://localhost:8000/health
```

Expected: `{"status":"healthy","message":"English Friend API работает"}`

Verify the ml_technical router loaded:

```powershell
curl http://localhost:8000/docs
```

Look for the `ml_technical` tag with 4 endpoints: `GET /{user_id}/topics`, `POST /{user_id}/sessions`, `POST /{user_id}/answers`, `GET /{user_id}/attempts`.

## 4. Build / Start the Mini App (Frontend)

```powershell
# From project root/frontend:
cd frontend
npm run build
npm run preview
```

The dev server listens on `http://localhost:5173`. The preview server (build) listens on `http://localhost:4173`.

**Variables to confirm:**
- `VITE_API_URL` — currently `http://localhost:8000` (owner confirmation)

If running inside Telegram Mini App, the host must be reachable from Telegram's proxy. For local dogfood, open the preview URL in a browser.

## 5. Verify MCP Server

The `ml_technical` MCP server runs as a stdio process:

```powershell
# From project root:
venv\Scripts\python.exe -m app.mcp.ml_technical_server
```

Expected: the process starts and waits for stdio JSON-RPC input. It exposes 4 tools:
- `get_ml_technical_progress` — read track/topic progress for a user
- `get_ml_technical_attempts` — read recent or needs_review attempts
- `append_ml_technical_external_review` — append Sonnet/Codex review evidence
- `list_ml_technical_question_pack` — read-only question pack

The `.mcp.json` config launches it via:

```json
"ml_technical": {
  "command": "C:\\Users\\badmaev_es\\develop\\englishFriend\\venv\\Scripts\\python.exe",
  "args": ["-m", "app.mcp.ml_technical_server"],
  "env": { "PYTHONPATH": "C:\\Users\\badmaev_es\\develop\\englishFriend" }
}
```

## 6. Run Focused Acceptance Tests

All tests are DB-free (pure function tests):

```powershell
# From project root:
venv\Scripts\python.exe -m pytest tests/test_ml_technical_questions.py tests/test_ml_technical_service.py tests/test_ml_technical_reviewer.py -v
```

Expected: 55 focused tests pass. No database connection is required.

Optional import sanity check:

```powershell
venv\Scripts\python.exe -c "import app.api.ml_technical; import app.mcp.ml_technical_server; print('imports=PASS')"
```

---

## Manual Smoke Checklist

Perform these steps in order. Record pass/fail for each.

| # | Step | Expected Evidence | Pass / Fail |
|---|------|-------------------|-------------|
| 1 | `GET /health` on API | `{"status":"healthy"}` | |
| 2 | `GET /api/v1/ml-technical/{user_id}/topics` | Returns 7 topics and backend-computed track/topic/question progress | |
| 3 | Select a topic → `POST /api/v1/ml-technical/{user_id}/sessions` | Returns a `session_id` and a `questions` array (rubric hidden) | |
| 4 | Type an answer for the first question and `POST /api/v1/ml-technical/{user_id}/answers` | Returns a review with `score_percent`, `covered_points`, `missing_points`, `feedback` | |
| 5 | **Rubric is hidden** before submit | The session response (step 3) does NOT contain `rubric_points` or `reference_explanation_ru` | |
| 6 | **Provider failure → needs_review** | Kill the vLLM server, then submit an answer. Response should have `status: "needs_review"` with a `failure_reason` | |
| 7 | **Second attempt affects progress** | Finish or leave the first session, start a new session, then answer the same question again when it returns in the queue. `GET /api/v1/ml-technical/{user_id}/attempts` should show both attempts and progress should reflect the new state | |
| 8 | **Next question advances** | After a successful review, clicking "next" advances to a different question in the queue | |
| 9 | **Pass threshold** | After scoring >= 70% on a question, the question should appear as `passed` (no longer prioritized in queue) | |

---

## Known Constraints

- The full legacy `tests/` suite (540 passed, 6 skipped, 22 failed, 14 setup errors) is **not** green independently. Do not claim a fully green repository.
- No live `Telegram Mini App + PostgreSQL + Qwen` end-to-end smoke has been run before this dogfood. This runbook IS that first smoke.
- Rubric/reference text is hidden by `public_question_view()` in the session response — this is enforced in the question pack module.
- The reviewer (`ml_technical_reviewer.py`) is fail-closed: any LLM error, timeout, or schema violation produces `status: "needs_review"` with no score.
- Progress is stored in `LearningPlan.roadmap["ml_technical"]` as append-only JSONB (attempts, sessions, external_reviews are never mutated).
- `PASS_THRESHOLD_PERCENT = 70.0` — questions scoring >= 70% are considered passed.
- `REPETITION_DUE_DAYS = 3` — passed questions reappear after 3 days.

## Startup Values Requiring Owner Confirmation

| Variable | Current Value | Source |
|----------|--------------|--------|
| `VLLM_BASE_URL` | `http://192.168.0.18:8000/v1` | `.env` |
| `VLLM_API_KEY` | Confirm locally; do not record here | `.env` |
| `DATABASE_URL` | Must be aligned with the selected local Compose database | `.env` / `docker-compose.yml` |
| `VITE_API_URL` | `http://localhost:8000` | `frontend/.env` |
| PostgreSQL container name | `english_friend_postgres` | `docker-compose.yml` |
| PostgreSQL default password | `password` (docker) / `postgres` (DB user in `.env`) | `docker-compose.yml` / `.env` |
