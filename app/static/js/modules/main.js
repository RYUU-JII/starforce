
import { fetchCompareSimulation } from './api.js';
import { ChartManager } from './charts.js';
import { autoCap } from './utils.js';
import { updateDisplayRangeUI, renderAuditTable, renderStats, buildBoxOptions, renderStrategyBox } from './ui.js';

const chartManager = new ChartManager();

// --- Input Helpers ---
const el = (id) => document.getElementById(id);
const val = (id) => el(id)?.value;
const num = (id, fallback) => { const v = parseFloat(val(id)); return Number.isFinite(v) ? v : fallback; };
const numInt = (id, fallback) => { const v = parseInt(val(id)); return Number.isFinite(v) ? v : fallback; };
const isChecked = (id) => el(id)?.checked || false;

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    updateModeUI();
    updateDisplayRangeUI(chartManager.displayRange);

    // Bind Tab Switching
    ['fail', 'success', 'meso'].forEach(m => {
        el('tab-' + m)?.addEventListener('click', () => {
            const activeView = chartManager.setChartMode(m);
            updateViewButtons(activeView);
            updateTabButtons(m);
            updateSmoothUI();
            updateTrimUI();
            chartManager.updateComparisonChart();
        });
    });

    ['hist', 'tail'].forEach(v => {
        el('view-' + v)?.addEventListener('click', () => {
            const activeView = chartManager.setChartView(v);
            updateViewButtons(activeView);
            updateSmoothUI();
            updateTrimUI();
            chartManager.updateComparisonChart();
        });
    });

    // Chart Controls
    el('btn-smooth')?.addEventListener('click', () => {
        chartManager.toggleSmooth();
        updateSmoothUI();
        chartManager.updateComparisonChart();
    });
    el('btn-log-y')?.addEventListener('click', () => {
        const isActive = chartManager.toggleLogY();
        toggleBtnStyle('btn-log-y', isActive, "Log Y: ON", "Log Y: OFF");
        chartManager.updateComparisonChart();
    });
    el('btn-log-x')?.addEventListener('click', () => {
        const isActive = chartManager.toggleLogX();
        toggleBtnStyle('btn-log-x', isActive, "Log X (Cost): ON", "Log X (Cost): OFF");
        chartManager.updateComparisonChart();
    });

    // Range Buttons
    [0.01, 0.1, 1, 0].forEach(r => {
        el('range-' + r)?.addEventListener('click', () => {
            chartManager.setDisplayRange(r);
            updateDisplayRangeUI(r);
            chartManager.updateComparisonChart();
        });
    });

    // Core Interaction
    el('sim-mode')?.addEventListener('change', updateModeUI);

    el('share-scope')?.addEventListener('change', function () {
        // Placeholder for scope change logic if needed
    });

    // Deck Inspection
    el('deck-inspect-star')?.addEventListener('change', (e) => {
        chartManager.setDeckInspectStar(parseInt(e.target.value));
        chartManager.updateDeckInspectChart();
    });
    el('chart-max-x')?.addEventListener('change', (e) => {
        chartManager.setDisplayMaxX(parseInt(e.target.value));
        chartManager.updateComparisonChart();
        chartManager.updateDeckInspectChart();
    });

    ['s', 'f'].forEach(mode => {
        el('btn-inspect-' + mode)?.addEventListener('click', () => {
            chartManager.setDeckInspectMode(mode);
            updateInspectButtons(mode);
            chartManager.updateDeckInspectChart();
        });
    });

    // Dual Presets
    el('dual-preset-normal')?.addEventListener('click', () => {
        applyDualPreset(0.5, 2.0);
    });
    el('dual-preset-whale')?.addEventListener('click', () => {
        applyDualPreset(0.9, 8.0); // 90% Nice, 10% Mean (but very mean)
    });
    el('dual-preset-extreme')?.addEventListener('click', () => {
        applyDualPreset(0.5, 5.0); // 50/50 split, but B is very mean
    });

    // Run Button
    el('run-btn')?.addEventListener('click', runSimulation);

    // Deck Inspector Toggle
    el('toggle-deck-inspect')?.addEventListener('click', () => {
        el('deck-inspect-details')?.toggleAttribute('open');
    });
});

