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
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    )""")
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
    ]
    for q in migrations:
        try:
            await db_execute(q)
        except Exception:
            logger.exception("Migration failed")
            raise

    await db_execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_battle_one_opponent
        ON battle_players(battle_id) WHERE role='opponent'
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
        if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q."); return
    parts=message.text.split()
    if len(parts)!=4:
        await message.answer("Format: /setlive fake 95114 342"); return
    mode=parts[1]
    try: base=int(parts[2]); online=int(parts[3])
    except: await message.answer("Sonlar noto‘g‘ri."); return
    await db_execute("INSERT INTO app_settings(key,value) VALUES('live_mode',$1) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",mode)
    await db_execute("INSERT INTO app_settings(key,value) VALUES('live_fake_base',$1) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",str(base))
    await db_execute("INSERT INTO app_settings(key,value) VALUES('live_fake_online',$1) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",str(online))
    await message.answer("✅ Live sozlamalari saqlandi.")

def parse_init_data(init_data: str):
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram initData")

    pairs={}
    hash_value=None
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        key,value=part.split("=",1)
        if key=="hash":
            hash_value=value
        else:
            pairs.setdefault(key,value)

    if not hash_value:
        raise HTTPException(status_code=401, detail="Missing Telegram hash")

    data_check="\n".join(
        f"{k}={pairs[k]}" for k in sorted(pairs)
    )

    secret_key=hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256
    ).digest()

    calculated=hmac.new(
        secret_key,
        data_check.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated,hash_value):
        raise HTTPException(status_code=401, detail="Invalid Telegram initData")

    try:
        auth_date=int(pairs.get("auth_date","0"))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth_date")

    if auth_date <= 0 or datetime.now(timezone.utc).timestamp()-auth_date > 86400:
        raise HTTPException(status_code=401, detail="Expired Telegram initData")

    user_raw=pairs.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="Telegram user missing")

    try:
        user=json.loads(unquote(user_raw))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Telegram user")

    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Telegram user id missing")

    return user

async def require_webapp_user(request: Request):
    init_data=request.headers.get("X-Telegram-Init-Data","").strip()
    if not init_data:
        init_data=request.headers.get("Telegram-WebApp-Init-Data","").strip()
    user=parse_init_data(init_data)
    await db_execute("""
        INSERT INTO users(user_id,username,first_name,last_name,last_seen,updated_at)
        VALUES($1,$2,$3,$4,NOW(),NOW())
        ON CONFLICT(user_id) DO UPDATE SET
          username=EXCLUDED.username,
          first_name=EXCLUDED.first_name,
          last_name=EXCLUDED.last_name,
          last_seen=NOW(),
          updated_at=NOW()
    """,
        int(user["id"]),
        user.get("username"),
        user.get("first_name"),
        user.get("last_name")
    )
    return user

def level_for_iq(score:int):
    if score < 85:
        return "Quyi"
    if score < 100:
        return "O‘rtacha"
    if score < 115:
        return "Yaxshi"
    if score < 130:
        return "Yuqori"
    return "Juda yuqori"

def level_for_percent(score:int):
    if score < 40:
        return "Boshlang‘ich"
    if score < 60:
        return "O‘rtacha"
    if score < 80:
        return "Yaxshi"
    return "Yuqori"

def iq_score_from_weighted(correct_weight:int, max_weight:int):
    if max_weight <= 0:
        return 70
    ratio=max(0,min(1,correct_weight/max_weight))
    return int(round(70+ratio*60))

def normalize_answer_map(value):
    if isinstance(value,dict):
        return {str(k):int(v) for k,v in value.items() if str(v).isdigit()}
    return {}

def test_questions(test_type:str):
    if test_type=="IQ":
        return IQ_QUESTIONS
    if test_type=="EQ":
        return [
            {"id":i+1,"question":q,"options":opts,"correct":correct}
            for i,(q,opts,correct) in enumerate(EQ_QUESTIONS)
        ]
    if test_type=="PQ":
        return [
            {"id":i+1,"question":q,"options":opts,"correct":correct}
            for i,(q,opts,correct) in enumerate(PQ_QUESTIONS)
        ]
    raise ValueError("Unknown test type")

def public_questions(test_type:str):
    result=[]
    for q in test_questions(test_type):
        if test_type=="IQ":
            result.append({
                "id":q["id"],
                "weight":q["weight"],
                "matrix":q["matrix"],
                "options":q["options"],
            })
        else:
            result.append({
                "id":q["id"],
                "question":q["question"],
                "options":q["options"],
            })
    return result

def max_weight(test_type:str):
    if test_type=="IQ":
        return sum(q["weight"] for q in IQ_QUESTIONS)
    return len(test_questions(test_type))

def calculate_result(test_type:str,answers:dict):
    questions=test_questions(test_type)
    correct=0
    weighted=0

    for q in questions:
        raw=answers.get(str(q["id"]))
        try:
            answer=int(raw)
        except (TypeError,ValueError):
            continue

        if answer==q["correct"]:
            correct += 1
            weighted += q.get("weight",1)

    if test_type=="IQ":
        score=iq_score_from_weighted(weighted,max_weight("IQ"))
        level=level_for_iq(score)
    else:
        score=int(round(correct/max(1,len(questions))*100))
        level=level_for_percent(score)

    return score,correct,level

async def get_user_language(user_id:int):
    row=await db_fetchrow("SELECT language FROM users WHERE user_id=$1",user_id)
    return row["language"] if row and row["language"] in TRANSLATIONS else "uz"

async def user_has_previous_result(user_id:int,test_type:str):
    return bool(await db_fetchrow(
        "SELECT 1 FROM results WHERE user_id=$1 AND test_type=$2 LIMIT 1",
        user_id,test_type
    ))

async def start_test_for_user(user_id:int,test_type:str):
    if test_type not in {"IQ","EQ","PQ"}:
        raise HTTPException(status_code=400,detail="Invalid test type")

    retry=await user_has_previous_result(user_id,test_type)

    price_key=f"{test_type.lower()}_retry_price" if retry else f"{test_type.lower()}_price"
    price=await setting_int(price_key,0)

    session_id=uuid4()
    expires=datetime.now(timezone.utc)+timedelta(minutes=30)

    await db_execute("""
        INSERT INTO test_sessions(
            session_id,user_id,test_type,status,answers,questions,
            started_at,expires_at,price,is_retry
        )
        VALUES($1,$2,$3,'active','{}'::jsonb,$4::jsonb,NOW(),$5,$6,$7)
    """,
        session_id,
        user_id,
        test_type,
        json.dumps(public_questions(test_type),ensure_ascii=False),
        expires,
        price,
        retry
    )

    return {
        "session_id":str(session_id),
        "test_type":test_type,
        "price":price,
        "is_retry":retry,
        "expires_at":expires.isoformat(),
        "questions":public_questions(test_type)
    }

async def create_payment_for_attempt(
    user_id:int,
    payment_type:str,
    amount:int,
    attempt_id=None,
    battle_id=None
):
    card=await db_fetchrow("""
        SELECT id,card_number,holder,bank
        FROM payment_cards
        WHERE active=TRUE
        ORDER BY id ASC
        LIMIT 1
    """)

    payment=await db_fetchrow("""
        INSERT INTO payments(
            user_id,attempt_id,battle_id,payment_type,amount,card_id,status
        )
        VALUES($1,$2,$3,$4,$5,$6,'pending')
        RETURNING id,created_at,status
    """,
        user_id,
        attempt_id,
        battle_id,
        payment_type,
        amount,
        card["id"] if card else None
    )

    return payment,card

async def notify_admin_payment(payment_id:int):
    if not ADMIN_USER_ID:
        return

    row=await db_fetchrow("""
        SELECT
            p.id,p.user_id,p.payment_type,p.amount,p.status,
            p.receipt_file_id,p.created_at,
            u.username,u.first_name,u.last_name
        FROM payments p
        JOIN users u ON u.user_id=p.user_id
        WHERE p.id=$1
    """,payment_id)

    if not row:
        return

    text=(
        f"💳 <b>Yangi to‘lov</b>\n\n"
        f"ID: <code>{row['id']}</code>\n"
        f"User: <code>{row['user_id']}</code>\n"
        f"Username: @{row['username'] or '—'}\n"
        f"Ism: {row['first_name'] or ''} {row['last_name'] or ''}\n"
        f"Turi: <b>{row['payment_type']}</b>\n"
        f"Summa: <b>{row['amount']:,} so‘m</b>\n"
        f"Status: {row['status']}"
    ).replace(",", " ")

    kb=InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash",callback_data=f"payapprove:{payment_id}"),
            InlineKeyboardButton(text="❌ Rad etish",callback_data=f"payreject:{payment_id}")
        ]
    ])

    if row["receipt_file_id"]:
        try:
            await bot.send_document(
                ADMIN_USER_ID,
                row["receipt_file_id"],
                caption=text,
                reply_markup=kb
            )
            return
        except Exception:
            logger.exception("Failed sending payment receipt")

    await bot.send_message(
        ADMIN_USER_ID,
        text,
        reply_markup=kb
    )

async def finalize_test(session_id,answers):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            session=await conn.fetchrow("""
                SELECT *
                FROM test_sessions
                WHERE session_id=$1
                FOR UPDATE
            """,session_id)

            if not session:
                raise HTTPException(status_code=404,detail="Session not found")

            if session["status"]=="completed":
                attempt=await conn.fetchrow("""
                    SELECT *
                    FROM test_attempts
                    WHERE session_id=$1
                """,session_id)
                return attempt

            if session["status"]!="active":
                raise HTTPException(status_code=409,detail="Session is not active")

            if session["expires_at"] < datetime.now(timezone.utc):
                await conn.execute(
                    "UPDATE test_sessions SET status='expired' WHERE session_id=$1",
                    session_id
                )
                raise HTTPException(status_code=410,detail="Session expired")

            expected_questions=session["questions"] or []
            expected_ids={str(q["id"]) for q in expected_questions}
            clean_answers={}
            for k,v in answers.items():
                if str(k) in expected_ids:
                    try:
                        iv=int(v)
                    except (TypeError,ValueError):
                        continue
                    if 0 <= iv <= 3:
                        clean_answers[str(k)]=iv

            test_type=session["test_type"]
            score,correct,level=calculate_result(test_type,clean_answers)

            attempt=await conn.fetchrow("""
                INSERT INTO test_attempts(
                    user_id,test_type,session_id,score,correct_count,
                    duration,payment_status,result_visible,level,answers
                )
                VALUES(
                    $1,$2,$3,$4,$5,
                    EXTRACT(EPOCH FROM (NOW()-$6))::INTEGER,
                    CASE WHEN $7=0 THEN 'not_required' ELSE 'pending' END,
                    CASE WHEN $7=0 THEN TRUE ELSE FALSE END,
                    $8,$9::jsonb
                )
                RETURNING *
            """,
                session["user_id"],
                test_type,
                session_id,
                score,
                correct,
                session["started_at"],
                session["price"],
                level,
                json.dumps(clean_answers)
            )

            await conn.execute("""
                UPDATE test_sessions
                SET status='completed',
                    answers=$2::jsonb,
                    score=$3,
                    correct_count=$4,
                    completed_at=NOW()
                WHERE session_id=$1
            """,
                session_id,
                json.dumps(clean_answers),
                score,
                correct
            )

            if session["price"] == 0:
                result=await conn.fetchrow("""
                    INSERT INTO results(
                        user_id,attempt_id,test_type,score,level
                    )
                    VALUES($1,$2,$3,$4,$5)
                    ON CONFLICT(attempt_id) DO UPDATE SET score=EXCLUDED.score
                    RETURNING *
                """,
                    session["user_id"],
                    attempt["id"],
                    test_type,
                    score,
                    level
                )
                await conn.execute("""
                    UPDATE test_attempts
                    SET result_visible=TRUE
                    WHERE id=$1
                """,attempt["id"])
            else:
                result=None

            return attempt

def generate_verification_code():
    alphabet=string.ascii_uppercase+string.digits
    while True:
        code="IQ-"+''.join(secrets.choice(alphabet) for _ in range(6))
        return code

def generate_certificate_id():
    return "CERT-"+uuid4().hex[:10].upper()

def safe_font(size:int,bold=False):
    candidates=[]
    if bold:
        candidates=[
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidates=[
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path,size)
            except Exception:
                pass

    return ImageFont.load_default()

def create_certificate_png(full_name,score,level,verification_code,created_at):
    width,height=1600,1100
    img=Image.new("RGB",(width,height),(10,13,22))
    draw=ImageDraw.Draw(img)

    gold=(218,180,75)
    white=(245,247,250)
    muted=(165,172,190)
    panel=(18,23,36)

    draw.rounded_rectangle(
        (35,35,width-35,height-35),
        radius=32,
        fill=panel,
        outline=gold,
        width=8
    )
    draw.rounded_rectangle(
        (65,65,width-65,height-65),
        radius=24,
        outline=(90,100,120),
        width=2
    )

    title_font=safe_font(72,True)
    subtitle_font=safe_font(32,False)
    name_font=safe_font(60,True)
    score_font=safe_font(100,True)
    normal_font=safe_font(34,False)
    code_font=safe_font(40,True)

    title="IQ TEST BOT"
    bbox=draw.textbbox((0,0),title,font=title_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,130),
        title,
        font=title_font,
        fill=gold
    )

    subtitle="SERTIFIKAT"
    bbox=draw.textbbox((0,0),subtitle,font=subtitle_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,230),
        subtitle,
        font=subtitle_font,
        fill=white
    )

    line="AQLLIY SALOHIYAT TO‘G‘RISIDA"
    bbox=draw.textbbox((0,0),line,font=normal_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,285),
        line,
        font=normal_font,
        fill=muted
    )

    # Simple brain/seal emblem.
    cx,cy=800,425
    draw.ellipse((cx-90,cy-90,cx+90,cy+90),outline=gold,width=6)
    draw.arc((cx-55,cy-55,cx+10,cy+55),90,270,fill=gold,width=5)
    draw.arc((cx-10,cy-55,cx+55,cy+55),270,90,fill=gold,width=5)
    draw.line((cx,cy-55,cx,cy+55),fill=gold,width=4)

    bbox=draw.textbbox((0,0),full_name,font=name_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,545),
        full_name,
        font=name_font,
        fill=white
    )

    score_text=f"IQ  {score}"
    bbox=draw.textbbox((0,0),score_text,font=score_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,650),
        score_text,
        font=score_font,
        fill=gold
    )

    level_text=f"Daraja: {level}"
    bbox=draw.textbbox((0,0),level_text,font=normal_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,790),
        level_text,
        font=normal_font,
        fill=white
    )

    date_text=created_at.strftime("%d.%m.%Y")
    bbox=draw.textbbox((0,0),date_text,font=normal_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,850),
        date_text,
        font=normal_font,
        fill=muted
    )

    code_text=verification_code
    bbox=draw.textbbox((0,0),code_text,font=code_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,930),
        code_text,
        font=code_font,
        fill=white
    )

    brand="IQ TEST BOT"
    bbox=draw.textbbox((0,0),brand,font=subtitle_font)
    draw.text(
        ((width-(bbox[2]-bbox[0]))/2,1000),
        brand,
        font=subtitle_font,
        fill=gold
    )

    output=io.BytesIO()
    img.save(output,format="PNG",optimize=True)
    output.seek(0)
    return output.getvalue()

async def ensure_certificate(user_id:int,result_id:int):
    existing=await db_fetchrow("""
        SELECT *
        FROM certificates
        WHERE result_id=$1
    """,result_id)

    if existing:
        return existing

    result=await db_fetchrow("""
        SELECT
            r.id,r.score,r.level,r.created_at,
            u.full_name,u.first_name,u.last_name
        FROM results r
        JOIN users u ON u.user_id=r.user_id
        WHERE r.id=$1 AND r.user_id=$2
    """,result_id,user_id)

    if not result:
        return None

    full_name=(
        result["full_name"]
        or " ".join(
            x for x in [result["first_name"],result["last_name"]]
            if x
        )
        or "Foydalanuvchi"
    )

    verification_code=generate_verification_code()
    certificate_id=generate_certificate_id()

    row=await db_fetchrow("""
        INSERT INTO certificates(
            user_id,result_id,certificate_id,verification_code,
            type,full_name,score,level
        )
        VALUES($1,$2,$3,$4,'IQ',$5,$6,$7)
        ON CONFLICT(result_id) DO UPDATE SET
            full_name=EXCLUDED.full_name,
            score=EXCLUDED.score,
            level=EXCLUDED.level
        RETURNING *
    """,
        user_id,
        result_id,
        certificate_id,
        verification_code,
        full_name,
        result["score"],
        result["level"]
    )

    return row

def parse_full_name(value):
    value=" ".join((value or "").strip().split())
    if len(value)<2:
        raise HTTPException(status_code=400,detail="Full name is required")
    return value[:150]

@asynccontextmanager
async def lifespan(app:FastAPI):
    global db_pool

    db_pool=await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30
    )

    await migrate()

    webhook_url=PUBLIC_BASE_URL.rstrip("/")+"/telegram/webhook"

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )

    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🧠 IQ TEST",
                web_app=WebAppInfo(url=WEBAPP_URL+"/app")
            )
        )
    except Exception:
        logger.exception("Failed to configure Telegram menu button")

    info=await bot.get_webhook_info()
    logger.info(
        "Telegram webhook configured: %s pending=%s",
        info.url,
        info.pending_update_count
    )

    logger.info("IQ TEST BOT ready")

    yield

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        logger.exception("Failed to delete webhook")

    try:
        await bot.session.close()
    except Exception:
        logger.exception("Failed to close bot session")

    if db_pool:
        await db_pool.close()
        db_pool=None

app=FastAPI(
    title="IQ TEST BOT",
    lifespan=lifespan
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR,"webapp")),
    name="static"
)

@app.get("/health")
async def health():
    db_ok=False
    if db_pool:
        try:
            await db_fetchrow("SELECT 1")
            db_ok=True
        except Exception:
            db_ok=False

    return {
        "ok":True,
        "database":db_ok,
        "service":"IQ TEST BOT"
    }

@app.get("/app",response_class=HTMLResponse)
async def webapp_page():
    path=os.path.join(BASE_DIR,"webapp","index.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404,detail="Mini App not found")

    with open(path,"r",encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/telegram/webhook")
async def telegram_webhook(request:Request):
    if WEBHOOK_SECRET:
        provided=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
        if not hmac.compare_digest(provided,WEBHOOK_SECRET):
            raise HTTPException(status_code=401,detail="Invalid webhook secret")

    try:
        payload=await request.json()
        update=types.Update.model_validate(payload)
        await dp.feed_update(bot,update)
        return {"ok":True}
    except Exception:
        logger.exception("Webhook update failed")
        raise HTTPException(status_code=500,detail="Webhook processing failed")

@app.get("/api/bootstrap")
async def api_bootstrap(request:Request):
    user=await require_webapp_user(request)
    user_id=int(user["id"])

    row=await db_fetchrow("""
        SELECT
            u.user_id,u.username,u.first_name,u.last_name,
            u.language,u.full_name,u.gender,u.age,u.country,
            (
                SELECT COUNT(*)
                FROM results r
                WHERE r.user_id=u.user_id AND r.test_type='IQ'
            ) AS iq_count
        FROM users u
        WHERE u.user_id=$1
    """,user_id)

    live_base=await setting_int("live_fake_base",95114)
    live_online=await setting_int("live_fake_online",342)

    return {
        "ok":True,
        "user":{
            "id":row["user_id"],
            "username":row["username"],
            "first_name":row["first_name"],
            "last_name":row["last_name"],
            "language":row["language"],
            "full_name":row["full_name"],
            "gender":row["gender"],
            "age":row["age"],
            "country":row["country"],
            "iq_count":row["iq_count"],
        },
        "prices":{
            "iq":await setting_int("iq_price"),
            "iq_retry":await setting_int("iq_retry_price"),
            "eq":await setting_int("eq_price"),
            "eq_retry":await setting_int("eq_retry_price"),
            "pq":await setting_int("pq_price"),
            "pq_retry":await setting_int("pq_retry_price"),
            "battle":await setting_int("battle_price"),
        },
        "live":{
            "base":live_base,
            "online":live_online
        }
    }

@app.post("/api/profile/save")
async def api_profile_save(request:Request):
    user=await require_webapp_user(request)
    user_id=int(user["id"])
    body=await request.json()

    full_name=parse_full_name(body.get("full_name"))
    gender=str(body.get("gender") or "")[:30]
    country=str(body.get("country") or "")[:80]

    try:
        age=int(body.get("age"))
    except (TypeError,ValueError):
        raise HTTPException(status_code=400,detail="Invalid age")

    if age<5 or age>100:
        raise HTTPException(status_code=400,detail="Invalid age")

    await db_execute("""
        UPDATE users
        SET full_name=$1,gender=$2,age=$3,country=$4,updated_at=NOW()
        WHERE user_id=$5
    """,
        full_name,gender,age,country,user_id
    )

    return {
        "ok":True,
        "profile":{
            "full_name":full_name,
            "gender":gender,
            "age":age,
            "country":country
        }
    }

@app.post("/api/test/start")
async def api_test_start(request:Request):
    user=await require_webapp_user(request)
    body=await request.json()
    test_type=str(body.get("test_type","IQ")).upper()

    return {
        "ok":True,
        "test":await start_test_for_user(int(user["id"]),test_type)
    }

@app.post("/api/test/{session_id}/submit")
async def api_test_submit(session_id:str,request:Request):
    user=await require_webapp_user(request)

    try:
        sid=__import__("uuid").UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400,detail="Invalid session id")

    body=await request.json()
    answers=normalize_answer_map(body.get("answers",{}))

    session=await db_fetchrow(
        "SELECT user_id FROM test_sessions WHERE session_id=$1",
        sid
    )

    if not session:
        raise HTTPException(status_code=404,detail="Session not found")

    if int(session["user_id"]) != int(user["id"]):
        raise HTTPException(status_code=403,detail="Forbidden")

    attempt=await finalize_test(sid,answers)

    payment=None
    card=None

    if attempt["payment_status"]=="pending":
        payment,card=await create_payment_for_attempt(
            int(user["id"]),
            f"{attempt['test_type'].lower()}_retry",
            await db_fetchrow(
                "SELECT price FROM test_sessions WHERE session_id=$1",
                sid
            )["price"],
            attempt_id=attempt["id"]
        )
        await notify_admin_payment(payment["id"])

    result=await db_fetchrow("""
        SELECT *
        FROM results
        WHERE attempt_id=$1
    """,attempt["id"])

    return {
        "ok":True,
        "attempt":{
            "id":attempt["id"],
            "test_type":attempt["test_type"],
            "score":attempt["score"],
            "correct_count":attempt["correct_count"],
            "level":attempt["level"],
            "result_visible":attempt["result_visible"]
        },
        "payment":{
            "id":payment["id"] if payment else None,
            "status":payment["status"] if payment else None,
            "amount":payment["amount"] if payment else 0,
            "card":{
                "id":card["id"],
                "card_number":card["card_number"],
                "holder":card["holder"],
                "bank":card["bank"]
            } if card else None
        },
        "result":{
            "id":result["id"],
            "score":result["score"],
            "level":result["level"]
        } if result else None
    }

@app.get("/api/test/{session_id}/resume")
async def api_test_resume(session_id:str,request:Request):
    user=await require_webapp_user(request)

    try:
        sid=__import__("uuid").UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400,detail="Invalid session id")

    row=await db_fetchrow("""
        SELECT *
        FROM test_sessions
        WHERE session_id=$1 AND user_id=$2
    """,sid,int(user["id"]))

    if not row:
        raise HTTPException(status_code=404,detail="Session not found")

    return {
        "ok":True,
        "session":{
            "session_id":str(row["session_id"]),
            "test_type":row["test_type"],
            "status":row["status"],
            "answers":row["answers"] or {},
            "questions":row["questions"] or [],
            "price":row["price"],
            "expires_at":row["expires_at"].isoformat()
        }
    }

@app.get("/api/result/{attempt_id}")
async def api_result(attempt_id:int,request:Request):
    user=await require_webapp_user(request)

    row=await db_fetchrow("""
        SELECT *
        FROM test_attempts
        WHERE id=$1 AND user_id=$2
    """,attempt_id,int(user["id"]))

    if not row:
        raise HTTPException(status_code=404,detail="Result not found")

    if not row["result_visible"]:
        payment=await db_fetchrow("""
            SELECT id,amount,status,receipt_file_id
            FROM payments
            WHERE attempt_id=$1
            ORDER BY id DESC LIMIT 1
        """,attempt_id)

        return {
            "ok":True,
            "locked":True,
            "attempt":{
                "id":row["id"],
                "test_type":row["test_type"],
                "score":row["score"],
                "correct_count":row["correct_count"],
                "level":row["level"]
            },
            "payment":{
                "id":payment["id"] if payment else None,
                "amount":payment["amount"] if payment else 0,
                "status":payment["status"] if payment else None,
                "has_receipt":bool(payment and payment["receipt_file_id"])
            }
        }

    result=await db_fetchrow(
        "SELECT * FROM results WHERE attempt_id=$1",
        attempt_id
    )

    return {
        "ok":True,
        "locked":False,
        "attempt":{
            "id":row["id"],
            "test_type":row["test_type"],
            "score":row["score"],
            "correct_count":row["correct_count"],
            "level":row["level"],
            "duration":row["duration"]
        },
        "result":{
            "id":result["id"],
            "score":result["score"],
            "level":result["level"],
            "created_at":result["created_at"].isoformat()
        } if result else None
    }

@app.post("/api/payment/create")
async def api_payment_create(request:Request):
    user=await require_webapp_user(request)
    body=await request.json()

    payment_type=str(body.get("payment_type","iq_retry"))
    if payment_type not in {"iq","iq_retry","eq","eq_retry","pq","pq_retry","battle"}:
        raise HTTPException(status_code=400,detail="Invalid payment type")

    amount=await setting_int(payment_type+"_price",0)

    payment,card=await create_payment_for_attempt(
        int(user["id"]),
        payment_type,
        amount
    )

    await notify_admin_payment(payment["id"])

    return {
        "ok":True,
        "payment":{
            "id":payment["id"],
            "amount":payment["amount"],
            "status":payment["status"]
        },
        "card":{
            "id":card["id"],
            "card_number":card["card_number"],
            "holder":card["holder"],
            "bank":card["bank"]
        } if card else None
    }

@app.post("/api/payment/{payment_id}/receipt")
async def api_payment_receipt(
    payment_id:int,
    request:Request,
    file:UploadFile=File(...)
):
    user=await require_webapp_user(request)

    payment=await db_fetchrow("""
        SELECT id,user_id,status,amount
        FROM payments
        WHERE id=$1
    """,payment_id)

    if not payment:
        raise HTTPException(status_code=404,detail="Payment not found")

    if int(payment["user_id"]) != int(user["id"]):
        raise HTTPException(status_code=403,detail="Forbidden")

    if payment["status"] not in {"pending","rejected"}:
        raise HTTPException(status_code=409,detail="Payment cannot accept receipt")

    content_type=(file.content_type or "").lower()
    if content_type not in {"image/jpeg","image/png","image/webp"}:
        raise HTTPException(status_code=400,detail="Receipt must be an image")

    data=await file.read()
    if not data or len(data)>10*1024*1024:
        raise HTTPException(status_code=400,detail="Invalid receipt size")

    telegram_file=None
    try:
        telegram_file=await bot.send_document(
            ADMIN_USER_ID,
            BufferedInputFile(data,filename=file.filename or "receipt.jpg"),
            caption=(
                f"🧾 <b>To‘lov cheki</b>\n\n"
                f"Payment: <code>{payment_id}</code>\n"
                f"User: <code>{user['id']}</code>\n"
                f"Summa: <b>{payment['amount']:,} so‘m</b>"
            ).replace(",", " ")
        )
    except Exception:
        logger.exception("Failed to send receipt to admin")

    file_id=None
    if telegram_file and getattr(telegram_file,"document",None):
        file_id=telegram_file.document.file_id

    await db_execute("""
        UPDATE payments
        SET receipt_file_id=COALESCE($2,receipt_file_id),
            status='pending',
            updated_at=NOW()
        WHERE id=$1
    """,payment_id,file_id)

    await notify_admin_payment(payment_id)

    return {
        "ok":True,
        "payment_id":payment_id,
        "status":"pending"
    }
    @app.get("/api/payment/mine")

async def api_payment_mine(request:Request):

    user=await require_webapp_user(request)

    rows=await db_fetch("""

        SELECT id,payment_type,amount,status,receipt_file_id,created_at

        FROM payments

        WHERE user_id=$1

        ORDER BY id DESC

        LIMIT 30

    """,int(user["id"]))

    return {

        "ok":True,

        "payments":[

            {

                "id":r["id"],

                "payment_type":r["payment_type"],

                "amount":r["amount"],

                "status":r["status"],

                "has_receipt":bool(r["receipt_file_id"]),

                "created_at":r["created_at"].isoformat()

            }

            for r in rows

        ]

    }

@app.get("/api/payment/{payment_id}/card")

async def api_payment_card(payment_id:int,request:Request):

    user=await require_webapp_user(request)

    payment=await db_fetchrow("""

        SELECT id,user_id,amount,status,card_id

        FROM payments

        WHERE id=$1

    """,payment_id)

    if not payment:

        raise HTTPException(status_code=404,detail="Payment not found")

    if int(payment["user_id"]) != int(user["id"]):

        raise HTTPException(status_code=403,detail="Forbidden")

    card=await db_fetchrow("""

        SELECT id,card_number,holder,bank

        FROM payment_cards

        WHERE id=$1 AND active=TRUE

    """,payment["card_id"])

    if not card:

        card=await db_fetchrow("""

            SELECT id,card_number,holder,bank

            FROM payment_cards

            WHERE active=TRUE

            ORDER BY id ASC

            LIMIT 1

        """)

    return {

        "ok":True,

        "card":{

            "id":card["id"],

            "card_number":card["card_number"],

            "holder":card["holder"],

            "bank":card["bank"]

        } if card else None

    }

@app.post("/api/admin/payment/{payment_id}/approve")

async def api_admin_payment_approve(payment_id:int,request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            payment=await conn.fetchrow("""

                SELECT *

                FROM payments

                WHERE id=$1

                FOR UPDATE

            """,payment_id)

            if not payment:

                raise HTTPException(status_code=404,detail="Payment not found")

            if payment["status"]=="approved":

                return {"ok":True,"status":"approved"}

            await conn.execute("""

                UPDATE payments

                SET status='approved',updated_at=NOW()

                WHERE id=$1

            """,payment_id)

            if payment["attempt_id"]:

                attempt=await conn.fetchrow("""

                    SELECT *

                    FROM test_attempts

                    WHERE id=$1

                    FOR UPDATE

                """,payment["attempt_id"])

                if attempt and not attempt["result_visible"]:

                    result=await conn.fetchrow("""

                        INSERT INTO results(

                            user_id,attempt_id,test_type,score,level

                        )

                        VALUES($1,$2,$3,$4,$5)

                        ON CONFLICT(attempt_id) DO UPDATE

                        SET score=EXCLUDED.score,

                            level=EXCLUDED.level

                        RETURNING *

                    """,

                        attempt["user_id"],

                        attempt["id"],

                        attempt["test_type"],

                        attempt["score"],

                        attempt["level"]

                    )

                    await conn.execute("""

                        UPDATE test_attempts

                        SET result_visible=TRUE,

                            payment_status='approved'

                        WHERE id=$1

                    """,attempt["id"])

                else:

                    result=None

            else:

                result=None

    return {

        "ok":True,

        "status":"approved",

        "result_id":result["id"] if result else None

    }

@app.post("/api/admin/payment/{payment_id}/reject")

async def api_admin_payment_reject(payment_id:int,request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    await db_execute("""

        UPDATE payments

        SET status='rejected',updated_at=NOW()

        WHERE id=$1

    """,payment_id)

    return {

        "ok":True,

        "status":"rejected"

    }

@app.get("/api/certificate/mine")

async def api_certificate_mine(request:Request):

    user=await require_webapp_user(request)

    result=await db_fetchrow("""

        SELECT *

        FROM results

        WHERE user_id=$1 AND test_type='IQ'

        ORDER BY created_at DESC

        LIMIT 1

    """,int(user["id"]))

    if not result:

        return {

            "ok":True,

            "certificate":None

        }

    cert=await ensure_certificate(

        int(user["id"]),

        int(result["id"])

    )

    if not cert:

        return {

            "ok":True,

            "certificate":None

        }

    return {

        "ok":True,

        "certificate":{

            "id":cert["id"],

            "certificate_id":cert["certificate_id"],

            "verification_code":cert["verification_code"],

            "type":cert["type"],

            "full_name":cert["full_name"],

            "score":cert["score"],

            "level":cert["level"],

            "created_at":cert["created_at"].isoformat(),

            "verify_url":f"{PUBLIC_BASE_URL}/api/certificate/{cert['verification_code']}"

        }

    }

@app.get("/api/certificate/{verification_code}")

async def api_certificate_verify(verification_code:str):

    cert=await db_fetchrow("""

        SELECT

            certificate_id,verification_code,type,

            full_name,score,level,created_at

        FROM certificates

        WHERE verification_code=$1

    """,verification_code.upper())

    if not cert:

        raise HTTPException(status_code=404,detail="Certificate not found")

    return {

        "ok":True,

        "certificate":{

            "certificate_id":cert["certificate_id"],

            "verification_code":cert["verification_code"],

            "type":cert["type"],

            "full_name":cert["full_name"],

            "score":cert["score"],

            "level":cert["level"],

            "created_at":cert["created_at"].isoformat()

        }

    }

@app.get("/api/certificate/{certificate_id}/png")

async def api_certificate_png(certificate_id:str,request:Request):

    user=await require_webapp_user(request)

    cert=await db_fetchrow("""

        SELECT *

        FROM certificates

        WHERE certificate_id=$1 AND user_id=$2

    """,certificate_id,int(user["id"]))

    if not cert:

        raise HTTPException(status_code=404,detail="Certificate not found")

    created_at=cert["created_at"]

    data=create_certificate_png(

        cert["full_name"],

        cert["score"],

        cert["level"] or "",

        cert["verification_code"],

        created_at

    )

    return Response(

        content=data,

        media_type="image/png",

        headers={

            "Content-Disposition":

                f'inline; filename="{cert["certificate_id"]}.png"'

        }

    )

@app.get("/api/ranking")

async def api_ranking(request:Request):

    user=await require_webapp_user(request)

    rows=await db_fetch("""

        SELECT

            r.user_id,

            COALESCE(u.full_name,

                NULLIF(TRIM(CONCAT_WS(' ',u.first_name,u.last_name)),''),

                COALESCE(u.username,'Foydalanuvchi')

            ) AS name,

            r.score,

            r.level,

            r.created_at

        FROM results r

        JOIN users u ON u.user_id=r.user_id

        WHERE r.test_type='IQ'

        ORDER BY r.score DESC,r.created_at ASC

        LIMIT 100

    """)

    ranking=[]

    for index,row in enumerate(rows,1):

        ranking.append({

            "rank":index,

            "user_id":row["user_id"],

            "name":row["name"],

            "score":row["score"],

            "level":row["level"],

            "created_at":row["created_at"].isoformat()

        })

    me=next(

        (x for x in ranking if int(x["user_id"])==int(user["id"])),

        None

    )

    return {

        "ok":True,

        "ranking":ranking,

        "me":me

    }

@app.get("/api/stats/live")

async def api_stats_live(request:Request):

    await require_webapp_user(request)

    mode=await setting("live_mode","fake")

    if mode=="fake":

        base=await setting_int("live_fake_base",95114)

        online=await setting_int("live_fake_online",342)

        delta=await setting_int("live_fake_delta",8)

        now=int(datetime.now(timezone.utc).timestamp())

        cycle=(now//5)%max(1,delta*2+1)-delta

        return {

            "ok":True,

            "mode":"fake",

            "total":max(0,base+cycle),

            "online":max(0,online+(cycle%5))

        }

    total=await db_fetchrow("""

        SELECT COUNT(*) AS c

        FROM users

    """)

    online=await db_fetchrow("""

        SELECT COUNT(*) AS c

        FROM users

        WHERE last_seen > NOW()-INTERVAL '5 minutes'

    """)

    return {

        "ok":True,

        "mode":"real",

        "total":int(total["c"]),

        "online":int(online["c"])

    }

def make_battle_code():

    alphabet=string.ascii_uppercase+string.digits

    while True:

        code="".join(secrets.choice(alphabet) for _ in range(4))

        return code

@app.post("/api/battle/create")

async def api_battle_create(request:Request):

    user=await require_webapp_user(request)

    user_id=int(user["id"])

    existing=await db_fetchrow("""

        SELECT b.id,b.code,b.status

        FROM battles b

        JOIN battle_players bp ON bp.battle_id=b.id

        WHERE bp.user_id=$1

          AND b.status IN ('waiting','ready','active')

        ORDER BY b.created_at DESC

        LIMIT 1

    """,user_id)

    if existing:

        return {

            "ok":True,

            "battle":{

                "id":str(existing["id"]),

                "code":existing["code"],

                "status":existing["status"]

            }

        }

    battle_id=uuid4()

    code=make_battle_code()

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            await conn.execute("""

                INSERT INTO battles(

                    id,code,status,created_by

                )

                VALUES($1,$2,'waiting',$3)

            """,battle_id,code,user_id)

            await conn.execute("""

                INSERT INTO battle_players(

                    battle_id,user_id,role

                )

                VALUES($1,$2,'creator')

            """,battle_id,user_id)

    return {

        "ok":True,

        "battle":{

            "id":str(battle_id),

            "code":code,

            "status":"waiting"

        }

    }

@app.post("/api/battle/join")

async def api_battle_join(request:Request):

    user=await require_webapp_user(request)

    user_id=int(user["id"])

    body=await request.json()

    code=str(body.get("code","")).strip().upper()

    if len(code)!=4:

        raise HTTPException(status_code=400,detail="Invalid battle code")

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            battle=await conn.fetchrow("""

                SELECT *

                FROM battles

                WHERE code=$1

                FOR UPDATE

            """,code)

            if not battle:

                raise HTTPException(status_code=404,detail="Battle not found")

            if battle["status"]!="waiting":

                raise HTTPException(status_code=409,detail="Battle is not waiting")

            if int(battle["created_by"])==user_id:

                raise HTTPException(status_code=400,detail="Cannot join your own battle")

            already=await conn.fetchrow("""

                SELECT *

                FROM battle_players

                WHERE battle_id=$1 AND user_id=$2

            """,battle["id"],user_id)

            if already:

                return {

                    "ok":True,

                    "battle":{

                        "id":str(battle["id"]),

                        "code":battle["code"],

                        "status":battle["status"]

                    }

                }

            await conn.execute("""

                INSERT INTO battle_players(

                    battle_id,user_id,role

                )

                VALUES($1,$2,'opponent')

            """,battle["id"],user_id)

            await conn.execute("""

                UPDATE battles

                SET status='ready',ready_at=NOW()

                WHERE id=$1

            """,battle["id"])

    return {

        "ok":True,

        "battle":{

            "id":str(battle["id"]),

            "code":battle["code"],

            "status":"ready"

        }

    }

@app.get("/api/battle/{battle_id}")

async def api_battle_get(battle_id:str,request:Request):

    user=await require_webapp_user(request)

    try:

        bid=__import__("uuid").UUID(battle_id)

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid battle id")

    battle=await db_fetchrow("""

        SELECT *

        FROM battles

        WHERE id=$1

    """,bid)

    if not battle:

        raise HTTPException(status_code=404,detail="Battle not found")

    player=await db_fetchrow("""

        SELECT *

        FROM battle_players

        WHERE battle_id=$1 AND user_id=$2

    """,bid,int(user["id"]))

    if not player:

        raise HTTPException(status_code=403,detail="Not a battle participant")

    opponent=await db_fetchrow("""

        SELECT

            bp.user_id,bp.role,bp.score,bp.finished_at,

            u.username,u.first_name,u.last_name

        FROM battle_players bp

        JOIN users u ON u.user_id=bp.user_id

        WHERE bp.battle_id=$1

          AND bp.user_id<>$2

        LIMIT 1

    """,bid,int(user["id"]))

    return {

        "ok":True,

        "battle":{

            "id":str(battle["id"]),

            "code":battle["code"],

            "status":battle["status"],

            "created_at":battle["created_at"].isoformat(),

            "ready_at":battle["ready_at"].isoformat() if battle["ready_at"] else None,

        },

        "me":{

            "role":player["role"],

            "score":player["score"],

            "finished":bool(player["finished_at"])

        },

        "opponent":{

            "username":opponent["username"],

            "first_name":opponent["first_name"],

            "last_name":opponent["last_name"],

            "finished":bool(opponent["finished_at"])

        } if opponent else None

    }

@app.post("/api/battle/{battle_id}/payment")

async def api_battle_payment(battle_id:str,request:Request):

    user=await require_webapp_user(request)

    try:

        bid=__import__("uuid").UUID(battle_id)

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid battle id")

    player=await db_fetchrow("""

        SELECT *

        FROM battle_players

        WHERE battle_id=$1 AND user_id=$2

    """,bid,int(user["id"]))

    if not player:

        raise HTTPException(status_code=403,detail="Not a battle participant")

    existing=await db_fetchrow("""

        SELECT *

        FROM payments

        WHERE battle_id=$1

          AND user_id=$2

          AND status IN ('pending','approved')

        ORDER BY id DESC

        LIMIT 1

    """,bid,int(user["id"]))

    if existing:

        card=await db_fetchrow("""

            SELECT id,card_number,holder,bank

            FROM payment_cards

            WHERE id=$1

        """,existing["card_id"])

        return {

            "ok":True,

            "payment":{

                "id":existing["id"],

                "amount":existing["amount"],

                "status":existing["status"]

            },

            "card":{

                "id":card["id"],

                "card_number":card["card_number"],

                "holder":card["holder"],

                "bank":card["bank"]

            } if card else None

        }

    amount=await setting_int("battle_price",7500)

    payment,card=await create_payment_for_attempt(

        int(user["id"]),

        "battle",

        amount,

        battle_id=bid

    )

    await db_execute("""

        UPDATE battle_players

        SET payment_id=$1

        WHERE battle_id=$2 AND user_id=$3

    """,payment["id"],bid,int(user["id"]))

    await notify_admin_payment(payment["id"])

    return {

        "ok":True,

        "payment":{

            "id":payment["id"],

            "amount":payment["amount"],

            "status":payment["status"]

        },

        "card":{

            "id":card["id"],

            "card_number":card["card_number"],

            "holder":card["holder"],

            "bank":card["bank"]

        } if card else None

    }

@app.post("/api/battle/{battle_id}/start")

async def api_battle_start(battle_id:str,request:Request):

    user=await require_webapp_user(request)

    try:

        bid=__import__("uuid").UUID(battle_id)

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid battle id")

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            battle=await conn.fetchrow("""

                SELECT *

                FROM battles

                WHERE id=$1

                FOR UPDATE

            """,bid)

            if not battle:

                raise HTTPException(status_code=404,detail="Battle not found")

            player=await conn.fetchrow("""

                SELECT *

                FROM battle_players

                WHERE battle_id=$1 AND user_id=$2

            """,bid,int(user["id"]))

            if not player:

                raise HTTPException(status_code=403,detail="Not a participant")

            players=await conn.fetch("""

                SELECT *

                FROM battle_players

                WHERE battle_id=$1

                ORDER BY role

            """,bid)

            if len(players)!=2:

                raise HTTPException(status_code=409,detail="Waiting for opponent")

            for p in players:

                if not p["payment_id"]:

                    raise HTTPException(status_code=402,detail="Payment required")

                payment=await conn.fetchrow("""

                    SELECT status

                    FROM payments

                    WHERE id=$1

                """,p["payment_id"])

                if not payment or payment["status"]!="approved":

                    raise HTTPException(status_code=402,detail="Both payments must be approved")

                if p["session_id"]:

                    continue

                session_id=uuid4()

                expires=datetime.now(timezone.utc)+timedelta(minutes=30)

                await conn.execute("""

                    INSERT INTO test_sessions(

                        session_id,user_id,test_type,status,answers,questions,

                        started_at,expires_at,price,is_retry

                    )

                    VALUES(

                        $1,$2,'IQ','active','{}'::jsonb,$3::jsonb,

                        NOW(),$4,0,FALSE

                    )

                """,

                    session_id,

                    p["user_id"],

                    json.dumps(public_questions("IQ"),ensure_ascii=False),

                    expires

                )

                await conn.execute("""

                    UPDATE battle_players

                    SET session_id=$1

                    WHERE battle_id=$2 AND user_id=$3

                """,

                    session_id,bid,p["user_id"]

                )

            await conn.execute("""

                UPDATE battles

                SET status='active'

                WHERE id=$1

            """,bid)

    me=await db_fetchrow("""

        SELECT session_id

        FROM battle_players

        WHERE battle_id=$1 AND user_id=$2

    """,bid,int(user["id"]))

    return {

        "ok":True,

        "battle_id":str(bid),

        "session_id":str(me["session_id"]),

        "questions":public_questions("IQ")

    }

@app.post("/api/battle/{battle_id}/submit")

async def api_battle_submit(battle_id:str,request:Request):

    user=await require_webapp_user(request)

    try:

        bid=__import__("uuid").UUID(battle_id)

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid battle id")

    body=await request.json()

    answers=normalize_answer_map(body.get("answers",{}))

    player=await db_fetchrow("""

        SELECT *

        FROM battle_players

        WHERE battle_id=$1 AND user_id=$2

    """,bid,int(user["id"]))

    if not player:

        raise HTTPException(status_code=403,detail="Not a participant")

    if not player["session_id"]:

        raise HTTPException(status_code=409,detail="Battle has not started")

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            bp=await conn.fetchrow("""

                SELECT *

                FROM battle_players

                WHERE battle_id=$1 AND user_id=$2

                FOR UPDATE

            """,bid,int(user["id"]))

            if bp["finished_at"]:

                return {

                    "ok":True,

                    "already_finished":True,

                    "score":bp["score"]

                }

            session=await conn.fetchrow("""

                SELECT *

                FROM test_sessions

                WHERE session_id=$1

                FOR UPDATE

            """,bp["session_id"])

            if not session:

                raise HTTPException(status_code=404,detail="Battle test session not found")

            score,correct,level=calculate_result("IQ",answers)

            await conn.execute("""

                UPDATE test_sessions

                SET status='completed',

                    answers=$2::jsonb,

                    score=$3,

                    correct_count=$4,

                    completed_at=NOW()

                WHERE session_id=$1

            """,

                bp["session_id"],

                json.dumps(answers),

                score,

                correct

            )

            await conn.execute("""

                UPDATE battle_players

                SET score=$1,

                    correct_count=$2,

                    finished_at=NOW()

                WHERE battle_id=$3 AND user_id=$4

            """,

                score,correct,bid,int(user["id"])

            )

            finished_count=await conn.fetchval("""

                SELECT COUNT(*)

                FROM battle_players

                WHERE battle_id=$1 AND finished_at IS NOT NULL

            """,bid)

            if finished_count==2:

                await conn.execute("""

                    UPDATE battles

                    SET status='finished',

                        finalized_at=NOW()

                    WHERE id=$1

                """,bid)

    return {

        "ok":True,

        "score":score,

        "correct_count":correct,

        "level":level,

        "waiting_for_opponent":finished_count<2

    }

@app.get("/api/battle/{battle_id}/result")

async def api_battle_result(battle_id:str,request:Request):

    user=await require_webapp_user(request)

    try:

        bid=__import__("uuid").UUID(battle_id)

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid battle id")

    me=await db_fetchrow("""

        SELECT *

        FROM battle_players

        WHERE battle_id=$1 AND user_id=$2

    """,bid,int(user["id"]))

    if not me:

        raise HTTPException(status_code=403,detail="Not a participant")

    opponent=await db_fetchrow("""

        SELECT *

        FROM battle_players

        WHERE battle_id=$1 AND user_id<>$2

        LIMIT 1

    """,bid,int(user["id"]))

    if not opponent:

        return {

            "ok":True,

            "status":"waiting",

            "result":None

        }

    if not me["finished_at"] or not opponent["finished_at"]:

        return {

            "ok":True,

            "status":"waiting",

            "result":None

        }

    if me["score"]>opponent["score"]:

        outcome="win"

    elif me["score"]<opponent["score"]:

        outcome="loss"

    else:

        outcome="draw"

    return {

        "ok":True,

        "status":"finished",

        "result":{

            "outcome":outcome,

            "my_score":me["score"],

            "opponent_score":opponent["score"],

            "my_correct":me["correct_count"],

            "opponent_correct":opponent["correct_count"]

        }

    }

@app.get("/api/referral")

async def api_referral(request:Request):

    user=await require_webapp_user(request)

    user_id=int(user["id"])

    count=await db_fetchval_safe("""

        SELECT COUNT(*)

        FROM referrals

        WHERE referrer_id=$1

    """,user_id)

    return {

        "ok":True,

        "referral_code":str(user_id),

        "link":f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}",

        "count":int(count or 0)

    }

async def db_fetchval_safe(query,*args):

    async with db_pool.acquire() as conn:

        return await conn.fetchval(query,*args)

@app.post("/api/referral/claim")

async def api_referral_claim(request:Request):

    user=await require_webapp_user(request)

    user_id=int(user["id"])

    body=await request.json()

    code=str(body.get("code","")).strip()

    if not code.startswith("ref_"):

        raise HTTPException(status_code=400,detail="Invalid referral code")

    try:

        referrer_id=int(code[4:])

    except ValueError:

        raise HTTPException(status_code=400,detail="Invalid referral code")

    if referrer_id==user_id:

        raise HTTPException(status_code=400,detail="Self referral is not allowed")

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            referrer=await conn.fetchrow(

                "SELECT user_id FROM users WHERE user_id=$1",

                referrer_id

            )

            if not referrer:

                raise HTTPException(status_code=404,detail="Referrer not found")

            existing=await conn.fetchrow("""

                SELECT *

                FROM referrals

                WHERE referred_id=$1

            """,user_id)

            if existing:

                return {

                    "ok":True,

                    "claimed":False,

                    "message":"Referral already claimed"

                }

            await conn.execute("""

                INSERT INTO referrals(referrer_id,referred_id)

                VALUES($1,$2)

            """,referrer_id,user_id)

    return {

        "ok":True,

        "claimed":True

    }

@dp.message(CommandStart())

async def start_handler(message:types.Message):

    await upsert_user(message.from_user)

    args=(message.text or "").split(maxsplit=1)

    start_param=args[1].strip() if len(args)>1 else ""

    if start_param.startswith("ref_"):

        try:

            referrer_id=int(start_param[4:])

            if referrer_id!=message.from_user.id:

                async with db_pool.acquire() as conn:

                    await conn.execute("""

                        INSERT INTO referrals(referrer_id,referred_id)

                        SELECT $1,$2

                        WHERE EXISTS(

                            SELECT 1 FROM users WHERE user_id=$1

                        )

                        ON CONFLICT(referred_id) DO NOTHING

                    """,referrer_id,message.from_user.id)

        except ValueError:

            pass

    lang=await get_user_language(message.from_user.id)

    await message.answer(

        t(lang,"welcome",name=message.from_user.first_name or "do‘st"),

        reply_markup=app_inline_keyboard(lang)

    )

    await message.answer(

        "👇",

        reply_markup=main_keyboard(lang)

    )

@dp.message(F.text.in_({

    "🧠 IQ · EQ · PQ testini ishlash",

    "🧠 Пройти IQ · EQ · PQ",

    "🧠 Take IQ · EQ · PQ"

}))

async def old_test_button(message:types.Message):

    lang=await get_user_language(message.from_user.id)

    await message.answer(

        "🧠 Mini App'ni oching:",

        reply_markup=app_inline_keyboard(lang)

    )

@dp.message(F.text.in_({

    "📜 Sertifikatim",

    "📜 Мой сертификат",

    "📜 My certificate"

}))

async def certificate_button(message:types.Message):

    await upsert_user(message.from_user)

    result=await db_fetchrow("""

        SELECT *

        FROM results

        WHERE user_id=$1 AND test_type='IQ'

        ORDER BY created_at DESC

        LIMIT 1

    """,message.from_user.id)

    if not result:

        lang=await get_user_language(message.from_user.id)

        await message.answer(t(lang,"no_cert"))

        return

    cert=await ensure_certificate(

        message.from_user.id,

        int(result["id"])

    )

    if not cert:

        await message.answer("Sertifikat topilmadi.")

        return

    await message.answer(

        f"📜 <b>IQ TEST BOT sertifikati</b>\n\n"

        f"Ism: <b>{cert['full_name']}</b>\n"

        f"IQ: <b>{cert['score']}</b>\n"

        f"Daraja: <b>{cert['level']}</b>\n"

        f"Kod: <code>{cert['verification_code']}</code>\n\n"

        f"Tekshirish:\n{PUBLIC_BASE_URL}/api/certificate/{cert['verification_code']}"

    )

@dp.message(F.text.in_({

    "🏆 Reyting",

    "🏆 Рейтинг",

    "🏆 Ranking"

}))

async def ranking_button(message:types.Message):

    await upsert_user(message.from_user)

    rows=await db_fetch("""

        SELECT

            COALESCE(

                u.full_name,

                NULLIF(TRIM(CONCAT_WS(' ',u.first_name,u.last_name)),''),

                COALESCE(u.username,'Foydalanuvchi')

            ) AS name,

            r.score

        FROM results r

        JOIN users u ON u.user_id=r.user_id

        WHERE r.test_type='IQ'

        ORDER BY r.score DESC,r.created_at ASC

        LIMIT 10

    """)

    if not rows:

        await message.answer("🏆 Hali reyting bo‘sh.")

        return

    text="🏆 <b>IQ TEST BOT — TOP 10</b>\n\n"

    for i,row in enumerate(rows,1):

        text+=f"{i}. {row['name']} — <b>{row['score']}</b>\n"

    await message.answer(text)

@dp.message(F.text.in_({

    "💰 Pul ishlash",

    "💰 Заработать",

    "💰 Earn"

}))

async def earn_button(message:types.Message):

    await upsert_user(message.from_user)

    link=f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"

    await message.answer(

        "💰 <b>Referral</b>\n\n"

        "Do‘stlaringizni botga taklif qiling.\n\n"

        f"Sizning havolangiz:\n<code>{link}</code>"

    )

@dp.message(F.text.in_({

    "ℹ️ Narx va yordam",

    "ℹ️ Цена и помощь",

    "ℹ️ Prices & help"

}))

async def help_button(message:types.Message):

    await upsert_user(message.from_user)

    iq=await setting_int("iq_price")

    iq_retry=await setting_int("iq_retry_price")

    eq=await setting_int("eq_price")

    pq=await setting_int("pq_price")

    battle=await setting_int("battle_price")

    await message.answer(

        "ℹ️ <b>IQ TEST BOT</b>\n\n"

        f"🧠 IQ: <b>{iq:,} so‘m</b>\n"

        f"🔄 IQ qayta: <b>{iq_retry:,} so‘m</b>\n"

        f"💭 EQ: <b>{eq:,} so‘m</b>\n"

        f"🎯 PQ: <b>{pq:,} so‘m</b>\n"

        f"⚔️ Battle: <b>{battle:,} so‘m / odam</b>\n\n"

        "Muammo bo‘lsa administratorga murojaat qiling."

    ).replace(",", " ")

@dp.message(F.text.in_({

    "🌐 Til",

    "🌐 Язык",

    "🌐 Language"

}))

async def language_button(message:types.Message):

    kb=InlineKeyboardMarkup(inline_keyboard=[

        [

            InlineKeyboardButton(text="🇺🇿 O‘zbek",callback_data="lang:uz"),

            InlineKeyboardButton(text="🇷🇺 Русский",callback_data="lang:ru"),

            InlineKeyboardButton(text="🇬🇧 English",callback_data="lang:en"),

        ]

    ])

    await message.answer("🌐 Tilni tanlang:",reply_markup=kb)

@dp.callback_query(F.data.startswith("lang:"))

async def language_callback(call:CallbackQuery):

    lang=call.data.split(":",1)[1]

    if lang not in TRANSLATIONS:

        await call.answer()

        return

    await db_execute("""

        UPDATE users

        SET language=$1,updated_at=NOW()

        WHERE user_id=$2

    """,lang,call.from_user.id)

    await call.answer(t(lang,"lang_changed"))

    try:

        await call.message.edit_text(

            t(

                lang,

                "welcome",

                name=call.from_user.first_name or "do‘st"

            ),

            reply_markup=app_inline_keyboard(lang)

        )

    except Exception:

        pass

@dp.callback_query(F.data.startswith("payapprove:"))

async def payment_approve_callback(call:CallbackQuery):

    if not await is_admin(call.from_user.id):

        await call.answer("Ruxsat yo‘q.",show_alert=True)

        return

    try:

        payment_id=int(call.data.split(":",1)[1])

    except ValueError:

        await call.answer("Noto‘g‘ri ID",show_alert=True)

        return

    class DummyRequest:

        async def json(self):

            return {}

    # Reuse the exact endpoint logic directly instead of manufacturing

    # Telegram/WebApp identity.

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            payment=await conn.fetchrow("""

                SELECT *

                FROM payments

                WHERE id=$1

                FOR UPDATE

            """,payment_id)

            if not payment:

                await call.answer("Payment topilmadi.",show_alert=True)

                return

            await conn.execute("""

                UPDATE payments

                SET status='approved',updated_at=NOW()

                WHERE id=$1

            """,payment_id)

            if payment["attempt_id"]:

                attempt=await conn.fetchrow("""

                    SELECT *

                    FROM test_attempts

                    WHERE id=$1

                    FOR UPDATE

                """,payment["attempt_id"])

                if attempt:

                    result=await conn.fetchrow("""

                        INSERT INTO results(

                            user_id,attempt_id,test_type,score,level

                        )

                        VALUES($1,$2,$3,$4,$5)

                        ON CONFLICT(attempt_id) DO UPDATE

                        SET score=EXCLUDED.score,

                            level=EXCLUDED.level

                        RETURNING *

                    """,

                        attempt["user_id"],

                        attempt["id"],

                        attempt["test_type"],

                        attempt["score"],

                        attempt["level"]

                    )

                    await conn.execute("""

                        UPDATE test_attempts

                        SET result_visible=TRUE,

                            payment_status='approved'

                        WHERE id=$1

                    """,attempt["id"])

    await call.answer("✅ To‘lov tasdiqlandi.")

    try:

        await call.message.edit_reply_markup(reply_markup=None)

    except Exception:

        pass

@dp.callback_query(F.data.startswith("payreject:"))

async def payment_reject_callback(call:CallbackQuery):

    if not await is_admin(call.from_user.id):

        await call.answer("Ruxsat yo‘q.",show_alert=True)

        return

    try:

        payment_id=int(call.data.split(":",1)[1])

    except ValueError:

        await call.answer("Noto‘g‘ri ID",show_alert=True)

        return

    await db_execute("""

        UPDATE payments

        SET status='rejected',updated_at=NOW()

        WHERE id=$1

    """,payment_id)

    await call.answer("❌ To‘lov rad etildi.")

    try:

        await call.message.edit_reply_markup(reply_markup=None)

    except Exception:

        pass

@dp.message(Command("admin"))

async def admin_command(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    await message.answer(

        "🛠 <b>ADMIN PANEL</b>\n\n"

        "/stats — statistika\n"

        "/payments — pending to‘lovlar\n"

        "/cards — kartalar\n"

        "/users — foydalanuvchilar\n"

        "/broadcast matn — xabar yuborish\n"

        "/setlive fake 95114 342 — live"

    )

@dp.message(Command("stats"))

async def admin_stats(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    users=await db_fetchval_safe("SELECT COUNT(*) FROM users")

    results=await db_fetchval_safe("SELECT COUNT(*) FROM results")

    payments=await db_fetchval_safe(

        "SELECT COUNT(*) FROM payments WHERE status='pending'"

    )

    battles=await db_fetchval_safe("SELECT COUNT(*) FROM battles")

    await message.answer(

        "📊 <b>Statistika</b>\n\n"

        f"👤 Users: <b>{users}</b>\n"

        f"🧠 Results: <b>{results}</b>\n"

        f"💳 Pending payments: <b>{payments}</b>\n"

        f"⚔️ Battles: <b>{battles}</b>"

    )

@dp.message(Command("payments"))

async def admin_payments(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    rows=await db_fetch("""

        SELECT

            p.id,p.user_id,p.payment_type,p.amount,p.status,

            p.created_at,u.username,u.first_name

        FROM payments p

        JOIN users u ON u.user_id=p.user_id

        WHERE p.status='pending'

        ORDER BY p.id DESC

        LIMIT 30

    """)

    if not rows:

        await message.answer("Pending to‘lovlar yo‘q.")

        return

    text="💳 <b>PENDING PAYMENTS</b>\n\n"

    for row in rows:

        text+=(

            f"#{row['id']} | "

            f"{row['payment_type']} | "

            f"{row['amount']:,} so‘m | "

            f"{row['first_name'] or row['username'] or row['user_id']}\n"

        )

    await message.answer(text.replace(",", " "))

@dp.message(Command("cards"))

async def admin_cards(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    rows=await db_fetch("""

        SELECT id,card_number,holder,bank,active

        FROM payment_cards

        ORDER BY id

    """)

    if not rows:

        await message.answer("Kartalar yo‘q.")

        return

    text="💳 <b>KARTALAR</b>\n\n"

    for row in rows:

        text+=(

            f"#{row['id']} "

            f"{row['card_number']} "

            f"{row['holder'] or ''} "

            f"{row['bank'] or ''} "

            f"{'✅' if row['active'] else '❌'}\n"

        )

    await message.answer(text)

@dp.message(Command("users"))

async def admin_users(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    rows=await db_fetch("""

        SELECT user_id,username,first_name,language,last_seen

        FROM users

        ORDER BY last_seen DESC

        LIMIT 30

    """)

    if not rows:

        await message.answer("Users yo‘q.")

        return

    text="👤 <b>USERS</b>\n\n"

    for row in rows:

        text+=(

            f"<code>{row['user_id']}</code> "

            f"@{row['username'] or '—'} "

            f"{row['first_name'] or ''} "

            f"[{row['language']}]\n"

        )

    await message.answer(text)

@dp.message(Command("broadcast"))

async def admin_broadcast(message:types.Message):

    if not await is_admin(message.from_user.id):

        await message.answer("Ruxsat yo‘q.")

        return

    text=(message.text or "").split(maxsplit=1)

    if len(text)<2:

        await message.answer("Format: /broadcast xabar")

        return

    broadcast_text=text[1]

    users=await db_fetch("SELECT user_id FROM users ORDER BY user_id")

    sent=0

    failed=0

    for row in users:

        try:

            await bot.send_message(

                int(row["user_id"]),

                broadcast_text

            )

            sent+=1

        except Exception:

            failed+=1

        await asyncio.sleep(.05)

    await message.answer(

        f"📢 Tugadi.\n\n"

        f"Yuborildi: <b>{sent}</b>\n"

        f"Xato: <b>{failed}</b>"

    )

@dp.message()

async def fallback_message(message:types.Message):

    await upsert_user(message.from_user)

    lang=await get_user_language(message.from_user.id)

    await message.answer(

        t(

            lang,

            "welcome",

            name=message.from_user.first_name or "do‘st"

        ),

        reply_markup=app_inline_keyboard(lang)

    )

@app.get("/api/admin/users")

async def api_admin_users(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    rows=await db_fetch("""

        SELECT

            user_id,username,first_name,last_name,

            language,full_name,gender,age,country,

            last_seen,created_at

        FROM users

        ORDER BY created_at DESC

        LIMIT 500

    """)

    return {

        "ok":True,

        "users":[

            {

                "user_id":r["user_id"],

                "username":r["username"],

                "first_name":r["first_name"],

                "last_name":r["last_name"],

                "language":r["language"],

                "full_name":r["full_name"],

                "gender":r["gender"],

                "age":r["age"],

                "country":r["country"],

                "last_seen":r["last_seen"].isoformat(),

                "created_at":r["created_at"].isoformat()

            }

            for r in rows

        ]

    }

@app.get("/api/admin/payments")

async def api_admin_payments(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    rows=await db_fetch("""

        SELECT

            p.id,p.user_id,p.payment_type,p.amount,

            p.status,p.receipt_file_id,p.created_at,

            u.username,u.first_name,u.last_name

        FROM payments p

        JOIN users u ON u.user_id=p.user_id

        ORDER BY p.id DESC

        LIMIT 500

    """)

    return {

        "ok":True,

        "payments":[

            {

                "id":r["id"],

                "user_id":r["user_id"],

                "payment_type":r["payment_type"],

                "amount":r["amount"],

                "status":r["status"],

                "has_receipt":bool(r["receipt_file_id"]),

                "username":r["username"],

                "first_name":r["first_name"],

                "last_name":r["last_name"],

                "created_at":r["created_at"].isoformat()

            }

            for r in rows

        ]

    }

@app.get("/api/admin/cards")

async def api_admin_cards(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    rows=await db_fetch("""

        SELECT id,card_number,holder,bank,active,created_at

        FROM payment_cards

        ORDER BY id DESC

    """)

    return {

        "ok":True,

        "cards":[

            {

                "id":r["id"],

                "card_number":r["card_number"],

                "holder":r["holder"],

                "bank":r["bank"],

                "active":r["active"],

                "created_at":r["created_at"].isoformat()

            }

            for r in rows

        ]

    }

@app.post("/api/admin/cards")

async def api_admin_add_card(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    body=await request.json()

    card_number="".join(

        ch for ch in str(body.get("card_number",""))

        if ch.isdigit()

    )

    if len(card_number)<12 or len(card_number)>19:

        raise HTTPException(status_code=400,detail="Invalid card number")

    holder=str(body.get("holder") or "").strip()[:100]

    bank=str(body.get("bank") or "").strip()[:100]

    row=await db_fetchrow("""

        INSERT INTO payment_cards(

            card_number,holder,bank,active

        )

        VALUES($1,$2,$3,TRUE)

        RETURNING id

    """,

        card_number,holder,bank

    )

    return {

        "ok":True,

        "id":row["id"]

    }

@app.post("/api/admin/cards/{card_id}/toggle")

async def api_admin_toggle_card(card_id:int,request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    row=await db_fetchrow("""

        UPDATE payment_cards

        SET active=NOT active

        WHERE id=$1

        RETURNING id,active

    """,card_id)

    if not row:

        raise HTTPException(status_code=404,detail="Card not found")

    return {

        "ok":True,

        "id":row["id"],

        "active":row["active"]

    }

@app.get("/api/admin/stats")

async def api_admin_stats(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    users=await db_fetchval_safe("SELECT COUNT(*) FROM users")

    iq_results=await db_fetchval_safe(

        "SELECT COUNT(*) FROM results WHERE test_type='IQ'"

    )

    eq_results=await db_fetchval_safe(

        "SELECT COUNT(*) FROM results WHERE test_type='EQ'"

    )

    pq_results=await db_fetchval_safe(

        "SELECT COUNT(*) FROM results WHERE test_type='PQ'"

    )

    payments=await db_fetchval_safe("SELECT COUNT(*) FROM payments")

    approved=await db_fetchval_safe(

        "SELECT COUNT(*) FROM payments WHERE status='approved'"

    )

    pending=await db_fetchval_safe(

        "SELECT COUNT(*) FROM payments WHERE status='pending'"

    )

    battles=await db_fetchval_safe("SELECT COUNT(*) FROM battles")

    certificates=await db_fetchval_safe("SELECT COUNT(*) FROM certificates")

    return {

        "ok":True,

        "stats":{

            "users":int(users or 0),

            "iq_results":int(iq_results or 0),

            "eq_results":int(eq_results or 0),

            "pq_results":int(pq_results or 0),

            "payments":int(payments or 0),

            "approved_payments":int(approved or 0),

            "pending_payments":int(pending or 0),

            "battles":int(battles or 0),

            "certificates":int(certificates or 0)

        }

    }

@app.post("/api/admin/settings")

async def api_admin_settings(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    body=await request.json()

    allowed={

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

        "live_fake_delta"

    }

    changed={}

    for key,value in body.items():

        if key not in allowed:

            continue

        if key=="live_mode":

            value=str(value)

            if value not in {"fake","real"}:

                raise HTTPException(

                    status_code=400,

                    detail="Invalid live mode"

                )

        else:

            try:

                value=int(value)

            except (TypeError,ValueError):

                raise HTTPException(

                    status_code=400,

                    detail=f"Invalid value for {key}"

                )

            if value<0:

                raise HTTPException(

                    status_code=400,

                    detail=f"Negative value for {key}"

                )

        await db_execute("""

            INSERT INTO app_settings(key,value)

            VALUES($1,$2)

            ON CONFLICT(key)

            DO UPDATE SET value=EXCLUDED.value

        """,key,str(value))

        changed[key]=value

    return {

        "ok":True,

        "changed":changed

    }

@app.get("/api/admin/settings")

async def api_admin_settings(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    keys=[

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

        "live_fake_delta"

    ]

    values={}

    for key in keys:

        values[key]=await setting(key)

    return {

        "ok":True,

        "settings":values

    }

@app.get("/api/admin/certificates")

async def api_admin_certificates(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    rows=await db_fetch("""

        SELECT

            c.id,c.certificate_id,c.verification_code,

            c.type,c.full_name,c.score,c.level,c.created_at,

            c.user_id

        FROM certificates c

        ORDER BY c.id DESC

        LIMIT 500

    """)

    return {

        "ok":True,

        "certificates":[

            {

                "id":r["id"],

                "certificate_id":r["certificate_id"],

                "verification_code":r["verification_code"],

                "type":r["type"],

                "full_name":r["full_name"],

                "score":r["score"],

                "level":r["level"],

                "user_id":r["user_id"],

                "created_at":r["created_at"].isoformat()

            }

            for r in rows

        ]

    }

@app.get("/api/admin/battles")

async def api_admin_battles(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    rows=await db_fetch("""

        SELECT

            b.id,b.code,b.status,b.created_by,

            b.created_at,b.ready_at,b.finalized_at,

            COUNT(bp.user_id) AS player_count

        FROM battles b

        LEFT JOIN battle_players bp ON bp.battle_id=b.id

        GROUP BY

            b.id,b.code,b.status,b.created_by,

            b.created_at,b.ready_at,b.finalized_at

        ORDER BY b.created_at DESC

        LIMIT 500

    """)

    return {

        "ok":True,

        "battles":[

            {

                "id":str(r["id"]),

                "code":r["code"],

                "status":r["status"],

                "created_by":r["created_by"],

                "player_count":int(r["player_count"]),

                "created_at":r["created_at"].isoformat(),

                "ready_at":r["ready_at"].isoformat() if r["ready_at"] else None,

                "finalized_at":r["finalized_at"].isoformat() if r["finalized_at"] else None

            }

            for r in rows

        ]

    }

@app.post("/api/admin/broadcast")

async def api_admin_broadcast(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    body=await request.json()

    text=str(body.get("text","")).strip()

    if not text:

        raise HTTPException(status_code=400,detail="Text is required")

    rows=await db_fetch("SELECT user_id FROM users ORDER BY user_id")

    sent=0

    failed=0

    for row in rows:

        try:

            await bot.send_message(int(row["user_id"]),text)

            sent+=1

        except Exception:

            failed+=1

        await asyncio.sleep(.05)

    return {

        "ok":True,

        "sent":sent,

        "failed":failed

    }

@app.get("/api/admin")

async def api_admin_home(request:Request):

    user=await require_webapp_user(request)

    if not await is_admin(int(user["id"])):

        raise HTTPException(status_code=403,detail="Forbidden")

    return {

        "ok":True,

        "admin":True

    }

if __name__=="__main__":

    uvicorn.run(

        app,

        host="0.0.0.0",

        port=PORT,

        log_level="info"

    )