# bot.py
# IQ TEST BOT — Professional Backend
# Part 1/2: Core, DB, IQ, EQ, PQ, Auth, HMAC (DEBUG)

import os
import io
import json
import random
import string
import hashlib
import hmac
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from urllib.parse import unquote

import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Update, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BufferedInputFile, CallbackQuery, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

# ==================== ENV ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot").strip().lstrip("@")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me").strip()
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN required")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL required")

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ===== STARTUP DEBUG (logger yaratilgandan keyin) =====
logger.warning("=" * 60)
logger.warning(f"STARTUP token_len={len(BOT_TOKEN)}")
logger.warning(f"STARTUP token_repr={repr(BOT_TOKEN)}")
logger.warning(f"STARTUP token_first15={BOT_TOKEN[:15]}")
logger.warning(f"STARTUP token_last10={BOT_TOKEN[-10:]}")
logger.warning(f"STARTUP webapp_url={WEBAPP_URL}")
logger.warning(f"STARTUP public_base_url={PUBLIC_BASE_URL}")
logger.warning(f"STARTUP webhook_secret_len={len(WEBHOOK_SECRET)}")
logger.warning("=" * 60)
# ======================================================

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
        "earn_title": "💰 <b>PUL ISHLASH</b>\n\nDo‘stlaringizni taklif qiling!\n\n🔗 Sizning havolangiz:\n<code>{link}</code>\n\n👥 Taklif qilinganlar: <b>{count}</b>",
        "help": "ℹ️ <b>NARX VA YORDAM</b>\n\n🧠 IQ test — {iq_price} so‘m\n🎭 EQ — IQ dan keyin tekin\n⏳ PQ — EQ dan keyin tekin\n⭐ To‘liq tahlil — uchalasidan keyin tekin\n🔄 IQ qayta — {iq_retry} so‘m\n⚔️ Battle — {battle_price} so‘m\n\n👤 <b>QO‘LLAB-QUVVATLASH</b>\n@omono_v",
        "lang_changed": "✅ Til o‘zgartirildi: O‘zbekcha",
        "cert_found": "✅ <b>Sertifikat topildi</b>\n\n👤 {name}\n📊 IQ-style Score: <b>{score}</b>\n📅 Sana: {date}",
        "cert_not_found": "❌ Sertifikat topilmadi.",
        "maintenance": "🛠 Bot texnik xizmatda.",
        "start_first": "Iltimos, avval /start buyrug‘ini bosing.",
    },
    "ru": {
        "choose_lang": "🌐 Выберите язык:",
        "welcome": "👋 Привет, {name}!\n\n🧠 <b>IQ TEST BOT</b>\n\nПройдите тесты IQ, EQ и прокрастинации.\n\n👇 Нажмите кнопку",
        "menu_test": "🧠 Пройти тест IQ · EQ · PQ",
        "menu_cert": "📜 Мой сертификат",
        "menu_rank": "🏆 Рейтинг",
        "menu_earn": "💰 Заработок",
        "menu_help": "ℹ️ Цены и помощь",
        "menu_lang": "🌐 Язык",
        "no_cert": "📜 У вас пока нет сертификата.",
        "ranking_title": "🏆 <b>РЕЙТИНГ</b>\n\n",
        "earn_title": "💰 <b>ЗАРАБОТОК</b>\n\n🔗 {link}\n\n👥 Приглашено: <b>{count}</b>",
        "help": "ℹ️ <b>ЦЕНЫ</b>\n\n🧠 IQ — {iq_price} сум\n🎭 EQ — бесплатно\n⏳ PQ — бесплатно\n🔄 Повтор IQ — {iq_retry} сум\n⚔️ Батл — {battle_price} сум\n\n👤 @omono_v",
        "lang_changed": "✅ Язык изменён: Русский",
        "cert_found": "✅ <b>Сертификат найден</b>\n\n👤 {name}\n📊 Score: <b>{score}</b>\n📅 {date}",
        "cert_not_found": "❌ Не найден.",
        "maintenance": "🛠 Бот на техобслуживании.",
        "start_first": "Сначала /start.",
    },
    "en": {
        "choose_lang": "🌐 Choose language:",
        "welcome": "👋 Hello, {name}!\n\n🧠 <b>IQ TEST BOT</b>\n\nTake IQ, EQ and procrastination tests.\n\n👇 Tap the button",
        "menu_test": "🧠 Take IQ · EQ · PQ test",
        "menu_cert": "📜 My Certificate",
        "menu_rank": "🏆 Ranking",
        "menu_earn": "💰 Earn Money",
        "menu_help": "ℹ️ Pricing & Help",
        "menu_lang": "🌐 Language",
        "no_cert": "📜 No certificate yet.",
        "ranking_title": "🏆 <b>RANKING</b>\n\n",
        "earn_title": "💰 <b>EARN</b>\n\n🔗 {link}\n\n👥 Invited: <b>{count}</b>",
        "help": "ℹ️ <b>PRICING</b>\n\n🧠 IQ — {iq_price} UZS\n🎭 EQ — free\n⏳ PQ — free\n🔄 Retry — {iq_retry} UZS\n⚔️ Battle — {battle_price} UZS\n\n👤 @omono_v",
        "lang_changed": "✅ Language: English",
        "cert_found": "✅ <b>Certificate found</b>\n\n👤 {name}\n📊 Score: <b>{score}</b>\n📅 {date}",
        "cert_not_found": "❌ Not found.",
        "maintenance": "🛠 Under maintenance.",
        "start_first": "Please /start first.",
    }
}

