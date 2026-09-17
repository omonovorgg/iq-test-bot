import os
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from io import BytesIO

import asyncpg
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from PIL import Image, ImageDraw, ImageFont
import uvicorn


# =========================
# ENV
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ZAKO_URL = os.getenv("ZAKO_URL", "https://t.me/zako_tbot")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is missing")


def clean_db_url(url: str) -> str:
    parts = urlsplit(url)

    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in {"sslmode", "channel_binding"}
    ]

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


DB_URL = clean_db_url(DATABASE_URL)

pool = None
BOT_USERNAME = ""


# =========================
# FASTAPI
# =========================

app = FastAPI(title="IQ TEST BOT")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "IQ TEST BOT",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# =========================
# QUESTIONS
# =========================

QUESTIONS = [
    {
        "q": "1/16\n\nQaysi belgi ketma-ketlikni davom ettiradi?\n\n● ▲ ● ▲\n▲ ● ▲ ●\n● ▲ ?",
        "options": ["●", "▲", "■", "◆"],
        "answer": 1,
        "weight": 1,
    },
    {
        "q": "2/16\n\n4 → 9\n6 → 15\n8 → 21\n11 → ?",
        "options": ["27", "30", "32", "33"],
        "answer": 1,
        "weight": 1,
    },
    {
        "q": "3/16\n\nSonlar ketma-ketligini davom ettiring:\n\n2, 6, 12, 20, 30, ?",
        "options": ["40", "41", "42", "44"],
        "answer": 2,
        "weight": 1,
    },
    {
        "q": "4/16\n\nQaysi variant naqshni to‘g‘ri davom ettiradi?\n\n○ △ ○ △\n□ ○ □ ○\n◇ □ ?",
        "options": ["◇ □", "○ □", "◇ ○", "△ □"],
        "answer": 0,
        "weight": 1,
    },
    {
        "q": "5/16\n\nHarflar ketma-ketligini davom ettiring:\n\nB, E, I, N, T, ?",
        "options": ["Y", "Z", "A", "B"],
        "answer": 2,
        "weight": 2,
    },
    {
        "q": "6/16\n\n3, 7, 15, 31, 63, ?",
        "options": ["95", "111", "127", "129"],
        "answer": 2,
        "weight": 2,
    },
    {
        "q": "7/16\n\n3 ta quti bor: QIZIL, KO‘K, YASHIL.\n\nFaqat bittasidagi yozuv rost:\n\nQizil: “Kalit ko‘k qutida.”\nKo‘k: “Kalit ko‘k qutida emas.”\nYashil: “Kalit qizil qutida emas.”\n\nKalit qaysi qutida?",
        "options": ["Qizil", "Ko‘k", "Yashil", "Aniqlab bo‘lmaydi"],
        "answer": 0,
        "weight": 2,
    },
    {
        "q": "8/16\n\nBelgilar har safar 90° ga buriladi va rang navbat bilan o‘zgaradi:\n\n○↑ → ●→ → ○↓ → ●← → ?",
        "options": ["○↑", "○→", "●↑", "●↓"],
        "answer": 0,
        "weight": 3,
    },
    {
        "q": "9/16\n\nA B dan oldin.\nB D dan oldin.\nD E dan oldin.\nC A dan keyin.\n\nQaysi tartib mumkin?",
        "options": [
            "B-A-D-E-C",
            "A-C-B-D-E",
            "D-A-B-C-E",
            "E-D-B-A-C",
        ],
        "answer": 1,
        "weight": 3,
    },
    {
        "q": "10/16\n\n2 × 3 + 2 = 8\n3 × 4 + 3 = 15\n4 × 5 + 4 = 24\n5 × 6 + 5 = ?",
        "options": ["30", "32", "35", "36"],
        "answer": 2,
        "weight": 3,
    },
    {
        "q": "11/16\n\nQaysi son yetishmayapti?\n\n1, 4, 10, 22, 46, ?",
        "options": ["82", "90", "94", "96"],
        "answer": 2,
        "weight": 4,
    },
    {
        "q": "12/16\n\nQoida:\nAgar karta old tomonida UNLI harf bo‘lsa,\norqa tomonida JUFT son bo‘lishi kerak.\n\nKartalar: A, D, 4, 7.\n\nQoidani tekshirish uchun qaysi kartalarni albatta ag‘darish kerak?",
        "options": [
            "Faqat A",
            "A va 7",
            "D va 4",
            "4 va 7",
        ],
        "answer": 1,
        "weight": 4,
    },
    {
        "q": "13/16\n\nKetma-ketlik:\n\nK — 7 — ▲ — M — 3 — ● — R — 9\n\n▲ belgisidan 3 ta o‘rin keyin nima turibdi?",
        "options": ["M", "3", "●", "R"],
        "answer": 2,
        "weight": 4,
    },
    {
        "q": "14/16\n\nBarcha A lar B.\nBa’zi B lar C.\n\nQaysi xulosa majburiy ravishda to‘g‘ri?",
        "options": [
            "Ba’zi A lar C",
            "Ba’zi A lar C ekanini aniqlab bo‘lmaydi",
            "Barcha C lar A",
            "Barcha B lar A",
        ],
        "answer": 1,
        "weight": 4,
    },
    {
        "q": "15/16\n\n4, 9, 19, 39, 79, ?",
        "options": ["149", "159", "169", "179"],
        "answer": 1,
        "weight": 5,
    },
    {
        "q": "16/16\n\n3, 7, 15, 31, 63, 127, ?",
        "options": ["191", "223", "255", "257"],
        "answer": 2,
        "weight": 5,
    },
]


