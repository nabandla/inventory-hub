# Inventory Hub - Handover (read this first in a new chat)

Last updated: 2026-10-18. No secrets in this file. Never put passwords here.

## Who / how to teach
- Learner is a data engineer (Databricks background) learning software engineering.
- Rules: don't write/edit code unless the user says "write it"; explain in plain language; give hints and ask them to predict first; review pasted code, don't rewrite it.
- Stack: Python/FastAPI, SQL Server (Azure SQL), React, GitHub Actions, Azure.
- Deadlines: Azure $200 credit expires **2026-11-12**; deploy lesson done by **2026-11-07**.

## Decisions
- Environments: **dev and prod only**, both on Azure SQL. No Docker / no local SQL Server. UAT skipped for now.
- **GitHub Actions CI/CD and automated deployment are required** (build/test on push, deploy dev then prod).
- Table-creation SQL must be kept as scripts in git (not clicked in the portal).

## Done
- Lesson 0: done.
- Lesson 1: FastAPI `/health` in `main.py`, run with `uvicorn main:app --reload`. Committed and pushed (github.com/nabandla/inventory-hub, commit 856db02). Tested via Swagger (/docs), curl, Postman.
- Lesson 2: Azure setup done.
  - Resource group `rg-inventory-hub` (Central India).
  - SQL server `sql-inventory-hub-nb01.database.windows.net`, SQL auth, admin login `nadmin` (password kept privately by the user).
  - Database `inventory-dev` on the free offer (serverless, auto-pause, overage billing disabled).
  - Firewall: Azure services allowed + user's laptop IP (may change; re-add if connection times out).
  - Connection verified in portal Query editor (`SELECT @@VERSION`).
  - Budget alert created ($20/month, 80% email).
- Windows PowerShell execution policy set to RemoteSigned (CurrentUser) so venv activation works.
- ODBC Driver 18 for SQL Server already installed. `pyodbc 5.3.0` installed in `.venv`.

## In progress: Lesson 3 (connect FastAPI to Azure SQL)
1. DONE: `pyodbc==5.3.0` installed and in `requirements.txt`.
2. DONE: `.env` (git-ignored; keys DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD, DB_DRIVER) and committed `.env.example` with fake values.
3. DONE: connection from Python to Azure SQL verified.
4. DONE: limited user `app_inventory` created in inventory-dev with db_datareader + db_datawriter only. `.env` now uses it. Verified CREATE TABLE is denied (error 262). `nadmin` is reserved for creating tables/running scripts, not the app.
5. DONE: `db/001_create_app_user.sql` saved (placeholder password) for reuse on prod.
6. DONE: `db.py` (get_connection + check_db, password wrapped in braces, connection always closed, errors logged server-side only) and `/health/db` in `main.py` (200 ok / 503 with safe message). Tested: success, wrong password, missing setting.
7. DONE: `db/002_create_items_table.sql` (run as nadmin in the portal on inventory-dev; id IDENTITY PK, unique sku, CHECK quantity>=0, UTC timestamps). Items API built in layers: `schemas.py` (validation), `repository.py` (all SQL, parameterized), `routers/items.py` (POST/GET/PUT/DELETE /items, 201/404/409/422/204), `db.get_db` (one connection per request), 503 handler for pyodbc errors in `main.py`.
   - Tests: 35 unit tests (fake in-memory repo, run in CI) + 4 integration tests marked `integration` (real dev DB; run locally with `pytest -m integration`; excluded by default via pytest.ini). Live-tested all endpoints against inventory-dev.
   - For prod: run `db/001` then `db/002` as nadmin on inventory-prod.
8. Pushed to GitHub (check `git status` for anything new).

## Lesson 4: GitHub Actions CI (built 2026-10-18)
- `.github/workflows/ci.yml`: on push/PR to main, ubuntu-latest, Python 3.14, installs unixodbc + `requirements-dev.txt`, runs `pytest -v`. Least-privilege `permissions: contents: read`, concurrency cancel, 10-min timeout, pip cache.
- `requirements.txt` = runtime deps; `requirements-dev.txt` = `-r requirements.txt` + pytest + httpx2 (test tools).
- `pytest.ini` (pythonpath=., testpaths=tests); `tests/test_health.py` (routes, DB faked via monkeypatch, 503 leaks nothing), `tests/test_db.py` (settings check, brace-escaped password, failure paths, connection closed). 9 tests pass locally and in a clean copy without `.env`.
- TODO (user): watch the first run in the GitHub Actions tab; if red, paste the log. Then break a test on purpose to see CI fail, and revert.
- Next: add branch protection on main requiring CI to pass (GitHub repo Settings), then items table (`db/002_...`) and endpoints, then CD to Azure.

