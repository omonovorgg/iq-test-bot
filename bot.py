import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    Update,
    CallbackQuery,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont


BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ZAKO_URL = os.environ.get("ZAKO_URL", "https://t.me/zako_tbot")
WEBAPP_URL = os.environ.get("WEBAPP_URL")
PORT = int(os.environ.get("PORT", "10000"))

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
    raise RuntimeError(f"webapp directory not found: {WEBAPP_DIR}")

QUESTIONS_COUNT = 16
CORRECT_ANSWERS = (1, 1, 2, 0, 2, 2, 0, 0, 1, 2, 2, 1, 2, 1, 1, 2)
WEIGHTS = (1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5)
MAX_RAW = sum(WEIGHTS)

pool: asyncpg.Pool | None = None
bot: Bot | None = None
BOT_USERNAME = ""
dp = Dispatcher()
app = FastAPI(title="IQ TEST BOT")
app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")


def clean_db_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in {"sslmode", "channel_binding"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(query), parts.fragment))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def webhook_url() -> str:
    parts = urlsplit(WEBAPP_URL)
    return f"{parts.scheme}://{parts.netloc}/telegram/webhook"


WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()

# Admin: username-based fallback plus optional numeric ID env.
# Set ADMIN_USER_ID later if you want an ID-only lock; no env change is required now.
ADMIN_USERNAME = "omono_v"
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0") or 0)

PAYMENT_MODE_RETEST = "first_free_retest_paid"
PAYMENT_MODE_RESULT = "result_paid"
PAYMENT_MODE_FREE = "all_free"
VALID_PAYMENT_MODES = {PAYMENT_MODE_RETEST, PAYMENT_MODE_RESULT, PAYMENT_MODE_FREE}

admin_state: dict[int, str] = {}
admin_temp: dict[int, dict] = {}


async def init_db() -> None:
    global pool
    pool = await asyncpg.create_pool(
        clean_db_url(DATABASE_URL),
        min_size=1,
        max_size=5,
        ssl="require",
        command_timeout=30,
    )
    async with pool.acquire() as conn:
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
                cert_claimed BOOLEAN NOT NULL DEFAULT FALSE,
                referred_by BIGINT,
                referral_counted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                current_index INTEGER NOT NULL DEFAULT 0,
                answers JSONB NOT NULL DEFAULT '[]'::jsonb,
                raw_score INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                language TEXT NOT NULL DEFAULT 'uz',
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                result_iq INTEGER,
                result_raw INTEGER,
                result_correct INTEGER,
                result_elapsed INTEGER,
                finished_at TIMESTAMPTZ
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                raw_score INTEGER NOT NULL,
                iq_score INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                elapsed INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT '';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'uz';
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

            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS current_index INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS answers JSONB NOT NULL DEFAULT '[]'::jsonb;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS raw_score INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS correct INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'uz';
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW();
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS completed BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_iq INTEGER;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_raw INTEGER;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_correct INTEGER;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_elapsed INTEGER;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS payment_cards (
                id BIGSERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS payments (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                amount INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                proof_file_id TEXT,
                proof_message_id BIGINT,
                reviewer_id BIGINT,
                consumed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            );

            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_unlocked BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS result_counted BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS payment_id BIGINT;
        """)

        await conn.execute("""
            INSERT INTO app_settings (key, value)
            VALUES
                ('price_uzs', '3000'),
                ('payment_mode', 'first_free_retest_paid')
            ON CONFLICT (key) DO NOTHING;
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_best_score
            ON users(best_score DESC NULLS LAST);
            CREATE INDEX IF NOT EXISTS idx_attempts_user_id
            ON attempts(user_id);
        """)
    print("Database initialized successfully.")


async def upsert_user(tg_user: dict, referral_id: int | None = None) -> None:
    assert pool is not None
    uid = int(tg_user["id"])
    if referral_id == uid:
        referral_id = None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, first_name, last_name, username, referred_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                username = EXCLUDED.username,
                referred_by = COALESCE(users.referred_by, EXCLUDED.referred_by),
                updated_at = NOW()
        """, uid, tg_user.get("first_name", "") or "",
             tg_user.get("last_name", "") or "",
             tg_user.get("username", "") or "", referral_id)


async def get_user(uid: int):
    assert pool is not None
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def count_referral(user_id: int) -> None:
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT referred_by, referral_counted FROM users
                WHERE user_id=$1 FOR UPDATE
            """, user_id)
            if not row or row["referred_by"] is None or row["referred_by"] == user_id:
                return
            if row["referral_counted"]:
                return
            exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id=$1", row["referred_by"]
            )
            if not exists:
                return
            await conn.execute("""
                UPDATE users SET referral_counted=TRUE, updated_at=NOW()
                WHERE user_id=$1
            """, user_id)
            await conn.execute("""
                UPDATE users SET referrals=referrals+1, updated_at=NOW()
                WHERE user_id=$1
            """, row["referred_by"])


def sanitize_answers(raw_answers) -> list[int]:
    if isinstance(raw_answers, str):
        try:
            raw_answers = json.loads(raw_answers)
        except Exception:
            raw_answers = []
    if not isinstance(raw_answers, list):
        return []
    clean: list[int] = []
    for value in raw_answers:
        try:
            value = int(value)
        except (TypeError, ValueError):
            break
        if not 0 <= value < 4:
            break
        clean.append(value)
        if len(clean) >= QUESTIONS_COUNT:
            break
    return clean


def score_answers(answers: list[int]) -> tuple[int, int]:
    correct = sum(
        1 for i, answer in enumerate(answers)
        if i < QUESTIONS_COUNT and answer == CORRECT_ANSWERS[i]
    )
    raw = sum(
        WEIGHTS[i] for i, answer in enumerate(answers)
        if i < QUESTIONS_COUNT and answer == CORRECT_ANSWERS[i]
    )
    return raw, correct


async def repair_session(conn, row):
    answers = sanitize_answers(row["answers"])
    raw, correct = score_answers(answers)
    expected_index = len(answers)
    changed = (
        int(row["current_index"]) != expected_index
        or int(row["raw_score"] or 0) != raw
        or int(row["correct"] or 0) != correct
        or list(row["answers"] or []) != answers
    )
    if changed:
        row = await conn.fetchrow("""
            UPDATE test_sessions
            SET current_index=$2,
                answers=$3::jsonb,
                raw_score=$4,
                correct=$5,
                last_activity=NOW()
            WHERE user_id=$1
            RETURNING *
        """, row["user_id"], expected_index, json.dumps(answers), raw, correct)
        print(
            f"Session repaired: user={row['user_id']} "
            f"index={expected_index} answers={len(answers)}"
        )
    return row


async def get_setting(key: str, default: str = "") -> str:
    assert pool is not None
    async with pool.acquire() as conn:
        value = await conn.fetchval("SELECT value FROM app_settings WHERE key=$1", key)
        return str(value) if value is not None else default


async def set_setting(key: str, value: str) -> None:
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO app_settings(key, value, updated_at)
            VALUES($1, $2, NOW())
            ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
        """, key, str(value))


async def get_price() -> int:
    raw = await get_setting("price_uzs", "3000")
    try:
        value = int(raw)
    except ValueError:
        value = 3000
    return max(0, value)


async def get_payment_mode() -> str:
    mode = await get_setting("payment_mode", PAYMENT_MODE_RETEST)
    return mode if mode in VALID_PAYMENT_MODES else PAYMENT_MODE_RETEST


async def active_cards() -> list[dict]:
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, card_number, holder
            FROM payment_cards
            WHERE active=TRUE
            ORDER BY id
        """)
    return [dict(r) for r in rows]


def is_admin_user(user) -> bool:
    if not user:
        return False
    if ADMIN_USER_ID and int(user.id) == ADMIN_USER_ID:
        return True
    return (user.username or "").lower() == ADMIN_USERNAME.lower()


async def remember_admin_chat(user_id: int) -> None:
    await set_setting("admin_chat_id", str(user_id))


async def get_admin_chat_id() -> int | None:
    raw = await get_setting("admin_chat_id", "0")
    try:
        value = int(raw)
    except ValueError:
        return None
    return value or None


def payment_mode_label(mode: str) -> str:
    return {
        PAYMENT_MODE_RETEST: "1️⃣ Birinchi test bepul → keyingi testlar pullik",
        PAYMENT_MODE_RESULT: "2️⃣ Test bepul → natijani ko‘rish pullik",
        PAYMENT_MODE_FREE: "3️⃣ Hammasi bepul",
    }.get(mode, mode)


async def create_payment(uid: int, purpose: str) -> dict:
    if purpose not in {"retest", "result"}:
        raise HTTPException(
            status_code=400,
            detail="INVALID_PAYMENT_PURPOSE"
        )

    assert pool is not None

    price = await get_price()

    if price <= 0:
        raise HTTPException(
            status_code=400,
            detail="PAYMENTS_DISABLED"
        )

    cards = await active_cards()

    if not cards:
        raise HTTPException(
            status_code=503,
            detail="NO_PAYMENT_CARD"
        )

    async with pool.acquire() as conn:
        async with conn.transaction():

            # -------------------------------------------------
            # 1. AVVAL TASDIQLANGAN, LEKIN HALI ISHLATILMAGAN
            #    TO‘LOVNI QIDIRAMIZ.
            #
            #    Foydalanuvchi Mini App'ni yopib qayta ochsa,
            #    yangi payment yaratmaymiz.
            # -------------------------------------------------

            approved = await conn.fetchrow("""
                SELECT id, amount, purpose, status, consumed
                FROM payments
                WHERE user_id=$1
                  AND purpose=$2
                  AND status='approved'
                  AND consumed=FALSE
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
            """, uid, purpose)

            if approved:
                payment_id = int(approved["id"])
                amount = int(approved["amount"])

                return {
                    "payment_id": payment_id,
                    "amount": amount,
                    "cards": cards,
                    "status": "approved",
                    "already_approved": True,
                }

            # -------------------------------------------------
            # 2. PENDING PAYMENT BOR BO‘LSA, SHUNI QAYTARAMIZ.
            #    Yangi payment yaratmaymiz.
            # -------------------------------------------------

            existing = await conn.fetchrow("""
                SELECT id, amount, purpose, status
                FROM payments
                WHERE user_id=$1
                  AND purpose=$2
                  AND status='pending'
                  AND consumed=FALSE
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
            """, uid, purpose)

            if existing:
                payment_id = int(existing["id"])
                amount = int(existing["amount"])

                return {
                    "payment_id": payment_id,
                    "amount": amount,
                    "cards": cards,
                    "status": "pending",
                    "already_approved": False,
                }

            # -------------------------------------------------
            # 3. UMUMAN PAYMENT YO‘Q BO‘LSA, YANGI YARATAMIZ.
            # -------------------------------------------------

            row = await conn.fetchrow("""
                INSERT INTO payments(
                    user_id,
                    amount,
                    purpose
                )
                VALUES($1,$2,$3)
                RETURNING id, amount
            """, uid, price, purpose)

            payment_id = int(row["id"])
            amount = int(row["amount"])

    return {
        "payment_id": payment_id,
        "amount": amount,
        "cards": cards,
        "status": "pending",
        "already_approved": False,
    }

async def payment_status(uid: int, payment_id: int) -> dict:
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, amount, purpose, status, consumed
            FROM payments WHERE id=$1 AND user_id=$2
        """, payment_id, uid)
    if not row:
        raise HTTPException(status_code=404, detail="PAYMENT_NOT_FOUND")
    return {"payment_id": int(row["id"]), "amount": int(row["amount"]),
            "purpose": row["purpose"], "status": row["status"],
            "consumed": bool(row["consumed"])}


