# ============================================================
# IQ TEST BOT
# bot.py
# ============================================================

import asyncio
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
import uvicorn

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
WEBAPP_URL = os.environ.get("WEBAPP_URL")

PORT = int(os.environ.get("PORT", "10000"))

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "omono_v"
).lstrip("@").lower()

ADMIN_USER_ID = int(
    os.environ.get("ADMIN_USER_ID", "0") or 0
)

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is missing")

if not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("WEBAPP_URL must start with https://")

if not WEBAPP_DIR.exists():
    raise RuntimeError(
        f"Missing webapp directory: {WEBAPP_DIR}"
    )


# ============================================================
# QUIZ
# ============================================================

QUESTIONS_COUNT = 18

QUIZ_VERSION = 5

# A=0 B=1 C=2 D=3
#
# This is the authoritative server-side answer key.
# Browser never sends a score.
CORRECT_ANSWERS = (
    1,
    2,
    0,
    2,
    2,
    1,
    0,
    0,
    2,
    2,
    1,
    2,
    1,
    2,
    3,
    1,
    2,
    2,
)

WEIGHTS = (
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    3,
    3,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
)

MAX_RAW = sum(WEIGHTS)


# ============================================================
# PAYMENT MODES
# ============================================================

PAYMENT_MODE_RETEST = "first_free_retest_paid"
PAYMENT_MODE_RESULT = "result_paid"
PAYMENT_MODE_FREE = "all_free"

VALID_PAYMENT_MODES = {
    PAYMENT_MODE_RETEST,
    PAYMENT_MODE_RESULT,
    PAYMENT_MODE_FREE,
}


# ============================================================
# GLOBALS
# ============================================================

pool: asyncpg.Pool | None = None
bot: Bot | None = None

BOT_USERNAME = ""

dp = Dispatcher()

app = FastAPI(
    title="IQ TEST BOT"
)

app.mount(
    "/static",
    StaticFiles(directory=str(WEBAPP_DIR)),
    name="static"
)

admin_state: dict[int, str] = {}


# ============================================================
# HELPERS
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_db_url(url: str) -> str:
    parts = urlsplit(url)

    query = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True
        )
        if key.lower() not in {
            "sslmode",
            "channel_binding",
        }
    ]

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def webhook_url() -> str:
    parts = urlsplit(WEBAPP_URL)

    return (
        f"{parts.scheme}://"
        f"{parts.netloc}"
        f"/telegram/webhook"
    )


def webhook_secret() -> str:
    return hashlib.sha256(
        BOT_TOKEN.encode()
    ).hexdigest()


def is_admin_user(user) -> bool:
    if not user:
        return False

    if ADMIN_USER_ID:
        try:
            if int(user.id) == ADMIN_USER_ID:
                return True
        except Exception:
            pass

    username = (
        getattr(user, "username", "") or ""
    ).lower()

    return username == ADMIN_USERNAME


def is_admin_id(user_id: int) -> bool:
    if ADMIN_USER_ID and int(user_id) == ADMIN_USER_ID:
        return True

    return False


# ============================================================
# DATABASE INIT
# ============================================================

async def init_db():
    global pool

    pool = await asyncpg.create_pool(
        clean_db_url(DATABASE_URL),
        min_size=1,
        max_size=8,
        ssl="require",
        command_timeout=30,
    )

    async with pool.acquire() as conn:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                first_name TEXT NOT NULL DEFAULT '',
                last_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'uz',

                attempts INTEGER NOT NULL DEFAULT 0,

                best_score INTEGER,
                best_raw INTEGER,
                best_time INTEGER,

                referrals INTEGER NOT NULL DEFAULT 0,

                referred_by BIGINT,
                referral_counted BOOLEAN NOT NULL DEFAULT FALSE,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS first_name
            TEXT NOT NULL DEFAULT ''
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_name
            TEXT NOT NULL DEFAULT ''
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS username
            TEXT NOT NULL DEFAULT ''
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS language
            TEXT NOT NULL DEFAULT 'uz'
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS attempts
            INTEGER NOT NULL DEFAULT 0
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_score
            INTEGER
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_raw
            INTEGER
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_time
            INTEGER
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referrals
            INTEGER NOT NULL DEFAULT 0
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referred_by
            BIGINT
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referral_counted
            BOOLEAN NOT NULL DEFAULT FALSE
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS updated_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """)

        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_seen
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """)

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            INSERT INTO app_settings(key,value)
            VALUES
                ('price_uzs','10000'),
                ('battle_price_uzs','7500'),
                ('payment_mode','first_free_retest_paid'),
                ('active_counter_minutes','10'),
                ('admin_chat_id','0')
            ON CONFLICT(key) DO NOTHING
        """)

        # ----------------------------------------------------
        # PAYMENT CARDS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_cards (
                id BIGSERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            ALTER TABLE payment_cards
            ADD COLUMN IF NOT EXISTS holder
            TEXT NOT NULL DEFAULT ''
        """)

        await conn.execute("""
            ALTER TABLE payment_cards
            ADD COLUMN IF NOT EXISTS active
            BOOLEAN NOT NULL DEFAULT TRUE
        """)

        # ----------------------------------------------------
        # IQ SESSIONS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_sessions (
                user_id BIGINT PRIMARY KEY
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                quiz_version INTEGER NOT NULL DEFAULT 5,

                answers JSONB NOT NULL
                    DEFAULT '[]'::jsonb,

                current_index INTEGER NOT NULL DEFAULT 0,

                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                completed BOOLEAN NOT NULL DEFAULT FALSE,

                result_iq INTEGER,
                result_raw INTEGER,
                result_correct INTEGER,
                result_elapsed INTEGER,

                result_counted BOOLEAN NOT NULL DEFAULT FALSE,
                result_unlocked BOOLEAN NOT NULL DEFAULT TRUE,

                payment_id BIGINT,

                finished_at TIMESTAMPTZ
            )
        """)

        # ----------------------------------------------------
        # ATTEMPTS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_attempts (
                id BIGSERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                raw_score INTEGER NOT NULL,
                iq_score INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                elapsed INTEGER NOT NULL,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ----------------------------------------------------
        # PAYMENTS
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_payments (
                id BIGSERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                amount INTEGER NOT NULL,

                purpose TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'pending',

                proof_file_id TEXT,
                proof_message_id BIGINT,

                reviewer_id BIGINT,

                consumed BOOLEAN NOT NULL DEFAULT FALSE,

                reference_id BIGINT,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )
        """)

        await conn.execute("""
            ALTER TABLE iq_payments
            ADD COLUMN IF NOT EXISTS reference_id
            BIGINT
        """)

        # ----------------------------------------------------
        # BATTLES
        # ----------------------------------------------------

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_battles (
                id BIGSERIAL PRIMARY KEY,

                code TEXT UNIQUE NOT NULL,

                creator_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                opponent_id BIGINT
                    REFERENCES users(user_id)
                    ON DELETE SET NULL,

                creator_payment_id BIGINT,
                opponent_payment_id BIGINT,

                creator_finished BOOLEAN NOT NULL DEFAULT FALSE,
                opponent_finished BOOLEAN NOT NULL DEFAULT FALSE,

                creator_iq INTEGER,
                opponent_iq INTEGER,

                status TEXT NOT NULL DEFAULT 'waiting',

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ----------------------------------------------------
        # INDEXES
        # ----------------------------------------------------

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_users_best_score
            ON users(best_score DESC NULLS LAST)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_users_last_seen
            ON users(last_seen)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_payments_status
            ON iq_payments(status,purpose)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_battles_code
            ON iq_battles(code)
        """)

    print("DATABASE INITIALIZED")


# ============================================================
# USERS
# ============================================================

async def upsert_user(
    tg_user: dict,
    referral_id: int | None = None
):
    assert pool is not None

    uid = int(tg_user["id"])

    if referral_id == uid:
        referral_id = None

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(
                user_id,
                first_name,
                last_name,
                username,
                referred_by,
                last_seen,
                updated_at
            )
            VALUES(
                $1,$2,$3,$4,$5,NOW(),NOW()
            )

            ON CONFLICT(user_id)
            DO UPDATE SET
                first_name=EXCLUDED.first_name,
                last_name=EXCLUDED.last_name,
                username=EXCLUDED.username,

                referred_by=
                    COALESCE(
                        users.referred_by,
                        EXCLUDED.referred_by
                    ),

                last_seen=NOW(),
                updated_at=NOW()
        """,
            uid,
            tg_user.get("first_name", "") or "",
            tg_user.get("last_name", "") or "",
            tg_user.get("username", "") or "",
            referral_id,
        )


async def get_user(uid: int):
    assert pool is not None

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id=$1
            """,
            uid,
        )


async def count_referral(uid: int):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            row = await conn.fetchrow("""
                SELECT
                    referred_by,
                    referral_counted
                FROM users
                WHERE user_id=$1
                FOR UPDATE
            """, uid)

            if not row:
                return

            ref = row["referred_by"]

            if not ref:
                return

            if int(ref) == uid:
                return

            if row["referral_counted"]:
                return

            exists = await conn.fetchval(
                """
                SELECT 1
                FROM users
                WHERE user_id=$1
                """,
                ref,
            )

            if not exists:
                return

            await conn.execute("""
                UPDATE users
                SET referral_counted=TRUE,
                    updated_at=NOW()
                WHERE user_id=$1
            """, uid)

            await conn.execute("""
                UPDATE users
                SET referrals=referrals+1,
                    updated_at=NOW()
                WHERE user_id=$1
            """, ref)


# ============================================================
# SETTINGS
# ============================================================

async def get_setting(
    key: str,
    default: str = ""
) -> str:

    assert pool is not None

    async with pool.acquire() as conn:
        value = await conn.fetchval(
            """
            SELECT value
            FROM app_settings
            WHERE key=$1
            """,
            key,
        )

    if value is None:
        return default

    return str(value)


async def set_setting(
    key: str,
    value: str
):
    assert pool is not None

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO app_settings(
                key,
                value,
                updated_at
            )
            VALUES($1,$2,NOW())

            ON CONFLICT(key)
            DO UPDATE SET
                value=EXCLUDED.value,
                updated_at=NOW()
        """,
            key,
            value,
        )


