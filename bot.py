import os
import re
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
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip()).rstrip("/")
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
# Short-lived admin input state for Telegram panel edits. Values are discarded
# immediately after a successful update, and never contain secrets.
ADMIN_PENDING: dict[int, str] = {}

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

LOCAL_BEHAVIOR_QUESTIONS = {
    "uz": {
        "EQ": [
            ("Muhim vazifa ustida ishlayotganingizda kimdir sizni bo‘lib yubordi. Eng to‘g‘ri birinchi qadam qaysi?", ["Jahl bilan javob berish", "To‘xtab, vaziyatni aniqlab, keyingi javobni ongli tanlash", "Hamma gapni e’tiborsiz qoldirish", "Vazifani tashlab ketish"], 1),
            ("Do‘stingiz ishingizni boshqalar oldida tanqid qildi. Eng konstruktiv javob qaysi?", ["Qarshi hujum qilish", "Mavzuni o‘zgartirish", "Tinglash, nimani yaxshilash mumkinligini so‘rash va xotirjam muhokama qilish", "Hech narsa bo‘lmagandek tutish"], 2),
            ("Jamoadoshingiz odatdagidan ancha jim. Eng foydali munosabat qaysi?", ["Uni gapirishga majburlash", "Yolg‘iz holatda holidan xabar olish va javob berishiga imkon berish", "Bu haqda g‘iybat qilish", "Uni chetlatish"], 1),
            ("Siz boshqalarga ta’sir qilgan xato qildingiz. Keyin nima qilishingiz kerak?", ["Xatoni tan olish, qisqa tushuntirish va oqibatini tuzatishga yordam berish", "Kimdir sezguncha yashirish", "Boshqani ayblash", "Jim kutish"], 0),
            ("Ikki kishi muhokamada keskin kelishmayapti. Suhbatni nima yaxshilaydi?", ["Darhol bir tomonni tanlash", "Fikringiz yutishi uchun ovozni balandlatish", "Har bir tomonning nuqtai nazari va kelishmovchilik sababini aniqlash", "Ikkalasini ham eshitmasdan suhbatni tugatish"], 2),
            ("Kechasi stressli xabar oldingiz. Odatda eng konstruktiv yondashuv qaysi?", ["Jahl bilan darhol javob berish", "Uni bir necha kishiga yuborish", "Yuboruvchini o‘chirib tashlash", "Reaksiyani bosib, xotirjam fikrlay olganingizda javob berish"], 3),
        ],
        "PQ": [
            ("Bugun uchta vazifangiz bor. Eng amaliy birinchi qadam qaysi?", ["Tasodifiy vazifalarni qilish", "Ularni shoshilinchligi va ta’siriga qarab ustuvorlashtirish", "Barcha vazifalardan qochish", "Eng oson ko‘ringanidan boshlash"], 1),
            ("Katta loyiha sizni bosib ketgandek tuyulmoqda. Nima foydali?", ["Reja tuzmaslik", "Motivatsiya kelishini kutish", "Hammasini birdan qilish", "Loyihani aniq bosqichlar va keyingi harakatlarga bo‘lish"], 3),
            ("Hozirgi rejangiz kutilgan natijani bermayapti. Nima qilish kerak?", ["Uni ko‘r-ko‘rona takrorlash", "Maqsaddan darhol voz kechish", "Dalillarni ko‘rib, nima o‘zgarganini aniqlash va rejani moslashtirish", "Vosita yoki odamni ayblash"], 2),
            ("Qiyin vazifani doim ortga suryapsiz. Eng amaliy yondashuv qaysi?", ["Vazifani yanada kattalashtirish", "Kichik, aniq birinchi qadamni belgilab boshlash", "Muddatni e’tiborsiz qoldirish", "Bog‘liq bo‘lmagan ishlarni qo‘shish"], 1),
            ("Maqsadingiz yangi imkoniyat bilan to‘qnashdi. Qaror qabul qilishga nima yordam beradi?", ["Ustuvorliklaringizga nisbatan foyda va zararlarni solishtirish", "Tasodifiy tanlash", "Boshqalarga siz uchun qaror qildirish", "Chegarasiz ikkisini ham qilish"], 0),
            ("Muhim bosqichni tugatdingiz. Keyingi bosqichni nima yaxshilaydi?", ["Hech qachon tahlil qilmaslik", "Hammasini qaytadan boshlash", "Nima ishlaganini, nima ishlamaganini va keyin nimani o‘zgartirishni yozib olish", "Fikr-mulohazadan qochish"], 2),
        ],
    },
    "ru": {
        "EQ": [
            ("Вас прервали во время важной задачи. Какой первый шаг наиболее конструктивен?", ["Ответить раздражённо", "Остановиться, уточнить ситуацию и осознанно выбрать реакцию", "Игнорировать всех", "Бросить задачу"], 1),
            ("Друг критикует вашу работу при других. Как ответить конструктивнее всего?", ["Атаковать в ответ", "Сменить тему", "Выслушать, спросить, что можно улучшить, и спокойно обсудить", "Сделать вид, что ничего не произошло"], 2),
            ("Вы заметили, что коллега необычно тихий. Что полезнее всего?", ["Заставить его говорить", "Лично узнать, всё ли в порядке, и дать пространство для ответа", "Сплетничать об этом", "Исключить его из команды"], 1),
            ("Вы допустили ошибку, которая повлияла на других. Что делать дальше?", ["Признать ошибку, кратко объяснить и помочь исправить последствия", "Скрывать её до обнаружения", "Обвинить другого", "Молча ждать"], 0),
            ("Два человека резко не согласны в обсуждении. Что скорее улучшит разговор?", ["Сразу выбрать сторону", "Говорить громче, чтобы победить", "Прояснить позицию каждого и причину разногласий", "Закончить разговор, не выслушав никого"], 2),
            ("Вы получили стрессовое сообщение поздно вечером. Как обычно конструктивнее поступить?", ["Сразу ответить в гневе", "Переслать его нескольким людям", "Удалить отправителя", "Сначала успокоить реакцию и ответить, когда сможете ясно мыслить"], 3),
        ],
        "PQ": [
            ("Сегодня у вас три задачи. Какой первый шаг наиболее практичен?", ["Делать случайные задачи", "Расставить приоритеты по срочности и влиянию", "Избегать всех задач", "Начать с самой лёгкой"], 1),
            ("Большой проект кажется непосильным. Что полезнее?", ["Не планировать", "Ждать мотивации", "Делать всё одновременно", "Разбить проект на конкретные этапы и следующие действия"], 3),
            ("Текущий план перестал давать ожидаемый результат. Что делать?", ["Слепо повторять его", "Сразу отказаться от цели", "Проверить данные, понять, что изменилось, и скорректировать план", "Обвинить инструмент"], 2),
            ("Вы постоянно откладываете сложную задачу. Что наиболее практично?", ["Сделать задачу ещё больше", "Определить маленькое конкретное первое действие и начать", "Игнорировать срок", "Добавить несвязанные задачи"], 1),
            ("Цель конфликтует с новой возможностью. Что поможет решить?", ["Сравнить компромиссы с вашими приоритетами", "Выбрать случайно", "Пусть все решат за вас", "Делать оба варианта без ограничений"], 0),
            ("Вы завершили важный этап. Что улучшит следующий?", ["Никогда не анализировать", "Сбросить всё", "Записать, что сработало, что нет и что изменить дальше", "Избегать обратной связи"], 2),
        ],
    },
    "en": {
        "EQ": EQ_QUESTIONS,
        "PQ": [
            ("You have three tasks today. What is the most practical first step?", ["Do random tasks", "Prioritize them by urgency and impact", "Avoid all tasks", "Start with the easiest one"], 1),
            ("A large project feels overwhelming. What is most useful?", ["Do not make a plan", "Wait for motivation", "Do everything at once", "Break the project into clear stages and next actions"], 3),
            ("Your current plan is no longer producing the expected result. What should you do?", ["Repeat it blindly", "Give up on the goal immediately", "Review the evidence, identify what changed, and adapt the plan", "Blame the tool or another person"], 2),
            ("You keep postponing a difficult task. What is the most practical approach?", ["Make the task even bigger", "Define one small, concrete first step and start", "Ignore the deadline", "Add unrelated work"], 1),
            ("Your goal conflicts with a new opportunity. What can help you decide?", ["Compare the benefits and trade-offs against your priorities", "Choose randomly", "Let other people decide for you", "Do both without any limits"], 0),
            ("You have completed an important stage. What will improve the next stage?", ["Never analyze it", "Start everything over", "Record what worked, what did not, and what to change next", "Avoid feedback"], 2),
        ],
    },
}


def localized_behavior_questions(test_type: str, lang: str):
    source = LOCAL_BEHAVIOR_QUESTIONS.get(lang, LOCAL_BEHAVIOR_QUESTIONS["uz"]).get(test_type)
    if not source:
        source = LOCAL_BEHAVIOR_QUESTIONS["en"][test_type]
    return [{"id": i + 1, "text": q, "options": opts} for i, (q, opts, _) in enumerate(source)]

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

