
import { autoCap, formatMeso } from './utils.js';



export function updateDisplayRangeUI(displayRange) {
    [0.01, 0.1, 1, 0].forEach(r => {
        const btn = document.getElementById('range-' + r);
        if (!btn) return;
        if (r === displayRange) {
            btn.classList.remove('bg-gray-900', 'text-gray-500');
            btn.classList.add('bg-blue-600', 'text-white');
        } else {
            btn.classList.add('bg-gray-900', 'text-gray-500');
            btn.classList.remove('bg-blue-600', 'text-white');
        }
    });
}

export function buildBoxOptions() {
    const deckEl = document.getElementById('deck-size');
    const boxEl = document.getElementById('box-size');
    const hintEl = document.getElementById('box-hint');
    if (!deckEl || !boxEl) return;

    const deckSize = parseInt(deckEl.value || '0');
    const minBox = Math.max(100, Math.floor(deckSize / 10));
    if (hintEl) hintEl.textContent = `Min box size: ${minBox} (max(100, deck/10))`;

    const current = boxEl.value || '0';
    boxEl.innerHTML = '';

    const offOpt = document.createElement('option');
    offOpt.value = '0'; offOpt.textContent = 'Off (no boxes)';
    boxEl.appendChild(offOpt);

    const seen = new Set();
    for (let n = 1; n <= 10; n++) {
        let size = minBox * n;
        if (seen.has(size)) continue;
        seen.add(size);
        const opt = document.createElement('option');
        opt.value = String(size); opt.textContent = `Min ×${n} = ${size}`;
        boxEl.appendChild(opt);
    }
    boxEl.value = current;
    // Simplified logic: preserve value if exists, else 0 (unless we strictly want the old behavior)
}

export function renderAuditTable(data, theory) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    for (let lv = 12; lv <= 21; lv++) {
        const slv = lv.toString();
        const t = theory[slv];
        const fair = data.fair.level_stats[slv] || { try: 0, success_rate: 0, fail_rate: 0, boom_rate: 0 };
        const rigged = data.rigged.level_stats[slv] || { try: 0, success_rate: 0, fail_rate: 0, boom_rate: 0 };

        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-700";
        tr.innerHTML = `
            <td class="p-3 border-r border-gray-700 font-bold bg-gray-800">${lv}★</td>
            <td class="p-3 border-r border-gray-700 text-center font-mono text-yellow-500">
                S:${(t[0] * 100).toFixed(1)}% / F:${(t[1] * 100).toFixed(1)}% / B:${(t[2] * 100).toFixed(1)}%
            </td>
            <td class="p-3 border-r border-gray-700 text-center font-mono text-blue-300">
                S:${fair.success_rate.toFixed(1)}% / F:${fair.fail_rate.toFixed(1)}% / B:${fair.boom_rate.toFixed(1)}%
            </td>
            <td class="p-3 text-center font-mono text-red-300">
                S:${rigged.success_rate.toFixed(1)}% / F:${rigged.fail_rate.toFixed(1)}% / B:${rigged.boom_rate.toFixed(1)}%
            </td>
        `;
        tbody.appendChild(tr);
    }
}

export function renderStats(data) {
    const set = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
    set('fair-s-var', data.fair.s_var.toFixed(1));
    set('fair-f-var', data.fair.f_var.toFixed(1));
    set('fair-cost', formatMeso(data.fair.avg_cost));

    set('rigged-s-var', data.rigged.s_var.toFixed(1));
    set('rigged-f-var', data.rigged.f_var.toFixed(1));
    set('rigged-cost', formatMeso(data.rigged.avg_cost));

    set('sim-run-count', data.simulation_count);
    set('sim-time', data.execution_time.toFixed(2) + 's');
    if (data.deck_stats) set('sim-wraps', data.deck_stats.rigged_wraps ?? '-');
}

export function renderStrategyBox(data) {
    const box = document.getElementById('strategy-box');
    if (!box) return;

    const fair = data.fair;
    const rigged = data.rigged;

    let text = `[ SIMULATION STRATEGY SNAPSHOT ]\n`;
    text += `Mode: ${data.config?.markov_mode ? 'Markov' : (data.config?.dual_mode ? 'Dual Deck' : 'Rigged Deck')}\n`;
    text += `Fixed Mode: ${data.config?.fixed_length_mode ? 'YES' : 'NO'}\n`;
    text += `Calibration: ${data.config?.auto_calibrate ? 'AUTO' : 'OFF'}\n`;
    text += `------------------------------------------\n`;
    text += `Statistic     | Fair World | Rigged World\n`;
    text += `------------------------------------------\n`;
    text += `Avg Cost      | ${formatMeso(fair.avg_cost).padStart(10)} | ${formatMeso(rigged.avg_cost).padStart(12)}\n`;
    text += `Cost Variance | ${(fair.cost_var / 1e18).toFixed(2).padStart(10)}e18 | ${(rigged.cost_var / 1e18).toFixed(2).padStart(12)}e18\n`;
    text += `Max Fail Strk | ${String(fair.max_f).padStart(10)} | ${String(rigged.max_f).padStart(12)}\n`;
    text += `Max Succ Strk | ${String(fair.max_s).padStart(10)} | ${String(rigged.max_s).padStart(12)}\n`;
    text += `------------------------------------------\n`;

    // Level Tries
    text += `[ Avg Tries / Level ]\n`;
    text += `Lv | Fair | Rigged\n`;
    for (let i = 15; i <= 21; i++) {
        const fTries = fair.level_avg_tries?.[String(i)]?.toFixed(1) || '-';
        const rTries = rigged.level_avg_tries?.[String(i)]?.toFixed(1) || '-';
        text += `${i} | ${fTries.padStart(4)} | ${rTries.padStart(6)}\n`;
    }
    text += `------------------------------------------\n`;
    text += `Execution: ${data.execution_time.toFixed(3)}s (${data.simulation_count} runs)`;

    box.textContent = text;
}