async def get_price() -> int:
    try:
        return max(
            0,
            int(
                await get_setting(
                    "price_uzs",
                    "10000"
                )
            )
        )
    except Exception:
        return 10000


async def get_battle_price() -> int:
    try:
        return max(
            0,
            int(
                await get_setting(
                    "battle_price_uzs",
                    "7500"
                )
            )
        )
    except Exception:
        return 7500


async def get_payment_mode() -> str:
    value = await get_setting(
        "payment_mode",
        PAYMENT_MODE_RETEST
    )

    if value not in VALID_PAYMENT_MODES:
        return PAYMENT_MODE_RETEST

    return value


# ============================================================
# ANSWERS / SCORE
# ============================================================

def sanitize_answers(values) -> list[int]:

    if isinstance(values, str):
        try:
            values = json.loads(values)
        except Exception:
            values = []

    if not isinstance(values, list):
        return []

    result = []

    for value in values[:QUESTIONS_COUNT]:

        try:
            value = int(value)
        except Exception:
            break

        if value < 0 or value > 3:
            break

        result.append(value)

    return result


def score_answers(
    answers: list[int]
) -> tuple[int, int]:

    correct = 0
    raw = 0

    for i in range(
        min(
            len(answers),
            QUESTIONS_COUNT
        )
    ):

        if answers[i] == CORRECT_ANSWERS[i]:

            correct += 1
            raw += WEIGHTS[i]

    return raw, correct


def calculate_iq(raw: int) -> int:

    raw = max(
        0,
        min(raw, MAX_RAW)
    )

    # Product score.
    # Not a standardized clinical IQ test.
    score = round(
        40 +
        (raw / MAX_RAW) * 120
    )

    return max(
        40,
        min(160, score)
    )


# ============================================================
# RANKING
# ============================================================

async def get_rank(uid: int) -> int | None:

    assert pool is not None

    async with pool.acquire() as conn:

        user = await conn.fetchrow("""
            SELECT
                best_score,
                best_time
            FROM users
            WHERE user_id=$1
        """, uid)

        if not user:
            return None

        if user["best_score"] is None:
            return None

        rank = await conn.fetchval("""
            SELECT COUNT(*) + 1
            FROM users
            WHERE best_score IS NOT NULL
            AND (
                best_score > $1

                OR (
                    best_score = $1

                    AND COALESCE(
                        best_time,
                        2147483647
                    )
                    <
                    COALESCE(
                        $2::INTEGER,
                        2147483647
                    )
                )
            )
        """,
            user["best_score"],
            user["best_time"],
        )

        return int(rank)


# ============================================================
# PAYMENT CARDS
# ============================================================

async def active_cards() -> list[dict]:

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT
                id,
                card_number,
                holder
            FROM payment_cards
            WHERE active=TRUE
            ORDER BY id
        """)

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# PAYMENTS
# ============================================================

async def create_payment(
    uid: int,
    purpose: str,
    amount: int | None = None,
    reference_id: int | None = None,
):

    if purpose not in {
        "retest",
        "result",
        "battle",
    }:
        raise HTTPException(
            400,
            "INVALID_PAYMENT_PURPOSE"
        )

    if amount is None:

        if purpose == "battle":
            amount = await get_battle_price()
        else:
            amount = await get_price()

    amount = int(amount)

    if amount <= 0:
        raise HTTPException(
            400,
            "PAYMENTS_DISABLED"
        )

    cards = await active_cards()

    if not cards:
        raise HTTPException(
            503,
            "NO_PAYMENT_CARD"
        )

    assert pool is not None

    async with pool.acquire() as conn:

        existing = await conn.fetchrow("""
            SELECT
                id,
                amount
            FROM iq_payments
            WHERE user_id=$1
            AND purpose=$2
            AND status='pending'
            AND consumed=FALSE

            AND reference_id
                IS NOT DISTINCT FROM $3

            ORDER BY id DESC
            LIMIT 1
        """,
            uid,
            purpose,
            reference_id,
        )

        if existing:

            payment_id = int(
                existing["id"]
            )

            amount = int(
                existing["amount"]
            )

        else:

            row = await conn.fetchrow("""
                INSERT INTO iq_payments(
                    user_id,
                    amount,
                    purpose,
                    reference_id
                )
                VALUES(
                    $1,$2,$3,$4
                )
                RETURNING id,amount
            """,
                uid,
                amount,
                purpose,
                reference_id,
            )

            payment_id = int(
                row["id"]
            )

            amount = int(
                row["amount"]
            )

    return {
        "payment_id": payment_id,
        "amount": amount,
        "cards": cards,
    }


async def payment_status(
    uid: int,
    payment_id: int
):

    assert pool is not None

    async with pool.acquire() as conn:

        row = await conn.fetchrow("""
            SELECT
                id,
                amount,
                purpose,
                status,
                consumed
            FROM iq_payments
            WHERE id=$1
            AND user_id=$2
        """,
            payment_id,
            uid,
        )

    if not row:
        raise HTTPException(
            404,
            "PAYMENT_NOT_FOUND"
        )

    return {
        "payment_id": int(row["id"]),
        "amount": int(row["amount"]),
        "purpose": row["purpose"],
        "status": row["status"],
        "consumed": bool(row["consumed"]),
    }


async def consume_payment(
    conn,
    uid: int,
    purpose: str
) -> int | None:

    row = await conn.fetchrow("""
        SELECT id
        FROM iq_payments

        WHERE user_id=$1
        AND purpose=$2
        AND status='approved'
        AND consumed=FALSE

        ORDER BY id ASC
        LIMIT 1

        FOR UPDATE
    """,
        uid,
        purpose,
    )

    if not row:
        return None

    await conn.execute("""
        UPDATE iq_payments
        SET consumed=TRUE
        WHERE id=$1
    """,
        row["id"],
    )

    return int(row["id"])


# ============================================================
# IQ ACCESS
# ============================================================

async def iq_access(uid: int):

    user = await get_user(uid)

    attempts = int(
        user["attempts"]
        if user
        else 0
    )

    mode = await get_payment_mode()

    # First test is always free.
    if attempts == 0:
        return {
            "allowed": True,
            "free": True,
            "price": 0,
        }

    # Everything free.
    if mode == PAYMENT_MODE_FREE:
        return {
            "allowed": True,
            "free": True,
            "price": 0,
        }

    # Result-paid mode: test itself remains accessible.
    if mode == PAYMENT_MODE_RESULT:
        return {
            "allowed": True,
            "free": True,
            "price": 0,
        }

    assert pool is not None

    async with pool.acquire() as conn:

        approved = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1
                FROM iq_payments
                WHERE user_id=$1
                AND purpose='retest'
                AND status='approved'
                AND consumed=FALSE
            )
        """, uid)

    return {
        "allowed": bool(approved),
        "free": False,
        "price": await get_price(),
    }


# ============================================================
# SESSION
# ============================================================

async def start_session(
    uid: int,
    language: str,
):

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            # Prevent double/concurrent starts.
            await conn.execute(
                """
                SELECT pg_advisory_xact_lock(
                    $1::bigint
                )
                """,
                uid,
            )

            user = await conn.fetchrow("""
                SELECT attempts
                FROM users
                WHERE user_id=$1
                FOR UPDATE
            """, uid)

            if not user:
                raise HTTPException(
                    401,
                    "USER_NOT_FOUND"
                )

            session = await conn.fetchrow("""
                SELECT *
                FROM iq_sessions
                WHERE user_id=$1
                FOR UPDATE
            """, uid)

            # Old question version:
            # never score it with new key.
            if session and int(
                session["quiz_version"]
            ) != QUIZ_VERSION:

                await conn.execute("""
                    DELETE FROM iq_sessions
                    WHERE user_id=$1
                """, uid)

                session = None

            # Existing unfinished session.
            if session and not session["completed"]:

                answers = sanitize_answers(
                    session["answers"]
                )

                if len(answers) < QUESTIONS_COUNT:

                    return session

                # Fully answered old session.
                await conn.execute("""
                    DELETE FROM iq_sessions
                    WHERE user_id=$1
                """, uid)

                session = None

            mode = await get_payment_mode()

            payment_id = None

            attempts = int(
                user["attempts"]
            )

            if (
                mode == PAYMENT_MODE_RETEST
                and attempts >= 1
            ):

                payment_id = await consume_payment(
                    conn,
                    uid,
                    "retest"
                )

                if payment_id is None:

                    price = await get_price()

                    raise HTTPException(
                        status_code=402,
                        detail="PAID_RETEST",
                        headers={
                            "X-Payment-Price":
                                str(price)
                        },
                    )

            row = await conn.fetchrow("""
                INSERT INTO iq_sessions(
                    user_id,
                    quiz_version,
                    answers,
                    current_index,
                    started_at,
                    last_activity,
                    payment_id
                )
                VALUES(
                    $1,
                    $2,
                    '[]'::jsonb,
                    0,
                    NOW(),
                    NOW(),
                    $3
                )
                RETURNING *
            """,
                uid,
                QUIZ_VERSION,
                payment_id,
            )

            return row