async def migrate_legacy_battle_ids():
    """Convert legacy integer battle IDs to UUIDs without deleting battle data."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            col = await conn.fetchrow("""
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='battles' AND column_name='id'
            """)
            if not col or col["udt_name"] == "uuid":
                return
            if col["udt_name"] not in ("int2", "int4", "int8"):
                raise RuntimeError(f"Unsupported legacy battles.id type: {col['data_type']}")

            # Mapping survives the whole transaction and is dropped afterwards.
            await conn.execute("DROP TABLE IF EXISTS _battle_id_migration_map")
            await conn.execute("CREATE TEMP TABLE _battle_id_migration_map (old_id BIGINT PRIMARY KEY, new_id UUID NOT NULL)")

            legacy_battles = await conn.fetch("SELECT id FROM battles ORDER BY id")
            for row in legacy_battles:
                await conn.execute(
                    "INSERT INTO _battle_id_migration_map(old_id,new_id) VALUES($1,$2)",
                    int(row["id"]), uuid4()
                )

            # Add UUID shadow columns first, then populate all references.
            await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS _id_uuid UUID")
            await conn.execute("""
                UPDATE battles b
                SET _id_uuid=m.new_id
                FROM _battle_id_migration_map m
                WHERE b.id=m.old_id
            """)

            bp_exists = await conn.fetchval("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='battle_players' AND column_name='battle_id'
            """)
            if bp_exists:
                await conn.execute("ALTER TABLE battle_players ADD COLUMN IF NOT EXISTS _battle_id_uuid UUID")
                await conn.execute("""
                    UPDATE battle_players bp
                    SET _battle_id_uuid=m.new_id
                    FROM _battle_id_migration_map m
                    WHERE bp.battle_id=m.old_id
                """)

            pay_exists = await conn.fetchval("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='payments' AND column_name='battle_id'
            """)
            if pay_exists:
                await conn.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS _battle_id_uuid UUID")
                await conn.execute("""
                    UPDATE payments p
                    SET _battle_id_uuid=m.new_id
                    FROM _battle_id_migration_map m
                    WHERE p.battle_id=m.old_id
                """)

            # Remove foreign keys pointing at the old integer PK before replacing it.
            fk_rows = await conn.fetch("""
                SELECT conrelid::regclass::text AS table_name, conname
                FROM pg_constraint
                WHERE contype='f' AND confrelid='battles'::regclass
            """)
            for fk in fk_rows:
                await conn.execute(f'ALTER TABLE {fk["table_name"]} DROP CONSTRAINT IF EXISTS "{fk["conname"]}"')

            # Replace battle_players' composite PK and battle_id column.
            if bp_exists:
                pk = await conn.fetchrow("""
                    SELECT conname FROM pg_constraint
                    WHERE conrelid='battle_players'::regclass AND contype='p'
                """)
                if pk:
                    await conn.execute(f'ALTER TABLE battle_players DROP CONSTRAINT IF EXISTS "{pk["conname"]}"')
                await conn.execute("ALTER TABLE battle_players DROP COLUMN battle_id")
                await conn.execute("ALTER TABLE battle_players RENAME COLUMN _battle_id_uuid TO battle_id")

            # Replace payments.battle_id while retaining payment history.
            if pay_exists:
                await conn.execute("ALTER TABLE payments DROP COLUMN battle_id")
                await conn.execute("ALTER TABLE payments RENAME COLUMN _battle_id_uuid TO battle_id")

            # Replace battles.id and its primary key.
            pk = await conn.fetchrow("""
                SELECT conname FROM pg_constraint
                WHERE conrelid='battles'::regclass AND contype='p'
            """)
            if pk:
                await conn.execute(f'ALTER TABLE battles DROP CONSTRAINT IF EXISTS "{pk["conname"]}"')
            await conn.execute("ALTER TABLE battles DROP COLUMN id")
            await conn.execute("ALTER TABLE battles RENAME COLUMN _id_uuid TO id")
            await conn.execute("ALTER TABLE battles ADD PRIMARY KEY (id)")

            if bp_exists:
                await conn.execute("""
                    ALTER TABLE battle_players
                    ADD CONSTRAINT battle_players_battle_id_fkey
                    FOREIGN KEY (battle_id) REFERENCES battles(id) ON DELETE CASCADE
                """)
                await conn.execute("ALTER TABLE battle_players ADD PRIMARY KEY (battle_id,user_id)")

            await conn.execute("DROP TABLE _battle_id_migration_map")
            logger.info("Migrated legacy integer battle IDs to UUIDs")

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
        current_index INTEGER NOT NULL DEFAULT 0,
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

    # Legacy battle schema migration. Earlier versions used INTEGER/BIGINT
    # battle IDs. The current API uses UUIDs, so an existing database must
    # migrate the primary/foreign keys instead of relying on CREATE TABLE IF
    # NOT EXISTS (which never changes an existing column type).
    await migrate_legacy_battle_ids()

    # Legacy test-session schemas: some older deployments stored session_id as
    # TEXT/VARCHAR. The current API consistently treats it as UUID and uses
    # $1::uuid in queries. Convert old valid UUID strings before the API starts.
    async with db_pool.acquire() as conn:
        session_type = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name='test_sessions'
              AND column_name='session_id'
        """)
        attempt_type = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name='test_attempts'
              AND column_name='session_id'
        """)
        battle_player_type = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name='battle_players'
              AND column_name='session_id'
        """)

        if session_type and session_type != 'uuid':
            invalid = await conn.fetchval("""
                SELECT COUNT(*) FROM test_sessions
                WHERE session_id IS NOT NULL
                  AND session_id::text <> ''
                  AND session_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            """)
            if invalid:
                raise RuntimeError(f"Database schema invalid: {invalid} test_sessions.session_id values are not UUIDs")

            await conn.execute("ALTER TABLE test_attempts DROP CONSTRAINT IF EXISTS test_attempts_session_id_fkey")
            await conn.execute("ALTER TABLE battle_players DROP CONSTRAINT IF EXISTS battle_players_session_id_fkey")
            await conn.execute("""
                ALTER TABLE test_sessions
                ALTER COLUMN session_id TYPE UUID
                USING NULLIF(session_id::text, '')::uuid
            """)
            if attempt_type and attempt_type != 'uuid':
                await conn.execute("""
                    ALTER TABLE test_attempts
                    ALTER COLUMN session_id TYPE UUID
                    USING NULLIF(session_id::text, '')::uuid
                """)
            if battle_player_type and battle_player_type != 'uuid':
                await conn.execute("""
                    ALTER TABLE battle_players
                    ALTER COLUMN session_id TYPE UUID
                    USING NULLIF(session_id::text, '')::uuid
                """)
            await conn.execute("""
                ALTER TABLE test_attempts
                ADD CONSTRAINT test_attempts_session_id_fkey
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id) ON DELETE SET NULL
            """)
            await conn.execute("""
                ALTER TABLE battle_players
                ADD CONSTRAINT battle_players_session_id_fkey
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id) ON DELETE SET NULL
            """)
            logger.info("Migrated legacy test session IDs to UUID")
        elif attempt_type and attempt_type != 'uuid':
            await conn.execute("ALTER TABLE test_attempts DROP CONSTRAINT IF EXISTS test_attempts_session_id_fkey")
            await conn.execute("""
                ALTER TABLE test_attempts
                ALTER COLUMN session_id TYPE UUID
                USING NULLIF(session_id::text, '')::uuid
            """)
            await conn.execute("""
                ALTER TABLE test_attempts
                ADD CONSTRAINT test_attempts_session_id_fkey
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id) ON DELETE SET NULL
            """)
            logger.info("Migrated legacy test_attempts.session_id to UUID")
        elif battle_player_type and battle_player_type != 'uuid':
            await conn.execute("ALTER TABLE battle_players DROP CONSTRAINT IF EXISTS battle_players_session_id_fkey")
            await conn.execute("""
                ALTER TABLE battle_players
                ALTER COLUMN session_id TYPE UUID
                USING NULLIF(session_id::text, '')::uuid
            """)
            await conn.execute("""
                ALTER TABLE battle_players
                ADD CONSTRAINT battle_players_session_id_fkey
                FOREIGN KEY (session_id) REFERENCES test_sessions(session_id) ON DELETE SET NULL
            """)
            logger.info("Migrated legacy battle_players.session_id to UUID")

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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language_selected BOOLEAN NOT NULL DEFAULT FALSE",
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
        # Legacy payment schemas may contain columns such as payment_id or
        # product that the current application no longer writes. If those old
        # columns are still NOT NULL, PostgreSQL rejects an otherwise valid
        # payment INSERT. They must remain nullable; current code uses payments.id
        # and payment_type instead.
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=\'payments\' AND column_name=\'payment_id\') THEN ALTER TABLE payments ALTER COLUMN payment_id DROP NOT NULL; END IF; IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=\'payments\' AND column_name=\'product\') THEN ALTER TABLE payments ALTER COLUMN product DROP NOT NULL; END IF; END $$;",
        # Existing databases may have an older test_sessions schema.
        # CREATE TABLE IF NOT EXISTS does not add columns to an existing table.
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS test_type TEXT",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS answers JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS questions JSONB",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS score INTEGER",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS correct_count INTEGER",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS is_retry BOOLEAN NOT NULL DEFAULT FALSE",
        # Battle columns are explicitly migrated because CREATE TABLE IF NOT EXISTS
        # does not alter an already-existing table.
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS code TEXT",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'waiting'",
        "ALTER TABLE battles ADD COLUMN IF NOT EXISTS created_by BIGINT",
        # Older production builds used battle_code instead of code and made
        # it NOT NULL. The current INSERT writes code, so preserve any old
        # value, then make the legacy column nullable.
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=\'battles\' AND column_name=\'battle_code\') THEN UPDATE battles SET code=COALESCE(code,battle_code) WHERE code IS NULL; ALTER TABLE battles ALTER COLUMN battle_code DROP NOT NULL; END IF; END $$;",
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

    # Repeat the legacy payment constraint cleanup after all migrations. This
    # is deliberately idempotent so an old production database can be upgraded
    # repeatedly without breaking the current payment INSERT.
    await db_execute("""
        DO $$
        DECLARE
            c RECORD;
        BEGIN
            -- Keep NOT NULL on columns that belong to the current payment model.
            -- Any extra NOT NULL column is necessarily legacy from an older
            -- version and the current INSERT cannot populate it. Making only
            -- those extra columns nullable prevents the exact "fix one column,
            -- next old column fails" migration loop.
            FOR c IN
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='payments'
                  AND is_nullable='NO'
                  AND column_name NOT IN (
                      'id','user_id','attempt_id','battle_id','payment_type',
                      'amount','card_id','receipt_file_id','status',
                      'created_at','updated_at'
                  )
            LOOP
                EXECUTE format('ALTER TABLE payments ALTER COLUMN %I DROP NOT NULL', c.column_name);
                RAISE NOTICE 'Relaxed legacy payments.% NOT NULL constraint', c.column_name;
            END LOOP;
        END $$;
    """)

    # Legacy battle tables can contain columns from older versions that the
    # current INSERT no longer supplies. Preserve useful data, but prevent an
    # unrelated legacy NOT NULL column from blocking creation of new battles.
    await db_execute("""
        DO $$
        DECLARE
            c RECORD;
        BEGIN
            FOR c IN
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='battles'
                  AND is_nullable='NO'
                  AND column_name NOT IN (
                      'id','code','status','created_by','created_at','ready_at','finalized_at'
                  )
            LOOP
                EXECUTE format('ALTER TABLE battles ALTER COLUMN %I DROP NOT NULL', c.column_name);
                RAISE NOTICE 'Relaxed legacy battles.% NOT NULL constraint', c.column_name;
            END LOOP;
        END $$;
    """)

    # Legacy databases created before results.attempt_id was UNIQUE can still
    # reach the runtime with no unique/exclusion constraint. The application
    # intentionally uses ON CONFLICT(attempt_id), so make that invariant true
    # before serving requests. Remove duplicate historical rows first;
    # certificates reference result rows with ON DELETE SET NULL.
    await db_execute("""
        DELETE FROM results r
        USING results newer
        WHERE r.attempt_id = newer.attempt_id
          AND r.attempt_id IS NOT NULL
          AND r.id > newer.id
    """)
    await db_execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS results_attempt_id_unique_idx
        ON results(attempt_id)
    """)

    # Final schema verification/self-healing pass. This runs after all legacy
    # migrations so an old database can never reach an API handler with a
    # partially upgraded test_sessions table. CREATE TABLE IF NOT EXISTS does\n    # not modify an existing table, therefore every runtime column used by the\n    # test flow is explicitly ensured here as well.\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS test_type TEXT")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS answers JSONB NOT NULL DEFAULT '{}'::jsonb")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS current_index INTEGER NOT NULL DEFAULT 0")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS questions JSONB")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS score INTEGER")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS correct_count INTEGER")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0")\n    await db_execute("ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS is_retry BOOLEAN NOT NULL DEFAULT FALSE")\n\n    # Old sessions may have been created before expires_at/questions existed.\n    # Give them a deterministic expiry and regenerate their public question\n    # payload when it is missing, without touching submitted answers.\n    await db_execute("""\n        UPDATE test_sessions\n        SET expires_at = COALESCE(expires_at, started_at + INTERVAL '30 minutes')\n        WHERE expires_at IS NULL\n    """)\n\n    required_schema = {\n        "test_sessions": {\n            "session_id", "user_id", "test_type", "status", "answers",\n            "questions", "score", "correct_count", "started_at",\n            "completed_at", "expires_at", "price", "is_retry"\n        },\n        "test_attempts": {\n            "id", "user_id", "test_type", "session_id", "score",\n            "correct_count", "duration", "payment_status",\n            "result_visible", "level", "answers", "created_at"\n        },\n        "results": {\n            "id", "user_id", "attempt_id", "test_type", "score",\n            "level", "created_at"\n        },\n        "payments": {\n            "id", "user_id", "attempt_id", "battle_id", "payment_type",\n            "amount", "card_id", "receipt_file_id", "status",\n            "created_at", "updated_at"\n        },\n        "payment_cards": {\n            "id", "card_number", "holder", "bank", "active", "created_at"\n        },\n        "battles": {\n            "id", "code", "status", "created_by", "created_at",\n            "ready_at", "finalized_at"\n        },\n        "battle_players": {\n            "battle_id", "user_id", "role", "payment_id", "session_id",\n            "score", "correct_count", "finished_at"\n        },\n        "certificates": {\n            "id", "user_id", "result_id", "certificate_id",\n            "verification_code", "type", "full_name", "score", "level",\n            "created_at"\n        },\n    }\n    async with db_pool.acquire() as conn:\n        for table, expected in required_schema.items():\n            rows = await conn.fetch(\n                """\n                SELECT column_name\n                FROM information_schema.columns\n                WHERE table_schema='public' AND table_name=$1\n                """,\n                table,\n            )\n            actual = {r["column_name"] for r in rows}\n            missing = sorted(expected - actual)\n            if missing:\n                raise RuntimeError(\n                    f"Database schema incomplete for {table}: missing {', '.join(missing)}"\n                )\n\n        q_type = await conn.fetchval("""\n            SELECT data_type\n            FROM information_schema.columns\n            WHERE table_schema='public'\n              AND table_name='test_sessions'\n              AND column_name='questions'\n        """)\n        if q_type != "jsonb":\n            raise RuntimeError(\n                f"Database schema invalid: test_sessions.questions must be jsonb, got {q_type!r}"\n            )\n\n    logger.info("Database schema verification passed: all runtime tables/columns are present")\n\n    # Existing databases may have battle_players rows created by an older
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
        INSERT INTO users(user_id,username,first_name,last_name,last_seen,updated_at,language_selected)
        VALUES($1,$2,$3,$4,NOW(),NOW(),FALSE)
        ON CONFLICT(user_id) DO UPDATE SET
          username=EXCLUDED.username,
          first_name=EXCLUDED.first_name,
          last_name=EXCLUDED.last_name,
          last_seen=NOW(),
          updated_at=NOW()
    """, tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)

