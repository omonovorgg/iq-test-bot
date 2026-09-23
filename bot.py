# =============================================================================
# IQ TEST BOT — bot.py
# Production build. Python 3.11, aiogram 3.x, FastAPI, asyncpg, Pillow.
# =============================================================================

import os
import io
import re
import json
import hmac
import glob
import time
import uuid
import string
import random
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, unquote, quote
from typing import Optional, Dict, Any, List, Tuple

import asyncpg
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from fastapi import FastAPI, Request, Response, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import (
    Update, Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, BufferedInputFile, FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# -----------------------------------------------------------------------------
# ENV (muhit o'zgaruvchilari)
# -----------------------------------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot").strip()
ADMIN_USER_ID_RAW = os.getenv("ADMIN_USER_ID", "0").strip()
WEBHOOK_SECRET_ENV = os.getenv("WEBHOOK_SECRET", "").strip()
PORT = int(os.getenv("PORT", "10000"))

try:
    ADMIN_USER_ID = int(ADMIN_USER_ID_RAW) if ADMIN_USER_ID_RAW else 0
except ValueError:
    ADMIN_USER_ID = 0

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Webhook secret: env yoki BOT_TOKEN'dan deterministik fallback
WEBHOOK_SECRET = WEBHOOK_SECRET_ENV or hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()

# Public base URL fallback (Render RENDER_EXTERNAL_URL ni o'zi beradi)
if not PUBLIC_BASE_URL:
    PUBLIC_BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")

WEBHOOK_URL = (PUBLIC_BASE_URL + "/telegram/webhook") if PUBLIC_BASE_URL else ""

# -----------------------------------------------------------------------------
# Logging (secretslarni to'liq log qilmaymiz)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("iqbot")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)


def _mask(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 8:
        return "***"
    return s[:4] + "***" + s[-2:]


log.info("BOT_TOKEN=%s", _mask(BOT_TOKEN))
log.info("PUBLIC_BASE_URL=%s", PUBLIC_BASE_URL or "(unset)")
log.info("WEBAPP_URL=%s", WEBAPP_URL or "(unset)")
log.info("ADMIN_USER_ID=%s", ADMIN_USER_ID)

# -----------------------------------------------------------------------------
# App settings default qiymatlari
# -----------------------------------------------------------------------------
DEFAULT_SETTINGS: Dict[str, str] = {
    "iq_price": "0",
    "iq_retry_price": "5000",
    "eq_price": "0",
    "eq_retry_price": "5000",
    "pq_price": "0",
    "pq_retry_price": "5000",
    "battle_price": "7500",
    "live_mode": "fake",
    "live_fake_base": "95114",
    "live_fake_online": "342",
    "live_fake_delta": "8",
}

# -----------------------------------------------------------------------------
# Database pool
# -----------------------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    # Render ba'zida postgres:// beradi — asyncpg postgresql:// kutadi
    dsn = DATABASE_URL
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    # asyncpg DSN ichida ?sslmode=... ni qabul qilmaydi; ajratib olamiz
    ssl_ctx = None
    # Neon va boshqa provayderlar ?sslmode=...&channel_binding=... qo'shadi.
    # asyncpg bularni DSN ichida qabul qilmaydi — hammasini olib tashlaymiz.
    if "sslmode=" in dsn:
        if "sslmode=require" in dsn or "sslmode=verify-full" in dsn:
            ssl_ctx = True
    # Hamma query parametrlarni olib tashlash
    if "?" in dsn:
        dsn = dsn.split("?", 1)[0]
    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=10,
            command_timeout=60,
            ssl=ssl_ctx,
        )
    except Exception as e:
        log.error("Failed to create DB pool: %s", e)
        raise
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception as e:
            log.error("Error closing DB pool: %s", e)
        _pool = None


# -----------------------------------------------------------------------------
# Schema + migratsiyalar
# -----------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    last_name   TEXT,
    language    TEXT DEFAULT 'uz',
    full_name   TEXT,
    gender      TEXT,
    age         INTEGER,
    country     TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admins (
    user_id     BIGINT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS test_sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    test_type   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    battle_id   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '2 hours'),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_test_sessions_user ON test_sessions(user_id, test_type);

CREATE TABLE IF NOT EXISTS test_attempts (
    attempt_id     BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL,
    test_type      TEXT NOT NULL,
    session_id     TEXT NOT NULL,
    answers        JSONB,
    score          INTEGER,
    correct_count  INTEGER,
    weighted       INTEGER,
    duration       INTEGER,
    level          TEXT,
    payment_status TEXT NOT NULL DEFAULT 'none',
    result_visible BOOLEAN NOT NULL DEFAULT TRUE,
    attempt_no     INTEGER NOT NULL DEFAULT 1,
    battle_id      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_attempts_user_type ON test_attempts(user_id, test_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attempts_session ON test_attempts(session_id);

CREATE TABLE IF NOT EXISTS results (
    result_id   BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    attempt_id  BIGINT NOT NULL,
    test_type   TEXT NOT NULL,
    score       INTEGER NOT NULL,
    level       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_results_attempt ON results(attempt_id);

CREATE TABLE IF NOT EXISTS payments (
    payment_id  BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    amount      INTEGER NOT NULL DEFAULT 0,
    purpose     TEXT NOT NULL,
    attempt_id  BIGINT,
    battle_id   TEXT,
    card_id     BIGINT,
    receipt_file_id TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at  TIMESTAMPTZ,
    decided_by  BIGINT
);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_battle ON payments(battle_id);

CREATE TABLE IF NOT EXISTS payment_cards (
    card_id      BIGSERIAL PRIMARY KEY,
    card_number  TEXT NOT NULL,
    holder       TEXT NOT NULL,
    bank         TEXT,
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS certificates (
    certificate_id    BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL,
    verification_code TEXT UNIQUE,
    type              TEXT,
    full_name         TEXT,
    score             INTEGER,
    level             TEXT,
    image_file_id     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_certificates_user ON certificates(user_id);

CREATE TABLE IF NOT EXISTS battles (
    battle_id      TEXT PRIMARY KEY,
    code           TEXT UNIQUE NOT NULL,
    creator_id     BIGINT NOT NULL,
    opponent_id    BIGINT,
    status         TEXT NOT NULL DEFAULT 'waiting',
    test_type      TEXT NOT NULL DEFAULT 'iq',
    winner_id      BIGINT,
    creator_score  INTEGER,
    opponent_score INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS battle_players (
    battle_id   TEXT NOT NULL,
    user_id     BIGINT NOT NULL,
    score       INTEGER,
    finished    BOOLEAN NOT NULL DEFAULT FALSE,
    payment_ok  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (battle_id, user_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id           BIGSERIAL PRIMARY KEY,
    referrer_id  BIGINT NOT NULL,
    referred_id  BIGINT NOT NULL UNIQUE,
    rewarded     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
"""

# Eski sxemalar uchun xavfsiz migratsiyalar
MIGRATIONS_SQL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'uz';
ALTER TABLE users ALTER COLUMN username DROP NOT NULL;
ALTER TABLE users ALTER COLUMN first_name DROP NOT NULL;
ALTER TABLE users ALTER COLUMN last_name DROP NOT NULL;

ALTER TABLE certificates ADD COLUMN IF NOT EXISTS verification_code TEXT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS certificate_id BIGINT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS type TEXT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS score INTEGER;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS level TEXT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS image_file_id TEXT;
ALTER TABLE certificates ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS bank TEXT;
ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE payments ADD COLUMN IF NOT EXISTS card_id BIGINT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS receipt_file_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS attempt_id BIGINT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS battle_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS decided_by BIGINT;

ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS answers JSONB;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS weighted INTEGER;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'none';
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS result_visible BOOLEAN DEFAULT TRUE;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS attempt_no INTEGER DEFAULT 1;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS battle_id TEXT;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS level TEXT;
ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;

ALTER TABLE battles ADD COLUMN IF NOT EXISTS winner_id BIGINT;
ALTER TABLE battles ADD COLUMN IF NOT EXISTS creator_score INTEGER;
ALTER TABLE battles ADD COLUMN IF NOT EXISTS opponent_score INTEGER;
ALTER TABLE battles ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE battles ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
ALTER TABLE battles ADD COLUMN IF NOT EXISTS test_type TEXT DEFAULT 'iq';
"""


async def ensure_schema() -> None:
    """Startup paytida sxema va migratsiyalarni bajaradi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(SCHEMA_SQL)
            await conn.execute(MIGRATIONS_SQL)
            log.info("Schema ensured")
        except Exception as e:
            log.error("Schema init failed: %s", e)
            raise


async def seed_settings() -> None:
    """Default settingslarni bazaga yozadi (duplicate bo'lmasligi uchun ON CONFLICT DO NOTHING)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        for k, v in DEFAULT_SETTINGS.items():
            await conn.execute(
                """
                INSERT INTO app_settings(key, value)
                VALUES($1, $2)
                ON CONFLICT (key) DO NOTHING
                """,
                k, v,
            )
    log.info("Settings seeded")


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM app_settings WHERE key=$1", key)
        if row is None:
            return default if default is not None else DEFAULT_SETTINGS.get(key)
        return row["value"]


async def get_setting_int(key: str, default: int = 0) -> int:
    val = await get_setting(key)
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


async def set_setting(key: str, value: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO app_settings(key, value, updated_at)
            VALUES($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
            """,
            key, str(value),
        )


# -----------------------------------------------------------------------------
# Foydalanuvchilar
# -----------------------------------------------------------------------------
async def upsert_user(tg_user) -> None:
    """Telegram foydalanuvchisini idempotent tarzda upsert qiladi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, username, first_name, last_name, last_seen)
            VALUES($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET username=EXCLUDED.username,
                first_name=EXCLUDED.first_name,
                last_name=EXCLUDED.last_name,
                last_seen=NOW(),
                updated_at=NOW()
            """,
            int(tg_user.id),
            tg_user.username,
            tg_user.first_name,
            tg_user.last_name,
        )


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", int(user_id))
        return dict(row) if row else None


async def set_user_language(user_id: int, lang: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language=$2, updated_at=NOW() WHERE user_id=$1",
            int(user_id), lang,
        )


# -----------------------------------------------------------------------------
# Telegram initData HMAC validatsiya (spetsifikatsiya 34-bo'limi)
# -----------------------------------------------------------------------------
def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    """
    Telegram WebApp initData ni spetsifikatsiya 34-bo'limiga to'liq mos tekshiradi.
    Muvaffaqiyatli bo'lsa dict qaytaradi ('user' decoded va h.k.), aks holda None.
    MUHIM: unquote faqat user JSONni HMAC tekshiruvidan KEYIN decode qilishda ishlatiladi.
    """
    if not init_data or not isinstance(init_data, str):
        return None
    if not bot_token:
        return None

    pairs: List[Tuple[str, str]] = []
    for chunk in init_data.split("&"):
        if not chunk:
            continue
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        pairs.append((k, v))

    hash_val: Optional[str] = None
    kept: List[Tuple[str, str]] = []
    for k, v in pairs:
        if k == "hash":
            hash_val = v
            continue
        kept.append((k, v))

    if not hash_val:
        return None

    # Sorted key=value, newline bilan data_check
    kept.sort(key=lambda kv: kv[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in kept)

    # WebAppData secret
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, hash_val):
        return None

    # auth_date tekshirish
    auth_date_val = None
    for k, v in kept:
        if k == "auth_date":
            auth_date_val = v
            break
    if auth_date_val is not None:
        try:
            auth_ts = int(auth_date_val)
        except ValueError:
            return None
        now_ts = int(time.time())
        if auth_ts <= 0 or now_ts - auth_ts > max_age_seconds:
            return None

    result: Dict[str, Any] = {}
    for k, v in kept:
        if k == "user":
            try:
                result["user"] = json.loads(unquote(v))
            except Exception:
                return None
        else:
            try:
                result[k] = unquote(v)
            except Exception:
                result[k] = v
    if "user" not in result or not isinstance(result["user"], dict):
        return None
    if "id" not in result["user"]:
        return None
    return result


async def auth_webapp(request: Request) -> Dict[str, Any]:
    """
    Mini App requestini Telegram initData orqali autentifikatsiya qiladi.
    Qabul qilinadi:
      - header: Authorization: tma <initData>
      - header: X-Init-Data: <initData>
      - JSON body kalit "initData"
      - form field "initData"
    Muvaffaqiyatli bo'lsa dict qaytaradi ('user' Telegram user dict).
    Aks holda HTTPException(401) ko'taradi.
    """
    init_data = ""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("tma "):
        init_data = auth[4:].strip()
    if not init_data:
        init_data = request.headers.get("x-init-data", "").strip()
    if not init_data:
        ct = request.headers.get("content-type", "")
        try:
            if "application/json" in ct:
                body = await request.json()
                if isinstance(body, dict):
                    init_data = str(body.get("initData") or body.get("init_data") or "")
            elif "form-data" in ct or "x-www-form-urlencoded" in ct:
                form = await request.form()
                init_data = str(form.get("initData") or form.get("init_data") or "")
        except Exception:
            init_data = ""
    if not init_data:
        raise HTTPException(status_code=401, detail="initData required")
    parsed = validate_init_data(init_data, BOT_TOKEN)
    if not parsed:
        raise HTTPException(status_code=401, detail="invalid initData")
    return parsed


async def auth_user_id(request: Request) -> int:
    """Mini App requestidan tasdiqlangan Telegram user_id ni qaytaradi."""
    parsed = await auth_webapp(request)
    return int(parsed["user"]["id"])
    # =============================================================================
# bot.py — PART 2/3 (PART 2/6)
# Savollar banki, scoring engine, sertifikat generatori,
# aiogram handlerlar, FastAPI route'lar, lifespan, uvicorn launcher.
# =============================================================================

# -----------------------------------------------------------------------------
# IQ TEST — 18 ta puzzle (3×3 matrix)
# -----------------------------------------------------------------------------
IQ_QUESTIONS: List[Dict[str, Any]] = [
    # --- EASY (Q1–Q6, weight=1) ---
    {
        "id": 1, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["circle", "triangle", "square"],
            ["square", "circle", "triangle"],
            ["triangle", "square", "?"],
        ],
        "options": [
            {"key": "A", "shape": "circle"},
            {"key": "B", "shape": "triangle"},
            {"key": "C", "shape": "square"},
            {"key": "D", "shape": "pentagon"},
        ],
        "correct": "A",
    },
    {
        "id": 2, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["1dot", "2dot", "3dot"],
            ["2dot", "3dot", "4dot"],
            ["3dot", "4dot", "?"],
        ],
        "options": [
            {"key": "A", "shape": "3dot"},
            {"key": "B", "shape": "4dot"},
            {"key": "C", "shape": "5dot"},
            {"key": "D", "shape": "6dot"},
        ],
        "correct": "C",
    },
    {
        "id": 3, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["dark", "mid", "light"],
            ["light", "dark", "mid"],
            ["mid", "light", "?"],
        ],
        "options": [
            {"key": "A", "shape": "dark"},
            {"key": "B", "shape": "mid"},
            {"key": "C", "shape": "light"},
            {"key": "D", "shape": "extra_light"},
        ],
        "correct": "A",
    },
    {
        "id": 4, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["triangle", "square", "pentagon"],
            ["square", "pentagon", "hexagon"],
            ["pentagon", "hexagon", "?"],
        ],
        "options": [
            {"key": "A", "shape": "pentagon"},
            {"key": "B", "shape": "hexagon"},
            {"key": "C", "shape": "heptagon"},
            {"key": "D", "shape": "octagon"},
        ],
        "correct": "C",
    },
    {
        "id": 5, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["arrow_up", "arrow_right", "arrow_down"],
            ["arrow_right", "arrow_down", "arrow_left"],
            ["arrow_down", "arrow_left", "?"],
        ],
        "options": [
            {"key": "A", "shape": "arrow_up"},
            {"key": "B", "shape": "arrow_right"},
            {"key": "C", "shape": "arrow_down"},
            {"key": "D", "shape": "arrow_left"},
        ],
        "correct": "A",
    },
    {
        "id": 6, "difficulty": "easy", "weight": 1,
        "matrix": [
            ["half", "full", "empty"],
            ["empty", "half", "full"],
            ["full", "empty", "?"],
        ],
        "options": [
            {"key": "A", "shape": "empty"},
            {"key": "B", "shape": "half"},
            {"key": "C", "shape": "full"},
            {"key": "D", "shape": "double_full"},
        ],
        "correct": "B",
    },
    # --- MEDIUM (Q7–Q12, weight=2) ---
    {
        "id": 7, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["circle+1", "circle+2", "circle+3"],
            ["circle+2", "circle+3", "circle+4"],
            ["circle+3", "circle+4", "?"],
        ],
        "options": [
            {"key": "A", "shape": "circle+3"},
            {"key": "B", "shape": "circle+4"},
            {"key": "C", "shape": "circle+5"},
            {"key": "D", "shape": "circle+6"},
        ],
        "correct": "C",
    },
    {
        "id": 8, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["red", "blue", "green"],
            ["blue", "green", "red"],
            ["green", "red", "?"],
        ],
        "options": [
            {"key": "A", "shape": "red"},
            {"key": "B", "shape": "blue"},
            {"key": "C", "shape": "green"},
            {"key": "D", "shape": "yellow"},
        ],
        "correct": "B",
    },
    {
        "id": 9, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["triangle_out", "triangle_in", "triangle_double"],
            ["triangle_in", "triangle_double", "triangle_out"],
            ["triangle_double", "triangle_out", "?"],
        ],
        "options": [
            {"key": "A", "shape": "triangle_out"},
            {"key": "B", "shape": "triangle_in"},
            {"key": "C", "shape": "triangle_double"},
            {"key": "D", "shape": "triangle_empty"},
        ],
        "correct": "B",
    },
    {
        "id": 10, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["1line", "2line", "3line"],
            ["2line", "3line", "4line"],
            ["3line", "4line", "?"],
        ],
        "options": [
            {"key": "A", "shape": "3line"},
            {"key": "B", "shape": "4line"},
            {"key": "C", "shape": "5line"},
            {"key": "D", "shape": "6line"},
        ],
        "correct": "C",
    },
    {
        "id": 11, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["star3", "star4", "star5"],
            ["star4", "star5", "star6"],
            ["star5", "star6", "?"],
        ],
        "options": [
            {"key": "A", "shape": "star5"},
            {"key": "B", "shape": "star6"},
            {"key": "C", "shape": "star7"},
            {"key": "D", "shape": "star8"},
        ],
        "correct": "C",
    },
    {
        "id": 12, "difficulty": "medium", "weight": 2,
        "matrix": [
            ["rot0", "rot90", "rot180"],
            ["rot90", "rot180", "rot270"],
            ["rot180", "rot270", "?"],
        ],
        "options": [
            {"key": "A", "shape": "rot0"},
            {"key": "B", "shape": "rot90"},
            {"key": "C", "shape": "rot180"},
            {"key": "D", "shape": "rot360"},
        ],
        "correct": "D",
    },
    # --- HARD (Q13–Q18, weight=3) ---
    {
        "id": 13, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["sq+1tri", "sq+2tri", "sq+3tri"],
            ["sq+2tri", "sq+3tri", "sq+4tri"],
            ["sq+3tri", "sq+4tri", "?"],
        ],
        "options": [
            {"key": "A", "shape": "sq+3tri"},
            {"key": "B", "shape": "sq+4tri"},
            {"key": "C", "shape": "sq+5tri"},
            {"key": "D", "shape": "sq+6tri"},
        ],
        "correct": "C",
    },
    {
        "id": 14, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["A1", "B2", "C3"],
            ["B2", "C3", "D4"],
            ["C3", "D4", "?"],
        ],
        "options": [
            {"key": "A", "shape": "D4"},
            {"key": "B", "shape": "E5"},
            {"key": "C", "shape": "F6"},
            {"key": "D", "shape": "G7"},
        ],
        "correct": "B",
    },
    {
        "id": 15, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["full+1dot", "half+2dot", "empty+3dot"],
            ["half+2dot", "empty+3dot", "full+4dot"],
            ["empty+3dot", "full+4dot", "?"],
        ],
        "options": [
            {"key": "A", "shape": "full+3dot"},
            {"key": "B", "shape": "half+5dot"},
            {"key": "C", "shape": "empty+5dot"},
            {"key": "D", "shape": "half+4dot"},
        ],
        "correct": "B",
    },
    {
        "id": 16, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["outer_red", "mid_blue", "inner_green"],
            ["mid_blue", "inner_green", "outer_red"],
            ["inner_green", "outer_red", "?"],
        ],
        "options": [
            {"key": "A", "shape": "outer_red"},
            {"key": "B", "shape": "mid_blue"},
            {"key": "C", "shape": "inner_green"},
            {"key": "D", "shape": "center_gold"},
        ],
        "correct": "B",
    },
    {
        "id": 17, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["tri+sq", "sq+pent", "pent+hex"],
            ["sq+pent", "pent+hex", "hex+hep"],
            ["pent+hex", "hex+hep", "?"],
        ],
        "options": [
            {"key": "A", "shape": "hex+hep"},
            {"key": "B", "shape": "hep+oct"},
            {"key": "C", "shape": "oct+non"},
            {"key": "D", "shape": "non+dec"},
        ],
        "correct": "B",
    },
    {
        "id": 18, "difficulty": "hard", "weight": 3,
        "matrix": [
            ["1c", "2c", "3c"],
            ["4c", "6c", "8c"],
            ["9c", "12c", "?"],
        ],
        "options": [
            {"key": "A", "shape": "14c"},
            {"key": "B", "shape": "15c"},
            {"key": "C", "shape": "16c"},
            {"key": "D", "shape": "18c"},
        ],
        "correct": "B",
    },
]

# -----------------------------------------------------------------------------
# EQ TEST — 6 situational savol
# -----------------------------------------------------------------------------
EQ_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "question": "Do'stingiz sizga sirini aytdi. Boshqa do'stingiz qiziqib so'radi. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "Sirni aytib qo'yaman, chunki u ham do'stim"},
            {"key": "B", "text": "Aytmayman, lekin \"bilmadim\" deb bahona topaman"},
            {"key": "C", "text": "Aytmayman, sababini tushuntiraman"},
            {"key": "D", "text": "Aytib qo'yaman, lekin \"hech kimga aytma\" deb qo'shaman"},
        ],
        "scores": {"A": 25, "B": 55, "C": 100, "D": 40},
    },
    {
        "id": 2,
        "question": "Ishda hamkasbingiz xato qildi va boshliq buni sizdan so'radi. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "To'g'ridan-to'g'ri hamkasbim xato qildi deb aytaman"},
            {"key": "B", "text": "Uning nomini aytmasdan, muammoni birgalikda hal qilishni taklif qilaman"},
            {"key": "C", "text": "Hamkasbimni himoya qilaman, xato o'zimniki deb aytaman"},
            {"key": "D", "text": "Boshliqqa javob bermayman"},
        ],
        "scores": {"A": 40, "B": 100, "C": 60, "D": 20},
    },
    {
        "id": 3,
        "question": "Yaqin do'stingiz qiyin vaziyatda va sizdan yordam so'radi. Lekin siz band. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "Bandligimni aytaman va keyinroq yordam beraman"},
            {"key": "B", "text": "Rejamni bekor qilib, hoziroq yordamga boraman"},
            {"key": "C", "text": "Vaqtim yo'q deb rad etaman"},
            {"key": "D", "text": "Onlayn maslahat beraman, lekin uchrashmayman"},
        ],
        "scores": {"A": 70, "B": 100, "C": 20, "D": 50},
    },
    {
        "id": 4,
        "question": "Suhbatda sizni tanqid qilishdi. Sizning munosabatingiz?",
        "options": [
            {"key": "A", "text": "Darhol himoyalanaman"},
            {"key": "B", "text": "Jahl bilan javob qaytaraman"},
            {"key": "C", "text": "Tinch tinglayman va foydali tomonini olaman"},
            {"key": "D", "text": "E'tibor bermayman"},
        ],
        "scores": {"A": 40, "B": 25, "C": 100, "D": 55},
    },
    {
        "id": 5,
        "question": "Bir guruh odamlar sizning fikringizga qarshi chiqdi. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "O'z fikrimni qat'iy himoya qilaman"},
            {"key": "B", "text": "Fikrimni o'zgartiraman, ko'pchilik to'g'ri deb o'ylayman"},
            {"key": "C", "text": "Ularning fikrini tinglayman, keyin qaror qabul qilaman"},
            {"key": "D", "text": "Suhbatni tark etaman"},
        ],
        "scores": {"A": 70, "B": 35, "C": 100, "D": 25},
    },
    {
        "id": 6,
        "question": "Siz xato qildingiz va bu boshqalarga zarar yetkazdi. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "Xatoni tan olaman va kechirim so'rayman"},
            {"key": "B", "text": "Vaziyatni tuzatishga harakat qilaman, lekin xatoni tan olmayman"},
            {"key": "C", "text": "Boshqa birovga ag'daraman"},
            {"key": "D", "text": "Hech narsa qilmayman, o'zi o'tib ketadi"},
        ],
        "scores": {"A": 100, "B": 60, "C": 15, "D": 20},
    },
]

# -----------------------------------------------------------------------------
# PQ TEST — 6 behavioral savol
# -----------------------------------------------------------------------------
PQ_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "question": "Yangi loyihani boshlashdan oldin nima qilasiz?",
        "options": [
            {"key": "A", "text": "Reja tuzaman va maqsadni aniqlayman"},
            {"key": "B", "text": "Darhol boshlayman, reja keyin"},
            {"key": "C", "text": "Boshqalardan maslahat so'rayman"},
            {"key": "D", "text": "Kutaman, ilhom kelishini"},
        ],
        "scores": {"A": 100, "B": 70, "C": 65, "D": 25},
    },
    {
        "id": 2,
        "question": "Maqsadingizga erishishda to'siqlarga uchrasangiz?",
        "options": [
            {"key": "A", "text": "Boshqa yo'l izlayman"},
            {"key": "B", "text": "Yordam so'rayman"},
            {"key": "C", "text": "Maqsadni o'zgartiraman"},
            {"key": "D", "text": "Tashlab qo'yaman"},
        ],
        "scores": {"A": 100, "B": 80, "C": 55, "D": 15},
    },
    {
        "id": 3,
        "question": "Vaqtingizni qanday boshqarasiz?",
        "options": [
            {"key": "A", "text": "Aniq jadval bo'yicha"},
            {"key": "B", "text": "Muhim ishlarni birinchi qilaman"},
            {"key": "C", "text": "Kayfiyatga qarab"},
            {"key": "D", "text": "Rejasiz, o'z-o'zidan"},
        ],
        "scores": {"A": 100, "B": 85, "C": 40, "D": 20},
    },
    {
        "id": 4,
        "question": "Qiyin qaror qabul qilishingiz kerak. Nima qilasiz?",
        "options": [
            {"key": "A", "text": "Barcha variantlarni tahlil qilaman"},
            {"key": "B", "text": "Intuitsiyaga tayanaman"},
            {"key": "C", "text": "Boshqalardan so'rayman"},
            {"key": "D", "text": "Kutaman, o'zi hal bo'ladi"},
        ],
        "scores": {"A": 100, "B": 70, "C": 55, "D": 20},
    },
    {
        "id": 5,
        "question": "Xatolaringizdan qanday saboq olasiz?",
        "options": [
            {"key": "A", "text": "Tahlil qilaman va takrorlamaslikka harakat qilaman"},
            {"key": "B", "text": "Esda saqlayman"},
            {"key": "C", "text": "Unutaman, oldinga qarayman"},
            {"key": "D", "text": "O'zimni ayblayman"},
        ],
        "scores": {"A": 100, "B": 75, "C": 55, "D": 30},
    },
    {
        "id": 6,
        "question": "Uzoq muddatli maqsadlaringiz bormi?",
        "options": [
            {"key": "A", "text": "Ha, aniq va yozilgan"},
            {"key": "B", "text": "Ha, lekin taxminiy"},
            {"key": "C", "text": "Faqat yaqin kelajak uchun"},
            {"key": "D", "text": "Yo'q, kun bilan yashayman"},
        ],
        "scores": {"A": 100, "B": 80, "C": 50, "D": 20},
    },
]

# -----------------------------------------------------------------------------
# Scoring engine (backend hisoblaydi, frontendga ishonmaymiz)
# -----------------------------------------------------------------------------
def score_iq(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    answers: {"1": "A", "2": "C", ...}
    Return: {score, correct_count, weighted, max_weighted, level}
    IQ-style score 70-130.
    """
    correct = 0
    weighted = 0
    max_weighted = 0
    for q in IQ_QUESTIONS:
        qid = str(q["id"])
        w = int(q["weight"])
        max_weighted += w
        user_ans = str(answers.get(qid, "")).strip().upper()
        if user_ans and user_ans == q["correct"]:
            correct += 1
            weighted += w
    # 70..130 mapping
    if max_weighted <= 0:
        score = 70
    else:
        ratio = weighted / max_weighted
        score = int(round(70 + ratio * 60))
    score = max(70, min(130, score))
    if score >= 125:
        level = "Genius"
    elif score >= 115:
        level = "Ajoyib"
    elif score >= 105:
        level = "Yuqori"
    elif score >= 95:
        level = "O'rtadan yuqori"
    elif score >= 85:
        level = "O'rtacha"
    elif score >= 75:
        level = "O'rtadan past"
    else:
        level = "Boshlang'ich"
    return {
        "score": score,
        "correct_count": correct,
        "weighted": weighted,
        "max_weighted": max_weighted,
        "level": level,
    }


def score_eq(answers: Dict[str, str]) -> Dict[str, Any]:
    """EQ — 0..100%."""
    total = 0
    count = 0
    for q in EQ_QUESTIONS:
        qid = str(q["id"])
        user_ans = str(answers.get(qid, "")).strip().upper()
        sc = q["scores"].get(user_ans)
        if sc is not None:
            total += int(sc)
        count += 1
    percent = int(round(total / count)) if count else 0
    percent = max(0, min(100, percent))
    if percent >= 85:
        level = "Yuqori emotsional intellekt"
    elif percent >= 70:
        level = "Yaxshi"
    elif percent >= 50:
        level = "O'rtacha"
    else:
        level = "Rivojlantirish kerak"
    return {"score": percent, "level": level}


def score_pq(answers: Dict[str, str]) -> Dict[str, Any]:
    """PQ — 0..100%."""
    total = 0
    count = 0
    for q in PQ_QUESTIONS:
        qid = str(q["id"])
        user_ans = str(answers.get(qid, "")).strip().upper()
        sc = q["scores"].get(user_ans)
        if sc is not None:
            total += int(sc)
        count += 1
    percent = int(round(total / count)) if count else 0
    percent = max(0, min(100, percent))
    if percent >= 85:
        level = "Yuqori mahsuldorlik"
    elif percent >= 70:
        level = "Yaxshi"
    elif percent >= 50:
        level = "O'rtacha"
    else:
        level = "Rivojlantirish kerak"
    return {"score": percent, "level": level}


# -----------------------------------------------------------------------------
# Certificate generator (Pillow) — DejaVu font, professional sizes
# -----------------------------------------------------------------------------
_FONT_CACHE: Dict[str, str] = {}


def _find_font_path(bold: bool = False) -> Optional[str]:
    """DejaVu font topadi (glob orqali)."""
    key = "bold" if bold else "regular"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    patterns = []
    if bold:
        patterns = [
            "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/**/DejaVuSans-Bold*.ttf",
            "/usr/share/fonts/**/*Bold*.ttf",
        ]
    else:
        patterns = [
            "/usr/share/fonts/**/DejaVuSans.ttf",
            "/usr/share/fonts/**/DejaVuSans-*.ttf",
            "/usr/share/fonts/**/*.ttf",
        ]
    for p in patterns:
        found = glob.glob(p, recursive=True)
        found = [f for f in found if "Bold" not in f or bold]
        if found:
            _FONT_CACHE[key] = found[0]
            return found[0]
    return None


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font_path(bold=bold)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception as e:
            log.error("Font load failed %s: %s", path, e)
    # Fallback: at least a truetype default if available
    return ImageFont.load_default()


def _generate_verification_code() -> str:
    """IQ-XXXXXX formatda unikal kod."""
    alphabet = string.ascii_uppercase + string.digits
    return "IQ-" + "".join(random.choice(alphabet) for _ in range(6))


def generate_certificate_png(
    full_name: str,
    score: int,
    level: str,
    verification_code: str,
    test_type: str = "IQ",
) -> bytes:
    """1600x1100 premium PNG sertifikat generatsiya qiladi."""
    W, H = 1600, 1100
    img = Image.new("RGB", (W, H), "#0a0e1a")
    draw = ImageDraw.Draw(img)

    # Background gradient (simple)
    for y in range(H):
        r = int(10 + (30 - 10) * (y / H))
        g = int(14 + (20 - 14) * (y / H))
        b = int(26 + (60 - 26) * (y / H))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Gold border
    gold = "#d4af37"
    gold_light = "#f0d67a"
    draw.rectangle([40, 40, W - 40, H - 40], outline=gold, width=6)
    draw.rectangle([58, 58, W - 58, H - 58], outline=gold_light, width=2)

    # Corner ornaments
    for cx, cy in [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]:
        draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=gold, width=4)
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=gold)

    # Header
    f_title = _load_font(96, bold=True)
    f_subtitle = _load_font(40)
    f_name = _load_font(78, bold=True)
    f_label = _load_font(34)
    f_value = _load_font(64, bold=True)
    f_code = _load_font(36)
    f_brand = _load_font(46, bold=True)

    def center_text(text: str, y: int, font, fill):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(text) * (font.size // 2 if hasattr(font, "size") else 20)
        draw.text(((W - w) // 2, y), text, font=font, fill=fill)

    # Title
    center_text("SERTIFIKAT", 120, f_title, gold_light)
    center_text("AQLLIY SALOHIYAT TO'G'RISIDA", 240, f_subtitle, "#e8eaf6")

    # Divider
    draw.line([(W // 2 - 300, 310), (W // 2 + 300, 310)], fill=gold, width=3)

    # Name
    center_text("Ushbu sertifikat", 360, f_label, "#c5cae9")
    safe_name = (full_name or "Foydalanuvchi").strip()[:50]
    center_text(safe_name, 410, f_name, "#ffffff")

    # Score box
    center_text(f"{test_type} natijasi", 540, f_label, "#c5cae9")
    score_str = f"{score} ball"
    center_text(score_str, 590, f_value, gold_light)
    center_text(level or "", 680, f_subtitle, "#e8eaf6")

    # Divider
    draw.line([(W // 2 - 300, 760), (W // 2 + 300, 760)], fill=gold, width=2)

    # Date
    today = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    center_text(f"Sana: {today}", 800, f_label, "#c5cae9")

    # Verification code
    center_text(f"Tekshirish kodi: {verification_code}", 870, f_code, gold_light)

    # Brain visual (simple)
    bx, by = W // 2, 1000
    draw.ellipse([bx - 70, by - 50, bx + 70, by + 50], outline=gold, width=4)
    draw.ellipse([bx - 50, by - 30, bx + 50, by + 30], outline=gold_light, width=2)
    draw.line([(bx, by - 50), (bx, by + 50)], fill=gold, width=2)

    # Brand
    center_text("IQ TEST BOT", 1040, f_brand, "#a78bfa")

    # Save
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Aiogram setup
# -----------------------------------------------------------------------------
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
router = Router()


# --- Tarjimalar (UZ / RU / EN) ---
I18N: Dict[str, Dict[str, str]] = {
    "uz": {
        "welcome": "🧠 <b>IQ TEST BOT</b>ga xush kelibsiz!\n\nBu yerda siz IQ, EQ va PQ testlarini ishlashingiz mumkin.",
        "start_btn": "🧠 IQ · EQ · PQ testini ishlash",
        "cert": "📜 Sertifikatim",
        "rank": "🏆 Reyting",
        "earn": "💰 Pul ishlash",
        "help": "ℹ️ Narx va yordam",
        "lang": "🌐 Til",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til o'zgartirildi",
        "no_cert": "❌ Sizda hali sertifikat yo'q. Testni yakunlab, sertifikat oling.",
        "help_text": (
            "ℹ️ <b>Narx va yordam</b>\n\n"
            "• IQ test — asosiy\n• EQ test — IQ dan keyin\n• PQ test — EQ dan keyin\n"
            "• Battle — do'stingiz bilan duel\n\n"
            "Savollar bo'lsa: admin bilan bog'laning."
        ),
        "earn_text": (
            "💰 <b>Pul ishlash</b>\n\n"
            "Do'stlaringizni taklif qiling va bonus oling.\n"
            "Sizning havolangiz:"
        ),
        "verify_ok": "✅ Sertifikat topildi",
        "verify_fail": "❌ Bunday sertifikat topilmadi.",
        "admin_denied": "⛔ Siz admin emassiz.",
    },
    "ru": {
        "welcome": "🧠 Добро пожаловать в <b>IQ TEST BOT</b>!\n\nЗдесь вы можете пройти IQ, EQ и PQ тесты.",
        "start_btn": "🧠 Пройти IQ · EQ · PQ",
        "cert": "📜 Мой сертификат",
        "rank": "🏆 Рейтинг",
        "earn": "💰 Заработок",
        "help": "ℹ️ Цены и помощь",
        "lang": "🌐 Язык",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык изменён",
        "no_cert": "❌ У вас пока нет сертификата.",
        "help_text": "ℹ️ <b>Цены и помощь</b>\n\n• IQ — основной\n• EQ — после IQ\n• PQ — после EQ\n\nВопросы: свяжитесь с админом.",
        "earn_text": "💰 <b>Заработок</b>\n\nПриглашайте друзей и получайте бонусы.\nВаша ссылка:",
        "verify_ok": "✅ Сертификат найден",
        "verify_fail": "❌ Сертификат не найден.",
        "admin_denied": "⛔ Вы не админ.",
    },
    "en": {
        "welcome": "🧠 Welcome to <b>IQ TEST BOT</b>!\n\nTake IQ, EQ and PQ tests here.",
        "start_btn": "🧠 Take IQ · EQ · PQ test",
        "cert": "📜 My certificate",
        "rank": "🏆 Ranking",
        "earn": "💰 Earn money",
        "help": "ℹ️ Prices & help",
        "lang": "🌐 Language",
        "choose_lang": "🌐 Choose language:",
        "lang_set": "✅ Language changed",
        "no_cert": "❌ You don't have a certificate yet.",
        "help_text": "ℹ️ <b>Prices & help</b>\n\n• IQ — main\n• EQ — after IQ\n• PQ — after EQ\n\nContact admin for questions.",
        "earn_text": "💰 <b>Earn money</b>\n\nInvite friends and earn bonuses.\nYour link:",
        "verify_ok": "✅ Certificate found",
        "verify_fail": "❌ Certificate not found.",
        "admin_denied": "⛔ You are not admin.",
    },
}


def tr(lang: str, key: str) -> str:
    lang = lang if lang in I18N else "uz"
    return I18N[lang].get(key) or I18N["uz"].get(key) or key


async def get_user_lang(user_id: int) -> str:
    u = await get_user(user_id)
    if u and u.get("language") in I18N:
        return u["language"]
    return "uz"


# --- Klaviaturalar ---
def kb_main_menu(lang: str, user_id: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton(
            text=tr(lang, "start_btn"),
            web_app=WebAppInfo(url=WEBAPP_URL + "/app"),
        )])
    rows.append([InlineKeyboardButton(text=tr(lang, "cert"), callback_data="menu:cert")])
    rows.append([
        InlineKeyboardButton(text=tr(lang, "rank"), callback_data="menu:rank"),
        InlineKeyboardButton(text=tr(lang, "earn"), callback_data="menu:earn"),
    ])
    rows.append([
        InlineKeyboardButton(text=tr(lang, "help"), callback_data="menu:help"),
        InlineKeyboardButton(text=tr(lang, "lang"), callback_data="menu:lang"),
    ])
    if ADMIN_USER_ID and user_id == ADMIN_USER_ID:
        rows.append([InlineKeyboardButton(text="🛠 Admin panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang:uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
        ],
    ])


# --- /start ---
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    try:
        await upsert_user(message.from_user)
    except Exception as e:
        log.error("upsert_user failed: %s", e)
    uid = int(message.from_user.id)
    lang = await get_user_lang(uid)

    # Referral: /start ref_<id>
    args = (command.args or "").strip()
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
            if referrer_id != uid and referrer_id > 0:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    exists = await conn.fetchrow(
                        "SELECT referrer_id FROM referrals WHERE referred_id=$1", uid
                    )
                    if not exists:
                        await conn.execute(
                            """
                            INSERT INTO referrals(referrer_id, referred_id)
                            VALUES($1, $2)
                            ON CONFLICT (referred_id) DO NOTHING
                            """,
                            referrer_id, uid,
                        )
        except Exception as e:
            log.error("referral record failed: %s", e)

    text = tr(lang, "welcome")
    try:
        await message.answer(text, reply_markup=kb_main_menu(lang, uid), parse_mode=ParseMode.HTML)
    except TelegramBadRequest as e:
        log.error("send welcome failed: %s", e)
        await message.answer(text)


# --- /admin ---
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    uid = int(message.from_user.id)
    if not ADMIN_USER_ID or uid != ADMIN_USER_ID:
        await message.answer(tr(await get_user_lang(uid), "admin_denied"))
        return
    await send_admin_home(message.chat.id)


async def send_admin_home(chat_id: int, edit_message_id: Optional[int] = None):
    text = "🛠 <b>Admin panel</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
         InlineKeyboardButton(text="📊 Statistics", callback_data="admin:stats")],
        [InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments"),
         InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="💰 Products", callback_data="admin:products"),
         InlineKeyboardButton(text="📜 Certificates", callback_data="admin:certs")],
        [InlineKeyboardButton(text="⚔️ Battles", callback_data="admin:battles"),
         InlineKeyboardButton(text="💳 Cards", callback_data="admin:cards")],
        [InlineKeyboardButton(text="🎯 Live Counter", callback_data="admin:live"),
         InlineKeyboardButton(text="⚙️ Settings", callback_data="admin:settings")],
    ])
    if edit_message_id and bot:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=edit_message_id,
                text=text, reply_markup=kb, parse_mode=ParseMode.HTML,
            )
            return
        except TelegramBadRequest:
            pass
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- Callbacks ---
@router.callback_query(F.data == "menu:lang")
async def cb_menu_lang(cq: CallbackQuery):
    try:
        await cq.message.edit_text("🌐 Tilni tanlang:", reply_markup=kb_lang())
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_lang(cq: CallbackQuery):
    lang = cq.data.split(":", 1)[1]
    if lang not in I18N:
        lang = "uz"
    try:
        await set_user_language(int(cq.from_user.id), lang)
    except Exception as e:
        log.error("set_language failed: %s", e)
    try:
        await cq.message.edit_text(
            tr(lang, "welcome"),
            reply_markup=kb_main_menu(lang, int(cq.from_user.id)),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass
    await cq.answer(tr(lang, "lang_set"))


@router.callback_query(F.data == "menu:help")
async def cb_help(cq: CallbackQuery):
    lang = await get_user_lang(int(cq.from_user.id))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="menu:back")
    ]])
    try:
        await cq.message.edit_text(tr(lang, "help_text"), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "menu:earn")
async def cb_earn(cq: CallbackQuery):
    uid = int(cq.from_user.id)
    lang = await get_user_lang(uid)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    text = f"{tr(lang, 'earn_text')}\n<code>{link}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="menu:back")
    ]])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "menu:back")
async def cb_back(cq: CallbackQuery):
    uid = int(cq.from_user.id)
    lang = await get_user_lang(uid)
    try:
        await cq.message.edit_text(
            tr(lang, "welcome"),
            reply_markup=kb_main_menu(lang, uid),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "menu:cert")
async def cb_my_cert(cq: CallbackQuery):
    uid = int(cq.from_user.id)
    lang = await get_user_lang(uid)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM certificates WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1",
            uid,
        )
    if not row:
        try:
            await cq.message.answer(tr(lang, "no_cert"))
        except Exception:
            pass
        await cq.answer()
        return
    cert = dict(row)
    caption = (
        f"📜 <b>Sertifikat</b>\n\n"
        f"Ism: {cert.get('full_name') or '-'}\n"
        f"Turi: {cert.get('type') or 'IQ'}\n"
        f"Ball: {cert.get('score')}\n"
        f"Daraja: {cert.get('level') or '-'}\n"
        f"Kod: <code>{cert.get('verification_code')}</code>"
    )
    # Try to send stored image, else regenerate
    sent = False
    if cert.get("image_file_id") and bot:
        try:
            await bot.send_photo(cq.message.chat.id, photo=cert["image_file_id"], caption=caption, parse_mode=ParseMode.HTML)
            sent = True
        except Exception as e:
            log.error("send stored cert failed: %s", e)
    if not sent and bot:
        try:
            png = generate_certificate_png(
                full_name=cert.get("full_name") or "Foydalanuvchi",
                score=int(cert.get("score") or 0),
                level=cert.get("level") or "",
                verification_code=cert.get("verification_code") or "IQ-000000",
                test_type=cert.get("type") or "IQ",
            )
            await bot.send_photo(
                cq.message.chat.id,
                photo=BufferedInputFile(png, filename="certificate.png"),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            log.error("regenerate cert failed: %s", e)
    await cq.answer()


@router.callback_query(F.data == "menu:rank")
async def cb_rank(cq: CallbackQuery):
    uid = int(cq.from_user.id)
    lang = await get_user_lang(uid)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.user_id, COALESCE(u.full_name, u.first_name, 'User') AS name,
                   MAX(r.score) AS best
            FROM results r JOIN users u ON u.user_id = r.user_id
            WHERE r.test_type = 'iq'
            GROUP BY u.user_id, name
            ORDER BY best DESC LIMIT 20
            """
        )
    lines = ["🏆 <b>Reyting</b>\n"]
    for i, r in enumerate(rows, 1):
        mark = "👉 " if int(r["user_id"]) == uid else ""
        lines.append(f"{mark}{i}. {r['name']} — <b>{r['best']}</b>")
    if not rows:
        lines.append("Hozircha natijalar yo'q.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="menu:back")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


# --- Certificate verify via message (IQ-XXXXXX) ---
@router.message(F.text.regexp(r"^IQ-[A-Z0-9]{6}$"))
async def verify_certificate(message: Message):
    code = (message.text or "").strip().upper()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM certificates WHERE verification_code=$1", code
        )
    uid = int(message.from_user.id)
    lang = await get_user_lang(uid)
    if not row:
        await message.answer(tr(lang, "verify_fail"))
        return
    c = dict(row)
    text = (
        f"{tr(lang, 'verify_ok')}\n\n"
        f"👤 {c.get('full_name') or '-'}\n"
        f"🧠 {c.get('type') or 'IQ'}: {c.get('score')}\n"
        f"⭐ {c.get('level') or '-'}\n"
        f"📅 {(c.get('created_at') or datetime.now(timezone.utc)).strftime('%d.%m.%Y')}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


# --- Admin callbacks ---
def _is_admin(uid: int) -> bool:
    return bool(ADMIN_USER_ID) and uid == ADMIN_USER_ID


@router.callback_query(F.data == "admin:home")
async def cb_admin_home(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    await send_admin_home(cq.message.chat.id, edit_message_id=cq.message.message_id)
    await cq.answer()


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        iq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='iq'")
        eq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='eq'")
        pq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='pq'")
        pending = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status='pending'")
        battles = await conn.fetchval("SELECT COUNT(*) FROM battles")
        certs = await conn.fetchval("SELECT COUNT(*) FROM certificates")
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Users: {users}\n🧠 IQ: {iq}\n🎭 EQ: {eq}\n⏳ PQ: {pq}\n"
        f"💳 Pending payments: {pending}\n⚔️ Battles: {battles}\n📜 Certs: {certs}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "admin:users")
async def cb_admin_users(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, COALESCE(full_name, first_name, username, 'User') AS n, created_at "
            "FROM users ORDER BY created_at DESC LIMIT 20"
        )
    lines = ["👥 <b>Oxirgi 20 user</b>\n"]
    for r in rows:
        lines.append(f"• {r['n']} (<code>{r['user_id']}</code>)")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "admin:payments")
async def cb_admin_payments(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT payment_id, user_id, amount, purpose, status FROM payments "
            "WHERE status='pending' ORDER BY created_at DESC LIMIT 20"
        )
    if not rows:
        text = "💳 Pending payments yo'q."
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️", callback_data="admin:home")
        ]])
        try:
            await cq.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            pass
        await cq.answer()
        return
    for r in rows:
        text = (
            f"💳 <b>Payment #{r['payment_id']}</b>\n"
            f"User: <code>{r['user_id']}</code>\n"
            f"Summa: {r['amount']}\n"
            f"Maqsad: {r['purpose']}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Approve", callback_data=f"pay:ok:{r['payment_id']}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"pay:no:{r['payment_id']}"),
        ]])
        try:
            await cq.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception as e:
            log.error("send payment card failed: %s", e)
    await cq.answer()


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay_decision(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    try:
        _, action, pid_s = cq.data.split(":", 2)
        pid = int(pid_s)
    except Exception:
        await cq.answer("❌")
        return
    new_status = "approved" if action == "ok" else "rejected"
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM payments WHERE payment_id=$1 FOR UPDATE", pid
            )
            if not row or row["status"] != "pending":
                await cq.answer("Allaqachon hal qilingan")
                return
            await conn.execute(
                "UPDATE payments SET status=$2, decided_at=NOW(), decided_by=$3 WHERE payment_id=$1",
                pid, new_status, int(cq.from_user.id),
            )
            payment = dict(row)
            # Apply side effects
            if new_status == "approved":
                if payment.get("purpose", "").startswith("iq") and payment.get("attempt_id"):
                    await conn.execute(
                        "UPDATE test_attempts SET result_visible=TRUE, payment_status='approved' WHERE attempt_id=$1",
                        int(payment["attempt_id"]),
                    )
                if payment.get("purpose", "").startswith("eq") and payment.get("attempt_id"):
                    await conn.execute(
                        "UPDATE test_attempts SET result_visible=TRUE, payment_status='approved' WHERE attempt_id=$1",
                        int(payment["attempt_id"]),
                    )
                if payment.get("purpose", "").startswith("pq") and payment.get("attempt_id"):
                    await conn.execute(
                        "UPDATE test_attempts SET result_visible=TRUE, payment_status='approved' WHERE attempt_id=$1",
                        int(payment["attempt_id"]),
                    )
                if payment.get("purpose") == "battle" and payment.get("battle_id"):
                    await conn.execute(
                        "UPDATE battle_players SET payment_ok=TRUE WHERE battle_id=$1 AND user_id=$2",
                        payment["battle_id"], int(payment["user_id"]),
                    )
                    # If both paid -> ready
                    row2 = await conn.fetch(
                        "SELECT user_id, payment_ok FROM battle_players WHERE battle_id=$1",
                        payment["battle_id"],
                    )
                    if len(row2) == 2 and all(bool(r["payment_ok"]) for r in row2):
                        await conn.execute(
                            "UPDATE battles SET status='ready' WHERE battle_id=$1 AND status IN ('waiting','payment')",
                            payment["battle_id"],
                        )
    # Notify user
    if bot:
        try:
            if new_status == "approved":
                await bot.send_message(int(payment["user_id"]), f"✅ To'lovingiz tasdiqlandi (#{pid}).")
            else:
                await bot.send_message(int(payment["user_id"]), f"❌ To'lovingiz rad etildi (#{pid}).")
        except Exception as e:
            log.error("notify user payment failed: %s", e)
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await cq.answer("✅" if new_status == "approved" else "❌")


@router.callback_query(F.data == "admin:products")
async def cb_admin_products(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    keys = ["iq_price", "iq_retry_price", "eq_price", "eq_retry_price",
            "pq_price", "pq_retry_price", "battle_price"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT key, value FROM app_settings WHERE key = ANY($1::text[]) ORDER BY key",
            keys,
        )
    d = {r["key"]: r["value"] for r in rows}
    lines = ["💰 <b>Narxlar</b>\n"]
    for k in keys:
        lines.append(f"• {k}: <b>{d.get(k, '-')}</b>")
    lines.append("\nO'zgartirish uchun: <code>/set iq_price 5000</code>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.message(Command("set"))
async def cmd_set(message: Message, command: CommandObject):
    if not _is_admin(int(message.from_user.id)):
        await message.answer("⛔")
        return
    args = (command.args or "").split()
    if len(args) != 2:
        await message.answer("Foydalanish: /set key value")
        return
    key, val = args[0], args[1]
    if key not in DEFAULT_SETTINGS:
        await message.answer("❌ Noma'lum key")
        return
    try:
        await set_setting(key, val)
        await message.answer(f"✅ {key} = {val}")
    except Exception as e:
        log.error("set_setting failed: %s", e)
        await message.answer("❌ Xato")


@router.callback_query(F.data == "admin:cards")
async def cb_admin_cards(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT card_id, card_number, holder, bank, active FROM payment_cards ORDER BY card_id DESC LIMIT 20"
        )
    lines = ["💳 <b>Kartalar</b>\n"]
    for r in rows:
        status = "✅" if r["active"] else "❌"
        lines.append(f"{status} #{r['card_id']}: {r['card_number']} — {r['holder']} ({r['bank'] or '-'})")
    if not rows:
        lines.append("Kartalar yo'q.")
    lines.append("\nQo'shish: <code>/addcard 8600... Ism Bank</code>")
    lines.append("O'chirish: <code>/delcard 1</code>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.message(Command("addcard"))
async def cmd_addcard(message: Message, command: CommandObject):
    if not _is_admin(int(message.from_user.id)):
        await message.answer("⛔")
        return
    args = (command.args or "").split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Foydalanish: /addcard <number> <holder> [bank]")
        return
    number, holder = args[0], args[1]
    bank = args[2] if len(args) > 2 else ""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO payment_cards(card_number, holder, bank, active) VALUES($1,$2,$3,TRUE)",
            number, holder, bank,
        )
    await message.answer("✅ Karta qo'shildi")


@router.message(Command("delcard"))
async def cmd_delcard(message: Message, command: CommandObject):
    if not _is_admin(int(message.from_user.id)):
        await message.answer("⛔")
        return
    try:
        cid = int((command.args or "").strip())
    except Exception:
        await message.answer("Foydalanish: /delcard <card_id>")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM payment_cards WHERE card_id=$1", cid)
    await message.answer("✅ O'chirildi")


@router.callback_query(F.data == "admin:certs")
async def cb_admin_certs(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT certificate_id, user_id, verification_code, type, score FROM certificates ORDER BY certificate_id DESC LIMIT 20"
        )
    lines = ["📜 <b>Sertifikatlar</b>\n"]
    for r in rows:
        lines.append(f"• {r['verification_code']} — {r['type']} {r['score']} (u:{r['user_id']})")
    if not rows:
        lines.append("Yo'q.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "admin:battles")
async def cb_admin_battles(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT battle_id, code, status, creator_id, opponent_id, winner_id FROM battles ORDER BY created_at DESC LIMIT 20"
        )
    lines = ["⚔️ <b>Battles</b>\n"]
    for r in rows:
        lines.append(f"• {r['code']} [{r['status']}] c:{r['creator_id']} o:{r['opponent_id'] or '-'} w:{r['winner_id'] or '-'}")
    if not rows:
        lines.append("Yo'q.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data == "admin:live")
async def cb_admin_live(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    mode = await get_setting("live_mode", "fake")
    base = await get_setting("live_fake_base", "95114")
    online = await get_setting("live_fake_online", "342")
    delta = await get_setting("live_fake_delta", "8")
    text = (
        f"🎯 <b>Live Counter</b>\n\n"
        f"Mode: <b>{mode}</b>\nBase: {base}\nOnline: {online}\nDelta: {delta}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="REAL", callback_data="live:real"),
         InlineKeyboardButton(text="FAKE", callback_data="live:fake")],
        [InlineKeyboardButton(text="⬅️", callback_data="admin:home")],
    ])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(F.data.startswith("live:"))
async def cb_admin_live_set(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    mode = cq.data.split(":", 1)[1]
    if mode not in ("real", "fake"):
        await cq.answer("❌")
        return
    await set_setting("live_mode", mode)
    await cq.answer(f"✅ {mode}")


@router.callback_query(F.data == "admin:settings")
async def cb_admin_settings(cq: CallbackQuery):
    if not _is_admin(int(cq.from_user.id)):
        await cq.answer("⛔", show_alert=True)
        return
    text = "⚙️ <b>Settings</b>\n\nBuyruqlar: /set, /addcard, /delcard, /broadcast"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️", callback_data="admin:home")
    ]])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject):
    if not _is_admin(int(message.from_user.id)):
        await message.answer("⛔")
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer("Foydalanish: /broadcast matn")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
    sent, failed = 0, 0
    for r in rows:
        try:
            await bot.send_message(int(r["user_id"]), text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.answer(f"✅ Yuborildi: {sent}\n❌ Xato: {failed}")


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    log.info("Starting up…")
    await init_pool()
    await ensure_schema()
    await seed_settings()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    # Webhook setup
    if WEBHOOK_URL:
        try:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET,
                drop_pending_updates=True,
            )
            info = await bot.get_webhook_info()
            log.info("Telegram webhook configured: %s pending=%s",
                     info.url, getattr(info, "pending_update_count", "?"))
        except Exception as e:
            log.error("Webhook setup failed: %s", e)
    else:
        log.warning("PUBLIC_BASE_URL not set — webhook not configured")

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Start"),
            BotCommand(command="admin", description="Admin panel"),
        ])
    except Exception as e:
        log.error("set_my_commands failed: %s", e)

    yield

    log.info("Shutting down…")
    try:
        if bot:
            if WEBHOOK_URL:
                try:
                    await bot.delete_webhook(drop_pending_updates=False)
                except Exception as e:
                    log.error("delete_webhook failed: %s", e)
            try:
                await bot.session.close()
            except Exception as e:
                log.error("bot session close failed: %s", e)
    finally:
        await close_pool()


app = FastAPI(lifespan=lifespan, title="IQ TEST BOT")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")
if os.path.isdir(WEBAPP_DIR):
    app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")
else:
    log.warning("webapp dir not found: %s", WEBAPP_DIR)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    index = os.path.join(WEBAPP_DIR, "index.html")
    if not os.path.isfile(index):
        return HTMLResponse("<h1>index.html not found</h1>", status_code=500)
    with open(index, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: Optional[str] = Header(default=None)):
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid secret")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    try:
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
    except Exception as e:
        log.error("webhook update failed: %s", e)
    return {"ok": True}
    # =============================================================================
# bot.py — PART 2/6 (davomi): API route'lar va uvicorn launcher
# =============================================================================

# -----------------------------------------------------------------------------
# /api/profile/save
# -----------------------------------------------------------------------------
@app.post("/api/profile/save")
async def api_profile_save(request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    full_name = str(body.get("full_name") or "").strip()[:120]
    gender = str(body.get("gender") or "").strip()[:32]
    age_raw = body.get("age")
    try:
        age = int(age_raw) if age_raw not in (None, "", "null") else None
    except Exception:
        age = None
    country = str(body.get("country") or "").strip()[:64]
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET full_name=COALESCE(NULLIF($2,''), full_name),
                gender=COALESCE(NULLIF($3,''), gender),
                age=COALESCE($4, age),
                country=COALESCE(NULLIF($5,''), country),
                updated_at=NOW()
            WHERE user_id=$1
            """,
            uid, full_name, gender, age, country,
        )
    return {"ok": True}


@app.get("/api/profile/me")
async def api_profile_me(request: Request):
    uid = await auth_user_id(request)
    u = await get_user(uid) or {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        has_iq = await conn.fetchval(
            "SELECT 1 FROM results WHERE user_id=$1 AND test_type='iq' LIMIT 1", uid
        )
        has_eq = await conn.fetchval(
            "SELECT 1 FROM results WHERE user_id=$1 AND test_type='eq' LIMIT 1", uid
        )
        has_pq = await conn.fetchval(
            "SELECT 1 FROM results WHERE user_id=$1 AND test_type='pq' LIMIT 1", uid
        )
    return {
        "ok": True,
        "user": {
            "user_id": uid,
            "full_name": u.get("full_name"),
            "gender": u.get("gender"),
            "age": u.get("age"),
            "country": u.get("country"),
            "language": u.get("language") or "uz",
        },
        "unlocked": {
            "iq": True,
            "eq": bool(has_iq),
            "pq": bool(has_eq),
            "personal": bool(has_iq and has_eq and has_pq),
        },
    }


# -----------------------------------------------------------------------------
# /api/stats/live  (GET only)
# -----------------------------------------------------------------------------
_live_fake_state = {"base": None, "online": None, "delta": None}


@app.get("/api/stats/live")
async def api_stats_live():
    mode = await get_setting("live_mode", "fake")
    if mode == "real":
        pool = await get_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            online = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_seen >= NOW() - INTERVAL '5 minutes'"
            ) or 0
        return {"ok": True, "mode": "real", "total": int(total), "online": int(online)}
    # fake
    base = await get_setting_int("live_fake_base", 95114)
    online0 = await get_setting_int("live_fake_online", 342)
    delta = await get_setting_int("live_fake_delta", 8)
    delta = max(0, delta)
    jitter_total = random.randint(-delta, delta)
    jitter_online = random.randint(-max(1, delta // 2), max(1, delta // 2))
    total = max(1, base + jitter_total)
    online = max(1, online0 + jitter_online)
    return {"ok": True, "mode": "fake", "total": int(total), "online": int(online)}


# -----------------------------------------------------------------------------
# /api/test/questions
# -----------------------------------------------------------------------------
@app.get("/api/test/questions")
async def api_test_questions(request: Request, type: str = "iq"):
    _ = await auth_user_id(request)
    t = (type or "iq").lower()
    if t == "iq":
        return {"ok": True, "type": "iq", "questions": IQ_QUESTIONS}
    if t == "eq":
        return {"ok": True, "type": "eq", "questions": EQ_QUESTIONS}
    if t == "pq":
        return {"ok": True, "type": "pq", "questions": PQ_QUESTIONS}
    raise HTTPException(status_code=400, detail="unknown test type")


# -----------------------------------------------------------------------------
# /api/test/start
# -----------------------------------------------------------------------------
@app.post("/api/test/start")
async def api_test_start(request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    t = str(body.get("type") or "iq").lower()
    if t not in ("iq", "eq", "pq"):
        raise HTTPException(status_code=400, detail="unknown type")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Unlock checks
        if t == "eq":
            exists = await conn.fetchval(
                "SELECT 1 FROM results WHERE user_id=$1 AND test_type='iq' LIMIT 1", uid
            )
            if not exists:
                raise HTTPException(status_code=403, detail="iq required first")
        if t == "pq":
            exists = await conn.fetchval(
                "SELECT 1 FROM results WHERE user_id=$1 AND test_type='eq' LIMIT 1", uid
            )
            if not exists:
                raise HTTPException(status_code=403, detail="eq required first")

        # attempt_no
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM test_attempts WHERE user_id=$1 AND test_type=$2",
            uid, t,
        ) or 0
        attempt_no = int(n) + 1

        session_id = uuid.uuid4().hex
        await conn.execute(
            """
            INSERT INTO test_sessions(session_id, user_id, test_type, status)
            VALUES($1, $2, $3, 'active')
            """,
            session_id, uid, t,
        )
    # price
    price_key = f"{t}_price" if attempt_no == 1 else f"{t}_retry_price"
    price = await get_setting_int(price_key, 0)
    return {
        "ok": True,
        "session_id": session_id,
        "type": t,
        "attempt_no": attempt_no,
        "price": price,
        "questions": IQ_QUESTIONS if t == "iq" else (EQ_QUESTIONS if t == "eq" else PQ_QUESTIONS),
    }


# -----------------------------------------------------------------------------
# /api/test/submit
# -----------------------------------------------------------------------------
@app.post("/api/test/submit")
async def api_test_submit(request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    session_id = str(body.get("session_id") or "").strip()
    answers = body.get("answers") or {}
    duration = int(body.get("duration") or 0) if str(body.get("duration") or "0").isdigit() else 0
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    if not isinstance(answers, dict):
        raise HTTPException(status_code=400, detail="answers must be object")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            sess = await conn.fetchrow(
                "SELECT * FROM test_sessions WHERE session_id=$1 FOR UPDATE", session_id
            )
            if not sess:
                raise HTTPException(status_code=404, detail="session not found")
            if int(sess["user_id"]) != uid:
                raise HTTPException(status_code=403, detail="not your session")
            if sess["status"] != "active":
                # idempotent: return existing attempt
                existing = await conn.fetchrow(
                    "SELECT * FROM test_attempts WHERE session_id=$1", session_id
                )
                if existing:
                    return _attempt_to_result(dict(existing))
                raise HTTPException(status_code=409, detail="session already used")

            t = str(sess["test_type"]).lower()
            attempt_no = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM test_attempts WHERE user_id=$1 AND test_type=$2",
                    uid, t,
                ) or 0
            ) + 1
            # scoring
            if t == "iq":
                s = score_iq(answers)
                score = s["score"]; level = s["level"]; correct = s["correct_count"]; weighted = s["weighted"]
            elif t == "eq":
                s = score_eq(answers)
                score = s["score"]; level = s["level"]; correct = 0; weighted = 0
            else:
                s = score_pq(answers)
                score = s["score"]; level = s["level"]; correct = 0; weighted = 0

            # price
            price_key = f"{t}_price" if attempt_no == 1 else f"{t}_retry_price"
            price = await get_setting_int(price_key, 0)

            visible = (price <= 0)
            payment_status = "none" if price <= 0 else "pending"

            row = await conn.fetchrow(
                """
                INSERT INTO test_attempts(
                    user_id, test_type, session_id, answers, score, correct_count,
                    weighted, duration, level, payment_status, result_visible, attempt_no
                )
                VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10,$11,$12)
                RETURNING *
                """,
                uid, t, session_id, json.dumps(answers), score, correct, weighted,
                duration, level, payment_status, visible, attempt_no,
            )
            await conn.execute(
                "UPDATE test_sessions SET status='completed', completed_at=NOW() WHERE session_id=$1",
                session_id,
            )

            # If free and visible -> write result
            if visible:
                await conn.execute(
                    """
                    INSERT INTO results(user_id, attempt_id, test_type, score, level)
                    VALUES($1,$2,$3,$4,$5)
                    ON CONFLICT (attempt_id) DO NOTHING
                    """,
                    uid, int(row["attempt_id"]), t, score, level,
                )
                # auto-generate certificate for IQ
                if t == "iq":
                    await _ensure_certificate(conn, uid, score, level, "IQ")
                if t == "eq":
                    await _ensure_certificate(conn, uid, score, level, "EQ")
                if t == "pq":
                    await _ensure_certificate(conn, uid, score, level, "PQ")

            result = _attempt_to_result(dict(row))
    if result.get("result_visible"):
        result["price"] = 0
    else:
        result["price"] = price
        result["payment_required"] = True
    return result


async def _ensure_certificate(conn, uid: int, score: int, level: str, ttype: str):
    u = await conn.fetchrow("SELECT full_name, first_name FROM users WHERE user_id=$1", uid)
    name = (u["full_name"] if u and u["full_name"] else (u["first_name"] if u else None)) or "Foydalanuvchi"
    existing = await conn.fetchrow(
        "SELECT certificate_id FROM certificates WHERE user_id=$1 AND type=$2",
        uid, ttype,
    )
    if existing:
        return
    code = _generate_verification_code()
    # ensure unique
    for _ in range(10):
        dup = await conn.fetchval(
            "SELECT 1 FROM certificates WHERE verification_code=$1", code
        )
        if not dup:
            break
        code = _generate_verification_code()
    await conn.execute(
        """
        INSERT INTO certificates(user_id, verification_code, type, full_name, score, level)
        VALUES($1,$2,$3,$4,$5,$6)
        """,
        uid, code, ttype, name, score, level,
    )


def _attempt_to_result(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "attempt_id": int(a.get("attempt_id") or 0),
        "type": a.get("test_type"),
        "score": a.get("score"),
        "level": a.get("level"),
        "correct_count": a.get("correct_count"),
        "weighted": a.get("weighted"),
        "result_visible": bool(a.get("result_visible")),
        "attempt_no": a.get("attempt_no"),
    }


# -----------------------------------------------------------------------------
# /api/result/me
# -----------------------------------------------------------------------------
@app.get("/api/result/me")
async def api_result_me(request: Request, type: str = "iq"):
    uid = await auth_user_id(request)
    t = (type or "iq").lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM test_attempts
            WHERE user_id=$1 AND test_type=$2
            ORDER BY attempt_id DESC LIMIT 1
            """,
            uid, t,
        )
        if not row:
            return {"ok": True, "has_result": False}
        a = dict(row)
        # certificate
        cert = await conn.fetchrow(
            "SELECT verification_code, type, score, level, created_at FROM certificates "
            "WHERE user_id=$1 AND type=$2 ORDER BY certificate_id DESC LIMIT 1",
            uid, t.upper(),
        )
    return {
        "ok": True,
        "has_result": True,
        "attempt_id": int(a["attempt_id"]),
        "type": a["test_type"],
        "score": a["score"],
        "level": a["level"],
        "correct_count": a["correct_count"],
        "weighted": a["weighted"],
        "result_visible": bool(a["result_visible"]),
        "payment_status": a["payment_status"],
        "certificate": {
            "verification_code": cert["verification_code"],
            "score": cert["score"],
            "level": cert["level"],
        } if cert else None,
    }


# -----------------------------------------------------------------------------
# /api/payment/cards
# -----------------------------------------------------------------------------
@app.get("/api/payment/cards")
async def api_payment_cards(request: Request):
    _ = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT card_id, card_number, holder, bank FROM payment_cards WHERE active=TRUE ORDER BY card_id DESC"
        )
    return {"ok": True, "cards": [dict(r) for r in rows]}


# -----------------------------------------------------------------------------
# /api/payment/create
# -----------------------------------------------------------------------------
@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    purpose = str(body.get("purpose") or "").strip()
    amount = int(body.get("amount") or 0)
    attempt_id = body.get("attempt_id")
    battle_id = body.get("battle_id")
    card_id = body.get("card_id")
    if purpose not in ("iq", "iq_retry", "eq", "eq_retry", "pq", "pq_retry", "battle"):
        raise HTTPException(status_code=400, detail="bad purpose")
    if amount < 0:
        raise HTTPException(status_code=400, detail="bad amount")
    pool = await get_pool()
    async with pool.acquire() as conn:
        # If IQ/EQ/PQ -> link attempt
        if attempt_id:
            a = await conn.fetchrow(
                "SELECT * FROM test_attempts WHERE attempt_id=$1", int(attempt_id)
            )
            if not a or int(a["user_id"]) != uid:
                raise HTTPException(status_code=403, detail="not your attempt")
        pid = await conn.fetchval(
            """
            INSERT INTO payments(user_id, amount, purpose, attempt_id, battle_id, card_id, status)
            VALUES($1,$2,$3,$4,$5,$6,'pending')
            RETURNING payment_id
            """,
            uid, amount, purpose,
            int(attempt_id) if attempt_id else None,
            str(battle_id) if battle_id else None,
            int(card_id) if card_id else None,
        )
    return {"ok": True, "payment_id": int(pid), "status": "pending"}


# -----------------------------------------------------------------------------
# /api/payment/receipt  (multipart upload OR file_id)
# -----------------------------------------------------------------------------
@app.post("/api/payment/receipt")
async def api_payment_receipt(request: Request):
    uid = await auth_user_id(request)
    ct = request.headers.get("content-type", "")
    payment_id = None
    file_id = None
    if "application/json" in ct:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="invalid json")
        payment_id = body.get("payment_id")
        file_id = body.get("file_id")
    else:
        form = await request.form()
        payment_id = form.get("payment_id")
        file_id = form.get("file_id")
    if not payment_id:
        raise HTTPException(status_code=400, detail="payment_id required")
    pool = await get_pool()
    async with pool.acquire() as conn:
        p = await conn.fetchrow("SELECT * FROM payments WHERE payment_id=$1", int(payment_id))
        if not p or int(p["user_id"]) != uid:
            raise HTTPException(status_code=403, detail="not your payment")
        if file_id:
            await conn.execute(
                "UPDATE payments SET receipt_file_id=$1 WHERE payment_id=$2",
                str(file_id), int(payment_id),
            )
    # Notify admin
    if ADMIN_USER_ID and bot:
        try:
            await bot.send_message(
                ADMIN_USER_ID,
                f"🧾 Yangi receipt #{payment_id} user {uid}",
            )
        except Exception as e:
            log.error("notify admin receipt failed: %s", e)
    return {"ok": True}


# -----------------------------------------------------------------------------
# /api/payment/status
# -----------------------------------------------------------------------------
@app.get("/api/payment/status")
async def api_payment_status(request: Request, payment_id: int):
    uid = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payment_id, status, purpose, amount FROM payments WHERE payment_id=$1 AND user_id=$2",
            int(payment_id), uid,
        )
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True, **dict(row)}


# -----------------------------------------------------------------------------
# /api/certificate/me
# -----------------------------------------------------------------------------
@app.get("/api/certificate/me")
async def api_cert_me(request: Request, type: str = "IQ"):
    uid = await auth_user_id(request)
    t = (type or "IQ").upper()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT verification_code, type, score, level, full_name, created_at FROM certificates "
            "WHERE user_id=$1 AND type=$2 ORDER BY certificate_id DESC LIMIT 1",
            uid, t,
        )
    if not row:
        return {"ok": True, "has_certificate": False}
    return {"ok": True, "has_certificate": True, **dict(row)}


# -----------------------------------------------------------------------------
# /api/ranking
# -----------------------------------------------------------------------------
@app.get("/api/ranking")
async def api_ranking(request: Request, type: str = "iq"):
    uid = await auth_user_id(request)
    t = (type or "iq").lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.user_id, COALESCE(u.full_name, u.first_name, 'User') AS name,
                   MAX(r.score) AS best
            FROM results r JOIN users u ON u.user_id = r.user_id
            WHERE r.test_type=$1
            GROUP BY u.user_id, name
            ORDER BY best DESC LIMIT 50
            """,
            t,
        )
        my_best = await conn.fetchval(
            "SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type=$2",
            uid, t,
        )
        my_pos = await conn.fetchval(
            """
            SELECT COUNT(*)+1 FROM (
                SELECT u.user_id, MAX(r.score) AS b
                FROM results r JOIN users u ON u.user_id = r.user_id
                WHERE r.test_type=$1
                GROUP BY u.user_id
                HAVING MAX(r.score) > COALESCE($2, -1)
            ) t
            """,
            t, my_best,
        )
    return {
        "ok": True,
        "type": t,
        "list": [{"rank": i + 1, **dict(r)} for i, r in enumerate(rows)],
        "me": {"best": my_best, "position": int(my_pos or 1)},
    }


# -----------------------------------------------------------------------------
# /api/referral/me
# -----------------------------------------------------------------------------
@app.get("/api/referral/me")
async def api_referral_me(request: Request):
    uid = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        cnt = await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", uid
        ) or 0
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    return {"ok": True, "count": int(cnt), "link": link}


# -----------------------------------------------------------------------------
# Battle
# -----------------------------------------------------------------------------
def _gen_battle_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(4))


@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    uid = await auth_user_id(request)
    price = await get_setting_int("battle_price", 7500)
    pool = await get_pool()
    async with pool.acquire() as conn:
        # unique code
        code = _gen_battle_code()
        for _ in range(20):
            exists = await conn.fetchval("SELECT 1 FROM battles WHERE code=$1", code)
            if not exists:
                break
            code = _gen_battle_code()
        battle_id = uuid.uuid4().hex
        await conn.execute(
            """
            INSERT INTO battles(battle_id, code, creator_id, status, test_type)
            VALUES($1,$2,$3,'waiting','iq')
            """,
            battle_id, code, uid,
        )
        await conn.execute(
            """
            INSERT INTO battle_players(battle_id, user_id, payment_ok)
            VALUES($1, $2, FALSE)
            """,
            battle_id, uid,
        )
    return {"ok": True, "battle_id": battle_id, "code": code, "price": price, "status": "waiting"}


@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    code = str(body.get("code") or "").strip().upper()
    if len(code) != 4:
        raise HTTPException(status_code=400, detail="bad code")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            b = await conn.fetchrow("SELECT * FROM battles WHERE code=$1 FOR UPDATE", code)
            if not b:
                raise HTTPException(status_code=404, detail="battle not found")
            if int(b["creator_id"]) == uid:
                raise HTTPException(status_code=400, detail="cannot join own battle")
            if b["opponent_id"] and int(b["opponent_id"]) != uid:
                raise HTTPException(status_code=409, detail="already full")
            if b["opponent_id"] is None:
                await conn.execute(
                    "UPDATE battles SET opponent_id=$2, status='payment' WHERE battle_id=$1",
                    b["battle_id"], uid,
                )
            await conn.execute(
                """
                INSERT INTO battle_players(battle_id, user_id, payment_ok)
                VALUES($1, $2, FALSE)
                ON CONFLICT (battle_id, user_id) DO NOTHING
                """,
                b["battle_id"], uid,
            )
    price = await get_setting_int("battle_price", 7500)
    return {"ok": True, "battle_id": b["battle_id"], "price": price, "status": "payment"}


@app.get("/api/battle/me")
async def api_battle_me(request: Request):
    uid = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT b.* FROM battles b JOIN battle_players p ON p.battle_id=b.battle_id
            WHERE p.user_id=$1 AND b.status NOT IN ('finished','cancelled')
            ORDER BY b.created_at DESC LIMIT 1
            """,
            uid,
        )
        if not row:
            return {"ok": True, "has_battle": False}
        b = dict(row)
        players = await conn.fetch(
            "SELECT user_id, payment_ok, finished, score FROM battle_players WHERE battle_id=$1",
            b["battle_id"],
        )
    return {
        "ok": True, "has_battle": True,
        "battle": {
            "battle_id": b["battle_id"],
            "code": b["code"],
            "status": b["status"],
            "creator_id": b["creator_id"],
            "opponent_id": b["opponent_id"],
            "winner_id": b["winner_id"],
            "players": [dict(p) for p in players],
            "you": uid,
        },
    }


@app.post("/api/battle/{battle_id}/submit")
async def api_battle_submit(battle_id: str, request: Request):
    uid = await auth_user_id(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise HTTPException(status_code=400, detail="answers must be object")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            b = await conn.fetchrow("SELECT * FROM battles WHERE battle_id=$1 FOR UPDATE", battle_id)
            if not b:
                raise HTTPException(status_code=404, detail="battle not found")
            if uid not in (int(b["creator_id"]), int(b["opponent_id"] or 0)):
                raise HTTPException(status_code=403, detail="not participant")
            if b["status"] not in ("ready", "active"):
                raise HTTPException(status_code=409, detail="not active")
            player = await conn.fetchrow(
                "SELECT * FROM battle_players WHERE battle_id=$1 AND user_id=$2 FOR UPDATE",
                battle_id, uid,
            )
            if not player or not bool(player["payment_ok"]):
                raise HTTPException(status_code=402, detail="payment required")
            if bool(player["finished"]):
                return {"ok": True, "already": True}

            s = score_iq(answers)
            score = s["score"]

            await conn.execute(
                "UPDATE battle_players SET score=$3, finished=TRUE WHERE battle_id=$1 AND user_id=$2",
                battle_id, uid, score,
            )
            # also record attempt for stats
            sid = uuid.uuid4().hex
            await conn.execute(
                """
                INSERT INTO test_sessions(session_id, user_id, test_type, status, battle_id)
                VALUES($1,$2,'iq','completed',$3)
                """,
                sid, uid, battle_id,
            )
            await conn.execute(
                """
                INSERT INTO test_attempts(
                    user_id, test_type, session_id, answers, score, level,
                    payment_status, result_visible, attempt_no, battle_id
                )
                VALUES($1,'iq',$2,$3::jsonb,$4,$5,'approved',TRUE,1,$6)
                ON CONFLICT (session_id) DO NOTHING
                """,
                uid, sid, json.dumps(answers), score, s["level"], battle_id,
            )

            # Finalize if both done
            rows = await conn.fetch(
                "SELECT user_id, score, finished FROM battle_players WHERE battle_id=$1",
                battle_id,
            )
            if len(rows) == 2 and all(bool(r["finished"]) for r in rows):
                creator_id = int(b["creator_id"])
                opp_id = int(b["opponent_id"])
                c_score = next(int(r["score"]) for r in rows if int(r["user_id"]) == creator_id)
                o_score = next(int(r["score"]) for r in rows if int(r["user_id"]) == opp_id)
                winner = None
                if c_score > o_score:
                    winner = creator_id
                elif o_score > c_score:
                    winner = opp_id
                await conn.execute(
                    """
                    UPDATE battles
                    SET status='finished', creator_score=$2, opponent_score=$3,
                        winner_id=$4, finished_at=NOW()
                    WHERE battle_id=$1 AND status != 'finished'
                    """,
                    battle_id, c_score, o_score, winner,
                )
    return {"ok": True}


@app.get("/api/battle/{battle_id}/state")
async def api_battle_state(battle_id: str, request: Request):
    uid = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE battle_id=$1", battle_id)
        if not b:
            raise HTTPException(status_code=404, detail="battle not found")
        if uid not in (int(b["creator_id"]), int(b["opponent_id"] or 0)):
            raise HTTPException(status_code=403, detail="not participant")
        players = await conn.fetch(
            "SELECT user_id, payment_ok, finished FROM battle_players WHERE battle_id=$1",
            battle_id,
        )
    you_done = next((bool(p["finished"]) for p in players if int(p["user_id"]) == uid), False)
    opp_done = next((bool(p["finished"]) for p in players if int(p["user_id"]) != uid), False)
    resp = {
        "ok": True,
        "battle_id": battle_id,
        "status": b["status"],
        "you_finished": you_done,
        "opponent_finished": opp_done,
        "you": uid,
    }
    if b["status"] == "finished":
        resp.update({
            "winner_id": b["winner_id"],
            "creator_score": b["creator_score"],
            "opponent_score": b["opponent_score"],
        })
    return resp


# -----------------------------------------------------------------------------
# Personal profile (IQ + EQ + PQ summary)
# -----------------------------------------------------------------------------
@app.get("/api/profile/personal")
async def api_profile_personal(request: Request):
    uid = await auth_user_id(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        iq = await conn.fetchval(
            "SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='iq'", uid
        )
        eq = await conn.fetchval(
            "SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='eq'", uid
        )
        pq = await conn.fetchval(
            "SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='pq'", uid
        )
    if iq is None or eq is None or pq is None:
        raise HTTPException(status_code=403, detail="locked")
    strengths = []
    growth = []
    if iq >= 110:
        strengths.append("Yuqori mantiqiy fikrlash")
    else:
        growth.append("Mantiqiy fikrlashni rivojlantirish")
    if eq >= 75:
        strengths.append("Yaxshi emotsional intellekt")
    else:
        growth.append("Emotsiyalarni boshqarish")
    if pq >= 75:
        strengths.append("Yuqori samaradorlik")
    else:
        growth.append("Vaqtni boshqarish va odatlar")
    return {
        "ok": True,
        "iq": iq, "eq": eq, "pq": pq,
        "strengths": strengths, "growth": growth,
    }


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
    