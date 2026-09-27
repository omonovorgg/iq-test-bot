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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

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

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db_pool: asyncpg.Pool | None = None

IQ_QUESTIONS = [
    # Each item is: id, weight, 8 matrix cells + question marker, 4 options, correct.
    # Renderer interprets cell descriptors deterministically.
    {"id":1,"weight":1,"matrix":[
        {"type":"dot","count":1},{"type":"dot","count":2},{"type":"dot","count":3},
        {"type":"dot","count":2},{"type":"dot","count":3},{"type":"dot","count":4},
        {"type":"dot","count":3},{"type":"dot","count":4},{"type":"question"}],
        "options":[{"type":"dot","count":5},{"type":"dot","count":6},{"type":"dot","count":7},{"type":"dot","count":4}],"correct":0},
    {"id":2,"weight":1,"matrix":[
        {"type":"shape","shape":"circle","fill":"full"},{"type":"shape","shape":"circle","fill":"half"},{"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"circle","fill":"half"},{"type":"shape","shape":"circle","fill":"empty"},{"type":"shape","shape":"circle","fill":"full"},
        {"type":"shape","shape":"circle","fill":"empty"},{"type":"shape","shape":"circle","fill":"full"},{"type":"question"}],
        "options":[{"type":"shape","shape":"circle","fill":"half"},{"type":"shape","shape":"circle","fill":"empty"},{"type":"shape","shape":"circle","fill":"full"},{"type":"shape","shape":"square","fill":"half"}],"correct":0},
    {"id":3,"weight":1,"matrix":[
        {"type":"grid","pos":0},{"type":"grid","pos":1},{"type":"grid","pos":2},
        {"type":"grid","pos":1},{"type":"grid","pos":2},{"type":"grid","pos":3},
        {"type":"grid","pos":2},{"type":"grid","pos":3},{"type":"question"}],
        "options":[{"type":"grid","pos":4},{"type":"grid","pos":5},{"type":"grid","pos":1},{"type":"grid","pos":6}],"correct":0},
    {"id":4,"weight":1,"matrix":[
        {"type":"shape","shape":"triangle","fill":"empty"},{"type":"shape","shape":"square","fill":"empty"},{"type":"shape","shape":"diamond","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},{"type":"shape","shape":"diamond","fill":"empty"},{"type":"shape","shape":"circle","fill":"empty"},
        {"type":"shape","shape":"diamond","fill":"empty"},{"type":"shape","shape":"circle","fill":"empty"},{"type":"question"}],
        "options":[{"type":"shape","shape":"triangle","fill":"empty"},{"type":"shape","shape":"square","fill":"empty"},{"type":"shape","shape":"circle","fill":"empty"},{"type":"shape","shape":"diamond","fill":"empty"}],"correct":0},
    {"id":5,"weight":1,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"empty"},{"type":"combo","shapes":["square"],"fill":"empty"},{"type":"combo","shapes":["circle","square"],"fill":"empty"},
        {"type":"combo","shapes":["triangle"],"fill":"half"},{"type":"combo","shapes":["diamond"],"fill":"half"},{"type":"combo","shapes":["triangle","diamond"],"fill":"half"},
        {"type":"combo","shapes":["circle","triangle"],"fill":"full"},{"type":"combo","shapes":["square","diamond"],"fill":"full"},{"type":"question"}],
        "options":[{"type":"combo","shapes":["circle","triangle","square","diamond"],"fill":"full"},{"type":"combo","shapes":["circle","square"],"fill":"full"},{"type":"combo","shapes":["triangle","diamond"],"fill":"full"},{"type":"combo","shapes":["circle","diamond"],"fill":"full"}],"correct":0},
    {"id":6,"weight":1,"matrix":[
        {"type":"num","val":2},{"type":"num","val":4},{"type":"num","val":6},
        {"type":"num","val":3},{"type":"num","val":6},{"type":"num","val":9},
        {"type":"num","val":4},{"type":"num","val":8},{"type":"question"}],
        "options":[{"type":"num","val":10},{"type":"num","val":12},{"type":"num","val":14},{"type":"num","val":16}],"correct":1},
    {"id":7,"weight":2,"matrix":[
        {"type":"shape","shape":"circle","fill":"full"},{"type":"shape","shape":"square","fill":"half"},{"type":"shape","shape":"triangle","fill":"empty"},
        {"type":"shape","shape":"square","fill":"empty"},{"type":"shape","shape":"triangle","fill":"full"},{"type":"shape","shape":"diamond","fill":"half"},
        {"type":"shape","shape":"triangle","fill":"half"},{"type":"shape","shape":"diamond","fill":"empty"},{"type":"question"}],
        "options":[{"type":"shape","shape":"circle","fill":"full"},{"type":"shape","shape":"circle","fill":"half"},{"type":"shape","shape":"circle","fill":"empty"},{"type":"shape","shape":"diamond","fill":"full"}],"correct":0},
    {"id":8,"weight":2,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"full"},{"type":"combo","shapes":["square"],"fill":"half"},{"type":"combo","shapes":["triangle"],"fill":"empty"},
        {"type":"combo","shapes":["square"],"fill":"half"},{"type":"combo","shapes":["triangle"],"fill":"empty"},{"type":"combo","shapes":["diamond"],"fill":"full"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},{"type":"combo","shapes":["diamond"],"fill":"full"},{"type":"question"}],
        "options":[{"type":"combo","shapes":["circle"],"fill":"half"},{"type":"combo","shapes":["circle"],"fill":"full"},{"type":"combo","shapes":["square"],"fill":"empty"},{"type":"combo","shapes":["diamond"],"fill":"half"}],"correct":1},
    {"id":9,"weight":2,"matrix":[
        {"type":"dot","count":1},{"type":"dot","count":3},{"type":"dot","count":6},
        {"type":"dot","count":2},{"type":"dot","count":5},{"type":"dot","count":9},
        {"type":"dot","count":3},{"type":"dot","count":7},{"type":"question"}],
        "options":[{"type":"dot","count":10},{"type":"dot","count":11},{"type":"dot","count":12},{"type":"dot","count":13}],"correct":2},
    {"id":10,"weight":2,"matrix":[
        {"type":"grid","pos":0},{"type":"grid","pos":4},{"type":"grid","pos":8},
        {"type":"grid","pos":1},{"type":"grid","pos":4},{"type":"grid","pos":7},
        {"type":"grid","pos":2},{"type":"grid","pos":4},{"type":"question"}],
        "options":[{"type":"grid","pos":6},{"type":"grid","pos":5},{"type":"grid","pos":3},{"type":"grid","pos":0}],"correct":0},
    {"id":11,"weight":2,"matrix":[
        {"type":"num","val":3},{"type":"num","val":5},{"type":"num","val":8},
        {"type":"num","val":5},{"type":"num","val":8},{"type":"num","val":13},
        {"type":"num","val":8},{"type":"num","val":13},{"type":"question"}],
        "options":[{"type":"num","val":18},{"type":"num","val":21},{"type":"num","val":20},{"type":"num","val":22}],"correct":1},
    {"id":12,"weight":2,"matrix":[
        {"type":"combo","shapes":["circle","square"],"fill":"empty"},{"type":"combo","shapes":["circle","triangle"],"fill":"half"},{"type":"combo","shapes":["circle","diamond"],"fill":"full"},
        {"type":"combo","shapes":["square","triangle"],"fill":"half"},{"type":"combo","shapes":["square","diamond"],"fill":"full"},{"type":"combo","shapes":["square","circle"],"fill":"empty"},
        {"type":"combo","shapes":["triangle","diamond"],"fill":"full"},{"type":"combo","shapes":["triangle","circle"],"fill":"empty"},{"type":"question"}],
        "options":[{"type":"combo","shapes":["triangle","square"],"fill":"half"},{"type":"combo","shapes":["triangle","square"],"fill":"full"},{"type":"combo","shapes":["diamond","square"],"fill":"empty"},{"type":"combo","shapes":["circle","diamond"],"fill":"half"}],"correct":0},
    {"id":13,"weight":3,"matrix":[
        {"type":"num","val":2},{"type":"num","val":3},{"type":"num","val":5},
        {"type":"num","val":3},{"type":"num","val":5},{"type":"num","val":8},
        {"type":"num","val":5},{"type":"num","val":8},{"type":"question"}],
        "options":[{"type":"num","val":12},{"type":"num","val":13},{"type":"num","val":14},{"type":"num","val":15}],"correct":1},
    {"id":14,"weight":3,"matrix":[
        {"type":"grid","pos":0},{"type":"grid","pos":2},{"type":"grid","pos":4},
        {"type":"grid","pos":3},{"type":"grid","pos":5},{"type":"grid","pos":7},
        {"type":"grid","pos":6},{"type":"grid","pos":8},{"type":"question"}],
        "options":[{"type":"grid","pos":1},{"type":"grid","pos":0},{"type":"grid","pos":2},{"type":"grid","pos":7}],"correct":0},
    {"id":15,"weight":3,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"empty"},{"type":"combo","shapes":["circle","square"],"fill":"half"},{"type":"combo","shapes":["circle","square","triangle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"half"},{"type":"combo","shapes":["square","triangle"],"fill":"full"},{"type":"combo","shapes":["square","triangle","diamond"],"fill":"empty"},
        {"type":"combo","shapes":["triangle"],"fill":"full"},{"type":"combo","shapes":["triangle","diamond"],"fill":"empty"},{"type":"question"}],
        "options":[{"type":"combo","shapes":["triangle","diamond","circle"],"fill":"half"},{"type":"combo","shapes":["triangle","diamond","circle"],"fill":"full"},{"type":"combo","shapes":["diamond","circle"],"fill":"half"},{"type":"combo","shapes":["triangle","circle"],"fill":"empty"}],"correct":0},
    {"id":16,"weight":3,"matrix":[
        {"type":"num","val":4},{"type":"num","val":7},{"type":"num","val":13},
        {"type":"num","val":5},{"type":"num","val":9},{"type":"num","val":17},
        {"type":"num","val":6},{"type":"num","val":11},{"type":"question"}],
        "options":[{"type":"num","val":21},{"type":"num","val":22},{"type":"num","val":23},{"type":"num","val":24}],"correct":0},
    {"id":17,"weight":3,"matrix":[
        {"type":"combo","shapes":["circle"],"fill":"full"},{"type":"combo","shapes":["square"],"fill":"full"},{"type":"combo","shapes":["triangle"],"fill":"full"},
        {"type":"combo","shapes":["square"],"fill":"half"},{"type":"combo","shapes":["triangle"],"fill":"half"},{"type":"combo","shapes":["diamond"],"fill":"half"},
        {"type":"combo","shapes":["triangle"],"fill":"empty"},{"type":"combo","shapes":["diamond"],"fill":"empty"},{"type":"question"}],
        "options":[{"type":"combo","shapes":["circle"],"fill":"empty"},{"type":"combo","shapes":["circle"],"fill":"half"},{"type":"combo","shapes":["diamond"],"fill":"empty"},{"type":"combo","shapes":["square"],"fill":"empty"}],"correct":0},
    {"id":18,"weight":3,"matrix":[
        {"type":"num","val":1},{"type":"num","val":4},{"type":"num","val":9},
        {"type":"num","val":8},{"type":"num","val":27},{"type":"num","val":64},
        {"type":"num","val":125},{"type":"num","val":216},{"type":"question"}],
        "options":[{"type":"num","val":343},{"type":"num","val":512},{"type":"num","val":729},{"type":"num","val":256}],"correct":0},
]