async def sync_session_answers(
    uid: int,
    answers: list[int]
):

    clean = sanitize_answers(
        answers
    )

    if len(clean) != QUESTIONS_COUNT:
        raise HTTPException(
            409,
            "INCOMPLETE"
        )

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            await conn.execute(
                """
                SELECT pg_advisory_xact_lock(
                    $1::bigint
                )
                """,
                uid,
            )

            session = await conn.fetchrow("""
                SELECT *
                FROM iq_sessions
                WHERE user_id=$1
                AND completed=FALSE
                FOR UPDATE
            """, uid)

            if not session:
                raise HTTPException(
                    409,
                    "SESSION_EXPIRED"
                )

            raw, correct = score_answers(
                clean
            )

            await conn.execute("""
                UPDATE iq_sessions
                SET
                    answers=$2::jsonb,
                    current_index=$3,
                    result_raw=$4,
                    result_correct=$5,
                    last_activity=NOW()

                WHERE user_id=$1
            """,
                uid,
                json.dumps(clean),
                QUESTIONS_COUNT,
                raw,
                correct,
            )

    return QUESTIONS_COUNT


# ============================================================
# FINISH SESSION
# ============================================================

async def finish_session(uid: int):

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            await conn.execute(
                """
                SELECT pg_advisory_xact_lock(
                    $1::bigint
                )
                """,
                uid,
            )

            session = await conn.fetchrow("""
                SELECT *
                FROM iq_sessions
                WHERE user_id=$1
                FOR UPDATE
            """, uid)

            if not session:
                raise HTTPException(
                    409,
                    "SESSION_NOT_FOUND"
                )

            answers = sanitize_answers(
                session["answers"]
            )

            if len(answers) != QUESTIONS_COUNT:
                raise HTTPException(
                    409,
                    "INCOMPLETE"
                )

            raw, correct = score_answers(
                answers
            )

            iq = calculate_iq(
                raw
            )

            elapsed = max(
                0,
                int(
                    (
                        now_utc()
                        -
                        session["started_at"]
                    ).total_seconds()
                )
            )

            mode = await get_payment_mode()

            # Result-paid:
            # first calculate/store result,
            # but don't unlock it until payment.
            if (
                mode == PAYMENT_MODE_RESULT
                and not session["result_unlocked"]
            ):

                payment = await conn.fetchrow("""
                    SELECT id
                    FROM iq_payments
                    WHERE user_id=$1
                    AND purpose='result'
                    AND status='approved'
                    AND consumed=FALSE

                    ORDER BY id ASC
                    LIMIT 1

                    FOR UPDATE
                """, uid)

                if payment:

                    await conn.execute("""
                        UPDATE iq_payments
                        SET consumed=TRUE
                        WHERE id=$1
                    """,
                        payment["id"],
                    )

                else:

                    await conn.execute("""
                        UPDATE iq_sessions
                        SET
                            completed=TRUE,
                            result_iq=$2,
                            result_raw=$3,
                            result_correct=$4,
                            result_elapsed=$5,
                            result_unlocked=FALSE,
                            last_activity=NOW()
                        WHERE user_id=$1
                    """,
                        uid,
                        iq,
                        raw,
                        correct,
                        elapsed,
                    )

                    raise HTTPException(
                        status_code=402,
                        detail="RESULT_PAYMENT_REQUIRED",
                        headers={
                            "X-Payment-Price":
                                str(await get_price())
                        },
                    )

            # Count only once.
            if not session["result_counted"]:

                await conn.execute("""
                    INSERT INTO iq_attempts(
                        user_id,
                        raw_score,
                        iq_score,
                        correct,
                        elapsed
                    )
                    VALUES(
                        $1,$2,$3,$4,$5
                    )
                """,
                    uid,
                    raw,
                    iq,
                    correct,
                    elapsed,
                )

                await conn.execute("""
                    UPDATE users
                    SET
                        attempts=attempts+1,

                        best_score=
                            CASE
                                WHEN best_score IS NULL
                                OR $2 > best_score
                                THEN $2
                                ELSE best_score
                            END,

                        best_raw=
                            CASE
                                WHEN best_score IS NULL
                                OR $2 > best_score
                                THEN $3
                                ELSE best_raw
                            END,

                        best_time=
                            CASE
                                WHEN best_score IS NULL
                                OR $2 > best_score
                                OR (
                                    $2 = best_score
                                    AND (
                                        best_time IS NULL
                                        OR $4 < best_time
                                    )
                                )
                                THEN $4
                                ELSE best_time
                            END,

                        updated_at=NOW(),
                        last_seen=NOW()

                    WHERE user_id=$1
                """,
                    uid,
                    iq,
                    raw,
                    elapsed,
                )

            await conn.execute("""
                UPDATE iq_sessions
                SET
                    completed=TRUE,
                    current_index=$2,
                    result_iq=$3,
                    result_raw=$4,
                    result_correct=$5,
                    result_elapsed=$6,
                    result_counted=TRUE,
                    result_unlocked=TRUE,
                    finished_at=NOW(),
                    last_activity=NOW()

                WHERE user_id=$1
            """,
                uid,
                QUESTIONS_COUNT,
                iq,
                raw,
                correct,
                elapsed,
            )

            return {
                "iq": iq,
                "raw": raw,
                "correct": correct,
                "elapsed": elapsed,
            }


# ============================================================
# BATTLE
# ============================================================

async def create_battle(
    uid: int
):

    price = await get_battle_price()

    cards = await active_cards()

    if price <= 0:
        raise HTTPException(
            400,
            "PAYMENTS_DISABLED"
        )

    if not cards:
        raise HTTPException(
            503,
            "NO_PAYMENT_CARD"
        )

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            code = None

            for _ in range(30):

                candidate = (
                    f"{secrets.randbelow(10000):04d}"
                )

                exists = await conn.fetchval("""
                    SELECT 1
                    FROM iq_battles
                    WHERE code=$1
                    AND status IN(
                        'waiting',
                        'ready',
                        'active'
                    )
                """,
                    candidate,
                )

                if not exists:
                    code = candidate
                    break

            if code is None:
                raise HTTPException(
                    503,
                    "BATTLE_CODE_UNAVAILABLE"
                )

            battle = await conn.fetchrow("""
                INSERT INTO iq_battles(
                    code,
                    creator_id,
                    status
                )
                VALUES(
                    $1,$2,'waiting'
                )
                RETURNING id,code
            """,
                code,
                uid,
            )

            payment = await conn.fetchrow("""
                INSERT INTO iq_payments(
                    user_id,
                    amount,
                    purpose,
                    reference_id
                )
                VALUES(
                    $1,$2,'battle',$3
                )
                RETURNING id,amount
            """,
                uid,
                price,
                battle["id"],
            )

            await conn.execute("""
                UPDATE iq_battles
                SET
                    creator_payment_id=$2,
                    updated_at=NOW()
                WHERE id=$1
            """,
                battle["id"],
                payment["id"],
            )

    return {
        "battle_id": int(
            battle["id"]
        ),
        "code": battle["code"],
        "payment_required": True,
        "payment_id": int(
            payment["id"]
        ),
        "amount": int(
            payment["amount"]
        ),
        "cards": cards,
    }


async def join_battle(
    uid: int,
    code: str
):

    code = str(code).strip()

    if not code.isdigit() or len(code) != 4:
        raise HTTPException(
            400,
            "INVALID_BATTLE_CODE"
        )

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            battle = await conn.fetchrow("""
                SELECT *
                FROM iq_battles
                WHERE code=$1
                AND status='waiting'
                FOR UPDATE
            """,
                code,
            )

            if not battle:
                raise HTTPException(
                    404,
                    "BATTLE_NOT_FOUND"
                )

            if int(
                battle["creator_id"]
            ) == uid:

                raise HTTPException(
                    400,
                    "CANNOT_JOIN_OWN_BATTLE"
                )

            if battle["opponent_id"]:

                raise HTTPException(
                    409,
                    "BATTLE_FULL"
                )

            price = await get_battle_price()

            cards = await active_cards()

            if price <= 0:
                raise HTTPException(
                    400,
                    "PAYMENTS_DISABLED"
                )

            if not cards:
                raise HTTPException(
                    503,
                    "NO_PAYMENT_CARD"
                )

            payment = await conn.fetchrow("""
                INSERT INTO iq_payments(
                    user_id,
                    amount,
                    purpose,
                    reference_id
                )
                VALUES(
                    $1,$2,'battle',$3
                )
                RETURNING id,amount
            """,
                uid,
                price,
                battle["id"],
            )

            await conn.execute("""
                UPDATE iq_battles
                SET
                    opponent_id=$2,
                    opponent_payment_id=$3,
                    status='ready',
                    updated_at=NOW()

                WHERE id=$1
            """,
                battle["id"],
                uid,
                payment["id"],
            )

    return {
        "battle_id": int(
            battle["id"]
        ),
        "code": code,
        "payment_required": True,
        "payment_id": int(
            payment["id"]
        ),
        "amount": int(
            payment["amount"]
        ),
        "cards": cards,
    }


async def battle_payment_approved(
    conn,
    payment_id
) -> bool:

    if not payment_id:
        return False

    result = await conn.fetchval("""
        SELECT status='approved'
        FROM iq_payments
        WHERE id=$1
    """,
        payment_id,
    )

    return bool(result)


