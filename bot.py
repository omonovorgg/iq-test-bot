
import os
import asyncio
import secrets
import string
import json
import hashlib
import hmac
import time
from urllib.parse import parse_qsl, unquote
from pathlib import Path
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
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
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup, WebAppInfo, BufferedInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
PORT = int(os.getenv("PORT", "10000"))

# The frontend currently contains exactly 18 IQ questions. The backend is the
# source of truth for scoring so a client cannot submit a forged raw_score.
IQ_QUESTION_COUNT = 18
IQ_CORRECT_ANSWERS = (
    0, 0, 0, 0, 1, 2, 0, 0, 2, 0, 0, 2, 0, 1, 1, 1, 2, 1
)
IQ_WEIGHTS = (1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5, 6, 6, 7)
IQ_MAX_RAW = sum(IQ_WEIGHTS)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is missing")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

app = FastAPI(title="IQTestPro")

if not WEBAPP_DIR.is_dir():
    raise RuntimeError(f"webapp directory not found: {WEBAPP_DIR}")

# Canonical Mini App path. Use an absolute filesystem path so Render does not
# depend on its current working directory.
app.mount(
    "/webapp",
    StaticFiles(directory=str(WEBAPP_DIR), html=True),
    name="webapp",
)

# Compatibility path for older frontend/payment code.
app.mount(
    "/static",
    StaticFiles(directory=str(WEBAPP_DIR)),
    name="static",
)

pool: asyncpg.Pool | None = None

LANGS = {"uz": "🇺🇿 O‘zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

PRODUCT_DEFAULTS = {
    "iq": ("🧠 IQ test", True, 10000),
    "eq": ("🎭 EQ", False, 0),
    "pq": ("⏳ Prokrastinatsiya", False, 0),
    "full": ("⭐ To‘liq tahlil", False, 0),
    "iq_retry": ("🔁 IQ qayta topshirish", True, 5000),
    "eq_retry": ("🔁 EQ qayta topshirish", True, 5000),
    "pq_retry": ("🔁 PQ qayta topshirish", True, 5000),
    "battle": ("⚔️ Do‘st bilan Battle", True, 7500),
}

def now():
    return datetime.now(timezone.utc)

async def db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, command_timeout=30)
    return pool

