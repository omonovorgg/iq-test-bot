import asyncio
import hashlib
import hmac
import json
import os
import secrets
import string
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
WEBAPP_URL = os.environ.get("WEBAPP_URL")
PORT = int(os.environ.get("PORT", "10000"))
# NOTE: per spec (section 3 / 88) the admin must be identified ONLY by
# ADMIN_USER_ID. ADMIN_USERNAME is kept only for display purposes
# (e.g. "support: @omono_v" in help text), never for auth checks.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "omono_v").lstrip("@").lower()
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0") or 0)

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")
if not WEBAPP_URL or not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("WEBAPP_URL must be an https:// URL")
if not WEBAPP_DIR.exists():
    raise RuntimeError(f"Missing webapp directory: {WEBAPP_DIR}")
if not ADMIN_USER_ID:
    print("WARNING: ADMIN_USER_ID is not set. Admin panel will be inaccessible.")

QUESTIONS_COUNT = 18
QUIZ_VERSION = 5  # bumped: answer key / weights realigned with frontend

# ---------------------------------------------------------------------------
# Authoritative server-side answer key.
#
# IMPORTANT: this array MUST always match, index for index, the `correct`
# field of each object in IQ_QUESTIONS inside webapp/app.js. If the puzzle
# bank in app.js is ever edited, this array must be updated in the same
# change, or scoring will silently diverge from what the user sees
# (see spec section 77).
#
# Q1..Q6   = EASY   (weight 1)
# Q7..Q12  = MEDIUM (weight 2)
# Q13..Q18 = HARD   (weight 3)
# ---------------------------------------------------------------------------
CORRECT_ANSWERS = (2, 1, 2, 3, 1, 3, 2, 3, 1, 0, 2, 1, 2, 3, 1, 0, 2, 3)
WEIGHTS = tuple([1] * 6 + [2] * 6 + [3] * 6)
MAX_RAW = sum(WEIGHTS)  # 36

PAYMENT_MODE_RETEST = "first_free_retest_paid"
PAYMENT_MODE_RESULT = "result_paid"
PAYMENT_MODE_FREE = "all_free"
VALID_PAYMENT_MODES = {PAYMENT_MODE_RETEST, PAYMENT_MODE_RESULT, PAYMENT_MODE_FREE}

# Payment purposes the API accepts. "iq" is the very first attempt (usually
# free, see access_iq()); "retest" is a paid IQ retry; eq/pq and their
# _retry variants are placeholders until the EQ/PQ product stage is built.
PAYMENT_PURPOSES = {"iq", "retest", "eq", "pq", "eq_retry", "pq_retry", "battle", "result"}

CERT_CODE_ALPHABET = string.ascii_uppercase + string.digits

pool: asyncpg.Pool | None = None
bot: Bot | None = None
BOT_USERNAME = ""
dp = Dispatcher()
app = FastAPI(title="IQ TEST BOT")
admin_state: dict[int, str] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_db_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in {"sslmode", "channel_binding"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def webhook_url() -> str:
    parts = urlsplit(WEBAPP_URL)
    return f"{parts.scheme}://{parts.netloc}/telegram/webhook"


def webhook_secret() -> str:
    return hashlib.sha256(BOT_TOKEN.encode()).hexdigest()


async def init_db() -> None:
    global pool
    pool = await asyncpg.create_pool(
        clean_db_url(DATABASE_URL), min_size=1, max_size=5, ssl="require", command_timeout=30
    )
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                first_name TEXT NOT NULL DEFAULT '',
                last_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER,
                best_raw INTEGER,
                best_time INTEGER,
                referrals INTEGER NOT NULL DEFAULT 0,
                cert_claimed BOOLEAN NOT NULL DEFAULT FALSE,
                referred_by BIGINT,
                referral_counted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS best_score INTEGER;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS best_raw INTEGER;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS best_time INTEGER;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS referrals INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS cert_claimed BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_counted BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW();
        """)

        await conn.execute("ALTER TABLE users ALTER COLUMN language SET DEFAULT ''")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            INSERT INTO app_settings(key,value) VALUES
                ('price_uzs','10000'),
                ('battle_price_uzs','7500'),
                ('payment_mode','first_free_retest_paid'),
                ('app_name','IQ TEST BOT'),
                ('retry_price_uzs','5000')
            ON CONFLICT(key) DO NOTHING;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_cards (
                id BIGSERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS holder TEXT NOT NULL DEFAULT ''")
        await conn.execute("ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_sessions (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                quiz_version INTEGER NOT NULL DEFAULT 5,
                answers JSONB NOT NULL DEFAULT '[]'::jsonb,
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                raw_score INTEGER NOT NULL,
                iq_score INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                elapsed INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_payments (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
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
        await conn.execute("ALTER TABLE iq_payments ADD COLUMN IF NOT EXISTS reference_id BIGINT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iq_battles (
                id BIGSERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                creator_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                opponent_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
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
        # Certificates: durable, verifiable records (spec sections 53-56).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id BIGSERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                first_name TEXT NOT NULL DEFAULT '',
                last_name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_best_score ON users(best_score DESC NULLS LAST);
            CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
            CREATE INDEX IF NOT EXISTS idx_iq_payments_user ON iq_payments(user_id,status,purpose);
            CREATE INDEX IF NOT EXISTS idx_iq_battles_code ON iq_battles(code);
            CREATE INDEX IF NOT EXISTS idx_certificates_code ON certificates(code);
            CREATE INDEX IF NOT EXISTS idx_certificates_user ON certificates(user_id);
        """)
    print("Database initialized successfully")


async def db_user(tg_user: dict, referral_id: int | None = None) -> None:
    assert pool is not None
    uid = int(tg_user["id"])
    if referral_id == uid:
        referral_id = None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id,first_name,last_name,username,referred_by,last_seen,updated_at)
            VALUES($1,$2,$3,$4,$5,NOW(),NOW())
            ON CONFLICT(user_id) DO UPDATE SET
                first_name=EXCLUDED.first_name,
                last_name=EXCLUDED.last_name,
                username=EXCLUDED.username,
                referred_by=COALESCE(users.referred_by,EXCLUDED.referred_by),
                last_seen=NOW(),
                updated_at=NOW()
        """, uid, tg_user.get("first_name") or "", tg_user.get("last_name") or "",
             tg_user.get("username") or "", referral_id)


async def get_user(uid: int):
    assert pool is not None
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def get_setting(key: str, default: str = "") -> str:
    assert pool is not None
    async with pool.acquire() as conn:
        value = await conn.fetchval("SELECT value FROM app_settings WHERE key=$1", key)
        return str(value) if value is not None else default


async def set_setting(key: str, value: str) -> None:
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO app_settings(key,value,updated_at) VALUES($1,$2,NOW())
            ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
        """, key, value)


async def get_price() -> int:
    try:
        return max(0, int(await get_setting("price_uzs", "10000")))
    except ValueError:
        return 10000


async def get_battle_price() -> int:
    try:
        return max(0, int(await get_setting("battle_price_uzs", "7500")))
    except ValueError:
        return 7500


async def get_retry_price() -> int:
    try:
        return max(0, int(await get_setting("retry_price_uzs", "5000")))
    except ValueError:
        return 5000


async def price_for_purpose(purpose: str) -> int:
    """Central place to resolve a price for any payment purpose.

    Kept intentionally simple (single retry price shared by IQ/EQ/PQ
    retries) until the products admin screen (spec section 66-68) is
    built with per-product pricing.
    """
    if purpose == "battle":
        return await get_battle_price()
    if purpose in {"iq", "result"}:
        return await get_price()
    # retest, eq, pq, eq_retry, pq_retry
    return await get_retry_price()


