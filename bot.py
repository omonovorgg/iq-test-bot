import os
import asyncio
import json
import secrets
import string
import hashlib
import hmac
import time
from pathlib import Path
from urllib.parse import parse_qsl
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    BufferedInputFile,
    WebAppInfo,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from PIL import Image, ImageDraw, ImageFont


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot")
PORT = int(os.getenv("PORT", "10000"))

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is missing")


# =========================================================
# IQ CONFIG
# =========================================================

QUESTIONS_COUNT = 18

# These answers match the 18 questions in app.js.
CORRECT_ANSWERS = (
    1,
    2,
    0,
    2,
    2,
    1,
    0,
    0,
    2,
    2,
    1,
    2,
    1,
    2,
    3,
    1,
    2,
    2,
)

WEIGHTS = (
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    3,
    3,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
)

MAX_RAW = sum(WEIGHTS)


# =========================================================
# APP
# =========================================================

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

app = FastAPI(title="IQ TEST BOT")

if not WEBAPP_DIR.is_dir():
    raise RuntimeError(f"webapp directory not found: {WEBAPP_DIR}")

app.mount(
    "/webapp",
    StaticFiles(directory=str(WEBAPP_DIR), html=True),
    name="webapp",
)

app.mount(
    "/static",
    StaticFiles(directory=str(WEBAPP_DIR)),
    name="static",
)

pool = None


# =========================================================
# DATABASE
# =========================================================

async def db():
    global pool

    if pool is None:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )

    return pool


