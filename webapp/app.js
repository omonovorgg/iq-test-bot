(() => {
    "use strict";

    const tg = window.Telegram?.WebApp || null;

    if (tg) {
        tg.ready();
        tg.expand();

        try {
            tg.setHeaderColor("#070914");
            tg.setBackgroundColor("#070914");
        } catch (_) {}
    }

    const app = document.getElementById("app");

    const state = {
        initData: tg?.initData || "",

        user: null,
        products: [],
        botUsername: "",

        screen: "home",

        testType: null,
        questions: [],
        index: 0,
        answers: [],

        profile: {},

        completed: {
            iq: false,
            eq: false,
            pq: false
        },

        battleId: null,
        busy: false
    };

    /* =========================================================
       HELPERS
    ========================================================= */

    const $ = (selector) => document.querySelector(selector);

    function esc(value) {
        return String(value ?? "")
            .replace(/[&<>"']/g, (char) => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            }[char]));
    }

    function toast(message) {
        let el = document.querySelector(".toast");

        if (!el) {
            el = document.createElement("div");
            el.className = "toast";
            document.body.appendChild(el);
        }

        el.textContent = message;
        el.classList.add("show");

        clearTimeout(el._timer);

        el._timer = setTimeout(() => {
            el.classList.remove("show");
        }, 2800);
    }

    function goBack() {
        renderHome();
    }

    async function api(path, options = {}) {

        const headers = {
            "Content-Type": "application/json"
        };

        if (state.initData) {
            headers["X-Telegram-Init-Data"] = state.initData;
        }

        const response = await fetch(path, {
            ...options,
            headers: {
                ...headers,
                ...(options.headers || {})
            }
        });

        const text = await response.text();

        let data = {};

        try {
            data = text ? JSON.parse(text) : {};
        } catch (_) {
            data = {
                detail: text || "Server javobi noto‘g‘ri."
            };
        }

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.error ||
                `Server xatosi: ${response.status}`
            );
        }

        return data;
    }

    function saveProgress() {
        try {
            localStorage.setItem(
                "iq_current_progress",
                JSON.stringify({
                    testType: state.testType,
                    index: state.index,
                    answers: state.answers,
                    profile: state.profile
                })
            );
        } catch (_) {}
    }

    function clearProgress() {
        try {
            localStorage.removeItem("iq_current_progress");
        } catch (_) {}
    }

    function markCompleted(type) {
        state.completed[type] = true;

        try {
            localStorage.setItem(`done_${type}`, "1");
        } catch (_) {}
    }

    function loadCompleted() {
        try {
            state.completed.iq =
                localStorage.getItem("done_iq") === "1";

            state.completed.eq =
                localStorage.getItem("done_eq") === "1";

            state.completed.pq =
                localStorage.getItem("done_pq") === "1";
        } catch (_) {}
    }

    /* =========================================================
       IQ — EXACTLY 18 QUESTIONS
       Backend answer indexes:
       0,0,0,0,1,2,0,0,2,0,0,2,0,1,1,1,2,1
    ========================================================= */

    const IQ = [

        {
            type: "sequence",
            title: "Ketma-ketlikdagi keyingi holatni toping.",
            visual: ["●", "●●", "●●●", "●●●●", "?"],
            options: ["●●●●●", "●●", "●●●●●●", "●"],
            correct: 0
        },

        {
            type: "sequence",
            title: "Strelka har safar 45° o‘ngga aylanmoqda. Keyingi holat?",
            visual: ["↑", "↗", "→", "↘", "?"],
            options: ["↓", "↙", "←", "↖"],
            correct: 0
        },

        {
            type: "sequence",
            title: "Shakllar ketma-ketligi qanday davom etadi?",
            visual: ["△", "□", "○", "△", "?"],
            options: ["□", "○", "◇", "△"],
            correct: 0
        },

        {
            type: "sequence",
            title: "Nuqtalar soni har safar 2 taga ortmoqda.",
            visual: ["•", "•••", "•••••", "?"],
            options: ["•••••••", "••••", "••••••", "••"],
            correct: 0
        },

        {
            type: "letters",
            title: "Har safar bitta harf tashlab ketilmoqda.",
            visual: ["A", "C", "E", "G", "?"],
            options: ["H", "I", "J", "K"],
            correct: 1
        },

        {
            type: "numbers",
            title: "Qonuniyatni aniqlang.",
            visual: ["2", "4", "8", "16", "?"],
            options: ["20", "24", "32", "36"],
            correct: 2
        },

        {
            type: "rotation",
            title: "Belgi har safar 90° soat strelkasi bo‘yicha aylanadi.",
            visual: ["↑", "→", "↓", "?"],
            options: ["←", "↗", "↘", "↑"],
            correct: 0
        },

        {
            type: "colors",
            title: "Ranglar spektr bo‘yicha davom etmoqda. Keyingisini toping.",
            visual: ["🟣", "🔵", "🟢", "🟡", "?"],
            options: ["🟠", "🔴", "🟣", "⚫"],
            correct: 0
        },

        {
            type: "numbers",
            title: "Har bir son avvalgisining 2 baravari.",
            visual: ["3", "6", "12", "24", "?"],
            options: ["36", "42", "48", "54"],
            correct: 2
        },

        {
            type: "pairs",
            title: "Har bir juftlikda chap va o‘ng belgi bir-biriga qarama-qarshi.",
            visual: ["▲▼", "■□", "●○", "?"],
            options: ["◆◇", "▲△", "■■", "○●"],
            correct: 0
        },

        {
            type: "rotation",
            title: "Strelka har safar 45° ga buriladi.",
            visual: ["↑", "↗", "→", "↘", "?"],
            options: ["↓", "↙", "←", "↖"],
            correct: 0
        },

        {
            type: "numbers",
            title: "1, 4, 9, 16 ketma-ketligining keyingi hadi?",
            visual: ["1", "4", "9", "16", "?"],
            options: ["20", "24", "25", "36"],
            correct: 2
        },

        {
            type: "repeat",
            title: "Ikki belgidan iborat sikl takrorlanmoqda.",
            visual: ["◆", "○", "◆", "○", "?"],
            options: ["◆", "○", "□", "△"],
            correct: 0
        },

        {
            type: "letters",
            title: "Ketma-ketlikni davom ettiring.",
            visual: ["B", "D", "F", "H", "?"],
            options: ["I", "J", "K", "L"],
            correct: 1
        },

        {
            type: "numbers",
            title: "Har safar 5 qo‘shilmoqda.",
            visual: ["5", "10", "15", "20", "?"],
            options: ["24", "25", "30", "35"],
            correct: 1
        },

        {
            type: "mapping",
            title: "Chapdagi son 2 ga ko‘paytirilmoqda.",
            visual: ["1 → 2", "2 → 4", "3 → 6", "4 → ?"],
            options: ["7", "8", "9", "10"],
            correct: 1
        },

        {
            type: "odd",
            title: "Qaysi katak boshqalardan farq qiladi?",
            visual: ["○", "○", "○", "?"],
            options: ["○", "○", "□", "○"],
            correct: 2
        },

        {
            type: "numbers",
            title: "Har safar son 3 ga bo‘linmoqda.",
            visual: ["81", "27", "9", "3", "?"],
            options: ["0", "1", "2", "6"],
            correct: 1
        }
    ];

    /* =========================================================
       EQ
    ========================================================= */

    const EQ = [

        {
            title: "Do‘stingiz xafa bo‘lib turibdi, lekin sababini aytmayapti. Eng foydali birinchi qadam?",
            options: [
                "Uni tinch tinglash va gapirishga tayyor ekaningizni bildirish",
                "Darhol nima qilish kerakligini aytish",
                "Mavzuni o‘zgartirish",
                "Nega xafa bo‘lganini o‘zingiz taxmin qilish"
            ],
            correct: 0
        },

        {
            title: "Jamoada ikki kishi bir-birining fikrini noto‘g‘ri tushundi. Siz nima qilasiz?",
            options: [
                "Kim aybdorligini aniqlaysiz",
                "Ikkala tomonning fikrini alohida tinglaysiz",
                "Bahs tugaguncha aralashmaysiz",
                "O‘zingizning fikringizni majburan qabul qildirasiz"
            ],
            correct: 1
        },

        {
            title: "Sizga tanqid aytildi va uning bir qismi adolatsiz tuyuldi. Eng konstruktiv yo‘l?",
            options: [
                "Darhol javob qaytarish",
                "Foydali qismini ajratib, qolganini aniqlashtirish",
                "Hammasini inkor qilish",
                "Suhbatni tugatish"
            ],
            correct: 1
        },

        {
            title: "Muhim suhbatdan oldin hissiyotlaringiz kuchayganini sezsangiz?",
            options: [
                "Bir oz tanaffus qilib, fikrlaringizni tartibga solish",
                "Hissiyot bilan darhol gapirish",
                "Suhbatni butunlay bekor qilish",
                "Boshqa odamni ayblash"
            ],
            correct: 0
        },

        {
            title: "Suhbatdoshingiz odatdagidan ancha jim bo‘lib qoldi.",
            options: [
                "Darhol sababini o‘zingiz belgilash",
                "Muloyim tarzda holatini so‘rash",
                "Buni atay qilayotganini aytish",
                "Umuman e’tibor bermaslik"
            ],
            correct: 1
        },

        {
            title: "Siz xato qilganingizni tushundingiz.",
            options: [
                "Xatoni yashirish",
                "Bahona topish",
                "Tan olish va tuzatishga harakat qilish",
                "Boshqa odamni ayblash"
            ],
            correct: 2
        },

        {
            title: "Do‘stingiz sizning fikringizga qat’iyan rozi emas.",
            options: [
                "Uni gapirtirmaslik",
                "Nima uchun shunday o‘ylayotganini tushunishga urinish",
                "Bahsni yutishga harakat qilish",
                "Suhbatni darhol tugatish"
            ],
            correct: 1
        },

        {
            title: "Jahlingiz chiqqan paytda muhim xabar yozishingiz kerak.",
            options: [
                "Darhol yuborish",
                "Tanaffus qilib, keyin qayta o‘qish",
                "Ataylab keskinroq yozish",
                "Umuman tushuntirmaslik"
            ],
            correct: 1
        },

        {
            title: "Kimdir sizga samimiy maqtov aytdi.",
            options: [
                "Boshqalarni undan past ko‘rish",
                "Oddiy minnatdorchilik bildirish",
                "Maqtovni rad etish",
                "Darhol o‘zingizni maqtash"
            ],
            correct: 1
        },

        {
            title: "Yangi odam jamoaga qo‘shildi va o‘zini noqulay his qilmoqda.",
            options: [
                "Uni o‘zi moslashishiga tashlab qo‘yish",
                "Suhbatga qo‘shilishiga yordam berish",
                "Uni sinab ko‘rish",
                "U haqida boshqalardan so‘rash"
            ],
            correct: 1
        },

        {
            title: "Ikki xil fikr bo‘yicha bahs ketmoqda. Qaysi yondashuv konstruktivroq?",
            options: [
                "Faktlarni tekshirish",
                "Kim balandroq gapirsa, o‘sha haq",
                "Bahsni cho‘zish",
                "Mavzuni almashtirish"
            ],
            correct: 0
        },

        {
            title: "Boshqa odamning hislarini tushunishga harakat qilish nima deyiladi?",
            options: [
                "Empatiya",
                "Raqobat",
                "Impuls",
                "Perfeksionizm"
            ],
            correct: 0
        }
    ];

    /* =========================================================
       PROCRASTINATION
    ========================================================= */

    const PQ = [

        {
            title: "Katta vazifani boshlash qiyin bo‘lyapti.",
            options: [
                "Uni 2 daqiqalik eng kichik qadamga bo‘lish",
                "Kayfiyat kelishini kutish",
                "Telefonni tekshirish",
                "Vazifani keyinga surish"
            ],
            correct: 0
        },

        {
            title: "Deadline hali uzoq. Eng barqaror yondashuv?",
            options: [
                "Vazifani bosqichlarga bo‘lib rejalash",
                "Oxirgi kunga qoldirish",
                "Umuman reja qilmaslik",
                "Faqat deadline kuni boshlash"
            ],
            correct: 0
        },

        {
            title: "Telefon bildirishnomalari sizni tez-tez chalg‘itmoqda.",
            options: [
                "Keraksiz bildirishnomalarni vaqtincha o‘chirish",
                "Har birini darhol tekshirish",
                "Telefonni ish stolining oldiga qo‘yish",
                "Har safar boshqa ilovaga kirish"
            ],
            correct: 0
        },

        {
            title: "Vazifa juda katta ko‘rinmoqda.",
            options: [
                "Uni kichik, aniq bosqichlarga ajratish",
                "Hammasini birdan tugatishga urinish",
                "Boshlamaslik",
                "Faqat reja haqida o‘ylash"
            ],
            correct: 0
        },

        {
            title: "Noaniq vazifalarni ko‘pincha qoldirasiz. Eng ehtimoliy sabab?",
            options: [
                "Faqat vaqt yetishmasligi",
                "Noaniqlik boshlashni qiyinlashtirishi mumkin",
                "Har doim dangasalik",
                "Har doim charchoq"
            ],
            correct: 1
        },

        {
            title: "Rejangiz kutilmaganda buzildi.",
            options: [
                "Rejani yangi sharoitga moslashtirish",
                "Butun kunni tashlab yuborish",
                "O‘zingizni ayblash",
                "Hammasini ertaga surish"
            ],
            correct: 0
        },

        {
            title: "Ishlashga kayfiyat yo‘q.",
            options: [
                "Kichik va oson qadamdan boshlash",
                "Kayfiyat kelishini kutish",
                "O‘yin ochish",
                "Ishni bekor qilish"
            ],
            correct: 0
        },

        {
            title: "Kichik mukofot tizimi qachon foydali bo‘lishi mumkin?",
            options: [
                "Tugallangan ishni kichik mukofot bilan bog‘lashda",
                "Ishni boshlashdan oldin mukofot olishda",
                "Faqat juda katta vazifalarda",
                "Hech qachon"
            ],
            correct: 0
        },

        {
            title: "Vazifa taxminan 30 daqiqada tugaydi.",
            options: [
                "Hozir boshlash",
                "Bir soat qo‘shimcha reja qilish",
                "Ertaga qoldirish",
                "Boshqa ish topish"
            ],
            correct: 0
        },

        {
            title: "Brauzerda keraksiz 12 ta tab ochiq.",
            options: [
                "Keraksizlarini yopish",
                "Yana bir tab ochish",
                "Hammasini qoldirish",
                "Telefonni tekshirish"
            ],
            correct: 0
        },

        {
            title: "Ishni boshlashdan oldin eng foydali savol?",
            options: [
                "Keyingi aniq qadam nima?",
                "Qanday qilib mukammal qilish mumkin?",
                "Qachon kayfiyatim keladi?",
                "Qachon tanaffus qilaman?"
            ],
            correct: 0
        },

        {
            title: "Bugungi ishning bir qismi tugamay qoldi.",
            options: [
                "Qolgan qismini aniq vaqtga rejalash",
                "Hammasini tashlash",
                "O‘zingizni ayblash",
                "Sabab izlab vaqt o‘tkazish"
            ],
            correct: 0
        }
    ];

    /* =========================================================
       VISUAL PUZZLE
    ========================================================= */

    function renderVisual(question) {

        if (!question.visual) {
            return "";
        }

        return `
            <div class="visual-puzzle">
                ${question.visual.map((item) => `
                    <div class="puzzle-cell ${item === "?" ? "question" : ""}">
                        ${esc(item)}
                    </div>
                `).join("")}
            </div>
        `;
    }

    function optionVisual(question, option) {

        if (question.type === "sequence" ||
            question.type === "rotation" ||
            question.type === "colors" ||
            question.type === "pairs" ||
            question.type === "repeat") {

            return `<span class="option-symbol">${esc(option)}</span>`;
        }

        return "";
    }

    /* =========================================================
       HOME
    ========================================================= */

    function renderHome() {

        state.screen = "home";

        app.innerHTML = `
            <main class="page home">

                <header class="brand-row">

                    <div class="brand">
                        <div class="brand-mark">IQ</div>

                        <div class="brand-text">
                            <b>IQ TEST BOT</b>
                            <small>SMART THINKING</small>
                        </div>
                    </div>

                    <button
                        class="lang-mini"
                        onclick="openLanguage()"
                    >
                        UZ
                    </button>

                </header>

                <section class="hero">

                    <div class="brain-glow">
                        🧠
                    </div>

                    <div class="eyebrow">
                        18 TA MANTIQIY PUZZLE
                    </div>

                    <h1>
                        IQ darajangizni
                        <br>
                        <span>sinab ko‘ring</span>
                    </h1>

                    <p>
                        18 ta mantiqiy puzzle orqali
                        fikrlash qobiliyatingizni sinang.
                    </p>

                </section>

                <section class="cards">

                    ${testCard(
                        "iq",
                        "🧠",
                        "IQ",
                        "18 ta mantiqiy puzzle",
                        true
                    )}

                    ${testCard(
                        "eq",
                        "🎭",
                        "EQ",
                        "IQ testidan keyin ochiladi"
                    )}

                    ${testCard(
                        "pq",
                        "⏳",
                        "PROKRASTINATSIYA",
                        "EQ testidan keyin ochiladi"
                    )}

                    ${testCard(
                        "full",
                        "⭐",
                        "SIZ QANDAY INSONSIZ",
                        "Uchala testdan keyin ochiladi"
                    )}

                </section>

                <button
                    class="battle-card"
                    onclick="renderBattle()"
                >

                    <div class="battle-icon">
                        ⚔️
                    </div>

                    <div class="battle-content">
                        <b>Do‘st bilan battle</b>
                        <small>
                            Kimning IQ natijasi yuqori?
                        </small>
                    </div>

                    <div class="battle-arrow">
                        →
                    </div>

                </button>

                <div class="live">
                    <span class="live-dot"></span>
                    <b id="liveCount">0</b>
                    kishi hozir faol
                </div>

                <div class="mini-note">
                    Natija • Reyting • Sertifikat
                </div>

            </main>
        `;

        loadCounter();
    }

    function testCard(
        code,
        icon,
        title,
        subtitle,
        active = false
    ) {

        const done = state.completed[code];

        let locked = false;

        if (code === "eq") {
            locked = !state.completed.iq;
        }

        if (code === "pq") {
            locked = !state.completed.eq;
        }

        if (code === "full") {
            locked = !(
                state.completed.iq &&
                state.completed.eq &&
                state.completed.pq
            );
        }

        let classes = "test-card";

        if (active && !locked) {
            classes += " active";
        }

        if (locked) {
            classes += " locked";
        }

        if (done) {
            classes += " done";
        }

        let right = "→";

        if (locked) {
            right = `
                <span class="lock-text">
                    🔒<br>
                    ${code === "eq"
                        ? "IQ dan keyin"
                        : code === "pq"
                            ? "EQ dan keyin"
                            : "Uchala testdan keyin"
                    }
                </span>
            `;
        }

        if (done) {
            right = "✓";
        }

        return `
            <button
                class="${classes}"
                onclick="cardClick('${code}')"
                data-code="${code}"
            >

                <div class="card-icon">
                    ${done ? "✓" : icon}
                </div>

                <div class="card-content">

                    <b>${esc(title)}</b>

                    <small>
                        ${done ? "Tugallangan" : esc(subtitle)}
                    </small>

                </div>

                <div class="card-right">
                    ${right}
                </div>

            </button>
        `;
    }

    /* =========================================================
       CARD CLICK
    ========================================================= */

    window.cardClick = async function(code) {

        if (state.busy) {
            return;
        }

        if (code === "iq") {

            try {

                const access = await api("/api/access/iq");

                if (access.allowed) {
                    renderIntro("iq");
                    return;
                }

                await startPayment("iq");

            } catch (error) {

                toast(error.message);

            }

            return;
        }

        if (
            code === "eq" &&
            !state.completed.iq
        ) {
            toast("Avval IQ testini tugating.");
            return;
        }

        if (
            code === "pq" &&
            !state.completed.eq
        ) {
            toast("Avval EQ testini tugating.");
            return;
        }

        if (
            code === "full" &&
            !(
                state.completed.iq &&
                state.completed.eq &&
                state.completed.pq
            )
        ) {
            toast("Avval uchala testni tugating.");
            return;
        }

        if (code === "full") {
            renderFull();
            return;
        }

        renderIntro(code);
    };

    /* =========================================================
       INTRO
    ========================================================= */

    function renderIntro(type) {

        state.testType = type;

        let data;

        if (type === "iq") {

            data = {
                icon: "🧠",
                eyebrow: "18 TA MANTIQIY PUZZLE",
                title: "Aql darajangizni aniqlang",
                desc:
                    "18 ta vizual va mantiqiy puzzle orqali fikrlash, analiz va muammolarni yechish qobiliyatingizni sinang.",
                chips: [
                    "📄 18 ta savol",
                    "∞ Vaqt cheksiz",
                    "🔷 Tasviriy mantiq",
                    "🏅 IQ natijasi"
                ]
            };

        } else if (type === "eq") {

            data = {
                icon: "🎭",
                eyebrow: "HISSIY INTELLEKT",
                title: "EQ darajangizni aniqlang",
                desc:
                    "Murakkab ijtimoiy va hissiy vaziyatlarda qanday qaror qilishingizni tekshiring.",
                chips: [
                    "📄 12 ta savol",
                    "∞ Vaqt cheksiz",
                    "🎭 Vaziyatli test",
                    "📊 EQ tahlil"
                ]
            };

        } else {

            data = {
                icon: "⏳",
                eyebrow: "PROKRASTINATSIYA",
                title: "Ishni keyinga surish odatingizni aniqlang",
                desc:
                    "Vazifalarni boshlash, chalg‘ish va deadline bilan ishlashdagi xatti-harakatlaringizni tahlil qiling.",
                chips: [
                    "📄 12 ta savol",
                    "∞ Vaqt cheksiz",
                    "🎯 Vaziyatli test",
                    "📊 Shaxsiy tahlil"
                ]
            };
        }

        app.innerHTML = `
            <main class="page intro">

                <button
                    class="back"
                    onclick="renderHome()"
                >
                    ← Orqaga
                </button>

                <div class="intro-icon">
                    ${data.icon}
                </div>

                <div class="eyebrow">
                    ${data.eyebrow}
                </div>

                <h1>
                    ${esc(data.title)}
                </h1>

                <p>
                    ${esc(data.desc)}
                </p>

                <div class="chips">
                    ${data.chips.map(item => `
                        <span class="chip">
                            ${esc(item)}
                        </span>
                    `).join("")}
                </div>

                <div class="how-card">

                    <div class="how-title">
                        Qanday ishlaydi?
                    </div>

                    <div class="how-list">

                        <div class="how-item">
                            <span class="how-number">1</span>
                            <span>Har bir savolga o‘zingizning javobingizni tanlaysiz.</span>
                        </div>

                        <div class="how-item">
                            <span class="how-number">2</span>
                            <span>IQ testida savollar bosqichma-bosqich murakkablashadi.</span>
                        </div>

                        <div class="how-item">
                            <span class="how-number">3</span>
                            <span>Vaqt cheklovi yo‘q — tezlikdan ko‘ra to‘g‘ri fikrlash muhim.</span>
                        </div>

                        <div class="how-item">
                            <span class="how-number">4</span>
                            <span>Yakunda natijangiz va keyingi testlar ochiladi.</span>
                        </div>

                    </div>

                </div>

                ${
                    type === "iq"
                    ? `
                        <div class="sample-card">

                            <div class="sample-label">
                                NAMUNA
                            </div>

                            <div class="sample-puzzle">
                                <div class="sample-box">●</div>
                                <div class="sample-box">●●</div>
                                <div class="sample-box">●●●</div>
                                <div class="sample-box">?</div>
                            </div>

                            <div
                                class="mini-note"
                                style="margin-top:12px"
                            >
                                Bu namuna haqiqiy 18 ta savol hisobiga kirmaydi.
                            </div>

                        </div>
                    `
                    : ""
                }

                <button
                    class="primary"
                    onclick="startProfile('${type}')"
                >
                    🚀 Testni boshlash
                    <span>→</span>
                </button>

            </main>
        `;
    }

    /* =========================================================
       PROFILE
    ========================================================= */

    window.startProfile = function(type) {

        state.testType = type;

        let saved = {};

        try {
            saved = JSON.parse(
                localStorage.getItem("iq_profile") || "{}"
            );
        } catch (_) {
            saved = {};
        }

        app.innerHTML = `
            <main class="page profile">

                <button
                    class="back"
                    onclick="renderIntro('${type}')"
                >
                    ← Orqaga
                </button>

                <h1>
                    O‘zingiz haqingizda
                </h1>

                <p>
                    Natijangiz va sertifikat uchun kerakli ma’lumotlarni kiriting.
                </p>

                <label class="form-label">
                    Ism va familiya

                    <input
                        id="fullName"
                        type="text"
                        maxlength="80"
                        autocomplete="name"
                        value="${esc(saved.fullName || "")}"
                        placeholder="Masalan: Muhammad Ali Omonov"
                    >
                </label>

                <div class="two">

                    <label class="form-label">
                        Yosh

                        <input
                            id="age"
                            type="number"
                            min="10"
                            max="100"
                            value="${esc(saved.age || "")}"
                            placeholder="20"
                        >
                    </label>

                    <label class="form-label">
                        Jins

                        <select id="gender">

                            <option value="">
                                Tanlang
                            </option>

                            <option value="Erkak"
                                ${saved.gender === "Erkak" ? "selected" : ""}>
                                Erkak
                            </option>

                            <option value="Ayol"
                                ${saved.gender === "Ayol" ? "selected" : ""}>
                                Ayol
                            </option>

                        </select>

                    </label>

                </div>

                <label class="form-label">
                    Mamlakat

                    <input
                        id="country"
                        type="text"
                        maxlength="50"
                        value="${esc(saved.country || "O‘zbekiston")}"
                        placeholder="O‘zbekiston"
                    >
                </label>

                <button
                    class="primary"
                    onclick="beginTest('${type}')"
                >
                    Davom etish
                    <span>→</span>
                </button>

            </main>
        `;
    };

    window.beginTest = function(type) {

        const fullName =
            ($("#fullName")?.value || "").trim();

        const age =
            ($("#age")?.value || "").trim();

        const gender =
            ($("#gender")?.value || "").trim();

        const country =
            ($("#country")?.value || "").trim();

        if (!fullName) {
            toast("Ism va familiyani kiriting.");
            return;
        }

        if (fullName.length < 3) {
            toast("Ism va familiya juda qisqa.");
            return;
        }

        state.profile = {
            fullName,
            age,
            gender,
            country
        };

        try {
            localStorage.setItem(
                "iq_profile",
                JSON.stringify(state.profile)
            );
        } catch (_) {}

        state.testType = type;

        if (type === "iq") {
            state.questions = IQ;
        } else if (type === "eq") {
            state.questions = EQ;
        } else {
            state.questions = PQ;
        }

        state.index = 0;
        state.answers = [];

        saveProgress();

        renderQuestion();
    };

    /* =========================================================
       QUESTION
    ========================================================= */

    function renderQuestion() {

        const question =
            state.questions[state.index];

        if (!question) {
            finishTest();
            return;
        }

        const total =
            state.questions.length;

        const current =
            state.index + 1;

        const percent =
            Math.round(
                ((current - 1) / total) * 100
            );

        app.innerHTML = `
            <main class="page test">

                <div class="test-top">

                    <button
                        class="test-back"
                        onclick="confirmExit()"
                    >
                        ←
                    </button>

                    <div class="test-title">
                        <b>
                            ${state.testType.toUpperCase()}
                        </b>

                        <small>
                            ${current} / ${total}
                        </small>
                    </div>

                    <div class="test-percent">
                        ${percent}%
                    </div>

                </div>

                <div class="progress">
                    <i style="width:${percent}%"></i>
                </div>

                <div class="question-label">
                    SAVOL ${current}
                </div>

                <h2 class="question-title">
                    ${esc(question.title)}
                </h2>

                ${state.testType === "iq"
                    ? renderVisual(question)
                    : ""
                }

                <div class="options">

                    ${question.options.map((option, index) => `

                        <button
                            class="option"
                            onclick="answerQuestion(${index})"
                        >

                            <span class="option-letter">
                                ${String.fromCharCode(65 + index)}
                            </span>

                            <span class="option-content">
                                ${esc(option)}
                            </span>

                            ${optionVisual(question, option)}

                        </button>

                    `).join("")}

                </div>

            </main>
        `;
    }

    window.answerQuestion = function(index) {

        if (state.busy) {
            return;
        }

        state.busy = true;

        state.answers[state.index] = index;

        saveProgress();

        setTimeout(() => {

            state.busy = false;

            state.index++;

            if (
                state.index >=
                state.questions.length
            ) {

                finishTest();

                return;
            }

            renderQuestion();

        }, 100);
    };

    window.confirmExit = function() {

        const leave = confirm(
            "Testni tark etmoqchimisiz?\n\n" +
            "Hozirgi javoblaringiz qurilmada saqlanadi."
        );

        if (leave) {
            renderHome();
        }
    };

    /* =========================================================
       FINISH
    ========================================================= */

    async function finishTest() {

        if (state.busy) {
            return;
        }

        state.busy = true;

        app.innerHTML = `
            <main class="page loading">

                <div class="loader"></div>

                <h2>
                    Natija hisoblanmoqda
                </h2>

                <p>
                    Bir oz kuting...
                </p>

            </main>
        `;

        try {

            const result =
                await api("/api/test/submit", {
                    method: "POST",

                    body: JSON.stringify({
                        test_type: state.testType,

                        answers: state.answers,

                        profile: state.profile,

                        battle_id: state.battleId || null
                    })
                });

            clearProgress();

            markCompleted(state.testType);

            renderResult(result);

        } catch (error) {

            console.error(error);

            app.innerHTML = `
                <main class="page error">

                    <div
                        class="result-icon"
                        style="margin-top:30px"
                    >
                        ⚠️
                    </div>

                    <h2>
                        Natijani saqlashda xatolik
                    </h2>

                    <p>
                        ${esc(error.message)}
                    </p>

                    <button
                        class="primary"
                        onclick="renderQuestion()"
                    >
                        Qayta urinish
                    </button>

                </main>
            `;

        } finally {

            state.busy = false;
        }
    }

    /* =========================================================
       RESULT
    ========================================================= */

    function renderResult(result) {

        const type =
            state.testType;

        const score =
            Number(
                result.score ??
                result.iq ??
                0
            );

        const correct =
            Number(
                result.correct ??
                0
            );

        const total =
            state.questions.length;

        let title = "Natijangiz";

        let icon = "🧠";

        if (type === "eq") {
            title = "EQ natijangiz";
            icon = "🎭";
        }

        if (type === "pq") {
            title = "Prokrastinatsiya natijangiz";
            icon = "⏳";
        }

        let label = "Natija";

        if (type === "iq") {

            if (score >= 125) {
                label = "Juda yuqori ko‘rsatkich";
            } else if (score >= 115) {
                label = "Yuqori ko‘rsatkich";
            } else if (score >= 100) {
                label = "O‘rtacha ko‘rsatkich";
            } else {
                label = "Rivojlantirish mumkin";
            }

        } else if (type === "eq") {

            label =
                score >= 80
                    ? "Yaxshi hissiy ko‘rsatkich"
                    : "Rivojlantirish mumkin";

        } else {

            label =
                score >= 70
                    ? "Prokrastinatsiya nazorat ostida"
                    : "Keyinga surish odati yuqori";
        }

        app.innerHTML = `
            <main class="page result">

                <div class="result-icon">
                    ${icon}
                </div>

                <div class="eyebrow">
                    TEST YAKUNLANDI
                </div>

                <h1>
                    ${title}
                </h1>

                <div class="score">
                    ${score}
                </div>

                <div class="score-label">
                    ${label}
                </div>

                <div class="result-main-card">

                    <span>
                        To‘g‘ri javoblar
                    </span>

                    <strong>
                        ${correct}/${total}
                    </strong>

                </div>

                <div class="metrics">

                    <div class="metric">

                        <div class="metric-icon">
                            🎯
                        </div>

                        <b>
                            ${Math.round(
                                (correct / total) * 100
                            )}%
                        </b>

                        <small>
                            Aniqlik
                        </small>

                    </div>

                    <div class="metric">

                        <div class="metric-icon">
                            🧠
                        </div>

                        <b>
                            ${type === "iq"
                                ? "IQ"
                                : type === "eq"
                                    ? "EQ"
                                    : "PQ"
                            }
                        </b>

                        <small>
                            Test turi
                        </small>

                    </div>

                    <div class="metric">

                        <div class="metric-icon">
                            🏆
                        </div>

                        <b>
                            ${result.rank
                                ? "#" + result.rank
                                : "—"
                            }
                        </b>

                        <small>
                            Reyting
                        </small>

                    </div>

                </div>

                <p class="result-text">
                    Bu natija IQ TEST BOT ichidagi
                    mahsulot ko‘rsatkichi hisoblanadi.
                    U klinik yoki standartlashtirilgan
                    psixologik tashxis o‘rnini bosmaydi.
                </p>

                ${nextButton(type)}

                <button
                    class="ghost"
                    onclick="renderHome()"
                >
                    Bosh sahifaga
                </button>

            </main>
        `;
    }

    function nextButton(type) {

        if (type === "iq") {

            return `
                <button
                    class="primary"
                    onclick="renderIntro('eq')"
                >
                    🎭 EQ testiga o‘tish
                    <span>→</span>
                </button>
            `;
        }

        if (type === "eq") {

            return `
                <button
                    class="primary"
                    onclick="renderIntro('pq')"
                >
                    ⏳ PQ testiga o‘tish
                    <span>→</span>
                </button>
            `;
        }

        return `
            <button
                class="primary"
                onclick="renderFull()"
            >
                ⭐ To‘liq tahlil
                <span>→</span>
            </button>
        `;
    }

    /* =========================================================
       FULL PROFILE
    ========================================================= */

    window.renderFull = function() {

        if (
            !(
                state.completed.iq &&
                state.completed.eq &&
                state.completed.pq
            )
        ) {

            toast(
                "Avval IQ, EQ va prokrastinatsiya testlarini tugating."
            );

            return;
        }

        app.innerHTML = `
            <main class="page result">

                <div class="result-icon">
                    ⭐
                </div>

                <div class="eyebrow">
                    TO‘LIQ TAHLIL
                </div>

                <h1>
                    Siz qanday insonsiz?
                </h1>

                <p class="result-text">
                    IQ, EQ va prokrastinatsiya
                    natijalaringiz asosida
                    shaxsiy profilingiz shakllantiriladi.
                </p>

                <div class="result-main-card">
                    <span>🧠 IQ</span>
                    <strong>✓ Tugallangan</strong>
                </div>

                <div class="result-main-card">
                    <span>🎭 EQ</span>
                    <strong>✓ Tugallangan</strong>
                </div>

                <div class="result-main-card">
                    <span>⏳ PQ</span>
                    <strong>✓ Tugallangan</strong>
                </div>

                <p class="result-text">
                    To‘liq individual tahlil backend
                    natijalari asosida kengaytiriladi.
                </p>

                <button
                    class="primary"
                    onclick="renderHome()"
                >
                    Bosh sahifaga
                    <span>→</span>
                </button>

            </main>
        `;
    };

    /* =========================================================
       PAYMENT
    ========================================================= */

    async function startPayment(productCode) {

        try {

            const result =
                await api("/api/payment/start", {
                    method: "POST",

                    body: JSON.stringify({
                        product_code: productCode
                    })
                });

            if (result.free) {
                renderIntro(productCode);
                return;
            }

            toast(
                "To‘lov ma’lumotlari Telegram chatga yuborildi."
            );

            setTimeout(() => {

                const username =
                    state.botUsername ||
                    "iqtest_ubot";

                const url =
                    `https://t.me/${username}`;

                if (tg?.openTelegramLink) {
                    tg.openTelegramLink(url);
                } else {
                    window.location.href = url;
                }

            }, 700);

        } catch (error) {

            toast(error.message);
        }
    }

    /* =========================================================
       BATTLE
    ========================================================= */

    window.renderBattle = function() {

        app.innerHTML = `
            <main class="page battle">

                <button
                    class="back"
                    onclick="renderHome()"
                >
                    ← Orqaga
                </button>

                <div class="battle-hero">
                    ⚔️
                </div>

                <div class="eyebrow">
                    IQ BATTLE
                </div>

                <h1>
                    Do‘st bilan battle
                </h1>

                <p>
                    Ikkalangiz ham bir xil 18 ta IQ
                    testini mustaqil yechasiz.
                    Javoblaringiz bir-biringizga
                    ko‘rinmaydi.
                </p>

                <div class="battle-price">
                    ⚡ Har bir ishtirokchi — 7 500 so‘m
                </div>

                <button
                    class="primary"
                    onclick="createBattle()"
                >
                    🔑 Battle kodini yaratish
                </button>

                <button
                    class="secondary"
                    onclick="joinBattle()"
                >
                    Kod bilan battle'ga kirish
                </button>

            </main>
        `;
    };

    window.createBattle = async function() {

        try {

            const result =
                await api("/api/battle/create", {
                    method: "POST",
                    body: JSON.stringify({})
                });

            state.battleId =
                result.battle_id;

            localStorage.setItem(
                "battle_id",
                String(state.battleId)
            );

            if (result.payment_required) {

                toast(
                    "Battle to‘lovi uchun Telegram chatga qayting."
                );

                setTimeout(() => {

                    const username =
                        state.botUsername ||
                        "iqtest_ubot";

                    const url =
                        `https://t.me/${username}`;

                    if (tg?.openTelegramLink) {
                        tg.openTelegramLink(url);
                    } else {
                        window.location.href = url;
                    }

                }, 700);

                return;
            }

            showBattleCode(result);

        } catch (error) {

            toast(error.message);
        }
    };

    function showBattleCode(result) {

        app.innerHTML = `
            <main class="page battle">

                <div class="battle-hero">
                    ⚔️
                </div>

                <div class="eyebrow">
                    BATTLE KODI
                </div>

                <h1>
                    Do‘stingizni chaqiring
                </h1>

                <div class="battle-code">
                    ${esc(result.code || "----")}
                </div>

                <div class="battle-status">
                    Ushbu kodni do‘stingizga yuboring.
                    U kod bilan qo‘shilgach,
                    ikkalangiz ham mustaqil IQ testini
                    ishlaysiz.
                </div>

                <button
                    class="primary"
                    onclick="shareBattleCode('${esc(result.code || "")}')"
                >
                    📤 Kodni ulashish
                </button>

                <button
                    class="secondary"
                    onclick="renderHome()"
                >
                    Bosh sahifa
                </button>

            </main>
        `;
    }

    window.shareBattleCode = function(code) {

        const text =
            `⚔️ IQ TEST BOT Battle\n\n` +
            `Battle kodi: ${code}\n\n` +
            `Kod bilan qo‘shil:`;

        if (tg?.openTelegramLink) {

            const url =
                "https://t.me/share/url?" +
                "url=" +
                encodeURIComponent(
                    `https://t.me/${state.botUsername || "iqtest_ubot"}`
                ) +
                "&text=" +
                encodeURIComponent(text);

            tg.openTelegramLink(url);

        } else if (navigator.share) {

            navigator.share({
                text
            }).catch(() => {});

        } else {

            toast(
                `Battle kodi: ${code}`
            );
        }
    };

    window.joinBattle = async function() {

        const code =
            prompt(
                "Do‘stingiz yuborgan 4 xonali kodni kiriting:"
            );

        if (!code) {
            return;
        }

        const clean =
            String(code)
                .replace(/\D/g, "")
                .slice(0, 4);

        if (clean.length !== 4) {
            toast("Battle kodi 4 xonali bo‘lishi kerak.");
            return;
        }

        try {

            const result =
                await api("/api/battle/join", {
                    method: "POST",

                    body: JSON.stringify({
                        code: clean
                    })
                });

            state.battleId =
                result.battle_id;

            localStorage.setItem(
                "battle_id",
                String(state.battleId)
            );

            if (result.payment_required) {

                toast(
                    "Battle to‘lovi uchun Telegram chatga qayting."
                );

                setTimeout(() => {

                    const username =
                        state.botUsername ||
                        "iqtest_ubot";

                    const url =
                        `https://t.me/${username}`;

                    if (tg?.openTelegramLink) {
                        tg.openTelegramLink(url);
                    } else {
                        window.location.href = url;
                    }

                }, 700);

                return;
            }

            renderIntro("iq");

        } catch (error) {

            toast(error.message);
        }
    };

    /* =========================================================
       LANGUAGE
    ========================================================= */

    window.openLanguage = function() {

        toast(
            "Tilni Telegram botidagi 🌐 Til bo‘limidan o‘zgartiring."
        );
    };

    /* =========================================================
       COUNTER
    ========================================================= */

    async function loadCounter() {

        const counter =
            document.getElementById("liveCount");

        if (!counter) {
            return;
        }

        try {

            const result =
                await api("/api/counter");

            const active =
                Number(result.active ?? 0);

            counter.textContent =
                active.toLocaleString("uz-UZ");

        } catch (error) {

            console.warn(
                "Counter error:",
                error
            );

            counter.textContent = "0";
        }
    }

    setInterval(
        loadCounter,
        30000
    );

    /* =========================================================
       INITIAL LOAD
    ========================================================= */

    async function loadApp() {

        try {

            if (!state.initData) {

                app.innerHTML = `
                    <main class="page error">

                        <div class="result-icon">
                            📱
                        </div>

                        <h2>
                            Telegram ichidan oching
                        </h2>

                        <p>
                            Bu Mini App faqat
                            Telegram ichida ishlaydi.
                        </p>

                    </main>
                `;

                return;
            }

            const [
                me,
                config
            ] = await Promise.all([
                api("/api/me"),
                api("/api/config")
            ]);

            state.user =
                me.user || null;

            state.products =
                config.products || [];

            state.botUsername =
                config.bot_username || "";

            loadCompleted();

            try {

                state.battleId =
                    Number(
                        localStorage.getItem("battle_id") || 0
                    ) || null;

            } catch (_) {}

            renderHome();

        } catch (error) {

            console.error(error);

            app.innerHTML = `
                <main class="page error">

                    <div class="result-icon">
                        ⚠️
                    </div>

                    <h2>
                        Ulanishda xatolik
                    </h2>

                    <p>
                        ${esc(error.message)}
                    </p>

                    <button
                        class="primary"
                        onclick="location.reload()"
                    >
                        Qayta urinish
                    </button>

                </main>
            `;
        }
    }

    window.renderHome = renderHome;

    loadApp();

})();