async def get_payment_mode() -> str:
    value = await get_setting("payment_mode", PAYMENT_MODE_RETEST)
    return value if value in VALID_PAYMENT_MODES else PAYMENT_MODE_RETEST


def is_admin(user) -> bool:
    """Admin identity is decided ONLY by Telegram user id (spec 3 / 88).

    A username can change hands, so it must never grant admin access.
    """
    if not user or not ADMIN_USER_ID:
        return False
    return int(user.id) == ADMIN_USER_ID


def sanitize_answers(values) -> list[int]:
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except Exception:
            values = []
    if not isinstance(values, list):
        return []
    out = []
    for value in values[:QUESTIONS_COUNT]:
        try:
            value = int(value)
        except (TypeError, ValueError):
            break
        if value < 0 or value > 3:
            break
        out.append(value)
    return out


def score_answers(answers: list[int]) -> tuple[int, int]:
    correct = sum(i < len(answers) and answers[i] == CORRECT_ANSWERS[i] for i in range(QUESTIONS_COUNT))
    raw = sum(WEIGHTS[i] for i in range(min(len(answers), QUESTIONS_COUNT)) if answers[i] == CORRECT_ANSWERS[i])
    return raw, int(correct)


def calculate_iq(raw: int) -> int:
    raw = max(0, min(raw, MAX_RAW))
    # Product score / IQ-style estimate, not a standardized clinical IQ test.
    return max(70, min(145, round(70 + raw / MAX_RAW * 75)))


def score_level_uz(score: int) -> str:
    if score >= 135:
        return "JUDA YUQORI DARAJA"
    if score >= 120:
        return "YUQORI DARAJA"
    if score >= 105:
        return "YAXSHI DARAJA"
    if score >= 90:
        return "O‘RTACHA DARAJA"
    return "RIVOJLANTIRISH MUMKIN"


async def active_cards() -> list[dict]:
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id,card_number,holder FROM payment_cards WHERE active=TRUE ORDER BY id")
    return [dict(r) for r in rows]


async def create_payment(uid: int, purpose: str, reference_id: int | None = None) -> dict:
    if purpose not in PAYMENT_PURPOSES:
        raise HTTPException(400, "INVALID_PAYMENT_PURPOSE")
    price = await price_for_purpose(purpose)
    if price <= 0:
        return {"free": True, "allowed": True, "payment_id": None, "amount": 0, "cards": []}
    cards = await active_cards()
    if not cards:
        raise HTTPException(503, "NO_PAYMENT_CARD")
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id,amount FROM iq_payments
            WHERE user_id=$1 AND purpose=$2 AND status='pending' AND consumed=FALSE
              AND reference_id IS NOT DISTINCT FROM $3
            ORDER BY id DESC LIMIT 1
        """, uid, purpose, reference_id)
        if row:
            payment_id, amount = int(row["id"]), int(row["amount"])
        else:
            row = await conn.fetchrow("""
                INSERT INTO iq_payments(user_id,amount,purpose,reference_id) VALUES($1,$2,$3,$4)
                RETURNING id,amount
            """, uid, price, purpose, reference_id)
            payment_id, amount = int(row["id"]), int(row["amount"])
    return {"payment_id": payment_id, "amount": amount, "cards": cards, "free": False}


async def payment_status(uid: int, payment_id: int) -> dict:
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id,amount,purpose,status,consumed FROM iq_payments WHERE id=$1 AND user_id=$2
        """, payment_id, uid)
    if not row:
        raise HTTPException(404, "PAYMENT_NOT_FOUND")
    return {"payment_id": int(row["id"]), "amount": int(row["amount"]),
            "purpose": row["purpose"], "status": row["status"], "consumed": bool(row["consumed"])}


async def consume_payment(conn, uid: int, purpose: str) -> int | None:
    row = await conn.fetchrow("""
        SELECT id FROM iq_payments
        WHERE user_id=$1 AND purpose=$2 AND status='approved' AND consumed=FALSE
        ORDER BY id ASC LIMIT 1 FOR UPDATE
    """, uid, purpose)
    if not row:
        return None
    await conn.execute("UPDATE iq_payments SET consumed=TRUE WHERE id=$1", row["id"])
    return int(row["id"])


async def get_rank(uid: int) -> int | None:
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT best_score,best_time FROM users WHERE user_id=$1", uid)
        if not row or row["best_score"] is None:
            return None
        rank = await conn.fetchval("""
            SELECT COUNT(*)+1 FROM users
            WHERE best_score IS NOT NULL AND (
                best_score>$1 OR
                (best_score=$1 AND COALESCE(best_time,2147483647)<COALESCE($2::INTEGER,2147483647))
            )
        """, row["best_score"], row["best_time"])
        return int(rank)


async def access_iq(uid: int) -> dict:
    assert pool is not None
    mode = await get_payment_mode()
    user = await get_user(uid)
    attempts = int(user["attempts"] if user else 0)
    if mode == PAYMENT_MODE_FREE or attempts == 0:
        return {"allowed": True, "free": True, "price": 0}
    if mode == PAYMENT_MODE_RESULT:
        return {"allowed": True, "free": True, "price": 0}
    async with pool.acquire() as conn:
        ok = await conn.fetchval("""
            SELECT EXISTS(SELECT 1 FROM iq_payments
            WHERE user_id=$1 AND purpose='retest' AND status='approved' AND consumed=FALSE)
        """, uid)
    return {"allowed": bool(ok), "free": False, "price": await get_retry_price()}


async def start_session(uid: int, language: str, battle_id: int | None = None) -> dict:
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)", uid)
            user = await conn.fetchrow("SELECT attempts FROM users WHERE user_id=$1 FOR UPDATE", uid)
            if not user:
                raise HTTPException(401, "USER_NOT_FOUND")
            session = await conn.fetchrow("SELECT * FROM iq_sessions WHERE user_id=$1 FOR UPDATE", uid)
            if session and int(session["quiz_version"]) != QUIZ_VERSION:
                await conn.execute("DELETE FROM iq_sessions WHERE user_id=$1", uid)
                session = None
            if session and not session["completed"]:
                answers = sanitize_answers(session["answers"])
                if len(answers) < QUESTIONS_COUNT:
                    return dict(session)
                await conn.execute("DELETE FROM iq_sessions WHERE user_id=$1", uid)
                session = None
            if session and session["completed"]:
                await conn.execute("DELETE FROM iq_sessions WHERE user_id=$1", uid)

            mode = await get_payment_mode()
            payment_id = None
            attempts = int(user["attempts"])
            if battle_id:
                battle = await conn.fetchrow(
                    "SELECT * FROM iq_battles WHERE id=$1 AND (creator_id=$2 OR opponent_id=$2) FOR UPDATE",
                    battle_id, uid
                )
                if not battle:
                    raise HTTPException(404, "BATTLE_NOT_FOUND")
                is_creator = int(battle["creator_id"]) == uid
                battle_payment_id = battle["creator_payment_id"] if is_creator else battle["opponent_payment_id"]
                if not battle_payment_id:
                    raise HTTPException(402, "BATTLE_PAYMENT_REQUIRED")
                payment = await conn.fetchrow(
                    "SELECT status,consumed FROM iq_payments WHERE id=$1 AND user_id=$2 FOR UPDATE",
                    battle_payment_id, uid
                )
                if not payment or payment["status"] != "approved" or payment["consumed"]:
                    raise HTTPException(402, "BATTLE_PAYMENT_REQUIRED")
                await conn.execute("UPDATE iq_payments SET consumed=TRUE WHERE id=$1", battle_payment_id)
                payment_id = int(battle_payment_id)
            elif mode == PAYMENT_MODE_RETEST and attempts > 0:
                payment_id = await consume_payment(conn, uid, "retest")
                if payment_id is None:
                    raise HTTPException(402, "PAID_RETEST")

            row = await conn.fetchrow("""
                INSERT INTO iq_sessions(user_id,quiz_version,started_at,last_activity,payment_id,result_unlocked)
                VALUES($1,$2,NOW(),NOW(),$3,TRUE) RETURNING *
            """, uid, QUIZ_VERSION, payment_id)
            return dict(row)


async def sync_answers(uid: int, answers: list[int]) -> dict:
    """Persist in-progress answers. Accepts partial or full answer lists —
    the Mini App can call this after every question (or once at the end);
    either way no per-question network round trip is required by the UI.
    """
    clean = sanitize_answers(answers)
    if not clean:
        raise HTTPException(400, "INVALID_ANSWERS")
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)", uid)
            row = await conn.fetchrow("SELECT * FROM iq_sessions WHERE user_id=$1 FOR UPDATE", uid)
            if not row or row["completed"]:
                raise HTTPException(409, "SESSION_EXPIRED")
            await conn.execute("""
                UPDATE iq_sessions SET answers=$2::jsonb,current_index=$3,
                last_activity=NOW() WHERE user_id=$1
            """, uid, json.dumps(clean), len(clean))
    return {"ok": True, "saved": len(clean)}


async def finish_session(uid: int) -> dict:
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)", uid)
            row = await conn.fetchrow("SELECT * FROM iq_sessions WHERE user_id=$1 FOR UPDATE", uid)
            if not row:
                raise HTTPException(409, "SESSION_EXPIRED")
            answers = sanitize_answers(row["answers"])
            if len(answers) != QUESTIONS_COUNT:
                raise HTTPException(409, "INCOMPLETE")
            raw, correct = score_answers(answers)
            iq = calculate_iq(raw)
            elapsed = max(0, int((now_utc() - row["started_at"]).total_seconds()))
            if row["completed"]:
                if row["result_unlocked"]:
                    return {"iq": int(row["result_iq"]), "raw": int(row["result_raw"]),
                            "correct": int(row["result_correct"]), "elapsed": int(row["result_elapsed"]),
                            "level": score_level_uz(int(row["result_iq"]))}
                payment_id = row["payment_id"]
                if not payment_id:
                    raise HTTPException(402, "PAYMENT_REQUIRED")
                payment = await conn.fetchrow(
                    "SELECT status,consumed FROM iq_payments WHERE id=$1 AND user_id=$2 FOR UPDATE",
                    payment_id, uid
                )
                if not payment or payment["status"] != "approved" or payment["consumed"]:
                    raise HTTPException(402, "PAYMENT_REQUIRED")
                await conn.execute("UPDATE iq_payments SET consumed=TRUE WHERE id=$1", payment_id)
                await conn.execute("""
                    INSERT INTO iq_attempts(user_id,raw_score,iq_score,correct,elapsed)
                    VALUES($1,$2,$3,$4,$5)
                """, uid, int(row["result_raw"]), int(row["result_iq"]), int(row["result_correct"]), int(row["result_elapsed"]))
                await conn.execute("""
                    UPDATE users SET attempts=attempts+1,
                    best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
                    best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
                    best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $4<best_time)) THEN $4 ELSE best_time END,
                    updated_at=NOW(),last_seen=NOW() WHERE user_id=$1
                """, uid, int(row["result_iq"]), int(row["result_raw"]), int(row["result_elapsed"]))
                await conn.execute("UPDATE iq_sessions SET result_unlocked=TRUE,result_counted=TRUE,last_activity=NOW() WHERE user_id=$1", uid)
                return {"iq": int(row["result_iq"]), "raw": int(row["result_raw"]),
                        "correct": int(row["result_correct"]), "elapsed": int(row["result_elapsed"]),
                        "level": score_level_uz(int(row["result_iq"]))}

            mode = await get_payment_mode()
            payment_id = row["payment_id"]
            if mode == PAYMENT_MODE_RESULT:
                if payment_id:
                    p = await conn.fetchrow("SELECT status,consumed FROM iq_payments WHERE id=$1 AND user_id=$2 FOR UPDATE", payment_id, uid)
                    if not p or p["status"] != "approved" or p["consumed"]:
                        raise HTTPException(402, "PAYMENT_REQUIRED")
                    await conn.execute("UPDATE iq_payments SET consumed=TRUE WHERE id=$1", payment_id)
                else:
                    cards = await active_cards()
                    if not cards:
                        raise HTTPException(503, "NO_PAYMENT_CARD")
                    p = await conn.fetchrow("INSERT INTO iq_payments(user_id,amount,purpose) VALUES($1,$2,'result') RETURNING id", uid, await get_price())
                    payment_id = int(p["id"])
                    await conn.execute("""
                        UPDATE iq_sessions SET completed=TRUE,result_iq=$2,result_raw=$3,result_correct=$4,
                        result_elapsed=$5,result_unlocked=FALSE,result_counted=FALSE,payment_id=$6,finished_at=NOW(),last_activity=NOW()
                        WHERE user_id=$1
                    """, uid, iq, raw, correct, elapsed, payment_id)
                    raise HTTPException(402, "PAYMENT_REQUIRED")

            await conn.execute("""
                INSERT INTO iq_attempts(user_id,raw_score,iq_score,correct,elapsed)
                VALUES($1,$2,$3,$4,$5)
            """, uid, raw, iq, correct, elapsed)
            await conn.execute("""
                UPDATE users SET attempts=attempts+1,
                best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
                best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
                best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $4<best_time)) THEN $4 ELSE best_time END,
                updated_at=NOW(),last_seen=NOW() WHERE user_id=$1
            """, uid, iq, raw, elapsed)
            await conn.execute("""
                UPDATE iq_sessions SET completed=TRUE,result_iq=$2,result_raw=$3,result_correct=$4,
                result_elapsed=$5,result_unlocked=TRUE,result_counted=TRUE,finished_at=NOW(),last_activity=NOW()
                WHERE user_id=$1
            """, uid, iq, raw, correct, elapsed)
            return {"iq": iq, "raw": raw, "correct": correct, "elapsed": elapsed, "level": score_level_uz(iq)}


