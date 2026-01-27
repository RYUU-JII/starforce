import { state } from './state.js';

export const render = {
    all() {
        this.summary();
        this.eventAnalysis();
        this.auditCards();
        this.table();
        this.heatmap();
        this.hypothesis();
    },

    seasonalContrast() {
        const sc = state.seasonContrast;
        if (!sc) return;

        const grid = document.getElementById('seasonGrid');
        if (!grid) return;

        const costFactor = sc.cost_factor || 0.4;
        const createCard = (key, data, label) => {
            const isPositive = data.error_count > 0;
            const sign = isPositive ? '+' : '';
            const color = isPositive ? 'var(--success)' : 'var(--danger)';
            const mesoSign = isPositive ? '이득 (Gain)' : '손실 (Loss)';
            const mesoVal = (data.error_count * costFactor).toFixed(1);

            return `
                <div class="season-card ${key}">
                    <span class="season-tag" style="color:#aaa">${label}</span>
                    <div class="season-desc">Start ~ End 구간 성공 오차</div>
                    <div class="season-value" style="color:${color}">${sign}${data.error_count.toLocaleString()}회</div>
                    <div class="season-desc">${isPositive ? '기대보다 더 많이 성공함' : '기대보다 덜 성공함 (억제됨)'}</div>
                    <div class="meso-value" style="color:${color}">💰 약 ${Math.abs(mesoVal)}억 메소 ${mesoSign}</div>
                </div>
            `;
        };

        grid.innerHTML =
            createCard('before', sc.before, sc.before.period) +
            createCard('after', sc.after, sc.after.period);
    },

    eventAnalysis() {
        const dec = state.eventDec;
        if (!dec) return;

        // 1. Global Index
        const dVal = document.getElementById('deceptionIndex');
        if (dVal && dec.insufficient_data) {
            dVal.textContent = 'N/A';
            dVal.style.color = '#888';
            document.getElementById('deceptionDesc').textContent = '데이터 부족 (분석 불가)';
        } else if (dVal) {
            dVal.textContent = dec.deception_index.toFixed(2);
            dVal.style.color = dec.deception_index > 0.5 ? '#cf6679' : '#03dac6';
            document.getElementById('deceptionDesc').textContent = dec.interpretation;
        }

        // 2. Star Groups
        const groupContainer = document.getElementById('starGroupContainer');
        if (groupContainer) {
            const groupHtml = Object.entries(dec.star_groups).map(([name, data]) => {
                if (data.insufficient_data) {
                    return `
                        <div style="margin-bottom:12px; border-bottom:1px solid #333; padding-bottom:8px;">
                            <div style="font-weight:bold; color:#e0e0e0; margin-bottom:4px;">${name}</div>
                            <div style="font-size:0.9em; color:#666;">⚠️ 데이터 부족</div>
                        </div>
                    `;
                }
                const color = data.deception > 1.0 ? '#cf6679' : (data.deception > 0 ? '#ffb74d' : '#03dac6');
                const varColor = data.var_suppression > 1.5 ? '#cf6679' : (data.var_suppression > 1.1 ? '#ffb74d' : '#888');

                return `
                    <div style="margin-bottom:12px; border-bottom:1px solid #333; padding-bottom:8px;">
                        <div style="font-weight:bold; color:#e0e0e0; margin-bottom:4px;">${name}</div>
                        <div style="display:flex; justify-content:space-between; font-size:0.9em;">
                            <span>기망 지수 (성공 억제): <b style="color:${color}">${data.deception > 0 ? '+' : ''}${data.deception}%</b></span>
                            <span>VAR 억제: <b style="color:${varColor}">x ${data.var_suppression.toFixed(2)}</b></span>
                        </div>
                    </div>
                `;
            }).join('');
            groupContainer.innerHTML = groupHtml;
        }

        // 3. Event Ranking
        const rankBody = document.getElementById('eventRankBody');
        if (rankBody) {
            if (!dec.events || dec.events.length === 0) {
                rankBody.innerHTML = '<tr><td colspan="3">분석 가능한 이벤트 없음</td></tr>';
            } else {
                rankBody.innerHTML = dec.events.map(e => {
                    const color = e.deception > 1.0 ? '#cf6679' : (e.deception > 0 ? '#ffb74d' : '#888');
                    return `
                        <tr>
                            <td style="font-size:0.85em; max-width:150px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${e.name}">${e.name}</td>
                            <td style="color:${color}; font-weight:bold;">${e.deception > 0 ? '+' : ''}${e.deception}%</td>
                            <td style="color:${e.var_suppression > 1.2 ? '#cf6679' : '#888'}">x ${e.var_suppression.toFixed(2)}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    },

    summary() {
        const MIN_N = 1_000_000;
        const MIN_K = 5;

        const candidates = state.data.filter(r => (r.total_n ?? 0) >= MIN_N && (r.succ_var_n ?? 0) >= MIN_K);
        const underStrong = candidates.filter(r => r.succ_var_ratio < 0.7 && (r.succ_var_q_under ?? 1) < 0.01);
        const underAny = candidates.filter(r => r.succ_var_ratio < 0.85 && (r.succ_var_q_under ?? 1) < 0.05);

        // "Integrity" here means consistency with iid binomial dispersion (Var(Z)≈1).
        const integrityPct = candidates.length > 0 ? Math.round(100 * (1 - underAny.length / candidates.length)) : 0;

        document.getElementById('integrityScore').textContent = integrityPct + '%';
        const bar = document.getElementById('integrityBar');
        bar.style.width = integrityPct + '%';

        let label, color;
        if (integrityPct < 25) { label = `🔴 과소산포 다발 (${underAny.length}/${candidates.length})`; color = '#cf6679'; }
        else if (integrityPct < 60) { label = `🟠 과소산포 일부 (${underAny.length}/${candidates.length})`; color = '#ffb74d'; }
        else { label = `🟢 독립 시행 가정과 대체로 일치 (${underAny.length}/${candidates.length})`; color = '#03dac6'; }
        document.getElementById('integrityLabel').textContent = label;
        bar.style.background = color;

        const guns = [...candidates]
            .sort((a, b) => (a.succ_var_q_under ?? 1) - (b.succ_var_q_under ?? 1))
            .slice(0, 3);
        const gunList = document.getElementById('smokingGunList');
        if (gunList) {
            gunList.innerHTML = guns.map(r => `
                <div class="gun-item">
                    <div><span class="star">${r.star}성 ${r.catch}</span> <span class="stats">| N=${r.total_n.toLocaleString()} | k=${r.succ_var_n} | VAR=${r.succ_var_ratio.toFixed(2)} | q=${(r.succ_var_q_under ?? 1).toExponential(1)}</span></div>
                    <span class="verdict">${
                        (r.succ_var_q_under ?? 1) < 0.01 && r.succ_var_ratio < 0.7 ? '🧊 과소산포(유의)' :
                        (r.succ_var_q_under ?? 1) < 0.05 && r.succ_var_ratio < 0.85 ? '🧊 VAR 낮음(유의)' :
                        r.succ_var_ratio < 0.85 ? '🧊 VAR 낮음(비유의)' :
                        '⚠️ 주의'
                    }</span>
                </div>
            `).join('') || '<div class="gun-item">해당 구간 없음</div>';
        }
    },

    auditCards() {
        const pMetric = document.getElementById('precisionMetric');
        if (pMetric) {
            const precisionCount = state.data.filter(r => r.precision === 'CRITICAL').length;
            pMetric.innerHTML = `<span style="color:${precisionCount > 0 ? '#cf6679' : '#03dac6'}">${precisionCount}개</span>`;
        }

        const tMetric = document.getElementById('thresholdMetric');
        if (tMetric) {
            const biasedDown = state.data.filter(r => (r.succ_bias_q ?? 1) < 0.05 && (r.succ_delta_pp ?? 0) <= -0.05).length;
            tMetric.innerHTML = `<span style="color:${biasedDown > 0 ? '#ffb74d' : '#03dac6'}">${biasedDown}개</span>`;
        }

        const zMetric = document.getElementById('zerosumMetric');
        if (zMetric) {
            const lastDrift = state.drift.length > 0 ? state.drift[state.drift.length - 1] : null;
            const zerosumScore = lastDrift ? Math.abs(lastDrift.cumulative_succ_z).toFixed(1) : '--';
            zMetric.innerHTML = `<span style="color:${parseFloat(zerosumScore) < 5 ? '#cf6679' : '#03dac6'}">Σ=${zerosumScore}</span>`;
        }
    },

    table() {
        const tbody = document.querySelector('#statsTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        document.querySelectorAll('#statsTable th').forEach(th => {
            th.classList.remove('sorted-asc', 'sorted-desc');
            if (th.dataset.key === state.sort.key) th.classList.add(state.sort.asc ? 'sorted-asc' : 'sorted-desc');
        });

        const sorted = [...state.data].sort((a, b) => {
            let va = a[state.sort.key], vb = b[state.sort.key];
            if (typeof va === 'string') return state.sort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
            return state.sort.asc ? va - vb : vb - va;
        });

        sorted.forEach(row => {
            const tr = document.createElement('tr');
            if (row.precision === 'CRITICAL') tr.classList.add('row-critical');
            else if (row.precision === 'HIGH') tr.classList.add('row-managed');

            const tooltip = [
                `Δp=${(row.succ_delta_pp ?? 0).toFixed(3)}pp ±${(row.succ_delta_pp_ci95 ?? 0).toFixed(3)}pp (95%)`,
                `bias q=${(row.succ_bias_q ?? 1).toExponential(2)}`,
                `VAR=${row.succ_var_ratio.toFixed(2)} (k=${row.succ_var_n}, q_under=${(row.succ_var_q_under ?? 1).toExponential(2)})`
            ].join('\n');

            tr.innerHTML = `
                <td>${row.star}</td>
                <td><span class="badge ${row.catch === 'ON' ? 'badge-on' : 'badge-off'}">${row.catch}</span></td>
                <td>${row.total_n.toLocaleString()}</td>
                <td class="tooltip" data-tip="${tooltip}">${row.succ_z.toFixed(2)}</td>
                <td>${(row.succ_delta_pp ?? 0).toFixed(3)}</td>
                <td style="color:${row.succ_var_ratio < 0.5 ? '#cf6679' : (row.succ_var_ratio > 1.5 ? '#ffb74d' : '#03dac6')}">${row.succ_var_ratio.toFixed(2)}</td>
                <td>${row.succ_var_n}</td>
                <td>${(row.succ_var_q_under ?? 1).toExponential(2)}</td>
                <td><span class="badge ${row.precision === 'CRITICAL' ? 'badge-danger' : row.precision === 'HIGH' ? 'badge-warning' : ''}">${row.precision}</span></td>
                <td>${row.verdict ?? ''}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    heatmap() {
        const heatmapArea = document.getElementById('heatmapArea');
        if (!heatmapArea) return;

        const { data, dates, stars } = state.heatmap;
        if (!dates || !stars || dates.length === 0) {
            heatmapArea.innerHTML = '히트맵 데이터 없음';
            return;
        }

        const cellMap = new Map();
        data.forEach(d => cellMap.set(`${d.star}|${d.date}`, d));

        const eventMap = {};
        if (state.eventDates) {
            state.eventDates.forEach(e => {
                eventMap[e.date] = e.events.join(', ');
            });
        }

        const relevantStars = stars.filter(s => s >= 12 && s <= 25);

        let html = '<table class="heatmap-table">';
        html += '<tr><th style="padding:5px;"></th>';
        dates.forEach(d => html += `<th class="heatmap-header" title="${eventMap[d] || ''}">${d.slice(4, 6)}/${d.slice(6, 8)}</th>`);
        html += '</tr>';

        relevantStars.forEach(star => {
            html += `<tr><td class="heatmap-label">${star}★</td>`;
            dates.forEach(date => {
                const cell = cellMap.get(`${star}|${date}`);
                const eventName = eventMap[date] || '이벤트 정보 없음';

                if (cell) {
                    const z = cell.succ_z;
                    const absZ = Math.abs(z);
                    let color;
                    if (absZ < 1.0) color = `rgba(3,218,198,${0.1 + (1 - absZ) * 0.3})`;
                    else if (absZ < 2.0) color = `rgba(255,183,77,${(absZ - 1.0) * 0.5 + 0.2})`;
                    else color = `rgba(207,102,121,${Math.min(0.9, (absZ - 2.0) * 0.2 + 0.5)})`;

                    html += `<td><div class="heatmap-cell" style="background:${color};" 
                        title="[${date}] ${eventName}\n${star}성: Z=${z.toFixed(2)} (N=${cell.total_n.toLocaleString()})">${z.toFixed(1)}</div></td>`;
                } else {
                    html += `<td><div class="heatmap-cell" style="background:#222;" title="[${date}] ${eventName}\n데이터 없음">-</div></td>`;
                }
            });
            html += '</tr>';
        });
        html += '</table>';
        heatmapArea.innerHTML = html;
    },

    hypothesis() {
        const result = document.getElementById('hypothesisResult');
        if (!result) return;

        const MIN_N = 1_000_000;
        const MIN_K = 5;
        const alpha = 0.01;

        const sample = state.data.filter(r => (r.total_n ?? 0) >= MIN_N && (r.succ_var_n ?? 0) >= MIN_K);
        const flagged = sample.filter(r => (r.succ_var_p_under ?? 1) < alpha && r.succ_var_ratio < 0.7);

        const binomTail = (k, n, p) => {
            if (k <= 0) return 1;
            // P(X >= k) for Binomial(n, p) computed via cumulative sum (n is small here).
            let prob = 0;
            for (let i = k; i <= n; i++) {
                // Compute nCi * p^i * (1-p)^(n-i) using log for stability
                let logC = 0;
                for (let j = 1; j <= i; j++) logC += Math.log((n - (i - j)) / j);
                prob += Math.exp(logC + i * Math.log(p) + (n - i) * Math.log(1 - p));
            }
            return Math.min(1, prob);
        };

        const pTail = binomTail(flagged.length, sample.length, alpha);

        const detail = `(표본 ${sample.length}개 중 ${flagged.length}개가 p_under<${alpha} & VAR<0.7)`;
        let verdict;
        if (sample.length === 0) {
            verdict = `<span style="color:#888">필터 조건에서 충분한 표본(N≥${MIN_N}, k≥${MIN_K})이 없습니다.</span>`;
        } else if (pTail < 1e-6) {
            verdict = `<span style="color:#cf6679">🚨 <b>강한 과소산포 증거</b> ${detail} / Binom-tail p=${pTail.toExponential(2)}. 독립 시행(Var(Z)≈1) 가정과 불일치 가능성이 큽니다.</span>`;
        } else if (pTail < 1e-3) {
            verdict = `<span style="color:#ffb74d">⚠️ <b>유의미한 과소산포</b> ${detail} / Binom-tail p=${pTail.toExponential(2)}.</span>`;
        } else {
            verdict = `<span style="color:#03dac6">✅ <b>뚜렷한 과소산포는 관측되지 않음</b> ${detail} / Binom-tail p=${pTail.toExponential(2)}.</span>`;
        }

        result.innerHTML = verdict;
    }
};
