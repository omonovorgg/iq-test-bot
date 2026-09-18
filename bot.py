import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "10000"))

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PRICE_UZS = int(os.getenv("PRICE_UZS", "15000"))

BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL environment variable is required")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("iq-test")


# ============================================================
# CONSTANTS
# ============================================================

QUESTION_COUNT = 16
TIME_LIMIT_SECONDS = 8 * 60

MIN_IQ = 70
MAX_IQ = 178

FREE_ATTEMPT = True


# Difficulty weights.
WEIGHTS = [
    5,
    5,
    7,
    7,
    9,
    9,
    11,
    11,
    13,
    13,
    15,
    15,
    17,
    17,
    19,
    23,
]

MAX_RAW = sum(WEIGHTS)


# ============================================================
# QUESTION BANK
#
# IMPORTANT:
# correct answer is NEVER returned to the frontend.
# ============================================================

QUESTIONS = [
    {
        "id": "Q01",
        "difficulty": 1,
        "category": "Pattern",
        "text": "2, 4, 6, 8, ?",
        "options": ["9", "10", "11", "12"],
        "correct": 1,
    },
    {
        "id": "Q02",
        "difficulty": 1,
        "category": "Pattern",
        "text": "A, C, E, G, ?",
        "options": ["H", "I", "J", "K"],
        "correct": 1,
    },
    {
        "id": "Q03",
        "difficulty": 2,
        "category": "Number",
        "text": "3, 6, 12, 24, ?",
        "options": ["36", "42", "48", "54"],
        "correct": 2,
    },
    {
        "id": "Q04",
        "difficulty": 2,
        "category": "Number",
        "text": "20, 17, 14, 11, ?",
        "options": ["8", "9", "7", "6"],
        "correct": 0,
    },
    {
        "id": "Q05",
        "difficulty": 3,
        "category": "Logic",
        "text": "Qaysi son boshqalardan farq qiladi?",
        "options": ["16", "25", "36", "45"],
        "correct": 3,
    },
    {
        "id": "Q06",
        "difficulty": 3,
        "category": "Pattern",
        "text": "1, 4, 9, 16, ?",
        "options": ["20", "24", "25", "27"],
        "correct": 2,
    },
    {
        "id": "Q07",
        "difficulty": 4,
        "category": "Logic",
        "text": "Agar barcha ZOR lar LUM bo‘lsa va barcha LUM lar KEN bo‘lsa, ZOR lar nima?",
        "options": ["KEN", "LUM emas", "ZOR emas", "Aniqlab bo‘lmaydi"],
        "correct": 0,
    },
    {
        "id": "Q08",
        "difficulty": 4,
        "category": "Number",
        "text": "2, 3, 5, 8, 12, ?",
        "options": ["15", "16", "17", "18"],
        "correct": 2,
    },
    {
        "id": "Q09",
        "difficulty": 5,
        "category": "Pattern",
        "text": "81, 27, 9, 3, ?",
        "options": ["0", "1", "2", "6"],
        "correct": 1,
    },
    {
        "id": "Q10",
        "difficulty": 5,
        "category": "Logic",
        "text": "5 ta mashina 5 daqiqada 5 ta detal ishlab chiqaradi. 100 ta mashina 100 ta detalni qancha vaqtda ishlab chiqaradi?",
        "options": ["5 daqiqa", "20 daqiqa", "100 daqiqa", "500 daqiqa"],
        "correct": 0,
    },
    {
        "id": "Q11",
        "difficulty": 6,
        "category": "Number",
        "text": "4, 7, 13, 25, 49, ?",
        "options": ["73", "81", "97", "101"],
        "correct": 2,
    },
    {
        "id": "Q12",
        "difficulty": 6,
        "category": "Logic",
        "text": "Bir qatorida 3 ta qora va 2 ta oq katak bor. Har bir qora katakdan keyin oq katak kelishi shart. Nechta tartib mumkin?",
        "options": ["3", "4", "5", "6"],
        "correct": 0,
    },
    {
        "id": "Q13",
        "difficulty": 7,
        "category": "Pattern",
        "text": "1, 2, 6, 24, 120, ?",
        "options": ["240", "360", "600", "720"],
        "correct": 3,
    },
    {
        "id": "Q14",
        "difficulty": 7,
        "category": "Logic",
        "text": "A > B. B > C. D > A. Qaysi biri eng katta?",
        "options": ["A", "B", "C", "D"],
        "correct": 3,
    },
    {
        "id": "Q15",
        "difficulty": 8,
        "category": "Number",
        "text": "2, 6, 12, 20, 30, ?",
        "options": ["36", "40", "42", "44"],
        "correct": 2,
    },
    {
        "id": "Q16",
        "difficulty": 8,
        "category": "Logic",
        "text": "Bir sonning 3 baravari undan 18 ga katta. Bu son nechchi?",
        "options": ["6", "8", "9", "12"],
        "correct": 0,
    },
]