async def battle_for_user(uid: int):
    assert pool is not None
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM iq_battles
            WHERE creator_id=$1 OR opponent_id=$1
            ORDER BY updated_at DESC LIMIT 1
        """, uid)


async def create_battle(uid: int) -> dict:
    assert pool is not None
    price = await get_battle_price()
    cards = await active_cards()
    if price <= 0:
        raise HTTPException(400, "PAYMENTS_DISABLED")
    if not cards:
        raise HTTPException(503, "NO_PAYMENT_CARD")
    async with pool.acquire() as conn:
        async with conn.transaction():
            code = None
            for _ in range(20):
                candidate = f"{secrets.randbelow(10000):04d}"
                exists = await conn.fetchval(
                    "SELECT 1 FROM iq_battles WHERE code=$1 AND status IN ('waiting','ready','active')", candidate
                )
                if not exists:
                    code = candidate
                    break
            if code is None:
                raise HTTPException(503, "BATTLE_CODE_UNAVAILABLE")
            battle = await conn.fetchrow(
                "INSERT INTO iq_battles(code,creator_id,status) VALUES($1,$2,'waiting') RETURNING id,code",
                code, uid
            )
            payment = await conn.fetchrow(
                "INSERT INTO iq_payments(user_id,amount,purpose,reference_id) VALUES($1,$2,'battle',$3) RETURNING id,amount",
                uid, price, int(battle["id"])
            )
            await conn.execute(
                "UPDATE iq_battles SET creator_payment_id=$2,updated_at=NOW() WHERE id=$1",
                battle["id"], payment["id"]
            )
    return {"battle_id": int(battle["id"]), "code": battle["code"], "payment_required": True,
            "payment_id": int(payment["id"]), "amount": int(payment["amount"]), "cards": cards}


async def join_battle(uid: int, code: str) -> dict:
    code = str(code).strip()
    if not code.isdigit() or len(code) != 4:
        raise HTTPException(400, "INVALID_BATTLE_CODE")
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            battle = await conn.fetchrow(
                "SELECT * FROM iq_battles WHERE code=$1 AND status='waiting' FOR UPDATE", code
            )
            if not battle:
                raise HTTPException(404, "BATTLE_NOT_FOUND")
            if int(battle["creator_id"]) == uid:
                raise HTTPException(400, "CANNOT_JOIN_OWN_BATTLE")
            if battle["opponent_id"] is not None:
                raise HTTPException(409, "BATTLE_FULL")
            price = await get_battle_price()
            cards = await active_cards()
            if price <= 0:
                raise HTTPException(400, "PAYMENTS_DISABLED")
            if not cards:
                raise HTTPException(503, "NO_PAYMENT_CARD")
            p = await conn.fetchrow(
                "INSERT INTO iq_payments(user_id,amount,purpose,reference_id) VALUES($1,$2,'battle',$3) RETURNING id,amount",
                uid, price, int(battle["id"])
            )
            await conn.execute(
                "UPDATE iq_battles SET opponent_id=$2,opponent_payment_id=$3,status='ready',updated_at=NOW() WHERE id=$1",
                battle["id"], uid, p["id"]
            )
    return {"battle_id": int(battle["id"]), "code": code, "payment_required": True,
            "payment_id": int(p["id"]), "amount": int(p["amount"]), "cards": cards}


async def battle_payment_ready(conn, payment_id: int) -> bool:
    if not payment_id:
        return False
    return bool(await conn.fetchval("SELECT status='approved' FROM iq_payments WHERE id=$1", payment_id))


async def battle_status(uid: int, battle_id: int | None = None) -> dict:
    assert pool is not None
    async with pool.acquire() as conn:
        if battle_id:
            row = await conn.fetchrow("SELECT * FROM iq_battles WHERE id=$1 AND (creator_id=$2 OR opponent_id=$2)", battle_id, uid)
        else:
            row = await conn.fetchrow("""
                SELECT * FROM iq_battles WHERE (creator_id=$1 OR opponent_id=$1)
                AND status NOT IN ('finished','cancelled') ORDER BY updated_at DESC LIMIT 1
            """, uid)
        if not row:
            raise HTTPException(404, "BATTLE_NOT_FOUND")
        mine_creator = int(row["creator_id"]) == uid
        my_payment = row["creator_payment_id"] if mine_creator else row["opponent_payment_id"]
        my_finished = bool(row["creator_finished"] if mine_creator else row["opponent_finished"])
        my_iq = row["creator_iq"] if mine_creator else row["opponent_iq"]
        opponent_joined = row["opponent_id"] is not None
        opponent_finished = bool(row["opponent_finished"] if mine_creator else row["creator_finished"])
        opponent_iq = row["opponent_iq"] if mine_creator else row["creator_iq"]
        paid = await battle_payment_ready(conn, int(my_payment) if my_payment else 0)
        if row["status"] == "finished":
            paid = True
        opponent_paid = False
        opponent_payment = row["opponent_payment_id"] if mine_creator else row["creator_payment_id"]
        if opponent_payment:
            opponent_paid = await battle_payment_ready(conn, int(opponent_payment))
            if row["status"] == "finished":
                opponent_paid = True
        result = None
        if row["status"] == "finished" and my_iq is not None and opponent_iq is not None:
            diff = int(my_iq) - int(opponent_iq)
            result = {"winner": "me" if diff > 0 else "opponent" if diff < 0 else "draw", "my_iq": int(my_iq), "opponent_iq": int(opponent_iq), "difference": abs(diff)}
        return {"battle_id": int(row["id"]), "code": row["code"], "status": row["status"],
                "payment_approved": paid, "opponent_payment_approved": opponent_paid,
                "both_paid": bool(paid and opponent_paid), "opponent_joined": opponent_joined,
                "my_finished": my_finished, "opponent_finished": opponent_finished,
                "my_iq": my_iq, "result": result}


async def finalize_battle(uid: int, iq: int, battle_id: int | None) -> None:
    if not battle_id:
        return
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM iq_battles WHERE id=$1 FOR UPDATE", battle_id)
            if not row or (int(row["creator_id"]) != uid and int(row["opponent_id"] or 0) != uid):
                return
            creator = int(row["creator_id"]) == uid
            if creator:
                await conn.execute("UPDATE iq_battles SET creator_finished=TRUE,creator_iq=$2,status=CASE WHEN opponent_finished THEN 'finished' ELSE 'active' END,updated_at=NOW() WHERE id=$1", battle_id, iq)
            else:
                await conn.execute("UPDATE iq_battles SET opponent_finished=TRUE,opponent_iq=$2,status=CASE WHEN creator_finished THEN 'finished' ELSE 'active' END,updated_at=NOW() WHERE id=$1", battle_id, iq)


def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(401, "INVALID_INIT_DATA")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash", None)
        if not received:
            raise ValueError("hash")
        auth_date = int(pairs.get("auth_date", "0"))
        now = int(now_utc().timestamp())
        if auth_date <= 0 or now - auth_date > 86400 or auth_date - now > 60:
            raise ValueError("auth_date")
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received):
            raise ValueError("hash")
        user = json.loads(pairs.get("user", "{}"))
        if not isinstance(user, dict) or not user.get("id"):
            raise ValueError("user")
        return user
    except Exception as exc:
        raise HTTPException(401, "INVALID_INIT_DATA") from exc


async def api_user(request: Request) -> dict:
    user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    await db_user(user)
    return user


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------

async def get_or_create_certificate(uid: int) -> dict | None:
    """Returns the user's certificate, creating one from their best score
    if they don't have one yet. Returns None if the user has no result.
    """
    assert pool is not None
    user = await get_user(uid)
    if not user or user["best_score"] is None:
        return None
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM certificates WHERE user_id=$1 ORDER BY id DESC LIMIT 1", uid)
        if existing:
            return dict(existing)
        async with conn.transaction():
            code = None
            for _ in range(20):
                candidate = "IQ-" + "".join(secrets.choice(CERT_CODE_ALPHABET) for _ in range(6))
                exists = await conn.fetchval("SELECT 1 FROM certificates WHERE code=$1", candidate)
                if not exists:
                    code = candidate
                    break
            if code is None:
                raise HTTPException(503, "CERTIFICATE_CODE_UNAVAILABLE")
            row = await conn.fetchrow("""
                INSERT INTO certificates(code,user_id,score,first_name,last_name)
                VALUES($1,$2,$3,$4,$5) RETURNING *
            """, code, uid, int(user["best_score"]), user["first_name"] or "", user["last_name"] or "")
            return dict(row)


async def find_certificate(code: str) -> dict | None:
    assert pool is not None
    code = code.strip().upper()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM certificates WHERE code=$1", code)
    return dict(row) if row else None


@app.get("/")
async def root():
    return {"status": "ok", "service": "IQ TEST BOT"}


@app.get("/health")
async def health():
    if pool is None:
        raise HTTPException(503, "DATABASE_NOT_READY")
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    path = WEBAPP_DIR / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


# The Mini App's index.html references /app/style.css and /app/app.js
# directly (not /static/...), so those exact paths must be served.
@app.get("/app/style.css")
async def app_style():
    return FileResponse(WEBAPP_DIR / "style.css", media_type="text/css")


@app.get("/app/app.js")
async def app_script():
    return FileResponse(WEBAPP_DIR / "app.js", media_type="application/javascript")


# Kept for any other static assets that might be added later.
app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")


@app.get("/api/config")
async def api_config(request: Request):
    user = await api_user(request)
    row = await get_user(int(user["id"]))
    iq_price = await get_price()
    battle_price = await get_battle_price()
    retry_price = await get_retry_price()

    assert pool is not None
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        online = await conn.fetchval("SELECT COUNT(*) FROM users WHERE last_seen > NOW() - INTERVAL '10 minutes'")

    return {
        "bot_username": BOT_USERNAME,
        "app_name": "IQ TEST BOT",
        "price_uzs": iq_price,
        "battle_price_uzs": battle_price,
        "retry_price_uzs": retry_price,
        "payment_mode": await get_payment_mode(),
        "question_count": QUESTIONS_COUNT,
        "language": (row["language"] if row else "") or "uz",
        "stats": {"total": int(total or 0), "online": int(online or 0)},
        "user": {
            "id": int(user["id"]),
            "firstName": row["first_name"] if row else "",
            "lastName": row["last_name"] if row else "",
            "username": row["username"] if row else "",
            "language": (row["language"] if row else "") or "uz",
        },
        "products": {
            "iq": {"price": iq_price, "free": True},
            "iq_retry": {"price": retry_price, "free": False},
            "eq_retry": {"price": retry_price, "free": False},
            "pq_retry": {"price": retry_price, "free": False},
            "battle": {"price": battle_price, "free": False},
        },
    }


@app.get("/api/stats/live")
async def api_stats_live(request: Request):
    await api_user(request)
    assert pool is not None
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        online = await conn.fetchval("SELECT COUNT(*) FROM users WHERE last_seen > NOW() - INTERVAL '10 minutes'")
    return {"total": int(total or 0), "online": int(online or 0)}


# Backward-compatible alias (some earlier builds call /api/counter).
@app.get("/api/counter")
async def api_counter(request: Request):
    return await api_stats_live(request)


@app.get("/api/me")
async def api_me(request: Request):
    user = await api_user(request)
    row = await get_user(int(user["id"]))
    return {"user": {"id": int(user["id"]), "first_name": row["first_name"], "last_name": row["last_name"],
                      "username": row["username"], "attempts": int(row["attempts"]), "best_score": row["best_score"]}}


@app.get("/api/access/iq")
async def api_access_iq(request: Request):
    user = await api_user(request)
    return await access_iq(int(user["id"]))


@app.post("/api/session/start")
async def api_session_start(request: Request):
    user = await api_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    language = body.get("language", "uz") if isinstance(body, dict) else "uz"
    if language not in {"uz", "ru", "en"}:
        language = "uz"
    battle_id = None
    try:
        battle_id = int(body.get("battle_id")) if isinstance(body, dict) and body.get("battle_id") else None
    except (TypeError, ValueError):
        battle_id = None
    row = await start_session(int(user["id"]), language, battle_id)
    answers = sanitize_answers(row["answers"])
    return {"index": int(row["current_index"]), "answers": answers,
            "elapsed": max(0, int((now_utc() - row["started_at"]).total_seconds())),
            "created": int(row["current_index"]) == 0,
            "session_id": str(int(user["id"])),
            "test_type": "iq",
            "battle_id": battle_id}


@app.post("/api/session/sync")
async def api_session_sync(request: Request):
    user = await api_user(request)
    try:
        body = await request.json()
        answers = body.get("answers", [])
    except Exception as exc:
        raise HTTPException(400, "INVALID_SYNC") from exc
    return await sync_answers(int(user["id"]), answers)


@app.post("/api/session/finish")
async def api_session_finish(request: Request):
    user = await api_user(request)
    result = await finish_session(int(user["id"]))
    battle_id = None
    try:
        body = await request.json()
        battle_id = int(body.get("battle_id")) if body.get("battle_id") else None
    except Exception:
        pass
    if battle_id:
        await finalize_battle(int(user["id"]), int(result["iq"]), battle_id)
    result["rank"] = await get_rank(int(user["id"]))
    return result


@app.post("/api/test/submit")
async def api_test_submit(request: Request):
    """Compatibility endpoint kept for older Mini App builds. Any
    client-provided score/answers for the IQ test are ignored; the server
    always recalculates from the synced session.
    """
    user = await api_user(request)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "INVALID_JSON") from exc

    test_type = str(body.get("test_type", "iq"))
    if test_type == "iq":
        answers = body.get("answers")
        if isinstance(answers, list) and answers:
            try:
                await sync_answers(int(user["id"]), answers)
            except HTTPException:
                pass
        result = await finish_session(int(user["id"]))
        battle_id = body.get("battle_id")
        if battle_id:
            try:
                await finalize_battle(int(user["id"]), int(result["iq"]), int(battle_id))
                result["battle_id"] = int(battle_id)
            except (TypeError, ValueError):
                pass
        result["rank"] = await get_rank(int(user["id"]))
        return result

    # EQ/PQ placeholder scoring — will be replaced by the real EQ/PQ module.
    answers = sanitize_answers(body.get("answers", []))
    if not answers:
        raise HTTPException(400, "ANSWERS_REQUIRED")
    score = round(sum(max(0, min(3, a)) for a in answers) / (len(answers) * 3) * 100)
    return {"score": score, "raw_score": score, "correct": 0, "total": len(answers), "test_type": test_type}


@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    user = await api_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    purpose = str(body.get("purpose") or body.get("product_code") or "retest")
    purpose = {"iq_retry": "retest"}.get(purpose, purpose)
    return await create_payment(int(user["id"]), purpose)


# Alias kept for older frontend builds that call /api/payment/start.
@app.post("/api/payment/start")
async def api_payment_start(request: Request):
    return await api_payment_create(request)


@app.get("/api/payment/{payment_id}")
async def api_payment_status(payment_id: int, request: Request):
    user = await api_user(request)
    return await payment_status(int(user["id"]), payment_id)


@app.get("/api/profile")
async def api_profile(request: Request):
    user = await api_user(request)
    row = await get_user(int(user["id"]))
    return {"first_name": row["first_name"], "last_name": row["last_name"], "attempts": int(row["attempts"]),
            "best_score": row["best_score"], "rank": await get_rank(int(user["id"]))}


@app.get("/api/ranking")
async def api_ranking(request: Request):
    await api_user(request)
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT first_name,username,best_score,best_time FROM users
            WHERE best_score IS NOT NULL ORDER BY best_score DESC,best_time ASC NULLS LAST,created_at ASC LIMIT 50
        """)
    return {"items": [{"first_name": r["first_name"], "username": r["username"], "best_score": r["best_score"], "best_time": r["best_time"]} for r in rows]}


