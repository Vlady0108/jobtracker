# Job Tracker
FastAPI + SQLModel (SQLite) + Jinja2 + HTMX. No Node, no build step.

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --reload

App: http://127.0.0.1:8000  ·  API docs: http://127.0.0.1:8000/docs
Data lives in `jobs.db`. To use Postgres, change the `create_engine` URL.
