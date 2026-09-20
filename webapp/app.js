"use strict";

/*
===========================================================
 IQ TEST BOT — FINAL MINI APP FRONTEND
 Stage 2

 - 18 IQ questions
 - Offline answering
 - No per-question network request
 - Real elapsed timer
 - 5-question celebration
 - Animated processing screen
 - Animated brain hero
 - Real active-user counter
 - Current backend API compatibility
 - Battle
 - Payment polling
===========================================================
*/

(() => {

    const tg = window.Telegram?.WebApp || null;

    const API = "";

    const QUESTION_COUNT = 18;

    const LETTERS = ["A", "B", "C", "D"];

    const STORAGE_KEY = "iq_test_bot_iq_session_v4";


    /* ======================================================
       STATE
    ====================================================== */

    const state = {
        lang: localStorage.getItem("iq_lang") || "uz",

        screen: "home",

        questions: [],

        index: 0,

        answers: [],

        startedAt: 0,

        elapsedBefore: 0,

        timer: null,

        busy: false,

        submitting: false,

        result: null,

        paymentId: null,

        paymentTimer: null,

        battleId: null,

        battleCode: null,

        battlePolling: null
    };


    /* ======================================================
       TRANSLATIONS
    ====================================================== */

    const T = {

        uz: {
            home: "Bosh sahifa",
            start: "TESTNI BOSHLASH",
            loading: "Yuklanmoqda...",
            error: "Xatolik yuz berdi.",
            telegramOnly: "Ilovani Telegram ichidan oching.",
            paid: "IQ test uchun to‘lov talab qilinadi.",
            paymentSent: "To‘lov oynasi ochildi. Chekni botga yuboring.",
            paymentWaiting: "To‘lov tasdiqlanishi kutilmoqda...",
            paymentApproved: "To‘lov tasdiqlandi.",
            paymentRejected: "To‘lov rad etildi.",
            connection: "Aloqa vaqtincha mavjud emas.",
            finishError: "Natijani yuborishda xatolik.",
            battleCreated: "Battle yaratildi.",
            battleJoined: "Battle'ga qo‘shildingiz.",
            battleWaiting: "Do‘stingiz qo‘shilishini kuting.",
            battleFull: "Bu battle to‘la.",
            battleError: "Battle bilan bog‘lanishda xatolik.",
            noAccess: "Bu test hozircha yopiq.",
            certificateError: "Sertifikatni olishda xatolik.",
            shareError: "Ulashib bo‘lmadi."
        },

        ru: {
            home: "Главная",
            start: "НАЧАТЬ ТЕСТ",
            loading: "Загрузка...",
            error: "Произошла ошибка.",
            telegramOnly: "Откройте приложение внутри Telegram.",
            paid: "Для IQ теста требуется оплата.",
            paymentSent: "Окно оплаты открыто. Отправьте чек боту.",
            paymentWaiting: "Ожидается подтверждение оплаты...",
            paymentApproved: "Оплата подтверждена.",
            paymentRejected: "Оплата отклонена.",
            connection: "Соединение временно недоступно.",
            finishError: "Ошибка отправки результата.",
            battleCreated: "Battle создан.",
            battleJoined: "Вы присоединились.",
            battleWaiting: "Ожидаем друга.",
            battleFull: "Battle уже заполнен.",
            battleError: "Ошибка Battle.",
            noAccess: "Этот тест сейчас закрыт.",
            certificateError: "Ошибка сертификата.",
            shareError: "Не удалось поделиться."
        },

        en: {
            home: "Home",
            start: "START TEST",
            loading: "Loading...",
            error: "Something went wrong.",
            telegramOnly: "Open the app inside Telegram.",
            paid: "Payment is required for the IQ test.",
            paymentSent: "Payment window opened. Send the receipt to the bot.",
            paymentWaiting: "Waiting for payment approval...",
            paymentApproved: "Payment approved.",
            paymentRejected: "Payment rejected.",
            connection: "Connection is temporarily unavailable.",
            finishError: "Could not submit result.",
            battleCreated: "Battle created.",
            battleJoined: "You joined the battle.",
            battleWaiting: "Waiting for your friend.",
            battleFull: "Battle is full.",
            battleError: "Battle error.",
            noAccess: "This test is currently locked.",
            certificateError: "Certificate error.",
            shareError: "Could not share."
        }
    };


    function t(key) {
        return T[state.lang]?.[key] || T.uz[key] || key;
    }


    /* ======================================================
       DOM
    ====================================================== */

    const $ = (id) => document.getElementById(id);


    /* ======================================================
       TELEGRAM
    ====================================================== */

    function initTelegram() {

        if (!tg) {
            console.warn("[IQ TEST BOT] Telegram WebApp not found");
            return;
        }

        try {
            tg.ready();
            tg.expand();

            tg.setHeaderColor?.("#080a13");
            tg.setBackgroundColor?.("#080a13");

            tg.disableVerticalSwipes?.();
        } catch (e) {
            console.warn("[IQ TEST BOT] Telegram init:", e);
        }
    }


    function initData() {
        return tg?.initData || "";
    }


    /* ======================================================
       API
    ====================================================== */

    async function api(path, options = {}) {

        const headers = {
            "Content-Type": "application/json",
            "X-Telegram-Init-Data": initData(),
            ...(options.headers || {})
        };

        const response = await fetch(
            API + path,
            {
                ...options,
                headers,
                cache: "no-store"
            }
        );

        let data = {};

        try {
            data = await response.json();
        } catch (_) {
            data = {};
        }

        if (!response.ok) {

            const error = new Error(
                data?.detail ||
                `HTTP_${response.status}`
            );

            error.status = response.status;
            error.detail = data?.detail;

            throw error;
        }

        return data;
    }


    /* ======================================================
       UI HELPERS
    ====================================================== */

    function showScreen(id) {

        document.querySelectorAll(".screen").forEach(screen => {
            screen.classList.remove("active");
        });

        const target = $(id);

        if (!target) {
            throw new Error("SCREEN_NOT_FOUND:" + id);
        }

        target.classList.add("active");

        state.screen = id;

        window.scrollTo({
            top: 0,
            behavior: "instant"
        });
    }


    function toast(message) {

        const el = $("toast");

        if (!el) return;

        el.textContent = String(message || "");

        el.classList.add("show");

        clearTimeout(toast.timer);

        toast.timer = setTimeout(() => {
            el.classList.remove("show");
        }, 3000);
    }


    function formatTime(seconds) {

        const total = Math.max(
            0,
            Math.floor(Number(seconds) || 0)
        );

        const minutes = Math.floor(total / 60);

        const secs = total % 60;

        return (
            String(minutes).padStart(2, "0") +
            ":" +
            String(secs).padStart(2, "0")
        );
    }


    /* ======================================================
       REAL TIMER
    ====================================================== */

    function getElapsed() {

        if (!state.startedAt) {
            return state.elapsedBefore || 0;
        }

        return (
            state.elapsedBefore +
            Math.floor(
                (Date.now() - state.startedAt) / 1000
            )
        );
    }


    function startTimer() {

        stopTimer();

        const update = () => {

            if (!$("elapsedTime")) return;

            $("elapsedTime").textContent =
                formatTime(getElapsed());
        };

        update();

        state.timer = setInterval(
            update,
            500
        );
    }


    function stopTimer() {

        if (state.timer) {

            clearInterval(state.timer);

            state.timer = null;
        }
    }


    /* ======================================================
       LOCAL STORAGE
    ====================================================== */

    function saveSession() {

        try {

            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({
                    index: state.index,
                    answers: state.answers,
                    startedAt: state.startedAt,
                    elapsedBefore: state.elapsedBefore,
                    lang: state.lang,
                    savedAt: Date.now()
                })
            );

        } catch (e) {

            console.warn(
                "[IQ TEST BOT] local save failed",
                e
            );
        }
    }


    function loadSession() {

        try {

            const raw =
                localStorage.getItem(STORAGE_KEY);

            if (!raw) return null;

            const data = JSON.parse(raw);

            if (!data) return null;

            if (
                !Array.isArray(data.answers) ||
                data.answers.length > QUESTION_COUNT
            ) {
                return null;
            }

            if (
                Number(data.index) < 0 ||
                Number(data.index) > QUESTION_COUNT
            ) {
                return null;
            }

            return data;

        } catch (_) {

            return null;
        }
    }


    function clearSession() {

        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (_) {}
    }


    /* ======================================================
       SVG HELPERS
    ====================================================== */

    function svgWrap(content, width = 330, height = 150) {

        return `
        <svg
            viewBox="0 0 ${width} ${height}"
            width="${width}"
            height="${height}"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
        >
            ${content}
        </svg>`;
    }


    function svgText(x, y, text, size = 18) {

        return `
        <text
            x="${x}"
            y="${y}"
            text-anchor="middle"
            fill="#f5f4fb"
            font-size="${size}"
            font-family="Inter, Arial, sans-serif"
            font-weight="700"
        >${text}</text>`;
    }


    function circle(x, y, r, fill = "#8d68ff") {

        return `
        <circle
            cx="${x}"
            cy="${y}"
            r="${r}"
            fill="${fill}"
        />`;
    }


    function square(x, y, s, fill = "#8d68ff") {

        return `
        <rect
            x="${x}"
            y="${y}"
            width="${s}"
            height="${s}"
            rx="7"
            fill="${fill}"
        />`;
    }


    function arrow(x, y, dir, size = 24) {

        const arrows = {
            up: "↑",
            right: "→",
            down: "↓",
            left: "←"
        };

        return svgText(
            x,
            y,
            arrows[dir] || "?",
            size
        );
    }


    /* ======================================================
       18 PROFESSIONAL IQ QUESTIONS
    ====================================================== */

    const QUESTIONS = [

        /* 1 */
        {
            id: 1,
            type: "visual",
            text: {
                uz: "Har bir qatorda ikkinchi belgi birinchining 90° soat strelkasi bo‘yicha aylantirilgan ko‘rinishi. ? o‘rniga nima keladi?",
                ru: "Во второй позиции каждого ряда символ повернут на 90° по часовой стрелке. Что должно стоять вместо ?",
                en: "In each row, the second symbol is the first rotated 90° clockwise. What replaces ?"
            },
            puzzle: () => svgWrap(`
                ${arrow(70,45,"up",30)}
                ${arrow(140,45,"right",30)}
                ${arrow(220,45,"down",30)}
                ${svgText(280,53,"?",30)}
                <line x1="40" y1="78" x2="300" y2="78"
                    stroke="#34384e" stroke-width="2"/>
                ${svgText(105,125,"1-qator",12)}
                ${svgText(245,125,"2-qator",12)}
            `),
            options: ["↑  Yuqoriga", "→  O‘ngga", "↓  Pastga", "←  Chapga"],
            answer: 3,
            weight: 1
        },


        /* 2 */
        {
            id: 2,
            type: "matrix",
            text: {
                uz: "Jadvalning har bir qatorida uchinchi son birinchi sonning 2 baravari va ikkinchi son yig‘indisiga teng. ? ni toping.",
                ru: "В каждой строке третье число равно удвоенному первому плюс второе. Найдите ?.",
                en: "In each row, the third number equals twice the first plus the second. Find ?."
            },
            puzzle: () => svgWrap(`
                ${svgText(75,45,"2",22)}
                ${svgText(165,45,"3",22)}
                ${svgText(255,45,"7",22)}

                ${svgText(75,88,"4",22)}
                ${svgText(165,88,"5",22)}
                ${svgText(255,88,"13",22)}

                ${svgText(75,131,"6",22)}
                ${svgText(165,131,"7",22)}
                ${svgText(255,131,"?",24)}
            `),
            options: ["17", "18", "19", "20"],
            answer: 2,
            weight: 1
        },


        /* 3 */
        {
            id: 3,
            type: "clock",
            text: {
                uz: "Soat 4:20 ni ko‘rsatmoqda. Strelkalar orasidagi kichik burchak necha daraja?",
                ru: "Часы показывают 4:20. Каков меньший угол между стрелками?",
                en: "A clock shows 4:20. What is the smaller angle between the hands?"
            },
            puzzle: () => svgWrap(`
                <circle cx="165" cy="75" r="53"
                    fill="none" stroke="#5b6178" stroke-width="2"/>
                ${svgText(165,31,"12",11)}
                ${svgText(211,80,"3",11)}
                ${svgText(165,128,"6",11)}
                ${svgText(119,80,"9",11)}

                <line x1="165" y1="75" x2="145" y2="45"
                    stroke="#ff8bd6" stroke-width="5"
                    stroke-linecap="round"/>

                <line x1="165" y1="75" x2="165" y2="26"
                    stroke="#9c82ff" stroke-width="3"
                    stroke-linecap="round"/>

                ${circle(165,75,5,"#ffffff")}
            `),
            options: ["10°", "20°", "30°", "40°"],
            answer: 0,
            weight: 1
        },


        /* 4 */
        {
            id: 4,
            type: "logic",
            text: {
                uz: "A, B, C, D va E bir qatorda turibdi. A — B dan oldin. C — D dan darhol keyin. E birinchi emas. Qaysi tartib mumkin?",
                ru: "A, B, C, D и E стоят в ряд. A левее B. C сразу после D. E не первый. Какой порядок возможен?",
                en: "A, B, C, D and E stand in a row. A is before B. C is immediately after D. E is not first. Which order is possible?"
            },
            puzzle: () => svgWrap(`
                ${["A","B","C","D","E"].map((x,i) => `
                    <rect x="${35+i*57}" y="45" width="43" height="43"
                        rx="10" fill="#181c30"
                        stroke="#424861"/>
                    ${svgText(56+i*57,73,x,16)}
                `).join("")}
            `),
            options: [
                "D-C-A-E-B",
                "A-C-D-E-B",
                "B-A-D-E-C",
                "E-D-C-B-A"
            ],
            answer: 0,
            weight: 1
        },


        /* 5 */
        {
            id: 5,
            type: "visual",
            text: {
                uz: "Qaysi shaklda markazga nisbatan simmetriya buzilgan?",
                ru: "В какой фигуре нарушена центральная симметрия?",
                en: "Which figure breaks the central symmetry?"
            },
            puzzle: () => svgWrap(`
                <g transform="translate(42 25)">
                    ${circle(20,25,8)}
                    ${circle(45,45,8)}
                    ${circle(20,65,8)}
                    ${circle(45,5,8)}
                </g>

                <g transform="translate(117 25)">
                    ${square(12,10,15)}
                    ${square(37,30,15)}
                    ${square(12,50,15)}
                    ${square(-8,30,15)}
                </g>

                <g transform="translate(205 25)">
                    ${circle(20,25,8)}
                    ${circle(45,5,8)}
                    ${circle(20,65,8)}
                    ${circle(45,45,8)}
                </g>

                <g transform="translate(280 25)">
                    ${square(10,10,15)}
                    ${square(35,30,15)}
                    ${square(10,50,15)}
                    ${square(30,65,15)}
                </g>
            `),
            options: [
                "1-shakl",
                "2-shakl",
                "3-shakl",
                "4-shakl"
            ],
            answer: 3,
            weight: 2
        },


        /* 6 */
        {
            id: 6,
            type: "sequence",
            text: {
                uz: "Ketma-ketlikdagi qonuniyatni toping: 3, 8, 18, 38, 78, ?",
                ru: "Найдите правило последовательности: 3, 8, 18, 38, 78, ?",
                en: "Find the rule: 3, 8, 18, 38, 78, ?"
            },
            puzzle: () => svgWrap(`
                ${svgText(40,55,"3",18)}
                ${svgText(100,55,"8",18)}
                ${svgText(160,55,"18",18)}
                ${svgText(225,55,"38",18)}
                ${svgText(295,55,"78",18)}
                ${svgText(325,110,"?",24)}
            `),
            options: ["154", "156", "158", "160"],
            answer: 2,
            weight: 2
        },


        /* 7 */
        {
            id: 7,
            type: "cube",
            text: {
                uz: "Kubning qarama-qarshi tomonlari A–D, B–E va C–F. A tomoni bilan qaysi tomon qirra bo‘lisha olmaydi?",
                ru: "Противоположные грани куба: A–D, B–E и C–F. Какая грань не может иметь общее ребро с A?",
                en: "Opposite cube faces are A–D, B–E and C–F. Which face cannot share an edge with A?"
            },
            puzzle: () => svgWrap(`
                <polygon points="125,25 205,50 205,120 125,95"
                    fill="#171b2d" stroke="#8d68ff" stroke-width="2"/>
                <polygon points="125,25 70,50 70,120 125,95"
                    fill="#111522" stroke="#ff70ca" stroke-width="2"/>
                <polygon points="125,25 180,5 260,30 205,50"
                    fill="#20243a" stroke="#5d9cff" stroke-width="2"/>

                ${svgText(160,82,"A",22)}
                ${svgText(98,82,"B",22)}
                ${svgText(210,35,"C",22)}
            `),
            options: ["B", "C", "E", "D"],
            answer: 3,
            weight: 2
        },


        /* 8 */
        {
            id: 8,
            type: "logic",
            text: {
                uz: "Barcha K lar L. Ba’zi L lar M. Qaysi xulosa albatta to‘g‘ri?",
                ru: "Все K являются L. Некоторые L являются M. Какой вывод обязательно верен?",
                en: "All K are L. Some L are M. Which conclusion must be true?"
            },
            puzzle: () => svgWrap(`
                <circle cx="115" cy="75" r="45"
                    fill="rgba(141,104,255,.08)"
                    stroke="#8d68ff" stroke-width="2"/>
                <circle cx="185" cy="75" r="45"
                    fill="rgba(255,112,202,.07)"
                    stroke="#ff70ca" stroke-width="2"/>
                ${svgText(115,81,"K",20)}
                ${svgText(185,81,"L",20)}
                ${svgText(250,81,"M",20)}
                <path d="M145 75 H155"
                    stroke="#7c8297" stroke-width="2"/>
            `),
            options: [
                "Barcha K lar L",
                "Ba’zi K lar M",
                "Hech bir K M emas",
                "Barcha M lar K"
            ],
            answer: 0,
            weight: 2
        },


        /* 9 */
        {
            id: 9,
            type: "matrix",
            text: {
                uz: "Har bir qatorning uchinchi katagi dastlabki ikki katakdagi qiymatlarning yig‘indisi bilan hosil bo‘ladi. ? ni toping.",
                ru: "Третий элемент каждой строки получается из суммы первых двух. Найдите ?.",
                en: "The third element of each row is formed from the sum of the first two. Find ?."
            },
            puzzle: () => svgWrap(`
                ${circle(55,35,13)}
                ${circle(125,35,18)}
                ${svgText(205,42,"=",20)}
                ${circle(260,35,31)}

                ${square(42,80,25)}
                ${square(115,80,25)}
                ${svgText(205,101,"=",20)}
                ${svgText(270,103,"?",27)}
            `),
            options: [
                "3 ta",
                "4 ta",
                "5 ta",
                "6 ta"
            ],
            answer: 2,
            weight: 3
        },


        /* 10 */
        {
            id: 10,
            type: "sequence",
            text: {
                uz: "Qoidani toping: 2 → 6, 3 → 12, 4 → 20, 7 → ?",
                ru: "Найдите правило: 2 → 6, 3 → 12, 4 → 20, 7 → ?",
                en: "Find the rule: 2 → 6, 3 → 12, 4 → 20, 7 → ?"
            },
            puzzle: () => svgWrap(`
                ${svgText(50,55,"2",20)}
                ${svgText(100,55,"→",20)}
                ${svgText(145,55,"6",20)}

                ${svgText(50,105,"4",20)}
                ${svgText(100,105,"→",20)}
                ${svgText(145,105,"20",20)}

                ${svgText(220,80,"7 → ?",26)}
            `),
            options: ["42", "49", "56", "63"],
            answer: 2,
            weight: 3
        },


        /* 11 */
        {
            id: 11,
            type: "logic",
            text: {
                uz: "Ba’zi rassomlar muhandis. Barcha muhandislar kitobxon. Qaysi xulosa majburiy?",
                ru: "Некоторые художники — инженеры. Все инженеры читают книги. Какой вывод обязателен?",
                en: "Some artists are engineers. All engineers are readers. Which conclusion is necessary?"
            },
            puzzle: () => svgWrap(`
                <circle cx="110" cy="75" r="42"
                    fill="rgba(255,112,202,.08)"
                    stroke="#ff70ca" stroke-width="2"/>
                <circle cx="190" cy="75" r="42"
                    fill="rgba(141,104,255,.08)"
                    stroke="#8d68ff" stroke-width="2"/>
                <circle cx="270" cy="75" r="42"
                    fill="rgba(93,156,255,.08)"
                    stroke="#5d9cff" stroke-width="2"/>

                ${svgText(110,81,"R",20)}
                ${svgText(190,81,"M",20)}
                ${svgText(270,81,"K",20)}
            `),
            options: [
                "Barcha rassomlar kitobxon",
                "Ba’zi rassomlar kitobxon",
                "Hech bir rassom kitobxon emas",
                "Barcha kitobxonlar muhandis"
            ],
            answer: 1,
            weight: 3
        },


        /* 12 */
        {
            id: 12,
            type: "rotation",
            text: {
                uz: "Chapdagi shakl har safar 90° ga soat strelkasi bo‘yicha aylantirilmoqda. Uchinchi aylanishdan keyin yo‘nalish qaysi?",
                ru: "Фигура каждый раз поворачивается на 90° по часовой стрелке. Какое направление после третьего поворота?",
                en: "The figure rotates 90° clockwise each time. What is its direction after the third rotation?"
            },
            puzzle: () => svgWrap(`
                ${arrow(60,55,"up",38)}
                ${svgText(110,60,"→",24)}
                ${arrow(165,55,"right",38)}
                ${svgText(215,60,"→",24)}
                ${arrow(270,55,"down",38)}
            `),
            options: [
                "↑ Yuqoriga",
                "→ O‘ngga",
                "↓ Pastga",
                "← Chapga"
            ],
            answer: 3,
            weight: 3
        },


        /* 13 */
        {
            id: 13,
            type: "logic",
            text: {
                uz: "A: “B yolg‘on gapiryapti.” B: “C yolg‘on gapiryapti.” C: “A va B bir xil turdagi odamlar.” Faqat bittasi rost gapirsa, kim rost gapiryapti?",
                ru: "A: «B лжёт». B: «C лжёт». C: «A и B одного типа». Если правду говорит только один, кто это?",
                en: "A says B lies. B says C lies. C says A and B are the same type. If exactly one tells the truth, who is it?"
            },
            puzzle: () => svgWrap(`
                <circle cx="80" cy="70" r="27"
                    fill="#171b2d" stroke="#8d68ff" stroke-width="2"/>
                <circle cx="165" cy="70" r="27"
                    fill="#171b2d" stroke="#ff70ca" stroke-width="2"/>
                <circle cx="250" cy="70" r="27"
                    fill="#171b2d" stroke="#5d9cff" stroke-width="2"/>
                ${svgText(80,77,"A",18)}
                ${svgText(165,77,"B",18)}
                ${svgText(250,77,"C",18)}
            `),
            options: ["A", "B", "C", "Hech biri"],
            answer: 1,
            weight: 3
        },


        /* 14 */
        {
            id: 14,
            type: "count",
            text: {
                uz: "4 xonali koddagi barcha raqamlar turlicha. Birinchi raqam 0 bo‘lishi mumkin emas. Nechta kod mavjud?",
                ru: "Все цифры 4-значного кода различны. Первая цифра не может быть 0. Сколько кодов?",
                en: "All digits in a 4-digit code are distinct. The first digit cannot be 0. How many codes exist?"
            },
            puzzle: () => svgWrap(`
                ${["□","□","□","□"].map((x,i) =>
                    svgText(75+i*62,72,x,34)
                ).join("")}
            `),
            options: ["4032", "4320", "4536", "5040"],
            answer: 1,
            weight: 4
        },


        /* 15 */
        {
            id: 15,
            type: "matrix",
            text: {
                uz: "3×3 jadvalda har bir qator va ustunda uchinchi qiymat oldingi ikkisining farqi bilan bog‘langan. Qaysi javob mos keladi?",
                ru: "В матрице 3×3 третье значение связано с разностью первых двух. Какой ответ подходит?",
                en: "In the 3×3 matrix, the third value is related to the difference of the first two. Which answer fits?"
            },
            puzzle: () => svgWrap(`
                ${[
                    ["8","3","5"],
                    ["11","4","7"],
                    ["15","6","?"]
                ].map((row,r) =>
                    row.map((v,c) =>
                        svgText(
                            70+c*95,
                            42+r*42,
                            v,
                            v === "?" ? 25 : 18
                        )
                    ).join("")
                ).join("")}
            `),
            options: ["7", "8", "9", "10"],
            answer: 2,
            weight: 4
        },


        /* 16 */
        {
            id: 16,
            type: "visual",
            text: {
                uz: "Har bir keyingi katakda qora nuqta 90° soat strelkasi bo‘yicha aylanadi, ichki chiziq esa qarama-qarshi yo‘nalishda aylanadi. Keyingi holat qaysi?",
                ru: "Чёрная точка поворачивается на 90° по часовой стрелке, внутренняя линия — в противоположную сторону. Какое положение следующее?",
                en: "The black dot rotates 90° clockwise while the inner line rotates oppositely. What comes next?"
            },
            puzzle: () => svgWrap(`
                <rect x="50" y="25" width="70" height="70" rx="12"
                    fill="#15192a" stroke="#454b62"/>
                ${circle(105,40,7)}
                <line x1="60" y1="85" x2="110" y2="35"
                    stroke="#9d82ff" stroke-width="4"/>

                ${svgText(145,65,"→",25)}

                <rect x="170" y="25" width="70" height="70" rx="12"
                    fill="#15192a" stroke="#454b62"/>
                ${circle(185,80,7)}
                <line x1="180" y1="35" x2="230" y2="85"
                    stroke="#9d82ff" stroke-width="4"/>

                ${svgText(265,65,"→",25)}

                <rect x="285" y="25" width="40" height="70" rx="12"
                    fill="#15192a" stroke="#454b62"/>
                ${svgText(305,68,"?",25)}
            `),
            options: [
                "Nuqta yuqorida, chiziq ↘",
                "Nuqta o‘ngda, chiziq ↙",
                "Nuqta pastda, chiziq ↖",
                "Nuqta chapda, chiziq ↗"
            ],
            answer: 2,
            weight: 4
        },


        /* 17 */
        {
            id: 17,
            type: "logic",
            text: {
                uz: "3 ta kalitning faqat bittasi lampani yoqadi. A kalit yoqilgan bo‘lsa, B o‘chiq. C yoqilgan bo‘lsa, A o‘chiq. B yoqilgan. Qaysi kalit lampani yoqishi mumkin?",
                ru: "Только один из 3 переключателей включает лампу. Если A включён, B выключен. Если C включён, A выключен. B включён. Какой переключатель может включить лампу?",
                en: "Only one of three switches turns on the lamp. If A is on, B is off. If C is on, A is off. B is on. Which switch can turn the lamp on?"
            },
            puzzle: () => svgWrap(`
                ${["A","B","C"].map((x,i) => `
                    <rect x="${65+i*90}" y="45" width="54" height="35"
                        rx="9"
                        fill="${i===1 ? "#7655ee" : "#181c30"}"
                        stroke="#555c75"/>
                    ${svgText(92+i*90,69,x,17)}
                `).join("")}
            `),
            options: [
                "A",
                "B",
                "C",
                "A yoki C"
            ],
            answer: 1,
            weight: 5
        },


        /* 18 */
        {
            id: 18,
            type: "final",
            text: {
                uz: "Final puzzle: uchta quti bor. Faqat bittasida oltin bor. 1-quti: “Oltin 2-qutida.” 2-quti: “Oltin bu qutida emas.” 3-quti: “Oltin 1-qutida.” Faqat bitta yozuv rost. Oltin qaysi qutida?",
                ru: "Финальная задача: три коробки. Только в одной золото. На 1: «Золото во 2». На 2: «Золота здесь нет». На 3: «Золото в 1». Только одна надпись истинна. Где золото?",
                en: "Final puzzle: three boxes, only one contains gold. Box 1 says gold is in box 2. Box 2 says gold is not here. Box 3 says gold is in box 1. Exactly one statement is true. Where is the gold?"
            },
            puzzle: () => svgWrap(`
                ${[1,2,3].map((x,i) => `
                    <rect x="${35+i*100}" y="35" width="72" height="70"
                        rx="13"
                        fill="#171b2d"
                        stroke="${i===1 ? "#9c73ff" : "#42485e"}"
                        stroke-width="2"/>
                    ${svgText(71+i*100,77,String(x),25)}
                `).join("")}
            `),
            options: [
                "1-qutida",
                "2-qutida",
                "3-qutida",
                "Aniqlab bo‘lmaydi"
            ],
            answer: 2,
            weight: 5
        }

    ];


    /* ======================================================
       QUESTION VALIDATION
    ====================================================== */

    function validateQuestions() {

        if (QUESTIONS.length !== QUESTION_COUNT) {
            throw new Error(
                `QUESTION_COUNT_INVALID:${QUESTIONS.length}`
            );
        }

        for (const q of QUESTIONS) {

            if (
                !q.text ||
                !q.text.uz ||
                !q.text.ru ||
                !q.text.en
            ) {
                throw new Error(
                    `QUESTION_TEXT_INVALID:${q.id}`
                );
            }

            if (
                !Array.isArray(q.options) ||
                q.options.length !== 4
            ) {
                throw new Error(
                    `QUESTION_OPTIONS_INVALID:${q.id}`
                );
            }

            if (
                !Number.isInteger(q.answer) ||
                q.answer < 0 ||
                q.answer > 3
            ) {
                throw new Error(
                    `QUESTION_ANSWER_INVALID:${q.id}`
                );
            }
        }
    }


    /* ======================================================
       HOME
    ====================================================== */

    async function openHome() {

        stopTimer();

        showScreen("homeScreen");

        updateLiveCounter();

        const iqCard = $("iqCard");

        if (iqCard) {
            iqCard.onclick = () => startIQ();
        }

        $("eqCard").onclick = () => {
            toast("Avval IQ testni yakunlang.");
        };

        $("pqCard").onclick = () => {
            toast("Avval EQ testni yakunlang.");
        };

        $("personalityCard").onclick = () => {
            toast("Avval IQ, EQ va Prokrastinatsiya testlarini yakunlang.");
        };

        $("battleCard").onclick = openBattle;

        $("langBtn").onclick = () => {
            $("languageModal").classList.remove("hidden");
        };
    }


    /* ======================================================
       LIVE COUNTER
    ====================================================== */

    async function updateLiveCounter() {

        const el = $("activeUsers");

        if (!el) return;

        try {

            const data = await api(
                "/api/counter",
                {
                    method: "GET"
                }
            );

            const count =
                Number(data?.active) || 1;

            el.textContent =
                count.toLocaleString("uz-UZ");

        } catch (_) {

            el.textContent = "—";
        }
    }


    /* ======================================================
       START IQ
    ====================================================== */

    async function startIQ() {

        if (state.busy || state.submitting) return;

        state.busy = true;

        try {

            const saved = loadSession();

            if (
                saved &&
                Array.isArray(saved.answers) &&
                saved.answers.length > 0 &&
                saved.answers.length < QUESTION_COUNT
            ) {

                const resume =
                    confirm(
                        "Oldingi test davomida saqlangan javoblaringiz bor. Davom etasizmi?"
                    );

                if (resume) {

                    state.index =
                        Number(saved.index) || 0;

                    state.answers =
                        saved.answers.slice();

                    state.startedAt =
                        Number(saved.startedAt) || Date.now();

                    state.elapsedBefore =
                        Number(saved.elapsedBefore) || 0;

                    renderQuestion();

                    return;
                }

                clearSession();
            }


            /*
             First check access.
             If access is granted -> start immediately.
             If not -> payment flow.
            */

            let access;

            try {

                access = await api(
                    "/api/access/iq",
                    {
                        method: "GET"
                    }
                );

            } catch (error) {

                /*
                 If access endpoint fails because of backend
                 schema or temporary network, don't start a
                 fake test.
                */

                throw error;
            }


            if (!access?.allowed) {

                await openPayment();

                return;
            }


            beginNewTest();

        } catch (error) {

            console.error(
                "[IQ TEST BOT] startIQ:",
                error
            );

            if (
                error?.status === 401 ||
                String(error?.detail || "").includes("initData")
            ) {
                toast(t("telegramOnly"));
            } else {
                toast(
                    `${t("error")} ${
                        error?.detail || ""
                    }`
                );
            }

        } finally {

            state.busy = false;
        }
    }


    /* ======================================================
       NEW TEST
    ====================================================== */

    function beginNewTest() {

        state.questions = QUESTIONS;

        state.index = 0;

        state.answers =
            new Array(QUESTION_COUNT).fill(null);

        state.startedAt = Date.now();

        state.elapsedBefore = 0;

        state.result = null;

        state.submitting = false;

        saveSession();

        renderQuestion();
    }


    /* ======================================================
       RENDER QUESTION
    ====================================================== */

    function renderQuestion() {

        if (
            state.index < 0 ||
            state.index >= QUESTION_COUNT
        ) {
            finishTest();
            return;
        }

        const q =
            state.questions[state.index];

        if (!q) {
            toast("Savol topilmadi.");
            return;
        }


        $("questionNumber").textContent =
            `${state.index + 1} / ${QUESTION_COUNT}`;


        $("progressFill").style.width =
            `${((state.index + 1) / QUESTION_COUNT) * 100}%`;


        $("questionText").textContent =
            q.text[state.lang] ||
            q.text.uz;


        $("puzzleArea").innerHTML =
            typeof q.puzzle === "function"
                ? q.puzzle()
                : "";


        const answers =
            $("answers");

        answers.innerHTML = "";


        q.options.forEach(
            (option, optionIndex) => {

                const button =
                    document.createElement("button");

                button.type = "button";

                button.className =
                    "answer-btn";

                button.dataset.index =
                    String(optionIndex);


                if (
                    state.answers[state.index] ===
                    optionIndex
                ) {
                    button.classList.add("selected");
                }


                button.innerHTML = `
                    <span class="answer-letter">
                        ${LETTERS[optionIndex]}
                    </span>

                    <span class="answer-text">
                        ${escapeHTML(option)}
                    </span>
                `;


                button.onclick = () =>
                    selectAnswer(optionIndex);


                answers.appendChild(button);
            }
        );


        const selected =
            state.answers[state.index];


        $("nextBtn").disabled =
            !Number.isInteger(selected);


        $("nextBtn").onclick =
            nextQuestion;


        $("testBackBtn").onclick =
            handleTestBack;


        showScreen("testScreen");

        startTimer();

        saveSession();
    }


    /* ======================================================
       ANSWER
    ====================================================== */

    function selectAnswer(index) {

        if (
            state.submitting ||
            state.index >= QUESTION_COUNT
        ) {
            return;
        }


        state.answers[state.index] =
            index;


        document
            .querySelectorAll(".answer-btn")
            .forEach(button => {

                button.classList.remove(
                    "selected"
                );

                if (
                    Number(button.dataset.index) ===
                    index
                ) {
                    button.classList.add(
                        "selected"
                    );
                }
            });


        $("nextBtn").disabled = false;

        saveSession();


        /*
         Tiny haptic feedback.
        */

        try {
            tg?.HapticFeedback?.selectionChanged?.();
        } catch (_) {}
    }


    /* ======================================================
       NEXT QUESTION
    ====================================================== */

    function nextQuestion() {

        const selected =
            state.answers[state.index];


        if (!Number.isInteger(selected)) {
            return;
        }


        const previous =
            state.index;


        state.index++;


        /*
         Celebration after Q5.
         Index 5 means the user just answered question 5.
        */

        if (previous === 4) {

            saveSession();

            showCelebration(() => {

                if (
                    state.index >=
                    QUESTION_COUNT
                ) {
                    finishTest();
                } else {
                    renderQuestion();
                }

            });

            return;
        }


        if (
            state.index >=
            QUESTION_COUNT
        ) {

            finishTest();

            return;
        }


        renderQuestion();
    }


    /* ======================================================
       CELEBRATION
    ====================================================== */

    function showCelebration(onContinue) {

        const modal =
            $("celebrationModal");

        modal.classList.remove("hidden");


        createConfetti();


        $("continueCelebrationBtn").onclick =
            () => {

                modal.classList.add(
                    "hidden"
                );

                onContinue();
            };
    }


    function createConfetti() {

        const container =
            $("confettiContainer");

        if (!container) return;

        container.innerHTML = "";


        for (let i = 0; i < 34; i++) {

            const piece =
                document.createElement("span");

            piece.className =
                "confetti";

            piece.style.left =
                `${Math.random() * 100}%`;

            piece.style.animationDelay =
                `${Math.random() * .45}s`;

            piece.style.transform =
                `rotate(${Math.random() * 360}deg)`;

            const colors = [
                "#8d68ff",
                "#ff70ca",
                "#6d9cff",
                "#ffd76a"
            ];

            piece.style.background =
                colors[
                    Math.floor(
                        Math.random() *
                        colors.length
                    )
                ];

            container.appendChild(piece);
        }
    }


    /* ======================================================
       FINISH TEST
    ====================================================== */

    async function finishTest() {

        if (state.submitting) return;

        if (
            state.answers.length !==
            QUESTION_COUNT
        ) {
            toast("Test hali tugamagan.");
            return;
        }


        if (
            state.answers.some(
                answer => !Number.isInteger(answer)
            )
        ) {
            toast("Barcha savollarga javob bering.");
            return;
        }


        state.submitting = true;

        stopTimer();

        showScreen(
            "processingScreen"
        );


        try {

            /*
             Calculate raw score locally.
             Backend currently accepts raw_score.
            */

            let raw = 0;

            QUESTIONS.forEach(
                (q, i) => {

                    if (
                        state.answers[i] ===
                        q.answer
                    ) {
                        raw += q.weight;
                    }
                }
            );


            const total =
                QUESTIONS.reduce(
                    (sum, q) =>
                        sum + q.weight,
                    0
                );


            const elapsed =
                getElapsed();


            const data =
                await api(
                    "/api/test/submit",
                    {
                        method: "POST",
                        body: JSON.stringify({
                            test_type: "iq",
                            answers: state.answers,
                            raw_score: raw,
                            total: total,
                            profile: {
                                fullName:
                                    tg?.initDataUnsafe?.user?.first_name ||
                                    "Foydalanuvchi",
                                elapsed
                            },
                            battle_id:
                                state.battleId || null
                        })
                    }
                );


            state.result = {
                ...data,
                elapsed,
                correct:
                    QUESTIONS.reduce(
                        (count, q, i) =>
                            count +
                            (
                                state.answers[i] ===
                                q.answer
                                    ? 1
                                    : 0
                            ),
                        0
                    )
            };


            clearSession();

            renderResult();


        } catch (error) {

            console.error(
                "[IQ TEST BOT] finish:",
                error
            );


            /*
             Keep answers in localStorage.
             The user does NOT lose the completed test
             just because internet/API temporarily failed.
            */

            saveSession();

            toast(
                error?.detail ||
                t("finishError")
            );


            /*
             Give the user the last question again
             instead of throwing them to home.
            */

            state.index =
                QUESTION_COUNT - 1;

            renderQuestion();


        } finally {

            state.submitting = false;
        }
    }


    /* ======================================================
       RESULT
    ====================================================== */

    function renderResult() {

        stopTimer();

        const result =
            state.result;

        if (!result) {
            openHome();
            return;
        }


        const score =
            Number(result.score ?? 0);


        const correct =
            Number(result.correct ?? 0);


        const elapsed =
            Number(result.elapsed ?? 0);


        $("iqScore").textContent =
            score || "—";


        $("correctCount").textContent =
            `${correct} / ${QUESTION_COUNT}`;


        $("resultTime").textContent =
            formatTime(elapsed);


        $("resultRank").textContent =
            "—";


        let title =
            "Natija tayyor";


        if (score >= 125) {
            title = "Juda kuchli natija";
        } else if (score >= 115) {
            title = "Yuqori natija";
        } else if (score >= 100) {
            title = "Yaxshi natija";
        } else if (score >= 85) {
            title = "O‘rtacha natija";
        } else {
            title = "Boshlang‘ich natija";
        }


        $("resultTitle").textContent =
            title;


        $("resultDescription").textContent =
            `${correct}/${QUESTION_COUNT} savol to‘g‘ri. Test vaqti ${formatTime(elapsed)}.`;


        $("certificateBtn").onclick =
            downloadCertificate;


        $("shareBtn").onclick =
            shareResult;


        $("homeResultBtn").onclick =
            openHome;


        showScreen("resultScreen");


        try {
            tg?.HapticFeedback?.notificationOccurred?.(
                "success"
            );
        } catch (_) {}
    }


    /* ======================================================
       CERTIFICATE
    ====================================================== */

    async function downloadCertificate() {

        try {

            const response =
                await fetch(
                    "/api/certificate",
                    {
                        method: "GET",
                        headers: {
                            "X-Telegram-Init-Data":
                                initData()
                        },
                        cache: "no-store"
                    }
                );


            if (!response.ok) {

                let data = {};

                try {
                    data =
                        await response.json();
                } catch (_) {}

                throw new Error(
                    data?.detail ||
                    "CERTIFICATE_ERROR"
                );
            }


            const blob =
                await response.blob();


            const url =
                URL.createObjectURL(blob);


            const a =
                document.createElement("a");


            a.href = url;

            a.download =
                "IQ-TEST-CERTIFICATE.png";

            document.body.appendChild(a);

            a.click();

            a.remove();

            setTimeout(
                () => URL.revokeObjectURL(url),
                2000
            );


        } catch (error) {

            console.error(
                "[IQ TEST BOT] certificate:",
                error
            );

            toast(
                error?.message ||
                t("certificateError")
            );
        }
    }


    /* ======================================================
       SHARE
    ====================================================== */

    async function shareResult() {

        if (!state.result) return;


        const score =
            state.result.score ?? "—";


        const correct =
            state.result.correct ?? "—";


        const text =
            `🧠 IQ TEST BOT\n\n` +
            `Mening IQ score'im: ${score}\n` +
            `${correct}/${QUESTION_COUNT} savol to‘g‘ri.`;


        try {

            if (
                tg?.openTelegramLink
            ) {

                const url =
                    `https://t.me/share/url?` +
                    `url=${encodeURIComponent(location.href)}` +
                    `&text=${encodeURIComponent(text)}`;

                tg.openTelegramLink(url);

                return;
            }


            if (
                navigator.share
            ) {

                await navigator.share({
                    title: "IQ TEST BOT",
                    text,
                    url: location.href
                });

                return;
            }


            await navigator.clipboard.writeText(
                text
            );

            toast(
                "Natija nusxalandi."
            );


        } catch (error) {

            console.warn(
                "[IQ TEST BOT] share:",
                error
            );

            toast(
                t("shareError")
            );
        }
    }


    /* ======================================================
       PAYMENT
    ====================================================== */

    async function openPayment() {

        $("paymentModal")
            .classList
            .remove("hidden");


        $("paymentText").textContent =
            "IQ test uchun to‘lov talab qilinadi. To‘lovni boshlang va chekni botga yuboring.";


        $("paymentStartBtn").onclick =
            startPayment;


        $("paymentCloseBtn").onclick =
            closePayment;
    }


    function closePayment() {

        $("paymentModal")
            .classList
            .add("hidden");

        stopPaymentPolling();
    }


    async function startPayment() {

        if (state.paymentId) {
            return;
        }


        try {

            $("paymentStartBtn").disabled =
                true;


            const data =
                await api(
                    "/api/payment/start",
                    {
                        method: "POST",
                        body: JSON.stringify({
                            product_code: "iq"
                        })
                    }
                );


            if (data?.free) {

                closePayment();

                beginNewTest();

                return;
            }


            state.paymentId =
                data.payment_id;


            $("paymentText").textContent =
                "To‘lov yaratildi. Botdagi ko‘rsatmalar bo‘yicha to‘lovni amalga oshiring va chekni yuboring.";


            $("paymentStartBtn").textContent =
                "TASDIQLANISHI KUTILMOQDA";


            /*
             Try to open the bot.
            */

            if (tg?.openTelegramLink) {

                const username =
                    data.bot_username ||
                    "iqtest_ubot";

                tg.openTelegramLink(
                    `https://t.me/${username}`
                );
            }


            startPaymentPolling();


        } catch (error) {

            console.error(
                "[IQ TEST BOT] payment:",
                error
            );

            $("paymentStartBtn").disabled =
                false;

            toast(
                error?.detail ||
                t("error")
            );
        }
    }


    function startPaymentPolling() {

        stopPaymentPolling();


        state.paymentTimer =
            setInterval(
                checkPayment,
                2500
            );


        checkPayment();
    }


    function stopPaymentPolling() {

        if (
            state.paymentTimer
        ) {

            clearInterval(
                state.paymentTimer
            );

            state.paymentTimer =
                null;
        }
    }


    async function checkPayment() {

        if (!state.paymentId) {
            return;
        }


        try {

            const data =
                await api(
                    `/api/payment/status/${state.paymentId}`,
                    {
                        method: "GET"
                    }
                );


            if (
                data.status ===
                "approved"
            ) {

                stopPaymentPolling();

                state.paymentId =
                    null;

                closePayment();

                toast(
                    t("paymentApproved")
                );

                beginNewTest();

                return;
            }


            if (
                data.status ===
                "rejected"
            ) {

                stopPaymentPolling();

                state.paymentId =
                    null;

                $("paymentStartBtn")
                    .disabled = false;

                $("paymentStartBtn")
                    .textContent =
                    "TO‘LOVNI BOSHLASH";

                toast(
                    t("paymentRejected")
                );
            }

        } catch (error) {

            console.warn(
                "[IQ TEST BOT] payment poll:",
                error
            );
        }
    }


    /* ======================================================
       BATTLE
    ====================================================== */

    function openBattle() {

        showScreen("battleScreen");

        $("battleBackBtn").onclick =
            () => openHome();


        $("createBattleBtn").onclick =
            createBattle;


        $("joinBattleBtn").onclick =
            joinBattle;
    }


    async function createBattle() {

        try {

            $("createBattleBtn").disabled =
                true;


            const data =
                await api(
                    "/api/battle/create",
                    {
                        method: "POST",
                        body: JSON.stringify({})
                    }
                );


            state.battleId =
                data.battle_id;

            state.battleCode =
                data.code;


            $("battleStatus").innerHTML =
                `
                <strong>⚔️ Battle kodi: ${escapeHTML(data.code)}</strong><br>
                Do‘stingizga shu 4 xonali kodni yuboring.
                `;


            if (data.payment_required) {

                toast(
                    "Battle uchun to‘lov talab qilinadi."
                );
            } else {

                toast(
                    t("battleCreated")
                );
            }


            startBattlePolling();


        } catch (error) {

            console.error(
                "[IQ TEST BOT] battle create:",
                error
            );

            toast(
                error?.detail ||
                t("battleError")
            );

        } finally {

            $("createBattleBtn").disabled =
                false;
        }
    }


    async function joinBattle() {

        const input =
            $("battleCodeInput");

        const code =
            String(input.value || "")
                .replace(/\D/g, "")
                .slice(0, 4);


        if (code.length !== 4) {

            toast(
                "4 xonali battle kodini kiriting."
            );

            return;
        }


        try {

            $("joinBattleBtn").disabled =
                true;


            const data =
                await api(
                    "/api/battle/join",
                    {
                        method: "POST",
                        body: JSON.stringify({
                            code
                        })
                    }
                );


            state.battleId =
                data.battle_id;

            state.battleCode =
                code;


            $("battleStatus").innerHTML =
                `
                <strong>⚔️ Battle'ga qo‘shildingiz.</strong><br>
                Endi IQ testni boshlashingiz mumkin.
                `;


            if (
                data.payment_required
            ) {

                toast(
                    "Battle to‘lovi talab qilinadi."
                );

            } else {

                toast(
                    t("battleJoined")
                );
            }


            startBattlePolling();


        } catch (error) {

            console.error(
                "[IQ TEST BOT] battle join:",
                error
            );

            toast(
                error?.detail ||
                t("battleError")
            );

        } finally {

            $("joinBattleBtn").disabled =
                false;
        }
    }


    function startBattlePolling() {

        stopBattlePolling();


        state.battlePolling =
            setInterval(
                checkBattle,
                3000
            );


        checkBattle();
    }


    function stopBattlePolling() {

        if (
            state.battlePolling
        ) {

            clearInterval(
                state.battlePolling
            );

            state.battlePolling =
                null;
        }
    }


    async function checkBattle() {

        if (!state.battleId) {
            return;
        }


        try {

            const data =
                await api(
                    `/api/battle/${state.battleId}`,
                    {
                        method: "GET"
                    }
                );


            if (
                data.status ===
                "waiting"
            ) {

                $("battleStatus").innerHTML =
                    `
                    <strong>⏳ Do‘stingiz kutilmoqda...</strong>
                    <br>
                    Kod: ${escapeHTML(state.battleCode || "")}
                    `;

                return;
            }


            if (
                data.status ===
                "ready"
            ) {

                $("battleStatus").innerHTML =
                    `
                    <strong>🟢 Battle tayyor!</strong>
                    <br>
                    IQ testni boshlang.
                    `;

                return;
            }


            if (
                data.status ===
                "finished"
            ) {

                stopBattlePolling();

                const result =
                    data.result || {};


                $("battleStatus").innerHTML =
                    `
                    <strong>🏆 BATTLE YAKUNLANDI</strong>
                    <br>
                    Siz: ${result.player1 ?? "—"}
                    <br>
                    Do‘stingiz: ${result.player2 ?? "—"}
                    `;

                return;
            }

        } catch (error) {

            console.warn(
                "[IQ TEST BOT] battle state:",
                error
            );
        }
    }


    /* ======================================================
       TEST BACK
    ====================================================== */

    function handleTestBack() {

        if (state.submitting) {
            return;
        }


        const leave =
            confirm(
                "Testdan chiqishni xohlaysizmi? Joriy javoblaringiz saqlanadi."
            );


        if (!leave) return;


        saveSession();

        stopTimer();

        openHome();
    }


    /* ======================================================
       LANGUAGE
    ====================================================== */

    function bindLanguage() {

        const modal =
            $("languageModal");


        modal
            .querySelectorAll(
                ".language-option"
            )
            .forEach(button => {

                button.onclick = () => {

                    const lang =
                        button.dataset.lang;


                    if (
                        !T[lang]
                    ) return;


                    state.lang =
                        lang;


                    localStorage.setItem(
                        "iq_lang",
                        lang
                    );


                    modal.classList.add(
                        "hidden"
                    );


                    $("langBtn").textContent =
                        lang.toUpperCase();


                    if (
                        state.screen ===
                        "testScreen"
                    ) {
                        renderQuestion();
                    }
                };
            });


        modal
            .querySelector(
                ".modal-backdrop"
            )
            ?.addEventListener(
                "click",
                () => {
                    modal.classList.add(
                        "hidden"
                    );
                }
            );
    }


    /* ======================================================
       ESCAPE
    ====================================================== */

    function escapeHTML(value) {

        return String(value ?? "")
            .replace(
                /[&<>"']/g,
                char => ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#039;"
                })[char]
            );
    }


    /* ======================================================
       BOOT
    ====================================================== */

    async function boot() {

        try {

            validateQuestions();

            initTelegram();

            $("langBtn").textContent =
                state.lang.toUpperCase();


            bindLanguage();


            $("paymentCloseBtn").onclick =
                closePayment;


            /*
             We intentionally do not make a blocking
             /api/me request here.

             Home must open instantly.
            */

            await openHome();


            console.log(
                "[IQ TEST BOT] FINAL MINI APP READY"
            );


        } catch (error) {

            console.error(
                "[IQ TEST BOT] BOOT ERROR:",
                error
            );

            toast(
                "Mini App yuklanishida xatolik."
            );
        }
    }


    /* ======================================================
       ONLINE / OFFLINE
    ====================================================== */

    window.addEventListener(
        "online",
        () => {

            if (
                state.index >= QUESTION_COUNT &&
                !state.submitting
            ) {
                finishTest();
            }
        }
    );


    window.addEventListener(
        "offline",
        () => {

            toast(
                "Internet uzildi. Javoblaringiz qurilmada saqlanadi."
            );
        }
    );


    /* ======================================================
       START
    ====================================================== */

    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            boot,
            { once: true }
        );

    } else {

        boot();
    }


    /* ======================================================
       DEBUG ACCESS
    ====================================================== */

    window.IQ_TEST_BOT = {
        state,
        questions: QUESTIONS,
        start: startIQ,
        home: openHome
    };

})();