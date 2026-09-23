window.Telegram = window.Telegram || {};

const app = {
    tg: null,
    user: null,
    initData: "",
    activeTest: null,
    currentQuestionIndex: 0,
    answers: {},
    questionsData: [],
    receiptFile: null,
    activeBattleId: null,

    init: function() {
        if (window.Telegram && window.Telegram.WebApp) {
            this.tg = window.Telegram.WebApp;
            this.tg.ready();
            this.tg.expand();
            this.initData = this.tg.initData || "";
            if (this.tg.initDataUnsafe && this.tg.initDataUnsafe.user) {
                this.user = this.tg.initDataUnsafe.user;
            }
        }
        this.startLiveCounterLoop();
        this.checkSavedProgress();
        this.fetchProfileStatus();
    },

    showToast: function(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerText = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.remove();
        }, 3500);
    },

    showView: function(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const target = document.getElementById(viewId);
        if (target) {
            target.classList.add('active');
            window.scrollTo(0, 0);
        }
    },

    api: async function(endpoint, method = "GET", payload = null, isFormData = false) {
        const headers = {};
        if (this.initData) {
            headers["X-Telegram-Init-Data"] = this.initData;
        }

        let body = null;
        if (payload) {
            if (isFormData) {
                body = payload;
            } else {
                headers["Content-Type"] = "application/json";
                body = JSON.stringify(payload);
            }
        }

        try {
            const response = await fetch(endpoint, { method, headers, body });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || "Server xatosi ro'y berdi");
            }
            return data;
        } catch (err) {
            this.showToast(err.message, 'error');
            throw err;
        }
    },

    startLiveCounterLoop: function() {
        const updateStats = async () => {
            try {
                const data = await this.api('/api/stats/live', 'GET');
                const el = document.getElementById('live-count-text');
                if (el && data && data.online !== undefined) {
                    el.innerText = data.online;
                }
            } catch (e) {
                // Silent fail for stats
            }
        };
        updateStats();
        setInterval(updateStats, 5000);
    },

    fetchProfileStatus: async function() {
        try {
            const data = await this.api('/api/profile/status', 'GET');
            if (data.full_name) {
                document.getElementById('input-fullname').value = data.full_name || '';
                document.getElementById('select-gender').value = data.gender || '';
                document.getElementById('input-age').value = data.age || '';
                document.getElementById('select-country').value = data.country || "O'zbekiston";
            }
            if (data.has_iq) {
                document.getElementById('badge-eq').innerText = 'Ochiq';
                document.getElementById('badge-eq').className = 'badge badge-unlocked';
                document.getElementById('card-eq').classList.remove('locked');
            }
            if (data.has_eq) {
                document.getElementById('badge-pq').innerText = 'Ochiq';
                document.getElementById('badge-pq').className = 'badge badge-unlocked';
                document.getElementById('card-pq').classList.remove('locked');
            }
            if (data.has_pq) {
                document.getElementById('badge-personal').innerText = 'Ochiq';
                document.getElementById('badge-personal').className = 'badge badge-unlocked';
                document.getElementById('card-personal').classList.remove('locked');
            }
        } catch (e) {}
    },

    startIQFlow: function() {
        const savedName = document.getElementById('input-fullname').value;
        if (!savedName) {
            this.showView('view-profile-setup');
        } else {
            this.showView('view-sample');
        }
    },

    handleProfileSubmit: async function(e) {
        e.preventDefault();
        const payload = {
            full_name: document.getElementById('input-fullname').value.trim(),
            gender: document.getElementById('select-gender').value,
            age: parseInt(document.getElementById('input-age').value, 10),
            country: document.getElementById('select-country').value
        };

        const btn = document.getElementById('btn-save-profile');
        btn.disabled = true;
        try {
            await this.api('/api/profile/save', 'POST', payload);
            this.showToast('Ma'lumotlar saqlandi', 'success');
            this.showView('view-sample');
        } catch (err) {
            // Handled in api
        } finally {
            btn.disabled = false;
        }
    },

    startActualTest: async function(type) {
        this.activeTest = type;
        this.currentQuestionIndex = 0;
        this.answers = {};
        
        try {
            const data = await this.api(`/api/test/questions?type=${type}`, 'GET');
            this.questionsData = data.questions;
            this.showView('view-test');
            this.renderQuestion();
        } catch (err) {}
    },

    renderQuestion: function() {
        const q = this.questionsData[this.currentQuestionIndex];
        const total = this.questionsData.length;
        
        document.getElementById('q-num-text').innerText = `Savol ${this.currentQuestionIndex + 1} / ${total}`;
        document.getElementById('q-diff-tag').innerText = q.difficulty ? q.difficulty.toUpperCase() : 'STANDARD';
        
        const progress = ((this.currentQuestionIndex + 1) / total) * 100;
        document.getElementById('test-progress-fill').style.width = `${progress}%`;

        // SVG Render
        const puzzleContainer = document.getElementById('puzzle-svg-render');
        puzzleContainer.innerHTML = q.svg_content;

        // Options
        const optionsContainer = document.getElementById('options-container');
        optionsContainer.innerHTML = '';
        
        ['A', 'B', 'C', 'D'].forEach(optKey => {
            if (q.options[optKey]) {
                const optCard = document.createElement('div');
                optCard.className = 'option-card';
                optCard.onclick = () => this.selectOption(optKey);
                optCard.innerHTML = `
                    <div style="width:100%; max-width:80px; height:80px;">${q.options[optKey]}</div>
                    <span class="option-label">Variant ${optKey}</span>
                `;
                optionsContainer.appendChild(optCard);
            }
        });
    },

    selectOption: function(key) {
        const q = this.questionsData[this.currentQuestionIndex];
        this.answers[q.id] = key;

        this.saveLocalProgress();

        if (this.currentQuestionIndex + 1 === 6 || this.currentQuestionIndex + 1 === 12) {
            this.showCelebration(this.currentQuestionIndex + 1);
            return;
        }

        this.nextQuestion();
    },

    nextQuestion: function() {
        if (this.currentQuestionIndex + 1 < this.questionsData.length) {
            this.currentQuestionIndex++;
            this.renderQuestion();
        } else {
            this.submitFinalTest();
        }
    },

    showCelebration: function(stage) {
        document.getElementById('celeb-title').innerText = `${stage}-savol yakunlandi!`;
        document.getElementById('celeb-desc').innerText = `Ajoyib temp! Mantiqiy tahlilingiz aniqlik bilan davom etmoqda.`;
        document.getElementById('modal-celebration').classList.add('active');
    },

    closeCelebration: function() {
        document.getElementById('modal-celebration').classList.remove('active');
        this.nextQuestion();
    },

    saveLocalProgress: function() {
        localStorage.setItem('iq_test_progress', JSON.stringify({
            test: this.activeTest,
            index: this.currentQuestionIndex,
            answers: this.answers
        }));
    },

    checkSavedProgress: function() {
        const raw = localStorage.getItem('iq_test_progress');
        if (raw) {
            try {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.answers) {
                    this.answers = parsed.answers;
                }
            } catch (e) {}
        }
    },

    submitFinalTest: async function() {
        this.showView('view-loading');
        localStorage.removeItem('iq_test_progress');

        setTimeout(async () => {
            try {
                const res = await this.api('/api/test/submit', 'POST', {
                    test_type: this.activeTest,
                    answers: this.answers
                });

                if (res.payment_required) {
                    this.renderPaymentScreen(res.price, res.card_details);
                } else {
                    this.renderResultScreen(res.result);
                }
            } catch (err) {
                this.showView('view-home');
            }
        }, 2000);
    },

    renderPaymentScreen: function(price, card) {
        document.getElementById('pay-price-amount').innerText = `${price.toLocaleString()} UZS`;
        if (card) {
            document.getElementById('pay-bank-name').innerText = card.bank || 'Bank Kartasi';
            document.getElementById('pay-card-number').innerText = card.card_number || '0000 0000 0000 0000';
            document.getElementById('pay-card-holder').innerText = card.holder || 'ADMIN';
        }
        this.showView('view-payment');
    },

    copyCardNumber: function() {
        const num = document.getElementById('pay-card-number').innerText;
        navigator.clipboard.writeText(num.replace(/\s+/g, ''));
        this.showToast('Karta raqami nusxalandi', 'success');
    },

    handleReceiptSelected: function(e) {
        const file = e.target.files[0];
        if (file) {
            this.receiptFile = file;
            document.getElementById('upload-label-text').innerText = file.name;
            document.getElementById('btn-submit-payment').disabled = false;
        }
    },

    submitPaymentReceipt: async function() {
        if (!this.receiptFile) return;
        const btn = document.getElementById('btn-submit-payment');
        btn.disabled = true;

        const formData = new FormData();
        formData.append('receipt', this.receiptFile);
        formData.append('test_type', this.activeTest || 'iq');

        try {
            await this.api('/api/payment/upload', 'POST', formData, true);
            this.showToast('Kvitansiya qabul qilindi. Tekshiruvdan so\'ng natija ochiladi.', 'success');
            this.showView('view-home');
        } catch (err) {
            btn.disabled = false;
        }
    },

    renderResultScreen: function(result) {
        document.getElementById('res-score-val').innerText = result.score;
        document.getElementById('res-level-text').innerText = result.level;
        document.getElementById('res-desc-text').innerText = result.description || '';
        this.showView('view-result');
    },

    fetchCertificate: async function() {
        try {
            const data = await this.api('/api/certificate/generate', 'POST', { test_type: 'iq' });
            if (data.status === 'ok') {
                this.showToast('Sertifikat Telegram botingizga yuborildi! 📜', 'success');
            }
        } catch (err) {}
    },

    openRankingView: async function() {
        try {
            const data = await this.api('/api/ranking/list', 'GET');
            const listContainer = document.getElementById('ranking-list-container');
            listContainer.innerHTML = '';
            
            data.rankings.forEach((item, index) => {
                const el = document.createElement('div');
                el.style.cssText = "display:flex; justify-content:space-between; padding:12px; background:var(--bg-card); margin-bottom:8px; border-radius:var(--radius-md); font-size:14px;";
                el.innerHTML = `
                    <span><strong>#${index + 1}</strong> ${item.full_name}</span>
                    <span style="color:var(--accent-purple); font-weight:700;">${item.score} IQ</span>
                `;
                listContainer.appendChild(el);
            });
            this.showView('view-ranking');
        } catch (err) {}
    },

    openBattleMenu: function() {
        this.showView('view-battle-menu');
    },

    createBattle: async function() {
        try {
            const res = await this.api('/api/battle/create', 'POST');
            this.activeBattleId = res.battle_id;
            document.getElementById('room-battle-code').innerText = res.code;
            this.showView('view-battle-room');
        } catch (err) {}
    },

    joinBattle: async function() {
        const code = document.getElementById('battle-code-input').value.trim().toUpperCase();
        if (!code || code.length !== 4) {
            this.showToast('4 xonali kodni kiriting', 'error');
            return;
        }
        try {
            const res = await this.api('/api/battle/join', 'POST', { code });
            this.activeBattleId = res.battle_id;
            document.getElementById('room-battle-code').innerText = code;
            this.showView('view-battle-room');
        } catch (err) {}
    },

    openPersonalProfile: async function() {
        try {
            const res = await this.api('/api/profile/analytics', 'GET');
            const box = document.getElementById('profile-analytics-content');
            box.innerHTML = `
                <div style="background:var(--bg-card); padding:16px; border-radius:var(--radius-lg); margin-bottom:12px;">
                    <h3>IQ Natija: ${res.iq_score || 'N/A'}</h3>
                    <p style="color:var(--text-secondary); font-size:13px; margin-top:4px;">${res.iq_desc || ''}</p>
                </div>
                <div style="background:var(--bg-card); padding:16px; border-radius:var(--radius-lg); margin-bottom:12px;">
                    <h3>EQ Ko'rsatkich: ${res.eq_score || 'N/A'}%</h3>
                    <p style="color:var(--text-secondary); font-size:13px; margin-top:4px;">Emotsional barqarorlik va empatiya darajasi</p>
                </div>
                <div style="background:var(--bg-card); padding:16px; border-radius:var(--radius-lg);">
                    <h3>PQ Ko'rsatkich: ${res.pq_score || 'N/A'}%</h3>
                    <p style="color:var(--text-secondary); font-size:13px; margin-top:4px;">Psixologik va xulq-atvor chidamliligi</p>
                </div>
            `;
            this.showView('view-personal-profile');
        } catch (err) {}
    }
};

document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