def t(lang: str, key: str, **kwargs):
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, TEXTS["uz"].get(key, key))
    return text.format(**kwargs) if kwargs else text


# ==================== IQ QUESTIONS (BACKEND ANSWER KEY) ====================
IQ_ANSWERS = [
    {"id": 1,  "correct": 2, "weight": 1, "category": "Raqamlar"},
    {"id": 2,  "correct": 0, "weight": 1, "category": "Pattern"},
    {"id": 3,  "correct": 3, "weight": 1, "category": "Fazoviy fikr"},
    {"id": 4,  "correct": 2, "weight": 1, "category": "Pattern"},
    {"id": 5,  "correct": 3, "weight": 1, "category": "Mantiq"},
    {"id": 6,  "correct": 1, "weight": 1, "category": "Pattern"},
    {"id": 7,  "correct": 1, "weight": 2, "category": "Pattern"},
    {"id": 8,  "correct": 2, "weight": 2, "category": "Fazoviy fikr"},
    {"id": 9,  "correct": 1, "weight": 2, "category": "Raqamlar"},
    {"id": 10, "correct": 1, "weight": 2, "category": "Mantiq"},
    {"id": 11, "correct": 1, "weight": 2, "category": "Pattern"},
    {"id": 12, "correct": 2, "weight": 2, "category": "Fazoviy fikr"},
    {"id": 13, "correct": 1, "weight": 3, "category": "Raqamlar"},
    {"id": 14, "correct": 0, "weight": 3, "category": "Pattern"},
    {"id": 15, "correct": 1, "weight": 3, "category": "Fazoviy fikr"},
    {"id": 16, "correct": 1, "weight": 3, "category": "Raqamlar"},
    {"id": 17, "correct": 2, "weight": 3, "category": "Mantiq"},
    {"id": 18, "correct": 1, "weight": 3, "category": "Pattern"},
]

EQ_ANSWERS = [
    {"id": 1, "scores": [4, 2, 3, 1], "category": "stress"},
    {"id": 2, "scores": [4, 1, 2, 1], "category": "empathy"},
    {"id": 3, "scores": [4, 3, 1, 1], "category": "self-awareness"},
    {"id": 4, "scores": [4, 2, 1, 2], "category": "conflict"},
    {"id": 5, "scores": [4, 2, 3, 1], "category": "emotion regulation"},
    {"id": 6, "scores": [4, 2, 1, 2], "category": "social perception"},
]

