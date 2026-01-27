import { state } from './state.js';

export const charts = {
    renderAll() {
        this.renderThreshold();
        this.renderDrift();
        this.renderDebt();
        this.renderMonthly();
        this.renderPrecision();
        this.renderHistogram();
    },

    renderThreshold() {
        const ctxT = document.getElementById('thresholdChart')?.getContext('2d');
        if (!ctxT) return;

        if (state.charts.threshold) state.charts.threshold.destroy();
        const thresholdPts = state.data.map(r => ({ x: r.succ_z, y: r.boom_z, label: `${r.star}* ${r.catch}` }));
        state.charts.threshold = new Chart(ctxT, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: '성공 Z vs 파괴 Z',
                    data: thresholdPts,
                    backgroundColor: thresholdPts.map(p => (p.x < -2 && p.y < 0) ? '#cf6679' : '#03dac6'),
                    pointRadius: 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: '성공 Z (음수=억제)' },
                        grid: {
                            color: (ctx) => ctx.tick.value === 0 ? 'rgba(255, 255, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)',
                            lineWidth: (ctx) => ctx.tick.value === 0 ? 2 : 1
                        }
                    },
                    y: {
                        title: { display: true, text: '파괴 Z (음수=억제)' },
                        grid: {
                            color: (ctx) => ctx.tick.value === 0 ? 'rgba(255, 255, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)',
                            lineWidth: (ctx) => ctx.tick.value === 0 ? 2 : 1
                        }
                    }
                },
                plugins: { tooltip: { callbacks: { label: ctx => `${ctx.raw.label}: 성공Z=${ctx.raw.x.toFixed(2)}, 파괴Z=${ctx.raw.y.toFixed(2)}` } } }
            }
        });
    },

    renderDrift() {
        const ctxD = document.getElementById('driftChart')?.getContext('2d');
        if (!ctxD) return;

        if (state.charts.drift) state.charts.drift.destroy();
        state.charts.drift = new Chart(ctxD, {
            type: 'line',
            data: {
                labels: state.drift.map(d => d.date),
                datasets: [
                    { label: '누적 성공 Z', data: state.drift.map(d => d.cumulative_succ_z), borderColor: '#bb86fc', yAxisID: 'y', fill: false, tension: 0.3 },
                    { label: '누적 성공 오차 (횟수)', data: state.drift.map(d => d.cumulative_error), borderColor: '#03dac6', yAxisID: 'y1', fill: true, backgroundColor: 'rgba(3, 218, 198, 0.05)', tension: 0.3 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: { title: { display: true, text: '누적 Z (회귀성)' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                    y1: { position: 'right', title: { display: true, text: '누적 오차 (회)' }, grid: { display: false } }
                },
                plugins: {
                    legend: { position: 'bottom' },
                    annotation: {
                        annotations: state.eventDates.filter(d => d.is_event_period).map(d => ({
                            type: 'box',
                            xMin: d.date,
                            xMax: d.date,
                            backgroundColor: 'rgba(187, 134, 252, 0.05)',
                            borderWidth: 0,
                            label: { content: 'EVENT', display: false }
                        }))
                    }
                }
            }
        });
    },

    renderDebt() {
        const ctxDebt = document.getElementById('debtChart')?.getContext('2d');
        if (!ctxDebt) return;

        if (state.charts.debt) state.charts.debt.destroy();
        state.charts.debt = new Chart(ctxDebt, {
            type: 'line',
            data: {
                labels: state.drift.map(d => d.date),
                datasets: [
                    { label: '누적 메소 손실액 (억)', data: state.drift.map(d => d.cumulative_meso / 100), borderColor: '#ffb74d', fill: true, backgroundColor: 'rgba(255, 183, 77, 0.1)', tension: 0.3 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { y: { title: { display: true, text: '메소 (억)' } } },
                plugins: { annotation: { annotations: state.eventDates.filter(d => d.is_event_period).map(d => ({ type: 'box', xMin: d.date, xMax: d.date, backgroundColor: 'rgba(255,183,77,0.05)', borderWidth: 0 })) } }
            }
        });
    },

    renderMonthly() {
        const ctxM = document.getElementById('monthlyChart')?.getContext('2d');
        if (!ctxM) return;

        if (state.charts.monthly) state.charts.monthly.destroy();
        state.charts.monthly = new Chart(ctxM, {
            type: 'bar',
            data: {
                labels: state.monthly.map(d => d.month),
                datasets: [
                    { label: '성공 Z 합계', data: state.monthly.map(d => d.total_succ_z), backgroundColor: '#bb86fc' },
                    { label: '파괴 Z 합계', data: state.monthly.map(d => d.total_boom_z), backgroundColor: '#cf6679' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: {
                        title: { display: true, text: 'Z-Score 합계' },
                        grid: { color: (ctx) => ctx.tick.value === 0 ? 'rgba(255, 255, 255, 0.5)' : 'rgba(255, 255, 255, 0.1)', lineWidth: (ctx) => ctx.tick.value === 0 ? 2 : 1 }
                    }
                }
            }
        });
    },

    renderPrecision() {
        const ctxP = document.getElementById('precisionChart')?.getContext('2d');
        if (!ctxP) return;

        if (state.charts.precision) state.charts.precision.destroy();
        const precisionPts = state.data
            .filter(r => (r.total_n ?? 0) > 0 && (r.succ_var_n ?? 0) > 1)
            .map(r => ({
                x: Math.log10(r.total_n),
                y: r.succ_var_ratio,
                label: `${r.star}* ${r.catch}`,
                k: r.succ_var_n,
                q: r.succ_var_q_under ?? 1
            }));
        state.charts.precision = new Chart(ctxP, {
            type: 'scatter',
            data: {
                datasets: [{
                    data: precisionPts,
                    backgroundColor: precisionPts.map(p => (p.y < 0.7 && p.q < 0.01 && p.k >= 5 && p.x >= 6) ? '#cf6679' : '#03dac6'),
                    pointRadius: 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'log₁₀(N) - 총 표본 크기' } },
                    y: { title: { display: true, text: 'VAR Ratio (성공 Z의 분산)' }, min: 0 }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.raw.label}: N=10^${ctx.raw.x.toFixed(1)}, VAR=${ctx.raw.y.toFixed(2)}, k=${ctx.raw.k}, q=${ctx.raw.q.toExponential(2)}`
                        }
                    }
                }
            }
        });
    },

    renderHistogram() {
        const ctxH = document.getElementById('histChart')?.getContext('2d');
        if (!ctxH) return;

        if (state.charts.hist) state.charts.hist.destroy();
        const pVals = state.data
            .filter(r => (r.succ_var_n ?? 0) >= 5 && (r.total_n ?? 0) >= 1_000_000)
            .map(r => r.succ_var_p_under ?? 1);

        const bins = [
            { label: '<1e-3', min: 0, max: 0.001 },
            { label: '1e-3~1e-2', min: 0.001, max: 0.01 },
            { label: '1e-2~5e-2', min: 0.01, max: 0.05 },
            { label: '5e-2~0.1', min: 0.05, max: 0.1 },
            { label: '0.1~0.2', min: 0.1, max: 0.2 },
            { label: '0.2~0.5', min: 0.2, max: 0.5 },
            { label: '0.5~1', min: 0.5, max: 1.0000001 }
        ];

        const counts = bins.map(b => pVals.filter(p => p >= b.min && p < b.max).length);
        const expected = bins.map(b => pVals.length * (b.max - b.min));
        state.charts.hist = new Chart(ctxH, {
            type: 'bar',
            data: {
                labels: bins.map(b => b.label),
                datasets: [
                    {
                        type: 'bar',
                        label: 'Observed',
                        data: counts,
                        backgroundColor: counts.map((_, i) => i < 2 ? '#cf6679' : '#03dac6')
                    },
                    {
                        type: 'line',
                        label: 'Expected (Uniform)',
                        data: expected,
                        borderColor: '#888',
                        borderDash: [6, 6],
                        pointRadius: 0,
                        tension: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}` } }
                },
                scales: {
                    y: { title: { display: true, text: 'Count' } }
                }
            }
        });
    }
};
