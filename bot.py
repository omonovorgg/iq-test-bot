import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

import asyncpg
import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/")

PORT = int(os.environ.get("PORT", "10000"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)

# Retest price.
PRICE_UZS = int(os.environ.get("PRICE_UZS", "3000"))

WEBAPP_DIR = Path(__file__).parent / "webapp"

if not WEBAPP_DIR.exists():
    raise RuntimeError("webapp directory not found")

if not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("WEBAPP_URL must start with https://")


# ============================================================
# TEST DEFINITION
# ============================================================
#
# IMPORTANT:
#
# These are ORIGINAL reasoning items.
#
# They are designed around:
#   - pattern induction
#   - relational reasoning
#   - spatial transformation
#   - classification
#   - numerical abstraction
#   - multi-rule reasoning
#
# They are NOT copied from Raven or another proprietary test.
#
# "correct" remains SERVER-SIDE.
# It is never sent to the Mini App.
#
# Difficulty:
#   1 = easiest
#   8 = hardest
#
# The scoring system later maps the weighted raw score to the
# entertainment-style "IQ" number shown by the product.
#
# IMPORTANT PSYCHOMETRIC NOTE:
# A real norm-referenced IQ score requires pilot testing,
# item analysis, reliability, validity and normative data.
# ============================================================


QUESTIONS = [

    # --------------------------------------------------------
    # 01 — BASIC ABSTRACT PATTERN
    # Rule:
    # triangle rotates 90° clockwise each step.
    # Sequence:
    # ↑ -> → -> ↓ -> ?
    # Answer: ←
    # --------------------------------------------------------
    {
        "id": "Q01",
        "difficulty": 1,
        "category": "PATTERN",
        "type": "visual",
        "prompt": "Ketma-ketlikni davom ettiradigan belgini toping.",
        "visual": {
            "kind": "sequence",
            "items": ["↑", "→", "↓", "?"]
        },
        "options": ["←", "↑", "→", "↓"],
        "correct": 0,
        "weight": 5,
    },

    # --------------------------------------------------------
    # 02 — SIMPLE RELATION
    # --------------------------------------------------------
    {
        "id": "Q02",
        "difficulty": 1,
        "category": "RELATION",
        "type": "visual",
        "prompt": "Qaysi belgi qoidani to‘g‘ri davom ettiradi?",
        "visual": {
            "kind": "sequence",
            "items": ["○", "●", "○", "●", "?"]
        },
        "options": ["○", "●", "△", "□"],
        "correct": 0,
        "weight": 5,
    },

    # --------------------------------------------------------
    # 03 — NUMBER TRANSFORMATION
    #
    # 2 -> 5 (+3)
    # 5 -> 11 (+6)
    # 11 -> 23 (+12)
    # next = +24 => 47
    # --------------------------------------------------------
    {
        "id": "Q03",
        "difficulty": 2,
        "category": "ABSTRACT",
        "type": "text",
        "prompt": "Qatorni davom ettiring: 2, 5, 11, 23, ?",
        "visual": None,
        "options": ["35", "45", "47", "49"],
        "correct": 2,
        "weight": 7,
    },

    # --------------------------------------------------------
    # 04 — CLASSIFICATION
    #
    # Three options have mirror symmetry;
    # one does not.
    # --------------------------------------------------------
    {
        "id": "Q04",
        "difficulty": 2,
        "category": "CLASSIFICATION",
        "type": "visual",
        "prompt": "Qaysi variant qolgan uchtasidan mantiqan farq qiladi?",
        "visual": {
            "kind": "symbols",
            "items": [
                "●○●",
                "○●○",
                "△○△",
                "●○△"
            ]
        },
        "options": [
            "●○●",
            "○●○",
            "△○△",
            "●○△"
        ],
        "correct": 3,
        "weight": 7,
    },

    # --------------------------------------------------------
    # 05 — ANALOGICAL TRANSFORMATION
    #
    # Shape moves one position clockwise.
    # --------------------------------------------------------
    {
        "id": "Q05",
        "difficulty": 3,
        "category": "ANALOGY",
        "type": "visual",
        "prompt": "Birinchi juftlikdagi o‘zgarishni ikkinchi juftlikka qo‘llang.",
        "visual": {
            "kind": "analogy",
            "left": "▲○",
            "middle": "○▲",
            "right": "■◇"
        },
        "options": [
            "■◇",
            "◇■",
            "□◇",
            "◇□"
        ],
        "correct": 1,
        "weight": 9,
    },

    # --------------------------------------------------------
    # 06 — MULTIPLICATIVE SEQUENCE
    #
    # 3, 6, 12, 24, 48
    # --------------------------------------------------------
    {
        "id": "Q06",
        "difficulty": 3,
        "category": "ABSTRACT",
        "type": "text",
        "prompt": "Qatorni davom ettiring: 3, 6, 12, 24, ?",
        "visual": None,
        "options": ["36", "42", "48", "54"],
        "correct": 2,
        "weight": 9,
    },

    # --------------------------------------------------------
    # 07 — SPATIAL ROTATION
    #
    # L-shape rotated 90 degrees.
    # --------------------------------------------------------
    {
        "id": "Q07",
        "difficulty": 4,
        "category": "SPATIAL",
        "type": "visual",
        "prompt": "Shakl 90° o‘ngga aylantirilsa, qaysi ko‘rinish hosil bo‘ladi?",
        "visual": {
            "kind": "rotation",
            "shape": "L"
        },
        "options": [
            "┌",
            "┐",
            "└",
            "┘"
        ],
        "correct": 1,
        "weight": 11,
    },

    # --------------------------------------------------------
    # 08 — TWO-STEP NUMBER RULE
    #
    # 1 -> 4 (+3)
    # 4 -> 10 (+6)
    # 10 -> 22 (+12)
    # 22 -> 46 (+24)
    # 46 -> 94 (+48)
    # --------------------------------------------------------
    {
        "id": "Q08",
        "difficulty": 4,
        "category": "ABSTRACT",
        "type": "text",
        "prompt": "Qatorni davom ettiring: 1, 4, 10, 22, 46, ?",
        "visual": None,
        "options": ["82", "90", "94", "98"],
        "correct": 2,
        "weight": 11,
    },

    # --------------------------------------------------------
    # 09 — MATRIX COUNTING
    #
    # Row/column pattern:
    # 2 3 5
    # 3 4 7
    # 5 7 ?
    #
    # third = first + second => 12
    # --------------------------------------------------------
    {
        "id": "Q09",
        "difficulty": 5,
        "category": "MATRIX",
        "type": "matrix",
        "prompt": "Har bir qatorda uchinchi qiymat birinchi ikkitasining yig‘indisidir. X ni toping.",
        "visual": {
            "kind": "numeric_matrix",
            "matrix": [
                ["2", "3", "5"],
                ["3", "4", "7"],
                ["5", "7", "?"]
            ]
        },
        "options": ["10", "11", "12", "13"],
        "correct": 2,
        "weight": 13,
    },

    # --------------------------------------------------------
    # 10 — ALTERNATING OPERATION
    #
    # +2, *2:
    # 3 +2 =5
    # 5*2=10
    # 10+2=12
    # 12*2=24
    # 24+2=26
    # --------------------------------------------------------
    {
        "id": "Q10",
        "difficulty": 5,
        "category": "SEQUENCE",
        "type": "text",
        "prompt": "Qatorni davom ettiring: 3, 5, 10, 12, 24, 26, ?",
        "visual": None,
        "options": ["28", "48", "50", "52"],
        "correct": 1,
        "weight": 13,
    },

    # --------------------------------------------------------
    # 11 — MULTI-RULE SHAPE MATRIX
    #
    # Row operation:
    # first shape + second shape = third shape
    # using shape combination.
    # --------------------------------------------------------
    {
        "id": "Q11",
        "difficulty": 6,
        "category": "MATRIX",
        "type": "visual",
        "prompt": "Qator va ustundagi ikkita qoidani birgalikda qo‘llab, X ni toping.",
        "visual": {
            "kind": "shape_matrix",
            "matrix": [
                ["○", "△", "○△"],
                ["□", "◇", "□◇"],
                ["○□", "△◇", "?"]
            ]
        },
        "options": [
            "○△",
            "□◇",
            "○□△◇",
            "○△□◇"
        ],
        "correct": 3,
        "weight": 15,
    },

    # --------------------------------------------------------
    # 12 — SPATIAL COMPOSITION
    # --------------------------------------------------------
    {
        "id": "Q12",
        "difficulty": 6,
        "category": "SPATIAL",
        "type": "visual",
        "prompt": "Chapdagi ikki shakl birlashtirilsa, qaysi natija hosil bo‘ladi?",
        "visual": {
            "kind": "composition",
            "left": "└",
            "right": "┐"
        },
        "options": [
            "□",
            "◇",
            "△",
            "○"
        ],
        "correct": 0,
        "weight": 15,
    },

    # --------------------------------------------------------
    # 13 — HIGHER-ORDER NUMBER PATTERN
    #
    # Differences:
    # 4, 8, 16, 32 -> next 64
    # 3,7,15,31,63 => next 127
    # --------------------------------------------------------
    {
        "id": "Q13",
        "difficulty": 7,
        "category": "ABSTRACT",
        "type": "text",
        "prompt": "Qatorni davom ettiring: 3, 7, 15, 31, 63, ?",
        "visual": None,
        "options": ["95", "111", "127", "129"],
        "correct": 2,
        "weight": 17,
    },

    # --------------------------------------------------------
    # 14 — DUAL-CONSTRAINT LOGIC
    #
    # Need number divisible by 4 and odd? impossible.
    # Instead:
    # divisible by 3 and even => 12.
    # --------------------------------------------------------
    {
        "id": "Q14",
        "difficulty": 7,
        "category": "LOGIC",
        "type": "text",
        "prompt": "Qaysi son bir vaqtning o‘zida juft va 3 ga bo‘linadi?",
        "visual": None,
        "options": ["9", "10", "12", "15"],
        "correct": 2,
        "weight": 17,
    },

    # --------------------------------------------------------
    # 15 — ADVANCED ALTERNATING TRANSFORMATION
    #
    # +3, *2:
    # 4+3=7
    # 7*2=14
    # 14+3=17
    # 17*2=34
    # 34+3=37
    # 37*2=74
    # --------------------------------------------------------
    {
        "id": "Q15",
        "difficulty": 8,
        "category": "ADVANCED",
        "type": "text",
        "prompt": "Navbatma-navbat +3 va ×2 qoidasini qo‘llang. 4, 7, 14, 17, 34, 37, ?",
        "visual": None,
        "options": ["71", "72", "74", "80"],
        "correct": 2,
        "weight": 19,
    },

    # --------------------------------------------------------
    # 16 — HIGHEST DIFFICULTY ABSTRACT MATRIX
    #
    # Four components:
    # shape, count, fill, direction.
    #
    # This item is intentionally the hardest.
    # --------------------------------------------------------
    {
        "id": "Q16",
        "difficulty": 8,
        "category": "ADVANCED MATRIX",
        "type": "matrix",
        "prompt": "Shakl, son va yo‘nalishdagi uchta qoidani birlashtirib, X ni toping.",
        "visual": {
            "kind": "advanced_matrix",
            "matrix": [
                ["○↑", "○→", "○↓"],
                ["△↑", "△→", "△↓"],
                ["□↑", "□→", "?"]
            ]
        },
        "options": [
            "□←",
            "□↑",
            "□↓",
            "△↓"
        ],
        "correct": 2,
        "weight": 23,
    },
]


QUESTIONS_COUNT = len(QUESTIONS)

QUESTION_MAP = {
    q["id"]: q
    for q in QUESTIONS
}

QUESTION_ORDER = [
    q["id"]
    for q in QUESTIONS
]

MAX_RAW = sum(
    q["weight"]
    for q in QUESTIONS
)


# ============================================================
# SCORE
# ============================================================

def calculate_raw_score(answers: dict):
    raw = 0
    correct = 0

    for question_id, selected in answers.items():

        question = QUESTION_MAP.get(question_id)

        if not question:
            continue

        try:
            selected = int(selected)
        except (TypeError, ValueError):
            continue

        if selected == question["correct"]:
            raw += question["weight"]
            correct += 1

    return raw, correct


def calculate_iq_style_score(raw: int):
    """
    Product score.

    This intentionally produces the requested high-end display range.
    It is NOT a clinically standardized IQ conversion.

    Minimum: 70
    Maximum: 178
    """

    if MAX_RAW <= 0:
        return 70

    normalized = raw / MAX_RAW

    score = round(
        70 + normalized * 108
    )

    return max(70, min(178, score))


# ============================================================
# PUBLIC QUESTION SERIALIZATION
# ============================================================

def public_question(question):
    """
    Remove the answer key before sending a question to the client.
    """

    return {
        "id": question["id"],
        "difficulty": question["difficulty"],
        "category": question["category"],
        "type": question["type"],
        "prompt": question["prompt"],
        "visual": question["visual"],
        "options": question["options"],
    }


def public_questions():
    return [
        public_question(q)
        for q in QUESTIONS
    ]


# ============================================================
# TELEGRAM AUTH
# ============================================================

def validate_init_data(init_data: str):

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Telegram authorization required"
        )

    try:
        pairs = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram init data"
        )

    received_hash = pairs.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            status_code=401,
            detail="Telegram hash missing"
        )

    auth_date = int(
        pairs.get("auth_date", "0")
    )

    # 24 hour validity.
    if not auth_date:
        raise HTTPException(
            status_code=401,
            detail="Telegram auth_date missing"
        )

    if abs(
        int(time.time()) - auth_date
    ) > 86400:

        raise HTTPException(
            status_code=401,
            detail="Telegram session expired"
        )

    data_check_string = "\n".join(
        f"{key}={pairs[key]}"
        for key in sorted(pairs)
    )

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        calculated_hash,
        received_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram signature"
        )

    user_raw = pairs.get("user")

    if not user_raw:
        raise HTTPException(
            status_code=401,
            detail="Telegram user missing"
        )

    try:
        return json.loads(user_raw)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram user data"
        )


async def authenticate(request: Request):

    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    user = validate_init_data(init_data)

    try:
        user_id = int(user["id"])
    except Exception:

        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram user ID"
        )

    return user_id, user


# ============================================================
# DATABASE
# ============================================================

async def init_db(pool):

    async with pool.acquire() as con:

        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (

                user_id BIGINT PRIMARY KEY,

                username TEXT,

                first_name TEXT,

                last_name TEXT,

                attempts INTEGER NOT NULL DEFAULT 0,

                best_score INTEGER NOT NULL DEFAULT 0,

                best_raw INTEGER NOT NULL DEFAULT 0,

                best_time INTEGER NOT NULL DEFAULT 0,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );


            CREATE TABLE IF NOT EXISTS test_sessions (

                attempt_id UUID PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                question_order JSONB NOT NULL,

                started_at TIMESTAMPTZ NOT NULL,

                finished_at TIMESTAMPTZ,

                answers JSONB,

                elapsed_seconds INTEGER,

                raw_score INTEGER,

                correct INTEGER,

                iq_score INTEGER,

                status TEXT NOT NULL DEFAULT 'active',

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );


            CREATE INDEX IF NOT EXISTS
            idx_test_sessions_user_status

            ON test_sessions(
                user_id,
                status
            );


            CREATE TABLE IF NOT EXISTS attempts (

                attempt_id UUID PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                raw_score INTEGER NOT NULL,

                iq_score INTEGER NOT NULL,

                correct INTEGER NOT NULL,

                elapsed_seconds INTEGER NOT NULL,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );


            CREATE INDEX IF NOT EXISTS
            idx_attempts_ranking

            ON attempts(
                iq_score DESC,
                elapsed_seconds ASC
            );


            CREATE TABLE IF NOT EXISTS payments (

                id BIGSERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,

                purpose TEXT NOT NULL,

                amount INTEGER NOT NULL,

                status TEXT NOT NULL DEFAULT 'pending',

                consumed BOOLEAN NOT NULL DEFAULT FALSE,

                proof_file_id TEXT,

                approved_at TIMESTAMPTZ,

                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );


            CREATE INDEX IF NOT EXISTS
            idx_payments_user

            ON payments(
                user_id,
                purpose,
                status,
                consumed
            );
            """
        )


async def upsert_user(pool, telegram_user):

    async with pool.acquire() as con:

        await con.execute(
            """
            INSERT INTO users(
                user_id,
                username,
                first_name,
                last_name
            )

            VALUES(
                $1,
                $2,
                $3,
                $4
            )

            ON CONFLICT(user_id)

            DO UPDATE SET

                username = EXCLUDED.username,

                first_name = EXCLUDED.first_name,

                last_name = EXCLUDED.last_name,

                updated_at = NOW()
            """,

            int(telegram_user["id"]),

            telegram_user.get("username"),

            telegram_user.get("first_name"),

            telegram_user.get("last_name"),
        )


# ============================================================
# MODELS
# ============================================================

class FinishPayload(BaseModel):

    attempt_id: uuid.UUID

    answers: dict[str, int] = Field(
        default_factory=dict
    )

    elapsed_seconds: int = Field(
        ge=0,
        le=3600
    )


class PaymentCreate(BaseModel):

    purpose: str = "retest"


# ============================================================
# FASTAPI
# ============================================================

async def create_app():

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        ssl="require",
    )

    await init_db(pool)

    app = FastAPI(
        title="IQ Test Bot",
        version="2.0.0"
    )


    # --------------------------------------------------------
    # HEALTH
    # --------------------------------------------------------

    @app.get("/health")
    async def health():

        return {
            "ok": True,
            "service": "iq-test-bot",
            "version": "2.0.0",
        }


    @app.get("/")
    async def root():

        return {
            "ok": True,
            "service": "iq-test-bot"
        }


    # --------------------------------------------------------
    # MINI APP
    # --------------------------------------------------------

    @app.get("/app")
    async def app_page():

        return FileResponse(
            WEBAPP_DIR / "index.html"
        )


    @app.get("/static/{file_path:path}")
    async def static_file(file_path: str):

        target = (
            WEBAPP_DIR / file_path
        ).resolve()

        web_root = WEBAPP_DIR.resolve()

        if (
            target != web_root
            and web_root not in target.parents
        ):

            raise HTTPException(
                status_code=404
            )

        if not target.is_file():

            raise HTTPException(
                status_code=404
            )

        return FileResponse(target)


    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    @app.get("/api/config")
    async def api_config(request: Request):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )

        async with pool.acquire() as con:

            user = await con.fetchrow(
                """
                SELECT
                    attempts,
                    best_score,
                    best_time
                FROM users
                WHERE user_id=$1
                """,
                user_id
            )

        return {

            "question_count": QUESTIONS_COUNT,

            "max_score": 178,

            "price_uzs": PRICE_UZS,

            "attempts": (
                user["attempts"]
                if user
                else 0
            ),

            "best_score": (
                user["best_score"]
                if user
                else 0
            ),

            "best_time": (
                user["best_time"]
                if user
                else 0
            ),

            "test_version": "2.0.0",

            "score_type": "reasoning_score",

            "standardized_iq": False,
        }


    # --------------------------------------------------------
    # TEST PACKAGE
    # --------------------------------------------------------

    @app.get("/api/test/package")
    async def test_package(request: Request):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )

        return {

            "version": "2.0.0",

            "question_count": QUESTIONS_COUNT,

            "questions": public_questions(),

            # Approximate maximum duration.
            "duration_seconds": 16 * 30,
        }


    # --------------------------------------------------------
    # START SESSION
    # --------------------------------------------------------

    @app.post("/api/session/start")
    async def session_start(request: Request):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )

        async with pool.acquire() as con:

            async with con.transaction():

                # Lock user.
                user = await con.fetchrow(
                    """
                    SELECT
                        attempts
                    FROM users
                    WHERE user_id=$1
                    FOR UPDATE
                    """,
                    user_id
                )

                if not user:

                    raise HTTPException(
                        status_code=404,
                        detail="User not found"
                    )

                attempts = user["attempts"]


                # Abandon old active sessions.
                await con.execute(
                    """
                    UPDATE test_sessions

                    SET
                        status='abandoned',
                        finished_at=NOW()

                    WHERE
                        user_id=$1
                        AND status='active'
                    """,
                    user_id
                )


                # First attempt is free.
                #
                # Further attempts require an approved
                # and unused retest payment.

                if attempts > 0:

                    payment = await con.fetchrow(
                        """
                        SELECT
                            id

                        FROM payments

                        WHERE
                            user_id=$1
                            AND purpose='retest'
                            AND status='approved'
                            AND consumed=FALSE

                        ORDER BY id ASC

                        LIMIT 1

                        FOR UPDATE
                        """,
                        user_id
                    )

                    if not payment:

                        raise HTTPException(
                            status_code=402,
                            detail="RETEST_PAYMENT_REQUIRED"
                        )

                    await con.execute(
                        """
                        UPDATE payments

                        SET consumed=TRUE

                        WHERE id=$1
                        """,
                        payment["id"]
                    )


                attempt_id = uuid.uuid4()

                started_at = datetime.now(
                    timezone.utc
                )


                await con.execute(
                    """
                    INSERT INTO test_sessions(

                        attempt_id,

                        user_id,

                        question_order,

                        started_at,

                        status

                    )

                    VALUES(

                        $1,

                        $2,

                        $3::jsonb,

                        $4,

                        'active'
                    )
                    """,

                    attempt_id,

                    user_id,

                    json.dumps(
                        QUESTION_ORDER
                    ),

                    started_at,
                )


        return {

            "ok": True,

            "attempt_id": str(
                attempt_id
            ),

            "started_at":
                started_at.isoformat(),

            "duration_seconds":
                16 * 30,

            "questions":
                public_questions(),
        }


    # --------------------------------------------------------
    # FINISH TEST
    # --------------------------------------------------------

    @app.post("/api/session/finish")
    async def session_finish(
        payload: FinishPayload,
        request: Request
    ):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )

        async with pool.acquire() as con:

            async with con.transaction():

                session = await con.fetchrow(
                    """
                    SELECT *

                    FROM test_sessions

                    WHERE
                        attempt_id=$1
                        AND user_id=$2

                    FOR UPDATE
                    """,

                    payload.attempt_id,

                    user_id,
                )

                if not session:

                    raise HTTPException(
                        status_code=404,
                        detail="Attempt not found"
                    )


                # Idempotency:
                #
                # If client retries the same attempt,
                # NEVER create another attempt/ranking entry.

                if session["status"] == "finished":

                    return {

                        "ok": True,

                        "already_processed": True,

                        "attempt_id":
                            str(payload.attempt_id),

                        "iq_score":
                            session["iq_score"],

                        "raw_score":
                            session["raw_score"],

                        "correct":
                            session["correct"],

                        "elapsed_seconds":
                            session["elapsed_seconds"],
                    }


                allowed_ids = set(
                    session["question_order"]
                )


                clean_answers = {}

                for question_id, answer in (
                    payload.answers.items()
                ):

                    question_id = str(
                        question_id
                    )

                    if question_id not in allowed_ids:
                        continue

                    try:
                        answer = int(answer)
                    except (
                        TypeError,
                        ValueError
                    ):
                        continue

                    if not 0 <= answer <= 3:
                        continue

                    clean_answers[
                        question_id
                    ] = answer


                raw_score, correct = (
                    calculate_raw_score(
                        clean_answers
                    )
                )


                iq_score = (
                    calculate_iq_style_score(
                        raw_score
                    )
                )


                await con.execute(
                    """
                    UPDATE test_sessions

                    SET

                        answers=$1::jsonb,

                        elapsed_seconds=$2,

                        raw_score=$3,

                        correct=$4,

                        iq_score=$5,

                        status='finished',

                        finished_at=NOW()

                    WHERE
                        attempt_id=$6
                    """,

                    json.dumps(
                        clean_answers
                    ),

                    payload.elapsed_seconds,

                    raw_score,

                    correct,

                    iq_score,

                    payload.attempt_id,
                )


                # Unique attempt_id makes this safe against
                # duplicate network retries.

                await con.execute(
                    """
                    INSERT INTO attempts(

                        attempt_id,

                        user_id,

                        raw_score,

                        iq_score,

                        correct,

                        elapsed_seconds

                    )

                    VALUES(

                        $1,

                        $2,

                        $3,

                        $4,

                        $5,

                        $6
                    )

                    ON CONFLICT(attempt_id)

                    DO NOTHING
                    """,

                    payload.attempt_id,

                    user_id,

                    raw_score,

                    iq_score,

                    correct,

                    payload.elapsed_seconds,
                )


                # Update user's personal best.

                await con.execute(
                    """
                    UPDATE users

                    SET

                        attempts =
                            attempts + 1,

                        best_score =
                            GREATEST(
                                best_score,
                                $2
                            ),

                        best_raw =
                            GREATEST(
                                best_raw,
                                $3
                            ),

                        best_time =
                            CASE

                                WHEN
                                    best_score < $2
                                    OR best_time = 0

                                THEN $4

                                WHEN
                                    best_score = $2
                                    AND $4 < best_time

                                THEN $4

                                ELSE best_time

                            END,

                        updated_at=NOW()

                    WHERE
                        user_id=$1
                    """,

                    user_id,

                    iq_score,

                    raw_score,

                    payload.elapsed_seconds,
                )


        return {

            "ok": True,

            "already_processed": False,

            "attempt_id":
                str(payload.attempt_id),

            "iq_score":
                iq_score,

            "raw_score":
                raw_score,

            "correct":
                correct,

            "elapsed_seconds":
                payload.elapsed_seconds,

            "score_label":
                "IQ",

            "standardized":
                False,
        }


    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    @app.get("/api/profile")
    async def profile(request: Request):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )

        async with pool.acquire() as con:

            user = await con.fetchrow(
                """
                SELECT
                    attempts,
                    best_score,
                    best_time

                FROM users

                WHERE user_id=$1
                """,

                user_id,
            )


            rank = await con.fetchval(
                """
                SELECT
                    COUNT(*) + 1

                FROM users

                WHERE
                    attempts > 0

                    AND best_score >

                    COALESCE(
                        (
                            SELECT best_score

                            FROM users

                            WHERE user_id=$1
                        ),
                        0
                    )
                """,

                user_id,
            )


        return {

            "attempts":
                user["attempts"]
                if user else 0,

            "best_score":
                user["best_score"]
                if user else 0,

            "best_time":
                user["best_time"]
                if user else 0,

            "rank":
                int(rank or 1),
        }


    # --------------------------------------------------------
    # RANKING
    # --------------------------------------------------------

    @app.get("/api/ranking")
    async def ranking(request: Request):

        await authenticate(request)

        async with pool.acquire() as con:

            rows = await con.fetch(
                """
                SELECT

                    first_name,

                    username,

                    best_score,

                    best_time

                FROM users

                WHERE attempts > 0

                ORDER BY

                    best_score DESC,

                    CASE

                        WHEN best_time = 0
                        THEN 999999

                        ELSE best_time

                    END ASC

                LIMIT 100
                """
            )


        return {

            "items": [

                {

                    "position":
                        index + 1,

                    "name":
                        row["first_name"]
                        or row["username"]
                        or "Foydalanuvchi",

                    "username":
                        row["username"],

                    "score":
                        row["best_score"],

                    "time":
                        row["best_time"],
                }

                for index, row
                in enumerate(rows)
            ]
        }


    # ========================================================
    # PAYMENT
    # ========================================================

    @app.post("/api/payment/create")
    async def create_payment(
        payload: PaymentCreate,
        request: Request
    ):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )


        if payload.purpose != "retest":

            raise HTTPException(
                status_code=400,
                detail="Invalid payment purpose"
            )


        async with pool.acquire() as con:

            existing = await con.fetchrow(
                """
                SELECT

                    id,

                    amount,

                    status

                FROM payments

                WHERE

                    user_id=$1

                    AND purpose='retest'

                    AND status IN(
                        'pending',
                        'approved'
                    )

                    AND consumed=FALSE

                ORDER BY id DESC

                LIMIT 1
                """,

                user_id,
            )


            if existing:

                return {

                    "payment_id":
                        existing["id"],

                    "amount":
                        existing["amount"],

                    "status":
                        existing["status"],
                }


            payment = await con.fetchrow(
                """
                INSERT INTO payments(

                    user_id,

                    purpose,

                    amount

                )

                VALUES(

                    $1,

                    'retest',

                    $2

                )

                RETURNING

                    id,

                    amount,

                    status
                """,

                user_id,

                PRICE_UZS,
            )


        return {

            "payment_id":
                payment["id"],

            "amount":
                payment["amount"],

            "status":
                payment["status"],
        }


    @app.get("/api/payment/{payment_id}")
    async def payment_status(
        payment_id: int,
        request: Request
    ):

        user_id, telegram_user = (
            await authenticate(request)
        )

        await upsert_user(
            pool,
            telegram_user
        )


        async with pool.acquire() as con:

            payment = await con.fetchrow(
                """
                SELECT

                    id,

                    amount,

                    status,

                    consumed

                FROM payments

                WHERE

                    id=$1

                    AND user_id=$2
                """,

                payment_id,

                user_id,
            )


        if not payment:

            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )


        return {

            "payment_id":
                payment["id"],

            "amount":
                payment["amount"],

            "status":
                payment["status"],

            "consumed":
                payment["consumed"],
        }


    # ========================================================
    # ADMIN PAYMENT APPROVAL
    # ========================================================

    @app.post(
        "/api/admin/payment/{payment_id}/approve"
    )
    async def admin_payment_approve(
        payment_id: int,
        request: Request
    ):

        user_id, telegram_user = (
            await authenticate(request)
        )

        if not ADMIN_ID:

            raise HTTPException(
                status_code=403,
                detail="ADMIN_ID is not configured"
            )


        if user_id != ADMIN_ID:

            raise HTTPException(
                status_code=403,
                detail="Admin only"
            )


        async with pool.acquire() as con:

            result = await con.execute(
                """
                UPDATE payments

                SET

                    status='approved',

                    approved_at=NOW()

                WHERE

                    id=$1

                    AND status='pending'
                """,

                payment_id,
            )


        return {

            "ok": True,

            "updated":
                result.endswith("1"),
        }


    # ========================================================
    # ADMIN PAYMENT REJECTION
    # ========================================================

    @app.post(
        "/api/admin/payment/{payment_id}/reject"
    )
    async def admin_payment_reject(
        payment_id: int,
        request: Request
    ):

        user_id, telegram_user = (
            await authenticate(request)
        )

        if not ADMIN_ID:

            raise HTTPException(
                status_code=403,
                detail="ADMIN_ID is not configured"
            )


        if user_id != ADMIN_ID:

            raise HTTPException(
                status_code=403,
                detail="Admin only"
            )


        async with pool.acquire() as con:

            result = await con.execute(
                """
                UPDATE payments

                SET

                    status='rejected'

                WHERE

                    id=$1

                    AND status='pending'
                """,

                payment_id,
            )


        return {

            "ok": True,

            "updated":
                result.endswith("1"),
        }


    return app, pool


# ============================================================
# TELEGRAM BOT
# ============================================================

async def run_bot():

    app, pool = await create_app()

    bot = Bot(
        token=BOT_TOKEN
    )

    dispatcher = Dispatcher()


    # --------------------------------------------------------
    # /start
    # --------------------------------------------------------

    @dispatcher.message(
        CommandStart()
    )
    async def start_handler(
        message: Message
    ):

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[

                [

                    InlineKeyboardButton(

                        text="🧠 IQ TESTNI BOSHLASH",

                        web_app=WebAppInfo(
                            url=f"{WEBAPP_URL}/app"
                        )
                    )
                ]
            ]
        )


        await message.answer(

            "🧠 IQ TEST\n\n"

            "16 ta mantiqiy va abstrakt "
            "fikrlash topshirig‘i.\n\n"

            "Test davomida javoblaringiz "
            "serverga yuborilmaydi.\n"

            "Natija test yakunida tekshiriladi.",

            reply_markup=keyboard
        )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    @dispatcher.message(F.text)
    async def fallback(
        message: Message
    ):

        await message.answer(

            "IQ testni ochish uchun "
            "/start buyrug‘ini bosing."
        )


    # --------------------------------------------------------
    # WEB SERVER
    # --------------------------------------------------------

    uvicorn_config = uvicorn.Config(

        app,

        host="0.0.0.0",

        port=PORT,

        log_level="info",
    )

    server = uvicorn.Server(
        uvicorn_config
    )


    async def run_web():

        await server.serve()


    try:

        await asyncio.gather(

            dispatcher.start_polling(
                bot
            ),

            run_web(),
        )

    finally:

        await pool.close()

        await bot.session.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        run_bot()
    )