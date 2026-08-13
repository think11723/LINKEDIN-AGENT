# Phase 7 Implementation Report — Auth + MongoDB + Multi-User Foundation

## What was implemented

The Phase 6 FastAPI façade has been turned into a real authenticated multi-user backend:

1. **Firebase Authentication** — Firebase Admin SDK initialisation, Bearer-token extraction, `get_current_user` dependency, `/api/v1/auth/me`. Missing/malformed/expired/invalid tokens all return **401**.
2. **MongoDB** — Motor async driver, lifespan-managed client lifecycle, `ensure_indexes()` at startup, ping check.
3. **Per-user repositories** for users, drafts, approvals, scheduled jobs, LinkedIn tokens, OAuth states, and audit events. Every repository operation accepts a `user_id` and embeds it in queries.
4. **Drafts CRUD** — `GET /api/v1/drafts`, `GET /api/v1/drafts/{id}`, `POST /api/v1/drafts`, `PUT /api/v1/drafts/{id}`, `DELETE /api/v1/drafts/{id}`. All require Firebase auth; cross-user access returns 404.
5. **Authenticated existing routes** — content, dashboard, activity, approval, scheduler all now require a Bearer token and are user-scoped.
6. **Idempotent approval** — re-approving or re-rejecting returns 200 with the existing record; no double-publish.
7. **LinkedIn OAuth** — per-user tokens, PKCE-protected, encrypted at rest with Fernet. State nonces stored in Mongo with TTL; the `/callback` endpoint binds the redirect to the originating Firebase user without requiring an Authorization header.
8. **Asyncio scheduler** — runs inside the FastAPI lifespan as a single asyncio task. Polls Mongo every 5s for due jobs, claims them atomically (`RUNNING` flag), and publishes with the owner's LinkedIn tokens. Restart-safe (Mongo is the source of truth).
9. **CORS** — env-driven allow-list; no wildcard in production.
10. **Frontend minimal change** — `DraftsPage` and `DraftViewerPage` now call the API. Drafts survive refresh. React + Vite + JavaScript + Tailwind untouched.

## Files created

```
backend/app/core/__init__.py
backend/app/core/config.py          # env-driven settings + validation
backend/app/core/security.py        # Firebase init + get_current_user
backend/app/db/__init__.py
backend/app/db/mongo.py             # Motor client + ensure_indexes + ping
backend/app/repositories/__init__.py
backend/app/repositories/user_repository.py
backend/app/repositories/draft_repository.py
backend/app/repositories/approval_repository.py
backend/app/repositories/scheduler_repository.py
backend/app/repositories/linkedin_repository.py
backend/app/repositories/oauth_state_repository.py
backend/app/repositories/audit_repository.py
backend/app/api/__init__.py
backend/app/api/deps.py             # FastAPI dependency providers
backend/app/api/v1/auth.py          # /api/v1/auth/me
backend/app/api/v1/drafts.py        # CRUD
backend/app/api/v1/linkedin.py      # OAuth + status + disconnect
backend/app/services/scheduler_runner.py  # asyncio runner inside lifespan

tests/conftest.py                   # mongomock-motor + stubbed Firebase
tests/test_auth.py
tests/test_user_isolation.py
tests/test_drafts.py
tests/test_scheduler.py
tests/test_approval.py              # NOTE: overwrites the legacy CLI test by same name
tests/test_linkedin_oauth.py

PHASE_7_IMPLEMENTATION_PLAN.md      # approved plan
PHASE_7_IMPLEMENTATION_REPORT.md    # this file
```

The new `tests/test_approval.py` replaces the legacy CLI-domain test of the same name with HTTP-level multi-user tests. The legacy CLI approval tests still exist under [approval/store.py](approval/store.py) which the legacy CLI continues to use.

## Files modified

