# bot.py — IQ TEST BOT v4.0 FINAL
# ============================================================
# IQ TEST BOT
# Python 3.11
# aiogram 3.x
# FastAPI
# PostgreSQL / asyncpg
# ============================================================

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
from urllib.parse import parse_qsl, unquote

import asyncpg

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Update,
    WebAppInfo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    BufferedInputFile,
    CallbackQuery,
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
    ReplyKeyboardBuilder,
)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from PIL import Image, ImageDraw, ImageFont

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")

ADMIN_USER_ID = int(
    os.getenv("ADMIN_USER_ID", "0").strip() or "0"
)

BOT_USERNAME = (
    os.getenv("BOT_USERNAME", "iqtest_ubot")
    .strip()
    .lstrip("@")
)

PUBLIC_BASE_URL = (
    os.getenv("PUBLIC_BASE_URL", "")
    .strip()
    .rstrip("/")
)

WEBHOOK_SECRET = (
    os.getenv("WEBHOOK_SECRET", "change-me")
    .strip()
)

PORT = int(os.getenv("PORT", "10000"))


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# GLOBALS
# ============================================================

db_pool: asyncpg.Pool | None = None


# ============================================================
# TEXTS
# ============================================================

TEXTS = {
    "uz": {
        "choose_lang": "🌐 Tilni tanlang:",

        "welcome": (
            "👋 Salom, {name}!\n\n"
            "<b>IQ TEST BOT</b>\n\n"
            "Boshlash uchun tugmani bosing."
        ),

        "menu_test": "🧠 IQ · EQ · PQ testini ishlash",
        "menu_cert": "🏆 Sertifikatim",
        "menu_rank": "📊 Reyting",
        "menu_earn": "💰 Pul ishlash",
        "menu_help": "💳 Narx va yordam",
        "menu_lang": "🌐 Til",

        "no_cert": "📄 Hali sertifikatingiz yo‘q.",

        "ranking_title": (
            "<b>📊 REYTING</b>\n\n"
        ),

        "earn_title": (
            "<b>💰 PUL ISHLASH</b>\n\n"
            "<code>{link}</code>\n\n"
            "Taklif: <b>{count}</b>"
        ),

        "help": (
            "<b>💳 NARX VA YORDAM</b>\n\n"
            "IQ — {iq_price}\n"
            "EQ — {eq_price}\n"
            "PQ — {pq_price}\n"
            "IQ retry — {iq_retry}\n"
            "Battle — {battle_price}\n\n"
            "@omono_v"
        ),

        "lang_changed": "🇺🇿 O‘zbekcha",

        "cert_found": (
            "<b>🏆 Sertifikat topildi</b>\n\n"
            "{name}\n"
            "Score: <b>{score}</b>\n"
            "{date}"
        ),

        "cert_not_found": "❌ Topilmadi.",
    },

    "ru": {
        "choose_lang": "🌐 Выберите язык:",

        "welcome": (
            "👋 Привет, {name}!\n\n"
            "<b>IQ TEST BOT</b>\n\n"
            "Нажмите кнопку."
        ),

        "menu_test": "🧠 Пройти IQ · EQ · PQ",
        "menu_cert": "🏆 Сертификат",
        "menu_rank": "📊 Рейтинг",
        "menu_earn": "💰 Заработок",
        "menu_help": "💳 Цены",
        "menu_lang": "🌐 Язык",

        "no_cert": "📄 Нет сертификата.",

        "ranking_title": (
            "<b>📊 РЕЙТИНГ</b>\n\n"
        ),

        "earn_title": (
            "<b>💰 ЗАРАБОТОК</b>\n\n"
            "<code>{link}</code>\n\n"
            "Приглашено: <b>{count}</b>"
        ),

        "help": (
            "<b>💳 ЦЕНЫ</b>\n\n"
            "IQ — {iq_price}\n"
            "EQ — {eq_price}\n"
            "PQ — {pq_price}\n"
            "Повтор — {iq_retry}\n"
            "Батл — {battle_price}\n\n"
            "@omono_v"
        ),

        "lang_changed": "🇷🇺 Русский",

        "cert_found": (
            "<b>🏆 Сертификат найден</b>\n\n"
            "{name}\n"
            "Score: <b>{score}</b>\n"
            "{date}"
        ),

        "cert_not_found": "❌ Не найден.",
    },

    "en": {
        "choose_lang": "🌐 Choose language:",

        "welcome": (
            "👋 Hello, {name}!\n\n"
            "<b>IQ TEST BOT</b>\n\n"
            "Tap the button to start."
        ),

        "menu_test": "🧠 Take IQ · EQ · PQ test",
        "menu_cert": "🏆 Certificate",
        "menu_rank": "📊 Ranking",
        "menu_earn": "💰 Earn",
        "menu_help": "💳 Pricing",
        "menu_lang": "🌐 Language",

        "no_cert": "📄 No certificate.",

        "ranking_title": (
            "<b>📊 RANKING</b>\n\n"
        ),

        "earn_title": (
            "<b>💰 EARN</b>\n\n"
            "<code>{link}</code>\n\n"
            "Invited: <b>{count}</b>"
        ),

        "help": (
            "<b>💳 PRICING</b>\n\n"
            "IQ — {iq_price}\n"
            "EQ — {eq_price}\n"
            "PQ — {pq_price}\n"
            "Retry — {iq_retry}\n"
            "Battle — {battle_price}\n\n"
            "@omono_v"
        ),

        "lang_changed": "🇬🇧 English",

        "cert_found": (
            "<b>🏆 Certificate found</b>\n\n"
            "{name}\n"
            "Score: <b>{score}</b>\n"
            "{date}"
        ),

        "cert_not_found": "❌ Not found.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """
    Translation helper.
    """

    lang_data = TEXTS.get(
        lang,
        TEXTS["uz"],
    )

    text = lang_data.get(
        key,
        TEXTS["uz"].get(key, key),
    )

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    return text


# ============================================================
# ANSWER KEYS
# ============================================================

IQ_ANSWERS = [
    {"correct": 2, "weight": 1},
    {"correct": 0, "weight": 1},
    {"correct": 3, "weight": 1},
    {"correct": 2, "weight": 1},
    {"correct": 3, "weight": 1},
    {"correct": 1, "weight": 1},

    {"correct": 1, "weight": 2},
    {"correct": 2, "weight": 2},
    {"correct": 1, "weight": 2},
    {"correct": 1, "weight": 2},
    {"correct": 1, "weight": 2},
    {"correct": 2, "weight": 2},

    {"correct": 1, "weight": 3},
    {"correct": 0, "weight": 3},
    {"correct": 1, "weight": 3},
    {"correct": 1, "weight": 3},
    {"correct": 2, "weight": 3},
    {"correct": 1, "weight": 3},
]


EQ_ANSWERS = [
    {"scores": [4, 2, 3, 1]},
    {"scores": [4, 1, 2, 1]},
    {"scores": [4, 3, 1, 1]},
    {"scores": [4, 2, 1, 2]},
    {"scores": [4, 2, 3, 1]},
    {"scores": [4, 2, 1, 2]},
]


PQ_ANSWERS = [
    {"scores": [2, 1, 2, 1]},
    {"scores": [4, 2, 1, 0]},
    {"scores": [4, 1, 2, 2]},
    {"scores": [4, 3, 1, 0]},
    {"scores": [4, 2, 1, 0]},
    {"scores": [4, 3, 1, 0]},
]


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:

        await conn.execute(
            """
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
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ
            )
            """
        )

        await conn.execute(
            """
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
                result_visible BOOLEAN DEFAULT TRUE,
                level TEXT
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                attempt_id INTEGER NOT NULL,
                test_type TEXT NOT NULL,
                score INTEGER NOT NULL,
                level TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
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
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_cards (
                id SERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL,
                bank TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                certificate_id TEXT UNIQUE NOT NULL,
                verification_code TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                result_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                type TEXT DEFAULT 'iq',
                full_name TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
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
            """
        )

        await conn.execute(
            """
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
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),

                UNIQUE(referred_id)
            )
            """
        )

        # ----------------------------------------------------
        # MIGRATIONS
        # ----------------------------------------------------

        migrations = [
            """
            ALTER TABLE users
            ALTER COLUMN last_name DROP NOT NULL
            """,

            """
            ALTER TABLE users
            ALTER COLUMN username DROP NOT NULL
            """,

            """
            ALTER TABLE users
            ALTER COLUMN first_name DROP NOT NULL
            """,

            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS gender TEXT
            """,

            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS age INTEGER
            """,

            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS country TEXT
            """,

            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS full_name TEXT
            """,

            """
            ALTER TABLE payment_cards
            ADD COLUMN IF NOT EXISTS bank TEXT
            """,

            """
            ALTER TABLE payment_cards
            ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE
            """,

            """
            ALTER TABLE payment_cards
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMPTZ DEFAULT NOW()
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS answers JSONB
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS test_status TEXT
            DEFAULT 'not_started'
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS payment_status TEXT
            DEFAULT 'pending'
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS session_id TEXT
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS current_question INTEGER
            DEFAULT 0
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS weighted INTEGER
            """,

            """
            ALTER TABLE battle_players
            ADD COLUMN IF NOT EXISTS finished_at
            TIMESTAMPTZ
            """,

            """
            ALTER TABLE battles
            ADD COLUMN IF NOT EXISTS winner_id BIGINT
            """,

            """
            ALTER TABLE test_attempts
            ADD COLUMN IF NOT EXISTS payment_status TEXT
            DEFAULT 'free'
            """,

            """
            ALTER TABLE test_attempts
            ADD COLUMN IF NOT EXISTS result_visible BOOLEAN
            DEFAULT TRUE
            """,

            """
            ALTER TABLE test_attempts
            ADD COLUMN IF NOT EXISTS level TEXT
            """,

            """
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS attempt_id INTEGER
            """,

            """
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS battle_id INTEGER
            """,

            """
            ALTER TABLE certificates
            ADD COLUMN IF NOT EXISTS type TEXT
            DEFAULT 'iq'
            """,

            """
            ALTER TABLE certificates
            ADD COLUMN IF NOT EXISTS full_name TEXT
            """,

            """
            ALTER TABLE certificates
            ADD COLUMN IF NOT EXISTS verification_code TEXT
            """,

            """
            ALTER TABLE certificates
            ADD COLUMN IF NOT EXISTS certificate_id TEXT
            """,
        ]

        for migration in migrations:
            try:
                await conn.execute(migration)
            except Exception as e:
                logger.warning(
                    "Migration skipped: %s",
                    e,
                )

        # ----------------------------------------------------
        # DEFAULT SETTINGS
        # ----------------------------------------------------

        defaults = {
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

        for key, value in defaults.items():
            await conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
                """,
                key,
                value,
            )

        # ----------------------------------------------------
        # MAIN ADMIN
        # ----------------------------------------------------

        if ADMIN_USER_ID:
            await conn.execute(
                """
                INSERT INTO admins (user_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
                """,
                ADMIN_USER_ID,
            )

        # ----------------------------------------------------
        # DEFAULT PAYMENT CARD
        # ----------------------------------------------------

        card_count = await conn.fetchval(
            "SELECT COUNT(*) FROM payment_cards"
        )

        if card_count == 0:
            await conn.execute(
                """
                INSERT INTO payment_cards
                    (card_number, holder, bank, active)
                VALUES
                    (
                        '8600 1234 5678 9012',
                        'IQ TEST BOT',
                        'Click',
                        TRUE
                    )
                """
            )

    logger.info("Database initialized successfully.")