@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    user = await api_user(request)
    return await create_battle(int(user["id"]))


@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    user = await api_user(request)
    try:
        body = await request.json()
        code = body.get("code", "")
    except Exception as exc:
        raise HTTPException(400, "INVALID_BATTLE_CODE") from exc
    return await join_battle(int(user["id"]), code)


@app.get("/api/battle/{battle_id}")
async def api_battle_status(battle_id: int, request: Request):
    user = await api_user(request)
    return await battle_status(int(user["id"]), battle_id)


@app.get("/api/battle")
async def api_my_battle(request: Request):
    user = await api_user(request)
    return await battle_status(int(user["id"]))


def load_font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_certificate(name: str, iq: int, code: str = "") -> bytes:
    w, h = 1400, 900
    img = Image.new("RGB", (w, h), "#080a14")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((35, 35, w - 35, h - 35), 36, outline="#8b6cff", width=4)
    d.rounded_rectangle((60, 60, w - 60, h - 60), 28, outline="#262b3d", width=2)

    def center(text, y, font, fill="#fff"):
        box = d.textbbox((0, 0), text, font=font)
        d.text(((w - box[2] + box[0]) / 2, y), text, font=font, fill=fill)

    center("IQ TEST BOT", 105, load_font(54, True), "#b9a8ff")
    center("SERTIFIKAT", 190, load_font(34, True), "#9fa8ba")
    center(name[:34] or "User", 280, load_font(48, True))
    center(str(iq), 380, load_font(130, True), "#ffffff")
    center(score_level_uz(iq), 520, load_font(28, True), "#c4b5fd")
    center("IQ-STYLE SCORE • PRODUCT ESTIMATE", 578, load_font(22, True), "#b9a8ff")
    center(now_utc().strftime("%Y-%m-%d"), 650, load_font(22), "#737c91")
    if code:
        center(code, 700, load_font(24, True), "#e5deff")
    out = BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