async def init_db():
    p = await db()
    async with p.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'uz',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products(
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            price INTEGER DEFAULT 0,
            retry_days INTEGER DEFAULT 5
        );
        CREATE TABLE IF NOT EXISTS test_results(
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            test_type TEXT NOT NULL,
            score INTEGER NOT NULL,
            raw_score INTEGER,
            total INTEGER,
            profile JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS payments(
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            product_code TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'waiting_receipt',
            receipt_file_id TEXT,
            receipt_kind TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            approved_at TIMESTAMPTZ,
            rejected_at TIMESTAMPTZ
        );
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ;
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS reviewed_by BIGINT;
        CREATE TABLE IF NOT EXISTS certificates(
            code TEXT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            cert_type TEXT NOT NULL,
            data JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS battles(
            id BIGSERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            player1 BIGINT REFERENCES users(id),
            player2 BIGINT REFERENCES users(id),
            status TEXT DEFAULT 'waiting',
            result JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS battle_payments(
            battle_id BIGINT REFERENCES battles(id) ON DELETE CASCADE,
            user_id BIGINT REFERENCES users(id),
            payment_id BIGINT REFERENCES payments(id),
            PRIMARY KEY(battle_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS progress(
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            test_type TEXT NOT NULL,
            answers JSONB DEFAULT '[]',
            current_index INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY(user_id,test_type)
        );
        """)
        for code, (title, enabled, price) in PRODUCT_DEFAULTS.items():
            await c.execute("""
                INSERT INTO products(code,title,enabled,price)
                VALUES($1,$2,$3,$4)
                ON CONFLICT(code) DO NOTHING
            """, code, title, enabled, price)
        await c.execute("""
            INSERT INTO settings(key,value) VALUES
            ('card_number','9860350148428500'),
            ('card_holder','Omonov M. A.'),
            ('click_info','Click orqali kartaga o‘tkazma qilishingiz mumkin.'),
            ('support','@admin'),
            ('iq_first_test_free','1')
            ON CONFLICT(key) DO NOTHING
        """)

async def upsert_user(tg):
    p = await db()
    await p.execute("""
        INSERT INTO users(id,username,first_name,last_name,last_seen)
        VALUES($1,$2,$3,$4,NOW())
        ON CONFLICT(id) DO UPDATE SET
          username=EXCLUDED.username,
          first_name=EXCLUDED.first_name,
          last_name=EXCLUDED.last_name,
          last_seen=NOW()
    """, tg.id, tg.username, tg.first_name, tg.last_name)

async def get_setting(key, default=""):
    p = await db()
    row = await p.fetchrow("SELECT value FROM settings WHERE key=$1", key)
    return row["value"] if row else default

async def set_setting(key, value):
    p = await db()
    await p.execute("""
        INSERT INTO settings(key,value) VALUES($1,$2)
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
    """, key, str(value))

async def product(code):
    p = await db()
    return await p.fetchrow("SELECT * FROM products WHERE code=$1", code)

def main_menu(lang="uz"):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="🧠 IQ · EQ · PQ testini ishlash", web_app=WebAppInfo(url=WEBAPP_URL)))
    kb.row(KeyboardButton(text="📜 Sertifikatim"), KeyboardButton(text="🏆 Reyting"))
    kb.row(KeyboardButton(text="💰 Pul ishlash"), KeyboardButton(text="ℹ️ Narx va yordam"))
    kb.row(KeyboardButton(text="🌐 Til"))
    return kb.as_markup(resize_keyboard=True)

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANGS["uz"], callback_data="lang:uz")],
        [InlineKeyboardButton(text=LANGS["ru"], callback_data="lang:ru")],
        [InlineKeyboardButton(text=LANGS["en"], callback_data="lang:en")],
    ])

@router.message(CommandStart())
async def start(message: Message):
    await upsert_user(message.from_user)
    p = await db()
    row = await p.fetchrow("SELECT language FROM users WHERE id=$1", message.from_user.id)
    if not row or not row["language"]:
        await message.answer("🌐 Tilni tanlang / Выберите язык / Choose a language:", reply_markup=lang_kb())
        return
    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name or 'do‘st'}!</b>\n\n"
        "🧠 <b>IQTestPro</b> — IQ, EQ va prokrastinatsiya testlari\n\n"
        "🧠 IQ — mantiqiy fikrlash darajangiz\n"
        "🎭 EQ — hissiy intellektingiz\n"
        "⏳ Prokrastinatsiya — ishni keyinga surish odatingiz\n\n"
        "⭐ Uchalasini topshirsangiz — to‘liq shaxsiy tahlil ochiladi\n"
        "📜 Sertifikat shu yerga PNG fayl bo‘lib keladi.\n\n"
        "👇 Boshlash uchun tugmani bosing",
        reply_markup=main_menu()
    )

@router.callback_query(F.data.startswith("lang:"))
async def language(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    p = await db()
    await p.execute("UPDATE users SET language=$1 WHERE id=$2", lang, callback.from_user.id)
    await callback.message.edit_text("✅ Til saqlandi.")
    await callback.message.answer(
        "👋 Xush kelibsiz!\n\n🧠 IQTestPro testlarini boshlashingiz mumkin.",
        reply_markup=main_menu(lang)
    )
    await callback.answer()

@router.message(F.text == "ℹ️ Narx va yordam")
async def prices(message: Message):
    p = await db()
    rows = await p.fetch("SELECT * FROM products ORDER BY code")
    labels = {r["code"]: r for r in rows}
    def line(code, text, free_text=None):
        r = labels.get(code)
        if not r or not r["enabled"] or r["price"] == 0:
            return text + (f" — {free_text}" if free_text else " — tekin")
        return f"{text} — {r['price']:,}".replace(",", " ") + " so‘m"
    support = await get_setting("support", "@admin")
    text = (
        "ℹ️ <b>NARX VA YORDAM</b>\n\n"
        f"{line('iq','🧠 IQ test')}\n"
        f"{line('eq','🎭 EQ','IQ dan keyin tekin')}\n"
        f"{line('pq','⏳ Prokrastinatsiya','EQ dan keyin tekin')}\n"
        f"{line('full','⭐ To‘liq tahlil','uchalasidan keyin tekin')}\n\n"
        f"{line('iq_retry','🔁 IQ ni 2-marta ishlash')}\n"
        f"{line('eq_retry','🔁 EQ / PQ ni qayta ishlash','5 kundan keyin tekin')}\n"
        f"{line('battle','⚔️ Do‘st bilan battle')}\n\n"
        "💳 To‘lov Click yoki karta orqali\n"
        "⏱ To‘lov 1–2 daqiqada tasdiqlanadi\n"
        "🏆 Tasdiqlangach natija o‘zi ochiladi\n"
        "📜 Sertifikat shu botga PNG fayl bo‘lib keladi\n\n"
        "🔑 Sertifikat kodingizni (IQ-XXXXX) shu yerga yozsangiz — topib beramiz\n\n"
        f"👤 <b>QO‘LLAB-QUVVATLASH</b>\n💬 {support}"
    )
    await message.answer(text)

@router.message(F.text == "🌐 Til")
async def change_language(message: Message):
    await message.answer("🌐 Tilni tanlang:", reply_markup=lang_kb())

@router.message(F.text == "🏆 Reyting")
async def ranking(message: Message):
    p = await db()
    rows = await p.fetch("""
      SELECT u.first_name,u.username,r.score
      FROM test_results r JOIN users u ON u.id=r.user_id
      WHERE r.test_type='iq'
      AND r.id IN (SELECT MAX(id) FROM test_results WHERE test_type='iq' GROUP BY user_id)
      ORDER BY r.score DESC, r.created_at ASC LIMIT 30
    """)
    lines = ["🏆 <b>IQ REYTING — TOP 30</b>\n"]
    for i,r in enumerate(rows,1):
        name = r["first_name"] or r["username"] or "Foydalanuvchi"
        lines.append(f"{i}. {name} — <b>{r['score']}</b>")
    await message.answer("\n".join(lines) if len(lines)>1 else "🏆 Hali reyting shakllanmagan.")

@router.message(F.text == "📜 Sertifikatim")
async def cert_search_help(message: Message):
    await message.answer("🔑 Sertifikat kodingizni yuboring.\nMasalan: <code>IQ-A1B2C3</code>")

@router.message(F.text.regexp(r"^(IQ|BT)-[A-Z0-9]{6}$"))
async def cert_lookup(message: Message):
    code = message.text.strip().upper()
    p = await db()
    row = await p.fetchrow("SELECT data FROM certificates WHERE code=$1", code)
    if not row:
        await message.answer("❌ Bunday sertifikat topilmadi.")
        return
    try:
        data = row["data"]
        path = make_certificate(data.get("name","Foydalanuvchi"), int(data.get("iq",0)), code)
        await message.answer_document(
            BufferedInputFile(open(path, "rb").read(), filename=f"{code}.png"),
            caption=f"📜 <b>Sertifikat topildi</b>\n\n🔑 <code>{code}</code>"
        )
    except Exception:
        await message.answer(f"✅ Sertifikat topildi.\n\nKod: <code>{code}</code>")

@router.message(F.text == "💰 Pul ishlash")
async def referral(message: Message):
    me = await bot.me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    await message.answer(
        "💰 <b>PUL ISHLASH</b>\n\n"
        "Do‘stlaringizni taklif qiling va referral tizimida ishtirok eting.\n\n"
        f"🔗 Sizning linkingiz:\n<code>{link}</code>\n\n"
        "📊 Statistika keyinroq shu bo‘limda ko‘rsatiladi."
    )

# ---------- Payment ----------

async def create_payment(user_id, product_code, amount=None):
    p = await db()
    r = await p.fetchrow("SELECT price FROM products WHERE code=$1", product_code)
    if not r:
        raise ValueError("Unknown product")
    price = amount if amount is not None else r["price"]
    return await p.fetchval("""
      INSERT INTO payments(user_id,product_code,amount)
      VALUES($1,$2,$3) RETURNING id
    """, user_id, product_code, price)

async def send_payment_message(user_id, payment_id, product_code, amount):
    card = await get_setting("card_number")
    holder = await get_setting("card_holder")
    click = await get_setting("click_info")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Karta raqamini nusxalash", callback_data=f"copycard:{payment_id}")],
        [InlineKeyboardButton(text="📤 Chek yuborish", callback_data=f"receipt:{payment_id}")],
    ])
    await bot.send_message(
        user_id,
        "💳 <b>IQ TEST UCHUN TO‘LOV</b>\n\n"
        f"💰 <b>Summa:</b> {amount:,}".replace(",", " ") + " so‘m\n\n"
        f"💳 <b>Karta:</b>\n<code>{card}</code>\n\n"
        f"👤 <b>Karta egasi:</b> {holder}\n\n"
        f"📱 {click}\n\n"
        "To‘lovni amalga oshirgach, chekni shu botga yuboring.",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("copycard:"))
async def copy_card(callback: CallbackQuery):
    card = await get_setting("card_number")
    await callback.message.answer(f"📋 Karta raqami:\n<code>{card}</code>\n\nNusxalab to‘lovni amalga oshiring.")
    await callback.answer("Karta raqami yuborildi")

@router.callback_query(F.data.startswith("receipt:"))
async def receipt_start(callback: CallbackQuery):
    pid = int(callback.data.split(":")[1])
    p = await db()
    row = await p.fetchrow("SELECT * FROM payments WHERE id=$1 AND user_id=$2", pid, callback.from_user.id)
    if not row:
        await callback.answer("To‘lov topilmadi", show_alert=True)
        return
    await callback.message.answer("📸 To‘lov chekini rasm yoki fayl ko‘rinishida yuboring.")
    await callback.answer()

@router.message(F.photo)
async def photo_receipt(message: Message):
    p = await db()
    row = await p.fetchrow("""
      SELECT * FROM payments WHERE user_id=$1 AND status='waiting_receipt'
      ORDER BY id DESC LIMIT 1
    """, message.from_user.id)
    if not row:
        return
    file_id = message.photo[-1].file_id
    await p.execute("""
      UPDATE payments SET receipt_file_id=$1,receipt_kind='photo' WHERE id=$2
    """, file_id, row["id"])
    await notify_admin_payment(row["id"], message.from_user.id, file_id, "photo")
    await message.answer("✅ Chekingiz qabul qilindi.\n\n⏳ Admin tomonidan tekshirilmoqda.")

@router.message(F.document)
async def document_receipt(message: Message):
    p = await db()
    row = await p.fetchrow("""
      SELECT * FROM payments WHERE user_id=$1 AND status='waiting_receipt'
      ORDER BY id DESC LIMIT 1
    """, message.from_user.id)
    if not row:
        return
    file_id = message.document.file_id
    await p.execute("""
      UPDATE payments SET receipt_file_id=$1,receipt_kind='document' WHERE id=$2
    """, file_id, row["id"])
    await notify_admin_payment(row["id"], message.from_user.id, file_id, "document")
    await message.answer("✅ Chekingiz qabul qilindi.\n\n⏳ Admin tomonidan tekshirilmoqda.")

async def notify_admin_payment(payment_id, user_id, file_id, kind):
    if not ADMIN_IDS:
        return
    p = await db()
    row = await p.fetchrow("""
      SELECT p.*,u.username,u.first_name,u.last_name
      FROM payments p JOIN users u ON u.id=p.user_id WHERE p.id=$1
    """, payment_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To‘lov tushgan", callback_data=f"payok:{payment_id}")],
        [InlineKeyboardButton(text="❌ To‘lov tushmagan", callback_data=f"payno:{payment_id}")],
    ])
    caption = (
        "💳 <b>YANGI TO‘LOV</b>\n\n"
        f"👤 {row['first_name'] or ''} {row['last_name'] or ''}\n"
        f"🆔 <code>{user_id}</code>\n"
        f"💰 {row['amount']:,} so‘m\n"
        f"📦 {row['product_code']}\n"
        f"🕐 {row['created_at']}\n"
    ).replace(",", " ")
    for admin in ADMIN_IDS:
        try:
            if kind == "photo":
                await bot.send_photo(admin, file_id, caption=caption, reply_markup=kb)
            else:
                await bot.send_document(admin, file_id, caption=caption, reply_markup=kb)
        except Exception:
            pass

async def unlock_product(user_id, product_code):
    # Unlock is represented by an approved payment. Test endpoint checks this.
    return True

@router.callback_query(F.data.startswith("payok:"))
async def pay_ok(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return
    pid = int(callback.data.split(":")[1])
    p = await db()
    row = await p.fetchrow("SELECT * FROM payments WHERE id=$1", pid)
    if not row or row["status"] != "waiting_receipt":
        await callback.answer("Bu to‘lov allaqachon ko‘rib chiqilgan.", show_alert=True)
        return
    await p.execute("UPDATE payments SET status='approved',approved_at=NOW() WHERE id=$1", pid)
    if row["product_code"] == "battle":
        bpay = await p.fetchrow("SELECT battle_id FROM battle_payments WHERE payment_id=$1", pid)
        if bpay:
            b = await p.fetchrow("SELECT * FROM battles WHERE id=$1", bpay["battle_id"])
            if b and b["player1"] and b["player2"]:
                await p.execute("UPDATE battles SET status='ready' WHERE id=$1", b["id"])
                await bot.send_message(row["user_id"],
                    f"✅ <b>Battle to‘lovi tasdiqlandi!</b>\n\n⚔️ Battle kodi: <code>{b['code']}</code>\n"
                    "Endi IQ testini boshlang.", reply_markup=main_menu())
            else:
                await bot.send_message(row["user_id"],
                    "✅ <b>Battle to‘lovi tasdiqlandi!</b>\n\n⚔️ Do‘stingiz qo‘shilishini kuting.", reply_markup=main_menu())
        else:
            await bot.send_message(row["user_id"], "✅ Battle to‘lovi tasdiqlandi.", reply_markup=main_menu())
    else:
        await bot.send_message(
            row["user_id"],
            "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
            "🧠 Sizning pullik imkoniyatingiz ochildi. Mini App'ga qaytib davom eting.",
            reply_markup=main_menu()
        )
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Tasdiqlandi")

@router.callback_query(F.data.startswith("payno:"))
async def pay_no(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return
    pid = int(callback.data.split(":")[1])
    p = await db()
    row = await p.fetchrow("SELECT * FROM payments WHERE id=$1", pid)
    if not row or row["status"] != "waiting_receipt":
        await callback.answer("Bu to‘lov allaqachon ko‘rib chiqilgan.", show_alert=True)
        return
    await p.execute("UPDATE payments SET status='rejected',rejected_at=NOW() WHERE id=$1", pid)
    await bot.send_message(row["user_id"],
        "❌ <b>To‘lov tasdiqlanmadi.</b>\n\n"
        "Iltimos, to‘lovni tekshirib, yangi chek yuboring.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Rad etildi")

# ---------- Admin ----------

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Users", callback_data="adm:users")],
        [InlineKeyboardButton(text="💳 To‘lovlar", callback_data="adm:payments")],
        [InlineKeyboardButton(text="💰 Mahsulotlar", callback_data="adm:products")],
        [InlineKeyboardButton(text="🎁 IQ birinchi test", callback_data="adm:iqfree")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats")],
        [InlineKeyboardButton(text="📢 Barchaga xabar", callback_data="adm:broadcast_all")],
        [InlineKeyboardButton(text="💳 Sotib olganlarga xabar", callback_data="adm:broadcast_buyers")],
    ])

@router.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_kb())

@router.callback_query(F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    p = await db()
    users = await p.fetchval("SELECT COUNT(*) FROM users")
    results = await p.fetchval("SELECT COUNT(*) FROM test_results")
    paid = await p.fetchval("SELECT COUNT(*) FROM payments WHERE status='approved'")
    revenue = await p.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'")
    await callback.message.edit_text(
        f"📊 <b>STATISTIKA</b>\n\n👥 Users: {users}\n🧠 Testlar: {results}\n"
        f"💳 To‘lovlar: {paid}\n💰 Daromad: {revenue:,} so‘m".replace(",", " "),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga",callback_data="adm:back")]])
    )
    await callback.answer()

@router.callback_query(F.data == "adm:iqfree")
async def admin_iq_free(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    current = await get_setting("iq_first_test_free", "1") == "1"
    await set_setting("iq_first_test_free", "0" if current else "1")
    state = "🟢 YOQILGAN — birinchi IQ testi bepul" if not current else "🔴 O‘CHIRILGAN — birinchi IQ testi ham pullik"
    await callback.answer("Sozlama yangilandi")
    await callback.message.edit_text(
        f"🎁 <b>IQ birinchi test</b>\n\n{state}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")]])
    )


@router.callback_query(F.data == "adm:products")
async def admin_products(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    p = await db()
    rows = await p.fetch("SELECT * FROM products ORDER BY code")
    b = InlineKeyboardBuilder()
    text = "💰 <b>MAHSULOTLAR</b>\n\n"
    for r in rows:
        status = "🟢" if r["enabled"] else "🔴"
        text += f"{status} {r['title']} — {r['price']:,} so‘m\n".replace(",", " ")
        b.button(text=f"{r['title']}", callback_data=f"prod:{r['code']}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back"))
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("prod:"))
async def admin_product_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    code = callback.data.split(":")[1]
    r = await product(code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢/🔴 Bepul/Pullik", callback_data=f"toggleprod:{code}")],
        [InlineKeyboardButton(text="💰 Narxni o‘zgartirish", callback_data=f"setprice:{code}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:products")]
    ])
    await callback.message.edit_text(
        f"<b>{r['title']}</b>\n\nHolat: {'🟢 Pullik' if r['enabled'] and r['price']>0 else '🆓 Bepul'}\n"
        f"Narx: {r['price']:,} so‘m".replace(",", " "),
        reply_markup=kb
    )
    await callback.answer()

class AdminState(StatesGroup):
    waiting_price = State()
    waiting_broadcast = State()
    waiting_user_id = State()
    waiting_user_message = State()

@router.callback_query(F.data.startswith("toggleprod:"))
async def toggle_product(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    code = callback.data.split(":")[1]
    r = await product(code)
    p = await db()
    if r["price"] > 0:
        await p.execute("UPDATE products SET price=0 WHERE code=$1", code)
    else:
        default = PRODUCT_DEFAULTS.get(code, ("",True,1000))[2]
        await p.execute("UPDATE products SET price=$1 WHERE code=$2", default, code)
    await callback.answer("Yangilandi")
    await admin_products(callback)

@router.callback_query(F.data.startswith("setprice:"))
async def set_price(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    code = callback.data.split(":")[1]
    await state.set_state(AdminState.waiting_price)
    await state.update_data(product_code=code)
    await callback.message.answer("💰 Yangi narxni so‘mda yuboring. Bepul qilish uchun 0 yozing.")
    await callback.answer()

@router.message(AdminState.waiting_price)
async def receive_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    if not message.text.isdigit():
        await message.answer("Faqat son yuboring.")
        return
    data = await state.get_data()
    price = int(message.text)
    p = await db()
    await p.execute("UPDATE products SET price=$1 WHERE code=$2", price, data["product_code"])
    await state.clear()
    await message.answer("✅ Narx yangilandi.")

@router.callback_query(F.data == "adm:users")
async def admin_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    p = await db()
    count = await p.fetchval("SELECT COUNT(*) FROM users")
    await callback.message.edit_text(
        f"👤 <b>USERS</b>\n\nJami: {count}\n\n"
        "Alohida userga xabar yuborish uchun:\n<code>/msg USER_ID matn</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Userga xabar",callback_data="adm:user_message")],
            [InlineKeyboardButton(text="📢 Barchaga xabar",callback_data="adm:broadcast_all")],
            [InlineKeyboardButton(text="💳 Sotib olganlarga xabar",callback_data="adm:broadcast_buyers")],
            [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="adm:back")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "adm:user_message")
async def admin_user_message_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminState.waiting_user_id)
    await callback.message.answer("👤 User ID yuboring.")
    await callback.answer()

@router.message(AdminState.waiting_user_id)
async def admin_user_id_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    if not (message.text or "").isdigit():
        await message.answer("Faqat Telegram User ID raqamini yuboring.")
        return
    await state.update_data(target_user_id=int(message.text))
    await state.set_state(AdminState.waiting_user_message)
    await message.answer("💬 Endi yuboriladigan xabarni yuboring.")

@router.message(AdminState.waiting_user_message)
async def admin_user_message_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    data = await state.get_data()
    try:
        await message.copy_to(data["target_user_id"])
        await message.answer("✅ Xabar yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborilmadi: {e}")
    await state.clear()

@router.message(Command("msg"))
async def admin_msg(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Format: /msg USER_ID xabar")
        return
    try: uid = int(parts[1])
    except:
        await message.answer("USER_ID noto‘g‘ri")
        return
    try:
        await bot.send_message(uid, parts[2])
        await message.answer("✅ Xabar yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborilmadi: {e}")

@router.callback_query(F.data.in_({"adm:broadcast_all","adm:broadcast_buyers"}))
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    kind = "buyers" if callback.data.endswith("buyers") else "all"
    await state.set_state(AdminState.waiting_broadcast)
    await state.update_data(kind=kind)
    await callback.message.answer("📢 Yuboriladigan xabarni yuboring. Matn, rasm yoki video bo‘lishi mumkin.")
    await callback.answer()

@router.message(AdminState.waiting_broadcast)
async def broadcast_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    data = await state.get_data()
    p = await db()
    if data["kind"] == "buyers":
        ids = await p.fetch("SELECT DISTINCT user_id FROM payments WHERE status='approved'")
    else:
        ids = await p.fetch("SELECT id FROM users")
    ok = fail = 0
    for r in ids:
        try:
            await message.copy_to(r["user_id"])
            ok += 1
        except:
            fail += 1
        await asyncio.sleep(0.04)
    await state.clear()
    await message.answer(f"📢 Tugadi.\n✅ {ok}\n❌ {fail}")

@router.callback_query(F.data == "adm:payments")
async def admin_payments(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    p = await db()
    rows = await p.fetch("""
      SELECT id,user_id,product_code,amount,status,created_at
      FROM payments ORDER BY id DESC LIMIT 20
    """)
    text = "💳 <b>SO‘NGGI TO‘LOVLAR</b>\n\n"
    for r in rows:
        text += f"#{r['id']} | {r['user_id']} | {r['amount']:,} | {r['status']}\n".replace(",", " ")
    await callback.message.edit_text(text or "To‘lovlar yo‘q.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga",callback_data="adm:back")]]))
    await callback.answer()

@router.callback_query(F.data == "adm:back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.edit_text("⚙️ <b>ADMIN PANEL</b>", reply_markup=admin_kb())
    await callback.answer()

# ---------- Certificate ----------

def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def make_certificate(name, iq, code, battle=False, opponent=None, opponent_iq=None):
    W,H=1600,1000
    img=Image.new("RGB",(W,H),(9,12,25))
    d=ImageDraw.Draw(img)
    # luxury frame
    for off in (18,28,40):
        d.rounded_rectangle((off,off,W-off,H-off), radius=24, outline=(194,151,61), width=2)
    d.ellipse((70,70,310,310), fill=(20,24,48), outline=(180,110,255), width=5)
    d.text((92,125),"IQ",font=font(100,True),fill=(210,170,70))
    title = "BATTLE G‘OLIBI" if battle else "SERTIFIKAT"
    d.text((W//2,90), title, anchor="ma", font=font(78,True), fill=(245,214,140))
    d.text((W//2,180), "IQTestPro.uz", anchor="ma", font=font(30), fill=(190,195,215))
    if battle:
        d.text((W//2,275), "⚔", anchor="ma", font=font(80,True), fill=(180,110,255))
        d.text((W//2,380), name, anchor="ma", font=font(62,True), fill=(245,245,250))
        d.text((W//2,465), "Do‘sti ustidan IQ Battle’da g‘alaba qozondi", anchor="ma", font=font(34), fill=(205,210,225))
        d.text((W//2,565), f"{iq}  —  {opponent_iq}", anchor="ma", font=font(100,True), fill=(190,120,255))
        d.text((W//2,680), "🏆 G‘ALABA", anchor="ma", font=font(58,True), fill=(245,214,140))
    else:
        d.text((W//2,285), "Ushbu sertifikat bilan", anchor="ma", font=font(30), fill=(190,195,215))
        d.text((W//2,360), name, anchor="ma", font=font(62,True), fill=(245,245,250))
        d.text((W//2,470), "IQ", anchor="ma", font=font(38,True), fill=(245,214,140))
        d.text((W//2,560), str(iq), anchor="ma", font=font(130,True), fill=(255,255,255))
        label = "Yuqori natija" if iq >= 110 else "Yaxshi natija"
        d.text((W//2,710), label, anchor="ma", font=font(35,True), fill=(190,120,255))
    d.text((W//2,850), f"Sertifikat kodi: {code}", anchor="ma", font=font(25), fill=(170,175,195))
    d.text((W//2,910), "Aql — imkoniyat. Harakat — natija.", anchor="ma", font=font(27), fill=(210,210,220))
    path=f"/tmp/{code}.png"
    img.save(path)
    return path

async def create_iq_certificate(user_id, name, iq):
    code="IQ-"+''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
    p=await db()
    await p.execute("INSERT INTO certificates(code,user_id,cert_type,data) VALUES($1,$2,'iq',$3::jsonb)",
                    code,user_id,json.dumps({"name":name,"iq":iq}))
    return code

# ---------- Web API ----------

def validate_init_data(init_data: str):
    """Validate Telegram Mini App initData according to Telegram's HMAC scheme."""
    if not init_data:
        raise HTTPException(401, "Telegram initData required")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
        data = dict(pairs)
        received_hash = data.pop("hash", None)
        if not received_hash:
            raise ValueError("hash missing")

        # auth_date is required and is intentionally bounded to reduce replay risk.
        auth_date = int(data.get("auth_date", "0"))
        current = int(time.time())
        if auth_date <= 0 or current - auth_date > 86400 or auth_date - current > 60:
            raise ValueError("auth_date invalid or expired")

        check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(data.items())
        )
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        calculated = hmac.new(
            secret_key, check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            raise ValueError("hash mismatch")

        raw_user = data.get("user")
        if not raw_user:
            raise ValueError("user missing")
        user = json.loads(raw_user)
        if not isinstance(user, dict) or not user.get("id"):
            raise ValueError("invalid user")
        return user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(401, "Invalid Telegram initData") from exc

async def api_user(x_telegram_init_data: str = Header(default="")):
    tg=validate_init_data(x_telegram_init_data)
    p=await db()
    await upsert_user(type("TG",(),{
        "id":tg["id"],"username":tg.get("username"),"first_name":tg.get("first_name"),
        "last_name":tg.get("last_name")
    })())
    return tg

@app.get("/")
async def root():
    return FileResponse(WEBAPP_DIR / "index.html", media_type="text/html")


@app.get("/app")
async def app_page():
    """Canonical Mini App entry point used by WEBAPP_URL."""
    return FileResponse(WEBAPP_DIR / "index.html", media_type="text/html")

@app.get("/api/me")
async def api_me(x_telegram_init_data: str = Header(default="")):
    tg=await api_user(x_telegram_init_data)
    p=await db()
    results=await p.fetch("SELECT test_type,score,created_at FROM test_results WHERE user_id=$1 ORDER BY id DESC",tg["id"])
    return {"user":tg,"results":[dict(r) for r in results]}

@app.get("/api/config")
async def api_config(x_telegram_init_data: str = Header(default="")):
    tg=await api_user(x_telegram_init_data)
    p=await db()
    rows=await p.fetch("SELECT code,title,enabled,price,retry_days FROM products")
    return {
        "products": [dict(r) for r in rows],
        "bot_username": BOT_USERNAME,
        "iq_first_test_free": await get_setting("iq_first_test_free", "1") == "1",
        "iq_question_count": IQ_QUESTION_COUNT,
    }

async def has_access(user_id, product_code):
    """Server-side product access rules.

    IQ: the first completed IQ attempt is free while `iq_first_test_free=1`.
    Subsequent IQ attempts require an approved `iq_retry` payment.
    EQ/PQ are unlocked after the previous test result exists.
    """
    p = await db()
    if product_code == "iq":
        first_free = await get_setting("iq_first_test_free", "1") == "1"
        if first_free:
            attempts = await p.fetchval(
                "SELECT COUNT(*) FROM test_results WHERE user_id=$1 AND test_type='iq'",
                user_id,
            )
            if int(attempts or 0) == 0:
                return True
        return bool(await p.fetchval(
            """SELECT EXISTS(
                SELECT 1 FROM payments
                WHERE user_id=$1 AND product_code='iq_retry'
                  AND status='approved' AND consumed_at IS NULL
            )""",
            user_id,
        ))

    if product_code == "eq":
        return bool(await p.fetchval(
            "SELECT EXISTS(SELECT 1 FROM test_results WHERE user_id=$1 AND test_type='iq')",
            user_id,
        ))

    if product_code == "pq":
        return bool(await p.fetchval(
            "SELECT EXISTS(SELECT 1 FROM test_results WHERE user_id=$1 AND test_type='eq')",
            user_id,
        ))

    if product_code == "full":
        return all([
            bool(await p.fetchval("SELECT EXISTS(SELECT 1 FROM test_results WHERE user_id=$1 AND test_type='iq')", user_id)),
            bool(await p.fetchval("SELECT EXISTS(SELECT 1 FROM test_results WHERE user_id=$1 AND test_type='eq')", user_id)),
            bool(await p.fetchval("SELECT EXISTS(SELECT 1 FROM test_results WHERE user_id=$1 AND test_type='pq')", user_id)),
        ])

    r = await p.fetchrow("SELECT price,enabled FROM products WHERE code=$1", product_code)
    if not r or not r["enabled"]:
        return False
    if r["price"] == 0:
        return True
    return bool(await p.fetchval(
        "SELECT EXISTS(SELECT 1 FROM payments WHERE user_id=$1 AND product_code=$2 AND status='approved')",
        user_id, product_code,
    ))

@app.post("/api/payment/start")
async def api_payment_start(payload: dict, x_telegram_init_data: str = Header(default="")):
    tg = await api_user(x_telegram_init_data)
    requested = str(payload.get("product_code", "iq")).strip()

    # The UI can request `iq` after the first attempt; internally that means
    # an IQ retest payment, so one approved payment cannot unlock unlimited attempts.
    code = "iq_retry" if requested == "iq" else requested

    r = await product(code)
    if not r or not r["enabled"]:
        raise HTTPException(400, "Product unavailable")
    if r["price"] == 0:
        return {"free": True, "payment_id": None, "product_code": code}

    pid = await create_payment(tg["id"], code, r["price"])
    await send_payment_message(tg["id"], pid, code, r["price"])
    return {"free": False, "payment_id": pid, "product_code": code}


@app.get("/api/access/{product_code}")
async def api_access(product_code: str, x_telegram_init_data: str = Header(default="")):
    tg = await api_user(x_telegram_init_data)
    return {"allowed": await has_access(tg["id"], product_code)}

@app.get("/api/payment/status/{payment_id}")
async def api_payment_status(payment_id: int, x_telegram_init_data: str = Header(default="")):
    tg = await api_user(x_telegram_init_data)
    p = await db()
    row = await p.fetchrow(
        "SELECT id,status,product_code,amount FROM payments WHERE id=$1 AND user_id=$2",
        payment_id, tg["id"]
    )
    if not row:
        raise HTTPException(404, "Payment not found")
    return dict(row)

@app.post("/api/test/submit")
async def api_test_submit(payload: dict, x_telegram_init_data: str = Header(default="")):
    tg = await api_user(x_telegram_init_data)
    test_type = str(payload.get("test_type", "iq")).lower().strip()
    answers = payload.get("answers", [])
    profile = payload.get("profile", {})
    battle_id = payload.get("battle_id")

    if not isinstance(answers, list):
        raise HTTPException(400, "Invalid answers")

    try:
        answers = [int(x) for x in answers]
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Invalid answers") from exc

    if test_type not in {"iq", "eq", "pq"}:
        raise HTTPException(400, "Unknown test type")

    expected_total = IQ_QUESTION_COUNT if test_type == "iq" else 12
    if len(answers) != expected_total:
        raise HTTPException(409, f"Test incomplete: expected {expected_total} answers")
    if any(x < 0 or x > 3 for x in answers):
        raise HTTPException(400, "Invalid answer option")

    if test_type == "iq":
        if not await has_access(tg["id"], "iq"):
            raise HTTPException(402, "Payment required")
        raw = sum(
            IQ_WEIGHTS[i]
            for i, answer in enumerate(answers)
            if answer == IQ_CORRECT_ANSWERS[i]
        )
        correct = sum(
            answer == IQ_CORRECT_ANSWERS[i]
            for i, answer in enumerate(answers)
        )
        # Product score, not a clinical/standardized IQ.
        score = max(40, min(160, round(40 + (raw / IQ_MAX_RAW) * 120)))
        total = IQ_QUESTION_COUNT
    elif test_type == "eq":
        if not await has_access(tg["id"], "eq"):
            raise HTTPException(403, "EQ is locked until IQ is completed")
        # EQ answer choices are scored by the frontend's 0..3 behavioral scale.
        raw = sum(max(0, 3 - a) for a in answers)
        correct = sum(1 for a in answers if a == 0)
        total = len(answers)
        score = max(40, min(160, round(70 + (raw / max(total * 3, 1)) * 70)))
    else:
        if not await has_access(tg["id"], "pq"):
            raise HTTPException(403, "PQ is locked until EQ is completed")
        raw = sum(max(0, 3 - a) for a in answers)
        correct = sum(1 for a in answers if a == 0)
        total = len(answers)
        score = max(40, min(160, round(70 + (raw / max(total * 3, 1)) * 70)))

    p = await db()
    await p.execute(
        """INSERT INTO test_results(user_id,test_type,score,raw_score,total,profile)
           VALUES($1,$2,$3,$4,$5,$6::jsonb)""",
        tg["id"], test_type, score, raw, total, json.dumps(profile if isinstance(profile, dict) else {}),
    )

    if test_type == "iq":
        # Consume exactly one approved retest payment. The first IQ attempt is
        # free; later attempts each need their own approved payment.
        await p.execute(
            """UPDATE payments SET consumed_at=NOW()
               WHERE id=(
                   SELECT id FROM payments
                   WHERE user_id=$1 AND product_code='iq_retry'
                     AND status='approved' AND consumed_at IS NULL
                   ORDER BY approved_at DESC NULLS LAST, id DESC
                   LIMIT 1
               )""",
            tg["id"],
        )

    cert_code = None
    if test_type == "iq":
        cert_code = await create_iq_certificate(
            tg["id"],
            profile.get("fullName") if isinstance(profile, dict) else None or tg.get("first_name") or "Foydalanuvchi",
            score,
        )
        try:
            name = profile.get("fullName") if isinstance(profile, dict) else None or tg.get("first_name") or "Foydalanuvchi"
            cert_path = make_certificate(name, score, cert_code)
            with open(cert_path, "rb") as fh:
                await bot.send_document(
                    tg["id"],
                    BufferedInputFile(fh.read(), filename=f"{cert_code}.png"),
                    caption=f"📜 <b>IQ sertifikatingiz tayyor!</b>\n\n🔑 Kod: <code>{cert_code}</code>",
                )
        except Exception as exc:
            print(f"Certificate delivery warning: {exc}")

    battle_finished = False
    if battle_id and test_type == "iq":
        b = await p.fetchrow("SELECT * FROM battles WHERE id=$1", int(battle_id))
        if b and tg["id"] in (b["player1"], b["player2"]) and b["status"] == "ready":
            r1 = await p.fetchrow(
                """SELECT score,created_at FROM test_results
                   WHERE user_id=$1 AND test_type='iq' AND created_at >= $2
                   ORDER BY id DESC LIMIT 1""",
                b["player1"], b["created_at"],
            )
            r2 = await p.fetchrow(
                """SELECT score,created_at FROM test_results
                   WHERE user_id=$1 AND test_type='iq' AND created_at >= $2
                   ORDER BY id DESC LIMIT 1""",
                b["player2"], b["created_at"],
            )
            if r1 and r2:
                winner = b["player1"] if r1["score"] > r2["score"] else b["player2"] if r2["score"] > r1["score"] else None
                result = {"player1": r1["score"], "player2": r2["score"], "winner": winner}
                await p.execute(
                    "UPDATE battles SET status='finished',result=$1::jsonb WHERE id=$2",
                    json.dumps(result), b["id"],
                )
                battle_finished = True
                for uid, myscore, oppscore, oppid in [
                    (b["player1"], r1["score"], r2["score"], b["player2"]),
                    (b["player2"], r2["score"], r1["score"], b["player1"]),
                ]:
                    if winner == uid:
                        await bot.send_message(uid, f"⚔️ <b>BATTLE YAKUNLANDI!</b>\n\n🧠 Siz: <b>{myscore}</b>\n🧠 Do‘stingiz: <b>{oppscore}</b>\n\n🏆 <b>SIZ G‘OLIB BO‘LDINGIZ!</b>")
                        try:
                            opponent = await p.fetchrow("SELECT first_name FROM users WHERE id=$1", oppid)
                            opponent_name = opponent["first_name"] if opponent else "Do‘st"
                            vcode = "BT-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                            await p.execute(
                                "INSERT INTO certificates(code,user_id,cert_type,data) VALUES($1,$2,'battle',$3::jsonb)",
                                vcode, uid, json.dumps({"name": name, "iq": myscore, "opponent": opponent_name, "opponent_iq": oppscore}),
                            )
                            path = make_certificate(name, myscore, vcode, True, opponent_name, oppscore)
                            with open(path, "rb") as fh:
                                await bot.send_document(
                                    uid,
                                    BufferedInputFile(fh.read(), filename=f"{vcode}.png"),
                                    caption=f"🏆 Battle g‘alaba sertifikati\n🔑 <code>{vcode}</code>",
                                )
                        except Exception as exc:
                            print(f"Battle certificate warning: {exc}")
                    elif winner is None:
                        await bot.send_message(uid, f"🤝 <b>BATTLE DURANG!</b>\n\nSiz: <b>{myscore}</b>\nDo‘stingiz: <b>{oppscore}</b>")
                    else:
                        await bot.send_message(uid, f"⚔️ <b>BATTLE YAKUNLANDI!</b>\n\nSiz: <b>{myscore}</b>\nDo‘stingiz: <b>{oppscore}</b>\n\n🏆 G‘olib: do‘stingiz.")

    return {
        "score": score,
        "raw_score": raw,
        "correct": correct,
        "total": total,
        "certificate_code": cert_code,
        "battle_finished": battle_finished,
    }

@app.get("/api/counter")
async def api_counter(x_telegram_init_data: str = Header(default="")):
    await api_user(x_telegram_init_data)
    p=await db()
    # privacy-safe approximate active count, no fake rolling growth
    count=await p.fetchval("SELECT COUNT(*) FROM users WHERE last_seen > NOW()-INTERVAL '10 minutes'")
    return {"active":max(1,int(count or 1))}

# ---------- Battle ----------

@router.callback_query(F.data.startswith("battle:"))
async def battle_callback(callback: CallbackQuery):
    # reserved for later UI callbacks; core battle APIs are below
    await callback.answer()


@app.post("/api/battle/create")
async def battle_create(payload: dict, x_telegram_init_data: str = Header(default="")):
    tg=await api_user(x_telegram_init_data)
    p=await db()
    code=''.join(secrets.choice(string.digits) for _ in range(4))
    bid=await p.fetchval("INSERT INTO battles(code,player1) VALUES($1,$2) RETURNING id",code,tg["id"])
    r=await product("battle")
    if r["price"]>0:
        pid=await create_payment(tg["id"],"battle",r["price"])
        await p.execute("INSERT INTO battle_payments(battle_id,user_id,payment_id) VALUES($1,$2,$3)",bid,tg["id"],pid)
        await send_payment_message(tg["id"],pid,"battle",r["price"])
        return {"payment_required":True,"payment_id":pid,"battle_id":bid,"code":code}
    await p.execute("UPDATE battles SET status='ready' WHERE id=$1",bid)
    return {"payment_required":False,"battle_id":bid,"code":code}

@app.post("/api/battle/join")
async def battle_join(payload: dict, x_telegram_init_data: str = Header(default="")):
    tg=await api_user(x_telegram_init_data)
    code=str(payload.get("code","")).strip()
    p=await db()
    b=await p.fetchrow("SELECT * FROM battles WHERE code=$1",code)
    if not b: raise HTTPException(404,"Battle code not found")
    if b["player1"]==tg["id"]: return {"battle_id":b["id"],"status":b["status"],"code":code}
    if b["player2"] and b["player2"]!=tg["id"]: raise HTTPException(409,"Battle full")
    await p.execute("UPDATE battles SET player2=$1 WHERE id=$2",tg["id"],b["id"])
    r=await product("battle")
    if r["price"]>0:
        pid=await create_payment(tg["id"],"battle",r["price"])
        await p.execute("INSERT INTO battle_payments(battle_id,user_id,payment_id) VALUES($1,$2,$3)",b["id"],tg["id"],pid)
        await send_payment_message(tg["id"],pid,"battle",r["price"])
        return {"payment_required":True,"payment_id":pid,"battle_id":b["id"],"code":code}
    await p.execute("UPDATE battles SET status='ready' WHERE id=$1",b["id"])
    return {"payment_required":False,"battle_id":b["id"],"status":"ready","code":code}

@app.get("/api/battle/{battle_id}")
async def battle_state(battle_id:int,x_telegram_init_data:str=Header(default="")):
    tg=await api_user(x_telegram_init_data)
    p=await db()
    b=await p.fetchrow("SELECT * FROM battles WHERE id=$1",battle_id)
    if not b or tg["id"] not in (b["player1"],b["player2"]): raise HTTPException(404,"Battle not found")
    return {"id":b["id"],"code":b["code"],"player1":b["player1"],"player2":b["player2"],"status":b["status"],"result":b["result"]}

# ---------- lifecycle ----------

@app.get("/health")
async def health():
    return {"ok":True,"service":"iqtestpro"}

async def bot_runner():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)

async def main():
    await init_db()
    config=uvicorn.Config(app,host="0.0.0.0",port=PORT,log_level="info")
    server=uvicorn.Server(config)
    await asyncio.gather(server.serve(),bot_runner())

if __name__=="__main__":
    asyncio.run(main())