MAX_RAW = sum(q["weight"] for q in QUESTIONS)


def calculate_iq(raw_score: int) -> int:
    ratio = raw_score / MAX_RAW
    return round(40 + ratio * 120)


def format_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


# =========================
# KEYBOARDS
# =========================

def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧠 IQ TESTNI BOSHLASH",
                    callback_data="start_test",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 REYTING",
                    callback_data="ranking",
                ),
                InlineKeyboardButton(
                    text="👤 PROFIL",
                    callback_data="profile",
                ),
            ],
        ]
    )


def answer_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="A",
                    callback_data="ans:0",
                ),
                InlineKeyboardButton(
                    text="B",
                    callback_data="ans:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="C",
                    callback_data="ans:2",
                ),
                InlineKeyboardButton(
                    text="D",
                    callback_data="ans:3",
                ),
            ],
        ]
    )


def result_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎓 SERTIFIKAT OLISH",
                    callback_data="certificate",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 QAYTA TEST — 3 000 so‘m",
                    callback_data="paid_test",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 REYTING",
                    callback_data="ranking",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 IQ'IMNI RIVOJLANTIRISH",
                    url=ZAKO_URL,
                )
            ],
        ]
    )


def invite_keyboard(user_id: int):
    username = BOT_USERNAME or "iqtestuzbot"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 DO‘STLARNI TAKLIF QILISH",
                    url=f"https://t.me/{username}?start=ref_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 BOSH MENYU",
                    callback_data="home",
                )
            ],
        ]
    )


# =========================
# DATABASE
# =========================

async def init_db():
    global pool

    pool = await asyncpg.create_pool(
        dsn=DB_URL,
        min_size=1,
        max_size=5,
        ssl="require",
        command_timeout=30,
    )

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                first_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER,
                best_raw INTEGER,
                best_time INTEGER,
                referrals INTEGER NOT NULL DEFAULT 0,
                cert_claimed BOOLEAN NOT NULL DEFAULT FALSE,
                referred_by BIGINT,
                referral_counted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,
                raw_score INTEGER NOT NULL,
                iq_score INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                elapsed INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_users_best_score
            ON users(best_score DESC NULLS LAST);

            CREATE INDEX IF NOT EXISTS idx_attempts_user_id
            ON attempts(user_id);
            """
        )


async def ensure_user(message: Message, referral_id=None):
    assert pool is not None

    user = message.from_user

    first_name = user.first_name or ""
    username = user.username or ""

    if referral_id == user.id:
        referral_id = None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                first_name,
                username,
                referred_by
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id)
            DO UPDATE SET
                first_name = EXCLUDED.first_name,
                username = EXCLUDED.username
            """,
            user.id,
            first_name,
            username,
            referral_id,
        )


