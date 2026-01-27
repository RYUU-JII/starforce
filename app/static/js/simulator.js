document.getElementById('toggle-deck-mode')?.addEventListener('change', function () {
    const label = document.getElementById('mode-label');
    if (this.checked) {
        label.textContent = "Independent";
        label.classList.add('text-red-400');
        label.classList.remove('text-gray-400');
    } else {
        label.textContent = "Shared";
        label.classList.remove('text-red-400');
        label.classList.add('text-gray-400');
    }
});

let cmpChart = null;
let currentData = null;
let chartMode = 'fail'; // fail, success, meso
let useBellCurve = false;
let useLogScale = false;

document.getElementById('intensity-slider')?.addEventListener('input', (e) => {
    document.getElementById('intensity-val').textContent = e.target.value;
});

async function runCompare() {
    const btn = document.getElementById('run-btn');
    const total = parseInt(document.getElementById('sim-count').value);
    const intensity = parseInt(document.getElementById('intensity-slider').value);
    const isIndependent = document.getElementById('toggle-deck-mode').checked;

    btn.disabled = true;
    btn.innerHTML = `Running...`;
    btn.classList.add('opacity-50');

    try {
        const res = await fetch('/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                total_tries: total,
                block_intensity: intensity,
                independent_deck: isIndependent
            })
        });
        const data = await res.json();
        currentData = data;
        renderData(data);
    } catch (e) {
        alert("Error: " + e);
        console.error(e);
    }

    btn.disabled = false;
    btn.innerHTML = "RUN AUDIT";
    btn.classList.remove('opacity-50');
}

function formatMeso(num) {
    if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
    if (num >= 10000) return (num / 10000).toFixed(1) + '만';
    return num;
}