async def get_user_language(user_id: int) -> str:
    row = await db_fetchrow("SELECT language FROM users WHERE user_id=$1", user_id)
    return row["language"] if row and row["language"] in TRANSLATIONS else "uz"

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
        row = await db_fetchrow("SELECT language,language_selected FROM users WHERE user_id=$1", message.from_user.id)
        lang = row["language"] if row and row["language"] in TRANSLATIONS else "uz"
        if not row or not bool(row["language_selected"]):
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
    await db_execute("UPDATE users SET language=$1,language_selected=TRUE,updated_at=NOW() WHERE user_id=$2", lang, callback.from_user.id)
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
        {"uz":"⬇️ Quyidagi tugma orqali Mini App'ni oching.","ru":"⬇️ Откройте Mini App кнопкой ниже.","en":"⬇️ Open the Mini App using the button below."}[lang],
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
    # The Telegram certificate button must deliver the real PNG certificate,
    # not a text-only summary. Reuse the exact same renderer as the Mini App.
    try:
        cert = await db_fetchrow("SELECT * FROM certificates WHERE certificate_id=$1", row["certificate_id"])
        if not cert:
            await message.answer("❌ Sertifikat topilmadi.")
            return
        raw = certificate_png(cert)
        photo = BufferedInputFile(raw, filename=f"{cert['certificate_id']}.png")
        await message.answer_photo(
            photo,
            caption=(
                f"📜 <b>IQ TEST BOT — Sertifikat</b>\n\n"
                f"👤 {cert['full_name']}\n"
                f"🧠 IQ: <b>{cert['score']}</b> · {cert['level'] or '—'}\n"
                f"🔐 <code>{cert['verification_code']}</code>"
            )
        )
    except Exception:
        logger.exception("Telegram certificate image delivery failed")
        await message.answer("❌ Sertifikat rasmini yuborishda xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.")

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

@dp.message(F.text.regexp(r"^(?!/).+"))
async def admin_pending_input(message: types.Message):
    user_id = message.from_user.id
    pending = ADMIN_PENDING.get(user_id)
    if not pending:
        return
    if not await is_admin(user_id):
        ADMIN_PENDING.pop(user_id, None)
        return

    raw = (message.text or "").strip()

    if pending.startswith("price:"):
        key = pending.split(":", 1)[1]
        allowed = {"iq_price", "iq_retry_price", "eq_price", "eq_retry_price", "pq_price", "pq_retry_price", "battle_price"}
        try:
            value = int(raw)
            if value < 0 or key not in allowed:
                raise ValueError
        except ValueError:
            await message.answer("❌ Narx 0 yoki undan katta butun son bo‘lishi kerak.")
            return
        await db_execute(
            "INSERT INTO app_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            key, str(value)
        )
        ADMIN_PENDING.pop(user_id, None)
        await message.answer(f"✅ <b>{key}</b> = <b>{value:,}</b> so‘m".replace(",", " "))
        await send_admin_panel(message)
        return

    if pending.startswith("live:"):
        field = pending.split(":", 1)[1]
        mapping = {"base": "live_fake_base", "online": "live_fake_online", "delta": "live_fake_delta"}
        key = mapping.get(field)
        try:
            value = int(raw)
            if value < 0 or not key:
                raise ValueError
        except ValueError:
            await message.answer("❌ Faqat 0 yoki undan katta butun son yuboring.")
            return
        await db_execute(
            "INSERT INTO app_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            key, str(value)
        )
        ADMIN_PENDING.pop(user_id, None)
        await message.answer(f"✅ Live <b>{field}</b> = <b>{value:,}</b>".replace(",", " "))
        await send_admin_panel(message)
        return

    if pending == "msg:user_id":
        try:
            target_id = int(raw)
            if target_id <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Telegram User ID faqat musbat son bo‘lishi kerak.")
            return
        exists = await db_fetchrow("SELECT user_id FROM users WHERE user_id=$1", target_id)
        if not exists:
            await message.answer("❌ Bu User ID bazada topilmadi. Qaytadan yuboring.")
            return
        ADMIN_PENDING[user_id] = f"msg:user:{target_id}"
        await message.answer(f"👤 User <code>{target_id}</code> tanlandi. Endi yuboriladigan xabar matnini yuboring.\n\nBekor qilish: /cancel")
        return

    if pending.startswith("msg:user:"):
        try:
            target_id = int(pending.split(":", 2)[2])
        except (ValueError, IndexError):
            ADMIN_PENDING.pop(user_id, None)
            await message.answer("❌ Xabar sessiyasi buzilgan. Qaytadan urinib ko‘ring.")
            return
        if not raw:
            await message.answer("❌ Bo‘sh xabar yuborib bo‘lmaydi.")
            return
        try:
            await bot.send_message(target_id, raw)
        except Exception as exc:
            logger.exception("Admin direct message failed: target=%s", target_id)
            await message.answer(f"❌ Xabar yuborilmadi. Telegram xatosi: <code>{type(exc).__name__}</code>")
            return
        ADMIN_PENDING.pop(user_id, None)
        await message.answer(f"✅ Xabar <code>{target_id}</code> foydalanuvchiga yuborildi.")
        return

    if pending in {"broadcast:all", "broadcast:paid"}:
        if not raw:
            await message.answer("❌ Bo‘sh xabar yuborib bo‘lmaydi.")
            return
        if pending == "broadcast:paid":
            users = await db_fetch("""
                SELECT DISTINCT u.user_id
                FROM users u
                JOIN payments p ON p.user_id=u.user_id
                WHERE p.status='approved'
                ORDER BY u.user_id
            """)
        else:
            users = await db_fetch("SELECT user_id FROM users ORDER BY user_id")
        sent = 0
        failed = 0
        for row in users:
            try:
                await bot.send_message(int(row["user_id"]), raw)
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1
        ADMIN_PENDING.pop(user_id, None)
        await message.answer(f"📨 <b>Yuborish yakunlandi</b>\n\n✅ Yuborildi: <b>{sent}</b>\n❌ Yetkazilmadi: <b>{failed}</b>\n👥 Jami: <b>{len(users)}</b>")
        return

    if pending == "card:add":
        parts = [x.strip() for x in raw.split("|", 2)]
        if len(parts) != 3 or not parts[0]:
            await message.answer("❌ Format noto‘g‘ri.\n<code>8600123456789012 | ISM FAMILIYA | BANK</code>")
            return
        await db_execute(
            "INSERT INTO payment_cards(card_number,holder,bank,active) VALUES($1,$2,$3,TRUE)",
            parts[0], parts[1], parts[2]
        )
        ADMIN_PENDING.pop(user_id, None)
        await message.answer("✅ Karta qo‘shildi va faol holatga o‘rnatildi.")
        await send_admin_panel(message)
        return

    if pending.startswith("card:edit:"):
        try:
            card_id = int(pending.split(":", 2)[2])
        except (ValueError, IndexError):
            ADMIN_PENDING.pop(user_id, None)
            await message.answer("❌ Karta ID noto‘g‘ri.")
            return
        parts = [x.strip() for x in raw.split("|", 2)]
        if len(parts) != 3 or not parts[0]:
            await message.answer("❌ Format noto‘g‘ri.\n<code>8600123456789012 | ISM FAMILIYA | BANK</code>")
            return
        await db_execute(
            "UPDATE payment_cards SET card_number=$1,holder=$2,bank=$3 WHERE id=$4",
            parts[0], parts[1], parts[2], card_id
        )
        ADMIN_PENDING.pop(user_id, None)
        await message.answer(f"✅ Karta <b>#{card_id}</b> yangilandi.")
        await send_admin_panel(message)
        return

    if pending == "user:lookup":
        try:
            target_id = int(raw)
            if target_id <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ User ID noto‘g‘ri.")
            return
        row = await db_fetchrow("""
            SELECT u.*, COALESCE((SELECT MAX(score) FROM results r WHERE r.user_id=u.user_id AND r.test_type='IQ'),0) best_iq,
                   (SELECT COUNT(*) FROM results r WHERE r.user_id=u.user_id) result_count,
                   (SELECT COUNT(*) FROM payments p WHERE p.user_id=u.user_id AND p.status='approved') paid_count
            FROM users u WHERE u.user_id=$1
        """, target_id)
        ADMIN_PENDING.pop(user_id, None)
        if not row:
            await message.answer("❌ Foydalanuvchi topilmadi.")
            return
        await message.answer(
            f"👤 <b>Foydalanuvchi</b>\n\n"
            f"ID: <code>{row['user_id']}</code>\n"
            f"Username: @{row['username'] or '—'}\n"
            f"Ism: <b>{row['full_name'] or row['first_name'] or '—'}</b>\n"
            f"Jins: {row['gender'] or '—'}\n"
            f"Yosh: {row['age'] or '—'}\n"
            f"Davlat: {row['country'] or '—'}\n"
            f"Eng yuqori IQ: <b>{row['best_iq']}</b>\n"
            f"Natijalar: <b>{row['result_count']}</b>\n"
            f"Tasdiqlangan to‘lovlar: <b>{row['paid_count']}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✉️ Xabar yozish", callback_data=f"admin:msg:{row['user_id']}")],
                [InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]
            ])
        )
        return