# ============================================================
# VALIDATION
# ============================================================

if len(QUESTIONS) != QUESTION_COUNT:
    raise RuntimeError(
        f"Question count error: expected {QUESTION_COUNT}, "
        f"got {len(QUESTIONS)}"
    )

if len(WEIGHTS) != QUESTION_COUNT:
    raise RuntimeError("Weights count does not match question count")

for q in QUESTIONS:
    if len(q["options"]) != 4:
        raise RuntimeError(f"{q['id']} must have exactly 4 options")

    if not 0 <= q["correct"] < 4:
        raise RuntimeError(f"Invalid correct answer in {q['id']}")


# ============================================================
# GLOBALS
# ============================================================

pool: Optional[asyncpg.Pool] = None
bot: Optional[Bot] = None
dp = Dispatcher()


# ============================================================
# TIME
# ============================================================

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# QUESTION SERIALIZATION
# ============================================================

def public_questions() -> list[dict[str, Any]]:
    """
    Never expose correct answers.
    """
    return [
        {
            "id": q["id"],
            "difficulty": q["difficulty"],
            "category": q["category"],
            "text": q["text"],
            "options": q["options"],
        }
        for q in QUESTIONS
    ]


# ============================================================
# IQ SCORING
# ============================================================

def calculate_iq(raw_score: int) -> int:
    """
    Product score mapped into requested 70–178 range.

    This is NOT a standardized clinical IQ scale.
    """
    raw_score = max(0, min(MAX_RAW, raw_score))

    value = MIN_IQ + (
        raw_score / MAX_RAW
    ) * (MAX_IQ - MIN_IQ)

    return max(
        MIN_IQ,
        min(MAX_IQ, int(round(value))),
    )


# ============================================================
# TELEGRAM WEBAPP AUTH
# ============================================================

def validate_telegram_init_data(
    init_data: str,
) -> Optional[dict[str, Any]]:
    """
    Validate Telegram WebApp initData using HMAC.

    Returns parsed user data or None.
    """

    if not init_data:
        return None

    try:
        pairs = {}

        for item in init_data.split("&"):
            if "=" not in item:
                continue

            key, value = item.split("=", 1)

            from urllib.parse import unquote

            pairs[key] = unquote(value)

        received_hash = pairs.pop("hash", None)

        if not received_hash:
            return None

        auth_date = pairs.get("auth_date")

        if not auth_date:
            return None

        try:
            auth_time = int(auth_date)
        except ValueError:
            return None

        # Telegram auth data should not be ancient.
        if abs(int(time.time()) - auth_time) > 86400:
            return None

        data_check_string = "\n".join(
            f"{key}={pairs[key]}"
            for key in sorted(pairs)
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash,
        ):
            return None

        user_raw = pairs.get("user")

        if not user_raw:
            return None

        user = json.loads(user_raw)

        if not user.get("id"):
            return None

        return {
            "telegram_id": int(user["id"]),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        }

    except Exception:
        logger.exception("Telegram initData validation failed")
        return None


async def get_webapp_user(
    init_data: str,
) -> dict[str, Any]:
    user = validate_telegram_init_data(init_data)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="INVALID_TELEGRAM_DATA",
        )

    return user


# ============================================================
# DATABASE
# ============================================================

