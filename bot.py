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
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    Update,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
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
                age = (now_utc() - active["last_activity"]).total_seconds()
                if age <= 7200:
                    return active, False
                await conn.execute(
                    "DELETE FROM test_sessions WHERE user_id=$1", uid
                )

            if int(user["attempts"]) >= 1:
                raise HTTPException(status_code=402, detail="PAID_RETEST")

            row = await conn.fetchrow("""
                INSERT INTO test_sessions (user_id, language, started_at, last_activity)
                VALUES ($1, $2, NOW(), NOW())
                RETURNING *
            """, uid, language)
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
                return (
                    int(row["result_iq"]),
                    int(row["result_raw"]),
                    int(row["result_correct"]),
                    int(row["result_elapsed"]),
                )

            row = await repair_session(conn, row)
            answers = sanitize_answers(row["answers"])
            if len(answers) != QUESTIONS_COUNT or int(row["current_index"]) != QUESTIONS_COUNT:
                raise HTTPException(status_code=409, detail="INCOMPLETE")

            raw, correct = score_answers(answers)
            iq = calculate_iq(raw)
            elapsed = max(0, round((now_utc() - row["started_at"]).total_seconds()))

            await conn.execute("""
                INSERT INTO attempts (user_id, raw_score, iq_score, correct, elapsed)
                VALUES ($1, $2, $3, $4, $5)
            """, uid, raw, iq, correct, elapsed)

            await conn.execute("""
                UPDATE users SET
                    attempts=attempts+1,
                    best_score=CASE WHEN best_score IS NULL OR $2 > best_score THEN $2 ELSE best_score END,
                    best_raw=CASE WHEN best_score IS NULL OR $2 > best_score THEN $3 ELSE best_raw END,
                    best_time=CASE
                        WHEN best_score IS NULL OR $2 > best_score
                             OR ($2=best_score AND (best_time IS NULL OR $4<best_time))
                        THEN $4 ELSE best_time END,
                    updated_at=NOW()
                WHERE user_id=$1
            """, uid, iq, raw, elapsed)

            await conn.execute("""
                UPDATE test_sessions SET
                    completed=TRUE,
                    result_iq=$2, result_raw=$3,
                    result_correct=$4, result_elapsed=$5,
                    finished_at=NOW(), last_activity=NOW()
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


@app.get("/")
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
    return FileResponse(WEBAPP_DIR / "index.html")


@app.get("/api/config")
async def api_config():
    return {"bot_username": BOT_USERNAME, "zako_url": ZAKO_URL}


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


def bot_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🧠 IQ TESTNI BOSHLASH",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])


@dp.message(CommandStart())
async def start(message: Message):
    if not message.from_user:
        return
    referral_id = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            referral_id = int(parts[1][4:])
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
        reply_markup=bot_keyboard(),
        parse_mode="HTML",
    )


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