async def init_db():
    p = await db()

    async with p.acquire() as c:
        await c.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                language TEXT DEFAULT 'uz',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen TIMESTAMPTZ DEFAULT NOW(),
                referrals INT DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS results(
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                test_type TEXT NOT NULL,
                score INT NOT NULL,
                raw_score INT DEFAULT 0,
                total INT DEFAULT 0,
                answers JSONB,
                profile JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS payments(
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                purpose TEXT NOT NULL,
                amount INT NOT NULL,
                status TEXT DEFAULT 'waiting_receipt',
                receipt_file_id TEXT,
                receipt_kind TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                approved_at TIMESTAMPTZ,
                reviewed_by BIGINT,
                consumed BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS battles(
                id BIGSERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                player1 BIGINT REFERENCES users(user_id),
                player2 BIGINT REFERENCES users(user_id),
                status TEXT DEFAULT 'waiting',
                result JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS battle_payments(
                battle_id BIGINT REFERENCES battles(id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(user_id),
                payment_id BIGINT REFERENCES payments(id),
                PRIMARY KEY(battle_id,user_id)
            );

            CREATE TABLE IF NOT EXISTS certificates(
                code TEXT PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                cert_type TEXT NOT NULL,
                data JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ DEFAULT NOW();

            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS consumed BOOLEAN DEFAULT FALSE;

            INSERT INTO settings(key,value)
            VALUES
                ('iq_free','1'),
                ('iq_price','10000'),
                ('iq_retry_price','5000'),
                ('battle_price','7500'),
                ('card_number','9860350148428500'),
                ('card_holder','Omonov M. A.'),
                ('support','@admin')
            ON CONFLICT(key) DO NOTHING;
            """
        )


async def setting(key, default=""):
    p = await db()

    row = await p.fetchrow(
        "SELECT value FROM settings WHERE key=$1",
        key,
    )

    return row["value"] if row else default


async def set_setting(key, value):
    p = await db()

    await p.execute(
        """
        INSERT INTO settings(key,value)
        VALUES($1,$2)
        ON CONFLICT(key)
        DO UPDATE SET value=EXCLUDED.value
        """,
        key,
        str(value),
    )


async def upsert_user(tg):
    p = await db()

    await p.execute(
        """
        INSERT INTO users(
            user_id,
            username,
            first_name,
            last_name,
            last_seen
        )
        VALUES($1,$2,$3,$4,NOW())

        ON CONFLICT(user_id)
        DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_name=EXCLUDED.last_name,
            updated_at=NOW(),
            last_seen=NOW()
        """,
        tg.id,
        tg.username or "",
        tg.first_name or "",
        tg.last_name or "",
    )


# =========================================================
# TELEGRAM MENU
# =========================================================

def main_menu():
    kb = ReplyKeyboardBuilder()

    kb.row(
        KeyboardButton(
            text="🧠 IQ · EQ · PQ testini ishlash",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )

    kb.row(
        KeyboardButton(text="📜 Sertifikatim"),
        KeyboardButton(text="🏆 Reyting"),
    )

    kb.row(
        KeyboardButton(text="💰 Pul ishlash"),
        KeyboardButton(text="ℹ️ Narx va yordam"),
    )

    kb.row(
        KeyboardButton(text="🌐 Til")
    )

    return kb.as_markup(resize_keyboard=True)


LANGS = {
    "uz": "🇺🇿 O‘zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=value,
                    callback_data=f"lang:{key}",
                )
            ]
            for key, value in LANGS.items()
        ]
    )


# =========================================================
# START
# =========================================================

@router.message(CommandStart())
async def start(message: Message):
    await upsert_user(message.from_user)

    p = await db()

    lang = await p.fetchval(
        """
        SELECT language
        FROM users
        WHERE user_id=$1
        """,
        message.from_user.id,
    )

    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1] if len(parts) > 1 else ""

    # Payment deep-link
    if payload.startswith("pay_"):
        try:
            payment_id = int(payload[4:])
            await payment_message(message, payment_id)
            return
        except ValueError:
            pass

    # Referral
    if payload.startswith("ref_"):
        try:
            ref_id = int(payload[4:])

            if ref_id != message.from_user.id:
                await p.execute(
                    """
                    UPDATE users
                    SET referrals=referrals+1
                    WHERE user_id=$1
                    """,
                    ref_id,
                )
        except ValueError:
            pass

    if not lang:
        await message.answer(
            "🌐 Tilni tanlang / Выберите язык / Choose a language:",
            reply_markup=language_keyboard(),
        )
        return

    await message.answer(
        f"""
👋 Salom, <b>{message.from_user.first_name or "do‘st"}!</b>

🧠 <b>IQ TEST BOT</b> — IQ, EQ va prokrastinatsiya testlari

🧠 IQ — mantiqiy fikrlash darajangiz
🎭 EQ — hissiy intellektingiz
⏳ Prokrastinatsiya — ishni keyinga surish odatingiz

⭐ Uchalasini topshirsangiz — to‘liq shaxsiy tahlil ochiladi

📜 Sertifikat shu botga PNG fayl bo‘lib keladi.

👇 Boshlash uchun tugmani bosing
""",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.split(":", 1)[1]

    p = await db()

    await p.execute(
        """
        UPDATE users
        SET language=$1
        WHERE user_id=$2
        """,
        lang,
        callback.from_user.id,
    )

    await callback.message.edit_text(
        "✅ Til saqlandi."
    )

    await callback.message.answer(
        "🧠 <b>IQ TEST BOT</b>\n\nTestni Mini App orqali boshlang.",
        reply_markup=main_menu(),
    )

    await callback.answer()


# =========================================================
# PRICE / HELP
# =========================================================

@router.message(F.text == "ℹ️ Narx va yordam")
async def price_help(message: Message):
    iq_price = int(await setting("iq_price", "10000"))
    retry_price = int(await setting("iq_retry_price", "5000"))
    battle_price = int(await setting("battle_price", "7500"))

    await message.answer(
        f"""
ℹ️ <b>NARX VA YORDAM</b>

🧠 IQ test — {iq_price:,} so‘m
🎭 EQ — IQ dan keyin tekin
⏳ Prokrastinatsiya — EQ dan keyin tekin
⭐ To‘liq tahlil — uchalasidan keyin tekin

🔁 IQ ni qayta ishlash — {retry_price:,} so‘m
⚔️ Do‘st bilan Battle — {battle_price:,} so‘m / ishtirokchi

💳 To‘lovdan keyin chekni botga yuborasiz.
⏱ Tasdiqlash odatda qisqa vaqt ichida amalga oshiriladi.

📜 Sertifikat PNG ko‘rinishida botga keladi.

👤 <b>Qo‘llab-quvvatlash</b>
💬 {await setting("support", "@admin")}
""".replace(",", " ")
    )


# =========================================================
# RANKING
# =========================================================

@router.message(F.text == "🏆 Reyting")
async def ranking(message: Message):
    p = await db()

    rows = await p.fetch(
        """
        SELECT
            u.first_name,
            u.username,
            r.score
        FROM results r
        JOIN users u
            ON u.user_id=r.user_id

        WHERE r.test_type='iq'

        AND r.id IN (
            SELECT MAX(id)
            FROM results
            WHERE test_type='iq'
            GROUP BY user_id
        )

        ORDER BY r.score DESC, r.created_at ASC
        LIMIT 30
        """
    )

    if not rows:
        await message.answer(
            "🏆 Hali reyting shakllanmagan."
        )
        return

    lines = [
        "🏆 <b>IQ REYTING — TOP 30</b>",
        "",
    ]

    for i, row in enumerate(rows, 1):
        name = (
            row["first_name"]
            or row["username"]
            or "Foydalanuvchi"
        )

        lines.append(
            f"{i}. {name} — <b>{row['score']}</b>"
        )

    await message.answer("\n".join(lines))


# =========================================================
# CERTIFICATE SEARCH
# =========================================================

@router.message(F.text == "📜 Sertifikatim")
async def certificate_help(message: Message):
    await message.answer(
        "🔑 Sertifikat kodingizni yuboring.\n\n"
        "Masalan:\n"
        "<code>IQ-A1B2C3</code>"
    )


@router.message(
    F.text.regexp(r"^(IQ|BT)-[A-Z0-9]{6}$")
)
async def certificate_lookup(message: Message):
    code = message.text.strip().upper()

    p = await db()

    row = await p.fetchrow(
        """
        SELECT data, cert_type
        FROM certificates
        WHERE code=$1
        """,
        code,
    )

    if not row:
        await message.answer(
            "❌ Sertifikat topilmadi."
        )
        return

    data = row["data"]

    path = certificate_png(
        data.get("name", "Foydalanuvchi"),
        int(data.get("iq", 0)),
        code,
        row["cert_type"] == "battle",
        data.get("opponent"),
        data.get("opponent_iq"),
    )

    await message.answer_document(
        BufferedInputFile(
            open(path, "rb").read(),
            filename=f"{code}.png",
        ),
        caption=(
            "📜 <b>Sertifikat topildi</b>\n\n"
            f"🔑 <code>{code}</code>"
        ),
    )


# =========================================================
# REFERRAL
# =========================================================

@router.message(F.text == "💰 Pul ishlash")
async def referral(message: Message):
    me = await bot.me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    await message.answer(
        f"""
💰 <b>PUL ISHLASH</b>

Do‘stlaringizni taklif qiling.

🔗 Sizning linkingiz:

<code>{link}</code>

Do‘stlaringiz shu link orqali botga kiradi.
"""
    )


# =========================================================
# LANGUAGE
# =========================================================

@router.message(F.text == "🌐 Til")
async def change_language(message: Message):
    await message.answer(
        "🌐 Tilni tanlang:",
        reply_markup=language_keyboard(),
    )


# =========================================================
# PAYMENT
# =========================================================

async def create_payment(
    user_id,
    purpose,
    amount,
):
    p = await db()

    return await p.fetchval(
        """
        INSERT INTO payments(
            user_id,
            purpose,
            amount
        )
        VALUES($1,$2,$3)
        RETURNING id
        """,
        user_id,
        purpose,
        amount,
    )


async def payment_message(
    message: Message,
    payment_id: int,
):
    p = await db()

    row = await p.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id=$1
        AND user_id=$2
        """,
        payment_id,
        message.from_user.id,
    )

    if not row:
        await message.answer(
            "❌ To‘lov topilmadi."
        )
        return

    amount = row["amount"]

    await message.answer(
        f"""
💳 <b>TO‘LOV</b>

💰 Summa:
<b>{amount:,} so‘m</b>

💳 Karta:
<code>{await setting("card_number")}</code>

👤 Karta egasi:
{await setting("card_holder")}

To‘lovni amalga oshirgach,
chekni shu botga yuboring.
""".replace(",", " "),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 CHEK YUBORISH",
                        callback_data=f"receipt:{payment_id}",
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith("receipt:"))
async def receipt_start(callback: CallbackQuery):
    await callback.message.answer(
        "📸 To‘lov chekini rasm yoki fayl qilib yuboring."
    )

    await callback.answer()


async def save_receipt(
    message: Message,
    file_id: str,
    kind: str,
):
    p = await db()

    row = await p.fetchrow(
        """
        SELECT id
        FROM payments
        WHERE user_id=$1
        AND status='waiting_receipt'
        ORDER BY id DESC
        LIMIT 1
        """,
        message.from_user.id,
    )

    if not row:
        return False

    payment_id = row["id"]

    await p.execute(
        """
        UPDATE payments
        SET
            receipt_file_id=$1,
            receipt_kind=$2,
            status='pending'
        WHERE id=$3
        """,
        file_id,
        kind,
        payment_id,
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"""
💳 <b>YANGI TO‘LOV #{payment_id}</b>

👤 User:
<code>{message.from_user.id}</code>

💰 To‘lov:
{await p.fetchval(
                    "SELECT amount FROM payments WHERE id=$1",
                    payment_id,
                )} so‘m
""",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ TASDIQLASH",
                                callback_data=f"payok:{payment_id}",
                            ),
                            InlineKeyboardButton(
                                text="❌ RAD ETISH",
                                callback_data=f"payno:{payment_id}",
                            ),
                        ]
                    ]
                ),
            )

            if kind == "photo":
                await bot.send_photo(
                    admin_id,
                    file_id,
                )
            else:
                await bot.send_document(
                    admin_id,
                    file_id,
                )

        except Exception as exc:
            print("Admin notification error:", exc)

    return True


