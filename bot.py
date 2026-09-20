import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import string
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
CERT_DIR = BASE_DIR / "certificates"
RECEIPT_DIR = BASE_DIR / "receipts"

CERT_DIR.mkdir(exist_ok=True)
RECEIPT_DIR.mkdir(exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0") or 0)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "omono_v").strip().lstrip("@")

WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("iq-test-bot")


# ============================================================
# TELEGRAM
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# DATABASE
# ============================================================

pool: Optional[asyncpg.Pool] = None


async def db_pool() -> asyncpg.Pool:
    global pool

    if pool is None:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )

    return pool


async def db_fetchrow(query: str, *args):
    p = await db_pool()

    async with p.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def db_fetch(query: str, *args):
    p = await db_pool()

    async with p.acquire() as conn:
        return await conn.fetch(query, *args)


async def db_execute(query: str, *args):
    p = await db_pool()

    async with p.acquire() as conn:
        return await conn.execute(query, *args)


# ============================================================
# IQ QUESTIONS
# ============================================================
#
# IMPORTANT:
# Frontend will use the same IDs/order.
#
# Final answer key:
# Q01 B
# Q02 C
# Q03 A
# Q04 C
# Q05 C
# Q06 B
# Q07 A
# Q08 A
# Q09 C
# Q10 C
# Q11 B
# Q12 C
# Q13 B
# Q14 C
# Q15 D
# Q16 B
# Q17 C
# Q18 C
#
# index:
# 1,2,0,2,2,1,0,0,2,2,1,2,1,2,3,1,2,2
# ============================================================

IQ_QUESTIONS = [
    {
        "id": "Q01",
        "difficulty": 1,
        "category": "logic",
        "correct": 1,
    },
    {
        "id": "Q02",
        "difficulty": 1,
        "category": "pattern",
        "correct": 2,
    },
    {
        "id": "Q03",
        "difficulty": 1,
        "category": "spatial",
        "correct": 0,
    },
    {
        "id": "Q04",
        "difficulty": 1,
        "category": "pattern",
        "correct": 2,
    },
    {
        "id": "Q05",
        "difficulty": 1,
        "category": "spatial",
        "correct": 2,
    },
    {
        "id": "Q06",
        "difficulty": 1,
        "category": "logic",
        "correct": 1,
    },
    {
        "id": "Q07",
        "difficulty": 2,
        "category": "pattern",
        "correct": 0,
    },
    {
        "id": "Q08",
        "difficulty": 2,
        "category": "logic",
        "correct": 0,
    },
    {
        "id": "Q09",
        "difficulty": 2,
        "category": "spatial",
        "correct": 2,
    },
    {
        "id": "Q10",
        "difficulty": 2,
        "category": "spatial",
        "correct": 2,
    },
    {
        "id": "Q11",
        "difficulty": 2,
        "category": "pattern",
        "correct": 1,
    },
    {
        "id": "Q12",
        "difficulty": 2,
        "category": "logic",
        "correct": 2,
    },
    {
        "id": "Q13",
        "difficulty": 3,
        "category": "pattern",
        "correct": 1,
    },
    {
        "id": "Q14",
        "difficulty": 3,
        "category": "spatial",
        "correct": 2,
    },
    {
        "id": "Q15",
        "difficulty": 3,
        "category": "spatial",
        "correct": 3,
    },
    {
        "id": "Q16",
        "difficulty": 3,
        "category": "logic",
        "correct": 1,
    },
    {
        "id": "Q17",
        "difficulty": 3,
        "category": "pattern",
        "correct": 2,
    },
    {
        "id": "Q18",
        "difficulty": 3,
        "category": "logic",
        "correct": 2,
    },
]

IQ_ANSWER_KEY = tuple(q["correct"] for q in IQ_QUESTIONS)

IQ_WEIGHTS = (
    1,
    1,
    1,
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    2,
    2,
    3,
    3,
    3,
    3,
    3,
    3,
)

IQ_MAX_RAW = sum(IQ_WEIGHTS)


# ============================================================
# DEFAULT PRODUCTS
# ============================================================

DEFAULT_PRODUCTS = {
    "iq": 10000,
    "iq_retry": 5000,
    "eq_retry": 5000,
    "pq_retry": 5000,
    "battle": 7500,
}


# ============================================================
# DATABASE SCHEMA
# ============================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language TEXT NOT NULL DEFAULT 'uz',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_users_last_seen
ON users(last_seen);

CREATE INDEX IF NOT EXISTS idx_users_username
ON users(username);


