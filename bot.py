# bot.py
# IQ TEST BOT — Professional Backend
# Part 1/2: Core, DB, IQ, EQ, PQ, Auth

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

db_pool: asyncpg.Pool = None
online_tracker = {}  # {user_id: last_seen_timestamp}


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
# 18 ta savol — Mensa/Raven standartida
# Frontend bilan 100% mos
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
        # users
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
        # admins
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # app_settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # test_sessions
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
        # test_attempts
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
        # test_answers
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
        # results
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
        # payments
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
        # payment_cards
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
        # certificates
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
        # battles
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
        # battle_players
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
        # referrals
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(referred_id)
            )
        """)

        # ===== MIGRATIONS =====
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
            return None
        parsed = {}
        for pair in init_data.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                parsed[k] = unquote(v)
        hash_val = parsed.pop("hash", None)
        if not hash_val:
            return None
        parsed.pop("signature", None)
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if calc != hash_val:
            logger.warning(f"HMAC FAIL token={bot_token[:10]}...")
            return None
        auth_date = int(parsed.get("auth_date", "0"))
        if datetime.now(timezone.utc).timestamp() - auth_date > 86400 * 2:
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
                JOIN users u ON u.user_id = c.user_id
                WHERE c.verification_code=$1
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
    # Live counter fake updater
    asyncio.create_task(live_counter_updater())
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
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"webhook error: {e}")
    return {"ok": True}


# ==================== AUTH HELPER ====================
def get_user_from_init(init_data: str):
    return validate_init_data(init_data, BOT_TOKEN)


async def require_user(request: Request):
    body = await request.json()
    user = get_user_from_init(body.get("initData", ""))
    if not user:
        raise HTTPException(401, "Unauthorized")
    return user, body


# ==================== API: ME ====================
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


# ==================== API: PROFILE SAVE ====================
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


# ==================== API: LIVE STATS ====================
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


# ==================== API: CONFIG ====================
@app.get("/api/config")
async def api_config():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM app_settings")
    return {"ok": True, "settings": {r["key"]: r["value"] for r in rows}}


# ==================== API: SESSION START ====================
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


# ==================== API: TEST SUBMIT ====================
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


# ==================== API: CERTIFICATE GET ====================
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


# ==================== LIVE COUNTER UPDATER ====================
async def live_counter_updater():
    """Fake live counter uchun background task"""
    while True:
        try:
            await asyncio.sleep(3)
        except:
            break
            
            # ==================== 2-QISM: BATTLE, PAYMENT, ADMIN, RUNNER ====================

# ==================== BATTLE API ====================

@app.post("/api/battle/create")
async def api_battle_create(request: Request):
    user, body = await require_user(request)
    price = await get_setting_int("battle_price", 7500)
    async with db_pool.acquire() as conn:
        # Faol battle borligini tekshirish
        existing = await conn.fetchrow("""
            SELECT b.* FROM battles b
            JOIN battle_players bp ON bp.battle_id = b.id
            WHERE bp.user_id=$1 AND b.status NOT IN ('completed','draw','cancelled')
        """, user["id"])
        if existing:
            return {"ok": False, "error": "ACTIVE_BATTLE_EXISTS", "battle_id": existing["id"], "code": existing["battle_code"]}

        code = gen_battle_code()
        for _ in range(10):
            chk = await conn.fetchval("SELECT 1 FROM battles WHERE battle_code=$1 AND status IN ('waiting_for_player','waiting_for_payment','ready','in_progress')", code)
            if not chk:
                break
            code = gen_battle_code()

        b = await conn.fetchrow("""
            INSERT INTO battles (battle_code, creator_id, status)
            VALUES ($1, $2, 'waiting_for_player') RETURNING id
        """, code, user["id"])
        await conn.execute("""
            INSERT INTO battle_players (battle_id, user_id, payment_status, test_status)
            VALUES ($1, $2, 'pending', 'not_started')
        """, b["id"], user["id"])
    return {"ok": True, "battle_id": b["id"], "code": code, "price": price}


@app.post("/api/battle/join")
async def api_battle_join(request: Request):
    user, body = await require_user(request)
    code = body.get("code", "").strip().upper()
    if not code:
        raise HTTPException(400, "Code required")
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE battle_code=$1", code)
        if not b:
            return {"ok": False, "error": "NOT_FOUND"}
        if b["creator_id"] == user["id"]:
            return {"ok": False, "error": "OWN_BATTLE"}
        if b["status"] not in ("waiting_for_player",):
            return {"ok": False, "error": "BATTLE_NOT_OPEN"}
        if b["opponent_id"]:
            return {"ok": False, "error": "BATTLE_FULL"}

        # Faol battle tekshiruvi
        existing = await conn.fetchrow("""
            SELECT b2.* FROM battles b2
            JOIN battle_players bp ON bp.battle_id = b2.id
            WHERE bp.user_id=$1 AND b2.status NOT IN ('completed','draw','cancelled')
        """, user["id"])
        if existing:
            return {"ok": False, "error": "ACTIVE_BATTLE_EXISTS"}

        await conn.execute("""
            UPDATE battles SET opponent_id=$1, status='waiting_for_payment' WHERE id=$2
        """, user["id"], b["id"])
        await conn.execute("""
            INSERT INTO battle_players (battle_id, user_id, payment_status, test_status)
            VALUES ($1, $2, 'pending', 'not_started')
            ON CONFLICT (battle_id, user_id) DO NOTHING
        """, b["id"], user["id"])
    return {"ok": True, "battle_id": b["id"]}


@app.post("/api/battle/{battle_id}")
async def api_battle_get(battle_id: int, request: Request):
    user, body = await require_user(request)
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE id=$1", battle_id)
        if not b:
            raise HTTPException(404, "Not found")
        players = await conn.fetch("""
            SELECT bp.user_id, bp.payment_status, bp.test_status, bp.score, bp.current_question,
                   u.first_name, u.username, u.full_name
            FROM battle_players bp
            JOIN users u ON u.user_id = bp.user_id
            WHERE bp.battle_id=$1
        """, battle_id)
        is_member = any(p["user_id"] == user["id"] for p in players)
        if not is_member:
            raise HTTPException(403, "Not a battle member")

    # Raqib progressini ko'rsatish (faqat current_question, score emas)
    players_out = []
    for p in players:
        item = {
            "user_id": p["user_id"],
            "payment_status": p["payment_status"],
            "test_status": p["test_status"],
            "current_question": p["current_question"] or 0,
            "name": p["full_name"] or p["first_name"] or p["username"] or "User",
            "is_me": p["user_id"] == user["id"],
        }
        # Faqat test tugagan bo'lsa score ko'rsatiladi
        if p["test_status"] == "completed" and b["status"] in ("completed", "draw"):
            item["score"] = p["score"]
        players_out.append(item)

    return {
        "ok": True,
        "battle": {
            "id": b["id"],
            "code": b["battle_code"],
            "status": b["status"],
            "creator_id": b["creator_id"],
            "opponent_id": b["opponent_id"],
            "winner_id": b["winner_id"],
            "created_at": b["created_at"].isoformat() if b["created_at"] else None,
        },
        "players": players_out,
    }


@app.post("/api/battle/{battle_id}/sync")
async def api_battle_sync(battle_id: int, request: Request):
    """Local progressni serverga yuborish (offline-first)"""
    user, body = await require_user(request)
    current = body.get("current_question", 0)
    answers = body.get("answers", [])
    async with db_pool.acquire() as conn:
        bp = await conn.fetchrow("""
            SELECT * FROM battle_players WHERE battle_id=$1 AND user_id=$2
        """, battle_id, user["id"])
        if not bp:
            raise HTTPException(403, "Not a battle member")
        await conn.execute("""
            UPDATE battle_players
            SET current_question=$1, answers=$2::jsonb, test_status='in_progress'
            WHERE battle_id=$3 AND user_id=$4
        """, current, json.dumps(answers), battle_id, user["id"])
    return {"ok": True}


@app.post("/api/battle/{battle_id}/start")
async def api_battle_start(battle_id: int, request: Request):
    """Testni boshlash — ikkala payment approved bo'lsa"""
    user, body = await require_user(request)
    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE id=$1", battle_id)
        if not b:
            raise HTTPException(404, "Not found")
        players = await conn.fetch("SELECT * FROM battle_players WHERE battle_id=$1", battle_id)
        if len(players) < 2:
            return {"ok": False, "error": "WAITING_FOR_PLAYER"}
        if not all(p["payment_status"] == "approved" for p in players):
            return {"ok": False, "error": "WAITING_FOR_PAYMENT"}
        if b["status"] == "ready":
            await conn.execute("UPDATE battles SET status='in_progress' WHERE id=$1", battle_id)
        # Session yaratish (agar yo'q bo'lsa)
        bp = await conn.fetchrow("SELECT * FROM battle_players WHERE battle_id=$1 AND user_id=$2", battle_id, user["id"])
        if not bp["session_id"]:
            sid = gen_session_id()
            await conn.execute("""
                UPDATE battle_players SET session_id=$1 WHERE battle_id=$2 AND user_id=$3
            """, sid, battle_id, user["id"])
        else:
            sid = bp["session_id"]
    return {"ok": True, "session_id": sid, "battle_status": "in_progress"}


@app.post("/api/battle/{battle_id}/finish")
async def api_battle_finish(battle_id: int, request: Request):
    user, body = await require_user(request)
    answers = body.get("answers", [])
    duration = body.get("duration", 0)

    async with db_pool.acquire() as conn:
        b = await conn.fetchrow("SELECT * FROM battles WHERE id=$1", battle_id)
        if not b:
            raise HTTPException(404, "Not found")
        bp = await conn.fetchrow("SELECT * FROM battle_players WHERE battle_id=$1 AND user_id=$2", battle_id, user["id"])
        if not bp:
            raise HTTPException(403, "Not a battle member")
        if bp["test_status"] == "completed":
            raise HTTPException(409, "Already finished")

        # Backend score hisoblash
        weighted = 0
        max_w = 0
        correct = 0
        for i, q in enumerate(IQ_ANSWERS):
            max_w += q["weight"]
            ans = answers[i] if i < len(answers) and answers[i] is not None else None
            if ans == q["correct"]:
                weighted += q["weight"]
                correct += 1
        score = int(70 + (weighted / max_w) * 60) if max_w else 70

        await conn.execute("""
            UPDATE battle_players
            SET score=$1, weighted=$2, answers=$3::jsonb, test_status='completed',
                current_question=18, finished_at=NOW()
            WHERE battle_id=$4 AND user_id=$5
        """, score, weighted, json.dumps(answers), battle_id, user["id"])

        # Ikkalasi tugatganmi?
        all_players = await conn.fetch("SELECT * FROM battle_players WHERE battle_id=$1", battle_id)
        completed = [p for p in all_players if p["test_status"] == "completed"]

        opponent_score = None
        winner_id = None
        final_status = None

        if len(completed) >= 2:
            p1 = completed[0]
            p2 = completed[1]
            opponent_score = p2["score"] if p1["user_id"] == user["id"] else p1["score"]

            if p1["score"] > p2["score"]:
                winner_id = p1["user_id"]
                final_status = "completed"
            elif p2["score"] > p1["score"]:
                winner_id = p2["user_id"]
                final_status = "completed"
            else:
                winner_id = None
                final_status = "draw"

            await conn.execute("""
                UPDATE battles SET status=$1, winner_id=$2, finished_at=NOW() WHERE id=$3
            """, final_status, winner_id, battle_id)

            # Battle sertifikat (faqat g'olibga, durang bo'lmasa)
            if winner_id:
                winner_bp = next(p for p in completed if p["user_id"] == winner_id)
                winner_score = winner_bp["score"]
                await conn.execute("""
                    INSERT INTO certificates (certificate_id, verification_code, user_id, result_id, score, type)
                    VALUES ($1, $2, $3, 0, $4, 'battle')
                """, gen_code("CERT"), gen_code("BT"), winner_id, winner_score)

                # G'olibga xabar yuborish
                try:
                    await bot.send_message(
                        winner_id,
                        f"🏆 <b>BATTLE G‘ALABASI!</b>\n\nSiz battle’da g‘olib bo‘ldingiz!\n\nSertifikat: /start → 📜 Sertifikatim"
                    )
                except Exception:
                    pass
            else:
                try:
                    await bot.send_message(user["id"], "🤝 <b>DURANG!</b>\n\nIkkalangizning natijangiz bir xil.")
                except Exception:
                    pass
        else:
            final_status = b["status"]
            # Opponent hali tugatmagan
            await conn.execute("UPDATE battles SET status='player_1_finished' WHERE id=$1", battle_id)

    return {
        "ok": True,
        "score": score,
        "weighted": weighted,
        "correct": correct,
        "opponent_score": opponent_score,
        "winner_id": winner_id,
        "final_status": final_status,
    }


# ==================== PAYMENT API ====================

@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    user, body = await require_user(request)
    product = body.get("product")
    attempt_id = body.get("attempt_id")
    battle_id = body.get("battle_id")

    price_map = {
        "iq": await get_setting_int("iq_price", 10000),
        "iq_retry": await get_setting_int("iq_retry_price", 5000),
        "eq": await get_setting_int("eq_price", 0),
        "eq_retry": await get_setting_int("eq_retry_price", 5000),
        "pq": await get_setting_int("pq_price", 0),
        "pq_retry": await get_setting_int("pq_retry_price", 5000),
        "battle": await get_setting_int("battle_price", 7500),
    }
    amount = price_map.get(product)
    if amount is None:
        raise HTTPException(400, "Invalid product")

    # BEPUL bo'lsa, to'lov yaratmasdan darhol OK
    if amount == 0:
        if product == "iq" and attempt_id:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE test_attempts SET payment_status='free', result_visible=TRUE WHERE id=$1
                """, attempt_id)
        return {"ok": True, "free": True, "amount": 0}

    # Duplicate pending payment tekshiruvi
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow("""
            SELECT payment_id FROM payments
            WHERE user_id=$1 AND product=$2 AND status='pending'
            AND COALESCE(attempt_id,0)=COALESCE($3,0) AND COALESCE(battle_id,0)=COALESCE($4,0)
            ORDER BY created_at DESC LIMIT 1
        """, user["id"], product, attempt_id, battle_id)
        if existing:
            pid = existing["payment_id"]
        else:
            pid = gen_payment_id()
            await conn.execute("""
                INSERT INTO payments (payment_id, user_id, product, amount, attempt_id, battle_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, pid, user["id"], product, amount, attempt_id, battle_id)

        cards = await conn.fetch("SELECT card_number, holder, bank FROM payment_cards WHERE active=TRUE")

    return {"ok": True, "payment_id": pid, "amount": amount, "cards": [dict(c) for c in cards]}


@app.post("/api/payment/receipt")
async def api_payment_receipt(request: Request):
    user, body = await require_user(request)
    pid = body.get("payment_id")
    file_id = body.get("file_id")
    if not pid or not file_id:
        raise HTTPException(400, "Missing fields")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE payments SET receipt_file_id=$1
            WHERE payment_id=$2 AND user_id=$3 AND status='pending'
        """, file_id, pid, user["id"])
        p = await conn.fetchrow("SELECT * FROM payments WHERE payment_id=$1", pid)
    # Adminga xabar
    if ADMIN_USER_ID and p:
        try:
            await bot.send_message(
                ADMIN_USER_ID,
                f"💳 <b>Yangi chek!</b>\n\nUser: <code>{user['id']}</code>\nProduct: <b>{p['product']}</b>\nAmount: <b>{p['amount']:,} so‘m</b>\n\n/admin → Payments"
            )
        except Exception:
            pass
    return {"ok": True}


@app.post("/api/payment/{payment_id}")
async def api_payment_get(payment_id: str, request: Request):
    user, body = await require_user(request)
    async with db_pool.acquire() as conn:
        p = await conn.fetchrow("""
            SELECT * FROM payments WHERE payment_id=$1 AND user_id=$2
        """, payment_id, user["id"])
    if not p:
        raise HTTPException(404, "Not found")
    return {"ok": True, "payment": {
        "payment_id": p["payment_id"],
        "product": p["product"],
        "amount": p["amount"],
        "status": p["status"],
        "created_at": p["created_at"].isoformat() if p["created_at"] else None,
    }}


@app.post("/api/result/check_payment")
async def api_result_check_payment(request: Request):
    """IQ natija ko'rinishi uchun payment tekshiruvi"""
    user, body = await require_user(request)
    attempt_id = body.get("attempt_id")
    if not attempt_id:
        raise HTTPException(400, "attempt_id required")
    async with db_pool.acquire() as conn:
        attempt = await conn.fetchrow("""
            SELECT * FROM test_attempts WHERE id=$1 AND user_id=$2
        """, attempt_id, user["id"])
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    return {
        "ok": True,
        "payment_status": attempt["payment_status"],
        "result_visible": attempt["result_visible"],
    }


# ==================== ADMIN PANEL ====================

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
    b.button(text="💳 Cards", callback_data="admin:cards")
    b.button(text="🎯 Live Counter", callback_data="admin:live")
    b.button(text="⚙️ Settings", callback_data="admin:settings")
    b.adjust(2, 2, 2, 2, 2, 1)
    return b.as_markup()


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("👑 <b>ADMIN PANEL</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin:menu")
async def admin_menu(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        await cb.message.edit_text("👑 <b>ADMIN PANEL</b>", reply_markup=admin_kb())
    except Exception:
        await cb.message.answer("👑 <b>ADMIN PANEL</b>", reply_markup=admin_kb())
    await cb.answer()


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            today = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at::date = NOW()::date") or 0
            iq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='iq'") or 0
            eq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='eq'") or 0
            pq = await conn.fetchval("SELECT COUNT(*) FROM results WHERE test_type='pq'") or 0
            pay = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status='approved'") or 0
            rev = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'") or 0
            battles = await conn.fetchval("SELECT COUNT(*) FROM battles") or 0
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
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_stats error: {e}")
    await cb.answer()


@dp.callback_query(F.data == "admin:users")
async def admin_users(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, first_name, username, language, created_at FROM users ORDER BY created_at DESC LIMIT 20")
        text = "👥 <b>USERS (oxirgi 20)</b>\n\n"
        for r in rows:
            name = r["first_name"] or r["username"] or "?"
            text += f"• <code>{r['user_id']}</code> — {name} [{r['language']}]\n"
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_users error: {e}")
    await cb.answer()


@dp.callback_query(F.data == "admin:payments")
async def admin_payments(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC LIMIT 20")
        if not rows:
            b = InlineKeyboardBuilder()
            b.button(text="⬅️ Orqaga", callback_data="admin:menu")
            await cb.message.edit_text("💳 Pending payments yo‘q.", reply_markup=b.as_markup())
            await cb.answer()
            return
        for p in rows:
            bb = InlineKeyboardBuilder()
            bb.button(text="✅ TASDIQLASH", callback_data=f"pay_ok:{p['payment_id']}")
            bb.button(text="❌ RAD ETISH", callback_data=f"pay_no:{p['payment_id']}")
            bb.adjust(2)
            text = (
                f"💳 <b>PAYMENT</b>\n\n"
                f"👤 User: <code>{p['user_id']}</code>\n"
                f"📦 Product: <b>{p['product']}</b>\n"
                f"💰 Amount: <b>{p['amount']:,} so‘m</b>\n"
                f"📅 {p['created_at'].strftime('%d.%m.%Y %H:%M')}"
            )
            if p["receipt_file_id"]:
                await cb.message.answer_photo(p["receipt_file_id"], caption=text, reply_markup=bb.as_markup())
            else:
                await cb.message.answer(text, reply_markup=bb.as_markup())
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        await cb.message.answer("—", reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_payments error: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("pay_ok:"))
async def pay_ok(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        pid = cb.data.split(":")[1]
        async with db_pool.acquire() as conn:
            p = await conn.fetchrow("SELECT * FROM payments WHERE payment_id=$1", pid)
            if not p or p["status"] != "pending":
                await cb.answer("Allaqachon ko‘rib chiqilgan")
                return
            await conn.execute("""
                UPDATE payments SET status='approved', approved_at=NOW() WHERE payment_id=$1
            """, pid)

            # Product bo'yicha unlock
            if p["product"] == "iq" and p["attempt_id"]:
                await conn.execute("""
                    UPDATE test_attempts SET payment_status='paid', result_visible=TRUE
                    WHERE id=$1
                """, p["attempt_id"])
                # Sertifikat yaratish
                att = await conn.fetchrow("SELECT * FROM test_attempts WHERE id=$1", p["attempt_id"])
                if att:
                    res = await conn.fetchrow("SELECT * FROM results WHERE attempt_id=$1", att["id"])
                    if res:
                        existing_cert = await conn.fetchval("SELECT 1 FROM certificates WHERE result_id=$1 AND type='iq'", res["id"])
                        if not existing_cert:
                            code = gen_code("IQ")
                            await conn.execute("""
                                INSERT INTO certificates (certificate_id, verification_code, user_id, result_id, score, type)
                                VALUES ($1, $2, $3, $4, $5, 'iq')
                            """, gen_code("CERT"), code, p["user_id"], res["id"], res["score"])
                try:
                    await bot.send_message(p["user_id"], "✅ To‘lov tasdiqlandi! IQ natijangiz ochildi.")
                except Exception:
                    pass

            elif p["product"] == "battle" and p["battle_id"]:
                await conn.execute("""
                    UPDATE battle_players SET payment_status='approved'
                    WHERE battle_id=$1 AND user_id=$2
                """, p["battle_id"], p["user_id"])
                # Ikkalasi ham approved bo'lsa, battle ready
                players = await conn.fetch("SELECT * FROM battle_players WHERE battle_id=$1", p["battle_id"])
                if len(players) >= 2 and all(pl["payment_status"] == "approved" for pl in players):
                    await conn.execute("""
                        UPDATE battles SET status='ready' WHERE id=$1 AND status='waiting_for_payment'
                    """, p["battle_id"])
                    # Ikkalasiga xabar
                    for pl in players:
                        try:
                            await bot.send_message(pl["user_id"], "🎉 Battle tayyor! /start → ⚔️ Battle davom ettirish")
                        except Exception:
                            pass

            elif p["product"] in ("eq_retry", "pq_retry", "iq_retry"):
                pass  # Retry uchun alohida logika

        if cb.message.caption:
            await cb.message.edit_caption(caption="✅ Tasdiqlandi")
        else:
            await cb.message.edit_text("✅ Tasdiqlandi")
    except Exception as e:
        logger.error(f"pay_ok error: {e}")
    await cb.answer("Approved")


@dp.callback_query(F.data.startswith("pay_no:"))
async def pay_no(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        pid = cb.data.split(":")[1]
        async with db_pool.acquire() as conn:
            p = await conn.fetchrow("SELECT * FROM payments WHERE payment_id=$1", pid)
            if not p or p["status"] != "pending":
                await cb.answer("Allaqachon ko‘rib chiqilgan")
                return
            await conn.execute("""
                UPDATE payments SET status='rejected' WHERE payment_id=$1
            """, pid)
            if p["product"] == "battle" and p["battle_id"]:
                await conn.execute("""
                    UPDATE battle_players SET payment_status='rejected'
                    WHERE battle_id=$1 AND user_id=$2
                """, p["battle_id"], p["user_id"])
            try:
                await bot.send_message(p["user_id"], "❌ To‘lov rad etildi.")
            except Exception:
                pass
        if cb.message.caption:
            await cb.message.edit_caption(caption="❌ Rad etildi")
        else:
            await cb.message.edit_text("❌ Rad etildi")
    except Exception as e:
        logger.error(f"pay_no error: {e}")
    await cb.answer("Rejected")


@dp.callback_query(F.data == "admin:products")
async def admin_products(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        iq = await get_setting("iq_price", "10000")
        iqr = await get_setting("iq_retry_price", "5000")
        eqr = await get_setting("eq_retry_price", "5000")
        pqr = await get_setting("pq_retry_price", "5000")
        battle = await get_setting("battle_price", "7500")
        text = (
            f"💰 <b>NARXLAR</b>\n\n"
            f"🧠 IQ: <b>{iq}</b> so‘m\n"
            f"🔄 IQ retry: <b>{iqr}</b> so‘m\n"
            f"🔄 EQ retry: <b>{eqr}</b> so‘m\n"
            f"🔄 PQ retry: <b>{pqr}</b> so‘m\n"
            f"⚔️ Battle: <b>{battle}</b> so‘m\n\n"
            f"O‘zgartirish uchun tugmani bosing:"
        )
        b = InlineKeyboardBuilder()
        b.button(text=f"🧠 IQ ({iq})", callback_data="set:iq_price")
        b.button(text=f"🔄 IQ retry ({iqr})", callback_data="set:iq_retry_price")
        b.button(text=f"🔄 EQ retry ({eqr})", callback_data="set:eq_retry_price")
        b.button(text=f"🔄 PQ retry ({pqr})", callback_data="set:pq_retry_price")
        b.button(text=f"⚔️ Battle ({battle})", callback_data="set:battle_price")
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        b.adjust(1)
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_products error: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("set:"))
async def admin_set_price(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        key = cb.data.split(":")[1]
        current = await get_setting(key, "0")
        # FSM o'rniga oddiy state — keyingi xabarni kutamiz
        ADMIN_STATE[cb.from_user.id] = {"action": "set_price", "key": key}
        await cb.message.edit_text(
            f"✏️ <b>{key}</b>\n\nHozirgi: <b>{current}</b> so‘m\n\nYangi narxni yozing (0 = BEPUL):"
        )
    except Exception as e:
        logger.error(f"admin_set_price error: {e}")
    await cb.answer()


@dp.callback_query(F.data == "admin:cards")
async def admin_cards(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        async with db_pool.acquire() as conn:
            cards = await conn.fetch("SELECT * FROM payment_cards ORDER BY created_at DESC")
        text = "💳 <b>TO‘LOV KARTALARI</b>\n\n"
        if not cards:
            text += "Hozircha karta yo‘q."
        else:
            for c in cards:
                status = "✅" if c["active"] else "❌"
                text += f"{status} <code>{c['card_number']}</code>\n   {c['holder']} | {c['bank'] or '—'}\n\n"
        b = InlineKeyboardBuilder()
        b.button(text="➕ Yangi karta", callback_data="card:add")
        for c in cards:
            b.button(text=f"✏️ {c['card_number'][-4:]}", callback_data=f"card:edit:{c['id']}")
            b.button(text=f"🗑 {c['card_number'][-4:]}", callback_data=f"card:del:{c['id']}")
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        b.adjust(1, 2)
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_cards error: {e}")
    await cb.answer()


@dp.callback_query(F.data == "card:add")
async def card_add(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    ADMIN_STATE[cb.from_user.id] = {"action": "card_add"}
    await cb.message.edit_text(
        "➕ <b>YANGI KARTA</b>\n\n"
        "Format:\n<code>KARTA_RAQAMI | HOLDER | BANK</code>\n\n"
        "Masalan:\n<code>8600 1234 5678 9012 | IQ TEST BOT | Click</code>"
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("card:edit:"))
async def card_edit(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        cid = int(cb.data.split(":")[2])
        async with db_pool.acquire() as conn:
            c = await conn.fetchrow("SELECT * FROM payment_cards WHERE id=$1", cid)
        if not c:
            await cb.answer("Topilmadi")
            return
        ADMIN_STATE[cb.from_user.id] = {"action": "card_edit", "id": cid}
        await cb.message.edit_text(
            f"✏️ <b>TAHRIRLASH</b>\n\n"
            f"Hozirgi:\n<code>{c['card_number']} | {c['holder']} | {c['bank'] or '—'}</code>\n\n"
            f"Yangi format:\n<code>KARTA | HOLDER | BANK</code>"
        )
    except Exception as e:
        logger.error(f"card_edit error: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("card:del:"))
async def card_del(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        cid = int(cb.data.split(":")[2])
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM payment_cards WHERE id=$1", cid)
        await cb.answer("🗑 O‘chirildi")
        await admin_cards(cb)
    except Exception as e:
        logger.error(f"card_del error: {e}")
    await cb.answer()


@dp.callback_query(F.data == "admin:live")
async def admin_live(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        mode = await get_setting("live_mode", "fake")
        base = await get_setting("live_fake_base", "95114")
        online = await get_setting("live_fake_online", "342")
        delta = await get_setting("live_fake_delta", "8")
        text = (
            f"🎯 <b>LIVE COUNTER</b>\n\n"
            f"Rejim: <b>{mode.upper()}</b>\n"
            f"Fake base: <b>{base}</b>\n"
            f"Fake online: <b>{online}</b>\n"
            f"Fake delta: <b>±{delta}</b>\n\n"
            f"Rejimni almashtiring:"
        )
        b = InlineKeyboardBuilder()
        b.button(text="📊 REAL", callback_data="live:mode:real")
        b.button(text="🎯 FAKE", callback_data="live:mode:fake")
        b.button(text=f"✏️ Base ({base})", callback_data="live:set:live_fake_base")
        b.button(text=f"✏️ Online ({online})", callback_data="live:set:live_fake_online")
        b.button(text=f"✏️ Delta (±{delta})", callback_data="live:set:live_fake_delta")
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        b.adjust(2, 1, 1, 1, 1)
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_live error: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("live:mode:"))
async def live_set_mode(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    mode = cb.data.split(":")[2]
    await set_setting("live_mode", mode)
    await cb.answer(f"Rejim: {mode.upper()}")
    await admin_live(cb)


@dp.callback_query(F.data.startswith("live:set:"))
async def live_set_value(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    key = cb.data.split(":")[2]
    ADMIN_STATE[cb.from_user.id] = {"action": "live_set", "key": key}
    current = await get_setting(key, "0")
    await cb.message.edit_text(f"✏️ <b>{key}</b>\n\nHozirgi: <b>{current}</b>\n\nYangi qiymat:")
    await cb.answer()


# ==================== ADMIN STATE HANDLER ====================
ADMIN_STATE = {}


@dp.message(F.photo)
async def handle_receipt(message: types.Message):
    try:
        async with db_pool.acquire() as conn:
            p = await conn.fetchrow("""
                SELECT * FROM payments WHERE user_id=$1 AND status='pending'
                ORDER BY created_at DESC LIMIT 1
            """, message.from_user.id)
            if not p:
                return
            await conn.execute("""
                UPDATE payments SET receipt_file_id=$1 WHERE payment_id=$2
            """, message.photo[-1].file_id, p["payment_id"])
        await message.answer("✅ Chek qabul qilindi. Admin tasdiqlashini kuting.")
        if ADMIN_USER_ID:
            try:
                await bot.send_message(
                    ADMIN_USER_ID,
                    f"💳 Yangi chek!\nUser: <code>{message.from_user.id}</code>\nProduct: {p['product']}\nAmount: {p['amount']:,} so‘m"
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"handle_receipt error: {e}")


@dp.message(F.text)
async def handle_admin_text(message: types.Message):
    """Admin state — narx o'zgartirish, karta qo'shish"""
    uid = message.from_user.id
    state = ADMIN_STATE.get(uid)
    if not state:
        return
    if not await is_admin(uid):
        ADMIN_STATE.pop(uid, None)
        return

    action = state.get("action")

    if action == "set_price":
        try:
            val = int(message.text.strip())
            if val < 0:
                raise ValueError
            key = state["key"]
            await set_setting(key, str(val))
            ADMIN_STATE.pop(uid, None)
            await message.answer(f"✅ <b>{key}</b> = <b>{val}</b> so‘m saqlandi.")
        except Exception:
            await message.answer("❌ Noto‘g‘ri qiymat. Musbat son kiriting.")
        return

    if action == "live_set":
        try:
            val = int(message.text.strip())
            key = state["key"]
            await set_setting(key, str(val))
            ADMIN_STATE.pop(uid, None)
            await message.answer(f"✅ <b>{key}</b> = <b>{val}</b> saqlandi.")
        except Exception:
            await message.answer("❌ Noto‘g‘ri qiymat.")
        return

    if action == "card_add":
        try:
            parts = [p.strip() for p in message.text.split("|")]
            if len(parts) < 2:
                raise ValueError
            card_number = parts[0]
            holder = parts[1]
            bank = parts[2] if len(parts) > 2 else ""
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO payment_cards (card_number, holder, bank, active)
                    VALUES ($1, $2, $3, TRUE)
                """, card_number, holder, bank)
            ADMIN_STATE.pop(uid, None)
            await message.answer("✅ Karta qo‘shildi.")
        except Exception as e:
            await message.answer(f"❌ Format xato: {e}")
        return

    if action == "card_edit":
        try:
            parts = [p.strip() for p in message.text.split("|")]
            if len(parts) < 2:
                raise ValueError
            cid = state["id"]
            card_number = parts[0]
            holder = parts[1]
            bank = parts[2] if len(parts) > 2 else ""
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE payment_cards SET card_number=$1, holder=$2, bank=$3 WHERE id=$4
                """, card_number, holder, bank, cid)
            ADMIN_STATE.pop(uid, None)
            await message.answer("✅ Karta yangilandi.")
        except Exception as e:
            await message.answer(f"❌ Format xato: {e}")
        return


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Format: /broadcast matn")
            return
        text = parts[1]
        async with db_pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id FROM users")
        sent = 0
        failed = 0
        for u in users:
            try:
                await bot.send_message(u["user_id"], text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await message.answer(f"✅ Yuborildi: {sent}\n❌ Xato: {failed}")
    except Exception as e:
        logger.error(f"cmd_broadcast error: {e}")


@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 Broadcast uchun: <code>/broadcast matn</code>")
    await cb.answer()


@dp.callback_query(F.data == "admin:settings")
async def admin_settings(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id):
        return
    try:
        support = await get_setting("support_username", "omono_v")
        free_end = await get_setting("free_launch_end", "—")
        maintenance = await get_setting("maintenance_mode", "0")
        text = (
            f"⚙️ <b>SETTINGS</b>\n\n"
            f"👤 Support: @{support}\n"
            f"📅 Free launch: {free_end}\n"
            f"🛠 Maintenance: {'ON' if maintenance == '1' else 'OFF'}"
        )
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="admin:menu")
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"admin_settings error: {e}")
    await cb.answer()


# ==================== BACKGROUND: LIVE FAKE UPDATER ====================
async def live_counter_updater():
    """Fake live counter uchun background task — kerak emas, API da random"""
    while True:
        await asyncio.sleep(60)


# ==================== RUNNER ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)