@router.message(F.photo)
async def photo_receipt(message: Message):
    ok = await save_receipt(
        message,
        message.photo[-1].file_id,
        "photo",
    )

    if ok:
        await message.answer(
            "✅ Chek qabul qilindi.\n"
            "Admin tasdiqlashini kuting."
        )


@router.message(F.document)
async def document_receipt(message: Message):
    ok = await save_receipt(
        message,
        message.document.file_id,
        "document",
    )

    if ok:
        await message.answer(
            "✅ Chek qabul qilindi.\n"
            "Admin tasdiqlashini kuting."
        )


@router.callback_query(F.data.startswith("payok:"))
async def payment_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return

    payment_id = int(
        callback.data.split(":", 1)[1]
    )

    p = await db()

    row = await p.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE id=$1
        """,
        payment_id,
    )

    if not row:
        await callback.answer(
            "To‘lov topilmadi",
            show_alert=True,
        )
        return

    await p.execute(
        """
        UPDATE payments
        SET
            status='approved',
            approved_at=NOW(),
            reviewed_by=$1
        WHERE id=$2
        """,
        callback.from_user.id,
        payment_id,
    )

    await callback.answer("Tasdiqlandi")

    await callback.message.answer(
        "✅ To‘lov tasdiqlandi."
    )

    try:
        await bot.send_message(
            row["user_id"],
            """
✅ <b>To‘lov tasdiqlandi!</b>

Mini Appga qaytib testni davom ettiring.
""",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("payno:"))
async def payment_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return

    payment_id = int(
        callback.data.split(":", 1)[1]
    )

    p = await db()

    row = await p.fetchrow(
        """
        SELECT user_id
        FROM payments
        WHERE id=$1
        """,
        payment_id,
    )

    await p.execute(
        """
        UPDATE payments
        SET
            status='rejected',
            reviewed_by=$1
        WHERE id=$2
        """,
        callback.from_user.id,
        payment_id,
    )

    await callback.answer("Rad etildi")

    if row:
        try:
            await bot.send_message(
                row["user_id"],
                """
