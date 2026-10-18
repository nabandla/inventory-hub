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
6. TODO: `/health/db` endpoint that really checks the database (return 503 if unreachable).
7. TODO: DB schema scripts (`db/002_...`) run as nadmin, e.g. items table.
8. TODO: push to GitHub (commits may still be local; check `git status`).

## Upcoming lessons
- Lesson 4: GitHub Actions CI (install deps, run tests on every push; secrets in GitHub secrets).
- Lesson 5: CD to Azure App Service (dev then prod); second DB `inventory-prod` may not be free - check the free-offer limit.
- Lesson 6: React frontend.

## Open teaching questions (user has not answered yet)
- Why several uvicorn workers in production and why no `--reload`?
- Why pin versions in requirements.txt?
- What does POST to /health return (405)?
- Why Azure-services firewall rule vs laptop-IP rule?
