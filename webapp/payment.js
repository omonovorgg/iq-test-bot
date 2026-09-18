"use strict";

(() => {
    const tg = window.Telegram?.WebApp || null;

    const API = "";

    const state = {
        busy: false,
        paymentId: null,
        purpose: "retest",
        pollTimer: null,
        pollStartedAt: 0,
        pollAttempts: 0,
        closeRequested: false
    };

    const POLL_INTERVAL = 2500;
    const MAX_POLL_TIME = 15 * 60 * 1000;

    function getInitData() {
        return tg?.initData || "";
    }

    function getElement(id) {
        return document.getElementById(id);
    }

    function escapeHTML(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function formatMoney(value) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "0";
        }

        return number.toLocaleString("uz-UZ");
    }

    function setStatus(text, type = "") {
        const element = getElement("paymentStatus");

        if (!element) {
            return;
        }

        element.textContent = text;
        element.dataset.status = type;
    }

    function showToast(message) {
        const toast = getElement("toast");
        const messageElement = getElement("toastMessage");

        if (!toast) {
            return;
        }

        if (messageElement) {
            messageElement.textContent = message;
        } else {
            toast.textContent = message;
        }

        toast.classList.add("visible");

        window.clearTimeout(
            showToast.timer
        );

        showToast.timer = window.setTimeout(() => {
            toast.classList.remove("visible");
        }, 3000);
    }

    async function request(path, options = {}) {
        const headers = new Headers(
            options.headers || {}
        );

        headers.set(
            "Content-Type",
            "application/json"
        );

        headers.set(
            "X-Telegram-Init-Data",
            getInitData()
        );

        const response = await fetch(
            `${API}${path}`,
            {
                ...options,
                headers,
                cache: "no-store"
            }
        );

        let data = null;

        try {
            data = await response.json();
        } catch {
            data = null;
        }

        if (!response.ok) {
            const error = new Error(
                data?.detail ||
                `HTTP_${response.status}`
            );

            error.status = response.status;
            error.detail = data?.detail || "";

            throw error;
        }

        return data;
    }

    async function getConfig() {
        return request("/api/config", {
            method: "GET"
        });
    }

    async function createPayment(purpose = "retest") {
        return request(
            "/api/payment/create",
            {
                method: "POST",
                body: JSON.stringify({
                    purpose
                })
            }
        );
    }

    async function getPaymentStatus(paymentId) {
        return request(
            `/api/payment/${encodeURIComponent(paymentId)}`,
            {
                method: "GET"
            }
        );
    }

    function clearPollTimer() {
        if (state.pollTimer !== null) {
            window.clearTimeout(
                state.pollTimer
            );

            state.pollTimer = null;
        }
    }

    function stopPolling() {
        clearPollTimer();
        state.pollStartedAt = 0;
        state.pollAttempts = 0;
    }

    function resetState() {
        stopPolling();

        state.paymentId = null;
        state.purpose = "retest";
        state.closeRequested = false;
    }

    function renderCards(cards) {
        const container = getElement("paymentCards");

        if (!container) {
            return;
        }

        container.innerHTML = "";

        if (!Array.isArray(cards) || cards.length === 0) {
            container.innerHTML = `
                <div class="payment-empty">
                    Admin hali karta qo‘shmagan.
                </div>
            `;

            return;
        }

        for (const card of cards) {
            const wrapper = document.createElement("div");

            wrapper.className = "payment-card";

            const title = escapeHTML(
                card.title || "Karta"
            );

            const number = escapeHTML(
                card.card_number || ""
            );

            const owner = escapeHTML(
                card.owner_name || ""
            );

            wrapper.innerHTML = `
                <div class="payment-card-title">
                    ${title}
                </div>

                <div class="payment-card-number">
                    ${number}
                </div>

                ${
                    owner
                        ? `
                            <div class="payment-card-owner">
                                ${owner}
                            </div>
                          `
                        : ""
                }

                <button
                    type="button"
                    class="payment-copy-button"
                    data-card-number="${number}"
                >
                    📋 Kartani nusxalash
                </button>
            `;

            container.appendChild(wrapper);
        }

        container
            .querySelectorAll(
                ".payment-copy-button"
            )
            .forEach(button => {
                button.addEventListener(
                    "click",
                    async () => {
                        const number =
                            button.dataset.cardNumber || "";

                        if (!number) {
                            return;
                        }

                        try {
                            await navigator.clipboard.writeText(
                                number
                            );

                            showToast(
                                "✅ Karta raqami nusxalandi"
                            );
                        } catch {
                            showToast(
                                "Karta raqamini qo‘lda nusxalang."
                            );
                        }
                    }
                );
            });
    }

    function updateAmount(amount) {
        const element = getElement(
            "paymentAmount"
        );

        if (!element) {
            return;
        }

        element.textContent =
            `${formatMoney(amount)} so‘m`;
    }

    function openModal() {
        const modal = getElement(
            "paymentModal"
        );

        if (!modal) {
            return false;
        }

        modal.classList.add("visible");
        modal.setAttribute(
            "aria-hidden",
            "false"
        );

        return true;
    }

    function closeModal() {
        const modal = getElement(
            "paymentModal"
        );

        if (!modal) {
            return;
        }

        modal.classList.remove("visible");
        modal.setAttribute(
            "aria-hidden",
            "true"
        );
    }

    async function openBotPayment() {
        if (!state.paymentId) {
            showToast(
                "To‘lov ID topilmadi."
            );

            return;
        }

        try {
            const config =
                await getConfig();

            const username = String(
                config?.bot_username || ""
            )
                .trim()
                .replace(/^@/, "");

            if (!username) {
                showToast(
                    "Bot manzili sozlanmagan."
                );

                return;
            }

            const url =
                `https://t.me/${encodeURIComponent(username)}` +
                `?start=pay_${encodeURIComponent(state.paymentId)}`;

            if (
                tg &&
                typeof tg.openTelegramLink === "function"
            ) {
                tg.openTelegramLink(url);
            } else {
                window.open(
                    url,
                    "_blank",
                    "noopener,noreferrer"
                );
            }
        } catch (error) {
            console.error(
                "openBotPayment:",
                error
            );

            showToast(
                "Botga o‘tib bo‘lmadi."
            );
        }
    }

    async function pollPayment() {
        if (!state.paymentId) {
            return;
        }

        if (
            state.pollStartedAt > 0 &&
            Date.now() - state.pollStartedAt >=
                MAX_POLL_TIME
        ) {
            stopPolling();

            setStatus(
                "⌛ To‘lovni tekshirish vaqti tugadi. Oynani yopib, keyin qayta tekshirishingiz mumkin.",
                "timeout"
            );

            return;
        }

        try {
            const data =
                await getPaymentStatus(
                    state.paymentId
                );

            const status =
                String(
                    data?.status || ""
                ).toLowerCase();

            if (status === "approved") {
                stopPolling();

                setStatus(
                    "✅ To‘lov tasdiqlandi.",
                    "approved"
                );

                window.setTimeout(() => {
                    closeModal();

                    const app =
                        window.IQTestApp;

                    if (
                        app &&
                        typeof app.startTest ===
                            "function"
                    ) {
                        app.startTest();
                    } else {
                        showToast(
                            "To‘lov tasdiqlandi. Qayta testni boshlang."
                        );
                    }

                    resetState();
                }, 500);

                return;
            }

            if (status === "rejected") {
                stopPolling();

                setStatus(
                    "❌ To‘lov rad etildi. Qayta to‘lov yuborishingiz mumkin.",
                    "rejected"
                );

                state.busy = false;

                return;
            }

            setStatus(
                "⏳ Chek/admin tasdig‘i kutilmoqda…",
                "pending"
            );

        } catch (error) {
            console.warn(
                "Payment status:",
                error
            );

            if (
                !navigator.onLine
            ) {
                setStatus(
                    "📡 Internet yo‘q. Aloqa tiklanganda tekshirish davom etadi.",
                    "offline"
                );
            } else {
                setStatus(
                    "⏳ To‘lov holati tekshirilmoqda…",
                    "checking"
                );
            }
        }

        state.pollAttempts += 1;

        const delay =
            state.pollAttempts < 10
                ? POLL_INTERVAL
                : 5000;

        state.pollTimer =
            window.setTimeout(
                pollPayment,
                delay
            );
    }

    async function startPayment(
        purpose = "retest"
    ) {
        if (state.busy) {
            return false;
        }

        if (!navigator.onLine) {
            showToast(
                "To‘lov uchun internet kerak."
            );

            return false;
        }

        state.busy = true;
        state.purpose = purpose;
        state.closeRequested = false;

        try {
            setStatus(
                "⏳ To‘lov ma’lumotlari olinmoqda…",
                "loading"
            );

            const payment =
                await createPayment(
                    purpose
                );

            if (
                !payment ||
                !payment.payment_id
            ) {
                throw new Error(
                    "PAYMENT_ID_MISSING"
                );
            }

            state.paymentId =
                payment.payment_id;

            updateAmount(
                payment.amount
            );

            renderCards(
                payment.cards
            );

            if (!openModal()) {
                throw new Error(
                    "PAYMENT_MODAL_NOT_FOUND"
                );
            }

            setStatus(
                "⏳ To‘lov kutilmoqda…",
                "pending"
            );

            state.pollStartedAt =
                Date.now();

            state.pollAttempts = 0;

            clearPollTimer();

            pollPayment();

            return true;

        } catch (error) {
            console.error(
                "startPayment:",
                error
            );

            state.busy = false;

            if (
                error.detail ===
                "NO_PAYMENT_CARD"
            ) {
                setStatus(
                    "❌ Admin hali to‘lov kartasini sozlamagan.",
                    "error"
                );

                showToast(
                    "Admin hali karta qo‘shmagan."
                );

            } else if (
                error.status === 401
            ) {
                setStatus(
                    "❌ Telegram sessiyasi tasdiqlanmadi.",
                    "error"
                );

                showToast(
                    "Telegram Mini App orqali qayta oching."
                );

            } else if (
                error.status === 503
            ) {
                setStatus(
                    "❌ To‘lov xizmati hozircha tayyor emas.",
                    "error"
                );

                showToast(
                    "To‘lov xizmati vaqtincha ishlamayapti."
                );

            } else {
                setStatus(
                    "❌ To‘lov oynasini ochib bo‘lmadi.",
                    "error"
                );

                showToast(
                    "To‘lovni boshlashda xatolik."
                );
            }

            return false;
        }
    }

    function handleClose() {
        if (state.busy) {
            state.closeRequested = true;
        }

        stopPolling();
        closeModal();

        state.busy = false;
        state.paymentId = null;
    }

    function bindEvents() {
        const closeButton =
            getElement(
                "paymentCloseBtn"
            );

        if (closeButton) {
            closeButton.addEventListener(
                "click",
                handleClose
            );
        }

        const botButton =
            getElement(
                "paymentOpenBotBtn"
            );

        if (botButton) {
            botButton.addEventListener(
                "click",
                openBotPayment
            );
        }

        const modal =
            getElement(
                "paymentModal"
            );

        if (modal) {
            modal.addEventListener(
                "click",
                event => {
                    if (
                        event.target === modal
                    ) {
                        handleClose();
                    }
                }
            );
        }

        window.addEventListener(
            "online",
            () => {
                if (
                    state.paymentId &&
                    state.pollStartedAt > 0
                ) {
                    clearPollTimer();

                    state.pollTimer =
                        window.setTimeout(
                            pollPayment,
                            100
                        );
                }
            }
        );

        window.addEventListener(
            "offline",
            () => {
                if (state.paymentId) {
                    setStatus(
                        "📡 Internet uzildi. Aloqa tiklanganda avtomatik tekshiriladi.",
                        "offline"
                    );
                }
            }
        );
    }

    function init() {
        bindEvents();

        window.IQPayment = Object.freeze({
            start: startPayment,
            open: startPayment,
            close: handleClose,
            get paymentId() {
                return state.paymentId;
            },
            get busy() {
                return state.busy;
            }
        });
    }

    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            init,
            { once: true }
        );
    } else {
        init();
    }
})();