❌ <b>To‘lov rad etildi.</b>

Chekni tekshirib qayta yuboring.
""",
            )
        except Exception:
            pass


# =========================================================
# ADMIN
# =========================================================

class AdminState(StatesGroup):
    user_id = State()
    user_message = State()
    broadcast = State()
    price = State()


def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="adm:stats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 To‘lovlar",
                    callback_data="adm:payments",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Userga xabar",
                    callback_data="adm:user",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="adm:broadcast",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ IQ narxi",
                    callback_data="adm:price",
                )
            ],
        ]
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Ruxsat yo‘q.")
        return

    await message.answer(
        "⚙️ <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    p = await db()

    users = await p.fetchval(
        "SELECT COUNT(*) FROM users"
    )

    active = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE last_seen >
        NOW()-INTERVAL '10 minutes'
        """
    )

    tests = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM results
        WHERE test_type='iq'
        """
    )

    revenue = await p.fetchval(
        """
        SELECT COALESCE(SUM(amount),0)
        FROM payments
        WHERE status='approved'
        """
    )

    await callback.message.edit_text(
        f"""
📊 <b>STATISTIKA</b>

👤 Users: {users}
🟢 Jonli: {active}
🧠 IQ testlar: {tests}
💰 Tushum: {revenue:,} so‘m
""".replace(",", " "),
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "adm:payments")
async def admin_payments(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    p = await db()

    rows = await p.fetch(
        """
        SELECT
            id,
            user_id,
            purpose,
            amount,
            status
        FROM payments
        ORDER BY id DESC
        LIMIT 20
        """
    )

    if not rows:
        text = "💳 <b>TO‘LOVLAR</b>\n\nHali to‘lov yo‘q."
    else:
        lines = ["💳 <b>TO‘LOVLAR</b>", ""]

        for row in rows:
            lines.append(
                f"#{row['id']} | "
                f"{row['user_id']} | "
                f"{row['amount']} so‘m | "
                f"{row['status']}"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "adm:price")
async def admin_price_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    if callback.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(
        AdminState.price
    )

    await callback.message.answer(
        "💰 Yangi IQ narxini so‘mda yuboring."
    )

    await callback.answer()


@router.message(AdminState.price)
async def admin_price_receive(
    message: Message,
    state: FSMContext,
):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not (message.text or "").isdigit():
        await message.answer(
            "Faqat raqam yuboring."
        )
        return

    await set_setting(
        "iq_price",
        int(message.text),
    )

    await state.clear()

    await message.answer(
        "✅ IQ narxi yangilandi."
    )


@router.callback_query(F.data == "adm:user")
async def admin_user_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    if callback.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(
        AdminState.user_id
    )

    await callback.message.answer(
        "👤 User ID yuboring."
    )

    await callback.answer()


@router.message(AdminState.user_id)
async def admin_user_id(
    message: Message,
    state: FSMContext,
):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not (message.text or "").isdigit():
        await message.answer(
            "ID raqam bo‘lishi kerak."
        )
        return

    await state.update_data(
        uid=int(message.text)
    )

    await state.set_state(
        AdminState.user_message
    )

    await message.answer(
        "💬 Endi xabarni yuboring."
    )


@router.message(AdminState.user_message)
async def admin_user_message(
    message: Message,
    state: FSMContext,
):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()

    try:
        await message.copy_to(
            data["uid"]
        )

        await message.answer(
            "✅ Xabar yuborildi."
        )

    except Exception as exc:
        await message.answer(
            f"❌ Yuborilmadi: {exc}"
        )

    await state.clear()


@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    if callback.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(
        AdminState.broadcast
    )

    await callback.message.answer(
        "📢 Broadcast xabarini yuboring."
    )

    await callback.answer()


@router.message(AdminState.broadcast)
async def admin_broadcast(
    message: Message,
    state: FSMContext,
):
    if message.from_user.id not in ADMIN_IDS:
        return

    p = await db()

    rows = await p.fetch(
        "SELECT user_id FROM users"
    )

    ok = 0
    failed = 0

    for row in rows:
        try:
            await message.copy_to(
                row["user_id"]
            )
            ok += 1
        except Exception:
            failed += 1

        await asyncio.sleep(0.03)

    await state.clear()

    await message.answer(
        f"""
📢 <b>Broadcast tugadi</b>

