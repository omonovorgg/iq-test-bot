import asyncio
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
import uvicorn

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


def clean_db_url(url: str) -> str:
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in {"sslmode", "channel_binding"}]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))

DB_URL = clean_db_url(DATABASE_URL)
pool: asyncpg.Pool | None = None
bot: Bot | None = None
BOT_USERNAME = ""

dp = Dispatcher()
app = FastAPI(title="IQ TEST BOT")
app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")


async def init_db() -> None:
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5, ssl="require", command_timeout=30)
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

        CREATE TABLE IF NOT EXISTS test_sessions (
            user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            current_index INTEGER NOT NULL DEFAULT 0,
            answers JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw_score INTEGER NOT NULL DEFAULT 0,
            correct INTEGER NOT NULL DEFAULT 0,
            language TEXT NOT NULL DEFAULT 'uz',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            raw_score INTEGER NOT NULL,
            iq_score INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            elapsed INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_users_best_score ON users(best_score DESC NULLS LAST);
        CREATE INDEX IF NOT EXISTS idx_attempts_user_id ON attempts(user_id);
        """)


async def upsert_user(tg_user: dict, referral_id: int | None = None) -> None:
    assert pool
    uid = int(tg_user["id"])
    if referral_id == uid:
        referral_id = None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, first_name, last_name, username, referred_by)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (user_id) DO UPDATE SET
                first_name=EXCLUDED.first_name,
                last_name=EXCLUDED.last_name,
                username=EXCLUDED.username,
                updated_at=NOW()
        """, uid, tg_user.get("first_name", ""), tg_user.get("last_name", ""), tg_user.get("username", "") or "", referral_id)


async def count_referral(user_id: int) -> None:
    assert pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT referred_by, referral_counted FROM users WHERE user_id=$1 FOR UPDATE", user_id)
            if not row or not row["referred_by"] or row["referral_counted"] or row["referred_by"] == user_id:
                return
            exists = await conn.fetchval("SELECT 1 FROM users WHERE user_id=$1", row["referred_by"])
            if exists:
                await conn.execute("UPDATE users SET referral_counted=TRUE WHERE user_id=$1", user_id)
                await conn.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=$1", row["referred_by"])


async def get_user(uid: int):
    assert pool
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)


async def create_or_get_session(uid: int, language: str):
    assert pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow("SELECT attempts FROM users WHERE user_id=$1 FOR UPDATE", uid)
            if not user:
                raise HTTPException(401, "User not found")
            active = await conn.fetchrow("SELECT * FROM test_sessions WHERE user_id=$1 AND completed=FALSE FOR UPDATE", uid)
            now = datetime.now(timezone.utc)
            if active:
                age = (now - active["last_activity"]).total_seconds()
                if age <= 7200:
                    return active, False
                await conn.execute("DELETE FROM test_sessions WHERE user_id=$1", uid)
            if user["attempts"] >= 1:
                raise HTTPException(402, "PAID_RETEST")
            row = await conn.fetchrow("""
                INSERT INTO test_sessions(user_id, language) VALUES($1,$2)
                RETURNING *
            """, uid, language)
            return row, True


async def save_answer(uid: int, question_index: int, selected: int):
    assert pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM test_sessions WHERE user_id=$1 AND completed=FALSE FOR UPDATE", uid)
            if not row:
                raise HTTPException(409, "SESSION_EXPIRED")
            if question_index != row["current_index"]:
                raise HTTPException(409, "OUT_OF_ORDER")
            if not 0 <= selected <= 3:
                raise HTTPException(400, "INVALID_ANSWER")
            answers = list(row["answers"])
            answers.append(selected)
            await conn.execute("""
                UPDATE test_sessions
                SET current_index=current_index+1, answers=$2::jsonb, last_activity=NOW()
                WHERE user_id=$1
            """, uid, json.dumps(answers))
            return len(answers)