@dp.message(Command("cancel"))
async def admin_cancel(message: types.Message):
    if await is_admin(message.from_user.id):
        ADMIN_PENDING.pop(message.from_user.id, None)
        await message.answer("↩️ Amal bekor qilindi.")

@dp.message(Command("broadcast"))
async def admin_broadcast(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Ruxsat yo‘q.")
        return
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer("Format: /broadcast Matn")
        return
    users = await db_fetch("SELECT user_id FROM users")
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], text)
            sent += 1
            await asyncio.sleep(.04)
        except Exception:
            pass
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
        [InlineKeyboardButton(text="📨 Userlarga xabar", callback_data="admin:messaging")],
    ])
    await target.answer("⚙️ <b>ADMIN PANEL</b>\n\nKerakli bo‘limni tanlang:", reply_markup=kb)

async def _admin_edit_message(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None):
    try:
        if callback.message and (callback.message.photo or callback.message.document):
            await callback.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text, reply_markup=markup)

async def _admin_home_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin:users"), InlineKeyboardButton(text="📊 Statistics", callback_data="admin:stats")],
        [InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments"), InlineKeyboardButton(text="💰 Products", callback_data="admin:products")],
        [InlineKeyboardButton(text="📜 Certificates", callback_data="admin:certs"), InlineKeyboardButton(text="⚔️ Battles", callback_data="admin:battles")],
        [InlineKeyboardButton(text="💳 Cards", callback_data="admin:cards"), InlineKeyboardButton(text="🎯 Live Counter", callback_data="admin:live")],
        [InlineKeyboardButton(text="📨 Userlarga xabar", callback_data="admin:messaging")],
    ])

@dp.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery):
    try:
        if not await is_admin(callback.from_user.id):
            await callback.answer("Ruxsat yo‘q", show_alert=True)
            return
        action = callback.data.split(":", 1)[1]

        if action == "home":
            await _admin_edit_message(callback, "⚙️ <b>ADMIN PANEL</b>\n\nKerakli bo‘limni tanlang:", await _admin_home_markup())
            await callback.answer()
            return

        if action.startswith("approve:"):
            pid = int(action.split(":", 1)[1])
            await callback.answer("Tasdiqlanmoqda…")
            p, status = await approve_payment_record(pid)
            if not p:
                await _admin_edit_message(callback, f"❌ Payment #{pid} topilmadi.")
                return
            if status == "rejected":
                await _admin_edit_message(callback, f"❌ Payment #{pid} avval rad etilgan.")
                return
            if status == "already":
                await _admin_edit_message(callback, f"✅ Payment #{pid} allaqachon tasdiqlangan.")
                return
            try:
                lang = await get_user_language(int(p["user_id"]))
                msg = {"uz":"✅ To‘lov tasdiqlandi. Natijangiz ochildi.","ru":"✅ Оплата подтверждена. Результат открыт.","en":"✅ Payment approved. Your result is now available."}[lang]
                await bot.send_message(p["user_id"], msg)
            except Exception:
                logger.exception("Admin approval notification failed")
            if p["attempt_id"]:
                try:
                    await ensure_and_send_iq_certificate(p["user_id"], p["attempt_id"])
                except Exception:
                    logger.exception("Paid certificate delivery failed")
            await _admin_edit_message(callback, f"✅ <b>Payment #{pid} tasdiqlandi.</b>")
            return

        if action.startswith("reject:"):
            pid = int(action.split(":", 1)[1])
            p = await db_fetchrow("SELECT * FROM payments WHERE id=$1", pid)
            if not p:
                await _admin_edit_message(callback, f"❌ Payment #{pid} topilmadi.")
                await callback.answer()
                return
            if p["status"] == "approved":
                await callback.answer("Bu payment allaqachon tasdiqlangan", show_alert=True)
                return
            await db_execute("UPDATE payments SET status='rejected',updated_at=NOW() WHERE id=$1", pid)
            if p["attempt_id"]:
                await db_execute("UPDATE test_attempts SET payment_status='rejected',result_visible=FALSE WHERE id=$1", p["attempt_id"])
            try:
                lang = await get_user_language(int(p["user_id"]))
                msg = {"uz":"❌ To‘lov rad etildi. Receiptni tekshirib qayta yuboring.","ru":"❌ Оплата отклонена. Проверьте чек и отправьте снова.","en":"❌ Payment rejected. Check the receipt and send it again."}[lang]
                await bot.send_message(p["user_id"], msg)
            except Exception:
                logger.exception("Admin rejection notification failed")
            await _admin_edit_message(callback, f"❌ <b>Payment #{pid} rad etildi.</b>")
            await callback.answer()
            return

        if action == "users":
            row = await db_fetchrow("SELECT COUNT(*) c FROM users")
            rows = await db_fetch("""
                SELECT u.user_id,u.username,u.full_name,u.first_name,u.last_seen,
                       COALESCE((SELECT MAX(r.score) FROM results r WHERE r.user_id=u.user_id AND r.test_type='IQ'),0) best_iq
                FROM users u ORDER BY u.last_seen DESC NULLS LAST LIMIT 8
            """)
            lines = [f"👥 <b>Users: {row['c']}</b>", ""]
            buttons = []
            for r in rows:
                name = r["full_name"] or r["first_name"] or "Foydalanuvchi"
                lines.append(f"<code>{r['user_id']}</code> · {name} · IQ <b>{r['best_iq']}</b>")
                buttons.append([InlineKeyboardButton(text=f"✉️ {name[:18]}", callback_data=f"admin:msg:{r['user_id']}")])
            buttons += [
                [InlineKeyboardButton(text="🔎 User ID qidirish", callback_data="admin:user_lookup"), InlineKeyboardButton(text="✉️ Userga yozish", callback_data="admin:msg")],
                [InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]
            ]
            await _admin_edit_message(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons))
            await callback.answer()
            return

        if action == "user_lookup":
            ADMIN_PENDING[callback.from_user.id] = "user:lookup"
            await callback.message.answer("🔎 Foydalanuvchi Telegram <b>User ID</b> sini yuboring.\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action == "msg":
            ADMIN_PENDING[callback.from_user.id] = "msg:user_id"
            await callback.message.answer("✉️ Xabar yuboriladigan foydalanuvchining Telegram <b>User ID</b> sini yuboring.\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action.startswith("msg:"):
            target_id = int(action.split(":", 1)[1])
            ADMIN_PENDING[callback.from_user.id] = f"msg:user:{target_id}"
            await callback.message.answer(f"✉️ <code>{target_id}</code> ga yuboriladigan xabar matnini yuboring.\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action == "messaging":
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 Bitta userga", callback_data="admin:msg")],
                [InlineKeyboardButton(text="📢 Barchaga", callback_data="admin:broadcast:all")],
                [InlineKeyboardButton(text="💳 To‘lov qilganlarga", callback_data="admin:broadcast:paid")],
                [InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")],
            ])
            await _admin_edit_message(callback, "📨 <b>USERLARGA XABAR</b>\n\nKimga yuborishni tanlang.", markup)
            await callback.answer()
            return

        if action.startswith("broadcast:"):
            mode = action.split(":", 1)[1]
            if mode not in {"all", "paid"}:
                await callback.answer("Noto‘g‘ri tur", show_alert=True)
                return
            ADMIN_PENDING[callback.from_user.id] = f"broadcast:{mode}"
            target = "barcha foydalanuvchilarga" if mode == "all" else "tasdiqlangan to‘lov qilgan foydalanuvchilarga"
            await callback.message.answer(f"📨 Xabarni {target} yuborish uchun matnni yuboring.\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action == "stats":
            stats = await db_fetchrow("""
                SELECT
                    (SELECT COUNT(*) FROM users) users,
                    (SELECT COUNT(*) FROM results) results,
                    (SELECT COUNT(*) FROM test_attempts WHERE status='finished') finished,
                    (SELECT COUNT(*) FROM payments WHERE status='pending') pending_payments,
                    (SELECT COUNT(*) FROM payments WHERE status='approved') approved_payments,
                    (SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved') revenue,
                    (SELECT COUNT(*) FROM certificates) certificates,
                    (SELECT COUNT(*) FROM battles) battles,
                    (SELECT COUNT(*) FROM referrals) referrals
            """)
            text = (
                "📊 <b>UMUMIY STATISTIKA</b>\n\n"
                f"👥 Users: <b>{stats['users']}</b>\n"
                f"🧠 Yakunlangan testlar: <b>{stats['finished']}</b>\n"
                f"📄 Natijalar: <b>{stats['results']}</b>\n"
                f"⏳ Kutilayotgan to‘lovlar: <b>{stats['pending_payments']}</b>\n"
                f"✅ Tasdiqlangan to‘lovlar: <b>{stats['approved_payments']}</b>\n"
                f"💰 Tushum: <b>{int(stats['revenue']):,}</b> so‘m\n"
                f"📜 Sertifikatlar: <b>{stats['certificates']}</b>\n"
                f"⚔️ Battles: <b>{stats['battles']}</b>\n"
                f"🤝 Referrals: <b>{stats['referrals']}</b>"
            ).replace(",", " ")
            await _admin_edit_message(callback, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]]))
            await callback.answer()
            return

        if action == "payments":
            rows = await db_fetch("""
                SELECT p.id,p.user_id,p.amount,p.status,p.payment_type,p.receipt_file_id,p.created_at,
                       u.full_name,u.username
                FROM payments p LEFT JOIN users u ON u.user_id=p.user_id
                ORDER BY CASE WHEN p.status='pending' THEN 0 ELSE 1 END, p.id DESC LIMIT 15
            """)
            if not rows:
                text = "💳 <b>Payments</b>\n\nPayment mavjud emas."
                buttons = []
            else:
                lines = ["💳 <b>PAYMENTS</b>", ""]
                buttons = []
                for r in rows:
                    state = {"pending":"⏳","approved":"✅","rejected":"❌"}.get(r["status"],"•")
                    name = r["full_name"] or ("@" + r["username"] if r["username"] else str(r["user_id"]))
                    lines.append(f"{state} <b>#{r['id']}</b> · {name} · {r['amount'] or 0} so‘m · {r['payment_type']}")
                    if r["status"] == "pending":
                        buttons.append([
                            InlineKeyboardButton(text=f"✅ #{r['id']}", callback_data=f"admin:approve:{r['id']}"),
                            InlineKeyboardButton(text=f"❌ #{r['id']}", callback_data=f"admin:reject:{r['id']}"),
                            InlineKeyboardButton(text="✉️", callback_data=f"admin:msg:{r['user_id']}"),
                        ])
                buttons.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:payments"), InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")])
                text = "\n".join(lines)
            await _admin_edit_message(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))
            await callback.answer()
            return

        if action == "products":
            keys = ["iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"]
            vals = await asyncio.gather(*(setting(k,"0") for k in keys))
            labels = ["IQ", "IQ qayta", "EQ", "EQ qayta", "PQ", "PQ qayta", "Battle"]
            keyboard = []
            for key, val, label in zip(keys, vals, labels):
                keyboard.append([InlineKeyboardButton(text=f"✏️ {label}: {val} so‘m", callback_data=f"admin:price:{key}")])
            keyboard.append([InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")])
            await _admin_edit_message(callback, "💰 <b>MAHSULOTLAR / NARXLAR</b>\n\nHar bir narxni alohida o‘zgartirish mumkin.", InlineKeyboardMarkup(inline_keyboard=keyboard))
            await callback.answer()
            return

        if action.startswith("price:"):
            key = action.split(":", 1)[1]
            allowed = {"iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"}
            if key not in allowed:
                await callback.answer("Noto‘g‘ri narx", show_alert=True)
                return
            ADMIN_PENDING[callback.from_user.id] = f"price:{key}"
            await callback.message.answer(f"✏️ <b>{key}</b> uchun yangi narxni yuboring.\nMasalan: <code>5000</code>\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action == "cards":
            rows = await db_fetch("SELECT id,card_number,holder,bank,active FROM payment_cards ORDER BY id DESC")
            lines = ["💳 <b>TO‘LOV KARTALARI</b>", ""]
            buttons = []
            for r in rows:
                state = "🟢" if r["active"] else "🔴"
                lines.append(f"{state} <b>#{r['id']}</b> · <code>{r['card_number']}</code> · {r['holder'] or '—'} · {r['bank'] or '—'}")
                buttons.append([
                    InlineKeyboardButton(text=f"✏️ #{r['id']}", callback_data=f"admin:card:edit:{r['id']}"),
                    InlineKeyboardButton(text="ON/OFF", callback_data=f"admin:card:toggle:{r['id']}"),
                    InlineKeyboardButton(text="🗑", callback_data=f"admin:card:delete:{r['id']}")
                ])
            buttons.append([InlineKeyboardButton(text="➕ Karta qo‘shish", callback_data="admin:card:add")])
            buttons.append([InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")])
            await _admin_edit_message(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons))
            await callback.answer()
            return

        if action == "card:add":
            ADMIN_PENDING[callback.from_user.id] = "card:add"
            await callback.message.answer("➕ Karta ma’lumotini yuboring:\n<code>KARTA | HOLDER | BANK</code>\n\nMasalan:\n<code>8600123456789012 | ALI OMONOV | Ipak Yo‘li</code>\n\nBekor qilish: /cancel")
            await callback.answer()
            return

        if action.startswith("card:edit:"):
            card_id = int(action.split(":")[2])
            ADMIN_PENDING[callback.from_user.id] = f"card:edit:{card_id}"
            await callback.message.answer(f"✏️ Karta <b>#{card_id}</b> ma’lumotlarini yuboring:\n<code>KARTA | HOLDER | BANK</code>")
            await callback.answer()
            return

        if action.startswith("card:toggle:"):
            card_id = int(action.split(":")[2])
            await db_execute("UPDATE payment_cards SET active=NOT active WHERE id=$1", card_id)
            await callback.answer("Karta holati o‘zgartirildi")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("💳 Karta holati yangilandi.")
            return

        if action.startswith("card:delete:"):
            card_id = int(action.split(":")[2])
            row = await db_fetchrow("SELECT card_number FROM payment_cards WHERE id=$1", card_id)
            if not row:
                await callback.answer("Karta topilmadi", show_alert=True)
                return
            await db_execute("DELETE FROM payment_cards WHERE id=$1", card_id)
            await callback.answer("Karta o‘chirildi")
            await _admin_edit_message(callback, f"🗑 Karta <b>#{card_id}</b> o‘chirildi.", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kartalar", callback_data="admin:cards")]]))
            return

        if action == "certs":
            row = await db_fetchrow("SELECT COUNT(*) c FROM certificates")
            recent = await db_fetch("SELECT certificate_id,full_name,score,created_at FROM certificates ORDER BY id DESC LIMIT 8")
            lines = [f"📜 <b>CERTIFICATES: {row['c']}</b>", ""]
            for r in recent:
                lines.append(f"• <b>{r['full_name']}</b> — IQ <b>{r['score']}</b> — <code>{r['certificate_id']}</code>")
            await _admin_edit_message(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]]))
            await callback.answer()
            return

        if action == "battles":
            rows = await db_fetch("""
                SELECT b.code,b.status,b.created_at,COUNT(bp.user_id) players
                FROM battles b LEFT JOIN battle_players bp ON bp.battle_id=b.id
                GROUP BY b.id ORDER BY b.created_at DESC LIMIT 10
            """)
            lines = ["⚔️ <b>BATTLЕS</b>", ""]
            for r in rows:
                lines.append(f"• <code>{r['code']}</code> · {r['status']} · {r['players']} players")
            if not rows:
                lines.append("Battle mavjud emas.")
            await _admin_edit_message(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:battles"), InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]]))
            await callback.answer()
            return

        if action == "live" or action.startswith("live_mode:") or action.startswith("live_edit:"):
            if action.startswith("live_mode:"):
                mode = action.split(":", 1)[1]
                if mode not in {"fake", "real"}:
                    await callback.answer("Noto‘g‘ri mode", show_alert=True)
                    return
                await db_execute("INSERT INTO app_settings(key,value) VALUES('live_mode',$1) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", mode)
            elif action.startswith("live_edit:"):
                field = action.split(":", 1)[1]
                if field not in {"base", "online", "delta"}:
                    await callback.answer("Noto‘g‘ri qiymat", show_alert=True)
                    return
                ADMIN_PENDING[callback.from_user.id] = f"live:{field}"
                await callback.message.answer(f"✏️ Live <b>{field}</b> qiymatini yuboring.\n\nBekor qilish: /cancel")
                await callback.answer()
                return
            vals = await asyncio.gather(setting("live_mode","fake"),setting("live_fake_base","95114"),setting("live_fake_online","342"),setting("live_fake_delta","8"))
            text = f"🎯 <b>LIVE COUNTER</b>\n\nMode: <b>{vals[0]}</b>\nJami: <b>{vals[1]}</b>\nOnline: <b>{vals[2]}</b>\nDelta: <b>{vals[3]}</b>"
            keyboard = [
                [InlineKeyboardButton(text="🟣 FAKE", callback_data="admin:live_mode:fake"), InlineKeyboardButton(text="🟢 REAL", callback_data="admin:live_mode:real")],
                [InlineKeyboardButton(text=f"✏️ Jami {vals[1]}", callback_data="admin:live_edit:base"), InlineKeyboardButton(text=f"✏️ Online {vals[2]}", callback_data="admin:live_edit:online")],
                [InlineKeyboardButton(text=f"✏️ Delta {vals[3]}", callback_data="admin:live_edit:delta")],
                [InlineKeyboardButton(text="⬅️ Admin", callback_data="admin:home")]
            ]
            await _admin_edit_message(callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard))
            await callback.answer()
            return

        await callback.answer("Noma’lum bo‘lim", show_alert=True)
    except Exception:
        logger.exception("Admin callback failed")
        await callback.answer("Xatolik. Render logini tekshiring.", show_alert=True)


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
    # Always pass UUIDs to asyncpg as strings. PostgreSQL casts them explicitly
    # in the test/battle queries, and this also keeps legacy TEXT schemas from
    # producing "expected str, got UUID" binding errors.
    return str(uuid4())

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

async def send_certificate_to_user(user_id: int, cert, prefix: str = "📜 Sertifikatingiz tayyor!"):
    """Send the generated certificate image to Telegram without breaking the test flow."""
    if not cert:
        return False
    try:
        raw = certificate_png(cert)
        photo = BufferedInputFile(raw, filename=f"{cert['certificate_id']}.png")
        caption = (
            f"{prefix}\n\n"
            f"🧠 IQ: <b>{cert['score']}</b>\n"
            f"🏷 {cert['level'] or '—'}\n"
            f"🔐 <code>{cert['verification_code']}</code>"
        )
        await bot.send_photo(user_id, photo, caption=caption)
        return True
    except Exception:
        logger.exception("Certificate delivery failed for user %s", user_id)
        return False

def certificate_png(cert):
    """Render the certificate in the same premium navy/cream/gold layout as the supplied reference."""
    # A compact built-in template is generated in code so Render needs no extra asset file.
    W, H = 1491, 1055
    img = Image.new("RGB", (W, H), (244, 240, 225))
    d = ImageDraw.Draw(img)
    navy = (8, 15, 31)
    gold = (184, 133, 47)
    cream = (249, 246, 236)
    muted = (86, 91, 106)
    dark = (17, 24, 40)

    # Reference-like dark corner panels.
    d.polygon([(0,0),(430,0),(210,150),(0,300)], fill=navy)
    d.polygon([(W,0),(W,330),(1260,145),(1110,0)], fill=navy)
    d.polygon([(0,H),(0,790),(230,900),(390,H)], fill=navy)
    d.polygon([(W,H),(W,820),(1270,910),(1110,H)], fill=navy)
    d.rounded_rectangle((24,18,W-24,H-18), radius=30, outline=gold, width=3)
    d.rounded_rectangle((40,35,W-40,H-35), radius=24, outline=(110,95,65), width=1)

    fp = font_path()
    if not fp:
        raise RuntimeError("Professional TTF font topilmadi")
    def font(sz): return ImageFont.truetype(fp, sz)
    def center(txt, y, f, fill=dark):
        box=d.textbbox((0,0), txt, font=f)
        d.text(((W-(box[2]-box[0]))/2, y), txt, font=f, fill=fill)
    def center_fit(txt,y,max_size,min_size,fill=dark,max_width=1080):
        size=max_size
        while size>min_size:
            f=font(size); box=d.textbbox((0,0),txt,font=f)
            if box[2]-box[0] <= max_width: break
            size-=2
        center(txt,y,font(max(size,min_size)),fill)

    # Header/logo.
    center("IQTESTPRO.UZ", 72, font(28), cream)
    center("AQLNI KASHF ETING", 112, font(17), (205,195,166))
    center("SERTIFIKAT", 160, font(78), gold)
    center("AQLLIY SALOHIYAT TO‘G‘RISIDA", 258, font(24), muted)
    center("USHBU SERTIFIKAT BILAN", 315, font(18), muted)

    full_name = str(cert.get("full_name") or "Foydalanuvchi")
    center_fit(full_name, 350, 62, 32, (24,31,48), 1050)
    d.line((340, 430, 1150, 430), fill=gold, width=2)

    center("IQ", 455, font(34), gold)
    center(str(cert.get("score", 0)), 490, font(100), (15,24,42))
    center(str(cert.get("level") or "O‘rta daraja").upper(), 605, font(22), muted)

    # Three compact metrics, visually matching the reference.
    metrics = [("Mantiqiy fikrlash", 92), ("Fazoviy tasavvur", 87), ("Naqsh aniqlash", 90)]
    xs = [385, 745, 1105]
    for (label, value), x in zip(metrics, xs):
        d.ellipse((x-52, 655, x+52, 759), outline=(196,174,128), width=2)
        center_x = x
        txt=str(value)+"/100"
        box=d.textbbox((0,0),txt,font=font(22))
        d.text((center_x-(box[2]-box[0])/2, 705),txt,font=font(22),fill=gold)
        box=d.textbbox((0,0),label,font=font(16))
        d.text((center_x-(box[2]-box[0])/2, 775),label,font=font(16),fill=muted)

    center("“Tafakkuringiz katta imkoniyatlarga loyiq.”", 840, font(25), (45,49,63))
    center("IQ TEST BOT · VERIFIED", 885, font(18), gold)

    created = cert.get("created_at")
    date_text = created.strftime("%d.%m.%Y") if hasattr(created, "strftime") else datetime.now().strftime("%d.%m.%Y")
    d.text((105, 900), date_text, font=font(20), fill=muted)
    d.text((105, 930), "SANA", font=font(13), fill=(130,130,135))
    d.text((1050, 900), str(cert.get("verification_code") or ""), font=font(18), fill=muted)
    d.text((1050, 930), "VERIFICATION", font=font(13), fill=(130,130,135))

    # Simple gold seal.
    cx, cy = 1300, 170
    d.ellipse((cx-78,cy-78,cx+78,cy+78), fill=(229,199,130), outline=gold, width=4)
    d.ellipse((cx-58,cy-58,cx+58,cy+58), outline=(117,83,31), width=3)
    check_font=font(52)
    check_box=d.textbbox((0,0),"✓",font=check_font)
    d.text((cx-(check_box[2]-check_box[0])/2, cy-34),"✓",font=check_font,fill=(83,58,22))

    bio=io.BytesIO(); img.save(bio,"PNG",optimize=True); bio.seek(0)
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
                    SELECT $1,$2,'IQ',$3,$4 WHERE NOT EXISTS (SELECT 1 FROM results r WHERE r.attempt_id=$2)
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
                SELECT $1,$2,$3,$4,$5 WHERE NOT EXISTS (SELECT 1 FROM results r WHERE r.attempt_id=$2)
            """,user_id,attempt_id,attempt["test_type"],attempt["score"],attempt["level"])
            return await conn.fetchrow("SELECT * FROM test_attempts WHERE id=$1",attempt_id)

app = FastAPI(title="IQ TEST BOT")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    # Render may probe the service root with HEAD/GET. Keep it 200 so a
    # configured root health-check cannot mark the service unhealthy.
    return {"status":"ok","service":"iq-test-bot"}

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/app", response_class=HTMLResponse)
async def app_page():
    path=os.path.join(BASE_DIR,"webapp","index.html")
    with open(path,"r",encoding="utf-8") as f:
        html=f.read()
    # Telegram WebView/Render can keep a 304-cached app.js after a deployment.
    # Always add a file-mtime query so the latest frontend is loaded without
    # requiring the user to clear Telegram cache manually.
    app_js_path=os.path.join(BASE_DIR,"webapp","app.js")
    try:
        version=str(int(os.path.getmtime(app_js_path)))
    except OSError:
        version="1"
    html=re.sub(r'/static/app\.js(?:\?[^"\']*)?', f'/static/app.js?v={version}', html)
    return HTMLResponse(html, headers={"Cache-Control":"no-store, max-age=0"})

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR,"webapp")), name="static")

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not WEBHOOK_SECRET or not hmac.compare_digest(supplied, WEBHOOK_SECRET):
        logger.warning("Telegram webhook rejected: invalid secret")
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
        update = Update.model_validate(payload)
        logger.info("Telegram update received: update_id=%s", update.update_id)
        await dp.feed_update(bot, update)
        logger.info("Telegram update processed: update_id=%s", update.update_id)
        return {"ok": True}
    except Exception:
        logger.exception("Webhook processing failed")
        # Telegram retries non-2xx responses. Return 200 only after aiogram
        # has actually received the update; real handler errors are logged.
        raise HTTPException(status_code=500, detail="Webhook processing error")

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
    await db_execute("UPDATE users SET last_seen=NOW(),updated_at=NOW() WHERE user_id=$1",uid)
    row=await db_fetchrow("SELECT * FROM users WHERE user_id=$1",uid)
    prices={k:await setting_int(k) for k in ["iq_price","iq_retry_price","eq_price","eq_retry_price","pq_price","pq_retry_price","battle_price"]}
    iq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='IQ' LIMIT 1",uid))
    eq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='EQ' LIMIT 1",uid))
    pq_done=bool(await db_fetchrow("SELECT 1 FROM results WHERE user_id=$1 AND test_type='PQ' LIMIT 1",uid))
    pending_payment = await db_fetchrow("""
        SELECT p.id, p.attempt_id, p.battle_id, p.payment_type, p.amount, p.status,
               p.receipt_file_id, p.created_at,
               c.card_number, c.holder, c.bank
        FROM payments p
        LEFT JOIN payment_cards c ON c.id=p.card_id
        WHERE p.user_id=$1 AND p.status='pending'
        ORDER BY p.id DESC LIMIT 1
    """, uid)
    pending_payload = None
    if pending_payment:
        pending_payload = dict(pending_payment)
        pending_payload["card"] = {
            "card_number": pending_payment["card_number"],
            "holder": pending_payment["holder"],
            "bank": pending_payment["bank"],
        } if pending_payment["card_number"] else None
    active=await db_fetchrow("SELECT session_id,test_type,questions,answers,current_index,started_at,expires_at,status FROM test_sessions WHERE user_id=$1 AND status='active' AND expires_at>NOW() ORDER BY started_at DESC LIMIT 1",uid)
    active_payload=None
    if active:
        lang=row["language"] if row["language"] in TRANSLATIONS else "uz"
        aq=normalize_test_questions(active["questions"],active["test_type"],lang)
        ai=max(0,min(int(active["current_index"] or 0),len(aq)-1))
        active_payload={"session_id":str(active["session_id"]),"test_type":active["test_type"],"questions":aq,"answers":active["answers"] if isinstance(active["answers"],dict) else {},"current_index":ai,"started_at":active["started_at"].isoformat(),"expires_at":active["expires_at"].isoformat()}
    stats=await db_fetchrow("""
        SELECT
          MAX(score) FILTER (WHERE test_type='IQ') AS iq_best,
          MAX(score) FILTER (WHERE test_type='EQ') AS eq_best,
          MAX(score) FILTER (WHERE test_type='PQ') AS pq_best,
          COUNT(*) AS total_tests,
          COUNT(*) FILTER (WHERE test_type='IQ') AS iq_attempts,
          COUNT(*) FILTER (WHERE test_type='EQ') AS eq_attempts,
          COUNT(*) FILTER (WHERE test_type='PQ') AS pq_attempts
        FROM results WHERE user_id=$1
    """,uid)
    iq_rank=await db_fetchrow("""
        SELECT COUNT(*)+1 AS position FROM (
          SELECT user_id, MAX(score) AS best_score FROM results WHERE test_type='IQ' GROUP BY user_id
        ) ranked
        WHERE best_score > COALESCE((SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='IQ'),-1)
    """,uid)
    profile_stats={"iq_best":int(stats["iq_best"]) if stats and stats["iq_best"] is not None else None,"eq_best":int(stats["eq_best"]) if stats and stats["eq_best"] is not None else None,"pq_best":int(stats["pq_best"]) if stats and stats["pq_best"] is not None else None,"total_tests":int(stats["total_tests"] or 0) if stats else 0,"iq_attempts":int(stats["iq_attempts"] or 0) if stats else 0,"eq_attempts":int(stats["eq_attempts"] or 0) if stats else 0,"pq_attempts":int(stats["pq_attempts"] or 0) if stats else 0,"iq_rank":int(iq_rank["position"]) if iq_rank else None}
    return {"ok":True,"user":{"id":uid,"username":row["username"],"first_name":row["first_name"],"language":row["language"],"language_selected":bool(row["language_selected"]),"full_name":row["full_name"],"gender":row["gender"],"age":row["age"],"country":row["country"],"hasIQ":iq_done,"hasEQ":eq_done,"hasPQ":pq_done},"prices":prices,"questions":public_iq_questions(),"pending_payment":pending_payload,"active_test":active_payload,"profile_stats":profile_stats}

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
    # Upsert instead of UPDATE-only: this is safe if bootstrap and profile save
    # race each other, and guarantees the validated Telegram user has a row.
    await db_execute("""
        INSERT INTO users(user_id,username,first_name,last_name,full_name,gender,age,country,last_seen,updated_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,NOW(),NOW())
        ON CONFLICT(user_id) DO UPDATE SET
          username=EXCLUDED.username,
          first_name=EXCLUDED.first_name,
          last_name=EXCLUDED.last_name,
          full_name=EXCLUDED.full_name,
          gender=EXCLUDED.gender,
          age=EXCLUDED.age,
          country=EXCLUDED.country,
          last_seen=NOW(),
          updated_at=NOW()
    """, uid, user.get("username"), user.get("first_name"), user.get("last_name"),
        full_name, gender, age, country)
    return {"ok":True}

@app.post("/api/test/start")
async def test_start(request: Request):
    user=await authenticated_user(request)
    data=await request.json()
    uid=int(user["id"])
    typ=str(data.get("test_type","IQ")).upper()
    lang_row=await db_fetchrow("SELECT language FROM users WHERE user_id=$1", uid)
    lang=(lang_row["language"] if lang_row and lang_row["language"] in TRANSLATIONS else "uz")
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
    active=await db_fetchrow("SELECT session_id,test_type,questions,answers,current_index,started_at,expires_at,price,is_retry FROM test_sessions WHERE user_id=$1 AND test_type=$2 AND status='active' AND expires_at>NOW() ORDER BY started_at DESC LIMIT 1",uid,typ)
    if active:
        # Never trust the raw DB JSON shape here. Older versions could store
        # JSONB as a JSON string, which made the frontend display Q3/16973.
        active_questions = normalize_test_questions(active["questions"], typ, lang)
        answers = active["answers"] if isinstance(active["answers"], dict) else {}
        answers = {str(k): int(v) for k,v in answers.items()
                   if str(k).isdigit() and 0 <= int(v) <= 3 and 1 <= int(k) <= len(active_questions)}
        current_index = max(0, min(int(active["current_index"] or 0), len(active_questions)-1))
        await db_execute(
            "UPDATE test_sessions SET questions=$1::jsonb,answers=$2::jsonb,current_index=$3 WHERE session_id=$4::uuid",
            json.dumps(active_questions), json.dumps(answers), current_index, str(active["session_id"])
        )
        return {"ok":True,"session_id":str(active["session_id"]),"test_type":active["test_type"],"questions":active_questions,"answers":answers,"current_index":current_index,"started_at":active["started_at"].isoformat(),"expires_at":active["expires_at"].isoformat(),"price":int(active["price"] or 0),"is_retry":bool(active["is_retry"]),"resumed":True}
    sid=new_session()
    expires=datetime.now(timezone.utc)+timedelta(minutes=30)
    if typ=="IQ":
        questions=public_iq_questions()
    else:
        questions=localized_behavior_questions(typ, lang)
    await db_execute(
        "INSERT INTO test_sessions(session_id,user_id,test_type,status,questions,expires_at,price,is_retry) VALUES($1,$2,$3,'active',$4,$5,$6,$7)",
        sid,uid,typ,json.dumps(questions),expires,price,has_previous
    )
    return {"ok":True,"session_id":str(sid),"test_type":typ,"questions":questions,"current_index":0,"answers":{},"expires_at":expires.isoformat(),"price":price,"is_retry":has_previous}

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
        source=LOCAL_BEHAVIOR_QUESTIONS["en"][session["test_type"]]
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
                        await conn.execute("INSERT INTO results(user_id,attempt_id,test_type,score,level) SELECT $1,$2,$3,$4,$5 WHERE NOT EXISTS (SELECT 1 FROM results r WHERE r.attempt_id=$2)",uid,attempt["id"],locked["test_type"],score,"EQ/PQ")
    if session["test_type"] == "IQ" and attempt["result_visible"]:
        # Free IQ: create and immediately send the certificate to the Telegram chat.
        # Certificate delivery must never turn a successfully completed test into HTTP 500.
        try:
            result_row = await db_fetchrow("SELECT * FROM results WHERE attempt_id=$1", attempt["id"])
            user_row = await db_fetchrow("SELECT full_name FROM users WHERE user_id=$1", uid)
            if result_row and user_row and user_row["full_name"]:
                cert = await create_certificate(uid, result_row["id"], user_row["full_name"], attempt["score"], attempt["level"])
                await send_certificate_to_user(uid, cert, "📜 IQ sertifikatingiz tayyor!")
        except Exception:
            logger.exception("Free certificate creation/delivery failed for user %s", uid)
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

@app.post("/api/test/{session_id}/progress")
async def test_progress(session_id: str, request: Request):
    user=await authenticated_user(request)
    uid=int(user["id"])
    data=await request.json()
    answers=data.get("answers") or {}
    if not isinstance(answers, dict):
        return json_error("Javoblar formati noto‘g‘ri",400)
    try:
        requested_index=int(data.get("current_index",0))
    except (TypeError,ValueError):
        requested_index=0
    session=await db_fetchrow("SELECT test_type,questions,status,expires_at FROM test_sessions WHERE session_id=$1::uuid AND user_id=$2",session_id,uid)
    if not session:
        return json_error("Session topilmadi",404)
    if session["status"] != "active":
        return json_error("Test allaqachon yakunlangan",409)
    if session["expires_at"] < datetime.now(timezone.utc):
        await db_execute("UPDATE test_sessions SET status='expired' WHERE session_id=$1::uuid AND user_id=$2 AND status='active'",session_id,uid)
        return json_error("Test vaqti tugagan",409)
    lang_row=await db_fetchrow("SELECT language FROM users WHERE user_id=$1",uid)
    lang=lang_row["language"] if lang_row and lang_row["language"] in TRANSLATIONS else "uz"
    questions=normalize_test_questions(session["questions"],session["test_type"],lang)
    max_index=max(0,len(questions)-1)
    current_index=max(0,min(requested_index,max_index))
    clean_answers={str(k):int(v) for k,v in answers.items() if str(k).isdigit() and 0 <= int(v) <= 3 and 1 <= int(k) <= len(questions)}
    await db_execute("UPDATE test_sessions SET current_index=$1, answers=$2::jsonb, questions=$3::jsonb WHERE session_id=$4::uuid AND user_id=$5 AND status='active'",current_index,json.dumps(clean_answers),json.dumps(questions),session_id,uid)
    return {"ok":True,"current_index":current_index}

@app.get("/api/test/{session_id}/resume")
async def test_resume(session_id: str, request: Request):
    user=await authenticated_user(request); uid=int(user["id"])
    s=await db_fetchrow("SELECT * FROM test_sessions WHERE session_id=$1 AND user_id=$2",session_id,uid)
    if not s: return json_error("Session topilmadi",404)
    lang_row=await db_fetchrow("SELECT language FROM users WHERE user_id=$1",uid)
    lang=lang_row["language"] if lang_row and lang_row["language"] in TRANSLATIONS else "uz"
    questions=normalize_test_questions(s["questions"],s["test_type"],lang)
    if s["status"]=="active" and s["expires_at"] < datetime.now(timezone.utc):
        await db_execute("UPDATE test_sessions SET status='expired' WHERE session_id=$1::uuid AND user_id=$2 AND status='active'",session_id,uid)
        return {"ok":True,"status":"expired","test_type":s["test_type"],"questions":questions,"answers":s["answers"],"current_index":int(s["current_index"] or 0)}
    current_index=max(0,min(int(s["current_index"] or 0),len(questions)-1))
    await db_execute("UPDATE test_sessions SET questions=$1::jsonb,current_index=$2 WHERE session_id=$3::uuid AND user_id=$4",json.dumps(questions),current_index,session_id,uid)
    return {"ok":True,"status":s["status"],"test_type":s["test_type"],"questions":questions,"answers":s["answers"],"current_index":current_index,"started_at":s["started_at"].isoformat(),"expires_at":s["expires_at"].isoformat()}

@app.get("/api/result/{attempt_id}")
async def get_result(attempt_id:int,request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    a=await get_owned_attempt(uid,attempt_id)
    if not a: return json_error("Natija topilmadi",404)
    if not a["result_visible"]: return {"ok":True,"visible":False,"payment_status":a["payment_status"]}
    if a["test_type"] == "IQ":
        try:
            await ensure_and_send_iq_certificate(uid, int(a["id"]))
        except Exception:
            logger.exception("Result certificate self-heal failed for user %s attempt %s", uid, attempt_id)
    question_count = 18 if a["test_type"] == "IQ" else 6
    correct_count = int(a["correct_count"] or 0)
    duration = max(0, int(a["duration"] or 0))
    accuracy = round((correct_count / question_count) * 100) if question_count else 0
    avg_time = round(duration / question_count, 1) if question_count and duration else 0
    rank_row = await db_fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE score > $1) + 1 AS position,
            COUNT(*) AS total
        FROM results
        WHERE test_type=$2
    """, int(a["score"] or 0), a["test_type"])
    return {
        "ok":True,
        "visible":True,
        "score":a["score"],
        "level":a["level"],
        "correct_count":correct_count,
        "question_count":question_count,
        "duration":duration,
        "accuracy":accuracy,
        "avg_time":avg_time,
        "ranking_position":int(rank_row["position"]) if rank_row else None,
        "ranking_total":int(rank_row["total"]) if rank_row else 0,
        "test_type":a["test_type"]
    }

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
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin:approve:{payment_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin:reject:{payment_id}"),
            ]
        ])
        sent=await bot.send_document(
            ADMIN_USER_ID,
            tg_file,
            caption=f"💳 <b>Receipt #{payment_id}</b>\nUser: <code>{uid}</code>\nAmount: <b>{p['amount']:,}</b> so‘m\n\nTasdiqlash yoki rad etish:",
            reply_markup=admin_kb,
        )
        file_id=sent.document.file_id if sent.document else None
    else:
        # Backward-compatible path for an existing Telegram file_id.
        try:
            form=await request.form()
            file_id=str(form.get("receipt_file_id") or "").strip() or None
        except Exception:
            file_id=None
    if not file_id: return json_error("Receipt faylini tanlang")
    await db_execute("""
        UPDATE payments
        SET receipt_file_id=$1,status='pending',updated_at=NOW()
        WHERE id=$2 AND user_id=$3
    """,file_id,payment_id,uid)
    if p["attempt_id"]:
        await db_execute("UPDATE test_attempts SET payment_status='pending',result_visible=FALSE WHERE id=$1 AND user_id=$2",p["attempt_id"],uid)
    return {"ok":True,"status":"pending"}