async def count_referral_if_needed(user_id: int):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            row = await conn.fetchrow(
                """
                SELECT referred_by, referral_counted
                FROM users
                WHERE user_id = $1
                FOR UPDATE
                """,
                user_id,
            )

            if not row:
                return

            referrer_id = row["referred_by"]
            already_counted = row["referral_counted"]

            if not referrer_id:
                return

            if already_counted:
                return

            if referrer_id == user_id:
                return

            referrer_exists = await conn.fetchval(
                """
                SELECT 1
                FROM users
                WHERE user_id = $1
                """,
                referrer_id,
            )

            if not referrer_exists:
                return

            await conn.execute(
                """
                UPDATE users
                SET referral_counted = TRUE
                WHERE user_id = $1
                """,
                user_id,
            )

            await conn.execute(
                """
                UPDATE users
                SET referrals = referrals + 1
                WHERE user_id = $1
                """,
                referrer_id,
            )


async def get_user(user_id: int):
    assert pool is not None

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )


async def save_attempt(
    user_id: int,
    raw_score: int,
    iq_score: int,
    correct: int,
    elapsed: int,
):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            await conn.execute(
                """
                INSERT INTO attempts (
                    user_id,
                    raw_score,
                    iq_score,
                    correct,
                    elapsed
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                raw_score,
                iq_score,
                correct,
                elapsed,
            )

            await conn.execute(
                """
                UPDATE users
                SET
                    attempts = attempts + 1,

                    best_score = CASE
                        WHEN best_score IS NULL
                             OR $2 > best_score
                        THEN $2
                        ELSE best_score
                    END,

                    best_raw = CASE
                        WHEN best_score IS NULL
                             OR $2 > best_score
                        THEN $3
                        ELSE best_raw
                    END,

                    best_time = CASE
                        WHEN best_score IS NULL
                             OR $2 > best_score
                             OR (
                                 $2 = best_score
                                 AND (
                                     best_time IS NULL
                                     OR $5 < best_time
                                 )
                             )
                        THEN $5
                        ELSE best_time
                    END

                WHERE user_id = $1
                """,
                user_id,
                iq_score,
                raw_score,
                correct,
                elapsed,
            )


async def get_rank(user_id: int):
    assert pool is not None

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT best_score, best_time
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )

        if not row or row["best_score"] is None:
            return None

        best_time = row["best_time"]

        if best_time is None:
            best_time = 2147483647

        rank = await conn.fetchval(
            """
            SELECT COUNT(*) + 1
            FROM users
            WHERE best_score IS NOT NULL
              AND (
                  best_score > $1
                  OR (
                      best_score = $1
                      AND COALESCE(best_time, 2147483647) < $2
                  )
              )
            """,
            row["best_score"],
            best_time,
        )

        return int(rank)


async def get_top_users(limit=10):
    assert pool is not None

    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
                first_name,
                username,
                best_score,
                best_time
            FROM users
            WHERE best_score IS NOT NULL
            ORDER BY
                best_score DESC,
                best_time ASC NULLS LAST,
                created_at ASC
            LIMIT $1
            """,
            limit,
        )


# =========================
# CERTIFICATE
# =========================

def get_font(size: int, bold=False):
    if bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def create_certificate(name: str, iq: int) -> bytes:
    width = 1200
    height = 800

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    title_font = get_font(62, True)
    score_font = get_font(110, True)
    normal_font = get_font(34)
    small_font = get_font(25)

    def centered(text, y, font):
        box = draw.textbbox((0, 0), text, font=font)
        text_width = box[2] - box[0]
        x = (width - text_width) // 2
        draw.text(
            (x, y),
            text,
            fill="black",
            font=font,
        )

    draw.rectangle(
        (30, 30, width - 30, height - 30),
        outline="black",
        width=5,
    )

    draw.rectangle(
        (50, 50, width - 50, height - 50),
        outline="black",
        width=2,
    )

    centered("ZAKO IQ", 105, title_font)
    centered("IQ TEST NATIJASI", 195, normal_font)
    centered(f"IQ SCORE  {iq}", 285, score_font)
    centered(name[:35], 450, title_font)

    centered(
        "ZAKO IQ testining taxminiy natijasi",
        560,
        normal_font,
    )

    centered(
        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        625,
        small_font,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


# =========================
# TEST SESSIONS
# =========================

user_sessions = {}

dp = Dispatcher()


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):

    args = message.text.split(maxsplit=1)

    referral_id = None

    if len(args) > 1:
        payload = args[1].strip()

        if payload.startswith("ref_"):
            try:
                referral_id = int(payload[4:])
            except ValueError:
                referral_id = None

    await ensure_user(
        message,
        referral_id,
    )

    await count_referral_if_needed(
        message.from_user.id
    )

    text = (
        "🧠 IQ TEST BOT\n\n"
        "16 ta mantiqiy savol orqali o‘zingizni sinab ko‘ring.\n\n"
        "• Birinchi test — BEPUL\n"
        "• 16 ta savol\n"
        "• IQ SCORE\n"
        "• Vaqt natijasi\n"
        "• Real reyting\n"
        "• Sertifikat\n\n"
        "Tayyor bo‘lsangiz, boshlang."
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
    )


# =========================
# HOME
# =========================

@dp.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):

    await callback.answer()

    await callback.message.edit_text(
        "🧠 IQ TEST BOT\n\n"
        "Testni boshlash uchun tugmani bosing.",
        reply_markup=main_keyboard(),
    )


# =========================
# START TEST
# =========================

@dp.callback_query(F.data == "start_test")
async def start_test_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    await callback.answer()

    await ensure_user(callback.message)

    if user_id in user_sessions:
        await callback.message.edit_text(
            "Sizda allaqachon boshlangan test bor.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="▶️ DAVOM ETISH",
                            callback_data="continue_test",
                        )
                    ]
                ]
            ),
        )
        return

    user = await get_user(user_id)

    if user and user["attempts"] > 0:
        await callback.message.edit_text(
            "Siz birinchi bepul testingizni allaqachon topshirgansiz.\n\n"
            "Keyingi test narxi: 3 000 so‘m.",
            reply_markup=result_keyboard(),
        )
        return

    user_sessions[user_id] = {
        "index": 0,
        "raw": 0,
        "correct": 0,
        "started_at": asyncio.get_running_loop().time(),
    }

    await send_question(
        callback.message,
        user_id,
    )


@dp.callback_query(F.data == "continue_test")
async def continue_test(callback: CallbackQuery):

    await callback.answer()

    user_id = callback.from_user.id

    if user_id not in user_sessions:
        await callback.message.edit_text(
            "Test sessiyasi topilmadi.\n\n"
            "Yangi testni boshlang.",
            reply_markup=main_keyboard(),
        )
        return

    await send_question(
        callback.message,
        user_id,
    )


# =========================
# SEND QUESTION
# =========================

async def send_question(
    message: Message,
    user_id: int,
):
    session = user_sessions.get(user_id)

    if not session:
        return

    index = session["index"]

    question = QUESTIONS[index]

    elapsed = int(
        asyncio.get_running_loop().time()
        - session["started_at"]
    )

    header = (
        f"{index + 1:02d}/16 • "
        f"{format_time(elapsed)}"
    )

    text = (
        f"{header}\n\n"
        f"{question['q']}"
    )

    await message.edit_text(
        text,
        reply_markup=answer_keyboard(),
    )


# =========================
# ANSWER
# =========================

@dp.callback_query(F.data.startswith("ans:"))
async def answer_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    session = user_sessions.get(user_id)

    if not session:
        await callback.answer(
            "Test sessiyasi topilmadi.",
            show_alert=True,
        )
        return

    try:
        selected = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "Xato javob.",
            show_alert=True,
        )
        return

    index = session["index"]

    question = QUESTIONS[index]

    if selected == question["answer"]:
        session["raw"] += question["weight"]
        session["correct"] += 1

    session["index"] += 1

    await callback.answer()

    if session["index"] >= len(QUESTIONS):

        await finish_test(
            callback.message,
            user_id,
        )

    else:

        await send_question(
            callback.message,
            user_id,
        )


# =========================
# FINISH TEST
# =========================

async def finish_test(
    message: Message,
    user_id: int,
):

    session = user_sessions.pop(
        user_id,
        None,
    )

    if not session:
        return

    elapsed = int(
        asyncio.get_running_loop().time()
        - session["started_at"]
    )

    iq = calculate_iq(
        session["raw"]
    )

    await save_attempt(
        user_id=user_id,
        raw_score=session["raw"],
        iq_score=iq,
        correct=session["correct"],
        elapsed=elapsed,
    )

    rank = await get_rank(user_id)

    if rank:
        rank_text = f"🏆 Reyting: #{rank}"
    else:
        rank_text = "🏆 Reyting: —"

    text = (
        "🧠 TEST YAKUNLANDI!\n\n"
        f"🎯 IQ SCORE: {iq}\n"
        f"✅ To‘g‘ri javoblar: "
        f"{session['correct']}/16\n"
        f"⏱ Vaqt: {format_time(elapsed)}\n"
        f"{rank_text}\n\n"
        "Natija ZAKO IQ testining "
        "taxminiy mahsulot skoridir."
    )

    await message.edit_text(
        text,
        reply_markup=result_keyboard(),
    )


# =========================
# CERTIFICATE
# =========================

@dp.callback_query(F.data == "certificate")
async def certificate_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    user_id = callback.from_user.id

    user = await get_user(user_id)

    if not user or user["best_score"] is None:
        await callback.message.answer(
            "Avval IQ testini topshiring.",
            reply_markup=main_keyboard(),
        )
        return

    if user["cert_claimed"]:
        await callback.message.answer(
            "Siz sertifikatni oldin olgansiz.",
            reply_markup=result_keyboard(),
        )
        return

    if user["referrals"] < 2:

        remaining = 2 - user["referrals"]

        await callback.message.answer(
            "🎓 Sertifikat bepul.\n\n"
            f"Sertifikatni olish uchun yana "
            f"{remaining} ta real taklif kerak.\n\n"
            "Taklif qilingan odam botga kirib, "
            "testni boshlashi kerak.",
            reply_markup=invite_keyboard(user_id),
        )
        return

    certificate = create_certificate(
        user["first_name"] or "Foydalanuvchi",
        user["best_score"],
    )

    assert pool is not None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET cert_claimed = TRUE
            WHERE user_id = $1
            """,
            user_id,
        )

    await callback.message.answer_document(
        BufferedInputFile(
            certificate,
            filename="zako_iq_certificate.png",
        ),
        caption=(
            f"🎓 IQ SCORE: {user['best_score']}\n\n"
            "ZAKO IQ sertifikati."
        ),
    )


# =========================
# PAID TEST
# =========================

@dp.callback_query(F.data == "paid_test")
async def paid_test_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    await callback.message.answer(
        "🔄 QAYTA TEST\n\n"
        "Narxi: 3 000 so‘m.\n\n"
        "To‘lov tizimi hali ulanmagan. "
        "Keyingi bosqichda qo‘shamiz.",
        reply_markup=main_keyboard(),
    )


# =========================
# RANKING
# =========================

@dp.callback_query(F.data == "ranking")
async def ranking_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    rows = await get_top_users(10)

    if not rows:

        await callback.message.edit_text(
            "🏆 REYTING\n\n"
            "Hali natijalar yo‘q.",
            reply_markup=main_keyboard(),
        )
        return

    lines = ["🏆 REYTING\n"]

    for i, row in enumerate(rows, start=1):

        name = (
            row["first_name"]
            or "Foydalanuvchi"
        )

        score = row["best_score"]

        lines.append(
            f"{i}. {name[:20]} — IQ {score}"
        )

    lines.append(
        "\n📌 Reyting real test natijalari asosida."
    )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=main_keyboard(),
    )


# =========================
# PROFILE
# =========================

@dp.callback_query(F.data == "profile")
async def profile_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    user = await get_user(
        callback.from_user.id
    )

    if not user:

        await callback.message.edit_text(
            "Profil topilmadi.",
            reply_markup=main_keyboard(),
        )
        return

    best = (
        user["best_score"]
        if user["best_score"] is not None
        else "—"
    )

    rank = await get_rank(
        callback.from_user.id
    )

    rank_text = (
        f"#{rank}"
        if rank
        else "—"
    )

    text = (
        "👤 PROFIL\n\n"
        f"🧠 Eng yaxshi IQ: {best}\n"
        f"🏆 Reyting: {rank_text}\n"
        f"📝 Testlar: {user['attempts']}\n"
        f"👥 Takliflar: {user['referrals']}\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================
# WEB SERVER
# =========================

async def run_web():

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server = uvicorn.Server(config)

    await server.serve()


# =========================
# MAIN
# =========================

async def main():

    global BOT_USERNAME

    await init_db()

    bot = Bot(
        token=BOT_TOKEN
    )

    me = await bot.get_me()

    BOT_USERNAME = me.username or ""

    print(
        f"Bot started: @{BOT_USERNAME}"
    )

    try:

        await asyncio.gather(
            dp.start_polling(bot),
            run_web(),
        )

    finally:

        await bot.session.close()

        if pool is not None:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