async def consume_approved_retest_payment(conn, uid: int) -> int | None:
    row = await conn.fetchrow("""
        SELECT id, amount FROM payments
        WHERE user_id=$1 AND purpose='retest' AND status='approved' AND consumed=FALSE
        ORDER BY id ASC LIMIT 1 FOR UPDATE
    """, uid)
    if not row:
        return None
    await conn.execute("UPDATE payments SET consumed=TRUE WHERE id=$1", row["id"])
    return int(row["id"])


async def unlock_result_payment(conn, uid: int, payment_id: int) -> None:
    payment = await conn.fetchrow("""
        SELECT * FROM payments WHERE id=$1 AND user_id=$2 FOR UPDATE
    """, payment_id, uid)
    if not payment or payment["status"] != "approved":
        raise HTTPException(status_code=409, detail="PAYMENT_NOT_APPROVED")
    session = await conn.fetchrow("""
        SELECT * FROM test_sessions
        WHERE user_id=$1 AND completed=TRUE AND result_counted=FALSE
        ORDER BY finished_at DESC NULLS LAST LIMIT 1 FOR UPDATE
    """, uid)
    if not session:
        raise HTTPException(status_code=409, detail="RESULT_NOT_FOUND")
    if payment["consumed"]:
        return
    iq = int(session["result_iq"])
    raw = int(session["result_raw"])
    correct = int(session["result_correct"])
    elapsed = int(session["result_elapsed"])
    await conn.execute("""
        INSERT INTO attempts(user_id, raw_score, iq_score, correct, elapsed)
        VALUES($1,$2,$3,$4,$5)
    """, uid, raw, iq, correct, elapsed)
    await conn.execute("""
        UPDATE users SET
            attempts=attempts+1,
            best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
            best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
            best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $4<best_time)) THEN $4 ELSE best_time END,
            updated_at=NOW() WHERE user_id=$1
    """, uid, iq, raw, elapsed)
    await conn.execute("""
        UPDATE test_sessions SET result_unlocked=TRUE, result_counted=TRUE, payment_id=$2, last_activity=NOW()
        WHERE user_id=$1 AND completed=TRUE AND result_counted=FALSE
    """, uid, payment_id)
    await conn.execute("UPDATE payments SET consumed=TRUE WHERE id=$1", payment_id)


async def create_or_get_session(uid: int, language: str):
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT attempts FROM users WHERE user_id=$1 FOR UPDATE", uid
            )
            if not user:
                raise HTTPException(status_code=401, detail="USER_NOT_FOUND")

            active = await conn.fetchrow("""
                SELECT * FROM test_sessions
                WHERE user_id=$1 AND completed=FALSE
                FOR UPDATE
            """, uid)

            if active:
                active = await repair_session(conn, active)
                answer_count = len(sanitize_answers(active["answers"]))

                # A session with all 16 answers is NOT an active quiz anymore.
                # Older versions could leave completed=FALSE with 16 answers,
                # which made /api/session/start return index=16 forever.
                if answer_count >= QUESTIONS_COUNT:
                    raw, correct = score_answers(sanitize_answers(active["answers"]))
                    iq = calculate_iq(raw)
                    elapsed = max(0, round((now_utc() - active["started_at"]).total_seconds()))
                    mode = await get_payment_mode()

                    if mode == PAYMENT_MODE_RESULT:
                        # Preserve the completed result until the result payment
                        # is approved. finish_session() / the frontend can then
                        # trigger the payment flow normally.
                        active = await conn.fetchrow("""
                            UPDATE test_sessions
                            SET completed=TRUE, current_index=$2, raw_score=$3,
                                correct=$4, result_iq=$5, result_raw=$3,
                                result_correct=$4, result_elapsed=$6,
                                result_unlocked=FALSE, result_counted=FALSE,
                                finished_at=COALESCE(finished_at, NOW()),
                                last_activity=NOW()
                            WHERE user_id=$1
                            RETURNING *
                        """, uid, QUESTIONS_COUNT, raw, correct, iq, elapsed)
                        print(f"Session finalized for result payment: user={uid}")
                        return active, False

                    # For free-result mode and the normal first-free/retest-paid
                    # mode, a fully answered legacy session is finalized exactly
                    # once, then removed so the next /start can create a new quiz.
                    if not bool(active["result_counted"]):
                        await conn.execute("""
                            INSERT INTO attempts(user_id, raw_score, iq_score, correct, elapsed)
                            VALUES($1,$2,$3,$4,$5)
                        """, uid, raw, iq, correct, elapsed)
                        await conn.execute("""
                            UPDATE users SET
                                attempts=attempts+1,
                                best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
                                best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
                                best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $4<best_time)) THEN $4 ELSE best_time END,
                                updated_at=NOW()
                            WHERE user_id=$1
                        """, uid, iq, raw, elapsed)

                    await conn.execute("DELETE FROM test_sessions WHERE user_id=$1", uid)
                    # Refresh the locked user row because attempts may have just
                    # changed and the payment decision below depends on it.
                    user = await conn.fetchrow(
                        "SELECT attempts FROM users WHERE user_id=$1 FOR UPDATE", uid
                    )
                else:
                    age = (now_utc() - active["last_activity"]).total_seconds()
                    if age <= 7200:
                        return active, False
                    await conn.execute(
                        "DELETE FROM test_sessions WHERE user_id=$1", uid
                    )

            mode = await get_payment_mode()
            payment_id = None
            if mode == PAYMENT_MODE_RETEST and int(user["attempts"]) >= 1:
                payment_id = await consume_approved_retest_payment(conn, uid)
                if payment_id is None:
                    price = await get_price()
                    raise HTTPException(
                        status_code=402,
                        detail="PAID_RETEST",
                        headers={"X-Payment-Price": str(price)},
                    )

            row = await conn.fetchrow("""
    INSERT INTO test_sessions (
        user_id,
        language,
        started_at,
        last_activity,
        payment_id
    )
    VALUES ($1, $2, NOW(), NOW(), $3)
    ON CONFLICT (user_id)
    DO UPDATE SET
        last_activity = NOW()
    RETURNING *
""", uid, language, payment_id)