CREATE TABLE IF NOT EXISTS admins (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS products (
    product_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    price BIGINT NOT NULL DEFAULT 0,
    is_free BOOLEAN NOT NULL DEFAULT FALSE,
    free_until TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS test_sessions (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    test_type TEXT NOT NULL,
    battle_id UUID,
    current_question INTEGER NOT NULL DEFAULT 0,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_sessions_user
ON test_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_test_sessions_battle
ON test_sessions(battle_id);


CREATE TABLE IF NOT EXISTS test_answers (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    answer INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, question_number)
);


CREATE TABLE IF NOT EXISTS test_attempts (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    test_type TEXT NOT NULL,
    score NUMERIC NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    total_questions INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    level TEXT,
    battle_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_user
ON test_attempts(user_id);

CREATE INDEX IF NOT EXISTS idx_attempts_score
ON test_attempts(score DESC);


CREATE TABLE IF NOT EXISTS results (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    attempt_id UUID NOT NULL REFERENCES test_attempts(id) ON DELETE CASCADE,
    test_type TEXT NOT NULL,
    score NUMERIC NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS payment_cards (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    card_number TEXT,
    click_number TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    product TEXT NOT NULL,
    amount BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    battle_id UUID,
    receipt_path TEXT,
    receipt_filename TEXT,
    admin_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    UNIQUE(id)
);

CREATE INDEX IF NOT EXISTS idx_payments_user
ON payments(user_id);

CREATE INDEX IF NOT EXISTS idx_payments_status
ON payments(status);


CREATE TABLE IF NOT EXISTS certificates (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    attempt_id UUID REFERENCES test_attempts(id) ON DELETE SET NULL,
    certificate_type TEXT NOT NULL DEFAULT 'iq',
    score NUMERIC,
    file_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_certificates_user
ON certificates(user_id);


CREATE TABLE IF NOT EXISTS battles (
    id UUID PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    creator_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    joiner_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_battles_code
ON battles(code);


CREATE TABLE IF NOT EXISTS battle_players (
    id BIGSERIAL PRIMARY KEY,
    battle_id UUID NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    payment_id UUID REFERENCES payments(id) ON DELETE SET NULL,
    payment_approved BOOLEAN NOT NULL DEFAULT FALSE,
    session_id UUID,
    attempt_id UUID,
    score NUMERIC,
    finished BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(battle_id, user_id)
);


CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    referrer_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referred_user_id BIGINT UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS broadcast_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    target_type TEXT NOT NULL,
    total_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def init_db():
    p = await db_pool()

    async with p.acquire() as conn:
        await conn.execute(SCHEMA_SQL)

        await conn.execute(
            """
            INSERT INTO admins(user_id, username)
            VALUES($1, $2)
            ON CONFLICT(user_id)
            DO UPDATE SET username = EXCLUDED.username
            """,
            ADMIN_USER_ID,
            ADMIN_USERNAME,
        )

        for key, price in DEFAULT_PRODUCTS.items():
            title = {
                "iq": "IQ testi",
                "iq_retry": "IQ qayta ishlash",
                "eq_retry": "EQ qayta ishlash",
                "pq_retry": "PQ qayta ishlash",
                "battle": "Battle",
            }[key]

            await conn.execute(
                """
                INSERT INTO products(
                    product_key,
                    title,
                    price,
                    is_free,
                    enabled
                )
                VALUES($1, $2, $3, FALSE, TRUE)
                ON CONFLICT(product_key) DO NOTHING
                """,
                key,
                title,
                price,
            )

        await conn.execute(
            """
            INSERT INTO app_settings(key, value)
            VALUES
                ('app_name', 'IQ TEST BOT'),
                ('active_window_minutes', '10'),
                ('retry_free_after_days', '5'),
                ('free_launch_until', '')
            ON CONFLICT(key) DO NOTHING
            """
        )

        if WEBAPP_URL:
            await conn.execute(
                """
                INSERT INTO app_settings(key, value)
                VALUES('webapp_url', $1)
                ON CONFLICT(key)
                DO UPDATE SET value = EXCLUDED.value
                """,
                WEBAPP_URL,
            )


# ============================================================
# HELPERS
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def json_dumps(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=json_default,
    )


def get_public_base_url() -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/")

    if WEBAPP_URL:
        return WEBAPP_URL.rstrip("/")

    return ""


def webhook_url() -> str:
    base = get_public_base_url()

    if not base:
        return ""

    return f"{base}/telegram/webhook"


def generate_uuid() -> str:
    return str(secrets.token_hex(16))


def generate_code(length: int = 4) -> str:
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))

        if code not in {"AAAA", "0000", "TEST"}:
            return code


def generate_certificate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "IQ-" + "".join(
            secrets.choice(alphabet)
            for _ in range(6)
        )

        exists = False

        # This function is called inside async flows where
        # uniqueness is also enforced by PostgreSQL.
        if not exists:
            return code


def score_level(score: float) -> str:
    if score >= 130:
        return "Juda yuqori daraja"

    if score >= 115:
        return "Yuqori daraja"

    if score >= 100:
        return "O‘rtachadan yuqori"

    if score >= 85:
        return "O‘rtacha daraja"

    if score >= 70:
        return "O‘rtachadan past"

    return "Boshlang‘ich daraja"


def calculate_iq(answers: list[int]) -> dict[str, Any]:
    correct = 0
    raw = 0

    categories = {
        "logic": {"correct": 0, "total": 0},
        "pattern": {"correct": 0, "total": 0},
        "spatial": {"correct": 0, "total": 0},
    }

    for index, question in enumerate(IQ_QUESTIONS):
        category = question["category"]

        categories[category]["total"] += 1

        answer = (
            answers[index]
            if index < len(answers)
            else -1
        )

        if answer == question["correct"]:
            correct += 1
            raw += IQ_WEIGHTS[index]
            categories[category]["correct"] += 1

    score = round(
        40 + (raw / IQ_MAX_RAW) * 120
    )

    metrics = {}

    for key, value in categories.items():
        if value["total"]:
            metrics[key] = round(
                value["correct"] /
                value["total"] *
                100
            )
        else:
            metrics[key] = 0

    return {
        "score": score,
        "iq_score": score,
        "correct": correct,
        "total": len(IQ_QUESTIONS),
        "raw": raw,
        "max_raw": IQ_MAX_RAW,
        "level": score_level(score),
        "metrics": metrics,
    }


def calculate_psych_score(
    answers: list[int],
    question_count: int,
    reverse_indexes: Optional[set[int]] = None,
) -> int:
    reverse_indexes = reverse_indexes or set()

    total = 0

    for index in range(question_count):
        answer = (
            answers[index]
            if index < len(answers)
            else 0
        )

        # 0..3 -> 0..100
        if index in reverse_indexes:
            answer = 3 - answer

        total += answer

    max_total = question_count * 3

    if max_total <= 0:
        return 0

    return round(
        total / max_total * 100
    )


def user_name_from_row(row) -> str:
    if not row:
        return "Foydalanuvchi"

    name = " ".join(
        part
        for part in [
            row.get("first_name"),
            row.get("last_name"),
        ]
        if part
    ).strip()

    if name:
        return name

    if row.get("username"):
        return f"@{row['username']}"

    return str(row["user_id"])


# ============================================================
# USER
# ============================================================

async def upsert_user(
    tg_user,
    language: Optional[str] = None,
):
    if language is None:
        existing = await db_fetchrow(
            """
            SELECT language
            FROM users
            WHERE user_id = $1
            """,
            tg_user.id,
        )

        language = (
            existing["language"]
            if existing
            else "uz"
        )

    await db_execute(
        """
        INSERT INTO users(
            user_id,
            username,
            first_name,
            last_name,
            language,
            last_seen,
            last_active
        )
        VALUES(
            $1,$2,$3,$4,$5,NOW(),NOW()
        )
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            last_seen = NOW(),
            last_active = NOW()
        """,
        tg_user.id,
        tg_user.username,
        tg_user.first_name,
        tg_user.last_name,
        language,
    )


async def get_user(user_id: int):
    return await db_fetchrow(
        """
        SELECT *
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )


async def save_language(
    user_id: int,
    language: str,
):
    await db_execute(
        """
        UPDATE users
        SET language = $2,
            last_active = NOW()
        WHERE user_id = $1
        """,
        user_id,
        language,
    )


# ============================================================
# ADMIN
# ============================================================

async def is_admin(user_id: int) -> bool:
    if ADMIN_USER_ID and user_id == ADMIN_USER_ID:
        return True

    row = await db_fetchrow(
        """
        SELECT 1
        FROM admins
        WHERE user_id = $1
          AND is_active = TRUE
        """,
        user_id,
    )

    return bool(row)


async def require_admin(user_id: int):
    if not await is_admin(user_id):
        raise HTTPException(
            status_code=403,
            detail="Admin huquqi kerak.",
        )


# ============================================================
# PRODUCT / PRICE
# ============================================================

async def get_product(product: str):
    return await db_fetchrow(
        """
        SELECT *
        FROM products
        WHERE product_key = $1
        """,
        product,
    )


async def get_products():
    return await db_fetch(
        """
        SELECT *
        FROM products
        ORDER BY
            CASE product_key
                WHEN 'iq' THEN 1
                WHEN 'iq_retry' THEN 2
                WHEN 'eq_retry' THEN 3
                WHEN 'pq_retry' THEN 4
                WHEN 'battle' THEN 5
                ELSE 99
            END
        """
    )


def product_is_free(row) -> bool:
    if not row:
        return False

    if row["is_free"]:
        return True

    free_until = row["free_until"]

    if free_until and free_until > now_utc():
        return True

    return False


async def product_access_required(
    user_id: int,
    product: str,
) -> bool:
    row = await get_product(product)

    if not row:
        return False

    if not row["enabled"]:
        return False

    if product_is_free(row):
        return False

    # First IQ attempt can be free if user has never
    # completed an IQ attempt.
    if product == "iq":
        count = await db_fetchrow(
            """
            SELECT COUNT(*) AS count
            FROM test_attempts
            WHERE user_id = $1
              AND test_type = 'iq'
            """,
            user_id,
        )

        if int(count["count"]) == 0:
            return False

    return True


async def has_approved_payment(
    user_id: int,
    product: str,
    battle_id: Optional[str] = None,
) -> bool:
    if battle_id:
        row = await db_fetchrow(
            """
            SELECT 1
            FROM payments
            WHERE user_id = $1
              AND product = $2
              AND battle_id = $3::uuid
              AND status = 'approved'
            ORDER BY approved_at DESC NULLS LAST
            LIMIT 1
            """,
            user_id,
            product,
            battle_id,
        )
    else:
        row = await db_fetchrow(
            """
            SELECT 1
            FROM payments
            WHERE user_id = $1
              AND product = $2
              AND status = 'approved'
            ORDER BY approved_at DESC NULLS LAST
            LIMIT 1
            """,
            user_id,
            product,
        )

    return bool(row)


# ============================================================
# TELEGRAM MINI APP INIT DATA
# ============================================================

def validate_telegram_init_data(
    init_data: str,
) -> Optional[dict]:
    if not init_data:
        return None

    try:
        parsed = dict(
            urllib.parse.parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = parsed.pop("hash", None)

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={parsed[key]}"
            for key in sorted(parsed)
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

        auth_date = int(
            parsed.get("auth_date", "0")
        )

        # 24h validity window.
        if (
            auth_date <= 0 or
            time.time() - auth_date > 86400
        ):
            return None

        user_raw = parsed.get("user")

        if not user_raw:
            return None

        user_data = json.loads(user_raw)

        return {
            "user": user_data,
            "auth_date": auth_date,
        }

    except Exception:
        logger.exception(
            "Mini App initData validation failed"
        )

        return None


async def miniapp_user(
    init_data: Optional[str],
):
    verified = validate_telegram_init_data(
        init_data or ""
    )

    if not verified:
        raise HTTPException(
            status_code=401,
            detail="Telegram initData noto‘g‘ri yoki eskirgan.",
        )

    user_data = verified["user"]

    user_id = int(user_data["id"])

    await db_execute(
        """
        UPDATE users
        SET last_seen = NOW(),
            last_active = NOW()
        WHERE user_id = $1
        """,
        user_id,
    )

    row = await get_user(user_id)

    if not row:
        # Normally impossible if /start was used,
        # but Mini App remains robust.
        class TempUser:
            id = user_id
            username = user_data.get("username")
            first_name = user_data.get("first_name")
            last_name = user_data.get("last_name")

        await upsert_user(TempUser())
        row = await get_user(user_id)

    return row


# ============================================================
# PAYMENT
# ============================================================

async def create_payment(
    user_id: int,
    product: str,
    battle_id: Optional[str] = None,
):
    product_row = await get_product(product)

    if not product_row:
        raise HTTPException(
            status_code=404,
            detail="Mahsulot topilmadi.",
        )

    if not product_row["enabled"]:
        raise HTTPException(
            status_code=400,
            detail="Bu mahsulot hozir mavjud emas.",
        )

    if product_is_free(product_row):
        return None

    amount = int(product_row["price"])

    if amount <= 0:
        return None

    # Duplicate pending payment protection.
    existing = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE user_id = $1
          AND product = $2
          AND status IN ('pending', 'pending_receipt')
          AND (
              battle_id IS NOT DISTINCT FROM
              CASE
                  WHEN $3::text IS NULL THEN NULL
                  ELSE $3::uuid
              END
          )
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
        product,
        battle_id,
    )

    if existing:
        return existing

    payment_id = await create_uuid_db()

    await db_execute(
        """
        INSERT INTO payments(
            id,
            user_id,
            product,
            amount,
            status,
            battle_id
        )
        VALUES(
            $1::uuid,
            $2,
            $3,
            $4,
            'pending',
            $5::uuid
        )
        """,
        payment_id,
        user_id,
        product,
        amount,
        battle_id,
    )

    return await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )


async def create_uuid_db() -> str:
    # PostgreSQL has gen_random_uuid only when pgcrypto
    # is available. To keep deployment simple we generate
    # the UUID in Python.
    import uuid

    return str(uuid.uuid4())


async def notify_admin_payment(payment_id: str):
    payment = await db_fetchrow(
        """
        SELECT
            p.*,
            u.username,
            u.first_name,
            u.last_name
        FROM payments p
        JOIN users u
          ON u.user_id = p.user_id
        WHERE p.id = $1::uuid
        """,
        payment_id,
    )

    if not payment:
        return

    admins = await db_fetch(
        """
        SELECT user_id
        FROM admins
        WHERE is_active = TRUE
        """
    )

    text = (
        "💳 <b>YANGI TO‘LOV</b>\n\n"
        f"👤 {escape_tg(user_name_from_row(payment))}\n"
        f"🆔 <code>{payment['user_id']}</code>\n"
        f"📦 {escape_tg(payment['product'])}\n"
        f"💰 {payment['amount']:,} so‘m\n"
        f"🧾 {payment['id']}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📎 CHEKNI KO‘RISH",
                    callback_data=f"pay_receipt:{payment_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ TASDIQLASH",
                    callback_data=f"pay_approve:{payment_id}",
                ),
                InlineKeyboardButton(
                    text="❌ RAD ETISH",
                    callback_data=f"pay_reject:{payment_id}",
                ),
            ],
        ]
    )

    for admin in admins:
        try:
            await bot.send_message(
                admin["user_id"],
                text,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Could not notify admin %s",
                admin["user_id"],
            )


def escape_tg(value: Any) -> str:
    # HTML-safe enough for our generated text.
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ============================================================
# CERTIFICATE
# ============================================================

def find_font(size: int, bold: bool = False):
    candidates = []

    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
        )

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def generate_certificate_png(
    name: str,
    score: int,
    level: str,
    code: str,
    certificate_type: str = "iq",
) -> str:
    width = 1400
    height = 1000

    image = Image.new(
        "RGB",
        (width, height),
        "#080912",
    )

    draw = ImageDraw.Draw(image)

    # Border.
    draw.rounded_rectangle(
        (40, 40, width - 40, height - 40),
        radius=42,
        outline="#8B5CF6",
        width=5,
    )

    draw.rounded_rectangle(
        (70, 70, width - 70, height - 70),
        radius=35,
        outline="#3B82F6",
        width=2,
    )

    title_font = find_font(70, True)
    name_font = find_font(62, True)
    score_font = find_font(120, True)
    normal_font = find_font(34, False)
    small_font = find_font(28, False)

    title = (
        "BATTLE VICTORY"
        if certificate_type == "battle"
        else "SERTIFIKAT"
    )

    def centered(
        text: str,
        y: int,
        font,
        fill="#FFFFFF",
    ):
        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font,
        )

        x = (width - (bbox[2] - bbox[0])) / 2

        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill,
        )

    centered(
        title,
        125,
        title_font,
        "#A78BFA",
    )

    centered(
        "IQ TEST BOT",
        215,
        normal_font,
        "#94A3B8",
    )

    centered(
        name[:40],
        300,
        name_font,
        "#FFFFFF",
    )

    centered(
        "IQ-style Score",
        410,
        normal_font,
        "#CBD5E1",
    )

    centered(
        str(score),
        455,
        score_font,
        "#FFFFFF",
    )

    centered(
        level,
        615,
        normal_font,
        "#A78BFA",
    )

    date_text = now_utc().strftime(
        "%d.%m.%Y"
    )

    centered(
        date_text,
        690,
        normal_font,
        "#CBD5E1",
    )

    centered(
        code,
        760,
        normal_font,
        "#60A5FA",
    )

    centered(
        "IQ TEST BOT",
        855,
        small_font,
        "#64748B",
    )

    filename = f"{code}.png"
    path = CERT_DIR / filename

    image.save(
        path,
        format="PNG",
        optimize=True,
    )

    return str(path)


async def create_certificate(
    user_id: int,
    attempt_id: str,
    certificate_type: str = "iq",
) -> dict:
    existing = await db_fetchrow(
        """
        SELECT *
        FROM certificates
        WHERE user_id = $1
          AND attempt_id = $2::uuid
          AND certificate_type = $3
        ORDER BY id DESC
        LIMIT 1
        """,
        user_id,
        attempt_id,
        certificate_type,
    )

    if existing:
        return dict(existing)

    attempt = await db_fetchrow(
        """
        SELECT
            a.*,
            u.first_name,
            u.last_name,
            u.username
        FROM test_attempts a
        JOIN users u
          ON u.user_id = a.user_id
        WHERE a.id = $1::uuid
          AND a.user_id = $2
        """,
        attempt_id,
        user_id,
    )

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="Natija topilmadi.",
        )

    code = generate_certificate_code()

    # DB uniqueness handles the very unlikely collision.
    name = user_name_from_row(attempt)

    score = int(float(attempt["score"]))
    level = attempt["level"] or score_level(score)

    path = generate_certificate_png(
        name=name,
        score=score,
        level=level,
        code=code,
        certificate_type=certificate_type,
    )

    await db_execute(
        """
        INSERT INTO certificates(
            code,
            user_id,
            attempt_id,
            certificate_type,
            score,
            file_path
        )
        VALUES(
            $1,
            $2,
            $3::uuid,
            $4,
            $5,
            $6
        )
        """,
        code,
        user_id,
        attempt_id,
        certificate_type,
        score,
        path,
    )

    row = await db_fetchrow(
        """
        SELECT *
        FROM certificates
        WHERE code = $1
        """,
        code,
    )

    return dict(row)


# ============================================================
# ACCESS / TEST SESSION
# ============================================================

async def latest_attempt(
    user_id: int,
    test_type: str,
):
    return await db_fetchrow(
        """
        SELECT *
        FROM test_attempts
        WHERE user_id = $1
          AND test_type = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
        test_type,
    )


async def create_session(
    user_id: int,
    test_type: str,
    battle_id: Optional[str] = None,
):
    import uuid

    session_id = str(uuid.uuid4())

    await db_execute(
        """
        INSERT INTO test_sessions(
            id,
            user_id,
            test_type,
            battle_id
        )
        VALUES(
            $1::uuid,
            $2,
            $3,
            $4::uuid
        )
        """,
        session_id,
        user_id,
        test_type,
        battle_id,
    )

    return session_id


async def get_session(
    session_id: str,
    user_id: int,
):
    return await db_fetchrow(
        """
        SELECT *
        FROM test_sessions
        WHERE id = $1::uuid
          AND user_id = $2
        """,
        session_id,
        user_id,
    )


async def sync_session(
    session_id: str,
    user_id: int,
    current: int,
    answers: list,
    elapsed_seconds: int,
):
    session = await get_session(
        session_id,
        user_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session topilmadi.",
        )

    if session["completed"]:
        return

    safe_answers = []

    for answer in answers[:18]:
        try:
            value = int(answer)
        except Exception:
            value = -1

        if value not in (0, 1, 2, 3):
            value = -1

        safe_answers.append(value)

    await db_execute(
        """
        UPDATE test_sessions
        SET current_question = $3,
            answers = $4::jsonb,
            elapsed_seconds = $5
        WHERE id = $1::uuid
          AND user_id = $2
          AND completed = FALSE
        """,
        session_id,
        user_id,
        max(0, min(17, int(current))),
        json_dumps(safe_answers),
        max(0, int(elapsed_seconds)),
    )

    for index, answer in enumerate(safe_answers):
        if answer < 0:
            continue

        await db_execute(
            """
            INSERT INTO test_answers(
                session_id,
                question_number,
                answer
            )
            VALUES(
                $1::uuid,
                $2,
                $3
            )
            ON CONFLICT(session_id, question_number)
            DO UPDATE SET
                answer = EXCLUDED.answer
            """,
            session_id,
            index + 1,
            answer,
        )


async def finish_session(
    user_id: int,
    session_id: str,
    answers: list,
    elapsed_seconds: int,
    battle_id: Optional[str] = None,
):
    session = await get_session(
        session_id,
        user_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session topilmadi.",
        )

    if session["completed"]:
        attempt = await db_fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE session_id = $1::uuid
            """,
            session_id,
        )

        if attempt:
            return await format_attempt_result(
                attempt
            )

    if session["test_type"] != "iq":
        raise HTTPException(
            status_code=400,
            detail="Bu endpoint faqat IQ uchun.",
        )

    if len(answers) != 18:
        raise HTTPException(
            status_code=400,
            detail="IQ test 18 ta javobdan iborat bo‘lishi kerak.",
        )

    clean_answers = []

    for answer in answers:
        try:
            answer = int(answer)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Javob formati noto‘g‘ri.",
            )

        if answer not in (0, 1, 2, 3):
            raise HTTPException(
                status_code=400,
                detail="Javob qiymati noto‘g‘ri.",
            )

        clean_answers.append(answer)

    result = calculate_iq(clean_answers)

    import uuid

    attempt_id = str(uuid.uuid4())

    async with (await db_pool()).acquire() as conn:
        async with conn.transaction():

            # Re-check duplicate submission inside transaction.
            existing = await conn.fetchrow(
                """
                SELECT *
                FROM test_attempts
                WHERE session_id = $1::uuid
                """,
                session_id,
            )

            if existing:
                return await format_attempt_result(
                    existing
                )

            await conn.execute(
                """
                UPDATE test_sessions
                SET
                    answers = $3::jsonb,
                    elapsed_seconds = $4,
                    completed = TRUE,
                    finished_at = NOW()
                WHERE id = $1::uuid
                  AND user_id = $2
                """,
                session_id,
                user_id,
                json_dumps(clean_answers),
                max(0, int(elapsed_seconds)),
            )

            await conn.execute(
                """
                INSERT INTO test_attempts(
                    id,
                    user_id,
                    session_id,
                    test_type,
                    score,
                    correct_answers,
                    total_questions,
                    elapsed_seconds,
                    metrics,
                    level,
                    battle_id
                )
                VALUES(
                    $1::uuid,
                    $2,
                    $3::uuid,
                    'iq',
                    $4,
                    $5,
                    $6,
                    $7,
                    $8::jsonb,
                    $9,
                    $10::uuid
                )
                """,
                attempt_id,
                user_id,
                session_id,
                result["score"],
                result["correct"],
                result["total"],
                max(0, int(elapsed_seconds)),
                json_dumps(result["metrics"]),
                result["level"],
                battle_id,
            )

            await conn.execute(
                """
                INSERT INTO results(
                    user_id,
                    attempt_id,
                    test_type,
                    score,
                    data
                )
                VALUES(
                    $1,
                    $2::uuid,
                    'iq',
                    $3,
                    $4::jsonb
                )
                """,
                user_id,
                attempt_id,
                result["score"],
                json_dumps(result),
            )

            for index, answer in enumerate(
                clean_answers
            ):
                await conn.execute(
                    """
                    INSERT INTO test_answers(
                        session_id,
                        question_number,
                        answer
                    )
                    VALUES(
                        $1::uuid,
                        $2,
                        $3
                    )
                    ON CONFLICT(
                        session_id,
                        question_number
                    )
                    DO UPDATE SET
                        answer = EXCLUDED.answer
                    """,
                    session_id,
                    index + 1,
                    answer,
                )

    result["attempt_id"] = attempt_id

    # Battle player is updated after the attempt exists.
    if battle_id:
        await update_battle_player_result(
            battle_id=battle_id,
            user_id=user_id,
            attempt_id=attempt_id,
            score=result["score"],
        )

    return result


async def format_attempt_result(attempt):
    metrics = attempt["metrics"]

    if isinstance(metrics, str):
        metrics = json.loads(metrics)

    return {
        "attempt_id": str(attempt["id"]),
        "score": float(attempt["score"]),
        "iq_score": float(attempt["score"]),
        "correct": attempt["correct_answers"],
        "total": attempt["total_questions"],
        "elapsed_seconds": attempt["elapsed_seconds"],
        "level": attempt["level"],
        "metrics": metrics or {},
    }


# ============================================================
# BATTLE
# ============================================================

async def get_battle(
    battle_id: str,
):
    return await db_fetchrow(
        """
        SELECT *
        FROM battles
        WHERE id = $1::uuid
        """,
        battle_id,
    )


async def update_battle_status(
    battle_id: str,
):
    battle = await get_battle(battle_id)

    if not battle:
        return

    players = await db_fetch(
        """
        SELECT *
        FROM battle_players
        WHERE battle_id = $1::uuid
        """,
        battle_id,
    )

    if len(players) < 2:
        return

    all_paid = all(
        bool(player["payment_approved"])
        for player in players
    )

    if (
        all_paid and
        battle["status"] == "waiting"
    ):
        await db_execute(
            """
            UPDATE battles
            SET
                status = 'ready',
                started_at = NOW()
            WHERE id = $1::uuid
            """,
            battle_id,
        )

    finished = [
        player
        for player in players
        if player["finished"]
    ]

    if len(finished) == 2:
        await db_execute(
            """
            UPDATE battles
            SET
                status = 'finished',
                finished_at = NOW()
            WHERE id = $1::uuid
            """,
            battle_id,
        )


async def update_battle_player_result(
    battle_id: str,
    user_id: int,
    attempt_id: str,
    score: float,
):
    await db_execute(
        """
        UPDATE battle_players
        SET
            attempt_id = $3::uuid,
            score = $4,
            finished = TRUE
        WHERE battle_id = $1::uuid
          AND user_id = $2
        """,
        battle_id,
        user_id,
        attempt_id,
        score,
    )

    await update_battle_status(
        battle_id
    )


async def battle_payload(
    battle_id: str,
    user_id: int,
):
    battle = await get_battle(battle_id)

    if not battle:
        raise HTTPException(
            status_code=404,
            detail="Battle topilmadi.",
        )

    players = await db_fetch(
        """
        SELECT
            bp.*,
            u.first_name,
            u.last_name,
            u.username
        FROM battle_players bp
        JOIN users u
          ON u.user_id = bp.user_id
        WHERE bp.battle_id = $1::uuid
        ORDER BY bp.created_at
        """,
        battle_id,
    )

    own = None
    opponent = None

    for player in players:
        if player["user_id"] == user_id:
            own = player
        else:
            opponent = player

    if not own:
        raise HTTPException(
            status_code=403,
            detail="Bu battle sizga tegishli emas.",
        )

    # Never expose opponent answers.
    return {
        "battle_id": str(battle["id"]),
        "code": battle["code"],
        "status": battle["status"],
        "role": own["role"],
        "opponent": (
            user_name_from_row(opponent)
            if opponent
            else None
        ),
        "own_score": (
            float(own["score"])
            if own["score"] is not None
            else None
        ),
        "own_finished": bool(
            own["finished"]
        ),
        "opponent_finished": bool(
            opponent["finished"]
        ) if opponent else False,
        "opponent_score": (
            float(opponent["score"])
            if (
                opponent and
                battle["status"] == "finished"
            )
            else None
        ),
    }


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="IQ TEST BOT",
    docs_url=None,
    redoc_url=None,
)

if WEBAPP_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(
            directory=str(WEBAPP_DIR)
        ),
        name="static",
    )


@app.get(
    "/",
    response_class=HTMLResponse,
)
async def root():
    return """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>IQ TEST BOT</title>
      </head>
      <body>
        <h1>IQ TEST BOT</h1>
        <p>Server ishlayapti.</p>
      </body>
    </html>
    """


@app.get(
    "/app",
    response_class=HTMLResponse,
)
async def mini_app():
    index = WEBAPP_DIR / "index.html"

    if not index.exists():
        raise HTTPException(
            status_code=404,
            detail="webapp/index.html topilmadi.",
        )

    return FileResponse(
        index,
        media_type="text/html",
    )


@app.get("/health")
async def health():
    try:
        await db_fetchrow(
            "SELECT 1"
        )

        return {
            "ok": True,
            "database": True,
            "app": "IQ TEST BOT",
        }

    except Exception as error:
        logger.exception(
            "Health database check failed"
        )

        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "database": False,
                "error": str(error),
            },
        )


# ============================================================
# API MODELS
# ============================================================

class SessionStartRequest(BaseModel):
    test_type: str = "iq"
    battle_id: Optional[str] = None


class SessionSyncRequest(BaseModel):
    session_id: str
    test_type: str = "iq"
    current: int = 0
    answers: list[int] = []
    elapsed_seconds: int = 0
    battle_id: Optional[str] = None


class TestFinishRequest(BaseModel):
    session_id: str
    test_type: str = "iq"
    answers: list[int]
    elapsed_seconds: int = 0
    battle_id: Optional[str] = None


class PaymentCreateRequest(BaseModel):
    product: str
    battle_id: Optional[str] = None


class BattleCreateRequest(BaseModel):
    pass


class BattleJoinRequest(BaseModel):
    code: str


class AdminPriceRequest(BaseModel):
    product: str
    price: int = 0
    is_free: bool = False
    free_until: Optional[str] = None
    enabled: bool = True


# ============================================================
# API AUTH
# ============================================================

async def api_user(
    x_telegram_init_data: Optional[str] = Header(
        default=None,
        alias="X-Telegram-Init-Data",
    ),
):
    return await miniapp_user(
        x_telegram_init_data
    )


# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
async def api_config(
    user=__import__("fastapi").Depends(api_user),
):
    products = await get_products()

    product_data = {}

    for row in products:
        product_data[row["product_key"]] = {
            "title": row["title"],
            "price": int(row["price"]),
            "is_free": product_is_free(row),
            "enabled": bool(row["enabled"]),
            "free_until": iso(row["free_until"]),
        }

    return {
        "app_name": "IQ TEST BOT",
        "battle_price": product_data.get(
            "battle",
            {},
        ).get("price", 7500),
        "products": product_data,
        "prices": {
            key: value["price"]
            for key, value in product_data.items()
        },
    }


# ============================================================
# ME / PROFILE
# ============================================================

@app.get("/api/me")
async def api_me(
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    iq = await latest_attempt(
        user_id,
        "iq",
    )

    eq = await latest_attempt(
        user_id,
        "eq",
    )

    pq = await latest_attempt(
        user_id,
        "pq",
    )

    certificates = await db_fetch(
        """
        SELECT
            code,
            certificate_type,
            score,
            created_at
        FROM certificates
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        user_id,
    )

    def attempt_json(row):
        if not row:
            return None

        return {
            "attempt_id": str(row["id"]),
            "score": float(row["score"]),
            "level": row["level"],
            "correct": row["correct_answers"],
            "total": row["total_questions"],
            "elapsed_seconds": row["elapsed_seconds"],
            "metrics": row["metrics"],
        }

    return {
        "user": {
            "user_id": user_id,
            "username": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "language": user["language"],
        },
        "result": attempt_json(iq),
        "eq": {
            "completed": bool(eq),
            "result": attempt_json(eq),
        },
        "pq": {
            "completed": bool(pq),
            "result": attempt_json(pq),
        },
        "profile": {
            "unlocked": bool(
                iq and eq and pq
            ),
            "result": None,
        },
        "certificates": [
            {
                "code": row["code"],
                "type": row["certificate_type"],
                "score": (
                    float(row["score"])
                    if row["score"] is not None
                    else None
                ),
                "created_at": iso(
                    row["created_at"]
                ),
            }
            for row in certificates
        ],
    }


@app.get("/api/profile")
async def api_profile(
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    iq = await latest_attempt(
        user_id,
        "iq",
    )

    eq = await latest_attempt(
        user_id,
        "eq",
    )

    pq = await latest_attempt(
        user_id,
        "pq",
    )

    if not (iq and eq and pq):
        return {
            "unlocked": False,
            "profile": None,
        }

    iq_score = float(iq["score"])
    eq_score = float(eq["score"])
    pq_score = float(pq["score"])

    profile = {
        "iq_score": iq_score,
        "eq_score": eq_score,
        "pq_score": pq_score,
        "strengths": [
            "Tahliliy fikrlash",
            "Vaziyatni tizimli ko‘rish",
            "Patternlarni aniqlash",
        ],
        "development": [
            "Rejalashtirish",
            "E’tiborni boshqarish",
            "Deadline nazorati",
        ],
    }

    return {
        "unlocked": True,
        "profile": profile,
    }


# ============================================================
# LIVE COUNTER
# ============================================================

@app.get("/api/stats/live")
async def api_stats_live(
    user=__import__("fastapi").Depends(api_user),
):
    row = await db_fetchrow(
        """
        SELECT
            COUNT(*)::BIGINT AS total_users,
            COUNT(*) FILTER(
                WHERE last_active >
                    NOW() - INTERVAL '10 minutes'
            )::BIGINT AS online_users
        FROM users
        """
    )

    return {
        "total_users": int(
            row["total_users"]
        ),
        "online": int(
            row["online_users"]
        ),
        "live_users": int(
            row["online_users"]
        ),
        "active_users": int(
            row["online_users"]
        ),
    }


@app.get("/api/counter")
async def api_counter(
    user=__import__("fastapi").Depends(api_user),
):
    return await api_stats_live(user)


# ============================================================
# SESSION START
# ============================================================

@app.post("/api/session/start")
async def api_session_start(
    body: SessionStartRequest,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    if body.test_type not in {
        "iq",
        "eq",
        "pq",
    }:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri test turi.",
        )

    # Battle session requires battle access.
    if body.battle_id:
        battle = await get_battle(
            body.battle_id
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Battle topilmadi.",
            )

        player = await db_fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            body.battle_id,
            user_id,
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Siz bu battle ishtirokchisi emassiz.",
            )

        if not player["payment_approved"]:
            raise HTTPException(
                status_code=402,
                detail="Battle to‘lovi tasdiqlanmagan.",
            )

    else:
        product = body.test_type

        if body.test_type == "iq":
            latest = await latest_attempt(
                user_id,
                "iq",
            )

            if latest:
                product = "iq_retry"

        required = await product_access_required(
            user_id,
            product,
        )

        if required:
            payment = await create_payment(
                user_id,
                product,
            )

            raise HTTPException(
                status_code=402,
                detail=json_dumps({
                    "code": "PAYMENT_REQUIRED",
                    "product": product,
                    "payment_id": str(
                        payment["id"]
                    ) if payment else None,
                    "amount": int(
                        payment["amount"]
                    ) if payment else 0,
                }),
            )

    session_id = await create_session(
        user_id=user_id,
        test_type=body.test_type,
        battle_id=body.battle_id,
    )

    if body.battle_id:
        await db_execute(
            """
            UPDATE battle_players
            SET session_id = $3::uuid
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            body.battle_id,
            user_id,
            session_id,
        )

    return {
        "session_id": session_id,
        "test_type": body.test_type,
        "battle_id": body.battle_id,
    }


# ============================================================
# SESSION SYNC
# ============================================================

@app.post("/api/session/sync")
async def api_session_sync(
    body: SessionSyncRequest,
    user=__import__("fastapi").Depends(api_user),
):
    await sync_session(
        session_id=body.session_id,
        user_id=int(user["user_id"]),
        current=body.current,
        answers=body.answers,
        elapsed_seconds=body.elapsed_seconds,
    )

    return {
        "ok": True,
    }


# ============================================================
# TEST SUBMIT
# ============================================================

@app.post("/api/test/submit")
async def api_test_submit(
    body: TestFinishRequest,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    if body.test_type == "iq":
        result = await finish_session(
            user_id=user_id,
            session_id=body.session_id,
            answers=body.answers,
            elapsed_seconds=body.elapsed_seconds,
            battle_id=body.battle_id,
        )

        return result

    # EQ / PQ can be submitted without server-side
    # question text. Their scoring is server authoritative.
    if body.test_type not in {
        "eq",
        "pq",
    }:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri test turi.",
        )

    if not body.answers:
        raise HTTPException(
            status_code=400,
            detail="Javoblar bo‘sh.",
        )

    product = (
        "eq_retry"
        if body.test_type == "eq"
        else "pq_retry"
    )

    previous = await latest_attempt(
        user_id,
        body.test_type,
    )

    if previous:
        required = await product_access_required(
            user_id,
            product,
        )

        if required:
            payment = await create_payment(
                user_id,
                product,
            )

            raise HTTPException(
                status_code=402,
                detail=json_dumps({
                    "code": "PAYMENT_REQUIRED",
                    "product": product,
                    "payment_id": str(
                        payment["id"]
                    ) if payment else None,
                }),
            )

    score = calculate_psych_score(
        body.answers,
        len(body.answers),
    )

    import uuid

    attempt_id = str(uuid.uuid4())

    # Create a session if frontend didn't create one.
    session_id = body.session_id

    existing_session = await get_session(
        session_id,
        user_id,
    )

    if not existing_session:
        await db_execute(
            """
            INSERT INTO test_sessions(
                id,
                user_id,
                test_type,
                answers,
                elapsed_seconds,
                completed,
                finished_at
            )
            VALUES(
                $1::uuid,
                $2,
                $3,
                $4::jsonb,
                $5,
                TRUE,
                NOW()
            )
            """,
            session_id,
            user_id,
            body.test_type,
            json_dumps(body.answers),
            body.elapsed_seconds,
        )

    await db_execute(
        """
        INSERT INTO test_attempts(
            id,
            user_id,
            session_id,
            test_type,
            score,
            correct_answers,
            total_questions,
            elapsed_seconds,
            metrics,
            level
        )
        VALUES(
            $1::uuid,
            $2,
            $3::uuid,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9::jsonb,
            $10
        )
        """,
        attempt_id,
        user_id,
        session_id,
        body.test_type,
        score,
        0,
        len(body.answers),
        body.elapsed_seconds,
        json_dumps({
            "score": score,
        }),
        (
            "Yuqori"
            if score >= 75
            else "O‘rtacha"
        ),
    )

    await db_execute(
        """
        INSERT INTO results(
            user_id,
            attempt_id,
            test_type,
            score,
            data
        )
        VALUES(
            $1,
            $2::uuid,
            $3,
            $4,
            $5::jsonb
        )
        """,
        user_id,
        attempt_id,
        body.test_type,
        score,
        json_dumps({
            "score": score,
        }),
    )

    return {
        "attempt_id": attempt_id,
        "score": score,
        "level": (
            "Yuqori"
            if score >= 75
            else "O‘rtacha"
        ),
    }


# ============================================================
# RESULT
# ============================================================

@app.get("/api/result/{attempt_id}")
async def api_result(
    attempt_id: str,
    user=__import__("fastapi").Depends(api_user),
):
    row = await db_fetchrow(
        """
        SELECT *
        FROM test_attempts
        WHERE id = $1::uuid
          AND user_id = $2
        """,
        attempt_id,
        int(user["user_id"]),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Natija topilmadi.",
        )

    return await format_attempt_result(
        row
    )


# ============================================================
# PAYMENT CREATE
# ============================================================

@app.post("/api/payment/create")
async def api_payment_create(
    body: PaymentCreateRequest,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    allowed = {
        "iq",
        "iq_retry",
        "eq_retry",
        "pq_retry",
        "battle",
    }

    if body.product not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri mahsulot.",
        )

    payment = await create_payment(
        user_id=user_id,
        product=body.product,
        battle_id=body.battle_id,
    )

    if not payment:
        return {
            "payment_id": None,
            "status": "free",
            "amount": 0,
            "is_free": True,
        }

    card = await db_fetchrow(
        """
        SELECT *
        FROM payment_cards
        WHERE is_active = TRUE
        ORDER BY id DESC
        LIMIT 1
        """
    )

    return {
        "payment_id": str(payment["id"]),
        "id": str(payment["id"]),
        "product": payment["product"],
        "amount": int(payment["amount"]),
        "status": payment["status"],
        "card_number": (
            card["card_number"]
            if card
            else ""
        ),
        "click_number": (
            card["click_number"]
            if card
            else ""
        ),
    }


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.get("/api/payment/{payment_id}")
async def api_payment_status(
    payment_id: str,
    user=__import__("fastapi").Depends(api_user),
):
    row = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
          AND user_id = $2
        """,
        payment_id,
        int(user["user_id"]),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Payment topilmadi.",
        )

    return {
        "payment_id": str(row["id"]),
        "status": row["status"],
        "product": row["product"],
        "amount": int(row["amount"]),
        "battle_id": (
            str(row["battle_id"])
            if row["battle_id"]
            else None
        ),
    }


# ============================================================
# PAYMENT RECEIPT
# ============================================================

@app.post("/api/payment/receipt")
async def api_payment_receipt(
    payment_id: str,
    receipt: UploadFile = File(...),
    user=__import__("fastapi").Depends(api_user),
):
    row = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
          AND user_id = $2
        """,
        payment_id,
        int(user["user_id"]),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Payment topilmadi.",
        )

    if row["status"] in {
        "approved",
        "rejected",
    }:
        raise HTTPException(
            status_code=400,
            detail="Bu payment allaqachon yakunlangan.",
        )

    content = await receipt.read()

    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Chek 8 MB dan katta bo‘lmasligi kerak.",
        )

    filename = receipt.filename or "receipt"

    suffix = Path(filename).suffix.lower()

    allowed_suffixes = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".pdf",
    }

    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail="Chek formati qo‘llab-quvvatlanmaydi.",
        )

    safe_name = (
        f"{payment_id}"
        f"_{secrets.token_hex(4)}"
        f"{suffix}"
    )

    path = RECEIPT_DIR / safe_name
    path.write_bytes(content)

    await db_execute(
        """
        UPDATE payments
        SET
            status = 'pending_receipt',
            receipt_path = $2,
            receipt_filename = $3,
            submitted_at = NOW()
        WHERE id = $1::uuid
        """,
        payment_id,
        str(path),
        filename,
    )

    await notify_admin_payment(
        payment_id
    )

    return {
        "ok": True,
        "status": "pending_receipt",
        "message": "Chek admin tasdiqlashiga yuborildi.",
    }


# ============================================================
# CERTIFICATE API
# ============================================================

@app.get("/api/certificate/{code}")
async def api_certificate_verify(
    code: str,
):
    row = await db_fetchrow(
        """
        SELECT
            c.*,
            u.first_name,
            u.last_name,
            u.username
        FROM certificates c
        JOIN users u
          ON u.user_id = c.user_id
        WHERE c.code = $1
        """,
        code.strip().upper(),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Sertifikat topilmadi.",
        )

    return {
        "valid": True,
        "code": row["code"],
        "name": user_name_from_row(row),
        "score": (
            float(row["score"])
            if row["score"] is not None
            else None
        ),
        "type": row["certificate_type"],
        "date": iso(row["created_at"]),
    }


@app.get("/api/certificate")
async def api_certificate_file(
    attempt_id: Optional[str] = None,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    if attempt_id:
        attempt = await db_fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE id = $1::uuid
              AND user_id = $2
            """,
            attempt_id,
            user_id,
        )
    else:
        attempt = await latest_attempt(
            user_id,
            "iq",
        )

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="IQ natijasi topilmadi.",
        )

    certificate = await create_certificate(
        user_id=user_id,
        attempt_id=str(attempt["id"]),
        certificate_type="iq",
    )

    path = Path(
        certificate["file_path"]
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Sertifikat fayli topilmadi.",
        )

    return FileResponse(
        path,
        media_type="image/png",
        filename=path.name,
    )


@app.post("/api/certificate/request")
async def api_certificate_request(
    payload: dict,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    attempt_id = payload.get(
        "attempt_id"
    )

    if not attempt_id:
        attempt = await latest_attempt(
            user_id,
            "iq",
        )

        if not attempt:
            raise HTTPException(
                status_code=404,
                detail="Natija topilmadi.",
            )

        attempt_id = str(
            attempt["id"]
        )

    certificate = await create_certificate(
        user_id=user_id,
        attempt_id=attempt_id,
        certificate_type=payload.get(
            "certificate_type",
            "iq",
        ),
    )

    base = get_public_base_url()

    file_url = (
        f"{base}/api/certificate"
        f"?attempt_id={attempt_id}"
        if base
        else None
    )

    try:
        await bot.send_document(
            user_id,
            FSInputFile(
                certificate["file_path"]
            ),
            caption=(
                "📜 <b>Sertifikatingiz tayyor!</b>\n\n"
                f"🔑 <code>{certificate['code']}</code>\n"
                "🧠 IQ TEST BOT"
            ),
        )
    except Exception:
        logger.exception(
            "Certificate Telegram send failed"
        )

    return {
        "ok": True,
        "code": certificate["code"],
        "file_url": file_url,
        "message": (
            "Sertifikat Telegram botga yuborildi."
        ),
    }


# ============================================================
# BATTLE CREATE
# ============================================================

@app.post("/api/battle/create")
async def api_battle_create(
    body: BattleCreateRequest,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    # Reuse an existing waiting battle created by the user.
    existing = await db_fetchrow(
        """
        SELECT *
        FROM battles
        WHERE creator_user_id = $1
          AND status = 'waiting'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
    )

    if existing:
        return {
            "battle_id": str(existing["id"]),
            "id": str(existing["id"]),
            "code": existing["code"],
            "battle_code": existing["code"],
            "role": "creator",
            "status": existing["status"],
        }

    # Create battle first, then attach payment.
    import uuid

    battle_id = str(uuid.uuid4())
    code = generate_code()

    await db_execute(
        """
        INSERT INTO battles(
            id,
            code,
            creator_user_id,
            status
        )
        VALUES(
            $1::uuid,
            $2,
            $3,
            'waiting'
        )
        """,
        battle_id,
        code,
        user_id,
    )

    await db_execute(
        """
        INSERT INTO battle_players(
            battle_id,
            user_id,
            role
        )
        VALUES(
            $1::uuid,
            $2,
            'creator'
        )
        """,
        battle_id,
        user_id,
    )

    product = await get_product("battle")

    if product_is_free(product):
        await db_execute(
            """
            UPDATE battle_players
            SET payment_approved = TRUE
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            battle_id,
            user_id,
        )
    else:
        payment = await create_payment(
            user_id,
            "battle",
            battle_id,
        )

        await db_execute(
            """
            UPDATE battle_players
            SET payment_id = $3::uuid
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            battle_id,
            user_id,
            str(payment["id"]),
        )

    await update_battle_status(
        battle_id
    )

    battle = await get_battle(
        battle_id
    )

    return {
        "battle_id": battle_id,
        "id": battle_id,
        "code": code,
        "battle_code": code,
        "role": "creator",
        "status": battle["status"],
        "payment_required": not product_is_free(
            product
        ),
    }


# ============================================================
# BATTLE JOIN
# ============================================================

@app.post("/api/battle/join")
async def api_battle_join(
    body: BattleJoinRequest,
    user=__import__("fastapi").Depends(api_user),
):
    user_id = int(user["user_id"])

    code = body.code.strip().upper()

    battle = await db_fetchrow(
        """
        SELECT *
        FROM battles
        WHERE code = $1
        """,
        code,
    )

    if not battle:
        raise HTTPException(
            status_code=404,
            detail="Battle kodi topilmadi.",
        )

    if battle["creator_user_id"] == user_id:
        raise HTTPException(
            status_code=400,
            detail="O‘zingiz yaratgan battlega o‘zingiz qo‘shila olmaysiz.",
        )

    if battle["joiner_user_id"] and \
       battle["joiner_user_id"] != user_id:
        raise HTTPException(
            status_code=409,
            detail="Battle allaqachon to‘lgan.",
        )

    if battle["status"] == "finished":
        raise HTTPException(
            status_code=400,
            detail="Battle tugagan.",
        )

    await db_execute(
        """
        UPDATE battles
        SET joiner_user_id = $2
        WHERE id = $1::uuid
        """,
        str(battle["id"]),
        user_id,
    )

    player = await db_fetchrow(
        """
        SELECT *
        FROM battle_players
        WHERE battle_id = $1::uuid
          AND user_id = $2
        """,
        str(battle["id"]),
        user_id,
    )

    if not player:
        await db_execute(
            """
            INSERT INTO battle_players(
                battle_id,
                user_id,
                role
            )
            VALUES(
                $1::uuid,
                $2,
                'joiner'
            )
            """,
            str(battle["id"]),
            user_id,
        )

    product = await get_product("battle")

    if product_is_free(product):
        await db_execute(
            """
            UPDATE battle_players
            SET payment_approved = TRUE
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            str(battle["id"]),
            user_id,
        )
    else:
        payment = await create_payment(
            user_id,
            "battle",
            str(battle["id"]),
        )

        await db_execute(
            """
            UPDATE battle_players
            SET payment_id = $3::uuid
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            str(battle["id"]),
            user_id,
            str(payment["id"]),
        )

    await update_battle_status(
        str(battle["id"])
    )

    updated = await get_battle(
        str(battle["id"])
    )

    creator = await get_user(
        updated["creator_user_id"]
    )

    return {
        "battle_id": str(updated["id"]),
        "id": str(updated["id"]),
        "code": updated["code"],
        "role": "joiner",
        "status": updated["status"],
        "creator_name": (
            user_name_from_row(creator)
            if creator
            else None
        ),
        "payment_required": not product_is_free(
            product
        ),
    }


# ============================================================
# BATTLE GET
# ============================================================

@app.get("/api/battle/{battle_id}")
async def api_battle_get(
    battle_id: str,
    user=__import__("fastapi").Depends(api_user),
):
    return await battle_payload(
        battle_id,
        int(user["user_id"]),
    )


# ============================================================
# BATTLE FINISH
# ============================================================

@app.post("/api/battle/{battle_id}/finish")
async def api_battle_finish(
    battle_id: str,
    user=__import__("fastapi").Depends(api_user),
):
    payload = await battle_payload(
        battle_id,
        int(user["user_id"]),
    )

    if payload["status"] != "finished":
        return {
            **payload,
            "winner": None,
            "draw": False,
        }

    own_score = payload["own_score"]
    opponent_score = payload["opponent_score"]

    winner = None

    if own_score > opponent_score:
        winner = "you"
    elif opponent_score > own_score:
        winner = "opponent"

    return {
        **payload,
        "winner": winner,
        "draw": winner is None,
    }


# ============================================================
# ADMIN API
# ============================================================

@app.get("/api/admin/products")
async def admin_products(
    user=__import__("fastapi").Depends(api_user),
):
    await require_admin(
        int(user["user_id"])
    )

    rows = await get_products()

    return [
        {
            "product": row["product_key"],
            "title": row["title"],
            "price": int(row["price"]),
            "is_free": product_is_free(row),
            "enabled": bool(row["enabled"]),
            "free_until": iso(
                row["free_until"]
            ),
        }
        for row in rows
    ]


@app.post("/api/admin/products")
async def admin_update_product(
    body: AdminPriceRequest,
    user=__import__("fastapi").Depends(api_user),
):
    await require_admin(
        int(user["user_id"])
    )

    if body.product not in DEFAULT_PRODUCTS:
        raise HTTPException(
            status_code=400,
            detail="Mahsulot topilmadi.",
        )

    free_until = None

    if body.free_until:
        try:
            free_until = datetime.fromisoformat(
                body.free_until.replace(
                    "Z",
                    "+00:00",
                )
            )
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="free_until formati noto‘g‘ri.",
            )

    await db_execute(
        """
        UPDATE products
        SET
            price = $2,
            is_free = $3,
            free_until = $4,
            enabled = $5,
            updated_at = NOW()
        WHERE product_key = $1
        """,
        body.product,
        max(0, int(body.price)),
        bool(body.is_free),
        free_until,
        bool(body.enabled),
    )

    return {
        "ok": True,
        "product": body.product,
    }


@app.get("/api/admin/stats")
async def admin_stats(
    user=__import__("fastapi").Depends(api_user),
):
    await require_admin(
        int(user["user_id"])
    )

    row = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS users,
            COUNT(*) FILTER(
                WHERE created_at >= CURRENT_DATE
            ) AS today
        FROM users
        """
    )

    iq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type = 'iq'
        """
    )

    eq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type = 'eq'
        """
    )

    pq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type = 'pq'
        """
    )

    payments = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS count,
            COALESCE(
                SUM(amount)
                FILTER(WHERE status = 'approved'),
                0
            ) AS revenue
        FROM payments
        """
    )

    battles = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM battles
        """
    )

    paying = await db_fetchrow(
        """
        SELECT COUNT(DISTINCT user_id) AS count
        FROM payments
        WHERE status = 'approved'
        """
    )

    return {
        "users": int(row["users"]),
        "today": int(row["today"]),
        "iq": int(iq["count"]),
        "eq": int(eq["count"]),
        "pq": int(pq["count"]),
        "payments": int(payments["count"]),
        "revenue": int(payments["revenue"]),
        "battles": int(battles["count"]),
        "paying_users": int(paying["count"]),
    }


@app.get("/api/admin/payments")
async def admin_payments(
    user=__import__("fastapi").Depends(api_user),
    status: str = "pending_receipt",
):
    await require_admin(
        int(user["user_id"])
    )

    rows = await db_fetch(
        """
        SELECT
            p.*,
            u.username,
            u.first_name,
            u.last_name
        FROM payments p
        JOIN users u
          ON u.user_id = p.user_id
        WHERE p.status = $1
        ORDER BY p.created_at DESC
        LIMIT 100
        """,
        status,
    )

    return [
        {
            "id": str(row["id"]),
            "user_id": row["user_id"],
            "username": row["username"],
            "name": user_name_from_row(row),
            "product": row["product"],
            "amount": int(row["amount"]),
            "status": row["status"],
            "receipt": row["receipt_path"],
            "created_at": iso(
                row["created_at"]
            ),
        }
        for row in rows
    ]


# ============================================================
# ADMIN RECEIPT FILE
# ============================================================

@app.get("/api/admin/payment/{payment_id}/receipt")
async def admin_payment_receipt(
    payment_id: str,
    user=__import__("fastapi").Depends(api_user),
):
    await require_admin(
        int(user["user_id"])
    )

    row = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )

    if not row or not row["receipt_path"]:
        raise HTTPException(
            status_code=404,
            detail="Chek topilmadi.",
        )

    path = Path(
        row["receipt_path"]
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Chek fayli topilmadi.",
        )

    return FileResponse(
        path,
        filename=row["receipt_filename"] or path.name,
    )


# ============================================================
# ADMIN PAYMENT ACTION
# ============================================================

async def approve_payment(
    payment_id: str,
):
    payment = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )

    if not payment:
        return None

    if payment["status"] == "approved":
        return payment

    await db_execute(
        """
        UPDATE payments
        SET
            status = 'approved',
            approved_at = NOW()
        WHERE id = $1::uuid
        """,
        payment_id,
    )

    # Battle player unlock.
    if payment["battle_id"]:
        await db_execute(
            """
            UPDATE battle_players
            SET payment_approved = TRUE
            WHERE battle_id = $1::uuid
              AND user_id = $2
            """,
            str(payment["battle_id"]),
            payment["user_id"],
        )

        await update_battle_status(
            str(payment["battle_id"])
        )

    return await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )


async def reject_payment(
    payment_id: str,
):
    await db_execute(
        """
        UPDATE payments
        SET
            status = 'rejected'
        WHERE id = $1::uuid
          AND status NOT IN(
              'approved',
              'rejected'
          )
        """,
        payment_id,
    )

    return await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )


# ============================================================
# RANKING
# ============================================================

async def ranking_rows(limit: int = 50):
    return await db_fetch(
        """
        SELECT
            a.user_id,
            MAX(a.score) AS score,
            u.first_name,
            u.last_name,
            u.username
        FROM test_attempts a
        JOIN users u
          ON u.user_id = a.user_id
        WHERE a.test_type = 'iq'
        GROUP BY
            a.user_id,
            u.first_name,
            u.last_name,
            u.username
        ORDER BY score DESC
        LIMIT $1
        """,
        limit,
    )


# ============================================================
# TELEGRAM KEYBOARDS
# ============================================================

def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O‘zbekcha",
                    callback_data="lang:uz",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang:ru",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang:en",
                )
            ],
        ]
    )


def main_keyboard():
    webapp_url = WEBAPP_URL or ""

    rows = []

    if webapp_url:
        rows.append(
            [
                KeyboardButton(
                    text="🧠 IQ · EQ · PQ testini ishlash",
                    web_app={
                        "url": webapp_url
                    },
                )
            ]
        )
    else:
        rows.append(
            [
                KeyboardButton(
                    text="🧠 IQ · EQ · PQ testini ishlash"
                )
            ]
        )

    rows.extend(
        [
            [
                KeyboardButton(
                    text="📜 Sertifikatim"
                ),
                KeyboardButton(
                    text="🏆 Reyting"
                ),
            ],
            [
                KeyboardButton(
                    text="💰 Pul ishlash"
                ),
                KeyboardButton(
                    text="ℹ️ Narx va yordam"
                ),
            ],
            [
                KeyboardButton(
                    text="🌐 Til"
                )
            ],
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Users",
                    callback_data="admin:users",
                ),
                InlineKeyboardButton(
                    text="📊 Statistics",
                    callback_data="admin:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💳 Payments",
                    callback_data="admin:payments",
                ),
                InlineKeyboardButton(
                    text="💰 Products",
                    callback_data="admin:products",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="admin:broadcast",
                ),
                InlineKeyboardButton(
                    text="🏆 Ranking",
                    callback_data="admin:ranking",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 Certificates",
                    callback_data="admin:certificates",
                ),
                InlineKeyboardButton(
                    text="⚔️ Battles",
                    callback_data="admin:battles",
                ),
            ],
        ]
    )


def product_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧠 IQ",
                    callback_data="product:iq",
                ),
                InlineKeyboardButton(
                    text="🔁 IQ RETRY",
                    callback_data="product:iq_retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎭 EQ RETRY",
                    callback_data="product:eq_retry",
                ),
                InlineKeyboardButton(
                    text="⏳ PQ RETRY",
                    callback_data="product:pq_retry",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚔️ BATTLE",
                    callback_data="product:battle",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Admin",
                    callback_data="admin:back",
                )
            ],
        ]
    )


def product_edit_keyboard(product: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Narx belgilash",
                    callback_data=f"product_price:{product}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆓 BEPUL qilish",
                    callback_data=f"product_free:{product}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 PAID qilish",
                    callback_data=f"product_paid:{product}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏱ Free muddat",
                    callback_data=f"product_until:{product}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Narxlar",
                    callback_data="admin:products",
                )
            ],
        ]
    )


# ============================================================
# FSM
# ============================================================

class AdminStates(StatesGroup):
    waiting_price = State()
    waiting_free_until = State()
    waiting_broadcast_text = State()
    waiting_user_message = State()


# ============================================================
# TELEGRAM START / LANGUAGE
# ============================================================

@dp.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await upsert_user(
        message.from_user
    )

    row = await get_user(
        message.from_user.id
    )

    if not row or not row["language"]:
        await message.answer(
            "🌐 <b>Tilni tanlang</b>\n\n"
            "Tilni tanlang:",
            reply_markup=language_keyboard(),
        )

        return

    await send_welcome(
        message,
        row["language"],
    )


async def send_welcome(
    message: Message,
    language: str = "uz",
):
    # Final UI branding is always IQ TEST BOT.
    await message.answer(
        f"👋 Salom, "
        f"<b>{escape_tg(message.from_user.first_name or 'do‘st')}</b>!\n\n"
        "🧠 <b>IQ TEST BOT</b>\n"
        "IQ, EQ va prokrastinatsiya testlarini\n"
        "ishlang, natijangizni bilib oling va\n"
        "shaxsiy profilingizni oching.\n\n"
        "👇 Boshlash uchun tugmani bosing",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(
    callback: CallbackQuery,
):
    language = callback.data.split(":", 1)[1]

    if language not in {
        "uz",
        "ru",
        "en",
    }:
        await callback.answer(
            "Noto‘g‘ri til.",
            show_alert=True,
        )
        return

    await save_language(
        callback.from_user.id,
        language,
    )

    await callback.answer(
        "Til saqlandi."
    )

    if callback.message:
        await callback.message.edit_text(
            "✅ Til saqlandi.\n\n"
            "🧠 <b>IQ TEST BOT</b>\n"
            "Endi testni boshlashingiz mumkin."
        )

        await callback.message.answer(
            "👇 Menyu:",
            reply_markup=main_keyboard(),
        )


@dp.message(F.text == "🌐 Til")
async def language_menu(
    message: Message,
):
    await message.answer(
        "🌐 <b>Tilni tanlang</b>",
        reply_markup=language_keyboard(),
    )


# ============================================================
# TELEGRAM CERTIFICATE
# ============================================================

@dp.message(F.text == "📜 Sertifikatim")
async def my_certificate(
    message: Message,
):
    row = await latest_attempt(
        message.from_user.id,
        "iq",
    )

    if not row:
        await message.answer(
            "📜 Hali sertifikatingiz yo‘q.\n\n"
            "Avval IQ testini yakunlang."
        )
        return

    try:
        certificate = await create_certificate(
            message.from_user.id,
            str(row["id"]),
            "iq",
        )

        await message.answer_document(
            FSInputFile(
                certificate["file_path"]
            ),
            caption=(
                "📜 <b>Sertifikatingiz</b>\n\n"
                f"🧠 IQ-style Score: "
                f"<b>{int(float(row['score']))}</b>\n"
                f"🔑 <code>{certificate['code']}</code>"
            ),
        )

    except Exception:
        logger.exception(
            "Certificate sending failed"
        )

        await message.answer(
            "❌ Sertifikat yaratishda xatolik yuz berdi."
        )


# ============================================================
# CERTIFICATE CODE SEARCH
# ============================================================

@dp.message(
    F.text.regexp(
        r"^IQ-[A-Za-z0-9]{6}$"
    )
)
async def verify_certificate_message(
    message: Message,
):
    code = message.text.strip().upper()

    row = await db_fetchrow(
        """
        SELECT
            c.*,
            u.first_name,
            u.last_name,
            u.username
        FROM certificates c
        JOIN users u
          ON u.user_id = c.user_id
        WHERE c.code = $1
        """,
        code,
    )

    if not row:
        await message.answer(
            "❌ <b>Sertifikat topilmadi.</b>\n\n"
            "Kod noto‘g‘ri yoki mavjud emas."
        )
        return

    await message.answer(
        "✅ <b>Sertifikat topildi</b>\n\n"
        f"👤 {escape_tg(user_name_from_row(row))}\n"
        f"🧠 IQ-style Score: "
        f"<b>{int(float(row['score'] or 0))}</b>\n"
        f"📅 {row['created_at'].strftime('%d.%m.%Y')}\n"
        f"🔑 <code>{row['code']}</code>"
    )


# ============================================================
# RANKING
# ============================================================

@dp.message(F.text == "🏆 Reyting")
async def ranking_message(
    message: Message,
):
    rows = await ranking_rows(20)

    if not rows:
        await message.answer(
            "🏆 Hali reyting bo‘sh."
        )
        return

    lines = [
        "🏆 <b>IQ TEST BOT — REYTING</b>",
        "",
    ]

    medals = [
        "🥇",
        "🥈",
        "🥉",
    ]

    for index, row in enumerate(rows):
        medal = (
            medals[index]
            if index < 3
            else f"{index + 1}."
        )

        name = user_name_from_row(row)

        lines.append(
            f"{medal} "
            f"{escape_tg(name)} — "
            f"<b>{int(float(row['score']))}</b>"
        )

    await message.answer(
        "\n".join(lines)
    )


# ============================================================
# PRICE / HELP
# ============================================================

@dp.message(F.text == "ℹ️ Narx va yordam")
async def price_help(
    message: Message,
):
    rows = await get_products()

    values = {
        row["product_key"]: (
            "tekin"
            if product_is_free(row)
            else f"{int(row['price']):,} so‘m"
        )
        for row in rows
    }

    await message.answer(
        "ℹ️ <b>NARX VA YORDAM</b>\n\n"
        f"🧠 IQ test — {values.get('iq', '—')}\n"
        "🎭 EQ — IQ dan keyin ochiladi\n"
        "⏳ Prokrastinatsiya — EQ dan keyin ochiladi\n"
        "⭐ To‘liq tahlil — uchalasidan keyin\n\n"
        f"🔄 IQ qayta — {values.get('iq_retry', '—')}\n"
        f"🔄 EQ qayta — {values.get('eq_retry', '—')}\n"
        f"🔄 PQ qayta — {values.get('pq_retry', '—')}\n"
        f"⚔️ Battle — {values.get('battle', '—')} / ishtirokchi\n\n"
        "💳 To‘lov Click yoki karta orqali\n"
        "⏱ To‘lov admin tasdiqlashidan keyin ochiladi\n"
        "📜 Sertifikat Telegram orqali yuboriladi\n\n"
        "👤 <b>QO‘LLAB-QUVVATLASH</b>\n"
        "@omono_v"
    )


# ============================================================
# REFERRAL / MONEY
# ============================================================

@dp.message(F.text == "💰 Pul ishlash")
async def referral_message(
    message: Message,
):
    user_id = message.from_user.id

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{user_id}"
    )

    count = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM referrals
        WHERE referrer_user_id = $1
        """,
        user_id,
    )

    await message.answer(
        "💰 <b>PUL ISHLASH</b>\n\n"
        "Do‘stlaringizni IQ TEST BOT'ga taklif qiling.\n\n"
        f"👥 Taklif qilganlaringiz: "
        f"<b>{int(count['count'])}</b>\n\n"
        f"🔗 <code>{link}</code>\n\n"
        "Linkni do‘stlaringizga yuboring."
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message,
):
    if not await is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        "👑 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN CALLBACKS