# ============================================================
# ID / CODE GENERATORS
# ============================================================

def gen_code(
    prefix: str = "IQ",
    length: int = 6,
) -> str:

    chars = string.ascii_uppercase + string.digits

    return (
        f"{prefix}-"
        + "".join(
            random.choices(
                chars,
                k=length,
            )
        )
    )


def gen_payment_id() -> str:
    chars = string.ascii_uppercase + string.digits

    return (
        "PAY-"
        + "".join(
            random.choices(
                chars,
                k=10,
            )
        )
    )


def gen_session_id() -> str:
    chars = string.ascii_uppercase + string.digits

    return (
        "SES-"
        + "".join(
            random.choices(
                chars,
                k=16,
            )
        )
    )


def gen_battle_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    return "".join(
        random.choices(
            chars,
            k=4,
        )
    )


# ============================================================
# TELEGRAM MINI APP INIT DATA VALIDATION
# ============================================================

def validate_init_data(
    init_data: str,
    bot_token: str,
):
    """
    Telegram Mini App initData server-side validation.

    Muhim:
    - hash data-check-stringdan chiqariladi.
    - query_id chiqarilmaydi.
    - URL encoded qiymatlar parse_qsl orqali decode qilinadi.
    - user JSON sifatida tekshiriladi.
    - auth_date juda eski bo‘lsa rad etiladi.
    """

    try:
        if not init_data or not bot_token:
            return None

        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
                strict_parsing=False,
            )
        )

        received_hash = parsed.pop(
            "hash",
            None,
        )

        if not received_hash:
            return None

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
            received_hash,
        ):
            logger.warning(
                "Telegram initData HMAC validation failed."
            )
            return None

        auth_date_raw = parsed.get(
            "auth_date",
            "0",
        )

        try:
            auth_date = int(auth_date_raw)
        except (TypeError, ValueError):
            return None

        if auth_date <= 0:
            return None

        now = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        # Kelajakdagi timestampni ham qabul qilmaymiz.
        if auth_date > now + 60:
            return None

        # 48 soatdan eski initData yaroqsiz.
        if now - auth_date > 86400 * 2:
            return None

        user_raw = parsed.get("user")

        if not user_raw:
            return None

        try:
            user = json.loads(user_raw)
        except json.JSONDecodeError:
            return None

        if not isinstance(user, dict):
            return None

        if not user.get("id"):
            return None

        return user

    except Exception as e:
        logger.exception(
            "validate_init_data error: %s",
            e,
        )
        return None


# ============================================================
# SETTINGS
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
            WHERE key=$1
            """,
            key,
        )

        if row:
            return row["value"]

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
                value=$2,
                updated_at=NOW()
            """,
            key,
            str(value),
        )


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


# ============================================================
# ADMIN CHECK
# ============================================================

async def is_admin(
    user_id: int,
) -> bool:

    # ADMIN_USER_ID har doim asosiy admin.
    if (
        ADMIN_USER_ID
        and int(user_id) == ADMIN_USER_ID
    ):
        return True

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM admins
                WHERE user_id=$1
                """,
                user_id,
            )

            return row is not None

    except Exception as e:
        logger.exception(
            "is_admin database error: %s",
            e,
        )

        # DB vaqtincha xato qilsa,
        # asosiy adminni bloklab qo‘ymaymiz.
        return (
            bool(ADMIN_USER_ID)
            and int(user_id) == ADMIN_USER_ID
        )


# ============================================================
# USER HELPERS
# ============================================================

async def get_user(
    user_id: int,
):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id=$1
            """,
            user_id,
        )


async def upsert_user(
    user,
):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users
                (
                    user_id,
                    username,
                    first_name,
                    last_name,
                    last_seen
                )
            VALUES
                ($1, $2, $3, $4, NOW())

            ON CONFLICT (user_id)
            DO UPDATE SET
                username=$2,
                first_name=$3,
                last_name=$4,
                last_seen=NOW()
            """,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
        )


# ============================================================
# TELEGRAM KEYBOARDS
# ============================================================

def lang_kb():

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


def main_menu_kb(
    lang: str,
):

    builder = ReplyKeyboardBuilder()

    builder.button(
        text=t(
            lang,
            "menu_test",
        ),
        web_app=WebAppInfo(
            url=f"{WEBAPP_URL}/app"
        ),
    )

    builder.button(
        text=t(
            lang,
            "menu_cert",
        )
    )

    builder.button(
        text=t(
            lang,
            "menu_rank",
        )
    )

    builder.button(
        text=t(
            lang,
            "menu_earn",
        )
    )

    builder.button(
        text=t(
            lang,
            "menu_help",
        )
    )

    builder.button(
        text=t(
            lang,
            "menu_lang",
        )
    )

    builder.adjust(
        1,
        2,
        2,
        1,
    )

    return builder.as_markup(
        resize_keyboard=True
    )


def admin_kb():

    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Users",
        callback_data="admin:users",
    )

    builder.button(
        text="📊 Statistics",
        callback_data="admin:stats",
    )

    builder.button(
        text="💳 Payments",
        callback_data="admin:payments",
    )

    builder.button(
        text="📢 Broadcast",
        callback_data="admin:broadcast",
    )

    builder.button(
        text="🛒 Products",
        callback_data="admin:products",
    )

    builder.button(
        text="🏆 Certificates",
        callback_data="admin:certs",
    )

    builder.button(
        text="⚔️ Battles",
        callback_data="admin:battles",
    )

    builder.button(
        text="💳 Cards",
        callback_data="admin:cards",
    )

    builder.button(
        text="📈 Live Counter",
        callback_data="admin:live",
    )

    builder.button(
        text="⚙️ Settings",
        callback_data="admin:settings",
    )

    builder.adjust(
        2,
        2,
        2,
        2,
        2,
    )

    return builder.as_markup()


# ============================================================
# BOT / DISPATCHER
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


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
            message.text.split()
            if message.text
            else []
        )

        # ----------------------------------------------------
        # REFERRAL
        # ----------------------------------------------------

        if (
            len(args) > 1
            and args[1].startswith("ref_")
        ):
            try:
                ref_id = int(
                    args[1].replace(
                        "ref_",
                        "",
                    )
                )

                if (
                    ref_id
                    != message.from_user.id
                ):
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO referrals
                                (
                                    referrer_id,
                                    referred_id
                                )
                            VALUES
                                ($1, $2)

                            ON CONFLICT
                                (referred_id)
                            DO NOTHING
                            """,
                            ref_id,
                            message.from_user.id,
                        )

            except Exception:
                pass

        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        if (
            not user
            or not user["language"]
        ):
            await message.answer(
                t(
                    "uz",
                    "choose_lang",
                ),
                reply_markup=lang_kb(),
            )
            return

        lang = user["language"]

        await message.answer(
            t(
                lang,
                "welcome",
                name=(
                    message.from_user.first_name
                    or "do‘stim"
                ),
            ),
            reply_markup=main_menu_kb(
                lang
            ),
        )

    except Exception as e:
        logger.exception(
            "cmd_start error: %s",
            e,
        )


# ============================================================
# LANGUAGE CALLBACK
# ============================================================

@dp.callback_query(
    F.data.startswith("lang:")
)
async def cb_lang(
    cb: CallbackQuery,
):

    try:
        lang = cb.data.split(
            ":",
            1,
        )[1]

        if lang not in TEXTS:
            await cb.answer(
                "Invalid language.",
                show_alert=True,
            )
            return

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET language=$1
                WHERE user_id=$2
                """,
                lang,
                cb.from_user.id,
            )

        await cb.answer()

        if cb.message:
            try:
                await cb.message.edit_text(
                    t(
                        lang,
                        "lang_changed",
                    )
                )
            except Exception:
                pass

            await cb.message.answer(
                t(
                    lang,
                    "welcome",
                    name=(
                        cb.from_user.first_name
                        or "do‘stim"
                    ),
                ),
                reply_markup=main_menu_kb(
                    lang
                ),
            )

    except Exception as e:
        logger.exception(
            "cb_lang error: %s",
            e,
        )

        try:
            await cb.answer()
        except Exception:
            pass


# ============================================================
# MENU — CERTIFICATE
# ============================================================

@dp.message(
    F.text.in_(
        [
            TEXTS["uz"]["menu_cert"],
            TEXTS["ru"]["menu_cert"],
            TEXTS["en"]["menu_cert"],
        ]
    )
)
async def menu_cert(
    message: types.Message,
):

    try:
        user = await get_user(
            message.from_user.id
        )

        lang = (
            user["language"]
            if user
            else "uz"
        )

        async with db_pool.acquire() as conn:

            cert = await conn.fetchrow(
                """
                SELECT
                    c.*,
                    u.full_name,
                    u.first_name
                FROM certificates c
                JOIN users u
                    ON u.user_id=c.user_id
                WHERE c.user_id=$1
                  AND c.type='iq'
                ORDER BY c.created_at DESC
                LIMIT 1
                """,
                message.from_user.id,
            )

        if not cert:
            await message.answer(
                t(
                    lang,
                    "no_cert",
                )
            )
            return

        name = (
            cert["full_name"]
            or cert["first_name"]
            or "User"
        )

        await message.answer(
            t(
                lang,
                "cert_found",
                name=name,
                score=cert["score"],
                date=cert[
                    "created_at"
                ].strftime(
                    "%d.%m.%Y"
                ),
            )
        )

    except Exception as e:
        logger.exception(
            "menu_cert error: %s",
            e,
        )
        # ============================================================
# MENU — RANKING
# ============================================================

@dp.message(
    F.text.in_(
        [
            TEXTS["uz"]["menu_rank"],
            TEXTS["ru"]["menu_rank"],
            TEXTS["en"]["menu_rank"],
        ]
    )
)
async def menu_rank(
    message: types.Message,
):
    try:
        user = await get_user(
            message.from_user.id
        )

        lang = (
            user["language"]
            if user
            else "uz"
        )

        async with db_pool.acquire() as conn:

            # Faqat natijasi haqiqatan ochilgan
            # attemptlar reytingga kiradi.
            rows = await conn.fetch(
                """
                SELECT
                    u.first_name,
                    u.username,
                    MAX(r.score) AS best
                FROM results r
                JOIN users u
                    ON u.user_id = r.user_id
                JOIN test_attempts ta
                    ON ta.id = r.attempt_id
                WHERE LOWER(TRIM(r.test_type)) = 'iq'
                  AND ta.result_visible = TRUE
                GROUP BY
                    u.user_id,
                    u.first_name,
                    u.username
                ORDER BY best DESC
                LIMIT 10
                """
            )

        text = t(
            lang,
            "ranking_title",
        )

        medals = [
            "🥇",
            "🥈",
            "🥉",
        ]

        for i, row in enumerate(
            rows,
            start=1,
        ):
            name = (
                row["first_name"]
                or row["username"]
                or "User"
            )

            prefix = (
                medals[i - 1]
                if i <= 3
                else f"{i}."
            )

            text += (
                f"{prefix} "
                f"{name} — "
                f"<b>{row['best']}</b>\n"
            )

        if not rows:
            text += "Hozircha bo‘sh."

        await message.answer(text)

    except Exception as e:
        logger.exception(
            "menu_rank error: %s",
            e,
        )


# ============================================================
# MENU — EARN / REFERRAL
# ============================================================

@dp.message(
    F.text.in_(
        [
            TEXTS["uz"]["menu_earn"],
            TEXTS["ru"]["menu_earn"],
            TEXTS["en"]["menu_earn"],
        ]
    )
)
async def menu_earn(
    message: types.Message,
):
    try:
        user = await get_user(
            message.from_user.id
        )

        lang = (
            user["language"]
            if user
            else "uz"
        )

        async with db_pool.acquire() as conn:

            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM referrals
                WHERE referrer_id=$1
                """,
                message.from_user.id,
            )

        link = (
            f"https://t.me/"
            f"{BOT_USERNAME}"
            f"?start=ref_"
            f"{message.from_user.id}"
        )

        await message.answer(
            t(
                lang,
                "earn_title",
                link=link,
                count=count or 0,
            )
        )

    except Exception as e:
        logger.exception(
            "menu_earn error: %s",
            e,
        )


# ============================================================
# MENU — HELP / PRICES
# ============================================================

@dp.message(
    F.text.in_(
        [
            TEXTS["uz"]["menu_help"],
            TEXTS["ru"]["menu_help"],
            TEXTS["en"]["menu_help"],
        ]
    )
)
async def menu_help(
    message: types.Message,
):
    try:
        user = await get_user(
            message.from_user.id
        )

        lang = (
            user["language"]
            if user
            else "uz"
        )

        iq_price = await get_setting(
            "iq_price",
            "0",
        )

        eq_price = await get_setting(
            "eq_price",
            "0",
        )

        pq_price = await get_setting(
            "pq_price",
            "0",
        )

        iq_retry = await get_setting(
            "iq_retry_price",
            "5000",
        )

        battle_price = await get_setting(
            "battle_price",
            "7500",
        )

        iq_str = (
            "BEPUL"
            if str(iq_price) == "0"
            else f"{iq_price} so‘m"
        )

        eq_str = (
            "BEPUL"
            if str(eq_price) == "0"
            else f"{eq_price} so‘m"
        )

        pq_str = (
            "BEPUL"
            if str(pq_price) == "0"
            else f"{pq_price} so‘m"
        )

        await message.answer(
            t(
                lang,
                "help",
                iq_price=iq_str,
                eq_price=eq_str,
                pq_price=pq_str,
                iq_retry=(
                    f"{iq_retry} so‘m"
                    if str(iq_retry) != "0"
                    else "BEPUL"
                ),
                battle_price=(
                    f"{battle_price} so‘m"
                    if str(battle_price) != "0"
                    else "BEPUL"
                ),
            )
        )

    except Exception as e:
        logger.exception(
            "menu_help error: %s",
            e,
        )


# ============================================================
# MENU — LANGUAGE
# ============================================================

@dp.message(
    F.text.in_(
        [
            TEXTS["uz"]["menu_lang"],
            TEXTS["ru"]["menu_lang"],
            TEXTS["en"]["menu_lang"],
        ]
    )
)
async def menu_lang(
    message: types.Message,
):
    try:
        await message.answer(
            t(
                "uz",
                "choose_lang",
            ),
            reply_markup=lang_kb(),
        )

    except Exception as e:
        logger.exception(
            "menu_lang error: %s",
            e,
        )


# ============================================================
# CERTIFICATE VERIFICATION
# ============================================================

@dp.message(
    F.text.regexp(
        r"^IQ-[A-Z0-9]{6}$"
    )
)
async def verify_cert(
    message: types.Message,
):
    try:
        code = (
            message.text
            or ""
        ).strip().upper()

        async with db_pool.acquire() as conn:

            cert = await conn.fetchrow(
                """
                SELECT
                    c.*,
                    u.first_name,
                    u.full_name
                FROM certificates c
                JOIN users u
                    ON u.user_id = c.user_id
                WHERE c.verification_code=$1
                LIMIT 1
                """,
                code,
            )

        if not cert:
            await message.answer(
                t(
                    "uz",
                    "cert_not_found",
                )
            )
            return

        name = (
            cert["full_name"]
            or cert["first_name"]
            or "User"
        )

        await message.answer(
            t(
                "uz",
                "cert_found",
                name=name,
                score=cert["score"],
                date=cert[
                    "created_at"
                ].strftime(
                    "%d.%m.%Y"
                ),
            )
        )

    except Exception as e:
        logger.exception(
            "verify_cert error: %s",
            e,
        )


# ============================================================
# CERTIFICATE PNG
# ============================================================

def generate_iq_certificate_png(
    name,
    score,
    code,
    date,
):
    import glob

    W = 1600
    H = 1100

    img = Image.new(
        "RGB",
        (W, H),
        "#0a0e1a",
    )

    draw = ImageDraw.Draw(img)

    # --------------------------------------------------------
    # BACKGROUND GRADIENT
    # --------------------------------------------------------

    for y in range(H):
        ratio = y / H

        r = int(
            10 + 20 * ratio
        )

        g = int(
            14 + 20 * ratio
        )

        b = int(
            26 + 40 * ratio
        )

        draw.line(
            [(0, y), (W, y)],
            fill=(r, g, b),
        )

    # --------------------------------------------------------
    # BORDERS
    # --------------------------------------------------------

    draw.rectangle(
        [
            30,
            30,
            W - 30,
            H - 30,
        ],
        outline="#d4af37",
        width=6,
    )

    draw.rectangle(
        [
            50,
            50,
            W - 50,
            H - 50,
        ],
        outline="#d4af37",
        width=2,
    )

    # --------------------------------------------------------
    # FONT LOADER
    # --------------------------------------------------------

    def load_font(
        size,
        bold=False,
        italic=False,
    ):
        candidates = [
            (
                "/usr/share/fonts/truetype/"
                "dejavu/DejaVuSans-Bold.ttf"
                if bold
                else (
                    "/usr/share/fonts/truetype/"
                    "dejavu/DejaVuSans-Oblique.ttf"
                    if italic
                    else
                    "/usr/share/fonts/truetype/"
                    "dejavu/DejaVuSans.ttf"
                )
            ),

            (
                "/usr/share/fonts/truetype/"
                "liberation/"
                "LiberationSans-Bold.ttf"
                if bold
                else (
                    "/usr/share/fonts/truetype/"
                    "liberation/"
                    "LiberationSans-Italic.ttf"
                    if italic
                    else
                    "/usr/share/fonts/truetype/"
                    "liberation/"
                    "LiberationSans-Regular.ttf"
                )
            ),

            (
                "/usr/share/fonts/dejavu/"
                "DejaVuSans-Bold.ttf"
                if bold
                else
                "/usr/share/fonts/dejavu/"
                "DejaVuSans.ttf"
            ),

            (
                "/usr/share/fonts/TTF/"
                "DejaVuSans-Bold.ttf"
                if bold
                else
                "/usr/share/fonts/TTF/"
                "DejaVuSans.ttf"
            ),
        ]

        for path in candidates:
            try:
                return ImageFont.truetype(
                    path,
                    size,
                )
            except Exception:
                continue

        patterns = [
            "/usr/share/fonts/**/*.ttf",
            "/usr/local/share/fonts/**/*.ttf",
        ]

        for pattern in patterns:
            for path in glob.glob(
                pattern,
                recursive=True,
            ):
                try:
                    return ImageFont.truetype(
                        path,
                        size,
                    )
                except Exception:
                    continue

        return ImageFont.load_default()

    # --------------------------------------------------------
    # FONTS
    # --------------------------------------------------------

    f_title = load_font(
        110,
        bold=True,
    )

    f_name = load_font(
        90,
        italic=True,
    )

    f_score = load_font(
        220,
        bold=True,
    )

    f_label = load_font(
        55,
        bold=True,
    )

    f_small = load_font(
        34,
    )

    # --------------------------------------------------------
    # CENTER TEXT HELPER
    # --------------------------------------------------------

    def center(
        text,
        font,
        y,
        fill="#ffffff",
    ):
        bbox = draw.textbbox(
            (0, 0),
            str(text),
            font=font,
        )

        width = (
            bbox[2] - bbox[0]
        )

        x = (
            W - width
        ) / 2

        draw.text(
            (x, y),
            str(text),
            font=font,
            fill=fill,
        )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    center(
        "IQ TEST",
        f_title,
        120,
        "#d4af37",
    )

    center(
        "CERTIFICATE",
        f_title,
        235,
        "#ffffff",
    )

    # --------------------------------------------------------
    # DECORATIVE LINE
    # --------------------------------------------------------

    draw.line(
        [
            (300, 430),
            (W - 300, 430),
        ],
        fill="#d4af37",
        width=2,
    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    safe_name = str(
        name or "User"
    )

    center(
        safe_name,
        f_name,
        330,
        "#ffffff",
    )

    draw.line(
        [
            (300, 460),
            (W - 300, 460),
        ],
        fill="#d4af37",
        width=2,
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    center(
        "IQ-STYLE SCORE",
        f_label,
        520,
        "#c9a227",
    )

    center(
        str(score),
        f_score,
        570,
        "#ffffff",
    )

    # --------------------------------------------------------
    # LEVEL
    # --------------------------------------------------------

    score_int = int(score or 0)

    if score_int >= 130:
        level = "JUDA YUQORI"

    elif score_int >= 115:
        level = "YUQORI DARAJA"

    elif score_int >= 100:
        level = "O‘RTA DARAJA"

    else:
        level = "RIVOJLANTIRISH KERAK"

    center(
        level,
        f_label,
        850,
        "#d4af37",
    )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    draw.text(
        (150, H - 160),
        f"Sana: {date}",
        font=f_small,
        fill="#c9a227",
    )

    draw.text(
        (150, H - 110),
        f"Kod: {code}",
        font=f_small,
        fill="#c9a227",
    )

    draw.text(
        (W - 500, H - 110),
        "IQ TEST BOT",
        font=f_small,
        fill="#c9a227",
    )

    # --------------------------------------------------------
    # VERIFIED SEAL
    # --------------------------------------------------------

    seal_x = W - 220
    seal_y = 240

    draw.ellipse(
        [
            seal_x - 100,
            seal_y - 100,
            seal_x + 100,
            seal_y + 100,
        ],
        outline="#d4af37",
        width=6,
    )

    draw.ellipse(
        [
            seal_x - 85,
            seal_y - 85,
            seal_x + 85,
            seal_y + 85,
        ],
        outline="#d4af37",
        width=2,
    )

    bbox = draw.textbbox(
        (0, 0),
        "VERIFIED",
        font=f_label,
    )

    text_width = (
        bbox[2] - bbox[0]
    )

    draw.text(
        (
            seal_x
            - text_width / 2,
            seal_y - 20,
        ),
        "VERIFIED",
        font=f_label,
        fill="#d4af37",
    )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    buffer = io.BytesIO()

    img.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    global db_pool

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not configured."
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

    # --------------------------------------------------------
    # TELEGRAM WEBHOOK
    # --------------------------------------------------------

    if (
        PUBLIC_BASE_URL
        and WEBHOOK_SECRET
    ):
        try:
            await bot.set_webhook(
                url=(
                    f"{PUBLIC_BASE_URL}"
                    "/telegram/webhook"
                ),
                secret_token=WEBHOOK_SECRET,
                drop_pending_updates=True,
            )

            logger.info(
                "Webhook set: %s",
                (
                    f"{PUBLIC_BASE_URL}"
                    "/telegram/webhook"
                ),
            )

        except Exception as e:
            logger.exception(
                "Webhook setup error: %s",
                e,
            )

    else:
        logger.warning(
            "PUBLIC_BASE_URL or "
            "WEBHOOK_SECRET is missing. "
            "Webhook was not configured."
        )

    yield

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

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
        "Application shutdown complete."
    )


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    lifespan=lifespan
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
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():
    try:

        if db_pool is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "starting"
                },
            )

        async with db_pool.acquire() as conn:
            await conn.execute(
                "SELECT 1"
            )

        return {
            "status": "ok"
        }

    except Exception as e:

        logger.exception(
            "Health check failed: %s",
            e,
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

    try:

        with open(
            "webapp/index.html",
            "r",
            encoding="utf-8",
        ) as file:

            return HTMLResponse(
                content=file.read()
            )

    except FileNotFoundError:

        return HTMLResponse(
            content=(
                "<h1>WebApp not found</h1>"
            ),
            status_code=404,
        )

    except Exception as e:

        logger.exception(
            "serve_app error: %s",
            e,
        )

        return HTMLResponse(
            content=(
                "<h1>Internal server error</h1>"
            ),
            status_code=500,
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

    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if (
        not WEBHOOK_SECRET
        or secret != WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid secret",
        )

    try:

        update_data = await request.json()

        update = Update.model_validate(
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

    except Exception as e:

        logger.exception(
            "Webhook error: %s",
            e,
        )

        # Telegram webhookga 500 qaytarmaymiz,
        # aks holda Telegram qayta-qayta yuborishi mumkin.
        return {
            "ok": True
        }


# ============================================================
# INIT DATA USER
# ============================================================

def get_user_from_init(
    init_data: str,
):
    return validate_init_data(
        init_data,
        BOT_TOKEN,
    )


# ============================================================
# AUTHENTICATED API USER
# ============================================================

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

    if not isinstance(
        body,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid request body",
        )

    init_data = body.get(
        "initData",
        "",
    )

    if (
        not isinstance(
            init_data,
            str,
        )
        or not init_data.strip()
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

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
# API — ME
# ============================================================

@app.post("/api/me")
async def api_me(
    request: Request,
):
    user, body = await require_user(
        request
    )

    uid = int(
        user["id"]
    )

    async with db_pool.acquire() as conn:

        db_user = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id=$1
            """,
            uid,
        )

        if not db_user:

            await conn.execute(
                """
                INSERT INTO users
                    (
                        user_id,
                        username,
                        first_name,
                        last_name,
                        last_seen
                    )
                VALUES
                    (
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
                WHERE user_id=$1
                """,
                uid,
            )

        else:

            await conn.execute(
                """
                UPDATE users
                SET last_seen=NOW(),
                    username=$2,
                    first_name=$3,
                    last_name=$4
                WHERE user_id=$1
                """,
                uid,
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
            )

        # ----------------------------------------------------
        # FAQAT OCHILGAN NATIJALAR
        # ----------------------------------------------------

        results = await conn.fetch(
            """
            SELECT
                LOWER(TRIM(r.test_type)) AS tt,
                MAX(r.score) AS best
            FROM results r
            JOIN test_attempts ta
                ON ta.id=r.attempt_id
            WHERE r.user_id=$1
              AND LOWER(TRIM(r.test_type))
                  IN ('iq', 'eq', 'pq')
              AND ta.result_visible=TRUE
            GROUP BY
                LOWER(TRIM(r.test_type))
            """,
            uid,
        )

        # ----------------------------------------------------
        # PENDING PAYMENTS
        # ----------------------------------------------------

        pending = await conn.fetch(
            """
            SELECT
                payment_id,
                product,
                amount,
                status,
                attempt_id,
                battle_id
            FROM payments
            WHERE user_id=$1
              AND status='pending'
            ORDER BY created_at DESC
            """,
            uid,
        )

        # ----------------------------------------------------
        # ACTIVE BATTLES
        # ----------------------------------------------------

        battles = await conn.fetch(
            """
            SELECT
                b.id,
                b.battle_code,
                b.status
            FROM battles b
            JOIN battle_players bp
                ON bp.battle_id=b.id
            WHERE bp.user_id=$1
              AND b.status NOT IN
                  (
                      'completed',
                      'draw',
                      'cancelled'
                  )
            ORDER BY b.created_at DESC
            """,
            uid,
        )

    completed = {
        row["tt"]: row["best"]
        for row in results
    }

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
# API — PROFILE SAVE
# ============================================================

@app.post("/api/profile/save")
async def api_profile_save(
    request: Request,
):
    user, body = await require_user(
        request
    )

    full_name = str(
        body.get(
            "full_name",
            "",
        )
        or ""
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

    # Age xavfsiz integerga o'tkaziladi.
    if age in (
        None,
        "",
    ):
        age_value = None
    else:
        try:
            age_value = int(age)
        except (
            TypeError,
            ValueError,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid age",
            )

        if not 1 <= age_value <= 120:
            raise HTTPException(
                status_code=400,
                detail="Invalid age",
            )

    async with db_pool.acquire() as conn:

        await conn.execute(
            """
            UPDATE users
            SET
                full_name=$1,
                gender=$2,
                age=$3,
                country=$4,
                last_seen=NOW()
            WHERE user_id=$5
            """,
            full_name or None,
            gender,
            age_value,
            country,
            user["id"],
        )

    return {
        "ok": True
    }


# ============================================================
# API — LIVE STATS
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

            # INTERVAL qiymati parametr bilan beriladi.
            online = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                WHERE last_seen >
                    NOW()
                    - ($1::text || ' minutes')
                      ::interval
                """,
                str(minutes),
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
            total,
        ),
        "online": max(
            0,
            online,
        ),
        "mode": mode,
    }


# ============================================================
# API — CONFIG
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

    return {
        "ok": True,
        "settings": {
            row["key"]: row["value"]
            for row in rows
        },
    }


# ============================================================
# API — START TEST SESSION
# ============================================================

@app.post("/api/session/start")
async def api_session_start(
    request: Request,
):
    user, body = await require_user(
        request
    )

    test_type = str(
        body.get(
            "test_type",
            "iq",
        )
        or "iq"
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

    sid = gen_session_id()

    async with db_pool.acquire() as conn:

        # Bir foydalanuvchining eski active
        # sessionlari qolib ketmasligi uchun
        # faqat shu test turidagi eski
        # sessionlarni yopamiz.
        await conn.execute(
            """
            UPDATE test_sessions
            SET status='expired'
            WHERE user_id=$1
              AND LOWER(TRIM(test_type))=$2
              AND status='active'
              AND expires_at < NOW()
            """,
            user["id"],
            test_type,
        )

        await conn.execute(
            """
            INSERT INTO test_sessions
                (
                    session_id,
                    user_id,
                    test_type,
                    status,
                    expires_at
                )
            VALUES
                (
                    $1,
                    $2,
                    $3,
                    'active',
                    NOW()
                    + INTERVAL '2 hours'
                )
            """,
            sid,
            user["id"],
            test_type,
        )

        attempt = await conn.fetchrow(
            """
            INSERT INTO test_attempts
                (
                    user_id,
                    test_type,
                    session_id,
                    status,
                    payment_status,
                    result_visible
                )
            VALUES
                (
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
# API — TEST SUBMIT
# ============================================================

@app.post("/api/test/submit")
async def api_test_submit(
    request: Request,
):
    user, body = await require_user(
        request
    )

    sid = body.get(
        "session_id"
    )

    answers = body.get(
        "answers",
        [],
    )

    duration = body.get(
        "duration",
        0,
    )

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if not isinstance(
        sid,
        str,
    ) or not sid.strip():
        raise HTTPException(
            status_code=400,
            detail="Session ID required",
        )

    if not isinstance(
        answers,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail="Answers must be a list",
        )

    try:
        duration = int(duration or 0)
    except (
        TypeError,
        ValueError,
    ):
        duration = 0

    if duration < 0:
        duration = 0

    # Haddan tashqari katta duration
    # ham qabul qilinmaydi.
    duration = min(
        duration,
        86400,
    )

    uid = int(
        user["id"]
    )

    async with db_pool.acquire() as conn:

        # ----------------------------------------------------
        # SESSION
        # ----------------------------------------------------

        sess = await conn.fetchrow(
            """
            SELECT *
            FROM test_sessions
            WHERE session_id=$1
              AND user_id=$2
            LIMIT 1
            """,
            sid,
            uid,
        )

        if not sess:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

        # Session expiry
        if (
            sess["expires_at"]
            and sess["expires_at"]
            < datetime.now(timezone.utc)
        ):
            await conn.execute(
                """
                UPDATE test_sessions
                SET status='expired'
                WHERE session_id=$1
                """,
                sid,
            )

            raise HTTPException(
                status_code=410,
                detail="Session expired",
            )

        if sess["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail="Already submitted",
            )

        test_type = (
            str(
                sess["test_type"]
                or ""
            )
            .strip()
            .lower()
        )

        if test_type not in {
            "iq",
            "eq",
            "pq",
        }:
            raise HTTPException(
                status_code=400,
                detail="Invalid test type",
            )

        # ----------------------------------------------------
        # ATTEMPT
        # ----------------------------------------------------

        attempt = await conn.fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE session_id=$1
              AND user_id=$2
            LIMIT 1
            """,
            sid,
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
                detail="Already completed",
            )

        attempt_id = int(
            attempt["id"]
        )

        # ====================================================
        # SERVER-SIDE SCORING
        # ====================================================

        score = 0
        correct = 0
        weighted = 0
        level = ""

        # ----------------------------------------------------
        # IQ
        # ----------------------------------------------------

        if test_type == "iq":

            max_weight = sum(
                int(q["weight"])
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
                    == int(
                        question["correct"]
                    )
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

            if score >= 115:
                level = "YUQORI DARAJA"

            elif score >= 100:
                level = "O‘RTA DARAJA"

            else:
                level = "RIVOJLANTIRISH"

        # ----------------------------------------------------
        # EQ
        # ----------------------------------------------------

        elif test_type == "eq":

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

                scores = question[
                    "scores"
                ]

                if (
                    answer is not None
                    and 0 <= answer < len(scores)
                ):
                    total += int(
                        scores[answer]
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

            # EQ'da correct frontenddan kelmaydi.
            correct = score

            if score >= 80:
                level = "JUDA YUQORI"

            elif score >= 60:
                level = "YUQORI"

            elif score >= 40:
                level = "O‘RTA"

            else:
                level = "RIVOJLANTIRISH"

        # ----------------------------------------------------
        # PQ
        # ----------------------------------------------------

        elif test_type == "pq":

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

                scores = question[
                    "scores"
                ]

                if (
                    answer is not None
                    and 0 <= answer < len(scores)
                ):
                    total += int(
                        scores[answer]
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

            if score >= 80:
                level = "JUDA YAXSHI"

            elif score >= 60:
                level = "YAXSHI"

            elif score >= 40:
                level = "O‘RTA"

            else:
                level = "RIVOJLANTIRISH"

        # ====================================================
        # PAYMENT DECISION
        # ====================================================

        price_key = f"{test_type}_price"
        retry_price_key = f"{test_type}_retry_price"

        first_price = await get_setting_int(
            price_key,
            0,
        )

        retry_price = await get_setting_int(
            retry_price_key,
            0,
        )

        # ----------------------------------------------------
        # OLD RESULT EXISTS?
        # ----------------------------------------------------
        #
        # Aynan shu yangi attemptdan oldingi natija.
        # Demak birinchi test va retry farqlanadi.
        # ----------------------------------------------------

        previous_result = await conn.fetchrow(
            """
            SELECT
                r.id,
                r.score,
                r.created_at
            FROM results r
            JOIN test_attempts ta
                ON ta.id=r.attempt_id
            WHERE r.user_id=$1
              AND LOWER(TRIM(r.test_type))=$2
              AND r.attempt_id <> $3
              AND ta.result_visible=TRUE
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            uid,
            test_type,
            attempt_id,
        )

        is_retry = (
            previous_result is not None
        )

        # ----------------------------------------------------
        # CORRECT PRODUCT
        # ----------------------------------------------------

        if is_retry:
            payment_product = (
                f"{test_type}_retry"
            )
            required_amount = retry_price

        else:
            payment_product = test_type
            required_amount = first_price

        # ----------------------------------------------------
        # PAYMENT STATE
        # ----------------------------------------------------

        payment_required = (
            required_amount > 0
        )

        payment_status = (
            "pending"
            if payment_required
            else "free"
        )

        result_visible = (
            not payment_required
        )

        # ====================================================
        # SAVE ATTEMPT
        # ====================================================

        await conn.execute(
            """
            UPDATE test_attempts
            SET
                finished_at=NOW(),
                score=$1,
                correct_count=$2,
                duration=$3,
                status='completed',
                payment_status=$4,
                result_visible=$5,
                level=$6
            WHERE id=$7
              AND user_id=$8
            """,
            score,
            correct,
            duration,
            payment_status,
            result_visible,
            level,
            attempt_id,
            uid,
        )

        # ====================================================
        # CLOSE SESSION
        # ====================================================

        await conn.execute(
            """
            UPDATE test_sessions
            SET status='completed'
            WHERE session_id=$1
              AND user_id=$2
            """,
            sid,
            uid,
        )

        # ====================================================
        # SAVE RESULT
        # ====================================================

        result_row = await conn.fetchrow(
            """
            INSERT INTO results
                (
                    user_id,
                    attempt_id,
                    test_type,
                    score,
                    level
                )
            VALUES
                (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5
                )
            RETURNING id
            """,
            uid,
            attempt_id,
            test_type,
            score,
            level,
        )

        result_id = int(
            result_row["id"]
        )

        # ====================================================
        # CERTIFICATE
        # ====================================================
        #
        # Faqat:
        #   IQ
        #   to‘lov kerak emas
        #   natija ochiq
        #
        # Payment pending bo‘lsa sertifikat hozircha
        # yaratilmaydi.
        # ====================================================

        certificate_code = None

        if (
            test_type == "iq"
            and result_visible
        ):

            urow = await conn.fetchrow(
                """
                SELECT
                    full_name,
                    first_name
                FROM users
                WHERE user_id=$1
                LIMIT 1
                """,
                uid,
            )

            name = (
                (
                    urow["full_name"]
                    or urow["first_name"]
                    or "User"
                )
                if urow
                else "User"
            )

            # Bir attempt uchun takroriy certificate
            # yaratmaslik.
            existing_cert = await conn.fetchrow(
                """
                SELECT
                    verification_code
                FROM certificates
                WHERE result_id=$1
                LIMIT 1
                """,
                result_id,
            )

            if existing_cert:

                certificate_code = (
                    existing_cert[
                        "verification_code"
                    ]
                )

            else:

                certificate_code = gen_code(
                    "IQ"
                )

                certificate_id = gen_code(
                    "CERT"
                )

                await conn.execute(
                    """
                    INSERT INTO certificates
                        (
                            certificate_id,
                            verification_code,
                            user_id,
                            result_id,
                            score,
                            type,
                            full_name
                        )
                    VALUES
                        (
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
                    certificate_code,
                    uid,
                    result_id,
                    score,
                    name,
                )

        # ====================================================
        # RESPONSE
        # ====================================================

        return {
            "ok": True,

            "score": score,
            "correct": correct,

            "total": (
                len(IQ_ANSWERS)
                if test_type == "iq"
                else (
                    len(EQ_ANSWERS)
                    if test_type == "eq"
                    else len(PQ_ANSWERS)
                )
            ),

            "level": level,
            "weighted": weighted,

            "result_visible": (
                result_visible
            ),

            "payment_required": (
                payment_required
            ),

            "payment_product": (
                payment_product
                if payment_required
                else None
            ),

            "payment_amount": (
                required_amount
                if payment_required
                else 0
            ),

            "is_retry": is_retry,

            "attempt_id": attempt_id,
            "result_id": result_id,

            "certificate_code": (
                certificate_code
            ),
        }


# ============================================================
# API — CERTIFICATE GENERATE
# ============================================================

@app.post(
    "/api/certificate/generate"
)
async def api_certificate_generate(
    request: Request,
):
    user, body = await require_user(
        request
    )

    uid = int(
        user["id"]
    )

    async with db_pool.acquire() as conn:

        cert = await conn.fetchrow(
            """
            SELECT
                c.*,
                u.full_name,
                u.first_name,
                ta.result_visible
            FROM certificates c
            JOIN users u
                ON u.user_id=c.user_id
            JOIN results r
                ON r.id=c.result_id
            JOIN test_attempts ta
                ON ta.id=r.attempt_id
            WHERE c.user_id=$1
              AND c.type='iq'
              AND ta.result_visible=TRUE
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            uid,
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
        code=cert[
            "verification_code"
        ],
        date=cert[
            "created_at"
        ].strftime(
            "%d.%m.%Y"
        ),
    )

    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition":
                (
                    'attachment; '
                    f'filename="'
                    f'{cert["verification_code"]}'
                    '.png"'
                )
        },
    )


# ============================================================
# API — CERTIFICATE CHECK
# ============================================================

@app.post(
    "/api/certificate/check"
)
async def api_certificate_check(
    request: Request,
):
    user, body = await require_user(
        request
    )

    uid = int(
        user["id"]
    )

    async with db_pool.acquire() as conn:

        cert = await conn.fetchrow(
            """
            SELECT
                c.verification_code
            FROM certificates c
            JOIN results r
                ON r.id=c.result_id
            JOIN test_attempts ta
                ON ta.id=r.attempt_id
            WHERE c.user_id=$1
              AND c.type='iq'
              AND ta.result_visible=TRUE
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            uid,
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
# RESULT ACCESS HELPER
# ============================================================

async def get_attempt_for_user(
    attempt_id: int,
    user_id: int,
):
    """
    Attempt faqat egasiga tegishli bo‘lsa qaytaradi.
    """

    async with db_pool.acquire() as conn:

        return await conn.fetchrow(
            """
            SELECT *
            FROM test_attempts
            WHERE id=$1
              AND user_id=$2
            LIMIT 1
            """,
            attempt_id,
            user_id,
        )


# ============================================================
# RESULT DETAILS
# ============================================================

@app.post(
    "/api/result/{attempt_id}"
)
async def api_result(
    attempt_id: int,
    request: Request,
):
    user, body = await require_user(
        request
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
            detail="Invalid attempt",
        )

    uid = int(
        user["id"]
    )

    async with db_pool.acquire() as conn:

        attempt = await conn.fetchrow(
            """
            SELECT
                ta.*,
                r.id AS result_id,
                r.score AS result_score,
                r.level AS result_level,
                r.created_at AS result_created_at
            FROM test_attempts ta
            LEFT JOIN results r
                ON r.attempt_id=ta.id
            WHERE ta.id=$1
              AND ta.user_id=$2
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            attempt_id,
            uid,
        )

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="Result not found",
        )

    if not attempt["result_visible"]:
        return {
            "ok": True,
            "result_visible": False,
            "payment_required": True,
            "attempt_id": attempt_id,
        }

    return {
        "ok": True,
        "result_visible": True,
        "payment_required": False,

        "attempt_id": attempt_id,

        "test_type": (
            attempt["test_type"]
        ),

        "score": (
            attempt["result_score"]
            if attempt["result_score"]
            is not None
            else attempt["score"]
        ),

        "level": (
            attempt["result_level"]
            if attempt["result_level"]
            else attempt["level"]
        ),

        "correct": (
            attempt["correct_count"]
        ),

        "duration": (
            attempt["duration"]
        ),
    }
    # ==================== PAYMENT ====================

TEST_PRODUCT_TYPES = {
    "iq": "iq",
    "iq_retry": "iq",
    "eq": "eq",
    "eq_retry": "eq",
    "pq": "pq",
    "pq_retry": "pq",
}


async def create_certificate_for_result(conn, user_id: int, result_id: int, test_type: str):
    """
    Result to'lovdan keyin ochilganda certificate yaratadi.
    Mavjud certificate bo'lsa qayta yaratmaydi.
    """
    test_type = str(test_type or "").lower().strip()

    if test_type not in {"iq", "eq", "pq"}:
        return

    exists = await conn.fetchval(
        """
        SELECT 1
        FROM certificates
        WHERE result_id=$1 AND type=$2
        LIMIT 1
        """,
        result_id,
        test_type,
    )

    if exists:
        return

    result = await conn.fetchrow(
        """
        SELECT score
        FROM results
        WHERE id=$1
        """,
        result_id,
    )

    if not result:
        return

    user_row = await conn.fetchrow(
        """
        SELECT full_name, first_name
        FROM users
        WHERE user_id=$1
        """,
        user_id,
    )

    full_name = (
        (user_row["full_name"] or user_row["first_name"] or "User")
        if user_row
        else "User"
    )

    prefix = {
        "iq": "IQ",
        "eq": "EQ",
        "pq": "PQ",
    }[test_type]

    await conn.execute(
        """
        INSERT INTO certificates
        (
            certificate_id,
            verification_code,
            user_id,
            result_id,
            score,
            type,
            full_name
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        gen_code("CERT"),
        gen_code(prefix),
        user_id,
        result_id,
        result["score"],
        test_type,
        full_name,
    )


@app.post("/api/payment/create")
async def api_payment_create(request: Request):
    user, body = await require_user(request)

    product = str(body.get("product") or "").strip().lower()

    attempt_id = body.get("attempt_id")
    battle_id = body.get("battle_id")

    try:
        attempt_id = int(attempt_id) if attempt_id is not None else None
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid attempt_id")

    try:
        battle_id = int(battle_id) if battle_id is not None else None
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid battle_id")

    price_map = {
        "iq": await get_setting_int("iq_price", 0),
        "iq_retry": await get_setting_int("iq_retry_price", 5000),

        "eq": await get_setting_int("eq_price", 0),
        "eq_retry": await get_setting_int("eq_retry_price", 5000),

        "pq": await get_setting_int("pq_price", 0),
        "pq_retry": await get_setting_int("pq_retry_price", 5000),

        "battle": await get_setting_int("battle_price", 7500),
    }

    if product not in price_map:
        raise HTTPException(400, "Invalid product")

    amount = price_map[product]

    # =========================================================
    # TEST PAYMENT
    # =========================================================

    if product != "battle":

        if not attempt_id:
            raise HTTPException(400, "attempt_id required")

        expected_type = TEST_PRODUCT_TYPES.get(product)

        async with db_pool.acquire() as conn:

            attempt = await conn.fetchrow(
                """
                SELECT
                    id,
                    user_id,
                    test_type,
                    payment_status,
                    result_visible,
                    finished_at
                FROM test_attempts
                WHERE id=$1
                """,
                attempt_id,
            )

            if not attempt:
                raise HTTPException(404, "Attempt not found")

            if int(attempt["user_id"]) != int(user["id"]):
                raise HTTPException(403, "Access denied")

            actual_type = str(
                attempt["test_type"] or ""
            ).strip().lower()

            if actual_type != expected_type:
                raise HTTPException(
                    400,
                    "Product and test type do not match",
                )

            # Natija allaqachon ochilgan bo'lsa qayta payment kerak emas.
            if attempt["result_visible"]:
                return {
                    "ok": True,
                    "free": True,
                    "already_paid": True,
                    "amount": 0,
                    "attempt_id": attempt_id,
                }

            # Retry mahsulot bo'lsa, oldingi ko'rinadigan natija mavjudligini tekshiramiz.
            if product.endswith("_retry"):

                previous = await conn.fetchval(
                    """
                    SELECT 1
                    FROM test_attempts ta
                    JOIN results r
                      ON r.attempt_id=ta.id
                    WHERE ta.user_id=$1
                      AND LOWER(TRIM(ta.test_type))=$2
                      AND ta.id <> $3
                      AND ta.result_visible=TRUE
                    LIMIT 1
                    """,
                    user["id"],
                    actual_type,
                    attempt_id,
                )

                if not previous:
                    raise HTTPException(
                        400,
                        "Retry is not available",
                    )

            # Bepul test
            if amount <= 0:

                await conn.execute(
                    """
                    UPDATE test_attempts
                    SET
                        payment_status='free',
                        result_visible=TRUE
                    WHERE id=$1
                    """,
                    attempt_id,
                )

                result = await conn.fetchrow(
                    """
                    SELECT id
                    FROM results
                    WHERE attempt_id=$1
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    attempt_id,
                )

                if result:
                    await create_certificate_for_result(
                        conn,
                        user["id"],
                        result["id"],
                        actual_type,
                    )

                return {
                    "ok": True,
                    "free": True,
                    "amount": 0,
                    "attempt_id": attempt_id,
                }

            # Bir xil pending paymentlarni ko'paytirmaymiz.
            existing = await conn.fetchrow(
                """
                SELECT payment_id
                FROM payments
                WHERE user_id=$1
                  AND product=$2
                  AND status='pending'
                  AND attempt_id=$3
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user["id"],
                product,
                attempt_id,
            )

            if existing:
                payment_id = existing["payment_id"]

            else:
                payment_id = gen_payment_id()

                await conn.execute(
                    """
                    INSERT INTO payments
                    (
                        payment_id,
                        user_id,
                        product,
                        amount,
                        attempt_id,
                        battle_id,
                        status
                    )
                    VALUES ($1, $2, $3, $4, $5, NULL, 'pending')
                    """,
                    payment_id,
                    user["id"],
                    product,
                    amount,
                    attempt_id,
                )

            cards = await conn.fetch(
                """
                SELECT
                    card_number,
                    holder,
                    bank
                FROM payment_cards
                WHERE active=TRUE
                ORDER BY created_at DESC
                """
            )

        return {
            "ok": True,
            "free": False,
            "payment_id": payment_id,
            "amount": amount,
            "product": product,
            "attempt_id": attempt_id,
            "cards": [dict(card) for card in cards],
        }

    # =========================================================
    # BATTLE PAYMENT
    # =========================================================

    if not battle_id:
        raise HTTPException(400, "battle_id required")

    async with db_pool.acquire() as conn:

        battle = await conn.fetchrow(
            """
            SELECT id, status
            FROM battles
            WHERE id=$1
            """,
            battle_id,
        )

        if not battle:
            raise HTTPException(404, "Battle not found")

        player = await conn.fetchrow(
            """
            SELECT user_id, payment_status
            FROM battle_players
            WHERE battle_id=$1
              AND user_id=$2
            """,
            battle_id,
            user["id"],
        )

        if not player:
            raise HTTPException(
                403,
                "You are not a battle participant",
            )

        if player["payment_status"] == "approved":
            return {
                "ok": True,
                "free": True,
                "already_paid": True,
                "amount": 0,
                "battle_id": battle_id,
            }

        existing = await conn.fetchrow(
            """
            SELECT payment_id
            FROM payments
            WHERE user_id=$1
              AND product='battle'
              AND battle_id=$2
              AND status='pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user["id"],
            battle_id,
        )

        if existing:
            payment_id = existing["payment_id"]

        else:
            payment_id = gen_payment_id()

            await conn.execute(
                """
                INSERT INTO payments
                (
                    payment_id,
                    user_id,
                    product,
                    amount,
                    attempt_id,
                    battle_id,
                    status
                )
                VALUES
                ($1, $2, 'battle', $3, NULL, $4, 'pending')
                """,
                payment_id,
                user["id"],
                amount,
                battle_id,
            )

        cards = await conn.fetch(
            """
            SELECT
                card_number,
                holder,
                bank
            FROM payment_cards
            WHERE active=TRUE
            ORDER BY created_at DESC
            """
        )

    return {
        "ok": True,
        "free": False,
        "payment_id": payment_id,
        "amount": amount,
        "product": "battle",
        "battle_id": battle_id,
        "cards": [dict(card) for card in cards],
    }


@app.post("/api/payment/{payment_id}")
async def api_payment_get(
    payment_id: str,
    request: Request,
):
    user, _ = await require_user(request)

    payment_id = str(payment_id or "").strip()

    if not payment_id:
        raise HTTPException(400, "Invalid payment_id")

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
                created_at,
                approved_at
            FROM payments
            WHERE payment_id=$1
              AND user_id=$2
            """,
            payment_id,
            user["id"],
        )

    if not payment:
        raise HTTPException(404, "Payment not found")

    return {
        "ok": True,
        "payment": dict(payment),
    }


# ==================== ADMIN ====================

ADMIN_STATE = {}


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "<b>ADMIN PANEL</b>",
        reply_markup=admin_kb(),
    )


@dp.callback_query(F.data == "admin:menu")
async def admin_menu(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        await cb.message.edit_text(
            "<b>ADMIN PANEL</b>",
            reply_markup=admin_kb(),
        )
    except Exception:
        await cb.message.answer(
            "<b>ADMIN PANEL</b>",
            reply_markup=admin_kb(),
        )

    await cb.answer()


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        async with db_pool.acquire() as conn:

            total = await conn.fetchval(
                "SELECT COUNT(*) FROM users"
            ) or 0

            today = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM users
                WHERE created_at::date=NOW()::date
                """
            ) or 0

            iq = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='iq'
                """
            ) or 0

            eq = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='eq'
                """
            ) or 0

            pq = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM results
                WHERE LOWER(TRIM(test_type))='pq'
                """
            ) or 0

            pay = await conn.fetchval(
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
            "<b>STATISTICS</b>\n\n"
            f"Users: <b>{total}</b>\n"
            f"Today: <b>{today}</b>\n"
            f"IQ: <b>{iq}</b>\n"
            f"EQ: <b>{eq}</b>\n"
            f"PQ: <b>{pq}</b>\n"
            f"Payments: <b>{pay}</b>\n"
            f"Revenue: <b>{revenue:,} so‘m</b>\n"
            f"Battles: <b>{battles}</b>"
        )

        b = InlineKeyboardBuilder()
        b.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        await cb.message.edit_text(
            text,
            reply_markup=b.as_markup(),
        )

    except Exception as e:
        logger.exception("admin_stats error: %s", e)

    await cb.answer()


@dp.callback_query(F.data == "admin:users")
async def admin_users(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
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

        text = "<b>USERS</b>\n\n"

        for row in rows:
            name = (
                row["first_name"]
                or row["username"]
                or "?"
            )

            text += (
                f"• <code>{row['user_id']}</code> — "
                f"{name} [{row['language']}]\n"
            )

        if not rows:
            text += "Bo‘sh"

        b = InlineKeyboardBuilder()
        b.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        await cb.message.edit_text(
            text,
            reply_markup=b.as_markup(),
        )

    except Exception as e:
        logger.exception("admin_users error: %s", e)

    await cb.answer()


@dp.callback_query(F.data == "admin:payments")
async def admin_payments(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
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
            b = InlineKeyboardBuilder()
            b.button(
                text="⬅️",
                callback_data="admin:menu",
            )

            await cb.message.edit_text(
                "Bo‘sh",
                reply_markup=b.as_markup(),
            )

            await cb.answer()
            return

        for payment in rows:

            keyboard = InlineKeyboardBuilder()

            keyboard.button(
                text="✅ Tasdiqlash",
                callback_data=f"pay_ok:{payment['payment_id']}",
            )

            keyboard.button(
                text="❌ Rad etish",
                callback_data=f"pay_no:{payment['payment_id']}",
            )

            keyboard.adjust(2)

            text = (
                f"<b>{payment['product']}</b>\n"
                f"User: <code>{payment['user_id']}</code>\n"
                f"Payment: <code>{payment['payment_id']}</code>\n"
                f"Amount: <b>{payment['amount']:,} so‘m</b>"
            )

            if payment["receipt_file_id"]:
                await cb.message.answer_photo(
                    payment["receipt_file_id"],
                    caption=text,
                    reply_markup=keyboard.as_markup(),
                )
            else:
                await cb.message.answer(
                    text,
                    reply_markup=keyboard.as_markup(),
                )

    except Exception as e:
        logger.exception("admin_payments error: %s", e)

    await cb.answer()
    # ==================== PAYMENT APPROVAL ====================

@dp.callback_query(F.data.startswith("pay_ok:"))
async def pay_ok(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        payment_id = cb.data.split(":", 1)[1].strip()

        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                """,
                payment_id,
            )

            if not payment:
                await cb.answer(
                    "Payment topilmadi",
                    show_alert=True,
                )
                return

            if payment["status"] != "pending":
                await cb.answer(
                    "Bu payment allaqachon ko‘rib chiqilgan",
                    show_alert=True,
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET
                    status='approved',
                    approved_at=NOW()
                WHERE payment_id=$1
                  AND status='pending'
                """,
                payment_id,
            )

            # =================================================
            # TEST PAYMENT
            # =================================================

            if payment["attempt_id"]:

                attempt = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        user_id,
                        test_type
                    FROM test_attempts
                    WHERE id=$1
                    """,
                    payment["attempt_id"],
                )

                if attempt:

                    test_type = str(
                        attempt["test_type"] or ""
                    ).strip().lower()

                    await conn.execute(
                        """
                        UPDATE test_attempts
                        SET
                            payment_status='paid',
                            result_visible=TRUE
                        WHERE id=$1
                        """,
                        payment["attempt_id"],
                    )

                    result = await conn.fetchrow(
                        """
                        SELECT id, score
                        FROM results
                        WHERE attempt_id=$1
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        payment["attempt_id"],
                    )

                    if result:
                        await create_certificate_for_result(
                            conn,
                            payment["user_id"],
                            result["id"],
                            test_type,
                        )

            # =================================================
            # BATTLE PAYMENT
            # =================================================

            if (
                payment["product"] == "battle"
                and payment["battle_id"]
            ):

                await conn.execute(
                    """
                    UPDATE battle_players
                    SET payment_status='approved'
                    WHERE battle_id=$1
                      AND user_id=$2
                    """,
                    payment["battle_id"],
                    payment["user_id"],
                )

                players = await conn.fetch(
                    """
                    SELECT
                        user_id,
                        payment_status
                    FROM battle_players
                    WHERE battle_id=$1
                    """,
                    payment["battle_id"],
                )

                if (
                    len(players) >= 2
                    and all(
                        p["payment_status"] == "approved"
                        for p in players
                    )
                ):
                    await conn.execute(
                        """
                        UPDATE battles
                        SET status='ready'
                        WHERE id=$1
                          AND status='waiting_for_payment'
                        """,
                        payment["battle_id"],
                    )

                    for player in players:
                        try:
                            await bot.send_message(
                                player["user_id"],
                                "⚔️ <b>Battle tayyor!</b>\n\n"
                                "Ikkala o‘yinchi ham to‘lovni tasdiqladi.",
                            )
                        except Exception:
                            pass

        # Userga umumiy payment tasdig‘i
        try:
            if payment["attempt_id"]:
                await bot.send_message(
                    payment["user_id"],
                    "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
                    "Natijangiz endi ochildi.",
                )

            elif payment["product"] == "battle":
                await bot.send_message(
                    payment["user_id"],
                    "✅ <b>Battle to‘lovi tasdiqlandi!</b>",
                )

        except Exception:
            pass

        # Admin xabarini yopamiz
        try:
            if cb.message.photo:
                await cb.message.edit_caption(
                    caption=(
                        "✅ <b>TASDIQLANDI</b>\n\n"
                        f"Payment: <code>{payment_id}</code>"
                    )
                )
            elif cb.message.caption:
                await cb.message.edit_caption(
                    caption=(
                        "✅ <b>TASDIQLANDI</b>\n\n"
                        f"Payment: <code>{payment_id}</code>"
                    )
                )
            else:
                await cb.message.edit_text(
                    "✅ <b>TASDIQLANDI</b>\n\n"
                    f"Payment: <code>{payment_id}</code>"
                )
        except Exception:
            pass

        await cb.answer("Tasdiqlandi")

    except Exception as e:
        logger.exception("pay_ok error: %s", e)
        await cb.answer(
            "Xatolik yuz berdi",
            show_alert=True,
        )


@dp.callback_query(F.data.startswith("pay_no:"))
async def pay_no(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        payment_id = cb.data.split(":", 1)[1].strip()

        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT *
                FROM payments
                WHERE payment_id=$1
                """,
                payment_id,
            )

            if not payment:
                await cb.answer(
                    "Payment topilmadi",
                    show_alert=True,
                )
                return

            if payment["status"] != "pending":
                await cb.answer(
                    "Bu payment allaqachon ko‘rib chiqilgan",
                    show_alert=True,
                )
                return

            await conn.execute(
                """
                UPDATE payments
                SET status='rejected'
                WHERE payment_id=$1
                  AND status='pending'
                """,
                payment_id,
            )

            if payment["attempt_id"]:

                await conn.execute(
                    """
                    UPDATE test_attempts
                    SET payment_status='rejected'
                    WHERE id=$1
                    """,
                    payment["attempt_id"],
                )

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
                    payment["user_id"],
                )

        try:
            await bot.send_message(
                payment["user_id"],
                "❌ <b>To‘lov rad etildi.</b>\n\n"
                "Chekni qayta tekshirib, kerak bo‘lsa yangi chek yuboring.",
            )
        except Exception:
            pass

        try:
            if cb.message.photo:
                await cb.message.edit_caption(
                    caption=(
                        "❌ <b>RAD ETILDI</b>\n\n"
                        f"Payment: <code>{payment_id}</code>"
                    )
                )
            elif cb.message.caption:
                await cb.message.edit_caption(
                    caption=(
                        "❌ <b>RAD ETILDI</b>\n\n"
                        f"Payment: <code>{payment_id}</code>"
                    )
                )
            else:
                await cb.message.edit_text(
                    "❌ <b>RAD ETILDI</b>\n\n"
                    f"Payment: <code>{payment_id}</code>"
                )
        except Exception:
            pass

        await cb.answer("Rad etildi")

    except Exception as e:
        logger.exception("pay_no error: %s", e)
        await cb.answer(
            "Xatolik yuz berdi",
            show_alert=True,
        )


# ==================== PRODUCTS ====================

@dp.callback_query(F.data == "admin:products")
async def admin_products(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        iq = await get_setting("iq_price", "0")
        iq_retry = await get_setting(
            "iq_retry_price",
            "5000",
        )

        eq = await get_setting("eq_price", "0")
        eq_retry = await get_setting(
            "eq_retry_price",
            "5000",
        )

        pq = await get_setting("pq_price", "0")
        pq_retry = await get_setting(
            "pq_retry_price",
            "5000",
        )

        battle = await get_setting(
            "battle_price",
            "7500",
        )

        text = (
            "<b>💰 NARXLAR</b>\n\n"
            f"IQ: <b>{iq}</b>\n"
            f"IQ retry: <b>{iq_retry}</b>\n"
            f"EQ: <b>{eq}</b>\n"
            f"EQ retry: <b>{eq_retry}</b>\n"
            f"PQ: <b>{pq}</b>\n"
            f"PQ retry: <b>{pq_retry}</b>\n"
            f"Battle: <b>{battle}</b>\n\n"
            "<i>0 = BEPUL</i>"
        )

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text=f"IQ ({iq})",
            callback_data="set:iq_price",
        )

        keyboard.button(
            text=f"IQ retry ({iq_retry})",
            callback_data="set:iq_retry_price",
        )

        keyboard.button(
            text=f"EQ ({eq})",
            callback_data="set:eq_price",
        )

        keyboard.button(
            text=f"EQ retry ({eq_retry})",
            callback_data="set:eq_retry_price",
        )

        keyboard.button(
            text=f"PQ ({pq})",
            callback_data="set:pq_price",
        )

        keyboard.button(
            text=f"PQ retry ({pq_retry})",
            callback_data="set:pq_retry_price",
        )

        keyboard.button(
            text=f"Battle ({battle})",
            callback_data="set:battle_price",
        )

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        keyboard.adjust(2, 2, 2, 1, 1)

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.exception("admin_products error: %s", e)

    await cb.answer()


@dp.callback_query(F.data.startswith("set:"))
async def admin_set_price(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        key = cb.data.split(":", 1)[1].strip()

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
                show_alert=True,
            )
            return

        current = await get_setting(
            key,
            "0",
        )

        ADMIN_STATE[cb.from_user.id] = {
            "action": "set_price",
            "key": key,
        }

        await cb.message.edit_text(
            f"<b>{key}</b>\n\n"
            f"Hozirgi: <b>{current}</b>\n\n"
            "Yangi narxni yuboring.\n"
            "<i>0 = bepul</i>"
        )

    except Exception as e:
        logger.exception(
            "admin_set_price error: %s",
            e,
        )

    await cb.answer()


# ==================== CARDS ====================

@dp.callback_query(F.data == "admin:cards")
async def admin_cards(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
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

        text = "<b>💳 KARTALAR</b>\n\n"

        for card in cards:

            status = "🟢" if card["active"] else "🔴"

            text += (
                f"{status} "
                f"<code>{card['card_number']}</code>\n"
                f"👤 {card['holder']}\n"
                f"🏦 {card['bank'] or '—'}\n\n"
            )

        if not cards:
            text += "Bo‘sh"

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="➕ Yangi",
            callback_data="card:add",
        )

        for card in cards:

            keyboard.button(
                text=f"✏️ {card['card_number'][-4:]}",
                callback_data=f"card:edit:{card['id']}",
            )

            keyboard.button(
                text=f"🗑 {card['card_number'][-4:]}",
                callback_data=f"card:del:{card['id']}",
            )

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        keyboard.adjust(1, 2)

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.exception(
            "admin_cards error: %s",
            e,
        )

    await cb.answer()


@dp.callback_query(F.data == "card:add")
async def card_add(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    ADMIN_STATE[cb.from_user.id] = {
        "action": "card_add",
    }

    await cb.message.edit_text(
        "💳 <b>KARTA QO‘SHISH</b>\n\n"
        "Format:\n"
        "<code>KARTA | HOLDER | BANK</code>"
    )

    await cb.answer()


@dp.callback_query(F.data.startswith("card:edit:"))
async def card_edit(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        cid = int(
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
                cid,
            )

        if not card:
            await cb.answer(
                "Karta topilmadi",
                show_alert=True,
            )
            return

        ADMIN_STATE[cb.from_user.id] = {
            "action": "card_edit",
            "id": cid,
        }

        await cb.message.edit_text(
            "💳 <b>KARTANI TAHRIRLASH</b>\n\n"
            f"Hozirgi:\n"
            f"<code>{card['card_number']} | "
            f"{card['holder']} | "
            f"{card['bank'] or '—'}</code>\n\n"
            "Yangi format:\n"
            "<code>KARTA | HOLDER | BANK</code>"
        )

    except Exception as e:
        logger.exception(
            "card_edit error: %s",
            e,
        )

    await cb.answer()


@dp.callback_query(F.data.startswith("card:del:"))
async def card_del(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        cid = int(
            cb.data.split(":")[2]
        )

        async with db_pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM payment_cards
                WHERE id=$1
                """,
                cid,
            )

        await cb.answer(
            "Karta o‘chirildi",
        )

        # Admin oynasini qayta chiqaramiz.
        await admin_cards(cb)

    except Exception as e:
        logger.exception(
            "card_del error: %s",
            e,
        )

        await cb.answer(
            "Xatolik",
            show_alert=True,
        )


# ==================== LIVE COUNTER ====================

@dp.callback_query(F.data == "admin:live")
async def admin_live(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        mode = await get_setting(
            "live_mode",
            "fake",
        )

        base = await get_setting(
            "live_fake_base",
            "95114",
        )

        online = await get_setting(
            "live_fake_online",
            "342",
        )

        delta = await get_setting(
            "live_fake_delta",
            "8",
        )

        text = (
            "<b>📊 LIVE COUNTER</b>\n\n"
            f"Rejim: <b>{mode.upper()}</b>\n"
            f"Base: <b>{base}</b>\n"
            f"Online: <b>{online}</b>\n"
            f"Delta: <b>±{delta}</b>"
        )

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="REAL",
            callback_data="live:mode:real",
        )

        keyboard.button(
            text="FAKE",
            callback_data="live:mode:fake",
        )

        keyboard.button(
            text=f"Base ({base})",
            callback_data="live:set:live_fake_base",
        )

        keyboard.button(
            text=f"Online ({online})",
            callback_data="live:set:live_fake_online",
        )

        keyboard.button(
            text=f"Delta (±{delta})",
            callback_data="live:set:live_fake_delta",
        )

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        keyboard.adjust(
            2,
            1,
            1,
            1,
            1,
        )

        try:
            await cb.message.edit_text(
                text,
                reply_markup=keyboard.as_markup(),
            )
        except Exception:
            await cb.message.answer(
                text,
                reply_markup=keyboard.as_markup(),
            )

    except Exception as e:
        logger.exception(
            "admin_live error: %s",
            e,
        )

    await cb.answer()


@dp.callback_query(F.data.startswith("live:mode:"))
async def live_set_mode(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    mode = cb.data.split(":")[2].strip().lower()

    if mode not in {"real", "fake"}:
        await cb.answer(
            "Noto‘g‘ri rejim",
            show_alert=True,
        )
        return

    await set_setting(
        "live_mode",
        mode,
    )

    await cb.answer(
        f"{mode.upper()}",
    )

    try:
        await admin_live(cb)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("live:set:"))
async def live_set_value(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    key = cb.data.split(":")[2].strip()

    allowed = {
        "live_fake_base",
        "live_fake_online",
        "live_fake_delta",
    }

    if key not in allowed:
        await cb.answer(
            "Noto‘g‘ri parametr",
            show_alert=True,
        )
        return

    ADMIN_STATE[cb.from_user.id] = {
        "action": "live_set",
        "key": key,
    }

    current = await get_setting(
        key,
        "0",
    )

    await cb.message.edit_text(
        f"<b>{key}</b>\n\n"
        f"Hozirgi: <b>{current}</b>\n\n"
        "Yangi qiymatni yuboring:"
    )

    await cb.answer()


# ==================== SETTINGS ====================

@dp.callback_query(F.data == "admin:settings")
async def admin_settings(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        support = await get_setting(
            "support_username",
            "omono_v",
        )

        text = (
            "<b>⚙️ SETTINGS</b>\n\n"
            f"Support: @{support}"
        )

        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.exception(
            "admin_settings error: %s",
            e,
        )

    await cb.answer()


@dp.callback_query(F.data == "admin:certs")
async def admin_certs(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    try:
        async with db_pool.acquire() as conn:

            count = await conn.fetchval(
                "SELECT COUNT(*) FROM certificates"
            ) or 0

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        await cb.message.edit_text(
            f"🏆 Sertifikatlar: <b>{count}</b>",
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.exception(
            "admin_certs error: %s",
            e,
        )

    await cb.answer()


# ==================== ADMIN BATTLES ====================

@dp.callback_query(F.data == "admin:battles")
async def admin_battles(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
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

        text = "<b>⚔️ BATTLES</b>\n\n"

        for battle in rows:
            text += (
                f"• <code>{battle['battle_code']}</code> "
                f"— {battle['status']}\n"
            )

        if not rows:
            text += "Bo‘sh"

        keyboard = InlineKeyboardBuilder()

        keyboard.button(
            text="⬅️",
            callback_data="admin:menu",
        )

        await cb.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.exception(
            "admin_battles error: %s",
            e,
        )

    await cb.answer()


# ==================== BROADCAST ====================

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(cb: CallbackQuery):

    if not await is_admin(cb.from_user.id):
        await cb.answer(
            "Ruxsat yo‘q",
            show_alert=True,
        )
        return

    await cb.message.edit_text(
        "📢 Broadcast:\n\n"
        "<code>/broadcast matn</code>"
    )

    await cb.answer()


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):

    if not await is_admin(message.from_user.id):
        return

    try:
        parts = (
            message.text or ""
        ).split(
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
                "Matn bo‘sh."
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

        for row in users:

            try:
                await bot.send_message(
                    row["user_id"],
                    broadcast_text,
                )

                sent += 1

                await asyncio.sleep(0.05)

            except Exception:
                failed += 1

        await message.answer(
            "📢 <b>Broadcast tugadi</b>\n\n"
            f"✅ Yuborildi: <b>{sent}</b>\n"
            f"❌ Xato: <b>{failed}</b>"
        )

    except Exception as e:
        logger.exception(
            "cmd_broadcast error: %s",
            e,
        )


# ==================== RECEIPT ====================

@dp.message(F.photo)
async def handle_receipt(message: types.Message):

    try:
        async with db_pool.acquire() as conn:

            payment = await conn.fetchrow(
                """
                SELECT
                    payment_id,
                    product,
                    amount,
                    user_id
                FROM payments
                WHERE user_id=$1
                  AND status='pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                message.from_user.id,
            )

            if not payment:
                return

            file_id = message.photo[-1].file_id

            await conn.execute(
                """
                UPDATE payments
                SET receipt_file_id=$1
                WHERE payment_id=$2
                """,
                file_id,
                payment["payment_id"],
            )

        await message.answer(
            "✅ <b>Chek qabul qilindi.</b>\n\n"
            "Admin tekshirishi kutilmoqda."
        )

        if ADMIN_USER_ID:

            try:
                keyboard = InlineKeyboardBuilder()

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
                    "🧾 <b>YANGI CHEK</b>\n\n"
                    f"User: "
                    f"<code>{message.from_user.id}</code>\n"
                    f"Product: "
                    f"<b>{payment['product']}</b>\n"
                    f"Amount: "
                    f"<b>{payment['amount']:,} so‘m</b>\n"
                    f"Payment: "
                    f"<code>{payment['payment_id']}</code>"
                )

                await bot.send_photo(
                    ADMIN_USER_ID,
                    file_id,
                    caption=caption,
                    reply_markup=keyboard.as_markup(),
                )

            except Exception as e:
                logger.exception(
                    "admin receipt send error: %s",
                    e,
                )

    except Exception as e:
        logger.exception(
            "handle_receipt error: %s",
            e,
        )


# ==================== ADMIN TEXT INPUT ====================

@dp.message(F.text)
async def handle_admin_text(message: types.Message):

    uid = message.from_user.id

    state = ADMIN_STATE.get(uid)

    if not state:
        return

    if not await is_admin(uid):

        ADMIN_STATE.pop(
            uid,
            None,
        )

        return

    action = state.get("action")

    # =========================================================
    # SET PRICE
    # =========================================================

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
                str(value),
            )

            ADMIN_STATE.pop(
                uid,
                None,
            )

            await message.answer(
                f"✅ {key} = <b>{value}</b>"
            )

        except Exception:
            await message.answer(
                "❌ Noto‘g‘ri qiymat.\n"
                "Faqat 0 yoki musbat son yuboring."
            )

        return

    # =========================================================
    # LIVE VALUE
    # =========================================================

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
                str(value),
            )

            ADMIN_STATE.pop(
                uid,
                None,
            )

            await message.answer(
                f"✅ {key} = <b>{value}</b>"
            )

        except Exception:
            await message.answer(
                "❌ Noto‘g‘ri qiymat."
            )

        return

    # =========================================================
    # ADD CARD
    # =========================================================

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
                    INSERT INTO payment_cards
                    (
                        card_number,
                        holder,
                        bank,
                        active
                    )
                    VALUES
                    ($1, $2, $3, TRUE)
                    """,
                    card_number,
                    holder,
                    bank,
                )

            ADMIN_STATE.pop(
                uid,
                None,
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

    # =========================================================
    # EDIT CARD
    # =========================================================

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

            if not card_number or not holder:
                raise ValueError

            card_id = int(
                state["id"]
            )

            async with db_pool.acquire() as conn:

                result = await conn.execute(
                    """
                    UPDATE payment_cards
                    SET
                        card_number=$1,
                        holder=$2,
                        bank=$3
                    WHERE id=$4
                    """,
                    card_number,
                    holder,
                    bank,
                    card_id,
                )

            ADMIN_STATE.pop(
                uid,
                None,
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


# ==================== RUNNER ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
    )