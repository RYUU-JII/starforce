import { state } from './state.js';
import { api } from './api.js';
import { render } from './render.js';

export const ui = {
    splitTimer: null,

    activateTab(btn, tabId) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(tabId + 'Section').classList.add('active');

        if (tabId === 'seasonal') {
            const seasonGrid = document.getElementById('seasonGrid');
            if (seasonGrid && state.seasonContrast) {
                render.seasonalContrast();
            } else if (seasonGrid) {
                // Initialize slider logic only when seasonal tab is first accessed or active
                // Actually this.initSlider handles if state.meta is ready.
                this.initSlider();
            }
        } else {
            // Re-render main charts if needed when switching back
        }
    },

    initSlider() {
        const slider = document.getElementById('splitSlider');
        if (!slider) return;
        if (slider.max > 0 && slider.max != 100) return; // Already initialized

        const dates = state.meta.dates;
        if (!dates || dates.length === 0) return;

        slider.min = 0;
        slider.max = dates.length - 1;
        slider.value = Math.floor(dates.length * 0.7);

        // Simple Formatter
        const fmt = (d) => d.length === 8 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : d;

        document.getElementById('sliderMinDate').textContent = fmt(dates[0]);
        document.getElementById('sliderMaxDate').textContent = fmt(dates[dates.length - 1]);

        const updateLabel = (val) => {
            const date = dates[val];
            document.getElementById('splitDateLabel').textContent = fmt(date);
            return date;
        };

        slider.oninput = (e) => {
            const date = updateLabel(e.target.value);
            this.updateSeasonal(date);
        };

        const initialDate = updateLabel(slider.value);
        this.updateSeasonal(initialDate);
    },

    async updateSeasonal(date) {
        clearTimeout(this.splitTimer);
        this.splitTimer = setTimeout(async () => {
            if (!state.query) return;
            state.seasonContrast = await api.fetchSeasonContrast(state.query, date);
            render.seasonalContrast();
        }, 100);
    }
};