EQ_QUESTIONS = [
    ("You are interrupted during an important task. What is the most constructive first step?", ["React angrily", "Pause, clarify the interruption, and choose a response", "Ignore everyone", "Quit the task"], 1),
    ("A friend criticizes your work in public. What is the most constructive response?", ["Attack back", "Change the subject", "Listen, ask what could be improved, and discuss it calmly", "Pretend nothing happened"], 2),
    ("You notice a teammate is unusually quiet. What is the most useful response?", ["Pressure them to talk", "Check in privately and give them space to respond", "Gossip about it", "Exclude them"], 1),
    ("You make a mistake that affects other people. What should you do next?", ["Acknowledge it, explain briefly, and help repair the impact", "Hide it until someone notices", "Blame someone else", "Wait silently"], 0),
    ("Two people strongly disagree in a discussion. What is most likely to improve the conversation?", ["Choose a side immediately", "Raise your voice so your point wins", "Clarify each person's viewpoint and the point of disagreement", "End the discussion without hearing either side"], 2),
    ("You receive a stressful message late at night. What is usually the most constructive approach?", ["Reply immediately while angry", "Forward it to several people", "Delete the sender", "Pause, regulate your reaction, and respond when you can think clearly"], 3),
]
PQ_QUESTIONS = [
    ("You have three tasks due today. What is the most practical first step?", ["Do random tasks", "Prioritize them by urgency and impact", "Avoid all tasks", "Start with whichever looks easiest"], 1),
    ("A long project feels overwhelming. What is most useful?", ["Never plan", "Wait until motivation appears", "Do everything at once", "Break the project into concrete milestones and next actions"], 3),
    ("Your current plan stops producing the expected result. What should you do?", ["Repeat it blindly", "Abandon the goal immediately", "Review the evidence, identify what changed, and adjust the plan", "Blame the tool"], 2),
    ("You keep delaying a difficult task. Which approach is most actionable?", ["Make the task larger", "Define a small concrete first action and start it", "Ignore the deadline", "Add unrelated tasks"], 1),
    ("A goal conflicts with a new opportunity. What helps you decide?", ["Compare the trade-offs against your priorities", "Choose randomly", "Ask everyone else to decide for you", "Do both without limits"], 0),
    ("You finish an important milestone. What improves the next phase?", ["Never review it", "Reset everything", "Record what worked, what failed, and what to change next", "Avoid feedback"], 2),
]

TRANSLATIONS = {
    "uz": {
        "choose_lang":"Tilni tanlang:",
        "welcome":"Salom, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nAqlingizni sinash uchun Mini App'ni oching.",
        "menu_test":"🧠 IQ · EQ · PQ testini ishlash",
        "menu_cert":"📜 Sertifikatim",
        "menu_rank":"🏆 Reyting",
        "menu_earn":"💰 Pul ishlash",
        "menu_help":"ℹ️ Narx va yordam",
        "menu_lang":"🌐 Til",
        "no_cert":"Hali sertifikatingiz yo‘q.",
        "cert_not_found":"Sertifikat topilmadi.",
        "lang_changed":"Til o‘zgartirildi.",
    },
    "ru": {
        "choose_lang":"Выберите язык:",
        "welcome":"Привет, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nОткройте Mini App, чтобы пройти тест.",
        "menu_test":"🧠 Пройти IQ · EQ · PQ",
        "menu_cert":"📜 Мой сертификат",
        "menu_rank":"🏆 Рейтинг",
        "menu_earn":"💰 Заработать",
        "menu_help":"ℹ️ Цена и помощь",
        "menu_lang":"🌐 Язык",
        "no_cert":"У вас пока нет сертификата.",
        "cert_not_found":"Сертификат не найден.",
        "lang_changed":"Язык изменён.",
    },
    "en": {
        "choose_lang":"Choose language:",
        "welcome":"Hello, {name}! 👋\n\n<b>IQ TEST BOT</b>\n\nOpen the Mini App to take the test.",
        "menu_test":"🧠 Take IQ · EQ · PQ",
        "menu_cert":"📜 My certificate",
        "menu_rank":"🏆 Ranking",
        "menu_earn":"💰 Earn",
        "menu_help":"ℹ️ Prices & help",
        "menu_lang":"🌐 Language",
        "no_cert":"You do not have a certificate yet.",
        "cert_not_found":"Certificate not found.",
        "lang_changed":"Language changed.",
    }
}

def t(lang: str, key: str, **kwargs):
    lang = lang if lang in TRANSLATIONS else "uz"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["uz"].get(key, key)).format(**kwargs)

async def db_execute(query, *args):
    async with db_pool.acquire() as conn:
        return await conn.execute(query, *args)

