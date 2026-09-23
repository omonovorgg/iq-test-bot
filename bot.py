# ============================================================
# IQ TEST BOT
# Backend v5 — clean architecture
# Python 3.11+
# aiogram 3.x + FastAPI + asyncpg + PostgreSQL
# ============================================================

import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import random
import secrets
import string

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from urllib.parse import parse_qsl

import asyncpg

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not WEBHOOK_SECRET:
    WEBHOOK_SECRET = hashlib.sha256(
        BOT_TOKEN.encode("utf-8")
    ).hexdigest()

BOT_USERNAME = os.getenv(
    "BOT_USERNAME",
    "kinotestbot",
).strip()

ADMIN_USER_ID_RAW = os.getenv(
    "ADMIN_USER_ID",
    "",
).strip()

try:
    ADMIN_USER_ID = int(ADMIN_USER_ID_RAW)
except (TypeError, ValueError):
    ADMIN_USER_ID = 0

try:
    PORT = int(os.getenv("PORT", "10000"))
except ValueError:
    PORT = 10000


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("iq_test_bot")


# ============================================================
# BASIC VALIDATION
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

if not WEBAPP_URL:
    logger.warning("WEBAPP_URL is empty")

if not PUBLIC_BASE_URL:
    logger.warning("PUBLIC_BASE_URL is empty")


# ============================================================
# GLOBAL OBJECTS
# ============================================================

db_pool: asyncpg.Pool | None = None

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# ============================================================
# CONSTANTS
# ============================================================

TEST_TYPES = {
    "iq",
    "eq",
    "pq",
}

PAYMENT_PRODUCTS = {
    "iq",
    "iq_retry",
    "eq",
    "eq_retry",
    "pq",
    "pq_retry",
    "battle",
}

BATTLE_STATUSES = {
    "waiting_for_player",
    "waiting_for_payment",
    "ready",
    "in_progress",
    "player_1_finished",
    "player_2_finished",
    "completed",
    "draw",
    "cancelled",
}

TEST_STATUSES = {
    "active",
    "completed",
    "cancelled",
}

PAYMENT_STATUSES = {
    "pending",
    "approved",
    "rejected",
}


# ============================================================
# IQ QUESTIONS
# ============================================================
#
# Backend is authoritative.
# Frontend only sends answer indexes.
#
# IMPORTANT:
# Do not calculate final IQ score on the frontend
# and trust that value.
# ============================================================

IQ_ANSWERS = [
    {
        "correct": 2,
        "weight": 1,
    },
    {
        "correct": 0,
        "weight": 1,
    },
    {
        "correct": 3,
        "weight": 1,
    },
    {
        "correct": 2,
        "weight": 1,
    },
    {
        "correct": 3,
        "weight": 1,
    },
    {
        "correct": 1,
        "weight": 1,
    },
    {
        "correct": 1,
        "weight": 2,
    },
    {
        "correct": 2,
        "weight": 2,
    },
    {
        "correct": 1,
        "weight": 2,
    },
    {
        "correct": 1,
        "weight": 2,
    },
    {
        "correct": 1,
        "weight": 2,
    },
    {
        "correct": 2,
        "weight": 2,
    },
    {
        "correct": 1,
        "weight": 3,
    },
    {
        "correct": 0,
        "weight": 3,
    },
    {
        "correct": 1,
        "weight": 3,
    },
    {
        "correct": 1,
        "weight": 3,
    },
    {
        "correct": 2,
        "weight": 3,
    },
    {
        "correct": 1,
        "weight": 3,
    },
]


# ============================================================
# EQ QUESTIONS
# ============================================================

EQ_ANSWERS = [
    {
        "scores": [4, 2, 3, 1],
    },
    {
        "scores": [4, 1, 2, 1],
    },
    {
        "scores": [4, 3, 1, 1],
    },
    {
        "scores": [4, 2, 1, 2],
    },
    {
        "scores": [4, 2, 3, 1],
    },
    {
        "scores": [4, 2, 1, 2],
    },
]


# ============================================================
# PQ QUESTIONS
# ============================================================

PQ_ANSWERS = [
    {
        "scores": [2, 1, 2, 1],
    },
    {
        "scores": [4, 2, 1, 0],
    },
    {
        "scores": [4, 1, 2, 2],
    },
    {
        "scores": [4, 3, 1, 0],
    },
    {
        "scores": [4, 2, 1, 0],
    },
    {
        "scores": [4, 3, 1, 0],
    },
]


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
    "iq_price": "0",
    "iq_retry_price": "5000",

    "eq_price": "0",
    "eq_retry_price": "5000",

    "pq_price": "0",
    "pq_retry_price": "5000",

    "battle_price": "7500",

    "support_username": "omono_v",

    "live_mode": "fake",
    "live_fake_base": "95114",
    "live_fake_online": "342",
    "live_fake_delta": "8",
    "live_real_online_minutes": "5",
}


# ============================================================
# ID GENERATORS
# ============================================================

def random_code(
    length: int = 6,
) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(
        secrets.choice(alphabet)
        for _ in range(length)
    )


def gen_code(
    prefix: str = "IQ",
    length: int = 6,
) -> str:
    return f"{prefix}-{random_code(length)}"


def gen_payment_id() -> str:
    return f"PAY-{random_code(10)}"


def gen_session_id() -> str:
    return f"SES-{random_code(16)}"


def gen_battle_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    return "".join(
        secrets.choice(alphabet)
        for _ in range(4)
    )


# ============================================================
# TELEGRAM INIT DATA VALIDATION
# ============================================================
#
# CRITICAL FIX:
#
# 1. parse_qsl() URL-decodes values.
# 2. ONLY "hash" is removed.
# 3. query_id remains.
# 4. signature remains.
# 5. user is NOT double-decoded.
# 6. hmac.compare_digest() is used.
# ============================================================

def validate_init_data(
    init_data: str,
    bot_token: str,
):
    try:
        if not init_data:
            logger.warning(
                "Telegram initData is empty"
            )
            return None

        if not bot_token:
            logger.error(
                "BOT_TOKEN is empty"
            )
            return None

        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
                strict_parsing=True,
            )
        )

        hash_value = parsed.pop(
            "hash",
            None,
        )

        if not hash_value:
            logger.warning(
                "Telegram initData has no hash"
            )
            return None

        # IMPORTANT:
        # query_id and signature are intentionally
        # NOT removed here.

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(
                parsed.items()
            )
        )

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            hash_value,
        ):
            logger.warning(
                "Telegram initData HMAC validation failed"
            )
            return None

        try:
            auth_date = int(
                parsed.get(
                    "auth_date",
                    "0",
                )
            )
        except (TypeError, ValueError):
            logger.warning(
                "Invalid auth_date"
            )
            return None

        if auth_date <= 0:
            return None

        now = datetime.now(
            timezone.utc
        ).timestamp()

        # 48-hour maximum lifetime.
        if now - auth_date > 172800:
            logger.warning(
                "Telegram initData expired"
            )
            return None

        if auth_date - now > 300:
            logger.warning(
                "Telegram initData auth_date is "
                "too far in the future"
            )
            return None

        user_raw = parsed.get("user")

        if not user_raw:
            logger.warning(
                "Telegram initData has no user"
            )
            return None

        # parse_qsl() already decoded it.
        # DO NOT call unquote() here.

        user = json.loads(user_raw)

        if not isinstance(user, dict):
            return None

        if not user.get("id"):
            return None

        return user

    except Exception as exc:
        logger.exception(
            "validate_init_data error: %s",
            exc,
        )
        return None


# ============================================================
# AUTH HELPERS
# ============================================================

def get_user_from_init(
    init_data: str,
):
    return validate_init_data(
        init_data,
        BOT_TOKEN,
    )


async def require_user(
    request: Request,
):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON body",
        )

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid request body",
        )

    init_data = str(
        body.get(
            "initData",
            "",
        )
    ).strip()

    user = get_user_from_init(
        init_data
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    return user, body


# ============================================================
# DATABASE SETTINGS
# ============================================================

async def get_setting(
    key: str,
    default=None,
):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT value
            FROM app_settings
            WHERE key = $1
            """,
            key,
        )

    if not row:
        return default

    return row["value"]


async def get_setting_int(
    key: str,
    default: int = 0,
) -> int:
    value = await get_setting(
        key,
        str(default),
    )

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


async def set_setting(
    key: str,
    value,
):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO app_settings
                (key, value, updated_at)
            VALUES
                ($1, $2, NOW())
            ON CONFLICT (key)
            DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = NOW()
            """,
            key,
            str(value),
        )


# ============================================================
# ADMIN CHECK
# ============================================================

async def is_admin(
    user_id: int,
) -> bool:

    # Primary admin from ENV always wins.
    if ADMIN_USER_ID:
        if int(user_id) == ADMIN_USER_ID:
            return True

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM admins
                WHERE user_id = $1
                LIMIT 1
                """,
                int(user_id),
            )

        return row is not None

    except Exception as exc:
        logger.error(
            "is_admin DB error: %s",
            exc,
        )

        # Do not accidentally remove the
        # ENV admin during a temporary DB problem.
        return bool(
            ADMIN_USER_ID
            and int(user_id) == ADMIN_USER_ID
        )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

async def init_db(
    pool: asyncpg.Pool,
):
    async with pool.acquire() as conn:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,

                language TEXT DEFAULT 'uz',

                full_name TEXT,
                gender TEXT,
                age INTEGER,
                country TEXT,

                last_seen TIMESTAMPTZ
                    DEFAULT NOW(),

                created_at TIMESTAMPTZ
                    DEFAULT NOW(),

                updated_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # ADMINS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                created_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # TEST SESSIONS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                session_id TEXT PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                test_type TEXT NOT NULL,

                status TEXT DEFAULT 'active',

                expires_at TIMESTAMPTZ NOT NULL,

                created_at TIMESTAMPTZ
                    DEFAULT NOW(),

                completed_at TIMESTAMPTZ
            )
            """
        )

        # ----------------------------------------------------
        # TEST ATTEMPTS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_attempts (
                id SERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                test_type TEXT NOT NULL,

                session_id TEXT,

                answers JSONB,

                score INTEGER,
                correct_count INTEGER,
                duration INTEGER,
                weighted INTEGER,

                level TEXT,

                status TEXT DEFAULT 'active',

                payment_status TEXT
                    DEFAULT 'free',

                result_visible BOOLEAN
                    DEFAULT TRUE,

                started_at TIMESTAMPTZ
                    DEFAULT NOW(),

                finished_at TIMESTAMPTZ
            )
            """
        )

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                attempt_id INTEGER
                    REFERENCES test_attempts(id)
                    ON DELETE SET NULL,

                test_type TEXT NOT NULL,

                score INTEGER NOT NULL,

                level TEXT,

                created_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # PAYMENTS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,

                payment_id TEXT UNIQUE NOT NULL,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                product TEXT NOT NULL,

                amount INTEGER NOT NULL,

                status TEXT DEFAULT 'pending',

                attempt_id INTEGER
                    REFERENCES test_attempts(id)
                    ON DELETE SET NULL,

                battle_id INTEGER,

                receipt_file_id TEXT,

                created_at TIMESTAMPTZ
                    DEFAULT NOW(),

                approved_at TIMESTAMPTZ,

                rejected_at TIMESTAMPTZ
            )
            """
        )

        # ----------------------------------------------------
        # PAYMENT CARDS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_cards (
                id SERIAL PRIMARY KEY,

                card_number TEXT NOT NULL,

                holder TEXT,

                bank TEXT,

                active BOOLEAN DEFAULT TRUE,

                created_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # CERTIFICATES
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,

                certificate_id TEXT UNIQUE,

                verification_code TEXT UNIQUE,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                result_id INTEGER,

                score INTEGER,

                type TEXT DEFAULT 'iq',

                full_name TEXT,

                created_at TIMESTAMPTZ
                    DEFAULT NOW()
            )
            """
        )

        # ----------------------------------------------------
        # BATTLES
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS battles (
                id SERIAL PRIMARY KEY,

                battle_code TEXT UNIQUE NOT NULL,

                creator_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                opponent_id BIGINT
                    REFERENCES users(user_id)
                    ON DELETE SET NULL,

                status TEXT
                    DEFAULT 'waiting_for_player',

                winner_id BIGINT
                    REFERENCES users(user_id)
                    ON DELETE SET NULL,

                created_at TIMESTAMPTZ
                    DEFAULT NOW(),

                finished_at TIMESTAMPTZ
            )
            """
        )

        # ----------------------------------------------------
        # BATTLE PLAYERS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS battle_players (
                id SERIAL PRIMARY KEY,

                battle_id INTEGER NOT NULL
                    REFERENCES battles(id)
                    ON DELETE CASCADE,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                payment_status TEXT
                    DEFAULT 'pending',

                test_status TEXT
                    DEFAULT 'not_started',

                session_id TEXT,

                current_question INTEGER
                    DEFAULT 0,

                answers JSONB,

                weighted INTEGER,

                score INTEGER,

                correct_count INTEGER,

                started_at TIMESTAMPTZ,

                finished_at TIMESTAMPTZ,

                UNIQUE (
                    battle_id,
                    user_id
                )
            )
            """
        )

        # ----------------------------------------------------
        # REFERRALS
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,

                referrer_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                referred_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                created_at TIMESTAMPTZ
                    DEFAULT NOW(),

                UNIQUE(referred_id)
            )
            """
        )

        # ----------------------------------------------------
        # INDEXES
        # ----------------------------------------------------

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_results_user_type
            ON results(user_id, test_type)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_attempts_user
            ON test_attempts(user_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_payments_user_status
            ON payments(user_id, status)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_battle_players_battle
            ON battle_players(battle_id)
            """
        )

        # ----------------------------------------------------
        # DEFAULT SETTINGS
        # ----------------------------------------------------

        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                """
                INSERT INTO app_settings
                    (key, value)
                VALUES
                    ($1, $2)
                ON CONFLICT (key)
                DO NOTHING
                """,
                key,
                value,
            )

        # ----------------------------------------------------
        # ENV ADMIN
        # ----------------------------------------------------

        if ADMIN_USER_ID:
            await conn.execute(
                """
                INSERT INTO admins(user_id)
                VALUES($1)
                ON CONFLICT(user_id)
                DO NOTHING
                """,
                ADMIN_USER_ID,
            )

        # ----------------------------------------------------
        # DEFAULT PAYMENT CARD
        # ----------------------------------------------------

        card_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM payment_cards
            """
        )

        if card_count == 0:
            await conn.execute(
                """
                INSERT INTO payment_cards
                    (
                        card_number,
                        holder,
                        bank,
                        active
                    )
                VALUES
                    (
                        '8600 1234 5678 9012',
                        'IQ TEST BOT',
                        'Click',
                        TRUE
                    )
                """
            )

    logger.info(
        "Database initialization completed"
    )


# ============================================================
# USER UPSERT
# ============================================================

async def upsert_user(
    telegram_user,
):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                last_name,
                last_seen,
                updated_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                NOW(),
                NOW()
            )
            ON CONFLICT(user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_seen = NOW(),
                updated_at = NOW()
            """,
            telegram_user.id,
            telegram_user.username,
            telegram_user.first_name,
            telegram_user.last_name,
        )


async def get_user(
    user_id: int,
):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )


# ============================================================
# LANGUAGE
# ============================================================

TEXTS = {
    "uz": {
        "welcome": (
            "Assalomu alaykum, "
            "{name}! 👋"
        ),
        "choose_lang": (
            "Tilni tanlang:"
        ),
    },

    "ru": {
        "welcome": (
            "Здравствуйте, "
            "{name}! 👋"
        ),
        "choose_lang": (
            "Выберите язык:"
        ),
    },

    "en": {
        "welcome": (
            "Hello, "
            "{name}! 👋"
        ),
        "choose_lang": (
            "Choose your language:"
        ),
    },
}


def t(
    lang: str,
    key: str,
    **kwargs,
):
    lang = lang if lang in TEXTS else "uz"

    value = TEXTS[lang].get(
        key,
        TEXTS["uz"].get(
            key,
            key,
        ),
    )

    try:
        return value.format(**kwargs)
    except Exception:
        return value


def language_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🇺🇿 O‘zbekcha",
        callback_data="lang:uz",
    )

    builder.button(
        text="🇷🇺 Русский",
        callback_data="lang:ru",
    )

    builder.button(
        text="🇬🇧 English",
        callback_data="lang:en",
    )

    builder.adjust(1)

    return builder.as_markup()


# ============================================================
# MAIN BOT KEYBOARD
# ============================================================

def main_menu_keyboard(
    lang: str,
):
    builder = InlineKeyboardBuilder()

    if WEBAPP_URL:
        builder.row(
            InlineKeyboardButton(
                text=t(
                    lang,
                    "menu_test",
                ),
                web_app=WebAppInfo(
                    url=WEBAPP_URL.rstrip("/") + "/app"
                ),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🏆 Reyting",
            callback_data="menu:rank",
        ),
        InlineKeyboardButton(
            text="📜 Sertifikat",
            callback_data="menu:cert",
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text="💰 Earn",
            callback_data="menu:earn",
        ),
        InlineKeyboardButton(
            text="❓ Yordam",
            callback_data="menu:help",
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text="🌐 Til",
            callback_data="menu:lang",
        )
    )

    return builder.as_markup()


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def cmd_start(
    message: types.Message,
):
    try:
        await upsert_user(
            message.from_user
        )

        user = await get_user(
            message.from_user.id
        )

        args = (
            message.text or ""
        ).split()

        # ------------------------------
        # REFERRAL
        # ------------------------------

        if (
            len(args) > 1
            and args[1].startswith("ref_")
        ):
            try:
                referrer_id = int(
                    args[1][4:]
                )

                if (
                    referrer_id
                    != message.from_user.id
                ):
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO referrals(
                                referrer_id,
                                referred_id
                            )
                            VALUES($1, $2)
                            ON CONFLICT(referred_id)
                            DO NOTHING
                            """,
                            referrer_id,
                            message.from_user.id,
                        )

            except Exception as exc:
                logger.warning(
                    "Referral error: %s",
                    exc,
                )

        # ------------------------------
        # LANGUAGE
        # ------------------------------

        if (
            not user
            or not user["language"]
        ):
            await message.answer(
                t(
                    "uz",
                    "choose_lang",
                ),
                reply_markup=language_keyboard(),
            )
            return

        lang = (
            user["language"]
            if user["language"] in TEXTS
            else "uz"
        )

        await message.answer(
            t(
                lang,
                "welcome",
                name=(
                    message.from_user.first_name
                    or "do‘stim"
                ),
            ),
            reply_markup=main_menu_keyboard(
                lang
            ),
        )

    except Exception as exc:
        logger.exception(
            "cmd_start error: %s",
            exc,
        )

        await message.answer(
            "Xatolik yuz berdi. "
            "Birozdan keyin qayta urinib ko‘ring."
        )


# ============================================================
# LANGUAGE CALLBACK
# ============================================================

@dp.callback_query(
    F.data.startswith("lang:")
)
async def language_callback(
    callback: CallbackQuery,
):
    try:
        lang = callback.data.split(
            ":",
            1,
        )[1]

        if lang not in TEXTS:
            await callback.answer(
                "Noto‘g‘ri til",
                show_alert=True,
            )
            return

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET
                    language = $1,
                    updated_at = NOW()
                WHERE user_id = $2
                """,
                lang,
                callback.from_user.id,
            )

        await callback.message.edit_text(
            t(
                lang,
                "welcome",
                name=(
                    callback.from_user.first_name
                    or "do‘stim"
                ),
            ),
            reply_markup=main_menu_keyboard(
                lang
            ),
        )

        await callback.answer(
            "Saqlandi"
        )

    except Exception as exc:
        logger.exception(
            "language callback error: %s",
            exc,
        )

        await callback.answer(
            "Xatolik",
            show_alert=True,
        )


# ============================================================
# MENU CALLBACKS
# ============================================================

@dp.callback_query(
    F.data == "menu:lang"
)
async def menu_language(
    callback: CallbackQuery,
):
    await callback.message.edit_text(
        "🌐 Tilni tanlang:",
        reply_markup=language_keyboard(),
    )

    await callback.answer()


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    global db_pool

    logger.info(
        "Starting database pool..."
    )

    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )

    await init_db(
        db_pool
    )

    # ------------------------------
    # TELEGRAM WEBHOOK
    # ------------------------------

    if (
        PUBLIC_BASE_URL
        and WEBHOOK_SECRET
    ):
        try:
            await bot.set_webhook(
                url=(
                    PUBLIC_BASE_URL.rstrip("/")
                    + "/telegram/webhook"
                ),
                secret_token=WEBHOOK_SECRET,
                drop_pending_updates=True,
            )

            logger.info(
                "Telegram webhook configured"
            )

        except Exception as exc:
            logger.exception(
                "Webhook setup failed: %s",
                exc,
            )

    else:
        logger.warning(
            "Webhook was not configured: "
            "PUBLIC_BASE_URL or WEBHOOK_SECRET missing"
        )

    yield

    logger.info(
        "Shutting down..."
    )

    try:
        await bot.delete_webhook()
    except Exception:
        pass

    try:
        await bot.session.close()
    except Exception:
        pass

    if db_pool:
        await db_pool.close()

    logger.info(
        "Shutdown completed"
    )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="IQ TEST BOT",
    lifespan=lifespan,
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory="webapp"
    ),
    name="static",
)


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "SELECT 1"
            )

        return {
            "status": "ok"
        }

    except Exception as exc:
        logger.error(
            "Health check failed: %s",
            exc,
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error"
            },
        )


# ============================================================
# WEB APP
# ============================================================

@app.get(
    "/app",
    response_class=HTMLResponse,
)
async def serve_app():

    file_path = (
        "webapp/index.html"
    )

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:
            return HTMLResponse(
                content=file.read()
            )

    except FileNotFoundError:
        return HTMLResponse(
            content=(
                "<h1>IQ TEST BOT</h1>"
                "<p>webapp/index.html not found.</p>"
            ),
            status_code=404,
        )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post(
    "/telegram/webhook"
)
async def telegram_webhook(
    request: Request,
):
    if WEBHOOK_SECRET:
        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if not hmac.compare_digest(
            received_secret or "",
            WEBHOOK_SECRET,
        ):
            raise HTTPException(
                status_code=403,
                detail="Invalid secret",
            )

    try:
        update_data = await request.json()

        update = types.Update.model_validate(
            update_data,
            context={
                "bot": bot
            },
        )

        await dp.feed_update(
            bot,
            update,
        )

        return {
            "ok": True
        }

    except Exception as exc:
        logger.exception(
            "Webhook processing error: %s",
            exc,
        )

        # Telegram webhook should still receive
        # a valid JSON response.
        return {
            "ok": True
        }
        # ============================================================
# API — USER / PROFILE / CONFIG / LIVE
# ============================================================

@app.post("/api/me")
async def api_me(
    request: Request,
):
    user, body = await require_user(request)

    uid = int(user["id"])

    async with db_pool.acquire() as conn:

        # User mavjud bo'lmasa yaratamiz.
        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                last_name,
                last_seen,
                updated_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                NOW(),
                NOW()
            )
            ON CONFLICT(user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_seen = NOW(),
                updated_at = NOW()
            """,
            uid,
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
        )

        db_user = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            uid,
        )

        # Faqat ko'rinadigan natijalar
        # foydalanuvchining completed holatiga kiradi.
        rows = await conn.fetch(
            """
            SELECT
                LOWER(TRIM(test_type)) AS test_type,
                MAX(score) AS best_score
            FROM results r
            JOIN test_attempts a
                ON a.id = r.attempt_id
            WHERE r.user_id = $1
              AND LOWER(TRIM(r.test_type))
                    IN ('iq', 'eq', 'pq')
              AND a.result_visible = TRUE
            GROUP BY LOWER(TRIM(test_type))
            """,
            uid,
        )

        completed = {
            row["test_type"]: row["best_score"]
            for row in rows
        }

        pending_payments = await conn.fetch(
            """
            SELECT
                payment_id,
                product,
                amount,
                status,
                attempt_id,
                battle_id
            FROM payments
            WHERE user_id = $1
              AND status = 'pending'
            ORDER BY created_at DESC
            """,
            uid,
        )

        active_battles = await conn.fetch(
            """
            SELECT
                b.id,
                b.battle_code,
                b.status
            FROM battles b
            JOIN battle_players bp
                ON bp.battle_id = b.id
            WHERE bp.user_id = $1
              AND b.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            ORDER BY b.created_at DESC
            """,
            uid,
        )

    return {
        "ok": True,

        "user": {
            "user_id": uid,
            "first_name": user.get(
                "first_name"
            ),
            "username": user.get(
                "username"
            ),
            "language": (
                db_user["language"]
                if db_user
                else "uz"
            ),
            "gender": (
                db_user["gender"]
                if db_user
                else None
            ),
            "age": (
                db_user["age"]
                if db_user
                else None
            ),
            "country": (
                db_user["country"]
                if db_user
                else None
            ),
            "full_name": (
                db_user["full_name"]
                if db_user
                else None
            ),
        },

        "completed": completed,

        "pending_payments": [
            dict(row)
            for row in pending_payments
        ],

        "active_battles": [
            dict(row)
            for row in active_battles
        ],
    }


# ============================================================
# PROFILE SAVE
# ============================================================

@app.post("/api/profile/save")
async def api_profile_save(
    request: Request,
):
    user, body = await require_user(request)

    full_name = str(
        body.get(
            "full_name",
            "",
        )
    ).strip()

    gender = str(
        body.get(
            "gender",
            "",
        )
    ).strip()

    country = str(
        body.get(
            "country",
            "",
        )
    ).strip()

    age_raw = body.get("age")

    # ----------------------------------------
    # VALIDATION
    # ----------------------------------------

    if len(full_name) < 3:
        raise HTTPException(
            status_code=400,
            detail="Full name is too short",
        )

    if len(full_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Full name is too long",
        )

    if gender not in (
        "male",
        "female",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid gender",
        )

    if not country:
        raise HTTPException(
            status_code=400,
            detail="Country is required",
        )

    try:
        age = int(age_raw)
    except (
        TypeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid age",
        )

    if not 8 <= age <= 100:
        raise HTTPException(
            status_code=400,
            detail="Invalid age range",
        )

    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE users
            SET
                full_name = $1,
                gender = $2,
                age = $3,
                country = $4,
                updated_at = NOW(),
                last_seen = NOW()
            WHERE user_id = $5
            """,
            full_name,
            gender,
            age,
            country,
            int(user["id"]),
        )

    return {
        "ok": True,
        "message": "Profile saved",
    }


# ============================================================
# LIVE COUNTER
# ============================================================

@app.get("/api/stats/live")
async def api_stats_live():

    mode = await get_setting(
        "live_mode",
        "fake",
    )

    if mode == "real":

        async with db_pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                """
            ) or 0

            minutes = await get_setting_int(
                "live_real_online_minutes",
                5,
            )

            online = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                WHERE last_seen >
                    NOW() -
                    ($1 * INTERVAL '1 minute')
                """,
                minutes,
            ) or 0

    else:

        base_total = await get_setting_int(
            "live_fake_base",
            95114,
        )

        base_online = await get_setting_int(
            "live_fake_online",
            342,
        )

        delta = await get_setting_int(
            "live_fake_delta",
            8,
        )

        total = (
            base_total
            + random.randint(
                -delta,
                delta,
            )
        )

        online = (
            base_online
            + random.randint(
                -delta,
                delta,
            )
        )

    return {
        "ok": True,
        "total": max(
            0,
            int(total),
        ),
        "online": max(
            0,
            int(online),
        ),
        "mode": mode,
    }


# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
async def api_config():

    async with db_pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT key, value
            FROM app_settings
            ORDER BY key
            """
        )

    settings = {
        row["key"]: row["value"]
        for row in rows
    }

    return {
        "ok": True,
        "settings": settings,
    }


# ============================================================
# TEST SESSION START
# ============================================================

@app.post("/api/session/start")
async def api_session_start(
    request: Request,
):
    user, body = await require_user(request)

    test_type = str(
        body.get(
            "test_type",
            "iq",
        )
    ).strip().lower()

    if test_type not in TEST_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid test type",
        )

    uid = int(user["id"])

    session_id = gen_session_id()

    async with db_pool.acquire() as conn:

        # Old active sessions are cancelled.
        await conn.execute(
            """
            UPDATE test_sessions
            SET
                status = 'cancelled',
                completed_at = NOW()
            WHERE user_id = $1
              AND status = 'active'
              AND (
                    expires_at IS NOT NULL
                    AND expires_at <= NOW()
                  OR
                    test_type = $2
                  )
            """,
            uid,
            test_type,
        )

        attempt = await conn.fetchrow(
            """
            INSERT INTO test_attempts (
                user_id,
                test_type,
                session_id,
                status,
                payment_status,
                result_visible
            )
            VALUES (
                $1,
                $2,
                $3,
                'active',
                'free',
                TRUE
            )
            RETURNING id
            """,
            uid,
            test_type,
            session_id,
        )

        await conn.execute(
            """
            INSERT INTO test_sessions (
                session_id,
                user_id,
                test_type,
                status,
                expires_at
            )
            VALUES (
                $1,
                $2,
                $3,
                'active',
                NOW() + INTERVAL '2 hours'
            )
            """,
            session_id,
            uid,
            test_type,
        )

    return {
        "ok": True,
        "session_id": session_id,
        "attempt_id": attempt["id"],
        "test_type": test_type,
    }


# ============================================================
# SCORE CALCULATORS
# ============================================================