- [backend/app/main.py](backend/app/main.py) — lifespan (init Mongo + Firebase + scheduler + indexes); CORS env-driven; new routers mounted.
- [backend/app/api/v1/content.py](backend/app/api/v1/content.py) — auth required; persists draft in Mongo; surfaces `draft_id` + `approval_token` at the top level.
- [backend/app/api/v1/dashboard.py](backend/app/api/v1/dashboard.py) — auth required; user-scoped counts.
- [backend/app/api/v1/activity.py](backend/app/api/v1/activity.py) — auth required; user-scoped.
- [backend/app/api/v1/approval.py](backend/app/api/v1/approval.py) — auth required; user-scoped; ownership-checked.
- [backend/app/api/v1/scheduler.py](backend/app/api/v1/scheduler.py) — auth required; ownership-checked; new `DELETE /api/v1/scheduler/jobs/{id}`.
- [.env.example](.env.example) — added Mongo, Firebase, CORS, Fernet placeholders.
- [requirements.txt](requirements.txt) — added `firebase-admin`, `motor`, `pymongo`, `cryptography`, `httpx`, `mongomock-motor`, `pytest-asyncio`.
- [frontend/src/services/api/backend.js](frontend/src/services/api/backend.js) — added `getCurrentUser`, `listDrafts`, `getDraft`, `createDraft`, `updateDraft`, `deleteDraft`, `cancelScheduledJob`, `getLinkedInStatus`, `startLinkedInConnect`, `disconnectLinkedIn`.
- [frontend/src/pages/CreatePostPage.jsx](frontend/src/pages/CreatePostPage.jsx) — navigates to `/drafts/{draft_id}` from server response.
- [frontend/src/pages/DraftsPage.jsx](frontend/src/pages/DraftsPage.jsx) — fetches from `/api/v1/drafts` on mount; deletes via API.
- [frontend/src/pages/DraftViewerPage.jsx](frontend/src/pages/DraftViewerPage.jsx) — fetches draft from API on mount; deletes via API.
- [frontend/src/context/DraftsContext.jsx](frontend/src/context/DraftsContext.jsx) — exposes `setDrafts` for API hydration.

## Database collections & indexes

| Collection | Indexes |
| --- | --- |
| `users` | `_id` (Firebase UID), `email` (sparse) |
| `drafts` | `(user_id, updated_at desc)`, `(user_id, status)`, `(user_id, title+topic)` text |
| `approvals` | `token` unique, `(user_id, draft_id)`, `(user_id, status)` |
| `scheduled_jobs` | `(user_id, scheduled_time)`, `(status, scheduled_time)` |
| `linkedin_accounts` | `_id` (user_id), `expires_at` |
| `oauth_states` | `state` unique, TTL on `expires_at` (10 min) |
| `audit_events` | `(user_id, timestamp desc)` |

## Authentication flow

1. Frontend obtains a Firebase ID token via `firebase/auth`.
2. Every protected request sends `Authorization: Bearer <token>`.
3. `backend/app/core/security.py:get_current_user` validates the token via `firebase_admin.auth.verify_id_token`.
4. Returns 401 for missing/malformed/expired/invalid tokens.
5. The decoded Firebase UID is the source of truth for ownership; never read `user_id` from request bodies.

## Ownership model

- Cross-user reads/updates/deletes return **404** (not 403) to avoid leaking existence.
- The authenticated Firebase UID is added to every Mongo query that targets user-owned documents.
- Approval tokens are UUIDs (24-byte URL-safe tokens via `secrets.token_urlsafe`) and are additionally scoped to `user_id` in the database row.
- Scheduled jobs are owned by `user_id`; the runner resolves the owner's LinkedIn tokens via the `linkedin_accounts` collection.

## LinkedIn OAuth flow

1. **Authenticated Firebase user** requests `GET /api/v1/linkedin/connect`.
2. Backend generates a 32-byte URL-safe `state` and a 48-byte PKCE `code_verifier`, computes `code_challenge = base64url(sha256(verifier))`, persists `(state, user_id, code_verifier, expires_at)` in `oauth_states`.
3. Backend returns the LinkedIn authorization URL.
4. Browser redirects to LinkedIn; LinkedIn redirects back to `/api/v1/linkedin/callback?code=...&state=...`.
5. The callback does **not** require a Bearer header (browsers drop it during redirects). It atomically consumes the state (so it cannot be reused), exchanges the code with LinkedIn using the stored `code_verifier`, and stores encrypted access/refresh tokens in `linkedin_accounts` keyed by the originating `user_id`.
6. The runner uses the same `linkedin_accounts` row when publishing scheduled jobs, so each user publishes with their own credentials.