async def db_fetchrow(query, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def db_fetch(query, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def migrate():
    global db_pool
    await db_execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT NOT NULL DEFAULT 'uz',
        full_name TEXT,
        gender TEXT,
        age INTEGER,
        country TEXT,
        last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS test_sessions (
        session_id UUID PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        test_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        answers JSONB NOT NULL DEFAULT '{}'::jsonb,
        questions JSONB,
        score INTEGER,
        correct_count INTEGER,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        expires_at TIMESTAMPTZ NOT NULL,
        price INTEGER NOT NULL DEFAULT 0,
        is_retry BOOLEAN NOT NULL DEFAULT FALSE
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS test_attempts (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        test_type TEXT NOT NULL,
        session_id UUID UNIQUE REFERENCES test_sessions(session_id) ON DELETE SET NULL,
        score INTEGER,
        correct_count INTEGER,
        duration INTEGER,
        payment_status TEXT NOT NULL DEFAULT 'not_required',
        result_visible BOOLEAN NOT NULL DEFAULT FALSE,
        level TEXT,
        answers JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS results (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        attempt_id BIGINT UNIQUE REFERENCES test_attempts(id) ON DELETE CASCADE,
        test_type TEXT NOT NULL,
        score INTEGER NOT NULL,
        level TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS payment_cards (
        id BIGSERIAL PRIMARY KEY,
        card_number TEXT NOT NULL,
        holder TEXT,
        bank TEXT,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        attempt_id BIGINT REFERENCES test_attempts(id) ON DELETE SET NULL,
        battle_id UUID,
        payment_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        card_id BIGINT REFERENCES payment_cards(id) ON DELETE SET NULL,
        receipt_file_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS certificates (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        result_id BIGINT UNIQUE REFERENCES results(id) ON DELETE SET NULL,
        certificate_id TEXT UNIQUE NOT NULL,
        verification_code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL DEFAULT 'IQ',
        full_name TEXT NOT NULL,
        score INTEGER NOT NULL,
        level TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS battles (
        id UUID PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting',
        created_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ready_at TIMESTAMPTZ,
        finalized_at TIMESTAMPTZ
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS battle_players (
        battle_id UUID NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        payment_id BIGINT REFERENCES payments(id) ON DELETE SET NULL,
        session_id UUID REFERENCES test_sessions(session_id) ON DELETE SET NULL,
        score INTEGER,
        correct_count INTEGER,
        finished_at TIMESTAMPTZ,
        PRIMARY KEY (battle_id, user_id)
    )""")
    await db_execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        referrer_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        referred_id BIGINT UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (referrer_id, referred_id)
    )""")

    # Safe migrations for existing installations.
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'uz'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS verification_code TEXT",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS certificate_id TEXT",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'IQ'",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS full_name TEXT",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS score INTEGER DEFAULT 0",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS level TEXT",
        "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS bank TEXT",
        "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS battle_id UUID",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS attempt_id BIGINT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS payment_status TEXT NOT NULL DEFAULT 'not_required'",
        "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS result_visible BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS level TEXT",
        "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS answers JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS duration INTEGER",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS attempt_id BIGINT",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS test_type TEXT",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS score INTEGER",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS level TEXT",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS result_id BIGINT",
        "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS card_number TEXT",
        "ALTER TABLE payment_cards ADD COLUMN IF NOT EXISTS holder TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS user_id BIGINT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_type TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS amount INTEGER",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS card_id BIGINT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS receipt_file_id TEXT",
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS is_retry BOOLEAN NOT NULL DEFAULT FALSE",
        # Battle columns are explicitly migrated because CREATE TABLE IF NOT EXISTS
        # does not alter an already-existing table.
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS code TEXT",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'waiting'",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS created_by BIGINT",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS ready_at TIMESTAMPTZ",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS role TEXT",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS payment_id BIGINT",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS session_id UUID",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS score INTEGER",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS correct_count INTEGER",
        "ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ",
        "ALTER TABLE referrals ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ]
    for q in migrations:
        try:
            await db_execute(q)
        except Exception:
            logger.exception("Migration failed: %s", q)
            raise

    # Existing databases may have battle_players rows created by an older
    # version without the role column. Backfill those rows before enforcing
    # NOT NULL, using battles.created_by to identify the creator.
    await db_execute("""
        UPDATE battle_players bp
        SET role = CASE
            WHEN EXISTS (
                SELECT 1
                FROM battles b
                WHERE b.id = bp.battle_id
                  AND b.created_by = bp.user_id
            ) THEN 'creator'
            ELSE 'opponent'
        END
        WHERE bp.role IS NULL OR bp.role=''
    """)
    await db_execute("""
        ALTER TABLE battle_players
        ALTER COLUMN role SET DEFAULT 'opponent'
    """)
    await db_execute("""
        ALTER TABLE battle_players
        ALTER COLUMN role SET NOT NULL
    """)

    # Battle row locking in join/start flows is the concurrency guard. A normal
    # index keeps legacy databases with duplicate historical rows migratable.
    await db_execute("""
        CREATE INDEX IF NOT EXISTS ix_battle_players_battle_role
        ON battle_players(battle_id, role)
    """)
    await db_execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_test_attempt_session ON test_attempts(session_id) WHERE session_id IS NOT NULL")
    await db_execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_certificate_result ON certificates(result_id) WHERE result_id IS NOT NULL")
    await db_execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_certificate_id ON certificates(certificate_id) WHERE certificate_id IS NOT NULL")
    await db_execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_certificate_verification ON certificates(verification_code) WHERE verification_code IS NOT NULL")

    defaults = {
        "iq_price":"0","iq_retry_price":"5000","eq_price":"0","eq_retry_price":"5000",
        "pq_price":"0","pq_retry_price":"5000","battle_price":"7500",
        "live_mode":"fake","live_fake_base":"95114","live_fake_online":"342","live_fake_delta":"8"
    }
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            for k, v in defaults.items():
                await conn.execute(
                    "INSERT INTO app_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO NOTHING",
                    k, v
                )
            if ADMIN_USER_ID:
                await conn.execute(
                    "INSERT INTO admins(user_id) VALUES($1) ON CONFLICT(user_id) DO NOTHING",
                    ADMIN_USER_ID
                )

async def setting(key, default=None):
    row = await db_fetchrow("SELECT value FROM app_settings WHERE key=$1", key)
    return row["value"] if row else default

async def setting_int(key, default=0):
    try:
        return int(await setting(key, str(default)))
    except (TypeError, ValueError):
        return default

async def upsert_user(tg_user: types.User):
    await db_execute("""
        INSERT INTO users(user_id,username,first_name,last_name,last_seen,updated_at)
        VALUES($1,$2,$3,$4,NOW(),NOW())
        ON CONFLICT(user_id) DO UPDATE SET
          username=EXCLUDED.username,
          first_name=EXCLUDED.first_name,
          last_name=EXCLUDED.last_name,
          last_seen=NOW(),
          updated_at=NOW()
    """, tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)

async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID or bool(
        await db_fetchrow("SELECT 1 FROM admins WHERE user_id=$1", user_id)
    )

def main_keyboard(lang="uz"):
    # IMPORTANT: a Mini App opened from a ReplyKeyboard web_app button
    # does not provide WebApp initData in Telegram clients. The backend
    # requires validated initData, so the actual Mini App launcher is an
    # InlineKeyboardButton below. Keep the reply keyboard for the other
    # bot actions only.
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang,"menu_cert")), KeyboardButton(text=t(lang,"menu_rank"))],
            [KeyboardButton(text=t(lang,"menu_earn")), KeyboardButton(text=t(lang,"menu_help"))],
            [KeyboardButton(text=t(lang,"menu_lang"))],
        ],
        resize_keyboard=True,
        is_persistent=True
    )

def app_inline_keyboard(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t(lang,"menu_test"),
            web_app=WebAppInfo(url=WEBAPP_URL + "/app")
        )]
    ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    try:
        await upsert_user(message.from_user)
        start_arg = (message.text or "").split(maxsplit=1)[1].strip() if len((message.text or "").split(maxsplit=1)) > 1 else ""
        if start_arg.startswith("ref_"):
            try:
                referrer_id = int(start_arg[4:])
                if referrer_id != message.from_user.id:
                    await db_execute(
                        "INSERT INTO referrals(referrer_id,referred_id) VALUES($1,$2) ON CONFLICT(referred_id) DO NOTHING",
                        referrer_id, message.from_user.id
                    )
            except (ValueError, asyncpg.PostgresError):
                logger.info("Invalid referral start parameter")
        row = await db_fetchrow("SELECT language FROM users WHERE user_id=$1", message.from_user.id)
        lang = row["language"] if row else "uz"
        if not row or row["language"] not in TRANSLATIONS:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
                 InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                 InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")]
            ])
            await message.answer(t("uz","choose_lang"), reply_markup=kb)
            return
        await message.answer(
            t(lang,"welcome",name=message.from_user.first_name or "do‘st"),
            reply_markup=app_inline_keyboard(lang)
        )
        await message.answer(
            "⬇️ Quyidagi tugma orqali Mini App'ni oching.",
            reply_markup=main_keyboard(lang)
        )
    except Exception:
        logger.exception("/start failed")
        await message.answer("Xatolik yuz berdi. Iltimos, qayta /start yuboring.")

@dp.callback_query(F.data.startswith("lang:"))
async def lang_callback(callback: CallbackQuery):
    lang = callback.data.split(":",1)[1]
    if lang not in TRANSLATIONS:
        await callback.answer("Invalid language", show_alert=True)
        return
    await db_execute("UPDATE users SET language=$1,updated_at=NOW() WHERE user_id=$2", lang, callback.from_user.id)
    await callback.answer(t(lang,"lang_changed"))
    try:
        await callback.message.edit_text(t(lang,"lang_changed"))
    except Exception:
        pass
    await callback.message.answer(
        t(lang,"welcome",name=callback.from_user.first_name or "friend"),
        reply_markup=app_inline_keyboard(lang)
    )
    await callback.message.answer(
        "⬇️ Quyidagi tugma orqali Mini App'ni oching.",
        reply_markup=main_keyboard(lang)
    )

@dp.message(F.text.regexp(r"^IQ-[A-Za-z0-9]{6}$"))
async def verify_certificate_message(message: types.Message):
    code = message.text.strip().upper()
    row = await db_fetchrow("SELECT full_name,score,level,verification_code,created_at FROM certificates WHERE verification_code=$1", code)
    if not row:
        await message.answer("❌ Sertifikat topilmadi.")
        return
    await message.answer(
        f"📜 <b>IQ TEST BOT</b>\n\n👤 {row['full_name']}\n🧠 IQ: <b>{row['score']}</b>\n🏷 {row['level'] or '—'}\n🔐 <code>{row['verification_code']}</code>"
    )

@dp.message(F.text.in_({"🧠 IQ · EQ · PQ testini ishlash","🧠 Пройти IQ · EQ · PQ","🧠 Take IQ · EQ · PQ"}))
async def open_app_from_old_keyboard(message: types.Message):
    # Handles old persistent keyboards that may still contain the previous
    # ReplyKeyboard web_app button. The Mini App itself must be launched
    # from an inline web_app button so Telegram supplies initData.
    row = await db_fetchrow(
        "SELECT language FROM users WHERE user_id=$1",
        message.from_user.id
    )
    lang = row["language"] if row and row["language"] in TRANSLATIONS else "uz"
    await message.answer(
        "🧠 Mini App'ni ochish uchun quyidagi tugmani bosing:",
        reply_markup=app_inline_keyboard(lang)
    )

@dp.message(F.text.in_({"📜 Sertifikatim","📜 Мой сертификат","📜 My certificate"}))
async def my_certificate(message: types.Message):
    row = await db_fetchrow("""
        SELECT certificate_id,verification_code,full_name,score,level,created_at
        FROM certificates WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1
    """, message.from_user.id)
    lang_row = await db_fetchrow("SELECT language FROM users WHERE user_id=$1", message.from_user.id)
    lang = lang_row["language"] if lang_row else "uz"
    if not row:
        await message.answer(t(lang,"no_cert"))
        return
    await message.answer(
        f"📜 <b>IQ TEST BOT</b>\n\n"
        f"👤 {row['full_name']}\n"
        f"🧠 IQ: <b>{row['score']}</b>\n"
        f"🏷 {row['level'] or '—'}\n"
        f"🔐 <code>{row['verification_code']}</code>"
    )

@dp.message(F.text.in_({"🏆 Reyting","🏆 Рейтинг","🏆 Ranking"}))
async def ranking_message(message: types.Message):
    rows = await db_fetch("""
        SELECT u.full_name, r.score, r.level
        FROM results r JOIN users u ON u.user_id=r.user_id
        WHERE r.test_type='IQ'
        ORDER BY r.score DESC, r.created_at ASC LIMIT 10
    """)
    if not rows:
        await message.answer("🏆 Reyting\n\nHali natijalar yo‘q.")
        return
    lines = ["🏆 <b>REYTING</b>",""]
    for i, r in enumerate(rows,1):
        lines.append(f"{i}. {r['full_name'] or 'Foydalanuvchi'} — <b>{r['score']}</b> · {r['level'] or '—'}")
    await message.answer("\n".join(lines))

@dp.message(F.text.in_({"ℹ️ Narx va yordam","ℹ️ Цена и помощь","ℹ️ Prices & help"}))
async def help_message(message: types.Message):
    vals = await asyncio.gather(
        setting_int("iq_price"), setting_int("eq_price"), setting_int("pq_price"), setting_int("battle_price")
    )
    await message.answer(
        f"<b>IQ TEST BOT</b>\n\n"
        f"🧠 IQ — {vals[0]:,} so‘m\n🎭 EQ — {vals[1]:,} so‘m\n⏳ PQ — {vals[2]:,} so‘m\n⚔️ Battle — {vals[3]:,} so‘m"
        .replace(",", " ")
    )