@app.get("/api/payment/mine")
async def my_payments(request:Request):
    user=await authenticated_user(request); uid=int(user["id"])
    rows=await db_fetch("""
        SELECT p.id,p.attempt_id,p.battle_id,p.payment_type,p.amount,p.status,p.receipt_file_id,p.created_at,
               c.card_number,c.holder,c.bank
        FROM payments p
        LEFT JOIN payment_cards c ON c.id=p.card_id
        WHERE p.user_id=$1 ORDER BY p.id DESC LIMIT 20
    """,uid)
    return {"ok":True,"payments":[dict(r) for r in rows]}

async def ensure_and_send_iq_certificate(user_id: int, attempt_id: int):
    """Create the IQ certificate if needed and send it once to the user."""
    attempt = await db_fetchrow("SELECT * FROM test_attempts WHERE id=$1 AND user_id=$2", attempt_id, user_id)
    if not attempt or attempt["test_type"] != "IQ":
        return None
    result_row = await db_fetchrow("SELECT * FROM results WHERE attempt_id=$1", attempt_id)
    user_row = await db_fetchrow("SELECT full_name FROM users WHERE user_id=$1", user_id)
    if not result_row or not user_row or not user_row["full_name"]:
        return None
    existing = await db_fetchrow("SELECT * FROM certificates WHERE result_id=$1", result_row["id"])
    if existing:
        # Approval can create the certificate inside its transaction before this
        # delivery helper runs. Existing certificate rows must still be sent.
        await send_certificate_to_user(user_id, existing, "📜 To‘lov tasdiqlandi — IQ sertifikatingiz tayyor!")
        return existing
    cert = await create_certificate(user_id, result_row["id"], user_row["full_name"], attempt["score"], attempt["level"])
    await send_certificate_to_user(user_id, cert, "📜 To‘lov tasdiqlandi — IQ sertifikatingiz tayyor!")
    return cert