return row, True


async def save_answer(uid: int, question_index: int, selected: int):
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT * FROM test_sessions
                WHERE user_id=$1 AND completed=FALSE
                FOR UPDATE
            """, uid)
            if not row:
                raise HTTPException(status_code=409, detail="SESSION_EXPIRED")

            row = await repair_session(conn, row)
            current_index = int(row["current_index"])

            if question_index != current_index:
                raise HTTPException(status_code=409, detail="OUT_OF_ORDER")
            if not 0 <= selected < 4:
                raise HTTPException(status_code=400, detail="INVALID_ANSWER")
            if current_index >= QUESTIONS_COUNT:
                raise HTTPException(status_code=409, detail="SESSION_COMPLETE")

            answers = sanitize_answers(row["answers"])
            if len(answers) != current_index:
                raise HTTPException(status_code=409, detail="SESSION_CORRUPTED")

            answers.append(selected)
            raw, correct = score_answers(answers)

            await conn.execute("""
                UPDATE test_sessions
                SET current_index=$2, answers=$3::jsonb,
                    raw_score=$4, correct=$5, last_activity=NOW()
                WHERE user_id=$1
            """, uid, current_index + 1, json.dumps(answers), raw, correct)
            return current_index + 1


def calculate_iq(raw: int) -> int:
    raw = max(0, min(int(raw), MAX_RAW))
    return round(40 + (raw / MAX_RAW) * 120)


async def finish_session(uid: int):
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM test_sessions WHERE user_id=$1 FOR UPDATE", uid
            )
            if not row:
                raise HTTPException(status_code=409, detail="SESSION_EXPIRED")

            if row["completed"]:
                if not bool(row["result_counted"]):
                    mode = await get_payment_mode()
                    if mode == PAYMENT_MODE_RESULT:
                        payment_id = row["payment_id"]
                        if payment_id:
                            payment = await conn.fetchrow("SELECT status, consumed FROM payments WHERE id=$1 AND user_id=$2", payment_id, uid)
                            if payment and payment["status"] == "approved" and not payment["consumed"]:
                                await unlock_result_payment(conn, uid, int(payment_id))
                            else:
                                raise HTTPException(status_code=402, detail="PAYMENT_REQUIRED")
                        else:
                            price = await get_price()
                            cards = await active_cards()
                            if not cards:
                                raise HTTPException(status_code=503, detail="NO_PAYMENT_CARD")
                            payment = await conn.fetchrow("""
                                INSERT INTO payments(user_id, amount, purpose) VALUES($1,$2,'result') RETURNING id
                            """, uid, price)
                            payment_id = int(payment["id"])
                            await conn.execute("UPDATE test_sessions SET payment_id=$2 WHERE user_id=$1", uid, payment_id)
                            raise HTTPException(status_code=402, detail="PAYMENT_REQUIRED")
                return (int(row["result_iq"]), int(row["result_raw"]), int(row["result_correct"]), int(row["result_elapsed"]))

            row = await repair_session(conn, row)
            answers = sanitize_answers(row["answers"])
            if len(answers) != QUESTIONS_COUNT or int(row["current_index"]) != QUESTIONS_COUNT:
                raise HTTPException(status_code=409, detail="INCOMPLETE")

            raw, correct = score_answers(answers)
            iq = calculate_iq(raw)
            elapsed = max(0, round((now_utc() - row["started_at"]).total_seconds()))
            mode = await get_payment_mode()

            if mode == PAYMENT_MODE_RESULT:
                price = await get_price()
                cards = await active_cards()
                if not cards:
                    raise HTTPException(status_code=503, detail="NO_PAYMENT_CARD")
                payment = await conn.fetchrow("""
                    INSERT INTO payments(user_id, amount, purpose) VALUES($1,$2,'result') RETURNING id
                """, uid, price)
                payment_id = int(payment["id"])
                await conn.execute("""
                    UPDATE test_sessions SET completed=TRUE, result_iq=$2, result_raw=$3, result_correct=$4, result_elapsed=$5, payment_id=$6, result_unlocked=FALSE, result_counted=FALSE, finished_at=NOW(), last_activity=NOW()
                    WHERE user_id=$1
                """, uid, iq, raw, correct, elapsed, payment_id)
                raise HTTPException(status_code=402, detail="PAYMENT_REQUIRED")

            await conn.execute("""
                INSERT INTO attempts (user_id, raw_score, iq_score, correct, elapsed)
                VALUES ($1, $2, $3, $4, $5)
            """, uid, raw, iq, correct, elapsed)

            await conn.execute("""
                UPDATE users SET
                    attempts=attempts+1,
                    best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
                    best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
                    best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $4<best_time)) THEN $4 ELSE best_time END,
                    updated_at=NOW() WHERE user_id=$1
            """, uid, iq, raw, elapsed)

            await conn.execute("""
                UPDATE test_sessions SET completed=TRUE, result_iq=$2, result_raw=$3, result_correct=$4, result_elapsed=$5, result_unlocked=TRUE, result_counted=TRUE, finished_at=NOW(), last_activity=NOW()
                WHERE user_id=$1
            """, uid, iq, raw, correct, elapsed)
            return iq, raw, correct, elapsed


async def get_rank(uid: int):
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT best_score,best_time FROM users WHERE user_id=$1", uid
        )
        if not row or row["best_score"] is None:
            return None
        rank = await conn.fetchval("""
            SELECT COUNT(*)+1 FROM users
            WHERE best_score IS NOT NULL AND (
                best_score>$1 OR (
                    best_score=$1 AND COALESCE(best_time,2147483647)
                    < COALESCE($2::INTEGER,2147483647)
                )
            )
        """, row["best_score"], row["best_time"])
        return int(rank)


def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=401, detail="INVALID_INIT_DATA")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            raise ValueError("hash missing")
        auth_date = int(pairs.get("auth_date", "0"))
        current_time = int(now_utc().timestamp())
        if auth_date <= 0 or current_time - auth_date > 86400:
            raise ValueError("auth date invalid or expired")
        if auth_date - current_time > 60:
            raise ValueError("future auth date")
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        calculated = hmac.new(
            secret, check.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            raise ValueError("hash mismatch")
        raw_user = pairs.get("user")
        if not raw_user:
            raise ValueError("user missing")
        user = json.loads(raw_user)
        if not isinstance(user, dict) or not user.get("id"):
            raise ValueError("invalid user")
        return user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="INVALID_INIT_DATA") from exc


async def api_user(request: Request) -> dict:
    return validate_init_data(
        request.headers.get("X-Telegram-Init-Data", "")
    )


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "IQ TEST BOT"}


@app.get("/health")
async def health():
    if pool is None:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_READY")
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/app")
async def app_page():
    index_path = WEBAPP_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    payment_script = '<script src="/static/payment.js?v=20260918-1"></script>'
    if "/static/payment.js" not in html:
        if "</body>" in html:
            html = html.replace("</body>", payment_script + "</body>")
        else:
            html += payment_script
    return HTMLResponse(content=html)


@app.get("/api/config")
async def api_config():
    return {
        "bot_username": BOT_USERNAME,
        "zako_url": ZAKO_URL,
        "price_uzs": await get_price(),
        "payment_mode": await get_payment_mode(),
    }


@app.post("/api/session/start")
async def api_start(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    language = body.get("language", "uz")
    if language not in {"uz", "ru", "en"}:
        language = "uz"

    await upsert_user(tg_user)
    await count_referral(uid)
    row, created = await create_or_get_session(uid, language)
    elapsed = max(0, round((now_utc() - row["started_at"]).total_seconds()))
    user = await get_user(uid)
    return {
        "user_id": uid,
        "created": created,
        "index": int(row["current_index"]),
        "answers": list(row["answers"] or []),
        "elapsed": elapsed,
        "attempts": int(user["attempts"]),
        "price_uzs": await get_price(),
        "payment_mode": await get_payment_mode(),
    }


@app.post("/api/session/answer")
async def api_answer(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
        index = int(body.get("index", -1))
        selected = int(body.get("selected", -1))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="INVALID_ANSWER") from exc
    new_index = await save_answer(uid, index, selected)
    return {"ok": True, "index": new_index}


@app.post("/api/session/finish")
async def api_finish(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    iq, raw, correct, elapsed = await finish_session(uid)
    return {
        "iq": iq, "raw": raw, "correct": correct,
        "elapsed": elapsed, "rank": await get_rank(uid)
    }


@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    purpose = body.get("purpose", "retest")
    result = await create_payment(uid, purpose)
    return result


@app.get("/api/payment/{payment_id}")
async def api_payment_get(payment_id: int, request: Request):
    tg_user = await api_user(request)
    return await payment_status(int(tg_user["id"]), payment_id)


@app.post("/api/payment/result/unlock")
async def api_payment_result_unlock(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
        payment_id = int(body.get("payment_id"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="INVALID_PAYMENT") from exc
    assert pool is not None
    async with pool.acquire() as conn:
        async with conn.transaction():
            await unlock_result_payment(conn, uid, payment_id)
            row = await conn.fetchrow("SELECT result_iq,result_raw,result_correct,result_elapsed FROM test_sessions WHERE user_id=$1 AND completed=TRUE ORDER BY finished_at DESC NULLS LAST LIMIT 1", uid)
    return {"ok": True, "iq": int(row["result_iq"]), "raw": int(row["result_raw"]), "correct": int(row["result_correct"]), "elapsed": int(row["result_elapsed"]), "rank": await get_rank(uid)}


@app.get("/api/profile")
async def api_profile(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    await upsert_user(tg_user)
    user = await get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    return {
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "username": user["username"],
        "attempts": int(user["attempts"]),
        "best_score": user["best_score"],
        "best_time": user["best_time"],
        "referrals": int(user["referrals"]),
        "rank": await get_rank(uid),
    }


@app.get("/api/ranking")
async def api_ranking(request: Request):
    await api_user(request)
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT first_name,username,best_score,best_time
            FROM users
            WHERE best_score IS NOT NULL
            ORDER BY best_score DESC,best_time ASC NULLS LAST,created_at ASC
            LIMIT 50
        """)
    return {"items": [
        {
            "first_name": r["first_name"],
            "username": r["username"],
            "best_score": r["best_score"],
            "best_time": r["best_time"],
        } for r in rows
    ]}