✅ {ok}
❌ {failed}
"""
    )


# =========================================================
# CERTIFICATE
# =========================================================

def font(size, bold=False):
    path = (
        "/usr/share/fonts/truetype/dejavu/"
        + (
            "DejaVuSans-Bold.ttf"
            if bold
            else "DejaVuSans.ttf"
        )
    )

    if os.path.exists(path):
        return ImageFont.truetype(
            path,
            size,
        )

    return ImageFont.load_default()


def certificate_png(
    name,
    iq,
    code,
    battle=False,
    opponent=None,
    opponent_iq=None,
):
    width = 1600
    height = 1000

    image = Image.new(
        "RGB",
        (width, height),
        (8, 10, 24),
    )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (25, 25, width - 25, height - 25),
        35,
        outline=(185, 130, 255),
        width=5,
    )

    draw.text(
        (800, 105),
        "IQ TEST BOT",
        anchor="ma",
        font=font(48, True),
        fill=(200, 190, 230),
    )

    draw.text(
        (800, 205),
        "BATTLE G‘OLIBI"
        if battle
        else "SERTIFIKAT",
        anchor="ma",
        font=font(76, True),
        fill=(245, 215, 145),
    )

    draw.text(
        (800, 365),
        name,
        anchor="ma",
        font=font(60, True),
        fill=(245, 245, 250),
    )

    draw.text(
        (800, 510),
        str(iq),
        anchor="ma",
        font=font(135, True),
        fill=(255, 255, 255),
    )

    if battle:
        draw.text(
            (800, 660),
            f"{iq}  —  {opponent_iq}",
            anchor="ma",
            font=font(55, True),
            fill=(195, 120, 255),
        )

        draw.text(
            (800, 760),
            "🏆 G‘ALABA",
            anchor="ma",
            font=font(48, True),
            fill=(245, 215, 145),
        )

    else:
        draw.text(
            (800, 690),
            "IQ-style product score",
            anchor="ma",
            font=font(30),
            fill=(185, 190, 210),
        )

    draw.text(
        (800, 870),
        f"Sertifikat kodi: {code}",
        anchor="ma",
        font=font(27),
        fill=(180, 185, 205),
    )

    path = f"/tmp/{code}.png"

    image.save(path)

    return path


async def make_certificate(
    user_id,
    name,
    iq,
    battle=False,
    opponent=None,
    opponent_iq=None,
):
    prefix = "BT-" if battle else "IQ-"

    code = (
        prefix
        + "".join(
            secrets.choice(
                string.ascii_uppercase
                + string.digits
            )
            for _ in range(6)
        )
    )

    p = await db()

    await p.execute(
        """
        INSERT INTO certificates(
            code,
            user_id,
            cert_type,
            data
        )
        VALUES(
            $1,
            $2,
            $3,
            $4::jsonb
        )
        """,
        code,
        user_id,
        "battle" if battle else "iq",
        json.dumps(
            {
                "name": name,
                "iq": iq,
                "opponent": opponent,
                "opponent_iq": opponent_iq,
            }
        ),
    )

    return code


# =========================================================
# TELEGRAM INIT DATA
# =========================================================

def validate_init_data(init_data):
    if not init_data:
        raise HTTPException(
            401,
            "Telegram initData required",
        )

    try:
        data = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = data.pop(
            "hash",
            None,
        )

        auth_date = int(
            data.get(
                "auth_date",
                "0",
            )
        )

        if (
            not received_hash
            or auth_date <= 0
            or abs(
                int(time.time())
                - auth_date
            ) > 86400
        ):
            raise ValueError()

        check_string = "\n".join(
            f"{key}={value}"
            for key, value
            in sorted(data.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash,
        ):
            raise ValueError()

        user = json.loads(
            data["user"]
        )

        return user

    except Exception as exc:
        raise HTTPException(
            401,
            "Invalid Telegram initData",
        ) from exc


async def api_user(
    init_data,
):
    user = validate_init_data(
        init_data
    )

    p = await db()

    await p.execute(
        """
        INSERT INTO users(
            user_id,
            first_name,
            username,
            last_name,
            last_seen
        )
        VALUES(
            $1,$2,$3,$4,NOW()
        )

        ON CONFLICT(user_id)
        DO UPDATE SET
            last_seen=NOW(),
            updated_at=NOW(),
            first_name=EXCLUDED.first_name,
            username=EXCLUDED.username,
            last_name=EXCLUDED.last_name
        """,
        user["id"],
        user.get("first_name", ""),
        user.get("username", ""),
        user.get("last_name", ""),
    )

    return user


# =========================================================
# WEB ROOT
# =========================================================

@app.get("/")
async def root():
    return FileResponse(
        WEBAPP_DIR / "index.html"
    )


@app.get("/app")
async def app_page():
    return FileResponse(
        WEBAPP_DIR / "index.html"
    )


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "iq-test-bot",
    }


# =========================================================
# CONFIG
# =========================================================

@app.get("/api/config")
async def api_config(
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    await api_user(
        x_telegram_init_data
    )

    return {
        "bot_username": BOT_USERNAME,
        "price_uzs": int(
            await setting(
                "iq_price",
                "10000",
            )
        ),
        "retry_price_uzs": int(
            await setting(
                "iq_retry_price",
                "5000",
            )
        ),
        "battle_price_uzs": int(
            await setting(
                "battle_price",
                "7500",
            )
        ),
        "iq_free": (
            await setting(
                "iq_free",
                "1",
            )
            == "1"
        ),
        "question_count": QUESTIONS_COUNT,
    }


# =========================================================
# REAL ACTIVE COUNTER
# =========================================================

@app.get("/api/counter")
async def api_counter(
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    await api_user(
        x_telegram_init_data
    )

    p = await db()

    count = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE last_seen >
        NOW()-INTERVAL '10 minutes'
        """
    )

    return {
        "active": max(
            1,
            int(count or 0),
        )
    }


# =========================================================
# IQ ACCESS
# =========================================================