async def approve_payment_record(payment_id:int):
    """Atomically approve a payment while supporting legacy PostgreSQL schemas."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            p=await conn.fetchrow("SELECT * FROM payments WHERE id=$1 FOR UPDATE",payment_id)
            if not p:
                return None, "not_found"
            if p["status"] == "approved":
                return p, "already"
            if p["status"] == "rejected":
                return p, "rejected"

            battle=None
            approved_count=0
            player_count=0
            if p["battle_id"]:
                await conn.execute(
                    "UPDATE battle_players SET payment_id=$1 WHERE battle_id=$2 AND user_id=$3",
                    p["id"],p["battle_id"],p["user_id"]
                )
                battle=await conn.fetchrow("SELECT * FROM battles WHERE id=$1 FOR UPDATE",p["battle_id"])
                approved_count=await conn.fetchval(
                    "SELECT COUNT(*) FROM battle_players bp JOIN payments pay ON pay.id=bp.payment_id WHERE bp.battle_id=$1 AND pay.status='approved'",
                    p["battle_id"]
                )
                player_count=await conn.fetchval(
                    "SELECT COUNT(*) FROM battle_players WHERE battle_id=$1",p["battle_id"]
                )

            if p["attempt_id"]:
                attempt_row=await conn.fetchrow(
                    "SELECT * FROM test_attempts WHERE id=$1 FOR UPDATE",p["attempt_id"]
                )
                if not attempt_row:
                    raise RuntimeError(f"Attempt #{p['attempt_id']} not found for payment #{payment_id}")
                await conn.execute(
                    "UPDATE test_attempts SET payment_status='approved',result_visible=TRUE WHERE id=$1",
                    p["attempt_id"]
                )

                result_row=await conn.fetchrow(
                    "SELECT * FROM results WHERE attempt_id=$1 ORDER BY id LIMIT 1",
                    p["attempt_id"]
                )
                if not result_row:
                    result_row=await conn.fetchrow("""
                        INSERT INTO results(user_id,attempt_id,test_type,score,level)
                        VALUES($1,$2,$3,$4,$5)
                        RETURNING *
                    """,p["user_id"],attempt_row["id"],attempt_row["test_type"],attempt_row["score"],attempt_row["level"])

                if attempt_row["test_type"] == "IQ":
                    user_row=await conn.fetchrow(
                        "SELECT full_name FROM users WHERE user_id=$1",p["user_id"]
                    )
                    if user_row and user_row["full_name"]:
                        cert_row=await conn.fetchrow(
                            "SELECT * FROM certificates WHERE result_id=$1 ORDER BY id LIMIT 1",
                            result_row["id"]
                        )
                        if not cert_row:
                            cert_row=await conn.fetchrow("""
                                INSERT INTO certificates(
                                    user_id,result_id,certificate_id,verification_code,type,full_name,score,level
                                )
                                VALUES($1,$2,$3,$4,'IQ',$5,$6,$7)
                                RETURNING *
                            """,p["user_id"],result_row["id"],
                                "CERT-"+secrets.token_hex(6).upper(),
                                "IQ-"+"".join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6)),
                                user_row["full_name"],attempt_row["score"],attempt_row["level"])

            # Do this last. If anything above fails, the transaction rolls back
            # and the payment remains pending so the admin can retry.
            await conn.execute(
                "UPDATE payments SET status='approved',updated_at=NOW() WHERE id=$1",payment_id
            )
            if p["battle_id"] and battle and player_count == 2 and approved_count + 1 == 2:
                await conn.execute(
                    "UPDATE battles SET status='ready',ready_at=NOW() WHERE id=$1 AND status<>'finished'",
                    p["battle_id"]
                )
            return p, "approved"

@app.post("/api/admin/payment/{payment_id}/approve")
async def admin_approve_payment(payment_id:int,request:Request):
    user=await authenticated_user(request)
    if not await is_admin(int(user["id"])): raise HTTPException(403,"Forbidden")
    p,status=await approve_payment_record(payment_id)
    if not p: return json_error("Payment topilmadi",404)
    if status == "rejected": return json_error("Payment avval rad etilgan",409)
    if status == "already": return {"ok":True,"status":"already"}
    try:
        lang = await get_user_language(int(p["user_id"]))
        msg = {"uz":"✅ To‘lov tasdiqlandi. Mini App’da keyingi bosqich ochildi.","ru":"✅ Оплата подтверждена. Следующий этап открыт в Mini App.","en":"✅ Payment approved. The next step is open in the Mini App."}[lang]
        await bot.send_message(p["user_id"], msg)
    except Exception: logger.exception("Payment notification failed")
    if p["attempt_id"]:
        try:
            await ensure_and_send_iq_certificate(p["user_id"],p["attempt_id"])
        except Exception:
            logger.exception("Paid certificate delivery failed")
    return {"ok":True,"status":"approved"}

@app.post("/api/admin/payment/{payment_id}/reject")
async def admin_reject_payment(payment_id:int,request:Request):
    user=await authenticated_user(request)
    if not await is_admin(int(user["id"])): raise HTTPException(403,"Forbidden")
    p=await db_fetchrow("SELECT * FROM payments WHERE id=$1",payment_id)
    if not p: return json_error("Payment topilmadi",404)
    if p["status"] == "approved": return json_error("Tasdiqlangan paymentni rad etib bo‘lmaydi",409)
    await db_execute("UPDATE payments SET status='rejected',updated_at=NOW() WHERE id=$1",payment_id)
    if p["attempt_id"]:
        await db_execute("UPDATE test_attempts SET payment_status='rejected',result_visible=FALSE WHERE id=$1",p["attempt_id"])
    try:
        lang = await get_user_language(int(p["user_id"]))
        msg = {"uz":"❌ To‘lov tasdiqlanmadi. Receipt rad etildi. Mini App’da Bosh sahifaga qaytishingiz mumkin.","ru":"❌ Оплата не подтверждена. Чек отклонён. Вернитесь на главную в Mini App.","en":"❌ Payment was not approved. The receipt was rejected. You can return to Home in the Mini App."}[lang]
        await bot.send_message(p["user_id"], msg)
    except Exception: logger.exception("Payment rejection notification failed")
    return {"ok":True,"status":"rejected"}

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
        SELECT u.full_name,b.score,b.level
        FROM (
          SELECT DISTINCT ON (user_id) user_id,score,level,created_at
          FROM results
          WHERE test_type='IQ'
          ORDER BY user_id,score DESC,created_at ASC
        ) b
        JOIN users u ON u.user_id=b.user_id
        ORDER BY b.score DESC,b.created_at ASC
        LIMIT 100
    """)
    items=[{"position":i+1,"name":r["full_name"] or "Foydalanuvchi","score":r["score"],"level":r["level"]} for i,r in enumerate(rows)]
    pos=next((x["position"] for x in items if x["name"] and False),None)
    mine=await db_fetchrow("""
        SELECT COUNT(*)+1 AS position FROM (
          SELECT user_id, MAX(score) AS best_score FROM results WHERE test_type='IQ' GROUP BY user_id
        ) ranked
        WHERE best_score > COALESCE((SELECT MAX(score) FROM results WHERE user_id=$1 AND test_type='IQ'),-1)
    """,uid)
    return {"ok":True,"ranking":items,"my_position":mine["position"] if mine else None}