async def battle_status(
    uid: int,
    battle_id: int | None = None
):

    assert pool is not None

    async with pool.acquire() as conn:

        if battle_id:

            row = await conn.fetchrow("""
                SELECT *
                FROM iq_battles
                WHERE id=$1
                AND (
                    creator_id=$2
                    OR opponent_id=$2
                )
            """,
                battle_id,
                uid,
            )

        else:

            row = await conn.fetchrow("""
                SELECT *
                FROM iq_battles

                WHERE (
                    creator_id=$1
                    OR opponent_id=$1
                )

                AND status NOT IN(
                    'finished',
                    'cancelled'
                )

                ORDER BY updated_at DESC
                LIMIT 1
            """,
                uid,
            )

        if not row:
            raise HTTPException(
                404,
                "BATTLE_NOT_FOUND"
            )

        creator = (
            int(row["creator_id"])
            == uid
        )

        my_payment = (
            row["creator_payment_id"]
            if creator
            else row["opponent_payment_id"]
        )

        opponent_payment = (
            row["opponent_payment_id"]
            if creator
            else row["creator_payment_id"]
        )

        my_finished = bool(
            row["creator_finished"]
            if creator
            else row["opponent_finished"]
        )

        opponent_finished = bool(
            row["opponent_finished"]
            if creator
            else row["creator_finished"]
        )

        my_iq = (
            row["creator_iq"]
            if creator
            else row["opponent_iq"]
        )

        opponent_iq = (
            row["opponent_iq"]
            if creator
            else row["creator_iq"]
        )

        mine_paid = await battle_payment_approved(
            conn,
            my_payment,
        )

        opponent_paid = await battle_payment_approved(
            conn,
            opponent_payment,
        )

        result = None

        if (
            row["status"] == "finished"
            and my_iq is not None
            and opponent_iq is not None
        ):

            diff = int(my_iq) - int(
                opponent_iq
            )

            result = {
                "winner":
                    "me"
                    if diff > 0
                    else
                    "opponent"
                    if diff < 0
                    else
                    "draw",

                "my_iq":
                    int(my_iq),

                "opponent_iq":
                    int(opponent_iq),

                "difference":
                    abs(diff),
            }

        return {
            "battle_id": int(row["id"]),
            "code": row["code"],
            "status": row["status"],

            "payment_approved":
                mine_paid,

            "opponent_payment_approved":
                opponent_paid,

            "both_paid":
                bool(
                    mine_paid
                    and opponent_paid
                ),

            "opponent_joined":
                row["opponent_id"] is not None,

            "my_finished":
                my_finished,

            "opponent_finished":
                opponent_finished,

            "my_iq":
                my_iq,

            "result":
                result,
        }


async def finalize_battle(
    uid: int,
    iq: int,
    battle_id: int | None
):

    if not battle_id:
        return None

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            battle = await conn.fetchrow("""
                SELECT *
                FROM iq_battles
                WHERE id=$1
                FOR UPDATE
            """,
                battle_id,
            )

            if not battle:
                return None

            if (
                int(battle["creator_id"])
                != uid
                and int(
                    battle["opponent_id"] or 0
                )
                != uid
            ):
                return None

            creator = (
                int(battle["creator_id"])
                == uid
            )

            if creator:

                await conn.execute("""
                    UPDATE iq_battles
                    SET
                        creator_finished=TRUE,
                        creator_iq=$2,

                        status=
                            CASE
                                WHEN opponent_finished
                                THEN 'finished'
                                ELSE 'active'
                            END,

                        updated_at=NOW()

                    WHERE id=$1
                """,
                    battle_id,
                    iq,
                )

            else:

                await conn.execute("""
                    UPDATE iq_battles
                    SET
                        opponent_finished=TRUE,
                        opponent_iq=$2,

                        status=
                            CASE
                                WHEN creator_finished
                                THEN 'finished'
                                ELSE 'active'
                            END,

                        updated_at=NOW()

                    WHERE id=$1
                """,
                    battle_id,
                    iq,
                )

            updated = await conn.fetchrow("""
                SELECT *
                FROM iq_battles
                WHERE id=$1
            """,
                battle_id,
            )

            if (
                updated["status"] == "finished"
                and updated["creator_iq"] is not None
                and updated["opponent_iq"] is not None
            ):

                return {
                    "finished": True,
                    "creator_id":
                        int(
                            updated[
                                "creator_id"
                            ]
                        ),

                    "opponent_id":
                        int(
                            updated[
                                "opponent_id"
                            ]
                        ),

                    "creator_iq":
                        int(
                            updated[
                                "creator_iq"
                            ]
                        ),

                    "opponent_iq":
                        int(
                            updated[
                                "opponent_iq"
                            ]
                        ),
                }

    return None


# ============================================================
# TELEGRAM INIT DATA VALIDATION
# ============================================================

def validate_init_data(
    init_data: str
) -> dict:

    if not init_data:
        raise HTTPException(
            401,
            "INVALID_INIT_DATA"
        )

    try:

        pairs = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = pairs.pop(
            "hash",
            None
        )

        if not received_hash:
            raise ValueError(
                "hash"
            )

        auth_date = int(
            pairs.get(
                "auth_date",
                "0"
            )
        )

        now = int(
            now_utc().timestamp()
        )

        if auth_date <= 0:
            raise ValueError(
                "auth_date"
            )

        if now - auth_date > 86400:
            raise ValueError(
                "expired"
            )

        if auth_date - now > 60:
            raise ValueError(
                "future"
            )

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value
            in sorted(
                pairs.items()
            )
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
            raise ValueError(
                "hash"
            )

        user = json.loads(
            pairs.get(
                "user",
                "{}"
            )
        )

        if (
            not isinstance(user, dict)
            or not user.get("id")
        ):
            raise ValueError(
                "user"
            )

        return user

    except Exception as exc:

        raise HTTPException(
            401,
            "INVALID_INIT_DATA"
        ) from exc


async def api_user(
    request: Request
) -> dict:

    user = validate_init_data(
        request.headers.get(
            "X-Telegram-Init-Data",
            ""
        )
    )

    await upsert_user(
        user
    )

    await count_referral(
        int(user["id"])
    )

    return user


# ============================================================
# FASTAPI
# ============================================================

@app.get("/")
async def root():

    return {
        "status": "ok",
        "service": "IQ TEST BOT",
        "version": QUIZ_VERSION,
    }


@app.get("/health")
async def health():

    if pool is None:
        raise HTTPException(
            503,
            "DATABASE_NOT_READY"
        )

    async with pool.acquire() as conn:
        await conn.fetchval(
            "SELECT 1"
        )

    return {
        "status": "ok"
    }


@app.get(
    "/app",
    response_class=HTMLResponse
)
async def app_page():

    path = WEBAPP_DIR / "index.html"

    return HTMLResponse(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
async def api_config(
    request: Request
):

    await api_user(request)

    return {
        "bot_username":
            BOT_USERNAME,

        "price_uzs":
            await get_price(),

        "battle_price_uzs":
            await get_battle_price(),

        "payment_mode":
            await get_payment_mode(),

        "question_count":
            QUESTIONS_COUNT,
    }


# ============================================================
# ACTIVE COUNTER
# ============================================================

@app.get("/api/counter")
async def api_counter(
    request: Request
):

    await api_user(request)

    assert pool is not None

    try:
        minutes = int(
            await get_setting(
                "active_counter_minutes",
                "10"
            )
        )
    except Exception:
        minutes = 10

    minutes = max(
        1,
        min(minutes, 60)
    )

    async with pool.acquire() as conn:

        active = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM users

            WHERE last_seen >
                NOW()
                -
                ($1::text || ' minutes')
                ::interval
            """,
            str(minutes),
        )

    return {
        "active":
            int(active or 0)
    }


# ============================================================
# PROFILE
# ============================================================

@app.get("/api/profile")
async def api_profile(
    request: Request
):

    user = await api_user(request)

    row = await get_user(
        int(user["id"])
    )

    return {
        "first_name":
            row["first_name"],

        "last_name":
            row["last_name"],

        "username":
            row["username"],

        "attempts":
            int(row["attempts"]),

        "best_score":
            row["best_score"],

        "best_time":
            row["best_time"],

        "referrals":
            int(row["referrals"]),

        "rank":
            await get_rank(
                int(user["id"])
            ),
    }


# ============================================================
# RANKING
# ============================================================

@app.get("/api/ranking")
async def api_ranking(
    request: Request
):

    await api_user(request)

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT
                first_name,
                username,
                best_score,
                best_time

            FROM users

            WHERE best_score IS NOT NULL

            ORDER BY
                best_score DESC,
                best_time ASC NULLS LAST,
                created_at ASC

            LIMIT 50
        """)

    return {
        "items": [
            {
                "first_name":
                    row["first_name"],

                "username":
                    row["username"],

                "best_score":
                    row["best_score"],

                "best_time":
                    row["best_time"],
            }

            for row in rows
        ]
    }


# ============================================================
# IQ ACCESS
# ============================================================

@app.get("/api/access/iq")
async def api_access_iq(
    request: Request
):

    user = await api_user(request)

    return await iq_access(
        int(user["id"])
    )


# ============================================================
# START SESSION
# ============================================================