# ============================================================

@dp.callback_query(F.data == "admin:back")
async def admin_back(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "👑 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


@dp.callback_query(F.data == "admin:stats")
async def admin_stats_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    row = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS users,
            COUNT(*) FILTER(
                WHERE created_at >= CURRENT_DATE
            ) AS today
        FROM users
        """
    )

    iq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type='iq'
        """
    )

    eq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type='eq'
        """
    )

    pq = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM test_attempts
        WHERE test_type='pq'
        """
    )

    payments = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS count,
            COALESCE(
                SUM(amount)
                FILTER(WHERE status='approved'),
                0
            ) AS revenue
        FROM payments
        """
    )

    battles = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM battles
        """
    )

    await callback.message.edit_text(
        "📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <b>{int(row['users'])}</b>\n"
        f"📅 Today: <b>{int(row['today'])}</b>\n\n"
        f"🧠 IQ: <b>{int(iq['count'])}</b>\n"
        f"🎭 EQ: <b>{int(eq['count'])}</b>\n"
        f"⏳ PQ: <b>{int(pq['count'])}</b>\n\n"
        f"💳 Payments: <b>{int(payments['count'])}</b>\n"
        f"💰 Revenue: <b>{int(payments['revenue']):,} so‘m</b>\n"
        f"⚔️ Battles: <b>{int(battles['count'])}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN PRODUCTS
# ============================================================

@dp.callback_query(F.data == "admin:products")
async def admin_products_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    rows = await get_products()

    lines = [
        "💰 <b>PRODUCTS</b>",
        "",
    ]

    for row in rows:
        status = (
            "🆓 BEPUL"
            if product_is_free(row)
            else f"💵 {int(row['price']):,} so‘m"
        )

        lines.append(
            f"{row['title']} — {status}"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=product_admin_keyboard(),
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("product:")
)
async def product_open_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    product = callback.data.split(
        ":",
        1,
    )[1]

    if product == "back":
        await admin_back(callback)
        return

    row = await get_product(product)

    if not row:
        await callback.answer(
            "Mahsulot topilmadi.",
            show_alert=True,
        )
        return

    status = (
        "🆓 BEPUL"
        if product_is_free(row)
        else "💳 PAID"
    )

    free_until = (
        row["free_until"].strftime(
            "%d.%m.%Y %H:%M"
        )
        if row["free_until"]
        else "yo‘q"
    )

    await callback.message.edit_text(
        "💰 <b>MAHSULOT SOZLAMALARI</b>\n\n"
        f"📦 {escape_tg(row['title'])}\n"
        f"💵 Narx: <b>{int(row['price']):,} so‘m</b>\n"
        f"📌 Holat: <b>{status}</b>\n"
        f"⏱ Free until: <b>{free_until}</b>\n\n"
        "Har bir mahsulot alohida boshqariladi.",
        reply_markup=product_edit_keyboard(
            product
        ),
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("product_price:")
)
async def product_price_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    product = callback.data.split(
        ":",
        1,
    )[1]

    await state.set_state(
        AdminStates.waiting_price
    )

    await state.update_data(
        product=product
    )

    await callback.message.answer(
        f"💰 <b>{escape_tg(product)}</b>\n\n"
        "Yangi narxni so‘mda yuboring.\n\n"
        "Masalan:\n"
        "<code>15000</code>"
    )

    await callback.answer()


@dp.message(AdminStates.waiting_price)
async def admin_set_price(
    message: Message,
    state: FSMContext,
):
    if not await is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    data = await state.get_data()

    product = data.get("product")

    try:
        price = int(
            message.text.strip()
        )
    except Exception:
        await message.answer(
            "❌ Faqat raqam yuboring.\n"
            "Masalan: <code>15000</code>"
        )
        return

    if price < 0:
        await message.answer(
            "❌ Narx manfiy bo‘lishi mumkin emas."
        )
        return

    await db_execute(
        """
        UPDATE products
        SET
            price = $2,
            is_free = FALSE,
            enabled = TRUE,
            updated_at = NOW()
        WHERE product_key = $1
        """,
        product,
        price,
    )

    await state.clear()

    await message.answer(
        f"✅ <b>{escape_tg(product)}</b>\n"
        f"narxi <b>{price:,} so‘m</b> qilib belgilandi.",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(
    F.data.startswith("product_free:")
)
async def product_free_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    product = callback.data.split(
        ":",
        1,
    )[1]

    await db_execute(
        """
        UPDATE products
        SET
            is_free = TRUE,
            enabled = TRUE,
            updated_at = NOW()
        WHERE product_key = $1
        """,
        product,
    )

    await callback.answer(
        "Mahsulot BEPUL qilindi."
    )

    row = await get_product(
        product
    )

    await callback.message.edit_text(
        f"💰 <b>{escape_tg(row['title'])}</b>\n\n"
        "🆓 <b>HOZIR BEPUL</b>\n\n"
        "Bu mahsulot uchun to‘lov talab qilinmaydi.",
        reply_markup=product_edit_keyboard(
            product
        ),
    )


@dp.callback_query(
    F.data.startswith("product_paid:")
)
async def product_paid_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    product = callback.data.split(
        ":",
        1,
    )[1]

    await db_execute(
        """
        UPDATE products
        SET
            is_free = FALSE,
            enabled = TRUE,
            free_until = NULL,
            updated_at = NOW()
        WHERE product_key = $1
        """,
        product,
    )

    row = await get_product(
        product
    )

    await callback.answer(
        "PAID rejim yoqildi."
    )

    await callback.message.edit_text(
        f"💰 <b>{escape_tg(row['title'])}</b>\n\n"
        f"💳 PAID\n"
        f"💵 {int(row['price']):,} so‘m",
        reply_markup=product_edit_keyboard(
            product
        ),
    )


@dp.callback_query(
    F.data.startswith("product_until:")
)
async def product_until_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    product = callback.data.split(
        ":",
        1,
    )[1]

    await state.set_state(
        AdminStates.waiting_free_until
    )

    await state.update_data(
        product=product
    )

    await callback.message.answer(
        "⏱ <b>FREE UNTIL</b>\n\n"
        "UTC vaqtini yuboring:\n"
        "<code>30.09.2026 23:59</code>\n\n"
        "Shu vaqtgacha mahsulot bepul bo‘ladi."
    )

    await callback.answer()


@dp.message(
    AdminStates.waiting_free_until
)
async def admin_set_free_until(
    message: Message,
    state: FSMContext,
):
    if not await is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    data = await state.get_data()

    product = data.get("product")

    try:
        value = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y %H:%M",
        ).replace(
            tzinfo=timezone.utc
        )
    except Exception:
        await message.answer(
            "❌ Format noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>30.09.2026 23:59</code>"
        )
        return

    await db_execute(
        """
        UPDATE products
        SET
            is_free = TRUE,
            free_until = $2,
            enabled = TRUE,
            updated_at = NOW()
        WHERE product_key = $1
        """,
        product,
        value,
    )

    await state.clear()

    await message.answer(
        f"✅ <b>{escape_tg(product)}</b>\n"
        f"{value.strftime('%d.%m.%Y %H:%M')} UTC gacha BEPUL.",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN PAYMENTS
# ============================================================

@dp.callback_query(F.data == "admin:payments")
async def admin_payments_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    rows = await db_fetch(
        """
        SELECT
            p.*,
            u.username,
            u.first_name,
            u.last_name
        FROM payments p
        JOIN users u
          ON u.user_id = p.user_id
        WHERE p.status IN(
            'pending',
            'pending_receipt'
        )
        ORDER BY p.created_at DESC
        LIMIT 20
        """
    )

    if not rows:
        text = (
            "💳 <b>PAYMENTS</b>\n\n"
            "Hozir pending payment yo‘q."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )

        await callback.answer()
        return

    for row in rows:
        caption = (
            "💳 <b>PAYMENT</b>\n\n"
            f"👤 {escape_tg(user_name_from_row(row))}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"📦 {escape_tg(row['product'])}\n"
            f"💰 {int(row['amount']):,} so‘m\n"
            f"📅 {row['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"🧾 <code>{row['id']}</code>"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📎 Chek",
                        callback_data=f"pay_receipt:{row['id']}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ TASDIQLASH",
                        callback_data=f"pay_approve:{row['id']}",
                    ),
                    InlineKeyboardButton(
                        text="❌ RAD ETISH",
                        callback_data=f"pay_reject:{row['id']}",
                    ),
                ],
            ]
        )

        await callback.message.answer(
            caption,
            reply_markup=keyboard,
        )

    await callback.message.answer(
        "💳 Payment queue.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("pay_receipt:")
)
async def payment_receipt_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    payment_id = callback.data.split(
        ":",
        1,
    )[1]

    row = await db_fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id = $1::uuid
        """,
        payment_id,
    )

    if not row or not row["receipt_path"]:
        await callback.answer(
            "Chek hali yuborilmagan.",
            show_alert=True,
        )
        return

    path = Path(
        row["receipt_path"]
    )

    if not path.exists():
        await callback.answer(
            "Chek fayli topilmadi.",
            show_alert=True,
        )
        return

    await callback.message.answer_document(
        FSInputFile(path),
        caption=(
            f"🧾 Payment: <code>{payment_id}</code>"
        ),
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith("pay_approve:")
)
async def payment_approve_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    payment_id = callback.data.split(
        ":",
        1,
    )[1]

    row = await approve_payment(
        payment_id
    )

    if not row:
        await callback.answer(
            "Payment topilmadi.",
            show_alert=True,
        )
        return

    try:
        await bot.send_message(
            row["user_id"],
            "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
            f"📦 {escape_tg(row['product'])}\n"
            f"💰 {int(row['amount']):,} so‘m\n\n"
            "Funksiya endi ochildi.",
        )
    except Exception:
        logger.exception(
            "Payment approval user notification failed"
        )

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer(
        "To‘lov tasdiqlandi."
    )


@dp.callback_query(
    F.data.startswith("pay_reject:")
)
async def payment_reject_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    payment_id = callback.data.split(
        ":",
        1,
    )[1]

    row = await reject_payment(
        payment_id
    )

    if not row:
        await callback.answer(
            "Payment topilmadi.",
            show_alert=True,
        )
        return

    try:
        await bot.send_message(
            row["user_id"],
            "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
            "Chekni tekshirib, kerak bo‘lsa qayta yuboring.",
        )
    except Exception:
        logger.exception(
            "Payment rejection notification failed"
        )

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer(
        "To‘lov rad etildi."
    )


# ============================================================
# ADMIN USERS
# ============================================================

@dp.callback_query(F.data == "admin:users")
async def admin_users_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    row = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER(
                WHERE last_active >
                    NOW() - INTERVAL '10 minutes'
            ) AS active
        FROM users
        """
    )

    await callback.message.edit_text(
        "👥 <b>USERS</b>\n\n"
        f"Total: <b>{int(row['total'])}</b>\n"
        f"Active: <b>{int(row['active'])}</b>\n\n"
        "User qidirish va to‘liq profil boshqaruvi "
        "keyingi admin qatlamida ishlatiladi.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN RANKING
# ============================================================

@dp.callback_query(F.data == "admin:ranking")
async def admin_ranking_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    rows = await ranking_rows(20)

    lines = [
        "🏆 <b>ADMIN RANKING</b>",
        "",
    ]

    for index, row in enumerate(rows):
        lines.append(
            f"{index + 1}. "
            f"{escape_tg(user_name_from_row(row))} — "
            f"<b>{int(float(row['score']))}</b>"
        )

    if len(lines) == 2:
        lines.append(
            "Hali ma’lumot yo‘q."
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN CERTIFICATES
# ============================================================

@dp.callback_query(F.data == "admin:certificates")
async def admin_certificates_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    row = await db_fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM certificates
        """
    )

    await callback.message.edit_text(
        "📜 <b>CERTIFICATES</b>\n\n"
        f"Jami sertifikatlar: "
        f"<b>{int(row['count'])}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN BATTLES
# ============================================================

@dp.callback_query(F.data == "admin:battles")
async def admin_battles_callback(
    callback: CallbackQuery,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    row = await db_fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER(
                WHERE status = 'finished'
            ) AS finished,
            COUNT(*) FILTER(
                WHERE status IN('waiting','ready')
            ) AS active
        FROM battles
        """
    )

    await callback.message.edit_text(
        "⚔️ <b>BATTLES</b>\n\n"
        f"Total: <b>{int(row['total'])}</b>\n"
        f"Active: <b>{int(row['active'])}</b>\n"
        f"Finished: <b>{int(row['finished'])}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="admin:back",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN BROADCAST
# ============================================================

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    await state.set_state(
        AdminStates.waiting_broadcast_text
    )

    await callback.message.answer(
        "📢 <b>BROADCAST</b>\n\n"
        "Xabar matnini yuboring.\n\n"
        "Keyin qaysi guruhga yuborishni tanlaysiz."
    )

    await callback.answer()


@dp.message(
    AdminStates.waiting_broadcast_text
)
async def admin_broadcast_text(
    message: Message,
    state: FSMContext,
):
    if not await is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    text = message.text or ""

    if not text.strip():
        await message.answer(
            "❌ Bo‘sh xabar yubormang."
        )
        return

    await state.update_data(
        broadcast_text=text
    )

    await state.set_state(None)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Hammaga",
                    callback_data="broadcast:all",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Sotib olganlarga",
                    callback_data="broadcast:buyers",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="broadcast:cancel",
                )
            ],
        ]
    )

    await message.answer(
        "📢 Qaysi auditoriyaga yuborilsin?",
        reply_markup=keyboard,
    )


@dp.callback_query(
    F.data.startswith("broadcast:")
)
async def broadcast_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    action = callback.data.split(
        ":",
        1,
    )[1]

    if action == "cancel":
        await state.clear()

        await callback.message.answer(
            "❌ Broadcast bekor qilindi.",
            reply_markup=admin_keyboard(),
        )

        await callback.answer()
        return

    data = await state.get_data()

    text = data.get(
        "broadcast_text"
    )

    if not text:
        await callback.answer(
            "Broadcast matni topilmadi.",
            show_alert=True,
        )
        return

    if action == "all":
        users = await db_fetch(
            """
            SELECT user_id
            FROM users
            WHERE is_blocked = FALSE
            """
        )

    elif action == "buyers":
        users = await db_fetch(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            JOIN payments p
              ON p.user_id = u.user_id
            WHERE u.is_blocked = FALSE
              AND p.status = 'approved'
            """
        )

    else:
        await callback.answer(
            "Noto‘g‘ri auditoriya.",
            show_alert=True,
        )
        return

    await callback.message.answer(
        f"📢 Broadcast boshlandi.\n"
        f"👥 Auditoriya: <b>{len(users)}</b>"
    )

    sent = 0

    for user in users:
        try:
            await bot.send_message(
                user["user_id"],
                text,
            )

            sent += 1

        except Exception:
            await db_execute(
                """
                UPDATE users
                SET is_blocked = TRUE
                WHERE user_id = $1
                """,
                user["user_id"],
            )

        await asyncio.sleep(
            0.04
        )

    await db_execute(
        """
        INSERT INTO broadcast_logs(
            admin_user_id,
            target_type,
            total_count,
            sent_count
        )
        VALUES(
            $1,
            $2,
            $3,
            $4
        )
        """,
        callback.from_user.id,
        action,
        len(users),
        sent,
    )

    await state.clear()

    await callback.message.answer(
        "✅ <b>BROADCAST TUGADI</b>\n\n"
        f"📨 Yuborildi: <b>{sent}</b>\n"
        f"👥 Jami: <b>{len(users)}</b>",
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


# ============================================================
# ADMIN FALLBACK
# ============================================================

@dp.message()
async def generic_message(
    message: Message,
):
    text = message.text or ""

    if text == "🧠 IQ · EQ · PQ testini ishlash":
        if WEBAPP_URL:
            await message.answer(
                "🧠 <b>IQ TEST BOT</b>\n\n"
                "👇 Testni boshlash uchun Mini App tugmasidan foydalaning.",
                reply_markup=main_keyboard(),
            )
        else:
            await message.answer(
                "⚠️ Mini App URL hali sozlanmagan."
            )


# ============================================================
# WEBHOOK
# ============================================================

@app.post("/telegram/webhook")
async def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: Optional[str] = Header(
        default=None,
    ),
):
    if WEBHOOK_SECRET:
        if (
            x_telegram_bot_api_secret_token
            != WEBHOOK_SECRET
        ):
            raise HTTPException(
                status_code=403,
                detail="Invalid webhook secret.",
            )

    try:
        telegram_update = Update.model_validate(
            update
        )

        await dp.feed_update(
            bot,
            telegram_update,
        )

        return {
            "ok": True
        }

    except Exception as error:
        logger.exception(
            "Webhook processing error"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(error),
            },
        )


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():
    logger.info(
        "Starting IQ TEST BOT..."
    )

    await init_db()

    # Remove any old webhook before setting the final one.
    try:
        await bot.delete_webhook(
            drop_pending_updates=False
        )
    except Exception:
        logger.exception(
            "Could not delete previous webhook"
        )

    url = webhook_url()

    if url:
        await bot.set_webhook(
            url=url,
            secret_token=(
                WEBHOOK_SECRET
                if WEBHOOK_SECRET
                else None
            ),
            drop_pending_updates=False,
            allowed_updates=dp.resolve_used_update_types(),
        )

        logger.info(
            "Webhook configured: %s",
            url,
        )
    else:
        logger.warning(
            "PUBLIC_BASE_URL/WEBAPP_URL not configured. "
            "Webhook was not configured."
        )

    logger.info(
        "IQ TEST BOT started."
    )


@app.on_event("shutdown")
async def shutdown():
    global pool

    try:
        await bot.delete_webhook(
            drop_pending_updates=False
        )
    except Exception:
        logger.exception(
            "Webhook cleanup failed"
        )

    try:
        await bot.session.close()
    except Exception:
        pass

    if pool:
        await pool.close()
        pool = None


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
    )