@app.get("/api/access/iq")
async def api_access_iq(
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    p = await db()

    attempts = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM results
        WHERE user_id=$1
        AND test_type='iq'
        """,
        user["id"],
    )

    free_enabled = (
        await setting(
            "iq_free",
            "1",
        )
        == "1"
    )

    paid_retry = await p.fetchval(
        """
        SELECT EXISTS(
            SELECT 1
            FROM payments
            WHERE user_id=$1
            AND purpose='iq_retry'
            AND status='approved'
            AND consumed=FALSE
        )
        """,
        user["id"],
    )

    return {
        "allowed": (
            free_enabled
            and attempts == 0
        ) or bool(paid_retry),

        "first_free": (
            free_enabled
            and attempts == 0
        ),
    }


# =========================================================
# PAYMENT CREATE
# =========================================================

@app.post("/api/payment/create")
async def api_payment_create(
    payload: dict,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    purpose = str(
        payload.get(
            "purpose",
            "retest",
        )
    ).strip()

    if purpose in {
        "retest",
        "result",
    }:
        internal_purpose = "iq_retry"

        amount = int(
            await setting(
                "iq_retry_price",
                "5000",
            )
        )

    elif purpose == "battle":
        internal_purpose = "battle"

        amount = int(
            await setting(
                "battle_price",
                "7500",
            )
        )

    else:
        raise HTTPException(
            400,
            "Invalid payment purpose",
        )

    payment_id = await create_payment(
        user["id"],
        internal_purpose,
        amount,
    )

    me = await bot.me()

    bot_link = (
        f"https://t.me/{me.username}"
        f"?start=pay_{payment_id}"
    )

    return {
        "payment_id": payment_id,
        "amount": amount,
        "bot_link": bot_link,
    }


# Compatibility endpoint
@app.post("/api/payment/start")
async def api_payment_start(
    payload: dict,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    purpose = payload.get(
        "product_code",
        "retest",
    )

    return await api_payment_create(
        {
            "purpose": purpose,
        },
        x_telegram_init_data,
    )


# =========================================================
# PAYMENT STATUS
# =========================================================

@app.get("/api/payment/{payment_id}")
async def api_payment_status(
    payment_id: int,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    p = await db()

    row = await p.fetchrow(
        """
        SELECT
            id,
            status,
            amount,
            purpose
        FROM payments
        WHERE id=$1
        AND user_id=$2
        """,
        payment_id,
        user["id"],
    )

    if not row:
        raise HTTPException(
            404,
            "Payment not found",
        )

    return dict(row)


@app.get("/api/payment/status/{payment_id}")
async def api_payment_status_old(
    payment_id: int,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    return await api_payment_status(
        payment_id,
        x_telegram_init_data,
    )


# =========================================================
# TEST SUBMIT
# =========================================================

@app.post("/api/test/submit")
async def api_test_submit(
    payload: dict,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    test_type = str(
        payload.get(
            "test_type",
            "iq",
        )
    )

    answers = payload.get(
        "answers",
        [],
    )

    profile = payload.get(
        "profile",
        {},
    )

    battle_id = payload.get(
        "battle_id"
    )

    try:
        answers = [
            int(x)
            for x in answers
        ]
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            400,
            "Invalid answers",
        ) from exc

    # -----------------------------------------------------
    # IQ
    # -----------------------------------------------------

    if test_type == "iq":
        if (
            len(answers)
            != QUESTIONS_COUNT
        ):
            raise HTTPException(
                409,
                "Test incomplete",
            )

        if any(
            x < 0 or x > 3
            for x in answers
        ):
            raise HTTPException(
                400,
                "Invalid answer",
            )

        p = await db()

        attempts = await p.fetchval(
            """
            SELECT COUNT(*)
            FROM results
            WHERE user_id=$1
            AND test_type='iq'
            """,
            user["id"],
        )

        paid_payment = await p.fetchrow(
            """
            SELECT id
            FROM payments
            WHERE user_id=$1
            AND purpose='iq_retry'
            AND status='approved'
            AND consumed=FALSE
            ORDER BY id
            LIMIT 1
            """,
            user["id"],
        )

        free_enabled = (
            await setting(
                "iq_free",
                "1",
            )
            == "1"
        )

        allowed = (
            free_enabled
            and attempts == 0
        ) or bool(paid_payment)

        if not allowed:
            raise HTTPException(
                402,
                "PAYMENT_REQUIRED",
            )

        raw_score = sum(
            WEIGHTS[i]
            for i, answer
            in enumerate(answers)
            if answer
            == CORRECT_ANSWERS[i]
        )

        correct = sum(
            answer
            == CORRECT_ANSWERS[i]
            for i, answer
            in enumerate(answers)
        )

        score = round(
            40
            + (
                raw_score
                / MAX_RAW
            )
            * 120
        )

        if paid_payment:
            await p.execute(
                """
                UPDATE payments
                SET consumed=TRUE
                WHERE id=$1
                """,
                paid_payment["id"],
            )

        total = QUESTIONS_COUNT

    # -----------------------------------------------------
    # EQ
    # -----------------------------------------------------

    elif test_type == "eq":
        if len(answers) != 12:
            raise HTTPException(
                409,
                "Test incomplete",
            )

        p = await db()

        iq_done = await p.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM results
                WHERE user_id=$1
                AND test_type='iq'
            )
            """,
            user["id"],
        )

        if not iq_done:
            raise HTTPException(
                403,
                "LOCKED",
            )

        raw_score = sum(
            3 - x
            for x in answers
        )

        correct = sum(
            x == 0
            for x in answers
        )

        score = round(
            70
            + (
                raw_score / 36
            )
            * 70
        )

        total = 12

    # -----------------------------------------------------
    # PQ
    # -----------------------------------------------------

    elif test_type == "pq":
        if len(answers) != 12:
            raise HTTPException(
                409,
                "Test incomplete",
            )

        p = await db()

        eq_done = await p.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM results
                WHERE user_id=$1
                AND test_type='eq'
            )
            """,
            user["id"],
        )

        if not eq_done:
            raise HTTPException(
                403,
                "LOCKED",
            )

        raw_score = sum(
            3 - x
            for x in answers
        )

        correct = sum(
            x == 0
            for x in answers
        )

        score = round(
            70
            + (
                raw_score / 36
            )
            * 70
        )

        total = 12

    else:
        raise HTTPException(
            400,
            "Unknown test type",
        )

    # -----------------------------------------------------
    # SAVE RESULT
    # -----------------------------------------------------

    p = await db()

    await p.execute(
        """
        INSERT INTO results(
            user_id,
            test_type,
            score,
            raw_score,
            total,
            answers,
            profile
        )
        VALUES(
            $1,
            $2,
            $3,
            $4,
            $5,
            $6::jsonb,
            $7::jsonb
        )
        """,
        user["id"],
        test_type,
        score,
        raw_score,
        total,
        json.dumps(answers),
        json.dumps(
            profile
            if isinstance(profile, dict)
            else {}
        ),
    )

    # -----------------------------------------------------
    # IQ CERTIFICATE
    # -----------------------------------------------------

    certificate_code = None

    if test_type == "iq":
        name = (
            profile.get("fullName")
            if isinstance(profile, dict)
            else None
        ) or user.get(
            "first_name"
        ) or "Foydalanuvchi"

        certificate_code = (
            await make_certificate(
                user["id"],
                name,
                score,
            )
        )

        try:
            path = certificate_png(
                name,
                score,
                certificate_code,
            )

            await bot.send_document(
                user["id"],
                BufferedInputFile(
                    open(
                        path,
                        "rb",
                    ).read(),
                    filename=(
                        certificate_code
                        + ".png"
                    ),
                ),
                caption=(
                    "📜 <b>IQ sertifikatingiz tayyor!</b>\n\n"
                    f"🔑 <code>{certificate_code}</code>"
                ),
            )

        except Exception as exc:
            print(
                "Certificate delivery warning:",
                exc,
            )

    # -----------------------------------------------------
    # BATTLE
    # -----------------------------------------------------

    battle_finished = False

    if (
        battle_id
        and test_type == "iq"
    ):
        battle_finished = await finish_battle(
            int(battle_id)
        )

    rank = await p.fetchval(
        """
        SELECT COUNT(*) + 1
        FROM results
        WHERE test_type='iq'
        AND score>$1
        """,
        score,
    )

    return {
        "score": score,
        "iq": score,
        "raw_score": raw_score,
        "correct": correct,
        "total": total,
        "rank": int(
            rank or 1
        ),
        "certificate_code": certificate_code,
        "battle_finished": battle_finished,
    }


# =========================================================
# BATTLE
# =========================================================

async def finish_battle(
    battle_id,
):
    p = await db()

    battle = await p.fetchrow(
        """
        SELECT *
        FROM battles
        WHERE id=$1
        """,
        battle_id,
    )

    if (
        not battle
        or battle["status"] != "ready"
        or not battle["player2"]
    ):
        return False

    r1 = await p.fetchrow(
        """
        SELECT score
        FROM results
        WHERE user_id=$1
        AND test_type='iq'
        AND created_at >= $2
        ORDER BY id DESC
        LIMIT 1
        """,
        battle["player1"],
        battle["created_at"],
    )

    r2 = await p.fetchrow(
        """
        SELECT score
        FROM results
        WHERE user_id=$1
        AND test_type='iq'
        AND created_at >= $2
        ORDER BY id DESC
        LIMIT 1
        """,
        battle["player2"],
        battle["created_at"],
    )

    if not r1 or not r2:
        return False

    score1 = r1["score"]
    score2 = r2["score"]

    winner = (
        battle["player1"]
        if score1 > score2
        else battle["player2"]
        if score2 > score1
        else None
    )

    result = {
        "player1": score1,
        "player2": score2,
        "winner": winner,
    }

    await p.execute(
        """
        UPDATE battles
        SET
            status='finished',
            result=$1::jsonb
        WHERE id=$2
        """,
        json.dumps(result),
        battle_id,
    )

    players = [
        (
            battle["player1"],
            score1,
            score2,
            battle["player2"],
        ),
        (
            battle["player2"],
            score2,
            score1,
            battle["player1"],
        ),
    ]

    for (
        user_id,
        my_score,
        opponent_score,
        opponent_id,
    ) in players:

        if winner == user_id:
            user_row = await p.fetchrow(
                """
                SELECT first_name
                FROM users
                WHERE user_id=$1
                """,
                user_id,
            )

            opponent_row = await p.fetchrow(
                """
                SELECT first_name
                FROM users
                WHERE user_id=$1
                """,
                opponent_id,
            )

            name = (
                user_row["first_name"]
                if user_row
                else "Foydalanuvchi"
            )

            opponent_name = (
                opponent_row["first_name"]
                if opponent_row
                else "Do‘st"
            )

            code = await make_certificate(
                user_id,
                name,
                my_score,
                True,
                opponent_name,
                opponent_score,
            )

            path = certificate_png(
                name,
                my_score,
                code,
                True,
                opponent_name,
                opponent_score,
            )

            try:
                await bot.send_document(
                    user_id,
                    BufferedInputFile(
                        open(
                            path,
                            "rb",
                        ).read(),
                        filename=code + ".png",
                    ),
                    caption=(
                        "🏆 <b>Battle g‘alaba sertifikati</b>\n\n"
                        f"🔑 <code>{code}</code>"
                    ),
                )
            except Exception:
                pass

            try:
                await bot.send_message(
                    user_id,
                    f"""