def calculate_iq(
    answers,
):
    if not isinstance(
        answers,
        list,
    ):
        answers = []

    weighted = 0
    correct = 0
    max_weight = sum(
        q["weight"]
        for q in IQ_ANSWERS
    )

    for index, question in enumerate(
        IQ_ANSWERS
    ):
        answer = (
            answers[index]
            if index < len(answers)
            else None
        )

        try:
            answer = (
                int(answer)
                if answer is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            answer = None

        if (
            answer is not None
            and answer
            == question["correct"]
        ):
            weighted += question[
                "weight"
            ]
            correct += 1

    score = (
        int(
            70
            + (
                weighted
                / max_weight
            )
            * 60
        )
        if max_weight
        else 70
    )

    if score >= 115:
        level = "YUQORI DARAJA"
    elif score >= 100:
        level = "O‘RTA DARAJA"
    else:
        level = "RIVOJLANTIRISH"

    return (
        score,
        correct,
        weighted,
        level,
    )


def calculate_eq(
    answers,
):
    if not isinstance(
        answers,
        list,
    ):
        answers = []

    total = 0

    for index, question in enumerate(
        EQ_ANSWERS
    ):
        answer = (
            answers[index]
            if index < len(answers)
            else None
        )

        try:
            answer = (
                int(answer)
                if answer is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            answer = None

        scores = question["scores"]

        if (
            answer is not None
            and 0 <= answer < len(scores)
        ):
            total += scores[answer]

    max_score = (
        len(EQ_ANSWERS) * 4
    )

    score = (
        int(
            (total / max_score)
            * 100
        )
        if max_score
        else 0
    )

    if score >= 80:
        level = "JUDA YUQORI"
    elif score >= 60:
        level = "YUQORI"
    elif score >= 40:
        level = "O‘RTA"
    else:
        level = "RIVOJLANTIRISH"

    return (
        score,
        score,
        total,
        level,
    )


def calculate_pq(
    answers,
):
    if not isinstance(
        answers,
        list,
    ):
        answers = []

    total = 0

    for index, question in enumerate(
        PQ_ANSWERS
    ):
        answer = (
            answers[index]
            if index < len(answers)
            else None
        )

        try:
            answer = (
                int(answer)
                if answer is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            answer = None

        scores = question["scores"]

        if (
            answer is not None
            and 0 <= answer < len(scores)
        ):
            total += scores[answer]

    max_score = (
        len(PQ_ANSWERS) * 4
    )

    score = (
        int(
            (total / max_score)
            * 100
        )
        if max_score
        else 0
    )

    if score >= 80:
        level = "JUDA YAXSHI"
    elif score >= 60:
        level = "YAXSHI"
    elif score >= 40:
        level = "O‘RTA"
    else:
        level = "RIVOJLANTIRISH"

    return (
        score,
        score,
        total,
        level,
    )


# ============================================================
# TEST SUBMIT
# ============================================================

@app.post("/api/test/submit")
async def api_test_submit(
    request: Request,
):
    user, body = await require_user(request)

    session_id = str(
        body.get(
            "session_id",
            "",
        )
    ).strip()

    answers = body.get(
        "answers",
        [],
    )

    duration_raw = body.get(
        "duration",
        0,
    )

    if not isinstance(
        answers,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail="Answers must be an array",
        )

    try:
        duration = max(
            0,
            int(duration_raw),
        )
    except (
        TypeError,
        ValueError,
    ):
        duration = 0

    uid = int(user["id"])

    async with db_pool.acquire() as conn:

        session = await conn.fetchrow(
            """
            SELECT *
            FROM test_sessions
            WHERE session_id = $1
              AND user_id = $2
            FOR UPDATE
            """,
            session_id,
            uid,
        )

        if not session:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

        if session["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail="Session already completed",
            )

        if (
            session["expires_at"]
            and session["expires_at"]
            < datetime.now(timezone.utc)
        ):
            await conn.execute(
                """
                UPDATE test_sessions
                SET
                    status = 'cancelled',
                    completed_at = NOW()
                WHERE session_id = $1
                """,
                session_id,
            )

            raise HTTPException(
                status_code=410,
                detail="Session expired",
            )

        attempt = await conn.fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE session_id = $1
              AND user_id = $2
            FOR UPDATE
            """,
            session_id,
            uid,
        )

        if not attempt:
            raise HTTPException(
                status_code=404,
                detail="Attempt not found",
            )

        if attempt["status"] == "completed":
            raise HTTPException(
                status_code=409,
                detail="Attempt already completed",
            )

        test_type = (
            session["test_type"]
            .strip()
            .lower()
        )

        # ----------------------------------------
        # CALCULATE SCORE ON SERVER
        # ----------------------------------------

        if test_type == "iq":

            (
                score,
                correct,
                weighted,
                level,
            ) = calculate_iq(
                answers
            )

        elif test_type == "eq":

            (
                score,
                correct,
                weighted,
                level,
            ) = calculate_eq(
                answers
            )

        elif test_type == "pq":

            (
                score,
                correct,
                weighted,
                level,
            ) = calculate_pq(
                answers
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported test type",
            )

        # ----------------------------------------
        # RETRY DETECTION
        # ----------------------------------------
        #
        # First attempt:
        #   iq / eq / pq
        #
        # Repeated attempt:
        #   iq_retry / eq_retry / pq_retry
        #
        previous_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM test_attempts
            WHERE user_id = $1
              AND test_type = $2
              AND id <> $3
              AND status = 'completed'
            """,
            uid,
            test_type,
            attempt["id"],
        )

        is_retry = (
            int(previous_count or 0)
            > 0
        )

        # ----------------------------------------
        # PRICE
        # ----------------------------------------

        if test_type == "iq":
            product = (
                "iq_retry"
                if is_retry
                else "iq"
            )

        elif test_type == "eq":
            product = (
                "eq_retry"
                if is_retry
                else "eq"
            )

        else:
            product = (
                "pq_retry"
                if is_retry
                else "pq"
            )

        price_key = (
            f"{product}_price"
            if product not in {
                "iq",
                "eq",
                "pq",
            }
            else product + "_price"
        )

        # The setting names are:
        # iq_price
        # iq_retry_price
        # eq_price
        # eq_retry_price
        # pq_price
        # pq_retry_price

        amount = await get_setting_int(
            price_key,
            0,
        )

        if amount > 0:
            payment_status = "pending"
            result_visible = False
        else:
            payment_status = "free"
            result_visible = True

        # ----------------------------------------
        # SAVE ANSWERS + RESULT STATE
        # ----------------------------------------

        await conn.execute(
            """
            UPDATE test_attempts
            SET
                answers = $1::jsonb,
                score = $2,
                correct_count = $3,
                weighted = $4,
                duration = $5,
                level = $6,
                status = 'completed',
                payment_status = $7,
                result_visible = $8,
                finished_at = NOW()
            WHERE id = $9
            """,
            json.dumps(
                answers,
                ensure_ascii=False,
            ),
            score,
            correct,
            weighted,
            duration,
            level,
            payment_status,
            result_visible,
            attempt["id"],
        )

        await conn.execute(
            """
            UPDATE test_sessions
            SET
                status = 'completed',
                completed_at = NOW()
            WHERE session_id = $1
            """,
            session_id,
        )

        # ----------------------------------------
        # RESULT RECORD
        # ----------------------------------------

        result = await conn.fetchrow(
            """
            INSERT INTO results (
                user_id,
                attempt_id,
                test_type,
                score,
                level
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5
            )
            RETURNING id
            """,
            uid,
            attempt["id"],
            test_type,
            score,
            level,
        )

        # ----------------------------------------
        # CERTIFICATE ONLY WHEN VISIBLE
        # ----------------------------------------

        certificate_code = None

        if (
            test_type == "iq"
            and result_visible
        ):
            certificate_code = (
                await create_iq_certificate(
                    conn=conn,
                    user_id=uid,
                    result_id=result["id"],
                    score=score,
                )
            )

    return {
        "ok": True,

        "score": score,
        "correct": correct,
        "total": len(
            IQ_ANSWERS
            if test_type == "iq"
            else EQ_ANSWERS
            if test_type == "eq"
            else PQ_ANSWERS
        ),

        "level": level,
        "weighted": weighted,

        "result_visible": result_visible,

        "payment_required": (
            payment_status == "pending"
        ),

        "payment_product": (
            product
            if payment_status == "pending"
            else None
        ),

        "payment_amount": (
            amount
            if payment_status == "pending"
            else 0
        ),

        "attempt_id": attempt["id"],

        "certificate_code": certificate_code,
    }


# ============================================================
# GET RESULT AFTER PAYMENT
# ============================================================

@app.get(
    "/api/result/{attempt_id}"
)
async def api_result(
    attempt_id: int,
    request: Request,
):
    user, body = await require_user(
        request
    )

    uid = int(user["id"])

    async with db_pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT
                a.id AS attempt_id,
                a.test_type,
                a.score,
                a.correct_count,
                a.duration,
                a.weighted,
                a.level,
                a.payment_status,
                a.result_visible,

                r.id AS result_id

            FROM test_attempts a

            LEFT JOIN results r
                ON r.attempt_id = a.id

            WHERE a.id = $1
              AND a.user_id = $2
            """,
            attempt_id,
            uid,
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Result not found",
            )

        if not row["result_visible"]:
            return {
                "ok": True,
                "result_visible": False,
                "payment_required": True,
                "attempt_id": attempt_id,
            }

        certificate = None

        if (
            row["test_type"] == "iq"
            and row["result_id"]
        ):
            certificate = await conn.fetchrow(
                """
                SELECT
                    verification_code
                FROM certificates
                WHERE result_id = $1
                  AND type = 'iq'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                row["result_id"],
            )

    return {
        "ok": True,
        "result_visible": True,
        "payment_required": False,

        "attempt_id": row[
            "attempt_id"
        ],

        "result_id": row[
            "result_id"
        ],

        "test_type": row[
            "test_type"
        ],

        "score": row[
            "score"
        ],

        "correct": row[
            "correct_count"
        ],

        "duration": row[
            "duration"
        ],

        "weighted": row[
            "weighted"
        ],

        "level": row[
            "level"
        ],

        "certificate_code": (
            certificate[
                "verification_code"
            ]
            if certificate
            else None
        ),
    }


# ============================================================
# CERTIFICATE CREATION
# ============================================================

async def create_iq_certificate(
    conn,
    user_id: int,
    result_id: int,
    score: int,
):
    existing = await conn.fetchrow(
        """
        SELECT verification_code
        FROM certificates
        WHERE result_id = $1
          AND type = 'iq'
        LIMIT 1
        """,
        result_id,
    )

    if existing:
        return existing[
            "verification_code"
        ]

    user = await conn.fetchrow(
        """
        SELECT
            full_name,
            first_name
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    name = (
        (
            user["full_name"]
            or user["first_name"]
        )
        if user
        else "User"
    )

    certificate_id = gen_code(
        "CERT"
    )

    verification_code = gen_code(
        "IQ"
    )

    await conn.execute(
        """
        INSERT INTO certificates (
            certificate_id,
            verification_code,
            user_id,
            result_id,
            score,
            type,
            full_name
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            'iq',
            $6
        )
        """,
        certificate_id,
        verification_code,
        user_id,
        result_id,
        score,
        name,
    )

    return verification_code
    # ============================================================
# PAYMENT
# ============================================================

PAYMENT_PRODUCTS = {
    "iq": "iq_price",
    "iq_retry": "iq_retry_price",
    "eq": "eq_price",
    "eq_retry": "eq_retry_price",
    "pq": "pq_price",
    "pq_retry": "pq_retry_price",
    "battle": "battle_price",
}


@app.post("/api/payment/create")
async def api_payment_create(
    request: Request,
):
    user, body = await require_user(request)

    product = str(
        body.get(
            "product",
            "",
        )
    ).strip().lower()

    attempt_id = body.get(
        "attempt_id"
    )

    battle_id = body.get(
        "battle_id"
    )

    if product not in PAYMENT_PRODUCTS:
        raise HTTPException(
            status_code=400,
            detail="Invalid product",
        )

    price_key = PAYMENT_PRODUCTS[
        product
    ]

    amount = await get_setting_int(
        price_key,
        0,
    )

    uid = int(user["id"])

    # ========================================================
    # TEST PAYMENT
    # ========================================================

    if product != "battle":

        if not attempt_id:
            raise HTTPException(
                status_code=400,
                detail="Attempt ID required",
            )

        try:
            attempt_id = int(
                attempt_id
            )
        except (
            TypeError,
            ValueError,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid attempt ID",
            )

        async with db_pool.acquire() as conn:

            attempt = await conn.fetchrow(
                """
                SELECT
                    id,
                    user_id,
                    test_type,
                    status,
                    payment_status,
                    result_visible
                FROM test_attempts
                WHERE id = $1
                  AND user_id = $2
                """,
                attempt_id,
                uid,
            )

            if not attempt:
                raise HTTPException(
                    status_code=404,
                    detail="Attempt not found",
                )

            test_type = (
                attempt["test_type"]
                .strip()
                .lower()
            )

            # Product va test bir-biriga mos bo'lishi shart.
            expected_products = {
                "iq": {
                    "iq",
                    "iq_retry",
                },
                "eq": {
                    "eq",
                    "eq_retry",
                },
                "pq": {
                    "pq",
                    "pq_retry",
                },
            }

            allowed = expected_products.get(
                test_type,
                set(),
            )

            if product not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Product does not match test",
                )

            if attempt["status"] != "completed":
                raise HTTPException(
                    status_code=400,
                    detail="Test is not completed",
                )

            # Natija allaqachon ochilgan bo'lsa,
            # qayta payment kerak emas.
            if attempt["result_visible"]:
                return {
                    "ok": True,
                    "free": True,
                    "amount": 0,
                    "attempt_id": attempt_id,
                }

            # =================================================
            # FREE PRODUCT
            # =================================================

            if amount <= 0:

                await conn.execute(
                    """
                    UPDATE test_attempts
                    SET
                        payment_status = 'free',
                        result_visible = TRUE
                    WHERE id = $1
                      AND user_id = $2
                    """,
                    attempt_id,
                    uid,
                )

                return {
                    "ok": True,
                    "free": True,
                    "amount": 0,
                    "attempt_id": attempt_id,
                }

            # =================================================
            # EXISTING PENDING PAYMENT
            # =================================================

            existing = await conn.fetchrow(
                """
                SELECT
                    payment_id,
                    amount
                FROM payments
                WHERE user_id = $1
                  AND product = $2
                  AND attempt_id = $3
                  AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uid,
                product,
                attempt_id,
            )

            if existing:

                payment_id = existing[
                    "payment_id"
                ]

            else:

                payment_id = gen_payment_id()

                await conn.execute(
                    """
                    INSERT INTO payments (
                        payment_id,
                        user_id,
                        product,
                        amount,
                        attempt_id,
                        status
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        $4,
                        $5,
                        'pending'
                    )
                    """,
                    payment_id,
                    uid,
                    product,
                    amount,
                    attempt_id,
                )

            cards = await conn.fetch(
                """
                SELECT
                    id,
                    card_number,
                    holder,
                    bank
                FROM payment_cards
                WHERE active = TRUE
                ORDER BY id
                """
            )

        return {
            "ok": True,
            "free": False,
            "payment_id": payment_id,
            "product": product,
            "amount": amount,
            "attempt_id": attempt_id,
            "cards": [
                dict(card)
                for card in cards
            ],
        }

    # ========================================================
    # BATTLE PAYMENT
    # ========================================================

    if not battle_id:
        raise HTTPException(
            status_code=400,
            detail="Battle ID required",
        )

    try:
        battle_id = int(
            battle_id
        )
    except (
        TypeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid battle ID",
        )

    async with db_pool.acquire() as conn:

        battle_player = await conn.fetchrow(
            """
            SELECT
                bp.battle_id,
                bp.user_id,
                bp.payment_status,
                b.status
            FROM battle_players bp
            JOIN battles b
                ON b.id = bp.battle_id
            WHERE bp.battle_id = $1
              AND bp.user_id = $2
            """,
            battle_id,
            uid,
        )

        if not battle_player:
            raise HTTPException(
                status_code=403,
                detail="You are not a battle player",
            )

        if battle_player[
            "payment_status"
        ] == "approved":
            return {
                "ok": True,
                "free": True,
                "amount": 0,
                "battle_id": battle_id,
            }

        if amount <= 0:

            await conn.execute(
                """
                UPDATE battle_players
                SET payment_status = 'approved'
                WHERE battle_id = $1
                  AND user_id = $2
                """,
                battle_id,
                uid,
            )

            await conn.execute(
                """
                UPDATE battles
                SET status = 'ready'
                WHERE id = $1
                  AND status = 'waiting_for_payment'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM battle_players
                      WHERE battle_id = $1
                        AND payment_status != 'approved'
                  )
                """,
                battle_id,
            )

            return {
                "ok": True,
                "free": True,
                "amount": 0,
                "battle_id": battle_id,
            }

        existing = await conn.fetchrow(
            """
            SELECT payment_id
            FROM payments
            WHERE user_id = $1
              AND product = 'battle'
              AND battle_id = $2
              AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            uid,
            battle_id,
        )

        if existing:
            payment_id = existing[
                "payment_id"
            ]
        else:
            payment_id = gen_payment_id()

            await conn.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    user_id,
                    product,
                    amount,
                    battle_id,
                    status
                )
                VALUES (
                    $1,
                    $2,
                    'battle',
                    $3,
                    $4,
                    'pending'
                )
                """,
                payment_id,
                uid,
                amount,
                battle_id,
            )

        cards = await conn.fetch(
            """
            SELECT
                id,
                card_number,
                holder,
                bank
            FROM payment_cards
            WHERE active = TRUE
            ORDER BY id
            """
        )

    return {
        "ok": True,
        "free": False,
        "payment_id": payment_id,
        "product": "battle",
        "amount": amount,
        "battle_id": battle_id,
        "cards": [
            dict(card)
            for card in cards
        ],
    }


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.post(
    "/api/payment/{payment_id}"
)
async def api_payment_get(
    payment_id: str,
    request: Request,
):
    user, body = await require_user(
        request
    )

    uid = int(user["id"])

    async with db_pool.acquire() as conn:

        payment = await conn.fetchrow(
            """
            SELECT
                payment_id,
                product,
                amount,
                status,
                attempt_id,
                battle_id,
                receipt_file_id,
                created_at,
                approved_at
            FROM payments
            WHERE payment_id = $1
              AND user_id = $2
            """,
            payment_id,
            uid,
        )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    return {
        "ok": True,
        "payment": dict(
            payment
        ),
    }


# ============================================================
# RECEIPT UPLOAD FROM WEBAPP
# ============================================================

async def save_payment_receipt(
    user_id: int,
    payment_id: str,
    file_id: str,
):
    async with db_pool.acquire() as conn:

        payment = await conn.fetchrow(
            """
            SELECT *
            FROM payments
            WHERE payment_id = $1
              AND user_id = $2
              AND status = 'pending'
            """,
            payment_id,
            user_id,
        )

        if not payment:
            return False

        await conn.execute(
            """
            UPDATE payments
            SET receipt_file_id = $1
            WHERE payment_id = $2
              AND user_id = $3
            """,
            file_id,
            payment_id,
            user_id,
        )

    return True
    # ============================================================
# ADMIN — PAYMENT APPROVAL / REJECTION
# ============================================================

def payment_product_to_test_type(product: str):
    product = (product or "").strip().lower()

    if product.startswith("iq"):
        return "iq"

    if product.startswith("eq"):
        return "eq"

    if product.startswith("pq"):
        return "pq"

    return None


async def ensure_certificate(
    conn,
    user_id: int,
    result_id: int,
    score: int,
    test_type: str,
):
    """
    Natija uchun sertifikatni faqat bir marta yaratadi.
    """

    existing = await conn.fetchval(
        """
        SELECT id
        FROM certificates
        WHERE result_id = $1
          AND type = $2
        LIMIT 1
        """,
        result_id,
        test_type,
    )

    if existing:
        cert = await conn.fetchrow(
            """
            SELECT verification_code
            FROM certificates
            WHERE id = $1
            """,
            existing,
        )

        return (
            cert["verification_code"]
            if cert
            else None
        )

    user_row = await conn.fetchrow(
        """
        SELECT
            full_name,
            first_name
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    if user_row:
        full_name = (
            user_row["full_name"]
            or user_row["first_name"]
            or "User"
        )
    else:
        full_name = "User"

    certificate_id = gen_code(
        "CERT"
    )

    verification_code = gen_code(
        test_type.upper(),
    )

    await conn.execute(
        """
        INSERT INTO certificates (
            certificate_id,
            verification_code,
            user_id,
            result_id,
            score,
            type,
            full_name
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7
        )
        """,
        certificate_id,
        verification_code,
        user_id,
        result_id,
        score,
        test_type,
        full_name,
    )

    return verification_code


async def notify_payment_approved(
    user_id: int,
    product: str,
):
    try:
        test_type = payment_product_to_test_type(
            product
        )

        if test_type:
            await bot.send_message(
                user_id,
                (
                    "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
                    f"{test_type.upper()} natijangiz endi ochiq."
                ),
            )
        else:
            await bot.send_message(
                user_id,
                "✅ <b>To‘lov tasdiqlandi!</b>",
            )

    except Exception as e:
        logger.warning(
            f"payment notification failed: {e}"
        )


@dp.callback_query(
    F.data.startswith("pay_ok:")
)
async def pay_ok(
    cb: CallbackQuery,
):
    if not await is_admin(
        cb.from_user.id
    ):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        payment_id = cb.data.split(
            ":",
            1,
        )[1].strip()

        if not payment_id:
            await cb.answer(
                "Payment ID noto‘g‘ri",
                show_alert=True,
            )
            return

        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id = $1
                FOR UPDATE
                """,
                payment_id,
            )

            if not payment:
                await cb.answer(
                    "To‘lov topilmadi",
                    show_alert=True,
                )
                return

            if payment["status"] != "pending":
                await cb.answer(
                    "Bu to‘lov allaqachon ko‘rib chiqilgan",
                    show_alert=True,
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET
                    status = 'approved',
                    approved_at = NOW()
                WHERE payment_id = $1
                """,
                payment_id,
            )

            product = (
                payment["product"]
                or ""
            ).strip().lower()

            user_id = int(
                payment["user_id"]
            )

            # =================================================
            # IQ / EQ / PQ
            # =================================================

            test_type = payment_product_to_test_type(
                product
            )

            if (
                test_type
                and payment["attempt_id"]
            ):

                attempt_id = int(
                    payment["attempt_id"]
                )

                attempt = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        user_id,
                        test_type,
                        status,
                        score,
                        result_visible
                    FROM test_attempts
                    WHERE id = $1
                      AND user_id = $2
                    FOR UPDATE
                    """,
                    attempt_id,
                    user_id,
                )

                if not attempt:
                    logger.error(
                        "Payment approved but attempt "
                        "not found: %s",
                        attempt_id,
                    )

                else:

                    actual_type = (
                        attempt["test_type"]
                        or ""
                    ).strip().lower()

                    # Product va attempt bir-biriga
                    # mos kelishini yana tekshiramiz.
                    if actual_type != test_type:
                        logger.error(
                            "Payment/test mismatch: "
                            "payment=%s attempt=%s",
                            product,
                            actual_type,
                        )

                    else:

                        await conn.execute(
                            """
                            UPDATE test_attempts
                            SET
                                payment_status = 'paid',
                                result_visible = TRUE
                            WHERE id = $1
                              AND user_id = $2
                            """,
                            attempt_id,
                            user_id,
                        )

                        result = await conn.fetchrow(
                            """
                            SELECT
                                id,
                                score,
                                test_type
                            FROM results
                            WHERE attempt_id = $1
                              AND user_id = $2
                            ORDER BY id DESC
                            LIMIT 1
                            """,
                            attempt_id,
                            user_id,
                        )

                        if result:

                            await ensure_certificate(
                                conn=conn,
                                user_id=user_id,
                                result_id=int(
                                    result["id"]
                                ),
                                score=int(
                                    result["score"]
                                ),
                                test_type=test_type,
                            )

            # =================================================
            # BATTLE
            # =================================================

            elif (
                product == "battle"
                and payment["battle_id"]
            ):

                battle_id = int(
                    payment["battle_id"]
                )

                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status = 'approved'
                    WHERE battle_id = $1
                      AND user_id = $2
                    """,
                    battle_id,
                    user_id,
                )

                players = await conn.fetch(
                    """
                    SELECT
                        user_id,
                        payment_status
                    FROM battle_players
                    WHERE battle_id = $1
                    """,
                    battle_id,
                )

                if (
                    len(players) >= 2
                    and all(
                        p["payment_status"]
                        == "approved"
                        for p in players
                    )
                ):

                    await conn.execute(
                        """
                        UPDATE battles
                        SET status = 'ready'
                        WHERE id = $1
                          AND status IN (
                              'waiting_for_payment',
                              'waiting_for_player'
                          )
                        """,
                        battle_id,
                    )

                    for player in players:
                        try:
                            await bot.send_message(
                                int(
                                    player["user_id"]
                                ),
                                (
                                    "⚔️ <b>Battle tayyor!</b>\n\n"
                                    "Ikkala ishtirokchi ham "
                                    "to‘lovni tasdiqladi."
                                ),
                            )
                        except Exception:
                            pass

        # =====================================================
        # ADMIN MESSAGE
        # =====================================================

        try:
            if cb.message:
                if cb.message.photo:
                    await cb.message.edit_caption(
                        caption=(
                            "✅ <b>TASDIQLANDI</b>\n\n"
                            f"Payment: <code>{payment_id}</code>"
                        ),
                        reply_markup=None,
                    )
                else:
                    await cb.message.edit_text(
                        (
                            "✅ <b>TASDIQLANDI</b>\n\n"
                            f"Payment: <code>{payment_id}</code>"
                        ),
                        reply_markup=None,
                    )
        except Exception as e:
            logger.warning(
                f"Could not edit payment message: {e}"
            )

        await notify_payment_approved(
            user_id=user_id,
            product=product,
        )

        await cb.answer(
            "To‘lov tasdiqlandi ✅"
        )

    except Exception as e:
        logger.exception(
            f"pay_ok error: {e}"
        )

        await cb.answer(
            "Tasdiqlashda xatolik",
            show_alert=True,
        )


@dp.callback_query(
    F.data.startswith("pay_no:")
)
async def pay_no(
    cb: CallbackQuery,
):
    if not await is_admin(
        cb.from_user.id
    ):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        payment_id = cb.data.split(
            ":",
            1,
        )[1].strip()

        if not payment_id:
            await cb.answer(
                "Payment ID noto‘g‘ri",
                show_alert=True,
            )
            return

        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id = $1
                FOR UPDATE
                """,
                payment_id,
            )

            if not payment:
                await cb.answer(
                    "To‘lov topilmadi",
                    show_alert=True,
                )
                return

            if payment["status"] != "pending":
                await cb.answer(
                    "Bu to‘lov allaqachon ko‘rib chiqilgan",
                    show_alert=True,
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET status = 'rejected'
                WHERE payment_id = $1
                """,
                payment_id,
            )

            if (
                payment["product"] == "battle"
                and payment["battle_id"]
            ):
                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status = 'rejected'
                    WHERE battle_id = $1
                      AND user_id = $2
                    """,
                    int(
                        payment["battle_id"]
                    ),
                    int(
                        payment["user_id"]
                    ),
                )

            user_id = int(
                payment["user_id"]
            )

            product = (
                payment["product"]
                or ""
            )

        try:
            await bot.send_message(
                user_id,
                (
                    "❌ <b>To‘lov rad etildi.</b>\n\n"
                    "Chekni tekshirib, kerak bo‘lsa "
                    "qaytadan yuboring."
                ),
            )
        except Exception:
            pass

        try:
            if cb.message:
                if cb.message.photo:
                    await cb.message.edit_caption(
                        caption=(
                            "❌ <b>RAD ETILDI</b>\n\n"
                            f"Payment: <code>{payment_id}</code>"
                        ),
                        reply_markup=None,
                    )
                else:
                    await cb.message.edit_text(
                        (
                            "❌ <b>RAD ETILDI</b>\n\n"
                            f"Payment: <code>{payment_id}</code>"
                        ),
                        reply_markup=None,
                    )
        except Exception:
            pass

        await cb.answer(
            "To‘lov rad etildi"
        )

    except Exception as e:
        logger.exception(
            f"pay_no error: {e}"
        )

        await cb.answer(
            "Rad etishda xatolik",
            show_alert=True,
        )