function renderData(data) {
    // Stats
    document.getElementById('fair-s-var').textContent = data.fair.s_var.toFixed(1);
    document.getElementById('fair-f-var').textContent = data.fair.f_var.toFixed(1);
    document.getElementById('fair-cost').textContent = formatMeso(data.fair.avg_cost);

    document.getElementById('rigged-s-var').textContent = data.rigged.s_var.toFixed(1);
    document.getElementById('rigged-f-var').textContent = data.rigged.f_var.toFixed(1);
    document.getElementById('rigged-cost').textContent = formatMeso(data.rigged.avg_cost);

    document.getElementById('sim-run-count').textContent = data.simulation_count;
    document.getElementById('sim-time').textContent = data.execution_time.toFixed(2) + 's';

    // Audit Table
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = '';

    for (let lv = 12; lv <= 21; lv++) {
        const slv = lv.toString();
        const theory = data.theory[slv];
        const fair = data.fair.level_stats[slv] || { try: 0, success_rate: 0, fail_rate: 0, boom_rate: 0 };
        const rigged = data.rigged.level_stats[slv] || { try: 0, success_rate: 0, fail_rate: 0, boom_rate: 0 };

        const t_s = (theory[0] * 100).toFixed(1);
        const t_f = (theory[1] * 100).toFixed(1);
        const t_b = (theory[2] * 100).toFixed(1);

        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-700";
        tr.innerHTML = `
            <td class="p-3 border-r border-gray-700 font-bold bg-gray-800">${lv}★</td>
            <td class="p-3 border-r border-gray-700 text-center font-mono text-yellow-500">
                S:${t_s}% / F:${t_f}% / B:${t_b}%
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

    // Chart
    updateChart();
}

function setChartMode(mode) {
    chartMode = mode;
    // Update tabs UI
    ['fail', 'success', 'meso'].forEach(m => {
        const btn = document.getElementById('tab-' + m);
        if (m === mode) {
            btn.classList.remove('bg-gray-900', 'text-gray-500');
            btn.classList.add('bg-gray-700', 'text-gray-300');
        } else {
            btn.classList.add('bg-gray-900', 'text-gray-500');
            btn.classList.remove('bg-gray-700', 'text-gray-300');
        }
    });
    updateChart();
}

function toggleCurve() {
    useBellCurve = !useBellCurve;
    const btn = document.getElementById('btn-curve');
    btn.textContent = useBellCurve ? "Bell Curve (Line)" : "Histogram (Bar)";
    updateChart();
}

function toggleLog() {
    useLogScale = !useLogScale;
    const btn = document.getElementById('btn-log');
    if (useLogScale) {
        btn.textContent = "Log Scale: ON";
        btn.classList.remove('bg-gray-900', 'text-gray-500');
        btn.classList.add('bg-blue-600', 'text-white');
    } else {
        btn.textContent = "Log Scale: OFF";
        btn.classList.add('bg-gray-900', 'text-gray-500');
        btn.classList.remove('bg-blue-600', 'text-white');
    }
    updateChart();
}

function getGaussian(mean, variance, x) {
    const sigma = Math.sqrt(variance);
    if (sigma === 0) return x === Math.round(mean) ? 1 : 0;
    const factor = 1 / (sigma * Math.sqrt(2 * Math.PI));
    const exponent = -0.5 * Math.pow((x - mean) / sigma, 2);
    return factor * Math.exp(exponent);
}

function updateChart() {
    if (!currentData) return;

    const ctx = document.getElementById('chart-comparison').getContext('2d');
    let fairHist, riggedHist;
    let label = "";

    if (chartMode === 'fail') {
        fairHist = currentData.fair.histogram;
        riggedHist = currentData.rigged.histogram;
        label = "Fail Streak Length";
        document.getElementById('chart-desc').textContent = "Distribution of consecutive failure strings. Longer tail = harsher bad luck.";
    } else if (chartMode === 'success') {
        fairHist = currentData.fair.s_histogram;
        riggedHist = currentData.rigged.s_histogram;
        label = "Success Streak Length";
        document.getElementById('chart-desc').textContent = "Distribution of consecutive success strings.";
    } else {
        fairHist = currentData.fair.m_histogram;
        riggedHist = currentData.rigged.m_histogram;
        label = "Meso Cost (1 Billion Units)";
        document.getElementById('chart-desc').textContent = "Distribution of Total Meso Cost to reach 22 stars. (Unit: 1,000,000,000 Mesos)";
    }

    // Prepare Data keys
    const allKeys = new Set([
        ...fairHist.map(d => d.x),
        ...riggedHist.map(d => d.x)
    ]);
    let labels = Array.from(allKeys).sort((a, b) => a - b);

    // If Bell Curve, generate range
    if (useBellCurve) {
        const calcStats = (hist) => {
            let sum = 0, count = 0;
            hist.forEach(d => { sum += d.x * d.y; count += d.y; });
            const mean = count ? sum / count : 0;
            let sumSq = 0;
            hist.forEach(d => { sumSq += d.y * Math.pow(d.x - mean, 2); });
            const variance = count ? sumSq / count : 0;
            return { mean, variance, count };
        };

        const fStats = calcStats(fairHist);
        const rStats = calcStats(riggedHist);

        const minX = labels[0] || 0;
        const maxX = labels[labels.length - 1] || 10;
        const range = maxX - minX;
        const step = range / 100; // 100 points
        labels = [];
        const fData = [], rData = [];

        for (let x = minX; x <= maxX; x += (step || 1)) {
            labels.push(x.toFixed(1));
            fData.push(getGaussian(fStats.mean, fStats.variance, x));
            rData.push(getGaussian(rStats.mean, rStats.variance, x));
        }

        drawChart(ctx, labels, fData, rData, 'line');
    } else {
        const getVal = (hist, k) => { const item = hist.find(d => d.x === k); return item ? item.y : 0; };
        drawChart(ctx, labels, labels.map(k => getVal(fairHist, k)), labels.map(k => getVal(riggedHist, k)), 'bar');
    }
}

function drawChart(ctx, labels, fData, rData, type) {
    if (cmpChart) cmpChart.destroy();

    const isBell = (type === 'line' && useBellCurve);

    cmpChart = new Chart(ctx, {
        type: type === 'bar' ? 'bar' : 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Fair World',
                    data: fData,
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.4)',
                    borderWidth: 2,
                    pointRadius: isBell ? 0 : 2,
                    fill: isBell ? false : true,
                    tension: 0.4
                },
                {
                    label: 'Rigged World',
                    data: rData,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.4)',
                    borderWidth: 2,
                    pointRadius: isBell ? 0 : 2,
                    fill: isBell ? false : true,
                    tension: 0.4
                }
            ]
        },
        options: {
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: {
                    type: useLogScale ? 'logarithmic' : 'linear',
                    beginAtZero: !useLogScale,
                    min: useLogScale ? 1 : undefined,
                    grid: { color: '#374151' },
                    title: { display: true, text: isBell ? 'Density' : 'Count' }
                },
                x: {
                    grid: { display: false }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return context.dataset.label + ': ' + context.raw.toFixed(isBell ? 4 : 0);
                        }
                    }
                }
            }
        }
    });
}
