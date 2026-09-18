import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from PIL import Image, ImageDraw, ImageFont


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ZAKO_URL = os.environ.get(
    "ZAKO_URL",
    "https://t.me/zako_tbot",
)
WEBAPP_URL = os.environ.get("WEBAPP_URL")
PORT = int(os.environ.get("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is missing")

if not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("WEBAPP_URL must start with https://")


# =========================================================
# DATABASE URL
# =========================================================

def clean_db_url(url: str) -> str:
    """
    Neon connection URL'dagi asyncpg uchun
    kerak bo'lmaydigan sslmode/channel_binding
    parametrlarini olib tashlaydi.
    """
    parsed = urlsplit(url)

    query = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if key.lower() not in {
            "sslmode",
            "channel_binding",
        }
    ]

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


DB_URL = clean_db_url(DATABASE_URL)

pool: asyncpg.Pool | None = None
bot: Bot | None = None
BOT_USERNAME = ""

dp = Dispatcher()

app = FastAPI(
    title="IQ TEST BOT",
)

if not WEBAPP_DIR.exists():
    raise RuntimeError(
        f"webapp directory not found: {WEBAPP_DIR}"
    )

app.mount(
    "/static",
    StaticFiles(directory=WEBAPP_DIR),
    name="static",
)


# =========================================================
# QUESTION ANSWERS / WEIGHTS
# =========================================================

# Frontenddagi QUESTIONS bilan aynan bir xil tartib.
CORRECT_ANSWERS = [
    1,  # 1
    1,  # 2
    2,  # 3
    0,  # 4
    2,  # 5
    2,  # 6
    0,  # 7
    0,  # 8
    1,  # 9
    2,  # 10
    2,  # 11
    1,  # 12
    2,  # 13
    1,  # 14
    1,  # 15
    2,  # 16
]

WEIGHTS = [
    1,  # 1
    1,  # 2
    1,  # 3
    1,  # 4
    2,  # 5
    2,  # 6
    2,  # 7
    3,  # 8
    3,  # 9
    3,  # 10
    4,  # 11
    4,  # 12
    4,  # 13
    4,  # 14
    5,  # 15
    5,  # 16
]

TOTAL_WEIGHT = sum(WEIGHTS)


# =========================================================
# DATABASE INITIALIZATION / MIGRATION
# =========================================================

async def init_db() -> None:
    global pool

    pool = await asyncpg.create_pool(
        DB_URL,
        min_size=1,
        max_size=5,
        ssl="require",
        command_timeout=30,
    )

    async with pool.acquire() as conn:

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            )
            """
        )

        # Muhim:
        # CREATE TABLE IF NOT EXISTS mavjud jadvalni
        # yangilamaydi.
        #
        # Shuning uchun barcha ustunlarni alohida
        # ADD COLUMN IF NOT EXISTS bilan tekshiramiz.

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS first_name
            TEXT NOT NULL DEFAULT ''
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_name
            TEXT NOT NULL DEFAULT ''
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS username
            TEXT NOT NULL DEFAULT ''
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS language
            TEXT NOT NULL DEFAULT 'uz'
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS attempts
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_score
            INTEGER
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_raw
            INTEGER
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS best_time
            INTEGER
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referrals
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS cert_claimed
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referred_by
            BIGINT
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referral_counted
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS updated_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        # -------------------------------------------------
        # TEST SESSIONS
        # -------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                user_id BIGINT PRIMARY KEY
                REFERENCES users(user_id)
                ON DELETE CASCADE
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS current_index
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS answers
            JSONB NOT NULL DEFAULT '[]'::jsonb
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS raw_score
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS correct
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS language
            TEXT NOT NULL DEFAULT 'uz'
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS started_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS last_activity
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        await conn.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN IF NOT EXISTS completed
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        # -------------------------------------------------
        # ATTEMPTS
        # -------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL
                REFERENCES users(user_id)
                ON DELETE CASCADE
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN IF NOT EXISTS raw_score
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN IF NOT EXISTS iq_score
            INTEGER NOT NULL DEFAULT 40
            """
        )

        await conn.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN IF NOT EXISTS correct
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN IF NOT EXISTS elapsed
            INTEGER NOT NULL DEFAULT 0
            """
        )

        await conn.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        # -------------------------------------------------
        # INDEXES
        # -------------------------------------------------

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_users_best_score
            ON users(best_score DESC NULLS LAST)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_attempts_user_id
            ON attempts(user_id)
            """
        )

    print("Database initialized successfully.")


