# bot.py
import os
import io
import json
import random
import string
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Update, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BufferedInputFile, CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

# ==================== ENV ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "IQTestBot")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://your-app.onrender.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN required")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL required")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_pool: asyncpg.Pool = None

# ==================== TRANSLATIONS ====================
TEXTS = {
    "uz": {
        "choose_lang": "🌐 Tilni tanlang:",
        "welcome": "👋 Salom, {name}!\n\n🧠 <b>IQ TEST BOT</b>\n\nIQ, EQ va prokrastinatsiya testlarini ishlang, natijangizni bilib oling va shaxsiy profilingizni oching.\n\n👇 Boshlash uchun tugmani bosing",
        "menu_test": "🧠 IQ · EQ · PQ testini ishlash",
        "menu_cert": "📜 Sertifikatim",
        "menu_rank": "🏆 Reyting",
        "menu_earn": "💰 Pul ishlash",
        "menu_help": "ℹ️ Narx va yordam",
        "menu_lang": "🌐 Til",
        "no_cert": "📜 Hali sertifikatingiz yo‘q.\nAvval IQ testni topshiring.",
        "ranking_title": "🏆 <b>REYTING</b>\n\n",
        "earn_title": "💰 <b>PUL ISHLASH</b>\n\nDo‘stlaringizni taklif qiling va har bir faol foydalanuvchi uchun mukofot oling!\n\n🔗 Sizning havolangiz:\n<code>{link}</code>\n\n👥 Taklif qilinganlar: <b>{count}</b>",
        "help": "ℹ️ <b>NARX VA YORDAM</b>\n\n🧠 IQ test — 10 000 so‘m\n🎭 EQ — IQ dan keyin tekin\n⏳ Prokrastinatsiya — EQ dan keyin tekin\n⭐ To‘liq tahlil — uchalasidan keyin tekin\n🔄 IQ qayta — 5 000 so‘m\n🔄 EQ / PQ qayta — 5 000 so‘m\n⚔️ Battle — 7 500 so‘m / ishtirokchi\n💳 To‘lov Click yoki karta orqali\n⏱ To‘lov 1–2 daqiqada tasdiqlanadi\n📜 Sertifikat Telegram orqali yuboriladi\n\n👤 <b>QO‘LLAB-QUVVATLASH</b>\n@omono_v",
        "lang_changed": "✅ Til o‘zgartirildi: O‘zbekcha",
        "cert_found": "✅ <b>Sertifikat topildi</b>\n\n👤 {name}\n📊 IQ-style Score: <b>{score}</b>\n📅 Sana: {date}",
        "cert_not_found": "❌ Sertifikat topilmadi.",
        "maintenance": "🛠 Bot texnik xizmatda. Keyinroq urinib ko‘ring.",
    },
    "ru": {
        "choose_lang": "🌐 Выберите язык:",
        "welcome": "👋 Привет, {name}!\n\n🧠 <b>IQ TEST BOT</b>\n\nПройдите тесты IQ, EQ и прокрастинации, узнайте результат и откройте свой профиль.\n\n👇 Нажмите кнопку, чтобы начать",
        "menu_test": "🧠 Пройти тест IQ · EQ · PQ",
        "menu_cert": "📜 Мой сертификат",
        "menu_rank": "🏆 Рейтинг",
        "menu_earn": "💰 Заработок",
        "menu_help": "ℹ️ Цены и помощь",
        "menu_lang": "🌐 Язык",
        "no_cert": "📜 У вас пока нет сертификата.\nСначала пройдите IQ тест.",
        "ranking_title": "🏆 <b>РЕЙТИНГ</b>\n\n",
        "earn_title": "💰 <b>ЗАРАБОТОК</b>\n\nПриглашайте друзей и получайте награду!\n\n🔗 Ваша ссылка:\n<code>{link}</code>\n\n👥 Приглашено: <b>{count}</b>",
        "help": "ℹ️ <b>ЦЕНЫ И ПОМОЩЬ</b>\n\n🧠 IQ тест — 10 000 сум\n🎭 EQ — бесплатно после IQ\n⏳ Прокрастинация — бесплатно после EQ\n⭐ Полный анализ — бесплатно после трёх\n🔄 Повтор IQ — 5 000 сум\n🔄 Повтор EQ / PQ — 5 000 сум\n⚔️ Батл — 7 500 сум / участник\n💳 Оплата через Click или карту\n⏱ Подтверждение 1–2 минуты\n📜 Сертификат отправляется в Telegram\n\n👤 <b>ПОДДЕРЖКА</b>\n@omono_v",
        "lang_changed": "✅ Язык изменён: Русский",
        "cert_found": "✅ <b>Сертификат найден</b>\n\n👤 {name}\n📊 IQ-style Score: <b>{score}</b>\n📅 Дата: {date}",
        "cert_not_found": "❌ Сертификат не найден.",
        "maintenance": "🛠 Бот на техобслуживании.",
    },
    "en": {
        "choose_lang": "🌐 Choose language:",
        "welcome": "👋 Hello, {name}!\n\n🧠 <b>IQ TEST BOT</b>\n\nTake IQ, EQ and procrastination tests, discover your results and unlock your personal profile.\n\n👇 Tap the button to start",
        "menu_test": "🧠 Take IQ · EQ · PQ test",
        "menu_cert": "📜 My Certificate",
        "menu_rank": "🏆 Ranking",
        "menu_earn": "💰 Earn Money",
        "menu_help": "ℹ️ Pricing & Help",
        "menu_lang": "🌐 Language",
        "no_cert": "📜 You don't have a certificate yet.\nTake the IQ test first.",
        "ranking_title": "🏆 <b>RANKING</b>\n\n",
        "earn_title": "💰 <b>EARN MONEY</b>\n\nInvite friends and get rewards!\n\n🔗 Your link:\n<code>{link}</code>\n\n👥 Invited: <b>{count}</b>",
        "help": "ℹ️ <b>PRICING & HELP</b>\n\n🧠 IQ test — 10 000 UZS\n🎭 EQ — free after IQ\n⏳ Procrastination — free after EQ\n⭐ Full analysis — free after all three\n🔄 IQ retry — 5 000 UZS\n🔄 EQ / PQ retry — 5 000 UZS\n⚔️ Battle — 7 500 UZS / player\n💳 Payment via Click or card\n⏱ Confirmation 1–2 minutes\n📜 Certificate sent via Telegram\n\n👤 <b>SUPPORT</b>\n@omono_v",
        "lang_changed": "✅ Language changed: English",
        "cert_found": "✅ <b>Certificate found</b>\n\n👤 {name}\n📊 IQ-style Score: <b>{score}</b>\n📅 Date: {date}",
        "cert_not_found": "❌ Certificate not found.",
        "maintenance": "🛠 Bot is under maintenance.",
    }
}