@app.get("/api/stats/live")
async def stats_live(request:Request):
    # Keep the current Mini App session alive for REAL mode. The frontend
    # polls this endpoint every few seconds, so active users remain counted.
    user=await authenticated_user(request)
    await db_execute("UPDATE users SET last_seen=NOW(),updated_at=NOW() WHERE user_id=$1", int(user["id"]))
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
            row=await db_fetchrow("INSERT INTO battles(id,code,created_by,status) VALUES($1,$2,$3,'waiting') RETURNING id,code",str(uuid4()),code,uid)
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
    db_pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=10,command_timeout=30,statement_cache_size=0)
    await migrate()
    webhook_url = PUBLIC_BASE_URL.rstrip("/") + "/telegram/webhook"
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
            allowed_updates=dp.resolve_used_update_types(),
        )
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🧠 IQ TEST BOT", web_app=WebAppInfo(url=WEBAPP_URL + "/app"))
        )
        info = await bot.get_webhook_info()
        logger.info(
            "Telegram webhook configured: url=%s pending=%s last_error=%s",
            info.url, info.pending_update_count, info.last_error_message,
        )
        if info.url != webhook_url:
            raise RuntimeError(f"Telegram webhook URL mismatch: expected={webhook_url!r} actual={info.url!r}")
    except Exception:
        logger.exception("Webhook configuration failed")
        raise
    try:
        yield
    finally:
        logger.info("Shutting down")
        # Keep the webhook registered during Render restarts. The next instance
        # sets the same URL/secret again during startup. Deleting it here creates
        # a needless window where Telegram has nowhere to deliver updates.
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
