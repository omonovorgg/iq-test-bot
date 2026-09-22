/* ============================================================
   IQ TEST BOT — app.js
   FINAL REBUILD
   ============================================================ */

"use strict";

/* ============================================================
   TELEGRAM WEB APP
   ============================================================ */

const tg = window.Telegram?.WebApp || null;

if (tg) {
    try {
        tg.ready();
        tg.expand();

        tg.setHeaderColor?.("#0a0e1a");
        tg.setBackgroundColor?.("#0a0e1a");
    } catch (e) {
        console.warn("[Telegram] init error:", e);
    }
}

/* ============================================================
   INIT DATA
   ============================================================ */

let initData = "";

function getInitData() {
    try {
        if (tg?.initData && tg.initData.length > 0) {
            initData = tg.initData;
        }
    } catch (e) {
        console.warn("[initData] error:", e);
    }

    return initData;
}

getInitData();

/*
 * Telegram WebApp ba'zan initData'ni darhol bermaydi.
 * Shuning uchun qisqa vaqt davomida qayta tekshiramiz.
 */
let initAttempts = 0;

const initInterval = setInterval(() => {
    initAttempts++;

    const value = getInitData();

    if (value) {
        console.log(
            "[initData] loaded:",
            value.length,
            "characters"
        );

        clearInterval(initInterval);
        return;
    }

    if (initAttempts >= 50) {
        clearInterval(initInterval);
        console.warn("[initData] empty after waiting");
    }
}, 100);

/* ============================================================
   HAPTIC
   ============================================================ */

function haptic(type = "light") {
    try {
        tg?.HapticFeedback?.impactOccurred(type);
    } catch (e) {
        // Telegram bo'lmasa jim ishlayveradi
    }
}

/* ============================================================
   API
   ============================================================ */

/*
 * Muhim tuzatish:
 * GET requestga JSON body yubormaymiz.
 *
 * Original app.js har bir requestga body yuborardi.
 * Bu ayrim server/proxy holatlarida muammo berishi mumkin.
 */

async function api(path, body = null, method = "POST") {
    try {
        const currentInitData =
            getInitData() || tg?.initData || "";

        const upperMethod = String(method).toUpperCase();

        const options = {
            method: upperMethod,
            headers: {
                "Content-Type": "application/json"
            }
        };

        if (upperMethod === "GET") {
            const params = new URLSearchParams();

            if (currentInitData) {
                params.set("initData", currentInitData);
            }

            const separator = path.includes("?") ? "&" : "?";

            const url = currentInitData
                ? `${path}${separator}${params.toString()}`
                : path;

            const response = await fetch(url, options);

            if (!response.ok) {
                console.warn(
                    "[API]",
                    upperMethod,
                    path,
                    response.status
                );

                return {
                    ok: false,
                    error: `HTTP_${response.status}`
                };
            }

            return await response.json();
        }

        const payload = {
            ...(body || {})
        };

        if (!payload.initData) {
            payload.initData = currentInitData;
        }

        options.body = JSON.stringify(payload);

        const response = await fetch(path, options);

        if (!response.ok) {
            console.warn(
                "[API]",
                upperMethod,
                path,
                response.status
            );

            let errorData = null;

            try {
                errorData = await response.json();
            } catch {}

            return {
                ok: false,
                error:
                    errorData?.error ||
                    `HTTP_${response.status}`
            };
        }

        return await response.json();

    } catch (error) {
        console.error(
            "[API ERROR]",
            path,
            error
        );

        return {
            ok: false,
            error: "NETWORK"
        };
    }
}

/* ============================================================
   GLOBAL STATE
   ============================================================ */

const State = {

    currentScreen: "home",

    user: null,

    /*
     * Backenddan kelgan completed qiymatlar.
     *
     * Misol:
     * {
     *   iq: 112,
     *   eq: 75,
     *   pq: 66
     * }
     */
    completed: {},

    settings: {},

    /* ---------------- TEST ---------------- */

    test: {
        type: "iq",

        sessionId: null,

        attemptId: null,

        current: 0,

        answers: [],

        startedAt: null,

        duration: 0,

        timerInterval: null,

        resultData: null
    },

    /* ---------------- BATTLE ---------------- */

    battle: {
        id: null,

        code: null,

        role: null,

        players: [],

        sessionId: null,

        current: 0,

        answers: [],

        startedAt: null,

        pollInterval: null
    },

    /* ---------------- PAYMENT ---------------- */

    payment: {
        id: null,

        product: null,

        amount: 0,

        cards: [],

        pollInterval: null,

        attemptId: null,

        battleId: null
    },

    /* ---------------- LIVE ---------------- */

    live: {
        interval: null
    },

    /* ---------------- PROFILE ---------------- */

    profile: {
        full_name: "",
        gender: null,
        age: null,
        country: null
    }
};

/* ============================================================
   IQ QUESTIONS — 18
   ============================================================ */

const QUESTIONS = [

    /* ---------------- Q1 ---------------- */

    {
        id: 1,
        weight: 1,

        matrix: [
            { type: "dot", count: 1 },
            { type: "dot", count: 2 },
            { type: "dot", count: 3 },

            { type: "dot", count: 2 },
            { type: "dot", count: 3 },
            { type: "dot", count: 4 },

            { type: "dot", count: 3 },
            { type: "dot", count: 4 },
            { type: "question" }
        ],

        options: [
            { type: "dot", count: 3 },
            { type: "dot", count: 4 },
            { type: "dot", count: 5 },
            { type: "dot", count: 6 }
        ],

        correct: 2
    },

    /* ---------------- Q2 ---------------- */

    {
        id: 2,
        weight: 1,

        matrix: [
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "square",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "empty"
            },

            {
                type: "shape",
                shape: "square",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            },

            {
                type: "shape",
                shape: "triangle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "shape",
                shape: "square",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "diamond",
                fill: "empty"
            }
        ],

        correct: 0
    },

    /* ---------------- Q3 ---------------- */

    {
        id: 3,
        weight: 1,

        matrix: [
            { type: "rotate", angle: 0 },
            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 180 },

            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 180 },
            { type: "rotate", angle: 270 },

            { type: "rotate", angle: 180 },
            { type: "rotate", angle: 270 },
            { type: "question" }
        ],

        options: [
            { type: "rotate", angle: 0 },
            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 270 },
            { type: "rotate", angle: 360 }
        ],

        correct: 3
    },

    /* ---------------- Q4 ---------------- */

    {
        id: 4,
        weight: 1,

        matrix: [
            { type: "size", size: 12 },
            { type: "size", size: 20 },
            { type: "size", size: 28 },

            { type: "size", size: 20 },
            { type: "size", size: 28 },
            { type: "size", size: 36 },

            { type: "size", size: 28 },
            { type: "size", size: 36 },
            { type: "question" }
        ],

        options: [
            { type: "size", size: 28 },
            { type: "size", size: 36 },
            { type: "size", size: 44 },
            { type: "size", size: 52 }
        ],

        correct: 2
    },

    /* ---------------- Q5 ---------------- */

    {
        id: 5,
        weight: 1,

        matrix: [
            { type: "grid", pos: 0 },
            { type: "grid", pos: 1 },
            { type: "grid", pos: 2 },

            { type: "grid", pos: 3 },
            { type: "grid", pos: 4 },
            { type: "grid", pos: 5 },

            { type: "grid", pos: 6 },
            { type: "grid", pos: 7 },
            { type: "question" }
        ],

        options: [
            { type: "grid", pos: 4 },
            { type: "grid", pos: 6 },
            { type: "grid", pos: 7 },
            { type: "grid", pos: 8 }
        ],

        correct: 3
    },

    /* ---------------- Q6 ---------------- */

    {
        id: 6,
        weight: 1,

        matrix: [
            {
                type: "shape",
                shape: "circle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "square",
                fill: "full"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },

            {
                type: "shape",
                shape: "square",
                fill: "full"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "full"
            },

            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "full"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "shape",
                shape: "circle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "square",
                fill: "full"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "diamond",
                fill: "full"
            }
        ],

        correct: 1
    },

    /* ---------------- Q7 ---------------- */

    {
        id: 7,
        weight: 2,

        matrix: [
            {
                type: "combo",
                shapes: ["circle"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["circle", "square", "triangle"],
                fill: "full"
            },

            {
                type: "combo",
                shapes: ["square"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["square", "triangle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["square", "triangle", "circle"],
                fill: "empty"
            },

            {
                type: "combo",
                shapes: ["triangle"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "half"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "combo",
                shapes: ["triangle"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle", "square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "square"],
                fill: "half"
            }
        ],

        correct: 1
    },

    /* ---------------- Q8 ---------------- */

    {
        id: 8,
        weight: 2,

        matrix: [
            {
                type: "shape",
                shape: "circle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "half"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            },

            {
                type: "shape",
                shape: "square",
                fill: "full"
            },
            {
                type: "shape",
                shape: "square",
                fill: "half"
            },
            {
                type: "shape",
                shape: "square",
                fill: "empty"
            },

            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "half"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "shape",
                shape: "triangle",
                fill: "full"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "half"
            },
            {
                type: "shape",
                shape: "triangle",
                fill: "empty"
            },
            {
                type: "shape",
                shape: "circle",
                fill: "empty"
            }
        ],

        correct: 2
    },

    /* ---------------- Q9 ---------------- */

    {
        id: 9,
        weight: 2,

        matrix: [
            { type: "num", val: 2 },
            { type: "num", val: 4 },
            { type: "num", val: 6 },

            { type: "num", val: 3 },
            { type: "num", val: 6 },
            { type: "num", val: 9 },

            { type: "num", val: 4 },
            { type: "num", val: 8 },
            { type: "question" }
        ],

        options: [
            { type: "num", val: 10 },
            { type: "num", val: 12 },
            { type: "num", val: 14 },
            { type: "num", val: 16 }
        ],

        correct: 1
    },

    /* ---------------- Q10 ---------------- */

    {
        id: 10,
        weight: 2,

        matrix: [
            { type: "rotate", angle: 45 },
            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 135 },

            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 135 },
            { type: "rotate", angle: 180 },

            { type: "rotate", angle: 135 },
            { type: "rotate", angle: 180 },
            { type: "question" }
        ],

        options: [
            { type: "rotate", angle: 180 },
            { type: "rotate", angle: 225 },
            { type: "rotate", angle: 270 },
            { type: "rotate", angle: 315 }
        ],

        correct: 1
    },

    /* ---------------- Q11 ---------------- */

    {
        id: 11,
        weight: 2,

        matrix: [
            { type: "dot", count: 1 },
            { type: "dot", count: 4 },
            { type: "dot", count: 9 },

            { type: "dot", count: 4 },
            { type: "dot", count: 9 },
            { type: "dot", count: 16 },

            { type: "dot", count: 9 },
            { type: "dot", count: 16 },
            { type: "question" }
        ],

        options: [
            { type: "dot", count: 16 },
            { type: "dot", count: 25 },
            { type: "dot", count: 36 },
            { type: "dot", count: 49 }
        ],

        correct: 1
    },

    /* ---------------- Q12 ---------------- */

    {
        id: 12,
        weight: 2,

        matrix: [
            { type: "grid", pos: 0 },
            { type: "grid", pos: 2 },
            { type: "grid", pos: 4 },

            { type: "grid", pos: 2 },
            { type: "grid", pos: 4 },
            { type: "grid", pos: 6 },

            { type: "grid", pos: 4 },
            { type: "grid", pos: 6 },
            { type: "question" }
        ],

        options: [
            { type: "grid", pos: 6 },
            { type: "grid", pos: 7 },
            { type: "grid", pos: 8 },
            { type: "grid", pos: 5 }
        ],

        correct: 2
    },

    /* ---------------- Q13 ---------------- */

    {
        id: 13,
        weight: 3,

        matrix: [
            { type: "num", val: 1 },
            { type: "num", val: 1 },
            { type: "num", val: 2 },

            { type: "num", val: 3 },
            { type: "num", val: 5 },
            { type: "num", val: 8 },

            { type: "num", val: 13 },
            { type: "num", val: 21 },
            { type: "question" }
        ],

        options: [
            { type: "num", val: 30 },
            { type: "num", val: 34 },
            { type: "num", val: 38 },
            { type: "num", val: 42 }
        ],

        correct: 1
    },

    /* ---------------- Q14 ---------------- */

    {
        id: 14,
        weight: 3,

        matrix: [
            {
                type: "combo",
                shapes: ["circle"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["circle", "square", "triangle"],
                fill: "empty"
            },

            {
                type: "combo",
                shapes: ["square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["square", "triangle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["square", "triangle", "circle"],
                fill: "full"
            },

            {
                type: "combo",
                shapes: ["triangle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "full"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "combo",
                shapes: ["triangle", "circle", "square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "square"],
                fill: "empty"
            }
        ],

        correct: 0
    },

    /* ---------------- Q15 ---------------- */

    {
        id: 15,
        weight: 3,

        matrix: [
            { type: "rotate", angle: 0 },
            { type: "rotate", angle: 45 },
            { type: "rotate", angle: 90 },

            { type: "rotate", angle: 45 },
            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 135 },

            { type: "rotate", angle: 90 },
            { type: "rotate", angle: 135 },
            { type: "question" }
        ],

        options: [
            { type: "rotate", angle: 135 },
            { type: "rotate", angle: 180 },
            { type: "rotate", angle: 225 },
            { type: "rotate", angle: 270 }
        ],

        correct: 1
    },

    /* ---------------- Q16 ---------------- */

    {
        id: 16,
        weight: 3,

        matrix: [
            { type: "num", val: 3 },
            { type: "num", val: 9 },
            { type: "num", val: 27 },

            { type: "num", val: 2 },
            { type: "num", val: 4 },
            { type: "num", val: 8 },

            { type: "num", val: 5 },
            { type: "num", val: 25 },
            { type: "question" }
        ],

        options: [
            { type: "num", val: 100 },
            { type: "num", val: 125 },
            { type: "num", val: 150 },
            { type: "num", val: 625 }
        ],

        correct: 1
    },

    /* ---------------- Q17 ---------------- */

    {
        id: 17,
        weight: 3,

        matrix: [
            { type: "grid", pos: 0 },
            { type: "grid", pos: 1 },
            { type: "grid", pos: 3 },

            { type: "grid", pos: 1 },
            { type: "grid", pos: 3 },
            { type: "grid", pos: 5 },

            { type: "grid", pos: 3 },
            { type: "grid", pos: 5 },
            { type: "question" }
        ],

        options: [
            { type: "grid", pos: 5 },
            { type: "grid", pos: 6 },
            { type: "grid", pos: 7 },
            { type: "grid", pos: 8 }
        ],

        correct: 2
    },

    /* ---------------- Q18 ---------------- */

    {
        id: 18,
        weight: 3,

        matrix: [
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["square", "triangle"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "empty"
            },

            {
                type: "combo",
                shapes: ["square", "triangle"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "full"
            },

            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "full"
            },
            { type: "question" }
        ],

        options: [
            {
                type: "combo",
                shapes: ["circle", "square"],
                fill: "full"
            },
            {
                type: "combo",
                shapes: ["square", "triangle"],
                fill: "half"
            },
            {
                type: "combo",
                shapes: ["triangle", "circle"],
                fill: "empty"
            },
            {
                type: "combo",
                shapes: ["circle", "triangle"],
                fill: "half"
            }
        ],

        correct: 1
    }
];

/* ============================================================
   EQ — 6 QUESTIONS
   ============================================================ */

const EQ_QUESTIONS = [

    {
        id: 1,

        text:
            "Ishingiz juda ko‘payib ketdi va boshliq yana yangi topshiriq berdi. Siz nima qilasiz?",

        options: [
            "Darhol ro‘yxat tuzaman va muhimini ajrataman",
            "Asabiylashaman, lekin baribir boshlayman",
            "Boshliqqa vaqt yetmasligini aytaman",
            "Kechqurun qolib ishlayman"
        ],

        scores: [4, 2, 3, 1]
    },

    {
        id: 2,

        text:
            "Do‘stingiz yig‘layapti va nima bo‘lganini aytmayapti. Siz:",

        options: [
            "Yoniga o‘tiraman va jim kutaman",
            "Darhol savol bera boshlayman",
            "Hazil qilib kayfiyatini ko‘taraman",
            "Uydan ketsam bo‘ladi deb o‘ylayman"
        ],

        scores: [4, 1, 2, 1]
    },

    {
        id: 3,

        text:
            "Siz xato qildingiz va buni birinchi bo‘lib kim payqadi?",

        options: [
            "O‘zim, darhol tan olaman",
            "Boshqalar aytganda tan olaman",
            "Inkor qilaman",
            "Bahona topaman"
        ],

        scores: [4, 3, 1, 1]
    },

    {
        id: 4,

        text:
            "Hamkasbingiz sizning fikringizni ochiq tanqid qildi. Siz:",

        options: [
            "Xotirjam tinglab, sababini so‘rayman",
            "Darhol javob qaytaraman",
            "Indamay qolaman",
            "Boshqalardan yordam so‘rayman"
        ],

        scores: [4, 2, 1, 2]
    },

    {
        id: 5,

        text:
            "Kutilmagan yomon xabar oldingiz. Birinchi harakatingiz:",

        options: [
            "Chuqur nafas olib, o‘zimni tutaman",
            "Darhol kimdirga aytaman",
            "Yolg‘iz qolaman",
            "Ishni tashlab ketaman"
        ],

        scores: [4, 2, 3, 1]
    },

    {
        id: 6,

        text:
            "Suhbatdoshning ko‘zlari boshqa tomonga qarayapti. Bu nimani bildiradi?",

        options: [
            "U zerikkan yoki shoshilyapti",
            "U yolg‘on gapiryapti",
            "U sizni yoqtirmaydi",
            "Hech narsa, shunchaki shunday"
        ],

        scores: [4, 2, 1, 2]
    }
];

/* ============================================================
   PQ — 6 QUESTIONS
   ============================================================ */

const PQ_QUESTIONS = [

    {
        id: 1,

        text:
            "Muhim loyiha bor, lekin siz uni doim keyinga surasiz. Sabab:",

        options: [
            "Qiyin bo‘lgani uchun",
            "Vaqt ko‘p deb o‘ylayman",
            "Nima qilishni bilmayman",
            "Kayfiyat yo‘q"
        ],

        scores: [2, 1, 2, 1]
    },

    {
        id: 2,

        text:
            "Imtihonga 7 kun qoldi. Siz:",

        options: [
            "Har kuni oz-oz tayyorlanaman",
            "Oxirgi 2 kunda qattiq tayyorlanaman",
            "Oxirgi kechada tayyorlanaman",
            "Tayyorlanmayman, nima bo‘lsa bo‘lsin"
        ],

        scores: [4, 2, 1, 0]
    },

    {
        id: 3,

        text:
            "Ishni boshlash uchun sizga nima kerak?",

        options: [
            "Aniq reja",
            "Kayfiyat",
            "Deadline",
            "Mukofot"
        ],

        scores: [4, 1, 2, 2]
    },

    {
        id: 4,

        text:
            "Ishlayotganingizda telefonni tez-tez tekshirasizmi?",

        options: [
            "Yo‘q, telefon boshqa xonada",
            "Ba‘zan, lekin o‘zimni tutaman",
            "Ha, har 10 daqiqada",
            "Doim qo‘limda"
        ],

        scores: [4, 3, 1, 0]
    },

    {
        id: 5,

        text:
            "Deadline yaqinlashganda siz:",

        options: [
            "Avvaldan tayyor bo‘laman",
            "Oxirgi paytda tezlashaman",
            "Kechikaman",
            "Umuman bajarmayman"
        ],

        scores: [4, 2, 1, 0]
    },

    {
        id: 6,

        text:
            "Rejangizni qanchalik bajarasiz?",

        options: [
            "Doim bajaraman",
            "Ko‘pincha bajaraman",
            "Ba‘zan bajaraman",
            "Deyarli hech qachon"
        ],

        scores: [4, 3, 1, 0]
    }
];

/* ============================================================
   RENDER — MATRIX CELL
   ============================================================ */

function renderCell(cell) {

    if (!cell) {
        return "";
    }

    if (cell.type === "question") {
        return `
            <span
                style="
                    font-size:32px;
                    font-weight:900;
                    color:#a78bfa;
                "
            >?</span>
        `;
    }

    /* ---------------- DOT ---------------- */

    if (cell.type === "dot") {

        const count = Math.min(
            Number(cell.count) || 0,
            16
        );

        let html = `
            <div
                style="
                    display:grid;
                    grid-template-columns:repeat(4,1fr);
                    gap:2px;
                    width:44px;
                    height:44px;
                    align-items:center;
                    justify-items:center;
                "
            >
        `;

        for (let i = 0; i < count; i++) {

            html += `
                <div
                    style="
                        width:6px;
                        height:6px;
                        border-radius:50%;
                        background:#a78bfa;
                        box-shadow:0 0 6px #a78bfa;
                    "
                ></div>
            `;
        }

        html += "</div>";

        return html;
    }

    /* ---------------- NUMBER ---------------- */

    if (cell.type === "num") {

        return `
            <span
                style="
                    font-size:22px;
                    font-weight:800;
                    color:#a78bfa;
                "
            >
                ${cell.val}
            </span>
        `;
    }

    /* ---------------- SHAPE ---------------- */

    if (cell.type === "shape") {

        const colors = {
            full: "#a78bfa",
            half: "rgba(167,139,250,.5)",
            empty: "transparent"
        };

        const fill =
            colors[cell.fill] || "transparent";

        if (cell.shape === "circle") {

            return `
                <svg
                    width="44"
                    height="44"
                    viewBox="0 0 44 44"
                >
                    <circle
                        cx="22"
                        cy="22"
                        r="14"
                        fill="${fill}"
                        stroke="#a78bfa"
                        stroke-width="2"
                    />
                </svg>
            `;
        }

        if (cell.shape === "square") {

            return `
                <svg
                    width="44"
                    height="44"
                    viewBox="0 0 44 44"
                >
                    <rect
                        x="7"
                        y="7"
                        width="30"
                        height="30"
                        rx="4"
                        fill="${fill}"
                        stroke="#a78bfa"
                        stroke-width="2"
                    />
                </svg>
            `;
        }

        if (cell.shape === "triangle") {

            return `
                <svg
                    width="44"
                    height="44"
                    viewBox="0 0 44 44"
                >
                    <polygon
                        points="22,7 37,37 7,37"
                        fill="${fill}"
                        stroke="#a78bfa"
                        stroke-width="2"
                        stroke-linejoin="round"
                    />
                </svg>
            `;
        }

        if (cell.shape === "diamond") {

            return `
                <svg
                    width="44"
                    height="44"
                    viewBox="0 0 44 44"
                >
                    <polygon
                        points="22,6 38,22 22,38 6,22"
                        fill="${fill}"
                        stroke="#a78bfa"
                        stroke-width="2"
                        stroke-linejoin="round"
                    />
                </svg>
            `;
        }
    }

    /* ---------------- ROTATE ---------------- */

    if (cell.type === "rotate") {

        return `
            <svg
                width="44"
                height="44"
                viewBox="0 0 44 44"
            >
                <g
                    transform="rotate(${cell.angle} 22 22)"
                >
                    <path
                        d="
                            M12 22
                            L32 22
                            M27 17
                            L32 22
                            L27 27
                        "
                        stroke="#a78bfa"
                        stroke-width="2.5"
                        fill="none"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    />
                </g>
            </svg>
        `;
    }

    /* ---------------- COMBO ---------------- */

    if (cell.type === "combo") {

        const colors = {
            full: "#a78bfa",
            half: "rgba(167,139,250,.5)",
            empty: "transparent"
        };

        const fill =
            colors[cell.fill] || "transparent";

        const shapes =
            Array.isArray(cell.shapes)
                ? cell.shapes
                : [];

        let svg = `
            <svg
                width="44"
                height="44"
                viewBox="0 0 44 44"
            >
        `;

        if (shapes.includes("triangle")) {

            svg += `
                <polygon
                    points="22,7 37,37 7,37"
                    fill="${fill}"
                    stroke="#a78bfa"
                    stroke-width="1.8"
                    stroke-linejoin="round"
                />
            `;
        }

        if (shapes.includes("square")) {

            svg += `
                <rect
                    x="8"
                    y="8"
                    width="28"
                    height="28"
                    rx="3"
                    fill="${fill}"
                    stroke="#a78bfa"
                    stroke-width="1.8"
                />
            `;
        }

        if (shapes.includes("circle")) {

            svg += `
                <circle
                    cx="22"
                    cy="22"
                    r="14"
                    fill="${fill}"
                    stroke="#a78bfa"
                    stroke-width="1.8"
                />
            `;
        }

        svg += "</svg>";

        return svg;
    }

    /* ---------------- SIZE ---------------- */

    if (cell.type === "size") {

        const size = Math.max(
            6,
            Math.min(
                Number(cell.size) || 20,
                40
            )
        );

        return `
            <svg
                width="44"
                height="44"
                viewBox="0 0 44 44"
            >
                <circle
                    cx="22"
                    cy="22"
                    r="${size / 2}"
                    fill="none"
                    stroke="#a78bfa"
                    stroke-width="2"
                />
            </svg>
        `;
    }

    /* ---------------- GRID ---------------- */

    if (cell.type === "grid") {

        const pos =
            Math.max(
                0,
                Math.min(
                    Number(cell.pos) || 0,
                    8
                )
            );

        const row = Math.floor(pos / 3);
        const col = pos % 3;

        return `
            <svg
                width="44"
                height="44"
                viewBox="0 0 44 44"
            >
                <rect
                    x="3"
                    y="3"
                    width="38"
                    height="38"
                    rx="4"
                    fill="none"
                    stroke="rgba(167,139,250,.3)"
                    stroke-width="1.5"
                />

                <circle
                    cx="${10 + col * 12}"
                    cy="${10 + row * 12}"
                    r="5"
                    fill="#a78bfa"
                />
            </svg>
        `;
    }

    return "";
}

/* ============================================================
   RENDER — MATRIX
   ============================================================ */

function renderMatrix(element, cells) {

    if (!element) {
        return;
    }

    if (!Array.isArray(cells)) {
        element.innerHTML = "";
        return;
    }

    element.innerHTML = cells
        .map(cell => `
            <div
                class="cell ${
                    cell?.type === "question"
                        ? "question"
                        : ""
                }"
            >
                ${renderCell(cell)}
            </div>
        `)
        .join("");
}

/* ============================================================
   RENDER — VISUAL OPTIONS
   ============================================================ */

function renderOptions(element, options, onSelect) {

    if (!element) {
        return;
    }

    if (!Array.isArray(options)) {
        element.innerHTML = "";
        return;
    }

    element.innerHTML = options
        .map((option, index) => `
            <div
                class="option"
                data-idx="${index}"
            >
                ${renderCell(option)}
            </div>
        `)
        .join("");

    element
        .querySelectorAll(".option")
        .forEach(option => {

            option.addEventListener("click", () => {

                haptic("light");

                element
                    .querySelectorAll(".option")
                    .forEach(item => {
                        item.classList.remove(
                            "selected"
                        );
                    });

                option.classList.add("selected");

                const index =
                    Number(option.dataset.idx);

                if (typeof onSelect === "function") {
                    onSelect(index);
                }
            });
        });
}

/* ============================================================
   RENDER — TEXT OPTIONS
   ============================================================ */

function renderTextOptions(
    element,
    options,
    onSelect
) {

    if (!element) {
        return;
    }

    if (!Array.isArray(options)) {
        element.innerHTML = "";
        return;
    }

    element.innerHTML = options
        .map((option, index) => `
            <div
                class="option text-option"
                data-idx="${index}"
            >
                <span class="opt-letter">
                    ${String.fromCharCode(65 + index)}
                </span>

                <span class="opt-text">
                    ${option}
                </span>
            </div>
        `)
        .join("");

    element
        .querySelectorAll(".option")
        .forEach(option => {

            option.addEventListener("click", () => {

                haptic("light");

                element
                    .querySelectorAll(".option")
                    .forEach(item => {
                        item.classList.remove(
                            "selected"
                        );
                    });

                option.classList.add("selected");

                const index =
                    Number(option.dataset.idx);

                if (typeof onSelect === "function") {
                    onSelect(index);
                }
            });
        });
}
/* ============================================================
   APP
   ============================================================ */

const App = {

    /* ========================================================
       INIT
       ======================================================== */

    async init() {

        console.log("[APP] init start");

        try {

            /* ---------- CONFIG ---------- */

            const cfg = await api(
                "/api/config",
                null,
                "GET"
            );

            if (cfg?.ok) {
                State.settings = cfg.settings || {};
            }

            /* ---------- LIVE ---------- */

            await this.refreshLive();
            this.startLiveLoop();

            /* ---------- USER ---------- */

            getInitData();

            if (initData) {

                const me = await api(
                    "/api/me",
                    {
                        initData
                    }
                );

                if (me?.ok) {

                    State.user = me.user || null;

                    State.completed =
                        me.completed || {};

                    /* ---------- PROFILE ---------- */

                    if (me.user?.full_name) {

                        State.profile.full_name =
                            me.user.full_name;

                        State.profile.gender =
                            me.user.gender || null;

                        State.profile.age =
                            me.user.age || null;

                        State.profile.country =
                            me.user.country || null;
                    }

                    /* ---------- UNLOCKS ---------- */

                    this.applyUnlocks();

                    /* ---------- ACTIVE BATTLE ---------- */

                    if (
                        Array.isArray(me.active_battles) &&
                        me.active_battles.length > 0
                    ) {

                        const battle =
                            me.active_battles[0];

                        State.battle.id =
                            battle.id;

                        State.battle.code =
                            battle.battle_code;
                    }
                }
            }

            console.log("[APP] init complete");

        } catch (error) {

            console.error(
                "[APP] init error:",
                error
            );
        }
    },


    /* ========================================================
       LIVE COUNTER
       ======================================================== */

    async refreshLive() {

        try {

            const res = await api(
                "/api/stats/live",
                null,
                "GET"
            );

            if (!res?.ok) {
                return;
            }

            this.animateNumber(
                "live-total",
                Number(res.total) || 0
            );

            this.animateNumber(
                "live-online",
                Number(res.online) || 0
            );

        } catch (error) {

            console.warn(
                "[LIVE] refresh error:",
                error
            );
        }
    },


    startLiveLoop() {

        if (State.live.interval) {
            clearInterval(
                State.live.interval
            );
        }

        State.live.interval = setInterval(
            () => {
                this.refreshLive();
            },
            5000
        );
    },


    animateNumber(id, target) {

        const el =
            document.getElementById(id);

        if (!el) {
            return;
        }

        target = Number(target) || 0;

        let current =
            parseInt(
                String(el.textContent)
                    .replace(/\D/g, ""),
                10
            ) || 0;

        if (current === target) {
            return;
        }

        const difference =
            target - current;

        const step =
            difference > 0
                ? Math.max(
                    1,
                    Math.floor(
                        difference / 10
                    )
                )
                : Math.min(
                    -1,
                    Math.ceil(
                        difference / 10
                    )
                );

        const timer =
            setInterval(() => {

                current += step;

                if (
                    (step > 0 &&
                        current >= target) ||
                    (step < 0 &&
                        current <= target)
                ) {

                    current = target;

                    clearInterval(timer);
                }

                el.textContent =
                    current.toLocaleString();

            }, 40);
    },


    /* ========================================================
       SCREEN NAVIGATION
       ======================================================== */

    go(screen) {

        document
            .querySelectorAll(".screen")
            .forEach(section => {
                section.classList.remove(
                    "active"
                );
            });

        const target =
            document.getElementById(
                "screen-" + screen
            );

        if (!target) {

            console.warn(
                "[NAV] screen not found:",
                screen
            );

            return;
        }

        target.classList.add("active");

        State.currentScreen =
            screen;

        window.scrollTo({
            top: 0,
            behavior: "instant"
        });

        haptic("light");
    },


    /* ========================================================
       UNLOCKS
       ======================================================== */

    applyUnlocks() {

        const completed =
            State.completed || {};

        console.log(
            "[UNLOCKS]",
            completed
        );

        /* ---------- IQ → EQ ---------- */

        if (
            completed.iq !== undefined &&
            completed.iq !== null
        ) {

            const card =
                document.getElementById(
                    "card-eq"
                );

            if (card) {

                card.classList.remove(
                    "locked"
                );

                card.classList.add(
                    "unlocked"
                );

                const state =
                    card.querySelector(
                        ".card-state"
                    );

                if (state) {
                    state.textContent = "";
                }

                const hint =
                    card.querySelector(
                        ".card-hint"
                    );

                if (hint) {
                    hint.textContent = "";
                }
            }
        }


        /* ---------- EQ → PQ ---------- */

        if (
            completed.eq !== undefined &&
            completed.eq !== null
        ) {

            const card =
                document.getElementById(
                    "card-pq"
                );

            if (card) {

                card.classList.remove(
                    "locked"
                );

                card.classList.add(
                    "unlocked"
                );

                const state =
                    card.querySelector(
                        ".card-state"
                    );

                if (state) {
                    state.textContent = "";
                }

                const hint =
                    card.querySelector(
                        ".card-hint"
                    );

                if (hint) {
                    hint.textContent = "";
                }
            }
        }


        /* ---------- ALL → PROFILE ---------- */

        if (
            completed.iq !== undefined &&
            completed.eq !== undefined &&
            completed.pq !== undefined
        ) {

            const card =
                document.getElementById(
                    "card-profile"
                );

            if (card) {

                card.classList.remove(
                    "locked"
                );

                card.classList.add(
                    "unlocked"
                );

                const state =
                    card.querySelector(
                        ".card-state"
                    );

                if (state) {
                    state.textContent = "";
                }
            }
        }
    },


    /* ========================================================
       IQ START
       ======================================================== */

    startIQ() {

        /*
         * IQ boshlanganda profilni har safar
         * tekshirtiramiz.
         */

        const savedName =
            State.profile.full_name || "";

        const nameInput =
            document.getElementById(
                "profile-fullname"
            );

        if (nameInput) {
            nameInput.value = savedName;
        }

        /*
         * Gender/age/country ni tozalaymiz.
         */

        State.profile.gender = null;
        State.profile.age = null;
        State.profile.country = null;

        document
            .querySelectorAll(
                "#gender-selector .option"
            )
            .forEach(el => {
                el.classList.remove(
                    "selected"
                );
            });

        document
            .querySelectorAll(
                "#country-selector .option"
            )
            .forEach(el => {
                el.classList.remove(
                    "selected"
                );
            });

        const ageInput =
            document.getElementById(
                "profile-age"
            );

        if (ageInput) {
            ageInput.value = "";
        }

        this.go(
            "profile-name"
        );
    },


    /* ========================================================
       SAVE PROFILE
       ======================================================== */

    async saveProfile() {

        const nameInput =
            document.getElementById(
                "profile-fullname"
            );

        const ageInput =
            document.getElementById(
                "profile-age"
            );

        const fullName =
            nameInput?.value
                ?.trim() || "";

        const gender =
            State.profile.gender;

        const age =
            parseInt(
                ageInput?.value,
                10
            );

        const country =
            State.profile.country;


        /* ---------- VALIDATION ---------- */

        if (
            !fullName ||
            fullName.length < 3
        ) {

            alert(
                "Ism-familiyani to‘liq kiriting."
            );

            nameInput?.focus();

            return;
        }


        if (!gender) {

            alert(
                "Jinsni tanlang."
            );

            return;
        }


        if (
            !age ||
            age < 8 ||
            age > 100
        ) {

            alert(
                "Yoshni to‘g‘ri kiriting (8-100)."
            );

            ageInput?.focus();

            return;
        }


        if (!country) {

            alert(
                "Davlatni tanlang."
            );

            return;
        }


        /* ---------- LOCAL STATE ---------- */

        State.profile.full_name =
            fullName;

        State.profile.gender =
            gender;

        State.profile.age =
            age;

        State.profile.country =
            country;


        /* ---------- BACKEND ---------- */

        if (initData) {

            const res = await api(
                "/api/profile/save",
                {
                    initData,
                    full_name: fullName,
                    gender,
                    age,
                    country
                }
            );

            if (!res?.ok) {

                alert(
                    "Profilni saqlashda xatolik."
                );

                return;
            }
        }


        haptic("medium");

        this.go(
            "iq-intro"
        );
    },


    /* ========================================================
       GENDER
       ======================================================== */

    selectGender(gender) {

        const allowed = [
            "male",
            "female"
        ];

        if (!allowed.includes(gender)) {
            return;
        }

        State.profile.gender =
            gender;

        document
            .querySelectorAll(
                "#gender-selector .option"
            )
            .forEach(el => {
                el.classList.remove(
                    "selected"
                );
            });

        const selected =
            document.querySelector(
                `#gender-selector [data-gender="${gender}"]`
            );

        selected?.classList.add(
            "selected"
        );

        haptic("light");
    },


    /* ========================================================
       COUNTRY
       ======================================================== */

    selectCountry(country) {

        const allowed = [
            "uz",
            "ru",
            "en",
            "kz",
            "kg",
            "tr"
        ];

        if (!allowed.includes(country)) {
            return;
        }

        State.profile.country =
            country;

        document
            .querySelectorAll(
                "#country-selector .option"
            )
            .forEach(el => {
                el.classList.remove(
                    "selected"
                );
            });

        const selected =
            document.querySelector(
                `#country-selector [data-country="${country}"]`
            );

        selected?.classList.add(
            "selected"
        );

        haptic("light");
    },


    /* ========================================================
       IQ TEST SESSION
       ======================================================== */

    async startIQTest() {

        haptic("medium");

        /*
         * Eski timer/session qoldig'ini tozalash.
         */

        if (State.test.timerInterval) {

            clearInterval(
                State.test.timerInterval
            );

            State.test.timerInterval =
                null;
        }

        State.test.type = "iq";

        State.test.sessionId =
            null;

        State.test.attemptId =
            null;

        State.test.current =
            0;

        State.test.answers =
            new Array(
                QUESTIONS.length
            ).fill(null);

        State.test.startedAt =
            Date.now();

        State.test.duration =
            0;

        State.test.resultData =
            null;


        /* ---------- BACKEND SESSION ---------- */

        if (initData) {

            const res = await api(
                "/api/session/start",
                {
                    initData,
                    test_type: "iq"
                }
            );

            if (res?.ok) {

                State.test.sessionId =
                    res.session_id || null;

                State.test.attemptId =
                    res.attempt_id || null;

            } else {

                console.warn(
                    "[IQ] session start failed:",
                    res
                );
            }
        }


        /* ---------- SAMPLE ---------- */

        this.go("sample");

        this.renderSample();
    },


    /* ========================================================
       SAMPLE QUESTION
       ======================================================== */

    renderSample() {

        const sample = {

            matrix: [
                {
                    type: "dot",
                    count: 1
                },
                {
                    type: "dot",
                    count: 2
                },
                {
                    type: "dot",
                    count: 3
                },

                {
                    type: "dot",
                    count: 2
                },
                {
                    type: "dot",
                    count: 3
                },
                {
                    type: "dot",
                    count: 4
                },

                {
                    type: "dot",
                    count: 3
                },
                {
                    type: "dot",
                    count: 4
                },
                {
                    type: "question"
                }
            ],

            options: [
                {
                    type: "dot",
                    count: 4
                },
                {
                    type: "dot",
                    count: 5
                },
                {
                    type: "dot",
                    count: 3
                },
                {
                    type: "dot",
                    count: 6
                }
            ],

            correct: 1
        };


        const matrix =
            document.getElementById(
                "sample-matrix"
            );

        const options =
            document.getElementById(
                "sample-options"
            );

        const next =
            document.getElementById(
                "sample-next"
            );


        renderMatrix(
            matrix,
            sample.matrix
        );


        if (next) {
            next.disabled = true;
        }


        renderOptions(
            options,
            sample.options,
            index => {

                if (next) {
                    next.disabled =
                        false;
                }

                /*
                 * Namunaviy savolda javobni
                 * vizual ko‘rsatamiz.
                 */

                options
                    ?.querySelectorAll(
                        ".option"
                    )
                    .forEach(
                        (option, i) => {

                            option.classList.remove(
                                "correct",
                                "wrong"
                            );

                            if (
                                i ===
                                sample.correct
                            ) {

                                option.classList.add(
                                    "correct"
                                );

                            } else if (
                                i === index
                            ) {

                                option.classList.add(
                                    "wrong"
                                );
                            }
                        }
                    );
            }
        );
    },


    /* ========================================================
       GO TO REAL IQ TEST
       ======================================================== */

    goTest() {

        this.go(
            "test"
        );

        this.renderQuestion();

        this.startTimer();
    },


    /* ========================================================
       TIMER
       ======================================================== */

    startTimer() {

        if (
            State.test.timerInterval
        ) {

            clearInterval(
                State.test.timerInterval
            );
        }

        State.test.timerInterval =
            setInterval(() => {

                if (
                    !State.test.startedAt
                ) {
                    return;
                }

                const elapsed =
                    Math.floor(
                        (
                            Date.now() -
                            State.test.startedAt
                        ) / 1000
                    );

                State.test.duration =
                    elapsed;

                const minutes =
                    String(
                        Math.floor(
                            elapsed / 60
                        )
                    ).padStart(2, "0");

                const seconds =
                    String(
                        elapsed % 60
                    ).padStart(2, "0");

                const timer =
                    document.getElementById(
                        "test-timer"
                    );

                if (timer) {

                    timer.textContent =
                        `${minutes}:${seconds}`;
                }

            }, 1000);
    },


    /* ========================================================
       RENDER IQ QUESTION
       ======================================================== */

    renderQuestion() {

        const index =
            State.test.current;

        const question =
            QUESTIONS[index];

        if (!question) {
            return;
        }


        const progressText =
            document.getElementById(
                "test-progress-text"
            );

        const progress =
            document.getElementById(
                "progress-fill"
            );

        const difficulty =
            document.getElementById(
                "difficulty-bar"
            );


        if (progressText) {

            progressText.textContent =
                `Q${index + 1} / ${QUESTIONS.length}`;
        }


        if (progress) {

            progress.style.width =
                (
                    index /
                    QUESTIONS.length *
                    100
                ) + "%";
        }


        /* ---------- DIFFICULTY ---------- */

        if (difficulty) {

            let html = "";

            for (
                let i = 0;
                i < QUESTIONS.length;
                i++
            ) {

                let level;

                if (i >= 12) {
                    level = "hard";
                } else if (i >= 6) {
                    level = "medium";
                } else {
                    level = "easy";
                }

                if (
                    i <= index
                ) {

                    html += `
                        <span
                            class="${level}"
                        ></span>
                    `;

                } else {

                    html += `
                        <span></span>
                    `;
                }
            }

            difficulty.innerHTML =
                html;
        }


        /* ---------- MATRIX ---------- */

        renderMatrix(
            document.getElementById(
                "test-matrix"
            ),
            question.matrix
        );


        /* ---------- NEXT ---------- */

        const next =
            document.getElementById(
                "test-next"
            );

        if (next) {

            next.disabled = true;

            next.textContent =
                index === QUESTIONS.length - 1
                    ? "YAKUNLASH →"
                    : "KEYINGISI →";
        }


        /* ---------- OPTIONS ---------- */

        renderOptions(
            document.getElementById(
                "test-options"
            ),
            question.options,
            selectedIndex => {

                State.test.answers[index] =
                    selectedIndex;

                if (next) {
                    next.disabled =
                        false;
                }
            }
        );


        /* ---------- RESTORE ANSWER ---------- */

        const previous =
            State.test.answers[index];

        if (
            previous !== null &&
            previous !== undefined
        ) {

            const options =
                document.querySelectorAll(
                    "#test-options .option"
                );

            const selected =
                options[previous];

            selected?.classList.add(
                "selected"
            );

            if (next) {
                next.disabled = false;
            }
        }
    },


    /* ========================================================
       NEXT IQ QUESTION
       ======================================================== */

    nextQuestion() {

        haptic("light");

        const current =
            State.test.current;


        /* ---------- Q6 ---------- */

        if (current === 5) {

            this.go("q6");

            return;
        }


        /* ---------- Q12 ---------- */

        if (current === 11) {

            this.go("q12");

            return;
        }


        /* ---------- LAST ---------- */

        if (
            current ===
            QUESTIONS.length - 1
        ) {

            this.finish();

            return;
        }


        /* ---------- NEXT ---------- */

        State.test.current =
            current + 1;

        this.renderQuestion();
    },


    /* ========================================================
       CONTINUE AFTER Q6
       ======================================================== */

    continueAfterQ6() {

        State.test.current = 6;

        this.go("test");

        this.renderQuestion();
    },


    /* ========================================================
       CONTINUE AFTER Q12
       ======================================================== */

    continueAfterQ12() {

        State.test.current = 12;

        this.go("test");

        this.renderQuestion();
    },


    /* ========================================================
       IQ FINISH — DAVOMI KEYINGI QISMDA
       ======================================================== */
    /* ========================================================
       IQ FINISH
       ======================================================== */

    async finish() {

        if (
            State.test.answers.length !==
            QUESTIONS.length
        ) {
            console.warn(
                "[IQ] answers length mismatch"
            );
        }

        if (State.test.timerInterval) {

            clearInterval(
                State.test.timerInterval
            );

            State.test.timerInterval =
                null;
        }

        this.go("iq-loading");

        await new Promise(resolve =>
            setTimeout(resolve, 2500)
        );


        let score = 0;
        let correct = 0;
        let level = "RIVOJLANTIRISH";

        let resultVisible = true;
        let paymentRequired = false;

        let attemptId =
            State.test.attemptId || null;


        /* ====================================================
           BACKEND
           ==================================================== */

        if (
            initData &&
            State.test.sessionId
        ) {

            const res = await api(
                "/api/test/submit",
                {
                    initData,

                    session_id:
                        State.test.sessionId,

                    answers:
                        State.test.answers,

                    duration:
                        State.test.duration
                }
            );


            if (res?.ok) {

                score =
                    Number(res.score) || 0;

                correct =
                    Number(res.correct) || 0;

                level =
                    res.level ||
                    "RIVOJLANTIRISH";

                resultVisible =
                    res.result_visible !== false;

                paymentRequired =
                    res.payment_required === true;

                attemptId =
                    res.attempt_id ||
                    attemptId;

                State.test.attemptId =
                    attemptId;

            } else {

                console.warn(
                    "[IQ] submit failed:",
                    res
                );

                /*
                 * Backend ishlamasa lokal hisob.
                 * Bu faqat fallback.
                 */

                const local =
                    this.calculateIQ();

                score = local.score;
                correct = local.correct;
                level = local.level;
            }

        } else {

            /*
             * Telegram tashqarisida test
             * ishlatilsa lokal fallback.
             */

            const local =
                this.calculateIQ();

            score = local.score;
            correct = local.correct;
            level = local.level;
        }


        /* ====================================================
           RESULT STATE
           ==================================================== */

        State.test.resultData = {
            score,
            correct,
            level,
            attemptId,
            resultVisible,
            paymentRequired
        };


        /*
         * MUHIM:
         *
         * Payment hali tasdiqlanmagan bo'lsa,
         * completed.iq ni frontendda unlock qilmaymiz.
         *
         * Backend tasdiqlagan natija / /api/me orqali
         * haqiqiy completed state keladi.
         */

        if (!paymentRequired) {

            State.completed.iq =
                score;
        }


        /* ====================================================
           PAYMENT REQUIRED
           ==================================================== */

        if (
            paymentRequired &&
            !resultVisible
        ) {

            const price =
                Number(
                    State.settings.iq_price || 0
                );

            const priceEl =
                document.getElementById(
                    "payreq-price"
                );

            if (priceEl) {

                priceEl.textContent =
                    price.toLocaleString(
                        "uz-UZ"
                    ) + " so‘m";
            }

            this.go(
                "payment-required"
            );

            return;
        }


        /* ====================================================
           FREE / VISIBLE RESULT
           ==================================================== */

        this.renderResult(
            score,
            correct,
            level
        );

        this.go("result");

        this.applyUnlocks();
    },


    /* ========================================================
       LOCAL IQ CALCULATION
       ======================================================== */

    calculateIQ() {

        let weighted = 0;
        let maxWeighted = 0;
        let correct = 0;


        QUESTIONS.forEach(
            (question, index) => {

                const weight =
                    Number(
                        question.weight
                    ) || 0;

                maxWeighted += weight;


                const answer =
                    State.test.answers[index];


                if (
                    answer ===
                    question.correct
                ) {

                    weighted += weight;

                    correct++;
                }
            }
        );


        let score = 70;

        if (maxWeighted > 0) {

            score = Math.round(
                70 +
                (
                    weighted /
                    maxWeighted
                ) * 60
            );
        }


        let level;

        if (score >= 115) {

            level =
                "YUQORI DARAJA";

        } else if (score >= 100) {

            level =
                "O‘RTA DARAJA";

        } else {

            level =
                "RIVOJLANTIRISH";
        }


        return {
            score,
            correct,
            weighted,
            maxWeighted,
            level
        };
    },


    /* ========================================================
       IQ RESULT
       ======================================================== */

    renderResult(
        score,
        correct,
        level
    ) {

        const scoreEl =
            document.getElementById(
                "res-score"
            );

        const levelEl =
            document.getElementById(
                "res-level"
            );

        const correctEl =
            document.getElementById(
                "res-correct"
            );

        const timeEl =
            document.getElementById(
                "res-time"
            );


        if (scoreEl) {
            scoreEl.textContent =
                score;
        }

        if (levelEl) {
            levelEl.textContent =
                level;
        }

        if (correctEl) {

            correctEl.textContent =
                `${correct} / ${QUESTIONS.length}`;
        }


        const duration =
            Number(
                State.test.duration
            ) || 0;

        const minutes =
            String(
                Math.floor(
                    duration / 60
                )
            ).padStart(2, "0");

        const seconds =
            String(
                duration % 60
            ).padStart(2, "0");

        if (timeEl) {

            timeEl.textContent =
                `${minutes}:${seconds}`;
        }


        /* ====================================================
           ANALYSIS
           ==================================================== */

        const directions = [

            {
                label: "Mantiq",
                val: Math.min(
                    100,
                    50 + correct * 3
                )
            },

            {
                label: "Pattern",
                val: Math.min(
                    100,
                    55 + correct * 2.5
                )
            },

            {
                label: "Raqamlar",
                val: Math.min(
                    100,
                    45 + correct * 3.2
                )
            },

            {
                label: "Fazoviy fikr",
                val: Math.min(
                    100,
                    40 + correct * 3.5
                )
            }
        ];


        document
            .querySelectorAll(".dir")
            .forEach((element, index) => {

                const direction =
                    directions[index];

                if (!direction) {
                    return;
                }

                element.dataset.label =
                    direction.label;


                const fill =
                    element.querySelector(
                        ".dir-fill"
                    );

                const value =
                    element.querySelector(
                        "span"
                    );


                if (value) {

                    value.textContent =
                        Math.round(
                            direction.val
                        ) + "%";
                }


                if (fill) {

                    fill.style.width =
                        "0%";

                    setTimeout(() => {

                        fill.style.width =
                            direction.val +
                            "%";

                    }, 100 + index * 150);
                }
            });


        const strongest =
            directions.reduce(
                (best, item) =>
                    item.val > best.val
                        ? item
                        : best,
                directions[0]
            );


        const strongestEl =
            document.getElementById(
                "res-strongest"
            );

        if (strongestEl) {

            strongestEl.textContent =
                strongest?.label || "—";
        }
    },


    /* ========================================================
       CERTIFICATE
       ======================================================== */

    async getCertificate() {

        if (!initData) {

            alert(
                "Sertifikat uchun Telegram kerak."
            );

            return;
        }

        haptic("medium");


        try {

            const response =
                await fetch(
                    "/api/certificate/generate",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                initData
                            })
                    }
                );


            if (!response.ok) {

                alert(
                    "Sertifikat topilmadi. " +
                    "Avval IQ testni yakunlang."
                );

                return;
            }


            const blob =
                await response.blob();

            const url =
                window.URL.createObjectURL(
                    blob
                );


            const link =
                document.createElement(
                    "a"
                );

            link.href = url;

            link.download =
                "IQ-TEST-BOT-Sertifikat.png";

            document.body.appendChild(
                link
            );

            link.click();

            link.remove();

            window.URL.revokeObjectURL(
                url
            );

        } catch (error) {

            console.error(
                "[CERTIFICATE]",
                error
            );

            alert(
                "Sertifikat yuklashda xatolik."
            );
        }
    },


    /* ========================================================
       SHARE RESULT
       ======================================================== */

    shareResult() {

        const score =
            document.getElementById(
                "res-score"
            )?.textContent || "0";


        const text =
            `IQ TEST BOT\n\n` +
            `Men IQ-style testda ` +
            `${score} ball oldim!\n` +
            `Siz ham sinab ko‘ring.`;


        const botUrl =
            "https://t.me/iqtest_ubot";


        const shareUrl =
            `https://t.me/share/url` +
            `?url=${encodeURIComponent(botUrl)}` +
            `&text=${encodeURIComponent(text)}`;


        if (tg?.openTelegramLink) {

            tg.openTelegramLink(
                shareUrl
            );

            return;
        }


        if (
            navigator.clipboard
        ) {

            navigator.clipboard
                .writeText(
                    `${text}\n${botUrl}`
                )
                .then(() => {

                    alert(
                        "Natija matni nusxalandi."
                    );

                })
                .catch(() => {

                    alert(
                        `${text}\n${botUrl}`
                    );
                });

        } else {

            alert(
                `${text}\n${botUrl}`
            );
        }
    },


    /* ========================================================
       RETRY IQ
       ======================================================== */

    retry() {

        const price =
            Number(
                State.settings.iq_retry_price ||
                0
            );


        /*
         * Agar backend retry uchun to'lov
         * talab qilsa, payment keyin yaratiladi.
         */

        if (
            price > 0 &&
            State.completed.iq
        ) {

            const confirmed =
                confirm(
                    `IQ testni qayta ishlash ` +
                    `${price.toLocaleString("uz-UZ")} so‘m.\n\n` +
                    `Davom etasizmi?`
                );

            if (!confirmed) {
                return;
            }
        }


        State.test = {

            type: "iq",

            sessionId: null,

            attemptId: null,

            current: 0,

            answers:
                new Array(
                    QUESTIONS.length
                ).fill(null),

            startedAt: null,

            duration: 0,

            timerInterval: null,

            resultData: null
        };


        this.startIQ();
    },


    /* ========================================================
       START IQ PAYMENT
       ======================================================== */

    async startIQPayment() {

        const attemptId =
            State.test.resultData?.attemptId ||
            State.test.attemptId ||
            null;


        await this.createPayment(
            "iq",
            attemptId,
            null
        );
    },


    /* ========================================================
       START BATTLE PAYMENT
       ======================================================== */

    async startBattlePayment() {

        if (!State.battle.id) {

            alert(
                "Battle topilmadi."
            );

            return;
        }


        await this.createPayment(
            "battle",
            null,
            State.battle.id
        );
    },


    /* ========================================================
       CREATE PAYMENT
       ======================================================== */

    async createPayment(
        product,
        attemptId = null,
        battleId = null
    ) {

        if (!initData) {

            alert(
                "To‘lov faqat Telegram orqali amalga oshiriladi."
            );

            return;
        }

        haptic("medium");


        const res =
            await api(
                "/api/payment/create",
                {
                    initData,

                    product,

                    attempt_id:
                        attemptId,

                    battle_id:
                        battleId
                }
            );


        if (!res?.ok) {

            console.error(
                "[PAYMENT CREATE]",
                res
            );

            alert(
                res?.error ||
                "To‘lov yaratishda xatolik."
            );

            return;
        }


        /* ====================================================
           FREE PRODUCT
           ==================================================== */

        if (res.free) {

            if (
                product === "iq"
            ) {

                const result =
                    State.test.resultData;

                if (result) {

                    State.completed.iq =
                        result.score;

                    this.renderResult(
                        result.score,
                        result.correct,
                        result.level
                    );

                    this.go("result");

                    this.applyUnlocks();
                }

                return;
            }


            if (
                product === "battle"
            ) {

                this.checkBattle();

                return;
            }


            /*
             * EQ / PQ uchun ham free
             * bo'lsa, ularning natijasi
             * o'z finish funksiyasida
             * boshqariladi.
             */

            return;
        }


        /* ====================================================
           PAYMENT STATE
           ==================================================== */

        State.payment.id =
            res.payment_id || null;

        State.payment.product =
            product;

        State.payment.amount =
            Number(res.amount) || 0;

        State.payment.cards =
            Array.isArray(res.cards)
                ? res.cards
                : [];

        State.payment.attemptId =
            attemptId;

        State.payment.battleId =
            battleId;


        /* ====================================================
           PAYMENT UI
           ==================================================== */

        const amountEl =
            document.getElementById(
                "pay-amount"
            );

        if (amountEl) {

            amountEl.textContent =
                State.payment.amount
                    .toLocaleString("uz-UZ") +
                " so‘m";
        }


        const cardsEl =
            document.getElementById(
                "pay-cards"
            );


        if (cardsEl) {

            if (
                State.payment.cards.length
            ) {

                cardsEl.innerHTML =
                    State.payment.cards
                        .map(card => `
                            <div class="pay-card">

                                <div
                                    class="pay-card-num"
                                >
                                    ${card.card_number || ""}
                                </div>

                                <div
                                    class="pay-card-holder"
                                >
                                    ${card.holder || ""}
                                </div>

                                <div
                                    class="pay-card-bank"
                                >
                                    ${card.bank || ""}
                                </div>

                            </div>
                        `)
                        .join("");

            } else {

                cardsEl.innerHTML = `
                    <div>
                        Karta mavjud emas.
                    </div>
                `;
            }
        }


        this.go("payment");

        this.startPaymentPoll();
    },


    /* ========================================================
       PAYMENT POLLING
       ======================================================== */

    startPaymentPoll() {

        if (
            State.payment.pollInterval
        ) {

            clearInterval(
                State.payment.pollInterval
            );
        }


        State.payment.pollInterval =
            setInterval(
                async () => {

                    if (
                        !State.payment.id
                    ) {
                        return;
                    }


                    const res =
                        await api(
                            `/api/payment/${State.payment.id}`,
                            {
                                initData
                            }
                        );


                    if (
                        !res?.ok ||
                        !res.payment
                    ) {
                        return;
                    }


                    if (
                        res.payment.status !==
                        "approved"
                    ) {
                        return;
                    }


                    clearInterval(
                        State.payment.pollInterval
                    );

                    State.payment.pollInterval =
                        null;


                    const product =
                        State.payment.product;


                    /* ---------- IQ ---------- */

                    if (
                        product === "iq"
                    ) {

                        const result =
                            State.test.resultData;

                        if (result) {

                            State.completed.iq =
                                result.score;

                            this.renderResult(
                                result.score,
                                result.correct,
                                result.level
                            );

                            this.go("result");

                            this.applyUnlocks();
                        }

                        return;
                    }


                    /* ---------- BATTLE ---------- */

                    if (
                        product === "battle"
                    ) {

                        await this.checkBattle();

                        return;
                    }


                    /*
                     * EQ/PQ payment approval:
                     * natijani serverdan qayta
                     * olish keyingi qismda
                     * bajariladi.
                     */
                },
                5000
            );
    },


    /* ========================================================
       RECEIPT MESSAGE
       ======================================================== */

    async sendReceipt() {

        alert(
            "Chek rasmini Telegram botga yuboring.\n\n" +
            "Bot → chek rasmini yuboring."
        );
    },


    /* ========================================================
       EQ — START
       ======================================================== */

    async startEQ() {

        const alreadyCompleted =
            State.completed.eq !==
            undefined &&
            State.completed.eq !==
            null;


        if (alreadyCompleted) {

            const retryPrice =
                Number(
                    State.settings.eq_retry_price ||
                    0
                );


            if (retryPrice > 0) {

                const confirmed =
                    confirm(
                        `EQ testni qayta ishlash ` +
                        `${retryPrice.toLocaleString("uz-UZ")} so‘m.\n\n` +
                        `Davom etasizmi?`
                    );

                if (!confirmed) {
                    return;
                }
            }
        }


        haptic("medium");


        if (State.test.timerInterval) {

            clearInterval(
                State.test.timerInterval
            );

            State.test.timerInterval =
                null;
        }


        State.test.type = "eq";

        State.test.sessionId =
            null;

        State.test.attemptId =
            null;

        State.test.current =
            0;

        State.test.answers =
            new Array(
                EQ_QUESTIONS.length
            ).fill(null);

        State.test.startedAt =
            Date.now();

        State.test.duration =
            0;

        State.test.resultData =
            null;


        if (initData) {

            const res =
                await api(
                    "/api/session/start",
                    {
                        initData,
                        test_type: "eq"
                    }
                );

            if (res?.ok) {

                State.test.sessionId =
                    res.session_id || null;

                State.test.attemptId =
                    res.attempt_id || null;
            }
        }


        this.go("eq-intro");
    },


    /* ========================================================
       EQ TEST
       ======================================================== */

    goEQTest() {

        this.go("eq-test");

        this.renderEQQuestion();
    },


    renderEQQuestion() {

        const index =
            State.test.current;

        const question =
            EQ_QUESTIONS[index];

        if (!question) {
            return;
        }


        const progress =
            document.getElementById(
                "eq-progress-text"
            );

        const fill =
            document.getElementById(
                "eq-progress-fill"
            );

        const text =
            document.getElementById(
                "eq-question-text"
            );

        const next =
            document.getElementById(
                "eq-next"
            );


        if (progress) {

            progress.textContent =
                `Q${index + 1} / ${EQ_QUESTIONS.length}`;
        }


        if (fill) {

            fill.style.width =
                (
                    index /
                    EQ_QUESTIONS.length *
                    100
                ) + "%";
        }


        if (text) {

            text.textContent =
                question.text;
        }


        if (next) {

            next.disabled = true;

            next.textContent =
                index ===
                EQ_QUESTIONS.length - 1
                    ? "YAKUNLASH →"
                    : "KEYINGISI →";
        }


        renderTextOptions(
            document.getElementById(
                "eq-options"
            ),
            question.options,
            selected => {

                State.test.answers[index] =
                    selected;

                if (next) {
                    next.disabled =
                        false;
                }
            }
        );
    },


    /* ========================================================
       EQ NEXT
       ======================================================== */

    nextEQQuestion() {

        haptic("light");

        if (
            State.test.current ===
            EQ_QUESTIONS.length - 1
        ) {

            this.finishEQ();

            return;
        }


        State.test.current++;

        this.renderEQQuestion();
    },


    /* ========================================================
       EQ FINISH — KEYINGI QISMDA DAVOM
       ======================================================== */
    /* ========================================================
       EQ FINISH
       ======================================================== */

    async finishEQ() {

        this.go("iq-loading");

        await new Promise(resolve =>
            setTimeout(resolve, 2500)
        );


        let total = 0;


        EQ_QUESTIONS.forEach(
            (question, index) => {

                const answer =
                    State.test.answers[index];

                if (
                    answer !== null &&
                    answer !== undefined
                ) {

                    total +=
                        Number(
                            question.scores[answer]
                        ) || 0;
                }
            }
        );


        const maxScore =
            EQ_QUESTIONS.length * 4;


        const percent =
            Math.round(
                (total / maxScore) * 100
            );


        let level;

        if (percent >= 80) {

            level =
                "JUDA YUQORI";

        } else if (percent >= 60) {

            level =
                "YUQORI";

        } else if (percent >= 40) {

            level =
                "O‘RTA";

        } else {

            level =
                "RIVOJLANTIRISH";
        }


        /* ====================================================
           BACKENDGA YUBORISH
           ==================================================== */

        let paymentRequired = false;

        let attemptId =
            State.test.attemptId ||
            null;


        if (
            initData &&
            State.test.sessionId
        ) {

            const res =
                await api(
                    "/api/test/submit",
                    {
                        initData,

                        session_id:
                            State.test.sessionId,

                        answers:
                            State.test.answers,

                        duration:
                            Math.floor(
                                (
                                    Date.now() -
                                    State.test.startedAt
                                ) / 1000
                            )
                    }
                );


            if (res?.ok) {

                paymentRequired =
                    res.payment_required === true;

                attemptId =
                    res.attempt_id ||
                    attemptId;

                State.test.attemptId =
                    attemptId;
            }
        }


        State.test.resultData = {

            score: percent,

            correct: total,

            level,

            attemptId,

            paymentRequired
        };


        /* ====================================================
           PAYMENT KERAK BO'LSA
           ==================================================== */

        if (paymentRequired) {

            const price =
                Number(
                    State.settings.eq_price ||
                    State.settings.eq_retry_price ||
                    0
                );


            const priceEl =
                document.getElementById(
                    "payreq-price"
                );

            if (priceEl) {

                priceEl.textContent =
                    price.toLocaleString(
                        "uz-UZ"
                    ) + " so‘m";
            }


            this.go(
                "payment-required"
            );

            return;
        }


        /* ====================================================
           FREE RESULT
           ==================================================== */

        State.completed.eq =
            percent;


        const scoreEl =
            document.getElementById(
                "eq-res-score"
            );

        const levelEl =
            document.getElementById(
                "eq-res-level"
            );


        if (scoreEl) {

            scoreEl.textContent =
                percent + "%";
        }


        if (levelEl) {

            levelEl.textContent =
                level;
        }


        this.go("eq-result");

        this.applyUnlocks();
    },


    /* ========================================================
       PQ START
       ======================================================== */

    async startPQ() {

        const alreadyCompleted =
            State.completed.pq !==
            undefined &&
            State.completed.pq !==
            null;


        if (alreadyCompleted) {

            const retryPrice =
                Number(
                    State.settings.pq_retry_price ||
                    0
                );


            if (retryPrice > 0) {

                const confirmed =
                    confirm(
                        `PQ testni qayta ishlash ` +
                        `${retryPrice.toLocaleString("uz-UZ")} so‘m.\n\n` +
                        `Davom etasizmi?`
                    );

                if (!confirmed) {
                    return;
                }
            }
        }


        haptic("medium");


        if (State.test.timerInterval) {

            clearInterval(
                State.test.timerInterval
            );

            State.test.timerInterval =
                null;
        }


        State.test.type = "pq";

        State.test.sessionId =
            null;

        State.test.attemptId =
            null;

        State.test.current =
            0;

        State.test.answers =
            new Array(
                PQ_QUESTIONS.length
            ).fill(null);

        State.test.startedAt =
            Date.now();

        State.test.duration =
            0;

        State.test.resultData =
            null;


        /* ====================================================
           BACKEND SESSION
           ==================================================== */

        if (initData) {

            const res =
                await api(
                    "/api/session/start",
                    {
                        initData,
                        test_type: "pq"
                    }
                );


            if (res?.ok) {

                State.test.sessionId =
                    res.session_id ||
                    null;

                State.test.attemptId =
                    res.attempt_id ||
                    null;
            }
        }


        this.go("pq-intro");
    },


    /* ========================================================
       PQ TEST START
       ======================================================== */

    goPQTest() {

        this.go("pq-test");

        this.renderPQQuestion();
    },


    /* ========================================================
       PQ QUESTION
       ======================================================== */

    renderPQQuestion() {

        const index =
            State.test.current;

        const question =
            PQ_QUESTIONS[index];


        if (!question) {
            return;
        }


        const progress =
            document.getElementById(
                "pq-progress-text"
            );

        const fill =
            document.getElementById(
                "pq-progress-fill"
            );

        const text =
            document.getElementById(
                "pq-question-text"
            );

        const next =
            document.getElementById(
                "pq-next"
            );


        /* ---------- PROGRESS ---------- */

        if (progress) {

            progress.textContent =
                `Q${index + 1} / ${PQ_QUESTIONS.length}`;
        }


        if (fill) {

            fill.style.width =
                (
                    index /
                    PQ_QUESTIONS.length *
                    100
                ) + "%";
        }


        /* ---------- QUESTION ---------- */

        if (text) {

            text.textContent =
                question.text;
        }


        /* ---------- NEXT ---------- */

        if (next) {

            next.disabled = true;

            next.textContent =
                index ===
                PQ_QUESTIONS.length - 1

                    ? "YAKUNLASH →"

                    : "KEYINGISI →";
        }


        /* ---------- OPTIONS ---------- */

        renderTextOptions(

            document.getElementById(
                "pq-options"
            ),

            question.options,

            selectedIndex => {

                State.test.answers[index] =
                    selectedIndex;


                if (next) {

                    next.disabled =
                        false;
                }
            }
        );


        /* ====================================================
           OLD ANSWERNI QAYTA KO'RSATISH
           ==================================================== */

        const previous =
            State.test.answers[index];


        if (
            previous !== null &&
            previous !== undefined
        ) {

            const options =
                document.querySelectorAll(
                    "#pq-options .option"
                );


            options[
                previous
            ]?.classList.add(
                "selected"
            );


            if (next) {
                next.disabled = false;
            }
        }
    },


    /* ========================================================
       PQ NEXT
       ======================================================== */

    nextPQQuestion() {

        haptic("light");


        if (
            State.test.current ===
            PQ_QUESTIONS.length - 1
        ) {

            this.finishPQ();

            return;
        }


        State.test.current++;

        this.renderPQQuestion();
    },


    /* ========================================================
       PQ FINISH
       ======================================================== */

    async finishPQ() {

        this.go("iq-loading");

        await new Promise(resolve =>
            setTimeout(resolve, 2500)
        );


        let total = 0;


        PQ_QUESTIONS.forEach(
            (question, index) => {

                const answer =
                    State.test.answers[index];


                if (
                    answer !== null &&
                    answer !== undefined
                ) {

                    total +=
                        Number(
                            question.scores[answer]
                        ) || 0;
                }
            }
        );


        const maxScore =
            PQ_QUESTIONS.length * 4;


        const percent =
            Math.round(
                (total / maxScore) * 100
            );


        let level;

        if (percent >= 80) {

            level =
                "JUDA YAXSHI";

        } else if (percent >= 60) {

            level =
                "YAXSHI";

        } else if (percent >= 40) {

            level =
                "O‘RTA";

        } else {

            level =
                "RIVOJLANTIRISH KERAK";
        }


        /* ====================================================
           BACKEND
           ==================================================== */

        let paymentRequired = false;

        let attemptId =
            State.test.attemptId ||
            null;


        if (
            initData &&
            State.test.sessionId
        ) {

            const res =
                await api(
                    "/api/test/submit",
                    {
                        initData,

                        session_id:
                            State.test.sessionId,

                        answers:
                            State.test.answers,

                        duration:
                            Math.floor(
                                (
                                    Date.now() -
                                    State.test.startedAt
                                ) / 1000
                            )
                    }
                );


            if (res?.ok) {

                paymentRequired =
                    res.payment_required === true;

                attemptId =
                    res.attempt_id ||
                    attemptId;

                State.test.attemptId =
                    attemptId;
            }
        }


        State.test.resultData = {

            score: percent,

            correct: total,

            level,

            attemptId,

            paymentRequired
        };


        /* ====================================================
           PAYMENT REQUIRED
           ==================================================== */

        if (paymentRequired) {

            const price =
                Number(
                    State.settings.pq_price ||
                    State.settings.pq_retry_price ||
                    0
                );


            const priceEl =
                document.getElementById(
                    "payreq-price"
                );


            if (priceEl) {

                priceEl.textContent =
                    price.toLocaleString(
                        "uz-UZ"
                    ) + " so‘m";
            }


            this.go(
                "payment-required"
            );

            return;
        }


        /* ====================================================
           RESULT
           ==================================================== */

        State.completed.pq =
            percent;


        const scoreEl =
            document.getElementById(
                "pq-res-score"
            );

        const levelEl =
            document.getElementById(
                "pq-res-level"
            );


        if (scoreEl) {

            scoreEl.textContent =
                percent + "%";
        }


        if (levelEl) {

            levelEl.textContent =
                level;
        }


        this.go("pq-result");

        this.applyUnlocks();
    },


    /* ========================================================
       PROFILE
       ======================================================== */

    openProfile() {

        const iq =
            State.completed.iq;

        const eq =
            State.completed.eq;

        const pq =
            State.completed.pq;


        if (
            iq === undefined ||
            iq === null ||
            eq === undefined ||
            eq === null ||
            pq === undefined ||
            pq === null
        ) {

            alert(
                "Avval IQ, EQ va PQ testlarini tugatishingiz kerak."
            );

            return;
        }


        const iqEl =
            document.getElementById(
                "prof-iq"
            );

        const eqEl =
            document.getElementById(
                "prof-eq"
            );

        const pqEl =
            document.getElementById(
                "prof-pq"
            );


        if (iqEl) {
            iqEl.textContent =
                iq;
        }

        if (eqEl) {
            eqEl.textContent =
                eq + "%";
        }

        if (pqEl) {
            pqEl.textContent =
                pq + "%";
        }


        /* ====================================================
           STRENGTHS / WEAKNESSES
           ==================================================== */

        const strengths = [];
        const weaknesses = [];


        if (iq >= 115) {

            strengths.push(
                "Kuchli mantiqiy fikrlash"
            );

        } else {

            weaknesses.push(
                "Mantiqiy fikrlashni rivojlantirish"
            );
        }


        if (eq >= 70) {

            strengths.push(
                "Yaxshi hissiy intellekt"
            );

        } else {

            weaknesses.push(
                "Emotsiyalarni boshqarish"
            );
        }


        if (pq >= 70) {

            strengths.push(
                "Ishni o‘z vaqtida bajarish"
            );

        } else {

            weaknesses.push(
                "Prokrastinatsiyani kamaytirish"
            );
        }


        const strengthsEl =
            document.getElementById(
                "prof-strengths"
            );

        const weaknessesEl =
            document.getElementById(
                "prof-weaknesses"
            );


        if (strengthsEl) {

            strengthsEl.innerHTML =
                strengths.length

                    ? strengths
                        .map(
                            item =>
                                `<li>${item}</li>`
                        )
                        .join("")

                    : "<li>—</li>";
        }


        if (weaknessesEl) {

            weaknessesEl.innerHTML =
                weaknesses.length

                    ? weaknesses
                        .map(
                            item =>
                                `<li>${item}</li>`
                        )
                        .join("")

                    : "<li>—</li>";
        }


        /* ====================================================
           OVERALL
           ==================================================== */

        const overall =
            Math.round(
                (
                    (
                        (iq - 70) /
                        60 *
                        100
                    ) * 0.5
                ) +
                (
                    eq * 0.25
                ) +
                (
                    pq * 0.25
                )
            );


        const overallEl =
            document.getElementById(
                "prof-overall"
            );


        if (overallEl) {

            overallEl.textContent =
                overall;
        }


        const summaryEl =
            document.getElementById(
                "prof-summary"
            );


        if (summaryEl) {

            summaryEl.textContent =
                overall >= 75

                    ? "Siz analitik va hissiy jihatdan kuchli insonsiz."

                    : overall >= 55

                        ? "Sizning profilingiz o‘rtacha, rivojlanish uchun joy bor."

                        : "Sizga bir nechta yo‘nalishda rivojlanish kerak.";
        }


        this.go("profile");
    },
        /* ========================================================
       BATTLE
       ======================================================== */

    openBattle() {

        this.go("battle-home");
    },


    /* ========================================================
       CREATE BATTLE
       ======================================================== */

    async createBattle() {

        if (!initData) {

            alert(
                "Battle faqat Telegram orqali ishlaydi."
            );

            return;
        }

        haptic("medium");


        const res =
            await api(
                "/api/battle/create",
                {
                    initData
                }
            );


        if (res?.ok) {

            State.battle.id =
                res.battle_id;

            State.battle.code =
                res.code;

            State.battle.role =
                "creator";


            const codeEl =
                document.getElementById(
                    "battle-code-display"
                );

            const priceEl =
                document.getElementById(
                    "battle-price-display"
                );


            if (codeEl) {

                codeEl.textContent =
                    res.code;
            }


            if (priceEl) {

                priceEl.textContent =
                    Number(
                        res.price || 0
                    ).toLocaleString(
                        "uz-UZ"
                    ) +
                    " so‘m";
            }


            this.go("battle-wait");

            this.startBattlePoll();

            return;
        }


        /* ====================================================
           ACTIVE BATTLE
           ==================================================== */

        if (
            res?.error ===
            "ACTIVE_BATTLE_EXISTS"
        ) {

            State.battle.id =
                res.battle_id;

            State.battle.code =
                res.code;

            State.battle.role =
                "creator";

            this.go("battle-wait");

            this.startBattlePoll();

            return;
        }


        alert(
            res?.error ||
            "Battle yaratishda xatolik."
        );
    },


    /* ========================================================
       JOIN BATTLE
       ======================================================== */

    async joinBattle() {

        const input =
            document.getElementById(
                "battle-join-code"
            );


        const code =
            input?.value
                ?.trim()
                .toUpperCase() || "";


        if (
            !/^[A-Z0-9]{4}$/.test(code)
        ) {

            alert(
                "4 xonali kod kiriting."
            );

            input?.focus();

            return;
        }


        if (!initData) {

            alert(
                "Battle faqat Telegram orqali ishlaydi."
            );

            return;
        }


        haptic("medium");


        const res =
            await api(
                "/api/battle/join",
                {
                    initData,
                    code
                }
            );


        if (res?.ok) {

            State.battle.id =
                res.battle_id;

            State.battle.code =
                code;

            State.battle.role =
                "opponent";


            this.go("battle-wait");

            this.startBattlePoll();

            return;
        }


        const errors = {

            NOT_FOUND:
                "Kod topilmadi.",

            OWN_BATTLE:
                "O‘z battlingizga qo‘shila olmaysiz.",

            BATTLE_NOT_OPEN:
                "Battle allaqachon boshlangan.",

            BATTLE_FULL:
                "Battle to‘lgan.",

            ACTIVE_BATTLE_EXISTS:
                "Sizda faol battle bor."
        };


        alert(
            errors[res?.error] ||
            res?.error ||
            "Battlega qo‘shilishda xatolik."
        );
    },


    /* ========================================================
       BATTLE POLLING
       ======================================================== */

    startBattlePoll() {

        if (
            State.battle.pollInterval
        ) {

            clearInterval(
                State.battle.pollInterval
            );
        }


        /*
         * Birinchi tekshiruvni darhol qilamiz.
         */

        this.checkBattle();


        State.battle.pollInterval =
            setInterval(
                () => {

                    this.checkBattle();

                },
                5000
            );
    },


    stopBattlePoll() {

        if (
            State.battle.pollInterval
        ) {

            clearInterval(
                State.battle.pollInterval
            );

            State.battle.pollInterval =
                null;
        }
    },


    /* ========================================================
       CHECK BATTLE
       ======================================================== */

    async checkBattle() {

        if (!State.battle.id) {
            return;
        }


        const res =
            await api(
                `/api/battle/${State.battle.id}`,
                {
                    initData
                }
            );


        if (!res?.ok) {
            return;
        }


        State.battle.players =
            Array.isArray(res.players)
                ? res.players
                : [];


        const battle =
            res.battle || {};


        const players =
            State.battle.players;


        const myPlayer =
            players.find(
                player =>
                    player.is_me
            );


        /* ====================================================
           STATUS
           ==================================================== */

        const statusEl =
            document.getElementById(
                "battle-wait-status"
            );


        if (statusEl) {

            if (
                battle.status ===
                "waiting_for_player"
            ) {

                statusEl.textContent =
                    "Do‘stingiz kodni kiritishini kuting...";

            } else if (
                battle.status ===
                "waiting_for_payment"
            ) {

                statusEl.textContent =
                    "To‘lovni amalga oshiring.";

            } else if (
                battle.status ===
                "ready"
            ) {

                statusEl.textContent =
                    "Ikkalangiz tayyorsiz! Testni boshlashingiz mumkin.";

            } else if (
                battle.status ===
                "in_progress"
            ) {

                statusEl.textContent =
                    "Test davom etmoqda.";

            } else if (
                battle.status ===
                "completed" ||
                battle.status ===
                "draw"
            ) {

                this.openBattleResult(res);

                return;
            }
        }


        /* ====================================================
           PLAYERS
           ==================================================== */

        const playersEl =
            document.getElementById(
                "battle-players-list"
            );


        if (playersEl) {

            playersEl.innerHTML =
                players
                    .map(player => {

                        const name =
                            player.is_me
                                ? "SIZ"
                                : (
                                    player.name ||
                                    "O‘yinchi"
                                );


                        const question =
                            Number(
                                player.current_question
                            ) || 0;


                        let status =
                            "—";


                        if (
                            player.test_status ===
                            "completed"
                        ) {

                            status =
                                "✓";

                        } else if (
                            player.test_status ===
                            "in_progress"
                        ) {

                            status =
                                "…";
                        }


                        return `
                            <div
                                class="battle-player-row ${
                                    player.is_me
                                        ? "me"
                                        : ""
                                }"
                            >

                                <span
                                    class="bp-name"
                                >
                                    ${name}
                                </span>

                                <span
                                    class="bp-progress"
                                >
                                    ${question}/18
                                </span>

                                <span
                                    class="bp-status"
                                >
                                    ${status}
                                </span>

                            </div>
                        `;
                    })
                    .join("");
        }


        /* ====================================================
           BUTTONS
           ==================================================== */

        const startBtn =
            document.getElementById(
                "battle-start-btn"
            );


        const continueBtn =
            document.getElementById(
                "battle-continue-btn"
            );


        if (
            startBtn &&
            battle.status === "ready" &&
            myPlayer &&
            myPlayer.test_status ===
                "not_started"
        ) {

            startBtn.style.display =
                "block";

        } else if (startBtn) {

            startBtn.style.display =
                "none";
        }


        if (
            continueBtn &&
            myPlayer &&
            myPlayer.test_status ===
                "in_progress"
        ) {

            continueBtn.style.display =
                "block";

        } else if (continueBtn) {

            continueBtn.style.display =
                "none";
        }
    },


    /* ========================================================
       START BATTLE TEST
       ======================================================== */

    async startBattleTest() {

        if (!State.battle.id) {

            alert(
                "Battle topilmadi."
            );

            return;
        }


        const res =
            await api(
                `/api/battle/${State.battle.id}/start`,
                {
                    initData
                }
            );


        if (!res?.ok) {

            alert(
                res?.error ||
                "Battle boshlanmadi."
            );

            return;
        }


        State.battle.sessionId =
            res.session_id || null;

        State.battle.current =
            0;

        State.battle.answers =
            new Array(
                QUESTIONS.length
            ).fill(null);

        State.battle.startedAt =
            Date.now();


        haptic("medium");

        this.go("battle-test");

        this.renderBattleQuestion();
    },


    /* ========================================================
       CONTINUE BATTLE
       ======================================================== */

    async continueBattle() {

        if (!State.battle.id) {
            return;
        }


        const res =
            await api(
                `/api/battle/${State.battle.id}`,
                {
                    initData
                }
            );


        if (!res?.ok) {
            return;
        }


        const myPlayer =
            (
                res.players || []
            ).find(
                player =>
                    player.is_me
            );


        if (
            myPlayer &&
            myPlayer.test_status ===
                "in_progress"
        ) {

            State.battle.current =
                Number(
                    myPlayer.current_question
                ) || 0;


            /*
             * Serverdagi javoblar
             * mavjud bo'lsa tiklaymiz.
             */

            State.battle.answers =
                Array.isArray(
                    myPlayer.answers
                )
                    ? myPlayer.answers
                    : new Array(
                        QUESTIONS.length
                    ).fill(null);


            State.battle.startedAt =
                Date.now();


            this.go("battle-test");

            this.renderBattleQuestion();

            return;
        }


        if (
            myPlayer &&
            myPlayer.test_status ===
                "not_started"
        ) {

            await this.startBattleTest();
        }
    },


    /* ========================================================
       RENDER BATTLE QUESTION
       ======================================================== */

    renderBattleQuestion() {

        const index =
            State.battle.current;


        const question =
            QUESTIONS[index];


        if (!question) {
            return;
        }


        const progress =
            document.getElementById(
                "battle-progress-text"
            );

        const fill =
            document.getElementById(
                "battle-progress-fill"
            );


        if (progress) {

            progress.textContent =
                `Q${index + 1} / ${QUESTIONS.length}`;
        }


        if (fill) {

            fill.style.width =
                (
                    index /
                    QUESTIONS.length *
                    100
                ) + "%";
        }


        renderMatrix(
            document.getElementById(
                "battle-matrix"
            ),
            question.matrix
        );


        const next =
            document.getElementById(
                "battle-next"
            );


        if (next) {

            next.disabled = true;

            next.textContent =
                index ===
                QUESTIONS.length - 1

                    ? "YAKUNLASH →"

                    : "KEYINGISI →";
        }


        renderOptions(

            document.getElementById(
                "battle-options"
            ),

            question.options,

            selectedIndex => {

                State.battle.answers[index] =
                    selectedIndex;


                if (next) {
                    next.disabled =
                        false;
                }


                /*
                 * Javobni serverga
                 * darhol sync qilamiz.
                 */

                this.syncBattle();
            }
        );


        /* ====================================================
           OLD ANSWER
           ==================================================== */

        const previous =
            State.battle.answers[index];


        if (
            previous !== null &&
            previous !== undefined
        ) {

            const options =
                document.querySelectorAll(
                    "#battle-options .option"
                );


            options[
                previous
            ]?.classList.add(
                "selected"
            );


            if (next) {
                next.disabled = false;
            }
        }
    },


    /* ========================================================
       SYNC BATTLE
       ======================================================== */

    async syncBattle() {

        if (!State.battle.id) {
            return;
        }


        try {

            await api(
                `/api/battle/${State.battle.id}/sync`,
                {
                    initData,

                    current_question:
                        State.battle.current + 1,

                    answers:
                        State.battle.answers
                }
            );

        } catch (error) {

            /*
             * Sync xatosi testni
             * to‘xtatmasligi kerak.
             */

            console.warn(
                "[BATTLE SYNC]",
                error
            );
        }
    },


    /* ========================================================
       NEXT BATTLE QUESTION
       ======================================================== */

    nextBattleQuestion() {

        haptic("light");


        if (
            State.battle.current ===
            QUESTIONS.length - 1
        ) {

            this.finishBattle();

            return;
        }


        State.battle.current++;


        /*
         * Keyingi savolga o'tishdan oldin
         * progress serverga yuboriladi.
         */

        this.syncBattle();

        this.renderBattleQuestion();
    },


    /* ========================================================
       FINISH BATTLE
       ======================================================== */

    async finishBattle() {

        if (!State.battle.id) {
            return;
        }


        this.go("iq-loading");


        await new Promise(resolve =>
            setTimeout(resolve, 1000)
        );


        const duration =
            State.battle.startedAt
                ? Math.floor(
                    (
                        Date.now() -
                        State.battle.startedAt
                    ) / 1000
                )
                : 0;


        const res =
            await api(
                `/api/battle/${State.battle.id}/finish`,
                {
                    initData,

                    answers:
                        State.battle.answers,

                    duration
                }
            );


        if (!res?.ok) {

            alert(
                res?.error ||
                "Battle yakunlashda xatolik."
            );

            this.go("battle-home");

            return;
        }


        this.stopBattlePoll();


        /* ====================================================
           MY SCORE
           ==================================================== */

        const myScoreEl =
            document.getElementById(
                "battle-my-score"
            );


        if (myScoreEl) {

            myScoreEl.textContent =
                Number(
                    res.score
                ) || 0;
        }


        /* ====================================================
           OPPONENT SCORE
           ==================================================== */

        const opponentScore =
            res.opponent_score;


        const opponentEl =
            document.getElementById(
                "battle-opp-score"
            );


        const winnerEl =
            document.getElementById(
                "battle-winner"
            );


        if (
            opponentScore !== null &&
            opponentScore !== undefined
        ) {

            if (opponentEl) {

                opponentEl.textContent =
                    Number(
                        opponentScore
                    ) || 0;
            }


            const myScore =
                Number(
                    res.score
                ) || 0;


            const enemyScore =
                Number(
                    opponentScore
                ) || 0;


            if (winnerEl) {

                if (
                    myScore > enemyScore
                ) {

                    winnerEl.textContent =
                        "SIZ G‘OLIB";

                    winnerEl.className =
                        "battle-winner win";

                } else if (
                    myScore < enemyScore
                ) {

                    winnerEl.textContent =
                        "DO‘STINGIZ G‘OLIB";

                    winnerEl.className =
                        "battle-winner lose";

                } else {

                    winnerEl.textContent =
                        "DURANG";

                    winnerEl.className =
                        "battle-winner draw";
                }
            }

        } else {

            if (opponentEl) {

                opponentEl.textContent =
                    "—";
            }


            if (winnerEl) {

                winnerEl.textContent =
                    "Kutilmoqda";

                winnerEl.className =
                    "battle-winner";
            }
        }


        this.go("battle-result");
    },


    /* ========================================================
       OPEN BATTLE RESULT
       ======================================================== */

    openBattleResult(data) {

        this.stopBattlePoll();


        const players =
            Array.isArray(data.players)
                ? data.players
                : [];


        const myPlayer =
            players.find(
                player =>
                    player.is_me
            );


        const opponent =
            players.find(
                player =>
                    !player.is_me
            );


        const myScoreEl =
            document.getElementById(
                "battle-my-score"
            );


        const opponentEl =
            document.getElementById(
                "battle-opp-score"
            );


        const winnerEl =
            document.getElementById(
                "battle-winner"
            );


        if (myScoreEl) {

            myScoreEl.textContent =
                myPlayer?.score ??
                "—";
        }


        if (opponentEl) {

            opponentEl.textContent =
                opponent?.score ??
                "—";
        }


        const battle =
            data.battle || {};


        if (winnerEl) {

            if (
                battle.status ===
                "draw"
            ) {

                winnerEl.textContent =
                    "DURANG";

                winnerEl.className =
                    "battle-winner draw";

            } else if (
                battle.winner_id !==
                undefined &&
                battle.winner_id !== null &&
                String(
                    battle.winner_id
                ) ===
                String(
                    State.user?.user_id
                )
            ) {

                winnerEl.textContent =
                    "SIZ G‘OLIB";

                winnerEl.className =
                    "battle-winner win";

            } else {

                winnerEl.textContent =
                    "DO‘STINGIZ G‘OLIB";

                winnerEl.className =
                    "battle-winner lose";
            }
        }


        this.go("battle-result");
    },
        /* ========================================================
       BACK / NAVIGATION
       ======================================================== */

    back() {

        const screen =
            State.currentScreen;


        const backMap = {

            "profile-name": "home",
            "iq-intro": "home",
            "sample": "iq-intro",
            "test": "home",

            "q6": "test",
            "q12": "test",

            "result": "home",

            "eq-intro": "home",
            "eq-test": "home",
            "eq-result": "home",

            "pq-intro": "home",
            "pq-test": "home",
            "pq-result": "home",

            "profile": "home",

            "battle-home": "home",
            "battle-wait": "battle-home",
            "battle-test": "battle-home",
            "battle-result": "battle-home",

            "payment": "home",
            "payment-required": "home",

            "iq-loading": "home"
        };


        const previous =
            backMap[screen] || "home";


        /*
         * Test davomida tasodifan chiqib
         * ketishni oldini olamiz.
         */

        if (
            screen === "test" ||
            screen === "eq-test" ||
            screen === "pq-test" ||
            screen === "battle-test"
        ) {

            const confirmed =
                confirm(
                    "Testni tark etsangiz, joriy natijalar saqlanmasligi mumkin.\n\n" +
                    "Chiqishni xohlaysizmi?"
                );


            if (!confirmed) {
                return;
            }
        }


        this.go(previous);
    },


    /* ========================================================
       HOME
       ======================================================== */

    home() {

        this.go("home");

        /*
         * Home ochilganda unlock holatini
         * qayta qo‘llaymiz.
         */

        this.applyUnlocks();
    },


    /* ========================================================
       PAYMENT SCREEN
       ======================================================== */

    openPayment() {

        if (
            !State.payment.id
        ) {

            alert(
                "Faol to‘lov topilmadi."
            );

            return;
        }

        this.go("payment");
    },


    /* ========================================================
       COPY BATTLE CODE
       ======================================================== */

    async copyBattleCode() {

        const code =
            State.battle.code ||
            document.getElementById(
                "battle-code-display"
            )?.textContent ||
            "";


        if (!code) {
            return;
        }


        try {

            await navigator.clipboard.writeText(
                code
            );


            haptic("light");


            alert(
                "Battle kodi nusxalandi."
            );

        } catch (error) {

            /*
             * Clipboard API ishlamasa
             * Telegram orqali fallback.
             */

            if (tg?.showPopup) {

                tg.showPopup({
                    title: "Battle kodi",
                    message: code,
                    buttons: [
                        {
                            type: "ok"
                        }
                    ]
                });

            } else {

                alert(
                    `Battle kodi: ${code}`
                );
            }
        }
    },


    /* ========================================================
       TELEGRAM USER
       ======================================================== */

    getTelegramUser() {

        try {

            return (
                tg?.initDataUnsafe
                    ?.user ||
                null
            );

        } catch {

            return null;
        }
    },


    /* ========================================================
       TELEGRAM CLOSE
       ======================================================== */

    close() {

        try {

            if (tg) {

                tg.close();

                return;
            }

        } catch (error) {

            console.warn(
                "[Telegram close]",
                error
            );
        }


        window.history.back();
    },


    /* ========================================================
       SHARE APP
       ======================================================== */

    shareApp() {

        const url =
            "https://t.me/iqtest_ubot";


        const text =
            "IQ TEST BOT — IQ, EQ va PQ testlarini sinab ko‘ring!";


        const shareUrl =
            "https://t.me/share/url" +
            "?url=" +
            encodeURIComponent(url) +
            "&text=" +
            encodeURIComponent(text);


        if (tg?.openTelegramLink) {

            tg.openTelegramLink(
                shareUrl
            );

            return;
        }


        window.open(
            shareUrl,
            "_blank"
        );
    },


    /* ========================================================
       RESET BATTLE
       ======================================================== */

    resetBattle() {

        this.stopBattlePoll();


        State.battle = {

            id: null,

            code: null,

            role: null,

            players: [],

            sessionId: null,

            current: 0,

            answers: [],

            startedAt: null,

            pollInterval: null
        };
    },


    /* ========================================================
       RESET PAYMENT
       ======================================================== */

    resetPayment() {

        if (
            State.payment.pollInterval
        ) {

            clearInterval(
                State.payment.pollInterval
            );
        }


        State.payment = {

            id: null,

            product: null,

            amount: 0,

            cards: [],

            pollInterval: null,

            attemptId: null,

            battleId: null
        };
    }
};


/* ============================================================
   EVENT BINDINGS
   ============================================================ */

function bindClick(
    selector,
    handler
) {

    const element =
        document.querySelector(
            selector
        );


    if (!element) {

        console.warn(
            "[EVENT] element not found:",
            selector
        );

        return;
    }


    /*
     * Duplicate listenerdan himoya.
     */

    if (
        element.dataset.bound ===
        "1"
    ) {
        return;
    }


    element.dataset.bound =
        "1";


    element.addEventListener(
        "click",
        handler
    );
}


/* ============================================================
   DOM READY
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        console.log(
            "[APP] DOM ready"
        );


        /* ====================================================
           INIT
           ==================================================== */

        App.init();


        /* ====================================================
           IQ
           ==================================================== */

        bindClick(
            '[data-test="iq"]',
            () => {

                haptic("medium");

                App.startIQ();
            }
        );


        /* ====================================================
           EQ
           ==================================================== */

        bindClick(
            "#card-eq",
            () => {

                const card =
                    document.getElementById(
                        "card-eq"
                    );


                if (
                    card?.classList.contains(
                        "locked"
                    )
                ) {

                    haptic("rigid");

                    return;
                }


                App.startEQ();
            }
        );


        /* ====================================================
           PQ
           ==================================================== */

        bindClick(
            "#card-pq",
            () => {

                const card =
                    document.getElementById(
                        "card-pq"
                    );


                if (
                    card?.classList.contains(
                        "locked"
                    )
                ) {

                    haptic("rigid");

                    return;
                }


                App.startPQ();
            }
        );


        /* ====================================================
           PROFILE
           ==================================================== */

        bindClick(
            "#card-profile",
            () => {

                const card =
                    document.getElementById(
                        "card-profile"
                    );


                if (
                    card?.classList.contains(
                        "locked"
                    )
                ) {

                    haptic("rigid");

                    return;
                }


                App.openProfile();
            }
        );


        /* ====================================================
           BATTLE
           ==================================================== */

        bindClick(
            "#battle-card",
            () => {

                App.openBattle();
            }
        );


        /* ====================================================
           PROFILE SAVE
           ==================================================== */

        bindClick(
            "#profile-save",
            () => {

                App.saveProfile();
            }
        );


        /* ====================================================
           SAMPLE NEXT
           ==================================================== */

        bindClick(
            "#sample-next",
            () => {

                App.goTest();
            }
        );


        /* ====================================================
           IQ NEXT
           ==================================================== */

        bindClick(
            "#test-next",
            () => {

                App.nextQuestion();
            }
        );


        /* ====================================================
           Q6 CONTINUE
           ==================================================== */

        bindClick(
            "#q6-next",
            () => {

                App.continueAfterQ6();
            }
        );


        /* ====================================================
           Q12 CONTINUE
           ==================================================== */

        bindClick(
            "#q12-next",
            () => {

                App.continueAfterQ12();
            }
        );


        /* ====================================================
           EQ INTRO
           ==================================================== */

        bindClick(
            "#eq-start",
            () => {

                App.goEQTest();
            }
        );


        /* ====================================================
           EQ NEXT
           ==================================================== */

        bindClick(
            "#eq-next",
            () => {

                App.nextEQQuestion();
            }
        );


        /* ====================================================
           PQ INTRO
           ==================================================== */

        bindClick(
            "#pq-start",
            () => {

                App.goPQTest();
            }
        );


        /* ====================================================
           PQ NEXT
           ==================================================== */

        bindClick(
            "#pq-next",
            () => {

                App.nextPQQuestion();
            }
        );


        /* ====================================================
           PROFILE GENDER
           ==================================================== */

        document
            .querySelectorAll(
                "#gender-selector [data-gender]"
            )
            .forEach(element => {

                if (
                    element.dataset.bound ===
                    "1"
                ) {
                    return;
                }


                element.dataset.bound =
                    "1";


                element.addEventListener(
                    "click",
                    () => {

                        App.selectGender(
                            element.dataset.gender
                        );
                    }
                );
            });


        /* ====================================================
           PROFILE COUNTRY
           ==================================================== */

        document
            .querySelectorAll(
                "#country-selector [data-country]"
            )
            .forEach(element => {

                if (
                    element.dataset.bound ===
                    "1"
                ) {
                    return;
                }


                element.dataset.bound =
                    "1";


                element.addEventListener(
                    "click",
                    () => {

                        App.selectCountry(
                            element.dataset.country
                        );
                    }
                );
            });


        /* ====================================================
           IQ PAYMENT
           ==================================================== */

        bindClick(
            "#iq-pay-btn",
            () => {

                App.startIQPayment();
            }
        );


        /* ====================================================
           RECEIPT
           ==================================================== */

        bindClick(
            "#send-receipt-btn",
            () => {

                App.sendReceipt();
            }
        );


        /* ====================================================
           CERTIFICATE
           ==================================================== */

        bindClick(
            "#certificate-btn",
            () => {

                App.getCertificate();
            }
        );


        /* ====================================================
           SHARE RESULT
           ==================================================== */

        bindClick(
            "#share-result-btn",
            () => {

                App.shareResult();
            }
        );


        /* ====================================================
           RETRY
           ==================================================== */

        bindClick(
            "#retry-btn",
            () => {

                App.retry();
            }
        );


        /* ====================================================
           BATTLE CREATE
           ==================================================== */

        bindClick(
            "#battle-create-btn",
            () => {

                App.createBattle();
            }
        );


        /* ====================================================
           BATTLE JOIN
           ==================================================== */

        bindClick(
            "#battle-join-btn",
            () => {

                App.joinBattle();
            }
        );


        /* ====================================================
           BATTLE START
           ==================================================== */

        bindClick(
            "#battle-start-btn",
            () => {

                App.startBattleTest();
            }
        );


        /* ====================================================
           BATTLE CONTINUE
           ==================================================== */

        bindClick(
            "#battle-continue-btn",
            () => {

                App.continueBattle();
            }
        );


        /* ====================================================
           BATTLE NEXT
           ==================================================== */

        bindClick(
            "#battle-next",
            () => {

                App.nextBattleQuestion();
            }
        );


        /* ====================================================
           BATTLE COPY
           ==================================================== */

        bindClick(
            "#battle-copy-btn",
            () => {

                App.copyBattleCode();
            }
        );


        console.log(
            "[APP] event bindings complete"
        );
    }
);