PQ_ANSWERS = [
    {"id": 1, "scores": [2, 1, 2, 1], "category": "task avoidance"},
    {"id": 2, "scores": [4, 2, 1, 0], "category": "delay"},
    {"id": 3, "scores": [4, 1, 2, 2], "category": "motivation"},
    {"id": 4, "scores": [4, 3, 1, 0], "category": "distraction"},
    {"id": 5, "scores": [4, 2, 1, 0], "category": "deadline"},
    {"id": 6, "scores": [4, 3, 1, 0], "category": "self-control"},
]


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
                gender TEXT,
                age INTEGER,
                country TEXT,
                full_name TEXT,
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
                status TEXT DEFAULT 'in_progress',
                payment_status TEXT DEFAULT 'free',
                result_visible BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_answers (
                id SERIAL PRIMARY KEY,
                attempt_id INTEGER NOT NULL,
                question_number INTEGER NOT NULL,
                answer INTEGER,
                is_correct BOOLEAN,
                time_spent INTEGER
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
                attempt_id INTEGER,
                battle_id INTEGER,
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
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
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
                type TEXT DEFAULT 'iq',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                id SERIAL PRIMARY KEY,
                battle_code TEXT UNIQUE NOT NULL,
                creator_id BIGINT NOT NULL,
                opponent_id BIGINT,
                status TEXT DEFAULT 'waiting_for_player',
                winner_id BIGINT,
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
                session_id TEXT,
                current_question INTEGER DEFAULT 0,
                answers JSONB,
                score INTEGER,
                weighted INTEGER,
                finished_at TIMESTAMPTZ,
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

        # MIGRATIONS
        migrations = [
            "ALTER TABLE users ALTER COLUMN last_name DROP NOT NULL",
            "ALTER TABLE users ALTER COLUMN username DROP NOT NULL",
            "ALTER TABLE users ALTER COLUMN first_name DROP NOT NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT",
            "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS bank TEXT",
            "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS answers JSONB",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS test_status TEXT DEFAULT 'not_started'",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'pending'",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS session_id TEXT",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS current_question INTEGER DEFAULT 0",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS weighted INTEGER",
            "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ",
            "ALTER TABLE battles ADD COLUMN IF NOT EXISTS winner_id BIGINT",
            "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS battle_id INTEGER",
            "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
            "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'free'",
            "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS result_visible BOOLEAN DEFAULT TRUE",
            "ALTER TABLE results ADD COLUMN IF NOT EXISTS level TEXT",
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS attempt_id INTEGER",
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS battle_id INTEGER",
            "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'iq'",
        ]
        for m in migrations:
            try:
                await conn.execute(m)
            except Exception as e:
                logger.warning(f"Migration skip: {e}")

        # Default settings
        defaults = {
            "iq_price": "10000",
            "iq_retry_price": "5000",
            "eq_price": "0",
            "eq_retry_price": "5000",
            "pq_price": "0",
            "pq_retry_price": "5000",
            "battle_price": "7500",
            "free_launch_end": "2026-09-30",
            "support_username": "omono_v",
            "maintenance_mode": "0",
            "live_mode": "fake",
            "live_fake_base": "95114",
            "live_fake_online": "342",
            "live_fake_interval": "3",
            "live_fake_delta": "8",
            "live_real_online_minutes": "5",
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

        cnt = await conn.fetchval("SELECT COUNT(*) FROM payment_cards")
        if cnt == 0:
            await conn.execute("""
                INSERT INTO payment_cards (card_number, holder, bank, active)
                VALUES ('8600 1234 5678 9012', 'IQ TEST BOT', 'Click', TRUE)
            """)

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
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(chars, k=4))

def validate_init_data(init_data: str, bot_token: str):
    try:
        if not init_data:
            logger.warning("INITDATA_EMPTY")
            return None
        parsed = {}
        for pair in init_data.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                parsed[k] = unquote(v)

        hash_val = parsed.pop("hash", None)
        if not hash_val:
            logger.warning("NO_HASH")
            return None

        # signature chiqarib tashlanadi
        parsed.pop("signature", None)

        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        # ===== HMAC DEBUG =====
        logger.warning("=" * 60)
        logger.warning(f"HMAC_DEBUG token_len={len(bot_token)}")
        logger.warning(f"HMAC_DEBUG token_repr={repr(bot_token)}")
        logger.warning(f"HMAC_DEBUG data_check_first200={data_check[:200]}")
        logger.warning(f"HMAC_DEBUG data_check_last100={data_check[-100:]}")
        logger.warning(f"HMAC_DEBUG calc={calc}")
        logger.warning(f"HMAC_DEBUG got ={hash_val}")
        logger.warning(f"HMAC_DEBUG MATCH={calc == hash_val}")
        logger.warning("=" * 60)
        # ======================

        if calc != hash_val:
            logger.warning("HMAC_FAIL")
            return None

        auth_date = int(parsed.get("auth_date", "0"))
        if datetime.now(timezone.utc).timestamp() - auth_date > 86400 * 2:
            logger.warning("EXPIRED")
            return None

        user = json.loads(parsed.get("user", "{}"))
        return user
    except Exception as e:
        logger.error(f"validate_init_data error: {e}")
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
        """, key, str(value))

async def get_setting_int(key: str, default: int = 0) -> int:
    v = await get_setting(key, str(default))
    try:
        return int(v)
    except:
        return default

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


# ==================== BOT ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ==================== /start ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    try:
        await upsert_user(message.from_user)
        user = await get_user(message.from_user.id)
        args = message.text.split()
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
    except Exception as e:
        logger.error(f"cmd_start error: {e}")


@dp.callback_query(F.data.startswith("lang:"))
async def cb_lang(cb: CallbackQuery):
    try:
        lang = cb.data.split(":")[1]
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE users SET language=$1 WHERE user_id=$2", lang, cb.from_user.id)
        await cb.message.edit_text(t(lang, "lang_changed"))
        await cb.message.answer(
            t(lang, "welcome", name=cb.from_user.first_name or "do‘stim"),
            reply_markup=main_menu_kb(lang)
        )
    except Exception as e:
        logger.error(f"cb_lang error: {e}")
    await cb.answer()


# ==================== MENU HANDLERS ====================
@dp.message(F.text.in_([TEXTS["uz"]["menu_cert"], TEXTS["ru"]["menu_cert"], TEXTS["en"]["menu_cert"]]))
async def menu_cert(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        lang = user["language"] if user else "uz"
        async with db_pool.acquire() as conn:
            cert = await conn.fetchrow("""
                SELECT c.*, u.full_name, u.first_name
                FROM certificates c
                JOIN users u ON u.user_id = c.user_id
                WHERE c.user_id=$1 AND c.type='iq'
                ORDER BY c.created_at DESC LIMIT 1
            """, message.from_user.id)
        if not cert:
            await message.answer(t(lang, "no_cert"))
            return
        name = cert["full_name"] or cert["first_name"] or "User"
        png = generate_iq_certificate_png(
            name=name,
            score=cert["score"],
            code=cert["verification_code"],
            date=cert["created_at"].strftime("%d.%m.%Y")
        )
        await message.answer_document(BufferedInputFile(png, filename=f"{cert['verification_code']}.png"))
    except Exception as e:
        logger.error(f"menu_cert error: {e}")


@dp.message(F.text.in_([TEXTS["uz"]["menu_rank"], TEXTS["ru"]["menu_rank"], TEXTS["en"]["menu_rank"]]))
async def menu_rank(message: types.Message):
    try:
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
    except Exception as e:
        logger.error(f"menu_rank error: {e}")


@dp.message(F.text.in_([TEXTS["uz"]["menu_earn"], TEXTS["ru"]["menu_earn"], TEXTS["en"]["menu_earn"]]))
async def menu_earn(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        lang = user["language"] if user else "uz"
        async with db_pool.acquire() as conn:
            cnt = await conn.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", message.from_user.id)
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
        await message.answer(t(lang, "earn_title", link=link, count=cnt))
    except Exception as e:
        logger.error(f"menu_earn error: {e}")


@dp.message(F.text.in_([TEXTS["uz"]["menu_help"], TEXTS["ru"]["menu_help"], TEXTS["en"]["menu_help"]]))
async def menu_help(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        lang = user["language"] if user else "uz"
        iq_price = await get_setting("iq_price", "10000")
        iq_retry = await get_setting("iq_retry_price", "5000")
        battle_price = await get_setting("battle_price", "7500")
        await message.answer(t(lang, "help", iq_price=iq_price, iq_retry=iq_retry, battle_price=battle_price))
    except Exception as e:
        logger.error(f"menu_help error: {e}")


@dp.message(F.text.in_([TEXTS["uz"]["menu_lang"], TEXTS["ru"]["menu_lang"], TEXTS["en"]["menu_lang"]]))
async def menu_lang(message: types.Message):
    try:
        await message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())
    except Exception as e:
        logger.error(f"menu_lang error: {e}")


# ==================== CERTIFICATE VERIFICATION ====================
@dp.message(F.text.regexp(r"^IQ-[A-Z0-9]{6}$"))
async def verify_cert(message: types.Message):
    try:
        code = message.text.strip()
        async with db_pool.acquire() as conn:
            cert = await conn.fetchrow("""
                SELECT c.*, u.first_name, u.full_name FROM certificates c
                JOIN users u ON u.user_id = c.user_id                WHERE c.verification_code=$1
            """, code)
        if not cert:
            await message.answer(t("uz", "cert_not_found"))
            return
        name = cert["full_name"] or cert["first_name"] or "User"
        await message.answer(t("uz", "cert_found",
            name=name,
            score=cert["score"],
            date=cert["created_at"].strftime("%d.%m.%Y")
        ))
    except Exception as e:
        logger.error(f"verify_cert error: {e}")


# ==================== CERTIFICATE PNG ====================
def generate_iq_certificate_png(name: str, score: int, code: str, date: str) -> bytes:
    W, H = 1600, 1100
    img = Image.new("RGB", (W, H), "#0a0e1a")
    draw = ImageDraw.Draw(img)

    for y in range(H):
        ratio = y / H
        r = int(10 + 20 * ratio)
        g = int(14 + 20 * ratio)
        b = int(26 + 40 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw.rectangle([30, 30, W-30, H-30], outline="#d4af37", width=6)
    draw.rectangle([50, 50, W-50, H-50], outline="#d4af37", width=2)

    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 110)
        f_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 80)
        f_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
        f_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
        f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        f_title = f_name = f_score = f_label = f_small = ImageFont.load_default()

    def center(text, font, y, fill="#d4af37"):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=font, fill=fill)

    center("SERTIFIKAT", f_title, 120, "#d4af37")
    center("AQLLIY SALOHIYAT TO‘G‘RISIDA", f_label, 260, "#c9a227")
    draw.line([(300, 420), (W-300, 420)], fill="#d4af37", width=2)
    center(name, f_name, 320, "#ffffff")
    draw.line([(300, 440), (W-300, 440)], fill="#d4af37", width=2)
    center("IQ-STYLE SCORE", f_label, 490, "#c9a227")
    center(str(score), f_score, 540, "#ffffff")
    if score >= 130:
        level = "JUDA YUQORI"
    elif score >= 115:
        level = "YUQORI DARAJA"
    elif score >= 100:
        level = "O‘RTA DARAJA"
    else:
        level = "RIVOJLANTIRISH KERAK"
    center(level, f_label, 800, "#d4af37")
    draw.text((150, H-150), f"Sana: {date}", font=f_small, fill="#c9a227")
    draw.text((150, H-100), f"Kod: {code}", font=f_small, fill="#c9a227")
    draw.text((W-450, H-100), "IQ TEST BOT", font=f_small, fill="#c9a227")

    seal_x, seal_y = W - 220, 220
    draw.ellipse([seal_x-100, seal_y-100, seal_x+100, seal_y+100], outline="#d4af37", width=6)
    draw.ellipse([seal_x-85, seal_y-85, seal_x+85, seal_y+85], outline="#d4af37", width=2)
    bbox = draw.textbbox((0, 0), "VERIFIED", font=f_small)
    draw.text((seal_x - (bbox[2]-bbox[0])/2, seal_y - 15), "VERIFIED", font=f_small, fill="#d4af37")

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
        logger.info(f"Webhook set: {PUBLIC_BASE_URL}/telegram/webhook")
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
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>webapp/index.html not found</h1>", status_code=404)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"webhook error: {e}")
    return {"ok": True}


# ==================== AUTH ====================
def get_user_from_init(init_data: str):
    return validate_init_data(init_data, BOT_TOKEN)

async def require_user(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    return user, body


# ==================== /api/me ====================
@app.post("/api/me")
async def api_me(request: Request):
    user, body = await require_user(request)
    uid = user["id"]
    async with db_pool.acquire() as conn:
        u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
        if not u:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
            """, uid, user.get("username"), user.get("first_name"), user.get("last_name"))
        results = await conn.fetch("""
            SELECT test_type, MAX(score) as best FROM results
            WHERE user_id=$1 AND test_type IN ('iq','eq','pq')
            GROUP BY test_type
        """, uid)
        active_sessions = await conn.fetch("""
            SELECT * FROM test_sessions
            WHERE user_id=$1 AND status='active' AND expires_at > NOW()
        """, uid)
        pending_payments = await conn.fetch("""
            SELECT * FROM payments WHERE user_id=$1 AND status='pending'
        """, uid)
        active_battles = await conn.fetch("""
            SELECT b.* FROM battles b
            JOIN battle_players bp ON bp.battle_id = b.id
            WHERE bp.user_id=$1 AND b.status NOT IN ('completed','draw','cancelled')
        """, uid)
    completed = {}
    for r in results:
        completed[r["test_type"]] = r["best"]
    return {
        "ok": True,
        "user": {
            "user_id": uid,
            "first_name": user.get("first_name"),
            "language": u["language"] if u else "uz",
            "gender": u["gender"] if u else None,
            "age": u["age"] if u else None,
            "country": u["country"] if u else None,
            "full_name": u["full_name"] if u else None,
        },
        "completed": completed,
        "active_sessions": [dict(s) for s in active_sessions],
        "pending_payments": [dict(p) for p in pending_payments],
        "active_battles": [dict(b) for b in active_battles],
    }


