/* ============================================================
   IQ TEST BOT — app.js
   FIXED / STABLE VERSION
   ============================================================ */

"use strict";

// ==================== TELEGRAM ====================

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


// ==================== INIT DATA ====================

let initData = "";

function getInitData() {
    try {
        const value = tg?.initData || "";

        if (value && value.length > 0) {
            initData = value;
        }
    } catch (e) {
        console.warn("[initData] read error:", e);
    }

    return initData;
}

getInitData();


// Telegram WebApp initData ba'zan WebApp ochilgandan keyin keladi.
// Shuning uchun qisqa vaqt davomida qayta tekshiramiz.
let initAttempts = 0;

const initInterval = setInterval(() => {
    initAttempts++;

    const value = getInitData();

    if (value) {
        console.log(
            "[initData] loaded:",
            value.length,
            "belgi"
        );

        clearInterval(initInterval);
        return;
    }

    if (initAttempts >= 50) {
        clearInterval(initInterval);

        console.warn(
            "[initData] 5 sekund ichida topilmadi"
        );
    }
}, 100);


// ==================== HAPTIC ====================

function haptic(type = "light") {
    try {
        tg?.HapticFeedback?.impactOccurred(type);
    } catch (e) {
        // Haptic mavjud bo'lmasa app ishlashda davom etadi.
    }
}


// ==================== API ====================

async function api(
    path,
    body = null,
    method = "POST"
) {
    const httpMethod = String(method || "POST").toUpperCase();

    try {
        const currentInitData =
            getInitData() ||
            tg?.initData ||
            "";

        let options = {
            method: httpMethod,
            headers: {
                "Content-Type": "application/json",
            },
        };

        /*
         * GET / HEAD requestlarda body yubormaymiz.
         *
         * Eski kodda /api/config va /api/stats/live kabi
         * GET endpointlarga ham JSON body yuborilayotgan edi.
         */
        if (
            httpMethod !== "GET" &&
            httpMethod !== "HEAD"
        ) {
            const payload = {
                ...(body || {}),
                initData: currentInitData,
            };

            options.body = JSON.stringify(payload);
        }

        const response = await fetch(
            path,
            options
        );

        let data = null;

        try {
            data = await response.json();
        } catch (e) {
            data = null;
        }

        if (!response.ok) {
            console.error(
                "[API HTTP ERROR]",
                response.status,
                path,
                data
            );

            return {
                ok: false,
                error:
                    data?.error ||
                    `HTTP_${response.status}`,
            };
        }

        return data || {
            ok: true,
        };

    } catch (error) {
        console.error(
            "[API NETWORK ERROR]",
            path,
            error
        );

        return {
            ok: false,
            error: "NETWORK",
        };
    }
}


// ==================== STATE ====================

const State = {

    currentScreen: "home",

    user: null,

    /*
     * completed:
     * {
     *   iq: score,
     *   eq: percent,
     *   pq: percent
     * }
     *
     * Muhim:
     * backend result_visible TRUE qilmaguncha
     * frontend bu qiymatni o'zi TRUE qilmaydi.
     */
    completed: {},

    settings: {},

    test: {
        type: "iq",

        sessionId: null,

        attemptId: null,

        current: 0,

        answers: [],

        startedAt: null,

        duration: 0,

        timerInterval: null,

        resultData: null,
    },

    battle: {
        id: null,

        code: null,

        role: null,

        players: [],

        sessionId: null,

        current: 0,

        answers: [],

        startedAt: null,

        pollInterval: null,
    },

    payment: {
        id: null,

        product: null,

        amount: 0,

        cards: [],

        pollInterval: null,

        attemptId: null,

        battleId: null,
    },

    live: {
        interval: null,
    },

    profile: {
        full_name: "",

        gender: null,

        age: null,

        country: null,
    },
};


// ==================== SAFE HELPERS ====================

function stopPaymentPolling() {
    if (State.payment.pollInterval) {
        clearInterval(
            State.payment.pollInterval
        );

        State.payment.pollInterval = null;
    }
}


function stopBattlePolling() {
    if (State.battle.pollInterval) {
        clearInterval(
            State.battle.pollInterval
        );

        State.battle.pollInterval = null;
    }
}


function stopTestTimer() {
    if (State.test.timerInterval) {
        clearInterval(
            State.test.timerInterval
        );

        State.test.timerInterval = null;
    }
}


function resetTestState(type = "iq") {

    stopTestTimer();

    State.test = {
        type,

        sessionId: null,

        attemptId: null,

        current: 0,

        answers: [],

        startedAt: null,

        duration: 0,

        timerInterval: null,

        resultData: null,
    };
}


function resetPaymentState() {

    stopPaymentPolling();

    State.payment = {
        id: null,

        product: null,

        amount: 0,

        cards: [],

        pollInterval: null,

        attemptId: null,

        battleId: null,
    };
}


// ============================================================
// MUHIM:
// Bu yerda QUESTIONS / EQ_QUESTIONS / PQ_QUESTIONS
// o'zgartirilmaydi.
// ============================================================


// ==================== 18 IQ QUESTIONS ====================
// ============================================================
// APP.JS — 2-QISM
// RENDER HELPERS + APP INIT + PROFILE
// ============================================================

// ==================== SAFE HELPERS ====================

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatNumber(value) {
    const number = Number(value || 0);
    return number.toLocaleString("uz-UZ");
}

function getElement(id) {
    return document.getElementById(id);
}

function showScreen(id) {
    document.querySelectorAll(".screen").forEach(screen => {
        screen.classList.remove("active");
    });

    const screen = getElement(id);

    if (screen) {
        screen.classList.add("active");
    }

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}

function setText(id, value) {
    const element = getElement(id);

    if (element) {
        element.textContent = value ?? "";
    }
}

function setHTML(id, html) {
    const element = getElement(id);

    if (element) {
        element.innerHTML = html;
    }
}

function setDisplay(id, display) {
    const element = getElement(id);

    if (element) {
        element.style.display = display;
    }
}

function getPrice(product) {
    const settings = State.settings || {};

    const prices = {
        iq: Number(settings.iq_price || 0),
        iq_retry: Number(settings.iq_retry_price || 0),

        eq: Number(settings.eq_price || 0),
        eq_retry: Number(settings.eq_retry_price || 0),

        pq: Number(settings.pq_price || 0),
        pq_retry: Number(settings.pq_retry_price || 0),

        battle: Number(settings.battle_price || 0)
    };

    return prices[product] ?? 0;
}

function getProductName(product) {
    const names = {
        iq: "IQ testi",
        iq_retry: "IQ testini qayta topshirish",
        eq: "EQ testi",
        eq_retry: "EQ testini qayta topshirish",
        pq: "PQ testi",
        pq_retry: "PQ testini qayta topshirish",
        battle: "Do‘st bilan Battle"
    };

    return names[product] || product;
}


// ==================== RENDER CELL ====================

function renderCell(cell) {
    if (!cell) {
        return "";
    }

    const type = cell.type || "text";
    const value = cell.value ?? "";

    // ---------- DOT ----------
    if (type === "dot") {
        const count = Number(value || 0);

        let dots = "";

        for (let i = 0; i < count; i++) {
            dots += '<span class="matrix-dot"></span>';
        }

        return `
            <div class="matrix-cell matrix-dot-cell">
                ${dots}
            </div>
        `;
    }

    // ---------- NUMBER ----------
    if (type === "num") {
        return `
            <div class="matrix-cell matrix-number">
                ${escapeHtml(value)}
            </div>
        `;
    }

    // ---------- SHAPE ----------
    if (type === "shape") {
        return `
            <div class="matrix-cell matrix-shape-cell">
                <div class="shape shape-${escapeHtml(value)}"></div>
            </div>
        `;
    }

    // ---------- ROTATE ----------
    if (type === "rotate") {
        return `
            <div class="matrix-cell matrix-rotate-cell">
                <div
                    class="rotate-shape"
                    style="transform: rotate(${Number(value) || 0}deg);"
                ></div>
            </div>
        `;
    }

    // ---------- SIZE ----------
    if (type === "size") {
        const size = Number(value || 20);

        return `
            <div class="matrix-cell matrix-size-cell">
                <div
                    class="size-shape"
                    style="
                        width:${size}px;
                        height:${size}px;
                    "
                ></div>
            </div>
        `;
    }

    // ---------- GRID ----------
    if (type === "grid") {
        const position = Number(value || 0);

        return `
            <div class="matrix-cell matrix-grid-cell">
                <div class="grid-3x3">
                    ${Array.from({ length: 9 }, (_, index) => `
                        <span
                            class="${index === position ? "active" : ""}"
                        ></span>
                    `).join("")}
                </div>
            </div>
        `;
    }

    // ---------- COMBO ----------
    if (type === "combo") {
        const shapes = Array.isArray(value)
            ? value
            : String(value)
                .split(",")
                .map(item => item.trim())
                .filter(Boolean);

        return `
            <div class="matrix-cell matrix-combo-cell">
                ${shapes.map(shape => `
                    <span class="combo-shape combo-${escapeHtml(shape)}"></span>
                `).join("")}
            </div>
        `;
    }

    // ---------- TEXT ----------
    return `
        <div class="matrix-cell matrix-text-cell">
            ${escapeHtml(value)}
        </div>
    `;
}


// ==================== RENDER MATRIX ====================

function renderMatrix(matrix) {
    if (!Array.isArray(matrix)) {
        return "";
    }

    return `
        <div class="matrix-wrapper">
            <div class="question-matrix">
                ${matrix.map(row => `
                    <div class="matrix-row">
                        ${
                            Array.isArray(row)
                                ? row.map(cell => renderCell(cell)).join("")
                                : ""
                        }
                    </div>
                `).join("")}
            </div>
        </div>
    `;
}


// ==================== RENDER IQ OPTIONS ====================

function renderOptions(question) {
    if (!question || !Array.isArray(question.options)) {
        return "";
    }

    return `
        <div class="answer-options">
            ${question.options.map((option, index) => `
                <button
                    type="button"
                    class="answer-option"
                    data-answer="${index}"
                >
                    <span class="answer-letter">
                        ${String.fromCharCode(65 + index)}
                    </span>

                    <span class="answer-content">
                        ${renderCell(option)}
                    </span>
                </button>
            `).join("")}
        </div>
    `;
}


// ==================== RENDER TEXT OPTIONS ====================

function renderTextOptions(question) {
    if (!question || !Array.isArray(question.options)) {
        return "";
    }

    return `
        <div class="answer-options text-answer-options">
            ${question.options.map((option, index) => `
                <button
                    type="button"
                    class="answer-option text-option"
                    data-answer="${index}"
                >
                    <span class="answer-letter">
                        ${String.fromCharCode(65 + index)}
                    </span>

                    <span class="answer-content">
                        ${escapeHtml(option)}
                    </span>
                </button>
            `).join("")}
        </div>
    `;
}


// ==================== QUESTION PROGRESS ====================

function updateQuestionProgress() {
    const type = State.test.type || "iq";

    let total = 0;

    if (type === "iq") {
        total = QUESTIONS.length;
    } else if (type === "eq") {
        total = EQ_QUESTIONS.length;
    } else if (type === "pq") {
        total = PQ_QUESTIONS.length;
    }

    const current = Number(State.test.current || 0);

    const number = current + 1;

    setText("question-number", `${number}/${total}`);
    setText("question-count", `${number} / ${total}`);

    const progress = total > 0
        ? Math.round((current / total) * 100)
        : 0;

    const progressBar = getElement("test-progress");

    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }

    const progressFill = getElement("progress-fill");

    if (progressFill) {
        progressFill.style.width = `${progress}%`;
    }
}


// ==================== RENDER IQ QUESTION ====================

function renderIQQuestion() {
    const question = QUESTIONS[State.test.current];

    if (!question) {
        finish();
        return;
    }

    updateQuestionProgress();

    setText(
        "question-title",
        question.title || `Savol ${State.test.current + 1}`
    );

    setHTML(
        "question-content",
        renderMatrix(question.matrix)
    );

    setHTML(
        "question-options",
        renderOptions(question)
    );

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.addEventListener("click", () => {
                const answer = Number(button.dataset.answer);

                selectIQAnswer(answer);
            });
        });

    showScreen("screen-test");
}


// ==================== SELECT IQ ANSWER ====================

function selectIQAnswer(answer) {
    const question = QUESTIONS[State.test.current];

    if (!question) {
        return;
    }

    State.test.answers[State.test.current] = answer;

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.classList.remove("selected");

            if (Number(button.dataset.answer) === answer) {
                button.classList.add("selected");
            }
        });

    setTimeout(() => {
        if (State.test.current >= QUESTIONS.length - 1) {
            finish();
        } else {
            State.test.current += 1;
            renderIQQuestion();
        }
    }, 220);
}


// ==================== RENDER EQ QUESTION ====================

function renderEQQuestion() {
    const question = EQ_QUESTIONS[State.test.current];

    if (!question) {
        finishEQ();
        return;
    }

    updateQuestionProgress();

    setText(
        "question-title",
        question.title || `Savol ${State.test.current + 1}`
    );

    setHTML(
        "question-content",
        `
            <div class="text-question">
                <div class="text-question-title">
                    ${escapeHtml(question.question || "")}
                </div>
            </div>
        `
    );

    setHTML(
        "question-options",
        renderTextOptions(question)
    );

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.addEventListener("click", () => {
                const answer = Number(button.dataset.answer);

                selectEQAnswer(answer);
            });
        });

    showScreen("screen-test");
}


// ==================== SELECT EQ ANSWER ====================

function selectEQAnswer(answer) {
    State.test.answers[State.test.current] = answer;

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.classList.remove("selected");

            if (Number(button.dataset.answer) === answer) {
                button.classList.add("selected");
            }
        });

    setTimeout(() => {
        if (State.test.current >= EQ_QUESTIONS.length - 1) {
            finishEQ();
        } else {
            State.test.current += 1;
            renderEQQuestion();
        }
    }, 220);
}


// ==================== RENDER PQ QUESTION ====================

function renderPQQuestion() {
    const question = PQ_QUESTIONS[State.test.current];

    if (!question) {
        finishPQ();
        return;
    }

    updateQuestionProgress();

    setText(
        "question-title",
        question.title || `Savol ${State.test.current + 1}`
    );

    setHTML(
        "question-content",
        `
            <div class="text-question">
                <div class="text-question-title">
                    ${escapeHtml(question.question || "")}
                </div>
            </div>
        `
    );

    setHTML(
        "question-options",
        renderTextOptions(question)
    );

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.addEventListener("click", () => {
                const answer = Number(button.dataset.answer);

                selectPQAnswer(answer);
            });
        });

    showScreen("screen-test");
}


// ==================== SELECT PQ ANSWER ====================

function selectPQAnswer(answer) {
    State.test.answers[State.test.current] = answer;

    document
        .querySelectorAll("#question-options .answer-option")
        .forEach(button => {
            button.classList.remove("selected");

            if (Number(button.dataset.answer) === answer) {
                button.classList.add("selected");
            }
        });

    setTimeout(() => {
        if (State.test.current >= PQ_QUESTIONS.length - 1) {
            finishPQ();
        } else {
            State.test.current += 1;
            renderPQQuestion();
        }
    }, 220);
}


// ============================================================
// APP
// ============================================================

const App = {

    async init() {
        try {
            if (tg) {
                try {
                    tg.ready();
                    tg.expand();
                } catch (error) {
                    console.warn("[APP] Telegram init warning:", error);
                }
            }

            // --------------------------------------------
            // CONFIG
            // --------------------------------------------

            try {
                const config = await api(
                    "/api/config",
                    null,
                    "GET"
                );

                if (config?.ok) {
                    State.settings = {
                        ...State.settings,
                        ...(config.settings || config.config || {})
                    };
                }
            } catch (error) {
                console.warn("[APP] Config error:", error);
            }

            // --------------------------------------------
            // LIVE STATS
            // --------------------------------------------

            try {
                const stats = await api(
                    "/api/stats/live",
                    null,
                    "GET"
                );

                if (stats?.ok) {
                    State.live = {
                        ...State.live,
                        ...(stats.stats || stats.data || {})
                    };

                    updateLiveCounter();
                }
            } catch (error) {
                console.warn("[APP] Live stats error:", error);
            }

            // --------------------------------------------
            // USER
            // --------------------------------------------

            if (State.initData) {
                try {
                    const me = await api(
                        "/api/me",
                        null,
                        "GET"
                    );

                    if (me?.ok) {
                        State.user = me.user || null;

                        State.completed = {
                            ...State.completed,
                            ...(me.completed || {})
                        };

                        State.profile = me.profile || null;

                        if (me.battle) {
                            State.battle = {
                                ...State.battle,
                                ...me.battle
                            };
                        }
                    }
                } catch (error) {
                    console.warn("[APP] /api/me error:", error);
                }
            }

            applyUnlocks();

            updateProfileHeader();

            bindGlobalEvents();

            hideLoadingScreen();

        } catch (error) {
            console.error("[APP] Initialization failed:", error);

            hideLoadingScreen();

            showToast(
                "Ilovani yuklashda xatolik yuz berdi",
                "error"
            );
        }
    }
};


// ==================== LOADING ====================

function hideLoadingScreen() {
    const loading = getElement("loading-screen");

    if (!loading) {
        return;
    }

    setTimeout(() => {
        loading.classList.add("hidden");
    }, 250);
}


// ==================== LIVE COUNTER ====================

function updateLiveCounter() {
    const live = State.live || {};

    const value =
        live.current ??
        live.live ??
        live.online ??
        live.count ??
        0;

    setText(
        "live-counter",
        formatNumber(value)
    );

    setText(
        "live-count",
        formatNumber(value)
    );
}


// ==================== PROFILE HEADER ====================

function updateProfileHeader() {
    const user = State.user;

    if (!user) {
        return;
    }

    const name =
        user.first_name ||
        user.firstName ||
        user.username ||
        "Foydalanuvchi";

    setText(
        "profile-name",
        name
    );

    if (user.username) {
        setText(
            "profile-username",
            `@${String(user.username).replace(/^@/, "")}`
        );
    }
}


// ==================== UNLOCK SYSTEM ====================

function applyUnlocks() {
    const completed = State.completed || {};

    const iqDone = completed.iq !== null &&
                   completed.iq !== undefined;

    const eqDone = completed.eq !== null &&
                   completed.eq !== undefined;

    const pqDone = completed.pq !== null &&
                   completed.pq !== undefined;

    const eqLocked = getElement("eq-lock");
    const pqLocked = getElement("pq-lock");
    const profileLocked = getElement("profile-lock");

    const eqCard = getElement("eq-card");
    const pqCard = getElement("pq-card");
    const profileCard = getElement("profile-card");

    // --------------------------------------------
    // EQ
    // --------------------------------------------

    if (eqCard) {
        eqCard.classList.toggle("locked", !iqDone);
    }

    if (eqLocked) {
        eqLocked.style.display = iqDone ? "none" : "";
    }

    // --------------------------------------------
    // PQ
    // --------------------------------------------

    if (pqCard) {
        pqCard.classList.toggle("locked", !eqDone);
    }

    if (pqLocked) {
        pqLocked.style.display = eqDone ? "none" : "";
    }

    // --------------------------------------------
    // PROFILE
    // --------------------------------------------

    const allDone = iqDone && eqDone && pqDone;

    if (profileCard) {
        profileCard.classList.toggle("locked", !allDone);
    }

    if (profileLocked) {
        profileLocked.style.display = allDone ? "none" : "";
    }

    // --------------------------------------------
    // HOME BUTTONS
    // --------------------------------------------

    const iqButton = getElement("start-iq-btn");
    const eqButton = getElement("start-eq-btn");
    const pqButton = getElement("start-pq-btn");

    if (eqButton) {
        eqButton.disabled = !iqDone;
    }

    if (pqButton) {
        pqButton.disabled = !eqDone;
    }

    // IQ is always available.
    if (iqButton) {
        iqButton.disabled = false;
    }
}


// ==================== GLOBAL EVENTS ====================

function bindGlobalEvents() {

    // --------------------------------------------
    // HOME / BACK
    // --------------------------------------------

    document.querySelectorAll("[data-screen]").forEach(element => {
        if (element.dataset.bound === "1") {
            return;
        }

        element.dataset.bound = "1";

        element.addEventListener("click", () => {
            const target = element.dataset.screen;

            if (target) {
                showScreen(target);
            }
        });
    });

    // --------------------------------------------
    // IQ
    // --------------------------------------------

    const iqButton = getElement("start-iq-btn");

    if (iqButton && iqButton.dataset.bound !== "1") {
        iqButton.dataset.bound = "1";

        iqButton.addEventListener("click", () => {
            startIQ();
        });
    }

    // --------------------------------------------
    // EQ
    // --------------------------------------------

    const eqButton = getElement("start-eq-btn");

    if (eqButton && eqButton.dataset.bound !== "1") {
        eqButton.dataset.bound = "1";

        eqButton.addEventListener("click", () => {
            startEQ();
        });
    }

    // --------------------------------------------
    // PQ
    // --------------------------------------------

    const pqButton = getElement("start-pq-btn");

    if (pqButton && pqButton.dataset.bound !== "1") {
        pqButton.dataset.bound = "1";

        pqButton.addEventListener("click", () => {
            startPQ();
        });
    }

    // --------------------------------------------
    // PROFILE
    // --------------------------------------------

    const profileButton = getElement("profile-card");

    if (profileButton && profileButton.dataset.bound !== "1") {
        profileButton.dataset.bound = "1";

        profileButton.addEventListener("click", () => {
            if (
                State.completed.iq !== null &&
                State.completed.iq !== undefined &&
                State.completed.eq !== null &&
                State.completed.eq !== undefined &&
                State.completed.pq !== null &&
                State.completed.pq !== undefined
            ) {
                openProfile();
            } else {
                showToast(
                    "Avval barcha testlarni yakunlang",
                    "warning"
                );
            }
        });
    }
}


// ============================================================
// START IQ
// ============================================================

async function startIQ() {

    stopTestTimer();

    resetTestState();

    State.test.type = "iq";
    State.test.current = 0;
    State.test.answers = [];

    const intro = getElement("screen-iq-intro");

    if (intro) {
        showScreen("screen-iq-intro");
    } else {
        await startIQTest();
    }
}


// ============================================================
// SAVE PROFILE
// ============================================================

async function saveProfile() {

    const fullNameInput = getElement("profile-full-name");
    const genderInput = getElement("profile-gender");
    const ageInput = getElement("profile-age");
    const countryInput = getElement("profile-country");

    const fullName = fullNameInput?.value?.trim() || "";
    const gender = genderInput?.value || "";
    const age = Number(ageInput?.value || 0);
    const country = countryInput?.value?.trim() || "";

    if (fullName.length < 3) {
        showToast(
            "Ism va familiyani to‘liq kiriting",
            "warning"
        );
        return;
    }

    if (!gender) {
        showToast(
            "Jinsni tanlang",
            "warning"
        );
        return;
    }

    if (!Number.isFinite(age) || age < 8 || age > 100) {
        showToast(
            "Yoshni to‘g‘ri kiriting",
            "warning"
        );
        return;
    }

    if (!country) {
        showToast(
            "Davlatni kiriting",
            "warning"
        );
        return;
    }

    try {
        const response = await api(
            "/api/profile/save",
            {
                full_name: fullName,
                gender,
                age,
                country
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Profilni saqlab bo‘lmadi"
            );
        }

        State.profile = response.profile || {
            full_name: fullName,
            gender,
            age,
            country
        };

        await startIQTest();

    } catch (error) {
        console.error("[PROFILE]", error);

        showToast(
            error.message || "Profilni saqlashda xatolik",
            "error"
        );
    }
}


// ============================================================
// START IQ TEST
// ============================================================

async function startIQTest() {

    stopTestTimer();

    resetTestState();

    State.test.type = "iq";
    State.test.current = 0;
    State.test.answers = [];

    try {

        if (!State.initData) {
            renderIQSample();
            return;
        }

        const response = await api(
            "/api/session/start",
            {
                test_type: "iq"
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Test sessiyasini boshlab bo‘lmadi"
            );
        }

        State.test.sessionId =
            response.session_id ||
            response.sessionId ||
            null;

        State.test.attemptId =
            response.attempt_id ||
            response.attemptId ||
            null;

        State.test.startedAt = Date.now();

        renderIQSample();

    } catch (error) {
        console.error("[IQ START]", error);

        showToast(
            error.message ||
            "Testni boshlashda xatolik",
            "error"
        );
    }
}


// ============================================================
// IQ SAMPLE SCREEN
// ============================================================

function renderIQSample() {

    const startButton =
        getElement("start-real-iq-btn");

    if (startButton) {

        if (startButton.dataset.bound !== "1") {

            startButton.dataset.bound = "1";

            startButton.addEventListener("click", () => {
                beginIQQuestions();
            });
        }
    }

    showScreen("screen-iq-sample");
}


// ============================================================
// BEGIN IQ QUESTIONS
// ============================================================

function beginIQQuestions() {

    State.test.current = 0;
    State.test.answers = [];

    renderIQQuestion();

    startTestTimer();
}


// ============================================================
// TEST TIMER
// ============================================================

function startTestTimer() {

    stopTestTimer();

    const duration =
        Number(State.settings?.iq_time_limit || 0);

    if (!duration || duration <= 0) {
        return;
    }

    State.test.timeLeft = duration;

    updateTimerDisplay();

    State.test.timer = setInterval(() => {

        State.test.timeLeft -= 1;

        updateTimerDisplay();

        if (State.test.timeLeft <= 0) {
            stopTestTimer();

            finish();

        }

    }, 1000);
}


function updateTimerDisplay() {

    const seconds =
        Math.max(0, Number(State.test.timeLeft || 0));

    const minutes =
        Math.floor(seconds / 60);

    const remainingSeconds =
        seconds % 60;

    const formatted =
        `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;

    setText("test-timer", formatted);
    setText("timer", formatted);
}


// ============================================================
// TOAST
// ============================================================

function showToast(message, type = "info") {

    const existing =
        getElement("app-toast");

    if (existing) {
        existing.remove();
    }

    const toast =
        document.createElement("div");

    toast.id = "app-toast";

    toast.className =
        `app-toast app-toast-${type}`;

    toast.textContent =
        String(message || "");

    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add("show");
    });

    setTimeout(() => {

        toast.classList.remove("show");

        setTimeout(() => {
            toast.remove();
        }, 250);

    }, 2800);
}


// ============================================================
// 2-QISM TUGADI
// ============================================================
// ============================================================
// APP.JS — 3-QISM
// IQ FINISH + RESULT + PAYMENT REQUIRED
// ============================================================


// ============================================================
// FINISH IQ TEST
// ============================================================

async function finish() {

    if (State.test.finished) {
        return;
    }

    State.test.finished = true;

    stopTestTimer();

    // --------------------------------------------
    // LOADING
    // --------------------------------------------

    showScreen("screen-result-loading");

    await sleep(3500);

    // --------------------------------------------
    // OFFLINE / BROWSER FALLBACK
    // --------------------------------------------

    if (!State.initData || !State.test.sessionId) {

        const localResult =
            calculateIQResult(State.test.answers);

        State.test.resultData = {
            test_type: "iq",
            score: localResult.score,
            correct: localResult.correct,
            total: QUESTIONS.length,
            level: localResult.level,
            result_visible: true,
            payment_required: false,
            payment_product: null,
            attempt_id: null
        };

        State.completed.iq =
            localResult.score;

        applyUnlocks();

        renderIQResult(
            State.test.resultData
        );

        return;
    }

    // --------------------------------------------
    // BACKEND SUBMIT
    // --------------------------------------------

    try {

        const response = await api(
            "/api/test/submit",
            {
                session_id: State.test.sessionId,
                test_type: "iq",
                answers: State.test.answers
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Natijani yuborib bo‘lmadi"
            );
        }

        const result = {
            ...response,

            test_type: "iq",

            attempt_id:
                response.attempt_id ||
                response.attemptId ||
                State.test.attemptId ||
                null
        };

        State.test.attemptId =
            result.attempt_id;

        State.test.resultData =
            result;

        // ----------------------------------------
        // PAYMENT REQUIRED
        // ----------------------------------------

        if (
            result.payment_required === true ||
            result.result_visible === false
        ) {

            /*
             * MUHIM:
             *
             * Bu yerda IQ completed qilinmaydi.
             *
             * Foydalanuvchi hali pul to‘lamagan.
             * Shuning uchun EQ ochilmasligi kerak.
             */

            showIQPaymentRequired(result);

            return;
        }

        // ----------------------------------------
        // FREE / ALREADY PAID
        // ----------------------------------------

        completeTestFromResult(
            "iq",
            result
        );

        renderIQResult(result);

    } catch (error) {

        console.error(
            "[IQ FINISH]",
            error
        );

        State.test.finished = false;

        showToast(
            error.message ||
            "Natijani hisoblashda xatolik",
            "error"
        );

        showScreen("screen-test");
    }
}


// ============================================================
// SLEEP
// ============================================================

function sleep(ms) {
    return new Promise(resolve => {
        setTimeout(resolve, ms);
    });
}


// ============================================================
// LOCAL IQ CALCULATION
// ============================================================

function calculateIQResult(answers) {

    let correct = 0;
    let weightedScore = 0;
    let maxWeightedScore = 0;

    QUESTIONS.forEach((question, index) => {

        const weight =
            Number(question.weight || 1);

        maxWeightedScore += weight;

        const answer =
            answers?.[index];

        if (
            answer !== undefined &&
            answer !== null &&
            Number(answer) === Number(question.correct)
        ) {
            correct += 1;
            weightedScore += weight;
        }
    });

    const score =
        maxWeightedScore > 0
            ? Math.round(
                (weightedScore / maxWeightedScore) * 100
            )
            : 0;

    let level = "O‘rtacha";

    if (score >= 90) {
        level = "Juda yuqori";
    } else if (score >= 75) {
        level = "Yuqori";
    } else if (score >= 60) {
        level = "O‘rtacha yuqori";
    } else if (score >= 40) {
        level = "O‘rtacha";
    } else if (score >= 25) {
        level = "Past";
    } else {
        level = "Juda past";
    }

    return {
        score,
        correct,
        level
    };
}


// ============================================================
// COMPLETE TEST FROM BACKEND RESULT
// ============================================================

function completeTestFromResult(
    type,
    result
) {

    const score =
        Number(
            result?.score ??
            result?.percentage ??
            result?.percent ??
            0
        );

    State.completed[type] = score;

    State.test.resultData = {
        ...State.test.resultData,
        ...result,
        score,
        result_visible: true,
        payment_required: false
    };

    applyUnlocks();
}


// ============================================================
// IQ PAYMENT REQUIRED
// ============================================================

function showIQPaymentRequired(result) {

    const product =
        result.payment_product ||
        (
            State.completed.iq !== null &&
            State.completed.iq !== undefined
                ? "iq_retry"
                : "iq"
        );

    const price =
        Number(
            result.price ??
            getPrice(product)
        );

    State.payment = {
        ...State.payment,
        product,
        attemptId:
            result.attempt_id ||
            State.test.attemptId ||
            null,
        price,
        paymentId: null
    };

    // --------------------------------------------
    // PRICE
    // --------------------------------------------

    setText(
        "payment-required-price",
        `${formatNumber(price)} so‘m`
    );

    setText(
        "iq-payment-price",
        `${formatNumber(price)} so‘m`
    );

    // --------------------------------------------
    // DESCRIPTION
    // --------------------------------------------

    const description =
        getElement("payment-required-description");

    if (description) {

        description.textContent =
            product === "iq_retry"
                ? "IQ testini qayta topshirish uchun to‘lov talab qilinadi."
                : "IQ test natijasini ko‘rish uchun to‘lov talab qilinadi.";
    }

    // --------------------------------------------
    // BUTTON
    // --------------------------------------------

    const button =
        getElement("start-iq-payment-btn");

    if (button) {

        button.disabled = false;

        if (button.dataset.bound !== "1") {

            button.dataset.bound = "1";

            button.addEventListener(
                "click",
                startIQPayment
            );
        }
    }

    showScreen(
        "screen-payment-required"
    );
}


// ============================================================
// RENDER IQ RESULT
// ============================================================

function renderIQResult(result) {

    const score =
        Number(
            result?.score ??
            result?.percentage ??
            0
        );

    const correct =
        Number(
            result?.correct ??
            result?.correct_answers ??
            0
        );

    const total =
        Number(
            result?.total ??
            result?.total_questions ??
            QUESTIONS.length
        );

    const level =
        result?.level ||
        getIQLevel(score);

    // --------------------------------------------
    // SCORE
    // --------------------------------------------

    setText(
        "iq-result-score",
        String(score)
    );

    setText(
        "result-score",
        String(score)
    );

    setText(
        "iq-score-value",
        String(score)
    );

    // --------------------------------------------
    // CORRECT
    // --------------------------------------------

    setText(
        "iq-result-correct",
        `${correct}/${total}`
    );

    setText(
        "result-correct",
        `${correct}/${total}`
    );

    // --------------------------------------------
    // LEVEL
    // --------------------------------------------

    setText(
        "iq-result-level",
        level
    );

    setText(
        "result-level",
        level
    );

    // --------------------------------------------
    // CIRCLE / PROGRESS
    // --------------------------------------------

    const circles =
        document.querySelectorAll(
            ".result-progress-circle"
        );

    circles.forEach(circle => {

        const radius =
            Number(circle.getAttribute("r") || 0);

        if (!radius) {
            return;
        }

        const circumference =
            2 * Math.PI * radius;

        circle.style.strokeDasharray =
            `${circumference}`;

        circle.style.strokeDashoffset =
            `${circumference * (1 - score / 100)}`;
    });

    // --------------------------------------------
    // DATA ATTRIBUTE
    // --------------------------------------------

    const resultScreen =
        getElement("screen-result");

    if (resultScreen) {
        resultScreen.dataset.score =
            String(score);
    }

    showScreen("screen-result");
}


// ============================================================
// IQ LEVEL
// ============================================================

function getIQLevel(score) {

    score = Number(score || 0);

    if (score >= 90) {
        return "Juda yuqori";
    }

    if (score >= 75) {
        return "Yuqori";
    }

    if (score >= 60) {
        return "O‘rtacha yuqori";
    }

    if (score >= 40) {
        return "O‘rtacha";
    }

    if (score >= 25) {
        return "Past";
    }

    return "Juda past";
}


// ============================================================
// IQ RETRY
// ============================================================

async function retry() {

    const retryPrice =
        getPrice("iq_retry");

    if (retryPrice > 0) {

        const confirmed =
            window.confirm(
                `IQ testini qayta topshirish narxi ${formatNumber(retryPrice)} so‘m.\n\nDavom etasizmi?`
            );

        if (!confirmed) {
            return;
        }
    }

    stopTestTimer();

    resetTestState();

    State.test.type = "iq";
    State.test.current = 0;
    State.test.answers = [];

    await startIQ();
}


// ============================================================
// RESET RESULT VIEW
// ============================================================

function closeResult() {

    stopTestTimer();

    showScreen("screen-home");
}


// ============================================================
// RESULT -> NEXT TEST
// ============================================================

function goToEQFromResult() {

    if (
        State.completed.iq === null ||
        State.completed.iq === undefined
    ) {
        showToast(
            "Avval IQ testini yakunlang",
            "warning"
        );

        return;
    }

    startEQ();
}


function goToPQFromResult() {

    if (
        State.completed.eq === null ||
        State.completed.eq === undefined
    ) {
        showToast(
            "Avval EQ testini yakunlang",
            "warning"
        );

        return;
    }

    startPQ();
}


// ============================================================
// PAYMENT BUTTON BINDING
// ============================================================

function bindPaymentButtons() {

    const iqPaymentButton =
        getElement("start-iq-payment-btn");

    if (
        iqPaymentButton &&
        iqPaymentButton.dataset.bound !== "1"
    ) {

        iqPaymentButton.dataset.bound = "1";

        iqPaymentButton.addEventListener(
            "click",
            startIQPayment
        );
    }

    const paymentCancelButton =
        getElement("payment-cancel-btn");

    if (
        paymentCancelButton &&
        paymentCancelButton.dataset.bound !== "1"
    ) {

        paymentCancelButton.dataset.bound = "1";

        paymentCancelButton.addEventListener(
            "click",
            () => {
                showScreen("screen-home");
            }
        );
    }

    const resultCloseButton =
        getElement("result-home-btn");

    if (
        resultCloseButton &&
        resultCloseButton.dataset.bound !== "1"
    ) {

        resultCloseButton.dataset.bound = "1";

        resultCloseButton.addEventListener(
            "click",
            closeResult
        );
    }

    const retryButton =
        getElement("retry-iq-btn");

    if (
        retryButton &&
        retryButton.dataset.bound !== "1"
    ) {

        retryButton.dataset.bound = "1";

        retryButton.addEventListener(
            "click",
            retry
        );
    }
}


// ============================================================
// OVERRIDE APP INIT BINDINGS
// ============================================================

const originalAppInit =
    App.init;

App.init = async function () {

    await originalAppInit();

    bindPaymentButtons();

    // Re-apply unlock state after all UI is loaded.
    applyUnlocks();

    updateLiveCounter();
};


// ============================================================
// AUTO START
// ============================================================

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        () => {
            App.init();
        },
        {
            once: true
        }
    );

} else {

    App.init();
}


// ============================================================
// 3-QISM TUGADI
// ============================================================
// ============================================================
// APP.JS — 4-QISM
// EQ + PQ TESTLARI
// ============================================================


// ============================================================
// START EQ
// ============================================================

async function startEQ() {

    // IQ tugamagan bo‘lsa — EQ ochilmaydi
    if (
        State.completed.iq === null ||
        State.completed.iq === undefined
    ) {
        showToast(
            "Avval IQ testini yakunlang",
            "warning"
        );
        return;
    }

    stopTestTimer();

    resetTestState();

    State.test.type = "eq";
    State.test.current = 0;
    State.test.answers = [];

    // Qayta topshirish bo‘lsa, faqat ogohlantiramiz.
    // To‘lovning o‘zi test tugagandan keyin backend tomonidan
    // aniqlanadi.
    if (
        State.completed.eq !== null &&
        State.completed.eq !== undefined
    ) {

        const price =
            getPrice("eq_retry");

        if (price > 0) {

            const confirmed =
                window.confirm(
                    `EQ testini qayta topshirish narxi ${formatNumber(price)} so‘m.\n\nDavom etasizmi?`
                );

            if (!confirmed) {
                return;
            }
        }
    }

    // Telegram bo‘lmagan holatda ham test ishlasin
    if (!State.initData) {
        renderEQQuestion();
        return;
    }

    try {

        const response = await api(
            "/api/session/start",
            {
                test_type: "eq"
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "EQ test sessiyasini boshlashda xatolik"
            );
        }

        State.test.sessionId =
            response.session_id ||
            response.sessionId ||
            null;

        State.test.attemptId =
            response.attempt_id ||
            response.attemptId ||
            null;

        State.test.startedAt =
            Date.now();

        renderEQQuestion();

    } catch (error) {

        console.error(
            "[EQ START]",
            error
        );

        showToast(
            error.message ||
            "EQ testini boshlashda xatolik",
            "error"
        );
    }
}


// ============================================================
// FINISH EQ
// ============================================================

async function finishEQ() {

    if (State.test.finished) {
        return;
    }

    State.test.finished = true;

    stopTestTimer();

    showScreen("screen-result-loading");

    await sleep(1800);

    // --------------------------------------------
    // OFFLINE FALLBACK
    // --------------------------------------------

    if (!State.initData || !State.test.sessionId) {

        const local =
            calculateEQResult(
                State.test.answers
            );

        State.test.resultData = {
            test_type: "eq",
            score: local.score,
            correct: local.correct,
            total: EQ_QUESTIONS.length,
            level: local.level,
            result_visible: true,
            payment_required: false,
            payment_product: null,
            attempt_id: null
        };

        State.completed.eq =
            local.score;

        applyUnlocks();

        renderEQResult(
            State.test.resultData
        );

        return;
    }

    // --------------------------------------------
    // BACKEND
    // --------------------------------------------

    try {

        const response = await api(
            "/api/test/submit",
            {
                session_id: State.test.sessionId,
                test_type: "eq",
                answers: State.test.answers
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "EQ natijasini yuborib bo‘lmadi"
            );
        }

        const result = {
            ...response,

            test_type: "eq",

            attempt_id:
                response.attempt_id ||
                response.attemptId ||
                State.test.attemptId ||
                null
        };

        State.test.attemptId =
            result.attempt_id;

        State.test.resultData =
            result;

        // ----------------------------------------
        // PAYMENT REQUIRED
        // ----------------------------------------

        if (
            result.payment_required === true ||
            result.result_visible === false
        ) {

            showTestPaymentRequired(
                "eq",
                result
            );

            return;
        }

        // ----------------------------------------
        // FREE / PAID
        // ----------------------------------------

        completeTestFromResult(
            "eq",
            result
        );

        renderEQResult(result);

    } catch (error) {

        console.error(
            "[EQ FINISH]",
            error
        );

        State.test.finished = false;

        showToast(
            error.message ||
            "EQ natijasini hisoblashda xatolik",
            "error"
        );

        showScreen("screen-test");
    }
}


// ============================================================
// CALCULATE EQ
// ============================================================

function calculateEQResult(answers) {

    let points = 0;
    let maxPoints = 0;
    let correct = 0;

    EQ_QUESTIONS.forEach(
        (question, index) => {

            const answer =
                answers?.[index];

            const scores =
                Array.isArray(question.scores)
                    ? question.scores
                    : [];

            const max =
                Math.max(
                    ...scores,
                    0
                );

            maxPoints += max;

            if (
                answer !== undefined &&
                answer !== null &&
                scores[answer] !== undefined
            ) {

                points +=
                    Number(scores[answer]);

                if (
                    Number(scores[answer]) === max
                ) {
                    correct++;
                }
            }
        }
    );

    const score =
        maxPoints > 0
            ? Math.round(
                (points / maxPoints) * 100
            )
            : 0;

    return {
        score,
        correct,
        level: getEQLevel(score)
    };
}


// ============================================================
// EQ LEVEL
// ============================================================

function getEQLevel(score) {

    score = Number(score || 0);

    if (score >= 85) {
        return "Juda yuqori";
    }

    if (score >= 70) {
        return "Yuqori";
    }

    if (score >= 50) {
        return "O‘rtacha";
    }

    if (score >= 30) {
        return "Past";
    }

    return "Juda past";
}


// ============================================================
// RENDER EQ RESULT
// ============================================================

function renderEQResult(result) {

    const score =
        Number(
            result?.score ??
            result?.percentage ??
            0
        );

    const correct =
        Number(
            result?.correct ??
            result?.correct_answers ??
            0
        );

    const total =
        Number(
            result?.total ??
            result?.total_questions ??
            EQ_QUESTIONS.length
        );

    const level =
        result?.level ||
        getEQLevel(score);

    setText(
        "eq-result-score",
        String(score)
    );

    setText(
        "eq-score-value",
        String(score)
    );

    setText(
        "eq-result-correct",
        `${correct}/${total}`
    );

    setText(
        "eq-result-level",
        level
    );

    setText(
        "result-score",
        String(score)
    );

    setText(
        "result-level",
        level
    );

    const resultScreen =
        getElement("screen-eq-result");

    if (resultScreen) {
        resultScreen.dataset.score =
            String(score);
    }

    showScreen("screen-eq-result");
}


// ============================================================
// START PQ
// ============================================================

async function startPQ() {

    // EQ tugamagan bo‘lsa PQ ochilmaydi
    if (
        State.completed.eq === null ||
        State.completed.eq === undefined
    ) {
        showToast(
            "Avval EQ testini yakunlang",
            "warning"
        );
        return;
    }

    stopTestTimer();

    resetTestState();

    State.test.type = "pq";
    State.test.current = 0;
    State.test.answers = [];

    if (
        State.completed.pq !== null &&
        State.completed.pq !== undefined
    ) {

        const price =
            getPrice("pq_retry");

        if (price > 0) {

            const confirmed =
                window.confirm(
                    `PQ testini qayta topshirish narxi ${formatNumber(price)} so‘m.\n\nDavom etasizmi?`
                );

            if (!confirmed) {
                return;
            }
        }
    }

    if (!State.initData) {
        renderPQQuestion();
        return;
    }

    try {

        const response = await api(
            "/api/session/start",
            {
                test_type: "pq"
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "PQ test sessiyasini boshlashda xatolik"
            );
        }

        State.test.sessionId =
            response.session_id ||
            response.sessionId ||
            null;

        State.test.attemptId =
            response.attempt_id ||
            response.attemptId ||
            null;

        State.test.startedAt =
            Date.now();

        renderPQQuestion();

    } catch (error) {

        console.error(
            "[PQ START]",
            error
        );

        showToast(
            error.message ||
            "PQ testini boshlashda xatolik",
            "error"
        );
    }
}


// ============================================================
// FINISH PQ
// ============================================================

async function finishPQ() {

    if (State.test.finished) {
        return;
    }

    State.test.finished = true;

    stopTestTimer();

    showScreen("screen-result-loading");

    await sleep(1800);

    // --------------------------------------------
    // OFFLINE FALLBACK
    // --------------------------------------------

    if (!State.initData || !State.test.sessionId) {

        const local =
            calculatePQResult(
                State.test.answers
            );

        State.test.resultData = {
            test_type: "pq",
            score: local.score,
            correct: local.correct,
            total: PQ_QUESTIONS.length,
            level: local.level,
            result_visible: true,
            payment_required: false,
            payment_product: null,
            attempt_id: null
        };

        State.completed.pq =
            local.score;

        applyUnlocks();

        renderPQResult(
            State.test.resultData
        );

        return;
    }

    // --------------------------------------------
    // BACKEND
    // --------------------------------------------

    try {

        const response = await api(
            "/api/test/submit",
            {
                session_id: State.test.sessionId,
                test_type: "pq",
                answers: State.test.answers
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "PQ natijasini yuborib bo‘lmadi"
            );
        }

        const result = {
            ...response,

            test_type: "pq",

            attempt_id:
                response.attempt_id ||
                response.attemptId ||
                State.test.attemptId ||
                null
        };

        State.test.attemptId =
            result.attempt_id;

        State.test.resultData =
            result;

        // ----------------------------------------
        // PAYMENT REQUIRED
        // ----------------------------------------

        if (
            result.payment_required === true ||
            result.result_visible === false
        ) {

            showTestPaymentRequired(
                "pq",
                result
            );

            return;
        }

        // ----------------------------------------
        // FREE / PAID
        // ----------------------------------------

        completeTestFromResult(
            "pq",
            result
        );

        renderPQResult(result);

    } catch (error) {

        console.error(
            "[PQ FINISH]",
            error
        );

        State.test.finished = false;

        showToast(
            error.message ||
            "PQ natijasini hisoblashda xatolik",
            "error"
        );

        showScreen("screen-test");
    }
}


// ============================================================
// CALCULATE PQ
// ============================================================

function calculatePQResult(answers) {

    let points = 0;
    let maxPoints = 0;
    let correct = 0;

    PQ_QUESTIONS.forEach(
        (question, index) => {

            const answer =
                answers?.[index];

            const scores =
                Array.isArray(question.scores)
                    ? question.scores
                    : [];

            const max =
                Math.max(
                    ...scores,
                    0
                );

            maxPoints += max;

            if (
                answer !== undefined &&
                answer !== null &&
                scores[answer] !== undefined
            ) {

                points +=
                    Number(scores[answer]);

                if (
                    Number(scores[answer]) === max
                ) {
                    correct++;
                }
            }
        }
    );

    const score =
        maxPoints > 0
            ? Math.round(
                (points / maxPoints) * 100
            )
            : 0;

    return {
        score,
        correct,
        level: getPQLevel(score)
    };
}


// ============================================================
// PQ LEVEL
// ============================================================

function getPQLevel(score) {

    score = Number(score || 0);

    if (score >= 85) {
        return "Juda yuqori";
    }

    if (score >= 70) {
        return "Yuqori";
    }

    if (score >= 50) {
        return "O‘rtacha";
    }

    if (score >= 30) {
        return "Past";
    }

    return "Juda past";
}


// ============================================================
// RENDER PQ RESULT
// ============================================================

function renderPQResult(result) {

    const score =
        Number(
            result?.score ??
            result?.percentage ??
            0
        );

    const correct =
        Number(
            result?.correct ??
            result?.correct_answers ??
            0
        );

    const total =
        Number(
            result?.total ??
            result?.total_questions ??
            PQ_QUESTIONS.length
        );

    const level =
        result?.level ||
        getPQLevel(score);

    setText(
        "pq-result-score",
        String(score)
    );

    setText(
        "pq-score-value",
        String(score)
    );

    setText(
        "pq-result-correct",
        `${correct}/${total}`
    );

    setText(
        "pq-result-level",
        level
    );

    setText(
        "result-score",
        String(score)
    );

    setText(
        "result-level",
        level
    );

    const resultScreen =
        getElement("screen-pq-result");

    if (resultScreen) {
        resultScreen.dataset.score =
            String(score);
    }

    showScreen("screen-pq-result");
}


// ============================================================
// GENERIC EQ/PQ PAYMENT REQUIRED
// ============================================================

function showTestPaymentRequired(
    type,
    result
) {

    const product =
        result.payment_product ||
        getRetryOrInitialProduct(type);

    const price =
        Number(
            result.price ??
            getPrice(product)
        );

    const attemptId =
        result.attempt_id ||
        State.test.attemptId ||
        null;

    State.payment = {
        ...State.payment,

        product,
        attemptId,
        price,
        paymentId: null,

        testType: type
    };

    State.test.resultData =
        result;

    // --------------------------------------------
    // PAYMENT TITLE
    // --------------------------------------------

    setText(
        "payment-title",
        getProductName(product)
    );

    setText(
        "payment-product-name",
        getProductName(product)
    );

    // --------------------------------------------
    // PRICE
    // --------------------------------------------

    setText(
        "payment-price",
        `${formatNumber(price)} so‘m`
    );

    setText(
        "payment-required-price",
        `${formatNumber(price)} so‘m`
    );

    // --------------------------------------------
    // DESCRIPTION
    // --------------------------------------------

    const description =
        getElement("payment-description");

    if (description) {

        description.textContent =
            product.endsWith("_retry")
                ? `${type.toUpperCase()} testini qayta topshirish uchun to‘lov talab qilinadi.`
                : `${type.toUpperCase()} test natijasini ko‘rish uchun to‘lov talab qilinadi.`;
    }

    // --------------------------------------------
    // PAYMENT BUTTON
    // --------------------------------------------

    const paymentButton =
        getElement("start-payment-btn");

    if (
        paymentButton &&
        paymentButton.dataset.bound !== "1"
    ) {

        paymentButton.dataset.bound = "1";

        paymentButton.addEventListener(
            "click",
            () => {
                createPayment(
                    product,
                    attemptId
                );
            }
        );
    }

    if (paymentButton) {
        paymentButton.disabled = false;
    }

    showScreen("screen-payment");
}


// ============================================================
// DETERMINE INITIAL / RETRY PRODUCT
// ============================================================

function getRetryOrInitialProduct(type) {

    const completed =
        State.completed?.[type];

    if (
        completed !== null &&
        completed !== undefined
    ) {
        return `${type}_retry`;
    }

    return type;
}


// ============================================================
// EQ RETRY
// ============================================================

async function retryEQ() {

    await startEQ();
}


// ============================================================
// PQ RETRY
// ============================================================

async function retryPQ() {

    await startPQ();
}


// ============================================================
// RESULT HOME BUTTONS
// ============================================================

function bindEQPQResultButtons() {

    const eqHome =
        getElement("eq-result-home-btn");

    if (
        eqHome &&
        eqHome.dataset.bound !== "1"
    ) {

        eqHome.dataset.bound = "1";

        eqHome.addEventListener(
            "click",
            () => {
                showScreen("screen-home");
            }
        );
    }

    const eqRetry =
        getElement("eq-retry-btn");

    if (
        eqRetry &&
        eqRetry.dataset.bound !== "1"
    ) {

        eqRetry.dataset.bound = "1";

        eqRetry.addEventListener(
            "click",
            retryEQ
        );
    }

    const pqHome =
        getElement("pq-result-home-btn");

    if (
        pqHome &&
        pqHome.dataset.bound !== "1"
    ) {

        pqHome.dataset.bound = "1";

        pqHome.addEventListener(
            "click",
            () => {
                showScreen("screen-home");
            }
        );
    }

    const pqRetry =
        getElement("pq-retry-btn");

    if (
        pqRetry &&
        pqRetry.dataset.bound !== "1"
    ) {

        pqRetry.dataset.bound = "1";

        pqRetry.addEventListener(
            "click",
            retryPQ
        );
    }
}


// ============================================================
// EXTEND INIT
// ============================================================

const previousInitAfterEQ =
    App.init;

App.init = async function () {

    await previousInitAfterEQ();

    bindEQPQResultButtons();

    applyUnlocks();
};


// ============================================================
// 4-QISM TUGADI
// ============================================================
// ============================================================
// APP.JS — 5-QISM
// PAYMENT SYSTEM
// ============================================================


// ============================================================
// CREATE PAYMENT
// ============================================================

async function createPayment(
    product,
    attemptId = null,
    battleId = null
) {

    if (!product) {
        showToast(
            "To‘lov mahsuloti aniqlanmadi",
            "error"
        );
        return;
    }

    // --------------------------------------------
    // DUPLICATE CLICK PROTECTION
    // --------------------------------------------

    if (State.payment.creating) {
        return;
    }

    State.payment.creating = true;

    try {

        const response = await api(
            "/api/payment/create",
            {
                product,
                attempt_id:
                    attemptId ||
                    State.test.attemptId ||
                    null,

                battle_id:
                    battleId ||
                    State.battle?.id ||
                    null
            }
        );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "To‘lov yaratib bo‘lmadi"
            );
        }

        // ----------------------------------------
        // FREE PAYMENT
        // ----------------------------------------

        if (
            response.free === true ||
            Number(response.amount || 0) === 0
        ) {

            State.payment = {
                ...State.payment,

                product,
                attemptId:
                    response.attempt_id ||
                    attemptId ||
                    State.test.attemptId ||
                    null,

                paymentId:
                    response.payment_id ||
                    null,

                price: 0,

                creating: false
            };

            await handlePaymentApproved(
                response
            );

            return;
        }

        // ----------------------------------------
        // SAVE PAYMENT
        // ----------------------------------------

        State.payment = {
            ...State.payment,

            product,

            attemptId:
                response.attempt_id ||
                attemptId ||
                State.test.attemptId ||
                null,

            battleId:
                response.battle_id ||
                battleId ||
                null,

            paymentId:
                response.payment_id ||
                response.id ||
                null,

            price:
                Number(
                    response.amount ||
                    response.price ||
                    getPrice(product)
                ),

            cards:
                response.cards ||
                response.payment_cards ||
                [],

            creating: false
        };

        // ----------------------------------------
        // PAYMENT ID CHECK
        // ----------------------------------------

        if (!State.payment.paymentId) {
            throw new Error(
                "Payment ID olinmadi"
            );
        }

        renderPaymentCards(
            State.payment.cards
        );

        renderPaymentInfo(
            State.payment
        );

        showScreen("screen-payment");

        startPaymentPoll();

    } catch (error) {

        console.error(
            "[PAYMENT CREATE]",
            error
        );

        State.payment.creating = false;

        showToast(
            error.message ||
            "To‘lovni boshlashda xatolik",
            "error"
        );
    }
}


// ============================================================
// IQ PAYMENT
// ============================================================

async function startIQPayment() {

    const product =
        State.payment.product ||
        State.test.resultData?.payment_product ||
        "iq";

    const attemptId =
        State.payment.attemptId ||
        State.test.attemptId ||
        null;

    if (!attemptId) {
        showToast(
            "Test natijasi topilmadi",
            "error"
        );
        return;
    }

    const price =
        getPrice(product);

    // --------------------------------------------
    // FREE
    // --------------------------------------------

    if (price <= 0) {

        await createPayment(
            product,
            attemptId
        );

        return;
    }

    await createPayment(
        product,
        attemptId
    );
}


// ============================================================
// PAYMENT INFO
// ============================================================

function renderPaymentInfo(payment) {

    const product =
        payment.product || "";

    const amount =
        Number(
            payment.price || 0
        );

    setText(
        "payment-product-name",
        getProductName(product)
    );

    setText(
        "payment-price",
        `${formatNumber(amount)} so‘m`
    );

    setText(
        "payment-required-price",
        `${formatNumber(amount)} so‘m`
    );

    const title =
        getElement("payment-title");

    if (title) {
        title.textContent =
            getProductName(product);
    }
}


// ============================================================
// RENDER PAYMENT CARDS
// ============================================================

function renderPaymentCards(cards) {

    const container =
        getElement("payment-cards");

    if (!container) {
        return;
    }

    if (
        !Array.isArray(cards) ||
        cards.length === 0
    ) {

        container.innerHTML = `
            <div class="payment-empty">
                <div class="payment-empty-icon">💳</div>
                <div class="payment-empty-title">
                    To‘lov kartalari topilmadi
                </div>
                <div class="payment-empty-text">
                    Iltimos, keyinroq qayta urinib ko‘ring.
                </div>
            </div>
        `;

        return;
    }

    container.innerHTML =
        cards.map(card => {

            const number =
                card.card_number ||
                card.number ||
                "";

            const holder =
                card.holder_name ||
                card.holder ||
                "";

            const bank =
                card.bank_name ||
                card.bank ||
                "";

            return `
                <div class="payment-card">
                    <div class="payment-card-top">

                        <div class="payment-bank">
                            ${escapeHtml(bank)}
                        </div>

                        <div class="payment-card-icon">
                            💳
                        </div>

                    </div>

                    <div class="payment-card-number">
                        ${escapeHtml(number)}
                    </div>

                    <div class="payment-card-bottom">

                        <div>
                            <div class="payment-card-label">
                                Karta egasi
                            </div>

                            <div class="payment-card-holder">
                                ${escapeHtml(holder)}
                            </div>
                        </div>

                        <button
                            type="button"
                            class="copy-card-btn"
                            data-card="${escapeHtml(number)}"
                        >
                            Nusxalash
                        </button>

                    </div>
                </div>
            `;

        }).join("");

    container
        .querySelectorAll(".copy-card-btn")
        .forEach(button => {

            button.addEventListener(
                "click",
                async () => {

                    const card =
                        button.dataset.card || "";

                    await copyText(card);

                    showToast(
                        "Karta raqami nusxalandi",
                        "success"
                    );
                }
            );

        });
}


// ============================================================
// COPY TEXT
// ============================================================

async function copyText(text) {

    try {

        if (
            navigator.clipboard &&
            window.isSecureContext
        ) {

            await navigator.clipboard.writeText(
                text
            );

            return true;
        }

        const textarea =
            document.createElement("textarea");

        textarea.value = text;

        textarea.style.position =
            "fixed";

        textarea.style.opacity =
            "0";

        document.body.appendChild(
            textarea
        );

        textarea.focus();
        textarea.select();

        document.execCommand(
            "copy"
        );

        textarea.remove();

        return true;

    } catch (error) {

        console.warn(
            "[COPY]",
            error
        );

        return false;
    }
}


// ============================================================
// PAYMENT POLLING
// ============================================================

function startPaymentPoll() {

    stopPaymentPolling();

    if (!State.payment.paymentId) {
        return;
    }

    checkPaymentStatus();

    State.payment.pollTimer =
        setInterval(
            checkPaymentStatus,
            5000
        );
}


// ============================================================
// CHECK PAYMENT STATUS
// ============================================================

async function checkPaymentStatus() {

    const paymentId =
        State.payment.paymentId;

    if (!paymentId) {
        stopPaymentPolling();
        return;
    }

    try {

        const response = await api(
            `/api/payment/${encodeURIComponent(paymentId)}`,
            {},
            "POST"
        );

        if (!response?.ok) {
            return;
        }

        const status =
            String(
                response.status || ""
            ).toLowerCase();

        // ----------------------------------------
        // APPROVED
        // ----------------------------------------

        if (
            status === "approved" ||
            status === "paid" ||
            status === "success"
        ) {

            stopPaymentPolling();

            await handlePaymentApproved(
                response
            );

            return;
        }

        // ----------------------------------------
        // REJECTED
        // ----------------------------------------

        if (
            status === "rejected" ||
            status === "cancelled" ||
            status === "canceled"
        ) {

            stopPaymentPolling();

            State.payment.status =
                status;

            showToast(
                "To‘lov tasdiqlanmadi",
                "error"
            );

            return;
        }

        // ----------------------------------------
        // PENDING
        // ----------------------------------------

        State.payment.status =
            status || "pending";

    } catch (error) {

        /*
         * Polling xatosida testni buzmaymiz.
         * Keyingi poll yana urinadi.
         */

        console.warn(
            "[PAYMENT POLL]",
            error
        );
    }
}


// ============================================================
// PAYMENT APPROVED
// ============================================================

async function handlePaymentApproved(
    paymentResponse
) {

    State.payment.status =
        "approved";

    const product =
        State.payment.product ||
        paymentResponse.product ||
        "";

    const attemptId =
        State.payment.attemptId ||
        paymentResponse.attempt_id ||
        State.test.attemptId ||
        null;

    const battleId =
        State.payment.battleId ||
        paymentResponse.battle_id ||
        null;

    // --------------------------------------------
    // BATTLE
    // --------------------------------------------

    if (
        product === "battle" ||
        battleId
    ) {

        State.payment.creating =
            false;

        State.payment.paymentId =
            paymentResponse.payment_id ||
            State.payment.paymentId;

        showToast(
            "To‘lov tasdiqlandi",
            "success"
        );

        if (battleId) {

            State.battle.id =
                battleId;

            await loadBattle(
                battleId
            );
        }

        resetPaymentState();

        return;
    }

    // --------------------------------------------
    // TEST
    // --------------------------------------------

    if (!attemptId) {

        showToast(
            "To‘lov tasdiqlandi, lekin test natijasi topilmadi",
            "warning"
        );

        resetPaymentState();

        showScreen("screen-home");

        return;
    }

    showToast(
        "To‘lov tasdiqlandi",
        "success"
    );

    /*
     * Muhim:
     *
     * Frontenddagi eski local natijaga ishonmaymiz.
     * To‘lovdan keyin backenddan natijani qayta olamiz.
     */

    const result =
        await fetchPaidResult(
            attemptId
        );

    if (!result) {

        showToast(
            "Natijani yuklashda xatolik. Qayta urinib ko‘ring.",
            "error"
        );

        return;
    }

    const type =
        normalizeTestType(
            result.test_type ||
            State.test.type ||
            getTypeFromProduct(product)
        );

    completeTestFromResult(
        type,
        result
    );

    State.test.resultData =
        result;

    resetPaymentState();

    // --------------------------------------------
    // RENDER RESULT
    // --------------------------------------------

    if (type === "iq") {

        renderIQResult(
            result
        );

    } else if (type === "eq") {

        renderEQResult(
            result
        );

    } else if (type === "pq") {

        renderPQResult(
            result
        );
    }
}


// ============================================================
// FETCH PAID RESULT
// ============================================================

async function fetchPaidResult(
    attemptId
) {

    try {

        const response = await api(
            `/api/result/${encodeURIComponent(attemptId)}`,
            {},
            "GET"
        );

        if (!response?.ok) {
            return null;
        }

        /*
         * Backend response turlicha bo‘lishi mumkin:
         * result obyekt ichida yoki response'ning o‘zida.
         */

        const result =
            response.result ||
            response.data ||
            response;

        if (
            result.result_visible === false
        ) {
            return null;
        }

        return result;

    } catch (error) {

        console.error(
            "[FETCH RESULT]",
            error
        );

        return null;
    }
}


// ============================================================
// NORMALIZE TEST TYPE
// ============================================================

function normalizeTestType(type) {

    const value =
        String(type || "")
            .trim()
            .toLowerCase();

    if (value === "iq") {
        return "iq";
    }

    if (value === "eq") {
        return "eq";
    }

    if (value === "pq") {
        return "pq";
    }

    return value;
}


// ============================================================
// PRODUCT -> TEST TYPE
// ============================================================

function getTypeFromProduct(
    product
) {

    const value =
        String(product || "")
            .toLowerCase();

    if (value.startsWith("iq")) {
        return "iq";
    }

    if (value.startsWith("eq")) {
        return "eq";
    }

    if (value.startsWith("pq")) {
        return "pq";
    }

    return "";
}


// ============================================================
// PAYMENT RECEIPT
// ============================================================

function sendReceipt() {

    /*
     * Bot orqali chek yuborish oqimi.
     *
     * Frontend faylni backendga upload qilmaydi.
     * Telegram WebApp'dan botga qaytish uchun
     * foydalanuvchiga aniq ko‘rsatma beradi.
     */

    const text =
        "To‘lovni amalga oshirgach, chek/skrinshotni Telegram botga yuboring.";

    if (tg) {

        try {

            tg.showPopup(
                {
                    title: "Chek yuborish",
                    message: text,
                    buttons: [
                        {
                            id: "ok",
                            type: "default",
                            text: "Tushundim"
                        }
                    ]
                }
            );

        } catch (error) {

            showToast(
                text,
                "info"
            );
        }

    } else {

        showToast(
            text,
            "info"
        );
    }
}


// ============================================================
// PAYMENT SCREEN BUTTONS
// ============================================================

function bindPaymentScreenButtons() {

    const receiptButton =
        getElement("send-receipt-btn");

    if (
        receiptButton &&
        receiptButton.dataset.bound !== "1"
    ) {

        receiptButton.dataset.bound =
            "1";

        receiptButton.addEventListener(
            "click",
            sendReceipt
        );
    }

    const cancelButton =
        getElement("payment-cancel-btn");

    if (
        cancelButton &&
        cancelButton.dataset.bound !== "1"
    ) {

        cancelButton.dataset.bound =
            "1";

        cancelButton.addEventListener(
            "click",
            () => {

                stopPaymentPolling();

                resetPaymentState();

                showScreen(
                    "screen-home"
                );
            }
        );
    }
}


// ============================================================
// RESET PAYMENT
// ============================================================

function clearPaymentData() {

    stopPaymentPolling();

    State.payment = {
        paymentId: null,
        product: null,
        attemptId: null,
        battleId: null,
        price: 0,
        cards: [],
        status: null,
        creating: false,
        pollTimer: null,
        testType: null
    };
}


// ============================================================
// PAYMENT ERROR RECOVERY
// ============================================================

function retryCurrentPayment() {

    const product =
        State.payment.product;

    const attemptId =
        State.payment.attemptId;

    const battleId =
        State.payment.battleId;

    if (!product) {
        showToast(
            "To‘lov ma’lumotlari topilmadi",
            "error"
        );
        return;
    }

    createPayment(
        product,
        attemptId,
        battleId
    );
}


// ============================================================
// EXTEND INIT
// ============================================================

const previousInitAfterPayment =
    App.init;

App.init = async function () {

    await previousInitAfterPayment();

    bindPaymentScreenButtons();

    bindPaymentButtons();

    bindEQPQResultButtons();

    applyUnlocks();
};


// ============================================================
// 5-QISM TUGADI
// ============================================================
// ============================================================
// APP.JS — 6-QISM
// PROFILE / OVERALL + BATTLE SYSTEM
// ============================================================


// ============================================================
// PROFILE
// ============================================================

function openProfile() {

    const iq =
        State.completed.iq;

    const eq =
        State.completed.eq;

    const pq =
        State.completed.pq;

    if (
        iq === null ||
        iq === undefined ||
        eq === null ||
        eq === undefined ||
        pq === null ||
        pq === undefined
    ) {
        showToast(
            "Avval barcha testlarni yakunlang",
            "warning"
        );

        return;
    }

    renderProfile();

    showScreen(
        "screen-profile"
    );
}


// ============================================================
// RENDER PROFILE
// ============================================================

function renderProfile() {

    const iq =
        Number(State.completed.iq || 0);

    const eq =
        Number(State.completed.eq || 0);

    const pq =
        Number(State.completed.pq || 0);

    const overall =
        Math.round(
            (iq + eq + pq) / 3
        );

    // --------------------------------------------
    // SCORES
    // --------------------------------------------

    setText(
        "profile-iq-score",
        String(iq)
    );

    setText(
        "profile-eq-score",
        String(eq)
    );

    setText(
        "profile-pq-score",
        String(pq)
    );

    setText(
        "profile-overall-score",
        String(overall)
    );

    setText(
        "overall-score",
        String(overall)
    );

    // --------------------------------------------
    // LEVEL
    // --------------------------------------------

    setText(
        "profile-overall-level",
        getOverallLevel(overall)
    );

    // --------------------------------------------
    // STRENGTHS / WEAKNESSES
    // --------------------------------------------

    const scores = [
        {
            name: "IQ",
            value: iq
        },
        {
            name: "EQ",
            value: eq
        },
        {
            name: "PQ",
            value: pq
        }
    ];

    const sorted =
        [...scores].sort(
            (a, b) => b.value - a.value
        );

    const strengths =
        sorted
            .slice(0, 2)
            .map(item => item.name);

    const weaknesses =
        sorted
            .slice(-1)
            .map(item => item.name);

    setHTML(
        "profile-strengths",
        strengths.map(
            item => `
                <span class="profile-tag">
                    ${escapeHtml(item)}
                </span>
            `
        ).join("")
    );

    setHTML(
        "profile-weaknesses",
        weaknesses.map(
            item => `
                <span class="profile-tag">
                    ${escapeHtml(item)}
                </span>
            `
        ).join("")
    );

    // --------------------------------------------
    // USER DATA
    // --------------------------------------------

    const profile =
        State.profile || {};

    setText(
        "profile-full-name",
        profile.full_name ||
        profile.fullName ||
        ""
    );

    setText(
        "profile-gender",
        profile.gender || ""
    );

    setText(
        "profile-age",
        profile.age
            ? String(profile.age)
            : ""
    );

    setText(
        "profile-country",
        profile.country || ""
    );
}


// ============================================================
// OVERALL LEVEL
// ============================================================

function getOverallLevel(score) {

    score = Number(score || 0);

    if (score >= 85) {
        return "Juda yuqori";
    }

    if (score >= 70) {
        return "Yuqori";
    }

    if (score >= 50) {
        return "O‘rtacha";
    }

    if (score >= 30) {
        return "Past";
    }

    return "Juda past";
}


// ============================================================
// PROFILE BACK
// ============================================================

function closeProfile() {

    showScreen(
        "screen-home"
    );
}


// ============================================================
// BATTLE STATE
// ============================================================

function resetBattleState() {

    stopBattlePolling();

    State.battle = {
        id: null,
        code: null,
        status: null,

        creator: null,
        opponent: null,

        players: [],

        currentQuestion: 0,
        answers: [],

        started: false,
        finished: false,

        result: null,

        paymentStatus: null,

        pollTimer: null
    };
}


// ============================================================
// OPEN BATTLE
// ============================================================

function openBattle() {

    resetBattleState();

    showScreen(
        "screen-battle"
    );

    renderBattleHome();
}


// ============================================================
// BATTLE HOME
// ============================================================

function renderBattleHome() {

    setText(
        "battle-code-input",
        ""
    );

    const input =
        getElement("battle-code-input");

    if (input) {
        input.value = "";
    }

    const createButton =
        getElement("battle-create-btn");

    if (
        createButton &&
        createButton.dataset.bound !== "1"
    ) {

        createButton.dataset.bound =
            "1";

        createButton.addEventListener(
            "click",
            createBattle
        );
    }

    const joinButton =
        getElement("battle-join-btn");

    if (
        joinButton &&
        joinButton.dataset.bound !== "1"
    ) {

        joinButton.dataset.bound =
            "1";

        joinButton.addEventListener(
            "click",
            joinBattle
        );
    }
}


// ============================================================
// CREATE BATTLE
// ============================================================

async function createBattle() {

    if (!State.initData) {

        showToast(
            "Battle Telegram ichida ishlaydi",
            "warning"
        );

        return;
    }

    try {

        const response =
            await api(
                "/api/battle/create",
                {}
            );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Battle yaratib bo‘lmadi"
            );
        }

        State.battle = {
            ...State.battle,

            id:
                response.battle_id ||
                response.id ||
                null,

            code:
                response.code ||
                response.join_code ||
                null,

            status:
                response.status ||
                "waiting"
        };

        renderBattleWaiting();

        startBattlePolling();

    } catch (error) {

        console.error(
            "[BATTLE CREATE]",
            error
        );

        showToast(
            error.message ||
            "Battle yaratishda xatolik",
            "error"
        );
    }
}


// ============================================================
// JOIN BATTLE
// ============================================================

async function joinBattle() {

    if (!State.initData) {

        showToast(
            "Battle Telegram ichida ishlaydi",
            "warning"
        );

        return;
    }

    const input =
        getElement("battle-code-input");

    const code =
        input?.value?.trim() || "";

    if (!code) {

        showToast(
            "Battle kodini kiriting",
            "warning"
        );

        return;
    }

    try {

        const response =
            await api(
                "/api/battle/join",
                {
                    code
                }
            );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Battle'ga qo‘shilib bo‘lmadi"
            );
        }

        State.battle = {
            ...State.battle,

            id:
                response.battle_id ||
                response.id ||
                null,

            code,

            status:
                response.status ||
                "waiting"
        };

        renderBattleWaiting();

        startBattlePolling();

    } catch (error) {

        console.error(
            "[BATTLE JOIN]",
            error
        );

        showToast(
            error.message ||
            "Battle kodini tekshiring",
            "error"
        );
    }
}


// ============================================================
// BATTLE WAITING
// ============================================================

function renderBattleWaiting() {

    setText(
        "battle-code-display",
        State.battle.code || "—"
    );

    setText(
        "battle-id-display",
        State.battle.id || "—"
    );

    const status =
        State.battle.status;

    if (
        status === "ready" ||
        status === "playing"
    ) {

        showScreen(
            "screen-battle-test"
        );

        return;
    }

    showScreen(
        "screen-battle-waiting"
    );
}


// ============================================================
// BATTLE POLLING
// ============================================================

function startBattlePolling() {

    stopBattlePolling();

    if (!State.battle.id) {
        return;
    }

    checkBattle();

    State.battle.pollTimer =
        setInterval(
            checkBattle,
            4000
        );
}


// ============================================================
// CHECK BATTLE
// ============================================================

async function checkBattle() {

    if (!State.battle.id) {
        stopBattlePolling();
        return;
    }

    try {

        const response =
            await api(
                `/api/battle/${encodeURIComponent(State.battle.id)}`,
                {},
                "GET"
            );

        if (!response?.ok) {
            return;
        }

        const battle =
            response.battle ||
            response.data ||
            response;

        State.battle = {
            ...State.battle,
            ...battle
        };

        const status =
            String(
                battle.status || ""
            ).toLowerCase();

        // ----------------------------------------
        // WAITING
        // ----------------------------------------

        if (
            status === "waiting" ||
            status === "waiting_for_player"
        ) {

            renderBattleWaiting();

            return;
        }

        // ----------------------------------------
        // WAITING FOR PAYMENT
        // ----------------------------------------

        if (
            status === "waiting_for_payment"
        ) {

            stopBattlePolling();

            renderBattlePayment();

            return;
        }

        // ----------------------------------------
        // READY / PLAYING
        // ----------------------------------------

        if (
            status === "ready" ||
            status === "playing"
        ) {

            if (!State.battle.started) {

                stopBattlePolling();

                startBattleTest();

            }

            return;
        }

        // ----------------------------------------
        // FINISHED
        // ----------------------------------------

        if (
            status === "finished" ||
            status === "completed"
        ) {

            stopBattlePolling();

            renderBattleResult(
                battle.result ||
                battle
            );
        }

    } catch (error) {

        console.warn(
            "[BATTLE POLL]",
            error
        );
    }
}


// ============================================================
// BATTLE PAYMENT
// ============================================================

function renderBattlePayment() {

    const price =
        getPrice("battle");

    setText(
        "battle-payment-price",
        `${formatNumber(price)} so‘m`
    );

    const button =
        getElement("battle-pay-btn");

    if (
        button &&
        button.dataset.bound !== "1"
    ) {

        button.dataset.bound =
            "1";

        button.addEventListener(
            "click",
            startBattlePayment
        );
    }

    if (button) {
        button.disabled = false;
    }

    showScreen(
        "screen-battle-payment"
    );
}


// ============================================================
// START BATTLE PAYMENT
// ============================================================

async function startBattlePayment() {

    if (!State.battle.id) {

        showToast(
            "Battle topilmadi",
            "error"
        );

        return;
    }

    const price =
        getPrice("battle");

    if (price <= 0) {

        await createPayment(
            "battle",
            null,
            State.battle.id
        );

        return;
    }

    await createPayment(
        "battle",
        null,
        State.battle.id
    );
}


// ============================================================
// START BATTLE TEST
// ============================================================

async function startBattleTest() {

    if (
        State.battle.started
    ) {
        return;
    }

    State.battle.started =
        true;

    State.battle.finished =
        false;

    State.battle.currentQuestion =
        0;

    State.battle.answers = [];

    // Battle uchun IQ savollaridan foydalanamiz.
    renderBattleQuestion();
}


// ============================================================
// RENDER BATTLE QUESTION
// ============================================================

function renderBattleQuestion() {

    const index =
        State.battle.currentQuestion;

    const question =
        QUESTIONS[index];

    if (!question) {

        finishBattle();

        return;
    }

    const total =
        QUESTIONS.length;

    setText(
        "battle-question-number",
        `${index + 1}/${total}`
    );

    setText(
        "battle-question-title",
        question.title ||
        `Savol ${index + 1}`
    );

    setHTML(
        "battle-question-content",
        renderMatrix(
            question.matrix
        )
    );

    setHTML(
        "battle-question-options",
        renderOptions(
            question
        )
    );

    document
        .querySelectorAll(
            "#battle-question-options .answer-option"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    const answer =
                        Number(
                            button.dataset.answer
                        );

                    selectBattleAnswer(
                        answer
                    );
                }
            );

        });

    showScreen(
        "screen-battle-test"
    );
}


// ============================================================
// SELECT BATTLE ANSWER
// ============================================================

function selectBattleAnswer(
    answer
) {

    if (
        State.battle.finished
    ) {
        return;
    }

    State.battle.answers[
        State.battle.currentQuestion
    ] = answer;

    document
        .querySelectorAll(
            "#battle-question-options .answer-option"
        )
        .forEach(button => {

            button.classList.remove(
                "selected"
            );

            if (
                Number(button.dataset.answer) ===
                answer
            ) {

                button.classList.add(
                    "selected"
                );
            }

        });

    setTimeout(
        () => {

            if (
                State.battle.currentQuestion >=
                QUESTIONS.length - 1
            ) {

                finishBattle();

            } else {

                State.battle.currentQuestion += 1;

                renderBattleQuestion();
            }

        },
        220
    );
}


// ============================================================
// FINISH BATTLE
// ============================================================

async function finishBattle() {

    if (
        State.battle.finished
    ) {
        return;
    }

    State.battle.finished =
        true;

    try {

        const response =
            await api(
                `/api/battle/${encodeURIComponent(State.battle.id)}/submit`,
                {
                    answers:
                        State.battle.answers
                }
            );

        if (!response?.ok) {
            throw new Error(
                response?.error ||
                "Battle natijasini yuborib bo‘lmadi"
            );
        }

        State.battle.result =
            response.result ||
            response;

        // ----------------------------------------
        // WAITING FOR OPPONENT
        // ----------------------------------------

        if (
            response.status === "waiting" ||
            response.waiting === true
        ) {

            State.battle.finished =
                false;

            showScreen(
                "screen-battle-waiting-result"
            );

            startBattlePolling();

            return;
        }

        renderBattleResult(
            State.battle.result
        );

    } catch (error) {

        console.error(
            "[BATTLE FINISH]",
            error
        );

        State.battle.finished =
            false;

        showToast(
            error.message ||
            "Battle natijasini yuborishda xatolik",
            "error"
        );
    }
}


// ============================================================
// RENDER BATTLE RESULT
// ============================================================

function renderBattleResult(
    result
) {

    const battle =
        result || {};

    const winner =
        battle.winner ||
        battle.winner_user ||
        null;

    const myScore =
        Number(
            battle.my_score ??
            battle.user_score ??
            battle.score ??
            0
        );

    const opponentScore =
        Number(
            battle.opponent_score ??
            battle.other_score ??
            0
        );

    setText(
        "battle-my-score",
        String(myScore)
    );

    setText(
        "battle-opponent-score",
        String(opponentScore)
    );

    // --------------------------------------------
    // WINNER
    // --------------------------------------------

    let winnerText =
        "Natija";

    if (
        winner === "draw" ||
        battle.is_draw === true
    ) {

        winnerText =
            "Durrang";

    } else if (
        winner === "me" ||
        battle.winner_is_me === true
    ) {

        winnerText =
            "Siz g‘oldingiz";

    } else if (
        winner === "opponent"
    ) {

        winnerText =
            "Raqib g‘alaba qozondi";

    } else if (
        typeof winner === "string" &&
        winner
    ) {

        winnerText =
            winner;
    }

    setText(
        "battle-winner",
        winnerText
    );

    showScreen(
        "screen-battle-result"
    );
}


// ============================================================
// BATTLE HOME
// ============================================================

function closeBattle() {

    stopBattlePolling();

    resetBattleState();

    showScreen(
        "screen-home"
    );
}


// ============================================================
// BATTLE RESULT HOME
// ============================================================

function closeBattleResult() {

    stopBattlePolling();

    resetBattleState();

    showScreen(
        "screen-home"
    );
}


// ============================================================
// BATTLE EVENTS
// ============================================================

function bindBattleEvents() {

    const battleButton =
        getElement("battle-btn");

    if (
        battleButton &&
        battleButton.dataset.bound !== "1"
    ) {

        battleButton.dataset.bound =
            "1";

        battleButton.addEventListener(
            "click",
            openBattle
        );
    }

    const battleBack =
        getElement("battle-back-btn");

    if (
        battleBack &&
        battleBack.dataset.bound !== "1"
    ) {

        battleBack.dataset.bound =
            "1";

        battleBack.addEventListener(
            "click",
            closeBattle
        );
    }

    const battleResultHome =
        getElement("battle-result-home-btn");

    if (
        battleResultHome &&
        battleResultHome.dataset.bound !== "1"
    ) {

        battleResultHome.dataset.bound =
            "1";

        battleResultHome.addEventListener(
            "click",
            closeBattleResult
        );
    }
}


// ============================================================
// FINAL GLOBAL BINDINGS
// ============================================================

function bindFinalEvents() {

    // --------------------------------------------
    // PROFILE
    // --------------------------------------------

    const profileBack =
        getElement("profile-back-btn");

    if (
        profileBack &&
        profileBack.dataset.bound !== "1"
    ) {

        profileBack.dataset.bound =
            "1";

        profileBack.addEventListener(
            "click",
            closeProfile
        );
    }

    // --------------------------------------------
    // BATTLE
    // --------------------------------------------

    bindBattleEvents();

    // --------------------------------------------
    // HOME
    // --------------------------------------------

    const homeButtons =
        document.querySelectorAll(
            "[data-go-home]"
        );

    homeButtons.forEach(
        button => {

            if (
                button.dataset.bound === "1"
            ) {
                return;
            }

            button.dataset.bound =
                "1";

            button.addEventListener(
                "click",
                () => {
                    showScreen(
                        "screen-home"
                    );
                }
            );
        }
    );
}


// ============================================================
// FINAL INIT WRAPPER
// ============================================================

const previousFinalInit =
    App.init;

App.init = async function () {

    await previousFinalInit();

    bindFinalEvents();

    bindPaymentButtons();

    bindPaymentScreenButtons();

    bindEQPQResultButtons();

    applyUnlocks();

    updateProfileHeader();

    updateLiveCounter();
};


// ============================================================
// 6-QISM TUGADI
// ============================================================
// ============================================================
// APP.JS — 7-QISM
// FINAL EVENTS + NAVIGATION + TELEGRAM + CLEANUP
// ============================================================


// ============================================================
// SAFE NAVIGATION
// ============================================================

function goHome() {

    stopTestTimer();
    stopPaymentPolling();
    stopBattlePolling();

    showScreen(
        "screen-home"
    );
}


// ============================================================
// GENERIC BACK
// ============================================================

function goBack() {

    const active =
        document.querySelector(
            ".screen.active"
        );

    if (!active) {
        goHome();
        return;
    }

    const id =
        active.id || "";

    // Test ichida orqaga bosilsa
    if (
        id === "screen-test"
    ) {

        const confirmed =
            window.confirm(
                "Testdan chiqmoqchimisiz? Hozirgi javoblar saqlanmaydi."
            );

        if (confirmed) {
            stopTestTimer();
            resetTestState();
            goHome();
        }

        return;
    }

    // IQ sample
    if (
        id === "screen-iq-sample"
    ) {
        goHome();
        return;
    }

    // Payment
    if (
        id === "screen-payment" ||
        id === "screen-payment-required"
    ) {

        stopPaymentPolling();
        resetPaymentState();

        goHome();

        return;
    }

    // EQ result
    if (
        id === "screen-eq-result"
    ) {
        goHome();
        return;
    }

    // PQ result
    if (
        id === "screen-pq-result"
    ) {
        goHome();
        return;
    }

    // IQ result
    if (
        id === "screen-result"
    ) {
        goHome();
        return;
    }

    // Profile
    if (
        id === "screen-profile"
    ) {
        goHome();
        return;
    }

    // Battle
    if (
        id === "screen-battle" ||
        id === "screen-battle-waiting" ||
        id === "screen-battle-payment"
    ) {

        stopBattlePolling();
        resetBattleState();

        goHome();

        return;
    }

    if (
        id === "screen-battle-result"
    ) {

        closeBattleResult();

        return;
    }

    // Default
    goHome();
}


// ============================================================
// TELEGRAM BACK BUTTON
// ============================================================

function setupTelegramBackButton() {

    if (!tg) {
        return;
    }

    try {

        if (
            !tg.BackButton
        ) {
            return;
        }

        tg.BackButton.onClick(
            goBack
        );

        updateTelegramBackButton();

    } catch (error) {

        console.warn(
            "[TELEGRAM BACK BUTTON]",
            error
        );
    }
}


// ============================================================
// UPDATE TELEGRAM BACK BUTTON
// ============================================================

function updateTelegramBackButton() {

    if (
        !tg ||
        !tg.BackButton
    ) {
        return;
    }

    const active =
        document.querySelector(
            ".screen.active"
        );

    if (!active) {
        tg.BackButton.hide();
        return;
    }

    const id =
        active.id || "";

    if (
        id === "screen-home"
    ) {

        tg.BackButton.hide();

    } else {

        tg.BackButton.show();
    }
}


// ============================================================
// SCREEN OBSERVER
// ============================================================

function setupScreenObserver() {

    const observer =
        new MutationObserver(
            () => {

                updateTelegramBackButton();

            }
        );

    document
        .querySelectorAll(
            ".screen"
        )
        .forEach(
            screen => {

                observer.observe(
                    screen,
                    {
                        attributes: true,
                        attributeFilter: [
                            "class"
                        ]
                    }
                );

            }
        );
}


// ============================================================
// BUTTON DOUBLE CLICK PROTECTION
// ============================================================

function protectButtons() {

    document
        .addEventListener(
            "click",
            event => {

                const button =
                    event.target.closest(
                        "button"
                    );

                if (!button) {
                    return;
                }

                if (
                    button.disabled
                ) {
                    event.preventDefault();
                    return;
                }

                /*
                 * Payment/test tugmalari uchun
                 * qisqa vaqt ichida ikkinchi clickni
                 * bloklaymiz.
                 */

                if (
                    button.dataset.busy === "1"
                ) {

                    event.preventDefault();
                    event.stopPropagation();

                    return;
                }

                const isImportant =
                    button.id?.includes("payment") ||
                    button.id?.includes("start-") ||
                    button.id?.includes("battle") ||
                    button.id?.includes("retry");

                if (!isImportant) {
                    return;
                }

                button.dataset.busy =
                    "1";

                setTimeout(
                    () => {
                        button.dataset.busy =
                            "0";
                    },
                    700
                );

            },
            true
        );
}


// ============================================================
// TELEGRAM MAIN BUTTON
// ============================================================

function setupTelegramMainButton() {

    if (
        !tg ||
        !tg.MainButton
    ) {
        return;
    }

    try {

        tg.MainButton.hide();

    } catch (error) {

        console.warn(
            "[TELEGRAM MAIN BUTTON]",
            error
        );
    }
}


// ============================================================
// TELEGRAM USER SYNC
// ============================================================

function syncTelegramUser() {

    if (!tg) {
        return;
    }

    try {

        const user =
            tg.initDataUnsafe?.user;

        if (!user) {
            return;
        }

        State.telegramUser =
            user;

        if (!State.user) {

            State.user = {
                id:
                    user.id,

                first_name:
                    user.first_name ||
                    "",

                last_name:
                    user.last_name ||
                    "",

                username:
                    user.username ||
                    ""
            };
        }

        updateProfileHeader();

    } catch (error) {

        console.warn(
            "[TELEGRAM USER]",
            error
        );
    }
}


// ============================================================
// PAGE VISIBILITY
// ============================================================

function setupVisibilityHandler() {

    document.addEventListener(
        "visibilitychange",
        () => {

            if (
                document.visibilityState ===
                "visible"
            ) {

                // Payment davom etayotgan bo‘lsa
                if (
                    State.payment?.paymentId
                ) {

                    checkPaymentStatus();
                }

                // Battle davom etayotgan bo‘lsa
                if (
                    State.battle?.id &&
                    !State.battle.finished
                ) {

                    checkBattle();
                }

            }

        }
    );
}


// ============================================================
// ONLINE / OFFLINE
// ============================================================

function setupConnectionHandler() {

    window.addEventListener(
        "online",
        () => {

            showToast(
                "Internet aloqasi tiklandi",
                "success"
            );

            if (
                State.payment?.paymentId
            ) {

                checkPaymentStatus();
            }

            if (
                State.battle?.id
            ) {

                checkBattle();
            }
        }
    );

    window.addEventListener(
        "offline",
        () => {

            showToast(
                "Internet aloqasi uzildi",
                "warning"
            );
        }
    );
}


// ============================================================
// PREVENT ACCIDENTAL PAGE EXIT DURING TEST
// ============================================================

function setupBeforeUnload() {

    window.addEventListener(
        "beforeunload",
        event => {

            const active =
                document.querySelector(
                    ".screen.active"
                );

            if (!active) {
                return;
            }

            const id =
                active.id || "";

            const testRunning =
                id === "screen-test" &&
                !State.test.finished;

            const battleRunning =
                id === "screen-battle-test" &&
                !State.battle.finished;

            if (
                testRunning ||
                battleRunning
            ) {

                event.preventDefault();

                event.returnValue =
                    "";
            }
        }
    );
}


// ============================================================
// ERROR HANDLING
// ============================================================

window.addEventListener(
    "error",
    event => {

        console.error(
            "[APP ERROR]",
            event.error ||
            event.message
        );
    }
);


window.addEventListener(
    "unhandledrejection",
    event => {

        console.error(
            "[APP UNHANDLED PROMISE]",
            event.reason
        );
    }
);


// ============================================================
// DEBUG HELPER
// ============================================================

window.ZAKO_DEBUG = {

    getState() {
        return State;
    },

    getUser() {
        return State.user;
    },

    getCompleted() {
        return State.completed;
    },

    getPayment() {
        return State.payment;
    },

    getBattle() {
        return State.battle;
    },

    goHome() {
        goHome();
    }

};


// ============================================================
// FINAL SETUP
// ============================================================

function finalSetup() {

    setupTelegramBackButton();

    setupTelegramMainButton();

    syncTelegramUser();

    setupScreenObserver();

    protectButtons();

    setupVisibilityHandler();

    setupConnectionHandler();

    setupBeforeUnload();

    updateTelegramBackButton();

    updateLiveCounter();

    updateProfileHeader();

    applyUnlocks();
}


// ============================================================
// FINAL DOM READY
// ============================================================

function bootApp() {

    try {

        finalSetup();

        console.log(
            "[APP] ZAKO IQ application ready"
        );

    } catch (error) {

        console.error(
            "[APP] Final setup error:",
            error
        );
    }
}


if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        bootApp,
        {
            once: true
        }
    );

} else {

    bootApp();
}


// ============================================================
// FINAL SAFETY CHECK
// ============================================================

setTimeout(
    () => {

        try {

            applyUnlocks();

            updateTelegramBackButton();

            updateLiveCounter();

        } catch (error) {

            console.error(
                "[APP] Safety check error:",
                error
            );
        }

    },
    1000
);


// ============================================================
// APP.JS — END
// ============================================================