def t(lang: str, key: str, **kwargs):
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, TEXTS["uz"].get(key, key))
    return text.format(**kwargs) if kwargs else text


# ==================== DB INIT ====================
async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'uz',
                last_seen TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                battle_id INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_answers (
                id SERIAL PRIMARY KEY,
                attempt_id INTEGER NOT NULL,
                question_number INTEGER NOT NULL,
                answer TEXT,
                is_correct BOOLEAN,
                time_spent INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_attempts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                session_id TEXT,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                score INTEGER,
                correct_count INTEGER,
                duration INTEGER,
                status TEXT DEFAULT 'in_progress'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                attempt_id INTEGER NOT NULL,
                test_type TEXT NOT NULL,
                score INTEGER NOT NULL,
                level TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                payment_id TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                product TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                receipt_file_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                approved_at TIMESTAMPTZ
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_cards (
                id SERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL,
                bank TEXT,
                active BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                certificate_id TEXT UNIQUE NOT NULL,
                verification_code TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                result_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                id SERIAL PRIMARY KEY,
                battle_code TEXT UNIQUE NOT NULL,
                creator_id BIGINT NOT NULL,
                opponent_id BIGINT,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS battle_players (
                id SERIAL PRIMARY KEY,
                battle_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                test_status TEXT DEFAULT 'not_started',
                score INTEGER,
                joined_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(battle_id, user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(referred_id)
            )
        """)
        defaults = {
            "iq_price": "10000",
            "iq_retry_price": "5000",
            "eq_retry_price": "5000",
            "pq_retry_price": "5000",
            "battle_price": "7500",
            "free_launch_end": "2026-09-30",
            "support_username": "omono_v",
            "maintenance_mode": "0",
        }
        for k, v in defaults.items():
            await conn.execute(
                "INSERT INTO app_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                k, v
            )
        if ADMIN_USER_ID:
            await conn.execute(
                "INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
                ADMIN_USER_ID
            )
    logger.info("DB initialized")


# ==================== HELPERS ====================
def gen_code(prefix="IQ", length=6):
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-" + "".join(random.choices(chars, k=length))

def gen_payment_id():
    return "PAY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def gen_session_id():
    return "SES-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))

def gen_battle_code():
    return "".join(random.choices(string.digits, k=4))

def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = dict(pair.split("=", 1) for pair in init_data.split("&"))
        hash_val = parsed.pop("hash", None)
        if not hash_val:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if calc != hash_val:
            return None
        auth_date = int(parsed.get("auth_date", "0"))
        if datetime.now(timezone.utc).timestamp() - auth_date > 86400:
            return None
        user = json.loads(parsed.get("user", "{}"))
        return user
    except Exception:
        return None

async def get_setting(key: str, default=None):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM app_settings WHERE key=$1", key)
        return row["value"] if row else default

async def set_setting(key: str, value: str):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO app_settings (key, value, updated_at) VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value=$2, updated_at=NOW()
        """, key, value)

async def is_admin(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admins WHERE user_id=$1", user_id)
        return row is not None

async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def upsert_user(user: types.User):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET username=$2, first_name=$3, last_name=$4, last_seen=NOW()
        """, user.id, user.username, user.first_name, user.last_name)


# ==================== KEYBOARDS ====================
def lang_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 O‘zbekcha", callback_data="lang:uz")
    b.button(text="🇷🇺 Русский", callback_data="lang:ru")
    b.button(text="🇬🇧 English", callback_data="lang:en")
    b.adjust(1)
    return b.as_markup()

def main_menu_kb(lang: str):
    b = ReplyKeyboardBuilder()
    b.button(text=t(lang, "menu_test"), web_app=WebAppInfo(url=f"{WEBAPP_URL}/app"))
    b.button(text=t(lang, "menu_cert"))
    b.button(text=t(lang, "menu_rank"))
    b.button(text=t(lang, "menu_earn"))
    b.button(text=t(lang, "menu_help"))
    b.button(text=t(lang, "menu_lang"))
    b.adjust(1, 2, 2, 1)
    return b.as_markup(resize_keyboard=True)

def admin_kb():
    b = InlineKeyboardBuilder()
    b.button(text="👥 Users", callback_data="admin:users")
    b.button(text="📊 Statistics", callback_data="admin:stats")
    b.button(text="💳 Payments", callback_data="admin:payments")
    b.button(text="📢 Broadcast", callback_data="admin:broadcast")
    b.button(text="💰 Products", callback_data="admin:products")
    b.button(text="🏆 Ranking", callback_data="admin:ranking")
    b.button(text="📜 Certificates", callback_data="admin:certs")
    b.button(text="⚔️ Battles", callback_data="admin:battles")
    b.button(text="⚙️ Settings", callback_data="admin:settings")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()


# ==================== BOT HANDLERS ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await upsert_user(message.from_user)
    user = await get_user(message.from_user.id)
    args = message.text.split()
    # Referral
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != message.from_user.id:
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO referrals (referrer_id, referred_id) VALUES ($1, $2)
                        ON CONFLICT (referred_id) DO NOTHING
                    """, ref_id, message.from_user.id)
        except Exception:
            pass

    if not user or not user["language"]:
        await message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())
        return
    lang = user["language"]
    await message.answer(
        t(lang, "welcome", name=message.from_user.first_name or "do‘stim"),
        reply_markup=main_menu_kb(lang)
    )


@dp.callback_query(F.data.startswith("lang:"))
async def cb_lang(cb: CallbackQuery):
    lang = cb.data.split(":")[1]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET language=$1 WHERE user_id=$2", lang, cb.from_user.id)
    await cb.message.edit_text(t(lang, "lang_changed"))
    await cb.message.answer(
        t(lang, "welcome", name=cb.from_user.first_name or "do‘stim"),
        reply_markup=main_menu_kb(lang)
    )
    await cb.answer()


@dp.message(F.text.in_([TEXTS["uz"]["menu_cert"], TEXTS["ru"]["menu_cert"], TEXTS["en"]["menu_cert"]]))
async def menu_cert(message: types.Message):
    user = await get_user(message.from_user.id)
    lang = user["language"] if user else "uz"
    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow(
            "SELECT * FROM certificates WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1",
            message.from_user.id
        )
    if not cert:
        await message.answer(t(lang, "no_cert"))
        return
    # Generate PNG
    png = generate_certificate_png(
        name=message.from_user.first_name or "User",
        score=cert["score"],
        code=cert["verification_code"],
        date=cert["created_at"].strftime("%d.%m.%Y")
    )
    await message.answer_document(BufferedInputFile(png, filename=f"{cert['verification_code']}.png"))


@dp.message(F.text.in_([TEXTS["uz"]["menu_rank"], TEXTS["ru"]["menu_rank"], TEXTS["en"]["menu_rank"]]))
async def menu_rank(message: types.Message):
    user = await get_user(message.from_user.id)
    lang = user["language"] if user else "uz"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.first_name, u.username, MAX(r.score) as best
            FROM results r
            JOIN users u ON u.user_id = r.user_id
            WHERE r.test_type='iq'
            GROUP BY u.user_id, u.first_name, u.username
            ORDER BY best DESC
            LIMIT 10
        """)
    text = t(lang, "ranking_title")
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows, 1):
        name = r["first_name"] or r["username"] or "User"
        prefix = medals[i-1] if i <= 3 else f"{i}."
        text += f"{prefix} {name} — <b>{r['best']}</b>\n"
    if not rows:
        text += "Hozircha natijalar yo‘q."
    await message.answer(text)


@dp.message(F.text.in_([TEXTS["uz"]["menu_earn"], TEXTS["ru"]["menu_earn"], TEXTS["en"]["menu_earn"]]))
async def menu_earn(message: types.Message):
    user = await get_user(message.from_user.id)
    lang = user["language"] if user else "uz"
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", message.from_user.id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    await message.answer(t(lang, "earn_title", link=link, count=cnt))


@dp.message(F.text.in_([TEXTS["uz"]["menu_help"], TEXTS["ru"]["menu_help"], TEXTS["en"]["menu_help"]]))
async def menu_help(message: types.Message):
    user = await get_user(message.from_user.id)
    lang = user["language"] if user else "uz"
    await message.answer(t(lang, "help"))


@dp.message(F.text.in_([TEXTS["uz"]["menu_lang"], TEXTS["ru"]["menu_lang"], TEXTS["en"]["menu_lang"]]))
async def menu_lang(message: types.Message):
    await message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())


# Certificate verification: user sends IQ-XXXXXX
@dp.message(F.text.regexp(r"^IQ-[A-Z0-9]{6}$"))
async def verify_cert(message: types.Message):
    code = message.text.strip()
    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow("""
            SELECT c.*, u.first_name FROM certificates c
            JOIN users u ON u.user_id = c.user_id
            WHERE c.verification_code=$1
        """, code)
    if not cert:
        await message.answer(t("uz", "cert_not_found"))
        return
    await message.answer(t("uz", "cert_found",
        name=cert["first_name"] or "User",
        score=cert["score"],
        date=cert["created_at"].strftime("%d.%m.%Y")
    ))


# Admin
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("👑 <b>ADMIN PANEL</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        today = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at::date = NOW()::date")
        iq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='iq'")
        eq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='eq'")
        pq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='pq'")
        pay = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status='approved'")
        rev = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'")
        battles = await conn.fetchval("SELECT COUNT(*) FROM battles")
    text = (
        f"📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <b>{total}</b>\n"
        f"📅 Today: <b>{today}</b>\n"
        f"🧠 IQ: <b>{iq}</b>\n"
        f"🎭 EQ: <b>{eq}</b>\n"
        f"⏳ PQ: <b>{pq}</b>\n"
        f"💳 Payments: <b>{pay}</b>\n"
        f"💰 Revenue: <b>{rev:,} so‘m</b>\n"
        f"⚔️ Battles: <b>{battles}</b>"
    )
    await cb.message.edit_text(text, reply_markup=admin_kb())
    await cb.answer()


@dp.callback_query(F.data == "admin:payments")
async def admin_payments(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC LIMIT 20")
    if not rows:
        await cb.message.edit_text("💳 Pending payments yo‘q.", reply_markup=admin_kb())
        await cb.answer()
        return
    for p in rows:
        b = InlineKeyboardBuilder()
        b.button(text="✅ TASDIQLASH", callback_data=f"pay_ok:{p['payment_id']}")
        b.button(text="❌ RAD ETISH", callback_data=f"pay_no:{p['payment_id']}")
        b.adjust(2)
        text = (
            f"💳 <b>PAYMENT</b>\n\n"
            f"👤 User: <code>{p['user_id']}</code>\n"
            f"📦 Product: <b>{p['product']}</b>\n"
            f"💰 Amount: <b>{p['amount']:,} so‘m</b>\n"
            f"📅 {p['created_at'].strftime('%d.%m.%Y %H:%M')}"
        )
        if p["receipt_file_id"]:
            await cb.message.answer_photo(p["receipt_file_id"], caption=text, reply_markup=b.as_markup())
        else:
            await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("pay_ok:"))
async def pay_ok(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    pid = cb.data.split(":")[1]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE payments SET status='approved', approved_at=NOW() WHERE payment_id=$1 AND status='pending'", pid)
    await cb.message.edit_caption(caption="✅ Tasdiqlandi") if cb.message.caption else await cb.message.edit_text("✅ Tasdiqlandi")
    await cb.answer("Approved")


@dp.callback_query(F.data.startswith("pay_no:"))
async def pay_no(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    pid = cb.data.split(":")[1]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE payments SET status='rejected' WHERE payment_id=$1 AND status='pending'", pid)
    await cb.message.edit_caption(caption="❌ Rad etildi") if cb.message.caption else await cb.message.edit_text("❌ Rad etildi")
    await cb.answer("Rejected")


# Receipt handler
@dp.message(F.photo)
async def handle_receipt(message: types.Message):
    # Eng oxirgi pending paymentni topish
    async with db_pool.acquire() as conn:
        p = await conn.fetchrow("""
            SELECT * FROM payments WHERE user_id=$1 AND status='pending'
            ORDER BY created_at DESC LIMIT 1
        """, message.from_user.id)
        if not p:
            return
        await conn.execute("UPDATE payments SET receipt_file_id=$1 WHERE payment_id=$2",
                           message.photo[-1].file_id, p["payment_id"])
    await message.answer("✅ Chek qabul qilindi. Admin tasdiqlashini kuting.")


# ==================== CERTIFICATE PNG ====================
def generate_certificate_png(name: str, score: int, code: str, date: str) -> bytes:
    W, H = 1600, 1100
    img = Image.new("RGB", (W, H), "#0a0e1a")
    draw = ImageDraw.Draw(img)

    # Gradient background (approx)
    for y in range(H):
        ratio = y / H
        r = int(10 + 20 * ratio)
        g = int(14 + 20 * ratio)
        b = int(26 + 40 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Gold border
    draw.rectangle([30, 30, W-30, H-30], outline="#d4af37", width=6)
    draw.rectangle([50, 50, W-50, H-50], outline="#d4af37", width=2)

    # Fonts
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 110)
        f_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 80)
        f_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
        f_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
        f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        f_title = f_name = f_score = f_label = f_small = ImageFont.load_default()

    def center(text, font, y, fill="#d4af37"):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=font, fill=fill)

    center("SERTIFIKAT", f_title, 120, "#d4af37")
    center("AQLLIY SALOHIYAT TO‘G‘RISIDA", f_label, 260, "#c9a227")

    # Name
    draw.line([(300, 420), (W-300, 420)], fill="#d4af37", width=2)
    center(name, f_name, 320, "#ffffff")
    draw.line([(300, 440), (W-300, 440)], fill="#d4af37", width=2)

    center("IQ-STYLE SCORE", f_label, 490, "#c9a227")
    center(str(score), f_score, 540, "#ffffff")

    # Level
    if score >= 130:
        level = "JUDA YUQORI"
    elif score >= 115:
        level = "YUQORI DARAJA"
    elif score >= 100:
        level = "O‘RTA DARAJA"
    else:
        level = "RIVOJLANTIRISH KERAK"
    center(level, f_label, 800, "#d4af37")

    # Bottom
    draw.text((150, H-150), f"📅 {date}", font=f_small, fill="#c9a227")
    draw.text((150, H-100), f"Kod: {code}", font=f_small, fill="#c9a227")
    draw.text((W-450, H-100), "IQ TEST BOT", font=f_small, fill="#c9a227")

    # Seal
    seal_x, seal_y = W - 220, 220
    draw.ellipse([seal_x-100, seal_y-100, seal_x+100, seal_y+100], outline="#d4af37", width=6)
    draw.ellipse([seal_x-85, seal_y-85, seal_x+85, seal_y+85], outline="#d4af37", width=2)
    center_bbox = draw.textbbox((0, 0), "VERIFIED", font=f_small)
    draw.text((seal_x - (center_bbox[2]-center_bbox[0])/2, seal_y - 15), "VERIFIED", font=f_small, fill="#d4af37")

    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


# ==================== FASTAPI ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    await init_db(db_pool)
    try:
        await bot.set_webhook(
            url=f"{PUBLIC_BASE_URL}/telegram/webhook",
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True
        )
        logger.info("Webhook set")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    yield
    await bot.session.close()
    await db_pool.close()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="webapp"), name="static")


@app.get("/health")
async def health():
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


# ---------- API ----------
def get_user_from_init(init_data: str) -> dict | None:
    return validate_init_data(init_data, BOT_TOKEN)


@app.post("/api/me")
async def api_me(request: Request):
    body = await request.json()
    init_data = body.get("initData", "")
    user = get_user_from_init(init_data)
    if not user:
        raise HTTPException(401, "Unauthorized")
    uid = user["id"]
    async with db_pool.acquire() as conn:
        u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
        results = await conn.fetch("SELECT test_type, MAX(score) as best FROM results WHERE user_id=$1 GROUP BY test_type", uid)
        active_sessions = await conn.fetch("SELECT * FROM test_sessions WHERE user_id=$1 AND status='active'", uid)
        pending_payments = await conn.fetch("SELECT * FROM payments WHERE user_id=$1 AND status='pending'", uid)
    completed = {r["test_type"]: r["best"] for r in results}
    return {
        "ok": True,
        "user": {
            "user_id": uid,
            "first_name": user.get("first_name"),
            "language": u["language"] if u else "uz",
        },
        "completed": completed,
        "active_sessions": [dict(s) for s in active_sessions],
        "pending_payments": [dict(p) for p in pending_payments],
    }


@app.get("/api/stats/live")
async def api_stats_live():
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        online = await conn.fetchval("SELECT COUNT(*) FROM users WHERE last_seen > NOW() - INTERVAL '5 minutes'")
    return {"ok": True, "total": total, "online": online}


@app.get("/api/config")
async def api_config():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM app_settings")
    return {"ok": True, "settings": {r["key"]: r["value"] for r in rows}}


@app.post("/api/session/start")
async def api_session_start(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    test_type = body.get("test_type", "iq")
    sid = gen_session_id()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO test_sessions (session_id, user_id, test_type, expires_at)
            VALUES ($1, $2, $3, NOW() + INTERVAL '2 hours')
        """, sid, user["id"], test_type)
        attempt = await conn.fetchrow("""
            INSERT INTO test_attempts (user_id, test_type, session_id)
            VALUES ($1, $2, $3) RETURNING id
        """, user["id"], test_type, sid)
    return {"ok": True, "session_id": sid, "attempt_id": attempt["id"]}


