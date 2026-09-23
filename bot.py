import os
import sys
import glob
import json
import hmac
import random
import string
import hashlib
import logging
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Header, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, FSInputFile
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

# LOGGING SETUP
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("IQTestBot")

# ENV CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
BOT_USERNAME = os.getenv("BOT_USERNAME", "iqtest_ubot").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0").strip() or 0)
PORT = int(os.getenv("PORT", "10000").strip())

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
if not WEBHOOK_SECRET and BOT_TOKEN:
    WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()

# GLOBAL DB POOL & BOT INSTANCE
db_pool: Optional[asyncpg.Pool] = None
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# DATABASE INITIALIZATION AND MIGRATIONS
async def init_db():
    global db_pool
    logger.info("Initializing PostgreSQL Connection Pool...")
    db_pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=2, max_size=10)

    async with db_pool.acquire() as conn:
        # Users Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'uz',
                full_name TEXT,
                gender TEXT,
                age INT,
                country TEXT,
                last_seen TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Migrations check
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS age INT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT;")

        # App Settings Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Payments Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                amount INT NOT NULL,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Payment Cards Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_cards (
                id SERIAL PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder TEXT NOT NULL,
                bank TEXT NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Results Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                score INT NOT NULL,
                level TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Certificates Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                verification_code TEXT UNIQUE NOT NULL,
                certificate_id TEXT NOT NULL,
                type TEXT NOT NULL,
                full_name TEXT NOT NULL,
                score INT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Battles Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                battle_id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                creator_id BIGINT NOT NULL,
                opponent_id BIGINT,
                status TEXT DEFAULT 'waiting',
                creator_score INT,
                opponent_score INT,
                winner_id BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Default Settings Seeding
        defaults = {
            "iq_price": "0",
            "iq_retry_price": "5000",
            "eq_price": "0",
            "pq_price": "0",
            "battle_price": "7500",
            "live_mode": "fake",
            "live_fake_base": "95114",
            "live_fake_online": "342",
            "live_fake_delta": "8"
        }
        for k, v in defaults.items():
            await conn.execute("""
                INSERT INTO app_settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING;
            """, k, v)

        # Seed Default Card if None exists
        card_cnt = await conn.fetchval("SELECT COUNT(*) FROM payment_cards;")
        if card_cnt == 0:
            await conn.execute("""
                INSERT INTO payment_cards (card_number, holder, bank, active)
                VALUES ('8600123456789012', 'IQ TEST OFFICIAL', 'Kapitalbank', TRUE);
            """)

    logger.info("Database initialized successfully.")

# TELEGRAM INIT DATA HMAC VALIDATOR
def validate_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = init_data.split("&")
        data_dict = {}
        hash_val = ""
        for pair in pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k == "hash":
                    hash_val = v
                else:
                    data_dict[k] = v

        sorted_keys = sorted(data_dict.keys())
        data_check_string = "\n".join([f"{k}={data_dict[k]}" for k in sorted_keys])

        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, hash_val):
            user_json = data_dict.get("user")
            if user_json:
                return json.loads(user_json)
        return None
    except Exception as e:
        logger.error(f"HMAC Validation error: {e}")
        return None

async def get_current_user_id(request: Request) -> int:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    validated_user = validate_init_data(init_data)
    if not validated_user or "id" not in validated_user:
        raise HTTPException(status_code=401, detail="Xavfsizlik tekshiruvidan o'tmadi (Invalid Telegram Auth)")
    return int(validated_user["id"])


# BOT KEYBOARDS & COMMAND HANDLERS
def get_main_keyboard() -> InlineKeyboardMarkup:
    web_app = WebAppInfo(url=WEBAPP_URL) if WEBAPP_URL else None
    builder = []
    if web_app:
        builder.append([InlineKeyboardButton(text="🧠 Testni Boshlash (Mini App)", web_app=web_app)])
    else:
        builder.append([InlineKeyboardButton(text="🌐 Veb-saytga o'tish", url=PUBLIC_BASE_URL)])
    
    builder.append([
        InlineKeyboardButton(text="📊 Natijalarim", callback_data="my_results"),
        InlineKeyboardButton(text="🏆 Reyting", callback_data="show_leaderboard")
    ])
    builder.append([
        InlineKeyboardButton(text="📜 Sertifikatni Tekshirish", callback_data="verify_cert_info")
    ])
    return InlineKeyboardMarkup(inline_keyboard=builder)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, last_seen)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_seen = NOW();
            """, user.id, user.username, user.first_name, user.last_name)

    welcome_text = (
        f"Assalomu alaykum, <b>{user.first_name}</b>!\n\n"
        f"<b>IQ / EQ / PQ Professional Sinov Platformasiga</b> xush kelibsiz.\n\n"
        f"🎯 Ushbu bot va Mini App orqali siz o'zingizning intellektual salohiyatingiz, "
        f"emotsional intellektingiz hamda ruhiy barqarorligingizni xalqaro standartlar asosida baholashingiz mumkin.\n\n"
        f"Tugmani bosib, ilovani ishga tushiring:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ Bu buyruq faqat administrator uchun mo'ljallangan.")
        return

    async with db_pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users;")
        total_tests = await conn.fetchval("SELECT COUNT(*) FROM results;")
        pending_payments = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status = 'pending';")

    admin_text = (
        f"🛠 <b>ADMINISTRATOR PANELI</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"📝 Topshirilgan testlar: <b>{total_tests}</b>\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{pending_payments}</b>\n\n"
        f"To'lovlarni tasdiqlash uchun /payments buyrug'ini yuboring."
    )
    await message.answer(admin_text, parse_mode="HTML")

@dp.message(Command("payments"))
async def cmd_payments(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.user_id, p.test_type, p.amount, u.full_name 
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending' ORDER BY p.created_at ASC LIMIT 5;
        """)

    if not rows:
        await message.answer("✅ Hozircha kutilayotgan to'lovlar yo'q.")
        return

    for r in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_pay_{r['id']}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_pay_{r['id']}")
        ]])
        txt = f"💳 <b>To'lov #{r['id']}</b>\nFoydalanuvchi: {r['full_name']} (ID: {r['user_id']})\nTest: {r['test_type'].upper()}\nSumma: {r['amount']} UZS"
        await message.answer(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("approve_pay_"))
async def cb_approve_payment(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_USER_ID:
        return
    pay_id = int(call.data.split("_")[2])

    async with db_pool.acquire() as conn:
        pay_info = await conn.fetchrow("SELECT user_id, test_type FROM payments WHERE id = $1;", pay_id)
        if pay_info:
            await conn.execute("UPDATE payments SET status = 'approved' WHERE id = $1;", pay_id)
            user_id = pay_info["user_id"]
            test_type = pay_info["test_type"]
            
            # User update status
            await conn.execute(f"UPDATE users SET has_{test_type} = TRUE WHERE user_id = $1;", user_id)
            
            try:
                await bot.send_message(
                    user_id, 
                    f"🎉 Sizning <b>{test_type.upper()}</b> testi uchun to'lovingiz tasdiqlandi! Mini App'ga kirib natijangizni ko'rishingiz va sertifikatni yuklab olishingiz mumkin.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Userga xabar yuborishda xatolik: {e}")

    await call.message.edit_text(f"✅ To'lov #{pay_id} tasdiqlandi.")

@dp.callback_query(F.data.startswith("reject_pay_"))
async def cb_reject_payment(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_USER_ID:
        return
    pay_id = int(call.data.split("_")[2])

    async with db_pool.acquire() as conn:
        pay_info = await conn.fetchrow("SELECT user_id FROM payments WHERE id = $1;", pay_id)
        if pay_info:
            await conn.execute("UPDATE payments SET status = 'rejected' WHERE id = $1;", pay_id)
            try:
                await bot.send_message(
                    pay_info["user_id"], 
                    f"⚠️ Siz yuborgan to'lov kvitansiyasi tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring yoki qo'llab-quvvatlash xizmati bilan bog'laning."
                )
            except Exception:
                pass

    await call.message.edit_text(f"❌ To'lov #{pay_id} rad etildi.")

# CERTIFICATE GENERATOR WITH PILLOW
def generate_certificate_image(full_name: str, score: int, cert_code: str, test_type: str = "IQ") -> BytesIO:
    width, height = 1200, 850
    image = Image.new("RGB", (width, height), color="#0a0e1a")
    draw = ImageDraw.Draw(image)

    # Decorative Border
    draw.rectangle([20, 20, width - 20, height - 20], outline="#a78bfa", width=4)
    draw.rectangle([30, 30, width - 30, height - 30], outline="rgba(255,255,255,0.1)", width=1)

    # Header Text
    draw.text((width // 2, 100), "XALQARO INTELLEKT SERTIFIKATI", fill="#a78bfa", anchor="mm", font_size=42)
    draw.text((width // 2, 160), "OFFICIAL INTELLIGENCE CERTIFICATE", fill="#94a3b8", anchor="mm", font_size=20)

    # Awarded To
    draw.text((width // 2, 280), "Ushbu sertifikat egasi:", fill="#64748b", anchor="mm", font_size=22)
    draw.text((width // 2, 350), full_name.upper(), fill="#ffffff", anchor="mm", font_size=52)

    # Achievement
    desc = f"Muvaffaqiyatli ravishda {test_type} sinovidan o'tib, yuqori natijani qayd etdi:"
    draw.text((width // 2, 450), desc, fill="#94a3b8", anchor="mm", font_size=22)
    
    # Score Circle / Display
    draw.text((width // 2, 540), f"{score} IQ POINTS", fill="#10b981", anchor="mm", font_size=60)

    # Footer Metadata
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    draw.text((100, 750), f"Sana: {date_str}", fill="#64748b", font_size=18)
    draw.text((width - 100, 750), f"Kod: {cert_code}", fill="#64748b", anchor="ra", font_size=18)

    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf


# FASTAPI APP & LIFESPAN MANAGEMENT
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    # Set Telegram Webhook
    if bot and PUBLIC_BASE_URL:
        webhook_url = f"{PUBLIC_BASE_URL}/api/telegram/webhook"
        logger.info(f"Setting Telegram Webhook to: {webhook_url}")
        await bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET)
        
    yield
    
    if bot:
        await bot.delete_webhook()
    if db_pool:
        await db_pool.close()

app = FastAPI(title="IQ Test Platform API", lifespan=lifespan)

# Static Files Setup
app.mount("/static", StaticFiles(directory="webapp"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# TELEGRAM WEBHOOK ENDPOINT
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: Optional[str] = Header(None)):
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized Webhook Access")
    
    update_data = await request.json()
    update = types.Update(**update_data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}


# API REST ENDPOINTS
@app.get("/api/stats/live")
async def get_live_stats():
    async with db_pool.acquire() as conn:
        base_str = await conn.fetchval("SELECT value FROM app_settings WHERE key='live_fake_base';") or "95000"
        online_str = await conn.fetchval("SELECT value FROM app_settings WHERE key='live_fake_online';") or "300"
        delta_str = await conn.fetchval("SELECT value FROM app_settings WHERE key='live_fake_delta';") or "5"
        
        base = int(base_str)
        online = int(online_str) + random.randint(-int(delta_str), int(delta_str))
        
        return {"total_tests": base, "online": max(10, online)}

@app.get("/api/profile/status")
async def get_profile_status(user_id: int = Depends(get_current_user_id)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT full_name, gender, age, country, 
                   EXISTS(SELECT 1 FROM results WHERE user_id=$1 AND test_type='iq') as has_iq,
                   EXISTS(SELECT 1 FROM results WHERE user_id=$1 AND test_type='eq') as has_eq,
                   EXISTS(SELECT 1 FROM results WHERE user_id=$1 AND test_type='pq') as has_pq
            FROM users WHERE user_id = $1;
        """, user_id)
        if not row:
            return {"full_name": None}
        return dict(row)

@app.post("/api/profile/save")
async def save_profile(data: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET full_name=$1, gender=$2, age=$3, country=$4, updated_at=NOW()
            WHERE user_id=$5;
        """, data.get("full_name"), data.get("gender"), data.get("age"), data.get("country"), user_id)
    return {"status": "success"}

@app.get("/api/test/questions")
async def get_test_questions(type: str = "iq", user_id: int = Depends(get_current_user_id)):
    # Generate 12 dynamic SVG pattern puzzles
    questions = []
    for i in range(1, 13):
        color = random.choice(["#a78bfa", "#60a5fa", "#10b981", "#f43f5e"])
        rotation = (i * 30) % 360
        
        svg_content = f"""
        <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="200" fill="#161d2f" rx="12"/>
            <circle cx="100" cy="100" r="70" stroke="{color}" stroke-width="4" fill="none" opacity="0.3"/>
            <g transform="translate(100,100) rotate({rotation})">
                <rect x="-30" y="-30" width="60" height="60" fill="{color}" rx="8"/>
                <circle cx="0" cy="0" r="15" fill="#ffffff"/>
            </g>
        </svg>
        """
        
        opts = {}
        for opt in ['A', 'B', 'C', 'D']:
            opt_rot = (rotation + (ord(opt) - 65) * 90) % 360
            opts[opt] = f"""
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <rect width="100" height="100" fill="#0a0e1a" rx="8"/>
                <g transform="translate(50,50) rotate({opt_rot})">
                    <rect x="-15" y="-15" width="30" height="30" fill="{color}" rx="4"/>
                </g>
            </svg>
            """

        questions.append({
            "id": i,
            "difficulty": "medium" if i <= 6 else "hard",
            "svg_content": svg_content,
            "options": opts
        })

    return {"questions": questions}

@app.post("/api/test/submit")
async def submit_test(payload: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    test_type = payload.get("test_type", "iq")
    answers = payload.get("answers", {})

    # Compute Score (Simulated logic based on pattern inputs)
    score = 90 + len(answers) * 4 + random.randint(1, 10)
    
    level = "O'rta"
    if score >= 130: level = "Dahshatli Intellekt (Genius)"
    elif score >= 115: level = "Yuqori Salohiyat"
    elif score >= 100: level = "O'rtadan Yuqori"

    async with db_pool.acquire() as conn:
        # Save Result
        await conn.execute("""
            INSERT INTO results (user_id, test_type, score, level)
            VALUES ($1, $2, $3, $4);
        """, user_id, test_type, score, level)

        # Check pricing requirements
        price_str = await conn.fetchval(f"SELECT value FROM app_settings WHERE key='{test_type}_price';") or "0"
        price = int(price_str)

        if price > 0:
            card_row = await conn.fetchrow("SELECT card_number, holder, bank FROM payment_cards WHERE active=TRUE LIMIT 1;")
            return {
                "payment_required": True,
                "price": price,
                "card_details": dict(card_row) if card_row else None
            }

    return {
        "payment_required": False,
        "result": {
            "score": score,
            "level": level,
            "description": f"Sizning intellektual ko'rsatkichingiz {score} ballni tashkil etdi. Bu umumiy aholining eng yuqori 15% qismiga kirishingizni anglatadi."
        }
    }

@app.post("/api/payment/upload")
async def upload_payment(
    receipt: UploadFile = File(...),
    test_type: str = Form("iq"),
    user_id: int = Depends(get_current_user_id)
):
    async with db_pool.acquire() as conn:
        amount_str = await conn.fetchval(f"SELECT value FROM app_settings WHERE key='{test_type}_price';") or "0"
        await conn.execute("""
            INSERT INTO payments (user_id, test_type, amount, receipt_file_id, status)
            VALUES ($1, $2, $3, $4, 'pending');
        """, user_id, test_type, int(amount_str), receipt.filename)

        # Notify Admin on Telegram
        if bot and ADMIN_USER_ID:
            user_info = await conn.fetchrow("SELECT full_name FROM users WHERE user_id=$1;", user_id)
            name = user_info["full_name"] if user_info else str(user_id)
            try:
                await bot.send_message(
                    ADMIN_USER_ID, 
                    f"📥 <b>Yangi to'lov kvitansiyasi!</b>\nFoydalanuvchi: {name}\nTest: {test_type.upper()}\n\nTasdiqlash uchun /payments buyrug'ini kiriting.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    return {"status": "ok"}

@app.get("/api/ranking/list")
async def get_ranking_list():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.full_name, MAX(r.score) as score
            FROM results r
            JOIN users u ON r.user_id = u.user_id
            WHERE u.full_name IS NOT NULL
            GROUP BY u.full_name
            ORDER BY score DESC LIMIT 10;
        """)
        return {"rankings": [dict(r) for r in rows]}

@app.post("/api/certificate/generate")
async def generate_certificate(payload: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT full_name FROM users WHERE user_id=$1;", user_id)
        res = await conn.fetchrow("SELECT score FROM results WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1;", user_id)

        if not user or not res:
            raise HTTPException(status_code=400, detail="Natija topilmadi")

        cert_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        buf = generate_certificate_image(user["full_name"] or "Foydalanuvchi", res["score"], cert_code)

        if bot:
            file_bytes = buf.getvalue()
            input_file = FSInputFile(BytesIO(file_bytes), filename=f"Certificate_{cert_code}.png")
            await bot.send_photo(
                chat_id=user_id,
                photo=input_file,
                caption=f"📜 <b>Rasmiy Sertifikatingiz!</b>\n\nSertifikat kodi: <code>{cert_code}</code>\nUshbu kod orqali haqiqiylikni tekshirish mumkin.",
                parse_mode="HTML"
            )

    return {"status": "ok", "code": cert_code}

# ENTRYPOINT RUNNER
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT, reload=False)

