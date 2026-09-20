"use strict";

(() => {

const tg = window.Telegram?.WebApp || null;
const API = "";

const QUESTION_COUNT = 18;

const state = {
    lang: localStorage.getItem("iq_lang") || "uz",

    screen: "home",

    type: null,

    index: 0,

    answers: [],

    startedAt: 0,

    timer: null,

    result: null,

    paymentId: null,

    battleId: null,

    busy: false,

    profile: {}
};


/* =========================================================
   HELPERS
========================================================= */

const I = (uz, ru, en) => ({
    uz,
    ru,
    en
});

const T = {

    uz: {
        brand: "IQ TEST BOT",
        hero: "IQ darajangizni sinab ko‘ring",
        desc: "18 ta mantiqiy puzzle orqali fikrlash qobiliyatingizni sinang.",
        start: "TESTNI BOSHLASH",

        iq: "IQ",
        eq: "EQ",
        pq: "PROKRASTINATSIYA",
        person: "SIZ QANDAY INSONSIZ",

        battle: "DO‘ST BILAN BATTLE",

        locked: "IQ dan keyin",
        locked2: "EQ dan keyin",
        locked3: "Uchala testdan keyin",

        live: "JONLI",

        loading: "Natija tayyorlanmoqda…",

        question: "MANTIQIY PUZZLE",

        next: "DAVOM ETISH",

        done: "TEST YAKUNLANDI",

        correct: "to‘g‘ri",
        time: "vaqt",
        score: "IQ SCORE",

        payment: "💳 TO‘LOV QILISH",

        paytext:
            "Qayta test uchun to‘lov talab qilinadi.",

        cancel: "BEKOR QILISH",

        join: "BATTLEGA QO‘SHILISH",

        create: "BATTLE YARATISH",

        code: "KOD",

        back: "ORTGA",

        home: "BOSH SAHIFA",

        share: "NATIJANI ULASHISH",

        error: "Xatolik yuz berdi.",

        free: "Birinchi IQ testi bepul."
    },

    ru: {
        brand: "IQ TEST BOT",
        hero: "Проверьте свой IQ",
        desc: "18 логических задач для проверки мышления.",
        start: "НАЧАТЬ ТЕСТ",

        iq: "IQ",
        eq: "EQ",
        pq: "ПРОКРАСТИНАЦИЯ",
        person: "КАКОЙ ВЫ ЧЕЛОВЕК",

        battle: "BATTLE С ДРУГОМ",

        locked: "После IQ",
        locked2: "После EQ",
        locked3: "После трёх тестов",

        live: "ОНЛАЙН",

        loading: "Готовим результат…",

        question: "ЛОГИЧЕСКАЯ ЗАДАЧА",

        next: "ПРОДОЛЖИТЬ",

        done: "ТЕСТ ЗАВЕРШЁН",

        correct: "верно",
        time: "время",
        score: "IQ SCORE",

        payment: "💳 ОПЛАТИТЬ",

        paytext:
            "Для повторного теста требуется оплата.",

        cancel: "ОТМЕНА",

        join: "ВОЙТИ В BATTLE",

        create: "СОЗДАТЬ BATTLE",

        code: "КОД",

        back: "НАЗАД",

        home: "ГЛАВНАЯ",

        share: "ПОДЕЛИТЬСЯ",

        error: "Произошла ошибка.",

        free: "Первая попытка бесплатно."
    },

    en: {
        brand: "IQ TEST BOT",
        hero: "Test your IQ",
        desc: "18 logic puzzles to challenge your reasoning.",
        start: "START TEST",

        iq: "IQ",
        eq: "EQ",
        pq: "PROCRASTINATION",
        person: "WHAT KIND OF PERSON ARE YOU",

        battle: "BATTLE WITH A FRIEND",

        locked: "After IQ",
        locked2: "After EQ",
        locked3: "After all three",

        live: "LIVE",

        loading: "Preparing result…",

        question: "LOGIC PUZZLE",

        next: "CONTINUE",

        done: "TEST COMPLETE",

        correct: "correct",
        time: "time",
        score: "IQ SCORE",

        payment: "💳 MAKE PAYMENT",

        paytext:
            "Payment is required for a retest.",

        cancel: "CANCEL",

        join: "JOIN BATTLE",

        create: "CREATE BATTLE",

        code: "CODE",

        back: "BACK",

        home: "HOME",

        share: "SHARE RESULT",

        error: "Something went wrong.",

        free: "First IQ attempt is free."
    }
};

const t = key =>
    T[state.lang]?.[key] ||
    T.uz[key] ||
    key;

const tr = value =>
    typeof value === "string"
        ? value
        : value[state.lang] || value.uz;

const esc = value =>
    String(value ?? "")
        .replace(
            /[&<>"']/g,
            char => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;"
            }[char])
        );


/* =========================================================
   IQ QUESTIONS
========================================================= */

const Q = [

    {
        q: I(
            "Ketma-ketlik: 4, 7, 13, 25, 49, ?",
            "Последовательность: 4, 7, 13, 25, 49, ?",
            "Sequence: 4, 7, 13, 25, 49, ?"
        ),
        o: I(
            ["73", "97", "98", "101"],
            ["73", "97", "98", "101"],
            ["73", "97", "98", "101"]
        ),
        a: 1
    },

    {
        q: I(
            "Ketma-ketlik: 2, 5, 11, 23, 47, ?",
            "Последовательность: 2, 5, 11, 23, 47, ?",
            "Sequence: 2, 5, 11, 23, 47, ?"
        ),
        o: I(
            ["91", "93", "95", "97"],
            ["91", "93", "95", "97"],
            ["91", "93", "95", "97"]
        ),
        a: 2
    },

    {
        q: I(
            "Ketma-ketlik: 3, 8, 15, 24, 35, ?",
            "Последовательность: 3, 8, 15, 24, 35, ?",
            "Sequence: 3, 8, 15, 24, 35, ?"
        ),
        o: I(
            ["48", "49", "50", "51"],
            ["48", "49", "50", "51"],
            ["48", "49", "50", "51"]
        ),
        a: 0
    },

    {
        q: I(
            "Ketma-ketlik: 2, 6, 12, 20, 30, ?",
            "Последовательность: 2, 6, 12, 20, 30, ?",
            "Sequence: 2, 6, 12, 20, 30, ?"
        ),
        o: I(
            ["38", "40", "42", "44"],
            ["38", "40", "42", "44"],
            ["38", "40", "42", "44"]
        ),
        a: 2
    },

    {
        q: I(
            "Ketma-ketlik: 1, 2, 6, 24, 120, ?",
            "Последовательность: 1, 2, 6, 24, 120, ?",
            "Sequence: 1, 2, 6, 24, 120, ?"
        ),
        o: I(
            ["480", "600", "720", "840"],
            ["480", "600", "720", "840"],
            ["480", "600", "720", "840"]
        ),
        a: 2
    },

    {
        q: I(
            "Harflar: A, C, F, J, O, ?",
            "Буквы: A, C, F, J, O, ?",
            "Letters: A, C, F, J, O, ?"
        ),
        o: I(
            ["T", "U", "V", "W"],
            ["T", "U", "V", "W"],
            ["T", "U", "V", "W"]
        ),
        a: 1
    },

    {
        q: I(
            "Barcha K lar L. Ba’zi L lar M. Qaysi gap albatta to‘g‘ri?",
            "Все K являются L. Некоторые L являются M. Что обязательно верно?",
            "All K are L. Some L are M. Which statement must be true?"
        ),
        o: I(
            [
                "Barcha K lar L",
                "Ba’zi K lar M",
                "Hech bir K M emas",
                "Barcha M lar K"
            ],
            [
                "Все K являются L",
                "Некоторые K являются M",
                "Ни один K не является M",
                "Все M являются K"
            ],
            [
                "All K are L",
                "Some K are M",
                "No K is M",
                "All M are K"
            ]
        ),
        a: 0
    },

    {
        q: I(
            "A — B dan oldin. C — D dan darhol keyin. E birinchi emas. Qaysi tartib mumkin?",
            "A перед B. C сразу после D. E не первый. Какой порядок возможен?",
            "A is before B. C is immediately after D. E is not first. Which order is possible?"
        ),
        o: I(
            [
                "D-C-A-E-B",
                "A-C-D-E-B",
                "B-A-D-E-C",
                "E-D-C-B-A"
            ],
            [
                "D-C-A-E-B",
                "A-C-D-E-B",
                "B-A-D-E-C",
                "E-D-C-B-A"
            ],
            [
                "D-C-A-E-B",
                "A-C-D-E-B",
                "B-A-D-E-C",
                "E-D-C-B-A"
            ]
        ),
        a: 0
    },

    {
        q: I(
            "Har qatorda 3-son = 1-son + 2-son: 2,5,7 / 4,9,13 / 6,13, ?",
            "В каждой строке 3-е число = 1-е + 2-е: 2,5,7 / 4,9,13 / 6,13, ?",
            "In each row, third number = first + second: 2,5,7 / 4,9,13 / 6,13, ?"
        ),
        o: I(
            ["17", "18", "19", "20"],
            ["17", "18", "19", "20"],
            ["17", "18", "19", "20"]
        ),
        a: 2
    },

    {
        q: I(
            "Ketma-ketlik: 1, 4, 10, 22, 46, ?",
            "Последовательность: 1, 4, 10, 22, 46, ?",
            "Sequence: 1, 4, 10, 22, 46, ?"
        ),
        o: I(
            ["90", "92", "94", "96"],
            ["90", "92", "94", "96"],
            ["90", "92", "94", "96"]
        ),
        a: 2
    },

    {
        q: I(
            "Ketma-ketlik: 2, 3, 6, 11, 18, 27, ?",
            "Последовательность: 2, 3, 6, 11, 18, 27, ?",
            "Sequence: 2, 3, 6, 11, 18, 27, ?"
        ),
        o: I(
            ["36", "38", "40", "42"],
            ["36", "38", "40", "42"],
            ["36", "38", "40", "42"]
        ),
        a: 1
    },

    {
        q: I(
            "Soat 3:40. Kichik burchak necha daraja?",
            "Часы показывают 3:40. Каков меньший угол?",
            "A clock shows 3:40. What is the smaller angle?"
        ),
        o: I(
            ["110°", "120°", "130°", "140°"],
            ["110°", "120°", "130°", "140°"],
            ["110°", "120°", "130°", "140°"]
        ),
        a: 2
    },

    {
        q: I(
            "Ba’zi rassomlar muhandis. Barcha muhandislar kitobxon. Nima albatta to‘g‘ri?",
            "Некоторые художники — инженеры. Все инженеры — читатели. Что обязательно верно?",
            "Some artists are engineers. All engineers are readers. What must be true?"
        ),
        o: I(
            [
                "Barcha rassomlar kitobxon",
                "Ba’zi rassomlar kitobxon",
                "Hech bir rassom kitobxon emas",
                "Barcha kitobxonlar muhandis"
            ],
            [
                "Все художники — читатели",
                "Некоторые художники — читатели",
                "Ни один художник не читает",
                "Все читатели — инженеры"
            ],
            [
                "All artists are readers",
                "Some artists are readers",
                "No artist is a reader",
                "All readers are engineers"
            ]
        ),
        a: 1
    },

    {
        q: I(
            "Ketma-ketlik: 2, 9, 28, 65, 126, ?",
            "Последовательность: 2, 9, 28, 65, 126, ?",
            "Sequence: 2, 9, 28, 65, 126, ?"
        ),
        o: I(
            ["181", "205", "217", "225"],
            ["181", "205", "217", "225"],
            ["181", "205", "217", "225"]
        ),
        a: 2
    },

    {
        q: I(
            "Kubda qarama-qarshi tomonlar A-D, B-E, C-F. Qaysi tomon A bilan qirra bo‘lisha olmaydi?",
            "У куба противоположные грани A-D, B-E, C-F. Какая грань не может иметь общее ребро с A?",
            "Cube opposites are A-D, B-E, C-F. Which face cannot share an edge with A?"
        ),
        o: I(
            ["B", "C", "E", "D"],
            ["B", "C", "E", "D"],
            ["B", "C", "E", "D"]
        ),
        a: 3
    },

    {
        q: I(
            "4 ta bir xil mashina 6 soatda 240 detal ishlab chiqaradi. 6 ta mashina 5 soatda nechta detal ishlab chiqaradi?",
            "4 одинаковые машины за 6 часов делают 240 деталей. Сколько сделают 6 машин за 5 часов?",
            "4 identical machines make 240 parts in 6 hours. How many do 6 machines make in 5 hours?"
        ),
        o: I(
            ["280", "300", "320", "360"],
            ["280", "300", "320", "360"],
            ["280", "300", "320", "360"]
        ),
        a: 1
    },

    {
        q: I(
            "4 xonali kodda barcha raqamlar turlicha. Birinchi raqam 0 emas. Nechta kod bor?",
            "В 4-значном коде все цифры различны. Первая не 0. Сколько кодов?",
            "A 4-digit code has distinct digits; first digit is not 0. How many codes?"
        ),
        o: I(
            ["4032", "4320", "4536", "5040"],
            ["4032", "4320", "4536", "5040"],
            ["4032", "4320", "4536", "5040"]
        ),
        a: 2
    },

    {
        q: I(
            "Ketma-ketlik: 1, 2, 6, 15, 31, 56, ?",
            "Последовательность: 1, 2, 6, 15, 31, 56, ?",
            "Sequence: 1, 2, 6, 15, 31, 56, ?"
        ),
        o: I(
            ["84", "88", "92", "96"],
            ["84", "88", "92", "96"],
            ["84", "88", "92", "96"]
        ),
        a: 2
    }
];


/* =========================================================
   LOCAL STORAGE
========================================================= */

function saveSession(){

    localStorage.setItem(
        "iq_offline_session",
        JSON.stringify({
            type: state.type,
            index: state.index,
            answers: state.answers,
            startedAt: state.startedAt,
            profile: state.profile
        })
    );
}

function clearSession(){
    localStorage.removeItem(
        "iq_offline_session"
    );
}


/* =========================================================
   API
========================================================= */

async function api(
    path,
    options = {}
){

    const response = await fetch(
        API + path,
        {
            ...options,

            headers:{
                "Content-Type":
                    "application/json",

                "X-Telegram-Init-Data":
                    tg?.initData || "",

                ...(options.headers || {})
            }
        }
    );

    let data = {};

    try{
        data = await response.json();
    }
    catch{}

    if(!response.ok){

        const error = new Error(
            data.detail ||
            data.error ||
            `HTTP ${response.status}`
        );

        error.status =
            response.status;

        error.data = data;

        throw error;
    }

    return data;
}


/* =========================================================
   INIT
========================================================= */

function init(){

    try{
        tg?.ready();
        tg?.expand();
    }
    catch{}

    renderHome();

    refreshCounter();

    setInterval(
        refreshCounter,
        30000
    );
}


/* =========================================================
   HOME
========================================================= */

function renderHome(){

    stopTimer();

    state.screen = "home";

    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="home">

            <header>

                <div class="brand">
                    <span class="brand-dot"></span>
                    ${t("brand")}
                </div>

                <button
                    class="lang"
                    id="langBtn"
                >
                    ${state.lang.toUpperCase()}
                </button>

            </header>


            <section class="hero">

                <div class="orb">

                    <div class="brain">
                        🧠
                    </div>

                    <i></i>
                    <i></i>
                    <i></i>

                </div>


                <div class="eyebrow">
                    18 TA MANTIQIY PUZZLE
                </div>


                <h1>
                    ${t("hero")}
                </h1>


                <p>
                    ${t("desc")}
                </p>


                <button
                    class="primary"
                    id="iqStart"
                >
                    ${t("start")}
                    <span>→</span>
                </button>

            </section>


            <section class="cards">

                <article
                    class="test-card active"
                    id="iqCard"
                >

                    <b>🧠</b>

                    <div>
                        <strong>
                            ${t("iq")}
                        </strong>

                        <small>
                            ${t("free")}
                        </small>
                    </div>

                    <span>→</span>

                </article>


                <article
                    class="test-card locked"
                >

                    <b>🎭</b>

                    <div>
                        <strong>
                            ${t("eq")}
                        </strong>

                        <small>
                            ${t("locked")}
                        </small>
                    </div>

                    <span>🔒</span>

                </article>


                <article
                    class="test-card locked"
                >

                    <b>⏳</b>

                    <div>
                        <strong>
                            ${t("pq")}
                        </strong>

                        <small>
                            ${t("locked2")}
                        </small>
                    </div>

                    <span>🔒</span>

                </article>


                <article
                    class="test-card locked"
                >

                    <b>⭐</b>

                    <div>
                        <strong>
                            ${t("person")}
                        </strong>

                        <small>
                            ${t("locked3")}
                        </small>
                    </div>

                    <span>🔒</span>

                </article>

            </section>


            <article
                class="battle-card"
                id="battle"
            >

                <div>

                    <b>⚔️</b>

                    <strong>
                        ${t("battle")}
                    </strong>

                    <small>
                        7 500 so‘m / ishtirokchi
                    </small>

                </div>

                <span>→</span>

            </article>


            <div class="live">

                <span>🟢</span>

                <b id="counter">
                    —
                </b>

                ${t("live")}

            </div>

        </main>
    `;


    document.getElementById(
        "iqStart"
    ).onclick = () =>
        start("iq");


    document.getElementById(
        "iqCard"
    ).onclick = () =>
        start("iq");


    document.getElementById(
        "battle"
    ).onclick = battleScreen;


    document.getElementById(
        "langBtn"
    ).onclick = languageScreen;
}


/* =========================================================
   COUNTER
========================================================= */

async function refreshCounter(){

    try{

        const data =
            await api(
                "/api/counter"
            );

        const element =
            document.getElementById(
                "counter"
            );

        if(element){
            element.textContent =
                data.active;
        }

    }
    catch{}
}


/* =========================================================
   LANGUAGE
========================================================= */

function languageScreen(){

    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="center">

            <div class="panel">

                <h2>
                    ${t("brand")}
                </h2>

                <p>
                    🌐 Tilni tanlang
                </p>

                <button
                    class="option"
                    data-lang="uz"
                >
                    🇺🇿 O‘zbekcha
                </button>

                <button
                    class="option"
                    data-lang="ru"
                >
                    🇷🇺 Русский
                </button>

                <button
                    class="option"
                    data-lang="en"
                >
                    🇬🇧 English
                </button>

                <button
                    class="ghost"
                    id="langBack"
                >
                    ${t("back")}
                </button>

            </div>

        </main>
    `;


    document
        .querySelectorAll(
            "[data-lang]"
        )
        .forEach(button => {

            button.onclick = () => {

                state.lang =
                    button.dataset.lang;

                localStorage.setItem(
                    "iq_lang",
                    state.lang
                );

                renderHome();
            };

        });


    document.getElementById(
        "langBack"
    ).onclick =
        renderHome;
}


/* =========================================================
   START TEST
========================================================= */

async function start(
    type,
    battleId = null
){

    if(type !== "iq"){

        toast(
            "Bu test hozircha qulflangan."
        );

        return;
    }

    try{

        const access =
            await api(
                "/api/access/iq"
            );

        if(!access.allowed){

            openPayment();

            return;
        }


        state.type = type;

        state.battleId =
            battleId;

        state.index = 0;

        state.answers = [];

        state.startedAt =
            Date.now();

        state.profile = {
            fullName:
                tg?.initDataUnsafe
                    ?.user
                    ?.first_name
                || ""
        };

        saveSession();

        renderQuestion();

    }
    catch(error){

        toast(
            error.message ||
            t("error")
        );
    }
}


/* =========================================================
   QUESTION SCREEN
========================================================= */

function renderQuestion(){

    state.screen = "test";

    const question =
        Q[state.index];

    const elapsed =
        Math.floor(
            (
                Date.now()
                - state.startedAt
            ) / 1000
        );


    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="test">

            <header
                class="test-head"
            >

                <button
                    class="icon"
                    id="quit"
                >
                    ×
                </button>


                <div>

                    <b>
                        ${t("question")}
                    </b>

                    <small>
                        ${state.index + 1}
                        /
                        ${QUESTION_COUNT}
                    </small>

                </div>


                <span id="clock">
                    ${formatTime(elapsed)}
                </span>

            </header>


            <div class="progress">

                <span
                    style="
                        width:
                        ${
                            (
                                (state.index + 1)
                                /
                                QUESTION_COUNT
                            ) * 100
                        }%
                    "
                ></span>

            </div>


            <section class="puzzle">

                <div class="q-number">
                    ${String(
                        state.index + 1
                    ).padStart(2,"0")}
                </div>


                <h2>
                    ${esc(
                        tr(question.q)
                    )}
                </h2>


                <div class="answers">

                    ${
                        tr(question.o)
                            .map(
                                (
                                    option,
                                    index
                                ) => `

                                    <button
                                        class="answer"
                                        data-a="${index}"
                                    >

                                        <em>
                                            ${
                                                String
                                                    .fromCharCode(
                                                        65 + index
                                                    )
                                            }
                                        </em>

                                        <span>
                                            ${esc(option)}
                                        </span>

                                    </button>
                                `
                            )
                            .join("")
                    }

                </div>

            </section>


            <div class="test-tip">

                Javoblar telefoningizda
                vaqtincha saqlanadi.
                Test davomida serverga
                har savolda ulanmaydi.

            </div>

        </main>
    `;


    document
        .querySelectorAll(
            "[data-a]"
        )
        .forEach(button => {

            button.onclick = () =>
                answer(
                    Number(
                        button.dataset.a
                    )
                );

        });


    document.getElementById(
        "quit"
    ).onclick = () => {

        if(
            confirm(
                "Testdan chiqilsinmi? Progress saqlanadi."
            )
        ){

            saveSession();

            renderHome();
        }

    };


    startTimer();
}


/* =========================================================
   TIMER
========================================================= */

function startTimer(){

    stopTimer();

    state.timer =
        setInterval(
            () => {

                const clock =
                    document.getElementById(
                        "clock"
                    );

                if(!clock)
                    return;

                clock.textContent =
                    formatTime(
                        Math.floor(
                            (
                                Date.now()
                                -
                                state.startedAt
                            ) / 1000
                        )
                    );

            },
            500
        );
}


function stopTimer(){

    if(state.timer){
        clearInterval(
            state.timer
        );
    }

    state.timer = null;
}


function formatTime(seconds){

    return (
        String(
            Math.floor(
                seconds / 60
            )
        ).padStart(2,"0")
        +
        ":"
        +
        String(
            seconds % 60
        ).padStart(2,"0")
    );
}


/* =========================================================
   ANSWER
========================================================= */

function answer(index){

    if(state.busy)
        return;

    state.busy = true;

    state.answers[
        state.index
    ] = index;

    saveSession();


    document
        .querySelectorAll(
            "[data-a]"
        )
        .forEach(
            button =>
                button.disabled = true
        );


    document
        .querySelector(
            `[data-a="${index}"]`
        )
        ?.classList.add(
            "selected"
        );


    setTimeout(
        async () => {

            state.index++;

            /*
             * Celebration exactly after question 5.
             */

            if(
                state.index === 5
            ){

                celebrate();

            }

            else if(
                state.index >=
                QUESTION_COUNT
            ){

                await finish();

            }

            else{

                renderQuestion();

            }

            state.busy = false;

        },
        180
    );
}


/* =========================================================
   CELEBRATION
========================================================= */

function celebrate(){

    document.getElementById(
        "app"
    ).innerHTML = `

        <main
            class="
                center
                celebration
            "
        >

            <div class="celebrate">

                <div class="burst">
                    ✦
                </div>

                <h2>
                    🎉 Ajoyib boshladingiz! 🚀
                </h2>

                <p>
                    Birinchi 5 savol ortda.
                    <br>
                    Shu zaylda davom eting!
                </p>

                <button
                    class="primary"
                    id="continue"
                >
                    ${t("next")} →
                </button>

            </div>

        </main>
    `;


    document.getElementById(
        "continue"
    ).onclick = () => {

        renderQuestion();

    };
}


/* =========================================================
   FINISH
========================================================= */

async function finish(){

    stopTimer();

    state.screen =
        "loading";


    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="center">

            <div class="loader">

                <div class="loader-brain">
                    🧠
                </div>

                <h2>
                    ${t("loading")}
                </h2>

                <p>
                    Javoblar serverda
                    tekshirilmoqda…
                </p>

            </div>

        </main>
    `;


    try{

        const data =
            await api(
                "/api/test/submit",
                {
                    method:"POST",

                    body:
                        JSON.stringify({
                            test_type:"iq",

                            answers:
                                state.answers
                                    .slice(
                                        0,
                                        QUESTION_COUNT
                                    ),

                            profile:
                                state.profile,

                            battle_id:
                                state.battleId
                        })
                }
            );


        state.result =
            data;

        clearSession();

        renderResult();

    }
    catch(error){

        console.error(
            "Finish error:",
            error
        );


        if(
            error.status === 402
        ){

            openPayment();

            return;
        }


        localStorage.setItem(
            "iq_pending_answers",
            JSON.stringify(
                state.answers
            )
        );


        document.getElementById(
            "app"
        ).innerHTML = `

            <main class="center">

                <div class="panel">

                    <h2>
                        ${t("error")}
                    </h2>

                    <p>
                        Javoblar qurilmada
                        saqlandi.
                        Internetni tiklab,
                        qayta urinishingiz mumkin.
                    </p>

                    <button
                        class="primary"
                        id="retry"
                    >
                        QAYTA URINISH
                    </button>

                    <button
                        class="ghost"
                        id="home"
                    >
                        ${t("home")}
                    </button>

                </div>

            </main>
        `;


        document.getElementById(
            "retry"
        ).onclick = finish;


        document.getElementById(
            "home"
        ).onclick =
            renderHome;
    }
}


/* =========================================================
   RESULT
========================================================= */

function renderResult(){

    const result =
        state.result;


    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="result">

            <div
                class="result-glow"
            ></div>


            <div class="result-card">

                <div
                    class="result-mark"
                >
                    ✓
                </div>


                <span>
                    ${t("done")}
                </span>


                <strong>
                    ${result.iq}
                </strong>


                <small>
                    ${t("score")}
                </small>


                <div
                    class="result-stats"
                >

                    <div>

                        <b>
                            ${result.correct}
                            /
                            ${result.total}
                        </b>

                        <small>
                            ${t("correct")}
                        </small>

                    </div>


                    <div>

                        <b>
                            ${formatTime(
                                Math.floor(
                                    (
                                        Date.now()
                                        -
                                        state.startedAt
                                    ) / 1000
                                )
                            )}
                        </b>

                        <small>
                            ${t("time")}
                        </small>

                    </div>


                    <div>

                        <b>
                            #${result.rank || "—"}
                        </b>

                        <small>
                            REYTING
                        </small>

                    </div>

                </div>


                <button
                    class="primary"
                    id="share"
                >
                    ${t("share")} ↗
                </button>


                <button
                    class="ghost"
                    id="home"
                >
                    ${t("home")}
                </button>

            </div>

        </main>
    `;


    document.getElementById(
        "home"
    ).onclick =
        renderHome;


    document.getElementById(
        "share"
    ).onclick =
        shareResult;
}


/* =========================================================
   SHARE
========================================================= */

async function shareResult(){

    const text =
        `🧠 IQ TEST BOT\n\n` +
        `Mening IQ-style scorem: ` +
        `${state.result?.iq}\n` +
        `18 ta mantiqiy puzzle.`;

    try{

        if(
            navigator.share
        ){

            await navigator.share({
                text
            });

        }

        else if(
            navigator.clipboard
        ){

            await navigator.clipboard.writeText(
                text
            );

            toast(
                "Natija nusxalandi."
            );
        }

    }
    catch{}
}


/* =========================================================
   PAYMENT
========================================================= */

function openPayment(){

    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="center">

            <div class="payment">

                <div
                    class="payment-icon"
                >
                    💳
                </div>


                <h2>
                    IQ TEST
                </h2>


                <p>
                    ${t("paytext")}
                </p>


                <div class="amount">
                    5 000 so‘m
                </div>


                <button
                    class="primary"
                    id="pay"
                >
                    ${t("payment")}
                </button>


                <button
                    class="ghost"
                    id="cancel"
                >
                    ${t("cancel")}
                </button>


                <div id="payStatus"></div>

            </div>

        </main>
    `;


    document.getElementById(
        "cancel"
    ).onclick =
        renderHome;


    document.getElementById(
        "pay"
    ).onclick =
        createPayment;
}


async function createPayment(){

    const button =
        document.getElementById(
            "pay"
        );

    button.disabled = true;


    try{

        const data =
            await api(
                "/api/payment/create",
                {
                    method:"POST",

                    body:
                        JSON.stringify({
                            purpose:"retest"
                        })
                }
            );


        state.paymentId =
            data.payment_id;


        document.getElementById(
            "payStatus"
        ).innerHTML = `

            <div class="pay-info">

                <b>
                    💳
                    ${Number(
                        data.amount
                    ).toLocaleString(
                        "uz-UZ"
                    )}
                    so‘m
                </b>

                <p>
                    Botdagi to‘lov xabarini
                    oching, kartaga o‘tkazing
                    va chek yuboring.
                </p>


                <button
                    class="secondary"
                    id="openBot"
                >
                    TO‘LOVNI BOTDA YAKUNLASH
                </button>

            </div>
        `;


        document.getElementById(
            "openBot"
        ).onclick = () => {

            if(
                tg?.openTelegramLink
            ){

                tg.openTelegramLink(
                    data.bot_link
                );

            }
            else{

                location.href =
                    data.bot_link;
            }
        };


        pollPayment();

    }
    catch(error){

        toast(
            error.message ||
            t("error")
        );

        button.disabled = false;
    }
}


function pollPayment(){

    let tries = 0;


    const check =
        async () => {

            if(
                !state.paymentId
            )
                return;


            if(
                tries++ > 120
            )
                return;


            try{

                const data =
                    await api(
                        `/api/payment/${state.paymentId}`
                    );


                if(
                    data.status ===
                    "approved"
                ){

                    toast(
                        "✅ To‘lov tasdiqlandi"
                    );


                    setTimeout(
                        () =>
                            start("iq"),
                        400
                    );

                    return;
                }


                if(
                    data.status ===
                    "rejected"
                ){

                    toast(
                        "❌ To‘lov rad etildi"
                    );

                    return;
                }

            }
            catch{}


            setTimeout(
                check,
                3000
            );
        };


    check();
}


/* =========================================================
   BATTLE
========================================================= */

function battleScreen(){

    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="center">

            <div class="battle-panel">

                <div
                    class="battle-logo"
                >
                    ⚔️
                </div>


                <h2>
                    ${t("battle")}
                </h2>


                <p>
                    Har bir ishtirokchi
                    mustaqil 18 savolni
                    yechadi.
                    G‘olib yakuniy IQ score
                    bo‘yicha aniqlanadi.
                </p>


                <button
                    class="primary"
                    id="create"
                >
                    ${t("create")}
                </button>


                <div class="divider">
                    yoki
                </div>


                <input
                    id="battleCode"
                    maxlength="4"
                    inputmode="numeric"
                    placeholder="4 xonali kod"
                >


                <button
                    class="secondary"
                    id="join"
                >
                    ${t("join")}
                </button>


                <button
                    class="ghost"
                    id="back"
                >
                    ${t("back")}
                </button>

            </div>

        </main>
    `;


    document.getElementById(
        "back"
    ).onclick =
        renderHome;


    document.getElementById(
        "create"
    ).onclick =
        createBattle;


    document.getElementById(
        "join"
    ).onclick =
        joinBattle;
}


async function createBattle(){

    try{

        const data =
            await api(
                "/api/battle/create",
                {
                    method:"POST",
                    body:"{}"
                }
            );


        state.battleId =
            data.battle_id;


        state.paymentId =
            data.payment_id;


        showBattleWaiting(
            data
        );

    }
    catch(error){

        toast(
            error.message ||
            t("error")
        );
    }
}


async function joinBattle(){

    const code =
        document
            .getElementById(
                "battleCode"
            )
            .value
            .trim();


    if(
        code.length !== 4
    ){

        toast(
            "4 xonali kod kiriting"
        );

        return;
    }


    try{

        const data =
            await api(
                "/api/battle/join",
                {
                    method:"POST",

                    body:
                        JSON.stringify({
                            code
                        })
                }
            );


        state.battleId =
            data.battle_id;


        state.paymentId =
            data.payment_id;


        showBattleWaiting(
            data
        );

    }
    catch(error){

        toast(
            error.message ||
            t("error")
        );
    }
}


function showBattleWaiting(
    data
){

    document.getElementById(
        "app"
    ).innerHTML = `

        <main class="center">

            <div class="battle-panel">

                <div
                    class="battle-logo"
                >
                    ⚔️
                </div>


                <h2>
                    BATTLE KODI
                </h2>


                <div
                    class="battle-code"
                >
                    ${data.code}
                </div>


                <p>
                    Do‘stingiz shu kod bilan
                    qo‘shilsin.
                    Har ikki ishtirokchining
                    to‘lovi tasdiqlangach,
                    Battle boshlanadi.
                </p>


                <button
                    class="primary"
                    id="payBattle"
                >
                    ${t("payment")}
                </button>


                <button
                    class="ghost"
                    id="home"
                >
                    ${t("home")}
                </button>

            </div>

        </main>
    `;


    document.getElementById(
        "home"
    ).onclick =
        renderHome;


    document.getElementById(
        "payBattle"
    ).onclick =
        async () => {

            try{

                const payment =
                    await api(
                        "/api/payment/create",
                        {
                            method:"POST",

                            body:
                                JSON.stringify({
                                    purpose:"battle"
                                })
                        }
                    );


                state.paymentId =
                    payment.payment_id;


                if(
                    tg?.openTelegramLink
                ){

                    tg.openTelegramLink(
                        payment.bot_link
                    );

                }


                pollBattlePayment();

            }
            catch(error){

                toast(
                    error.message ||
                    t("error")
                );
            }

        };
}


function pollBattlePayment(){

    let tries = 0;


    const check =
        async () => {

            if(
                tries++ > 200
            )
                return;


            try{

                const payment =
                    await api(
                        `/api/payment/${state.paymentId}`
                    );


                if(
                    payment.status ===
                    "approved"
                ){

                    try{

                        const battle =
                            await api(
                                `/api/battle/${state.battleId}`
                            );


                        if(
                            battle.status ===
                            "ready"
                        ){

                            toast(
                                "✅ Battle boshlandi"
                            );

                            start(
                                "iq",
                                state.battleId
                            );

                            return;
                        }

                        toast(
                            "✅ To‘lov tasdiqlandi. Do‘stingizni kuting…"
                        );

                    }
                    catch{}

                }

            }
            catch{}


            setTimeout(
                check,
                3000
            );
        };


    check();
}


/* =========================================================
   TOAST
========================================================= */

function toast(message){

    let element =
        document.getElementById(
            "toast"
        );


    if(!element){

        element =
            document.createElement(
                "div"
            );

        element.id =
            "toast";

        document.body.appendChild(
            element
        );
    }


    element.textContent =
        message;


    element.classList.add(
        "show"
    );


    setTimeout(
        () =>
            element.classList.remove(
                "show"
            ),
        2500
    );
}


/* =========================================================
   ONLINE / OFFLINE
========================================================= */

window.addEventListener(
    "online",
    () => {

        if(
            state.screen ===
            "test"
        ){

            toast(
                "🌐 Internet qaytdi"
            );
        }

    }
);


window.addEventListener(
    "offline",
    () => {

        if(
            state.screen ===
            "test"
        ){

            toast(
                "📴 Offline rejim. Test davom etadi."
            );
        }

    }
);


window.addEventListener(
    "beforeunload",
    () => {

        if(
            state.screen ===
            "test"
        ){

            saveSession();
        }

    }
);


/* =========================================================
   START APP
========================================================= */

init();

})();