async def finish_session(uid: int):
    assert pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM test_sessions WHERE user_id=$1 AND completed=FALSE FOR UPDATE", uid)
            if not row:
                raise HTTPException(409, "SESSION_EXPIRED")
            answers = list(row["answers"])
            if len(answers) != 16:
                raise HTTPException(409, "INCOMPLETE")
            # Original question bank answers/weights. Frontend never determines the score.
            correct_answers = [1, 1, 2, 0, 2, 2, 0, 0, 1, 2, 2, 1, 2, 1, 1, 2]
            weights = [1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5]
            correct = sum(a == b for a, b in zip(answers, correct_answers))
            raw = sum(w for a, b, w in zip(answers, correct_answers, weights) if a == b)
            iq = round(40 + (raw / sum(weights)) * 120)
            elapsed = max(0, round((datetime.now(timezone.utc) - row["started_at"]).total_seconds()))
            await conn.execute("""
                INSERT INTO attempts(user_id, raw_score, iq_score, correct, elapsed)
                VALUES($1,$2,$3,$4,$5)
            """, uid, raw, iq, correct, elapsed)
            await conn.execute("""
                UPDATE users SET attempts=attempts+1,
                    best_score=CASE WHEN best_score IS NULL OR $2>best_score THEN $2 ELSE best_score END,
                    best_raw=CASE WHEN best_score IS NULL OR $2>best_score THEN $3 ELSE best_raw END,
                    best_time=CASE WHEN best_score IS NULL OR $2>best_score OR ($2=best_score AND (best_time IS NULL OR $5<best_time)) THEN $5 ELSE best_time END,
                    updated_at=NOW()
                WHERE user_id=$1
            """, uid, iq, raw, correct, elapsed)
            await conn.execute("DELETE FROM test_sessions WHERE user_id=$1", uid)
            return iq, raw, correct, elapsed


async def get_rank(uid: int):
    assert pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT best_score,best_time FROM users WHERE user_id=$1", uid)
        if not row or row["best_score"] is None:
            return None
        return await conn.fetchval("""
            SELECT COUNT(*)+1 FROM users
            WHERE best_score IS NOT NULL AND (
                best_score>$1 OR (best_score=$1 AND COALESCE(best_time,2147483647)<COALESCE($2,2147483647))
            )
        """, row["best_score"], row["best_time"])


# ---------- Telegram Mini App auth ----------
def validate_init_data(init_data: str) -> dict:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash", None)
        auth_date = int(pairs.get("auth_date", "0"))
        if not received:
            raise ValueError
        now = int(datetime.now(timezone.utc).timestamp())
        if auth_date <= 0 or now - auth_date > 86400:
            raise ValueError
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise ValueError
        if "user" not in pairs:
            raise ValueError
        return json.loads(pairs["user"])
    except Exception as exc:
        raise HTTPException(401, "INVALID_INIT_DATA") from exc


async def api_user(request: Request) -> dict:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return validate_init_data(init_data)


# ---------- API ----------
@app.get("/")
async def root():
    return {"status": "ok", "service": "IQ TEST BOT"}


@app.get("/health")
async def health():
    if pool is None:
        raise HTTPException(503, "database not ready")
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/app")
async def app_page():
    return FileResponse(WEBAPP_DIR / "index.html")


@app.post("/api/session/start")
async def api_start(request: Request):
    tg = await api_user(request)
    uid = int(tg["id"])
    body = await request.json()
    language = body.get("language", "uz")
    if language not in {"uz", "ru", "en"}:
        language = "uz"
    await upsert_user(tg)
    await count_referral(uid)
    row, created = await create_or_get_session(uid, language)
    elapsed = max(0, round((datetime.now(timezone.utc) - row["started_at"]).total_seconds()))
    return {"user_id": uid, "created": created, "index": row["current_index"], "answers": list(row["answers"]), "elapsed": elapsed, "attempts": (await get_user(uid))["attempts"]}


@app.post("/api/session/answer")
async def api_answer(request: Request):
    tg = await api_user(request)
    uid = int(tg["id"])
    body = await request.json()
    index = int(body.get("index", -1))
    selected = int(body.get("selected", -1))
    await save_answer(uid, index, selected)
    return {"ok": True}


@app.post("/api/session/finish")
async def api_finish(request: Request):
    tg = await api_user(request)
    uid = int(tg["id"])
    iq, raw, correct, elapsed = await finish_session(uid)
    rank = await get_rank(uid)
    return {"iq": iq, "raw": raw, "correct": correct, "elapsed": elapsed, "rank": rank}