// --- UI Updates ---

function updateModeUI() {
    const mode = val('sim-mode');
    const desc = el('mode-desc');

    // Hide all first
    ['params-standard', 'params-deck', 'params-deck-mode', 'params-anti-cluster', 'params-dual', 'params-markov'].forEach(id => {
        el(id)?.classList.add('hidden');
    });

    if (mode === 'standard') {
        el('params-standard')?.classList.remove('hidden');
        if (desc) desc.textContent = "Fair Simulation. Every outcome is purely random (IID).";
    } else if (mode === 'rigged_deck') {
        el('params-deck')?.classList.remove('hidden');
        el('params-deck-mode')?.classList.remove('hidden');
        if (desc) desc.textContent = "Cluster Deck. Pre-shuffled deck with controlled streakiness.";
    } else if (mode === 'rigged_dual') {
        el('params-deck')?.classList.remove('hidden');
        el('params-deck-mode')?.classList.remove('hidden');
        el('params-anti-cluster')?.classList.remove('hidden');
        el('params-dual')?.classList.remove('hidden');
        if (desc) desc.textContent = "Dual Deck. Partition users into 'Nice' (A) and 'Mean' (B) decks.";
    } else if (mode === 'markov') {
        el('params-markov')?.classList.remove('hidden');
        if (desc) desc.textContent = "Markov Chain. Transition probabilities depend on previous outcome.";
    }
}

function updateTabButtons(activeMode) {
    ['fail', 'success', 'meso'].forEach(tm => {
        const btn = el('tab-' + tm);
        if (tm === activeMode) {
            btn.classList.remove('bg-gray-900', 'text-gray-500');
            btn.classList.add('bg-gray-700', 'text-gray-300');
        } else {
            btn.classList.add('bg-gray-900', 'text-gray-500');
            btn.classList.remove('bg-gray-700', 'text-gray-300');
        }
    });
}

function updateViewButtons(activeView) {
    ['hist', 'tail'].forEach(v => {
        const btn = el('view-' + v);
        if (v === activeView) {
            btn.classList.remove('bg-gray-900', 'text-gray-500');
            btn.classList.add('bg-gray-700', 'text-gray-300');
        } else {
            btn.classList.add('bg-gray-900', 'text-gray-500');
            btn.classList.remove('bg-gray-700', 'text-gray-300');
        }
    });
}

function updateInspectButtons(mode) {
    const btnS = el('btn-inspect-s');
    const btnF = el('btn-inspect-f');
    if (mode === 's') {
        btnS.classList.add('bg-blue-600', 'text-white'); btnS.classList.remove('text-gray-400', 'hover:bg-gray-700');
        btnF.classList.remove('bg-blue-600', 'text-white'); btnF.classList.add('text-gray-400', 'hover:bg-gray-700');
    } else {
        btnF.classList.add('bg-blue-600', 'text-white'); btnF.classList.remove('text-gray-400', 'hover:bg-gray-700');
        btnS.classList.remove('bg-blue-600', 'text-white'); btnS.classList.add('text-gray-400', 'hover:bg-gray-700');
    }
}

function toggleBtnStyle(id, isActive, textOn, textOff) {
    const btn = el(id);
    if (!btn) return;
    if (isActive) {
        btn.textContent = textOn;
        btn.classList.remove('bg-gray-900', 'text-gray-500');
        btn.classList.add('bg-blue-600', 'text-white');
    } else {
        btn.textContent = textOff;
        btn.classList.add('bg-gray-900', 'text-gray-500');
        btn.classList.remove('bg-blue-600', 'text-white');
    }
}

function applyDualPreset(bias, mult) {
    const biasEl = el('dual-bias');
    const multEl = el('corr-length-b-unified');
    if (biasEl) {
        biasEl.value = bias;
        el('bias-val').innerText = `${Math.round(bias * 100)}% Mean`;
    }
    if (multEl) {
        multEl.value = mult;
        el('val-corr-b-unified').innerText = mult;
    }
}