def load_font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_certificate_png(name: str, iq: int) -> bytes:
    width, height = 1400, 900
    image = Image.new("RGB", (width, height), "#0b0d16")
    draw = ImageDraw.Draw(image)

    def center(text: str, y: int, font, fill="#ffffff"):
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2]-box[0])) / 2, y), text,
                  font=font, fill=fill)

    draw.rounded_rectangle((35,35,width-35,height-35),
                           radius=36, outline="#8b6cff", width=4)
    draw.rounded_rectangle((58,58,width-58,height-58),
                           radius=28, outline="#2b3040", width=2)
    center("ZAKO IQ", 115, load_font(64, True), "#b8a8ff")
    center("IQ TEST CERTIFICATE", 215, load_font(30, True), "#aeb5c6")
    center(str(iq), 290, load_font(150, True))
    center("IQ SCORE", 470, load_font(30, True), "#b8a8ff")
    center(name[:32] or "User", 545, load_font(46, True))
    center("ZAKO IQ testining taxminiy natijasi", 640, load_font(25), "#aeb5c6")
    center(now_utc().strftime("%Y-%m-%d"), 700, load_font(22), "#777f91")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


@app.get("/api/certificate")
async def api_certificate(request: Request):
    tg_user = await api_user(request)
    uid = int(tg_user["id"])
    user = await get_user(uid)
    if not user or user["best_score"] is None:
        raise HTTPException(status_code=404, detail="NO_RESULT")
    if int(user["referrals"]) < 2:
        raise HTTPException(status_code=403, detail="REFERRALS_REQUIRED")
    if not user["cert_claimed"]:
        assert pool is not None
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET cert_claimed=TRUE,updated_at=NOW() WHERE user_id=$1",
                uid,
            )
    data = make_certificate_png(user["first_name"] or "User",
                                int(user["best_score"]))
    return Response(
        content=data,
        media_type="image/png",
        headers={"Content-Disposition":
                 'inline; filename="zako-iq-certificate.png"'},
    )


def admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Kartalar", callback_data="adm_cards")],
        [InlineKeyboardButton(text="💰 Narxni o‘zgartirish", callback_data="adm_price")],
        [InlineKeyboardButton(text="⚙️ To‘lov rejimi", callback_data="adm_mode")],
        [InlineKeyboardButton(text="📋 To‘lovlar", callback_data="adm_payments")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
    ])


def admin_cards_keyboard(cards):
    rows = [[InlineKeyboardButton(text="➕ Karta qo‘shish", callback_data="adm_card_add")]]
    for card in cards:
        rows.append([InlineKeyboardButton(text=f"🗑 {card['card_number']} — {card['holder'] or 'Ism yo‘q'}", callback_data=f"adm_card_del:{card['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Birinchi bepul / keyingi pullik", callback_data="adm_mode:first_free_retest_paid")],
        [InlineKeyboardButton(text="2️⃣ Test bepul / natija pullik", callback_data="adm_mode:result_paid")],
        [InlineKeyboardButton(text="3️⃣ Hammasi bepul", callback_data="adm_mode:all_free")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm_home")],
    ])


async def admin_text() -> str:
    price = await get_price()
    mode = await get_payment_mode()
    cards = await active_cards()
    return (
        "👑 <b>IQ TEST ADMIN PANEL</b>\n\n"
        f"💰 Narx: <b>{price:,} so‘m</b>\n"
        f"⚙️ Rejim: <b>{payment_mode_label(mode)}</b>\n"
        f"💳 Faol kartalar: <b>{len(cards)}</b>\n\n"
        "Kerakli bo‘limni tanlang."
    )