# =========================================================
# USER
# =========================================================

async def upsert_user(
    tg_user: dict,
    referral_id: int | None = None,
) -> None:

    assert pool is not None

    uid = int(tg_user["id"])

    if referral_id == uid:
        referral_id = None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                first_name,
                last_name,
                username,
                referred_by
            )
            VALUES ($1, $2, $3, $4, $5)

            ON CONFLICT (user_id)
            DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                username = EXCLUDED.username,
                updated_at = NOW()
            """,
            uid,
            tg_user.get("first_name", "") or "",
            tg_user.get("last_name", "") or "",
            tg_user.get("username", "") or "",
            referral_id,
        )


async def get_user(uid: int):
    assert pool is not None

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            uid,
        )


# =========================================================
# REFERRAL
# =========================================================

async def count_referral(uid: int) -> None:
    """
    Referral faqat taklif qilingan odam
    testni boshlaganda hisoblanadi.
    """

    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            row = await conn.fetchrow(
                """
                SELECT
                    referred_by,
                    referral_counted
                FROM users
                WHERE user_id = $1
                FOR UPDATE
                """,
                uid,
            )

            if not row:
                return

            referred_by = row["referred_by"]
            already_counted = row["referral_counted"]

            if not referred_by:
                return

            if already_counted:
                return

            if int(referred_by) == uid:
                return

            inviter_exists = await conn.fetchval(
                """
                SELECT 1
                FROM users
                WHERE user_id = $1
                """,
                referred_by,
            )

            if not inviter_exists:
                return

            await conn.execute(
                """
                UPDATE users
                SET referral_counted = TRUE,
                    updated_at = NOW()
                WHERE user_id = $1
                """,
                uid,
            )

            await conn.execute(
                """
                UPDATE users
                SET referrals = referrals + 1,
                    updated_at = NOW()
                WHERE user_id = $1
                """,
                referred_by,
            )


# =========================================================
# SESSION
# =========================================================

async def create_or_get_session(
    uid: int,
    language: str,
):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            user = await conn.fetchrow(
                """
                SELECT attempts
                FROM users
                WHERE user_id = $1
                FOR UPDATE
                """,
                uid,
            )

            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="USER_NOT_FOUND",
                )

            active = await conn.fetchrow(
                """
                SELECT *
                FROM test_sessions
                WHERE user_id = $1
                  AND completed = FALSE
                FOR UPDATE
                """,
                uid,
            )

            now = datetime.now(timezone.utc)

            if active:
                last_activity = active["last_activity"]

                if last_activity is None:
                    age = 0
                else:
                    age = (
                        now - last_activity
                    ).total_seconds()

                # 2 soat ichida davom ettirish mumkin.
                if age <= 7200:
                    return active, False

                # 2 soatdan eski sessionni bekor qilamiz.
                await conn.execute(
                    """
                    DELETE FROM test_sessions
                    WHERE user_id = $1
                    """,
                    uid,
                )

            # Birinchi test bepul.
            # Keyingi test uchun payment keyin qo'shiladi.
            if int(user["attempts"]) >= 1:
                raise HTTPException(
                    status_code=402,
                    detail="PAID_RETEST",
                )

            row = await conn.fetchrow(
                """
                INSERT INTO test_sessions (
                    user_id,
                    current_index,
                    answers,
                    raw_score,
                    correct,
                    language,
                    started_at,
                    last_activity,
                    completed
                )
                VALUES (
                    $1,
                    0,
                    '[]'::jsonb,
                    0,
                    0,
                    $2,
                    NOW(),
                    NOW(),
                    FALSE
                )
                RETURNING *
                """,
                uid,
                language,
            )

            return row, True


def normalize_answers(value) -> list[int]:
    """
    asyncpg JSONB ba'zan list, ba'zan boshqa
    JSON qiymat qaytarishi mumkin.
    """
    if value is None:
        return []

    if isinstance(value, list):
        result = []

        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                pass

        return result

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return [
                    int(x)
                    for x in parsed
                    if str(x).isdigit()
                ]
        except Exception:
            pass

    return []


async def save_answer(
    uid: int,
    question_index: int,
    selected: int,
):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            row = await conn.fetchrow(
                """
                SELECT *
                FROM test_sessions
                WHERE user_id = $1
                  AND completed = FALSE
                FOR UPDATE
                """,
                uid,
            )

            if not row:
                raise HTTPException(
                    status_code=409,
                    detail="SESSION_EXPIRED",
                )

            current_index = int(
                row["current_index"]
            )

            if question_index != current_index:
                raise HTTPException(
                    status_code=409,
                    detail="OUT_OF_ORDER",
                )

            if not 0 <= selected <= 3:
                raise HTTPException(
                    status_code=400,
                    detail="INVALID_ANSWER",
                )

            if current_index >= 16:
                raise HTTPException(
                    status_code=409,
                    detail="TEST_ALREADY_COMPLETE",
                )

            answers = normalize_answers(
                row["answers"]
            )

            # Faqat aynan navbatdagi savolga javob.
            answers.append(selected)

            is_correct = (
                selected
                == CORRECT_ANSWERS[current_index]
            )

            new_correct = int(
                row["correct"]
            ) + (
                1 if is_correct else 0
            )

            new_raw = int(
                row["raw_score"]
            ) + (
                WEIGHTS[current_index]
                if is_correct
                else 0
            )

            new_index = current_index + 1

            await conn.execute(
                """
                UPDATE test_sessions
                SET
                    current_index = $2,
                    answers = $3::jsonb,
                    raw_score = $4,
                    correct = $5,
                    last_activity = NOW()
                WHERE user_id = $1
                """,
                uid,
                new_index,
                json.dumps(answers),
                new_raw,
                new_correct,
            )

            return {
                "index": new_index,
                "correct": new_correct,
                "raw": new_raw,
            }


# =========================================================
# IQ SCORE
# =========================================================

def calculate_iq(raw_score: int) -> int:
    """
    ZAKO mahsulot skori.
    Bu klinik/normativ IQ testi emas.
    """

    ratio = (
        raw_score / TOTAL_WEIGHT
    )

    iq = round(
        40 + ratio * 120
    )

    return max(
        40,
        min(160, iq),
    )


# =========================================================
# FINISH SESSION
# =========================================================

async def finish_session(uid: int):
    assert pool is not None

    async with pool.acquire() as conn:
        async with conn.transaction():

            row = await conn.fetchrow(
                """
                SELECT *
                FROM test_sessions
                WHERE user_id = $1
                  AND completed = FALSE
                FOR UPDATE
                """,
                uid,
            )

            if not row:
                raise HTTPException(
                    status_code=409,
                    detail="SESSION_EXPIRED",
                )

            answers = normalize_answers(
                row["answers"]
            )

            if len(answers) != 16:
                raise HTTPException(
                    status_code=409,
                    detail="INCOMPLETE",
                )

            correct = 0
            raw = 0

            for index, answer in enumerate(answers):
                if answer == CORRECT_ANSWERS[index]:
                    correct += 1
                    raw += WEIGHTS[index]

            iq = calculate_iq(raw)

            elapsed = max(
                0,
                round(
                    (
                        datetime.now(timezone.utc)
                        - row["started_at"]
                    ).total_seconds()
                ),
            )

            # Natijani saqlash
            await conn.execute(
                """
                INSERT INTO attempts (
                    user_id,
                    raw_score,
                    iq_score,
                    correct,
                    elapsed
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5
                )
                """,
                uid,
                raw,
                iq,
                correct,
                elapsed,
            )

            # User statistikasi
            # MUHIM: bu yerda endi ortiqcha $4 argument yo'q.
            await conn.execute(
                """
                UPDATE users
                SET
                    attempts = attempts + 1,

                    best_score =
                        CASE
                            WHEN best_score IS NULL
                                 OR $2 > best_score
                            THEN $2
                            ELSE best_score
                        END,

                    best_raw =
                        CASE
                            WHEN best_score IS NULL
                                 OR $2 > best_score
                            THEN $3
                            ELSE best_raw
                        END,

                    best_time =
                        CASE
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
                        END,

                    updated_at = NOW()

                WHERE user_id = $1
                """,
                uid,
                iq,
                raw,
                elapsed,
            )

            # Test session tugadi
            await conn.execute(
                """
                DELETE FROM test_sessions
                WHERE user_id = $1
                """,
                uid,
            )

            return (
                iq,
                raw,
                correct,
                elapsed,
            )


# =========================================================
# RANK
# =========================================================

async def get_rank(uid: int):
    assert pool is not None

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT
                best_score,
                best_time
            FROM users
            WHERE user_id = $1
            """,
            uid,
        )

        if not row:
            return None

        if row["best_score"] is None:
            return None

        rank = await conn.fetchval(
            """
            SELECT COUNT(*) + 1
            FROM users
            WHERE best_score IS NOT NULL
              AND (
                    best_score > $1
                    OR (
                        best_score = $1
                        AND COALESCE(
                            best_time,
                            2147483647
                        )
                        <
                        COALESCE(
                            $2,
                            2147483647
                        )
                    )
              )
            """,
            row["best_score"],
            row["best_time"],
        )

        return int(rank)