# ============================================================
# RECEIPT HANDLER
# ============================================================

@dp.message(F.photo)
async def handle_receipt(
    message: types.Message,
):
    try:
        user_id = int(
            message.from_user.id
        )

        file_id = (
            message.photo[-1].file_id
        )

        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT
                    payment_id,
                    user_id,
                    product,
                    amount,
                    status
                FROM payments
                WHERE user_id = $1
                  AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
            )

            if not payment:
                await message.answer(
                    "⚠️ Faol to‘lov topilmadi."
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET receipt_file_id = $1
                WHERE payment_id = $2
                  AND user_id = $3
                  AND status = 'pending'
                """,
                file_id,
                payment["payment_id"],
                user_id,
            )

        await message.answer(
            (
                "✅ <b>Chek qabul qilindi.</b>\n\n"
                "Admin tekshirganidan keyin "
                "to‘lovingiz tasdiqlanadi."
            )
        )

        # =====================================================
        # ADMIN'GA RASMNING O'ZI + TUGMALAR
        # =====================================================

        if ADMIN_USER_ID:

            keyboard = (
                InlineKeyboardBuilder()
            )

            keyboard.button(
                text="✅ Tasdiqlash",
                callback_data=(
                    f"pay_ok:{payment['payment_id']}"
                ),
            )

            keyboard.button(
                text="❌ Rad etish",
                callback_data=(
                    f"pay_no:{payment['payment_id']}"
                ),
            )

            keyboard.adjust(2)

            caption = (
                "💳 <b>YANGI CHEK</b>\n\n"
                f"👤 User: "
                f"<code>{user_id}</code>\n"
                f"📦 Mahsulot: "
                f"<b>{payment['product']}</b>\n"
                f"💰 Summa: "
                f"<b>{payment['amount']:,} so‘m</b>\n"
                f"🧾 Payment: "
                f"<code>{payment['payment_id']}</code>"
            )

            try:
                await bot.send_photo(
                    chat_id=ADMIN_USER_ID,
                    photo=file_id,
                    caption=caption,
                    reply_markup=(
                        keyboard.as_markup()
                    ),
                )

            except Exception as e:
                logger.error(
                    f"Could not send receipt to admin: {e}"
                )

    except Exception as e:
        logger.exception(
            f"handle_receipt error: {e}"
        )

        try:
            await message.answer(
                "❌ Chekni qabul qilishda xatolik."
            )
        except Exception:
            pass
            # ============================================================
# SESSION + TEST SUBMIT
# ============================================================

@app.post("/api/session/start")
async def api_session_start(request: Request):
    user, body = await require_user(request)

    test_type = str(
        body.get("test_type", "iq")
    ).strip().lower()

    if test_type not in ("iq", "eq", "pq"):
        raise HTTPException(
            status_code=400,
            detail="Invalid test type",
        )

    sid = gen_session_id()

    async with db_pool.acquire() as conn:

        # Eski aktiv sessionlarni yopamiz.
        await conn.execute(
            """
            UPDATE test_sessions
            SET status = 'expired'
            WHERE user_id = $1
              AND status = 'active'
              AND expires_at < NOW()
            """,
            user["id"],
        )

        await conn.execute(
            """
            INSERT INTO test_sessions (
                session_id,
                user_id,
                test_type,
                status,
                expires_at
            )
            VALUES (
                $1,
                $2,
                $3,
                'active',
                NOW() + INTERVAL '2 hours'
            )
            """,
            sid,
            user["id"],
            test_type,
        )

        attempt = await conn.fetchrow(
            """
            INSERT INTO test_attempts (
                user_id,
                test_type,
                session_id,
                status,
                payment_status,
                result_visible
            )
            VALUES (
                $1,
                $2,
                $3,
                'in_progress',
                'free',
                TRUE
            )
            RETURNING id
            """,
            user["id"],
            test_type,
            sid,
        )

    return {
        "ok": True,
        "session_id": sid,
        "attempt_id": attempt["id"],
        "test_type": test_type,
    }


# ============================================================
# TEST SUBMIT
# ============================================================

@app.post("/api/test/submit")
async def api_test_submit(request: Request):
    user, body = await require_user(request)

    sid = str(
        body.get("session_id", "")
    ).strip()

    answers = body.get(
        "answers",
        [],
    )

    duration = body.get(
        "duration",
        0,
    )

    if not sid:
        raise HTTPException(
            status_code=400,
            detail="Session required",
        )

    if not isinstance(answers, list):
        raise HTTPException(
            status_code=400,
            detail="Answers must be a list",
        )

    try:
        duration = max(
            0,
            int(duration),
        )
    except Exception:
        duration = 0

    async with db_pool.acquire() as conn:

        # ----------------------------------------------------
        # SESSION
        # ----------------------------------------------------

        sess = await conn.fetchrow(
            """
            SELECT *
            FROM test_sessions
            WHERE session_id = $1
              AND user_id = $2
            FOR UPDATE
            """,
            sid,
            user["id"],
        )

        if not sess:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

        if sess["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail="Already submitted or session inactive",
            )

        # Session muddati
        if (
            sess["expires_at"]
            and sess["expires_at"] < datetime.now(timezone.utc)
        ):
            await conn.execute(
                """
                UPDATE test_sessions
                SET status = 'expired'
                WHERE session_id = $1
                """,
                sid,
            )

            raise HTTPException(
                status_code=410,
                detail="Session expired",
            )

        # ----------------------------------------------------
        # ATTEMPT
        # ----------------------------------------------------

        attempt = await conn.fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE session_id = $1
              AND user_id = $2
            FOR UPDATE
            """,
            sid,
            user["id"],
        )

        if not attempt:
            raise HTTPException(
                status_code=404,
                detail="Attempt not found",
            )

        if attempt["status"] == "completed":
            raise HTTPException(
                status_code=409,
                detail="Completed",
            )

        test_type = (
            sess["test_type"]
            or ""
        ).strip().lower()

        score = 0
        correct = 0
        level = ""
        weighted = 0

        payment_status = "free"
        result_visible = True

        # ====================================================
        # IQ
        # ====================================================

        if test_type == "iq":

            max_weight = sum(
                int(q["weight"])
                for q in IQ_ANSWERS
            )

            for i, question in enumerate(
                IQ_ANSWERS
            ):

                answer = (
                    answers[i]
                    if i < len(answers)
                    else None
                )

                try:
                    answer = (
                        int(answer)
                        if answer is not None
                        else None
                    )
                except Exception:
                    answer = None

                if (
                    answer is not None
                    and answer
                    == question["correct"]
                ):
                    weighted += int(
                        question["weight"]
                    )
                    correct += 1

            score = (
                int(
                    70
                    + (
                        weighted
                        / max_weight
                    )
                    * 60
                )
                if max_weight
                else 70
            )

            level = (
                "YUQORI DARAJA"
                if score >= 115
                else "O‘RTA DARAJA"
                if score >= 100
                else "RIVOJLANTIRISH"
            )

            price = await get_setting_int(
                "iq_price",
                0,
            )

            if price > 0:
                payment_status = "pending"
                result_visible = False

        # ====================================================
        # EQ
        # ====================================================

        elif test_type == "eq":

            total = 0

            for i, question in enumerate(
                EQ_ANSWERS
            ):

                answer = (
                    answers[i]
                    if i < len(answers)
                    else None
                )

                try:
                    answer = (
                        int(answer)
                        if answer is not None
                        else None
                    )
                except Exception:
                    answer = None

                if (
                    answer is not None
                    and 0 <= answer
                    < len(question["scores"])
                ):
                    total += int(
                        question["scores"][answer]
                    )

            max_score = (
                len(EQ_ANSWERS) * 4
            )

            score = (
                int(
                    (
                        total
                        / max_score
                    )
                    * 100
                )
                if max_score
                else 0
            )

            # EQ uchun PDFdagi mantiq:
            # correct qiymati score bilan teng.
            correct = score

            level = (
                "JUDA YUQORI"
                if score >= 80
                else "YUQORI"
                if score >= 60
                else "O‘RTA"
                if score >= 40
                else "RIVOJLANTIRISH"
            )

            price = await get_setting_int(
                "eq_price",
                0,
            )

            if price > 0:
                payment_status = "pending"
                result_visible = False

        # ====================================================
        # PQ
        # ====================================================

        elif test_type == "pq":

            total = 0

            for i, question in enumerate(
                PQ_ANSWERS
            ):

                answer = (
                    answers[i]
                    if i < len(answers)
                    else None
                )

                try:
                    answer = (
                        int(answer)
                        if answer is not None
                        else None
                    )
                except Exception:
                    answer = None

                if (
                    answer is not None
                    and 0 <= answer
                    < len(question["scores"])
                ):
                    total += int(
                        question["scores"][answer]
                    )

            max_score = (
                len(PQ_ANSWERS) * 4
            )

            score = (
                int(
                    (
                        total
                        / max_score
                    )
                    * 100
                )
                if max_score
                else 0
            )

            correct = score

            level = (
                "JUDA YAXSHI"
                if score >= 80
                else "YAXSHI"
                if score >= 60
                else "O‘RTA"
                if score >= 40
                else "RIVOJLANTIRISH"
            )

            price = await get_setting_int(
                "pq_price",
                0,
            )

            if price > 0:
                payment_status = "pending"
                result_visible = False

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported test type",
            )

        # ====================================================
        # SAVE ATTEMPT
        # ====================================================

        await conn.execute(
            """
            UPDATE test_attempts
            SET
                finished_at = NOW(),
                score = $1,
                correct_count = $2,
                duration = $3,
                status = 'completed',
                payment_status = $4,
                result_visible = $5,
                level = $6
            WHERE id = $7
              AND user_id = $8
            """,
            score,
            correct,
            duration,
            payment_status,
            result_visible,
            level,
            attempt["id"],
            user["id"],
        )

        # Session completed
        await conn.execute(
            """
            UPDATE test_sessions
            SET status = 'completed'
            WHERE session_id = $1
              AND user_id = $2
            """,
            sid,
            user["id"],
        )

        # ====================================================
        # SAVE RESULT
        # ====================================================

        result = await conn.fetchrow(
            """
            INSERT INTO results (
                user_id,
                attempt_id,
                test_type,
                score,
                level
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5
            )
            RETURNING id
            """,
            user["id"],
            attempt["id"],
            test_type,
            score,
            level,
        )

        # ====================================================
        # IQ CERTIFICATE
        # Faqat natija ochiq bo‘lsa.
        # ====================================================

        certificate_code = None

        if (
            test_type == "iq"
            and result_visible
        ):

            certificate_code = (
                await ensure_certificate(
                    conn=conn,
                    user_id=user["id"],
                    result_id=int(
                        result["id"]
                    ),
                    score=score,
                    test_type="iq",
                )
            )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "ok": True,
        "score": score,
        "correct": correct,
        "total": len(answers),
        "level": level,
        "weighted": weighted,
        "result_visible": result_visible,
        "payment_required": (
            payment_status == "pending"
        ),
        "payment_status": payment_status,
        "attempt_id": attempt["id"],
        "certificate_code": certificate_code,
    }


# ============================================================
# RESULT
# ============================================================