## API-key auth (built 2026-10-19)
- `auth.py`: `require_api_key` dependency; header `X-API-Key`, constant-time compare, 401 for missing/wrong, **fails closed with 503 if server has no API_KEY**. Attached to the whole `/items` router. `/health` and `/health/db` stay open (Azure probes can't send keys).
- Dev key generated into local `.env` as `API_KEY` (never shown in chat; user keeps a copy in their password manager). `.env.example` has `API_KEY=change-me`. Generate a DIFFERENT key for prod: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- 52 unit tests + 4 integration tests pass; live-tested with and without key. Swagger `/docs` shows an Authorize button.
- Limits (known, accepted for now): one shared key per environment, no per-caller keys/hashing/rotation. For the React site with user logins plan Entra ID/OAuth tokens; never put the API key in browser code; will need CORS.
- Deferred by user: retry logic for serverless auto-pause (first request after idle can time out with error 258, `check_db`/`get_connection` should retry transient errors with backoff but never retry login failures).

## Hosting decision (2026-10-19)
- Chosen: **Azure App Service (Linux, Python)** for dev and prod (one plan can host both apps). Function App stays a possible later alternative (team uses them; FastAPI can run via AsgiFunctionApp). Known risk: ODBC Driver 18 may need installing on App Service. Use GitHub Actions + OIDC login for CD; dev auto-deploys, prod needs approval; smoke tests (/health, /health/db) after deploy; Postman environments dev/prod with `base_url` and `api_key`.
- Next: create App Service plan + dev app in portal (user), startup command, app settings (DB_* and API_KEY), manual deploy + Postman test, then CD, Key Vault, prod.

## Azure dev deployment (set up 2026-10-19)
- Web app `app-inventory-hub-dev-nb01` (Linux, Python 3.14, Free F1, plan asp-inventory-hub, Central India) in rg-inventory-hub. URL: https://app-inventory-hub-dev-nb01-bshrg6aueegke9bn.centralindia-01.azurewebsites.net
- App settings (portal): DB_SERVER, DB_NAME=inventory-dev, DB_USER=app_inventory (never nadmin), DB_PASSWORD, DB_DRIVER, API_KEY, SCM_DO_BUILD_DURING_DEPLOYMENT=true. Startup command: `python -m uvicorn main:app --host 0.0.0.0 --port 8000`.
- Deployment Center (OIDC) failed ("couldn't verify how GitHub Actions issues OIDC tokens"), so OIDC was set up manually: Entra app registration `github-inventory-hub-deploy` with federated credential `github-inventory-hub-dev` (subject uses IDs: `repo:nabandla@18088056/inventory-hub@1424283928:environment:dev`), role Website Contributor on the web app only. GitHub environment `dev` holds secrets AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_SUBSCRIPTION_ID.
- If the login step fails with "No matching federated identity record found", the error prints the real `sub` claim; edit the federated credential to match it.
- `.github/workflows/ci.yml` is now one pipeline: `test` -> `deploy-dev` (environment dev, OIDC login, zip deploy, smoke test of /health then /health/db with retries). PRs only run tests.
- Known risks: ODBC Driver 18 may be missing on App Service (symptom: /health ok, /health/db 503; check Log stream); Free F1 cold starts; DB auto-pause.
- RESULT (2026-10-19): dev deploy WORKS end to end. First attempts failed with `Site Disabled (403)` = Free F1 daily CPU quota exceeded (likely startup crash loop before code existed); fixed by scaling the plan to **Basic B1** (remember: costs money, scale down/delete after Nov 12; Always On enabled). Smoke test passed (/health 503 -> 000 -> 200 while the app started); /health/db and /items verified in Postman against the Azure URL.
- Dev local and dev Azure share the same `inventory-dev` database.
- PROD (set up 2026-10-19): database `inventory-prod` on the same SQL server (db/001 with a NEW generated password for prod `app_inventory`, then db/002); web app `app-inventory-hub-prod-nb01` on the same Basic plan with its own settings (DB_NAME=inventory-prod, prod DB_PASSWORD, prod API_KEY; the prod secrets live only in the user's password manager and Azure, not in `.env`). Federated credential `github-inventory-hub-prod` (environment `prod`), Website Contributor on the prod app, GitHub environment `prod` with required reviewer (the user), main-only, and the 3 secrets.
- Pipeline (`ci.yml`): `test` -> `package` (zip built once) -> `deploy-dev` (+ smoke test + 401 check) -> `deploy-prod` (waits for the user's approval, then the same package, smoke test, 401 check; read-only on purpose). PRs only run tests.
- Next (after prod pipeline verified): Key Vault, retry logic for DB auto-pause, then the React site (CORS + token auth). Postman: environments need a Postman sign-in; otherwise edit the URL by hand.
- (old plan) Postman with Azure URL (env `Dev Azure`), then Key Vault, prod (inventory-prod DB with db/001 + db/002, prod app, GitHub `prod` environment with required reviewers, new key).

## Prod approval gate (found broken 2026-10-19, fixed same day)
- The `prod` job once started 3 seconds after dev finished = Required reviewers was not saved on the GitHub `prod` environment. User then saved it (Settings > Environments > prod: Required reviewers = nabandla, Prevent self-review OFF, main only). Lesson: always prove a control blocks something; check the job shows "Waiting".

## Roadmap "the proper way" (decided 2026-10-19; user said to ignore the Nov 12 credit deadline)
Model: a DIFFERENT team will build the frontend in a SEPARATE repo (`inventory-hub-web`), so this API is a product with a contract.
- **Phase A (in progress): contract + CORS.** A1 DONE: items routes versioned under `/v1/items` (`/health`, `/health/db` stay unversioned; old `/items` now 404; tests in `tests/test_versioning.py`; pipeline 401 check uses `/v1/items`). A2 TODO: CORS allowed origins from a setting (custom header X-API-Key triggers OPTIONS preflight) + tests. A3 TODO: OpenAPI snapshot checked in + CI test that fails on breaking contract changes.
- **Phase B:** Microsoft Entra ID auth replaces the shared API key (API app registration with roles like Items.Read/Items.Write, SPA registration with MSAL auth-code+PKCE, JWT validation of signature/iss/aud/exp/roles, client-credentials for other servers).
- **Phase C:** frontend repo (React/Vite, MSAL, Vitest, Playwright, Azure Static Web Apps, own pipeline); develop locally against dev first.
- **Phase D:** passwordless DB via App Service managed identity (`CREATE USER ... FROM EXTERNAL PROVIDER`), remove DB_PASSWORD, migrations run by the pipeline (Alembic/Flyway).
- **Phase E:** Application Insights + alerts, deployment slots, DB retry/backoff + pooling (deferred earlier).
- **Phase F:** Bicep/Terraform IaC, private endpoints/VNet, Azure API Management. These cost money.
- Frontend interim idea if a deployed dev frontend is wanted before Phase B: Static Web Apps behind login with the dev key only. Never for prod.

## Secrets plan (decided 2026-10-18)
- Local dev: `.env` (git-ignored). GitHub Actions: GitHub Secrets. Deployed Azure App Service (dev and prod): **Azure Key Vault + managed identity** (Key Vault references in app settings, so `db.py` keeps reading env vars). Do this in the deploy lesson, not before.

## Notes for later
- FastAPI `TestClient` needs the extra package `httpx2` (add to requirements when writing tests in the CI lesson).
- `check_db()` opens a new connection per call; consider pooling/probe frequency later.

## Upcoming lessons
- Lesson 4: GitHub Actions CI (install deps, run tests on every push; secrets in GitHub secrets).
- Lesson 5: CD to Azure App Service (dev then prod); second DB `inventory-prod` may not be free - check the free-offer limit.
- Lesson 6: React frontend.

## Open teaching questions (user has not answered yet)
- Why several uvicorn workers in production and why no `--reload`?
- Why pin versions in requirements.txt?
- What does POST to /health return (405)?
- Why Azure-services firewall rule vs laptop-IP rule?