@app.post("/api/test/submit")
async def api_test_submit(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    sid = body.get("session_id")
    answers = body.get("answers", [])
    async with db_pool.acquire() as conn:
        sess = await conn.fetchrow("SELECT * FROM test_sessions WHERE session_id=$1 AND user_id=$2", sid, user["id"])
        if not sess:
            raise HTTPException(404, "Session not found")
        if sess["status"] != "active":
            raise HTTPException(409, "Session already submitted")
        attempt = await conn.fetchrow("SELECT * FROM test_attempts WHERE session_id=$1", sid)
        if not attempt or attempt["status"] == "completed":
            raise HTTPException(409, "Attempt already completed")
        # Score calculation (placeholder — real questions in app.js)
        # Backend uses same answer key as frontend
        from_answers = body.get("answer_key", [])
        correct = 0
        for i, a in enumerate(answers):
            if i < len(from_answers) and a == from_answers[i]:
                correct += 1
        total = len(from_answers) or 18
        score = int(70 + (correct / total) * 60)  # IQ-style 70-130
        duration = body.get("duration", 0)
        await conn.execute("""
            UPDATE test_attempts SET finished_at=NOW(), score=$1, correct_count=$2, duration=$3, status='completed'
            WHERE id=$4
        """, score, correct, duration, attempt["id"])
        await conn.execute("UPDATE test_sessions SET status='completed' WHERE session_id=$1", sid)
        level = "YUQORI DARAJA" if score >= 115 else ("O‘RTA DARAJA" if score >= 100 else "RIVOJLANTIRISH")
        res = await conn.fetchrow("""
            INSERT INTO results (user_id, attempt_id, test_type, score, level)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, user["id"], attempt["id"], sess["test_type"], score, level)
        # Auto certificate
        code = gen_code("IQ")
        await conn.execute("""
            INSERT INTO certificates (certificate_id, verification_code, user_id, result_id, score)
            VALUES ($1, $2, $3, $4, $5)
        """, gen_code("CERT"), code, user["id"], res["id"], score)
    return {"ok": True, "score": score, "correct": correct, "total": total, "level": level, "certificate_code": code}


@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    product = body.get("product")
    price_map = {
        "iq": int(await get_setting("iq_price", "10000")),
        "iq_retry": int(await get_setting("iq_retry_price", "5000")),
        "eq_retry": int(await get_setting("eq_retry_price", "5000")),
        "pq_retry": int(await get_setting("pq_retry_price", "5000")),
        "battle": int(await get_setting("battle_price", "7500")),
    }
    amount = price_map.get(product)
    if not amount:
        raise HTTPException(400, "Invalid product")
    pid = gen_payment_id()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO payments (payment_id, user_id, product, amount)
            VALUES ($1, $2, $3, $4)
        """, pid, user["id"], product, amount)
        cards = await conn.fetch("SELECT card_number, holder, bank FROM payment_cards WHERE active=TRUE")
    return {"ok": True, "payment_id": pid, "amount": amount, "cards": [dict(c) for c in cards]}


@app.post("/api/payment/receipt")
async def api_payment_receipt(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    pid = body.get("payment_id")
    file_id = body.get("file_id")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE payments SET receipt_file_id=$1
            WHERE payment_id=$2 AND user_id=$3 AND status='pending'
        """, file_id, pid, user["id"])
    return {"ok": True}


@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    code = gen_battle_code()
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("""
            INSERT INTO battles (battle_code, creator_id) VALUES ($1, $2) RETURNING id
        """, code, user["id"])
        await conn.execute("""
            INSERT INTO battle_players (battle_id, user_id) VALUES ($1, $2)
        """, b["id"], user["id"])
    return {"ok": True, "battle_id": b["id"], "code": code}


@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    code = body.get("code")
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE battle_code=$1 AND status='waiting'", code)
        if not b:
            raise HTTPException(404, "Battle not found")
        if b["creator_id"] == user["id"]:
            raise HTTPException(400, "Cannot join own battle")
        await conn.execute("UPDATE battles SET opponent_id=$1, status='active' WHERE id=$2", user["id"], b["id"])
        await conn.execute("INSERT INTO battle_players (battle_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", b["id"], user["id"])
    return {"ok": True, "battle_id": b["id"]}


@app.get("/api/battle/{battle_id}")
async def api_battle_get(battle_id: int, request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE id=$1", battle_id)
        if not b:
            raise HTTPException(404, "Not found")
        players = await conn.fetch("SELECT * FROM battle_players WHERE battle_id=$1", battle_id)
    return {"ok": True, "battle": dict(b), "players": [dict(p) for p in players]}


@app.get("/api/certificate/{code}")
async def api_certificate(code: str):
    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow("""
            SELECT c.*, u.first_name FROM certificates c
            JOIN users u ON u.user_id = c.user_id
            WHERE c.verification_code=$1
        """, code)
    if not cert:
        return {"ok": False, "error": "NOT_FOUND"}
    return {"ok": True, "certificate": {
        "code": cert["verification_code"],
        "name": cert["first_name"],
        "score": cert["score"],
        "date": cert["created_at"].strftime("%d.%m.%Y"),
    }}


# ==================== RUN ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)