import asyncio
import io
import os
import sqlite3
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from PIL import Image, ImageDraw, ImageFont


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ZAKO bot
ZAKO_URL = os.getenv("ZAKO_URL", "https://t.me/zako_tbot")

# Your Telegram ID
ADMIN_IDS = {2109569429}

DB_PATH = "iq_test.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")


# =========================================================
# IQ QUESTION BANK
# =========================================================
#
# weight = difficulty contribution
#
# IMPORTANT:
# This is a ZAKO product score, not a clinically normed IQ.
#

QUESTIONS = [
    {
        "q": (
            "Qaysi belgi ? o‘rniga keladi?\n\n"
            "●  ▲  ●  ▲\n"
            "▲  ●  ▲  ●\n"
            "●  ▲  ●  ?"
        ),
        "options": ["●", "▲", "■", "◆"],
        "answer": 1,
        "weight": 1,
    },

    {
        "q": (
            "Qoidani toping:\n\n"
            "4 → 9\n"
            "6 → 15\n"
            "8 → 21\n"
            "11 → ?"
        ),
        "options": ["27", "30", "32", "33"],
        "answer": 1,
        "weight": 1,
    },

    {
        "q": (
            "Ketma-ketlikni davom ettiring:\n\n"
            "2, 6, 12, 20, 30, ?"
        ),
        "options": ["40", "41", "42", "44"],
        "answer": 2,
        "weight": 1,
    },

    {
        "q": (
            "Har bir qatorda uchinchi guruh "
            "birinchi ikkita guruhdagi shakllarni birlashtiradi.\n\n"
            "○   △   ○△\n"
            "□   ○   □○\n"
            "◇   □   ?"
        ),
        "options": ["◇□", "○□", "◇○", "△□"],
        "answer": 0,
        "weight": 1,
    },

    {
        "q": (
            "Harf ketma-ketligini davom ettiring:\n\n"
            "B, E, I, N, T, ?\n\n"
            "Har safar oldingi harfdan 3, 4, 5, 6, 7 "
            "pozitsiya oldinga yuriladi."
        ),
        "options": ["Y", "Z", "A", "B"],
        "answer": 2,
        "weight": 2,
    },

    {
        "q": (
            "Ketma-ketlikni davom ettiring:\n\n"
            "3, 7, 15, 31, 63, ?"
        ),
        "options": ["95", "111", "127", "129"],
        "answer": 2,
        "weight": 2,
    },

    {
        "q": (
            "Uchta quti bor. Faqat bittasida kalit bor.\n\n"
            "🔴 Qizil: «Kalit ko‘k qutida.»\n"
            "🔵 Ko‘k: «Kalit ko‘k qutida emas.»\n"
            "🟢 Yashil: «Kalit qizil qutida emas.»\n\n"
            "Faqat BITTA yozuv rost.\n\n"
            "Kalit qaysi qutida?"
        ),
        "options": [
            "🔴 Qizil",
            "🔵 Ko‘k",
            "🟢 Yashil",
            "Aniqlab bo‘lmaydi",
        ],
        "answer": 0,
        "weight": 2,
    },

    {
        "q": (
            "Ketma-ketlikdagi keyingi juftlikni toping:\n\n"
            "○ ↑\n"
            "● →\n"
            "○ ↓\n"
            "● ←\n"
            "?"
        ),
        "options": [
            "○ ↑",
            "○ →",
            "● ↑",
            "● ↓",
        ],
        "answer": 0,
        "weight": 3,
    },

    {
        "q": (
            "A, B, C, D, E beshta odam navbatda turibdi.\n\n"
            "• A — B dan oldinda.\n"
            "• B — D dan oldinda.\n"
            "• D — E dan oldinda.\n"
            "• C — A dan keyin.\n\n"
            "Qaysi tartib MUMKIN?"
        ),
        "options": [
            "B–A–D–E–C",
            "A–C–B–D–E",
            "D–A–B–C–E",
            "E–D–B–A–C",
        ],
        "answer": 1,
        "weight": 3,
    },

    {
        "q": (
            "Qoidani toping:\n\n"
            "2   3   8\n"
            "3   4   15\n"
            "4   5   24\n"
            "5   6   ?"
        ),
        "options": ["30", "32", "35", "36"],
        "answer": 2,
        "weight": 3,
    },

    {
        "q": (
            "Har qadamda ikki o‘zgarish bor:\n\n"
            "1. ○ va ● navbat bilan almashadi.\n"
            "2. Yo‘nalish har safar 90° soat strelkasi "
            "bo‘yicha aylanadi.\n\n"
            "○↑ → ●→ → ○↓ → ●← → ?"
        ),
        "options": ["○↑", "○←", "●↑", "●↓"],
        "answer": 0,
        "weight": 4,
    },

    {
        "q": (
            "Kartalarning bir tomonida harf, ikkinchi tomonida son bor.\n\n"
            "[ A ]   [ D ]   [ 4 ]   [ 7 ]\n\n"
            "Qoida:\n"
            "«Agar bir tomonida UNLI harf bo‘lsa, "
            "ikkinchi tomonida JUFT son bo‘lishi kerak.»\n\n"
            "Qoidani tekshirish uchun qaysi kartalarni "
            "albatta ag‘darish kerak?"
        ),
        "options": [
            "A va 4",
            "A va 7",
            "D va 4",
            "D va 7",
        ],
        "answer": 1,
        "weight": 4,
    },

    {
        "q": (
            "Quyidagi belgilarni 5 soniya yodlab oling:\n\n"
            "K — 7 — ▲ — M — 3 — ● — R — 9\n\n"
            "▲ belgisidan UCHTA pozitsiya keyin "
            "nima turgan edi?"
        ),
        "options": ["M", "3", "●", "R"],
        "answer": 2,
        "weight": 4,
    },

    {
        "q": (
            "Mantiqiy xulosa:\n\n"
            "Barcha A lar B.\n"
            "Ba'zi B lar C.\n\n"
            "Shundan «Ba'zi A lar C» degan xulosani "
            "albatta chiqarish mumkinmi?"
        ),
        "options": [
            "Ha, albatta",
            "Yo‘q, ma'lumot yetarli emas",
            "Faqat A lar ko‘p bo‘lsa",
            "Faqat C lar B bo‘lsa",
        ],
        "answer": 1,
        "weight": 4,
    },

    {
        "q": (
            "Ketma-ketlikni davom ettiring:\n\n"
            "4, 9, 19, 39, 79, ?"
        ),
        "options": ["119", "149", "159", "169"],
        "answer": 2,
        "weight": 5,
    },

    {
        "q": (
            "FINAL PUZZLE 🧠\n\n"
            "3, 7, 15, 31, 63, 127, ?\n\n"
            "Har safar oldingi son 2 ga ko‘paytirilib, "
            "1 qo‘shiladi."
        ),
        "options": ["247", "254", "255", "257"],
        "answer": 2,
        "weight": 5,
    },
]


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            attempts INTEGER DEFAULT 0,
            best_score INTEGER,
            best_raw INTEGER,
            best_time INTEGER,
            referrals INTEGER DEFAULT 0,
            cert_claimed INTEGER DEFAULT 0,
            referred_by INTEGER,
            referral_counted INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            raw_score INTEGER,
            iq_score INTEGER,
            correct INTEGER,
            elapsed INTEGER,
            created_at TEXT
        )
        """
    )

    conn.commit()
    return conn


def ensure_user(user_id, first_name, username, referred_by=None):
    conn = get_db()

    existing = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not existing:
        conn.execute(
            """
            INSERT INTO users
            (
                user_id,
                first_name,
                username,
                referred_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                first_name or "",
                username or "",
                referred_by,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET first_name = ?, username = ?
            WHERE user_id = ?
            """,
            (
                first_name or "",
                username or "",
                user_id,
            ),
        )

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT
            user_id,
            first_name,
            username,
            attempts,
            best_score,
            best_raw,
            best_time,
            referrals,
            cert_claimed,
            referred_by,
            referral_counted
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()
    return row


def count_referral_if_needed(user_id):
    """
    Referral is counted only when the referred user starts the IQ test.
    This prevents simple link-opening abuse.
    """
    conn = get_db()

    row = conn.execute(
        """
        SELECT referred_by, referral_counted
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if not row:
        conn.close()
        return

    referred_by, already_counted = row

    if (
        referred_by
        and referred_by != user_id
        and not already_counted
    ):
        conn.execute(
            """
            UPDATE users
            SET referral_counted = 1
            WHERE user_id = ?
            """,
            (user_id,),
        )

        conn.execute(
            """
            UPDATE users
            SET referrals = referrals + 1
            WHERE user_id = ?
            """,
            (referred_by,),
        )

        conn.commit()

    conn.close()


# =========================================================
# SCORING
# =========================================================

def calculate_iq(raw_score):
    max_score = sum(q["weight"] for q in QUESTIONS)

    if max_score <= 0:
        return 40

    ratio = raw_score / max_score

    # ZAKO product-defined score.
    iq = round(40 + ratio * 120)

    return max(40, min(160, iq))


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧠 TESTNI BOSHLASH",
                    callback_data="start_test",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 REYTING",
                    callback_data="ranking",
                ),
                InlineKeyboardButton(
                    text="👤 PROFILIM",
                    callback_data="profile",
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
                    text="🚀 IQ'IMNI RIVOJLANTIRISH",
                    callback_data="zako",
                )
            ],
        ]
    )