async def send_payment_instructions(message: Message, payment_id: int):
    assert pool is not None
    async with pool.acquire() as conn:
        payment = await conn.fetchrow("""
            SELECT id, amount, purpose, status, user_id
            FROM payments WHERE id=$1 AND user_id=$2
        """, payment_id, message.from_user.id)
    if not payment or payment["status"] != "pending":
        await message.answer("❌ Bu to‘lov topilmadi yoki allaqachon yopilgan.")
        return
    cards = await active_cards()
    if not cards:
        await message.answer("❌ Hozircha to‘lov kartasi sozlanmagan. Admin bilan bog‘laning.")
        return
    lines = [
        f"💳 <b>To‘lov #{payment_id}</b>",
        f"💰 Summa: <b>{int(payment['amount']):,} so‘m</b>",
        "",
        "<b>Kartalar:</b>",
    ]
    for card in cards:
        lines.append(f"• <code>{card['card_number']}</code> — {card['holder'] or ''}")
    lines += [
        "",
        "To‘lovni amalga oshirgach, <b>chek/skrinshotni shu chatga yuboring</b>.",
        "Admin tekshiradi va tasdiqlagach test/natija ochiladi.",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


async def notify_admins_payment(payment_id: int, user_id: int, proof_file_id: str):
    if bot is None:
        return
    admin_chat_id = await get_admin_chat_id()
    if not admin_chat_id:
        print("Payment proof received but admin_chat_id is not configured. Open /admin first.")
        return
    user = await get_user(user_id)
    name = ((user["first_name"] or "") + " " + (user["last_name"] or "")).strip() if user else "User"
    username = user["username"] if user else ""
    assert pool is not None
    async with pool.acquire() as conn:
        payment = await conn.fetchrow("SELECT amount,purpose FROM payments WHERE id=$1", payment_id)
    amount = int(payment["amount"]) if payment else await get_price()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_ok:{payment_id}"),
         InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_no:{payment_id}")]
    ])
    caption = (
        f"💳 <b>Yangi to‘lov</b>\n\n"
        f"ID: <code>{payment_id}</code>\n"
        f"User: <b>{name}</b>\n"
        f"Username: @{username or '-'}\n"
        f"User ID: <code>{user_id}</code>\n"
        f"Summa: <b>{amount:,} so‘m</b>"
    )
    try:
        await bot.send_photo(admin_chat_id, proof_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
    except Exception as exc:
        print(f"Admin payment notification failed: {exc}")


def bot_keyboard(is_admin: bool = False):
    rows = [[
        InlineKeyboardButton(
            text="🧠 IQ TESTNI BOSHLASH",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]]
    if is_admin:
        rows.append([InlineKeyboardButton(text="👑 ADMIN PANEL", callback_data="adm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message):
    if not message.from_user:
        return
    referral_id = None
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1] if len(parts) == 2 else ""
    if payload.startswith("pay_"):
        try:
            payment_id = int(payload[4:])
            await upsert_user({
                "id": message.from_user.id,
                "first_name": message.from_user.first_name or "",
                "last_name": message.from_user.last_name or "",
                "username": message.from_user.username or "",
            })
            await send_payment_instructions(message, payment_id)
            return
        except ValueError:
            pass

    if payload.startswith("ref_"):
        try:
            referral_id = int(payload[4:])
        except ValueError:
            referral_id = None

    tg_user = {
        "id": message.from_user.id,
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
    }
    await upsert_user(tg_user, referral_id)
    await message.answer(
        "🧠 <b>IQ TEST BOT</b>\n\n"
        "16 ta original mantiqiy puzzle orqali o‘zingizni sinab ko‘ring.\n\n"
        "• Birinchi test — bepul\n"
        "• Natija va reyting\n"
        "• Sertifikat\n"
        "• UZ / RU / EN\n\n"
        "Test Mini App ichida ishlaydi.",
        reply_markup=bot_keyboard(is_admin_user(message.from_user)),
        parse_mode="HTML",
    )


@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin_user(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo‘q.")
        return
    await remember_admin_chat(message.from_user.id)
    await message.answer(await admin_text(), parse_mode="HTML", reply_markup=admin_panel_keyboard())


@dp.callback_query(lambda c: c.data == "adm_home")
async def admin_home_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return
    await remember_admin_chat(callback.from_user.id)
    await callback.message.edit_text(await admin_text(), parse_mode="HTML", reply_markup=admin_panel_keyboard())
    await callback.answer()


@dp.callback_query(lambda c: c.data == "adm_cards")
async def admin_cards_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    cards = await active_cards()
    text = "💳 <b>Kartalar</b>\n\n" + ("\n".join(f"#{c['id']}  <code>{c['card_number']}</code> — {c['holder'] or '-'}" for c in cards) if cards else "Hali karta qo‘shilmagan.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_cards_keyboard(cards))
    await callback.answer()


@dp.callback_query(lambda c: c.data == "adm_card_add")
async def admin_card_add_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    admin_state[callback.from_user.id] = "card_add"
    await callback.message.answer("💳 Karta ma’lumotini shu formatda yuboring:\n\n<code>8600123456789012 | ISM FAMILIYA</code>", parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("adm_card_del:"))
async def admin_card_delete_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    card_id = int(callback.data.split(":",1)[1])
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute("UPDATE payment_cards SET active=FALSE WHERE id=$1", card_id)
    await callback.answer("Karta o‘chirildi")
    cards = await active_cards()
    await callback.message.edit_text("💳 <b>Kartalar</b>", parse_mode="HTML", reply_markup=admin_cards_keyboard(cards))


@dp.callback_query(lambda c: c.data == "adm_price")
async def admin_price_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    admin_state[callback.from_user.id] = "price"
    await callback.message.answer(f"💰 Yangi narxni faqat son bilan yuboring. Hozirgi: <b>{await get_price():,} so‘m</b>", parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "adm_mode")
async def admin_mode_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    await callback.message.edit_text("⚙️ <b>To‘lov rejimi</b>\n\nQaysi modelni ishlatamiz?", parse_mode="HTML", reply_markup=admin_mode_keyboard())
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("adm_mode:"))
async def admin_mode_set_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    mode = callback.data.split(":",1)[1]
    if mode not in VALID_PAYMENT_MODES:
        await callback.answer("Noto‘g‘ri rejim", show_alert=True); return
    await set_setting("payment_mode", mode)
    await callback.answer("Rejim saqlandi")
    await callback.message.edit_text(await admin_text(), parse_mode="HTML", reply_markup=admin_panel_keyboard())


@dp.callback_query(lambda c: c.data == "adm_payments")
async def admin_payments_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    assert pool is not None
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id,p.user_id,p.amount,p.purpose,p.status,p.created_at,u.first_name,u.username
            FROM payments p JOIN users u ON u.user_id=p.user_id
            WHERE p.status='pending' ORDER BY p.id DESC LIMIT 20
        """)
    if not rows:
        text = "📋 <b>Kutilayotgan to‘lovlar</b>\n\nHozircha yo‘q."
    else:
        text = "📋 <b>Kutilayotgan to‘lovlar</b>\n\n" + "\n".join(f"#{r['id']} • {r['amount']:,} so‘m • {r['first_name'] or '-'} • @{r['username'] or '-'}" for r in rows)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm_home")]]))
    await callback.answer()


@dp.callback_query(lambda c: c.data == "adm_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    assert pool is not None
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        attempts = await conn.fetchval("SELECT COUNT(*) FROM attempts")
        pending = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status='pending'")
        approved = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'")
    text = f"📊 <b>Statistika</b>\n\n👥 Users: <b>{users}</b>\n🧠 Yakunlangan testlar: <b>{attempts}</b>\n⏳ Kutilayotgan to‘lovlar: <b>{pending}</b>\n💰 Tasdiqlangan to‘lovlar: <b>{approved:,} so‘m</b>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm_home")]]))
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("pay_ok:"))
async def payment_approve_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    payment_id = int(callback.data.split(":",1)[1])
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM payments WHERE id=$1 FOR UPDATE", payment_id)
        if not row:
            await callback.answer("To‘lov topilmadi", show_alert=True); return
        await conn.execute("UPDATE payments SET status='approved', reviewer_id=$2, reviewed_at=NOW() WHERE id=$1", payment_id, callback.from_user.id)
        user_id = int(row["user_id"])
    try:
        if bot is not None:
            await bot.send_message(user_id, "✅ <b>To‘lov tasdiqlandi.</b> Mini App'ga qaytib davom eting.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("To‘lov tasdiqlandi")
    await callback.message.edit_caption((callback.message.caption or "") + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")


@dp.callback_query(lambda c: c.data and c.data.startswith("pay_no:"))
async def payment_reject_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("Ruxsat yo‘q", show_alert=True); return
    await remember_admin_chat(callback.from_user.id)
    payment_id = int(callback.data.split(":",1)[1])
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM payments WHERE id=$1", payment_id)
        if not row:
            await callback.answer("To‘lov topilmadi", show_alert=True); return
        await conn.execute("UPDATE payments SET status='rejected', reviewer_id=$2, reviewed_at=NOW() WHERE id=$1", payment_id, callback.from_user.id)
        user_id = int(row["user_id"])
    try:
        if bot is not None:
            await bot.send_message(user_id, "❌ <b>To‘lov rad etildi.</b> Chekni tekshirib, qayta yuboring.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("To‘lov rad etildi")
    await callback.message.edit_caption((callback.message.caption or "") + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")


@dp.message(lambda m: m.from_user is not None and is_admin_user(m.from_user) and m.from_user.id in admin_state)
async def admin_text_input(message: Message):
    uid = message.from_user.id
    state_name = admin_state.get(uid)
    text = (message.text or "").strip()
    if state_name == "price":
        try:
            price = int(text.replace(" ", ""))
            if price < 0 or price > 100000000:
                raise ValueError
        except ValueError:
            await message.answer("❌ Narx noto‘g‘ri. Masalan: <code>5000</code>", parse_mode="HTML")
            return
        await set_setting("price_uzs", str(price))
        admin_state.pop(uid, None)
        await message.answer(f"✅ Narx saqlandi: <b>{price:,} so‘m</b>", parse_mode="HTML", reply_markup=admin_panel_keyboard())
        return
    if state_name == "card_add":
        parts = [x.strip() for x in text.split("|", 1)]
        card_number = parts[0].replace(" ", "") if parts else ""
        holder = parts[1].strip() if len(parts) == 2 else ""
        if (
            len(parts) != 2
            or not card_number.isdigit()
            or len(card_number) < 8
            or len(card_number) > 32
            or not holder
        ):
            await message.answer("❌ Format noto‘g‘ri. Masalan: <code>8600123456789012 | ISM FAMILIYA</code>", parse_mode="HTML")
            return
        assert pool is not None
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM payment_cards WHERE card_number=$1 AND active=TRUE", card_number)
            if exists:
                await message.answer("❌ Bu karta allaqachon qo‘shilgan.")
                return
            await conn.execute("INSERT INTO payment_cards(card_number, holder) VALUES($1,$2)", card_number, holder)
        admin_state.pop(uid, None)
        await message.answer("✅ Karta qo‘shildi.", reply_markup=admin_panel_keyboard())


@dp.message(lambda m: m.from_user is not None and m.photo is not None)
async def payment_proof_photo(message: Message):
    if not message.from_user:
        return
    assert pool is not None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, amount, purpose FROM payments
            WHERE user_id=$1 AND status='pending' AND consumed=FALSE
            ORDER BY id DESC LIMIT 1
        """, message.from_user.id)
        if not row:
            return
        file_id = message.photo[-1].file_id
        await conn.execute(
            "UPDATE payments SET proof_file_id=$2, proof_message_id=$3 WHERE id=$1",
            row["id"], file_id, message.message_id
        )
    await message.answer("✅ Chek qabul qilindi. Admin tekshiradi.")
    await notify_admins_payment(int(row["id"]), message.from_user.id, file_id)


async def configure_bot():
    assert bot is not None
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="🧠 IQ TEST",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )
    await bot.set_webhook(
        url=webhook_url(),
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=False,
        allowed_updates=dp.resolve_used_update_types(),
    )
    info = await bot.get_webhook_info()
    print(f"Webhook configured: {info.url}")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    global bot
    if bot is None:
        raise HTTPException(status_code=503, detail="BOT_NOT_READY")
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as exc:
        print(f"Webhook update error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="WEBHOOK_ERROR") from exc


async def run_web():
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    global bot, BOT_USERNAME
    await init_db()
    bot = Bot(BOT_TOKEN)
    me = await bot.get_me()
    BOT_USERNAME = me.username or ""
    print(f"Bot started: @{BOT_USERNAME}")
    await configure_bot()

    try:
        await run_web()
    finally:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as exc:
            print(f"Webhook cleanup warning: {exc}")
        await bot.session.close()
        if pool is not None:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