@app.post("/api/session/start")
async def api_session_start(
    request: Request
):

    user = await api_user(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

    language = (
        body.get(
            "language",
            "uz"
        )
        if isinstance(body, dict)
        else "uz"
    )

    if language not in {
        "uz",
        "ru",
        "en",
    }:
        language = "uz"

    row = await start_session(
        int(user["id"]),
        language,
    )

    answers = sanitize_answers(
        row["answers"]
    )

    elapsed = max(
        0,
        int(
            (
                now_utc()
                -
                row["started_at"]
            ).total_seconds()
        )
    )

    return {
        "index":
            int(
                row["current_index"]
            ),

        "answers":
            answers,

        "elapsed":
            elapsed,

        "created":
            int(
                row["current_index"]
            ) == 0,

        "attempts":
            int(
                (
                    await get_user(
                        int(user["id"])
                    )
                )["attempts"]
            ),
    }


# ============================================================
# OFFLINE-FIRST SYNC
# ============================================================

@app.post("/api/session/sync")
async def api_session_sync(
    request: Request
):

    user = await api_user(request)

    try:

        body = await request.json()

        answers = (
            body.get(
                "answers",
                []
            )
            if isinstance(body, dict)
            else []
        )

    except Exception as exc:

        raise HTTPException(
            400,
            "INVALID_SYNC"
        ) from exc

    await sync_session_answers(
        int(user["id"]),
        answers,
    )

    return {
        "ok": True
    }


# ============================================================
# FINISH
# ============================================================

@app.post("/api/session/finish")
async def api_session_finish(
    request: Request
):

    user = await api_user(request)

    result = await finish_session(
        int(user["id"])
    )

    return {
        **result,

        "rank":
            await get_rank(
                int(user["id"])
            ),
    }


# ============================================================
# PAYMENT API
# ============================================================

@app.post("/api/payment/create")
async def api_payment_create(
    request: Request
):

    user = await api_user(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

    purpose = str(
        body.get(
            "purpose",
            "retest"
        )
    )

    payment = await create_payment(
        int(user["id"]),
        purpose,
    )

    # Send payment instructions directly to Telegram.
    if bot:

        cards_text = "\n".join(
            (
                f"💳 <code>{card['card_number']}</code>"
                f" — {card['holder'] or ''}"
            ).strip()
            for card in payment["cards"]
        )

        text = (
            "💳 <b>TO‘LOV</b>\n\n"
            f"💰 Summa: "
            f"<b>{payment['amount']:,} so‘m</b>\n\n"
            f"{cards_text}\n\n"
            "1️⃣ Yuqoridagi kartaga to‘lov qiling.\n"
            "2️⃣ Chek/skrinshotni shu botga yuboring.\n"
            "3️⃣ Admin tasdiqlagach test avtomatik ochiladi.\n\n"
            f"🔑 To‘lov ID: "
            f"<code>{payment['payment_id']}</code>"
        )

        try:

            await bot.send_message(
                int(user["id"]),
                text,
                parse_mode="HTML",
            )

        except Exception as exc:

            print(
                "PAYMENT MESSAGE ERROR:",
                exc
            )

    return payment


@app.get(
    "/api/payment/{payment_id}"
)
async def api_payment_status(
    payment_id: int,
    request: Request,
):

    user = await api_user(request)

    return await payment_status(
        int(user["id"]),
        payment_id,
    )


# ============================================================
# BATTLE API
# ============================================================

@app.post("/api/battle/create")
async def api_battle_create(
    request: Request
):

    user = await api_user(request)

    return await create_battle(
        int(user["id"])
    )


@app.post("/api/battle/join")
async def api_battle_join(
    request: Request
):

    user = await api_user(request)

    try:

        body = await request.json()

        code = (
            body.get(
                "code",
                ""
            )
            if isinstance(body, dict)
            else ""
        )

    except Exception as exc:

        raise HTTPException(
            400,
            "INVALID_BATTLE_CODE"
        ) from exc

    return await join_battle(
        int(user["id"]),
        code,
    )


@app.get("/api/battle")
async def api_my_battle(
    request: Request
):

    user = await api_user(request)

    return await battle_status(
        int(user["id"])
    )


@app.get(
    "/api/battle/{battle_id}"
)
async def api_battle_status(
    battle_id: int,
    request: Request,
):

    user = await api_user(request)

    return await battle_status(
        int(user["id"]),
        battle_id,
    )


# ============================================================
# CERTIFICATE
# ============================================================

def load_font(
    size: int,
    bold: bool = False
):

    paths = [

        (
            "/usr/share/fonts/"
            "truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
            if bold
            else
            "/usr/share/fonts/"
            "truetype/dejavu/"
            "DejaVuSans.ttf"
        ),

        (
            "/usr/share/fonts/"
            "truetype/liberation2/"
            "LiberationSans-Bold.ttf"
            if bold
            else
            "/usr/share/fonts/"
            "truetype/liberation2/"
            "LiberationSans-Regular.ttf"
        ),
    ]

    for path in paths:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


def make_certificate(
    name: str,
    iq: int,
    code: str,
    title: str = "SERTIFIKAT",
):

    width = 1400
    height = 900

    image = Image.new(
        "RGB",
        (width, height),
        "#080a14"
    )

    draw = ImageDraw.Draw(
        image
    )

    # Outer border
    draw.rounded_rectangle(
        (
            32,
            32,
            width - 32,
            height - 32
        ),
        radius=36,
        outline="#8f6cff",
        width=4,
    )

    # Inner border
    draw.rounded_rectangle(
        (
            60,
            60,
            width - 60,
            height - 60
        ),
        radius=28,
        outline="#272b3d",
        width=2,
    )

    def center(
        text,
        y,
        font,
        fill="#ffffff"
    ):

        box = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        text_width = (
            box[2] - box[0]
        )

        draw.text(
            (
                (width - text_width) / 2,
                y,
            ),
            text,
            font=font,
            fill=fill,
        )

    center(
        "IQ TEST BOT",
        105,
        load_font(
            54,
            True
        ),
        "#bda8ff",
    )

    center(
        title,
        195,
        load_font(
            32,
            True
        ),
        "#9ea7ba",
    )

    center(
        name[:38] or "User",
        290,
        load_font(
            48,
            True
        ),
    )

    center(
        str(iq),
        390,
        load_font(
            130,
            True
        ),
        "#ffffff",
    )

    center(
        "IQ SCORE",
        545,
        load_font(
            26,
            True
        ),
        "#bd9cff",
    )

    center(
        "18 ta mantiqiy puzzle natijasi",
        595,
        load_font(
            23
        ),
        "#9ba3b6",
    )

    center(
        now_utc().strftime(
            "%d.%m.%Y"
        ),
        660,
        load_font(
            21
        ),
        "#70798c",
    )

    center(
        code,
        720,
        load_font(
            20
        ),
        "#70798c",
    )

    output = BytesIO()

    image.save(
        output,
        "PNG",
        optimize=True,
    )

    return output.getvalue()


@app.get("/api/certificate")
async def api_certificate(
    request: Request
):

    user = await api_user(request)

    row = await get_user(
        int(user["id"])
    )

    if not row:
        raise HTTPException(
            404,
            "USER_NOT_FOUND"
        )

    if row["best_score"] is None:
        raise HTTPException(
            404,
            "NO_RESULT"
        )

    data = make_certificate(
        (
            f"{row['first_name']} "
            f"{row['last_name']}"
        ).strip(),

        int(
            row["best_score"]
        ),

        f"IQ-{int(user['id'])}",
    )

    return Response(
        data,
        media_type="image/png",
        headers={
            "Content-Disposition":
                'inline; '
                'filename="iq-test-certificate.png"'
        },
    )


# ============================================================
# ADMIN HELPERS
# ============================================================

async def remember_admin_chat(
    user_id: int
):

    await set_setting(
        "admin_chat_id",
        str(user_id)
    )


async def get_admin_chat_id():

    try:

        value = int(
            await get_setting(
                "admin_chat_id",
                "0"
            )
        )

        return value or None

    except Exception:

        return None


def admin_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="💳 Kartalar",
                    callback_data="adm_cards"
                ),

                InlineKeyboardButton(
                    text="💰 Narx",
                    callback_data="adm_price"
                ),
            ],

            [
                InlineKeyboardButton(
                    text="⚙️ To‘lov rejimi",
                    callback_data="adm_mode"
                ),

                InlineKeyboardButton(
                    text="📋 To‘lovlar",
                    callback_data="adm_payments"
                ),
            ],

            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="adm_stats"
                ),

                InlineKeyboardButton(
                    text="👥 Foydalanuvchilar",
                    callback_data="adm_users"
                ),
            ],

        ]
    )


def mode_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="1️⃣ Birinchi bepul / keyingi pullik",
                    callback_data=
                        f"adm_mode:{PAYMENT_MODE_RETEST}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="2️⃣ Test bepul / natija pullik",
                    callback_data=
                        f"adm_mode:{PAYMENT_MODE_RESULT}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="3️⃣ Hammasi bepul",
                    callback_data=
                        f"adm_mode:{PAYMENT_MODE_FREE}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Admin",
                    callback_data="adm_home"
                )
            ],
        ]
    )


def cards_keyboard(
    cards
):

    rows = [

        [
            InlineKeyboardButton(
                text="➕ Karta qo‘shish",
                callback_data="adm_card_add"
            )
        ]
    ]

    for card in cards:

        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"🗑 "
                        f"{card['card_number']}"
                        f" — "
                        f"{card['holder'] or '-'}"
                    ),
                    callback_data=
                        f"adm_card_del:{card['id']}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Admin",
                callback_data="adm_home"
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# ============================================================
# ADMIN TEXT
# ============================================================

