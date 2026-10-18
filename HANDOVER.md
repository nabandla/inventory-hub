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
