"""Job application tracker: FastAPI + SQLModel (SQLite) + Jinja2 + HTMX."""
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

STATUSES = ["Wishlist", "Applied", "Interview", "Offer", "Rejected"]
FOLLOW_UP_AFTER_DAYS = 14


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company: str
    role: str
    status: str = "Applied"
    location: str = ""
    link: str = ""
    notes: str = ""
    applied_on: date = Field(default_factory=date.today)


engine = create_engine("sqlite:///jobs.db", connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Job Tracker", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


def list_context(session: Session, q: str = "", filter: str = "") -> dict:
    stmt = select(Application).order_by(
        col(Application.applied_on).desc(), col(Application.id).desc()
    )
    if filter in STATUSES:
        stmt = stmt.where(Application.status == filter)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            col(Application.company).ilike(like) | col(Application.role).ilike(like)
        )
    counts = Counter(session.exec(select(Application.status)).all())
    return {
        "apps": session.exec(stmt).all(),
        "counts": counts,
        "total": sum(counts.values()),
        "statuses": STATUSES,
        "filter": filter if filter in STATUSES else "",
        "q": q,
        "today": date.today(),
        "stale_days": FOLLOW_UP_AFTER_DAYS,
    }


def render_list(request: Request, session: Session, q: str, filter: str):
    return templates.TemplateResponse(
        request, "_list.html", list_context(session, q, filter)
    )


# ---------- HTML (HTMX) routes ----------
@app.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    ctx = list_context(session)
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/applications")
def list_applications(
    request: Request,
    q: str = "",
    filter: str = "",
    session: Session = Depends(get_session),
):
    return render_list(request, session, q, filter)


@app.post("/applications")
def create_application(
    request: Request,
    company: str = Form(...),
    role: str = Form(...),
    status: str = Form("Applied"),
    location: str = Form(""),
    link: str = Form(""),
    notes: str = Form(""),
    applied_on: str = Form(""),
    session: Session = Depends(get_session),
):
    if status not in STATUSES:
        raise HTTPException(422, "Unknown status")
    session.add(
        Application(
            company=company.strip(),
            role=role.strip(),
            status=status,
            location=location.strip(),
            link=link.strip(),
            notes=notes.strip(),
            applied_on=date.fromisoformat(applied_on) if applied_on else date.today(),
        )
    )
    session.commit()
    return render_list(request, session, "", "")


@app.post("/applications/{app_id}/status")
def update_status(
    app_id: int,
    request: Request,
    status: str = Form(...),
    q: str = Form(""),
    filter: str = Form(""),
    session: Session = Depends(get_session),
):
    item = session.get(Application, app_id)
    if not item or status not in STATUSES:
        raise HTTPException(404)
    item.status = status
    session.add(item)
    session.commit()
    return render_list(request, session, q, filter)


@app.post("/applications/{app_id}/delete")
def delete_application(
    app_id: int,
    request: Request,
    q: str = Form(""),
    filter: str = Form(""),
    session: Session = Depends(get_session),
):
    item = session.get(Application, app_id)
    if item:
        session.delete(item)
        session.commit()
    return render_list(request, session, q, filter)


# ---------- JSON API (see /docs) ----------
@app.get("/api/applications", response_model=list[Application])
def api_list(
    status: Optional[str] = Query(None), session: Session = Depends(get_session)
):
    stmt = select(Application).order_by(col(Application.applied_on).desc())
    if status:
        stmt = stmt.where(Application.status == status)
    return session.exec(stmt).all()


@app.post("/api/applications", response_model=Application, status_code=201)
def api_create(item: Application, session: Session = Depends(get_session)):
    item.id = None
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