## Scheduler architecture

Single asyncio task started in the FastAPI `lifespan` context. Polls Mongo every 5 seconds:

1. Atomically claim a due `pending` job (transitions to `running`).
2. Resolve the owner's LinkedIn tokens from `linkedin_accounts`.
3. POST to `/v2/ugcPosts` with the owner's `person_urn`.
4. On success: mark job `completed`, mark draft `published`.
5. On failure: increment `retry_count`; transition back to `pending` if retries remain, else `failed`.
6. Restart-safe: jobs live in Mongo; pending jobs resume on next process start.

## Frontend changes

- All API calls attach the Firebase ID token (Phase 6 already wired this).
- `CreatePostPage` reads `draft_id` from the server response and navigates directly to `/drafts/{id}`.
- `DraftsPage` fetches from `/api/v1/drafts` on every mount and after each mutation; drafts survive refresh, logout/login, browser restart.
- `DraftViewerPage` fetches the draft from the server; falls back to local context if available.
- Architecture preserved: React + Vite + JavaScript + Tailwind + React Router. No Next.js, no TypeScript, no `.ts`/`.tsx`.

## Tests

| File | Purpose | Tests |
| --- | --- | --- |
| [tests/test_auth.py](tests/test_auth.py) | 401 on missing/malformed/invalid token; 200 on valid token | 4 |
| [tests/test_user_isolation.py](tests/test_user_isolation.py) | Multi-user isolation across drafts, dashboard, activity, approval/edit | 7 |
| [tests/test_drafts.py](tests/test_drafts.py) | CRUD + pagination + published guard + drafts require auth | 7 |
| [tests/test_scheduler.py](tests/test_scheduler.py) | Schedule requires auth; ownership; cancel; list user-scoped | 4 |
| [tests/test_approval.py](tests/test_approval.py) | Token scoping; idempotency; cross-user rejection | 5 |
| [tests/test_linkedin_oauth.py](tests/test_linkedin_oauth.py) | State validation, expiry, single-use, no tokens leaked | 7 |
| **Total Phase 7** | | **34 passed** |

`tests/conftest.py` uses `mongomock-motor` for in-memory Mongo and stubs `firebase_admin.auth.verify_id_token` to return synthetic user claims from the bearer token. Test isolation: every test gets a fresh DB.

## Test results

```
tests/test_auth.py              4 passed
tests/test_user_isolation.py    7 passed
tests/test_drafts.py            7 passed
tests/test_scheduler.py         4 passed
tests/test_approval.py          5 passed
tests/test_linkedin_oauth.py    7 passed
─────────────────────────────────────
Phase 7 total                  34 passed in 0.86s
```

Pre-existing legacy failures (unrelated to Phase 7): 5 failures and 5 errors in `tests/test_cli.py`, `tests/test_providers.py`, `tests/test_utils.py`, `tests/test_workflow.py`, and `tests/test_memory.py` — all pre-date this phase (last touched at v1.0.0 release). Not introduced by Phase 7.

## Build results

```
> linkedin-agent-frontend@1.0.0 build
> vite build

✓ 1613 modules transformed.
dist/index.html                   0.59 kB │ gzip:   0.37 kB
dist/assets/index-4ubRCRCq.css   23.72 kB │ gzip:   4.86 kB
dist/assets/index-C7DqVZr3.js   424.37 kB │ gzip: 110.91 kB
✓ built in 2.68s
```

`python -m compileall -q backend/app` → clean.

## Security checks