# =========================================================
# TELEGRAM MINI APP AUTH
# =========================================================

def validate_init_data(
    init_data: str,
) -> dict:

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="INVALID_INIT_DATA",
        )

    try:
        pairs = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = pairs.pop(
            "hash",
            None,
        )

        if not received_hash:
            raise ValueError(
                "hash missing"
            )

        auth_date = int(
            pairs.get(
                "auth_date",
                "0",
            )
        )

        now = int(
            datetime.now(
                timezone.utc
            ).timestamp()
        )

        # Telegram initData 24 soatdan eski bo'lmasin.
        if (
            auth_date <= 0
            or now - auth_date > 86400
        ):
            raise ValueError(
                "auth_date expired"
            )

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(
                pairs.items()
            )
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash,
        ):
            raise ValueError(
                "hash mismatch"
            )

        raw_user = pairs.get("user")

        if not raw_user:
            raise ValueError(
                "user missing"
            )

        user = json.loads(
            raw_user
        )

        if not user.get("id"):
            raise ValueError(
                "user id missing"
            )

        return user

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "Telegram initData validation error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=401,
            detail="INVALID_INIT_DATA",
        ) from exc


async def api_user(
    request: Request,
) -> dict:

    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    )

    return validate_init_data(
        init_data
    )


# =========================================================
# WEB ROUTES
# =========================================================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "IQ TEST BOT",
    }


@app.get("/health")
async def health():

    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_NOT_READY",
        )

    async with pool.acquire() as conn:
        await conn.fetchval(
            "SELECT 1"
        )

    return {
        "status": "ok",
        "database": "ok",
    }


@app.get("/app")
async def app_page():
    return FileResponse(
        WEBAPP_DIR / "index.html"
    )


@app.get("/api/config")
async def api_config():
    return {
        "bot_username": BOT_USERNAME,
        "zako_url": ZAKO_URL,
        "webapp_url": WEBAPP_URL,
    }


# =========================================================
# START SESSION API
# =========================================================

@app.post("/api/session/start")
async def api_start(
    request: Request,
):

    tg_user = await api_user(
        request
    )

    uid = int(
        tg_user["id"]
    )

    try:
        body = await request.json()
    except Exception:
        body = {}

    language = body.get(
        "language",
        "uz",
    )

    if language not in {
        "uz",
        "ru",
        "en",
    }:
        language = "uz"

    await upsert_user(
        tg_user
    )

    # Referral aynan test boshlanganda hisoblanadi.
    await count_referral(
        uid
    )

    row, created = (
        await create_or_get_session(
            uid,
            language,
        )
    )

    elapsed = max(
        0,
        round(
            (
                datetime.now(timezone.utc)
                - row["started_at"]
            ).total_seconds()
        ),
    )

    user = await get_user(
        uid
    )

    return {
        "user_id": uid,
        "created": created,
        "index": int(
            row["current_index"]
        ),
        "answers": normalize_answers(
            row["answers"]
        ),
        "elapsed": elapsed,
        "attempts": int(
            user["attempts"]
        ) if user else 0,
    }


# =========================================================
# ANSWER API
# =========================================================

@app.post("/api/session/answer")
async def api_answer(
    request: Request,
):

    tg_user = await api_user(
        request
    )

    uid = int(
        tg_user["id"]
    )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="INVALID_JSON",
        )

    try:
        index = int(
            body.get(
                "index",
                -1,
            )
        )

        selected = int(
            body.get(
                "selected",
                -1,
            )
        )

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="INVALID_ANSWER",
        )

    result = await save_answer(
        uid,
        index,
        selected,
    )

    return {
        "ok": True,
        **result,
    }


# =========================================================
# FINISH API
# =========================================================

@app.post("/api/session/finish")
async def api_finish(
    request: Request,
):

    tg_user = await api_user(
        request
    )

    uid = int(
        tg_user["id"]
    )

    iq, raw, correct, elapsed = (
        await finish_session(uid)
    )

    rank = await get_rank(
        uid
    )

    return {
        "iq": iq,
        "raw": raw,
        "correct": correct,
        "elapsed": elapsed,
        "rank": rank,
    }


# =========================================================
# PROFILE API
# =========================================================

@app.get("/api/profile")
async def api_profile(
    request: Request,
):

    tg_user = await api_user(
        request
    )

    uid = int(
        tg_user["id"]
    )

    await upsert_user(
        tg_user
    )

    user = await get_user(
        uid
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="USER_NOT_FOUND",
        )

    rank = await get_rank(
        uid
    )

    return {
        "first_name": user[
            "first_name"
        ],
        "last_name": user[
            "last_name"
        ],
        "username": user[
            "username"
        ],
        "attempts": int(
            user["attempts"]
        ),
        "best_score": user[
            "best_score"
        ],
        "best_time": user[
            "best_time"
        ],
        "referrals": int(
            user["referrals"]
        ),
        "rank": rank,
    }


# =========================================================
# RANKING API
# =========================================================

@app.get("/api/ranking")
async def api_ranking(
    request: Request,
):

    await api_user(
        request
    )

    assert pool is not None

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                first_name,
                last_name,
                username,
                best_score,
                best_time
            FROM users
            WHERE best_score IS NOT NULL
            ORDER BY
                best_score DESC,
                best_time ASC NULLS LAST,
                created_at ASC
            LIMIT 50
            """
        )

    items = []

    for row in rows:
        items.append(
            {
                "first_name": row[
                    "first_name"
                ],
                "last_name": row[
                    "last_name"
                ],
                "username": row[
                    "username"
                ],
                "best_score": row[
                    "best_score"
                ],
                "best_time": row[
                    "best_time"
                ],
            }
        )

    return {
        "items": items
    }


# =========================================================
# CERTIFICATE
# =========================================================

def get_font(
    size: int,
    bold: bool = False,
):
    paths = []

    if bold:
        paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]
        )
    else:
        paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
        )

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(
                path,
                size,
            )

    return ImageFont.load_default()


def make_certificate_png(
    name: str,
    iq: int,
) -> bytes:

    width = 1400
    height = 900

    image = Image.new(
        "RGB",
        (width, height),
        "#0b0d16",
    )

    draw = ImageDraw.Draw(
        image
    )

    def center_text(
        text: str,
        y: int,
        font,
        fill: str = "#ffffff",
    ):
        box = draw.textbbox(
            (0, 0),
            text,
            font=font,
        )

        text_width = (
            box[2] - box[0]
        )

        x = (
            width - text_width
        ) / 2

        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill,
        )

    # Outer border
    draw.rounded_rectangle(
        (
            35,
            35,
            width - 35,
            height - 35,
        ),
        radius=36,
        outline="#8b6cff",
        width=4,
    )

    # Inner border
    draw.rounded_rectangle(
        (
            58,
            58,
            width - 58,
            height - 58,
        ),
        radius=28,
        outline="#2b3040",
        width=2,
    )

    center_text(
        "ZAKO IQ",
        110,
        get_font(64, True),
        "#b8a8ff",
    )

    center_text(
        "IQ TEST CERTIFICATE",
        215,
        get_font(30, True),
        "#aeb5c6",
    )

    center_text(
        str(iq),
        285,
        get_font(150, True),
        "#ffffff",
    )

    center_text(
        "IQ SCORE",
        470,
        get_font(30, True),
        "#b8a8ff",
    )

    clean_name = (
        name.strip()
        if name
        else "User"
    )

    center_text(
        clean_name[:32],
        545,
        get_font(46, True),
        "#ffffff",
    )

    center_text(
        "ZAKO IQ testining taxminiy natijasi",
        640,
        get_font(25),
        "#aeb5c6",
    )

    center_text(
        datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d"),
        700,
        get_font(22),
        "#777f91",
    )

    output = BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    return output.getvalue()


@app.get("/api/certificate")
async def api_certificate(
    request: Request,
):

    tg_user = await api_user(
        request
    )

    uid = int(
        tg_user["id"]
    )

    user = await get_user(
        uid
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="NO_RESULT",
        )

    if user["best_score"] is None:
        raise HTTPException(
            status_code=404,
            detail="NO_RESULT",
        )

    # 2 ta haqiqiy referral kerak.
    if int(user["referrals"]) < 2:
        raise HTTPException(
            status_code=403,
            detail="REFERRALS_REQUIRED",
        )

    if not user["cert_claimed"]:
        assert pool is not None

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET
                    cert_claimed = TRUE,
                    updated_at = NOW()
                WHERE user_id = $1
                """,
                uid,
            )

    data = make_certificate_png(
        user["first_name"]
        or "User",
        int(user["best_score"]),
    )

    return StreamingResponse(
        iter([data]),
        media_type="image/png",
        headers={
            "Content-Disposition":
                "inline; "
                "filename=zako-iq-certificate.png"
        },
    )