@app.get("/api/profile")
async def api_profile(request: Request):
    tg = await api_user(request)
    uid = int(tg["id"])
    await upsert_user(tg)
    user = await get_user(uid)
    rank = await get_rank(uid)
    return {
        "first_name": user["first_name"], "username": user["username"], "attempts": user["attempts"],
        "best_score": user["best_score"], "best_time": user["best_time"], "referrals": user["referrals"], "rank": rank
    }


@app.get("/api/ranking")
async def api_ranking(request: Request):
    await api_user(request)
    assert pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT first_name, username, best_score, best_time FROM users
            WHERE best_score IS NOT NULL ORDER BY best_score DESC, best_time ASC NULLS LAST, created_at ASC LIMIT 50
        """)
    return {"items": [dict(r) for r in rows]}


# ---------- Certificate ----------
def make_certificate_png(name: str, iq: int) -> bytes:
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1400, 900
    img = Image.new("RGB", (w, h), "#0b0d16")
    d = ImageDraw.Draw(img)

    def font(size, bold=False):
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
        for path in paths:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def center(text, y, f, fill="#ffffff"):
        box=d.textbbox((0,0),text,font=f)
        d.text(((w-(box[2]-box[0]))/2,y),text,font=f,fill=fill)

    d.rounded_rectangle((35,35,w-35,h-35), radius=36, outline="#8b6cff", width=4)
    d.rounded_rectangle((58,58,w-58,h-58), radius=28, outline="#2b3040", width=2)
    center("ZAKO IQ", 115, font(64, True), "#b8a8ff")
    center("IQ TEST CERTIFICATE", 215, font(30, True), "#aeb5c6")
    center(str(iq), 290, font(150, True), "#ffffff")
    center("IQ SCORE", 470, font(30, True), "#b8a8ff")
    center(name[:32], 545, font(46, True), "#ffffff")
    center("ZAKO IQ testining taxminiy natijasi", 640, font(25), "#aeb5c6")
    center(datetime.now(timezone.utc).strftime("%Y-%m-%d"), 700, font(22), "#777f91")

    out=BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


@app.get("/api/certificate")
async def api_certificate(request: Request):
    tg = await api_user(request)
    uid = int(tg["id"])
    user = await get_user(uid)
    if not user or user["best_score"] is None:
        raise HTTPException(404, "NO_RESULT")
    if user["referrals"] < 2 and not user["cert_claimed"]:
        raise HTTPException(403, "REFERRALS_REQUIRED")
    if not user["cert_claimed"]:
        assert pool
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET cert_claimed=TRUE, updated_at=NOW() WHERE user_id=$1", uid)
    data = make_certificate_png(user["first_name"] or "User", int(user["best_score"]))
    return StreamingResponse(iter([data]), media_type="image/png", headers={"Content-Disposition":"inline; filename=zako-iq-certificate.png"})


# ---------- Bot ----------
def bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧠 IQ TESTNI BOSHLASH", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


@dp.message(CommandStart())
async def start(message: Message):
    referral_id = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            referral_id = int(parts[1][4:])
        except ValueError:
            referral_id = None
    tg = {
        "id": message.from_user.id,
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
    }
    await upsert_user(tg, referral_id)
    await message.answer(
        "🧠 <b>IQ TEST BOT</b>\n\n16 ta original mantiqiy puzzle orqali o‘zingizni sinab ko‘ring.\n\n• Birinchi test — bepul\n• Natija va reyting\n• Sertifikat\n• UZ / RU / EN\n\nTest Mini App ichida ishlaydi.",
        reply_markup=bot_keyboard(), parse_mode="HTML"
    )


async def run_web() -> None:
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    global bot, BOT_USERNAME
    await init_db()
    bot = Bot(BOT_TOKEN)
    me = await bot.get_me()
    BOT_USERNAME = me.username or ""
    print(f"Bot started: @{BOT_USERNAME}")
    try:
        await asyncio.gather(dp.start_polling(bot), run_web())
    finally:
        await bot.session.close()
        if pool:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
