import { state } from './state.js';
import { api } from './api.js';
import { render } from './render.js';
import { charts } from './charts.js';

function bhAdjust(pValues) {
    const m = pValues.length;
    const indexed = pValues
        .map((p, i) => ({ p: Number.isFinite(p) ? p : 1, i }))
        .sort((a, b) => a.p - b.p);

    const q = new Array(m).fill(1);
    let prev = 1;
    for (let j = m - 1; j >= 0; j--) {
        const rank = j + 1;
        const val = Math.min(1, (indexed[j].p * m) / rank);
        prev = Math.min(prev, val);
        q[indexed[j].i] = prev;
    }
    return q;
}

export const filters = {
    async init() {
        state.meta = await api.fetchMeta();

        const container = document.getElementById('eventCheckboxes');
        if (container) {
            state.meta.events.forEach(e => {
                const lbl = document.createElement('label');
                lbl.innerHTML = `<input type="checkbox" value="${e}" checked> ${e}`;
                container.appendChild(lbl);
            });
        }

        document.querySelectorAll('#statsTable th[data-key]').forEach(th => {
            th.addEventListener('click', () => {
                const key = th.dataset.key;
                state.sort = { key, asc: state.sort.key === key ? !state.sort.asc : true };
                render.table();
            });
        });

        await this.apply();
    },

    async apply() {
        const checkboxes = document.querySelectorAll('#eventCheckboxes input:checked');
        const selectedEvents = Array.from(checkboxes).map(cb => cb.value);
        const starMin = parseInt(document.getElementById('starMin').value) || 0;
        const starMax = parseInt(document.getElementById('starMax').value) || 29;
        const stars = []; for (let i = starMin; i <= starMax; i++) stars.push(i);

        const payload = {
            events: selectedEvents,
            stars: stars,
            catch_ops: document.getElementById('catchFilter').value ? [document.getElementById('catchFilter').value] : [],
            min_samples: parseInt(document.getElementById('minSamples').value)
        };
        state.query = payload;

        let bundle;
        try {
            bundle = await api.fetchBundle(payload);
        } catch (e) {
            console.error(e);
            alert('Audit API 호출 실패. 서버 로그를 확인하세요.');
            return;
        }

        state.drift = bundle.drift;
        state.heatmap = bundle.heatmap;
        state.monthly = bundle.monthly;
        state.eventDec = bundle.eventDec;
        state.eventDates = bundle.eventDates;
        state.seasonContrast = bundle.seasonContrast;

        const raw = bundle.query?.results ?? [];
        const biasQ = bhAdjust(raw.map(r => r.succ_p_val));
        const underQ = bhAdjust(raw.map(r => r.succ_var_p_under));
        const overQ = bhAdjust(raw.map(r => r.succ_var_p_over));

        const MIN_N = 1_000_000;
        const MIN_K = 5;

        state.data = raw.map((r, idx) => {
            const absZ = Math.abs(r.succ_z);
            const deltaPP = (r.succ_delta_p ?? 0) * 100;
            const deltaPPci = (r.succ_delta_p_ci95 ?? 0) * 100;

            const qBias = biasQ[idx];
            const qUnder = underQ[idx];
            const qOver = overQ[idx];

            const hasStrongK = (r.succ_var_n ?? 0) >= MIN_K;
            const hasStrongN = (r.total_n ?? 0) >= MIN_N;

            const strongUnder = hasStrongN && hasStrongK && r.succ_var_ratio < 0.7 && qUnder < 0.01;
            const mildUnder = hasStrongN && hasStrongK && r.succ_var_ratio < 0.85 && qUnder < 0.05;
            const overDisp = hasStrongN && hasStrongK && r.succ_var_ratio > 1.5 && qOver < 0.05;

            const biased = hasStrongN && qBias < 0.05 && Math.abs(deltaPP) >= 0.05;
            const biasDir = deltaPP < 0 ? 'DOWN' : 'UP';

            let precision = 'NORMAL';
            if (strongUnder) precision = 'CRITICAL';
            else if (mildUnder) precision = 'HIGH';

            let verdict = '✅ 독립 시행과 일치';
            if (strongUnder) verdict = '🧊 과소산포(강함)';
            else if (mildUnder) verdict = '🧊 과소산포';
            else if (overDisp) verdict = '🌪️ 과대산포';
            else if (biased) verdict = biasDir === 'DOWN' ? '⬇️ 성공 억제' : '⬆️ 성공 과다';

            return {
                ...r,
                abs_succ_z: absZ,
                succ_bias_q: qBias,
                succ_var_q_under: qUnder,
                succ_var_q_over: qOver,
                succ_delta_pp: deltaPP,
                succ_delta_pp_ci95: deltaPPci,
                precision,
                verdict
            };
        });

        render.all();
        charts.renderAll();
    }
};