# =========================================================
# TELEGRAM BOT
# =========================================================

def bot_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧠 IQ TESTNI BOSHLASH",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    ),
                )
            ]
        ]
    )


@dp.message(CommandStart())
async def start(
    message: Message,
):

    if not message.from_user:
        return

    referral_id = None

    parts = (
        message.text or ""
    ).split(
        maxsplit=1
    )

    if (
        len(parts) == 2
        and parts[1].startswith("ref_")
    ):
        try:
            referral_id = int(
                parts[1][4:]
            )
        except ValueError:
            referral_id = None

    tg_user = {
        "id": message.from_user.id,
        "first_name":
            message.from_user.first_name
            or "",
        "last_name":
            message.from_user.last_name
            or "",
        "username":
            message.from_user.username
            or "",
    }

    await upsert_user(
        tg_user,
        referral_id,
    )

    await message.answer(
        (
            "🧠 <b>IQ TEST BOT</b>\n\n"
            "16 ta original mantiqiy puzzle "
            "orqali o‘zingizni sinab ko‘ring.\n\n"
            "• Birinchi test — bepul\n"
            "• IQ SCORE\n"
            "• Real reyting\n"
            "• Sertifikat\n"
            "• UZ / RU / EN\n\n"
            "Test to‘liq Mini App ichida ishlaydi."
        ),
        reply_markup=bot_keyboard(),
        parse_mode="HTML",
    )


# =========================================================
# WEB SERVER
# =========================================================

async def run_web():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

    server = uvicorn.Server(
        config
    )

    await server.serve()


# =========================================================
# MAIN
# =========================================================

async def main():

    global bot
    global BOT_USERNAME

    await init_db()

    bot = Bot(
        BOT_TOKEN
    )

    me = await bot.get_me()

    BOT_USERNAME = (
        me.username or ""
    )

    print(
        f"Bot started: @{BOT_USERNAME}"
    )

    # Telegram chat menyusida ham Mini App chiqadi.
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🧠 IQ TEST",
                web_app=WebAppInfo(
                    url=WEBAPP_URL
                ),
            )
        )

        print(
            "Telegram Mini App menu button configured."
        )

    except Exception as exc:
        print(
            "Menu button setup warning:",
            repr(exc),
        )

    try:

        await asyncio.gather(
            dp.start_polling(bot),
            run_web(),
        )

    finally:

        try:
            await bot.session.close()
        except Exception:
            pass

        if pool is not None:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