@dp.message(F.text.in_({"🌐 Til","🌐 Язык","🌐 Language"}))
async def language_message(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")]
    ])
    await message.answer("Til / Язык / Language", reply_markup=kb)

@dp.message(F.text.in_({"💰 Pul ishlash","💰 Заработать","💰 Earn"}))
async def referral_message(message: types.Message):
    count = await db_fetchrow("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id=$1", message.from_user.id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    await message.answer(f"💰 <b>Pul ishlash</b>\n\nTaklif havolangiz:\n<code>{link}</code>\n\nTakliflar: <b>{count['c']}</b>")

@dp.message(Command("addcard"))
async def admin_add_card(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    payload=message.text.partition(" ")[2].strip()
    parts=[x.strip() for x in payload.split("|",2)]
    if len(parts)!=3 or not parts[0]:
        await message.answer("Format: /addcard 8600...|HOLDER|BANK"); return
    await db_execute("INSERT INTO payment_cards(card_number,holder,bank,active) VALUES($1,$2,$3,TRUE)",*parts)
    await message.answer("✅ Karta qo‘shildi.")

@dp.message(Command("delcard"))
async def admin_delete_card(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    try: cid=int(message.text.partition(" ")[2].strip())
    except: await message.answer("Format: /delcard ID"); return
    await db_execute("DELETE FROM payment_cards WHERE id=$1",cid)
    await message.answer("✅ Karta o‘chirildi.")

@dp.message(Command("cardon"))
async def admin_card_on(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    try: cid=int(message.text.partition(" ")[2].strip())
    except: await message.answer("Format: /cardon ID"); return
    await db_execute("UPDATE payment_cards SET active=TRUE WHERE id=$1",cid); await message.answer("✅ Karta faollashtirildi.")

@dp.message(Command("cardoff"))
async def admin_card_off(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    try: cid=int(message.text.partition(" ")[2].strip())
    except: await message.answer("Format: /cardoff ID"); return
    await db_execute("UPDATE payment_cards SET active=FALSE WHERE id=$1",cid); await message.answer("✅ Karta o‘chirildi.")

@dp.message(Command("setprice"))
async def admin_set_price(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    parts=message.text.split()
    if len(parts)!=3 or parts[1] not in {"iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"}:
        await message.answer("Format: /setprice iq_price 5000"); return
    try: val=int(parts[2]); assert val>=0
    except: await message.answer("Narx 0 yoki musbat son bo‘lsin."); return
    await db_execute("INSERT INTO app_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",parts[1],str(val))
    await message.answer(f"✅ {parts[1]} = {val}")

@dp.message(Command("setlive"))
async def admin_set_live(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    parts=message.text.split()
    if len(parts) not in (3,5) or parts[1] not in ("fake","real"):
        await message.answer("Format: /setlive fake 95114 342 8 yoki /setlive real"); return
    await db_execute("INSERT INTO app_settings(key,value) VALUES('live_mode',$1) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",parts[1])
    if parts[1]=="fake" and len(parts)==5:
        for k,v in zip(("live_fake_base","live_fake_online","live_fake_delta"),parts[2:]):
            try:int(v)
            except: await message.answer("Fake qiymatlar son bo‘lsin."); return
            await db_execute("INSERT INTO app_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",k,v)
    await message.answer("✅ Live counter yangilandi.")

@dp.message(Command("broadcast"))
async def admin_broadcast(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    text=message.text.partition(" ")[2].strip()
    if not text: await message.answer("Format: /broadcast Matn"); return
    users=await db_fetch("SELECT user_id FROM users")
    sent=0
    for u in users:
        try:
            await bot.send_message(u["user_id"],text)
            sent+=1
            await asyncio.sleep(.05)
        except Exception:
            logger.exception("Broadcast delivery failed for user %s",u["user_id"])
    await message.answer(f"✅ Yuborildi: {sent}/{len(users)}")

@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q.")
        return
    await send_admin_panel(message)

async def send_admin_panel(target):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
         InlineKeyboardButton(text="📊 Statistics", callback_data="admin:stats")],
        [InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments"),
         InlineKeyboardButton(text="💰 Products", callback_data="admin:products")],
        [InlineKeyboardButton(text="📜 Certificates", callback_data="admin:certs"),
         InlineKeyboardButton(text="⚔️ Battles", callback_data="admin:battles")],
        [InlineKeyboardButton(text="💳 Cards", callback_data="admin:cards"),
         InlineKeyboardButton(text="🎯 Live Counter", callback_data="admin:live")],
    ])
    await target.answer("⚙️ <b>ADMIN PANEL</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery):
    try:
        if not await is_admin(callback.from_user.id):
            await callback.answer("Ruxsat yo‘q", show_alert=True)
            return
        action = callback.data.split(":",1)[1]
        payment_buttons = []
        if action == "home":
            try: await callback.message.delete()
            except Exception: pass
            await send_admin_panel(callback.message)
            await callback.answer()
            return
        if action.startswith("approve:"):
            try: pid=int(action.split(":",1)[1])
            except ValueError: await callback.answer("Payment ID noto‘g‘ri",show_alert=True); return
            p,status=await approve_payment_record(pid)
            if not p: await callback.answer("Payment topilmadi",show_alert=True); return
            try: await bot.send_message(p["user_id"],"✅ To‘lov tasdiqlandi.")
            except Exception: logger.exception("Admin approval notification failed")
            text=f"✅ Payment #{pid} tasdiqlandi."
        elif action.startswith("reject:"):
            try: pid=int(action.split(":",1)[1])
            except ValueError: await callback.answer("Payment ID noto‘g‘ri",show_alert=True); return
            p=await db_fetchrow("SELECT * FROM payments WHERE id=$1",pid)
            if not p: await callback.answer("Payment topilmadi",show_alert=True); return
            await db_execute("UPDATE payments SET status='rejected',updated_at=NOW() WHERE id=$1",pid)
            try: await bot.send_message(p["user_id"],"❌ To‘lov rad etildi. Receiptni tekshirib qayta yuboring.")
            except Exception: logger.exception("Admin rejection notification failed")
            text=f"❌ Payment #{pid} rad etildi."
        elif action == "users":
            row = await db_fetchrow("SELECT COUNT(*) c FROM users")
            text = f"👥 Users: <b>{row['c']}</b>"
        elif action == "stats":
            row = await db_fetchrow("SELECT COUNT(*) c FROM results")
            text = f"📊 Results: <b>{row['c']}</b>"
        elif action == "payments":
            rows = await db_fetch("SELECT id,user_id,amount,status,payment_type FROM payments ORDER BY id DESC LIMIT 10")
            text = "💳 <b>Payments</b>\n\n" + "\n".join(
                f"#{r['id']} · {r['user_id']} · {r['amount']} · {r['status']} · {r['payment_type']}" for r in rows
            ) if rows else "Payment yo‘q."
            payment_buttons = [[InlineKeyboardButton(text=f"#{r['id']} ✅", callback_data=f"admin:approve:{r['id']}"), InlineKeyboardButton(text=f"#{r['id']} ❌", callback_data=f"admin:reject:{r['id']}")] for r in rows if r['status']=='pending']
        elif action == "products":
            keys=["iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"]
            vals=await asyncio.gather(*(setting(k,"0") for k in keys))
            text="💰 <b>Products</b>\n\n"+"\n".join(f"{k}: {v}" for k,v in zip(keys,vals))
        elif action == "certs":
            row=await db_fetchrow("SELECT COUNT(*) c FROM certificates")
            text=f"📜 Certificates: <b>{row['c']}</b>"
        elif action == "battles":
            row=await db_fetchrow("SELECT COUNT(*) c FROM battles")
            text=f"⚔️ Battles: <b>{row['c']}</b>"
        elif action == "cards":
            rows=await db_fetch("SELECT id,card_number,holder,bank,active FROM payment_cards ORDER BY id DESC")
            text="💳 <b>Cards</b>\n\n" + "\n".join(
                f"#{r['id']} · {r['card_number']} · {r['holder'] or ''} · {r['bank'] or ''} · {'ON' if r['active'] else 'OFF'}" for r in rows
            ) if rows else "Kartalar yo‘q."
        elif action == "live":
            vals=await asyncio.gather(setting("live_mode","fake"),setting("live_fake_base","95114"),setting("live_fake_online","342"),setting("live_fake_delta","8"))
            text=f"🎯 Live\nmode={vals[0]}\nbase={vals[1]}\nonline={vals[2]}\ndelta={vals[3]}"
        else:
            text="Noma’lum bo‘lim."
        keyboard = payment_buttons + [[InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    except Exception:
        logger.exception("Admin callback failed")
        await callback.answer("Xatolik", show_alert=True)

@dp.callback_query(F.data=="admin:home")
async def admin_home(callback: CallbackQuery):
    if await is_admin(callback.from_user.id):
        await callback.message.delete()
        await send_admin_panel(callback.message)

def validate_init_data(init_data: str, bot_token: str):
    """Validate Telegram Mini App initData exactly as a query string.

    Telegram signs the decoded key/value pairs (excluding ``hash``), sorted
    alphabetically and joined with newlines.  ``parse_qsl`` is important here:
    manually hashing the still-percent-encoded values can produce an invalid
    hash even though Telegram supplied valid initData.
    """
    if not init_data:
        raise ValueError("initData is empty")

    from urllib.parse import parse_qsl

    try:
        items = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    except Exception as exc:
        raise ValueError("invalid initData format") from exc

    pairs = {}
    for key, value in items:
        if key == "hash":
            # Telegram sends one hash. Keep the last one if a malformed client
            # supplied duplicates; duplicate fields are not accepted as trusted
            # identity data unless the final HMAC still matches.
            pairs["__telegram_hash__"] = value
        else:
            pairs[key] = value

    hash_value = pairs.pop("__telegram_hash__", "")
    if not hash_value:
        raise ValueError("hash missing")

    data_check = "\n".join(
        f"{key}={pairs[key]}" for key in sorted(pairs)
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256
    ).digest()

    calculated = hmac.new(
        secret_key,
        data_check.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated, hash_value):
        raise ValueError("invalid hash")

    if "auth_date" not in pairs:
        raise ValueError("auth_date missing")

    try:
        auth_date = int(pairs["auth_date"])
    except ValueError:
        raise ValueError("invalid auth_date")

    if abs(int(datetime.now(timezone.utc).timestamp()) - auth_date) > 86400:
        raise ValueError("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise ValueError("user missing")

    try:
        user = json.loads(user_raw)
    except Exception as exc:
        raise ValueError("invalid user json") from exc

    if not isinstance(user, dict) or not user.get("id"):
        raise ValueError("invalid user")

    return user

async def authenticated_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if not init_data:
        init_data = request.headers.get("X-Telegram-WebApp-Init-Data", "").strip()
    try:
        return validate_init_data(init_data, BOT_TOKEN)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

def json_error(message, status=400):
    return JSONResponse({"ok":False,"error":message}, status_code=status)

def level_for_score(score):
    if score < 85: return "Boshlang‘ich"
    if score < 100: return "O‘rtacha"
    if score < 115: return "Yaxshi"
    if score < 125: return "Yuqori"
    return "Juda yuqori"

def calculate_iq(answers):
    total=0
    max_total=sum(q["weight"] for q in IQ_QUESTIONS)
    for q in IQ_QUESTIONS:
        ans=answers.get(str(q["id"]))
        if ans == q["correct"]:
            total += q["weight"]
    score = round(70 + 60 * total / max_total)
    return max(70,min(130,score)), total, max_total

def public_iq_questions():
    return [{k:v for k,v in q.items() if k != "correct"} for q in IQ_QUESTIONS]

def new_session():
    return uuid4()

async def get_owned_attempt(user_id, attempt_id):
    return await db_fetchrow("SELECT * FROM test_attempts WHERE id=$1 AND user_id=$2", attempt_id, user_id)

async def active_card():
    return await db_fetchrow("SELECT * FROM payment_cards WHERE active=TRUE ORDER BY created_at DESC LIMIT 1")

async def create_certificate(user_id, result_id, full_name, score, level):
    existing = await db_fetchrow("SELECT * FROM certificates WHERE result_id=$1", result_id)
    if existing:
        return existing
    code = "IQ-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    cid = "CERT-" + secrets.token_hex(6).upper()
    return await db_fetchrow("""
        INSERT INTO certificates(user_id,result_id,certificate_id,verification_code,type,full_name,score,level)
        VALUES($1,$2,$3,$4,'IQ',$5,$6,$7) RETURNING *
    """, user_id,result_id,cid,code,full_name,score,level)

def font_path(size=64):
    patterns = [
        "/usr/share/fonts/**/*.ttf",
        "/usr/local/share/fonts/**/*.ttf",
        "/usr/share/fonts/truetype/dejavu/*.ttf",
    ]
    files=[]
    for p in patterns: files.extend(glob.glob(p, recursive=True))
    preferred=[p for p in files if "DejaVuSans" in p]
    return preferred[0] if preferred else (files[0] if files else None)

def certificate_png(cert):
    img=Image.new("RGB",(1600,1100),(8,11,22))
    d=ImageDraw.Draw(img)
    gold=(220,180,75); white=(245,247,255); muted=(180,188,210)
    d.rounded_rectangle((35,35,1565,1065),radius=35,outline=gold,width=8)
    d.rounded_rectangle((65,65,1535,1035),radius=25,outline=(65,72,100),width=2)
    cx,cy=800,250
    d.ellipse((cx-95,cy-95,cx+95,cy+95),outline=gold,width=5)
    d.ellipse((cx-70,cy-70,cx+70,cy+70),outline=(120,130,170),width=2)
    for i in range(8):
        x=cx+int(45*((i%4)-1.5)); y=cy+int(35*((i//4)-0.5))
        d.ellipse((x-10,y-10,x+10,y+10),fill=gold)
    fp=font_path()
    if not fp:
        raise RuntimeError("Professional TTF font topilmadi")
    def font(sz):
        return ImageFont.truetype(fp,sz)
    def center(txt,y,f,fill=white):
        box=d.textbbox((0,0),txt,font=f); d.text(((1600-(box[2]-box[0]))/2,y),txt,font=f,fill=fill)
    def center_fit(txt,y,max_size,min_size,fill=white,max_width=1320):
        size=max_size
        while size>min_size:
            f=font(size); box=d.textbbox((0,0),txt,font=f)
            if box[2]-box[0] <= max_width: break
            size-=2
        center(txt,y,font(max(size,min_size)),fill)
    center("SERTIFIKAT",380,font(82),gold)
    center("AQLLIY SALOHIYAT TO‘G‘RISIDA",485,font(42),muted)
    center_fit(str(cert["full_name"]),590,66,34,white)
    center_fit(f"IQ  {cert['score']}  ·  {cert['level'] or '—'}",690,48,30,white)
    center_fit(f"Verification: {cert['verification_code']}",790,38,24,muted)
    center("IQ TEST BOT",910,font(36),gold)
    bio=io.BytesIO(); img.save(bio,"PNG"); bio.seek(0)
    return bio.getvalue()

async def submit_iq_internal(user_id, session_id, answers, duration=0):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            session = await conn.fetchrow(
                "SELECT * FROM test_sessions WHERE session_id=$1 AND user_id=$2 FOR UPDATE",
                session_id, user_id
            )
            if not session:
                raise ValueError("session_not_found")
            if session["status"] == "completed":
                return await conn.fetchrow("SELECT * FROM test_attempts WHERE session_id=$1", session_id)
            if session["expires_at"] < datetime.now(timezone.utc):
                raise ValueError("session_expired")
            score, correct_count, _ = calculate_iq(answers)
            price = int(session["price"] or 0)
            payment_status = "approved" if (price or 0) == 0 else "pending"
            visible = (price or 0) == 0
            attempt = await conn.fetchrow("""
                INSERT INTO test_attempts(user_id,test_type,session_id,score,correct_count,duration,payment_status,result_visible,level,answers)
                VALUES($1,'IQ',$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
            """, user_id, session_id, score, correct_count, max(0, int(duration)),
                payment_status, visible, level_for_score(score), json.dumps(answers))
            await conn.execute("""
                UPDATE test_sessions SET status='completed',answers=$2,score=$3,correct_count=$4,completed_at=NOW()
                WHERE session_id=$1
            """, session_id, json.dumps(answers), score, correct_count)
            if visible:
                await conn.execute("""
                    INSERT INTO results(user_id,attempt_id,test_type,score,level)
                    VALUES($1,$2,'IQ',$3,$4) ON CONFLICT(attempt_id) DO NOTHING
                """, user_id, attempt["id"], score, level_for_score(score))
            return attempt

async def expose_result(attempt_id, user_id):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            attempt=await conn.fetchrow("SELECT * FROM test_attempts WHERE id=$1 AND user_id=$2 FOR UPDATE",attempt_id,user_id)
            if not attempt: return None
            if attempt["result_visible"]:
                return attempt
            payment=await conn.fetchrow("SELECT * FROM payments WHERE attempt_id=$1 AND user_id=$2 AND status='approved' ORDER BY id DESC LIMIT 1",attempt_id,user_id)
            if not payment: return attempt
            await conn.execute("UPDATE test_attempts SET result_visible=TRUE,payment_status='approved' WHERE id=$1",attempt_id)
            await conn.execute("""
                INSERT INTO results(user_id,attempt_id,test_type,score,level)
                VALUES($1,$2,$3,$4,$5) ON CONFLICT(attempt_id) DO NOTHING
            """,user_id,attempt_id,attempt["test_type"],attempt["score"],attempt["level"])
            return await conn.fetchrow("SELECT * FROM test_attempts WHERE id=$1",attempt_id)

app = FastAPI(title="IQ TEST BOT")

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/app", response_class=HTMLResponse)
async def app_page():
    path=os.path.join(BASE_DIR,"webapp","index.html")
    with open(path,"r",encoding="utf-8") as f:
        return HTMLResponse(f.read())

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR,"webapp")), name="static")

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    supplied=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if not WEBHOOK_SECRET or not hmac.compare_digest(supplied,WEBHOOK_SECRET):
        raise HTTPException(status_code=403,detail="Forbidden")
    try:
        payload=await request.json()
        update=Update.model_validate(payload)
        await dp.feed_update(bot,update)
        return {"ok":True}
    except Exception:
        logger.exception("Webhook processing failed")
        raise HTTPException(status_code=500,detail="Webhook processing error")

@app.get("/api/bootstrap")
async def api_bootstrap(request: Request):
    user=await authenticated_user(request)
    uid=int(user["id"])
    await db_execute("""
        INSERT INTO users(user_id,username,first_name,last_name,last_seen,updated_at)
        VALUES($1,$2,$3,$4,NOW(),NOW())
        ON CONFLICT(user_id) DO UPDATE SET username=$2,first_name=$3,last_name=$4,last_seen=NOW(),updated_at=NOW()
    """,uid,user.get("username"),user.get("first_name"),user.get("last_name"))
    row=await db_fetchrow("SELECT * FROM users WHERE user_id=$1",uid)
    prices={k:await setting_int(k) for k in ["iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"]}
    iq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='IQ' LIMIT 1",uid))
    eq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='EQ' LIMIT 1",uid))
    pq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='PQ' LIMIT 1",uid))
    return {"ok":True,"user":{"id":uid,"username":row["username"],"first_name":row["first_name"],"language":row["language"],"full_name":row["full_name"],"gender":row["gender"],"age":row["age"],"country":row["country"],"hasIQ":iq_done,"hasEQ":eq_done,"hasPQ":pq_done},"prices":prices,"questions":public_iq_questions()}

@app.post("/api/profile/save")
async def profile_save(request: Request):
    user=await authenticated_user(request); data=await request.json(); uid=int(user["id"])
    full_name=str(data.get("full_name","")).strip()
    gender=str(data.get("gender","")).strip()
    country=str(data.get("country","")).strip()
    try: age=int(data.get("age"))
    except: return json_error("Yosh noto‘g‘ri")
    if not full_name or len(full_name)>120 or gender not in ("male","female") or age<10 or age>120 or not country:
        return json_error("Profil ma’lumotlari noto‘g‘ri")
    await db_execute("UPDATE users SET full_name=$1,gender=$2,age=$3,country=$4,updated_at=NOW() WHERE user_id=$5",full_name,gender,age,country,uid)
    return {"ok":True}

@app.post("/api/test/start")
async def test_start(request: Request):
    user=await authenticated_user(request)
    data=await request.json()
    uid=int(user["id"])
    typ=str(data.get("test_type","IQ")).upper()
    if typ not in ("IQ","EQ","PQ"):
        return json_error("Noto‘g‘ri test")
    if typ=="EQ":
        exists=await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='IQ' LIMIT 1",uid)
        if not exists: return json_error("Avval IQ testni yakunlang",403)
    if typ=="PQ":
        exists=await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='EQ' LIMIT 1",uid)
        if not exists: return json_error("Avval EQ testni yakunlang",403)

    price_key={"IQ":"iq_price","EQ":"eq_price","PQ":"pq_price"}[typ]
    retry_key={"IQ":"iq_retry_price","EQ":"eq_retry_price","PQ":"pq_retry_price"}[typ]
    has_previous=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type=$2 LIMIT 1",uid,typ))
    price=await setting_int(retry_key if has_previous else price_key,0)
    active=await db_fetchrow("SELECT session_id,test_type,questions,answers,started_at,expires_at,price,is_retry FROM test_sessions WHERE user_id=$1 AND test_type=$2 AND status='active' AND expires_at>NOW() ORDER BY started_at DESC LIMIT 1",uid,typ)
    if active:
        return {"ok":True,"session_id":str(active["session_id"]),"test_type":active["test_type"],"questions":active["questions"],"answers":active["answers"],"started_at":active["started_at"].isoformat(),"expires_at":active["expires_at"].isoformat(),"price":int(active["price"] or 0),"is_retry":bool(active["is_retry"]),"resumed":True}
    sid=new_session()
    expires=datetime.now(timezone.utc)+timedelta(minutes=30)
    if typ=="IQ":
        questions=public_iq_questions()
    else:
        source=EQ_QUESTIONS if typ=="EQ" else PQ_QUESTIONS
        questions=[{"id":i+1,"text":q,"options":opts} for i,(q,opts,_) in enumerate(source)]
    await db_execute(
        "INSERT INTO test_sessions(session_id,user_id,test_type,status,questions,expires_at,price,is_retry) VALUES($1,$2,$3,'active',$4,$5,$6,$7)",
        sid,uid,typ,json.dumps(questions),expires,price,has_previous
    )
    return {"ok":True,"session_id":str(sid),"test_type":typ,"questions":questions,"expires_at":expires.isoformat(),"price":price,"is_retry":has_previous}

@app.post("/api/test/{session_id}/submit")
async def test_submit(session_id: str, request: Request):
    user=await authenticated_user(request)
    data=await request.json()
    uid=int(user["id"])
    answers=data.get("answers") or {}
    try: duration=max(0,int(data.get("duration") or 0))
    except (TypeError,ValueError): duration=0
    session=await db_fetchrow("SELECT * FROM test_sessions WHERE session_id=$1::uuid AND user_id=$2",session_id,uid)
    if not session: return json_error("Session topilmadi",404)
    if session["status"] == "completed":
        attempt=await db_fetchrow("SELECT * FROM test_attempts WHERE session_id=$1::uuid",session_id)
        if not attempt: return json_error("Session holati noto‘g‘ri",409)
    elif session["expires_at"] < datetime.now(timezone.utc):
        return json_error("Test vaqti tugagan",409)
    elif session["test_type"]=="IQ":
        try: attempt=await submit_iq_internal(uid,session_id,answers,duration)
        except ValueError as exc: return json_error(str(exc),409)
    else:
        source=EQ_QUESTIONS if session["test_type"]=="EQ" else PQ_QUESTIONS
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                locked=await conn.fetchrow("SELECT * FROM test_sessions WHERE session_id=$1::uuid AND user_id=$2 FOR UPDATE",session_id,uid)
                if locked["status"]=="completed":
                    attempt=await conn.fetchrow("SELECT * FROM test_attempts WHERE session_id=$1::uuid",session_id)
                else:
                    correct=sum(1 for i,(_,_,c) in enumerate(source) if answers.get(str(i+1)) == c or str(answers.get(str(i+1))) == str(c))
                    score=round(100*correct/len(source))
                    price=int(locked["price"] or 0)
                    visible=price==0
                    payment_status="approved" if visible else "pending"
                    attempt=await conn.fetchrow("""
                        INSERT INTO test_attempts(user_id,test_type,session_id,score,correct_count,duration,payment_status,result_visible,level,answers)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *
                    """,uid,locked["test_type"],session_id,score,correct,duration,payment_status,visible,"EQ/PQ",json.dumps(answers))
                    await conn.execute("UPDATE test_sessions SET status='completed',answers=$2,score=$3,correct_count=$4,completed_at=NOW() WHERE session_id=$1::uuid",session_id,json.dumps(answers),score,correct)
                    if visible:
                        await conn.execute("INSERT INTO results(user_id,attempt_id,test_type,score,level) VALUES($1,$2,$3,$4,$5) ON CONFLICT(attempt_id) DO NOTHING",uid,attempt["id"],locked["test_type"],score,"EQ/PQ")
    if session["test_type"] == "IQ" and attempt["result_visible"]:
        result_row = await db_fetchrow("SELECT * FROM results WHERE attempt_id=$1", attempt["id"])
        user_row = await db_fetchrow("SELECT full_name FROM users WHERE user_id=$1", uid)
        if result_row and user_row and user_row["full_name"]:
            await create_certificate(uid, result_row["id"], user_row["full_name"], attempt["score"], attempt["level"])
    price=int(session["price"] or 0)
    if price>0 and attempt["payment_status"]!="approved":
        card=await active_card()
        existing=await db_fetchrow("SELECT id,status,amount,card_id FROM payments WHERE attempt_id=$1 AND user_id=$2 ORDER BY id DESC LIMIT 1",attempt["id"],uid)
        if existing:
            payment_id=existing["id"]
            if existing["status"]=="approved":
                return {"ok":True,"payment_required":False,"attempt_id":attempt["id"],"score":attempt["score"],"level":attempt["level"],"correct_count":attempt["correct_count"]}
        else:
            created=await db_fetchrow("INSERT INTO payments(user_id,attempt_id,payment_type,amount,card_id,status) VALUES($1,$2,$3,$4,$5,'pending') RETURNING id",uid,attempt["id"],session["test_type"],price,card["id"] if card else None)
            payment_id=created["id"]
        return {"ok":True,"payment_required":True,"attempt_id":attempt["id"],"payment_id":payment_id,"amount":price,"card":dict(card) if card else None}
    return {"ok":True,"payment_required":False,"attempt_id":attempt["id"],"score":attempt["score"],"level":attempt["level"],"correct_count":attempt["correct_count"]}

@app.get("/api/test/{session_id}/resume")
async def test_resume(session_id: str, request: Request):
    user=await authenticated_user(request); uid=int(user["id"])
    s=await db_fetchrow("SELECT * FROM test_sessions WHERE session_id=$1 AND user_id=$2",session_id,uid)
    if not s: return json_error("Session topilmadi",404)
    if s["status"]=="active" and s["expires_at"] < datetime.now(timezone.utc):
        await db_execute("UPDATE test_sessions SET status='expired' WHERE session_id=$1::uuid AND user_id=$2 AND status='active'",session_id,uid)
        return {"ok":True,"status":"expired","test_type":s["test_type"],"questions":s["questions"],"answers":s["answers"]}
    return {"ok":True,"status":s["status"],"test_type":s["test_type"],"questions":s["questions"],"answers":s["answers"]}

@app.get("/api/result/{attempt_id}")
async def get_result(attempt_id:int,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    a=await get_owned_attempt(uid,attempt_id)
    if not a: return json_error("Natija topilmadi",404)
    if not a["result_visible"]: return {"ok":True,"visible":False,"payment_status":a["payment_status"]}
    return {"ok":True,"visible":True,"score":a["score"],"level":a["level"],"correct_count":a["correct_count"],"test_type":a["test_type"]}

@app.post("/api/payment/create")
async def payment_create(request:Request):
    user=await authenticated_user(request); data=await request.json(); uid=int(user["id"])
    attempt_id=data.get("attempt_id"); payment_type=str(data.get("payment_type","IQ"))
    a=await get_owned_attempt(uid,int(attempt_id))
    if not a: return json_error("Attempt topilmadi",404)
    if a["payment_status"]=="approved": return {"ok":True,"status":"approved"}
    if payment_type != a["test_type"]:
        return json_error("Payment turi attempt bilan mos emas")
    key={"IQ":"iq_price","EQ":"eq_price","PQ":"pq_price"}.get(payment_type)
    if not key: return json_error("Payment turi noto‘g‘ri")
    amount=await setting_int(key)
    if amount <= 0:
        return {"ok":True,"status":"not_required","amount":0}
    card=await active_card()
    existing=await db_fetchrow("SELECT id,status,amount,card_id FROM payments WHERE attempt_id=$1 AND user_id=$2 ORDER BY id DESC LIMIT 1",int(attempt_id),uid)
    if existing and existing["status"] in ("pending","approved"):
        selected_card=await db_fetchrow("SELECT id,card_number,holder,bank,active FROM payment_cards WHERE id=$1",existing["card_id"]) if existing["card_id"] else card
        return {"ok":True,"payment_id":existing["id"],"status":existing["status"],"amount":existing["amount"],"card":dict(selected_card) if selected_card else None}
    p=await db_fetchrow("INSERT INTO payments(user_id,attempt_id,payment_type,amount,card_id,status) VALUES($1,$2,$3,$4,$5,'pending') RETURNING id",uid,int(attempt_id),payment_type,amount,card["id"] if card else None)
    return {"ok":True,"payment_id":p["id"],"status":"pending","amount":amount,"card":dict(card) if card else None}

@app.post("/api/payment/{payment_id}/receipt")
async def payment_receipt(payment_id:int,request:Request,receipt:UploadFile|None=File(default=None)):
    user=await authenticated_user(request)
    uid=int(user["id"])
    p=await db_fetchrow("SELECT * FROM payments WHERE id=$1 AND user_id=$2",payment_id,uid)
    if not p: return json_error("Payment topilmadi",404)
    if p["status"]=="approved": return {"ok":True,"status":"approved"}
    file_id=None
    if receipt is not None:
        if not receipt.content_type or not receipt.content_type.startswith("image/"):
            return json_error("Receipt faqat rasm bo‘lishi kerak")
        raw=await receipt.read()
        if len(raw)>8*1024*1024:
            return json_error("Receipt 8 MB dan kichik bo‘lishi kerak")
        if not ADMIN_USER_ID:
            return json_error("Admin sozlanmagan",500)
        tg_file=BufferedInputFile(raw,filename=receipt.filename or "receipt.jpg")
        sent=await bot.send_document(ADMIN_USER_ID,tg_file,caption=f"💳 Receipt #{payment_id}\nUser: <code>{uid}</code>\nAmount: <b>{p['amount']}</b>")
        file_id=sent.document.file_id if sent.document else None
    else:
        # Backward-compatible path for an existing Telegram file_id.
        try:
            form=await request.form()
            file_id=str(form.get("receipt_file_id") or "").strip() or None
        except Exception:
            file_id=None
    if not file_id: return json_error("Receipt faylini tanlang")
    await db_execute("UPDATE payments SET receipt_file_id=$1,updated_at=NOW() WHERE id=$2 AND user_id=$3",file_id,payment_id,uid)
    return {"ok":True,"status":"pending"}

@app.get("/api/payment/mine")
async def my_payments(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    rows=await db_fetch("SELECT id,attempt_id,payment_type,amount,status,created_at FROM payments WHERE user_id=$1 ORDER BY id DESC LIMIT 20",uid)
    return {"ok":True,"payments":[dict(r) for r in rows]}

async def approve_payment_record(payment_id:int):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            p=await conn.fetchrow("SELECT * FROM payments WHERE id=$1 FOR UPDATE",payment_id)
            if not p: return None, "not_found"
            if p["status"]=="approved": return p, "already"
            await conn.execute("UPDATE payments SET status='approved',updated_at=NOW() WHERE id=$1",payment_id)
            if p["battle_id"]:
                await conn.execute("UPDATE battle_players SET payment_id=$1 WHERE battle_id=$2 AND user_id=$3",p["id"],p["battle_id"],p["user_id"])
                battle=await conn.fetchrow("SELECT * FROM battles WHERE id=$1 FOR UPDATE",p["battle_id"])
                approved_count=await conn.fetchval("SELECT COUNT(*) FROM battle_players bp JOIN payments pay ON pay.id=bp.payment_id WHERE bp.battle_id=$1 AND pay.status='approved'",p["battle_id"])
                player_count=await conn.fetchval("SELECT COUNT(*) FROM battle_players WHERE battle_id=$1",p["battle_id"])
                if battle and player_count==2 and approved_count==2:
                    await conn.execute("UPDATE battles SET status='ready',ready_at=NOW() WHERE id=$1 AND status<>'finished'",p["battle_id"])
            if p["attempt_id"]:
                await conn.execute("UPDATE test_attempts SET payment_status='approved',result_visible=TRUE WHERE id=$1",p["attempt_id"])
                await conn.execute("""
                    INSERT INTO results(user_id,attempt_id,test_type,score,level)
                    SELECT user_id,id,test_type,score,level FROM test_attempts WHERE id=$1
                    ON CONFLICT(attempt_id) DO NOTHING
                """,p["attempt_id"])
                attempt_row=await conn.fetchrow("SELECT * FROM test_attempts WHERE id=$1",p["attempt_id"])
                if attempt_row and attempt_row["test_type"]=="IQ":
                    result_row=await conn.fetchrow("SELECT * FROM results WHERE attempt_id=$1",p["attempt_id"])
                    user_row=await conn.fetchrow("SELECT full_name FROM users WHERE user_id=$1",p["user_id"])
                    if result_row and user_row and user_row["full_name"]:
                        await conn.execute("""
                            INSERT INTO certificates(user_id,result_id,certificate_id,verification_code,type,full_name,score,level)
                            VALUES($1,$2,$3,$4,'IQ',$5,$6,$7) ON CONFLICT(result_id) DO NOTHING
                        """,p["user_id"],result_row["id"],"CERT-"+secrets.token_hex(6).upper(),"IQ-"+"".join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6)),user_row["full_name"],attempt_row["score"],attempt_row["level"])
            return p, "approved"

@app.post("/api/admin/payment/{payment_id}/approve")
async def admin_approve_payment(payment_id:int,request:Request):
    user=await authenticated_user(request)
    if not await is_admin(int(user["id"])): raise HTTPException(403,"Forbidden")
    p,status=await approve_payment_record(payment_id)
    if not p: return json_error("Payment topilmadi",404)
    try:
        await bot.send_message(p["user_id"],"✅ To‘lov tasdiqlandi. Natijangiz yoki Battle ochildi.")
    except Exception: logger.exception("Payment notification failed")
    return {"ok":True,"status":status}

@app.post("/api/admin/payment/{payment_id}/reject")
async def admin_reject_payment(payment_id:int,request:Request):
    user=await authenticated_user(request)
    if not await is_admin(int(user["id"])): raise HTTPException(403,"Forbidden")
    p=await db_fetchrow("SELECT * FROM payments WHERE id=$1",payment_id)
    if not p: return json_error("Payment topilmadi",404)
    await db_execute("UPDATE payments SET status='rejected',updated_at=NOW() WHERE id=$1",payment_id)
    try: await bot.send_message(p["user_id"],"❌ To‘lov rad etildi. Iltimos, receiptni tekshirib qayta yuboring.")
    except Exception: logger.exception("Payment rejection notification failed")
    return {"ok":True}

@app.get("/api/payment/{payment_id}/card")
async def payment_card(payment_id:int,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    p=await db_fetchrow("SELECT * FROM payments WHERE id=$1 AND user_id=$2",payment_id,uid)
    if not p: return json_error("Payment topilmadi",404)
    card=await db_fetchrow("SELECT id,card_number,holder,bank,active FROM payment_cards WHERE id=$1 AND active=TRUE",p["card_id"])
    return {"ok":True,"card":dict(card) if card else None}

@app.get("/api/certificate/mine")
async def certificate_mine(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    row=await db_fetchrow("SELECT * FROM certificates WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1",uid)
    if not row: return {"ok":True,"certificate":None}
    return {"ok":True,"certificate":dict(row)}

@app.get("/api/certificate/{verification_code}")
async def certificate_verify(verification_code:str,request:Request):
    # Public verification by unique code, no private fields beyond certificate.
    row=await db_fetchrow("SELECT full_name,score,level,verification_code,created_at FROM certificates WHERE verification_code=$1",verification_code.upper())
    if not row: return json_error("Sertifikat topilmadi",404)
    return {"ok":True,"certificate":dict(row)}

@app.get("/api/certificate/{certificate_id}/png")
async def certificate_png_endpoint(certificate_id:str,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    cert=await db_fetchrow("SELECT * FROM certificates WHERE certificate_id=$1 AND user_id=$2",certificate_id,uid)
    if not cert: return json_error("Sertifikat topilmadi",404)
    return Response(certificate_png(cert),media_type="image/png",headers={"Content-Disposition":f'inline; filename="{certificate_id}.png"'})

@app.get("/api/ranking")
async def api_ranking(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    rows=await db_fetch("""
        SELECT u.full_name,r.score,r.level
        FROM results r JOIN users u ON u.user_id=r.user_id
        WHERE r.test_type='IQ'
        ORDER BY r.score DESC,r.created_at ASC LIMIT 100
    """)
    items=[{"position":i+1,"name":r["full_name"] or "Foydalanuvchi","score":r["score"],"level":r["level"]} for i,r in enumerate(rows)]
    pos=next((x["position"] for x in items if x["name"] and False),None)
    mine=await db_fetchrow("""
        SELECT COUNT(*)+1 AS position FROM results
        WHERE test_type='IQ' AND score > COALESCE((SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='IQ'),-1)
    """,uid)
    return {"ok":True,"ranking":items,"my_position":mine["position"] if mine else None}

@app.get("/api/stats/live")
async def stats_live(request:Request):
    mode=await setting("live_mode","fake")
    if mode=="real":
        row=await db_fetchrow("SELECT COUNT(*) c FROM users WHERE last_seen > NOW()-INTERVAL '5 minutes'")
        online=max(0,int(row["c"]))
        total=await db_fetchrow("SELECT COUNT(*) c FROM users")
        return {"ok":True,"mode":"real","total":int(total["c"]),"online":online}
    base=await setting_int("live_fake_base",95114); online=await setting_int("live_fake_online",342); delta=await setting_int("live_fake_delta",8)
    import random
    value=max(1,base+random.randint(-delta,delta))
    on=max(1,online+random.randint(-max(1,delta//2),max(1,delta//2)))
    return {"ok":True,"mode":"fake","total":value,"online":on}

def battle_code():
    alphabet=string.ascii_uppercase+string.digits
    return "".join(secrets.choice(alphabet) for _ in range(4))

@app.post("/api/battle/create")
async def battle_create(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    price=await setting_int("battle_price",7500)
    for _ in range(10):
        code=battle_code()
        try:
            row=await db_fetchrow("INSERT INTO battles(id,code,created_by,status) VALUES($1,$2,$3,'waiting') RETURNING id,code",uuid4(),code,uid)
            break
        except asyncpg.UniqueViolationError:
            continue
    else: return json_error("Battle kodini yaratib bo‘lmadi",500)
    await db_execute("INSERT INTO battle_players(battle_id,user_id,role) VALUES($1,$2,'creator')",row["id"],uid)
    return {"ok":True,"battle_id":str(row["id"]),"code":row["code"],"price":price}

@app.post("/api/battle/join")
async def battle_join(request:Request):
    user=await authenticated_user(request)
    data=await request.json()
    uid=int(user["id"])
    code=str(data.get("code","")).upper().strip()
    if len(code)!=4 or any(c not in string.ascii_uppercase+string.digits for c in code):
        return json_error("Battle kodi 4 belgidan iborat")
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            battle=await conn.fetchrow("SELECT * FROM battles WHERE code=$1 FOR UPDATE",code)
            if not battle: return json_error("Battle topilmadi",404)
            if battle["created_by"]==uid: return json_error("O‘zingizga opponent bo‘la olmaysiz")
            if battle["status"] not in ("waiting","payments"): return json_error("Battle allaqachon boshlangan")
            existing=await conn.fetchrow("SELECT * FROM battle_players WHERE battle_id=$1 AND user_id=$2",battle["id"],uid)
            if not existing:
                try:
                    await conn.execute("INSERT INTO battle_players(battle_id,user_id,role) VALUES($1,$2,'opponent')",battle["id"],uid)
                except asyncpg.UniqueViolationError:
                    return json_error("Bu battle allaqachon to‘ldirilgan",409)
            await conn.execute("UPDATE battles SET status='payments' WHERE id=$1 AND status='waiting'",battle["id"])
    price=await setting_int("battle_price",7500)
    return {"ok":True,"battle_id":str(battle["id"]),"price":price}

@app.get("/api/battle/{battle_id}")
async def battle_get(battle_id:str,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    b=await db_fetchrow("SELECT * FROM battles WHERE id=$1::uuid",battle_id)
    if not b: return json_error("Battle topilmadi",404)
    p=await db_fetchrow("SELECT * FROM battle_players WHERE battle_id=$1::uuid AND user_id=$2",battle_id,uid)
    if not p: raise HTTPException(403,"Forbidden")
    players=await db_fetch("SELECT user_id,role,score,finished_at FROM battle_players WHERE battle_id=$1::uuid ORDER BY role",battle_id)
    # Never expose opponent score before both finish.
    both_finished=all(x["finished_at"] is not None for x in players) and len(players)==2
    safe_players=[]
    for x in players:
        safe_players.append({"role":x["role"],"is_me":x["user_id"]==uid,"finished":x["finished_at"] is not None,"score":x["score"] if (x["user_id"]==uid or both_finished) else None})
    return {"ok":True,"battle":{"id":str(b["id"]),"code":b["code"],"status":b["status"],"players":safe_players}}

@app.post("/api/battle/{battle_id}/payment")
async def battle_payment(battle_id:str,request:Request):
    user=await authenticated_user(request)
    uid=int(user["id"])
    p=await db_fetchrow("SELECT * FROM battle_players WHERE battle_id=$1::uuid AND user_id=$2",battle_id,uid)
    if not p: raise HTTPException(403,"Forbidden")
    amount=await setting_int("battle_price",7500)
    existing=await db_fetchrow("SELECT * FROM payments WHERE battle_id=$1::uuid AND user_id=$2 ORDER BY id DESC LIMIT 1",battle_id,uid)
    card=await active_card()
    if existing:
        if existing["status"]=="approved":
            return {"ok":True,"payment_id":existing["id"],"amount":existing["amount"],"status":"approved","card":dict(card) if card else None}
        if existing["status"]=="pending":
            selected_card=await db_fetchrow("SELECT id,card_number,holder,bank,active FROM payment_cards WHERE id=$1",existing["card_id"]) if existing["card_id"] else card
            return {"ok":True,"payment_id":existing["id"],"amount":existing["amount"],"status":"pending","card":dict(selected_card) if selected_card else None}
    pay=await db_fetchrow("INSERT INTO payments(user_id,battle_id,payment_type,amount,card_id,status) VALUES($1,$2::uuid,'BATTLE',$3,$4,'pending') RETURNING id",uid,battle_id,amount,card["id"] if card else None)
    await db_execute("UPDATE battle_players SET payment_id=$1 WHERE battle_id=$2::uuid AND user_id=$3",pay["id"],battle_id,uid)
    return {"ok":True,"payment_id":pay["id"],"amount":amount,"status":"pending","card":dict(card) if card else None}

@app.get("/api/battle/{battle_id}/start")
async def battle_start(battle_id:str,request:Request):
    user=await authenticated_user(request)
    uid=int(user["id"])
    async with db_pool.acquire() as conn:
        battle=await conn.fetchrow("SELECT * FROM battles WHERE id=$1::uuid",battle_id)
        player=await conn.fetchrow("SELECT * FROM battle_players WHERE battle_id=$1::uuid AND user_id=$2",battle_id,uid)
        if not battle or not player: raise HTTPException(403,"Forbidden")
        players=await conn.fetch("""SELECT bp.*, pay.status AS payment_status FROM battle_players bp LEFT JOIN payments pay ON pay.id=bp.payment_id WHERE bp.battle_id=$1::uuid ORDER BY bp.role""",battle_id)
    if len(players)!=2 or any(x["payment_status"]!="approved" for x in players):
        return {"ok":True,"ready":False,"status":battle["status"] if battle else "unknown"}
    return {"ok":True,"ready":True,"status":"ready","questions":public_iq_questions()}

@app.post("/api/battle/{battle_id}/submit")
async def battle_submit(battle_id:str,request:Request):
    user=await authenticated_user(request)
    data=await request.json()
    uid=int(user["id"])
    answers=data.get("answers") or {}
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            p=await conn.fetchrow("SELECT * FROM battle_players WHERE battle_id=$1::uuid AND user_id=$2 FOR UPDATE",battle_id,uid)
            if not p: raise HTTPException(403,"Forbidden")
            approved=await conn.fetchrow("SELECT 1 FROM payments WHERE id=$1 AND status='approved' AND user_id=$2",p["payment_id"],uid)
            if not approved: return json_error("Battle payment approved emas",403)
            battle=await conn.fetchrow("SELECT * FROM battles WHERE id=$1::uuid FOR UPDATE",battle_id)
            if not battle or battle["status"] not in ("ready","finished"):
                return json_error("Battle hali tayyor emas",409)
            if p["finished_at"] is not None:
                return {"ok":True,"already_finished":True,"score":p["score"]}
            score,correct,_=calculate_iq(answers)
            await conn.execute("UPDATE battle_players SET score=$1,correct_count=$2,finished_at=NOW() WHERE battle_id=$3::uuid AND user_id=$4",score,correct,battle_id,uid)
            players=await conn.fetch("SELECT user_id,score,finished_at FROM battle_players WHERE battle_id=$1::uuid FOR UPDATE",battle_id)
            if len(players)==2 and all(x["finished_at"] is not None for x in players):
                await conn.execute("UPDATE battles SET status='finished',finalized_at=NOW() WHERE id=$1::uuid AND status<>'finished'",battle_id)
                status="finished"
            else:
                status="waiting_opponent"
    return {"ok":True,"score":score,"status":status}

@app.get("/api/battle/{battle_id}/result")
async def battle_result(battle_id:str,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    b=await db_fetchrow("SELECT * FROM battles WHERE id=$1::uuid",battle_id)
    p=await db_fetchrow("SELECT * FROM battle_players WHERE battle_id=$1::uuid AND user_id=$2",battle_id,uid)
    if not b or not p: raise HTTPException(403,"Forbidden")
    players=await db_fetch("SELECT user_id,score,finished_at FROM battle_players WHERE battle_id=$1::uuid",battle_id)
    if len(players)!=2 or not all(x["finished_at"] for x in players):
        return {"ok":True,"ready":False}
    a,bp=players
    if a["score"]==bp["score"]: outcome="draw"
    else: outcome="win" if p["score"]==max(a["score"],bp["score"]) else "loss"
    return {"ok":True,"ready":True,"outcome":outcome,"my_score":p["score"],"opponent_score":next(x["score"] for x in players if x["user_id"]!=uid)}

@app.get("/api/referral")
async def referral(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    row=await db_fetchrow("SELECT COUNT(*) c FROM referrals WHERE referrer_id=$1",uid)
    link=f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    return {"ok":True,"link":link,"count":int(row["c"])}

@app.post("/api/referral/claim")
async def referral_claim(request:Request):
    user=await authenticated_user(request); data=await request.json(); uid=int(user["id"]); ref=int(data.get("referrer_id",0))
    if ref==uid: return json_error("O‘zingizni taklif qila olmaysiz")
    if not ref or not await db_fetchrow("SELECT 1 FROM users WHERE user_id=$1",ref): return json_error("Referrer topilmadi")
    try:
        await db_execute("INSERT INTO referrals(referrer_id,referred_id) VALUES($1,$2) ON CONFLICT(referred_id) DO NOTHING",ref,uid)
    except Exception: logger.exception("Referral claim failed")
    return {"ok":True}

@asynccontextmanager
async def lifespan(application: FastAPI):
    global db_pool
    logger.info("Starting application")
    db_pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=10,command_timeout=30)
    await migrate()
    webhook_url=PUBLIC_BASE_URL.rstrip("/")+"/telegram/webhook"
    try:
        await bot.set_webhook(url=webhook_url,secret_token=WEBHOOK_SECRET,drop_pending_updates=True)
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🧠 IQ TEST BOT", web_app=WebAppInfo(url=WEBAPP_URL + "/app")))
        info=await bot.get_webhook_info()
        logger.info("Telegram webhook configured: %s pending=%s",info.url,info.pending_update_count)
    except Exception:
        logger.exception("Webhook configuration failed")
        raise
    try:
        yield
    finally:
        logger.info("Shutting down")
        try:
            if PUBLIC_BASE_URL:
                await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("Webhook shutdown failed")
        try:
            await bot.session.close()
        except Exception:
            logger.exception("Bot session close failed")
        try:
            if db_pool:
                await db_pool.close()
        except Exception:
            logger.exception("Database pool close failed")

app.router.lifespan_context=lifespan

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=PORT,log_level="info")