@app.get("/api/result/{attempt_id}")
async def api_result(
    attempt_id: int,
    request: Request,
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        attempt = await conn.fetchrow(
            """
            SELECT
                id,
                user_id,
                test_type,
                score,
                correct_count,
                duration,
                status,
                payment_status,
                result_visible,
                level,
                finished_at
            FROM test_attempts
            WHERE id = $1
              AND user_id = $2
            """,
            attempt_id,
            user["id"],
        )

        if not attempt:
            raise HTTPException(
                status_code=404,
                detail="Result not found",
            )

        if not attempt["result_visible"]:
            return {
                "ok": True,
                "visible": False,
                "payment_required": True,
                "payment_status": (
                    attempt["payment_status"]
                ),
                "attempt_id": attempt["id"],
                "test_type": attempt["test_type"],
            }

        result = await conn.fetchrow(
            """
            SELECT
                id,
                score,
                level,
                test_type
            FROM results
            WHERE attempt_id = $1
              AND user_id = $2
            ORDER BY id DESC
            LIMIT 1
            """,
            attempt_id,
            user["id"],
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Result data not found",
            )

        certificate_code = None

        if (
            str(
                attempt["test_type"]
            ).lower()
            == "iq"
        ):
            certificate_code = (
                await conn.fetchval(
                    """
                    SELECT verification_code
                    FROM certificates
                    WHERE result_id = $1
                      AND type = 'iq'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    result["id"],
                )
            )

        return {
            "ok": True,
            "visible": True,
            "payment_required": False,
            "payment_status": (
                attempt["payment_status"]
            ),
            "attempt_id": attempt["id"],
            "test_type": attempt["test_type"],
            "score": result["score"],
            "correct": attempt["correct_count"],
            "duration": attempt["duration"],
            "level": result["level"],
            "certificate_code": certificate_code,
            "finished_at": (
                attempt["finished_at"].isoformat()
                if attempt["finished_at"]
                else None
            ),
        }
        # ============================================================
# PAYMENT API
# ============================================================

@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    user, body = await require_user(request)

    product = str(
        body.get("product", "")
    ).strip().lower()

    attempt_id = body.get("attempt_id")
    battle_id = body.get("battle_id")

    try:
        attempt_id = (
            int(attempt_id)
            if attempt_id is not None
            else None
        )
    except Exception:
        attempt_id = None

    try:
        battle_id = (
            int(battle_id)
            if battle_id is not None
            else None
        )
    except Exception:
        battle_id = None

    # --------------------------------------------------------
    # PRICE MAP
    # --------------------------------------------------------

    price_map = {
        "iq": await get_setting_int(
            "iq_price",
            0,
        ),

        "iq_retry": await get_setting_int(
            "iq_retry_price",
            5000,
        ),

        "eq": await get_setting_int(
            "eq_price",
            0,
        ),

        "eq_retry": await get_setting_int(
            "eq_retry_price",
            5000,
        ),

        "pq": await get_setting_int(
            "pq_price",
            0,
        ),

        "pq_retry": await get_setting_int(
            "pq_retry_price",
            5000,
        ),

        "battle": await get_setting_int(
            "battle_price",
            7500,
        ),
    }

    if product not in price_map:
        raise HTTPException(
            status_code=400,
            detail="Invalid product",
        )

    amount = int(
        price_map[product]
    )

    # --------------------------------------------------------
    # TEST PRODUCT VALIDATION
    # --------------------------------------------------------

    test_type = payment_product_to_test_type(
        product
    )

    if test_type and attempt_id:

        async with db_pool.acquire() as conn:

            attempt = await conn.fetchrow(
                """
                SELECT
                    id,
                    user_id,
                    test_type,
                    status,
                    payment_status,
                    result_visible
                FROM test_attempts
                WHERE id = $1
                  AND user_id = $2
                """,
                attempt_id,
                user["id"],
            )

            if not attempt:
                raise HTTPException(
                    status_code=404,
                    detail="Attempt not found",
                )

            actual_type = (
                str(
                    attempt["test_type"]
                    or ""
                )
                .strip()
                .lower()
            )

            # retry mahsulotini ham asl test
            # bilan tekshiramiz.
            if actual_type != test_type:
                raise HTTPException(
                    status_code=400,
                    detail="Payment/test mismatch",
                )

            if attempt["status"] != "completed":
                raise HTTPException(
                    status_code=409,
                    detail="Test is not completed",
                )

            # Natija allaqachon ochilgan bo‘lsa,
            # yana payment yaratish shart emas.
            if attempt["result_visible"]:
                return {
                    "ok": True,
                    "already_unlocked": True,
                    "free": True,
                    "amount": 0,
                    "attempt_id": attempt_id,
                }

    # --------------------------------------------------------
    # BATTLE VALIDATION
    # --------------------------------------------------------

    if product == "battle":

        if not battle_id:
            raise HTTPException(
                status_code=400,
                detail="Battle ID required",
            )

        async with db_pool.acquire() as conn:

            player = await conn.fetchrow(
                """
                SELECT
                    bp.id,
                    bp.battle_id,
                    bp.user_id,
                    bp.payment_status,
                    b.status
                FROM battle_players bp
                JOIN battles b
                  ON b.id = bp.battle_id
                WHERE bp.battle_id = $1
                  AND bp.user_id = $2
                """,
                battle_id,
                user["id"],
            )

            if not player:
                raise HTTPException(
                    status_code=403,
                    detail="Not a battle member",
                )

            if player["status"] in (
                "completed",
                "draw",
                "cancelled",
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Battle is closed",
                )

            if (
                player["payment_status"]
                == "approved"
            ):
                return {
                    "ok": True,
                    "already_paid": True,
                    "free": True,
                    "amount": 0,
                    "battle_id": battle_id,
                }

    # --------------------------------------------------------
    # ZERO PRICE
    # --------------------------------------------------------

    if amount == 0:

        async with db_pool.acquire() as conn:

            if test_type and attempt_id:

                await conn.execute(
                    """
                    UPDATE test_attempts
                    SET
                        payment_status = 'free',
                        result_visible = TRUE
                    WHERE id = $1
                      AND user_id = $2
                    """,
                    attempt_id,
                    user["id"],
                )

            elif product == "battle":

                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status = 'approved'
                    WHERE battle_id = $1
                      AND user_id = $2
                    """,
                    battle_id,
                    user["id"],
                )

        return {
            "ok": True,
            "free": True,
            "amount": 0,
            "attempt_id": attempt_id,
            "battle_id": battle_id,
        }

    # --------------------------------------------------------
    # EXISTING PENDING PAYMENT
    # --------------------------------------------------------

    async with db_pool.acquire() as conn:

        existing = await conn.fetchrow(
            """
            SELECT
                payment_id,
                product,
                amount,
                status,
                receipt_file_id
            FROM payments
            WHERE user_id = $1
              AND product = $2
              AND status = 'pending'
              AND COALESCE(attempt_id, 0)
                  = COALESCE($3, 0)
              AND COALESCE(battle_id, 0)
                  = COALESCE($4, 0)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user["id"],
            product,
            attempt_id,
            battle_id,
        )

        if existing:

            payment_id = existing[
                "payment_id"
            ]

        else:

            payment_id = gen_payment_id()

            await conn.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    user_id,
                    product,
                    amount,
                    status,
                    attempt_id,
                    battle_id
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    'pending',
                    $5,
                    $6
                )
                """,
                payment_id,
                user["id"],
                product,
                amount,
                attempt_id,
                battle_id,
            )

        # ----------------------------------------------------
        # ACTIVE CARDS
        # ----------------------------------------------------

        cards = await conn.fetch(
            """
            SELECT
                card_number,
                holder,
                bank
            FROM payment_cards
            WHERE active = TRUE
            ORDER BY id ASC
            """
        )

    return {
        "ok": True,
        "free": False,
        "payment_id": payment_id,
        "product": product,
        "amount": amount,
        "attempt_id": attempt_id,
        "battle_id": battle_id,
        "cards": [
            dict(card)
            for card in cards
        ],
    }


# ============================================================
# PAYMENT STATUS
# ============================================================

@app.post("/api/payment/{payment_id}")
async def api_payment_get(
    payment_id: str,
    request: Request,
):
    user, body = await require_user(request)

    payment_id = str(
        payment_id
    ).strip()

    if not payment_id:
        raise HTTPException(
            status_code=400,
            detail="Payment ID required",
        )

    async with db_pool.acquire() as conn:

        payment = await conn.fetchrow(
            """
            SELECT
                payment_id,
                user_id,
                product,
                amount,
                status,
                attempt_id,
                battle_id,
                receipt_file_id,
                created_at,
                approved_at
            FROM payments
            WHERE payment_id = $1
              AND user_id = $2
            """,
            payment_id,
            user["id"],
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found",
            )

    return {
        "ok": True,
        "payment": {
            "payment_id": payment[
                "payment_id"
            ],
            "product": payment[
                "product"
            ],
            "amount": payment[
                "amount"
            ],
            "status": payment[
                "status"
            ],
            "attempt_id": payment[
                "attempt_id"
            ],
            "battle_id": payment[
                "battle_id"
            ],
            "has_receipt": bool(
                payment[
                    "receipt_file_id"
                ]
            ),
            "created_at": (
                payment["created_at"].isoformat()
                if payment["created_at"]
                else None
            ),
            "approved_at": (
                payment["approved_at"].isoformat()
                if payment["approved_at"]
                else None
            ),
        },
    }
    # ============================================================
# BATTLE API
# ============================================================

@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    user, body = await require_user(request)

    price = await get_setting_int(
        "battle_price",
        7500,
    )

    async with db_pool.acquire() as conn:

        # Userning boshqa aktiv Battle'i bormi?
        existing = await conn.fetchrow(
            """
            SELECT
                b.id,
                b.battle_code
            FROM battles b
            JOIN battle_players bp
              ON bp.battle_id = b.id
            WHERE bp.user_id = $1
              AND b.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            LIMIT 1
            """,
            user["id"],
        )

        if existing:
            return {
                "ok": False,
                "error": "ACTIVE_BATTLE_EXISTS",
                "battle_id": existing["id"],
                "code": existing["battle_code"],
            }

        # Unique battle code
        code = gen_battle_code()

        for _ in range(20):

            exists = await conn.fetchval(
                """
                SELECT 1
                FROM battles
                WHERE battle_code = $1
                  AND status IN (
                      'waiting_for_player',
                      'waiting_for_payment',
                      'ready',
                      'in_progress'
                  )
                """,
                code,
            )

            if not exists:
                break

            code = gen_battle_code()

        else:
            raise HTTPException(
                status_code=500,
                detail="Could not generate battle code",
            )

        battle = await conn.fetchrow(
            """
            INSERT INTO battles (
                battle_code,
                creator_id,
                status
            )
            VALUES (
                $1,
                $2,
                'waiting_for_player'
            )
            RETURNING id
            """,
            code,
            user["id"],
        )

        await conn.execute(
            """
            INSERT INTO battle_players (
                battle_id,
                user_id,
                payment_status,
                test_status,
                current_question
            )
            VALUES (
                $1,
                $2,
                'pending',
                'not_started',
                0
            )
            """,
            battle["id"],
            user["id"],
        )

    return {
        "ok": True,
        "battle_id": battle["id"],
        "code": code,
        "price": price,
    }


# ============================================================
# BATTLE JOIN
# ============================================================

@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    user, body = await require_user(request)

    code = str(
        body.get("code", "")
    ).strip().upper()

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Code required",
        )

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE battle_code = $1
            FOR UPDATE
            """,
            code,
        )

        if not battle:
            return {
                "ok": False,
                "error": "NOT_FOUND",
            }

        if battle["creator_id"] == user["id"]:
            return {
                "ok": False,
                "error": "OWN_BATTLE",
            }

        if battle["status"] != "waiting_for_player":
            return {
                "ok": False,
                "error": "BATTLE_NOT_OPEN",
            }

        if battle["opponent_id"]:
            return {
                "ok": False,
                "error": "BATTLE_FULL",
            }

        # Userning boshqa aktiv Battle'i
        existing = await conn.fetchrow(
            """
            SELECT b2.id
            FROM battles b2
            JOIN battle_players bp
              ON bp.battle_id = b2.id
            WHERE bp.user_id = $1
              AND b2.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            LIMIT 1
            """,
            user["id"],
        )

        if existing:
            return {
                "ok": False,
                "error": "ACTIVE_BATTLE_EXISTS",
            }

        await conn.execute(
            """
            UPDATE battles
            SET
                opponent_id = $1,
                status = 'waiting_for_payment'
            WHERE id = $2
            """,
            user["id"],
            battle["id"],
        )

        await conn.execute(
            """
            INSERT INTO battle_players (
                battle_id,
                user_id,
                payment_status,
                test_status,
                current_question
            )
            VALUES (
                $1,
                $2,
                'pending',
                'not_started',
                0
            )
            ON CONFLICT (
                battle_id,
                user_id
            )
            DO NOTHING
            """,
            battle["id"],
            user["id"],
        )

    return {
        "ok": True,
        "battle_id": battle["id"],
    }


# ============================================================
# BATTLE STATUS
# ============================================================

@app.post("/api/battle/{battle_id}")
async def api_battle_get(
    battle_id: int,
    request: Request,
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id = $1
            """,
            battle_id,
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Battle not found",
            )

        players = await conn.fetch(
            """
            SELECT
                bp.user_id,
                bp.payment_status,
                bp.test_status,
                bp.score,
                bp.current_question,
                u.first_name,
                u.username,
                u.full_name
            FROM battle_players bp
            JOIN users u
              ON u.user_id = bp.user_id
            WHERE bp.battle_id = $1
            ORDER BY bp.joined_at ASC
            """,
            battle_id,
        )

        is_member = any(
            p["user_id"] == user["id"]
            for p in players
        )

        if not is_member:
            raise HTTPException(
                status_code=403,
                detail="Not a battle member",
            )

        output_players = []

        for player in players:

            name = (
                player["full_name"]
                or player["first_name"]
                or player["username"]
                or "User"
            )

            item = {
                "user_id": player["user_id"],
                "payment_status": player[
                    "payment_status"
                ],
                "test_status": player[
                    "test_status"
                ],
                "current_question": (
                    player["current_question"]
                    or 0
                ),
                "name": name,
                "is_me": (
                    player["user_id"]
                    == user["id"]
                ),
            }

            # Score faqat Battle tugagandan keyin
            # opponentga ochiladi.
            if (
                player["test_status"]
                == "completed"
                and battle["status"]
                in (
                    "completed",
                    "draw",
                )
            ):
                item["score"] = player[
                    "score"
                ]

            output_players.append(item)

    return {
        "ok": True,
        "battle": {
            "id": battle["id"],
            "code": battle["battle_code"],
            "status": battle["status"],
            "creator_id": battle[
                "creator_id"
            ],
            "opponent_id": battle[
                "opponent_id"
            ],
            "winner_id": battle[
                "winner_id"
            ],
        },
        "players": output_players,
    }


# ============================================================
# BATTLE SYNC
# ============================================================

@app.post("/api/battle/{battle_id}/sync")
async def api_battle_sync(
    battle_id: int,
    request: Request,
):
    user, body = await require_user(request)

    current_question = body.get(
        "current_question",
        0,
    )

    answers = body.get(
        "answers",
        [],
    )

    if not isinstance(answers, list):
        answers = []

    try:
        current_question = max(
            0,
            int(current_question),
        )
    except Exception:
        current_question = 0

    async with db_pool.acquire() as conn:

        player = await conn.fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id = $1
              AND user_id = $2
            """,
            battle_id,
            user["id"],
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Not a battle member",
            )

        battle = await conn.fetchrow(
            """
            SELECT status
            FROM battles
            WHERE id = $1
            """,
            battle_id,
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Battle not found",
            )

        if battle["status"] != "in_progress":
            return {
                "ok": False,
                "error": "BATTLE_NOT_IN_PROGRESS",
            }

        if player["test_status"] == "completed":
            return {
                "ok": False,
                "error": "ALREADY_FINISHED",
            }

        await conn.execute(
            """
            UPDATE battle_players
            SET
                current_question = $1,
                answers = $2::jsonb,
                test_status = 'in_progress'
            WHERE battle_id = $3
              AND user_id = $4
            """,
            current_question,
            json.dumps(answers),
            battle_id,
            user["id"],
        )

    return {
        "ok": True,
        "current_question": current_question,
    }


# ============================================================
# BATTLE START
# ============================================================

@app.post("/api/battle/{battle_id}/start")
async def api_battle_start(
    battle_id: int,
    request: Request,
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id = $1
            FOR UPDATE
            """,
            battle_id,
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Battle not found",
            )

        players = await conn.fetch(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id = $1
            ORDER BY joined_at ASC
            """,
            battle_id,
        )

        if not any(
            p["user_id"] == user["id"]
            for p in players
        ):
            raise HTTPException(
                status_code=403,
                detail="Not a battle member",
            )

        if len(players) < 2:
            return {
                "ok": False,
                "error": "WAITING_FOR_PLAYER",
            }

        if not all(
            p["payment_status"]
            == "approved"
            for p in players
        ):
            return {
                "ok": False,
                "error": "WAITING_FOR_PAYMENT",
            }

        # Battle faqat ready holatidan
        # in_progress ga o'tadi.
        if battle["status"] == "ready":

            await conn.execute(
                """
                UPDATE battles
                SET status = 'in_progress'
                WHERE id = $1
                """,
                battle_id,
            )

        elif battle["status"] != "in_progress":

            return {
                "ok": False,
                "error": "BATTLE_NOT_READY",
                "status": battle["status"],
            }

        player = await conn.fetchrow(
            """
            SELECT session_id
            FROM battle_players
            WHERE battle_id = $1
              AND user_id = $2
            """,
            battle_id,
            user["id"],
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Player not found",
            )

        session_id = player[
            "session_id"
        ]

        if not session_id:

            session_id = gen_session_id()

            await conn.execute(
                """
                UPDATE battle_players
                SET
                    session_id = $1,
                    test_status = 'in_progress'
                WHERE battle_id = $2
                  AND user_id = $3
                """,
                session_id,
                battle_id,
                user["id"],
            )

        else:

            await conn.execute(
                """
                UPDATE battle_players
                SET test_status = 'in_progress'
                WHERE battle_id = $1
                  AND user_id = $2
                  AND test_status != 'completed'
                """,
                battle_id,
                user["id"],
            )

    return {
        "ok": True,
        "session_id": session_id,
        "battle_status": "in_progress",
    }


# ============================================================
# BATTLE FINISH
# ============================================================

@app.post("/api/battle/{battle_id}/finish")
async def api_battle_finish(
    battle_id: int,
    request: Request,
):
    user, body = await require_user(request)

    answers = body.get(
        "answers",
        [],
    )

    if not isinstance(answers, list):
        answers = []

    try:
        duration = max(
            0,
            int(
                body.get(
                    "duration",
                    0,
                )
            ),
        )
    except Exception:
        duration = 0

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id = $1
            FOR UPDATE
            """,
            battle_id,
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Battle not found",
            )

        player = await conn.fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id = $1
              AND user_id = $2
            FOR UPDATE
            """,
            battle_id,
            user["id"],
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Not a battle member",
            )

        if player["test_status"] == "completed":
            raise HTTPException(
                status_code=409,
                detail="Already finished",
            )

        if battle["status"] != "in_progress":
            raise HTTPException(
                status_code=409,
                detail="Battle is not in progress",
            )

        # ----------------------------------------------------
        # IQ SCORE
        # ----------------------------------------------------

        weighted = 0
        correct = 0
        max_weight = 0

        for question in IQ_ANSWERS:
            max_weight += int(
                question["weight"]
            )

        for i, question in enumerate(
            IQ_ANSWERS
        ):

            answer = (
                answers[i]
                if i < len(answers)
                else None
            )

            try:
                answer = (
                    int(answer)
                    if answer is not None
                    else None
                )
            except Exception:
                answer = None

            if (
                answer is not None
                and answer
                == question["correct"]
            ):
                weighted += int(
                    question["weight"]
                )
                correct += 1

        score = (
            int(
                70
                + (
                    weighted
                    / max_weight
                )
                * 60
            )
            if max_weight
            else 70
        )

        # ----------------------------------------------------
        # SAVE PLAYER
        # ----------------------------------------------------

        await conn.execute(
            """
            UPDATE battle_players
            SET
                score = $1,
                weighted = $2,
                answers = $3::jsonb,
                test_status = 'completed',
                current_question = $4,
                finished_at = NOW()
            WHERE battle_id = $5
              AND user_id = $6
            """,
            score,
            weighted,
            json.dumps(answers),
            len(IQ_ANSWERS),
            battle_id,
            user["id"],
        )

        # ----------------------------------------------------
        # CHECK BOTH PLAYERS
        # ----------------------------------------------------

        all_players = await conn.fetch(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id = $1
            ORDER BY joined_at ASC
            """,
            battle_id,
        )

        completed = [
            p
            for p in all_players
            if p["test_status"]
            == "completed"
        ]

        opponent_score = None
        winner_id = None
        final_status = (
            battle["status"]
        )

        if len(completed) >= 2:

            player_1 = completed[0]
            player_2 = completed[1]

            if (
                player_1["user_id"]
                == user["id"]
            ):
                opponent = player_2
            else:
                opponent = player_1

            opponent_score = opponent[
                "score"
            ]

            if (
                player_1["score"]
                > player_2["score"]
            ):

                winner_id = player_1[
                    "user_id"
                ]

                final_status = "completed"

            elif (
                player_2["score"]
                > player_1["score"]
            ):

                winner_id = player_2[
                    "user_id"
                ]

                final_status = "completed"

            else:

                winner_id = None
                final_status = "draw"

            await conn.execute(
                """
                UPDATE battles
                SET
                    status = $1,
                    winner_id = $2,
                    finished_at = NOW()
                WHERE id = $3
                """,
                final_status,
                winner_id,
                battle_id,
            )

            # ------------------------------------------------
            # WINNER CERTIFICATE
            # ------------------------------------------------

            if winner_id:

                winner_player = next(
                    (
                        p
                        for p in completed
                        if p["user_id"]
                        == winner_id
                    ),
                    None,
                )

                if winner_player:

                    user_row = await conn.fetchrow(
                        """
                        SELECT
                            full_name,
                            first_name
                        FROM users
                        WHERE user_id = $1
                        """,
                        winner_id,
                    )

                    winner_name = (
                        (
                            user_row["full_name"]
                            or user_row["first_name"]
                            or "User"
                        )
                        if user_row
                        else "User"
                    )

                    # PDFdagi Battle sertifikat
                    # oqimini saqlaymiz.
                    existing_certificate = await conn.fetchval(
                        """
                        SELECT id
                        FROM certificates
                        WHERE user_id = $1
                          AND type = 'battle'
                          AND result_id = 0
                        LIMIT 1
                        """,
                        winner_id,
                    )

                    if not existing_certificate:

                        await conn.execute(
                            """
                            INSERT INTO certificates (
                                certificate_id,
                                verification_code,
                                user_id,
                                result_id,
                                score,
                                type,
                                full_name
                            )
                            VALUES (
                                $1,
                                $2,
                                $3,
                                0,
                                $4,
                                'battle',
                                $5
                            )
                            """,
                            gen_code("CERT"),
                            gen_code("BT"),
                            winner_id,
                            winner_player["score"],
                            winner_name,
                        )

            # ------------------------------------------------
            # NOTIFY BOTH
            # ------------------------------------------------

            for p in completed:

                try:

                    if final_status == "draw":

                        text = (
                            "⚔️ <b>Battle tugadi!</b>\n\n"
                            "🤝 Natija: <b>DURRANG</b>\n"
                            f"Ball: <b>{p['score']}</b>"
                        )

                    elif p["user_id"] == winner_id:

                        text = (
                            "🏆 <b>Battle tugadi!</b>\n\n"
                            "Siz g‘olib bo‘ldingiz! 🎉\n"
                            f"Ball: <b>{p['score']}</b>"
                        )

                    else:

                        text = (
                            "⚔️ <b>Battle tugadi!</b>\n\n"
                            "Sizning natijangiz saqlandi.\n"
                            f"Ball: <b>{p['score']}</b>"
                        )

                    await bot.send_message(
                        p["user_id"],
                        text,
                    )

                except Exception:
                    pass

        else:

            # Birinchi o‘yinchi tugatdi,
            # ikkinchisi hali ishlayapti.
            await conn.execute(
                """
                UPDATE battles
                SET status = 'player_1_finished'
                WHERE id = $1
                  AND status = 'in_progress'
                """,
                battle_id,
            )

            final_status = (
                "player_1_finished"
            )

    return {
        "ok": True,
        "score": score,
        "weighted": weighted,
        "correct": correct,
        "duration": duration,
        "opponent_score": opponent_score,
        "winner_id": winner_id,
        "final_status": final_status,
    }
    # ============================================================
# CERTIFICATE API
# ============================================================

@app.post("/api/certificate/generate")
async def api_certificate_generate(
    request: Request,
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        cert = await conn.fetchrow(
            """
            SELECT
                c.*,
                u.full_name,
                u.first_name
            FROM certificates c
            JOIN users u
              ON u.user_id = c.user_id
            WHERE c.user_id = $1
              AND c.type = 'iq'
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            user["id"],
        )

        if not cert:
            raise HTTPException(
                status_code=404,
                detail="No certificate",
            )

        name = (
            cert["full_name"]
            or cert["first_name"]
            or "User"
        )

        png = generate_iq_certificate_png(
            name=name,
            score=cert["score"],
            code=cert["verification_code"],
            date=cert["created_at"].strftime(
                "%d.%m.%Y"
            ),
        )

    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition":
                f'attachment; filename="'
                f'{cert["verification_code"]}.png"'
        },
    )


@app.post("/api/certificate/check")
async def api_certificate_check(
    request: Request,
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        cert = await conn.fetchrow(
            """
            SELECT verification_code
            FROM certificates
            WHERE user_id = $1
              AND type = 'iq'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user["id"],
        )

    if not cert:
        return {
            "ok": True,
            "has_certificate": False,
        }

    return {
        "ok": True,
        "has_certificate": True,
        "code": cert[
            "verification_code"
        ],
    }


# ============================================================
# CURRENT USER / ME
# ============================================================

@app.post("/api/me")
async def api_me(
    request: Request,
):
    user, body = await require_user(request)

    uid = user["id"]

    async with db_pool.acquire() as conn:

        # ----------------------------------------
        # USER
        # ----------------------------------------

        db_user = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            uid,
        )

        if not db_user:

            await conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    username,
                    first_name,
                    last_name,
                    last_seen
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    NOW()
                )
                """,
                uid,
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
            )

            db_user = await conn.fetchrow(
                """
                SELECT *
                FROM users
                WHERE user_id = $1
                """,
                uid,
            )

        else:

            # Telegram'dagi yangi ism/username
            # oxirgi qiymat bilan yangilanadi.
            await conn.execute(
                """
                UPDATE users
                SET
                    username = $1,
                    first_name = $2,
                    last_name = $3,
                    last_seen = NOW()
                WHERE user_id = $4
                """,
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
                uid,
            )

        # ----------------------------------------
        # COMPLETED RESULTS
        # ----------------------------------------

        results = await conn.fetch(
            """
            SELECT
                LOWER(TRIM(test_type)) AS tt,
                MAX(score) AS best
            FROM results
            WHERE user_id = $1
              AND LOWER(TRIM(test_type))
                  IN ('iq', 'eq', 'pq')
            GROUP BY LOWER(TRIM(test_type))
            """,
            uid,
        )

        completed = {
            row["tt"]: row["best"]
            for row in results
        }

        # ----------------------------------------
        # PENDING PAYMENTS
        # ----------------------------------------

        pending = await conn.fetch(
            """
            SELECT
                payment_id,
                product,
                amount,
                status
            FROM payments
            WHERE user_id = $1
              AND status = 'pending'
            ORDER BY created_at DESC
            """,
            uid,
        )

        # ----------------------------------------
        # ACTIVE BATTLES
        # ----------------------------------------

        battles = await conn.fetch(
            """
            SELECT
                b.id,
                b.battle_code,
                b.status
            FROM battles b
            JOIN battle_players bp
              ON bp.battle_id = b.id
            WHERE bp.user_id = $1
              AND b.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            ORDER BY b.id DESC
            """,
            uid,
        )

    return {
        "ok": True,

        "user": {
            "user_id": uid,
            "first_name": user.get(
                "first_name"
            ),

            "language": (
                db_user["language"]
                if db_user
                else "uz"
            ),

            "gender": (
                db_user["gender"]
                if db_user
                else None
            ),

            "age": (
                db_user["age"]
                if db_user
                else None
            ),

            "country": (
                db_user["country"]
                if db_user
                else None
            ),

            "full_name": (
                db_user["full_name"]
                if db_user
                else None
            ),
        },

        "completed": completed,

        "pending_payments": [
            dict(row)
            for row in pending
        ],

        "active_battles": [
            dict(row)
            for row in battles
        ],
    }


# ============================================================
# PROFILE SAVE
# ============================================================

@app.post("/api/profile/save")
async def api_profile_save(
    request: Request,
):
    user, body = await require_user(request)

    full_name = str(
        body.get(
            "full_name",
            "",
        )
    ).strip()

    gender = body.get(
        "gender"
    )

    age = body.get(
        "age"
    )

    country = body.get(
        "country"
    )

    # Minimal validation.
    if len(full_name) > 120:
        raise HTTPException(
            status_code=400,
            detail="Full name is too long",
        )

    if gender is not None:
        gender = str(gender).strip()

    if country is not None:
        country = str(country).strip()

    if age is not None:
        try:
            age = int(age)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid age",
            )

        if age < 1 or age > 120:
            raise HTTPException(
                status_code=400,
                detail="Invalid age",
            )

    async with db_pool.acquire() as conn:

        # User mavjud bo'lmasa ham profile
        # save ishlashi uchun yaratamiz.
        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                last_name
            )
            VALUES (
                $1,
                $2,
                $3,
                $4
            )
            ON CONFLICT (user_id)
            DO NOTHING
            """,
            user["id"],
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
        )

        await conn.execute(
            """
            UPDATE users
            SET
                full_name = $1,
                gender = $2,
                age = $3,
                country = $4,
                last_seen = NOW()
            WHERE user_id = $5
            """,
            full_name,
            gender,
            age,
            country,
            user["id"],
        )

    return {
        "ok": True,
    }
    # ============================================================
# LIVE COUNTER
# ============================================================

@app.get("/api/stats/live")
async def api_stats_live():

    mode = await get_setting(
        "live_mode",
        "fake",
    )

    # --------------------------------------------------------
    # REAL MODE
    # --------------------------------------------------------

    if mode == "real":

        async with db_pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                """
            ) or 0

            minutes = await get_setting_int(
                "live_real_online_minutes",
                5,
            )

            online = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM users
                WHERE last_seen >
                    NOW() -
                    INTERVAL '{minutes} minutes'
                """
            ) or 0

    # --------------------------------------------------------
    # FAKE MODE
    # --------------------------------------------------------

    else:

        base_total = await get_setting_int(
            "live_fake_base",
            95114,
        )

        base_online = await get_setting_int(
            "live_fake_online",
            342,
        )

        delta = await get_setting_int(
            "live_fake_delta",
            8,
        )

        # Salbiy qiymatga tushib ketmasin.
        total = max(
            0,
            base_total
            + random.randint(
                -delta,
                delta,
            ),
        )

        online = max(
            0,
            base_online
            + random.randint(
                -delta,
                delta,
            ),
        )

    return {
        "ok": True,
        "total": total,
        "online": online,
        "mode": mode,
    }


# ============================================================
# APP CONFIG
# ============================================================

@app.get("/api/config")
async def api_config():

    async with db_pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                key,
                value
            FROM app_settings
            ORDER BY key
            """
        )

    settings = {
        row["key"]: row["value"]
        for row in rows
    }

    return {
        "ok": True,
        "settings": settings,
    }


# ============================================================
# TEST SESSION START
# ============================================================

@app.post("/api/session/start")
async def api_session_start(
    request: Request,
):
    user, body = await require_user(request)

    test_type = str(
        body.get(
            "test_type",
            "iq",
        )
    ).strip().lower()

    allowed_types = {
        "iq",
        "eq",
        "pq",
    }

    if test_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid test type",
        )

    session_id = gen_session_id()

    async with db_pool.acquire() as conn:

        # ----------------------------------------------------
        # SESSION
        # ----------------------------------------------------

        await conn.execute(
            """
            INSERT INTO test_sessions (
                session_id,
                user_id,
                test_type,
                status,
                started_at,
                expires_at
            )
            VALUES (
                $1,
                $2,
                $3,
                'active',
                NOW(),
                NOW() + INTERVAL '2 hours'
            )
            """,
            session_id,
            user["id"],
            test_type,
        )

        # ----------------------------------------------------
        # ATTEMPT
        # ----------------------------------------------------

        attempt = await conn.fetchrow(
            """
            INSERT INTO test_attempts (
                user_id,
                test_type,
                session_id,
                started_at,
                status,
                payment_status,
                result_visible
            )
            VALUES (
                $1,
                $2,
                $3,
                NOW(),
                'in_progress',
                'free',
                TRUE
            )
            RETURNING id
            """,
            user["id"],
            test_type,
            session_id,
        )

    return {
        "ok": True,
        "session_id": session_id,
        "attempt_id": attempt["id"],
        "test_type": test_type,
    }
    # ============================================================
# PAYMENT ADMIN CALLBACKS
# ============================================================

@dp.callback_query(F.data.startswith("pay_ok:"))
async def pay_ok(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo‘q", show_alert=True)
        return

    try:
        pid = cb.data.split(":", 1)[1]

        async with db_pool.acquire() as conn:
            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                """,
                pid
            )

            if not payment:
                await cb.answer("To‘lov topilmadi", show_alert=True)
                return

            if payment["status"] != "pending":
                await cb.answer("Bu to‘lov allaqachon ko‘rib chiqilgan", show_alert=True)
                return

            # --------------------------------------------
            # PAYMENT -> APPROVED
            # --------------------------------------------

            await conn.execute(
                """
                UPDATE payments
                SET status='approved',
                    approved_at=NOW()
                WHERE payment_id=$1
                """,
                pid
            )

            product = payment["product"]
            user_id = payment["user_id"]
            attempt_id = payment["attempt_id"]
            battle_id = payment["battle_id"]

            # --------------------------------------------
            # IQ / EQ / PQ TEST PAYMENT
            # --------------------------------------------

            if product in (
                "iq",
                "iq_retry",
                "eq",
                "eq_retry",
                "pq",
                "pq_retry",
            ) and attempt_id:

                await conn.execute(
                    """
                    UPDATE test_attempts
                    SET payment_status='paid',
                        result_visible=TRUE
                    WHERE id=$1
                    """,
                    attempt_id
                )

                # IQ certificate
                if product in ("iq", "iq_retry"):
                    result = await conn.fetchrow(
                        """
                        SELECT id, score
                        FROM results
                        WHERE attempt_id=$1
                        LIMIT 1
                        """,
                        attempt_id
                    )

                    if result:
                        certificate_exists = await conn.fetchval(
                            """
                            SELECT 1
                            FROM certificates
                            WHERE result_id=$1
                              AND type='iq'
                            LIMIT 1
                            """,
                            result["id"]
                        )

                        if not certificate_exists:
                            user_row = await conn.fetchrow(
                                """
                                SELECT full_name, first_name
                                FROM users
                                WHERE user_id=$1
                                """,
                                user_id
                            )

                            if user_row:
                                full_name = (
                                    user_row["full_name"]
                                    or user_row["first_name"]
                                    or "User"
                                )
                            else:
                                full_name = "User"

                            await conn.execute(
                                """
                                INSERT INTO certificates (
                                    certificate_id,
                                    verification_code,
                                    user_id,
                                    result_id,
                                    score,
                                    type,
                                    full_name
                                )
                                VALUES (
                                    $1,
                                    $2,
                                    $3,
                                    $4,
                                    $5,
                                    'iq',
                                    $6
                                )
                                """,
                                gen_code("CERT"),
                                gen_code("IQ"),
                                user_id,
                                result["id"],
                                result["score"],
                                full_name
                            )

                # ----------------------------------------
                # USER NOTIFICATION
                # ----------------------------------------

                product_names = {
                    "iq": "IQ testi",
                    "iq_retry": "IQ qayta topshirish",
                    "eq": "EQ testi",
                    "eq_retry": "EQ qayta topshirish",
                    "pq": "PQ testi",
                    "pq_retry": "PQ qayta topshirish",
                }

                product_name = product_names.get(
                    product,
                    "Test"
                )

                try:
                    await bot.send_message(
                        user_id,
                        (
                            "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
                            f"📋 {product_name}\n\n"
                            "Natijangiz endi ochiq."
                        )
                    )
                except Exception:
                    pass

            # --------------------------------------------
            # BATTLE PAYMENT
            # --------------------------------------------

            elif product == "battle" and battle_id:

                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status='approved'
                    WHERE battle_id=$1
                      AND user_id=$2
                    """,
                    battle_id,
                    user_id
                )

                players = await conn.fetch(
                    """
                    SELECT user_id, payment_status
                    FROM battle_players
                    WHERE battle_id=$1
                    ORDER BY joined_at ASC
                    """,
                    battle_id
                )

                if (
                    len(players) >= 2
                    and all(
                        player["payment_status"] == "approved"
                        for player in players
                    )
                ):
                    await conn.execute(
                        """
                        UPDATE battles
                        SET status='ready'
                        WHERE id=$1
                          AND status='waiting_for_payment'
                        """,
                        battle_id
                    )

                    for player in players:
                        try:
                            await bot.send_message(
                                player["user_id"],
                                (
                                    "⚔️ <b>Battle tayyor!</b>\n\n"
                                    "Ikkala ishtirokchining to‘lovi "
                                    "tasdiqlandi.\n"
                                    "Testni boshlashingiz mumkin."
                                )
                            )
                        except Exception:
                            pass

                else:
                    try:
                        await bot.send_message(
                            user_id,
                            (
                                "✅ <b>Battle to‘lovi tasdiqlandi!</b>\n\n"
                                "Ikkinchi ishtirokchining to‘lovi "
                                "kutilmoqda."
                            )
                        )
                    except Exception:
                        pass

            else:
                # Noma'lum yoki noto‘g‘ri payment bog‘lanishi
                logger.warning(
                    "Approved payment has unsupported relation: "
                    f"payment={pid}, product={product}, "
                    f"attempt_id={attempt_id}, battle_id={battle_id}"
                )

        # --------------------------------------------
        # ADMIN MESSAGE UPDATE
        # --------------------------------------------

        try:
            if cb.message:
                if cb.message.caption:
                    await cb.message.edit_caption(
                        caption="✅ <b>Tasdiqlandi</b>"
                    )
                else:
                    await cb.message.edit_text(
                        "✅ <b>Tasdiqlandi</b>"
                    )
        except Exception:
            pass

        await cb.answer("To‘lov tasdiqlandi")

    except Exception as e:
        logger.exception(f"pay_ok error: {e}")
        await cb.answer(
            "Xatolik yuz berdi",
            show_alert=True
        )


# ============================================================
# PAYMENT REJECT
# ============================================================

@dp.callback_query(F.data.startswith("pay_no:"))
async def pay_no(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo‘q", show_alert=True)
        return

    try:
        pid = cb.data.split(":", 1)[1]

        async with db_pool.acquire() as conn:
            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                """,
                pid
            )

            if not payment:
                await cb.answer(
                    "To‘lov topilmadi",
                    show_alert=True
                )
                return

            if payment["status"] != "pending":
                await cb.answer(
                    "Bu to‘lov allaqachon ko‘rib chiqilgan",
                    show_alert=True
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET status='rejected'
                WHERE payment_id=$1
                """,
                pid
            )

            # Battle bo‘lsa, player payment holatini ham rad qilamiz
            if (
                payment["product"] == "battle"
                and payment["battle_id"]
            ):
                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status='rejected'
                    WHERE battle_id=$1
                      AND user_id=$2
                    """,
                    payment["battle_id"],
                    payment["user_id"]
                )

            # Userga xabar
            try:
                await bot.send_message(
                    payment["user_id"],
                    (
                        "❌ <b>To‘lov rad etildi.</b>\n\n"
                        "Yuborgan chekingiz tasdiqlanmadi.\n"
                        "Iltimos, to‘g‘ri chek yuboring."
                    )
                )
            except Exception:
                pass

        # Admin xabarini yangilash
        try:
            if cb.message:
                if cb.message.caption:
                    await cb.message.edit_caption(
                        caption="❌ <b>Rad etildi</b>"
                    )
                else:
                    await cb.message.edit_text(
                        "❌ <b>Rad etildi</b>"
                    )
        except Exception:
            pass

        await cb.answer("To‘lov rad etildi")

    except Exception as e:
        logger.exception(f"pay_no error: {e}")
        await cb.answer(
            "Xatolik yuz berdi",
            show_alert=True
        )


# ============================================================
# RECEIPT HANDLER
# ============================================================

@dp.message(F.photo)
async def handle_receipt(message: types.Message):
    try:
        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT
                    payment_id,
                    user_id,
                    product,
                    amount
                FROM payments
                WHERE user_id=$1
                  AND status='pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                message.from_user.id
            )

            if not payment:
                return

            # Eng katta sifatdagi rasm
            file_id = message.photo[-1].file_id

            await conn.execute(
                """
                UPDATE payments
                SET receipt_file_id=$1
                WHERE payment_id=$2
                """,
                file_id,
                payment["payment_id"]
            )

            await message.answer(
                "✅ <b>Chek qabul qilindi.</b>\n\n"
                "Admin tekshirganidan keyin "
                "to‘lovingiz tasdiqlanadi."
            )

            # --------------------------------------------
            # ADMIN GA CHEK + BUTTONLAR
            # --------------------------------------------

            if ADMIN_USER_ID:
                try:
                    keyboard = InlineKeyboardBuilder()

                    keyboard.button(
                        text="✅ Tasdiqlash",
                        callback_data=(
                            f"pay_ok:{payment['payment_id']}"
                        )
                    )

                    keyboard.button(
                        text="❌ Rad etish",
                        callback_data=(
                            f"pay_no:{payment['payment_id']}"
                        )
                    )

                    keyboard.adjust(2)

                    caption = (
                        "💳 <b>YANGI TO‘LOV CHEKI</b>\n\n"
                        f"👤 User: "
                        f"<code>{payment['user_id']}</code>\n"
                        f"📦 Mahsulot: "
                        f"<b>{payment['product']}</b>\n"
                        f"💰 Summa: "
                        f"<b>{payment['amount']:,} so‘m</b>\n"
                        f"🆔 Payment: "
                        f"<code>{payment['payment_id']}</code>"
                    )

                    await bot.send_photo(
                        ADMIN_USER_ID,
                        photo=file_id,
                        caption=caption,
                        reply_markup=keyboard.as_markup()
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to send receipt to admin: {e}"
                    )

    except Exception as e:
        logger.exception(
            f"handle_receipt error: {e}"
        )
        # ============================================================
# CERTIFICATE API
# ============================================================

@app.post("/api/certificate/generate")
async def api_certificate_generate(request: Request):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow(
            """
            SELECT
                c.*,
                u.full_name,
                u.first_name
            FROM certificates c
            JOIN users u ON u.user_id = c.user_id
            WHERE c.user_id=$1
              AND c.type='iq'
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            user["id"]
        )

        if not cert:
            raise HTTPException(
                status_code=404,
                detail="No certificate"
            )

        name = (
            cert["full_name"]
            or cert["first_name"]
            or "User"
        )

        png = generate_iq_certificate_png(
            name=name,
            score=cert["score"],
            code=cert["verification_code"],
            date=cert["created_at"].strftime("%d.%m.%Y")
        )

        return Response(
            content=png,
            media_type="image/png",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{cert["verification_code"]}.png"'
            }
        )


@app.post("/api/certificate/check")
async def api_certificate_check(request: Request):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow(
            """
            SELECT verification_code
            FROM certificates
            WHERE user_id=$1
              AND type='iq'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user["id"]
        )

        if not cert:
            return {
                "ok": True,
                "has_certificate": False
            }

        return {
            "ok": True,
            "has_certificate": True,
            "code": cert["verification_code"]
        }


# ============================================================
# BATTLE
# ============================================================

@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    user, body = await require_user(request)

    price = await get_setting_int(
        "battle_price",
        7500
    )

    async with db_pool.acquire() as conn:

        existing = await conn.fetchrow(
            """
            SELECT
                b.id,
                b.battle_code
            FROM battles b
            JOIN battle_players bp
                ON bp.battle_id = b.id
            WHERE bp.user_id=$1
              AND b.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            """,
            user["id"]
        )

        if existing:
            return {
                "ok": False,
                "error": "ACTIVE_BATTLE_EXISTS",
                "battle_id": existing["id"],
                "code": existing["battle_code"]
            }

        code = gen_battle_code()

        for _ in range(20):
            exists = await conn.fetchval(
                """
                SELECT 1
                FROM battles
                WHERE battle_code=$1
                  AND status IN (
                      'waiting_for_player',
                      'waiting_for_payment',
                      'ready',
                      'in_progress'
                  )
                """,
                code
            )

            if not exists:
                break

            code = gen_battle_code()

        battle = await conn.fetchrow(
            """
            INSERT INTO battles (
                battle_code,
                creator_id,
                status
            )
            VALUES (
                $1,
                $2,
                'waiting_for_player'
            )
            RETURNING id
            """,
            code,
            user["id"]
        )

        await conn.execute(
            """
            INSERT INTO battle_players (
                battle_id,
                user_id,
                payment_status,
                test_status
            )
            VALUES (
                $1,
                $2,
                'pending',
                'not_started'
            )
            """,
            battle["id"],
            user["id"]
        )

        return {
            "ok": True,
            "battle_id": battle["id"],
            "code": code,
            "price": price
        }


@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    user, body = await require_user(request)

    code = body.get(
        "code",
        ""
    ).strip().upper()

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Code required"
        )

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE battle_code=$1
            """,
            code
        )

        if not battle:
            return {
                "ok": False,
                "error": "NOT_FOUND"
            }

        if battle["creator_id"] == user["id"]:
            return {
                "ok": False,
                "error": "OWN_BATTLE"
            }

        if battle["status"] != "waiting_for_player":
            return {
                "ok": False,
                "error": "BATTLE_NOT_OPEN"
            }

        if battle["opponent_id"]:
            return {
                "ok": False,
                "error": "BATTLE_FULL"
            }

        existing = await conn.fetchrow(
            """
            SELECT b2.id
            FROM battles b2
            JOIN battle_players bp
                ON bp.battle_id = b2.id
            WHERE bp.user_id=$1
              AND b2.status NOT IN (
                  'completed',
                  'draw',
                  'cancelled'
              )
            """,
            user["id"]
        )

        if existing:
            return {
                "ok": False,
                "error": "ACTIVE_BATTLE_EXISTS"
            }

        await conn.execute(
            """
            UPDATE battles
            SET opponent_id=$1,
                status='waiting_for_payment'
            WHERE id=$2
            """,
            user["id"],
            battle["id"]
        )

        await conn.execute(
            """
            INSERT INTO battle_players (
                battle_id,
                user_id,
                payment_status,
                test_status
            )
            VALUES (
                $1,
                $2,
                'pending',
                'not_started'
            )
            ON CONFLICT (
                battle_id,
                user_id
            )
            DO NOTHING
            """,
            battle["id"],
            user["id"]
        )

        return {
            "ok": True,
            "battle_id": battle["id"]
        }


# ============================================================
# BATTLE STATUS
# ============================================================

@app.post("/api/battle/{battle_id}")
async def api_battle_get(
    battle_id: int,
    request: Request
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id=$1
            """,
            battle_id
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )

        players = await conn.fetch(
            """
            SELECT
                bp.user_id,
                bp.payment_status,
                bp.test_status,
                bp.score,
                bp.current_question,
                u.first_name,
                u.username,
                u.full_name
            FROM battle_players bp
            JOIN users u
                ON u.user_id = bp.user_id
            WHERE bp.battle_id=$1
            """,
            battle_id
        )

        is_member = any(
            p["user_id"] == user["id"]
            for p in players
        )

        if not is_member:
            raise HTTPException(
                status_code=403,
                detail="Not member"
            )

        output = []

        for player in players:
            item = {
                "user_id": player["user_id"],
                "payment_status": player["payment_status"],
                "test_status": player["test_status"],
                "current_question":
                    player["current_question"] or 0,
                "name":
                    player["full_name"]
                    or player["first_name"]
                    or player["username"]
                    or "User",
                "is_me":
                    player["user_id"] == user["id"]
            }

            if (
                player["test_status"] == "completed"
                and battle["status"] in (
                    "completed",
                    "draw"
                )
            ):
                item["score"] = player["score"]

            output.append(item)

        return {
            "ok": True,
            "battle": {
                "id": battle["id"],
                "code": battle["battle_code"],
                "status": battle["status"],
                "creator_id": battle["creator_id"],
                "opponent_id": battle["opponent_id"],
                "winner_id": battle["winner_id"]
            },
            "players": output
        }


# ============================================================
# BATTLE SYNC
# ============================================================

@app.post("/api/battle/{battle_id}/sync")
async def api_battle_sync(
    battle_id: int,
    request: Request
):
    user, body = await require_user(request)

    current_question = body.get(
        "current_question",
        0
    )

    answers = body.get(
        "answers",
        []
    )

    async with db_pool.acquire() as conn:

        player = await conn.fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id=$1
              AND user_id=$2
            """,
            battle_id,
            user["id"]
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Not member"
            )

        await conn.execute(
            """
            UPDATE battle_players
            SET current_question=$1,
                answers=$2::jsonb,
                test_status='in_progress'
            WHERE battle_id=$3
              AND user_id=$4
            """,
            current_question,
            json.dumps(answers),
            battle_id,
            user["id"]
        )

        return {
            "ok": True
        }


# ============================================================
# BATTLE START
# ============================================================

@app.post("/api/battle/{battle_id}/start")
async def api_battle_start(
    battle_id: int,
    request: Request
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id=$1
            """,
            battle_id
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )

        players = await conn.fetch(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id=$1
            """,
            battle_id
        )

        if len(players) < 2:
            return {
                "ok": False,
                "error": "WAITING_FOR_PLAYER"
            }

        if not all(
            p["payment_status"] == "approved"
            for p in players
        ):
            return {
                "ok": False,
                "error": "WAITING_FOR_PAYMENT"
            }

        if battle["status"] == "ready":
            await conn.execute(
                """
                UPDATE battles
                SET status='in_progress'
                WHERE id=$1
                """,
                battle_id
            )

        player = await conn.fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id=$1
              AND user_id=$2
            """,
            battle_id,
            user["id"]
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Not member"
            )

        if not player["session_id"]:
            session_id = gen_session_id()

            await conn.execute(
                """
                UPDATE battle_players
                SET session_id=$1
                WHERE battle_id=$2
                  AND user_id=$3
                """,
                session_id,
                battle_id,
                user["id"]
            )
        else:
            session_id = player["session_id"]

        return {
            "ok": True,
            "session_id": session_id,
            "battle_status": "in_progress"
        }


# ============================================================
# BATTLE FINISH
# ============================================================

@app.post("/api/battle/{battle_id}/finish")
async def api_battle_finish(
    battle_id: int,
    request: Request
):
    user, body = await require_user(request)

    answers = body.get(
        "answers",
        []
    )

    duration = body.get(
        "duration",
        0
    )

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id=$1
            """,
            battle_id
        )

        if not battle:
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )

        player = await conn.fetchrow(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id=$1
              AND user_id=$2
            """,
            battle_id,
            user["id"]
        )

        if not player:
            raise HTTPException(
                status_code=403,
                detail="Not member"
            )

        if player["test_status"] == "completed":
            raise HTTPException(
                status_code=409,
                detail="Already finished"
            )

        weighted = 0
        max_weight = 0
        correct = 0

        for i, question in enumerate(IQ_ANSWERS):

            max_weight += question["weight"]

            answer = (
                answers[i]
                if i < len(answers)
                and answers[i] is not None
                else None
            )

            if answer == question["correct"]:
                weighted += question["weight"]
                correct += 1

        score = (
            int(
                70
                + (weighted / max_weight) * 60
            )
            if max_weight
            else 70
        )

        await conn.execute(
            """
            UPDATE battle_players
            SET score=$1,
                weighted=$2,
                answers=$3::jsonb,
                test_status='completed',
                current_question=18,
                finished_at=NOW()
            WHERE battle_id=$4
              AND user_id=$5
            """,
            score,
            weighted,
            json.dumps(answers),
            battle_id,
            user["id"]
        )

        all_players = await conn.fetch(
            """
            SELECT *
            FROM battle_players
            WHERE battle_id=$1
            """,
            battle_id
        )

        completed = [
            p
            for p in all_players
            if p["test_status"] == "completed"
        ]

        opponent_score = None
        winner_id = None
        final_status = None

        # --------------------------------------------
        # IKKALA PLAYER HAM TUGATGAN
        # --------------------------------------------

        if len(completed) >= 2:

            p1 = completed[0]
            p2 = completed[1]

            if p1["user_id"] == user["id"]:
                opponent_score = p2["score"]
            else:
                opponent_score = p1["score"]

            if p1["score"] > p2["score"]:
                winner_id = p1["user_id"]
                final_status = "completed"

            elif p2["score"] > p1["score"]:
                winner_id = p2["user_id"]
                final_status = "completed"

            else:
                winner_id = None
                final_status = "draw"

            await conn.execute(
                """
                UPDATE battles
                SET status=$1,
                    winner_id=$2,
                    finished_at=NOW()
                WHERE id=$3
                """,
                final_status,
                winner_id,
                battle_id
            )

            # ----------------------------------------
            # WINNER CERTIFICATE
            # ----------------------------------------

            if winner_id:

                winner_player = next(
                    p
                    for p in completed
                    if p["user_id"] == winner_id
                )

                user_row = await conn.fetchrow(
                    """
                    SELECT full_name, first_name
                    FROM users
                    WHERE user_id=$1
                    """,
                    winner_id
                )

                name = (
                    (
                        user_row["full_name"]
                        or user_row["first_name"]
                        or "User"
                    )
                    if user_row
                    else "User"
                )

                await conn.execute(
                    """
                    INSERT INTO certificates (
                        certificate_id,
                        verification_code,
                        user_id,
                        result_id,
                        score,
                        type,
                        full_name
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        0,
                        $4,
                        'battle',
                        $5
                    )
                    """,
                    gen_code("CERT"),
                    gen_code("BT"),
                    winner_id,
                    winner_player["score"],
                    name
                )

        # --------------------------------------------
        # FAQAT BIRINCHI PLAYER TUGATGAN
        # --------------------------------------------

        else:

            final_status = battle["status"]

            await conn.execute(
                """
                UPDATE battles
                SET status='player_1_finished'
                WHERE id=$1
                """,
                battle_id
            )

        return {
            "ok": True,
            "score": score,
            "weighted": weighted,
            "correct": correct,
            "duration": duration,
            "opponent_score": opponent_score,
            "winner_id": winner_id,
            "final_status": final_status
        }
        # ============================================================
# PAYMENT STATUS
# ============================================================

@app.post("/api/payment/{payment_id}")
async def api_payment_get(
    payment_id: str,
    request: Request
):
    user, body = await require_user(request)

    async with db_pool.acquire() as conn:

        payment = await conn.fetchrow(
            """
            SELECT
                payment_id,
                product,
                amount,
                status
            FROM payments
            WHERE payment_id=$1
              AND user_id=$2
            """,
            payment_id,
            user["id"]
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Not found"
            )

        return {
            "ok": True,
            "payment": dict(payment)
        }


# ============================================================
# ADMIN
# ============================================================

ADMIN_STATE = {}


# ============================================================
# /admin
# ============================================================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🛠 <b>ADMIN PANEL</b>",
        reply_markup=admin_kb()
    )


# ============================================================
# ADMIN MENU
# ============================================================

@dp.callback_query(F.data == "admin:menu")
async def admin_menu(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        await cb.message.edit_text(
            "🛠 <b>ADMIN PANEL</b>",
            reply_markup=admin_kb()
        )

    except Exception:
        try:
            await cb.message.answer(
                "🛠 <b>ADMIN PANEL</b>",
                reply_markup=admin_kb()
            )
        except Exception:
            pass

    await cb.answer()


# ============================================================
# ADMIN STATISTICS
# ============================================================

@dp.callback_query(F.data == "admin:stats")
async def admin_stats(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            total_users = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                """
            ) or 0

            today_users = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                WHERE created_at::date = NOW()::date
                """
            ) or 0

            iq_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='iq'
                """
            ) or 0

            eq_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='eq'
                """
            ) or 0

            pq_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='pq'
                """
            ) or 0

            approved_payments = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM payments
                WHERE status='approved'
                """
            ) or 0

            revenue = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE status='approved'
                """
            ) or 0

            battles = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM battles
                """
            ) or 0

            text = (
                "📊 <b>STATISTICS</b>\n\n"
                f"👥 Users: <b>{total_users}</b>\n"
                f"📅 Today: <b>{today_users}</b>\n\n"
                f"🧠 IQ: <b>{iq_count}</b>\n"
                f"❤️ EQ: <b>{eq_count}</b>\n"
                f"⚡ PQ: <b>{pq_count}</b>\n\n"
                f"💳 Payments: <b>{approved_payments}</b>\n"
                f"💰 Revenue: <b>{revenue:,} so‘m</b>\n"
                f"⚔️ Battles: <b>{battles}</b>"
            )

            keyboard = InlineKeyboardBuilder()

            keyboard.button(
                text="⬅️",
                callback_data="admin:menu"
            )

            await cb.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )

    except Exception as e:
        logger.exception(
            f"admin_stats error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN USERS
# ============================================================

@dp.callback_query(F.data == "admin:users")
async def admin_users(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT
                    user_id,
                    first_name,
                    username,
                    language
                FROM users
                ORDER BY created_at DESC
                LIMIT 20
                """
            )

            text = "👥 <b>USERS</b>\n\n"

            if not rows:
                text += "Hozircha foydalanuvchilar yo‘q."

            else:
                for row in rows:

                    name = (
                        row["first_name"]
                        or row["username"]
                        or "?"
                    )

                    language = (
                        row["language"]
                        or "-"
                    )

                    text += (
                        f"• <code>{row['user_id']}</code> — "
                        f"{name} [{language}]\n"
                    )

            keyboard = InlineKeyboardBuilder()

            keyboard.button(
                text="⬅️",
                callback_data="admin:menu"
            )

            await cb.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )

    except Exception as e:
        logger.exception(
            f"admin_users error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN PAYMENTS
# ============================================================

@dp.callback_query(F.data == "admin:payments")
async def admin_payments(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT
                    payment_id,
                    user_id,
                    product,
                    amount,
                    receipt_file_id,
                    created_at
                FROM payments
                WHERE status='pending'
                ORDER BY created_at DESC
                LIMIT 20
                """
            )

            if not rows:

                keyboard = InlineKeyboardBuilder()

                keyboard.button(
                    text="⬅️",
                    callback_data="admin:menu"
                )

                await cb.message.edit_text(
                    "📭 <b>To‘lovlar bo‘sh.</b>",
                    reply_markup=keyboard.as_markup()
                )

                await cb.answer()
                return

            for payment in rows:

                keyboard = InlineKeyboardBuilder()

                keyboard.button(
                    text="✅ Tasdiqlash",
                    callback_data=(
                        f"pay_ok:{payment['payment_id']}"
                    )
                )

                keyboard.button(
                    text="❌ Rad etish",
                    callback_data=(
                        f"pay_no:{payment['payment_id']}"
                    )
                )

                keyboard.adjust(2)

                text = (
                    f"💳 <b>{payment['product']}</b>\n"
                    f"👤 <code>{payment['user_id']}</code>\n"
                    f"💰 <b>{payment['amount']:,} so‘m</b>\n"
                    f"🆔 <code>{payment['payment_id']}</code>"
                )

                if payment["receipt_file_id"]:

                    await cb.message.answer_photo(
                        payment["receipt_file_id"],
                        caption=text,
                        reply_markup=keyboard.as_markup()
                    )

                else:

                    await cb.message.answer(
                        text,
                        reply_markup=keyboard.as_markup()
                    )

    except Exception as e:
        logger.exception(
            f"admin_payments error: {e}"
        )

    await cb.answer()
    # ============================================================
# ADMIN PRODUCTS / PRICES
# ============================================================

@dp.callback_query(F.data == "admin:products")
async def admin_products(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        iq = await get_setting(
            "iq_price",
            "0"
        )

        iq_retry = await get_setting(
            "iq_retry_price",
            "5000"
        )

        eq = await get_setting(
            "eq_price",
            "0"
        )

        eq_retry = await get_setting(
            "eq_retry_price",
            "5000"
        )

        pq = await get_setting(
            "pq_price",
            "0"
        )

        pq_retry = await get_setting(
            "pq_retry_price",
            "5000"
        )

        battle = await get_setting(
            "battle_price",
            "7500"
        )

        text = (
            "💰 <b>NARXLAR</b>\n\n"
            f"🧠 IQ: <b>{iq}</b>\n"
            f"🔄 IQ retry: <b>{iq_retry}</b>\n\n"
            f"❤️ EQ: <b>{eq}</b>\n"
            f"🔄 EQ retry: <b>{eq_retry}</b>\n\n"
            f"⚡ PQ: <b>{pq}</b>\n"
            f"🔄 PQ retry: <b>{pq_retry}</b>\n\n"
            f"⚔️ Battle: <b>{battle}</b>\n\n"
            "0 = BEPUL"
        )

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text=f"🧠 IQ ({iq})",
            callback_data="set:iq_price"
        )

        keyboard.button(
            text=f"🔄 IQ retry ({iq_retry})",
            callback_data="set:iq_retry_price"
        )

        keyboard.button(
            text=f"❤️ EQ ({eq})",
            callback_data="set:eq_price"
        )

        keyboard.button(
            text=f"🔄 EQ retry ({eq_retry})",
            callback_data="set:eq_retry_price"
        )

        keyboard.button(
            text=f"⚡ PQ ({pq})",
            callback_data="set:pq_price"
        )

        keyboard.button(
            text=f"🔄 PQ retry ({pq_retry})",
            callback_data="set:pq_retry_price"
        )

        keyboard.button(
            text=f"⚔️ Battle ({battle})",
            callback_data="set:battle_price"
        )

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu"
        )

        keyboard.adjust(
            2, 2, 2, 1, 1
        )

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.exception(
            f"admin_products error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN SET PRICE
# ============================================================

@dp.callback_query(F.data.startswith("set:"))
async def admin_set_price(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        key = cb.data.split(
            ":",
            1
        )[1]

        allowed = {
            "iq_price",
            "iq_retry_price",
            "eq_price",
            "eq_retry_price",
            "pq_price",
            "pq_retry_price",
            "battle_price",
        }

        if key not in allowed:
            await cb.answer(
                "Noto‘g‘ri parametr",
                show_alert=True
            )
            return

        current = await get_setting(
            key,
            "0"
        )

        ADMIN_STATE[
            cb.from_user.id
        ] = {
            "action": "set_price",
            "key": key
        }

        await cb.message.edit_text(
            f"💰 <b>{key}</b>\n\n"
            f"Hozirgi: <b>{current}</b>\n\n"
            "Yangi narxni yuboring.\n"
            "0 = BEPUL"
        )

    except Exception as e:
        logger.exception(
            f"admin_set_price error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN CARDS
# ============================================================

@dp.callback_query(F.data == "admin:cards")
async def admin_cards(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            cards = await conn.fetch(
                """
                SELECT
                    id,
                    card_number,
                    holder,
                    bank,
                    active
                FROM payment_cards
                ORDER BY created_at DESC
                """
            )

            text = "💳 <b>KARTALAR</b>\n\n"

            for card in cards:

                status = (
                    "🟢"
                    if card["active"]
                    else "🔴"
                )

                text += (
                    f"{status} "
                    f"<code>{card['card_number']}</code>\n"
                    f"👤 {card['holder']}\n"
                    f"🏦 {card['bank'] or '—'}\n\n"
                )

            if not cards:
                text += "📭 Bo‘sh"

            keyboard = InlineKeyboardBuilder()

            keyboard.button(
                text="➕ Yangi karta",
                callback_data="card:add"
            )

            for card in cards:

                keyboard.button(
                    text=(
                        f"✏️ "
                        f"{card['card_number'][-4:]}"
                    ),
                    callback_data=(
                        f"card:edit:{card['id']}"
                    )
                )

                keyboard.button(
                    text=(
                        f"🗑 "
                        f"{card['card_number'][-4:]}"
                    ),
                    callback_data=(
                        f"card:del:{card['id']}"
                    )
                )

            keyboard.button(
                text="⬅️",
                callback_data="admin:menu"
            )

            keyboard.adjust(
                1,
                2
            )

            await cb.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )

    except Exception as e:
        logger.exception(
            f"admin_cards error: {e}"
        )

    await cb.answer()


# ============================================================
# ADD CARD
# ============================================================

@dp.callback_query(F.data == "card:add")
async def card_add(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    ADMIN_STATE[
        cb.from_user.id
    ] = {
        "action": "card_add"
    }

    await cb.message.edit_text(
        "💳 <b>KARTA QO‘SHISH</b>\n\n"
        "Format:\n"
        "<code>KARTA | HOLDER | BANK</code>\n\n"
        "Masalan:\n"
        "<code>8600 1234 5678 9012 | "
        "IQ TEST BOT | Click</code>"
    )

    await cb.answer()


# ============================================================
# EDIT CARD
# ============================================================

@dp.callback_query(
    F.data.startswith("card:edit:")
)
async def card_edit(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        card_id = int(
            cb.data.split(":")[2]
        )

        async with db_pool.acquire() as conn:

            card = await conn.fetchrow(
                """
                SELECT
                    id,
                    card_number,
                    holder,
                    bank
                FROM payment_cards
                WHERE id=$1
                """,
                card_id
            )

            if not card:
                await cb.answer(
                    "Karta topilmadi",
                    show_alert=True
                )
                return

        ADMIN_STATE[
            cb.from_user.id
        ] = {
            "action": "card_edit",
            "id": card_id
        }

        await cb.message.edit_text(
            "✏️ <b>KARTANI O‘ZGARTIRISH</b>\n\n"
            "Hozirgi:\n"
            f"<code>{card['card_number']} | "
            f"{card['holder']} | "
            f"{card['bank'] or '—'}</code>\n\n"
            "Yangi format:\n"
            "<code>KARTA | HOLDER | BANK</code>"
        )

    except Exception as e:
        logger.exception(
            f"card_edit error: {e}"
        )

    await cb.answer()


# ============================================================
# DELETE CARD
# ============================================================

@dp.callback_query(
    F.data.startswith("card:del:")
)
async def card_del(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        card_id = int(
            cb.data.split(":")[2]
        )

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM payment_cards
                WHERE id=$1
                """,
                card_id
            )

        await cb.answer(
            "Karta o‘chirildi"
        )

        await admin_cards(cb)

    except Exception as e:
        logger.exception(
            f"card_del error: {e}"
        )

        await cb.answer(
            "Xatolik",
            show_alert=True
        )


# ============================================================
# LIVE COUNTER
# ============================================================

@dp.callback_query(F.data == "admin:live")
async def admin_live(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        mode = await get_setting(
            "live_mode",
            "fake"
        )

        base = await get_setting(
            "live_fake_base",
            "95114"
        )

        online = await get_setting(
            "live_fake_online",
            "342"
        )

        delta = await get_setting(
            "live_fake_delta",
            "8"
        )

        text = (
            "📈 <b>LIVE COUNTER</b>\n\n"
            f"Rejim: <b>{mode.upper()}</b>\n"
            f"Base: <b>{base}</b>\n"
            f"Online: <b>{online}</b>\n"
            f"Delta: <b>±{delta}</b>"
        )

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="🟢 REAL",
            callback_data="live:mode:real"
        )

        keyboard.button(
            text="🟡 FAKE",
            callback_data="live:mode:fake"
        )

        keyboard.button(
            text=f"Base ({base})",
            callback_data="live:set:live_fake_base"
        )

        keyboard.button(
            text=f"Online ({online})",
            callback_data="live:set:live_fake_online"
        )

        keyboard.button(
            text=f"Delta (±{delta})",
            callback_data="live:set:live_fake_delta"
        )

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu"
        )

        keyboard.adjust(
            2,
            1,
            1,
            1,
            1
        )

        try:
            await cb.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )
        except Exception:
            await cb.message.answer(
                text,
                reply_markup=keyboard.as_markup()
            )

    except Exception as e:
        logger.exception(
            f"admin_live error: {e}"
        )

    await cb.answer()


# ============================================================
# LIVE MODE
# ============================================================

@dp.callback_query(
    F.data.startswith("live:mode:")
)
async def live_set_mode(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    mode = cb.data.split(":")[2]

    if mode not in ("real", "fake"):
        await cb.answer(
            "Noto‘g‘ri rejim",
            show_alert=True
        )
        return

    await set_setting(
        "live_mode",
        mode
    )

    await cb.answer(
        f"{mode.upper()} yoqildi"
    )

    try:
        await admin_live(cb)
    except Exception:
        pass


# ============================================================
# LIVE VALUE
# ============================================================

@dp.callback_query(
    F.data.startswith("live:set:")
)
async def live_set_value(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    key = cb.data.split(":")[2]

    allowed = {
        "live_fake_base",
        "live_fake_online",
        "live_fake_delta"
    }

    if key not in allowed:
        await cb.answer(
            "Noto‘g‘ri parametr",
            show_alert=True
        )
        return

    current = await get_setting(
        key,
        "0"
    )

    ADMIN_STATE[
        cb.from_user.id
    ] = {
        "action": "live_set",
        "key": key
    }

    await cb.message.edit_text(
        f"📈 <b>{key}</b>\n\n"
        f"Hozirgi: <b>{current}</b>\n\n"
        "Yangi qiymatni yuboring:"
    )

    await cb.answer()


# ============================================================
# ADMIN SETTINGS
# ============================================================

@dp.callback_query(F.data == "admin:settings")
async def admin_settings(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        support = await get_setting(
            "support_username",
            "omono_v"
        )

        text = (
            "⚙️ <b>SETTINGS</b>\n\n"
            f"👤 Support: @{support}"
        )

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu"
        )

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.exception(
            f"admin_settings error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN CERTIFICATES
# ============================================================

@dp.callback_query(F.data == "admin:certs")
async def admin_certs(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM certificates
                """
            ) or 0

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu"
        )

        await cb.message.edit_text(
            f"📜 Sertifikatlar: <b>{count}</b>",
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.exception(
            f"admin_certs error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN BATTLES
# ============================================================

@dp.callback_query(F.data == "admin:battles")
async def admin_battles(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    try:
        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT
                    id,
                    battle_code,
                    status
                FROM battles
                ORDER BY created_at DESC
                LIMIT 10
                """
            )

        text = "⚔️ <b>BATTLES</b>\n\n"

        if rows:
            for battle in rows:
                text += (
                    f"• <code>{battle['battle_code']}</code> "
                    f"— {battle['status']}\n"
                )
        else:
            text += "📭 Bo‘sh"

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu"
        )

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.exception(
            f"admin_battles error: {e}"
        )

    await cb.answer()


# ============================================================
# ADMIN BROADCAST
# ============================================================

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True
        )
        return

    await cb.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Format:\n"
        "<code>/broadcast matn</code>"
    )

    await cb.answer()


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):

    if not await is_admin(
        message.from_user.id
    ):
        return

    try:
        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) < 2:
            await message.answer(
                "Format:\n"
                "<code>/broadcast matn</code>"
            )
            return

        broadcast_text = parts[1].strip()

        if not broadcast_text:
            await message.answer(
                "Matn bo‘sh bo‘lishi mumkin emas."
            )
            return

        async with db_pool.acquire() as conn:

            users = await conn.fetch(
                """
                SELECT user_id
                FROM users
                """
            )

        sent = 0
        failed = 0

        for user_row in users:

            try:
                await bot.send_message(
                    user_row["user_id"],
                    broadcast_text
                )

                sent += 1

                await asyncio.sleep(
                    0.05
                )

            except Exception:
                failed += 1

        await message.answer(
            "📢 <b>Broadcast tugadi</b>\n\n"
            f"✅ Yuborildi: <b>{sent}</b>\n"
            f"❌ Xato: <b>{failed}</b>"
        )

    except Exception as e:
        logger.exception(
            f"cmd_broadcast error: {e}"
        )


# ============================================================
# ADMIN TEXT INPUT
# ============================================================

@dp.message(F.text)
async def handle_admin_text(
    message: types.Message
):

    user_id = message.from_user.id

    state = ADMIN_STATE.get(
        user_id
    )

    if not state:
        return

    if not await is_admin(user_id):
        ADMIN_STATE.pop(
            user_id,
            None
        )
        return

    action = state.get(
        "action"
    )

    # --------------------------------------------------------
    # SET PRICE
    # --------------------------------------------------------

    if action == "set_price":

        try:
            value = int(
                message.text.strip()
            )

            if value < 0:
                raise ValueError

            key = state["key"]

            await set_setting(
                key,
                str(value)
            )

            ADMIN_STATE.pop(
                user_id,
                None
            )

            await message.answer(
                f"✅ <b>{key}</b> = "
                f"<b>{value}</b>"
            )

        except Exception:
            await message.answer(
                "❌ Noto‘g‘ri qiymat.\n"
                "Faqat 0 yoki musbat son yuboring."
            )

        return

    # --------------------------------------------------------
    # LIVE VALUE
    # --------------------------------------------------------

    if action == "live_set":

        try:
            value = int(
                message.text.strip()
            )

            if value < 0:
                raise ValueError

            key = state["key"]

            await set_setting(
                key,
                str(value)
            )

            ADMIN_STATE.pop(
                user_id,
                None
            )

            await message.answer(
                f"✅ <b>{key}</b> = "
                f"<b>{value}</b>"
            )

        except Exception:
            await message.answer(
                "❌ Noto‘g‘ri qiymat."
            )

        return

    # --------------------------------------------------------
    # ADD CARD
    # --------------------------------------------------------

    if action == "card_add":

        try:
            parts = [
                part.strip()
                for part in message.text.split("|")
            ]

            if len(parts) < 2:
                raise ValueError

            card_number = parts[0]
            holder = parts[1]
            bank = (
                parts[2]
                if len(parts) > 2
                else ""
            )

            if not card_number or not holder:
                raise ValueError

            async with db_pool.acquire() as conn:

                await conn.execute(
                    """
                    INSERT INTO payment_cards (
                        card_number,
                        holder,
                        bank,
                        active
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        TRUE
                    )
                    """,
                    card_number,
                    holder,
                    bank
                )

            ADMIN_STATE.pop(
                user_id,
                None
            )

            await message.answer(
                "✅ Karta qo‘shildi."
            )

        except Exception:
            await message.answer(
                "❌ Format xato.\n\n"
                "<code>KARTA | HOLDER | BANK</code>"
            )

        return

    # --------------------------------------------------------
    # EDIT CARD
    # --------------------------------------------------------

    if action == "card_edit":

        try:
            parts = [
                part.strip()
                for part in message.text.split("|")
            ]

            if len(parts) < 2:
                raise ValueError

            card_number = parts[0]
            holder = parts[1]
            bank = (
                parts[2]
                if len(parts) > 2
                else ""
            )

            card_id = state["id"]

            async with db_pool.acquire() as conn:

                result = await conn.execute(
                    """
                    UPDATE payment_cards
                    SET card_number=$1,
                        holder=$2,
                        bank=$3
                    WHERE id=$4
                    """,
                    card_number,
                    holder,
                    bank,
                    card_id
                )

            if result == "UPDATE 0":
                raise ValueError

            ADMIN_STATE.pop(
                user_id,
                None
            )

            await message.answer(
                "✅ Karta yangilandi."
            )

        except Exception:
            await message.answer(
                "❌ Format xato.\n\n"
                "<code>KARTA | HOLDER | BANK</code>"
            )

        return


# ============================================================
# RUNNER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT
    )
    
    