# ==================== /api/profile/save ====================
@app.post("/api/profile/save")
async def api_profile_save(request: Request):
    user, body = await require_user(request)
    full_name = body.get("full_name", "").strip()
    gender = body.get("gender")
    age = body.get("age")
    country = body.get("country")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET full_name=$1, gender=$2, age=$3, country=$4
            WHERE user_id=$5
        """, full_name, gender, age, country, user["id"])
    return {"ok": True}


# ==================== /api/stats/live ====================
@app.get("/api/stats/live")
async def api_stats_live():
    mode = await get_setting("live_mode", "fake")
    if mode == "real":
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            minutes = await get_setting_int("live_real_online_minutes", 5)
            online = await conn.fetchval(
                f"SELECT COUNT(*) FROM users WHERE last_seen > NOW() - INTERVAL '{minutes} minutes'"
            ) or 0
    else:
        base_total = await get_setting_int("live_fake_base", 95114)
        base_online = await get_setting_int("live_fake_online", 342)
        delta = await get_setting_int("live_fake_delta", 8)
        total = base_total + random.randint(-delta, delta)
        online = base_online + random.randint(-delta, delta)
    return {"ok": True, "total": total, "online": online, "mode": mode}


# ==================== /api/config ====================
@app.get("/api/config")
async def api_config():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM app_settings")
    return {"ok": True, "settings": {r["key"]: r["value"] for r in rows}}


# ==================== /api/session/start ====================
@app.post("/api/session/start")
async def api_session_start(request: Request):
    user, body = await require_user(request)
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


# ==================== /api/test/submit ====================
@app.post("/api/test/submit")
async def api_test_submit(request: Request):
    user, body = await require_user(request)
    sid = body.get("session_id")
    answers = body.get("answers", [])
    duration = body.get("duration", 0)

    async with db_pool.acquire() as conn:
        sess = await conn.fetchrow("SELECT * FROM test_sessions WHERE session_id=$1 AND user_id=$2", sid, user["id"])
        if not sess:
            raise HTTPException(404, "Session not found")
        if sess["status"] != "active":
            raise HTTPException(409, "Session already submitted")
        attempt = await conn.fetchrow("SELECT * FROM test_attempts WHERE session_id=$1", sid)
        if not attempt or attempt["status"] == "completed":
            raise HTTPException(409, "Attempt already completed")

        test_type = sess["test_type"]
        score = 0
        correct = 0
        level = ""
        weighted = 0
        payment_status = "free"
        result_visible = True

        if test_type == "iq":
            max_w = 0
            for i, q in enumerate(IQ_ANSWERS):
                max_w += q["weight"]
                ans = answers[i] if i < len(answers) and answers[i] is not None else None
                if ans == q["correct"]:
                    weighted += q["weight"]
                    correct += 1
            score = int(70 + (weighted / max_w) * 60) if max_w else 70
            level = "YUQORI DARAJA" if score >= 115 else ("O‘RTA DARAJA" if score >= 100 else "RIVOJLANTIRISH")
            iq_price = await get_setting_int("iq_price", 10000)
            if iq_price > 0:
                payment_status = "pending"
                result_visible = False

        elif test_type == "eq":
            total = 0
            for i, q in enumerate(EQ_ANSWERS):
                ans = answers[i] if i < len(answers) and answers[i] is not None else None
                if ans is not None and 0 <= ans < len(q["scores"]):
                    total += q["scores"][ans]
            max_score = len(EQ_ANSWERS) * 4
            score = int((total / max_score) * 100) if max_score else 0
            correct = score
            level = "JUDA YUQORI" if score >= 80 else ("YUQORI" if score >= 60 else ("O‘RTA" if score >= 40 else "RIVOJLANTIRISH"))

        elif test_type == "pq":
            total = 0
            for i, q in enumerate(PQ_ANSWERS):
                ans = answers[i] if i < len(answers) and answers[i] is not None else None
                if ans is not None and 0 <= ans < len(q["scores"]):
                    total += q["scores"][ans]
            max_score = len(PQ_ANSWERS) * 4
            score = int((total / max_score) * 100) if max_score else 0
            correct = score
            level = "JUDA YAXSHI" if score >= 80 else ("YAXSHI" if score >= 60 else ("O‘RTA" if score >= 40 else "RIVOJLANTIRISH"))

        await conn.execute("""
            UPDATE test_attempts
            SET finished_at=NOW(), score=$1, correct_count=$2, duration=$3, status='completed',
                payment_status=$4, result_visible=$5
            WHERE id=$6
        """, score, correct, duration, payment_status, result_visible, attempt["id"])

        for i, a in enumerate(answers):
            await conn.execute("""
                INSERT INTO test_answers (attempt_id, question_number, answer, is_correct)
                VALUES ($1, $2, $3, $4)
            """, attempt["id"], i + 1, a, None)

        await conn.execute("UPDATE test_sessions SET status='completed' WHERE session_id=$1", sid)

        res = await conn.fetchrow("""
            INSERT INTO results (user_id, attempt_id, test_type, score, level)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, user["id"], attempt["id"], test_type, score, level)

        certificate_code = None
        if test_type == "iq" and result_visible:
            certificate_code = gen_code("IQ")
            await conn.execute("""
                INSERT INTO certificates (certificate_id, verification_code, user_id, result_id, score, type)
                VALUES ($1, $2, $3, $4, $5, 'iq')
            """, gen_code("CERT"), certificate_code, user["id"], res["id"], score)

    return {
        "ok": True,
        "score": score,
        "correct": correct,
        "total": len(answers),
        "level": level,
        "weighted": weighted,
        "result_visible": result_visible,
        "payment_required": payment_status == "pending",
        "attempt_id": attempt["id"],
        "certificate_code": certificate_code,
    }


# ==================== /api/certificate/{code} ====================
@app.get("/api/certificate/{code}")
async def api_certificate(code: str):
    async with db_pool.acquire() as conn:
        cert = await conn.fetchrow("""
            SELECT c.*, u.first_name, u.full_name FROM certificates c
            JOIN users u ON u.user_id = c.user_id
            WHERE c.verification_code=$1
        """, code)
    if not cert:
        return {"ok": False, "error": "NOT_FOUND"}
    return {"ok": True, "certificate": {
        "code": cert["verification_code"],
        "name": cert["full_name"] or cert["first_name"],
        "score": cert["score"],
        "date": cert["created_at"].strftime("%d.%m.%Y"),
    }}


# ==================== 2-QISM BOSHLANADI ====================
# Quyidagi qismni AVVALGI javobdan (2-QISM) oling:
# - Battle API
# - Payment API
# - Admin panel
# - Certificate battle PNG
# - Runner
#
# 2-QISM ni SHU YERGA paste qiling.