async def admin_text():

    assert pool is not None

    async with pool.acquire() as conn:

        users = await conn.fetchval(
            "SELECT COUNT(*) FROM users"
        )

        attempts = await conn.fetchval(
            "SELECT COUNT(*) FROM iq_attempts"
        )

        pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM iq_payments
            WHERE status='pending'
        """)

        approved = await conn.fetchval("""
            SELECT COUNT(*)
            FROM iq_payments
            WHERE status='approved'
        """)

    price = await get_price()
    battle_price = await get_battle_price()
    mode = await get_payment_mode()

    return (
        "👑 <b>IQ TEST BOT — ADMIN</b>\n\n"

        f"👥 Foydalanuvchilar: "
        f"<b>{users}</b>\n"

        f"🧠 Testlar: "
        f"<b>{attempts}</b>\n"

        f"⏳ Kutilayotgan to‘lovlar: "
        f"<b>{pending}</b>\n"

        f"✅ Tasdiqlangan to‘lovlar: "
        f"<b>{approved}</b>\n\n"

        f"🧠 IQ narxi: "
        f"<b>{price:,} so‘m</b>\n"

        f"⚔️ Battle: "
        f"<b>{battle_price:,} so‘m</b>\n"

        f"⚙️ Rejim: "
        f"<code>{mode}</code>"
    )


# ============================================================
# BOT KEYBOARD
# ============================================================

def main_keyboard(
    admin=False
):

    rows = [

        [
            KeyboardButton(
                text=
                "🧠 IQ · EQ · PQ testini ishlash",
                web_app=WebAppInfo(
                    url=WEBAPP_URL
                )
            )
        ],

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
            ),
        ],
    ]

    if admin:

        rows.append(
            [
                KeyboardButton(
                    text="👑 Admin"
                )
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def command_start(
    message: Message
):

    if not message.from_user:
        return

    parts = (
        message.text or ""
    ).split(
        maxsplit=1
    )

    payload = (
        parts[1]
        if len(parts) == 2
        else ""
    )

    referral_id = None

    if payload.startswith(
        "ref_"
    ):

        try:
            referral_id = int(
                payload[4:]
            )
        except Exception:
            referral_id = None

    await upsert_user(
        {
            "id":
                message.from_user.id,

            "first_name":
                message.from_user.first_name
                or "",

            "last_name":
                message.from_user.last_name
                or "",

            "username":
                message.from_user.username
                or "",
        },
        referral_id,
    )

    await count_referral(
        message.from_user.id
    )

    await message.answer(
        (
            "👋 Salom, "
            f"<b>{message.from_user.first_name or 'do‘st'}</b>!\n\n"

            "🧠 <b>IQ TEST BOT</b>\n\n"

            "18 ta mantiqiy puzzle orqali "
            "fikrlash qobiliyatingizni sinang.\n\n"

            "• Birinchi IQ testi — bepul\n"
            "• Natija va reyting\n"
            "• Sertifikat\n"
            "• Do‘st bilan Battle\n\n"

            "👇 Boshlash uchun tugmani bosing."
        ),
        reply_markup=main_keyboard(
            is_admin_user(
                message.from_user
            )
        ),
        parse_mode="HTML",
    )


# ============================================================
# CERTIFICATE MESSAGE
# ============================================================

@dp.message(
    F.text == "📜 Sertifikatim"
)
async def certificate_message(
    message: Message
):

    if not message.from_user:
        return

    row = await get_user(
        message.from_user.id
    )

    if (
        not row
        or row["best_score"] is None
    ):

        await message.answer(
            "📜 Hali IQ natijangiz yo‘q.\n\n"
            "Avval testni topshiring."
        )

        return

    data = make_certificate(
        (
            f"{row['first_name']} "
            f"{row['last_name']}"
        ).strip(),

        int(
            row["best_score"]
        ),

        f"IQ-{message.from_user.id}",
    )

    await message.answer_document(
        BufferedInputFile(
            data,
            filename=
                "iq-test-certificate.png",
        ),

        caption=(
            "📜 <b>IQ TEST BOT sertifikati</b>\n\n"
            f"🧠 IQ score: "
            f"<b>{int(row['best_score'])}</b>"
        ),

        parse_mode="HTML",
    )


# ============================================================
# RANKING MESSAGE
# ============================================================

@dp.message(
    F.text == "🏆 Reyting"
)
async def ranking_message(
    message: Message
):

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT
                first_name,
                username,
                best_score

            FROM users

            WHERE best_score IS NOT NULL

            ORDER BY
                best_score DESC,
                best_time ASC NULLS LAST

            LIMIT 10
        """)

    if not rows:

        await message.answer(
            "🏆 Hali reyting bo‘sh."
        )

        return

    text = (
        "🏆 <b>IQ TEST BOT — TOP 10</b>\n\n"
    )

    medals = [
        "🥇",
        "🥈",
        "🥉",
    ]

    for index, row in enumerate(rows):

        name = (
            row["first_name"]
            or row["username"]
            or "User"
        )

        prefix = (
            medals[index]
            if index < 3
            else f"{index + 1}."
        )

        text += (
            f"{prefix} "
            f"<b>{name}</b> — "
            f"<b>{row['best_score']}</b>\n"
        )

    await message.answer(
        text,
        parse_mode="HTML"
    )


# ============================================================
# PRICE / HELP
# ============================================================

@dp.message(
    F.text == "ℹ️ Narx va yordam"
)
async def help_message(
    message: Message
):

    price = await get_price()
    battle = await get_battle_price()

    await message.answer(
        (
            "ℹ️ <b>NARX VA YORDAM</b>\n\n"

            f"🧠 IQ test — "
            f"<b>{price:,} so‘m</b>\n"

            "🎭 EQ — IQ dan keyin tekin\n"
            "⏳ Prokrastinatsiya — EQ dan keyin tekin\n"
            "⭐ To‘liq tahlil — uchalasidan keyin tekin\n\n"

            f"🔁 IQ ni qayta ishlash — "
            f"<b>{price:,} so‘m</b>\n"

            f"⚔️ Do‘st bilan Battle — "
            f"<b>{battle:,} so‘m</b>\n\n"

            "💳 To‘lov karta orqali\n"
            "⏱ To‘lov admin tomonidan tekshiriladi\n"
            "📜 Sertifikat PNG ko‘rinishida beriladi\n\n"

            "👤 <b>QO‘LLAB-QUVVATLASH</b>\n"
            "💬 @omono_v"
        ),
        parse_mode="HTML",
    )


# ============================================================
# LANGUAGE
# ============================================================