@app.post("/api/certificate/create")
async def api_certificate_create(request: Request):
    user = await api_user(request)
    cert = await get_or_create_certificate(int(user["id"]))
    if not cert:
        raise HTTPException(404, "NO_RESULT")
    return {"code": cert["code"], "score": cert["score"], "createdAt": cert["created_at"].isoformat()}


@app.get("/api/certificate")
async def api_certificate(request: Request):
    user = await api_user(request)
    cert = await get_or_create_certificate(int(user["id"]))
    if not cert:
        raise HTTPException(404, "NO_RESULT")
    name = f"{cert['first_name']} {cert['last_name']}".strip() or "User"
    data = make_certificate(name, int(cert["score"]), cert["code"])
    return Response(data, media_type="image/png", headers={"Content-Disposition": 'inline; filename="iq-test-certificate.png"'})


@app.get("/api/certificate/{code}")
async def api_certificate_verify(code: str):
    cert = await find_certificate(code)
    if not cert:
        raise HTTPException(404, "CERTIFICATE_NOT_FOUND")
    return {
        "code": cert["code"],
        "score": cert["score"],
        "name": f"{cert['first_name']} {cert['last_name']}".strip(),
        "date": cert["created_at"].strftime("%d.%m.%Y"),
    }


async def admin_chat_id() -> int | None:
    raw = await get_setting("admin_chat_id", "0")
    try:
        return int(raw) or None
    except ValueError:
        return None


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Kartalar", callback_data="adm_cards"), InlineKeyboardButton(text="💰 Narx", callback_data="adm_price")],
        [InlineKeyboardButton(text="⚙ To‘lov rejimi", callback_data="adm_mode"), InlineKeyboardButton(text="📋 To‘lovlar", callback_data="adm_payments")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
    ])


def card_keyboard(cards):
    rows = [[InlineKeyboardButton(text="➕ Karta qo‘shish", callback_data="adm_card_add")]]
    rows += [[InlineKeyboardButton(text=f"🗑 {c['card_number']} — {c['holder'] or '-'}", callback_data=f"adm_card_del:{c['id']}")] for c in cards]
    rows.append([InlineKeyboardButton(text="⬅ Admin", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1⃣ Birinchi bepul / keyingi pullik", callback_data=f"adm_mode:{PAYMENT_MODE_RETEST}")],
        [InlineKeyboardButton(text="2⃣ Test bepul / natija pullik", callback_data=f"adm_mode:{PAYMENT_MODE_RESULT}")],
        [InlineKeyboardButton(text="3⃣ Hammasi bepul", callback_data=f"adm_mode:{PAYMENT_MODE_FREE}")],
        [InlineKeyboardButton(text="⬅ Admin", callback_data="adm_home")],
    ])


async def admin_text() -> str:
    cards = await active_cards()
    return ("👑 <b>IQ TEST BOT ADMIN</b>\n\n"
            f"💰 IQ narxi: <b>{await get_price():,} so‘m</b>\n"
            f"⚔ Battle: <b>{await get_battle_price():,} so‘m / ishtirokchi</b>\n"
            f"⚙ Rejim: <b>{await get_payment_mode()}</b>\n"
            f"💳 Faol kartalar: <b>{len(cards)}</b>")


async def send_payment_instructions(message: Message, payment_id: int):
    assert pool is not None
    async with pool.acquire() as conn:
        p = await conn.fetchrow("SELECT id,amount,status FROM iq_payments WHERE id=$1 AND user_id=$2", payment_id, message.from_user.id)
    if not p or p["status"] != "pending":
        await message.answer("❌ To‘lov topilmadi yoki allaqachon yopilgan.")
        return
    cards = await active_cards()
    if not cards:
        await message.answer("❌ Hozircha to‘lov kartasi sozlanmagan. Admin bilan bog‘laning.")
        return
    lines = [f"💳 <b>To‘lov #{payment_id}</b>", f"💰 Summa: <b>{int(p['amount']):,} so‘m</b>", "", "<b>Karta:</b>"]
    for c in cards:
        lines.append(f"• <code>{c['card_number']}</code> — {c['holder']}")
    lines += ["", "To‘lovni amalga oshirgach, <b>chek/skrinshotni shu chatga yuboring</b>.", "Admin tasdiqlagach Mini App avtomatik davom etadi."]
    await message.answer("\n".join(lines), parse_mode="HTML")


async def notify_admin(payment_id: int, user_id: int, file_id: str):
    if bot is None:
        return
    chat_id = await admin_chat_id()
    if not chat_id:
        print("Admin chat is not registered. Open /admin first.")
        return
    user = await get_user(user_id)
    name = ((user["first_name"] or "") + " " + (user["last_name"] or "")).strip() if user else "User"
    assert pool is not None
    async with pool.acquire() as conn:
        p = await conn.fetchrow("SELECT amount,purpose FROM iq_payments WHERE id=$1", payment_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_ok:{payment_id}"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_no:{payment_id}")]])
    caption = f"💳 <b>Yangi to‘lov</b>\n\nID: <code>{payment_id}</code>\nUser: <b>{name}</b>\nUser ID: <code>{user_id}</code>\nSumma: <b>{int(p['amount']) if p else 0:,} so‘m</b>\nMaqsad: <b>{p['purpose'] if p else '-'}</b>"
    try:
        await bot.send_photo(chat_id, file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
    except Exception as exc:
        print("Admin notification error:", exc)


def bot_keyboard(admin: bool = False):
    rows = [
        [KeyboardButton(text="🧠 IQ · EQ · PQ testini ishlash", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton(text="📜 Sertifikatim"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="💰 Pul ishlash"), KeyboardButton(text="ℹ Narx va yordam")],
        [KeyboardButton(text="🌐 Til")],
    ]
    if admin:
        rows.append([KeyboardButton(text="👑 Admin")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


@dp.message(CommandStart())
async def command_start(message: Message):
    if not message.from_user:
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""

    referral_id = None
    if payload.startswith("ref_"):
        try:
            referral_id = int(payload[4:])
        except ValueError:
            referral_id = None

    await db_user({
        "id": message.from_user.id,
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
    }, referral_id)

    if payload.startswith("pay_"):
        try:
            await send_payment_instructions(message, int(payload[4:]))
            return
        except ValueError:
            pass

    row = await get_user(message.from_user.id)
    language = (row["language"] if row else "") or ""

    if language not in {"uz", "ru", "en"}:
        await message.answer(
            "🌐 <b>Tilni tanlang</b>\n\n"
            "🇺🇿 O‘zbekcha\n"
            "🇷🇺 Русский\n"
            "🇬🇧 English",
            reply_markup=language_keyboard(),
            parse_mode="HTML",
        )
        return

    await send_welcome(message, language)


def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
    ])


async def send_welcome(message: Message, language: str):
    name = message.from_user.first_name or "do‘st"
    await message.answer(
        f"👋 Salom, <b>{name}</b>!\n\n"
        "🧠 <b>IQ TEST BOT</b>\n"
        "IQ, EQ va prokrastinatsiya testlarini\n"
        "ishlang, natijangizni bilib oling va\n"
        "shaxsiy profilingizni oching.\n\n"
        "👇 Boshlash uchun tugmani bosing.",
        reply_markup=bot_keyboard(is_admin(message.from_user)),
        parse_mode="HTML",
    )


@dp.callback_query(lambda c: bool(c.data) and c.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.split(":", 1)[1]
    if lang not in {"uz", "ru", "en"}:
        await callback.answer("Noto‘g‘ri til.", show_alert=True)
        return

    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language=$1,updated_at=NOW(),last_seen=NOW() WHERE user_id=$2",
            lang,
            callback.from_user.id,
        )

    await callback.answer("Til saqlandi.")
    try:
        await callback.message.edit_text("✅ Til saqlandi.")
    except Exception:
        pass
    if callback.message:
        await callback.message.answer(
            "👇 Menyu:",
            reply_markup=bot_keyboard(is_admin(callback.from_user)),
        )


@dp.message(lambda m: m.text == "📜 Sertifikatim")
async def certificate_message(message: Message):
    if not message.from_user:
        return
    cert = await get_or_create_certificate(message.from_user.id)
    if not cert:
        await message.answer("📜 Hali IQ natijangiz yo‘q. Avval testni topshiring.")
        return
    name = f"{cert['first_name']} {cert['last_name']}".strip() or "User"
    data = make_certificate(name, int(cert["score"]), cert["code"])
    await message.answer_document(
        BufferedInputFile(data, filename="iq-test-certificate.png"),
        caption=(
            f"📜 <b>IQ TEST BOT sertifikati</b>\n"
            f"🧠 IQ-style Score: <b>{int(cert['score'])}</b>\n"
            f"🔑 Kod: <code>{cert['code']}</code>\n\n"
            "Ushbu kodni botga yuborib, sertifikatni istalgan vaqtda tekshirish mumkin."
        ),
        parse_mode="HTML",
    )


@dp.message(lambda m: m.text == "🏆 Reyting")
async def ranking_message(message: Message):
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT first_name,username,best_score FROM users
            WHERE best_score IS NOT NULL
            ORDER BY best_score DESC, best_time ASC NULLS LAST, created_at ASC
            LIMIT 10
        """)
    if not rows:
        await message.answer("🏆 Hali reytingda natijalar yo‘q.")
        return
    lines = ["🏆 <b>IQ TEST BOT — TOP 10</b>", ""]
    for i, r in enumerate(rows, 1):
        name = (r["first_name"] or "User").strip()
        lines.append(f"<b>{i}.</b> {name} — <b>{r['best_score']}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(lambda m: m.text == "ℹ Narx va yordam")
async def help_message(message: Message):
    await message.answer(
        f"ℹ <b>NARX VA YORDAM</b>\n\n"
        f"🧠 IQ test — <b>{await get_price():,} so‘m</b>\n"
        "🎭 EQ — IQ dan keyin ochiladi\n"
        "⏳ Prokrastinatsiya — EQ dan keyin ochiladi\n"
        "⭐ To‘liq tahlil — uchala testdan keyin\n"
        f"🔄 Qayta ishlash — <b>{await get_retry_price():,} so‘m</b>\n"
        f"⚔ Do‘st bilan Battle — <b>{await get_battle_price():,} so‘m / ishtirokchi</b>\n\n"
        "💳 To‘lov kartaga amalga oshiriladi. Chekni shu botga yuborasiz.\n"
        "⏱ Admin tasdiqlagach Mini App avtomatik davom etadi.\n\n"
        "👤 Qo‘llab-quvvatlash: @" + ADMIN_USERNAME,
        parse_mode="HTML",
    )


@dp.message(lambda m: m.text == "💰 Pul ishlash")
async def money_message(message: Message):
    me = await bot.get_me() if bot else None
    username = me.username if me else BOT_USERNAME
    if not username:
        await message.answer("❌ Bot username topilmadi.")
        return
    assert pool is not None
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE referred_by=$1",
            message.from_user.id,
        )
    link = f"https://t.me/{username}?start=ref_{message.from_user.id}"
    await message.answer(
        "💰 <b>PUL ISHLASH</b>\n\n"
        "Do‘stlaringizni IQ TEST BOT'ga taklif qiling.\n\n"
        f"👥 Taklif qilganlaringiz: <b>{int(count or 0)}</b>\n\n"
        f"🔗 <code>{link}</code>",
        parse_mode="HTML",
    )


@dp.message(lambda m: m.text == "🌐 Til")
async def language_message(message: Message):
    await message.answer(
        "🌐 <b>Tilni tanlang</b>",
        reply_markup=language_keyboard(),
        parse_mode="HTML",
    )


@dp.message(lambda m: m.text == "👑 Admin")
async def admin_button_message(message: Message):
    await admin_command(message)


@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user):
        await message.answer("⛔ Ruxsat yo‘q.")
        return
    await set_setting("admin_chat_id", str(message.from_user.id))
    await message.answer(await admin_text(), parse_mode="HTML", reply_markup=admin_keyboard())


@dp.callback_query(lambda c: c.data == "adm_home")
async def adm_home(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    await set_setting("admin_chat_id", str(c.from_user.id))
    await c.message.edit_text(await admin_text(), parse_mode="HTML", reply_markup=admin_keyboard()); await c.answer()


@dp.callback_query(lambda c: c.data == "adm_cards")
async def adm_cards(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    await c.message.edit_text("💳 <b>Faol kartalar</b>", parse_mode="HTML", reply_markup=card_keyboard(await active_cards())); await c.answer()


@dp.callback_query(lambda c: c.data == "adm_card_add")
async def adm_card_add(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    admin_state[c.from_user.id] = "card"
    await c.message.answer("💳 Format:\n<code>8600123456789012 | ISM FAMILIYA</code>", parse_mode="HTML"); await c.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("adm_card_del:"))
async def adm_card_del(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    card_id = int(c.data.split(":", 1)[1])
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute("UPDATE payment_cards SET active=FALSE WHERE id=$1", card_id)
    await c.answer("Karta o‘chirildi"); await c.message.edit_text("💳 <b>Faol kartalar</b>", parse_mode="HTML", reply_markup=card_keyboard(await active_cards()))


@dp.callback_query(lambda c: c.data == "adm_price")
async def adm_price(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    admin_state[c.from_user.id] = "price"
    await c.message.answer(f"💰 Yangi IQ narxini yuboring. Hozirgi: <b>{await get_price():,} so‘m</b>", parse_mode="HTML"); await c.answer()


@dp.callback_query(lambda c: c.data == "adm_mode")
async def adm_mode(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    await c.message.edit_text("⚙ <b>To‘lov rejimi</b>", parse_mode="HTML", reply_markup=mode_keyboard()); await c.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("adm_mode:"))
async def adm_mode_set(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    mode = c.data.split(":", 1)[1]
    if mode not in VALID_PAYMENT_MODES: return await c.answer("Noto‘g‘ri rejim", show_alert=True)
    await set_setting("payment_mode", mode); await c.answer("Saqlandi")
    await c.message.edit_text(await admin_text(), parse_mode="HTML", reply_markup=admin_keyboard())


@dp.callback_query(lambda c: c.data == "adm_payments")
async def adm_payments(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id,p.amount,p.purpose,p.status,p.created_at,u.first_name,u.username
            FROM iq_payments p JOIN users u ON u.user_id=p.user_id
            WHERE p.status='pending' ORDER BY p.id DESC LIMIT 30
        """)
    text = "📋 <b>Kutilayotgan to‘lovlar</b>\n\n" + ("\n".join(f"#{r['id']} • {r['amount']:,} • {r['first_name'] or '-'} • @{r['username'] or '-'}" for r in rows) if rows else "Hozircha yo‘q.")
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Admin", callback_data="adm_home")]])); await c.answer()


@dp.callback_query(lambda c: c.data == "adm_stats")
async def adm_stats(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    assert pool is not None
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        attempts = await conn.fetchval("SELECT COUNT(*) FROM iq_attempts")
        pending = await conn.fetchval("SELECT COUNT(*) FROM iq_payments WHERE status='pending'")
        approved = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM iq_payments WHERE status='approved'")
    await c.message.edit_text(f"📊 <b>Statistika</b>\n\n👥 Users: <b>{users}</b>\n🧠 IQ testlar: <b>{attempts}</b>\n⏳ Pending: <b>{pending}</b>\n💰 Approved: <b>{approved:,} so‘m</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Admin", callback_data="adm_home")]])); await c.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("pay_ok:"))
async def pay_ok(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    payment_id = int(c.data.split(":", 1)[1]); assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id,status,purpose FROM iq_payments WHERE id=$1 FOR UPDATE", payment_id)
        if not row: return await c.answer("To‘lov topilmadi", show_alert=True)
        await conn.execute("UPDATE iq_payments SET status='approved',reviewer_id=$2,reviewed_at=NOW() WHERE id=$1", payment_id, c.from_user.id)
        uid = int(row["user_id"])
    try:
        await bot.send_message(uid, "✅ <b>To‘lov tasdiqlandi.</b> Mini App'ga qayting.", parse_mode="HTML")
    except Exception: pass
    await c.answer("Tasdiqlandi")
    if c.message.caption:
        await c.message.edit_caption(caption=c.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")


@dp.callback_query(lambda c: c.data and c.data.startswith("pay_no:"))
async def pay_no(c: CallbackQuery):
    if not is_admin(c.from_user): return await c.answer("Ruxsat yo‘q", show_alert=True)
    payment_id = int(c.data.split(":", 1)[1]); assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM iq_payments WHERE id=$1", payment_id)
        if not row: return await c.answer("To‘lov topilmadi", show_alert=True)
        await conn.execute("UPDATE iq_payments SET status='rejected',reviewer_id=$2,reviewed_at=NOW() WHERE id=$1", payment_id, c.from_user.id)
        uid = int(row["user_id"])
    try: await bot.send_message(uid, "❌ <b>To‘lov rad etildi.</b>", parse_mode="HTML")
    except Exception: pass
    await c.answer("Rad etildi")
    if c.message.caption:
        await c.message.edit_caption(caption=c.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")


@dp.message(lambda m: m.from_user is not None and is_admin(m.from_user) and m.from_user.id in admin_state)
async def admin_input(message: Message):
    uid = message.from_user.id; mode = admin_state.get(uid); text = (message.text or "").strip()
    if mode == "price":
        try: price = int(text.replace(" ", "")); assert 0 <= price <= 100000000
        except Exception:
            await message.answer("❌ Faqat son yuboring."); return
        await set_setting("price_uzs", str(price)); admin_state.pop(uid, None); await message.answer("✅ Narx saqlandi.", reply_markup=admin_keyboard()); return
    if mode == "card":
        parts = [x.strip() for x in text.split("|", 1)]
        number = parts[0].replace(" ", "") if parts else ""; holder = parts[1] if len(parts) == 2 else ""
        if not number.isdigit() or not 8 <= len(number) <= 32 or not holder:
            await message.answer("❌ Format noto‘g‘ri.\n<code>8600123456789012 | ISM FAMILIYA</code>", parse_mode="HTML"); return
        assert pool is not None
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO payment_cards(card_number,holder) VALUES($1,$2)", number, holder)
        admin_state.pop(uid, None); await message.answer("✅ Karta qo‘shildi.", reply_markup=admin_keyboard())


@dp.message(lambda m: m.from_user is not None and m.photo is not None)
async def payment_proof(message: Message):
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id FROM iq_payments WHERE user_id=$1 AND status='pending' AND consumed=FALSE
            ORDER BY id DESC LIMIT 1
        """, message.from_user.id)
        if not row:
            return
        pid = int(row["id"]); fid = message.photo[-1].file_id
        await conn.execute("UPDATE iq_payments SET proof_file_id=$2,proof_message_id=$3 WHERE id=$1", pid, fid, message.message_id)
    await message.answer("✅ Chek qabul qilindi. Admin tekshiradi.")
    await notify_admin(pid, message.from_user.id, fid)


def looks_like_certificate_code(text: str) -> bool:
    text = text.strip().upper()
    if not text.startswith("IQ-"):
        return False
    tail = text[3:]
    return len(tail) == 6 and all(c in CERT_CODE_ALPHABET for c in tail)


@dp.message(lambda m: m.from_user is not None and m.text and looks_like_certificate_code(m.text)
            and m.from_user.id not in admin_state)
async def certificate_verify_message(message: Message):
    """Spec section 55: anyone can send a certificate code to the bot and
    get back a verification, without revealing which codes are "real"
    beyond what the DB confirms.
    """
    cert = await find_certificate(message.text or "")
    if not cert:
        await message.answer("❌ Bunday sertifikat topilmadi.")
        return
    name = f"{cert['first_name']} {cert['last_name']}".strip() or "Foydalanuvchi"
    await message.answer(
        "✅ <b>Sertifikat topildi</b>\n\n"
        f"👤 {name}\n"
        f"🧠 IQ-style Score: <b>{int(cert['score'])}</b>\n"
        f"📅 Sana: {cert['created_at'].strftime('%d.%m.%Y')}",
        parse_mode="HTML",
    )


async def configure_bot() -> None:
    assert bot is not None
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🧠 IQ TEST", web_app=WebAppInfo(url=WEBAPP_URL)))
    await bot.set_webhook(url=webhook_url(), secret_token=webhook_secret(), drop_pending_updates=False, allowed_updates=dp.resolve_used_update_types())
    info = await bot.get_webhook_info(); print("Webhook:", info.url)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if bot is None:
        raise HTTPException(503, "BOT_NOT_READY")
    if not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), webhook_secret()):
        raise HTTPException(403, "FORBIDDEN")
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as exc:
        print("Webhook error:", repr(exc))
        raise HTTPException(500, "WEBHOOK_ERROR") from exc


async def run_web():
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info"))
    await server.serve()


async def main():
    global bot, BOT_USERNAME
    await init_db()
    bot = Bot(BOT_TOKEN)
    me = await bot.get_me(); BOT_USERNAME = me.username or ""
    print(f"Bot started: @{BOT_USERNAME}")
    await configure_bot()
    try:
        await run_web()
    finally:
        try: await bot.delete_webhook(drop_pending_updates=False)
        except Exception as exc: print("Webhook cleanup:", exc)
        await bot.session.close()
        if pool is not None: await pool.close()


if __name__ == "__main__":
    asyncio.run(main())