function updateSmoothUI() {
    const btn = el('btn-smooth');
    if (!btn) return;
    if (chartManager.chartView !== 'hist') {
        btn.textContent = "Smooth (Gaussian): OFF";
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        btn.classList.remove('bg-gray-700', 'text-gray-300');
        btn.classList.add('bg-gray-900', 'text-gray-500');
    } else {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        if (chartManager.useGaussian) {
            btn.textContent = "Smooth (Gaussian): ON";
            btn.classList.add('bg-gray-700', 'text-gray-300');
            btn.classList.remove('bg-gray-900', 'text-gray-500');
        } else {
            btn.textContent = "Smooth (Gaussian): OFF";
            btn.classList.add('bg-gray-900', 'text-gray-500');
            btn.classList.remove('bg-gray-700', 'text-gray-300');
        }
    }
}

function updateTrimUI() {
    const buttons = [0.01, 0.1, 1, 0].map(r => el('range-' + r)).filter(Boolean);
    if (chartManager.chartView !== 'hist') {
        buttons.forEach(btn => { btn.disabled = true; btn.classList.add('opacity-50', 'cursor-not-allowed'); });
    } else {
        buttons.forEach(btn => { btn.disabled = false; btn.classList.remove('opacity-50', 'cursor-not-allowed'); });
    }
}

async function runSimulation() {
    const btn = el('run-btn');
    const loading = el('deck-loading');
    const mode = val('sim-mode');

    btn.disabled = true;
    btn.innerHTML = `Running...`;
    btn.classList.add('opacity-50');
    if (loading) loading.classList.remove('hidden');

    try {
        const mode = val('sim-mode');

        // Base payload with Global Setup params
        const payload = {
            users: numInt('user-count', 2000),
            runs_per_user: numInt('runs-per-user', 1),
            share_scope: val('share-scope'),
            auto_calibrate: isChecked('auto-calibrate'),

            // Global Mode Flags (Defaults)
            dual_mode: false,
            markov_mode: false,
            sticky_rng: false,
            start_mode: 'random'
        };

        if (mode === 'standard') {
            // Standard - Pure IID
            payload.start_mode = 'random';
            payload.fixed_length_mode = true; // irrelevant for IID but set for consistency
            payload.corr_length_s = 1.0;
            payload.corr_length_f = 1.0;
            payload.corr_length_b = 1.0;
        } else if (mode === 'rigged_deck') {
            // Cluster Deck
            payload.start_mode = 'streak_a';
            payload.fixed_length_mode = document.querySelector('input[name="deck-len-mode"]:checked')?.value === 'fixed';
            const len = num('corr-length-a', 1.0);
            payload.corr_length_s = len;
            payload.corr_length_f = len;
            payload.corr_length_b = len;
            payload.anti_cluster_mode = false; // Strictly isolated to Dual Deck A
        } else if (mode === 'rigged_dual') {
            // Dual Deck
            payload.start_mode = 'streak_a';
            payload.dual_mode = true;
            payload.fixed_length_mode = document.querySelector('input[name="deck-len-mode"]:checked')?.value === 'fixed';

            // Deck A Mapping
            const lenA = num('corr-length-a', 1.0);
            payload.corr_length_s = lenA;
            payload.corr_length_f = lenA;
            payload.corr_length_b = lenA;
            payload.anti_cluster_mode = isChecked('anti-cluster');

            // Deck B Mapping
            payload.dual_bias = 1.0 - num('dual-bias', 0.5);
            const lenB = num('corr-length-b-unified', 5.0);
            payload.corr_length_s_b = lenB;
            payload.corr_length_f_b = lenB;
            payload.corr_length_b_b = lenB;
        } else if (mode === 'markov') {
            // Markov Chain
            payload.markov_mode = true;
            payload.markov_rho = num('markov-rho', 0.0);
        }

        const data = await fetchCompareSimulation(payload);
        chartManager.setData(data);
        chartManager.setFixedLengthMode(payload.fixed_length_mode);
        renderStats(data);
        renderStrategyBox(data);
        renderAuditTable(data, data.theory);
        chartManager.updateComparisonChart();
        chartManager.updateDeckInspectChart();

    } catch (e) {
        alert("Error: " + e.message);
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "RUN AUDIT";
        btn.classList.remove('opacity-50');
        if (loading) loading.classList.add('hidden');
    }
}