def answer_keyboard(index):
    q = QUESTIONS[index]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"A) {q['options'][0]}",
                    callback_data=f"answer:{index}:0",
                ),
                InlineKeyboardButton(
                    text=f"B) {q['options'][1]}",
                    callback_data=f"answer:{index}:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"C) {q['options'][2]}",
                    callback_data=f"answer:{index}:2",
                ),
                InlineKeyboardButton(
                    text=f"D) {q['options'][3]}",
                    callback_data=f"answer:{index}:3",
                ),
            ],
        ]
    )


# =========================================================
# TEST SESSIONS
# =========================================================

sessions = {}


async def send_question(bot, chat_id, user_id, index):
    session = sessions.get(user_id)

    if not session:
        return

    q = QUESTIONS[index]

    elapsed = int(time.time() - session["started_at"])

    text = (
        "🧠 <b>IQ TEST</b>\n\n"
        f"<b>{index + 1} / {len(QUESTIONS)}</b>    "
        f"⏱️ {elapsed // 60:02d}:{elapsed % 60:02d}\n\n"
        f"{q['q']}\n\n"
        "<i>Eng to‘g‘ri javobni tanlang.</i>"
    )

    await bot.send_message(
        chat_id,
        text,
        reply_markup=answer_keyboard(index),
    )