async def init_db() -> None:
    global pool

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )

    async with pool.acquire() as conn:

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id UUID PRIMARY KEY,
                telegram_id BIGINT NOT NULL
                    REFERENCES users(telegram_id)
                    ON DELETE CASCADE,

                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ,

                elapsed_seconds INTEGER NOT NULL DEFAULT 0,

                answers JSONB,
                raw_score INTEGER,
                correct_count INTEGER,
                iq_score INTEGER,

                status TEXT NOT NULL DEFAULT 'active',

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attempts_user
            ON attempts(telegram_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_attempts_ranking
            ON attempts(iq_score DESC)
            WHERE status='finished'
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id UUID PRIMARY KEY,

                telegram_id BIGINT NOT NULL
                    REFERENCES users(telegram_id)
                    ON DELETE CASCADE,

                amount INTEGER NOT NULL,

                purpose TEXT NOT NULL DEFAULT 'retest',

                status TEXT NOT NULL DEFAULT 'pending',

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                decided_at TIMESTAMPTZ,

                admin_id BIGINT
            )
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_payments_user
            ON payments(telegram_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_payments_status
            ON payments(status)
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_cards (
                id BIGSERIAL PRIMARY KEY,

                title TEXT NOT NULL,
                card_number TEXT NOT NULL,

                owner_name TEXT,

                active BOOLEAN NOT NULL DEFAULT TRUE,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    logger.info("Database initialized")


# ============================================================
# USER UPSERT
# ============================================================

async def upsert_user(user: dict[str, Any]) -> None:
    assert pool is not None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                telegram_id,
                username,
                first_name,
                last_name
            )
            VALUES ($1,$2,$3,$4)

            ON CONFLICT (telegram_id)
            DO UPDATE SET
                username=EXCLUDED.username,
                first_name=EXCLUDED.first_name,
                last_name=EXCLUDED.last_name,
                updated_at=NOW()
            """,
            user["telegram_id"],
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
        )


# ============================================================
# ATTEMPT HELPERS
# ============================================================

async def get_attempt(
    attempt_id: uuid.UUID,
) -> Optional[asyncpg.Record]:

    assert pool is not None

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM attempts
            WHERE attempt_id=$1
            """,
            attempt_id,
        )


async def abandon_active_attempts(
    telegram_id: int,
) -> None:

    assert pool is not None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE attempts
            SET status='abandoned',
                finished_at=NOW()
            WHERE telegram_id=$1
              AND status='active'
            """,
            telegram_id,
        )


# ============================================================
# PAYMENT HELPERS
# ============================================================

async def has_unused_retest_payment(
    telegram_id: int,
) -> bool:

    assert pool is not None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT payment_id
            FROM payments
            WHERE telegram_id=$1
              AND purpose='retest'
              AND status='approved'
            ORDER BY decided_at ASC
            LIMIT 1
            """,
            telegram_id,
        )

        return row is not None


async def consume_retest_payment(
    conn: asyncpg.Connection,
    telegram_id: int,
) -> Optional[uuid.UUID]:

    row = await conn.fetchrow(
        """
        SELECT payment_id
        FROM payments
        WHERE telegram_id=$1
          AND purpose='retest'
          AND status='approved'
        ORDER BY decided_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
        """,
        telegram_id,
    )

    if not row:
        return None

    payment_id = row["payment_id"]

    await conn.execute(
        """
        UPDATE payments
        SET status='used'
        WHERE payment_id=$1
          AND status='approved'
        """,
        payment_id,
    )

    return payment_id


# ============================================================
# REQUEST MODELS
# ============================================================

class StartAttemptRequest(BaseModel):
    attempt_id: Optional[str] = None


class FinishAttemptRequest(BaseModel):
    attempt_id: str
    answers: dict[str, int] = Field(default_factory=dict)
    elapsed_seconds: int = Field(default=0, ge=0, le=TIME_LIMIT_SECONDS + 120)


class PaymentCreateRequest(BaseModel):
    purpose: str = "retest"


class AdminDecisionRequest(BaseModel):
    action: str


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    yield

    global pool

    if pool:
        await pool.close()

    logger.info("Database pool closed")


app = FastAPI(
    title="IQ Test Bot API",
    version="3.0.0",
    lifespan=lifespan,
)


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():
    return {
        "ok": True,
        "service": "IQ TEST BOT",
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "database": pool is not None,
    }


