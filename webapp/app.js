(() => {
    "use strict";

    /*
     * ============================================================
     * IQ TEST BOT — MINI APP
     * app.js
     *
     * Architecture:
     *   Telegram Mini App
     *        ↓
     *   this frontend
     *        ↓
     *   REST API
     *        ↓
     *   PostgreSQL backend
     *
     * IMPORTANT:
     * - Answers are stored locally while testing.
     * - The server is contacted only when necessary.
     * - The backend remains the authoritative source for final score.
     * - Do not rename API paths without updating bot.py.
     * ============================================================
     */

    const APP_NAME = "IQ TEST BOT";
    const STORAGE_KEY = "iq_test_bot_state_v3";
    const PAYMENT_STORAGE_KEY = "iq_test_bot_payment_v3";
    const API_TIMEOUT = 15000;
    const TOTAL_QUESTIONS = 18;

    const tg = window.Telegram?.WebApp || null;

    const state = {
        screen: "home",

        user: null,
        config: null,

        liveUsers: 0,
        totalUsers: 0,

        test: {
            type: "iq",
            sessionId: null,
            battleId: null,
            current: 0,
            answers: [],
            startedAt: null,
            elapsedSeconds: 0,
            submitted: false,
            result: null
        },

        result: null,

        battle: {
            id: null,
            code: null,
            role: null,
            status: null,
            opponent: null,
            ownScore: null,
            opponentScore: null
        },

        payment: {
            id: null,
            product: null,
            amount: null,
            status: null,
            createdAt: null
        },

        eq: {
            unlocked: false,
            completed: false,
            answers: [],
            result: null
        },

        pq: {
            unlocked: false,
            completed: false,
            answers: [],
            result: null
        },

        profile: {
            unlocked: false,
            result: null
        }
    };

    let timerHandle = null;
    let liveRefreshHandle = null;
    let busy = false;
    let testTransitionLock = false;

    /*
     * ============================================================
     * IQ QUESTION BANK
     * ============================================================
     *
     * Difficulty:
     *   1-6   = easy
     *   7-12  = medium
     *   13-18 = hard
     *
     * The visual renderer creates the puzzle itself.
     * The backend will contain the same question IDs and answer key.
     *
     * correct:
     *   0 = A
     *   1 = B
     *   2 = C
     *   3 = D
     */

    const IQ_QUESTIONS = [
        {
            id: "Q01",
            difficulty: 1,
            category: "pattern",
            title: "Qaysi katakdagi shakl ketma-ketlikni davom ettiradi?",
            type: "dots-count",
            cells: [1, 2, 3, 2, 3, 4, 3, 4, null],
            options: [4, 5, 6, 7],
            correct: 1,
            explanation: "Har bir qator va ustunda nuqtalar soni bir birlikka oshib boradi."
        },

        {
            id: "Q02",
            difficulty: 1,
            category: "visual",
            title: "Qaysi shakl mantiqiy ravishda yetishmayapti?",
            type: "shape-count",
            cells: [
                "circle",
                "square square",
                "triangle triangle triangle",
                "square",
                "triangle triangle",
                "circle circle circle",
                "triangle",
                "circle circle",
                null
            ],
            options: [
                "square square square",
                "triangle triangle triangle",
                "circle circle circle",
                "square square"
            ],
            correct: 2,
            explanation: "Har bir qator shakl turi va soni bo‘yicha o‘zaro siljiydi."
        },

        {
            id: "Q03",
            difficulty: 1,
            category: "spatial",
            title: "Strelkalar qanday yo‘nalishda davom etmoqda?",
            type: "arrows",
            cells: [
                "SW", "S", "SE",
                "E", "NE", "N",
                "NW", "W", null
            ],
            options: ["S", "NE", "E", "SE"],
            correct: 3,
            explanation: "Har bir qatorda yo‘nalishlar 45 darajalik mantiqiy siljish bilan joylashgan."
        },

        {
            id: "Q04",
            difficulty: 1,
            category: "visual",
            title: "Shakllarning kattaligi qanday o‘zgaradi?",
            type: "size",
            cells: [
                1, 2, 3,
                2, 3, 4,
                3, 4, null
            ],
            options: [4, 5, 6, 7],
            correct: 0,
            explanation: "Har bir qatorda va ustunda kattalik bir birlikka oshadi."
        },

        {
            id: "Q05",
            difficulty: 1,
            category: "spatial",
            title: "Nuqta qaysi holatda davom etadi?",
            type: "grid-position",
            cells: [
                "BR", "BC", "BL",
                "MR", "MC", "ML",
                "TR", "TC", null
            ],
            options: ["TL", "TR", "MR", "BC"],
            correct: 0,
            explanation: "Nuqta har bir qatorda o‘ngdan chapga, qatorlarda esa pastdan yuqoriga siljiydi."
        },

        {
            id: "Q06",
            difficulty: 1,
            category: "logic",
            title: "Qaysi variant umumiy qoidaga mos kelmaydi?",
            type: "odd-one-out",
            cells: [
                "circle+2",
                "square+4",
                "triangle+3",
                "pentagon+5",
                "hexagon+6",
                "diamond+4",
                "octagon+8",
                "heptagon+7",
                null
            ],
            options: [
                "circle + 2",
                "diamond + 4",
                "pentagon + 5",
                "hexagon + 6"
            ],
            correct: 1,
            explanation: "Diamond nomi bo‘yicha standart ko‘pburchak tomonlari soniga mos kelmaydi."
        },

        {
            id: "Q07",
            difficulty: 2,
            category: "pattern",
            title: "To‘ldirilgan va bo‘sh doiralar qanday almashmoqda?",
            type: "fill-matrix",
            cells: [
                "FFFEEE",
                "FFEEEE",
                "FEEEEE",
                "FFEEEE",
                "FEEEFF",
                "EEEEEE",
                "FEEEEE",
                "EEEEEE",
                null
            ],
            options: [
                "FFFEEE",
                "FFEEEE",
                "FEEEEE",
                "EEEEEE"
            ],
            correct: 3,
            explanation: "To‘ldirilgan elementlar qator va ustunlar bo‘yicha kamayib boradi."
        },

        {
            id: "Q08",
            difficulty: 2,
            category: "logic",
            title: "Ikki shakl birlashganda qanday natija hosil bo‘ladi?",
            type: "shape-combination",
            cells: [
                "circle+triangle",
                "triangle+square",
                "circle+square",
                "square+diamond",
                "diamond+circle",
                "square+circle",
                "triangle+diamond",
                "circle+diamond",
                null
            ],
            options: [
                "triangle+circle",
                "triangle+square",
                "square+diamond",
                "circle+triangle"
            ],
            correct: 1,
            explanation: "Ustunlar orasida birinchi va ikkinchi elementlarning kombinatsiyasi saqlanadi."
        },

        {
            id: "Q09",
            difficulty: 2,
            category: "spatial",
            title: "Strelka va aylanish qoidasini toping.",
            type: "arrows",
            cells: [
                "N", "E", "S",
                "W", "N", "E",
                "S", "W", null
            ],
            options: ["N", "E", "S", "W"],
            correct: 0,
            explanation: "Har bir qator keyingi qatorda 90 darajaga siljiydi."
        },

        {
            id: "Q10",
            difficulty: 2,
            category: "spatial",
            title: "Nuqta qaysi joyga ko‘chadi?",
            type: "grid-position",
            cells: [
                "TL", "TC", "TR",
                "ML", "MC", "MR",
                "BL", "BC", null
            ],
            options: ["TL", "TC", "BL", "BR"],
            correct: 3,
            explanation: "Grid bo‘ylab nuqta chapdan o‘ngga va yuqoridan pastga ketma-ket yuradi."
        },

        {
            id: "Q11",
            difficulty: 2,
            category: "pattern",
            title: "Shakl soni va yo‘nalish birgalikda o‘zgaradi.",
            type: "multi-shape",
            cells: [
                "triangle:1",
                "triangle:2",
                "triangle:3",
                "square:2",
                "square:3",
                "square:4",
                "circle:3",
                "circle:4",
                null
            ],
            options: [
                "circle:4",
                "circle:5",
                "square:5",
                "triangle:5"
            ],
            correct: 1,
            explanation: "Har bir qator shakl turini o‘zgartiradi, son esa bir birlikka oshadi."
        },

        {
            id: "Q12",
            difficulty: 2,
            category: "logic",
            title: "Ikki mustaqil qoidani bir vaqtda toping.",
            type: "double-rule",
            cells: [
                "circle-filled-small",
                "circle-open-medium",
                "circle-filled-large",
                "square-open-small",
                "square-filled-medium",
                "square-open-large",
                "triangle-filled-small",
                "triangle-open-medium",
                null
            ],
            options: [
                "triangle-filled-large",
                "triangle-open-large",
                "circle-filled-large",
                "square-filled-large"
            ],
            correct: 1,
            explanation: "Shakl qator bo‘yicha o‘zgaradi, to‘ldirish va kattalik ustun bo‘yicha almashadi."
        },

        {
            id: "Q13",
            difficulty: 3,
            category: "pattern",
            title: "Uchta parametr bir vaqtning o‘zida o‘zgaradi.",
            type: "triple-rule",
            cells: [
                "circle:N:1",
                "square:E:2",
                "triangle:S:3",
                "square:E:2",
                "triangle:S:3",
                "circle:W:4",
                "triangle:S:3",
                "circle:W:4",
                null
            ],
            options: [
                "circle:N:5",
                "square:E:5",
                "square:N:5",
                "triangle:W:5"
            ],
            correct: 2,
            explanation: "Shakl, yo‘nalish va son bir-biriga bog‘langan uchta sikl orqali siljiydi."
        },

        {
            id: "Q14",
            difficulty: 3,
            category: "spatial",
            title: "Aylanish va to‘ldirish qoidalarini birlashtiring.",
            type: "rotation-fill",
            cells: [
                "N:F",
                "E:O",
                "S:F",
                "W:O",
                "N:F",
                "E:O",
                "S:F",
                "W:O",
                null
            ],
            options: [
                "N:F",
                "E:F",
                "S:O",
                "W:F"
            ],
            correct: 0,
            explanation: "Yo‘nalish sikli va to‘ldirish sikli bir vaqtda takrorlanadi."
        },

        {
            id: "Q15",
            difficulty: 3,
            category: "spatial",
            title: "Kubning qaysi yuzi ko‘rsatilgan qirra bilan birga bo‘la olmaydi?",
            type: "cube",
            cells: [
                "A-top,B-left,C-front",
                "B-top,C-left,D-front",
                "C-top,D-left,E-front",
                "D-top,E-left,F-front",
                "E-top,F-left,A-front",
                "F-top,A-left,B-front",
                "A-top,C-left,E-front",
                "B-top,D-left,F-front",
                null
            ],
            options: [
                "A",
                "B",
                "C",
                "D"
            ],
            correct: 3,
            explanation: "Kubning qarama-qarshi yuzlari bir qirra bo‘ylab uchrashmaydi."
        },

        {
            id: "Q16",
            difficulty: 3,
            category: "logic",
            title: "Har bir katak avvalgi ikki katakning kombinatsiyasidan hosil bo‘ladi.",
            type: "combination",
            cells: [
                "A+B",
                "B+C",
                "A+C",
                "D+E",
                "E+F",
                "D+F",
                "G+H",
                "H+I",
                null
            ],
            options: [
                "G+H",
                "G+I",
                "H+I",
                "G+J"
            ],
            correct: 1,
            explanation: "Uchinchi katak birinchi va ikkinchi elementlarning umumiy kombinatsiyasini beradi."
        },

        {
            id: "Q17",
            difficulty: 3,
            category: "pattern",
            title: "Murakkab matrix: son, holat va joylashuvni birlashtiring.",
            type: "complex",
            cells: [
                "3:F:TL",
                "2:O:TC",
                "1:F:TR",
                "2:O:ML",
                "1:F:MC",
                "3:O:MR",
                "1:F:BL",
                "3:O:BC",
                null
            ],
            options: [
                "2:F:BR",
                "1:O:BR",
                "2:F:BR",
                "3:F:BR"
            ],
            correct: 2,
            explanation: "Sonlar va to‘ldirish holati qator/ustun sikllari orqali birlashadi; nuqta esa grid bo‘ylab yuradi."
        },

        {
            id: "Q18",
            difficulty: 3,
            category: "logic",
            title: "Final puzzle: uchta mustaqil qonunni toping.",
            type: "final-matrix",
            cells: [
                "circle:1:N",
                "square:2:E",
                "triangle:3:S",
                "square:2:E",
                "triangle:3:S",
                "circle:4:W",
                "triangle:3:S",
                "circle:4:W",
                null
            ],
            options: [
                "square:5:N",
                "circle:5:N",
                "triangle:5:N",
                "square:4:E"
            ],
            correct: 3,
            explanation: "Final katak shakl, son va yo‘nalishning uchta siklini birlashtiradi."
        }
    ];

    /*
     * ============================================================
     * EQ / PQ QUESTION BANK
     * ============================================================
     *
     * These are intentionally scenario-based rather than
     * "good person / bad person" questions.
     */

    const EQ_QUESTIONS = [
        {
            id: "EQ01",
            text: "Do‘stingiz sizga jahli chiqib gapirdi. Birinchi reaksiyangiz qanday bo‘ladi?",
            options: [
                "Darhol xuddi shunday javob qaytaraman.",
                "Nega bunday gapirganini tushunishga harakat qilaman.",
                "Gapni butunlay e’tiborsiz qoldiraman.",
                "Men ham xafa bo‘lib, suhbatni tugataman."
            ]
        },
        {
            id: "EQ02",
            text: "Jamoada kimdir xato qildi va boshqalar uni ayblay boshladi.",
            options: [
                "Men ham xatosini ko‘rsataman.",
                "Vaziyatni tinchlantirib, muammoni hal qilishga o‘taman.",
                "Umuman aralashmayman.",
                "Uni himoya qilib, boshqalarga qarshi chiqaman."
            ]
        },
        {
            id: "EQ03",
            text: "Kayfiyatingiz yomon, lekin muhim uchrashuv bor.",
            options: [
                "Hamma oldida kayfiyatimni ko‘rsataman.",
                "His-tuyg‘umni tan olib, lekin vazifamni bajarishga harakat qilaman.",
                "Uchrashuvni bekor qilaman.",
                "Boshqalarning kayfiyatini ham buzaman."
            ]
        },
        {
            id: "EQ04",
            text: "Kimdir sizni noto‘g‘ri tushundi.",
            options: [
                "Uni ayblayman.",
                "O‘z fikrimni boshqacha va aniqroq tushuntiraman.",
                "Gaplashmay qo‘yaman.",
                "Uning xatosini hammaga aytaman."
            ]
        },
        {
            id: "EQ05",
            text: "Yaqin insoningiz jim bo‘lib qolganini sezdingiz.",
            options: [
                "Nima bo‘lganini bosim bilan so‘rayman.",
                "Unga joy berib, kerak bo‘lsa yonida ekanimni bildiraman.",
                "Hech narsa bo‘lmagandek davom etaman.",
                "Darhol eng yomon sababni taxmin qilaman."
            ]
        },
        {
            id: "EQ06",
            text: "Siz haqingizda tanqid bildirildi.",
            options: [
                "Darhol himoyalanaman.",
                "Qaysi qismi foydali ekanini ajratib ko‘raman.",
                "Tanqid qilgan odamni tanqid qilaman.",
                "Hammasini shaxsiy hujum deb qabul qilaman."
            ]
        }
    ];

    const PQ_QUESTIONS = [
        {
            id: "PQ01",
            text: "Muhim ishga 3 kun bor, lekin hozir boshlash uchun kayfiyat yo‘q.",
            options: [
                "Oxirgi kungacha kutaman.",
                "Kamida kichik bir qismini hozir boshlayman.",
                "Boshqa ish topib qilaman.",
                "Ishni butunlay unutishga harakat qilaman."
            ]
        },
        {
            id: "PQ02",
            text: "Telefoningizda ijtimoiy tarmoq ochiq, oldingizda esa bajarilishi kerak bo‘lgan ish turibdi.",
            options: [
                "Bir necha daqiqa deb kiraman va uzoq qolib ketaman.",
                "Telefonni chetga qo‘yib, vaqt chegarasi belgilayman.",
                "Ishni tashlab qo‘yaman.",
                "Kimdir kelib aytishini kutaman."
            ]
        },
        {
            id: "PQ03",
            text: "Vazifa juda katta ko‘rinmoqda.",
            options: [
                "Boshlamaslik uchun sabab izlayman.",
                "Uni kichik bosqichlarga bo‘lib boshlayman.",
                "Deadline yaqinlashishini kutaman.",
                "Boshqa odamga topshirishga urinaman."
            ]
        },
        {
            id: "PQ04",
            text: "Rejangiz buzildi.",
            options: [
                "Butun kunni tashlab yuboraman.",
                "Rejani qayta tuzib, keyingi eng kichik qadamni tanlayman.",
                "Ertaga boshlayman.",
                "Muammoni e’tiborsiz qoldiraman."
            ]
        },
        {
            id: "PQ05",
            text: "Ishni boshlash qiyin, lekin tugatgach foydasi katta.",
            options: [
                "Foydasi bo‘lsa ham keyinga suraman.",
                "Boshlash uchun qisqa vaqt ajrataman.",
                "Boshqa odamning motivatsiyasini kutaman.",
                "Umuman qilmayman."
            ]
        },
        {
            id: "PQ06",
            text: "Deadline ertaga, ishning yarmi qolgan.",
            options: [
                "Stress sabab yana vaqt yo‘qotaman.",
                "Prioritetlarni belgilab, qolgan vaqtni ishga ajrataman.",
                "Vazifani topshirmaslikni o‘ylayman.",
                "Deadline o'tib ketishini kutaman."
            ]
        }
    ];

    /*
     * ============================================================
     * SAFE STORAGE
     * ============================================================
     */

    function safeJSONParse(value, fallback = null) {
        try {
            return value ? JSON.parse(value) : fallback;
        } catch {
            return fallback;
        }
    }

    function saveState() {
        try {
            const payload = {
                test: state.test,
                result: state.result,
                battle: state.battle,
                payment: state.payment,
                eq: state.eq,
                pq: state.pq,
                profile: state.profile
            };

            localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        } catch (error) {
            console.warn("[IQ TEST BOT] State save failed:", error);
        }
    }

    function restoreState() {
        try {
            const saved = safeJSONParse(
                localStorage.getItem(STORAGE_KEY),
                null
            );

            if (!saved) {
                return;
            }

            if (saved.test) {
                state.test = {
                    ...state.test,
                    ...saved.test
                };
            }

            if (saved.result) {
                state.result = saved.result;
            }

            if (saved.battle) {
                state.battle = {
                    ...state.battle,
                    ...saved.battle
                };
            }

            if (saved.payment) {
                state.payment = {
                    ...state.payment,
                    ...saved.payment
                };
            }

            if (saved.eq) {
                state.eq = {
                    ...state.eq,
                    ...saved.eq
                };
            }

            if (saved.pq) {
                state.pq = {
                    ...state.pq,
                    ...saved.pq
                };
            }

            if (saved.profile) {
                state.profile = {
                    ...state.profile,
                    ...saved.profile
                };
            }
        } catch (error) {
            console.warn("[IQ TEST BOT] State restore failed:", error);
        }
    }

    function clearTestState() {
        state.test = {
            type: "iq",
            sessionId: null,
            battleId: null,
            current: 0,
            answers: [],
            startedAt: null,
            elapsedSeconds: 0,
            submitted: false,
            result: null
        };

        saveState();
    }

    /*
     * ============================================================
     * TELEGRAM
     * ============================================================
     */

    function initTelegram() {
        if (!tg) {
            document.body.classList.add("telegram-unavailable");
            return;
        }

        try {
            tg.ready();
            tg.expand();

            if (typeof tg.setHeaderColor === "function") {
                tg.setHeaderColor("#080912");
            }

            if (typeof tg.setBackgroundColor === "function") {
                tg.setBackgroundColor("#080912");
            }
        } catch (error) {
            console.warn("[IQ TEST BOT] Telegram init failed:", error);
        }
    }

    function haptic(type = "light") {
        try {
            const impact = tg?.HapticFeedback;

            if (!impact) {
                return;
            }

            if (type === "success") {
                impact.notificationOccurred("success");
            } else if (type === "error") {
                impact.notificationOccurred("error");
            } else if (type === "warning") {
                impact.notificationOccurred("warning");
            } else {
                impact.impactOccurred(type);
            }
        } catch {
            // Haptic is optional.
        }
    }

    function closeMiniApp() {
        try {
            tg?.close();
        } catch {
            window.history.back();
        }
    }

    /*
     * ============================================================
     * API
     * ============================================================
     */

    function getInitData() {
        return tg?.initData || "";
    }

    function getApiBase() {
        const configured =
            window.IQ_TEST_BOT_API_BASE ||
            document.documentElement.dataset.apiBase ||
            "";

        return configured.replace(/\/+$/, "");
    }

    async function api(path, options = {}) {
        const controller = new AbortController();
        const timeout = setTimeout(() => {
            controller.abort();
        }, options.timeout || API_TIMEOUT);

        const headers = new Headers(options.headers || {});

        headers.set("Accept", "application/json");

        if (options.body && !(options.body instanceof FormData)) {
            headers.set("Content-Type", "application/json");
        }

        const initData = getInitData();

        if (initData) {
            headers.set("X-Telegram-Init-Data", initData);
        }

        let body = options.body;

        if (
            body &&
            !(body instanceof FormData) &&
            typeof body !== "string"
        ) {
            body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${getApiBase()}${path}`, {
                method: options.method || "GET",
                headers,
                body,
                credentials: "include",
                cache: "no-store",
                signal: controller.signal
            });

            const text = await response.text();

            let data = null;

            if (text) {
                try {
                    data = JSON.parse(text);
                } catch {
                    data = {
                        detail: text
                    };
                }
            }

            if (!response.ok) {
                const error = new Error(
                    data?.detail ||
                    data?.message ||
                    `Server error: ${response.status}`
                );

                error.status = response.status;
                error.data = data;

                throw error;
            }

            return data || {};
        } catch (error) {
            if (error.name === "AbortError") {
                const timeoutError = new Error(
                    "Server javobi juda uzoq kutilmoqda."
                );

                timeoutError.code = "TIMEOUT";

                throw timeoutError;
            }

            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    /*
     * ============================================================
     * UTILITIES
     * ============================================================
     */

    function uid(prefix = "local") {
        if (window.crypto?.randomUUID) {
            return `${prefix}_${window.crypto.randomUUID()}`;
        }

        return `${prefix}_${Date.now()}_${Math.random()
            .toString(36)
            .slice(2, 10)}`;
    }

    function escapeHTML(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString("uz-UZ");
    }

    function formatDuration(seconds) {
        const total = Math.max(0, Math.floor(seconds || 0));
        const minutes = Math.floor(total / 60);
        const secs = total % 60;

        return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(
            2,
            "0"
        )}`;
    }

    function getQuestion() {
        return IQ_QUESTIONS[state.test.current] || null;
    }

    function getAnswerLetter(index) {
        return ["A", "B", "C", "D"][index] || "";
    }

    function getDifficultyLabel(level) {
        if (level === 1) return "Boshlang‘ich";
        if (level === 2) return "O‘rta";
        return "Murakkab";
    }

    function showToast(message, type = "info") {
        let toast = document.querySelector(".iqtb-toast");

        if (!toast) {
            toast = document.createElement("div");
            toast.className = "iqtb-toast";
            document.body.appendChild(toast);
        }

        toast.className = `iqtb-toast is-${type}`;
        toast.textContent = message;

        requestAnimationFrame(() => {
            toast.classList.add("is-visible");
        });

        clearTimeout(showToast.timer);

        showToast.timer = setTimeout(() => {
            toast.classList.remove("is-visible");
        }, 2800);
    }

    function setBusy(value) {
        busy = Boolean(value);

        document.body.classList.toggle("is-busy", busy);
    }

    function scrollTop() {
        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    }

    /*
     * ============================================================
     * SVG PUZZLE RENDERER
     * ============================================================
     */

    function svgWrap(content, viewBox = "0 0 300 220") {
        return `
            <svg
                class="puzzle-svg"
                viewBox="${viewBox}"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
            >
                ${content}
            </svg>
        `;
    }

    function drawDot(x, y, filled = true, r = 11) {
        return `
            <circle
                cx="${x}"
                cy="${y}"
                r="${r}"
                class="puzzle-dot ${filled ? "is-filled" : "is-open"}"
            />
        `;
    }

    function drawArrow(direction, x = 150, y = 110, size = 45) {
        const vectors = {
            N: [0, -1],
            NE: [0.707, -0.707],
            E: [1, 0],
            SE: [0.707, 0.707],
            S: [0, 1],
            SW: [-0.707, 0.707],
            W: [-1, 0],
            NW: [-0.707, -0.707]
        };

        const [vx, vy] = vectors[direction] || vectors.N;

        const ex = x + vx * size;
        const ey = y + vy * size;

        const px = -vy;
        const py = vx;

        const hx1 = ex - vx * 17 + px * 12;
        const hy1 = ey - vy * 17 + py * 12;

        const hx2 = ex - vx * 17 - px * 12;
        const hy2 = ey - vy * 17 - py * 12;

        return `
            <g class="puzzle-arrow">
                <line
                    x1="${x}"
                    y1="${y}"
                    x2="${ex}"
                    y2="${ey}"
                />
                <line
                    x1="${ex}"
                    y1="${ey}"
                    x2="${hx1}"
                    y2="${hy1}"
                />
                <line
                    x1="${ex}"
                    y1="${ey}"
                    x2="${hx2}"
                    y2="${hy2}"
                />
            </g>
        `;
    }

    function drawShape(shape, x = 150, y = 110, size = 34) {
        if (shape === "circle") {
            return `
                <circle
                    cx="${x}"
                    cy="${y}"
                    r="${size}"
                    class="puzzle-shape"
                />
            `;
        }

        if (shape === "square") {
            return `
                <rect
                    x="${x - size}"
                    y="${y - size}"
                    width="${size * 2}"
                    height="${size * 2}"
                    class="puzzle-shape"
                />
            `;
        }

        if (shape === "triangle") {
            const h = size * 1.8;

            return `
                <polygon
                    points="
                        ${x},${y - h / 2}
                        ${x - size},${y + h / 2}
                        ${x + size},${y + h / 2}
                    "
                    class="puzzle-shape"
                />
            `;
        }

        if (shape === "diamond") {
            return `
                <polygon
                    points="
                        ${x},${y - size}
                        ${x + size},${y}
                        ${x},${y + size}
                        ${x - size},${y}
                    "
                    class="puzzle-shape"
                />
            `;
        }

        return `
            <circle
                cx="${x}"
                cy="${y}"
                r="${size}"
                class="puzzle-shape"
            />
        `;
    }

    function drawGrid(position, compact = false) {
        const startX = compact ? 90 : 75;
        const startY = compact ? 55 : 50;
        const cell = compact ? 40 : 50;

        const map = {
            TL: [0, 0],
            TC: [1, 0],
            TR: [2, 0],
            ML: [0, 1],
            MC: [1, 1],
            MR: [2, 1],
            BL: [0, 2],
            BC: [1, 2],
            BR: [2, 2]
        };

        const [cx, cy] = map[position] || map.MC;

        let grid = "";

        for (let i = 0; i < 4; i += 1) {
            grid += `
                <line
                    x1="${startX}"
                    y1="${startY + i * cell}"
                    x2="${startX + cell * 3}"
                    y2="${startY + i * cell}"
                    class="grid-line"
                />
                <line
                    x1="${startX + i * cell}"
                    y1="${startY}"
                    x2="${startX + i * cell}"
                    y2="${startY + cell * 3}"
                    class="grid-line"
                />
            `;
        }

        grid += `
            <circle
                cx="${startX + cell * cx + cell / 2}"
                cy="${startY + cell * cy + cell / 2}"
                r="${compact ? 9 : 13}"
                class="puzzle-dot is-filled"
            />
        `;

        return grid;
    }

    function drawClock(value) {
        const [hour, minute] = value.split(":").map(Number);

        const hourAngle = ((hour % 12) + minute / 60) * 30;
        const minuteAngle = minute * 6;

        function hand(angle, length, width) {
            const rad = ((angle - 90) * Math.PI) / 180;

            const x = 150 + Math.cos(rad) * length;
            const y = 110 + Math.sin(rad) * length;

            return `
                <line
                    x1="150"
                    y1="110"
                    x2="${x}"
                    y2="${y}"
                    stroke="currentColor"
                    stroke-width="${width}"
                    stroke-linecap="round"
                />
            `;
        }

        return `
            <circle
                cx="150"
                cy="110"
                r="66"
                class="clock-face"
            />
            ${hand(hourAngle, 35, 9)}
            ${hand(minuteAngle, 52, 7)}
            <circle
                cx="150"
                cy="110"
                r="6"
                class="clock-center"
            />
        `;
    }

    function renderCellVisual(question, value, compact = false) {
        if (value === null || value === undefined) {
            return `
                <div class="matrix-missing">
                    <span>?</span>
                </div>
            `;
        }

        if (question.type === "dots-count") {
            const count = Number(value);
            let dots = "";

            for (let i = 0; i < count; i += 1) {
                const col = i % 5;
                const row = Math.floor(i / 5);

                dots += drawDot(
                    105 + col * 23,
                    88 + row * 30,
                    true,
                    compact ? 7 : 9
                );
            }

            return svgWrap(dots);
        }

        if (
            question.type === "shape-count" ||
            question.type === "shape-combination"
        ) {
            const parts = String(value).split("+");
            const shapes = [];

            for (const part of parts) {
                const [name, countRaw] = part.trim().split(/\s+/);
                const count = Number(countRaw || 1);

                for (let i = 0; i < count; i += 1) {
                    shapes.push(name);
                }
            }

            const max = Math.min(shapes.length, 5);

            let content = "";

            for (let i = 0; i < max; i += 1) {
                const x = 110 + (i % 3) * 42;
                const y = shapes.length > 3
                    ? 85 + Math.floor(i / 3) * 48
                    : 110;

                content += drawShape(
                    shapes[i],
                    x,
                    y,
                    compact ? 15 : 22
                );
            }

            return svgWrap(content);
        }

        if (question.type === "arrows") {
            return svgWrap(
                drawArrow(
                    value,
                    150,
                    110,
                    compact ? 32 : 50
                )
            );
        }

        if (question.type === "size") {
            const size = 18 + Number(value) * 8;

            return svgWrap(
                drawShape(
                    "triangle",
                    150,
                    110,
                    Math.min(size, 54)
                )
            );
        }

        if (question.type === "grid-position") {
            return svgWrap(drawGrid(value, compact));
        }

        if (question.type === "odd-one-out") {
            const [shape, count] = String(value).split("+");

            return svgWrap(
                drawShape(
                    shape,
                    130,
                    110,
                    compact ? 22 : 32
                ) +
                `
                    <text
                        x="195"
                        y="118"
                        class="puzzle-number"
                    >
                        ${escapeHTML(count)}
                    </text>
                `
            );
        }

        if (question.type === "fill-matrix") {
            const pattern = String(value);

            let content = "";

            [...pattern].forEach((char, index) => {
                const filled = char === "F";
                const x = 90 + (index % 3) * 45;
                const y = 85 + Math.floor(index / 3) * 45;

                content += drawDot(
                    x,
                    y,
                    filled,
                    compact ? 11 : 15
                );
            });

            return svgWrap(content);
        }

        if (question.type === "multi-shape") {
            const [shape, countRaw] = String(value).split(":");
            const count = Number(countRaw);

            let content = "";

            for (let i = 0; i < count; i += 1) {
                content += drawShape(
                    shape,
                    110 + (i % 3) * 42,
                    count > 3
                        ? 85 + Math.floor(i / 3) * 45
                        : 110,
                    compact ? 14 : 21
                );
            }

            return svgWrap(content);
        }

        if (question.type === "double-rule") {
            const [shape, fill, sizeName] = String(value).split("-");

            const sizeMap = {
                small: 18,
                medium: 27,
                large: 37
            };

            const size = sizeMap[sizeName] || 27;

            const shapeSvg = drawShape(
                shape,
                150,
                110,
                compact ? size * 0.65 : size
            );

            const fillClass =
                fill === "filled"
                    ? "puzzle-filled-shape"
                    : "puzzle-open-shape";

            return svgWrap(
                shapeSvg.replace(
                    'class="puzzle-shape"',
                    `class="puzzle-shape ${fillClass}"`
                )
            );
        }

        if (
            question.type === "triple-rule" ||
            question.type === "complex" ||
            question.type === "final-matrix"
        ) {
            const parts = String(value).split(":");
            const shape = parts[0];
            const direction = parts[1];
            const number = Number(parts[2]);

            let content = drawShape(
                shape,
                150,
                105,
                compact ? 22 : 31
            );

            content += drawArrow(
                direction,
                150,
                105,
                compact ? 28 : 40
            );

            content += `
                <text
                    x="150"
                    y="185"
                    text-anchor="middle"
                    class="puzzle-number"
                >
                    ${number}
                </text>
            `;

            return svgWrap(content);
        }

        if (question.type === "rotation-fill") {
            const [direction, fill] = String(value).split(":");

            const fillCircle =
                fill === "F"
                    ? `
                        <circle
                            cx="150"
                            cy="110"
                            r="20"
                            class="puzzle-dot is-filled"
                        />
                    `
                    : `
                        <circle
                            cx="150"
                            cy="110"
                            r="20"
                            class="puzzle-dot is-open"
                        />
                    `;

            return svgWrap(
                drawArrow(
                    direction,
                    150,
                    110,
                    compact ? 32 : 48
                ) +
                fillCircle
            );
        }

        if (question.type === "cube") {
            return svgWrap(`
                <g class="cube">
                    <polygon
                        points="150,55 205,85 150,115 95,85"
                    />
                    <polygon
                        points="95,85 150,115 150,180 95,150"
                    />
                    <polygon
                        points="150,115 205,85 205,150 150,180"
                    />
                </g>
                <text x="150" y="105" class="cube-letter">?</text>
            `);
        }

        if (question.type === "combination") {
            const parts = String(value).split("+");

            return svgWrap(`
                ${drawShape(
                    parts[0] === "A" || parts[0] === "D" || parts[0] === "G"
                        ? "circle"
                        : "square",
                    120,
                    110,
                    compact ? 16 : 24
                )}
                ${drawShape(
                    parts[1] === "B" || parts[1] === "E" || parts[1] === "H"
                        ? "triangle"
                        : "diamond",
                    180,
                    110,
                    compact ? 16 : 24
                )}
            `);
        }

        return svgWrap(
            drawShape("circle", 150, 110, compact ? 20 : 30)
        );
    }

    function renderQuestionMatrix(question) {
        const values = question.cells;

        return `
            <div class="matrix-board">
                ${values.map((value, index) => `
                    <div class="matrix-cell ${value === null ? "is-missing" : ""}">
                        ${renderCellVisual(question, value)}
                    </div>
                `).join("")}
            </div>
        `;
    }

    function renderOptions(question) {
        return `
            <div class="answer-grid">
                ${question.options.map((option, index) => `
                    <button
                        class="answer-card"
                        type="button"
                        data-answer="${index}"
                        aria-label="Javob ${getAnswerLetter(index)}"
                    >
                        <span class="answer-letter">
                            ${getAnswerLetter(index)}
                        </span>

                        <span class="answer-visual">
                            ${renderCellVisual(
                                question,
                                option,
                                true
                            )}
                        </span>
                    </button>
                `).join("")}
            </div>
        `;
    }

    /*
     * ============================================================
     * ROOT / SHELL
     * ============================================================
     */

    function ensureRoot() {
        let root = document.getElementById("app");

        if (!root) {
            root = document.createElement("main");
            root.id = "app";
            document.body.appendChild(root);
        }

        return root;
    }

    function renderShell() {
        const root = ensureRoot();

        root.innerHTML = `
            <div class="app-shell">

                <header class="app-header">
                    <button
                        class="header-back"
                        id="headerBack"
                        type="button"
                        aria-label="Orqaga"
                    >
                        <span>‹</span>
                    </button>

                    <div class="header-brand">
                        <div class="header-brand-name">
                            IQ TEST BOT
                        </div>
                        <div class="header-brand-subtitle">
                            mini ilova
                        </div>
                    </div>

                    <button
                        class="header-menu"
                        id="headerMenu"
                        type="button"
                        aria-label="Menyu"
                    >
                        <span></span>
                        <span></span>
                        <span></span>
                    </button>
                </header>

                <div id="screenContainer"></div>

                <div
                    id="globalLoading"
                    class="global-loading"
                    hidden
                >
                    <div class="loading-brain">🧠</div>
                    <div class="loading-title">
                        Yuklanmoqda...
                    </div>
                </div>
            </div>
        `;

        document
            .getElementById("headerBack")
            ?.addEventListener("click", handleHeaderBack);

        document
            .getElementById("headerMenu")
            ?.addEventListener("click", openQuickMenu);
    }

    function setScreen(screen) {
        state.screen = screen;

        const back = document.getElementById("headerBack");

        if (back) {
            back.hidden = screen === "home";
        }

        renderCurrentScreen();
        scrollTop();
    }

    function renderCurrentScreen() {
        const container = document.getElementById("screenContainer");

        if (!container) {
            return;
        }

        switch (state.screen) {
            case "home":
                container.innerHTML = renderHome();
                bindHomeEvents();
                break;

            case "intro":
                container.innerHTML = renderIQIntro();
                bindIntroEvents();
                break;

            case "test":
                container.innerHTML = renderTestScreen();
                bindTestEvents();
                break;

            case "processing":
                container.innerHTML = renderProcessing();
                break;

            case "result":
                container.innerHTML = renderResult();
                bindResultEvents();
                break;

            case "eq":
                container.innerHTML = renderPsychologicalTest(
                    "eq"
                );
                bindPsychologicalEvents("eq");
                break;

            case "pq":
                container.innerHTML = renderPsychologicalTest(
                    "pq"
                );
                bindPsychologicalEvents("pq");
                break;

            case "profile":
                container.innerHTML = renderProfile();
                bindProfileEvents();
                break;

            case "battle":
                container.innerHTML = renderBattle();
                bindBattleEvents();
                break;

            default:
                state.screen = "home";
                container.innerHTML = renderHome();
                bindHomeEvents();
        }
    }

    /*
     * ============================================================
     * HOME
     * ============================================================
     */

    function renderHome() {
        const iqDone = Boolean(state.result);
        const eqUnlocked = iqDone;
        const pqUnlocked = state.eq.completed;
        const profileUnlocked =
            state.eq.completed &&
            state.pq.completed;

        return `
            <section class="screen screen-home">

                <div class="hero">
                    <div class="hero-orbit orbit-one"></div>
                    <div class="hero-orbit orbit-two"></div>

                    <div class="hero-brain">
                        <div class="brain-glow"></div>
                        <div class="brain-symbol">🧠</div>
                    </div>

                    <div class="hero-kicker">
                        IQ TEST BOT
                    </div>

                    <h1>
                        18 TA MANTIQIY PUZZLE
                    </h1>

                    <p>
                        IQ darajangizni sinab ko‘ring
                    </p>

                    <span>
                        18 ta mantiqiy puzzle orqali
                        fikrlash qobiliyatingizni sinang.
                    </span>
                </div>

                <div class="test-cards">

                    <button
                        class="test-card test-card-iq ${iqDone ? "is-completed" : ""}"
                        type="button"
                        data-open="iq"
                    >
                        <div class="test-card-icon">
                            🧠
                        </div>

                        <div class="test-card-copy">
                            <strong>IQ</strong>
                            <span>
                                Mantiqiy fikrlash darajangiz
                            </span>
                        </div>

                        <div class="test-card-status">
                            ${iqDone ? "✓" : "›"}
                        </div>
                    </button>

                    <button
                        class="test-card ${eqUnlocked ? "is-open" : "is-locked"}"
                        type="button"
                        data-open="eq"
                        ${eqUnlocked ? "" : "disabled"}
                    >
                        <div class="test-card-icon">
                            🎭
                        </div>

                        <div class="test-card-copy">
                            <strong>
                                EQ
                                ${eqUnlocked ? "" : "🔒"}
                            </strong>
                            <span>
                                His-tuyg‘ularni tushunish
                                <small>
                                    ${eqUnlocked
                                        ? "IQ dan keyin"
                                        : "IQ dan keyin ochiladi"}
                                </small>
                            </span>
                        </div>

                        <div class="test-card-status">
                            ${state.eq.completed ? "✓" : "›"}
                        </div>
                    </button>

                    <button
                        class="test-card ${pqUnlocked ? "is-open" : "is-locked"}"
                        type="button"
                        data-open="pq"
                        ${pqUnlocked ? "" : "disabled"}
                    >
                        <div class="test-card-icon">
                            ⏳
                        </div>

                        <div class="test-card-copy">
                            <strong>
                                PROKRASTINATSIYA
                                ${pqUnlocked ? "" : "🔒"}
                            </strong>
                            <span>
                                Ishni keyinga surish odati
                                <small>
                                    ${pqUnlocked
                                        ? "EQ dan keyin"
                                        : "EQ dan keyin ochiladi"}
                                </small>
                            </span>
                        </div>

                        <div class="test-card-status">
                            ${state.pq.completed ? "✓" : "›"}
                        </div>
                    </button>

                    <button
                        class="test-card ${profileUnlocked ? "is-open" : "is-locked"}"
                        type="button"
                        data-open="profile"
                        ${profileUnlocked ? "" : "disabled"}
                    >
                        <div class="test-card-icon">
                            ⭐
                        </div>

                        <div class="test-card-copy">
                            <strong>
                                SIZ QANDAY INSONSIZ?
                                ${profileUnlocked ? "" : "🔒"}
                            </strong>
                            <span>
                                Uchala testdan keyin
                            </span>
                        </div>

                        <div class="test-card-status">
                            ${profileUnlocked ? "›" : "🔒"}
                        </div>
                    </button>

                </div>

                <section class="live-card">
                    <div class="live-top">
                        <span class="live-dot"></span>
                        <span>JONLI</span>
                    </div>

                    <div class="live-number" id="totalUsers">
                        ${formatNumber(state.totalUsers)}
                    </div>

                    <div class="live-label">
                        Botga qo‘shilganlar soni
                    </div>

                    <div class="live-online">
                        <span>👥</span>
                        Hozirda
                        <strong id="liveUsers">
                            ${formatNumber(state.liveUsers)}
                        </strong>
                        kishi onlayn
                    </div>
                </section>

                <button
                    class="battle-home-card"
                    type="button"
                    id="openBattle"
                >
                    <div>
                        <strong>
                            ⚔️ DO‘ST BILAN BATTLE
                        </strong>
                        <span>
                            Do‘stingiz bilan IQ natijangizni
                            solishtiring
                        </span>
                    </div>

                    <span class="battle-price">
                        ${formatNumber(
                            state.config?.battle_price || 7500
                        )} so‘m
                    </span>
                </button>

                <div class="home-footer-note">
                    IQ-style score — standart klinik IQ testi emas.
                </div>

            </section>
        `;
    }

    function bindHomeEvents() {
        document
            .querySelectorAll("[data-open]")
            .forEach((button) => {
                button.addEventListener("click", () => {
                    const target = button.dataset.open;

                    if (target === "iq") {
                        openIQ();
                    } else if (target === "eq") {
                        openEQ();
                    } else if (target === "pq") {
                        openPQ();
                    } else if (target === "profile") {
                        openProfile();
                    }
                });
            });

        document
            .getElementById("openBattle")
            ?.addEventListener("click", openBattle);

        animateCounter(
            document.getElementById("totalUsers"),
            state.totalUsers
        );

        animateCounter(
            document.getElementById("liveUsers"),
            state.liveUsers
        );
    }

    /*
     * ============================================================
     * IQ INTRO
     * ============================================================
     */

    function renderIQIntro() {
        return `
            <section class="screen intro-screen">

                <div class="intro-hero">
                    <div class="intro-icon">
                        🧠
                    </div>

                    <div class="eyebrow">
                        IQ TEST
                    </div>

                    <h1>
                        Aql darajangizni aniqlang
                    </h1>

                    <p>
                        18 ta tasviriy mantiq savoli
                    </p>
                </div>

                <div class="intro-features">
                    <div>
                        <strong>📄</strong>
                        <span>18 ta savol</span>
                    </div>

                    <div>
                        <strong>∞</strong>
                        <span>Vaqt cheksiz</span>
                    </div>

                    <div>
                        <strong>🔷</strong>
                        <span>Tasviriy mantiq</span>
                    </div>

                    <div>
                        <strong>🏅</strong>
                        <span>IQ-style natija</span>
                    </div>
                </div>

                <div class="glass-panel">
                    <h2>💡 Qanday ishlaydi?</h2>

                    <ol>
                        <li>
                            18 ta savolga javob bering.
                        </li>
                        <li>
                            Har bir puzzle mantiqiy fikrlashni
                            tekshiradi.
                        </li>
                        <li>
                            Natijangiz test yakunida hisoblanadi.
                        </li>
                        <li>
                            Sertifikatingizni olishingiz mumkin.
                        </li>
                    </ol>
                </div>

                <div class="difficulty-preview">
                    <div>
                        <span>1–6</span>
                        <small>Oson</small>
                    </div>

                    <div>
                        <span>7–12</span>
                        <small>O‘rta</small>
                    </div>

                    <div>
                        <span>13–18</span>
                        <small>Murakkab</small>
                    </div>
                </div>

                <button
                    class="primary-button"
                    id="startIQ"
                    type="button"
                >
                    🚀 TESTNI BOSHLASH
                </button>

                <button
                    class="secondary-button"
                    id="sampleQuestion"
                    type="button"
                >
                    🧩 Namunaviy savol
                </button>

                <div class="disclaimer">
                    Bu test mahsulotning IQ-style score tizimi.
                    U standartlashtirilgan klinik IQ testi emas.
                </div>

            </section>
        `;
    }

    function bindIntroEvents() {
        document
            .getElementById("startIQ")
            ?.addEventListener("click", () => {
                startIQTest();
            });

        document
            .getElementById("sampleQuestion")
            ?.addEventListener("click", openSample);
    }

    function openSample() {
        const sample = {
            id: "SAMPLE",
            difficulty: 1,
            category: "pattern",
            type: "dots-count",
            cells: [1, 2, 3, 2, 3, 4, 3, 4, null],
            options: [4, 5, 6, 7],
            correct: 1
        };

        const modal = document.createElement("div");

        modal.className = "modal-backdrop";

        modal.innerHTML = `
            <div class="modal-card sample-modal">
                <button
                    class="modal-close"
                    type="button"
                    aria-label="Yopish"
                >
                    ×
                </button>

                <div class="eyebrow">
                    NAMUNAVIY SAVOL
                </div>

                <h2>
                    Qaysi variant yetishmayapti?
                </h2>

                <div class="sample-matrix">
                    ${renderQuestionMatrix(sample)}
                </div>

                <div class="sample-options">
                    ${sample.options.map((option, index) => `
                        <div class="sample-option">
                            <span>
                                ${getAnswerLetter(index)}
                            </span>
                            ${renderCellVisual(
                                sample,
                                option,
                                true
                            )}
                        </div>
                    `).join("")}
                </div>

                <div class="sample-answer">
                    To‘g‘ri javob:
                    <strong>B</strong>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal
            .querySelector(".modal-close")
            ?.addEventListener("click", () => {
                modal.remove();
            });

        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.remove();
            }
        });
    }

    /*
     * ============================================================
     * IQ TEST
     * ============================================================
     */

    async function startIQTest(options = {}) {
        if (busy) {
            return;
        }

        const hasExisting =
            state.test.type === "iq" &&
            state.test.startedAt &&
            !state.test.submitted &&
            state.test.answers.length > 0;

        if (
            hasExisting &&
            !options.forceNew
        ) {
            const shouldResume = window.confirm(
                "Oldingi IQ testingiz davom ettirilishi mumkin. Davom etasizmi?"
            );

            if (shouldResume) {
                setScreen("test");
                startTimer();
                return;
            }

            clearTestState();
        }

        setBusy(true);

        try {
            let sessionId = uid("iq");

            try {
                const response = await api(
                    "/api/session/start",
                    {
                        method: "POST",
                        body: {
                            test_type: "iq",
                            battle_id: state.battle.id || null
                        }
                    }
                );

                sessionId =
                    response.session_id ||
                    response.id ||
                    sessionId;
            } catch (error) {
                if (error.status === 402) {
                    setBusy(false);
                    await openPayment("iq");
                    return;
                }

                /*
                 * Offline-first:
                 * if server cannot be reached, a local session is
                 * still allowed. Final submission will retry.
                 */
                console.warn(
                    "[IQ TEST BOT] Session start fallback:",
                    error
                );
            }

            state.test = {
                type: "iq",
                sessionId,
                battleId: state.battle.id || null,
                current: 0,
                answers: [],
                startedAt: Date.now(),
                elapsedSeconds: 0,
                submitted: false,
                result: null
            };

            saveState();

            setScreen("test");
            startTimer();
        } finally {
            setBusy(false);
        }
    }

    function renderTestScreen() {
        const question = getQuestion();

        if (!question) {
            return renderHome();
        }

        const index = state.test.current;
        const selected = state.test.answers[index];

        const progress = ((index + 1) / TOTAL_QUESTIONS) * 100;

        return `
            <section class="screen test-screen">

                <div class="test-meta">
                    <div class="test-name">
                        <span class="iq-gradient">IQ</span>
                        TEST
                    </div>

                    <div class="question-counter">
                        Savol ${index + 1} / ${TOTAL_QUESTIONS}
                    </div>

                    <div class="timer" id="testTimer">
                        ${formatDuration(
                            state.test.elapsedSeconds
                        )}
                    </div>
                </div>

                <div class="progress-track">
                    <div
                        class="progress-fill"
                        style="width:${progress}%"
                    ></div>
                </div>

                <div class="difficulty-pill">
                    ${getDifficultyLabel(question.difficulty)}
                </div>

                <div class="question-heading">
                    <h1>
                        ${escapeHTML(question.title)}
                    </h1>
                </div>

                <div class="question-matrix-wrap">
                    ${renderQuestionMatrix(question)}
                </div>

                <div class="answer-title">
                    Javobni tanlang
                </div>

                ${renderOptions(question)}

                <div class="test-bottom">
                    <button
                        class="next-button ${selected === undefined ? "is-disabled" : ""}"
                        id="nextQuestion"
                        type="button"
                        ${selected === undefined ? "disabled" : ""}
                    >
                        ${index === TOTAL_QUESTIONS - 1
                            ? "Yakunlash ✓"
                            : "Keyingisi →"}
                    </button>
                </div>

                <div class="offline-status">
                    <span class="offline-dot"></span>
                    Javoblar telefoningizda saqlanadi
                </div>

            </section>
        `;
    }

    function bindTestEvents() {
        document
            .querySelectorAll(".answer-card")
            .forEach((button) => {
                button.addEventListener("click", () => {
                    selectAnswer(
                        Number(button.dataset.answer)
                    );
                });
            });

        document
            .getElementById("nextQuestion")
            ?.addEventListener("click", nextQuestion);

        updateTimerElement();
    }

    function selectAnswer(index) {
        if (busy || testTransitionLock) {
            return;
        }

        const question = getQuestion();

        if (!question) {
            return;
        }

        state.test.answers[state.test.current] = index;

        saveState();

        haptic("light");

        document
            .querySelectorAll(".answer-card")
            .forEach((button) => {
                const selected =
                    Number(button.dataset.answer) === index;

                button.classList.toggle(
                    "is-selected",
                    selected
                );
            });

        const nextButton =
            document.getElementById("nextQuestion");

        if (nextButton) {
            nextButton.disabled = false;
            nextButton.classList.remove("is-disabled");
        }
    }

    async function nextQuestion() {
        if (
            busy ||
            testTransitionLock
        ) {
            return;
        }

        const currentAnswer =
            state.test.answers[state.test.current];

        if (currentAnswer === undefined) {
            showToast(
                "Avval javobni tanlang.",
                "warning"
            );

            return;
        }

        testTransitionLock = true;

        try {
            if (state.test.current === 4) {
                await showFiveQuestionCelebration();
            }

            if (
                state.test.current ===
                TOTAL_QUESTIONS - 1
            ) {
                await finishIQTest();
                return;
            }

            state.test.current += 1;

            saveState();

            renderCurrentScreen();

            haptic("light");
        } finally {
            testTransitionLock = false;
        }
    }

    function showFiveQuestionCelebration() {
        return new Promise((resolve) => {
            const overlay = document.createElement("div");

            overlay.className =
                "celebration-overlay celebration-five";

            overlay.innerHTML = `
                <div class="celebration-card">
                    <div class="celebration-particles">
                        ✦ ✧ ✦ ✧ ✦
                    </div>

                    <div class="celebration-icon">
                        🎉
                    </div>

                    <h2>
                        Ajoyib boshladingiz! 🚀
                    </h2>

                    <p>
                        Birinchi 5 savol ortda.
                        Shu zaylda davom eting!
                    </p>

                    <button
                        class="primary-button"
                        id="continueAfterFive"
                        type="button"
                    >
                        Davom etish →
                    </button>
                </div>
            `;

            document.body.appendChild(overlay);

            requestAnimationFrame(() => {
                overlay.classList.add("is-visible");
            });

            overlay
                .querySelector("#continueAfterFive")
                ?.addEventListener("click", () => {
                    overlay.classList.remove("is-visible");

                    setTimeout(() => {
                        overlay.remove();
                        resolve();
                    }, 220);
                });
        });
    }

    function startTimer() {
        stopTimer();

        if (!state.test.startedAt) {
            state.test.startedAt = Date.now();
        }

        timerHandle = setInterval(() => {
            const elapsed = Math.floor(
                (Date.now() - state.test.startedAt) / 1000
            );

            state.test.elapsedSeconds = elapsed;

            updateTimerElement();

            if (elapsed % 5 === 0) {
                saveState();
            }
        }, 1000);

        updateTimerElement();
    }

    function stopTimer() {
        if (timerHandle) {
            clearInterval(timerHandle);
            timerHandle = null;
        }
    }

    function updateTimerElement() {
        const timer =
            document.getElementById("testTimer");

        if (timer) {
            timer.textContent =
                formatDuration(
                    state.test.elapsedSeconds
                );
        }
    }

    /*
     * ============================================================
     * IQ SUBMISSION
     * ============================================================
     */

    async function finishIQTest() {
        stopTimer();

        state.test.submitted = true;

        saveState();

        setScreen("processing");

        await sleep(1100);

        let result = null;

        try {
            result = await api(
                "/api/test/submit",
                {
                    method: "POST",
                    timeout: 20000,
                    body: {
                        test_type: "iq",
                        session_id: state.test.sessionId,
                        battle_id: state.test.battleId || null,
                        answers: state.test.answers,
                        elapsed_seconds:
                            state.test.elapsedSeconds
                    }
                }
            );
        } catch (error) {
            console.error(
                "[IQ TEST BOT] IQ submit failed:",
                error
            );

            /*
             * If backend is unavailable, calculate a local
             * provisional result. It is clearly marked as
             * provisional until the server confirms it.
             */
            if (
                error.name === "TypeError" ||
                error.code === "TIMEOUT" ||
                !navigator.onLine
            ) {
                result = buildLocalResult();
                result.provisional = true;
            } else {
                state.test.submitted = false;
                saveState();

                setScreen("test");

                showToast(
                    error.message ||
                    "Natijani yuborishda xatolik yuz berdi.",
                    "error"
                );

                return;
            }
        }

        state.result = normalizeIQResult(result);

        state.test.result = state.result;

        state.test.submitted = true;

        saveState();

        haptic("success");

        await sleep(500);

        setScreen("result");
    }

    function buildLocalResult() {
        let raw = 0;
        let correct = 0;

        const weights = IQ_QUESTIONS.map(
            (_, index) => {
                if (index < 6) return 1;
                if (index < 12) return 2;
                return 3;
            }
        );

        IQ_QUESTIONS.forEach((question, index) => {
            const answer =
                state.test.answers[index];

            if (answer === question.correct) {
                correct += 1;
                raw += weights[index];
            }
        });

        const maxRaw =
            weights.reduce(
                (sum, value) => sum + value,
                0
            );

        const score = Math.round(
            40 + (raw / maxRaw) * 120
        );

        return {
            attempt_id: state.test.sessionId,
            score,
            iq_score: score,
            correct,
            total: TOTAL_QUESTIONS,
            elapsed_seconds:
                state.test.elapsedSeconds,
            level: getScoreLevel(score),
            metrics: buildMetrics(),
            provisional: true
        };
    }

    function normalizeIQResult(result) {
        const score = Number(
            result?.iq_score ??
            result?.score ??
            0
        );

        return {
            ...result,
            score,
            iq_score: score,
            correct: Number(
                result?.correct ??
                result?.correct_answers ??
                0
            ),
            total: Number(
                result?.total ??
                TOTAL_QUESTIONS
            ),
            elapsed_seconds: Number(
                result?.elapsed_seconds ??
                state.test.elapsedSeconds
            ),
            level:
                result?.level ||
                getScoreLevel(score),
            metrics:
                result?.metrics ||
                buildMetrics()
        };
    }

    function getScoreLevel(score) {
        if (score >= 130) {
            return "Juda yuqori daraja";
        }

        if (score >= 115) {
            return "Yuqori daraja";
        }

        if (score >= 100) {
            return "O‘rtachadan yuqori";
        }

        if (score >= 85) {
            return "O‘rtacha daraja";
        }

        if (score >= 70) {
            return "O‘rtachadan past";
        }

        return "Boshlang‘ich daraja";
    }

    function buildMetrics() {
        const categories = {
            logic: {
                correct: 0,
                total: 0
            },
            spatial: {
                correct: 0,
                total: 0
            },
            pattern: {
                correct: 0,
                total: 0
            }
        };

        IQ_QUESTIONS.forEach(
            (question, index) => {
                const category =
                    categories[question.category];

                if (!category) {
                    return;
                }

                category.total += 1;

                if (
                    state.test.answers[index] ===
                    question.correct
                ) {
                    category.correct += 1;
                }
            }
        );

        const toScore = (item) => {
            if (!item.total) {
                return 0;
            }

            return Math.round(
                (item.correct / item.total) * 100
            );
        };

        return {
            logic: toScore(categories.logic),
            spatial: toScore(categories.spatial),
            pattern: toScore(categories.pattern)
        };
    }

    /*
     * ============================================================
     * PROCESSING
     * ============================================================
     */

    function renderProcessing() {
        return `
            <section class="screen processing-screen">

                <div class="processing-brain">
                    <div class="processing-ring ring-one"></div>
                    <div class="processing-ring ring-two"></div>

                    <div class="processing-core">
                        🧠
                    </div>
                </div>

                <div class="processing-kicker">
                    TEST YAKUNLANDI
                </div>

                <h1>
                    Natijangiz
                    hisoblanmoqda...
                </h1>

                <div class="processing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                    <span></span>
                    <span></span>
                </div>

                <p>
                    Javoblaringiz tahlil qilinmoqda
                </p>

            </section>
        `;
    }

    /*
     * ============================================================
     * RESULT
     * ============================================================
     */

    function renderResult() {
        const result =
            state.result ||
            state.test.result ||
            buildLocalResult();

        const score = Number(
            result.iq_score ||
            result.score ||
            0
        );

        const correct = Number(
            result.correct || 0
        );

        const total = Number(
            result.total ||
            TOTAL_QUESTIONS
        );

        const metrics =
            result.metrics ||
            buildMetrics();

        const provisional =
            result.provisional === true;

        return `
            <section class="screen result-screen">

                <div class="result-celebration">
                    <div class="result-confetti">
                        ✦ ✧ ✦ ✧ ✦
                    </div>

                    <div class="result-check">
                        ✓
                    </div>

                    <div class="eyebrow">
                        TEST YAKUNLANDI
                    </div>

                    <h1>
                        SIZNING NATIJANGIZ
                    </h1>
                </div>

                <div class="score-card">

                    <div class="score-label">
                        IQ-STYLE SCORE
                    </div>

                    <div
                        class="score-number"
                        data-score="${score}"
                    >
                        0
                    </div>

                    <div class="score-level">
                        ${escapeHTML(
                            result.level ||
                            getScoreLevel(score)
                        )}
                    </div>

                    <div class="score-line"></div>

                    <div class="result-stats">

                        <div>
                            <strong>
                                ${correct}/${total}
                            </strong>
                            <span>
                                To‘g‘ri javob
                            </span>
                        </div>

                        <div>
                            <strong>
                                ${formatDuration(
                                    result.elapsed_seconds
                                )}
                            </strong>
                            <span>
                                Test vaqti
                            </span>
                        </div>

                    </div>
                </div>

                <div class="metrics-card">
                    <div class="section-title">
                        📊 YO‘NALISHLAR
                    </div>

                    ${metricRow(
                        "Mantiqiy fikrlash",
                        metrics.logic
                    )}

                    ${metricRow(
                        "Fazoviy tasavvur",
                        metrics.spatial
                    )}

                    ${metricRow(
                        "Naqsh aniqlash",
                        metrics.pattern
                    )}
                </div>

                <div class="strength-card">
                    <div class="strength-icon">
                        💡
                    </div>

                    <div>
                        <span>
                            KUCHLI TOMONINGIZ
                        </span>

                        <strong>
                            ${escapeHTML(
                                getStrongestMetric(
                                    metrics
                                )
                            )}
                        </strong>
                    </div>
                </div>

                ${
                    provisional
                        ? `
                            <div class="warning-card">
                                <strong>
                                    ⚠️ Vaqtinchalik natija
                                </strong>

                                <span>
                                    Internet tiklangach natija
                                    server bilan sinxronlanadi.
                                </span>
                            </div>
                        `
                        : ""
                }

                <div class="result-actions">

                    <button
                        class="primary-button"
                        id="certificateButton"
                        type="button"
                    >
                        📜 SERTIFIKATNI OLISH
                    </button>

                    <button
                        class="secondary-button"
                        id="shareResultButton"
                        type="button"
                    >
                        📤 NATIJANI ULASHISH
                    </button>

                    <button
                        class="ghost-button"
                        id="retryIQButton"
                        type="button"
                    >
                        🔄 IQ TESTNI QAYTA ISHLASH
                    </button>

                    <button
                        class="ghost-button"
                        id="continueEQButton"
                        type="button"
                    >
                        🎭 EQ TESTINI OCHISH
                    </button>

                </div>

                <div class="result-disclaimer">
                    IQ-style score — standart klinik IQ testi emas.
                </div>

            </section>
        `;
    }

    function metricRow(label, value) {
        const score = Math.max(
            0,
            Math.min(100, Number(value || 0))
        );

        return `
            <div class="metric-row">
                <div class="metric-head">
                    <span>
                        ${escapeHTML(label)}
                    </span>

                    <strong>
                        ${score}/100
                    </strong>
                </div>

                <div class="metric-track">
                    <div
                        class="metric-fill"
                        style="width:${score}%"
                    ></div>
                </div>
            </div>
        `;
    }

    function getStrongestMetric(metrics) {
        const list = [
            {
                name: "Mantiqiy fikrlash",
                value: Number(metrics.logic || 0)
            },
            {
                name: "Fazoviy tasavvur",
                value: Number(metrics.spatial || 0)
            },
            {
                name: "Naqshlarni aniqlash",
                value: Number(metrics.pattern || 0)
            }
        ];

        list.sort(
            (a, b) => b.value - a.value
        );

        return list[0]?.name || "Mantiqiy fikrlash";
    }

    function bindResultEvents() {
        animateScore();

        document
            .getElementById("certificateButton")
            ?.addEventListener(
                "click",
                requestCertificate
            );

        document
            .getElementById("shareResultButton")
            ?.addEventListener(
                "click",
                shareResult
            );

        document
            .getElementById("retryIQButton")
            ?.addEventListener(
                "click",
                () => openPayment("iq_retry")
            );

        document
            .getElementById("continueEQButton")
            ?.addEventListener(
                "click",
                openEQ
            );
    }

    function animateScore() {
        const element =
            document.querySelector(
                ".score-number"
            );

        if (!element) {
            return;
        }

        const target = Number(
            element.dataset.score || 0
        );

        const duration = 1300;
        const started = performance.now();

        function tick(now) {
            const progress = Math.min(
                1,
                (now - started) / duration
            );

            const eased =
                1 -
                Math.pow(
                    1 - progress,
                    3
                );

            element.textContent =
                Math.round(
                    target * eased
                );

            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    }

    async function requestCertificate() {
        if (busy) {
            return;
        }

        setBusy(true);

        try {
            const attemptId =
                state.result?.attempt_id ||
                state.test.sessionId;

            const response = await api(
                "/api/certificate/request",
                {
                    method: "POST",
                    body: {
                        attempt_id: attemptId,
                        certificate_type:
                            "iq"
                    }
                }
            );

            if (response.file_url) {
                window.open(
                    response.file_url,
                    "_blank"
                );
            }

            showToast(
                response.message ||
                "Sertifikat Telegram botga yuborildi.",
                "success"
            );
        } catch (error) {
            showToast(
                error.message ||
                "Sertifikat olishda xatolik.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    }

    async function shareResult() {
        const score =
            state.result?.iq_score ||
            state.result?.score ||
            0;

        const text =
            `🧠 IQ TEST BOT\n\n` +
            `Mening IQ-style score'im: ${score}\n\n` +
            `Sen ham o‘zingni sinab ko‘r!`;

        try {
            if (
                navigator.share
            ) {
                await navigator.share({
                    title: APP_NAME,
                    text
                });

                return;
            }
        } catch {
            // User cancelled native share.
        }

        try {
            await navigator.clipboard.writeText(
                text
            );

            showToast(
                "Natija matni nusxalandi.",
                "success"
            );
        } catch {
            showToast(
                text,
                "info"
            );
        }
    }

    /*
     * ============================================================
     * EQ / PQ
     * ============================================================
     */

    function openEQ() {
        if (!state.result) {
            showToast(
                "Avval IQ testini yakunlang.",
                "warning"
            );

            return;
        }

        setScreen("eq");
    }

    function openPQ() {
        if (!state.eq.completed) {
            showToast(
                "Avval EQ testini yakunlang.",
                "warning"
            );

            return;
        }

        setScreen("pq");
    }

    function renderPsychologicalTest(type) {
        const questions =
            type === "eq"
                ? EQ_QUESTIONS
                : PQ_QUESTIONS;

        const data =
            type === "eq"
                ? state.eq
                : state.pq;

        const title =
            type === "eq"
                ? "Hissiy intellekt"
                : "Prokrastinatsiya";

        const subtitle =
            type === "eq"
                ? "Vaziyatlarda qanday fikrlashingizni aniqlang."
                : "Ishni keyinga surish odatlaringizni tahlil qiling.";

        return `
            <section class="screen psychology-screen">

                <div class="psychology-header">
                    <div class="intro-icon">
                        ${type === "eq" ? "🎭" : "⏳"}
                    </div>

                    <div class="eyebrow">
                        ${type === "eq" ? "EQ" : "PQ"}
                    </div>

                    <h1>
                        ${title}
                    </h1>

                    <p>
                        ${subtitle}
                    </p>
                </div>

                <div class="psych-progress">
                    <div
                        class="progress-fill"
                        style="width:${(
                            (data.answers.length /
                                questions.length) *
                            100
                        )}%"
                    ></div>
                </div>

                <div class="psych-question-list">
                    ${questions.map(
                        (question, index) => `
                            <div class="psych-question">
                                <div class="psych-number">
                                    ${index + 1}
                                </div>

                                <h2>
                                    ${escapeHTML(
                                        question.text
                                    )}
                                </h2>

                                <div class="psych-options">
                                    ${question.options.map(
                                        (option, optionIndex) => `
                                            <button
                                                type="button"
                                                class="psych-option ${
                                                    data.answers[index] ===
                                                    optionIndex
                                                        ? "is-selected"
                                                        : ""
                                                }"
                                                data-psych-type="${type}"
                                                data-question="${index}"
                                                data-answer="${optionIndex}"
                                            >
                                                <span>
                                                    ${getAnswerLetter(
                                                        optionIndex
                                                    )}
                                                </span>

                                                <strong>
                                                    ${escapeHTML(
                                                        option
                                                    )}
                                                </strong>
                                            </button>
                                        `
                                    ).join("")}
                                </div>
                            </div>
                        `
                    ).join("")}
                </div>

                <button
                    class="primary-button"
                    id="finishPsychButton"
                    type="button"
                >
                    ${data.answers.length === questions.length
                        ? "Yakunlash ✓"
                        : "Javoblarni davom ettirish"}
                </button>

            </section>
        `;
    }

    function bindPsychologicalEvents(type) {
        document
            .querySelectorAll(
                `[data-psych-type="${type}"]`
            )
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    () => {
                        const question =
                            Number(
                                button.dataset.question
                            );

                        const answer =
                            Number(
                                button.dataset.answer
                            );

                        const target =
                            type === "eq"
                                ? state.eq
                                : state.pq;

                        target.answers[question] =
                            answer;

                        saveState();

                        document
                            .querySelectorAll(
                                `[data-psych-type="${type}"][data-question="${question}"]`
                            )
                            .forEach((item) => {
                                item.classList.toggle(
                                    "is-selected",
                                    Number(
                                        item.dataset.answer
                                    ) === answer
                                );
                            });
                    }
                );
            });

        document
            .getElementById("finishPsychButton")
            ?.addEventListener(
                "click",
                () => finishPsychologicalTest(type)
            );
    }

    async function finishPsychologicalTest(type) {
        const target =
            type === "eq"
                ? state.eq
                : state.pq;

        const questions =
            type === "eq"
                ? EQ_QUESTIONS
                : PQ_QUESTIONS;

        if (
            target.answers.length !==
            questions.length ||
            target.answers.some(
                (answer) =>
                    answer === undefined
            )
        ) {
            showToast(
                "Barcha savollarga javob bering.",
                "warning"
            );

            return;
        }

        if (busy) {
            return;
        }

        setBusy(true);

        try {
            const response = await api(
                "/api/test/submit",
                {
                    method: "POST",
                    body: {
                        test_type: type,
                        answers: target.answers
                    }
                }
            );

            target.result = response;
            target.completed = true;

            if (type === "eq") {
                target.unlocked = true;
            }

            saveState();

            showToast(
                type === "eq"
                    ? "EQ testi tugadi."
                    : "Prokrastinatsiya testi tugadi.",
                "success"
            );

            if (type === "eq") {
                state.pq.unlocked = true;
                setScreen("pq");
            } else {
                state.profile.unlocked = true;

                try {
                    const profile =
                        await api(
                            "/api/profile/generate",
                            {
                                method: "POST"
                            }
                        );

                    state.profile.result =
                        profile;
                } catch (error) {
                    console.warn(
                        "[IQ TEST BOT] Profile generation fallback:",
                        error
                    );
                }

                setScreen("profile");
            }
        } catch (error) {
            showToast(
                error.message ||
                "Natijani saqlashda xatolik.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    }

    /*
     * ============================================================
     * PERSONAL ANALYSIS
     * ============================================================
     */

    function openProfile() {
        if (
            !state.eq.completed ||
            !state.pq.completed
        ) {
            showToast(
                "Avval IQ, EQ va PQ testlarini yakunlang.",
                "warning"
            );

            return;
        }

        setScreen("profile");
    }

    function renderProfile() {
        const profile =
            state.profile.result || {};

        const iq =
            state.result?.iq_score ||
            state.result?.score ||
            0;

        const eq =
            Number(
                profile.eq_score ??
                state.eq.result?.score ??
                0
            );

        const pq =
            Number(
                profile.pq_score ??
                state.pq.result?.score ??
                0
            );

        return `
            <section class="screen profile-screen">

                <div class="profile-hero">
                    <div class="intro-icon">
                        ⭐
                    </div>

                    <div class="eyebrow">
                        SHAXSIY TAHLIL
                    </div>

                    <h1>
                        Siz qanday insonsiz?
                    </h1>

                    <p>
                        Uchta test natijasi asosida
                        umumiy profilingiz.
                    </p>
                </div>

                <div class="profile-score-grid">

                    <div>
                        <span>🧠 IQ</span>
                        <strong>${iq}</strong>
                    </div>

                    <div>
                        <span>🎭 EQ</span>
                        <strong>${eq || "—"}</strong>
                    </div>

                    <div>
                        <span>⏳ PQ</span>
                        <strong>${pq || "—"}</strong>
                    </div>

                </div>

                <div class="glass-panel profile-panel">
                    <h2>
                        Umumiy profil
                    </h2>

                    <p>
                        Sizning mantiqiy fikrlashingiz,
                        hissiy qarorlaringiz va ishni
                        boshlash odatlaringiz birgalikda
                        tahlil qilinadi.
                    </p>
                </div>

                <div class="analysis-columns">

                    <div class="analysis-card">
                        <span>💪</span>
                        <strong>
                            Kuchli tomonlar
                        </strong>
                        <p>
                            Tahliliy fikrlash,
                            patternlarni aniqlash va
                            vaziyatni tizimli ko‘rish.
                        </p>
                    </div>

                    <div class="analysis-card">
                        <span>🎯</span>
                        <strong>
                            Rivojlantirish
                        </strong>
                        <p>
                            Rejalashtirish, e’tiborni
                            boshqarish va hissiy bosim
                            ostida qaror qilish.
                        </p>
                    </div>

                </div>

                <button
                    class="primary-button"
                    id="profileDone"
                    type="button"
                >
                    ✓ TUGATISH
                </button>

            </section>
        `;
    }

    function bindProfileEvents() {
        document
            .getElementById("profileDone")
            ?.addEventListener(
                "click",
                () => setScreen("home")
            );
    }

    /*
     * ============================================================
     * BATTLE
     * ============================================================
     */

    function openBattle() {
        setScreen("battle");
    }

    function renderBattle() {
        const battle = state.battle;

        return `
            <section class="screen battle-screen">

                <div class="battle-hero">
                    <div class="battle-icon">
                        ⚔️
                    </div>

                    <div class="eyebrow">
                        IQ BATTLE
                    </div>

                    <h1>
                        Do‘stingiz bilan bellashing
                    </h1>

                    <p>
                        18 ta mustaqil IQ savoli.
                        Natijada final IQ-style score
                        solishtiriladi.
                    </p>

                    <div class="battle-price-large">
                        ${formatNumber(
                            state.config?.battle_price ||
                            7500
                        )}
                        so‘m / ishtirokchi
                    </div>
                </div>

                ${
                    battle.id
                        ? renderExistingBattle()
                        : `
                            <div class="battle-actions">

                                <button
                                    class="primary-button"
                                    id="createBattleButton"
                                    type="button"
                                >
                                    ⚔️ BATTLE YARATISH
                                </button>

                                <div class="battle-divider">
                                    <span>yoki</span>
                                </div>

                                <div class="battle-join-box">
                                    <input
                                        id="battleCodeInput"
                                        type="text"
                                        maxlength="4"
                                        inputmode="text"
                                        autocomplete="off"
                                        placeholder="4 xonali kod"
                                    />

                                    <button
                                        class="secondary-button"
                                        id="joinBattleButton"
                                        type="button"
                                    >
                                        KOD BILAN KIRISH
                                    </button>
                                </div>

                            </div>
                        `
                }

                <div class="battle-rules">
                    <div>
                        ✓ Ikkala o‘yinchi alohida test ishlaydi.
                    </div>
                    <div>
                        ✓ Javoblaringiz bir-biringizga ko‘rinmaydi.
                    </div>
                    <div>
                        ✓ G‘olib final IQ-style score bilan aniqlanadi.
                    </div>
                    <div>
                        ✓ Teng natija — durang.
                    </div>
                </div>

            </section>
        `;
    }

    function renderExistingBattle() {
        const battle = state.battle;

        return `
            <div class="battle-existing">

                <div class="battle-code-card">
                    <span>
                        BATTLE KODI
                    </span>

                    <strong>
                        ${escapeHTML(
                            battle.code || "----"
                        )}
                    </strong>

                    <small>
                        Do‘stingizga shu kodni yuboring.
                    </small>
                </div>

                <div class="battle-status-card">
                    <div class="battle-status-dot"></div>

                    <strong>
                        ${
                            battle.status === "ready"
                                ? "Battle tayyor"
                                : "Do‘stingiz kutilmoqda..."
                        }
                    </strong>

                    <span>
                        ${
                            battle.opponent
                                ? `Raqib: ${escapeHTML(
                                    battle.opponent
                                )}`
                                : "Kod orqali do‘stingiz qo‘shilishi kerak."
                        }
                    </span>
                </div>

                ${
                    battle.status === "ready"
                        ? `
                            <button
                                class="primary-button"
                                id="startBattleButton"
                                type="button"
                            >
                                🚀 BATTLE TESTINI BOSHLASH
                            </button>
                        `
                        : `
                            <button
                                class="secondary-button"
                                id="refreshBattleButton"
                                type="button"
                            >
                                ↻ HOLATNI TEKSHIRISH
                            </button>
                        `
                }

            </div>
        `;
    }

    function bindBattleEvents() {
        document
            .getElementById("createBattleButton")
            ?.addEventListener(
                "click",
                createBattle
            );

        document
            .getElementById("joinBattleButton")
            ?.addEventListener(
                "click",
                joinBattle
            );

        document
            .getElementById("startBattleButton")
            ?.addEventListener(
                "click",
                startBattle
            );

        document
            .getElementById("refreshBattleButton")
            ?.addEventListener(
                "click",
                refreshBattle
            );
    }

    async function createBattle() {
        if (busy) {
            return;
        }

        setBusy(true);

        try {
            const response = await api(
                "/api/battle/create",
                {
                    method: "POST",
                    body: {}
                }
            );

            state.battle = {
                ...state.battle,
                id:
                    response.battle_id ||
                    response.id,
                code:
                    response.code ||
                    response.battle_code,
                role: "creator",
                status:
                    response.status ||
                    "waiting"
            };

            saveState();

            setScreen("battle");

            showToast(
                "Battle yaratildi.",
                "success"
            );
        } catch (error) {
            if (error.status === 402) {
                await openPayment("battle");
                return;
            }

            showToast(
                error.message ||
                "Battle yaratishda xatolik.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    }

    async function joinBattle() {
        const input =
            document.getElementById(
                "battleCodeInput"
            );

        const code =
            input?.value
                ?.trim()
                .toUpperCase();

        if (!code || code.length !== 4) {
            showToast(
                "4 xonali battle kodini kiriting.",
                "warning"
            );

            return;
        }

        if (busy) {
            return;
        }

        setBusy(true);

        try {
            const response = await api(
                "/api/battle/join",
                {
                    method: "POST",
                    body: {
                        code
                    }
                }
            );

            state.battle = {
                ...state.battle,
                id:
                    response.battle_id ||
                    response.id,
                code,
                role: "joiner",
                status:
                    response.status ||
                    "ready",
                opponent:
                    response.creator_name ||
                    null
            };

            saveState();

            setScreen("battle");

            showToast(
                "Battlega qo‘shildingiz.",
                "success"
            );
        } catch (error) {
            if (error.status === 402) {
                await openPayment("battle");
                return;
            }

            showToast(
                error.message ||
                "Battlega qo‘shilishda xatolik.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    }

    async function refreshBattle() {
        if (!state.battle.id) {
            return;
        }

        try {
            const response = await api(
                `/api/battle/${encodeURIComponent(
                    state.battle.id
                )}`
            );

            state.battle = {
                ...state.battle,
                ...response,
                id:
                    response.battle_id ||
                    response.id ||
                    state.battle.id
            };

            saveState();

            setScreen("battle");
        } catch (error) {
            showToast(
                error.message ||
                "Battle holatini olishda xatolik.",
                "error"
            );
        }
    }

    async function startBattle() {
        if (!state.battle.id) {
            return;
        }

        state.test.battleId =
            state.battle.id;

        await startIQTest({
            forceNew: true
        });
    }

    /*
     * ============================================================
     * PAYMENT
     * ============================================================
     */

    async function openPayment(product) {
        if (busy) {
            return;
        }

        setBusy(true);

        try {
            const response = await api(
                "/api/payment/create",
                {
                    method: "POST",
                    body: {
                        product
                    }
                }
            );

            state.payment = {
                id:
                    response.payment_id ||
                    response.id,
                product,
                amount:
                    Number(
                        response.amount ||
                        response.price ||
                        0
                    ),
                status:
                    response.status ||
                    "pending",
                createdAt:
                    Date.now()
            };

            saveState();

            renderPaymentModal(
                response
            );

            startPaymentPolling();
        } catch (error) {
            showToast(
                error.message ||
                "To‘lov oynasini ochib bo‘lmadi.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    }

    function renderPaymentModal(data = {}) {
        const existing =
            document.querySelector(
                ".payment-modal"
            );

        existing?.remove();

        const amount =
            Number(
                data.amount ||
                data.price ||
                state.payment.amount ||
                getProductPrice(
                    state.payment.product
                )
            );

        const cardNumber =
            data.card_number ||
            data.card ||
            "Admin karta raqami";

        const click =
            data.click_number ||
            data.click ||
            "";

        const modal =
            document.createElement("div");

        modal.className =
            "modal-backdrop payment-modal";

        modal.innerHTML = `
            <div class="modal-card payment-card">

                <button
                    class="modal-close"
                    type="button"
                    aria-label="Yopish"
                >
                    ×
                </button>

                <div class="payment-icon">
                    💳
                </div>

                <div class="eyebrow">
                    TO‘LOV
                </div>

                <h2>
                    To‘lovni amalga oshiring
                </h2>

                <div class="payment-amount">
                    ${formatNumber(amount)} so‘m
                </div>

                <div class="payment-method">
                    <span>
                        Karta
                    </span>

                    <strong>
                        ${escapeHTML(cardNumber)}
                    </strong>
                </div>

                ${
                    click
                        ? `
                            <div class="payment-method">
                                <span>
                                    Click
                                </span>

                                <strong>
                                    ${escapeHTML(click)}
                                </strong>
                            </div>
                        `
                        : ""
                }

                <p class="payment-help">
                    To‘lovni amalga oshirgach,
                    chekni yuboring.
                </p>

                <label class="receipt-upload">
                    <span>
                        📎 Chekni tanlash
                    </span>

                    <input
                        id="receiptFile"
                        type="file"
                        accept="image/*,.pdf"
                    />
                </label>

                <button
                    class="primary-button"
                    id="sendReceiptButton"
                    type="button"
                >
                    💳 TO‘LOV QILISH
                </button>

                <div class="payment-status">
                    To‘lov holati:
                    <strong>
                        Kutilmoqda
                    </strong>
                </div>

            </div>
        `;

        document.body.appendChild(modal);

        modal
            .querySelector(".modal-close")
            ?.addEventListener(
                "click",
                () => modal.remove()
            );

        modal.addEventListener(
            "click",
            (event) => {
                if (event.target === modal) {
                    modal.remove();
                }
            }
        );

        modal
            .querySelector(
                "#sendReceiptButton"
            )
            ?.addEventListener(
                "click",
                submitReceipt
            );
    }

    function getProductPrice(product) {
        const defaults = {
            iq: 10000,
            iq_retry: 5000,
            eq_retry: 5000,
            pq_retry: 5000,
            battle: 7500
        };

        return Number(
            state.config?.prices?.[product] ??
            state.config?.[`${product}_price`] ??
            defaults[product] ??
            0
        );
    }

    async function submitReceipt() {
        const file =
            document.getElementById(
                "receiptFile"
            )?.files?.[0];

        if (!file) {
            showToast(
                "Avval chekni tanlang.",
                "warning"
            );

            return;
        }

        if (!state.payment.id) {
            showToast(
                "Payment ID topilmadi.",
                "error"
            );

            return;
        }

        const button =
            document.getElementById(
                "sendReceiptButton"
            );

        if (button) {
            button.disabled = true;
        }

        try {
            const form =
                new FormData();

            form.append(
                "payment_id",
                state.payment.id
            );

            form.append(
                "receipt",
                file
            );

            await api(
                "/api/payment/receipt",
                {
                    method: "POST",
                    body: form,
                    timeout: 30000
                }
            );

            state.payment.status =
                "pending_receipt";

            saveState();

            showToast(
                "Chek yuborildi. Admin tasdiqlashini kuting.",
                "success"
            );

            const status =
                document.querySelector(
                    ".payment-status strong"
                );

            if (status) {
                status.textContent =
                    "Admin tasdiqlashi kutilmoqda";
            }
        } catch (error) {
            showToast(
                error.message ||
                "Chekni yuborishda xatolik.",
                "error"
            );
        } finally {
            if (button) {
                button.disabled = false;
            }
        }
    }

    function startPaymentPolling() {
        stopPaymentPolling();

        if (!state.payment.id) {
            return;
        }

        state.paymentPoll = setInterval(
            async () => {
                try {
                    const response =
                        await api(
                            `/api/payment/${encodeURIComponent(
                                state.payment.id
                            )}`
                        );

                    const status =
                        response.status;

                    state.payment.status =
                        status;

                    saveState();

                    if (
                        status === "approved" ||
                        status === "paid" ||
                        status === "completed"
                    ) {
                        stopPaymentPolling();

                        document
                            .querySelector(
                                ".payment-modal"
                            )
                            ?.remove();

                        showToast(
                            "To‘lov tasdiqlandi. Funksiya ochildi.",
                            "success"
                        );

                        if (
                            state.payment.product ===
                            "battle"
                        ) {
                            await createBattleAfterPayment();
                        } else {
                            await resumeAfterPayment(
                                state.payment.product
                            );
                        }
                    }

                    if (
                        status === "rejected" ||
                        status === "cancelled"
                    ) {
                        stopPaymentPolling();

                        showToast(
                            "To‘lov rad etildi.",
                            "error"
                        );
                    }
                } catch (error) {
                    console.warn(
                        "[IQ TEST BOT] Payment polling:",
                        error
                    );
                }
            },
            4000
        );
    }

    function stopPaymentPolling() {
        if (state.paymentPoll) {
            clearInterval(
                state.paymentPoll
            );

            state.paymentPoll = null;
        }
    }

    async function resumeAfterPayment(product) {
        if (
            product === "iq" ||
            product === "iq_retry"
        ) {
            await startIQTest({
                forceNew: true
            });

            return;
        }

        if (product === "eq_retry") {
            state.eq.answers = [];
            state.eq.completed = false;

            saveState();

            setScreen("eq");

            return;
        }

        if (product === "pq_retry") {
            state.pq.answers = [];
            state.pq.completed = false;

            saveState();

            setScreen("pq");
        }
    }

    async function createBattleAfterPayment() {
        try {
            const response = await api(
                "/api/battle/create",
                {
                    method: "POST",
                    body: {
                        paid: true
                    }
                }
            );

            state.battle = {
                ...state.battle,
                id:
                    response.battle_id ||
                    response.id,
                code:
                    response.code ||
                    response.battle_code,
                role: "creator",
                status:
                    response.status ||
                    "waiting"
            };

            saveState();

            setScreen("battle");
        } catch (error) {
            showToast(
                error.message ||
                "Battle yaratilmadi.",
                "error"
            );
        }
    }

    /*
     * ============================================================
     * LIVE STATS
     * ============================================================
     */

    async function loadLiveStats() {
        try {
            const response =
                await api(
                    "/api/stats/live",
                    {
                        timeout: 8000
                    }
                );

            state.liveUsers =
                Number(
                    response.online ??
                    response.live_users ??
                    response.active_users ??
                    0
                );

            state.totalUsers =
                Number(
                    response.total_users ??
                    response.users ??
                    0
                );

            updateLiveCounters();
        } catch (error) {
            console.warn(
                "[IQ TEST BOT] Live stats unavailable:",
                error
            );
        }
    }

    function updateLiveCounters() {
        const total =
            document.getElementById(
                "totalUsers"
            );

        const live =
            document.getElementById(
                "liveUsers"
            );

        if (total) {
            animateCounter(
                total,
                state.totalUsers
            );
        }

        if (live) {
            animateCounter(
                live,
                state.liveUsers
            );
        }
    }

    function animateCounter(element, target) {
        if (!element) {
            return;
        }

        const finalValue =
            Number(target || 0);

        const currentText =
            element.textContent
                ?.replace(/[^\d]/g, "");

        const startValue =
            Number(currentText || 0);

        if (startValue === finalValue) {
            element.textContent =
                formatNumber(finalValue);

            return;
        }

        const duration = 700;
        const start = performance.now();

        function tick(now) {
            const progress =
                Math.min(
                    1,
                    (now - start) / duration
                );

            const value =
                Math.round(
                    startValue +
                    (finalValue - startValue) *
                    progress
                );

            element.textContent =
                formatNumber(value);

            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    }

    function startLiveRefresh() {
        stopLiveRefresh();

        loadLiveStats();

        liveRefreshHandle =
            setInterval(
                loadLiveStats,
                30000
            );
    }

    function stopLiveRefresh() {
        if (liveRefreshHandle) {
            clearInterval(
                liveRefreshHandle
            );

            liveRefreshHandle = null;
        }
    }

    /*
     * ============================================================
     * QUICK MENU
     * ============================================================
     */

    function openQuickMenu() {
        const existing =
            document.querySelector(
                ".quick-menu-backdrop"
            );

        if (existing) {
            existing.remove();
            return;
        }

        const modal =
            document.createElement("div");

        modal.className =
            "quick-menu-backdrop";

        modal.innerHTML = `
            <div class="quick-menu-card">

                <button
                    class="modal-close"
                    type="button"
                    aria-label="Yopish"
                >
                    ×
                </button>

                <div class="quick-menu-brand">
                    IQ TEST BOT
                </div>

                <button
                    type="button"
                    data-action="home"
                >
                    🏠 Bosh sahifa
                </button>

                <button
                    type="button"
                    data-action="language"
                >
                    🌐 Til
                </button>

                <button
                    type="button"
                    data-action="help"
                >
                    ℹ️ Narx va yordam
                </button>

                <button
                    type="button"
                    data-action="close"
                >
                    ✕ Mini App'ni yopish
                </button>

            </div>
        `;

        document.body.appendChild(modal);

        modal
            .querySelector(".modal-close")
            ?.addEventListener(
                "click",
                () => modal.remove()
            );

        modal
            .querySelectorAll(
                "[data-action]"
            )
            .forEach((button) => {
                button.addEventListener(
                    "click",
                    () => {
                        const action =
                            button.dataset.action;

                        modal.remove();

                        if (action === "home") {
                            setScreen("home");
                        } else if (
                            action === "language"
                        ) {
                            showToast(
                                "Tilni Telegram bot menyusidan o‘zgartiring.",
                                "info"
                            );
                        } else if (
                            action === "help"
                        ) {
                            showToast(
                                "Narx va yordam Telegram botda mavjud.",
                                "info"
                            );
                        } else if (
                            action === "close"
                        ) {
                            closeMiniApp();
                        }
                    }
                );
            });
    }

    function handleHeaderBack() {
        if (busy) {
            return;
        }

        if (state.screen === "home") {
            return;
        }

        if (
            state.screen === "test" &&
            state.test.answers.length > 0 &&
            !state.test.submitted
        ) {
            const leave =
                window.confirm(
                    "Test davom etmoqda. Chiqsangiz progress saqlanadi. Chiqishni xohlaysizmi?"
                );

            if (!leave) {
                return;
            }

            saveState();
        }

        setScreen("home");
    }

    /*
     * ============================================================
     * CONFIG / USER
     * ============================================================
     */

    async function loadConfig() {
        try {
            const response =
                await api(
                    "/api/config",
                    {
                        timeout: 8000
                    }
                );

            state.config =
                response || {};

            return response;
        } catch (error) {
            console.warn(
                "[IQ TEST BOT] Config unavailable:",
                error
            );

            state.config = {
                battle_price: 7500,
                prices: {
                    iq: 10000,
                    iq_retry: 5000,
                    eq_retry: 5000,
                    pq_retry: 5000,
                    battle: 7500
                }
            };

            return state.config;
        }
    }

    async function loadMe() {
        try {
            const response =
                await api(
                    "/api/me",
                    {
                        timeout: 10000
                    }
                );

            state.user =
                response.user ||
                response;

            if (
                response.result &&
                !state.result
            ) {
                state.result =
                    normalizeIQResult(
                        response.result
                    );
            }

            if (response.eq) {
                state.eq = {
                    ...state.eq,
                    ...response.eq
                };
            }

            if (response.pq) {
                state.pq = {
                    ...state.pq,
                    ...response.pq
                };
            }

            if (response.profile) {
                state.profile = {
                    ...state.profile,
                    ...response.profile
                };
            }

            saveState();
        } catch (error) {
            console.warn(
                "[IQ TEST BOT] User state unavailable:",
                error
            );
        }
    }

    /*
     * ============================================================
     * NETWORK RECOVERY
     * ============================================================
     */

    window.addEventListener(
        "online",
        async () => {
            document.body.classList.remove(
                "is-offline"
            );

            showToast(
                "Internet qaytdi.",
                "success"
            );

            await syncPendingState();
        }
    );

    window.addEventListener(
        "offline",
        () => {
            document.body.classList.add(
                "is-offline"
            );

            showToast(
                "Internet yo‘q. Testni davom ettirishingiz mumkin.",
                "warning"
            );
        }
    );

    async function syncPendingState() {
        if (
            !state.test.sessionId ||
            state.test.answers.length === 0
        ) {
            return;
        }

        if (
            state.test.submitted &&
            state.result
        ) {
            return;
        }

        try {
            await api(
                "/api/session/sync",
                {
                    method: "POST",
                    body: {
                        session_id:
                            state.test.sessionId,
                        test_type:
                            state.test.type,
                        current:
                            state.test.current,
                        answers:
                            state.test.answers,
                        elapsed_seconds:
                            state.test.elapsedSeconds,
                        battle_id:
                            state.test.battleId || null
                    }
                }
            );
        } catch (error) {
            console.warn(
                "[IQ TEST BOT] Sync postponed:",
                error
            );
        }
    }

    /*
     * ============================================================
     * VISIBILITY / LIFECYCLE
     * ============================================================
     */

    document.addEventListener(
        "visibilitychange",
        () => {
            if (
                document.visibilityState ===
                "hidden"
            ) {
                saveState();
            }

            if (
                document.visibilityState ===
                "visible"
            ) {
                if (
                    state.screen === "test" &&
                    state.test.startedAt &&
                    !state.test.submitted
                ) {
                    const elapsed =
                        Math.floor(
                            (Date.now() -
                                state.test.startedAt) /
                            1000
                        );

                    state.test.elapsedSeconds =
                        Math.max(
                            state.test.elapsedSeconds,
                            elapsed
                        );

                    updateTimerElement();
                }

                syncPendingState();
            }
        }
    );

    window.addEventListener(
        "beforeunload",
        () => {
            saveState();
        }
    );

    /*
     * ============================================================
     * SMALL HELPERS
     * ============================================================
     */

    function sleep(ms) {
        return new Promise(
            (resolve) =>
                setTimeout(resolve, ms)
        );
    }

    /*
     * ============================================================
     * APP START
     * ============================================================
     */

    async function boot() {
        initTelegram();
        restoreState();
        renderShell();

        if (!navigator.onLine) {
            document.body.classList.add(
                "is-offline"
            );
        }

        setScreen("home");

        /*
         * Load remote information in parallel.
         * Failure of either call must NOT destroy the UI.
         */
        await Promise.allSettled([
            loadConfig(),
            loadMe(),
            loadLiveStats()
        ]);

        /*
         * Re-render once remote config/user data has arrived.
         */
        if (state.screen === "home") {
            renderCurrentScreen();
        }

        startLiveRefresh();

        /*
         * Restore an interrupted test.
         */
        const interrupted =
            state.test.startedAt &&
            !state.test.submitted &&
            state.test.answers.length > 0 &&
            state.test.current < TOTAL_QUESTIONS;

        if (interrupted) {
            setTimeout(() => {
                const resume =
                    window.confirm(
                        `Oldingi IQ testingiz ${state.test.current + 1}-savolda qolgan. Davom etasizmi?`
                    );

                if (resume) {
                    setScreen("test");
                    startTimer();
                } else {
                    clearTestState();
                }
            }, 450);
        }
    }

    /*
     * Expose a tiny debug interface only in development.
     * No sensitive Telegram data is exposed.
     */
    if (
        location.hostname === "localhost" ||
        location.hostname === "127.0.0.1"
    ) {
        window.IQTestBotDebug = {
            state,
            questions: IQ_QUESTIONS,
            openIQ,
            openBattle,
            render: renderCurrentScreen
        };
    }

    boot().catch((error) => {
        console.error(
            "[IQ TEST BOT] Fatal frontend boot error:",
            error
        );

        const root = ensureRoot();

        root.innerHTML = `
            <section class="fatal-error-screen">
                <div>
                    <div class="fatal-icon">
                        🧠
                    </div>

                    <h1>
                        IQ TEST BOT
                    </h1>

                    <p>
                        Ilovani ishga tushirishda
                        texnik xatolik yuz berdi.
                    </p>

                    <button
                        type="button"
                        onclick="location.reload()"
                    >
                        QAYTA URINISH
                    </button>
                </div>
            </section>
        `;
    });

})();