import { state } from './state.js';

export const gapAnalysis = {
    data: null,
    async fetch(star = 17) {
        console.log(`[GapAnalysis] Fetching data for ${star}*`);
        try {
            if (!this.data) {
                const res = await fetch('/api/audit/temporal-gap');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                this.data = await res.json();
                console.log('[GapAnalysis] Data loaded:', Object.keys(this.data));
            }
            this.render(star);
        } catch (err) {
            console.error('[GapAnalysis] Fetch failed:', err);
            const autocc = document.getElementById('gapAutocorr');
            if (autocc) autocc.innerHTML = `<span style="color:#cf6679">Error</span>`;
        }
    },
    render(star) {
        console.log(`[GapAnalysis] Rendering star ${star}`);
        const starData = this.data[star];
        if (!starData) {
            console.warn(`[GapAnalysis] No data for star ${star}`);
            return;
        }

        // Update Metrics
        const autocc = document.getElementById('gapAutocorr');
        if (autocc) {
            autocc.innerHTML = `<span style="color:${starData.real.autocorr < 0 ? '#cf6679' : '#03dac6'}">${starData.real.autocorr.toFixed(2)}</span>`;
        }

        const varEl = document.getElementById('gapVariance');
        if (varEl) {
            varEl.innerHTML = `<span style="color:${starData.real.variance < 0.7 ? '#cf6679' : (starData.real.variance < 0.9 ? '#ffb74d' : '#03dac6')}">${starData.real.variance.toFixed(2)}</span>`;
        }

        const skewEl = document.getElementById('gapSkew');
        if (skewEl) {
            skewEl.innerHTML = `<span style="color:${Math.abs(starData.real.skew) > 0.5 ? '#ffb74d' : '#03dac6'}">${starData.real.skew.toFixed(2)}</span>`;
        }

        const distEl = document.getElementById('gapDistance');
        if (distEl) {
            const dist = Math.abs(starData.real.autocorr - starData.iid.autocorr);
            distEl.innerHTML = `<span>${(dist * 100).toFixed(1)}% Deviation</span>`;
        }

        // Render Time Series
        const ctxTS = document.getElementById('gapTimeSeriesChart');
        if (ctxTS) {
            if (state.charts.gapTS) state.charts.gapTS.destroy();

            const labels = starData.real.hourly.map(d => d.timestamp.slice(11, 16));
            state.charts.gapTS = new Chart(ctxTS.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Real Z-Score (Observed)',
                            data: starData.real.z_scores,
                            borderColor: '#bb86fc',
                            backgroundColor: 'rgba(187, 134, 252, 0.1)',
                            fill: false,
                            tension: 0.1,
                            borderWidth: 2
                        },
                        {
                            label: 'IID Z-Score (Fair Simulation)',
                            data: starData.iid.z_scores,
                            borderColor: '#03dac6',
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.1,
                            borderWidth: 1.5
                        }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                        y: {
                            title: { display: true, text: 'Z-Score' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    },
                    plugins: { legend: { position: 'bottom', labels: { color: '#888' } } }
                }
            });
        }

        // Render Distribution
        const ctxDist = document.getElementById('gapDistChart');
        if (ctxDist) {
            if (state.charts.gapDist) state.charts.gapDist.destroy();

            const bins = [-3, -2, -1, 0, 1, 2, 3];
            const getCounts = (zScores) => bins.slice(0, -1).map((b, i) => zScores.filter(z => z >= b && z < bins[i + 1]).length);

            state.charts.gapDist = new Chart(ctxDist.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: ['-3~-2', '-2~-1', '-1~0', '0~1', '1~2', '2~3'],
                    datasets: [
                        { label: 'Real', data: getCounts(starData.real.z_scores), backgroundColor: 'rgba(187, 134, 252, 0.5)' },
                        { label: 'IID', data: getCounts(starData.iid.z_scores), backgroundColor: 'rgba(3, 218, 198, 0.5)' }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#888' } } },
                    scales: {
                        x: { ticks: { color: '#666' } },
                        y: { ticks: { color: '#666' } }
                    }
                }
            });
        }

        // Render Star Comparison
        const ctxStar = document.getElementById('gapStarChart');
        if (ctxStar) {
            if (state.charts.gapStar) state.charts.gapStar.destroy();

            const stars = Object.keys(this.data).sort((a, b) => a - b);
            state.charts.gapStar = new Chart(ctxStar.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: stars.map(s => s + '★'),
                    datasets: [{
                        label: 'Autocorrelation (Negative = Rebalancing)',
                        data: stars.map(s => this.data[s].real.autocorr),
                        backgroundColor: stars.map(s => this.data[s].real.autocorr < -0.2 ? '#cf6679' : '#bb86fc')
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                        y: { title: { display: true, text: 'Corr Index', color: '#888' }, min: -0.6, max: 0.6, ticks: { color: '#666' } },
                        x: { ticks: { color: '#666' } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }
};
