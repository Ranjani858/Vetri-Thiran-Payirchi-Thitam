from datetime import date
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
)

from fastapi.middleware.cors import (
    CORSMiddleware
)

from fastapi.responses import (
    FileResponse
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import (
    chat,
    generate_insight,
)

from .config import (
    get_settings
)

from .database import (
    get_db,
    init_db,
)

from .models import (
    Budget,
    Transaction,
)

from .schemas import (
    BudgetCreate,
    BudgetOut,
    ChatRequest,
    InsightRequest,
    TransactionCreate,
    TransactionOut,
)

from .services import (
    get_month_context,
)


settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=
        settings.cors_list,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


FRONTEND = (
    Path(__file__)
    .resolve()
    .parents[2]
    / "frontend"
)


@app.on_event("startup")
def startup():

    init_db()


@app.get(
    "/",
    include_in_schema=False,
)
def root():

    return FileResponse(
        FRONTEND / "index.html"
    )


@app.get(
    "/styles.css",
    include_in_schema=False,
)
def styles():

    return FileResponse(
        FRONTEND / "styles.css",
        media_type="text/css",
    )


@app.get(
    "/app.js",
    include_in_schema=False,
)
def javascript():

    return FileResponse(
        FRONTEND / "app.js",
        media_type="application/javascript",
    )


@app.get("/api/health")
def health():

    return {
        "status": "ok",

        "app":
            settings.app_name,

        "ai_configured":
            bool(
                settings.openai_api_key
            ),
    }


@app.get(
    "/api/transactions",
    response_model=list[TransactionOut],
)
def list_transactions(

    month: str | None =
        Query(
            default=None,
            pattern=r"^\d{4}-\d{2}$",
        ),

    db: Session =
        Depends(get_db),
):

    statement = (
        select(Transaction)
        .order_by(
            Transaction.transaction_date.desc(),
            Transaction.id.desc(),
        )
    )

    if month:

        start = date.fromisoformat(
            month + "-01"
        )

        if start.month == 12:

            end = date(
                start.year + 1,
                1,
                1,
            )

        else:

            end = date(
                start.year,
                start.month + 1,
                1,
            )

        statement = statement.where(
            Transaction.transaction_date >= start,
            Transaction.transaction_date < end,
        )

    return db.scalars(
        statement
    ).all()


@app.post(
    "/api/transactions",
    response_model=TransactionOut,
    status_code=201,
)
def create_transaction(

    payload: TransactionCreate,

    db: Session =
        Depends(get_db),
):

    item = Transaction(
        **payload.model_dump()
    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return item


@app.delete(
    "/api/transactions/{transaction_id}"
)
def delete_transaction(

    transaction_id: int,

    db: Session =
        Depends(get_db),
):

    item = db.get(
        Transaction,
        transaction_id,
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    db.delete(item)

    db.commit()

    return {
        "deleted":
            transaction_id
    }


@app.get(
    "/api/budgets",
    response_model=list[BudgetOut],
)
def list_budgets(

    month: str | None =
        Query(
            default=None,
            pattern=r"^\d{4}-\d{2}$",
        ),

    db: Session =
        Depends(get_db),
):

    statement = (
        select(Budget)
        .order_by(
            Budget.month.desc(),
            Budget.category,
        )
    )

    if month:

        statement = statement.where(
            Budget.month == month
        )

    return db.scalars(
        statement
    ).all()


@app.post(
    "/api/budgets",
    response_model=BudgetOut,
    status_code=201,
)
def create_budget(

    payload: BudgetCreate,

    db: Session =
        Depends(get_db),
):

    existing = db.scalar(
        select(Budget)
        .where(
            Budget.month == payload.month,
            Budget.category == payload.category,
        )
    )

    if existing:

        existing.limit_amount = (
            payload.limit_amount
        )

        db.commit()

        db.refresh(existing)

        return existing

    item = Budget(
        **payload.model_dump()
    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return item


@app.delete(
    "/api/budgets/{budget_id}"
)
def delete_budget(

    budget_id: int,

    db: Session =
        Depends(get_db),
):

    item = db.get(
        Budget,
        budget_id,
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    db.delete(item)

    db.commit()

    return {
        "deleted":
            budget_id
    }


@app.get("/api/dashboard")
def dashboard(

    month: str =
        Query(
            ...,
            pattern=r"^\d{4}-\d{2}$",
        ),

    db: Session =
        Depends(get_db),
):

    return get_month_context(
        db,
        month,
    )


@app.post("/api/insights")
def insights(

    payload: InsightRequest,

    db: Session =
        Depends(get_db),
):

    context = get_month_context(
        db,
        payload.month,
    )

    return generate_insight(
        context
    )


@app.post("/api/chat")
def assistant_chat(

    payload: ChatRequest,

    db: Session =
        Depends(get_db),
):

    context = get_month_context(
        db,
        payload.month,
    )

    return chat(
        context,
        payload.message,
    )