@dp.message(
    F.text == "🌐 Til"
)
async def language_message(
    message: Message
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🇺🇿 O‘zbekcha",
                    callback_data="lang:uz"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang:ru"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang:en"
                )
            ],
        ]
    )

    await message.answer(
        "🌐 <b>Tilni tanlang:</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@dp.callback_query(
    F.data.startswith("lang:")
)
async def language_callback(
    callback: CallbackQuery
):

    language = callback.data.split(
        ":",
        1
    )[1]

    if language not in {
        "uz",
        "ru",
        "en",
    }:
        await callback.answer()
        return

    assert pool is not None

    async with pool.acquire() as conn:

        await conn.execute("""
            UPDATE users
            SET
                language=$2,
                updated_at=NOW()
            WHERE user_id=$1
        """,
            callback.from_user.id,
            language,
        )

    await callback.answer(
        "Til saqlandi"
    )

    await callback.message.edit_text(
        (
            "🌐 Til saqlandi.\n\n"
            "Mini App ichida ham "
            "tilni o‘zgartirishingiz mumkin."
        )
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message
):

    if not is_admin_user(
        message.from_user
    ):

        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    await remember_admin_chat(
        message.from_user.id
    )

    await message.answer(
        await admin_text(),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


@dp.message(
    F.text == "👑 Admin"
)
async def admin_button(
    message: Message
):

    await admin_command(
        message
    )


# ============================================================
# ADMIN HOME
# ============================================================

@dp.callback_query(
    F.data == "adm_home"
)
async def admin_home(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    await remember_admin_chat(
        callback.from_user.id
    )

    await callback.message.edit_text(
        await admin_text(),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


# ============================================================
# ADMIN CARDS
# ============================================================

@dp.callback_query(
    F.data == "adm_cards"
)
async def admin_cards(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    await remember_admin_chat(
        callback.from_user.id
    )

    cards = await active_cards()

    if cards:

        text = (
            "💳 <b>TO‘LOV KARTALARI</b>\n\n"
            +
            "\n".join(
                (
                    f"#{card['id']} "
                    f"<code>{card['card_number']}</code>"
                    f" — "
                    f"{card['holder'] or '-'}"
                )
                for card in cards
            )
        )

    else:

        text = (
            "💳 <b>TO‘LOV KARTALARI</b>\n\n"
            "Hali karta qo‘shilmagan."
        )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=cards_keyboard(
            cards
        ),
    )

    await callback.answer()


@dp.callback_query(
    F.data == "adm_card_add"
)
async def admin_card_add(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    admin_state[
        callback.from_user.id
    ] = "add_card"

    await callback.message.answer(
        (
            "💳 <b>Yangi karta</b>\n\n"
            "Quyidagi formatda yuboring:\n\n"
            "<code>8600 1234 5678 9012 | ISM FAMILIYA</code>"
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith(
        "adm_card_del:"
    )
)
async def admin_card_delete(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    try:

        card_id = int(
            callback.data.split(
                ":",
                1
            )[1]
        )

    except Exception:

        await callback.answer(
            "Noto‘g‘ri karta",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        await conn.execute("""
            UPDATE payment_cards
            SET active=FALSE
            WHERE id=$1
        """,
            card_id,
        )

    await callback.answer(
        "Karta o‘chirildi"
    )

    cards = await active_cards()

    await callback.message.edit_reply_markup(
        reply_markup=cards_keyboard(
            cards
        )
    )


# ============================================================
# ADMIN PRICE
# ============================================================

@dp.callback_query(
    F.data == "adm_price"
)
async def admin_price(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    admin_state[
        callback.from_user.id
    ] = "price"

    await callback.message.answer(
        (
            "💰 <b>IQ narxini o‘zgartirish</b>\n\n"
            f"Hozirgi narx: "
            f"<b>{await get_price():,} so‘m</b>\n\n"
            "Yangi summani faqat raqamda yuboring.\n"
            "Masalan: <code>10000</code>"
        ),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# ADMIN MODE
# ============================================================

@dp.callback_query(
    F.data == "adm_mode"
)
async def admin_mode(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    await callback.message.edit_text(
        (
            "⚙️ <b>TO‘LOV REJIMI</b>\n\n"
            f"Hozirgi: "
            f"<code>{await get_payment_mode()}</code>"
        ),
        parse_mode="HTML",
        reply_markup=mode_keyboard(),
    )

    await callback.answer()


@dp.callback_query(
    F.data.startswith(
        "adm_mode:"
    )
)
async def admin_mode_set(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    mode = callback.data.split(
        ":",
        1
    )[1]

    if mode not in VALID_PAYMENT_MODES:

        await callback.answer(
            "Noto‘g‘ri rejim",
            show_alert=True
        )

        return

    await set_setting(
        "payment_mode",
        mode
    )

    await callback.answer(
        "Rejim saqlandi"
    )

    await callback.message.edit_text(
        (
            "✅ <b>To‘lov rejimi o‘zgardi</b>\n\n"
            f"<code>{mode}</code>"
        ),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN PAYMENTS
# ============================================================

@dp.callback_query(
    F.data == "adm_payments"
)
async def admin_payments(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT
                p.id,
                p.user_id,
                p.amount,
                p.purpose,
                p.status,
                p.created_at,

                u.first_name,
                u.username

            FROM iq_payments p

            LEFT JOIN users u
                ON u.user_id=p.user_id

            ORDER BY p.id DESC

            LIMIT 20
        """)

    if not rows:

        text = (
            "📋 <b>TO‘LOVLAR</b>\n\n"
            "Hali to‘lov yo‘q."
        )

    else:

        lines = []

        for row in rows:

            name = (
                row["first_name"]
                or row["username"]
                or str(row["user_id"])
            )

            lines.append(
                (
                    f"#{row['id']} "
                    f"<b>{name}</b>\n"
                    f"💰 {row['amount']:,} so‘m\n"
                    f"🎯 {row['purpose']}\n"
                    f"📌 {row['status']}"
                )
            )

        text = (
            "📋 <b>SO‘NGGI TO‘LOVLAR</b>\n\n"
            +
            "\n\n".join(lines)
        )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="adm_home"
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN STATS
# ============================================================

@dp.callback_query(
    F.data == "adm_stats"
)
async def admin_stats(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users"
        )

        total_attempts = await conn.fetchval(
            "SELECT COUNT(*) FROM iq_attempts"
        )

        active = await conn.fetchval("""
            SELECT COUNT(*)
            FROM users
            WHERE last_seen >
                NOW() - INTERVAL '10 minutes'
        """)

        pending = await conn.fetchval("""
            SELECT COUNT(*)
            FROM iq_payments
            WHERE status='pending'
        """)

        approved = await conn.fetchval("""
            SELECT COUNT(*)
            FROM iq_payments
            WHERE status='approved'
        """)

        revenue = await conn.fetchval("""
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM iq_payments
            WHERE status='approved'
        """)

    text = (
        "📊 <b>STATISTIKA</b>\n\n"

        f"👥 Users: "
        f"<b>{total_users}</b>\n"

        f"🧠 Testlar: "
        f"<b>{total_attempts}</b>\n"

        f"🟢 Faol: "
        f"<b>{active}</b>\n\n"

        f"⏳ Pending: "
        f"<b>{pending}</b>\n"

        f"✅ Approved: "
        f"<b>{approved}</b>\n"

        f"💰 Tasdiqlangan summa: "
        f"<b>{int(revenue):,} so‘m</b>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="adm_home"
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN USERS
# ============================================================

@dp.callback_query(
    F.data == "adm_users"
)
async def admin_users(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT
                user_id,
                first_name,
                username,
                attempts,
                best_score

            FROM users

            ORDER BY
                last_seen DESC

            LIMIT 20
        """)

    lines = [
        "👥 <b>SO‘NGGI FOYDALANUVCHILAR</b>\n"
    ]

    for row in rows:

        name = (
            row["first_name"]
            or row["username"]
            or "User"
        )

        lines.append(
            (
                f"👤 <b>{name}</b>\n"
                f"ID: <code>{row['user_id']}</code>\n"
                f"Test: {row['attempts']}\n"
                f"IQ: {row['best_score'] or '—'}"
            )
        )

    await callback.message.edit_text(
        "\n\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Admin",
                        callback_data="adm_home"
                    )
                ]
            ]
        ),
    )

    await callback.answer()


# ============================================================
# ADMIN TEXT INPUT
# ============================================================

@dp.message()
async def admin_text_input(
    message: Message
):

    if not message.from_user:
        return

    uid = message.from_user.id

    if not is_admin_user(
        message.from_user
    ):
        return

    state = admin_state.get(
        uid
    )

    if not state:
        return

    text = (
        message.text or ""
    ).strip()

    # --------------------------------------------------------
    # ADD CARD
    # --------------------------------------------------------

    if state == "add_card":

        parts = text.split(
            "|",
            1
        )

        card_number = (
            parts[0].strip()
        )

        holder = (
            parts[1].strip()
            if len(parts) == 2
            else ""
        )

        digits = (
            card_number
            .replace(" ", "")
            .replace("-", "")
        )

        if not digits.isdigit():

            await message.answer(
                "❌ Karta raqami noto‘g‘ri."
            )

            return

        if len(digits) < 12:

            await message.answer(
                "❌ Karta raqami juda qisqa."
            )

            return

        assert pool is not None

        async with pool.acquire() as conn:

            await conn.execute("""
                INSERT INTO payment_cards(
                    card_number,
                    holder
                )
                VALUES($1,$2)
            """,
                card_number,
                holder,
            )

        admin_state.pop(
            uid,
            None
        )

        await message.answer(
            "✅ Karta qo‘shildi.",
            reply_markup=main_keyboard(
                True
            ),
        )

        return

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    if state == "price":

        try:

            price = int(text)

            if price < 0:
                raise ValueError

        except Exception:

            await message.answer(
                "❌ Faqat musbat raqam yuboring."
            )

            return

        await set_setting(
            "price_uzs",
            str(price)
        )

        admin_state.pop(
            uid,
            None
        )

        await message.answer(
            f"✅ IQ narxi "
            f"<b>{price:,} so‘m</b> qilib saqlandi.",
            parse_mode="HTML",
            reply_markup=main_keyboard(
                True
            ),
        )

        return


# ============================================================
# PAYMENT PROOF
# ============================================================

@dp.message(
    F.photo
)
async def payment_proof(
    message: Message
):

    if not message.from_user:
        return

    user_id = (
        message.from_user.id
    )

    assert pool is not None

    async with pool.acquire() as conn:

        payment = await conn.fetchrow("""
            SELECT *
            FROM iq_payments

            WHERE user_id=$1
            AND status='pending'

            ORDER BY id DESC

            LIMIT 1
        """,
            user_id,
        )

    if not payment:

        await message.answer(
            "📷 Rasm qabul qilindi, "
            "lekin aktiv to‘lov topilmadi."
        )

        return

    photo = (
        message.photo[-1]
    )

    assert pool is not None

    async with pool.acquire() as conn:

        await conn.execute("""
            UPDATE iq_payments

            SET
                proof_file_id=$2,
                proof_message_id=$3

            WHERE id=$1
        """,
            payment["id"],
            photo.file_id,
            message.message_id,
        )

    admin_id = await get_admin_chat_id()

    if not admin_id:

        # fallback to ADMIN_USER_ID
        admin_id = (
            ADMIN_USER_ID
            if ADMIN_USER_ID
            else None
        )

    if bot and admin_id:

        name = (
            message.from_user.first_name
            or message.from_user.username
            or str(user_id)
        )

        caption = (
            "💳 <b>YANGI TO‘LOV</b>\n\n"

            f"👤 {name}\n"
            f"🆔 <code>{user_id}</code>\n\n"

            f"💰 Summa: "
            f"<b>{payment['amount']:,} so‘m</b>\n"

            f"🎯 Maqsad: "
            f"<b>{payment['purpose']}</b>\n"

            f"🔑 Payment ID: "
            f"<code>{payment['id']}</code>"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[

                [
                    InlineKeyboardButton(
                        text="✅ TASDIQLASH",
                        callback_data=
                            f"payapprove:{payment['id']}"
                    )
                ],

                [
                    InlineKeyboardButton(
                        text="❌ RAD ETISH",
                        callback_data=
                            f"payreject:{payment['id']}"
                    )
                ],

            ]
        )

        try:

            await bot.send_photo(
                admin_id,
                photo.file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception as exc:

            print(
                "ADMIN PAYMENT SEND ERROR:",
                exc
            )

    await message.answer(
        (
            "📷 <b>Chek qabul qilindi.</b>\n\n"
            "⏳ Admin to‘lovni tekshiradi.\n"
            "Tasdiqlangach test avtomatik ochiladi."
        ),
        parse_mode="HTML",
    )


# ============================================================
# PAYMENT APPROVE
# ============================================================

@dp.callback_query(
    F.data.startswith(
        "payapprove:"
    )
)
async def payment_approve(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    try:

        payment_id = int(
            callback.data.split(
                ":",
                1
            )[1]
        )

    except Exception:

        await callback.answer(
            "Noto‘g‘ri payment",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow("""
                SELECT *
                FROM iq_payments
                WHERE id=$1
                FOR UPDATE
            """,
                payment_id,
            )

            if not payment:

                await callback.answer(
                    "Payment topilmadi",
                    show_alert=True
                )

                return

            if payment["status"] != "pending":

                await callback.answer(
                    "Bu payment allaqachon ko‘rilgan.",
                    show_alert=True
                )

                return

            await conn.execute("""
                UPDATE iq_payments

                SET
                    status='approved',
                    reviewer_id=$2,
                    reviewed_at=NOW()

                WHERE id=$1
            """,
                payment_id,
                callback.from_user.id,
            )

    # Notify user.
    if bot:

        try:

            if payment["purpose"] == "battle":

                text = (
                    "⚔️ <b>BATTLE TO‘LOVI TASDIQLANDI</b>\n\n"
                    "Battle oynasiga qayting va davom eting."
                )

            elif payment["purpose"] == "result":

                text = (
                    "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
                    "Natijangiz endi ochildi."
                )

            else:

                text = (
                    "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
                    "🔓 Qayta IQ testini boshlashingiz mumkin."
                )

            await bot.send_message(
                int(payment["user_id"]),
                text,
                parse_mode="HTML",
            )

        except Exception as exc:

            print(
                "PAYMENT USER NOTIFY ERROR:",
                exc
            )

    await callback.answer(
        "To‘lov tasdiqlandi"
    )

    try:

        await callback.message.edit_caption(
            caption=(
                callback.message.caption
                or ""
            )
            +
            "\n\n✅ <b>TASDIQLANDI</b>",
            parse_mode="HTML",
        )

    except Exception:
        pass


# ============================================================
# PAYMENT REJECT
# ============================================================

@dp.callback_query(
    F.data.startswith(
        "payreject:"
    )
)
async def payment_reject(
    callback: CallbackQuery
):

    if not is_admin_user(
        callback.from_user
    ):

        await callback.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )

        return

    try:

        payment_id = int(
            callback.data.split(
                ":",
                1
            )[1]
        )

    except Exception:

        await callback.answer(
            "Noto‘g‘ri payment",
            show_alert=True
        )

        return

    assert pool is not None

    async with pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow("""
                SELECT *
                FROM iq_payments
                WHERE id=$1
                FOR UPDATE
            """,
                payment_id,
            )

            if not payment:

                await callback.answer(
                    "Payment topilmadi",
                    show_alert=True
                )

                return

            if payment["status"] != "pending":

                await callback.answer(
                    "Bu payment allaqachon ko‘rilgan.",
                    show_alert=True
                )

                return

            await conn.execute("""
                UPDATE iq_payments

                SET
                    status='rejected',
                    reviewer_id=$2,
                    reviewed_at=NOW()

                WHERE id=$1
            """,
                payment_id,
                callback.from_user.id,
            )

    if bot:

        try:

            await bot.send_message(
                int(payment["user_id"]),
                (
                    "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
                    "Chekni tekshiring va "
                    "to‘g‘ri to‘lov dalilini yuboring."
                ),
                parse_mode="HTML",
            )

        except Exception as exc:

            print(
                "REJECT NOTIFY ERROR:",
                exc
            )

    await callback.answer(
        "To‘lov rad etildi"
    )

    try:

        await callback.message.edit_caption(
            caption=(
                callback.message.caption
                or ""
            )
            +
            "\n\n❌ <b>RAD ETILDI</b>",
            parse_mode="HTML",
        )

    except Exception:
        pass


# ============================================================
# BATTLE FINISH NOTIFICATION
# ============================================================

async def send_battle_result(
    battle_result: dict
):

    if not bot:
        return

    creator_id = battle_result[
        "creator_id"
    ]

    opponent_id = battle_result[
        "opponent_id"
    ]

    creator_iq = battle_result[
        "creator_iq"
    ]

    opponent_iq = battle_result[
        "opponent_iq"
    ]

    if creator_iq > opponent_iq:

        winner_id = creator_id
        loser_id = opponent_id

    elif opponent_iq > creator_iq:

        winner_id = opponent_id
        loser_id = creator_id

    else:

        winner_id = None
        loser_id = None

    if winner_id:

        winner = await get_user(
            winner_id
        )

        winner_name = (
            f"{winner['first_name']} "
            f"{winner['last_name']}"
        ).strip()

        certificate = make_certificate(
            winner_name,
            max(
                creator_iq,
                opponent_iq
            ),
            f"BATTLE-{winner_id}",
            "BATTLE VICTORY",
        )

        try:

            await bot.send_document(
                winner_id,
                BufferedInputFile(
                    certificate,
                    filename=
                        "battle-victory.png"
                ),
                caption=(
                    "🏆 <b>BATTLE G‘ALABA!</b>\n\n"
                    f"🧠 Sizning IQ: "
                    f"<b>{max(creator_iq, opponent_iq)}</b>\n"
                    f"⚔️ Raqib IQ: "
                    f"<b>{min(creator_iq, opponent_iq)}</b>\n\n"
                    "📜 Battle Victory sertifikati."
                ),
                parse_mode="HTML",
            )

        except Exception as exc:

            print(
                "BATTLE CERT ERROR:",
                exc
            )

        if loser_id:

            try:

                await bot.send_message(
                    loser_id,
                    (
                        "⚔️ <b>Battle yakunlandi.</b>\n\n"
                        f"🧠 Sizning IQ: "
                        f"<b>{min(creator_iq, opponent_iq)}</b>\n"
                        f"🏆 Raqib IQ: "
                        f"<b>{max(creator_iq, opponent_iq)}</b>"
                    ),
                    parse_mode="HTML",
                )

            except Exception:
                pass

    else:

        for uid in [
            creator_id,
            opponent_id,
        ]:

            try:

                await bot.send_message(
                    uid,
                    (
                        "🤝 <b>BATTLE DURANG!</b>\n\n"
                        f"🧠 IQ: <b>{creator_iq}</b>"
                    ),
                    parse_mode="HTML",
                )

            except Exception:
                pass


# ============================================================
# API FINISH WITH BATTLE
# ============================================================

# Keep a separate endpoint wrapper that supports
# battle_id sent by frontend.
#
# The main /api/session/finish above is intentionally simple.
# Battle frontend can call /api/battle/finish.


@app.post("/api/battle/finish")
async def api_battle_finish(
    request: Request
):

    user = await api_user(request)

    try:

        body = await request.json()

        battle_id = int(
            body.get(
                "battle_id"
            )
        )

    except Exception as exc:

        raise HTTPException(
            400,
            "INVALID_BATTLE_ID"
        ) from exc

    result = await finish_session(
        int(user["id"])
    )

    battle_result = await finalize_battle(
        int(user["id"]),
        int(result["iq"]),
        battle_id,
    )

    result["rank"] = await get_rank(
        int(user["id"])
    )

    if battle_result:

        asyncio.create_task(
            send_battle_result(
                battle_result
            )
        )

    return result


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request
):

    if not bot:
        raise HTTPException(
            503,
            "BOT_NOT_READY"
        )

    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        ""
    )

    if not hmac.compare_digest(
        secret,
        webhook_secret()
    ):

        raise HTTPException(
            403,
            "FORBIDDEN"
        )

    data = await request.json()

    update = Update.model_validate(
        data
    )

    await dp.feed_update(
        bot,
        update
    )

    return {
        "ok": True
    }


# ============================================================
# BOT STARTUP
# ============================================================

async def setup_bot():

    global bot
    global BOT_USERNAME

    bot = Bot(
        BOT_TOKEN
    )

    me = await bot.get_me()

    BOT_USERNAME = (
        me.username
        or ""
    )

    # Delete old webhook so polling
    # never conflicts with an old Render instance.
    try:

        await bot.delete_webhook(
            drop_pending_updates=False
        )

    except Exception as exc:

        print(
            "WEBHOOK DELETE:",
            exc
        )

    try:

        await bot.set_chat_menu_button(
            menu_button=
                MenuButtonWebApp(
                    text="🧠 IQ TEST",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    ),
                )
        )

    except Exception as exc:

        print(
            "MENU BUTTON ERROR:",
            exc
        )

    print(
        f"BOT STARTED: @{BOT_USERNAME}"
    )


# ============================================================
# WEB SERVER
# ============================================================

async def run_web():

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server = uvicorn.Server(
        config
    )

    await server.serve()


# ============================================================
# POLLING
# ============================================================

async def run_bot():

    assert bot is not None

    await dp.start_polling(
        bot,
        allowed_updates=
            dp.resolve_used_update_types(),
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    await init_db()

    await setup_bot()

    try:

        await asyncio.gather(
            run_web(),
            run_bot(),
        )

    finally:

        if bot:

            try:
                await bot.session.close()
            except Exception:
                pass

        if pool:

            try:
                await pool.close()
            except Exception:
                pass


if __name__ == "__main__":

    asyncio.run(
        main()
    )