🏆 <b>BATTLE YAKUNLANDI!</b>

🧠 Siz: <b>{my_score}</b>
🧠 Do‘stingiz: <b>{opponent_score}</b>

🏆 <b>SIZ G‘OLIB BO‘LDINGIZ!</b>
""",
                )
            except Exception:
                pass

        else:
            try:
                if winner is None:
                    text = f"""
⚔️ <b>BATTLE YAKUNLANDI!</b>

Siz: <b>{my_score}</b>
Do‘stingiz: <b>{opponent_score}</b>

🤝 <b>DURANG</b>
"""
                else:
                    text = f"""
⚔️ <b>BATTLE YAKUNLANDI!</b>

Siz: <b>{my_score}</b>
Do‘stingiz: <b>{opponent_score}</b>

🏆 G‘olib do‘stingiz.
"""

                await bot.send_message(
                    user_id,
                    text,
                )

            except Exception:
                pass

    return True


@app.post("/api/battle/create")
async def battle_create(
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    p = await db()

    code = "".join(
        secrets.choice(
            string.digits
        )
        for _ in range(4)
    )

    battle_id = await p.fetchval(
        """
        INSERT INTO battles(
            code,
            player1
        )
        VALUES($1,$2)
        RETURNING id
        """,
        code,
        user["id"],
    )

    price = int(
        await setting(
            "battle_price",
            "7500",
        )
    )

    payment_id = await create_payment(
        user["id"],
        "battle",
        price,
    )

    await p.execute(
        """
        INSERT INTO battle_payments(
            battle_id,
            user_id,
            payment_id
        )
        VALUES($1,$2,$3)
        """,
        battle_id,
        user["id"],
        payment_id,
    )

    return {
        "battle_id": battle_id,
        "code": code,
        "payment_required": True,
        "payment_id": payment_id,
    }


@app.post("/api/battle/join")
async def battle_join(
    payload: dict,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    code = str(
        payload.get(
            "code",
            "",
        )
    ).strip()

    p = await db()

    battle = await p.fetchrow(
        """
        SELECT *
        FROM battles
        WHERE code=$1
        """,
        code,
    )

    if not battle:
        raise HTTPException(
            404,
            "Battle code not found",
        )

    if (
        battle["player2"]
        and battle["player2"]
        != user["id"]
    ):
        raise HTTPException(
            409,
            "Battle full",
        )

    await p.execute(
        """
        UPDATE battles
        SET player2=$1
        WHERE id=$2
        """,
        user["id"],
        battle["id"],
    )

    price = int(
        await setting(
            "battle_price",
            "7500",
        )
    )

    payment_id = await create_payment(
        user["id"],
        "battle",
        price,
    )

    await p.execute(
        """
        INSERT INTO battle_payments(
            battle_id,
            user_id,
            payment_id
        )
        VALUES($1,$2,$3)
        ON CONFLICT DO NOTHING
        """,
        battle["id"],
        user["id"],
        payment_id,
    )

    return {
        "battle_id": battle["id"],
        "code": code,
        "payment_required": True,
        "payment_id": payment_id,
    }


@app.get("/api/battle/{battle_id}")
async def battle_state(
    battle_id: int,
    x_telegram_init_data: str = Header(
        default=""
    ),
):
    user = await api_user(
        x_telegram_init_data
    )

    p = await db()

    battle = await p.fetchrow(
        """
        SELECT *
        FROM battles
        WHERE id=$1
        """,
        battle_id,
    )

    if (
        not battle
        or user["id"]
        not in (
            battle["player1"],
            battle["player2"],
        )
    ):
        raise HTTPException(
            404,
            "Battle not found",
        )

    approved_payments = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM battle_payments bp
        JOIN payments p
            ON p.id=bp.payment_id
        WHERE bp.battle_id=$1
        AND p.status='approved'
        """,
        battle_id,
    )

    if (
        approved_payments >= 2
        and battle["player2"]
    ):
        await p.execute(
            """
            UPDATE battles
            SET status='ready'
            WHERE id=$1
            AND status='waiting'
            """,
            battle_id,
        )

        battle = await p.fetchrow(
            """
            SELECT *
            FROM battles
            WHERE id=$1
            """,
            battle_id,
        )

    return {
        "id": battle["id"],
        "code": battle["code"],
        "status": battle["status"],
        "player1": battle["player1"],
        "player2": battle["player2"],
        "result": battle["result"],
    }


# =========================================================
# START
# =========================================================

async def main():
    await init_db()

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot),
    )


if __name__ == "__main__":
    asyncio.run(main())