@app.get("/api/config")
async def api_config():
    return {
        "ok": True,
        "question_count": QUESTION_COUNT,
        "time_limit": TIME_LIMIT_SECONDS,
        "price": PRICE_UZS,
        "max_iq": MAX_IQ,
    }


# ============================================================
# TEST PACKAGE
# ============================================================

@app.get("/api/test/package")
async def test_package(
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    return {
        "ok": True,
        "question_count": QUESTION_COUNT,
        "time_limit": TIME_LIMIT_SECONDS,
        "questions": public_questions(),
    }


# ============================================================
# START ATTEMPT
# ============================================================

@app.post("/api/session/start")
async def start_attempt(
    body: StartAttemptRequest,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    telegram_id = user["telegram_id"]

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            # Never allow multiple active attempts.
            await conn.execute(
                """
                UPDATE attempts
                SET status='abandoned',
                    finished_at=NOW()
                WHERE telegram_id=$1
                  AND status='active'
                """,
                telegram_id,
            )

            # Check finished attempts.
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM attempts
                WHERE telegram_id=$1
                  AND status='finished'
                """,
                telegram_id,
            )

            payment_used = None

            if count > 0:

                payment_used = await consume_retest_payment(
                    conn,
                    telegram_id,
                )

                if not payment_used:
                    raise HTTPException(
                        status_code=402,
                        detail="PAID_RETEST",
                    )

            attempt_id = uuid.uuid4()

            if body.attempt_id:
                try:
                    requested_id = uuid.UUID(body.attempt_id)

                    # Only use client attempt_id if it is not already present.
                    existing = await conn.fetchrow(
                        """
                        SELECT attempt_id
                        FROM attempts
                        WHERE attempt_id=$1
                        """,
                        requested_id,
                    )

                    if not existing:
                        attempt_id = requested_id

                except ValueError:
                    pass

            await conn.execute(
                """
                INSERT INTO attempts (
                    attempt_id,
                    telegram_id,
                    started_at,
                    status
                )
                VALUES ($1,$2,NOW(),'active')
                """,
                attempt_id,
                telegram_id,
            )

    return {
        "ok": True,
        "attempt_id": str(attempt_id),
        "attemptId": str(attempt_id),
        "question_count": QUESTION_COUNT,
        "time_limit": TIME_LIMIT_SECONDS,
        "timeLimit": TIME_LIMIT_SECONDS,
        "questions": public_questions(),
    }


# ============================================================
# FINISH ATTEMPT
# ============================================================

@app.post("/api/session/finish")
async def finish_attempt(
    body: FinishAttemptRequest,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    try:
        attempt_id = uuid.UUID(body.attempt_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="INVALID_ATTEMPT_ID",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            attempt = await conn.fetchrow(
                """
                SELECT *
                FROM attempts
                WHERE attempt_id=$1
                FOR UPDATE
                """,
                attempt_id,
            )

            if not attempt:
                raise HTTPException(
                    status_code=404,
                    detail="ATTEMPT_NOT_FOUND",
                )

            if attempt["telegram_id"] != user["telegram_id"]:
                raise HTTPException(
                    status_code=403,
                    detail="ATTEMPT_OWNER_MISMATCH",
                )

            # Idempotency:
            # if already finished, return exactly the stored result.
            if attempt["status"] == "finished":
                return {
                    "ok": True,
                    "attempt_id": str(attempt_id),
                    "status": "finished",
                    "iq": attempt["iq_score"],
                    "iq_score": attempt["iq_score"],
                    "raw_score": attempt["raw_score"],
                    "correct": attempt["correct_count"],
                    "correct_count": attempt["correct_count"],
                    "elapsed_seconds": attempt["elapsed_seconds"],
                    "elapsed": attempt["elapsed_seconds"],
                    "synced": True,
                    "idempotent": True,
                }

            if attempt["status"] != "active":
                raise HTTPException(
                    status_code=409,
                    detail="ATTEMPT_NOT_ACTIVE",
                )

            # Server is authoritative.
            elapsed = min(
                body.elapsed_seconds,
                TIME_LIMIT_SECONDS,
            )

            answers = body.answers or {}

            if not isinstance(answers, dict):
                raise HTTPException(
                    status_code=400,
                    detail="INVALID_ANSWERS",
                )

            # Strict answer validation.
            clean_answers: dict[str, int] = {}

            for key, value in answers.items():

                if not isinstance(key, str):
                    continue

                if not isinstance(value, int):
                    continue

                if key not in {q["id"] for q in QUESTIONS}:
                    continue

                if value < 0 or value >= 4:
                    continue

                clean_answers[key] = value

            raw_score = 0
            correct_count = 0

            question_map = {
                q["id"]: q
                for q in QUESTIONS
            }

            for index, question in enumerate(QUESTIONS):

                selected = clean_answers.get(
                    question["id"]
                )

                if selected is not None:
                    if selected == question["correct"]:
                        raw_score += WEIGHTS[index]
                        correct_count += 1

            iq_score = calculate_iq(raw_score)

            await conn.execute(
                """
                UPDATE attempts
                SET
                    finished_at=NOW(),
                    elapsed_seconds=$2,
                    answers=$3::jsonb,
                    raw_score=$4,
                    correct_count=$5,
                    iq_score=$6,
                    status='finished'
                WHERE attempt_id=$1
                """,
                attempt_id,
                elapsed,
                json.dumps(clean_answers),
                raw_score,
                correct_count,
                iq_score,
            )

    return {
        "ok": True,
        "attempt_id": str(attempt_id),
        "attemptId": str(attempt_id),
        "status": "finished",

        "iq": iq_score,
        "iq_score": iq_score,

        "raw_score": raw_score,

        "correct": correct_count,
        "correct_count": correct_count,

        "total": QUESTION_COUNT,
        "question_count": QUESTION_COUNT,

        "elapsed_seconds": elapsed,
        "elapsed": elapsed,

        "synced": True,
        "idempotent": False,
    }


# ============================================================
# PROFILE
# ============================================================

@app.get("/api/profile")
async def profile(
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    assert pool is not None

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE status='finished'
                ) AS tests,

                MAX(iq_score) FILTER (
                    WHERE status='finished'
                ) AS best_iq,

                AVG(iq_score) FILTER (
                    WHERE status='finished'
                ) AS average_iq

            FROM attempts
            WHERE telegram_id=$1
            """,
            user["telegram_id"],
        )

    return {
        "ok": True,
        "user": {
            "telegram_id": user["telegram_id"],
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        },
        "tests": int(row["tests"] or 0),
        "best_iq": int(row["best_iq"]) if row["best_iq"] is not None else None,
        "average_iq": (
            round(float(row["average_iq"]), 1)
            if row["average_iq"] is not None
            else None
        ),
    }


# ============================================================
# RANKING
# ============================================================

@app.get("/api/ranking")
async def ranking(
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                a.telegram_id,
                a.iq_score,
                a.correct_count,
                a.finished_at,
                u.username,
                u.first_name
            FROM attempts a
            JOIN users u
              ON u.telegram_id=a.telegram_id

            WHERE a.status='finished'
              AND a.iq_score IS NOT NULL

            ORDER BY
                a.iq_score DESC,
                a.finished_at ASC

            LIMIT 100
            """
        )

        my_best = await conn.fetchrow(
            """
            SELECT MAX(iq_score) AS iq
            FROM attempts
            WHERE telegram_id=$1
              AND status='finished'
            """,
            user["telegram_id"],
        )

    items = []

    for position, row in enumerate(rows, start=1):

        display_name = (
            row["first_name"]
            or (
                f"@{row['username']}"
                if row["username"]
                else "Foydalanuvchi"
            )
        )

        items.append(
            {
                "position": position,
                "rank": position,
                "name": display_name,
                "username": row["username"],
                "iq": row["iq_score"],
                "score": row["iq_score"],
                "correct": row["correct_count"],
            }
        )

    my_iq = my_best["iq"]

    my_position = None

    if my_iq is not None:
        my_position = await conn_fetch_rank(
            user["telegram_id"],
            my_iq,
        )

    return {
        "ok": True,
        "items": items,
        "ranking": items,
        "my_rank": my_position,
        "my_position": my_position,
        "my_score": my_iq,
        "my_iq": my_iq,
    }


async def conn_fetch_rank(
    telegram_id: int,
    iq: int,
) -> Optional[int]:

    assert pool is not None

    async with pool.acquire() as conn:

        rank = await conn.fetchval(
            """
            SELECT COUNT(*) + 1
            FROM (
                SELECT
                    telegram_id,
                    MAX(iq_score) AS best_iq
                FROM attempts
                WHERE status='finished'
                GROUP BY telegram_id
            ) x
            WHERE x.best_iq > $1
            """,
            iq,
        )

        return int(rank) if rank is not None else None


# ============================================================
# PAYMENT CREATE
# ============================================================

@app.post("/api/payment/create")
async def create_payment(
    body: PaymentCreateRequest,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    await upsert_user(user)

    purpose = body.purpose.strip().lower()

    if purpose not in {
        "retest",
        "result",
    }:
        purpose = "retest"

    assert pool is not None

    async with pool.acquire() as conn:

        cards = await conn.fetch(
            """
            SELECT
                id,
                title,
                card_number,
                owner_name
            FROM payment_cards
            WHERE active=TRUE
            ORDER BY id ASC
            """
        )

        if not cards:
            raise HTTPException(
                status_code=503,
                detail="NO_PAYMENT_CARD",
            )

        payment_id = uuid.uuid4()

        await conn.execute(
            """
            INSERT INTO payments (
                payment_id,
                telegram_id,
                amount,
                purpose,
                status
            )
            VALUES ($1,$2,$3,$4,'pending')
            """,
            payment_id,
            user["telegram_id"],
            PRICE_UZS,
            purpose,
        )

    return {
        "ok": True,
        "payment_id": str(payment_id),
        "paymentId": str(payment_id),
        "amount": PRICE_UZS,
        "purpose": purpose,
        "status": "pending",

        "cards": [
            {
                "id": card["id"],
                "title": card["title"],
                "card_number": card["card_number"],
                "owner_name": card["owner_name"],
            }
            for card in cards
        ],
    }


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.get("/api/payment/{payment_id}")
async def payment_status(
    payment_id: str,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="INVALID_PAYMENT_ID",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT
                payment_id,
                amount,
                purpose,
                status,
                created_at,
                decided_at
            FROM payments
            WHERE payment_id=$1
              AND telegram_id=$2
            """,
            pid,
            user["telegram_id"],
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="PAYMENT_NOT_FOUND",
        )

    return {
        "ok": True,
        "payment_id": str(row["payment_id"]),
        "paymentId": str(row["payment_id"]),
        "amount": row["amount"],
        "purpose": row["purpose"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "decided_at": (
            row["decided_at"].isoformat()
            if row["decided_at"]
            else None
        ),
    }


# ============================================================
# ADMIN AUTH
# ============================================================

def is_admin(telegram_id: int) -> bool:
    return (
        ADMIN_ID != 0
        and telegram_id == ADMIN_ID
    )


# ============================================================
# ADMIN PAYMENT LIST
# ============================================================

@app.get("/api/admin/payments")
async def admin_payments(
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    if not is_admin(user["telegram_id"]):
        raise HTTPException(
            status_code=403,
            detail="ADMIN_ONLY",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                payment_id,
                telegram_id,
                amount,
                purpose,
                status,
                created_at,
                decided_at
            FROM payments
            ORDER BY created_at DESC
            LIMIT 100
            """
        )

    return {
        "ok": True,
        "payments": [
            {
                "payment_id": str(row["payment_id"]),
                "telegram_id": row["telegram_id"],
                "amount": row["amount"],
                "purpose": row["purpose"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
                "decided_at": (
                    row["decided_at"].isoformat()
                    if row["decided_at"]
                    else None
                ),
            }
            for row in rows
        ],
    }


# ============================================================
# ADMIN PAYMENT DECISION
# ============================================================

@app.post("/api/admin/payment/{payment_id}")
async def admin_payment_decision(
    payment_id: str,
    body: AdminDecisionRequest,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    if not is_admin(user["telegram_id"]):
        raise HTTPException(
            status_code=403,
            detail="ADMIN_ONLY",
        )

    action = body.action.strip().lower()

    if action not in {
        "approve",
        "reject",
    }:
        raise HTTPException(
            status_code=400,
            detail="INVALID_ACTION",
        )

    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="INVALID_PAYMENT_ID",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                FOR UPDATE
                """,
                pid,
            )

            if not payment:
                raise HTTPException(
                    status_code=404,
                    detail="PAYMENT_NOT_FOUND",
                )

            if payment["status"] != "pending":
                return {
                    "ok": True,
                    "status": payment["status"],
                    "already_decided": True,
                }

            new_status = (
                "approved"
                if action == "approve"
                else "rejected"
            )

            await conn.execute(
                """
                UPDATE payments
                SET
                    status=$2,
                    decided_at=NOW(),
                    admin_id=$3
                WHERE payment_id=$1
                  AND status='pending'
                """,
                pid,
                new_status,
                user["telegram_id"],
            )

            telegram_id = payment["telegram_id"]

    # Telegram notification.
    if bot:

        try:

            if action == "approve":

                await bot.send_message(
                    telegram_id,
                    (
                        "✅ To‘lov tasdiqlandi.\n\n"
                        "IQ TEST qayta topshirish imkoniyati ochildi."
                    ),
                )

            else:

                await bot.send_message(
                    telegram_id,
                    (
                        "❌ To‘lov rad etildi.\n\n"
                        "Agar xatolik bo‘lsa, qayta to‘lov yuboring."
                    ),
                )

        except Exception:
            logger.exception(
                "Could not send payment notification"
            )

    return {
        "ok": True,
        "status": (
            "approved"
            if action == "approve"
            else "rejected"
        ),
    }


# ============================================================
# ADMIN ADD CARD
# ============================================================

@app.post("/api/admin/cards")
async def admin_add_card(
    request: Request,
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    if not is_admin(user["telegram_id"]):
        raise HTTPException(
            status_code=403,
            detail="ADMIN_ONLY",
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="INVALID_JSON",
        )

    title = str(data.get("title", "")).strip()
    card_number = str(data.get("card_number", "")).strip()
    owner_name = str(data.get("owner_name", "")).strip()

    if not title or not card_number:
        raise HTTPException(
            status_code=400,
            detail="CARD_DATA_REQUIRED",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        card_id = await conn.fetchval(
            """
            INSERT INTO payment_cards (
                title,
                card_number,
                owner_name,
                active
            )
            VALUES ($1,$2,$3,TRUE)
            RETURNING id
            """,
            title,
            card_number,
            owner_name or None,
        )

    return {
        "ok": True,
        "card_id": card_id,
    }


# ============================================================
# ADMIN CARD LIST
# ============================================================

@app.get("/api/admin/cards")
async def admin_cards(
    x_telegram_init_data: str = Header(default=""),
):
    user = await get_webapp_user(x_telegram_init_data)

    if not is_admin(user["telegram_id"]):
        raise HTTPException(
            status_code=403,
            detail="ADMIN_ONLY",
        )

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                id,
                title,
                card_number,
                owner_name,
                active
            FROM payment_cards
            ORDER BY id ASC
            """
        )

    return {
        "ok": True,
        "cards": [
            {
                "id": row["id"],
                "title": row["title"],
                "card_number": row["card_number"],
                "owner_name": row["owner_name"],
                "active": row["active"],
            }
            for row in rows
        ],
    }


# ============================================================
# BOT
# ============================================================

def main_keyboard() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧠 IQ TEST",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    ),
                )
            ]
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: Message):

    if message.from_user:

        user = {
            "telegram_id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
        }

        try:
            await upsert_user(user)
        except Exception:
            logger.exception(
                "Could not save Telegram user"
            )

    await message.answer(
        (
            "🧠 <b>IQ TEST</b>\n\n"
            "16 ta mantiqiy savol.\n"
            "Vaqt: 8 daqiqa.\n\n"
            "Natijangiz test yakunida hisoblanadi."
        ),
        reply_markup=main_keyboard(),
    )


# ============================================================
# ADMIN TELEGRAM COMMANDS
# ============================================================

@dp.message(F.text == "/admin")
async def admin_command(message: Message):

    if not message.from_user:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ruxsat yo‘q.")
        return

    assert pool is not None

    async with pool.acquire() as conn:

        pending = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status='pending'
            """
        )

        users = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM users
            """
        )

        tests = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE status='finished'
            """
        )

    await message.answer(
        (
            "🛠 <b>ADMIN PANEL</b>\n\n"
            f"👥 Users: <b>{users}</b>\n"
            f"🧠 Finished tests: <b>{tests}</b>\n"
            f"💳 Pending payments: <b>{pending}</b>\n\n"
            "To‘lovlarni ko‘rish:\n"
            "/payments"
        )
    )


@dp.message(F.text == "/payments")
async def payments_command(message: Message):

    if not message.from_user:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ruxsat yo‘q.")
        return

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                payment_id,
                telegram_id,
                amount,
                purpose,
                status,
                created_at
            FROM payments
            WHERE status='pending'
            ORDER BY created_at ASC
            LIMIT 20
            """
        )

    if not rows:
        await message.answer(
            "📭 Hozir pending to‘lov yo‘q."
        )
        return

    for row in rows:

        payment_id = str(row["payment_id"])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Tasdiqlash",
                        callback_data=f"pay:approve:{payment_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Rad etish",
                        callback_data=f"pay:reject:{payment_id}",
                    ),
                ]
            ]
        )

        await message.answer(
            (
                "💳 <b>Yangi to‘lov</b>\n\n"
                f"👤 User: <code>{row['telegram_id']}</code>\n"
                f"💰 Summa: <b>{row['amount']:,} UZS</b>\n"
                f"🎯 Purpose: {row['purpose']}\n"
                f"🆔 <code>{payment_id}</code>\n"
                f"📅 {row['created_at'].isoformat()}"
            ),
            reply_markup=keyboard,
        )


# ============================================================
# ADMIN CALLBACK
# ============================================================

@dp.callback_query(F.data.startswith("pay:"))
async def payment_callback(callback):

    if not callback.from_user:
        return

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    parts = callback.data.split(":")

    if len(parts) != 3:
        await callback.answer(
            "Noto‘g‘ri callback.",
            show_alert=True,
        )
        return

    _, action, payment_id = parts

    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        await callback.answer(
            "Payment ID xato.",
            show_alert=True,
        )
        return

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                FOR UPDATE
                """,
                pid,
            )

            if not payment:
                await callback.answer(
                    "To‘lov topilmadi.",
                    show_alert=True,
                )
                return

            if payment["status"] != "pending":
                await callback.answer(
                    f"Allaqachon: {payment['status']}",
                    show_alert=True,
                )
                return

            new_status = (
                "approved"
                if action == "approve"
                else "rejected"
            )

            await conn.execute(
                """
                UPDATE payments
                SET
                    status=$2,
                    decided_at=NOW(),
                    admin_id=$3
                WHERE payment_id=$1
                  AND status='pending'
                """,
                pid,
                new_status,
                callback.from_user.id,
            )

            telegram_id = payment["telegram_id"]

    if action == "approve":

        await callback.answer(
            "✅ To‘lov tasdiqlandi."
        )

        text = (
            "✅ <b>To‘lov tasdiqlandi</b>\n\n"
            "Qayta IQ TEST topshirish imkoniyati ochildi."
        )

    else:

        await callback.answer(
            "❌ To‘lov rad etildi."
        )

        text = (
            "❌ <b>To‘lov rad etildi</b>\n\n"
            "Qayta to‘lov yuborishingiz mumkin."
        )

    try:
        await bot.send_message(
            telegram_id,
            text,
        )
    except Exception:
        logger.exception(
            "Payment notification failed"
        )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass


# ============================================================
# WEB SERVER + BOT RUNNER
# ============================================================

async def run_bot():
    global bot

    bot = Bot(
        token=BOT_TOKEN
    )

    logger.info("Starting Telegram polling")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


async def run_web():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server = uvicorn.Server(config)

    logger.info(
        "Starting FastAPI server on port %s",
        PORT,
    )

    await server.serve()


async def main():
    await asyncio.gather(
        run_web(),
        run_bot(),
    )


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped")