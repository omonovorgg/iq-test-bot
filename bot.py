import os
import io
import json
import hmac
import hashlib
import logging
import asyncio
import secrets
import string
import glob
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from urllib.parse import unquote

import asyncpg
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Update, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile, CallbackQuery, MenuButtonWebApp
)

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot").strip().lstrip("@")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0") or 0)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not WEBHOOK_SECRET and BOT_TOKEN:
    WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()

PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("iq-test-bot")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is required")
if not PUBLIC_BASE_URL:
    raise RuntimeError("PUBLIC_BASE_URL is required")

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
db_pool: asyncpg.Pool | None = None


IQ_QUESTIONS = [
    {"id":1,"weight":1,"matrix":[
        {"type":"dot","count":1},{"type":"dot","count":2},{"type":"dot","count":3},
        {"type":"dot","count":2},{"type":"dot","count":3},{"type":"dot","count":4},
        {"type":"dot","count":3},{"type":"dot","count":4},{"type":"question"}
    ],
    "options":[
        {"type":"dot","count":5},
        {"type":"dot","count":6},
        {"type":"dot","count":7},
        {"type":"dot","count":4}
    ],
    "correct":0},

    {"id":2,"weight":1,"matrix":[
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"circle","fill":"half"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"half"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"question"}
    ],
    "options":[
        {"type":"shape","shape":"circle","fill":"half"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"square","fill":"half"}
    ],
    "correct":0},

    {"id":3,"weight":1,"matrix":[
        {"type":"grid","pos":0},
        {"type":"grid","pos":1},
        {"type":"grid","pos":2},
        {"type":"grid","pos":1},
        {"type":"grid","pos":2},
        {"type":"grid","pos":3},
        {"type":"grid","pos":2},
        {"type":"grid","pos":3},
        {"type":"question"}
    ],
    "options":[
        {"type":"grid","pos":4},
        {"type":"grid","pos":5},
        {"type":"grid","pos":1},
        {"type":"grid","pos":6}
    ],
    "correct":0},

    {"id":4,"weight":1,"matrix":[
        {"type":"shape","shape":"triangle","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"question"}
    ],
    "options":[
        {"type":"shape","shape":"triangle","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"empty"}
    ],
    "correct":0},

    {"id":5,"weight":1,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"empty"},
        {"type":"combo","shapes":["square"],"fill":"empty"},
        {"type":"combo","shapes":["circle","square"],"fill":"empty"},
        {"type":"combo","shapes":["triangle"],"fill":"half"},
        {"type":"combo","shapes":["diamond"],"fill":"half"},
        {"type":"combo","shapes":["triangle","diamond"],"fill":"half"},
        {"type":"combo","shapes":["circle","triangle"],"fill":"full"},
        {"type":"combo","shapes":["square","diamond"],"fill":"full"},
        {"type":"question"}
    ],
    "options":[
        {"type":"combo","shapes":["circle","triangle","square","diamond"],"fill":"full"},
        {"type":"combo","shapes":["circle","square"],"fill":"full"},
        {"type":"combo","shapes":["triangle","diamond"],"fill":"full"},
        {"type":"combo","shapes":["circle","diamond"],"fill":"full"}
    ],
    "correct":0},

    {"id":6,"weight":1,"matrix":[
        {"type":"num","val":2},
        {"type":"num","val":4},
        {"type":"num","val":6},
        {"type":"num","val":3},
        {"type":"num","val":6},
        {"type":"num","val":9},
        {"type":"num","val":4},
        {"type":"num","val":8},
        {"type":"question"}
    ],
    "options":[
        {"type":"num","val":10},
        {"type":"num","val":12},
        {"type":"num","val":14},
        {"type":"num","val":16}
    ],
    "correct":1},

    {"id":7,"weight":2,"matrix":[
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"square","fill":"half"},
        {"type":"shape","shape":"triangle","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},
        {"type":"shape","shape":"triangle","fill":"full"},
        {"type":"shape","shape":"diamond","fill":"half"},
        {"type":"shape","shape":"triangle","fill":"half"},
        {"type":"shape","shape":"diamond","fill":"empty"},
        {"type":"question"}
    ],
    "options":[
        {"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"circle","fill":"half"},
        {"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"full"}
    ],
    "correct":0},

    {"id":8,"weight":2,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"half"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},
        {"type":"combo","shapes":["square"],"fill":"half"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},
        {"type":"combo","shapes":["diamond"],"fill":"full"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},
        {"type":"combo","shapes":["diamond"],"fill":"full"},
        {"type":"question"}
    ],
    "options":[
        {"type":"combo","shapes":["circle"],"fill":"half"},
        {"type":"combo","shapes":["circle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"empty"},
        {"type":"combo","shapes":["diamond"],"fill":"half"}
    ],
    "correct":1},

    {"id":9,"weight":2,"matrix":[
        {"type":"dot","count":1},
        {"type":"dot","count":3},
        {"type":"dot","count":6},
        {"type":"dot","count":2},
        {"type":"dot","count":5},
        {"type":"dot","count":9},
        {"type":"dot","count":3},
        {"type":"dot","count":7},
        {"type":"question"}
    ],
    "options":[
        {"type":"dot","count":10},
        {"type":"dot","count":11},
        {"type":"dot","count":12},
        {"type":"dot","count":13}
    ],
    "correct":2},

    {"id":10,"weight":2,"matrix":[
        {"type":"grid","pos":0},
        {"type":"grid","pos":4},
        {"type":"grid","pos":8},
        {"type":"grid","pos":1},
        {"type":"grid","pos":4},
        {"type":"grid","pos":7},
        {"type":"grid","pos":2},
        {"type":"grid","pos":4},
        {"type":"question"}
    ],
    "options":[
        {"type":"grid","pos":6},
        {"type":"grid","pos":5},
        {"type":"grid","pos":3},
        {"type":"grid","pos":0}
    ],
    "correct":0},

    {"id":11,"weight":2,"matrix":[
        {"type":"num","val":3},
        {"type":"num","val":5},
        {"type":"num","val":8},
        {"type":"num","val":5},
        {"type":"num","val":8},
        {"type":"num","val":13},
        {"type":"num","val":8},
        {"type":"num","val":13},
        {"type":"question"}
    ],
    "options":[
        {"type":"num","val":18},
        {"type":"num","val":21},
        {"type":"num","val":20},
        {"type":"num","val":22}
    ],
    "correct":1},

    {"id":12,"weight":2,"matrix":[
        {"type":"combo","shapes":["circle","square"],"fill":"empty"},
        {"type":"combo","shapes":["circle","triangle"],"fill":"half"},
        {"type":"combo","shapes":["circle","diamond"],"fill":"full"},
        {"type":"combo","shapes":["square","triangle"],"fill":"half"},
        {"type":"combo","shapes":["square","diamond"],"fill":"full"},
        {"type":"combo","shapes":["square","circle"],"fill":"empty"},
        {"type":"combo","shapes":["triangle","diamond"],"fill":"full"},
        {"type":"combo","shapes":["triangle","circle"],"fill":"empty"},
        {"type":"question"}
    ],
    "options":[
        {"type":"combo","shapes":["triangle","square"],"fill":"half"},
        {"type":"combo","shapes":["triangle","square"],"fill":"full"},
        {"type":"combo","shapes":["diamond","square"],"fill":"empty"},
        {"type":"combo","shapes":["circle","diamond"],"fill":"half"}
    ],
    "correct":0},

    {"id":13,"weight":3,"matrix":[
        {"type":"num","val":2},
        {"type":"num","val":3},
        {"type":"num","val":5},
        {"type":"num","val":3},
        {"type":"num","val":5},
        {"type":"num","val":8},
        {"type":"num","val":5},
        {"type":"num","val":8},
        {"type":"question"}
    ],
    "options":[
        {"type":"num","val":12},
        {"type":"num","val":13},
        {"type":"num","val":14},
        {"type":"num","val":15}
    ],
    "correct":1},

    {"id":14,"weight":3,"matrix":[
        {"type":"grid","pos":0},
        {"type":"grid","pos":2},
        {"type":"grid","pos":4},
        {"type":"grid","pos":3},
        {"type":"grid","pos":5},
        {"type":"grid","pos":7},
        {"type":"grid","pos":6},
        {"type":"grid","pos":8},
        {"type":"question"}
    ],
    "options":[
        {"type":"grid","pos":1},
        {"type":"grid","pos":0},
        {"type":"grid","pos":2},
        {"type":"grid","pos":7}
    ],
    "correct":0},

    {"id":15,"weight":3,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"empty"},
        {"type":"combo","shapes":["circle","square"],"fill":"half"},
        {"type":"combo","shapes":["circle","square","triangle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"half"},
        {"type":"combo","shapes":["square","triangle"],"fill":"full"},
        {"type":"combo","shapes":["square","triangle","diamond"],"fill":"empty"},
        {"type":"combo","shapes":["triangle"],"fill":"full"},
        {"type":"combo","shapes":["triangle","diamond"],"fill":"empty"},
        {"type":"question"}
    ],
    "options":[
        {"type":"combo","shapes":["triangle","diamond","circle"],"fill":"half"},
        {"type":"combo","shapes":["triangle","diamond","circle"],"fill":"full"},
        {"type":"combo","shapes":["diamond","circle"],"fill":"half"},
        {"type":"combo","shapes":["triangle","circle"],"fill":"empty"}
    ],
    "correct":0},

    {"id":16,"weight":3,"matrix":[
        {"type":"num","val":4},
        {"type":"num","val":7},
        {"type":"num","val":13},
        {"type":"num","val":5},
        {"type":"num","val":9},
        {"type":"num","val":17},
        {"type":"num","val":6},
        {"type":"num","val":11},
        {"type":"question"}
    ],
    "options":[
        {"type":"num","val":21},
        {"type":"num","val":22},
        {"type":"num","val":23},
        {"type":"num","val":24}
    ],
    "correct":0},

    {"id":17,"weight":3,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"full"},
        {"type":"combo","shapes":["triangle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"half"},
        {"type":"combo","shapes":["triangle"],"fill":"half"},
        {"type":"combo","shapes":["diamond"],"fill":"half"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},
        {"type":"combo","shapes":["diamond"],"fill":"empty"},
        {"type":"question"}
    ],
    "options":[
        {"type":"combo","shapes":["circle"],"fill":"empty"},
        {"type":"combo","shapes":["circle"],"fill":"half"},
        {"type":"combo","shapes":["diamond"],"fill":"empty"},
        {"type":"combo","shapes":["square"],"fill":"empty"}
    ],
    "correct":0},

    {"id":18,"weight":3,"matrix":[
        {"type":"num","val":1},
        {"type":"num","val":4},
        {"type":"num","val":9},
        {"type":"num","val":8},
        {"type":"num","val":27},
        {"type":"num","val":64},
        {"type":"num","val":125},
        {"type":"num","val":216},
        {"type":"question"}
    ],
    "options":[
        {"type":"num","val":343},
        {"type":"num","val":512},
        {"type":"num","val":729},
        {"type":"num","val":256}
    ],
    "correct":0},
]


EQ_QUESTIONS = [
    (
        "You are interrupted during an important task. What is the most constructive first step?",
        [
            "React angrily",
            "Pause, clarify the interruption, and choose a response",
            "Ignore everyone",
            "Quit the task"
        ],
        1
    ),
    (
        "A friend criticizes your work in public. What is the most constructive response?",
        [
            "Attack back",
            "Change the subject",
            "Listen, ask what could be improved, and discuss it calmly",
            "Pretend nothing happened"
        ],
        2
    ),
    (
        "You notice a teammate is unusually quiet. What is the most useful response?",
        [
            "Pressure them to talk",
            "Check in privately and give them space to respond",
            "Gossip about it",
            "Exclude them"
        ],
        1
    ),
    (
        "You make a mistake that affects other people. What should you do next?",
        [
            "Acknowledge it, explain briefly, and help repair the impact",
            "Hide it until someone notices",
            "Blame someone else",
            "Wait silently"
        ],
        0
    ),
    (
        "Two people strongly disagree in a discussion. What is most likely to improve the conversation?",
        [
            "Choose a side immediately",
            "Raise your voice so your point wins",
            "Clarify each person's viewpoint and the point of disagreement",
            "End the discussion without hearing either side"
        ],
        2
    ),
    (
        "You receive a stressful message late at night. What is usually the most constructive approach?",
        [
            "Reply immediately while angry",
            "Forward it to several people",
            "Delete the sender",
            "Pause, regulate your reaction, and respond when you can think clearly"
        ],
        3
    ),
]


PQ_QUESTIONS = [
    (
        "You have three tasks due today. What is the most practical first step?",
        [
            "Do random tasks",
            "Prioritize them by urgency and impact",
            "Avoid all tasks",
            "Start with whichever looks easiest"
        ],
        1
    ),
    (
        "A long project feels overwhelming. What is most useful?",
        [
            "Never plan",
            "Wait until motivation appears",
            "Do everything at once",
            "Break the project into concrete milestones and next actions"
        ],
        3
    ),
    (
        "Your current plan stops producing the expected result. What should you do?",
        [
            "Repeat it blindly",
            "Abandon the goal immediately",
            "Review the evidence, identify what changed, and adjust the plan",
            "Blame the tool"
        ],
        2
    ),
    (
        "You keep delaying a difficult task. Which approach is most actionable?",
        [
            "Make the task larger",
            "Define a small concrete first action and start it",
            "Ignore the deadline",
            "Add unrelated tasks"
        ],
        1
    ),
    (
        "A goal conflicts with a new opportunity. What helps you decide?",
        [
            "Compare the trade-offs against your priorities",
            "Choose randomly",
            "Ask everyone else to decide for you",
            "Do both without limits"
        ],
        0
    ),
    (
        "You finish an important milestone. What improves the next phase?",
        [
            "Never review it",
            "Reset everything",
            "Record what worked, what failed, and what to change next",
            "Avoid feedback"
        ],
        2
    ),
]


TRANSLATIONS = {
    "uz": {
        "choose_lang": "Tilni tanlang:",
        "welcome": "Salom, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nAqlingizni sinash uchun Mini App'ni oching.",
        "menu_test": "🧠 IQ · EQ · PQ testini ishlash",
        "menu_cert": "📜 Sertifikatim",
        "menu_rank": "🏆 Reyting",
        "menu_earn": "💰 Pul ishlash",
        "menu_help": "ℹ️ Narx va yordam",
        "menu_lang": "🌐 Til",
        "no_cert": "Hali sertifikatingiz yo‘q.",
        "cert_not_found": "Sertifikat topilmadi.",
        "lang_changed": "Til o‘zgartirildi.",
    },
    "ru": {
        "choose_lang": "Выберите язык:",
        "welcome": "Привет, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nОткройте Mini App, чтобы пройти тест.",
        "menu_test": "🧠 Пройти IQ · EQ · PQ",
        "menu_cert": "📜 Мой сертификат",
        "menu_rank": "🏆 Рейтинг",
        "menu_earn": "💰 Заработать",
        "menu_help": "ℹ️ Цена и помощь",
        "menu_lang": "🌐 Язык",
        "lang_changed": "Язык изменён.",
    },
    "en": {
        "choose_lang": "Choose language:",
        "welcome": "Hello, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nOpen the Mini App to take the test.",
        "menu_test": "🧠 Take IQ · EQ · PQ",
        "menu_cert": "📜 My certificate",
        "menu_rank": "🏆 Ranking",
        "menu_earn": "💰 Earn",
        "menu_help": "ℹ️ Prices & help",
        "menu_lang": "🌐 Language",
        "lang_changed": "Language changed.",
    }
}


def t(lang: str, key: str, **kwargs):
    lang = lang if lang in TRANSLATIONS else "uz"
    value = TRANSLATIONS[lang].get(key, key)
    return value.format(**kwargs)


def utcnow():
    return datetime.now(timezone.utc)


def json_dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


async def db_execute(query, *args):
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with db_pool.acquire() as conn:
        return await conn.execute(query, *args)


async def db_fetch(query, *args):
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with db_pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def db_fetchrow(query, *args):
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def db_fetchval(query, *args):
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with db_pool.acquire() as conn:
        return await conn.fetchval(query, *args)
        async def init_db():
    global db_pool

    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )

    await db_execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT NOT NULL DEFAULT 'uz',
            country TEXT,
            gender TEXT,
            age INTEGER,
            full_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id BIGINT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS test_sessions (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            test_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            questions JSONB NOT NULL,
            answers JSONB NOT NULL DEFAULT '{}'::jsonb,
            current_index INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS test_attempts (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            session_id UUID REFERENCES test_sessions(id) ON DELETE SET NULL,
            test_type TEXT NOT NULL,
            answers JSONB NOT NULL,
            score NUMERIC NOT NULL DEFAULT 0,
            max_score NUMERIC NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(session_id)
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS results (
            id UUID PRIMARY KEY,
            attempt_id UUID NOT NULL REFERENCES test_attempts(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            test_type TEXT NOT NULL,
            score NUMERIC NOT NULL DEFAULT 0,
            level TEXT,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            product TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            card_id UUID,
            receipt_file_id TEXT,
            receipt_filename TEXT,
            receipt_content_type TEXT,
            admin_id BIGINT,
            admin_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS payment_cards (
            id UUID PRIMARY KEY,
            card_number TEXT NOT NULL,
            holder TEXT,
            bank TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            certificate_id TEXT UNIQUE,
            verification_code TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL DEFAULT 'IQ',
            full_name TEXT NOT NULL,
            score NUMERIC NOT NULL,
            level TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS battles (
            id UUID PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            created_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            price INTEGER NOT NULL DEFAULT 7500,
            question_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS battle_players (
            id UUID PRIMARY KEY,
            battle_id UUID NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            payment_status TEXT NOT NULL DEFAULT 'pending',
            payment_id UUID,
            score NUMERIC,
            answers JSONB,
            completed_at TIMESTAMPTZ,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(battle_id, user_id)
        )
    """)

    await db_execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id UUID PRIMARY KEY,
            referrer_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            referred_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            reward INTEGER NOT NULL DEFAULT 0,
            rewarded BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(referrer_id, referred_id),
            UNIQUE(referred_id)
        )
    """)

    migrations = [
        ("users", "updated_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),
        ("users", "username", "TEXT"),
        ("users", "first_name", "TEXT"),
        ("users", "last_name", "TEXT"),
        ("users", "language", "TEXT NOT NULL DEFAULT 'uz'"),
        ("users", "country", "TEXT"),
        ("users", "gender", "TEXT"),
        ("users", "age", "INTEGER"),
        ("users", "full_name", "TEXT"),

        ("certificates", "certificate_id", "TEXT"),
        ("certificates", "verification_code", "TEXT"),
        ("certificates", "type", "TEXT NOT NULL DEFAULT 'IQ'"),
        ("certificates", "full_name", "TEXT"),
        ("certificates", "score", "NUMERIC NOT NULL DEFAULT 0"),
        ("certificates", "level", "TEXT"),

        ("payment_cards", "bank", "TEXT"),
        ("payment_cards", "active", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("payment_cards", "created_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),

        ("payments", "card_id", "UUID"),
        ("payments", "receipt_file_id", "TEXT"),
        ("payments", "receipt_filename", "TEXT"),
        ("payments", "receipt_content_type", "TEXT"),
        ("payments", "admin_id", "BIGINT"),
        ("payments", "admin_note", "TEXT"),
        ("payments", "updated_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),

        ("test_sessions", "answers", "JSONB NOT NULL DEFAULT '{}'::jsonb"),
        ("test_sessions", "current_index", "INTEGER NOT NULL DEFAULT 0"),
        ("test_sessions", "expires_at", "TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '2 hours'"),

        ("battle_players", "payment_id", "UUID"),
        ("battle_players", "score", "NUMERIC"),
        ("battle_players", "answers", "JSONB"),
        ("battle_players", "completed_at", "TIMESTAMPTZ"),
    ]

    for table, column, definition in migrations:
        try:
            await db_execute(
                f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {definition}'
            )
        except Exception as exc:
            logger.warning(
                "Migration skipped: %s.%s -> %s",
                table,
                column,
                exc,
            )

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_users_updated_at
        ON users(updated_at)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_test_sessions_user
        ON test_sessions(user_id)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_test_sessions_status
        ON test_sessions(status)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_attempts_user
        ON test_attempts(user_id)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_results_user
        ON results(user_id)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_payments_user
        ON payments(user_id)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_payments_status
        ON payments(status)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_battle_players_battle
        ON battle_players(battle_id)
    """)

    await db_execute("""
        CREATE INDEX IF NOT EXISTS idx_certificates_user
        ON certificates(user_id)
    """)

    await db_execute("""
        INSERT INTO app_settings(key, value)
        VALUES
            ('iq_price', '0'),
            ('iq_retry_price', '5000'),
            ('eq_price', '0'),
            ('eq_retry_price', '5000'),
            ('pq_price', '0'),
            ('pq_retry_price', '5000'),
            ('battle_price', '7500'),
            ('live_mode', 'fake'),
            ('live_fake_base', '95114'),
            ('live_fake_online', '342'),
            ('live_fake_delta', '8')
        ON CONFLICT(key) DO NOTHING
    """)

    if ADMIN_USER_ID:
        await db_execute("""
            INSERT INTO admins(user_id)
            VALUES($1)
            ON CONFLICT(user_id) DO NOTHING
        """, ADMIN_USER_ID)

    logger.info("Database initialized successfully")


async def get_setting(key: str, default=None):
    row = await db_fetchrow(
        "SELECT value FROM app_settings WHERE key=$1",
        key
    )
    return row["value"] if row else default


async def set_setting(key: str, value):
    await db_execute("""
        INSERT INTO app_settings(key, value)
        VALUES($1, $2)
        ON CONFLICT(key)
        DO UPDATE SET value=EXCLUDED.value
    """, key, str(value))


async def get_int_setting(key: str, default: int):
    value = await get_setting(key, str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def get_user(user_id: int):
    return await db_fetchrow(
        "SELECT * FROM users WHERE user_id=$1",
        user_id
    )


async def upsert_user(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language: str | None = None,
):
    if language not in TRANSLATIONS:
        language = "uz"

    await db_execute("""
        INSERT INTO users(
            user_id,
            username,
            first_name,
            last_name,
            language,
            updated_at
        )
        VALUES($1,$2,$3,$4,$5,NOW())
        ON CONFLICT(user_id)
        DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_name=EXCLUDED.last_name,
            updated_at=NOW()
    """,
        user_id,
        username,
        first_name,
        last_name,
        language,
    )


def main_keyboard(lang="uz"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "menu_cert")),
                KeyboardButton(text=t(lang, "menu_rank")),
            ],
            [
                KeyboardButton(text=t(lang, "menu_earn")),
                KeyboardButton(text=t(lang, "menu_help")),
            ],
            [
                KeyboardButton(text=t(lang, "menu_lang")),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def app_inline_keyboard(lang="uz"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "menu_test"),
                    web_app=WebAppInfo(
                        url=f"{WEBAPP_URL}/app"
                    ),
                )
            ]
        ]
    )


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )


async def is_admin(user_id: int):
    if user_id == ADMIN_USER_ID:
        return True

    row = await db_fetchrow(
        "SELECT 1 FROM admins WHERE user_id=$1",
        user_id
    )
    return bool(row)


def parse_webapp_init_data(init_data: str):
    pairs = {}

    for item in init_data.split("&"):
        if "=" not in item:
            continue

        key, value = item.split("=", 1)

        if key in pairs:
            continue

        pairs[key] = value

    return pairs


def validate_init_data(init_data: str):
    if not init_data:
        return None

    pairs = parse_webapp_init_data(init_data)

    received_hash = pairs.get("hash")
    if not received_hash:
        return None

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw:
        return None

    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return None

    now = int(datetime.now(timezone.utc).timestamp())

    if auth_date > now + 60:
        return None

    if now - auth_date > 86400:
        return None

    data_check_items = []

    for key in sorted(pairs):
        if key in {"hash", "signature"}:
            continue

        data_check_items.append(
            f"{key}={pairs[key]}"
        )

    data_check_string = "\n".join(data_check_items)

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        calculated_hash.lower(),
        received_hash.lower(),
    ):
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None

    try:
        user_data = json.loads(unquote(user_raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    if not isinstance(user_data, dict):
        return None

    user_id = user_data.get("id")
    if not user_id:
        return None

    return {
        "user": user_data,
        "user_id": int(user_id),
        "auth_date": auth_date,
        "query_id": pairs.get("query_id"),
    }


async def authenticated_user(request: Request):
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("X-Telegram-WebApp-Init-Data")
        or ""
    )

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="initData is empty"
        )

    validated = validate_init_data(init_data)

    if not validated:
        raise HTTPException(
            status_code=401,
            detail="invalid Telegram initData"
        )

    user_data = validated["user"]

    await upsert_user(
        validated["user_id"],
        user_data.get("username"),
        user_data.get("first_name"),
        user_data.get("last_name"),
    )

    return validated


def require_admin(request: Request, auth):
    user_id = auth["user_id"]

    if user_id != ADMIN_USER_ID:
        raise HTTPException(
            status_code=403,
            detail="admin access required"
        )


def clean_text(value, max_length=500):
    if value is None:
        return ""

    value = str(value).strip()

    return value[:max_length]


def normalize_gender(value):
    value = clean_text(value, 20).lower()

    allowed = {
        "male",
        "female",
        "other",
        "erkak",
        "ayol",
        "boshqa",
        "мужчина",
        "женщина",
        "другое",
    }

    return value if value in allowed else None


def normalize_age(value):
    try:
        age = int(value)
    except (TypeError, ValueError):
        return None

    if age < 5 or age > 100:
        return None

    return age


def normalize_country(value):
    value = clean_text(value, 100)

    return value or None


def iq_level(score: float):
    if score < 80:
        return "Boshlang‘ich"
    if score < 90:
        return "O‘rtacha-past"
    if score < 100:
        return "O‘rtacha"
    if score < 110:
        return "Yaxshi"
    if score < 120:
        return "Yuqori"
    if score < 130:
        return "Juda yuqori"
    return "Exceptional"


def calculate_iq(answers: dict):
    total_weight = sum(q["weight"] for q in IQ_QUESTIONS)
    earned = 0

    for q in IQ_QUESTIONS:
        raw = answers.get(str(q["id"]))

        try:
            selected = int(raw)
        except (TypeError, ValueError):
            continue

        if selected == q["correct"]:
            earned += q["weight"]

    ratio = earned / total_weight if total_weight else 0

    score = round(70 + ratio * 60)

    return max(70, min(130, score)), earned, total_weight


def calculate_standard_score(
    questions,
    answers: dict,
):
    correct = 0

    for index, question in enumerate(questions):
        raw = answers.get(str(index))

        try:
            selected = int(raw)
        except (TypeError, ValueError):
            continue

        if selected == question[2]:
            correct += 1

    total = len(questions)

    percentage = round(
        (correct / total) * 100
    ) if total else 0

    return percentage, correct, total


def make_test_payload(test_type: str):
    if test_type == "IQ":
        return [
            {
                "id": q["id"],
                "weight": q["weight"],
                "matrix": q["matrix"],
                "options": q["options"],
            }
            for q in IQ_QUESTIONS
        ]

    if test_type == "EQ":
        return [
            {
                "id": index,
                "question": question,
                "options": options,
            }
            for index, (question, options, _) in enumerate(EQ_QUESTIONS)
        ]

    if test_type == "PQ":
        return [
            {
                "id": index,
                "question": question,
                "options": options,
            }
            for index, (question, options, _) in enumerate(PQ_QUESTIONS)
        ]

    raise ValueError("Unknown test type")


def make_random_battle_code(length=4):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(
        secrets.choice(alphabet)
        for _ in range(length)
    )


async def unique_battle_code(conn):
    for _ in range(30):
        code = make_random_battle_code()

        exists = await conn.fetchval(
            "SELECT 1 FROM battles WHERE code=$1",
            code
        )

        if not exists:
            return code

    raise RuntimeError("Could not generate unique battle code")
    async def calculate_personal_profile(user_id: int):
    rows = await db_fetch("""
        SELECT test_type, score
        FROM results
        WHERE user_id=$1
        ORDER BY created_at DESC
    """, user_id)

    latest = {}

    for row in rows:
        test_type = row["test_type"]

        if test_type not in latest:
            latest[test_type] = float(row["score"])

    iq = latest.get("IQ")
    eq = latest.get("EQ")
    pq = latest.get("PQ")

    strengths = []
    development = []

    if iq is not None:
        if iq >= 115:
            strengths.append("Mantiqiy va analitik fikrlash")
        elif iq < 90:
            development.append("Mantiqiy masalalarni bosqichma-bosqich tahlil qilish")

    if eq is not None:
        if eq >= 75:
            strengths.append("Hissiy vaziyatlarni anglash")
        elif eq < 55:
            development.append("Hissiyotlarni boshqarish va kommunikatsiya")

    if pq is not None:
        if pq >= 75:
            strengths.append("Rejalashtirish va amaliy qarorlar")
        elif pq < 55:
            development.append("Rejalashtirish va vazifalarni ustuvorlashtirish")

    if not strengths:
        strengths.append("Profil hali yetarli ma'lumotga ega emas")

    if not development:
        development.append("Natijalarni muntazam qayta ko‘rib borish")

    return {
        "iq": iq,
        "eq": eq,
        "pq": pq,
        "unlocked": (
            iq is not None
            and eq is not None
            and pq is not None
        ),
        "strengths": strengths,
        "development_areas": development,
    }


def serialize_question_for_api(question):
    return {
        "id": question["id"],
        "weight": question.get("weight", 1),
        "matrix": question.get("matrix"),
        "options": question.get("options"),
    }


def serialize_db_row(row):
    if row is None:
        return None

    result = {}

    for key in row.keys():
        value = row[key]

        if isinstance(value, datetime):
            value = value.isoformat()

        elif isinstance(value, asyncpg.Record):
            value = dict(value)

        result[key] = value

    return result


async def create_test_session(
    user_id: int,
    test_type: str,
):
    test_type = test_type.upper()

    if test_type not in {"IQ", "EQ", "PQ"}:
        raise ValueError("Invalid test type")

    questions = make_test_payload(test_type)

    session_id = uuid4()

    expires_at = utcnow() + timedelta(hours=2)

    await db_execute("""
        UPDATE test_sessions
        SET status='expired'
        WHERE user_id=$1
          AND test_type=$2
          AND status IN ('created','active')
          AND expires_at < NOW()
    """, user_id, test_type)

    active = await db_fetchrow("""
        SELECT id
        FROM test_sessions
        WHERE user_id=$1
          AND test_type=$2
          AND status IN ('created','active')
          AND expires_at > NOW()
        ORDER BY started_at DESC
        LIMIT 1
    """, user_id, test_type)

    if active:
        return str(active["id"])

    await db_execute("""
        INSERT INTO test_sessions(
            id,
            user_id,
            test_type,
            status,
            questions,
            answers,
            current_index,
            started_at,
            expires_at
        )
        VALUES(
            $1,
            $2,
            $3,
            'active',
            $4::jsonb,
            '{}'::jsonb,
            0,
            NOW(),
            $5
        )
    """,
        session_id,
        user_id,
        test_type,
        json_dumps(questions),
        expires_at,
    )

    return str(session_id)


async def get_test_session(
    session_id,
    user_id: int,
):
    try:
        session_uuid = session_id if hasattr(session_id, "hex") else uuid4()
    except Exception:
        session_uuid = None

    try:
        if not hasattr(session_id, "hex"):
            from uuid import UUID
            session_uuid = UUID(str(session_id))
    except (ValueError, TypeError):
        return None

    return await db_fetchrow("""
        SELECT *
        FROM test_sessions
        WHERE id=$1
          AND user_id=$2
    """,
        session_uuid,
        user_id,
    )


async def save_session_answers(
    session_id,
    user_id: int,
    answers: dict,
    current_index: int | None = None,
):
    from uuid import UUID

    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, TypeError):
        return False

    session = await db_fetchrow("""
        SELECT id, status, expires_at
        FROM test_sessions
        WHERE id=$1
          AND user_id=$2
        FOR UPDATE
    """, session_uuid, user_id)

    if not session:
        return False

    if session["status"] in {"completed", "expired"}:
        return False

    if session["expires_at"] < utcnow():
        await db_execute("""
            UPDATE test_sessions
            SET status='expired'
            WHERE id=$1
        """, session_uuid)
        return False

    if current_index is None:
        await db_execute("""
            UPDATE test_sessions
            SET answers=$1::jsonb
            WHERE id=$2
        """,
            json_dumps(answers),
            session_uuid,
        )
    else:
        await db_execute("""
            UPDATE test_sessions
            SET
                answers=$1::jsonb,
                current_index=$2
            WHERE id=$3
        """,
            json_dumps(answers),
            current_index,
            session_uuid,
        )

    return True


async def complete_test_session(
    session_id,
    user_id: int,
    answers: dict,
):
    from uuid import UUID

    try:
        session_uuid = UUID(str(session_id))
    except (ValueError, TypeError):
        raise ValueError("Invalid session ID")

    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            session = await conn.fetchrow("""
                SELECT *
                FROM test_sessions
                WHERE id=$1
                  AND user_id=$2
                FOR UPDATE
            """,
                session_uuid,
                user_id,
            )

            if not session:
                raise ValueError("Session not found")

            if session["status"] == "completed":
                existing = await conn.fetchrow("""
                    SELECT *
                    FROM test_attempts
                    WHERE session_id=$1
                """,
                    session_uuid,
                )

                return {
                    "duplicate": True,
                    "attempt": serialize_db_row(existing),
                }

            if session["status"] == "expired":
                raise ValueError("Session expired")

            if session["expires_at"] < utcnow():
                await conn.execute("""
                    UPDATE test_sessions
                    SET status='expired'
                    WHERE id=$1
                """,
                    session_uuid,
                )
                raise ValueError("Session expired")

            test_type = session["test_type"]

            if test_type == "IQ":
                score, earned, max_score = calculate_iq(answers)
                level = iq_level(score)

            elif test_type == "EQ":
                score, earned, max_score = calculate_standard_score(
                    EQ_QUESTIONS,
                    answers,
                )
                level = (
                    "Yuqori"
                    if score >= 75
                    else "O‘rtacha"
                    if score >= 50
                    else "Rivojlantirish kerak"
                )

            elif test_type == "PQ":
                score, earned, max_score = calculate_standard_score(
                    PQ_QUESTIONS,
                    answers,
                )
                level = (
                    "Yuqori"
                    if score >= 75
                    else "O‘rtacha"
                    if score >= 50
                    else "Rivojlantirish kerak"
                )

            else:
                raise ValueError("Unknown test type")

            attempt_id = uuid4()
            result_id = uuid4()

            await conn.execute("""
                INSERT INTO test_attempts(
                    id,
                    user_id,
                    session_id,
                    test_type,
                    answers,
                    score,
                    max_score
                )
                VALUES(
                    $1,
                    $2,
                    $3,
                    $4,
                    $5::jsonb,
                    $6,
                    $7
                )
            """,
                attempt_id,
                user_id,
                session_uuid,
                test_type,
                json_dumps(answers),
                score,
                max_score,
            )

            details = {
                "earned": earned,
                "max_score": max_score,
                "answers_count": len(answers),
            }

            await conn.execute("""
                INSERT INTO results(
                    id,
                    attempt_id,
                    user_id,
                    test_type,
                    score,
                    level,
                    details
                )
                VALUES(
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7::jsonb
                )
            """,
                result_id,
                attempt_id,
                user_id,
                test_type,
                score,
                level,
                json_dumps(details),
            )

            await conn.execute("""
                UPDATE test_sessions
                SET
                    status='completed',
                    answers=$1::jsonb,
                    current_index=999,
                    completed_at=NOW()
                WHERE id=$2
            """,
                json_dumps(answers),
                session_uuid,
            )

            return {
                "duplicate": False,
                "attempt_id": str(attempt_id),
                "result_id": str(result_id),
                "test_type": test_type,
                "score": score,
                "max_score": max_score,
                "level": level,
                "details": details,
            }


async def get_latest_result(
    user_id: int,
    test_type: str,
):
    return await db_fetchrow("""
        SELECT
            r.*,
            a.answers,
            a.id AS attempt_id
        FROM results r
        JOIN test_attempts a
          ON a.id=r.attempt_id
        WHERE r.user_id=$1
          AND r.test_type=$2
        ORDER BY r.created_at DESC
        LIMIT 1
    """,
        user_id,
        test_type,
    )


async def get_result_for_user(
    user_id: int,
    attempt_id,
):
    from uuid import UUID

    try:
        attempt_uuid = UUID(str(attempt_id))
    except (ValueError, TypeError):
        return None

    return await db_fetchrow("""
        SELECT
            r.*,
            a.answers,
            a.max_score,
            a.id AS attempt_id
        FROM results r
        JOIN test_attempts a
          ON a.id=r.attempt_id
        WHERE r.user_id=$1
          AND a.id=$2
        LIMIT 1
    """,
        user_id,
        attempt_uuid,
    )


async def create_certificate(
    user_id: int,
    score: float,
    level: str,
    full_name: str,
):
    existing = await db_fetchrow("""
        SELECT *
        FROM certificates
        WHERE user_id=$1
          AND type='IQ'
        ORDER BY created_at DESC
        LIMIT 1
    """,
        user_id,
    )

    if existing and float(existing["score"]) == float(score):
        return existing

    certificate_id = (
        "IQ-"
        + secrets.token_hex(4).upper()
    )

    verification_code = (
        "IQ-"
        + "".join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(6)
        )
    )

    while await db_fetchval(
        "SELECT 1 FROM certificates WHERE verification_code=$1",
        verification_code,
    ):
        verification_code = (
            "IQ-"
            + "".join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(6)
            )
        )

    certificate_uuid = uuid4()

    await db_execute("""
        INSERT INTO certificates(
            id,
            user_id,
            certificate_id,
            verification_code,
            type,
            full_name,
            score,
            level
        )
        VALUES(
            $1,$2,$3,$4,'IQ',$5,$6,$7
        )
    """,
        certificate_uuid,
        user_id,
        certificate_id,
        verification_code,
        full_name,
        score,
        level,
    )

    return await db_fetchrow("""
        SELECT *
        FROM certificates
        WHERE id=$1
    """,
        certificate_uuid,
    )
    def find_font(size: int, bold: bool = False):
    candidates = []

    if bold:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ])
    else:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ])

    candidates.extend(
        glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    )

    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue

    return ImageFont.load_default()


def draw_centered_text(
    draw,
    text,
    font,
    center_x,
    y,
    fill,
):
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]

    draw.text(
        (center_x - width / 2, y),
        text,
        font=font,
        fill=fill,
    )


def generate_certificate_png(certificate):
    width, height = 1600, 1100

    image = Image.new(
        "RGB",
        (width, height),
        (10, 14, 26),
    )

    draw = ImageDraw.Draw(image)

    outer_gold = (220, 180, 70)
    inner_gold = (245, 210, 120)
    white = (245, 247, 255)
    muted = (180, 188, 210)
    violet = (167, 139, 250)

    draw.rounded_rectangle(
        (45, 45, width - 45, height - 45),
        radius=35,
        outline=outer_gold,
        width=8,
    )

    draw.rounded_rectangle(
        (70, 70, width - 70, height - 70),
        radius=28,
        outline=inner_gold,
        width=2,
    )

    center_x = width // 2

    title_font = find_font(70, bold=True)
    subtitle_font = find_font(36, bold=True)
    name_font = find_font(62, bold=True)
    score_font = find_font(100, bold=True)
    normal_font = find_font(30)
    small_font = find_font(24)

    draw_centered_text(
        draw,
        "SERTIFIKAT",
        title_font,
        center_x,
        145,
        inner_gold,
    )

    draw_centered_text(
        draw,
        "AQLLIY SALOHIYAT TO‘G‘RISIDA",
        subtitle_font,
        center_x,
        235,
        white,
    )

    seal_center = (center_x, 380)
    seal_radius = 72

    draw.ellipse(
        (
            seal_center[0] - seal_radius,
            seal_center[1] - seal_radius,
            seal_center[0] + seal_radius,
            seal_center[1] + seal_radius,
        ),
        outline=inner_gold,
        width=5,
    )

    draw.ellipse(
        (
            seal_center[0] - 55,
            seal_center[1] - 55,
            seal_center[0] + 55,
            seal_center[1] + 55,
        ),
        outline=violet,
        width=3,
    )

    draw_centered_text(
        draw,
        "IQ",
        find_font(44, bold=True),
        center_x,
        350,
        inner_gold,
    )

    draw_centered_text(
        draw,
        "Ushbu sertifikat",
        normal_font,
        center_x,
        485,
        muted,
    )

    full_name = str(certificate["full_name"]).strip()

    if len(full_name) > 42:
        name_font = find_font(48, bold=True)

    draw_centered_text(
        draw,
        full_name,
        name_font,
        center_x,
        530,
        white,
    )

    draw_centered_text(
        draw,
        "IQ test natijasini muvaffaqiyatli qayd etganini tasdiqlaydi.",
        normal_font,
        center_x,
        625,
        muted,
    )

    score = float(certificate["score"])

    if score.is_integer():
        score_text = str(int(score))
    else:
        score_text = f"{score:.1f}"

    draw_centered_text(
        draw,
        f"IQ {score_text}",
        score_font,
        center_x,
        685,
        inner_gold,
    )

    draw_centered_text(
        draw,
        str(certificate["level"] or ""),
        subtitle_font,
        center_x,
        805,
        violet,
    )

    created_at = certificate["created_at"]

    if isinstance(created_at, datetime):
        created_date = created_at.astimezone(
            timezone.utc
        ).strftime("%d.%m.%Y")
    else:
        created_date = str(created_at)[:10]

    verification = str(
        certificate["verification_code"]
    )

    draw.text(
        (115, 940),
        f"Verification: {verification}",
        font=small_font,
        fill=muted,
    )

    draw.text(
        (115, 985),
        f"Date: {created_date}",
        font=small_font,
        fill=muted,
    )

    brand = "IQ TEST BOT"

    bbox = draw.textbbox(
        (0, 0),
        brand,
        font=small_font,
    )

    draw.text(
        (
            width - 115 - (bbox[2] - bbox[0]),
            965,
        ),
        brand,
        font=small_font,
        fill=white,
    )

    output = io.BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output.getvalue()


async def get_or_create_iq_certificate(user_id: int):
    result = await get_latest_result(user_id, "IQ")

    if not result:
        return None

    user = await get_user(user_id)

    if not user:
        return None

    full_name = (
        user["full_name"]
        or " ".join(
            x for x in [
                user["first_name"],
                user["last_name"],
            ]
            if x
        )
        or "IQ TEST USER"
    )

    return await create_certificate(
        user_id=user_id,
        score=float(result["score"]),
        level=result["level"] or iq_level(float(result["score"])),
        full_name=full_name,
    )


async def notify_user(
    user_id: int,
    text: str,
    reply_markup=None,
):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not notify user %s: %s",
            user_id,
            exc,
        )
        return False


async def create_payment(
    user_id: int,
    product: str,
    amount: int,
):
    card = await db_fetchrow("""
        SELECT *
        FROM payment_cards
        WHERE active=TRUE
        ORDER BY created_at ASC
        LIMIT 1
    """)

    card_id = card["id"] if card else None

    payment_id = uuid4()

    await db_execute("""
        INSERT INTO payments(
            id,
            user_id,
            product,
            amount,
            status,
            card_id
        )
        VALUES(
            $1,$2,$3,$4,'pending',$5
        )
    """,
        payment_id,
        user_id,
        product,
        amount,
        card_id,
    )

    return await db_fetchrow("""
        SELECT *
        FROM payments
        WHERE id=$1
    """,
        payment_id,
    )


async def get_payment_for_user(
    user_id: int,
    payment_id,
):
    from uuid import UUID

    try:
        payment_uuid = UUID(str(payment_id))
    except (ValueError, TypeError):
        return None

    return await db_fetchrow("""
        SELECT
            p.*,
            c.card_number,
            c.holder AS card_holder,
            c.bank
        FROM payments p
        LEFT JOIN payment_cards c
            ON c.id=p.card_id
        WHERE p.id=$1
          AND p.user_id=$2
    """,
        payment_uuid,
        user_id,
    )


async def get_active_card():
    return await db_fetchrow("""
        SELECT *
        FROM payment_cards
        WHERE active=TRUE
        ORDER BY created_at ASC
        LIMIT 1
    """)


async def approve_payment(
    payment_id,
    admin_id: int,
):
    from uuid import UUID

    try:
        payment_uuid = UUID(str(payment_id))
    except (ValueError, TypeError):
        return None

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            payment = await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE id=$1
                FOR UPDATE
            """,
                payment_uuid,
            )

            if not payment:
                return None

            if payment["status"] == "approved":
                return payment

            await conn.execute("""
                UPDATE payments
                SET
                    status='approved',
                    admin_id=$1,
                    updated_at=NOW()
                WHERE id=$2
            """,
                admin_id,
                payment_uuid,
            )

            updated = await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE id=$1
            """,
                payment_uuid,
            )

    return updated


async def reject_payment(
    payment_id,
    admin_id: int,
    note: str = "",
):
    from uuid import UUID

    try:
        payment_uuid = UUID(str(payment_id))
    except (ValueError, TypeError):
        return None

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            payment = await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE id=$1
                FOR UPDATE
            """,
                payment_uuid,
            )

            if not payment:
                return None

            await conn.execute("""
                UPDATE payments
                SET
                    status='rejected',
                    admin_id=$1,
                    admin_note=$2,
                    updated_at=NOW()
                WHERE id=$3
            """,
                admin_id,
                clean_text(note, 500),
                payment_uuid,
            )

            return await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE id=$1
            """,
                payment_uuid,
            )


async def payment_has_approved_product(
    user_id: int,
    product: str,
):
    row = await db_fetchrow("""
        SELECT id
        FROM payments
        WHERE user_id=$1
          AND product=$2
          AND status='approved'
        ORDER BY updated_at DESC
        LIMIT 1
    """,
        user_id,
        product,
    )

    return bool(row)


async def get_user_payments(user_id: int):
    return await db_fetch("""
        SELECT
            p.*,
            c.card_number,
            c.holder AS card_holder,
            c.bank
        FROM payments p
        LEFT JOIN payment_cards c
            ON c.id=p.card_id
        WHERE p.user_id=$1
        ORDER BY p.created_at DESC
    """,
        user_id,
    )


async def create_battle(
    user_id: int,
):
    price = await get_int_setting(
        "battle_price",
        7500,
    )

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            code = await unique_battle_code(conn)

            question_ids = [
                q["id"]
                for q in IQ_QUESTIONS
            ]

            battle_id = uuid4()

            await conn.execute("""
                INSERT INTO battles(
                    id,
                    code,
                    status,
                    created_by,
                    price,
                    question_ids
                )
                VALUES(
                    $1,$2,'waiting',$3,$4,$5::jsonb
                )
            """,
                battle_id,
                code,
                user_id,
                price,
                json_dumps(question_ids),
            )

            player_id = uuid4()

            await conn.execute("""
                INSERT INTO battle_players(
                    id,
                    battle_id,
                    user_id,
                    payment_status
                )
                VALUES(
                    $1,$2,$3,'pending'
                )
            """,
                player_id,
                battle_id,
                user_id,
            )

    return await db_fetchrow("""
        SELECT *
        FROM battles
        WHERE id=$1
    """,
        battle_id,
    )


async def get_battle(
    battle_id,
):
    from uuid import UUID

    try:
        battle_uuid = UUID(str(battle_id))
    except (ValueError, TypeError):
        return None

    return await db_fetchrow("""
        SELECT *
        FROM battles
        WHERE id=$1
    """,
        battle_uuid,
    )


async def get_battle_by_code(
    code: str,
):
    return await db_fetchrow("""
        SELECT *
        FROM battles
        WHERE code=$1
    """,
        clean_text(code, 4).upper(),
    )


async def get_battle_player(
    battle_id,
    user_id: int,
):
    from uuid import UUID

    try:
        battle_uuid = UUID(str(battle_id))
    except (ValueError, TypeError):
        return None

    return await db_fetchrow("""
        SELECT *
        FROM battle_players
        WHERE battle_id=$1
          AND user_id=$2
    """,
        battle_uuid,
        user_id,
    )


async def join_battle(
    user_id: int,
    code: str,
):
    from uuid import UUID

    code = clean_text(code, 4).upper()

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            battle = await conn.fetchrow("""
                SELECT *
                FROM battles
                WHERE code=$1
                FOR UPDATE
            """,
                code,
            )

            if not battle:
                raise ValueError("Battle not found")

            if battle["created_by"] == user_id:
                raise ValueError("You cannot join your own battle")

            if battle["status"] != "waiting":
                raise ValueError("Battle is not available")

            existing = await conn.fetchrow("""
                SELECT *
                FROM battle_players
                WHERE battle_id=$1
                  AND user_id=$2
            """,
                battle["id"],
                user_id,
            )

            if existing:
                return battle

            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM battle_players
                WHERE battle_id=$1
            """,
                battle["id"],
            )

            if count >= 2:
                raise ValueError("Battle is full")

            await conn.execute("""
                INSERT INTO battle_players(
                    id,
                    battle_id,
                    user_id,
                    payment_status
                )
                VALUES(
                    $1,$2,$3,'pending'
                )
            """,
                uuid4(),
                battle["id"],
                user_id,
            )

            await conn.execute("""
                UPDATE battles
                SET status='ready'
                WHERE id=$1
                  AND status='waiting'
            """,
                battle["id"],
            )

            return await conn.fetchrow("""
                SELECT *
                FROM battles
                WHERE id=$1
            """,
                battle["id"],
            )
            async def start_battle_if_ready(
    battle_id,
    admin_id: int,
):
    from uuid import UUID

    if not await is_admin(admin_id):
        raise PermissionError("Admin access required")

    try:
        battle_uuid = UUID(str(battle_id))
    except (ValueError, TypeError):
        raise ValueError("Invalid battle ID")

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            battle = await conn.fetchrow("""
                SELECT *
                FROM battles
                WHERE id=$1
                FOR UPDATE
            """,
                battle_uuid,
            )

            if not battle:
                raise ValueError("Battle not found")

            if battle["status"] not in {"ready", "waiting"}:
                return battle

            players = await conn.fetch("""
                SELECT *
                FROM battle_players
                WHERE battle_id=$1
                ORDER BY joined_at ASC
            """,
                battle_uuid,
            )

            if len(players) != 2:
                raise ValueError("Battle needs two players")

            if any(
                player["payment_status"] != "approved"
                for player in players
            ):
                raise ValueError("Both players must be approved")

            await conn.execute("""
                UPDATE battles
                SET
                    status='active',
                    started_at=NOW()
                WHERE id=$1
            """,
                battle_uuid,
            )

            return await conn.fetchrow("""
                SELECT *
                FROM battles
                WHERE id=$1
            """,
                battle_uuid,
            )


async def approve_battle_payment(
    battle_id,
    user_id: int,
    payment_id,
    admin_id: int,
):
    if not await is_admin(admin_id):
        raise PermissionError("Admin access required")

    from uuid import UUID

    try:
        battle_uuid = UUID(str(battle_id))
        payment_uuid = UUID(str(payment_id))
    except (ValueError, TypeError):
        raise ValueError("Invalid ID")

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            payment = await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE id=$1
                  AND user_id=$2
                FOR UPDATE
            """,
                payment_uuid,
                user_id,
            )

            if not payment:
                raise ValueError("Payment not found")

            await conn.execute("""
                UPDATE payments
                SET
                    status='approved',
                    admin_id=$1,
                    updated_at=NOW()
                WHERE id=$2
            """,
                admin_id,
                payment_uuid,
            )

            player = await conn.fetchrow("""
                SELECT *
                FROM battle_players
                WHERE battle_id=$1
                  AND user_id=$2
                FOR UPDATE
            """,
                battle_uuid,
                user_id,
            )

            if not player:
                raise ValueError("Battle player not found")

            await conn.execute("""
                UPDATE battle_players
                SET
                    payment_status='approved',
                    payment_id=$1
                WHERE battle_id=$2
                  AND user_id=$3
            """,
                payment_uuid,
                battle_uuid,
                user_id,
            )

            return await conn.fetchrow("""
                SELECT *
                FROM battle_players
                WHERE battle_id=$1
                  AND user_id=$2
            """,
                battle_uuid,
                user_id,
            )


async def submit_battle(
    battle_id,
    user_id: int,
    answers: dict,
):
    from uuid import UUID

    try:
        battle_uuid = UUID(str(battle_id))
    except (ValueError, TypeError):
        raise ValueError("Invalid battle ID")

    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            battle = await conn.fetchrow("""
                SELECT *
                FROM battles
                WHERE id=$1
                FOR UPDATE
            """,
                battle_uuid,
            )

            if not battle:
                raise ValueError("Battle not found")

            if battle["status"] not in {"active", "ready"}:
                if battle["status"] == "completed":
                    existing = await conn.fetchrow("""
                        SELECT *
                        FROM battle_players
                        WHERE battle_id=$1
                          AND user_id=$2
                    """,
                        battle_uuid,
                        user_id,
                    )

                    return {
                        "duplicate": True,
                        "score": (
                            float(existing["score"])
                            if existing and existing["score"] is not None
                            else None
                        ),
                    }

                raise ValueError("Battle is not active")

            player = await conn.fetchrow("""
                SELECT *
                FROM battle_players
                WHERE battle_id=$1
                  AND user_id=$2
                FOR UPDATE
            """,
                battle_uuid,
                user_id,
            )

            if not player:
                raise ValueError("You are not in this battle")

            if player["payment_status"] != "approved":
                raise ValueError("Payment is not approved")

            if player["score"] is not None:
                return {
                    "duplicate": True,
                    "score": float(player["score"]),
                }

            score, earned, max_score = calculate_iq(
                answers
            )

            await conn.execute("""
                UPDATE battle_players
                SET
                    answers=$1::jsonb,
                    score=$2,
                    completed_at=NOW()
                WHERE battle_id=$3
                  AND user_id=$4
            """,
                json_dumps(answers),
                score,
                battle_uuid,
                user_id,
            )

            completed_count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM battle_players
                WHERE battle_id=$1
                  AND score IS NOT NULL
            """,
                battle_uuid,
            )

            total_players = await conn.fetchval("""
                SELECT COUNT(*)
                FROM battle_players
                WHERE battle_id=$1
            """,
                battle_uuid,
            )

            if completed_count == 2 and total_players == 2:
                await conn.execute("""
                    UPDATE battles
                    SET
                        status='completed',
                        completed_at=NOW()
                    WHERE id=$1
                """,
                    battle_uuid,
                )

            return {
                "duplicate": False,
                "score": score,
                "earned": earned,
                "max_score": max_score,
                "completed": (
                    completed_count == 2
                    and total_players == 2
                ),
            }


async def get_battle_result(
    battle_id,
    user_id: int,
):
    from uuid import UUID

    try:
        battle_uuid = UUID(str(battle_id))
    except (ValueError, TypeError):
        return None

    battle = await db_fetchrow("""
        SELECT *
        FROM battles
        WHERE id=$1
    """,
        battle_uuid,
    )

    if not battle:
        return None

    me = await db_fetchrow("""
        SELECT *
        FROM battle_players
        WHERE battle_id=$1
          AND user_id=$2
    """,
        battle_uuid,
        user_id,
    )

    if not me:
        return None

    players = await db_fetch("""
        SELECT
            user_id,
            score,
            completed_at
        FROM battle_players
        WHERE battle_id=$1
        ORDER BY joined_at ASC
    """,
        battle_uuid,
    )

    if len(players) != 2:
        return {
            "status": battle["status"],
            "completed": False,
            "score": (
                float(me["score"])
                if me["score"] is not None
                else None
            ),
            "opponent_score": None,
            "result": None,
        }

    opponent = next(
        (
            p for p in players
            if p["user_id"] != user_id
        ),
        None,
    )

    my_score = (
        float(me["score"])
        if me["score"] is not None
        else None
    )

    opponent_score = (
        float(opponent["score"])
        if opponent and opponent["score"] is not None
        else None
    )

    if my_score is None or opponent_score is None:
        return {
            "status": battle["status"],
            "completed": False,
            "score": my_score,
            "opponent_score": None,
            "result": None,
        }

    if my_score > opponent_score:
        result = "win"
    elif my_score < opponent_score:
        result = "loss"
    else:
        result = "draw"

    return {
        "status": battle["status"],
        "completed": True,
        "score": my_score,
        "opponent_score": opponent_score,
        "result": result,
    }


async def create_referral(
    referrer_id: int,
    referred_id: int,
):
    if referrer_id == referred_id:
        return False

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval("""
                SELECT 1
                FROM referrals
                WHERE referred_id=$1
            """,
                referred_id,
            )

            if exists:
                return False

            reward = 0

            await conn.execute("""
                INSERT INTO referrals(
                    id,
                    referrer_id,
                    referred_id,
                    reward,
                    rewarded
                )
                VALUES(
                    $1,$2,$3,$4,FALSE
                )
                ON CONFLICT(referred_id)
                DO NOTHING
            """,
                uuid4(),
                referrer_id,
                referred_id,
                reward,
            )

    return True


async def get_referral_stats(user_id: int):
    count = await db_fetchval("""
        SELECT COUNT(*)
        FROM referrals
        WHERE referrer_id=$1
    """,
        user_id,
    )

    rewarded = await db_fetchval("""
        SELECT COALESCE(SUM(reward),0)
        FROM referrals
        WHERE referrer_id=$1
          AND rewarded=TRUE
    """,
        user_id,
    )

    return {
        "count": int(count or 0),
        "rewarded": int(rewarded or 0),
    }


async def build_bootstrap(user_id: int):
    user = await get_user(user_id)

    if not user:
        raise ValueError("User not found")

    profile = await calculate_personal_profile(
        user_id
    )

    latest_iq = await get_latest_result(
        user_id,
        "IQ",
    )

    latest_eq = await get_latest_result(
        user_id,
        "EQ",
    )

    latest_pq = await get_latest_result(
        user_id,
        "PQ",
    )

    iq_price = await get_int_setting(
        "iq_price",
        0,
    )

    eq_price = await get_int_setting(
        "eq_price",
        0,
    )

    pq_price = await get_int_setting(
        "pq_price",
        0,
    )

    battle_price = await get_int_setting(
        "battle_price",
        7500,
    )

    referral = await get_referral_stats(
        user_id
    )

    return {
        "brand": "IQ TEST BOT",

        "user": {
            "id": user_id,
            "username": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "language": user["language"],
            "full_name": user["full_name"],
            "country": user["country"],
            "gender": user["gender"],
            "age": user["age"],

            "hasIQ": latest_iq is not None,
            "hasEQ": latest_eq is not None,
            "hasPQ": latest_pq is not None,

            "iq": (
                float(latest_iq["score"])
                if latest_iq
                else None
            ),
            "eq": (
                float(latest_eq["score"])
                if latest_eq
                else None
            ),
            "pq": (
                float(latest_pq["score"])
                if latest_pq
                else None
            ),
        },

        "profile": profile,

        "questions": {
            "IQ": make_test_payload("IQ"),
            "EQ": make_test_payload("EQ"),
            "PQ": make_test_payload("PQ"),
        },

        "prices": {
            "iq": iq_price,
            "eq": eq_price,
            "pq": pq_price,
            "battle": battle_price,
        },

        "referral": referral,

        "battle": {
            "price": battle_price,
        },
    }


def safe_json_loads(value, default):
    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


async def get_live_stats():
    mode = await get_setting(
        "live_mode",
        "fake",
    )

    if mode == "real":
        online = await db_fetchval("""
            SELECT COUNT(*)
            FROM users
            WHERE updated_at > NOW() - INTERVAL '10 minutes'
        """)

        return {
            "mode": "real",
            "base": int(online or 0),
            "online": int(online or 0),
            "delta": 0,
        }

    base = await get_int_setting(
        "live_fake_base",
        95114,
    )

    online = await get_int_setting(
        "live_fake_online",
        342,
    )

    delta = await get_int_setting(
        "live_fake_delta",
        8,
    )

    return {
        "mode": "fake",
        "base": base,
        "online": online,
        "delta": delta,
    }


async def ranking_rows(limit=50):
    limit = max(1, min(int(limit), 100))

    return await db_fetch("""
        SELECT
            u.user_id,
            COALESCE(
                NULLIF(u.full_name, ''),
                NULLIF(
                    TRIM(
                        CONCAT_WS(
                            ' ',
                            u.first_name,
                            u.last_name
                        )
                    ),
                    ''
                ),
                COALESCE(u.username, 'User')
            ) AS display_name,
            MAX(r.score) FILTER (
                WHERE r.test_type='IQ'
            ) AS iq_score,
            MAX(r.created_at) AS latest_activity
        FROM users u
        JOIN results r
          ON r.user_id=u.user_id
        GROUP BY
            u.user_id,
            u.full_name,
            u.first_name,
            u.last_name,
            u.username
        HAVING MAX(r.score) FILTER (
            WHERE r.test_type='IQ'
        ) IS NOT NULL
        ORDER BY
            iq_score DESC,
            latest_activity ASC
        LIMIT $1
    """,
        limit,
    )
    @dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user

    if not user:
        return

    language = "uz"

    existing = await get_user(user.id)

    if existing and existing["language"] in TRANSLATIONS:
        language = existing["language"]

    await upsert_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        language,
    )

    command = message.text or ""

    if command.startswith("/start "):
        payload = command.split(" ", 1)[1].strip()

        if payload.startswith("ref_"):
            try:
                referrer_id = int(
                    payload.replace("ref_", "", 1)
                )

                if referrer_id != user.id:
                    await create_referral(
                        referrer_id,
                        user.id,
                    )
            except (ValueError, TypeError):
                pass

    display_name = (
        user.first_name
        or user.username
        or "User"
    )

    await message.answer(
        t(
            language,
            "welcome",
            name=display_name,
        ),
        reply_markup=app_inline_keyboard(language),
    )

    await message.answer(
        "⬇️ Quyidagi tugma orqali Mini App'ni oching.",
        reply_markup=main_keyboard(language),
    )


@dp.message(
    F.text.in_({
        "🧠 IQ · EQ · PQ testini ishlash",
        "🧠 Пройти IQ · EQ · PQ",
        "🧠 Take IQ · EQ · PQ",
    })
)
async def open_app_from_old_keyboard(
    message: types.Message,
):
    row = await db_fetchrow(
        "SELECT language FROM users WHERE user_id=$1",
        message.from_user.id,
    )

    lang = (
        row["language"]
        if row and row["language"] in TRANSLATIONS
        else "uz"
    )

    await message.answer(
        "🧠 Mini App'ni ochish uchun quyidagi tugmani bosing:",
        reply_markup=app_inline_keyboard(lang),
    )


@dp.message(F.text.in_({
    "🌐 Til",
    "🌐 Язык",
    "🌐 Language",
}))
async def language_handler(message: types.Message):
    await message.answer(
        "Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=language_keyboard(),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(
    callback: CallbackQuery,
):
    if not callback.from_user:
        await callback.answer()
        return

    lang = callback.data.split(":", 1)[1]

    if lang not in TRANSLATIONS:
        await callback.answer()
        return

    await db_execute("""
        UPDATE users
        SET
            language=$1,
            updated_at=NOW()
        WHERE user_id=$2
    """,
        lang,
        callback.from_user.id,
    )

    await callback.answer(
        t(lang, "lang_changed")
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.message.answer(
        t(
            lang,
            "welcome",
            name=(
                callback.from_user.first_name
                or callback.from_user.username
                or "User"
            ),
        ),
        reply_markup=app_inline_keyboard(lang),
    )

    await callback.message.answer(
        "⬇️ Mini App:",
        reply_markup=main_keyboard(lang),
    )


@dp.message(F.text.in_({
    "📜 Sertifikatim",
    "📜 Мой сертификат",
    "📜 My certificate",
}))
async def certificate_handler(
    message: types.Message,
):
    certificate = await get_or_create_iq_certificate(
        message.from_user.id
    )

    if not certificate:
        await message.answer(
            "Hali IQ testi natijasi asosida sertifikat mavjud emas."
        )
        return

    png = generate_certificate_png(
        certificate
    )

    await message.answer_document(
        BufferedInputFile(
            png,
            filename=(
                f"{certificate['verification_code']}.png"
            ),
        ),
        caption=(
            "📜 <b>IQ TEST BOT</b>\n\n"
            f"IQ: <b>{float(certificate['score']):g}</b>\n"
            f"Daraja: <b>{certificate['level']}</b>\n"
            f"Verification: <code>"
            f"{certificate['verification_code']}"
            f"</code>"
        ),
    )


@dp.message(F.text.in_({
    "🏆 Reyting",
    "🏆 Рейтинг",
    "🏆 Ranking",
}))
async def ranking_handler(
    message: types.Message,
):
    rows = await ranking_rows(20)

    if not rows:
        await message.answer(
            "🏆 Hozircha reyting uchun natijalar mavjud emas."
        )
        return

    lines = [
        "🏆 <b>IQ TEST BOT — REYTING</b>",
        "",
    ]

    for index, row in enumerate(rows, 1):
        name = str(
            row["display_name"]
            or "User"
        )

        score = row["iq_score"]

        if score is None:
            continue

        score_value = float(score)

        if score_value.is_integer():
            score_text = str(int(score_value))
        else:
            score_text = f"{score_value:.1f}"

        lines.append(
            f"<b>{index}.</b> "
            f"{name[:32]} — "
            f"<b>IQ {score_text}</b>"
        )

    await message.answer(
        "\n".join(lines)
    )


@dp.message(F.text.in_({
    "💰 Pul ishlash",
    "💰 Заработать",
    "💰 Earn",
}))
async def earn_handler(
    message: types.Message,
):
    bot_username = BOT_USERNAME

    referral_link = (
        f"https://t.me/{bot_username}"
        f"?start=ref_{message.from_user.id}"
    )

    stats = await get_referral_stats(
        message.from_user.id
    )

    await message.answer(
        "💰 <b>Do‘stlaringizni taklif qiling</b>\n\n"
        "Sizning referral havolangiz:\n"
        f"<code>{referral_link}</code>\n\n"
        f"👥 Taklif qilinganlar: <b>{stats['count']}</b>\n"
        f"🎁 Mukofot: <b>{stats['rewarded']}</b>"
    )


@dp.message(F.text.in_({
    "ℹ️ Narx va yordam",
    "ℹ️ Цена и помощь",
    "ℹ️ Prices & help",
}))
async def help_handler(
    message: types.Message,
):
    iq_price = await get_int_setting(
        "iq_price",
        0,
    )

    iq_retry = await get_int_setting(
        "iq_retry_price",
        5000,
    )

    eq_price = await get_int_setting(
        "eq_price",
        0,
    )

    eq_retry = await get_int_setting(
        "eq_retry_price",
        5000,
    )

    pq_price = await get_int_setting(
        "pq_price",
        0,
    )

    pq_retry = await get_int_setting(
        "pq_retry_price",
        5000,
    )

    battle_price = await get_int_setting(
        "battle_price",
        7500,
    )

    await message.answer(
        "ℹ️ <b>IQ TEST BOT</b>\n\n"
        f"🧠 IQ: <b>{iq_price:,} so‘m</b>\n"
        f"🔄 IQ qayta: <b>{iq_retry:,} so‘m</b>\n\n"
        f"❤️ EQ: <b>{eq_price:,} so‘m</b>\n"
        f"🔄 EQ qayta: <b>{eq_retry:,} so‘m</b>\n\n"
        f"🎯 PQ: <b>{pq_price:,} so‘m</b>\n"
        f"🔄 PQ qayta: <b>{pq_retry:,} so‘m</b>\n\n"
        f"⚔️ Battle: <b>{battle_price:,} so‘m / ishtirokchi</b>\n\n"
        "Savol yoki muammo bo‘lsa, administrator bilan bog‘laning."
    )


@dp.message(Command("admin"))
async def admin_command(
    message: types.Message,
):
    if not await is_admin(message.from_user.id):
        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Users",
                    callback_data="admin:users",
                ),
                InlineKeyboardButton(
                    text="📊 Statistics",
                    callback_data="admin:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💳 Payments",
                    callback_data="admin:payments",
                ),
                InlineKeyboardButton(
                    text="💳 Cards",
                    callback_data="admin:cards",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Certificates",
                    callback_data="admin:certificates",
                ),
                InlineKeyboardButton(
                    text="⚔️ Battles",
                    callback_data="admin:battles",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📡 Live Counter",
                    callback_data="admin:live",
                ),
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="admin:settings",
                ),
            ],
        ]
    )

    await message.answer(
        "🛠 <b>ADMIN PANEL</b>",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.startswith("admin:"))
async def admin_callback(
    callback: CallbackQuery,
):
    if not await is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Access denied",
            show_alert=True,
        )
        return

    action = callback.data.split(":", 1)[1]

    if action == "users":
        count = await db_fetchval(
            "SELECT COUNT(*) FROM users"
        )

        await callback.message.answer(
            f"👥 Users: <b>{int(count or 0)}</b>"
        )

    elif action == "stats":
        users = await db_fetchval(
            "SELECT COUNT(*) FROM users"
        )

        attempts = await db_fetchval(
            "SELECT COUNT(*) FROM test_attempts"
        )

        payments = await db_fetchval(
            "SELECT COUNT(*) FROM payments"
        )

        await callback.message.answer(
            "📊 <b>Statistics</b>\n\n"
            f"Users: <b>{int(users or 0)}</b>\n"
            f"Attempts: <b>{int(attempts or 0)}</b>\n"
            f"Payments: <b>{int(payments or 0)}</b>"
        )

    elif action == "payments":
        rows = await db_fetch("""
            SELECT
                p.id,
                p.user_id,
                p.product,
                p.amount,
                p.status,
                p.created_at
            FROM payments p
            ORDER BY p.created_at DESC
            LIMIT 20
        """)

        if not rows:
            await callback.message.answer(
                "💳 Paymentlar yo‘q."
            )
        else:
            lines = [
                "💳 <b>Oxirgi paymentlar</b>",
                "",
            ]

            for row in rows:
                lines.append(
                    f"<code>{str(row['id'])[:8]}</code> | "
                    f"{row['user_id']} | "
                    f"{row['product']} | "
                    f"{row['amount']:,} | "
                    f"{row['status']}"
                )

            await callback.message.answer(
                "\n".join(lines)
            )

    elif action == "cards":
        cards = await db_fetch("""
            SELECT *
            FROM payment_cards
            ORDER BY created_at ASC
        """)

        if not cards:
            await callback.message.answer(
                "💳 Payment kartalari mavjud emas."
            )
        else:
            lines = [
                "💳 <b>Payment cards</b>",
                "",
            ]

            for card in cards:
                lines.append(
                    f"• {card['card_number']} | "
                    f"{card['holder'] or '-'} | "
                    f"{card['bank'] or '-'} | "
                    f"{'ACTIVE' if card['active'] else 'OFF'}"
                )

            await callback.message.answer(
                "\n".join(lines)
            )

    elif action == "certificates":
        count = await db_fetchval(
            "SELECT COUNT(*) FROM certificates"
        )

        await callback.message.answer(
            f"📜 Certificates: <b>{int(count or 0)}</b>"
        )

    elif action == "battles":
        rows = await db_fetch("""
            SELECT
                status,
                COUNT(*) AS count
            FROM battles
            GROUP BY status
            ORDER BY status
        """)

        lines = ["⚔️ <b>Battles</b>", ""]

        if rows:
            for row in rows:
                lines.append(
                    f"{row['status']}: "
                    f"<b>{int(row['count'])}</b>"
                )
        else:
            lines.append("Battle mavjud emas.")

        await callback.message.answer(
            "\n".join(lines)
        )

    elif action == "live":
        stats = await get_live_stats()

        await callback.message.answer(
            "📡 <b>Live Counter</b>\n\n"
            f"Mode: <b>{stats['mode']}</b>\n"
            f"Base: <b>{stats['base']}</b>\n"
            f"Online: <b>{stats['online']}</b>\n"
            f"Delta: <b>{stats['delta']}</b>"
        )

    elif action == "settings":
        keys = [
            "iq_price",
            "iq_retry_price",
            "eq_price",
            "eq_retry_price",
            "pq_price",
            "pq_retry_price",
            "battle_price",
            "live_mode",
            "live_fake_base",
            "live_fake_online",
            "live_fake_delta",
        ]

        lines = ["⚙️ <b>Settings</b>", ""]

        for key in keys:
            value = await get_setting(key, "-")
            lines.append(
                f"<code>{key}</code> = <b>{value}</b>"
            )

        await callback.message.answer(
            "\n".join(lines)
        )

    await callback.answer()


@dp.message()
async def fallback_message(
    message: types.Message,
):
    if not message.from_user:
        return

    row = await db_fetchrow(
        "SELECT language FROM users WHERE user_id=$1",
        message.from_user.id,
    )

    lang = (
        row["language"]
        if row and row["language"] in TRANSLATIONS
        else "uz"
    )

    await message.answer(
        "🧠 IQ TEST BOT\n\n"
        "Mini App'ni ochish uchun quyidagi tugmani bosing:",
        reply_markup=app_inline_keyboard(lang),
    )
    async def webhook_startup():
    webhook_url = (
        PUBLIC_BASE_URL.rstrip("/")
        + "/telegram/webhook"
    )

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )

    info = await bot.get_webhook_info()

    logger.info(
        "Telegram webhook configured: %s pending=%s",
        info.url,
        info.pending_update_count,
    )


async def webhook_shutdown():
    try:
        await bot.delete_webhook(
            drop_pending_updates=False
        )
    except Exception as exc:
        logger.warning(
            "Webhook cleanup failed: %s",
            exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool

    background_tasks = []

    try:
        await init_db()

        await webhook_startup()

        logger.info(
            "IQ TEST BOT is ready on port %s",
            PORT,
        )

        yield

    finally:
        for task in background_tasks:
            if not task.done():
                task.cancel()

        if background_tasks:
            await asyncio.gather(
                *background_tasks,
                return_exceptions=True,
            )

        await webhook_shutdown()

        try:
            await bot.session.close()
        except Exception as exc:
            logger.warning(
                "Bot session cleanup failed: %s",
                exc,
            )

        if db_pool is not None:
            await db_pool.close()
            db_pool = None

        logger.info("Shutdown complete")



app = FastAPI(
    title="IQ TEST BOT",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    database_ok = False

    if db_pool is not None:
        try:
            await db_fetchval("SELECT 1")
            database_ok = True
        except Exception:
            database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "bot": True,
    }


@app.get("/app", response_class=HTMLResponse)
async def mini_app():
    index_path = os.path.join(
        os.path.dirname(__file__),
        "webapp",
        "index.html",
    )

    if not os.path.isfile(index_path):
        raise HTTPException(
            status_code=404,
            detail="Mini App not found",
        )

    with open(
        index_path,
        "r",
        encoding="utf-8",
    ) as file:
        return HTMLResponse(
            content=file.read()
        )


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        "",
    )

    if not WEBHOOK_SECRET or not hmac.compare_digest(
        received_secret,
        WEBHOOK_SECRET,
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook secret",
        )

    body = await request.body()

    if not body:
        return {"ok": True}

    try:
        data = json.loads(
            body.decode("utf-8")
        )

        update = Update.model_validate(
            data
        )

        await dp.feed_update(
            bot,
            update,
        )

        return {"ok": True}

    except Exception as exc:
        logger.exception(
            "Webhook update failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Webhook processing failed",
        )


@app.get("/api/bootstrap")
async def api_bootstrap(
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        data = await build_bootstrap(
            auth["user_id"]
        )

        return JSONResponse(data)

    except Exception as exc:
        logger.exception(
            "Bootstrap failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Bootstrap failed",
        )


@app.post("/api/profile/save")
async def api_profile_save(
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON",
        )

    full_name = clean_text(
        body.get("full_name"),
        150,
    )

    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Full name is required",
        )

    age = normalize_age(
        body.get("age")
    )

    if age is None:
        raise HTTPException(
            status_code=400,
            detail="Valid age is required",
        )

    gender = normalize_gender(
        body.get("gender")
    )

    if not gender:
        raise HTTPException(
            status_code=400,
            detail="Valid gender is required",
        )

    country = normalize_country(
        body.get("country")
    )

    if not country:
        raise HTTPException(
            status_code=400,
            detail="Country is required",
        )

    await db_execute("""
        UPDATE users
        SET
            full_name=$1,
            age=$2,
            gender=$3,
            country=$4,
            updated_at=NOW()
        WHERE user_id=$5
    """,
        full_name,
        age,
        gender,
        country,
        auth["user_id"],
    )

    return {
        "ok": True,
        "profile": {
            "full_name": full_name,
            "age": age,
            "gender": gender,
            "country": country,
        },
    }


@app.post("/api/test/start")
async def api_test_start(
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

    test_type = str(
        body.get("test_type")
        or body.get("type")
        or "IQ"
    ).upper()

    if test_type not in {
        "IQ",
        "EQ",
        "PQ",
    }:
        raise HTTPException(
            status_code=400,
            detail="Invalid test type",
        )

    user = await get_user(
        auth["user_id"]
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if not user["full_name"] or not user["age"] or not user["country"]:
        raise HTTPException(
            status_code=400,
            detail="Profile must be completed first",
        )

    price = await get_int_setting(
        f"{test_type.lower()}_price",
        0,
    )

    if price > 0:
        approved = await payment_has_approved_product(
            auth["user_id"],
            test_type,
        )

        if not approved:
            return JSONResponse({
                "ok": False,
                "payment_required": True,
                "price": price,
                "test_type": test_type,
            })

    session_id = await create_test_session(
        auth["user_id"],
        test_type,
    )

    session = await get_test_session(
        session_id,
        auth["user_id"],
    )

    if not session:
        raise HTTPException(
            status_code=500,
            detail="Session creation failed",
        )

    questions = safe_json_loads(
        session["questions"],
        [],
    )

    answers = safe_json_loads(
        session["answers"],
        {},
    )

    return {
        "ok": True,
        "session_id": str(session["id"]),
        "test_type": session["test_type"],
        "status": session["status"],
        "questions": questions,
        "answers": answers,
        "current_index": session["current_index"],
        "expires_at": session["expires_at"].isoformat(),
    }


@app.get("/api/test/{session_id}/resume")
async def api_test_resume(
    session_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    session = await get_test_session(
        session_id,
        auth["user_id"],
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    if (
        session["status"] != "completed"
        and session["expires_at"] < utcnow()
    ):
        await db_execute("""
            UPDATE test_sessions
            SET status='expired'
            WHERE id=$1
        """,
            session["id"],
        )

        raise HTTPException(
            status_code=410,
            detail="Session expired",
        )

    return {
        "ok": True,
        "session_id": str(session["id"]),
        "test_type": session["test_type"],
        "status": session["status"],
        "questions": safe_json_loads(
            session["questions"],
            [],
        ),
        "answers": safe_json_loads(
            session["answers"],
            {},
        ),
        "current_index": session["current_index"],
        "expires_at": session["expires_at"].isoformat(),
    }


@app.post("/api/test/{session_id}/submit")
async def api_test_submit(
    session_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON",
        )

    answers = body.get("answers")

    if not isinstance(answers, dict):
        raise HTTPException(
            status_code=400,
            detail="answers must be an object",
        )

    session = await get_test_session(
        session_id,
        auth["user_id"],
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        result = await complete_test_session(
            session_id,
            auth["user_id"],
            answers,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if result.get("duplicate"):
        attempt_id = result.get("attempt", {}).get("id")

        if attempt_id:
            existing = await get_result_for_user(
                auth["user_id"],
                attempt_id,
            )

            if existing:
                return {
                    "ok": True,
                    "duplicate": True,
                    "attempt_id": str(
                        existing["attempt_id"]
                    ),
                    "result_id": str(
                        existing["id"]
                    ),
                    "test_type": existing["test_type"],
                    "score": float(existing["score"]),
                    "level": existing["level"],
                }

        return {
            "ok": True,
            "duplicate": True,
        }

    if result["test_type"] == "IQ":
        certificate = await get_or_create_iq_certificate(
            auth["user_id"]
        )

        result["certificate"] = (
            serialize_db_row(certificate)
            if certificate
            else None
        )

    return {
        "ok": True,
        **result,
    }


@app.get("/api/result/{attempt_id}")
async def api_result(
    attempt_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    result = await get_result_for_user(
        auth["user_id"],
        attempt_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Result not found",
        )

    return {
        "ok": True,
        "result": {
            "id": str(result["id"]),
            "attempt_id": str(result["attempt_id"]),
            "test_type": result["test_type"],
            "score": float(result["score"]),
            "level": result["level"],
            "details": safe_json_loads(
                result["details"],
                {},
            ),
            "answers": safe_json_loads(
                result["answers"],
                {},
            ),
            "created_at": result["created_at"].isoformat(),
        },
    }


@app.post("/api/payment/create")
async def api_payment_create(
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

    product = str(
        body.get("product")
        or ""
    ).upper()

    allowed = {
        "IQ",
        "EQ",
        "PQ",
        "BATTLE",
    }

    if product not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Invalid product",
        )

    setting_key = (
        "battle_price"
        if product == "BATTLE"
        else f"{product.lower()}_retry_price"
    )

    amount = await get_int_setting(
        setting_key,
        7500 if product == "BATTLE" else 5000,
    )

    payment = await create_payment(
        auth["user_id"],
        product,
        amount,
    )

    card = None

    if payment["card_id"]:
        card = await db_fetchrow("""
            SELECT *
            FROM payment_cards
            WHERE id=$1
        """,
            payment["card_id"],
        )

    return {
        "ok": True,
        "payment": {
            "id": str(payment["id"]),
            "product": payment["product"],
            "amount": payment["amount"],
            "status": payment["status"],
            "card": (
                {
                    "id": str(card["id"]),
                    "card_number": card["card_number"],
                    "holder": card["holder"],
                    "bank": card["bank"],
                }
                if card
                else None
            ),
        },
    }


@app.get("/api/payment/mine")
async def api_payment_mine(
    request: Request,
):
    auth = await authenticated_user(request)

    rows = await get_user_payments(
        auth["user_id"]
    )

    return {
        "ok": True,
        "payments": [
            {
                "id": str(row["id"]),
                "product": row["product"],
                "amount": row["amount"],
                "status": row["status"],
                "card": (
                    {
                        "card_number": row["card_number"],
                        "holder": row["card_holder"],
                        "bank": row["bank"],
                    }
                    if row["card_number"]
                    else None
                ),
                "receipt_file_id": row["receipt_file_id"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ],
    }


@app.post("/api/payment/{payment_id}/receipt")
async def api_payment_receipt(
    payment_id: str,
    request: Request,
    receipt: UploadFile | None = File(default=None),
):
    auth = await authenticated_user(request)

    payment = await get_payment_for_user(
        auth["user_id"],
        payment_id,
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    if payment["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Payment is not pending",
        )

    if receipt is None:
        raise HTTPException(
            status_code=400,
            detail="Receipt file is required",
        )

    content_type = (
        receipt.content_type
        or ""
    ).lower()

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG or WEBP receipts are allowed",
        )

    data = await receipt.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Empty receipt",
        )

    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Receipt is too large",
        )

    telegram_file_id = None

    try:
        sent = await bot.send_document(
            chat_id=ADMIN_USER_ID,
            document=BufferedInputFile(
                data,
                filename=receipt.filename or "receipt",
            ),
            caption=(
                "💳 <b>Yangi payment receipt</b>\n\n"
                f"User: <code>{auth['user_id']}</code>\n"
                f"Payment: <code>{payment_id}</code>\n"
                f"Product: <b>{payment['product']}</b>\n"
                f"Amount: <b>{payment['amount']:,} so‘m</b>"
            ),
        )

        telegram_file_id = (
            sent.document.file_id
            if sent.document
            else None
        )

    except Exception as exc:
        logger.warning(
            "Could not forward receipt to admin: %s",
            exc,
        )

    await db_execute("""
        UPDATE payments
        SET
            receipt_file_id=$1,
            receipt_filename=$2,
            receipt_content_type=$3,
            updated_at=NOW()
        WHERE id=$4
          AND user_id=$5
    """,
        telegram_file_id,
        receipt.filename,
        content_type,
        payment["id"],
        auth["user_id"],
    )

    return {
        "ok": True,
        "receipt_file_id": telegram_file_id,
    }


@app.get("/api/ranking")
async def api_ranking(
    request: Request,
):
    await authenticated_user(request)

    rows = await ranking_rows(100)

    ranking = []

    for index, row in enumerate(rows, 1):
        score = row["iq_score"]

        if score is None:
            continue

        ranking.append({
            "rank": index,
            "user_id": row["user_id"],
            "name": row["display_name"],
            "score": float(score),
        })

    return {
        "ok": True,
        "ranking": ranking,
    }


@app.get("/api/stats/live")
async def api_stats_live(
    request: Request,
):
    await authenticated_user(request)

    return await get_live_stats()


@app.get("/api/certificate/mine")
async def api_certificate_mine(
    request: Request,
):
    auth = await authenticated_user(request)

    certificate = await get_or_create_iq_certificate(
        auth["user_id"]
    )

    if not certificate:
        return {
            "ok": True,
            "certificate": None,
        }

    return {
        "ok": True,
        "certificate": {
            "id": str(certificate["id"]),
            "certificate_id": certificate["certificate_id"],
            "verification_code": certificate["verification_code"],
            "type": certificate["type"],
            "full_name": certificate["full_name"],
            "score": float(certificate["score"]),
            "level": certificate["level"],
            "created_at": certificate["created_at"].isoformat(),
        },
    }


@app.get("/api/certificate/{certificate_id}/png")
async def api_certificate_png(
    certificate_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        from uuid import UUID
        certificate_uuid = UUID(str(certificate_id))
    except (ValueError, TypeError):
        certificate_uuid = None

    if certificate_uuid:
        certificate = await db_fetchrow("""
            SELECT *
            FROM certificates
            WHERE id=$1
              AND user_id=$2
        """,
            certificate_uuid,
            auth["user_id"],
        )
    else:
        certificate = await db_fetchrow("""
            SELECT *
            FROM certificates
            WHERE certificate_id=$1
              AND user_id=$2
        """,
            certificate_id,
            auth["user_id"],
        )

    if not certificate:
        raise HTTPException(
            status_code=404,
            detail="Certificate not found",
        )

    png = generate_certificate_png(
        certificate
    )

    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                'inline; filename="certificate.png"'
            )
        },
    )


@app.get("/api/certificate/verify/{verification_code}")
async def api_certificate_verify(
    verification_code: str,
):
    certificate = await db_fetchrow("""
        SELECT
            certificate_id,
            verification_code,
            type,
            full_name,
            score,
            level,
            created_at
        FROM certificates
        WHERE verification_code=$1
    """,
        clean_text(
            verification_code,
            30,
        ).upper(),
    )

    if not certificate:
        return {
            "ok": True,
            "valid": False,
        }

    return {
        "ok": True,
        "valid": True,
        "certificate": {
            "certificate_id": certificate["certificate_id"],
            "verification_code": certificate["verification_code"],
            "type": certificate["type"],
            "full_name": certificate["full_name"],
            "score": float(certificate["score"]),
            "level": certificate["level"],
            "created_at": certificate["created_at"].isoformat(),
        },
    }


@app.post("/api/battle/create")
async def api_battle_create(
    request: Request,
):
    auth = await authenticated_user(request)

    battle = await create_battle(
        auth["user_id"]
    )

    return {
        "ok": True,
        "battle": {
            "id": str(battle["id"]),
            "code": battle["code"],
            "status": battle["status"],
            "price": battle["price"],
        },
    }


@app.post("/api/battle/join")
async def api_battle_join(
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

    code = clean_text(
        body.get("code"),
        4,
    ).upper()

    if len(code) != 4:
        raise HTTPException(
            status_code=400,
            detail="Battle code must contain 4 characters",
        )

    try:
        battle = await join_battle(
            auth["user_id"],
            code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "ok": True,
        "battle": {
            "id": str(battle["id"]),
            "code": battle["code"],
            "status": battle["status"],
            "price": battle["price"],
        },
    }


@app.get("/api/battle/{battle_id}/start")
async def api_battle_start(
    battle_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    battle = await get_battle(
        battle_id
    )

    if not battle:
        raise HTTPException(
            status_code=404,
            detail="Battle not found",
        )

    player = await get_battle_player(
        battle_id,
        auth["user_id"],
    )

    if not player:
        raise HTTPException(
            status_code=403,
            detail="You are not a participant",
        )

    if player["payment_status"] != "approved":
        return {
            "ok": True,
            "payment_required": True,
            "price": battle["price"],
        }

    if battle["status"] not in {
        "active",
        "completed",
    }:
        return {
            "ok": True,
            "ready": False,
            "status": battle["status"],
        }

    questions = make_test_payload("IQ")

    return {
        "ok": True,
        "ready": True,
        "status": battle["status"],
        "battle_id": str(battle["id"]),
        "questions": questions,
    }


@app.post("/api/battle/{battle_id}/payment")
async def api_battle_payment(
    battle_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    battle = await get_battle(
        battle_id
    )

    if not battle:
        raise HTTPException(
            status_code=404,
            detail="Battle not found",
        )

    player = await get_battle_player(
        battle_id,
        auth["user_id"],
    )

    if not player:
        raise HTTPException(
            status_code=403,
            detail="You are not a participant",
        )

    existing = await db_fetchrow("""
        SELECT *
        FROM payments
        WHERE id=$1
          AND user_id=$2
    """,
        player["payment_id"],
        auth["user_id"],
    ) if player["payment_id"] else None

    if existing:
        payment = existing
    else:
        payment = await create_payment(
            auth["user_id"],
            "BATTLE",
            int(battle["price"]),
        )

        await db_execute("""
            UPDATE battle_players
            SET payment_id=$1
            WHERE battle_id=$2
              AND user_id=$3
        """,
            payment["id"],
            battle["id"],
            auth["user_id"],
        )

    card = await get_active_card()

    return {
        "ok": True,
        "payment": {
            "id": str(payment["id"]),
            "product": "BATTLE",
            "amount": payment["amount"],
            "status": payment["status"],
            "card": (
                {
                    "id": str(card["id"]),
                    "card_number": card["card_number"],
                    "holder": card["holder"],
                    "bank": card["bank"],
                }
                if card
                else None
            ),
        },
    }


@app.post("/api/battle/{battle_id}/submit")
async def api_battle_submit(
    battle_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON",
        )

    answers = body.get("answers")

    if not isinstance(answers, dict):
        raise HTTPException(
            status_code=400,
            detail="answers must be an object",
        )

    try:
        result = await submit_battle(
            battle_id,
            auth["user_id"],
            answers,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "ok": True,
        **result,
    }


@app.get("/api/battle/{battle_id}/result")
async def api_battle_result(
    battle_id: str,
    request: Request,
):
    auth = await authenticated_user(request)

    result = await get_battle_result(
        battle_id,
        auth["user_id"],
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Battle result not found",
        )

    return {
        "ok": True,
        **result,
    }


@app.get("/api/referral")
async def api_referral(
    request: Request,
):
    auth = await authenticated_user(request)

    stats = await get_referral_stats(
        auth["user_id"]
    )

    referral_link = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=ref_{auth['user_id']}"
    )

    return {
        "ok": True,
        "link": referral_link,
        **stats,
    }


webapp_dir = os.path.join(
    os.path.dirname(__file__),
    "webapp",
)

if os.path.isdir(webapp_dir):
    app.mount(
        "/static",
        StaticFiles(directory=webapp_dir),
        name="static",
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )