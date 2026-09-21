"use strict";

/*
 * ============================================================
 * IQ TEST BOT — MINI APP
 * Frontend application
 *
 * Architecture:
 * Telegram Mini App
 *       ↓
 * Local state / Offline test
 *       ↓
 * Optional backend sync
 *
 * IMPORTANT:
 * - IQ test is fully playable offline.
 * - User ID is NEVER trusted from URL/client for security.
 * - Backend must validate Telegram initData.
 * - This file contains no payment secrets.
 * ============================================================
 */

(() => {
    /* ========================================================
       CONFIG
       ======================================================== */

    const APP_NAME = "IQ TEST BOT";
    const STORAGE_KEY = "iq_test_bot_state_v1";
    const LAST_RESULT_KEY = "iq_test_bot_last_result_v1";

    const API_BASE = "/api";

    const TOTAL_QUESTIONS = 18;

    const DIFFICULTY = {
        EASY: "OSON",
        MEDIUM: "O‘RTA",
        HARD: "QIYIN"
    };

    const TELEGRAM = window.Telegram?.WebApp || null;

    /* ========================================================
       DOM HELPERS
       ======================================================== */

    const $ = (selector) => document.querySelector(selector);

    const $$ = (selector) => Array.from(
        document.querySelectorAll(selector)
    );

    function byId(id) {
        return document.getElementById(id);
    }

    /* ========================================================
       DOM REFERENCES
       ======================================================== */

    const DOM = {
        loading: byId("loading-screen"),
        main: byId("main-content"),

        screens: $$(".screen"),

        greeting: byId("user-greeting"),

        languageButton: byId("language-button"),

        startIq: byId("start-iq-button"),
        iqCard: byId("iq-card"),
        eqCard: byId("eq-card"),
        pqCard: byId("pq-card"),
        profileCard: byId("profile-card"),
        battleCard: byId("battle-card"),

        totalUsers: byId("total-users"),
        onlineUsers: byId("online-users"),

        iqIntroBack: byId("iq-intro-back"),
        beginIq: byId("begin-iq-test"),

        testExit: byId("test-exit"),
        questionCurrent: byId("question-current"),
        questionTotal: byId("question-total"),
        questionProgress: byId("question-progress"),
        testTimer: byId("test-timer"),

        difficultyLabel: byId("difficulty-label"),
        questionTitle: byId("question-title"),
        questionDescription: byId("question-description"),
        questionVisual: byId("question-visual"),
        answerOptions: byId("answer-options"),
        nextQuestion: byId("next-question"),

        continueAfterFive: byId("continue-after-five"),

        resultHome: byId("result-home"),
        resultScore: byId("result-score"),
        resultLevel: byId("result-level"),
        resultCorrect: byId("result-correct"),
        resultTime: byId("result-time"),

        metricLogic: byId("metric-logic"),
        metricLogicValue: byId("metric-logic-value"),

        metricPattern: byId("metric-pattern"),
        metricPatternValue: byId("metric-pattern-value"),

        metricNumber: byId("metric-number"),
        metricNumberValue: byId("metric-number-value"),

        metricSpatial: byId("metric-spatial"),
        metricSpatialValue: byId("metric-spatial-value"),

        resultStrength: byId("result-strength"),

        certificateButton: byId("certificate-button"),
        shareResultButton: byId("share-result-button"),
        retryIqButton: byId("retry-iq-button"),

        languageBack: byId("language-back"),
        languageOptions: $$(".language-option"),

        lockedTitle: byId("locked-title"),
        lockedDescription: byId("locked-description"),
        lockedAction: byId("locked-action"),

        errorMessage: byId("error-message"),
        errorRetry: byId("error-retry"),

        toast: byId("toast"),
        toastIcon: byId("toast-icon"),
        toastMessage: byId("toast-message"),

        modalBackdrop: byId("modal-backdrop"),
        modal: byId("modal"),
        modalClose: byId("modal-close"),
        modalIcon: byId("modal-icon"),
        modalTitle: byId("modal-title"),
        modalMessage: byId("modal-message"),
        modalCancel: byId("modal-cancel"),
        modalConfirm: byId("modal-confirm")
    };

    /* ========================================================
       APPLICATION STATE
       ======================================================== */

    const state = {
        initialized: false,

        user: {
            id: null,
            username: "",
            firstName: "",
            lastName: "",
            language: "uz"
        },

        stats: {
            total: 0,
            online: 0
        },

        currentScreen: "home",

        test: {
            active: false,
            sessionId: null,
            currentIndex: 0,
            answers: [],
            startedAt: null,
            elapsedBeforePause: 0,
            selectedAnswer: null,
            completed: false,
            celebrationShown: false,
            startedFromResume: false
        },

        lastResult: null,

        pendingModalAction: null,

        language: "uz",

        backend: {
            available: false
        }
    };

    let timerInterval = null;
    let toastTimer = null;

    /* ========================================================
       TELEGRAM INITIALIZATION
       ======================================================== */

    function initTelegram() {
        if (!TELEGRAM) {
            return;
        }

        try {
            TELEGRAM.ready();

            if (typeof TELEGRAM.expand === "function") {
                TELEGRAM.expand();
            }

            if (typeof TELEGRAM.disableVerticalSwipes === "function") {
                try {
                    TELEGRAM.disableVerticalSwipes();
                } catch (_) {
                    // Older Telegram clients may not support this.
                }
            }

            applyTelegramTheme();
        } catch (error) {
            console.warn("[IQ TEST BOT] Telegram init:", error);
        }
    }

    function applyTelegramTheme() {
        if (!TELEGRAM) {
            return;
        }

        const root = document.documentElement;

        const bg =
            TELEGRAM.backgroundColor ||
            "#060811";

        const secondary =
            TELEGRAM.secondaryBackgroundColor ||
            "#0a0d19";

        root.style.setProperty("--bg", bg);
        root.style.setProperty("--bg-soft", secondary);
    }

    function haptic(type = "light") {
        try {
            if (
                TELEGRAM &&
                TELEGRAM.HapticFeedback &&
                typeof TELEGRAM.HapticFeedback.impactOccurred === "function"
            ) {
                TELEGRAM.HapticFeedback.impactOccurred(type);
            }
        } catch (_) {
            // Haptic is optional.
        }
    }

    function notificationHaptic(type = "success") {
        try {
            if (
                TELEGRAM &&
                TELEGRAM.HapticFeedback &&
                typeof TELEGRAM.HapticFeedback.notificationOccurred === "function"
            ) {
                TELEGRAM.HapticFeedback.notificationOccurred(type);
            }
        } catch (_) {
            // Optional.
        }
    }

    /* ========================================================
       TELEGRAM USER
       ======================================================== */

    function getTelegramUser() {
        const user = TELEGRAM?.initDataUnsafe?.user;

        if (!user) {
            return null;
        }

        return {
            id: user.id || null,
            username: user.username || "",
            firstName: user.first_name || "",
            lastName: user.last_name || ""
        };
    }

    function getDisplayName() {
        const first =
            state.user.firstName ||
            getTelegramUser()?.firstName ||
            "";

        return first.trim() || "Do‘st";
    }

    /* ========================================================
       STORAGE
       ======================================================== */

    function safeStorageGet(key) {
        try {
            return localStorage.getItem(key);
        } catch (error) {
            console.warn("[IQ TEST BOT] localStorage read:", error);
            return null;
        }
    }

    function safeStorageSet(key, value) {
        try {
            localStorage.setItem(key, value);
            return true;
        } catch (error) {
            console.warn("[IQ TEST BOT] localStorage write:", error);
            return false;
        }
    }

    function safeStorageRemove(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.warn("[IQ TEST BOT] localStorage remove:", error);
        }
    }

    function loadLocalState() {
        const raw = safeStorageGet(STORAGE_KEY);

        if (!raw) {
            return;
        }

        try {
            const saved = JSON.parse(raw);

            if (
                saved &&
                typeof saved === "object"
            ) {
                if (saved.user) {
                    state.user = {
                        ...state.user,
                        ...saved.user
                    };
                }

                if (saved.test) {
                    state.test = {
                        ...state.test,
                        ...saved.test
                    };
                }

                if (saved.lastResult) {
                    state.lastResult = saved.lastResult;
                }

                if (saved.language) {
                    state.language = saved.language;
                    state.user.language = saved.language;
                }
            }
        } catch (error) {
            console.warn("[IQ TEST BOT] Invalid local state:", error);
            safeStorageRemove(STORAGE_KEY);
        }
    }

    function saveLocalState() {
        const payload = {
            user: state.user,
            test: state.test,
            lastResult: state.lastResult,
            language: state.language,
            savedAt: Date.now()
        };

        safeStorageSet(
            STORAGE_KEY,
            JSON.stringify(payload)
        );
    }

    function saveLastResult(result) {
        safeStorageSet(
            LAST_RESULT_KEY,
            JSON.stringify(result)
        );
    }

    /* ========================================================
       API LAYER
       ======================================================== */

    async function apiRequest(
        path,
        options = {}
    ) {
        const controller = new AbortController();

        const timeout = setTimeout(() => {
            controller.abort();
        }, options.timeout || 8000);

        try {
            const headers = {
                "Content-Type": "application/json",
                ...(options.headers || {})
            };

            if (TELEGRAM?.initData) {
                headers["X-Telegram-Init-Data"] =
                    TELEGRAM.initData;
            }

            const response = await fetch(
                `${API_BASE}${path}`,
                {
                    method: options.method || "GET",
                    headers,
                    body:
                        options.body !== undefined
                            ? JSON.stringify(options.body)
                            : undefined,
                    signal: controller.signal,
                    credentials: "same-origin"
                }
            );

            let data = null;

            const contentType =
                response.headers.get("content-type") || "";

            if (contentType.includes("application/json")) {
                data = await response.json();
            } else {
                const text = await response.text();

                data = {
                    success: response.ok,
                    text
                };
            }

            if (!response.ok) {
                const message =
                    data?.message ||
                    data?.error ||
                    data?.detail ||
                    `HTTP ${response.status}`;

                const err = new Error(
                    typeof message === "string" ? message : JSON.stringify(message)
                );

                err.status = response.status;
                err.data = data;

                throw err;
            }

            return data;
        } finally {
            clearTimeout(timeout);
        }
    }

    async function apiGet(path, timeout = 6000) {
        return apiRequest(path, {
            method: "GET",
            timeout
        });
    }

    async function apiPost(
        path,
        body,
        timeout = 8000
    ) {
        return apiRequest(path, {
            method: "POST",
            body,
            timeout
        });
    }

    /* ========================================================
       BACKEND BOOTSTRAP
       ======================================================== */

    async function loadBackendData() {
        try {
            const config = await apiGet("/config", 5000);

            state.backend.available = true;

            if (config?.language) {
                state.language =
                    config.language;
            }

            if (config?.stats) {
                updateLiveStats(config.stats);
            }

            if (config?.user) {
                mergeBackendUser(config.user);
            }
        } catch (error) {
            state.backend.available = false;

            console.info(
                "[IQ TEST BOT] Backend unavailable. Offline mode."
            );
        }
    }

    function mergeBackendUser(user) {
        if (!user || typeof user !== "object") {
            return;
        }

        state.user = {
            ...state.user,
            ...user
        };

        if (user.language) {
            state.language = user.language;
        }
    }

    async function loadUserProfile() {
        try {
            const data = await apiGet("/me", 5000);

            if (data?.user) {
                mergeBackendUser(data.user);
            }

            if (data?.lastResult) {
                state.lastResult = data.lastResult;
            }

            state.backend.available = true;
            saveLocalState();
        } catch (error) {
            // Offline is valid.
        }
    }

    async function loadLiveStats() {
        try {
            const data = await apiGet(
                "/stats/live",
                5000
            );

            if (data) {
                updateLiveStats({
                    total:
                        data.total ??
                        data.total_users ??
                        0,

                    online:
                        data.online ??
                        data.online_users ??
                        0
                });
            }

            state.backend.available = true;
        } catch (_) {
            // Keep previous/local values.
        }
    }

    function updateLiveStats(stats) {
        const total = Number(stats?.total || 0);
        const online = Number(stats?.online || 0);

        if (Number.isFinite(total)) {
            state.stats.total = Math.max(0, total);
        }

        if (Number.isFinite(online)) {
            state.stats.online = Math.max(0, online);
        }

        animateNumber(
            DOM.totalUsers,
            state.stats.total
        );

        animateNumber(
            DOM.onlineUsers,
            state.stats.online
        );
    }

    function animateNumber(element, target) {
        if (!element) {
            return;
        }

        const numericTarget = Math.max(
            0,
            Number(target) || 0
        );

        const current =
            Number(
                String(element.textContent)
                    .replace(/\D/g, "")
            ) || 0;

        if (current === numericTarget) {
            element.textContent =
                numericTarget.toLocaleString("uz-UZ");

            return;
        }

        const duration = 500;
        const startTime = performance.now();

        function frame(now) {
            const progress = Math.min(
                1,
                (now - startTime) / duration
            );

            const eased =
                1 - Math.pow(1 - progress, 3);

            const value = Math.round(
                current +
                (numericTarget - current) * eased
            );

            element.textContent =
                value.toLocaleString("uz-UZ");

            if (progress < 1) {
                requestAnimationFrame(frame);
            }
        }

        requestAnimationFrame(frame);
    }

    /* ========================================================
       SCREEN NAVIGATION
       ======================================================== */

    function showScreen(name) {
        const targetId = `screen-${name}`;

        DOM.screens.forEach((screen) => {
            screen.classList.toggle(
                "active",
                screen.id === targetId
            );
        });

        state.currentScreen = name;

        window.scrollTo({
            top: 0,
            behavior: "instant"
        });
    }

    function goHome() {
        stopTimer();

        if (state.test.active && !state.test.completed) {
            state.test.active = false;
            saveLocalState();
        }

        showScreen("home");
        updateHomeUI();
    }

    /* ========================================================
       HOME
       ======================================================== */

    function updateHomeUI() {
        if (DOM.greeting) {
            DOM.greeting.textContent =
                `Salom, ${getDisplayName()} 👋`;
        }

        updateUnlockStates();

        if (state.stats.total > 0) {
            DOM.totalUsers.textContent =
                state.stats.total.toLocaleString("uz-UZ");
        }

        if (state.stats.online > 0) {
            DOM.onlineUsers.textContent =
                state.stats.online.toLocaleString("uz-UZ");
        }
    }

    function updateUnlockStates() {
        const result = state.lastResult;

        const hasIQ =
            Boolean(
                result?.testType === "iq" ||
                result?.iqCompleted ||
                result?.score
            );

        const hasEQ =
            Boolean(result?.eqCompleted);

        const hasPQ =
            Boolean(result?.pqCompleted);

        updateLockedCard(
            DOM.eqCard,
            hasIQ
        );

        updateLockedCard(
            DOM.pqCard,
            hasEQ
        );

        updateLockedCard(
            DOM.profileCard,
            hasIQ && hasEQ && hasPQ
        );
    }

    function updateLockedCard(card, unlocked) {
        if (!card) {
            return;
        }

        if (unlocked) {
            card.classList.remove("locked-card");
            card.dataset.unlocked = "true";

            const badge =
                card.querySelector(".locked-badge");

            if (badge) {
                badge.textContent = "OCHIQ";
                badge.classList.remove("locked-badge");
                badge.classList.add("active-badge");
            }

            const arrow =
                card.querySelector(".test-arrow");

            if (arrow) {
                arrow.textContent = "→";
            }
        } else {
            card.classList.add("locked-card");
            card.dataset.unlocked = "false";
        }
    }

    /* ========================================================
       LANGUAGE
       ======================================================== */

    function openLanguage() {
        updateLanguageSelection();
        showScreen("language");
    }

    function updateLanguageSelection() {
        DOM.languageOptions.forEach((button) => {
            const active =
                button.dataset.language ===
                state.language;

            button.classList.toggle(
                "active",
                active
            );
        });
    }

    function setLanguage(language) {
        const allowed = ["uz", "ru", "en"];

        if (!allowed.includes(language)) {
            return;
        }

        state.language = language;
        state.user.language = language;

        saveLocalState();
        updateLanguageSelection();

        showToast(
            language === "uz"
                ? "Til O‘zbekcha qilib tanlandi."
                : language === "ru"
                    ? "Язык выбран: русский."
                    : "English selected.",
            "✓"
        );

        haptic("light");

        /*
         * Full multilingual content can later be switched
         * through a translation dictionary without changing
         * the application architecture.
         */
    }

    /* ========================================================
       IQ QUESTION BANK
       ======================================================== */

    /*
     * Every question has:
     * id
     * difficulty
     * category
     * title
     * description
     * render(container)
     * options
     * correct
     *
     * Options themselves are visual SVG/HTML objects.
     *
     * IMPORTANT: the `correct` index for every question below MUST be
     * kept identical to CORRECT_ANSWERS in bot.py (same order). If a
     * question is edited here, update bot.py in the same change.
     */

    const IQ_QUESTIONS = [

        /* ====================================================
           EASY 1
           ==================================================== */

        {
            id: "iq-e1",
            difficulty: DIFFICULTY.EASY,
            category: "pattern",
            title: "Qaysi katak yetishmayapti?",
            description:
                "Har bir qatorda shakllar bir xil tartibda siljiydi.",
            correct: 2,

            render(container) {
                container.innerHTML = matrixHTML([
                    ["circle", "square", "triangle"],
                    ["square", "triangle", "circle"],
                    ["triangle", "circle", "missing"]
                ]);
            },

            options: [
                shapeOption("circle"),
                shapeOption("square"),
                shapeOption("triangle"),
                shapeOption("diamond")
            ]
        },

        /* ====================================================
           EASY 2
           ==================================================== */

        {
            id: "iq-e2",
            difficulty: DIFFICULTY.EASY,
            category: "rotation",
            title: "Keyingi shaklni toping.",
            description:
                "Shakl har safar bir xil burchakka aylanmoqda.",
            correct: 1,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(
                            arrowShape(0)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            arrowShape(90)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            arrowShape(180)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            arrowShape(270)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            questionMark()
                        )}
                    </div>
                `;
            },

            options: [
                shapeOption("arrow-up"),
                shapeOption("arrow-right"),
                shapeOption("arrow-down"),
                shapeOption("arrow-left")
            ]
        },

        /* ====================================================
           EASY 3
           ==================================================== */

        {
            id: "iq-e3",
            difficulty: DIFFICULTY.EASY,
            category: "count",
            title: "Qaysi variant davom ettiradi?",
            description:
                "Nuqtalar soni har bosqichda bittaga oshmoqda.",
            correct: 2,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence count-sequence">
                        ${visualTile(dotsShape(1))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(dotsShape(2))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(dotsShape(3))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("dots-2"),
                shapeOption("dots-3"),
                shapeOption("dots-4"),
                shapeOption("dots-5")
            ]
        },

        /* ====================================================
           EASY 4
           ==================================================== */

        {
            id: "iq-e4",
            difficulty: DIFFICULTY.EASY,
            category: "position",
            title: "Nuqta qayerda bo‘lishi kerak?",
            description:
                "Nuqta har safar keyingi burchakka o‘tmoqda.",
            correct: 3,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(positionShape("tl"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(positionShape("tr"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(positionShape("br"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("position-tl"),
                shapeOption("position-tr"),
                shapeOption("position-br"),
                shapeOption("position-bl")
            ]
        },

        /* ====================================================
           EASY 5
           ==================================================== */

        {
            id: "iq-e5",
            difficulty: DIFFICULTY.EASY,
            category: "transformation",
            title: "Qaysi shakl keyingi bosqich?",
            description:
                "Har bosqichda tashqi shakl ichki shaklga aylanadi.",
            correct: 1,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(nestedShape("circle", "square"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(nestedShape("square", "triangle"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(nestedShape("triangle", "circle"))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("nested-circle-square"),
                shapeOption("nested-circle-triangle"),
                shapeOption("nested-square-circle"),
                shapeOption("nested-triangle-square")
            ]
        },

        /* ====================================================
           EASY 6
           ==================================================== */

        {
            id: "iq-e6",
            difficulty: DIFFICULTY.EASY,
            category: "odd-one-out",
            title: "Qaysi biri boshqalardan farq qiladi?",
            description:
                "To‘rtta shakldan faqat bittasining yo‘nalishi boshqacha.",
            correct: 3,

            render(container) {
                container.innerHTML = `
                    <div class="visual-options-row">
                        ${visualTile(arrowShape(0))}
                        ${visualTile(arrowShape(0))}
                        ${visualTile(arrowShape(0))}
                        ${visualTile(arrowShape(180))}
                    </div>
                `;
            },

            options: [
                shapeOption("arrow-up"),
                shapeOption("arrow-up"),
                shapeOption("arrow-up"),
                shapeOption("arrow-down")
            ]
        },

        /* ====================================================
           MEDIUM 7
           ==================================================== */

        {
            id: "iq-m1",
            difficulty: DIFFICULTY.MEDIUM,
            category: "matrix",
            title: "Matritsadagi qonuniyatni toping.",
            description:
                "Qator va ustunlar birgalikda o‘zgaradi.",
            correct: 2,

            render(container) {
                container.innerHTML = matrixHTML([
                    ["circle", "square", "circle-square"],
                    ["triangle", "circle", "triangle-circle"],
                    ["square", "triangle", "missing"]
                ]);
            },

            options: [
                shapeOption("circle-triangle"),
                shapeOption("square-circle"),
                shapeOption("square-triangle"),
                shapeOption("triangle-square")
            ]
        },

        /* ====================================================
           MEDIUM 8
           ==================================================== */

        {
            id: "iq-m2",
            difficulty: DIFFICULTY.MEDIUM,
            category: "rotation",
            title: "Burilish va to‘ldirishni aniqlang.",
            description:
                "Shakl 90° aylanadi va to‘ldirish navbatma-navbat o‘zgaradi.",
            correct: 3,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(
                            filledArrow(0, false)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            filledArrow(90, true)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            filledArrow(180, false)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("filled-arrow-up"),
                shapeOption("filled-arrow-right"),
                shapeOption("filled-arrow-down"),
                shapeOption("outline-arrow-left")
            ]
        },

        /* ====================================================
           MEDIUM 9
           ==================================================== */

        {
            id: "iq-m3",
            difficulty: DIFFICULTY.MEDIUM,
            category: "count",
            title: "Ikki xil qoida ishlayapti.",
            description:
                "Nuqtalar soni oshadi, rang esa navbat bilan almashadi.",
            correct: 1,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(
                            dotsColored(2, false)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            dotsColored(3, true)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(
                            dotsColored(4, false)
                        )}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("dots-4"),
                shapeOption("dots-5-filled"),
                shapeOption("dots-5"),
                shapeOption("dots-6")
            ]
        },

        /* ====================================================
           MEDIUM 10
           ==================================================== */

        {
            id: "iq-m4",
            difficulty: DIFFICULTY.MEDIUM,
            category: "position",
            title: "Yo‘nalish qayerga ko‘chadi?",
            description:
                "Shakl markaz atrofida soat strelkasi bo‘yicha yuradi.",
            correct: 0,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual">
                        ${gridPosition("tl")}
                        ${gridPosition("tc")}
                        ${gridPosition("tr")}
                        ${gridPosition("ml")}
                        ${gridPosition("c")}
                        ${gridPosition("mr")}
                        ${gridPosition("bl")}
                        ${gridPosition("bc")}
                        ${gridPosition("missing")}
                    </div>
                `;
            },

            options: [
                shapeOption("position-br"),
                shapeOption("position-bc"),
                shapeOption("position-bl"),
                shapeOption("position-c")
            ]
        },

        /* ====================================================
           MEDIUM 11
           ==================================================== */

        {
            id: "iq-m5",
            difficulty: DIFFICULTY.MEDIUM,
            category: "combination",
            title: "Ikki shakl birlashganda nima hosil bo‘ladi?",
            description:
                "Har bir yangi katak oldingi ikki shaklning kombinatsiyasidir.",
            correct: 2,

            render(container) {
                container.innerHTML = matrixHTML([
                    ["circle", "triangle", "circle-triangle"],
                    ["square", "circle", "square-circle"],
                    ["triangle", "square", "missing"]
                ]);
            },

            options: [
                shapeOption("triangle-circle"),
                shapeOption("circle-square"),
                shapeOption("triangle-square"),
                shapeOption("square-triangle")
            ]
        },

        /* ====================================================
           MEDIUM 12
           ==================================================== */

        {
            id: "iq-m6",
            difficulty: DIFFICULTY.MEDIUM,
            category: "fill",
            title: "Qaysi variant qonuniyatni saqlaydi?",
            description:
                "Har bir qadamda bo‘sh va to‘liq shakl almashadi.",
            correct: 1,

            render(container) {
                container.innerHTML = `
                    <div class="visual-sequence">
                        ${visualTile(circleFill(false))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(squareFill(true))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(triangleFill(false))}
                        <span class="sequence-arrow">→</span>
                        ${visualTile(questionMark())}
                    </div>
                `;
            },

            options: [
                shapeOption("circle-filled"),
                shapeOption("square-filled"),
                shapeOption("triangle-filled"),
                shapeOption("diamond-filled")
            ]
        },

        /* ====================================================
           HARD 13
           ==================================================== */

        {
            id: "iq-h1",
            difficulty: DIFFICULTY.HARD,
            category: "matrix",
            title: "Murakkab matritsani yeching.",
            description:
                "Shakl, yo‘nalish va son bir vaqtning o‘zida o‘zgaradi.",
            correct: 2,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual hard-matrix">
                        ${matrixCell("circle", 0, 1)}
                        ${matrixCell("square", 90, 2)}
                        ${matrixCell("triangle", 180, 3)}

                        ${matrixCell("square", 90, 2)}
                        ${matrixCell("triangle", 180, 3)}
                        ${matrixCell("circle", 270, 4)}

                        ${matrixCell("triangle", 180, 3)}
                        ${matrixCell("circle", 270, 4)}
                        ${matrixCell("missing", 0, 0)}
                    </div>
                `;
            },

            options: [
                shapeOption("hard-circle"),
                shapeOption("hard-square"),
                shapeOption("hard-triangle"),
                shapeOption("hard-diamond")
            ]
        },

        /* ====================================================
           HARD 14
           ==================================================== */

        {
            id: "iq-h2",
            difficulty: DIFFICULTY.HARD,
            category: "spatial",
            title: "Fazoviy burilishni aniqlang.",
            description:
                "Kub har safar 90° buriladi. Belgilangan yuzani kuzating.",
            correct: 3,

            render(container) {
                container.innerHTML = `
                    <div class="cube-sequence">
                        ${cubeSVG(0, "A")}
                        <span>→</span>
                        ${cubeSVG(90, "B")}
                        <span>→</span>
                        ${cubeSVG(180, "C")}
                        <span>→</span>
                        ${cubeSVG(270, "?")}
                    </div>
                `;
            },

            options: [
                shapeOption("cube-a"),
                shapeOption("cube-b"),
                shapeOption("cube-c"),
                shapeOption("cube-d")
            ]
        },

        /* ====================================================
           HARD 15
           ==================================================== */

        {
            id: "iq-h3",
            difficulty: DIFFICULTY.HARD,
            category: "double-rule",
            title: "Ikki qoidani bir vaqtning o‘zida toping.",
            description:
                "Har qatorda shakl aylanadi, har ustunda esa to‘ldirish o‘zgaradi.",
            correct: 1,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual hard-matrix">
                        ${matrixCell("circle", 0, 1)}
                        ${matrixCell("circle", 90, 0)}
                        ${matrixCell("circle", 180, 1)}

                        ${matrixCell("square", 90, 0)}
                        ${matrixCell("square", 180, 1)}
                        ${matrixCell("square", 270, 0)}

                        ${matrixCell("triangle", 180, 1)}
                        ${matrixCell("triangle", 270, 0)}
                        ${matrixCell("missing", 0, 0)}
                    </div>
                `;
            },

            options: [
                shapeOption("triangle-outline"),
                shapeOption("triangle-filled"),
                shapeOption("square-filled"),
                shapeOption("circle-outline")
            ]
        },

        /* ====================================================
           HARD 16
           ==================================================== */

        {
            id: "iq-h4",
            difficulty: DIFFICULTY.HARD,
            category: "combination",
            title: "Elementlar qanday qo‘shilmoqda?",
            description:
                "Har bir qatorda chap va o‘rta kataklar o‘ng katakda birlashadi.",
            correct: 0,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual hard-matrix">
                        ${matrixCell("circle", 0, 0)}
                        ${matrixCell("square", 0, 0)}
                        ${matrixCell("circle-square", 0, 0)}

                        ${matrixCell("triangle", 0, 0)}
                        ${matrixCell("circle", 0, 0)}
                        ${matrixCell("triangle-circle", 0, 0)}

                        ${matrixCell("square", 0, 0)}
                        ${matrixCell("triangle", 0, 0)}
                        ${matrixCell("missing", 0, 0)}
                    </div>
                `;
            },

            options: [
                shapeOption("square-triangle"),
                shapeOption("circle-square"),
                shapeOption("triangle-circle"),
                shapeOption("circle-triangle")
            ]
        },

        /* ====================================================
           HARD 17
           ==================================================== */

        {
            id: "iq-h5",
            difficulty: DIFFICULTY.HARD,
            category: "multi-rule",
            title: "Eng murakkab qonuniyatni toping.",
            description:
                "Shakl, burilish va nuqtalar soni uch xil qoida bo‘yicha o‘zgaradi.",
            correct: 2,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual hard-matrix">
                        ${complexCell("circle", 0, 1)}
                        ${complexCell("square", 90, 2)}
                        ${complexCell("triangle", 180, 3)}

                        ${complexCell("square", 90, 2)}
                        ${complexCell("triangle", 180, 3)}
                        ${complexCell("circle", 270, 4)}

                        ${complexCell("triangle", 180, 3)}
                        ${complexCell("circle", 270, 4)}
                        ${complexCell("missing", 0, 0)}
                    </div>
                `;
            },

            options: [
                shapeOption("complex-square"),
                shapeOption("complex-circle"),
                shapeOption("complex-triangle"),
                shapeOption("complex-diamond")
            ]
        },

        /* ====================================================
           HARD 18
           ==================================================== */

        {
            id: "iq-h6",
            difficulty: DIFFICULTY.HARD,
            category: "final-matrix",
            title: "Yakuniy puzzle.",
            description:
                "Qator va ustundagi o‘zgarishlarni birlashtirib javobni toping.",
            correct: 3,

            render(container) {
                container.innerHTML = `
                    <div class="matrix-visual final-matrix">
                        ${finalMatrixCell("circle", 0, 1, 1)}
                        ${finalMatrixCell("square", 90, 2, 0)}
                        ${finalMatrixCell("triangle", 180, 3, 1)}

                        ${finalMatrixCell("square", 90, 2, 0)}
                        ${finalMatrixCell("triangle", 180, 3, 1)}
                        ${finalMatrixCell("diamond", 270, 4, 0)}

                        ${finalMatrixCell("triangle", 180, 3, 1)}
                        ${finalMatrixCell("diamond", 270, 4, 0)}
                        ${finalMatrixCell("missing", 0, 0, 0)}
                    </div>
                `;
            },

            options: [
                shapeOption("final-circle"),
                shapeOption("final-square"),
                shapeOption("final-triangle"),
                shapeOption("final-diamond")
            ]
        }
    ];

    /* ========================================================
       VISUAL HELPERS
       ======================================================== */

    function svgWrap(content, extraClass = "") {
        return `
            <svg
                class="puzzle-svg ${extraClass}"
                viewBox="0 0 100 100"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
            >
                ${content}
            </svg>
        `;
    }

    function svgShape(
        type,
        {
            rotate = 0,
            filled = true,
            x = 50,
            y = 50,
            scale = 1
        } = {}
    ) {
        const fill = filled
            ? "rgba(167,139,250,0.9)"
            : "none";

        const stroke =
            "rgba(196,181,253,0.95)";

        const transform =
            `translate(${x} ${y}) rotate(${rotate}) scale(${scale}) translate(-50 -50)`;

        if (type === "circle") {
            return `
                <circle
                    cx="${x}"
                    cy="${y}"
                    r="${22 * scale}"
                    fill="${fill}"
                    stroke="${stroke}"
                    stroke-width="3"
                />
            `;
        }

        if (type === "square") {
            return `
                <rect
                    x="${x - 20 * scale}"
                    y="${y - 20 * scale}"
                    width="${40 * scale}"
                    height="${40 * scale}"
                    rx="${5 * scale}"
                    fill="${fill}"
                    stroke="${stroke}"
                    stroke-width="3"
                    transform="rotate(${rotate} ${x} ${y})"
                />
            `;
        }

        if (type === "triangle") {
            const points = trianglePoints(
                x,
                y,
                25 * scale,
                rotate
            );

            return `
                <polygon
                    points="${points}"
                    fill="${fill}"
                    stroke="${stroke}"
                    stroke-width="3"
                    stroke-linejoin="round"
                />
            `;
        }

        if (type === "diamond") {
            return `
                <polygon
                    points="
                        ${x},${y - 27 * scale}
                        ${x + 27 * scale},${y}
                        ${x},${y + 27 * scale}
                        ${x - 27 * scale},${y}
                    "
                    fill="${fill}"
                    stroke="${stroke}"
                    stroke-width="3"
                />
            `;
        }

        return `
            <circle
                cx="${x}"
                cy="${y}"
                r="20"
                fill="none"
                stroke="${stroke}"
                stroke-width="3"
            />
        `;
    }

    function trianglePoints(cx, cy, radius, rotation) {
        const points = [];

        for (let i = 0; i < 3; i++) {
            const angle =
                (
                    -90 +
                    rotation +
                    i * 120
                ) *
                Math.PI /
                180;

            points.push(
                `${cx + radius * Math.cos(angle)},` +
                `${cy + radius * Math.sin(angle)}`
            );
        }

        return points.join(" ");
    }

    function questionMark() {
        return svgWrap(`
            <text
                x="50"
                y="61"
                text-anchor="middle"
                font-size="48"
                font-weight="800"
                fill="rgba(167,139,250,0.9)"
            >?</text>
        `);
    }

    function arrowShape(rotation = 0) {
        return svgWrap(`
            <g transform="rotate(${rotation} 50 50)">
                <path
                    d="M50 16 L78 48 L62 48 L62 83 L38 83 L38 48 L22 48 Z"
                    fill="rgba(167,139,250,0.88)"
                    stroke="rgba(221,214,254,0.95)"
                    stroke-width="3"
                    stroke-linejoin="round"
                />
            </g>
        `);
    }

    function filledArrow(rotation, filled) {
        return svgWrap(`
            <g transform="rotate(${rotation} 50 50)">
                <path
                    d="M50 15 L78 48 L63 48 L63 84 L37 84 L37 48 L22 48 Z"
                    fill="${filled ? "rgba(167,139,250,0.9)" : "none"}"
                    stroke="rgba(221,214,254,0.95)"
                    stroke-width="3"
                    stroke-linejoin="round"
                />
            </g>
        `);
    }

    function dotsShape(count) {
        const positions = [
            [35, 35],
            [65, 35],
            [50, 50],
            [35, 65],
            [65, 65],
            [50, 28]
        ];

        const circles = positions
            .slice(0, count)
            .map(([x, y]) => `
                <circle
                    cx="${x}"
                    cy="${y}"
                    r="7"
                    fill="rgba(167,139,250,0.9)"
                />
            `)
            .join("");

        return svgWrap(circles);
    }

    function dotsColored(count, filled) {
        const positions = [
            [35, 35],
            [65, 35],
            [50, 50],
            [35, 65],
            [65, 65],
            [50, 28]
        ];

        const circles = positions
            .slice(0, count)
            .map(([x, y]) => `
                <circle
                    cx="${x}"
                    cy="${y}"
                    r="7"
                    fill="${filled
                        ? "rgba(79,140,255,0.9)"
                        : "none"}"
                    stroke="rgba(196,181,253,0.95)"
                    stroke-width="3"
                />
            `)
            .join("");

        return svgWrap(circles);
    }

    function positionShape(position) {
        const positions = {
            tl: [25, 25],
            tr: [75, 25],
            br: [75, 75],
            bl: [25, 75],
            c: [50, 50]
        };

        const [x, y] =
            positions[position] ||
            positions.c;

        return svgWrap(`
            <rect
                x="12"
                y="12"
                width="76"
                height="76"
                rx="10"
                fill="none"
                stroke="rgba(255,255,255,0.08)"
                stroke-width="2"
            />
            <circle
                cx="${x}"
                cy="${y}"
                r="10"
                fill="rgba(167,139,250,0.95)"
            />
        `);
    }

    function nestedShape(outer, inner) {
        return svgWrap(
            svgShape(outer, {
                filled: false,
                scale: 0.9
            }) +
            svgShape(inner, {
                filled: true,
                scale: 0.38
            })
        );
    }

    function circleFill(filled) {
        return svgWrap(
            svgShape("circle", {
                filled
            })
        );
    }

    function shapeOption(type) {
        return {
            type,
            html: optionVisual(type)
        };
    }

    function optionVisual(type) {
        switch (type) {
            case "circle":
                return svgShape("circle");

            case "square":
                return svgShape("square");

            case "triangle":
                return svgShape("triangle");

            case "diamond":
                return svgShape("diamond");

            case "arrow-up":
                return arrowShape(0);

            case "arrow-right":
                return arrowShape(90);

            case "arrow-down":
                return arrowShape(180);

            case "arrow-left":
                return arrowShape(270);

            case "dots-2":
                return dotsShape(2);

            case "dots-3":
                return dotsShape(3);

            case "dots-4":
                return dotsShape(4);

            case "dots-5":
                return dotsShape(5);

            case "dots-5-filled":
                return dotsColored(5, true);

            case "position-tl":
                return positionShape("tl");

            case "position-tr":
                return positionShape("tr");

            case "position-br":
                return positionShape("br");

            case "position-bl":
                return positionShape("bl");

            case "nested-circle-square":
                return nestedShape("circle", "square");

            case "nested-circle-triangle":
                return nestedShape("circle", "triangle");

            case "nested-square-circle":
                return nestedShape("square", "circle");

            case "nested-triangle-square":
                return nestedShape("triangle", "square");

            case "circle-triangle":
                return nestedShape("circle", "triangle");

            case "triangle-circle":
                return nestedShape("triangle", "circle");

            case "square-circle":
                return nestedShape("square", "circle");

            case "square-triangle":
                return nestedShape("square", "triangle");

            case "triangle-square":
                return nestedShape("triangle", "square");

            case "filled-arrow-up":
                return filledArrow(0, true);

            case "filled-arrow-right":
                return filledArrow(90, true);

            case "filled-arrow-down":
                return filledArrow(180, true);

            case "outline-arrow-left":
                return filledArrow(270, false);

            case "circle-filled":
                return circleFill(true);

            case "square-filled":
                return svgWrap(
                    svgShape("square", {
                        filled: true
                    })
                );

            case "triangle-filled":
                return svgWrap(
                    svgShape("triangle", {
                        filled: true
                    })
                );

            case "diamond-filled":
                return svgWrap(
                    svgShape("diamond", {
                        filled: true
                    })
                );

            case "hard-circle":
                return matrixOptionShape("circle", 0, 4);

            case "hard-square":
                return matrixOptionShape("square", 90, 5);

            case "hard-triangle":
                return matrixOptionShape("triangle", 180, 6);

            case "hard-diamond":
                return matrixOptionShape("diamond", 270, 7);

            case "triangle-outline":
                return svgWrap(
                    svgShape("triangle", {
                        filled: false
                    })
                );

            case "triangle-filled":
                return svgWrap(
                    svgShape("triangle", {
                        filled: true
                    })
                );

            case "cube-a":
                return cubeSVG(0, "A");

            case "cube-b":
                return cubeSVG(90, "B");

            case "cube-c":
                return cubeSVG(180, "C");

            case "cube-d":
                return cubeSVG(270, "D");

            case "complex-square":
                return complexCell("square", 90, 5);

            case "complex-circle":
                return complexCell("circle", 180, 5);

            case "complex-triangle":
                return complexCell("triangle", 270, 5);

            case "complex-diamond":
                return complexCell("diamond", 0, 5);

            case "final-circle":
                return finalOption("circle", 0, 5, 1);

            case "final-square":
                return finalOption("square", 90, 5, 0);

            case "final-triangle":
                return finalOption("triangle", 180, 5, 1);

            case "final-diamond":
                return finalOption("diamond", 270, 5, 0);

            default:
                return questionMark();
        }
    }

    function visualTile(content) {
        return `
            <div class="puzzle-tile">
                ${content}
            </div>
        `;
    }

    function matrixHTML(cells) {
        return `
            <div class="matrix-visual">
                ${cells.map((row) =>
                    row.map((cell) =>
                        matrixCell(
                            cell,
                            0,
                            0
                        )
                    ).join("")
                ).join("")}
            </div>
        `;
    }

    function matrixCell(
        type,
        rotation = 0,
        count = 0
    ) {
        if (type === "missing") {
            return `
                <div class="matrix-cell missing-cell">
                    <span>?</span>
                </div>
            `;
        }

        return `
            <div class="matrix-cell">
                ${matrixOptionShape(
                    type,
                    rotation,
                    count
                )}
            </div>
        `;
    }

    function matrixOptionShape(
        type,
        rotation = 0,
        count = 0
    ) {
        let content =
            svgShape(type, {
                rotate: rotation,
                filled: true,
                scale: 0.7
            });

        if (count > 0) {
            content += `
                <text
                    x="87"
                    y="18"
                    text-anchor="middle"
                    font-size="11"
                    font-weight="800"
                    fill="rgba(196,181,253,0.9)"
                >${count}</text>
            `;
        }

        return svgWrap(content);
    }

    function gridPosition(position) {
        if (position === "missing") {
            return `
                <div class="matrix-cell missing-cell">
                    <span>?</span>
                </div>
            `;
        }

        const positions = {
            tl: [28, 28],
            tc: [50, 28],
            tr: [72, 28],
            ml: [28, 50],
            c: [50, 50],
            mr: [72, 50],
            bl: [28, 72],
            bc: [50, 72],
            br: [72, 72]
        };

        const [x, y] =
            positions[position] ||
            positions.c;

        return `
            <div class="matrix-cell">
                ${svgWrap(`
                    <rect
                        x="15"
                        y="15"
                        width="70"
                        height="70"
                        rx="9"
                        fill="none"
                        stroke="rgba(255,255,255,0.06)"
                        stroke-width="2"
                    />
                    <circle
                        cx="${x}"
                        cy="${y}"
                        r="9"
                        fill="rgba(167,139,250,0.95)"
                    />
                `)}
            </div>
        `;
    }

    function complexCell(
        type,
        rotation,
        count
    ) {
        if (type === "missing") {
            return `
                <div class="matrix-cell missing-cell">
                    <span>?</span>
                </div>
            `;
        }

        return `
            <div class="matrix-cell">
                ${svgWrap(`
                    ${svgShape(type, {
                        rotate: rotation,
                        filled: true,
                        scale: 0.68
                    })}
                    <g fill="rgba(34,211,238,0.9)">
                        ${Array.from(
                            { length: Math.min(count, 4) },
                            (_, i) => `
                                <circle
                                    cx="${34 + i * 11}"
                                    cy="82"
                                    r="3"
                                />
                            `
                        ).join("")}
                    </g>
                `)}
            </div>
        `;
    }

    function finalMatrixCell(
        type,
        rotation,
        count,
        filled
    ) {
        if (type === "missing") {
            return `
                <div class="matrix-cell missing-cell">
                    <span>?</span>
                </div>
            `;
        }

        return `
            <div class="matrix-cell">
                ${svgWrap(`
                    ${svgShape(type, {
                        rotate: rotation,
                        filled: Boolean(filled),
                        scale: 0.68
                    })}
                    <text
                        x="86"
                        y="17"
                        text-anchor="middle"
                        font-size="10"
                        font-weight="800"
                        fill="rgba(34,211,238,0.9)"
                    >${count}</text>
                `)}
            </div>
        `;
    }

    function finalOption(
        type,
        rotation,
        count,
        filled
    ) {
        return svgWrap(`
            ${svgShape(type, {
                rotate: rotation,
                filled: Boolean(filled),
                scale: 0.72
            })}
            <text
                x="86"
                y="17"
                text-anchor="middle"
                font-size="11"
                font-weight="800"
                fill="rgba(34,211,238,0.9)"
            >${count}</text>
        `);
    }

    function cubeSVG(rotation = 0, label = "") {
        return svgWrap(`
            <g transform="rotate(${rotation} 50 50)">
                <polygon
                    points="50,12 84,31 84,69 50,88 16,69 16,31"
                    fill="rgba(139,92,246,0.12)"
                    stroke="rgba(196,181,253,0.9)"
                    stroke-width="3"
                />

                <polygon
                    points="50,12 84,31 50,50 16,31"
                    fill="rgba(79,140,255,0.2)"
                    stroke="rgba(196,181,253,0.7)"
                    stroke-width="2"
                />

                <polygon
                    points="16,31 50,50 50,88 16,69"
                    fill="rgba(34,211,238,0.12)"
                    stroke="rgba(196,181,253,0.7)"
                    stroke-width="2"
                />

                <polygon
                    points="50,50 84,31 84,69 50,88"
                    fill="rgba(167,139,250,0.18)"
                    stroke="rgba(196,181,253,0.7)"
                    stroke-width="2"
                />

                <text
                    x="50"
                    y="58"
                    text-anchor="middle"
                    font-size="18"
                    font-weight="900"
                    fill="rgba(255,255,255,0.92)"
                >${label}</text>
            </g>
        `);
    }

    /* ========================================================
       QUESTION RENDERING
       ======================================================== */

    function getCurrentQuestion() {
        return IQ_QUESTIONS[
            state.test.currentIndex
        ];
    }

    function renderCurrentQuestion() {
        const question =
            getCurrentQuestion();

        if (!question) {
            finishTest();
            return;
        }

        const index =
            state.test.currentIndex;

        DOM.questionCurrent.textContent =
            String(index + 1);

        DOM.questionTotal.textContent =
            String(TOTAL_QUESTIONS);

        DOM.questionProgress.style.width =
            `${((index + 1) / TOTAL_QUESTIONS) * 100}%`;

        DOM.difficultyLabel.textContent =
            question.difficulty;

        DOM.questionTitle.textContent =
            question.title;

        DOM.questionDescription.textContent =
            question.description;

        DOM.questionVisual.innerHTML = "";

        try {
            question.render(
                DOM.questionVisual
            );
        } catch (error) {
            console.error(
                "[IQ TEST BOT] Puzzle render error:",
                error
            );

            DOM.questionVisual.innerHTML =
                `<div class="puzzle-error">
                    Puzzle yuklanmadi.
                </div>`;
        }

        renderAnswerOptions(question);

        state.test.selectedAnswer =
            Number.isInteger(
                state.test.answers[index]
            )
                ? state.test.answers[index]
                : null;

        if (
            state.test.selectedAnswer !== null
        ) {
            selectAnswerUI(
                state.test.selectedAnswer,
                false
            );
        }

        DOM.nextQuestion.disabled =
            state.test.selectedAnswer === null;

        updateNextButtonText();

        saveLocalState();
    }

    function renderAnswerOptions(question) {
        DOM.answerOptions.innerHTML = "";

        question.options.forEach(
            (option, index) => {
                const button =
                    document.createElement("button");

                button.type = "button";
                button.className =
                    "answer-option";

                button.dataset.index =
                    String(index);

                button.innerHTML = `
                    <span class="answer-letter">
                        ${String.fromCharCode(65 + index)}
                    </span>

                    <span class="answer-visual">
                        ${option.html}
                    </span>
                `;

                button.addEventListener(
                    "click",
                    () => {
                        selectAnswer(
                            index
                        );
                    }
                );

                DOM.answerOptions.appendChild(
                    button
                );
            }
        );
    }

    function selectAnswer(index) {
        const question =
            getCurrentQuestion();

        if (
            !question ||
            !Number.isInteger(index) ||
            index < 0 ||
            index >= question.options.length
        ) {
            return;
        }

        state.test.selectedAnswer =
            index;

        state.test.answers[
            state.test.currentIndex
        ] = index;

        selectAnswerUI(index, true);

        DOM.nextQuestion.disabled =
            false;

        haptic("light");

        saveLocalState();

        /*
         * Best-effort background sync of progress after every answer.
         * This is fire-and-forget: the test never waits for the network
         * (spec section 22/23). If it fails (offline), the full answer
         * set is synced again at finish time.
         */
        syncAnswersInBackground();
    }

    function selectAnswerUI(
        selectedIndex,
        withHaptic = false
    ) {
        const buttons =
            $$(".answer-option");

        buttons.forEach((button) => {
            const index =
                Number(button.dataset.index);

            button.classList.toggle(
                "selected",
                index === selectedIndex
            );
        });

        if (withHaptic) {
            haptic("light");
        }
    }

    function updateNextButtonText() {
        if (!DOM.nextQuestion) {
            return;
        }

        const isLast =
            state.test.currentIndex ===
            TOTAL_QUESTIONS - 1;

        DOM.nextQuestion.innerHTML = isLast
            ? `YAKUNLASH <span>✓</span>`
            : `DAVOM ETISH <span>→</span>`;
    }

    /* ========================================================
       TEST SESSION
       ======================================================== */

    function createSessionId() {
        if (
            typeof crypto !== "undefined" &&
            typeof crypto.randomUUID === "function"
        ) {
            return crypto.randomUUID();
        }

        return [
            Date.now().toString(36),
            Math.random()
                .toString(36)
                .slice(2),
            Math.random()
                .toString(36)
                .slice(2)
        ].join("-");
    }

    function hasResumableTest() {
        if (!state.test) {
            return false;
        }

        if (!state.test.active) {
            return false;
        }

        if (state.test.completed) {
            return false;
        }

        if (
            !Number.isInteger(
                state.test.currentIndex
            )
        ) {
            return false;
        }

        if (
            state.test.currentIndex < 0 ||
            state.test.currentIndex >= TOTAL_QUESTIONS
        ) {
            return false;
        }

        return true;
    }

    async function startIqFlow() {
        haptic("medium");

        if (hasResumableTest()) {
            openResumeModal();
            return;
        }

        showScreen("iq-intro");
    }

    function openResumeModal() {
        openModal({
            icon: "🧠",
            title: "Test davom etmoqda",
            message:
                `Siz ${state.test.currentIndex + 1}-savolgacha yetgansiz. ` +
                "Testni davom ettirasizmi?",

            confirmText: "DAVOM ETISH",
            cancelText: "YANGI TEST",

            onConfirm: () => {
                resumeIqTest();
            },

            onCancel: () => {
                resetTestState();
                showScreen("iq-intro");
            }
        });
    }

    async function beginIqTest() {
        haptic("medium");

        resetTestState();

        state.test.active = true;
        state.test.sessionId =
            createSessionId();

        state.test.currentIndex = 0;
        state.test.answers = [];
        state.test.startedAt = Date.now();
        state.test.elapsedBeforePause = 0;
        state.test.selectedAnswer = null;
        state.test.completed = false;
        state.test.celebrationShown = false;
        state.test.startedFromResume = false;

        saveLocalState();

        showScreen("iq-test");

        startTimer();
        renderCurrentQuestion();

        /*
         * Backend is optional here.
         * The test itself does not wait for it.
         */
        syncSessionStart();
    }

    function resumeIqTest() {
        if (!hasResumableTest()) {
            beginIqTest();
            return;
        }

        state.test.startedFromResume = true;
        state.test.active = true;

        showScreen("iq-test");

        startTimer();
        renderCurrentQuestion();

        haptic("light");
    }

    function resetTestState() {
        stopTimer();

        state.test = {
            active: false,
            sessionId: null,
            currentIndex: 0,
            answers: [],
            startedAt: null,
            elapsedBeforePause: 0,
            selectedAnswer: null,
            completed: false,
            celebrationShown: false,
            startedFromResume: false
        };

        saveLocalState();
    }

    /* ========================================================
       TIMER
       ======================================================== */

    function startTimer() {
        stopTimer();

        timerInterval =
            setInterval(
                updateTimer,
                1000
            );

        updateTimer();
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function getElapsedSeconds() {
        if (!state.test.startedAt) {
            return Math.max(
                0,
                Number(
                    state.test.elapsedBeforePause
                ) || 0
            );
        }

        const current =
            Math.floor(
                (Date.now() -
                    state.test.startedAt) /
                    1000
            );

        return Math.max(
            0,
            current +
                Number(
                    state.test.elapsedBeforePause
                ) ||
                0
        );
    }

    function updateTimer() {
        if (!state.test.active) {
            return;
        }

        const seconds =
            getElapsedSeconds();

        DOM.testTimer.textContent =
            formatTime(seconds);
    }

    function formatTime(totalSeconds) {
        const seconds = Math.max(
            0,
            Math.floor(
                Number(totalSeconds) || 0
            )
        );

        const hours =
            Math.floor(seconds / 3600);

        const minutes =
            Math.floor(
                (seconds % 3600) / 60
            );

        const remaining =
            seconds % 60;

        if (hours > 0) {
            return [
                String(hours).padStart(2, "0"),
                String(minutes).padStart(2, "0"),
                String(remaining).padStart(2, "0")
            ].join(":");
        }

        return [
            String(minutes).padStart(2, "0"),
            String(remaining).padStart(2, "0")
        ].join(":");
    }

    /* ========================================================
       NEXT QUESTION
       ======================================================== */

    function nextQuestion() {
        if (
            state.test.selectedAnswer === null
        ) {
            showToast(
                "Avval javobni tanlang.",
                "!"
            );

            haptic("heavy");
            return;
        }

        const current =
            state.test.currentIndex;

        /*
         * Celebration is shown after Q5,
         * before opening Q6.
         */
        if (
            current === 4 &&
            !state.test.celebrationShown
        ) {
            state.test.celebrationShown = true;

            saveLocalState();

            showCelebration();

            return;
        }

        if (
            current >= TOTAL_QUESTIONS - 1
        ) {
            finishTest();
            return;
        }

        state.test.currentIndex += 1;

        state.test.selectedAnswer =
            Number.isInteger(
                state.test.answers[
                    state.test.currentIndex
                ]
            )
                ? state.test.answers[
                    state.test.currentIndex
                ]
                : null;

        saveLocalState();

        renderCurrentQuestion();

        haptic("light");
    }

    function continueAfterFive() {
        state.test.currentIndex = 5;

        state.test.selectedAnswer =
            Number.isInteger(
                state.test.answers[5]
            )
                ? state.test.answers[5]
                : null;

        state.test.active = true;

        saveLocalState();

        showScreen("iq-test");

        startTimer();
        renderCurrentQuestion();

        haptic("medium");
    }

    function showCelebration() {
        stopTimer();

        showScreen("celebration");

        notificationHaptic("success");
    }

    /* ========================================================
       EXIT TEST
       ======================================================== */

    function confirmExitTest() {
        openModal({
            icon: "⚠️",
            title: "Testdan chiqasizmi?",
            message:
                "Progressingiz saqlanadi. Keyin testni davom ettirishingiz mumkin.",

            confirmText: "CHIQISH",
            cancelText: "DAVOM ETISH",

            onConfirm: () => {
                state.test.active = false;

                /*
                 * Preserve progress so user can resume.
                 */
                saveLocalState();

                goHome();
            }
        });
    }

    /* ========================================================
       FINISH TEST
       ======================================================== */

    async function finishTest() {
        if (state.test.completed) {
            return;
        }

        if (
            state.test.answers.length <
            TOTAL_QUESTIONS
        ) {
            showToast(
                "Barcha savollarga javob bering.",
                "!"
            );

            return;
        }

        stopTimer();

        state.test.active = false;
        state.test.completed = true;

        const elapsed =
            getElapsedSeconds();

        /*
         * Local, offline-safe result. This gives the metric breakdown
         * (logic/pattern/number/spatial) shown in the UI, and acts as a
         * provisional score if the backend cannot be reached yet.
         * The authoritative score/correct/elapsed always come from the
         * server once synced — see submitResultToBackend() below.
         */
        const localResult =
            calculateResult(
                state.test.answers,
                elapsed
            );

        state.lastResult = localResult;

        saveLastResult(localResult);
        saveLocalState();

        showScreen("analyzing");

        notificationHaptic("success");

        /*
         * Small visual analysis period. Runs the real sync underneath it,
         * so the delay is not wasted time.
         */
        const [finalResult] = await Promise.all([
            submitResultToBackend(localResult),
            wait(1600)
        ]);

        state.lastResult = finalResult;

        saveLastResult(finalResult);
        saveLocalState();

        renderResult(finalResult);

        showScreen("result");

        if (!finalResult.synced) {
            showToast(
                "Internet yo‘q — natija vaqtinchalik. Internet qaytganda yakunlanadi.",
                "⚡",
                3500
            );
        }
    }

    /*
     * Sends the full answer set to the backend and asks it to compute
     * the authoritative score (spec sections 29-31, 78, 93). The backend
     * is the only source of truth for score/correct/elapsed; this
     * function overlays those authoritative fields on top of the local
     * result (which still supplies the category breakdown).
     *
     * Returns the merged result. Never throws — on any failure it
     * returns the local result unchanged with `synced: false`, so the
     * offline flow (spec section 25/79) keeps working.
     */
    async function submitResultToBackend(localResult) {
        try {
            // Make sure a session exists server-side even if the initial
            // /session/start call failed earlier while offline.
            await apiPost(
                "/session/start",
                { language: state.language },
                6000
            );

            await apiPost(
                "/session/sync",
                { answers: localResult.answers },
                8000
            );

            const battleId =
                state.test.battleId || null;

            const finish = await apiPost(
                "/session/finish",
                battleId ? { battle_id: battleId } : {},
                10000
            );

            state.backend.available = true;

            return {
                ...localResult,
                score: Number(finish.iq ?? localResult.score),
                level: finish.level || localResult.level,
                correct: Number(finish.correct ?? localResult.correct),
                elapsedSeconds: Number(finish.elapsed ?? localResult.elapsedSeconds),
                elapsed: formatTime(
                    Number(finish.elapsed ?? localResult.elapsedSeconds)
                ),
                rank: finish.rank ?? null,
                synced: true
            };
        } catch (error) {
            console.info(
                "[IQ TEST BOT] Result sync failed, will retry when online.",
                error
            );

            return {
                ...localResult,
                synced: false
            };
        }
    }

    /*
     * Retries a pending (unsynced) result. Called when connectivity
     * returns (spec section 25: "Internet qaytgach: local state -> sync
     * -> backend").
     */
    async function retryPendingSync() {
        const result = state.lastResult;

        if (!result || result.synced) {
            return;
        }

        const finalResult =
            await submitResultToBackend(result);

        state.lastResult = finalResult;

        saveLastResult(finalResult);
        saveLocalState();

        if (finalResult.synced) {
            if (state.currentScreen === "result") {
                renderResult(finalResult);
            }

            showToast(
                "Natijangiz serverga yuklandi.",
                "✓"
            );
        }
    }

    /*
     * Best-effort per-answer sync. Never blocks the UI and never surfaces
     * errors — the full answer set is re-sent (and is authoritative) at
     * finish time regardless of whether these succeed.
     */
    async function syncAnswersInBackground() {
        if (!state.test.active) {
            return;
        }

        try {
            await apiPost(
                "/session/sync",
                { answers: state.test.answers },
                4000
            );

            state.backend.available = true;
        } catch (_) {
            // Ignored on purpose — offline-first.
        }
    }

    function calculateResult(
        answers,
        elapsedSeconds
    ) {
        let correct = 0;
        let weightedCorrect = 0;
        let totalWeight = 0;

        const categories = {
            logic: {
                correct: 0,
                total: 0
            },

            pattern: {
                correct: 0,
                total: 0
            },

            number: {
                correct: 0,
                total: 0
            },

            spatial: {
                correct: 0,
                total: 0
            }
        };

        IQ_QUESTIONS.forEach(
            (question, index) => {
                const answer =
                    answers[index];

                const weight =
                    question.difficulty === DIFFICULTY.EASY
                        ? 1
                        : question.difficulty === DIFFICULTY.MEDIUM
                            ? 2
                            : 3;

                totalWeight += weight;

                const isCorrect =
                    Number(answer) ===
                    Number(question.correct);

                if (isCorrect) {
                    correct += 1;
                    weightedCorrect += weight;
                }

                const category =
                    normalizeCategory(
                        question.category
                    );

                if (categories[category]) {
                    categories[category].total += 1;

                    if (isCorrect) {
                        categories[category].correct += 1;
                    }
                }
            }
        );

        const percentage =
            totalWeight > 0
                ? weightedCorrect /
                    totalWeight
                : 0;

        /*
         * IQ-style score.
         *
         * This is intentionally NOT a clinical/
         * standardized IQ measurement. It mirrors the
         * backend's formula (70..145) so the provisional
         * offline score is close to what the server will
         * confirm once synced.
         */
        const score =
            clamp(
                Math.round(
                    70 +
                    percentage * 75
                ),
                70,
                145
            );

        const metrics =
            calculateMetrics(
                categories,
                answers
            );

        const level =
            getScoreLevel(score);

        const strength =
            getStrongestMetric(metrics);

        return {
            id: createSessionId(),

            testType: "iq",

            score,
            level,

            correct,
            total: TOTAL_QUESTIONS,

            elapsedSeconds,

            elapsed: formatTime(
                elapsedSeconds
            ),

            metrics,

            strength,

            answers: [...answers],

            completedAt: Date.now(),

            iqCompleted: true,

            synced: false,

            /*
             * Used later by EQ/PQ unlock logic.
             */
            eqCompleted:
                Boolean(
                    state.lastResult?.eqCompleted
                ),

            pqCompleted:
                Boolean(
                    state.lastResult?.pqCompleted
                ),

            sessionId:
                state.test.sessionId
        };
    }

    function normalizeCategory(category) {
        if (
            category === "pattern" ||
            category === "matrix" ||
            category === "combination" ||
            category === "transformation" ||
            category === "double-rule" ||
            category === "multi-rule" ||
            category === "final-matrix"
        ) {
            return "pattern";
        }

        if (
            category === "count"
        ) {
            return "number";
        }

        if (
            category === "spatial"
        ) {
            return "spatial";
        }

        return "logic";
    }

    function calculateMetrics(
        categories,
        answers
    ) {
        const getPercentage =
            (key) => {
                const item =
                    categories[key];

                if (
                    !item ||
                    item.total === 0
                ) {
                    return 0;
                }

                return Math.round(
                    (
                        item.correct /
                        item.total
                    ) * 100
                );
            };

        const logic =
            clamp(
                getPercentage("logic"),
                0,
                100
            );

        const pattern =
            clamp(
                getPercentage("pattern"),
                0,
                100
            );

        const number =
            clamp(
                getPercentage("number"),
                0,
                100
            );

        const spatial =
            clamp(
                getPercentage("spatial"),
                0,
                100
            );

        return {
            logic,
            pattern,
            number,
            spatial
        };
    }

    function getScoreLevel(score) {
        if (score >= 135) {
            return "JUDA YUQORI DARAJA";
        }

        if (score >= 120) {
            return "YUQORI DARAJA";
        }

        if (score >= 105) {
            return "YAXSHI DARAJA";
        }

        if (score >= 90) {
            return "O‘RTACHA DARAJA";
        }

        return "RIVOJLANTIRISH MUMKIN";
    }

    function getStrongestMetric(metrics) {
        const list = [
            {
                key: "logic",
                value: metrics.logic,
                name: "Logical reasoning"
            },

            {
                key: "pattern",
                value: metrics.pattern,
                name: "Pattern recognition"
            },

            {
                key: "number",
                value: metrics.number,
                name: "Numerical reasoning"
            },

            {
                key: "spatial",
                value: metrics.spatial,
                name: "Spatial reasoning"
            }
        ];

        list.sort(
            (a, b) =>
                b.value - a.value
        );

        return list[0]?.name ||
            "Logical reasoning";
    }

    /* ========================================================
       RESULT RENDERING
       ======================================================== */

    function renderResult(result) {
        if (!result) {
            return;
        }

        DOM.resultScore.textContent =
            String(result.score);

        DOM.resultLevel.textContent =
            result.level;

        DOM.resultCorrect.textContent =
            `${result.correct} / ${result.total}`;

        DOM.resultTime.textContent =
            result.elapsed;

        setMetric(
            DOM.metricLogic,
            DOM.metricLogicValue,
            result.metrics.logic
        );

        setMetric(
            DOM.metricPattern,
            DOM.metricPatternValue,
            result.metrics.pattern
        );

        setMetric(
            DOM.metricNumber,
            DOM.metricNumberValue,
            result.metrics.number
        );

        setMetric(
            DOM.metricSpatial,
            DOM.metricSpatialValue,
            result.metrics.spatial
        );

        DOM.resultStrength.textContent =
            result.strength;

        requestAnimationFrame(() => {
            animateResultMetrics(result);
        });
    }

    function setMetric(
        bar,
        label,
        value
    ) {
        const safeValue =
            clamp(
                Number(value) || 0,
                0,
                100
            );

        if (bar) {
            bar.style.width =
                `${safeValue}%`;
        }

        if (label) {
            label.textContent =
                `${safeValue}%`;
        }
    }

    function animateResultMetrics(result) {
        const metrics = [
            [
                DOM.metricLogic,
                result.metrics.logic
            ],
            [
                DOM.metricPattern,
                result.metrics.pattern
            ],
            [
                DOM.metricNumber,
                result.metrics.number
            ],
            [
                DOM.metricSpatial,
                result.metrics.spatial
            ]
        ];

        metrics.forEach(
            ([bar, value], index) => {
                if (!bar) {
                    return;
                }

                bar.style.width = "0%";

                setTimeout(() => {
                    bar.style.width =
                        `${clamp(
                            Number(value) || 0,
                            0,
                            100
                        )}%`;
                }, 120 + index * 100);
            }
        );
    }

    /* ========================================================
       RESULT ACTIONS
       ======================================================== */

    function openResultHome() {
        goHome();
    }

    function retryIq() {
        haptic("medium");

        resetTestState();

        showScreen("iq-intro");
    }

    async function shareResult() {
        const result =
            state.lastResult;

        if (!result) {
            showToast(
                "Natija topilmadi.",
                "!"
            );

            return;
        }

        const text =
            `🧠 IQ TEST BOT\n\n` +
            `Mening IQ-style Score: ${result.score}\n` +
            `${result.level}\n` +
            `✓ ${result.correct}/${result.total} to‘g‘ri\n\n` +
            `Siz ham o‘zingizni sinab ko‘ring!`;

        /*
         * Telegram share dialog if available.
         */
        if (
            TELEGRAM &&
            typeof TELEGRAM.openTelegramLink === "function"
        ) {
            const url =
                `https://t.me/share/url?url=&text=${encodeURIComponent(text)}`;

            try {
                TELEGRAM.openTelegramLink(url);
                return;
            } catch (_) {
                // Fallback below.
            }
        }

        if (
            navigator.share &&
            typeof navigator.share === "function"
        ) {
            try {
                await navigator.share({
                    title: APP_NAME,
                    text
                });

                return;
            } catch (error) {
                if (
                    error?.name ===
                    "AbortError"
                ) {
                    return;
                }
            }
        }

        try {
            await navigator.clipboard.writeText(
                text
            );

            showToast(
                "Natija nusxalandi.",
                "✓"
            );
        } catch (_) {
            showToast(
                text,
                "🧠"
            );
        }
    }

    async function requestCertificate() {
        const result =
            state.lastResult;

        if (!result) {
            showToast(
                "Natija topilmadi.",
                "!"
            );

            return;
        }

        if (!result.synced) {
            showToast(
                "Sertifikat uchun internet kerak. Ulanish tiklangach qayta urinib ko‘ring.",
                "!"
            );

            return;
        }

        try {
            const response =
                await apiPost(
                    "/certificate/create",
                    {},
                    10000
                );

            if (response?.code) {
                showToast(
                    `📜 Sertifikat tayyor: ${response.code}. To‘liq faylni Telegram botdan oling.`,
                    "✓",
                    4000
                );

                return;
            }

            showToast(
                "Sertifikat server orqali tayyorlanadi.",
                "📜"
            );
        } catch (error) {
            showToast(
                "Sertifikatni olishda xatolik. Birozdan so‘ng qayta urinib ko‘ring.",
                "!"
            );
        }
    }

    function openExternal(url) {
        if (!url) {
            return;
        }

        try {
            if (
                TELEGRAM &&
                typeof TELEGRAM.openLink === "function"
            ) {
                TELEGRAM.openLink(url);
                return;
            }
        } catch (_) {
            // Fallback.
        }

        window.open(
            url,
            "_blank",
            "noopener,noreferrer"
        );
    }

    /* ========================================================
       LOCKED TESTS
       ======================================================== */

    function handleEqClick() {
        const unlocked =
            DOM.eqCard?.dataset.unlocked ===
            "true";

        if (unlocked) {
            showToast(
                "EQ testi keyingi bosqichda ochiladi.",
                "🎭"
            );

            return;
        }

        openLocked(
            "Avval IQ testini yakunlang",
            "EQ testini ochish uchun IQ testini tugatishingiz kerak."
        );
    }

    function handlePqClick() {
        const unlocked =
            DOM.pqCard?.dataset.unlocked ===
            "true";

        if (unlocked) {
            showToast(
                "Prokrastinatsiya testi keyingi bosqichda ochiladi.",
                "⏳"
            );

            return;
        }

        openLocked(
            "Avval EQ testini yakunlang",
            "Prokrastinatsiya testi EQ testidan keyin ochiladi."
        );
    }

    function handleProfileClick() {
        const unlocked =
            DOM.profileCard?.dataset.unlocked ===
            "true";

        if (unlocked) {
            showToast(
                "Shaxsiy tahlil keyingi bosqichda ochiladi.",
                "⭐"
            );

            return;
        }

        openLocked(
            "Avval uchta testni yakunlang",
            "Shaxsiy profilingiz IQ, EQ va PQ natijalari asosida tuziladi."
        );
    }

    function openLocked(
        title,
        description
    ) {
        DOM.lockedTitle.textContent =
            title;

        DOM.lockedDescription.textContent =
            description;

        DOM.lockedAction.textContent =
            "IQ TESTNI BOSHLASH →";

        DOM.lockedAction.onclick =
            () => {
                showScreen("iq-intro");
            };

        showScreen("locked");
    }

    /* ========================================================
       BATTLE
       ======================================================== */

    function openBattle() {
        haptic("medium");

        /*
         * Battle UI is deliberately not faked.
         * The full battle flow (create/join/payment/compare) is a
         * separate build stage — see project notes. This only wires
         * up battle creation so the code exists end-to-end.
         */
        openModal({
            icon: "⚔️",
            title: "DO‘ST BILAN BATTLE",
            message:
                "Battle rejimida do‘stingiz bilan IQ-style Score natijangizni solishtirasiz. Har bir ishtirokchi to‘lov qiladi.",

            confirmText: "BATTLE YARATISH",
            cancelText: "BEKOR QILISH",

            onConfirm: createBattle
        });
    }

    async function createBattle() {
        try {
            const response =
                await apiPost(
                    "/battle/create",
                    {},
                    10000
                );

            if (
                response?.code
            ) {
                showToast(
                    `Battle kodi: ${response.code}. To‘lovni bot orqali amalga oshiring.`,
                    "⚔️",
                    4000
                );

                return;
            }

            showToast(
                "Battle yaratishda xatolik.",
                "!"
            );
        } catch (_) {
            showToast(
                "Battle serveri hozircha mavjud emas.",
                "!"
            );
        }
    }

    /* ========================================================
       MODAL
       ======================================================== */

    function openModal({
        icon = "⚠️",
        title = "Diqqat",
        message = "",
        confirmText = "TASDIQLASH",
        cancelText = "BEKOR QILISH",
        onConfirm = null,
        onCancel = null
    }) {
        DOM.modalIcon.textContent =
            icon;

        DOM.modalTitle.textContent =
            title;

        DOM.modalMessage.textContent =
            message;

        DOM.modalConfirm.textContent =
            confirmText;

        DOM.modalCancel.textContent =
            cancelText;

        state.pendingModalAction = {
            onConfirm,
            onCancel
        };

        DOM.modalBackdrop.classList.remove(
            "hidden"
        );

        DOM.modalBackdrop.setAttribute(
            "aria-hidden",
            "false"
        );

        requestAnimationFrame(() => {
            DOM.modalConfirm.focus();
        });
    }

    function closeModal(
        runCancel = false
    ) {
        const action =
            state.pendingModalAction;

        state.pendingModalAction =
            null;

        DOM.modalBackdrop.classList.add(
            "hidden"
        );

        DOM.modalBackdrop.setAttribute(
            "aria-hidden",
            "true"
        );

        if (
            runCancel &&
            typeof action?.onCancel ===
                "function"
        ) {
            action.onCancel();
        }
    }

    function confirmModal() {
        const action =
            state.pendingModalAction;

        state.pendingModalAction =
            null;

        DOM.modalBackdrop.classList.add(
            "hidden"
        );

        DOM.modalBackdrop.setAttribute(
            "aria-hidden",
            "true"
        );

        if (
            typeof action?.onConfirm ===
                "function"
        ) {
            action.onConfirm();
        }
    }

    /* ========================================================
       TOAST
       ======================================================== */

    function showToast(
        message,
        icon = "✓",
        duration = 2500
    ) {
        if (!DOM.toast) {
            return;
        }

        DOM.toastMessage.textContent =
            message;

        DOM.toastIcon.textContent =
            icon;

        DOM.toast.classList.add("show");

        if (toastTimer) {
            clearTimeout(toastTimer);
        }

        toastTimer =
            setTimeout(() => {
                DOM.toast.classList.remove(
                    "show"
                );
            }, duration);
    }

    /* ========================================================
       SYNC
       ======================================================== */

    async function syncSessionStart() {
        try {
            await apiPost(
                "/session/start",
                {
                    language: state.language
                },
                5000
            );

            state.backend.available =
                true;
        } catch (_) {
            /*
             * Intentionally ignored.
             * Local test continues; session/start is retried
             * from submitResultToBackend() at finish time.
             */
        }
    }

    /* ========================================================
       NETWORK RECONNECT
       ======================================================== */

    async function handleOnline() {
        showToast(
            "Internet qaytdi.",
            "✓",
            1800
        );

        await retryPendingSync();

        await loadLiveStats();
    }

    function handleOffline() {
        showToast(
            "Internet uzildi. Test offline davom etadi.",
            "⚡",
            3000
        );
    }

    /* ========================================================
       APP INITIALIZATION
       ======================================================== */

    async function initializeApp() {
        if (state.initialized) {
            return;
        }

        initTelegram();

        loadLocalState();

        const telegramUser =
            getTelegramUser();

        if (telegramUser) {
            state.user = {
                ...state.user,
                ...telegramUser
            };
        }

        updateHomeUI();

        /*
         * UI becomes available without waiting for server.
         */
        showMainApp();

        /*
         * Server calls happen in background.
         */
        await Promise.allSettled([
            loadBackendData(),
            loadUserProfile(),
            loadLiveStats()
        ]);

        updateHomeUI();

        state.initialized = true;

        /*
         * If a previous result never made it to the server
         * (app was closed offline right after finishing), retry now.
         */
        if (
            state.lastResult &&
            state.lastResult.synced === false
        ) {
            retryPendingSync();
        }

        /*
         * If the app was closed during a test,
         * don't automatically jump into it.
         * Home shows and user can choose Resume.
         */
        if (
            hasResumableTest()
        ) {
            showToast(
                `IQ testingiz saqlandi — ${state.test.currentIndex + 1}-savoldan davom etishingiz mumkin.`,
                "🧠",
                3500
            );
        }
    }

    function showMainApp() {
        if (DOM.main) {
            DOM.main.classList.remove(
                "hidden"
            );
        }

        setTimeout(() => {
            if (DOM.loading) {
                DOM.loading.classList.add(
                    "loaded"
                );
            }
        }, 180);
    }

    /* ========================================================
       EVENT LISTENERS
       ======================================================== */

    function bindEvents() {
        /*
         * HOME
         */
        DOM.startIq?.addEventListener(
            "click",
            startIqFlow
        );

        DOM.iqCard?.addEventListener(
            "click",
            startIqFlow
        );

        DOM.eqCard?.addEventListener(
            "click",
            handleEqClick
        );

        DOM.pqCard?.addEventListener(
            "click",
            handlePqClick
        );

        DOM.profileCard?.addEventListener(
            "click",
            handleProfileClick
        );

        DOM.battleCard?.addEventListener(
            "click",
            openBattle
        );

        DOM.languageButton?.addEventListener(
            "click",
            openLanguage
        );

        /*
         * IQ INTRO
         */
        DOM.iqIntroBack?.addEventListener(
            "click",
            goHome
        );

        DOM.beginIq?.addEventListener(
            "click",
            beginIqTest
        );

        /*
         * TEST
         */
        DOM.testExit?.addEventListener(
            "click",
            confirmExitTest
        );

        DOM.nextQuestion?.addEventListener(
            "click",
            nextQuestion
        );

        DOM.continueAfterFive?.addEventListener(
            "click",
            continueAfterFive
        );

        /*
         * RESULT
         */
        DOM.resultHome?.addEventListener(
            "click",
            goHome
        );

        DOM.retryIqButton?.addEventListener(
            "click",
            retryIq
        );

        DOM.shareResultButton?.addEventListener(
            "click",
            shareResult
        );

        DOM.certificateButton?.addEventListener(
            "click",
            requestCertificate
        );

        /*
         * LANGUAGE
         */
        DOM.languageBack?.addEventListener(
            "click",
            goHome
        );

        DOM.languageOptions.forEach(
            (button) => {
                button.addEventListener(
                    "click",
                    () => {
                        setLanguage(
                            button.dataset.language
                        );
                    }
                );
            }
        );

        /*
         * Error
         */
        DOM.errorRetry?.addEventListener(
            "click",
            () => {
                window.location.reload();
            }
        );

        /*
         * MODAL
         */
        DOM.modalClose?.addEventListener(
            "click",
            () => closeModal(true)
        );

        DOM.modalCancel?.addEventListener(
            "click",
            () => closeModal(true)
        );

        DOM.modalConfirm?.addEventListener(
            "click",
            confirmModal
        );

        DOM.modalBackdrop?.addEventListener(
            "click",
            (event) => {
                if (
                    event.target ===
                    DOM.modalBackdrop
                ) {
                    closeModal(true);
                }
            }
        );

        /*
         * Keyboard support for desktop testing.
         */
        document.addEventListener(
            "keydown",
            handleKeyboard
        );

        /*
         * Network.
         */
        window.addEventListener(
            "online",
            handleOnline
        );

        window.addEventListener(
            "offline",
            handleOffline
        );

        /*
         * Visibility.
         *
         * We don't stop the test simply because
         * Telegram was backgrounded. State remains
         * persistent and timer is based on timestamps.
         */
        document.addEventListener(
            "visibilitychange",
            () => {
                if (
                    document.visibilityState ===
                    "visible"
                ) {
                    if (
                        state.test.active
                    ) {
                        updateTimer();
                    }
                } else {
                    saveLocalState();
                }
            }
        );
    }

    function handleKeyboard(event) {
        if (
            state.currentScreen !==
            "iq-test"
        ) {
            return;
        }

        if (
            ["1", "2", "3", "4"]
                .includes(event.key)
        ) {
            selectAnswer(
                Number(event.key) - 1
            );

            return;
        }

        if (
            event.key === "Enter" &&
            state.test.selectedAnswer !== null
        ) {
            nextQuestion();
        }
    }

    /* ========================================================
       SAFETY / VALIDATION
       ======================================================== */

    function validateQuestionBank() {
        if (
            IQ_QUESTIONS.length !==
            TOTAL_QUESTIONS
        ) {
            throw new Error(
                `IQ question count is ${IQ_QUESTIONS.length}, expected ${TOTAL_QUESTIONS}.`
            );
        }

        IQ_QUESTIONS.forEach(
            (question, index) => {
                if (!question.id) {
                    throw new Error(
                        `Question ${index + 1} has no ID.`
                    );
                }

                if (
                    ![
                        DIFFICULTY.EASY,
                        DIFFICULTY.MEDIUM,
                        DIFFICULTY.HARD
                    ].includes(
                        question.difficulty
                    )
                ) {
                    throw new Error(
                        `Question ${index + 1} has invalid difficulty.`
                    );
                }

                if (
                    !Array.isArray(
                        question.options
                    ) ||
                    question.options.length !== 4
                ) {
                    throw new Error(
                        `Question ${index + 1} must have exactly 4 options.`
                    );
                }

                if (
                    !Number.isInteger(
                        question.correct
                    ) ||
                    question.correct < 0 ||
                    question.correct > 3
                ) {
                    throw new Error(
                        `Question ${index + 1} has invalid answer.`
                    );
                }

                if (
                    typeof question.render !==
                    "function"
                ) {
                    throw new Error(
                        `Question ${index + 1} has no render function.`
                    );
                }
            }
        );

        const easy =
            IQ_QUESTIONS.filter(
                q =>
                    q.difficulty ===
                    DIFFICULTY.EASY
            ).length;

        const medium =
            IQ_QUESTIONS.filter(
                q =>
                    q.difficulty ===
                    DIFFICULTY.MEDIUM
            ).length;

        const hard =
            IQ_QUESTIONS.filter(
                q =>
                    q.difficulty ===
                    DIFFICULTY.HARD
            ).length;

        if (
            easy !== 6 ||
            medium !== 6 ||
            hard !== 6
        ) {
            throw new Error(
                `Difficulty distribution must be 6/6/6. Got ${easy}/${medium}/${hard}.`
            );
        }
    }

    /* ========================================================
       UTILS
       ======================================================== */

    function clamp(
        value,
        min,
        max
    ) {
        return Math.min(
            max,
            Math.max(
                min,
                value
            )
        );
    }

    function wait(ms) {
        return new Promise(
            resolve =>
                setTimeout(
                    resolve,
                    ms
                )
        );
    }

    /* ========================================================
       ERROR HANDLING
       ======================================================== */

    window.addEventListener(
        "error",
        (event) => {
            console.error(
                "[IQ TEST BOT] Runtime error:",
                event.error || event.message
            );
        }
    );

    window.addEventListener(
        "unhandledrejection",
        (event) => {
            console.error(
                "[IQ TEST BOT] Promise error:",
                event.reason
            );
        }
    );

    /* ========================================================
       STARTUP
       ======================================================== */

    try {
        validateQuestionBank();
    } catch (error) {
        console.error(
            "[IQ TEST BOT] Question bank error:",
            error
        );

        if (DOM.errorMessage) {
            DOM.errorMessage.textContent =
                "IQ savollar bazasida texnik xato mavjud.";
        }
    }

    bindEvents();

    initializeApp();

})();