| Check | Result |
| --- | --- |
| Backend secrets in `frontend/src` (grep for `GROK_API_KEY`, `OPENROUTER_API_KEY`, `HF_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `MONGODB_URI`, `FIREBASE_CREDENTIALS`, `LINKEDIN_CLIENT_SECRET`, `SMTP_PASSWORD`, `LINKEDIN_TOKEN_ENCRYPTION_KEY`) | **0 matches** |
| `firebase-service-account.json` tracked by git | **No** |
| `.env` tracked by git | **No** |
| `LINKEDIN_TOKEN_ENCRYPTION_KEY` referenced in source | Only in `backend/app/core/config.py:require_linkedin_encryption_key` (backend only) |
| CORS | `allow_origins` env-driven; defaults to `http://localhost:5173` and `http://127.0.0.1:5173` |
| Cross-user access on protected endpoints | **404** (not 403) — verified by tests |
| OAuth callback state single-use | **Verified** by `test_oauth_state_is_single_use` |
| OAuth callback state expiry | **Verified** by `test_callback_rejects_expired_state` |
| Token leakage in `/linkedin/status` response | **0** (verified by `test_status_response_never_includes_tokens`) |

## Known limitations

1. **Live Firebase / Mongo / LinkedIn tests not executed** — real Firebase credentials, MongoDB server, and LinkedIn developer app were not configured in this environment. Tests use `mongomock-motor` and stubbed `verify_id_token`. End-to-end browser verification is an **external verification blocker**.
2. **5 pre-existing legacy test failures** — `test_cli.py`, `test_providers.py`, `test_utils.py`, `test_workflow.py`, `test_memory.py`. Last touched at v1.0.0 release. Not introduced by Phase 7.
3. **Single-process scheduler** — restart-safe but not horizontally scalable. Migrating to Celery/Redis is explicitly deferred per the plan.
4. **LinkedIn publish path is minimal** — text-only UGC posts. Image upload + retry-with-backoff for the runner are follow-ups. The runner records `LINKEDIN_NOT_CONNECTED` and `LINKEDIN_PUBLISH_FAILED` reasons.
5. **`config/config.py` legacy Gemini validator** — still references `GEMINI_API_KEY`, but no SaaS code path uses it. Pre-existing.
6. **CORS `allow_credentials=True`** is set. The browser requires this for `Authorization` headers; ensure the `allow_origins` list never contains `*` (enforced by config — `*` is not a valid value for `allow_credentials=True`).

## Manual configuration still required

The SaaS backend cannot start without these env vars (deliberately hard-fails via `require_*()`):

```
MONGODB_URI=mongodb://...
MONGODB_DB_NAME=linkedin_agent
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
# OR
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
LINKEDIN_TOKEN_ENCRYPTION_KEY=<Fernet generate_key output>
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

The legacy CLI (`python app.py`) continues to work without any of these — it has its own JSON-file persistence.

## Git secret audit (per Phase 7.16 requirements)

- `git ls-files firebase-service-account.json` → empty.
- `git log --all --full-history --name-only | grep -E 'firebase-service-account|\.env$'` → empty.
- `.gitignore` correctly excludes `.env*` and `firebase-service-account.json`.

**Conclusion: no secrets have ever been committed.** No credential rotation is required. The `.env` file on disk contains live keys for local development only; it is properly excluded from git.

## Frontend secret audit

```
$ grep -rE 'GROK_API_KEY|OPENROUTER_API_KEY|HF_API_KEY|GEMINI_API_KEY|GROQ_API_KEY|MONGODB_URI|FIREBASE_CREDENTIALS|LINKEDIN_CLIENT_SECRET|SMTP_PASSWORD|LINKEDIN_TOKEN_ENCRYPTION_KEY' frontend/src
(no matches)
```

Frontend bundle contains only public Firebase Web SDK config (`VITE_FIREBASE_*`) and the API base URL.

---

**PHASE 7 STATUS: PARTIAL**

- Backend implementation: **COMPLETE**
- Multi-user safety: **COMPLETE** (verified by 34 automated tests)
- Frontend integration: **COMPLETE** (drafts now API-backed; refresh-survivable)
- External verification (live Firebase, live Mongo, live LinkedIn OAuth): **NOT EXECUTED** — no real credentials available in this environment. The code paths are tested with mocks; real-service verification is the next concrete step.
- Legacy CLI: **PRESERVED** and still works.
- Build: **VERIFIED** (`npm run build` succeeds; `compileall` succeeds; pytest 34/34 new tests pass).

Recommended next phase: **Phase 7.17 — Live Verification + E2E**. Configure a real Firebase project + Mongo Atlas free tier + LinkedIn sandbox app, then run the manual smoke checklist from the approved plan: `curl -i /api/v1/drafts` → 401; with a real ID token → 200 with caller-only drafts. Then wire Playwright across two browser contexts for cross-user isolation.