# =========================================================
# FINISH TEST
# =========================================================

async def finish_test(callback: CallbackQuery):
    user_id = callback.from_user.id

    session = sessions.get(user_id)

    if not session:
        await callback.answer(
            "Test sessiyasi topilmadi.",
            show_alert=True,
        )
        return

    elapsed = int(time.time() - session["started_at"])

    raw_score = session["raw_score"]
    correct = session["correct"]

    iq_score = calculate_iq(raw_score)

    conn = get_db()

    old = conn.execute(
        """
        SELECT best_score, best_raw, best_time
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    old_best_score = old[0] if old else None
    old_best_raw = old[1] if old else None
    old_best_time = old[2] if old else None

    new_best_score = (
        iq_score
        if old_best_score is None or iq_score > old_best_score
        else old_best_score
    )

    new_best_raw = (
        raw_score
        if old_best_raw is None or raw_score > old_best_raw
        else old_best_raw
    )

    new_best_time = (
        elapsed
        if old_best_time is None or elapsed < old_best_time
        else old_best_time
    )

    conn.execute(
        """
        UPDATE users
        SET
            attempts = attempts + 1,
            best_score = ?,
            best_raw = ?,
            best_time = ?
        WHERE user_id = ?
        """,
        (
            new_best_score,
            new_best_raw,
            new_best_time,
            user_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO attempts
        (
            user_id,
            raw_score,
            iq_score,
            correct,
            elapsed,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            raw_score,
            iq_score,
            correct,
            elapsed,
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    rank = (
        conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE best_score > ?
            """,
            (iq_score,),
        ).fetchone()[0]
        + 1
    )

    conn.commit()
    conn.close()

    sessions.pop(user_id, None)

    await callback.message.edit_text(
        "🎉 <b>TEST YAKUNLANDI!</b>\n\n"
        "🧠 <b>IQ SCORE</b>\n\n"
        f"<b>{iq_score}</b>\n\n"
        f"📊 Reyting: <b>#{rank}</b>\n"
        f"✅ To‘g‘ri javoblar: <b>{correct}/16</b>\n"
        f"⏱️ Vaqt: <b>{elapsed // 60:02d}:{elapsed % 60:02d}</b>\n\n"
        "<i>Bu ZAKO IQ testi asosida hisoblangan "
        "taxminiy score hisoblanadi.</i>",
        reply_markup=result_keyboard(),
    )


# =========================================================
# CERTIFICATE
# =========================================================

def get_font(size, bold=False):
    paths = [
        (
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
            if bold
            else
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf"
        )
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


async def create_certificate(callback: CallbackQuery, iq_score):
    user = callback.from_user

    image = Image.new(
        "RGB",
        (1400, 900),
        "white",
    )

    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (35, 35, 1365, 865),
        outline="black",
        width=5,
    )

    draw.text(
        (700, 125),
        "ZAKO IQ",
        anchor="mm",
        font=get_font(76, True),
    )

    draw.text(
        (700, 220),
        "IQ TEST NATIJASI",
        anchor="mm",
        font=get_font(40, True),
    )

    draw.text(
        (700, 365),
        f"IQ SCORE  {iq_score}",
        anchor="mm",
        font=get_font(68, True),
    )

    draw.text(
        (700, 485),
        user.first_name or "Foydalanuvchi",
        anchor="mm",
        font=get_font(44, True),
    )

    draw.text(
        (700, 590),
        datetime.now().strftime("%d.%m.%Y"),
        anchor="mm",
        font=get_font(30),
    )

    draw.text(
        (700, 735),
        "ZAKO IQ testining taxminiy natijasi",
        anchor="mm",
        font=get_font(24),
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


# =========================================================
# BOT
# =========================================================

async def main():
    get_db().close()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher()

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    @dp.message(CommandStart())
    async def start_handler(message: Message):
        referred_by = None

        parts = message.text.split(maxsplit=1)

        if len(parts) == 2:
            argument = parts[1]

            if argument.startswith("ref_"):
                try:
                    referred_by = int(argument[4:])
                except ValueError:
                    referred_by = None

        ensure_user(
            user_id=message.from_user.id,
            first_name=message.from_user.first_name,
            username=message.from_user.username,
            referred_by=referred_by,
        )

        await message.answer(
            "🧠 <b>IQ TEST</b>\n\n"
            "16 ta mantiqiy puzzle orqali "
            "o‘zingizni sinab ko‘ring.\n\n"
            "🎯 IQ SCORE\n"
            "🏆 Reyting\n"
            "🎓 Sertifikat\n"
            "🚀 IQ rivojlantirish\n\n"
            "<b>Tayyor bo‘lsangiz, boshlang.</b>",
            reply_markup=main_keyboard(),
        )

    # -----------------------------------------------------
    # START TEST
    # -----------------------------------------------------

    @dp.callback_query(F.data == "start_test")
    async def start_test_handler(callback: CallbackQuery):
        user_id = callback.from_user.id

        ensure_user(
            user_id,
            callback.from_user.first_name,
            callback.from_user.username,
        )

        # Count referral only when test is actually started.
        count_referral_if_needed(user_id)

        sessions[user_id] = {
            "index": 0,
            "raw_score": 0,
            "correct": 0,
            "started_at": time.time(),
        }

        await callback.answer()

        await callback.message.edit_text(
            "🧠 <b>IQ TEST BOSHLANDI</b>\n\n"
            "16 ta puzzle.\n\n"
            "Har savolda A, B, C yoki D javobdan "
            "birini tanlang.\n\n"
            "⏱️ Umumiy vaqt hisoblanadi.\n"
            "Savolga alohida countdown yo‘q."
        )

        await asyncio.sleep(0.5)

        await send_question(
            callback.bot,
            callback.message.chat.id,
            user_id,
            0,
        )

    # -----------------------------------------------------
    # ANSWER
    # -----------------------------------------------------

    @dp.callback_query(F.data.startswith("answer:"))
    async def answer_handler(callback: CallbackQuery):
        user_id = callback.from_user.id

        session = sessions.get(user_id)

        if not session:
            await callback.answer(
                "Test sessiyasi topilmadi. Qaytadan boshlang.",
                show_alert=True,
            )
            return

        try:
            _, index_str, answer_str = callback.data.split(":")
            index = int(index_str)
            selected = int(answer_str)
        except (ValueError, AttributeError):
            await callback.answer(
                "Noto‘g‘ri javob.",
                show_alert=True,
            )
            return

        if index != session["index"]:
            await callback.answer(
                "Bu savol allaqachon javoblangan.",
                show_alert=True,
            )
            return

        question = QUESTIONS[index]

        if selected == question["answer"]:
            session["correct"] += 1
            session["raw_score"] += question["weight"]

            await callback.answer("✅ To‘g‘ri!")
        else:
            await callback.answer("❌ Noto‘g‘ri.")

        session["index"] += 1

        if session["index"] >= len(QUESTIONS):
            await finish_test(callback)
            return

        await send_question(
            callback.bot,
            callback.message.chat.id,
            user_id,
            session["index"],
        )

    # -----------------------------------------------------
    # CERTIFICATE
    # -----------------------------------------------------

    @dp.callback_query(F.data == "certificate")
    async def certificate_handler(callback: CallbackQuery):
        user_id = callback.from_user.id

        row = get_user(user_id)

        if not row:
            await callback.answer(
                "Avval testni ishlang.",
                show_alert=True,
            )
            return

        referrals = row[7]
        best_score = row[4]

        if not best_score:
            await callback.answer(
                "Avval IQ testni ishlang.",
                show_alert=True,
            )
            return

        if referrals < 2:
            me = await callback.bot.get_me()

            referral_link = (
                f"https://t.me/{me.username}"
                f"?start=ref_{user_id}"
            )

            await callback.message.edit_text(
                "🎓 <b>SERTIFIKAT</b>\n\n"
                "Sertifikatingizni <b>bepul</b> olish uchun "
                "2 ta do‘stingizni IQ testga taklif qiling.\n\n"
                f"👥 Takliflar: <b>{referrals}/2</b>\n\n"
                "Do‘stingiz siz yuborgan havola orqali kirib, "
                "<b>testni boshlaganida</b> taklif hisoblanadi.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📤 DO‘STIMGA YUBORISH",
                                url=(
                                    "https://t.me/share/url"
                                    f"?url={referral_link}"
                                    "&text=🧠%20IQ%20testni%20"
                                    "ishlab%20ko‘r!"
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="🔄 TEKSHIRISH",
                                callback_data="certificate",
                            )
                        ],
                    ]
                ),
            )

            await callback.answer()
            return

        conn = get_db()

        conn.execute(
            """
            UPDATE users
            SET cert_claimed = 1
            WHERE user_id = ?
            """,
            (user_id,),
        )

        conn.commit()
        conn.close()

        certificate = await create_certificate(
            callback,
            best_score,
        )

        await callback.message.answer_document(
            BufferedInputFile(
                certificate,
                filename="zako_iq_certificate.png",
            ),
            caption=(
                "🎓 <b>Sertifikatingiz tayyor!</b>\n\n"
                "🧠 IQ SCORE: "
                f"<b>{best_score}</b>\n\n"
                "Do‘stlaringiz bilan ulashing."
            ),
        )

        await callback.answer("🎓 Sertifikat tayyor!")

    # -----------------------------------------------------
    # PAID RETEST
    # -----------------------------------------------------

    @dp.callback_query(F.data == "paid_test")
    async def paid_test_handler(callback: CallbackQuery):
        await callback.answer()

        await callback.message.edit_text(
            "🔄 <b>QAYTA TEST</b>\n\n"
            "Birinchi urinish — bepul.\n"
            "Keyingi urinish — <b>3 000 so‘m</b>.\n\n"
            "💳 To‘lov tizimi tez orada ulanadi.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ ORQAGA",
                            callback_data="back_home",
                        )
                    ]
                ]
            ),
        )

    # -----------------------------------------------------
    # ZAKO
    # -----------------------------------------------------

    @dp.callback_query(F.data == "zako")
    async def zako_handler(callback: CallbackQuery):
        await callback.answer()

        await callback.message.answer(
            "🚀 <b>IQ'INGIZNI RIVOJLANTIRING</b>\n\n"
            "ZAKO'da 30 kunlik IQ challenge "
            "orqali o‘zingizni rivojlantiring.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🧠 ZAKO'GA O‘TISH",
                            url=ZAKO_URL,
                        )
                    ]
                ]
            ),
        )

    # -----------------------------------------------------
    # PROFILE
    # -----------------------------------------------------

    @dp.callback_query(F.data == "profile")
    async def profile_handler(callback: CallbackQuery):
        row = get_user(callback.from_user.id)

        if not row:
            await callback.answer(
                "Avval /start bosing.",
                show_alert=True,
            )
            return

        best_score = row[4] if row[4] else "—"
        attempts = row[3]
        referrals = row[7]
        certificate = "Olingan" if row[8] else "Olinmagan"

        await callback.message.edit_text(
            "👤 <b>PROFILIM</b>\n\n"
            f"🧠 Eng yaxshi IQ: <b>{best_score}</b>\n"
            f"🎯 Urinishlar: <b>{attempts}</b>\n"
            f"👥 Takliflar: <b>{referrals}/2</b>\n"
            f"🎓 Sertifikat: <b>{certificate}</b>",
            reply_markup=main_keyboard(),
        )

        await callback.answer()

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    @dp.callback_query(F.data == "ranking")
    async def ranking_handler(callback: CallbackQuery):
        conn = get_db()

        rows = conn.execute(
            """
            SELECT first_name, username, best_score
            FROM users
            WHERE best_score IS NOT NULL
            ORDER BY best_score DESC, best_time ASC
            LIMIT 10
            """
        ).fetchall()

        conn.close()

        if not rows:
            text = (
                "🏆 <b>REYTING</b>\n\n"
                "Hozircha natijalar yo‘q."
            )
        else:
            lines = ["🏆 <b>REYTING</b>\n"]

            for position, row in enumerate(rows, 1):
                first_name, username, score = row

                if username:
                    name = f"@{username}"
                else:
                    name = first_name or "Foydalanuvchi"

                lines.append(
                    f"{position}. {name} — <b>{score}</b>"
                )

            text = "\n".join(lines)

        await callback.message.edit_text(
            text,
            reply_markup=main_keyboard(),
        )

        await callback.answer()

    # -----------------------------------------------------
    # BACK HOME
    # -----------------------------------------------------

    @dp.callback_query(F.data == "back_home")
    async def back_home_handler(callback: CallbackQuery):
        await callback.answer()

        await callback.message.edit_text(
            "🧠 <b>IQ TEST</b>\n\n"
            "O‘zingizni 16 ta mantiqiy puzzle "
            "orqali sinab ko‘ring.",
            reply_markup=main_keyboard(),
        )

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    @dp.message(Command("admin"))
    async def admin_handler(message: Message):
        if message.from_user.id not in ADMIN_IDS:
            return

        conn = get_db()

        users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        attempts = conn.execute(
            "SELECT COUNT(*) FROM attempts"
        ).fetchone()[0]

        referrals = conn.execute(
            "SELECT COALESCE(SUM(referrals), 0) FROM users"
        ).fetchone()[0]

        conn.close()

        await message.answer(
            "🔐 <b>ADMIN PANEL</b>\n\n"
            f"👥 Users: <b>{users}</b>\n"
            f"🧠 Testlar: <b>{attempts}</b>\n"
            f"📤 Referral: <b>{referrals}</b>"
        )

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    @dp.message()
    async def fallback_handler(message: Message):
        await message.answer(
            "🧠 IQ TEST\n\n"
            "Testni boshlash uchun quyidagi tugmani bosing.",
            reply_markup=main_keyboard(),
        )

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    print("IQ TEST BOT started.")

    await dp.start_polling(bot)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