/* ============================================================
   GLOBAL NAVIGATION BUTTONS
   ============================================================ */

document.addEventListener(
    "click",
    event => {

        const target =
            event.target.closest(
                "[data-screen]"
            );


        if (!target) {
            return;
        }


        const screen =
            target.dataset.screen;


        if (!screen) {
            return;
        }


        /*
         * Agar data-screen ishlatilgan bo‘lsa,
         * App.go orqali o'tamiz.
         */

        event.preventDefault();

        App.go(screen);
    }
);


/* ============================================================
   BACK BUTTONS
   ============================================================ */

document.addEventListener(
    "click",
    event => {

        const target =
            event.target.closest(
                "[data-back]"
            );


        if (!target) {
            return;
        }


        event.preventDefault();

        App.back();
    }
);


/* ============================================================
   VISIBILITY
   ============================================================ */

document.addEventListener(
    "visibilitychange",
    () => {

        if (
            document.visibilityState ===
            "visible"
        ) {

            /*
             * Telegram WebApp qayta ochilganda
             * server state yangilanadi.
             */

            App.refreshLive();


            if (
                State.currentScreen ===
                "battle-wait" &&
                State.battle.id
            ) {

                App.checkBattle();
            }
        }
    }
);


/* ============================================================
   ONLINE / OFFLINE
   ============================================================ */

window.addEventListener(
    "online",
    () => {

        console.log(
            "[NETWORK] online"
        );


        const offline =
            document.getElementById(
                "offline-banner"
            );


        if (offline) {

            offline.style.display =
                "none";
        }


        App.refreshLive();
    }
);


window.addEventListener(
    "offline",
    () => {

        console.warn(
            "[NETWORK] offline"
        );


        const offline =
            document.getElementById(
                "offline-banner"
            );


        if (offline) {

            offline.style.display =
                "block";
        }
    }
);


/* ============================================================
   GLOBAL ERROR HANDLER
   ============================================================ */

window.addEventListener(
    "error",
    event => {

        console.error(
            "[GLOBAL ERROR]",
            event.error ||
            event.message
        );
    }
);


window.addEventListener(
    "unhandledrejection",
    event => {

        console.error(
            "[UNHANDLED PROMISE]",
            event.reason
        );
    }
);


/* ============================================================
   TELEGRAM MAIN BUTTON
   ============================================================ */

if (tg?.MainButton) {

    try {

        tg.MainButton.hide();

    } catch (error) {

        console.warn(
            "[Telegram MainButton]",
            error
        );
    }
}


/* ============================================================
   TELEGRAM BACK BUTTON
   ============================================================ */

if (tg?.BackButton) {

    try {

        tg.BackButton.onClick(
            () => {

                App.back();
            }
        );

    } catch (error) {

        console.warn(
            "[Telegram BackButton]",
            error
        );
    }
}


/* ============================================================
   PAGE UNLOAD
   ============================================================ */

window.addEventListener(
    "beforeunload",
    () => {

        if (
            State.test.timerInterval
        ) {

            clearInterval(
                State.test.timerInterval
            );
        }


        if (
            State.battle.pollInterval
        ) {

            clearInterval(
                State.battle.pollInterval
            );
        }


        if (
            State.payment.pollInterval
        ) {

            clearInterval(
                State.payment.pollInterval
            );
        }


        if (
            State.live.interval
        ) {

            clearInterval(
                State.live.interval
            );
        }
    }
);


/* ============================================================
   DEBUG
   ============================================================ */

window.IQTestApp = App;

window.IQTestState = State;

window.IQQuestions = QUESTIONS;


/* ============================================================
   FINAL
   ============================================================ */

console.log(
    "[IQ TEST BOT] app.js loaded successfully"
);