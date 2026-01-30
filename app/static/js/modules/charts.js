
export class ChartManager {
    constructor() {
        this.cmpChart = null;
        this.deckChart = null;
        this.currentData = null;
        this.deckAnalysis = null;

        // Chart Config State
        this.chartMode = 'fail'; // fail, success, meso
        this.chartView = 'hist'; // hist, tail
        this.useLogY = false;
        this.useLogX = false;
        this.useGaussian = false;
        this.displayRange = 0.1;
        this.displayMaxX = 200;
        this.deckInspectStar = 17;
        this.deckInspectMode = 's';
        this.fixedLengthMode = false;

        // Mode mapping
        this.viewByMode = { fail: 'hist', success: 'hist', meso: 'tail' };
    }

    setData(data) {
        this.currentData = data;
        if (data.deck_analysis) {
            this.deckAnalysis = data.deck_analysis;
        }
    }

    setChartMode(mode) {
        this.chartMode = mode;
        this.chartView = this.viewByMode[mode] || 'hist';
        // Return active view so UI can update buttons
        return this.chartView;
    }

    setChartView(view) {
        this.chartView = view;
        this.viewByMode[this.chartMode] = view;
    }

    toggleLogY() { this.useLogY = !this.useLogY; return this.useLogY; }
    toggleLogX() { this.useLogX = !this.useLogX; return this.useLogX; }
    toggleSmooth() {
        if (this.chartView === 'hist') this.useGaussian = !this.useGaussian;
        return this.useGaussian;
    }

    setDisplayRange(val) { this.displayRange = val; }
    setDisplayMaxX(val) { this.displayMaxX = Math.max(0, val); }

    setDeckInspectStar(val) { this.deckInspectStar = val; }
    setDeckInspectMode(mode) { this.deckInspectMode = mode; }
    setFixedLengthMode(isFixed) { this.fixedLengthMode = isFixed; }

    updateComparisonChart() {
        if (!this.currentData) return;

        const ctx = document.getElementById('chart-comparison').getContext('2d');
        let fairHist, riggedHist;
        let label = "";
        let desc = "";

        if (this.chartMode === 'fail') {
            fairHist = this.currentData.fair.histogram;
            riggedHist = this.currentData.rigged.histogram;
            label = "Fail Streak Length (No Boom)";
            desc = this.chartView === 'tail'
                ? "Tail probability P(streak ≥ x). Shows extreme bad-luck risk."
                : `Histogram of consecutive failure streaks (probability %).${this.displayRange > 0 ? ` Showing bins ≥${this.displayRange}% probability.` : ''}`;
        } else if (this.chartMode === 'success') {
            fairHist = this.currentData.fair.s_histogram;
            riggedHist = this.currentData.rigged.s_histogram;
            label = "Success Streak Length";
            desc = this.chartView === 'tail'
                ? "Tail probability P(streak ≥ x). Shows extreme good-luck risk."
                : `Histogram of consecutive success streaks (probability %).${this.displayRange > 0 ? ` Showing bins ≥${this.displayRange}% probability.` : ''}`;
        } else {
            fairHist = this.currentData.fair.m_histogram;
            riggedHist = this.currentData.rigged.m_histogram;
            label = "Meso Cost (1 Billion Units)";
            desc = this.chartView === 'tail'
                ? "Tail probability P(cost ≥ x). Highlights high-cost risk."
                : `Histogram of total meso cost to reach 22★ (probability %).${this.displayRange > 0 ? ` Showing bins ≥${this.displayRange}% probability.` : ''}`;
        }

        const descEl = document.getElementById('chart-desc');
        if (descEl) descEl.textContent = desc;

        const allKeys = new Set([
            ...fairHist.map(d => d.x),
            ...riggedHist.map(d => d.x)
        ]);
        let keys = Array.from(allKeys).sort((a, b) => a - b);

        if (this.displayMaxX > 0) {
            keys = keys.filter(k => k <= this.displayMaxX);
        }

        const getCounts = (hist) => {
            const map = new Map(hist.map(d => [d.x, d.y]));
            return keys.map(k => map.get(k) || 0);
        };
        let fCounts = getCounts(fairHist);
        let rCounts = getCounts(riggedHist);

        // Trim
        if (this.chartView === 'hist' && this.displayRange > 0) {
            const fTotal = fCounts.reduce((a, b) => a + b, 0) || 1;
            const rTotal = rCounts.reduce((a, b) => a + b, 0) || 1;
            const fProbs = fCounts.map(v => (v / fTotal) * 100);
            const rProbs = rCounts.map(v => (v / rTotal) * 100);
            const maxProbs = fProbs.map((fp, i) => Math.max(fp, rProbs[i]));

            let lowerIdx = 0;
            let upperIdx = maxProbs.length - 1;
            for (let i = 0; i < maxProbs.length; i++) {
                if (maxProbs[i] >= this.displayRange) { lowerIdx = i; break; }
            }
            for (let i = maxProbs.length - 1; i >= 0; i--) {
                if (maxProbs[i] >= this.displayRange) { upperIdx = i; break; }
            }
            if (lowerIdx <= upperIdx) {
                keys = keys.slice(lowerIdx, upperIdx + 1);
                fCounts = fCounts.slice(lowerIdx, upperIdx + 1);
                rCounts = rCounts.slice(lowerIdx, upperIdx + 1);
            }
        }

        const fTotal = fCounts.reduce((a, b) => a + b, 0) || 1;
        const rTotal = rCounts.reduce((a, b) => a + b, 0) || 1;

        let fVals = [], rVals = [];
        if (this.chartView === 'tail') {
            let fCum = 0, rCum = 0;
            for (let i = keys.length - 1; i >= 0; i--) {
                fCum += fCounts[i];
                rCum += rCounts[i];
                fVals[i] = (fCum / fTotal) * 100;
                rVals[i] = (rCum / rTotal) * 100;
            }
        } else {
            fVals = fCounts.map(v => (v / fTotal) * 100);
            rVals = rCounts.map(v => (v / rTotal) * 100);
        }

        const useLogXEffective = (this.chartMode === 'meso') && this.useLogX;
        const type = (this.chartView === 'tail' || useLogXEffective) ? 'line' : 'bar';
        const yLabel = this.chartView === 'tail' ? 'Tail Probability (%)' : 'Probability (%)';

        let gaussFair = null, gaussRigged = null;
        if (this.chartView === 'hist' && this.useGaussian) {
            gaussFair = this._calcGaussian(keys, fVals);
            if (!this.fixedLengthMode) { // Only show Rigged Gauss if not fixed
                gaussRigged = this._calcGaussian(keys, rVals);
            }
        }

        // Confidence Intervals (Fair World, Hist Only)
        let fairCI = null;
        if (this.chartView === 'hist') {
            const rawCounts = getCounts(fairHist);
            // Re-slice to match display range keys
            const sliceStart = this.displayRange > 0 ? fCounts.indexOf(fCounts.find((_, i) => keys[i] === keys[0])) : 0;
            // Note: fCounts/rCounts were already sliced in previous steps if displayRange > 0
            // But we need the 'count' values corresponding to 'keys' to calculate SE.
            // fCounts currently holds the cropped counts.
            fairCI = this._calcCI(keys, fCounts, fTotal);
        }

        // Percentile Markers (Meso Only)
        let markers = [];
        if (this.chartMode === 'meso') {
            const getP = (hist, p) => {
                let cum = 0;
                const total = hist.reduce((a, b) => a + b.y, 0);
                const target = total * p;
                for (let d of hist) {
                    cum += d.y;
                    if (cum >= target) return d.x;
                }
                return hist[hist.length - 1].x;
            };

            // P99
            const p99f = getP(this.currentData.fair.m_histogram, 0.99);
            const p99r = getP(this.currentData.rigged.m_histogram, 0.99);
            markers.push({ x: p99f, label: 'Fair P99', color: '#60a5fa' });
            markers.push({ x: p99r, label: 'Rigged P99', color: '#ef4444' });

            // P99.9
            const p999f = getP(this.currentData.fair.m_histogram, 0.999);
            const p999r = getP(this.currentData.rigged.m_histogram, 0.999);
            markers.push({ x: p999f, label: 'Fair P99.9', color: '#93c5fd', dash: [4, 4] });
            markers.push({ x: p999r, label: 'Rigged P99.9', color: '#fca5a5', dash: [4, 4] });
        }

        const plotKeys = useLogXEffective ? keys.map(k => (k <= 0 ? 0.1 : k)) : keys;
        const xLabels = type === 'bar' ? keys : plotKeys;

        this._drawChart(ctx, xLabels, fVals, rVals, {
            type,
            useLogY: this.useLogY,
            useLogX: useLogXEffective,
            yLabel,
            xLabel: label,
            gaussFair,
            gaussRigged,
            fairCI,
            markers
        });
    }

    _calcGaussian(keys, values) {
        if (keys.length === 0) return [];
        const mean = keys.reduce((acc, x, i) => acc + x * values[i], 0) / 100;
        const variance = keys.reduce((acc, x, i) => acc + values[i] * Math.pow(x - mean, 2), 0) / 100;
        if (!isFinite(variance) || variance <= 0) return values.map(() => 0);
        const sigma = Math.sqrt(variance);
        const pdf = keys.map(x => (1 / (sigma * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mean) / sigma, 2)));
        const sumPdf = pdf.reduce((a, b) => a + b, 0) || 1;
        return pdf.map(v => (v / sumPdf) * 100);
    }

    _calcCI(keys, counts, total) {
        // Standard Error for proportion p: sqrt(p(1-p)/n) * 1.96 (for 95%)
        // Returns { upper: [], lower: [] } normalized to %
        if (!total || total < 1) return { upper: keys.map(() => 0), lower: keys.map(() => 0) };
        const cimult = 1.96;
        const upper = [];
        const lower = [];

        counts.forEach(c => {
            const p = c / total;
            const se = Math.sqrt((p * (1 - p)) / total);
            // Convert to percentages
            let u = (p + cimult * se) * 100;
            let l = (p - cimult * se) * 100;
            if (l < 0) l = 0;
            upper.push(u);
            lower.push(l);
        });
        return { upper, lower };
    }

    _drawChart(ctx, labels, fData, rData, opts) {
        // Paranoid destruction
        const canvasId = ctx.canvas.id;
        if (canvasId) {
            const existing = Chart.getChart(canvasId);
            if (existing) existing.destroy();
        }

        if (this.cmpChart) {
            try { this.cmpChart.destroy(); } catch (e) { }
            this.cmpChart = null;
        }

        const type = opts.type || 'bar';
        const usePoints = type === 'line';
        const useLogYLocal = !!opts.useLogY;
        const useLogXLocal = !!opts.useLogX;

        let minPositive = Infinity;
        [...fData, ...rData].forEach(v => { if (v > 0 && v < minPositive) minPositive = v; });
        if (!isFinite(minPositive)) minPositive = 0.0001;

        const adjustLog = (arr) => useLogYLocal ? arr.map(v => v <= 0 ? minPositive * 0.5 : v) : arr;

        // Prepare Datasets
        const datasets = [];

        // 1. Fair World CI (Background Band)
        if (opts.fairCI) {
            const fLower = usePoints ? labels.map((x, i) => ({ x, y: adjustLog(opts.fairCI.lower)[i] })) : adjustLog(opts.fairCI.lower);
            const fUpper = usePoints ? labels.map((x, i) => ({ x, y: adjustLog(opts.fairCI.upper)[i] })) : adjustLog(opts.fairCI.upper);

            datasets.push({
                label: 'Fair 95% CI',
                data: fUpper,
                type: 'line',
                borderColor: 'transparent',
                backgroundColor: 'rgba(96, 165, 250, 0.1)', // Very faint blue
                fill: '+1', // Fill to next dataset (Lower)
                pointRadius: 0,
                borderWidth: 0,
                order: 10
            });
            datasets.push({
                label: 'Fair 95% CI (Lower)',
                data: fLower,
                type: 'line',
                borderColor: 'transparent',
                backgroundColor: 'transparent',
                fill: false,
                pointRadius: 0,
                borderWidth: 0,
                order: 10
            });
        }

        // 2. Main Data
        const fSeries = usePoints ? labels.map((x, i) => ({ x, y: adjustLog(fData)[i] })) : adjustLog(fData);
        const rSeries = usePoints ? labels.map((x, i) => ({ x, y: adjustLog(rData)[i] })) : adjustLog(rData);

        datasets.push({
            label: 'Fair World',
            data: fSeries,
            borderColor: '#60a5fa',
            backgroundColor: 'rgba(96, 165, 250, 0.4)',
            borderWidth: 2,
            pointRadius: usePoints ? 0 : 2,
            fill: usePoints ? false : true,
            tension: 0.2,
            order: 5
        });

        datasets.push({
            label: 'Rigged World',
            data: rSeries,
            borderColor: '#ef4444',
            backgroundColor: 'rgba(239, 68, 68, 0.4)',
            borderWidth: 2,
            pointRadius: usePoints ? 0 : 2,
            fill: usePoints ? false : true,
            tension: 0.2,
            order: 4
        });

        // 3. Gaussian Overlay
        if (opts.gaussFair) {
            datasets.push({
                label: 'Fair (Gauss)', data: usePoints ? labels.map((x, i) => ({ x, y: adjustLog(opts.gaussFair)[i] })) : adjustLog(opts.gaussFair),
                type: 'line', borderColor: '#93c5fd', borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, fill: false, order: 3
            });
        }
        if (opts.gaussRigged) {
            datasets.push({
                label: 'Rigged (Gauss)', data: usePoints ? labels.map((x, i) => ({ x, y: adjustLog(opts.gaussRigged)[i] })) : adjustLog(opts.gaussRigged),
                type: 'line', borderColor: '#fca5a5', borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, fill: false, order: 3
            });
        }

        // 4. Percentile Markers (Cost Only)
        if (opts.markers && opts.markers.length > 0) {
            // Find Y-max for drawing lines
            let yMax = 0;
            [...fData, ...rData].forEach(v => { if (v > yMax) yMax = v; });

            opts.markers.forEach(m => {
                let markerData = [];
                if (usePoints) {
                    markerData = [{ x: m.x, y: 0 }, { x: m.x, y: yMax }];
                } else {
                    // Category axis
                    const idx = labels.indexOf(m.x);
                    if (idx !== -1) {
                        markerData = labels.map((_, i) => (i === idx ? yMax : null));
                    }
                }

                if (markerData.length > 0) {
                    datasets.push({
                        label: m.label,
                        data: markerData,
                        type: 'line',
                        borderColor: m.color,
                        borderWidth: 1.5,
                        borderDash: m.dash || [2, 2],
                        pointRadius: 0,
                        order: 1,
                        spanGaps: true
                    });
                }
            });
        }

        this.cmpChart = new Chart(ctx, {
            type: type === 'bar' ? 'bar' : 'line',
            data: {
                labels: usePoints ? undefined : labels,
                datasets: datasets
            },
            options: {
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: {
                        type: useLogYLocal ? 'logarithmic' : 'linear',
                        min: useLogYLocal ? minPositive * 0.5 : undefined,
                        grid: { color: '#374151' },
                        title: { display: true, text: opts.yLabel || '' }
                    },
                    x: {
                        type: useLogXLocal ? 'logarithmic' : (usePoints ? 'linear' : 'category'),
                        grid: { display: false },
                        title: { display: true, text: opts.xLabel || '' }
                    }
                }
            }
        });
    }

    updateDeckInspectChart() {
        if (!this.deckAnalysis) return;
        const canvas = document.getElementById('chart-deck-analysis');
        if (!canvas) return;

        const starData = this.deckAnalysis[this.deckInspectStar.toString()];
        if (!starData) return;

        const dist = starData[this.deckInspectMode];
        if (!dist || Object.keys(dist).length === 0) {
            if (this.deckChart) this.deckChart.destroy();
            return;
        }

        let lengths = Object.keys(dist).map(Number).sort((a, b) => a - b);
        let counts = lengths.map(l => dist[l]);

        if (this.displayMaxX > 0) {
            const cutIdx = lengths.findIndex(l => l > this.displayMaxX);
            if (cutIdx !== -1) {
                lengths = lengths.slice(0, cutIdx);
                counts = counts.slice(0, cutIdx);
            }
        } else if (lengths.length > 2000) {
            lengths = lengths.slice(0, 2000);
            counts = counts.slice(0, 2000);
        }

        const ctx = canvas.getContext('2d');

        // Destory previous
        const existing = Chart.getChart(canvas.id);
        if (existing) existing.destroy();
        if (this.deckChart) {
            try { this.deckChart.destroy(); } catch (e) { }
            this.deckChart = null;
        }

        this.deckChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: lengths,
                datasets: [
                    {
                        type: 'bar', label: 'Actual', data: counts,
                        backgroundColor: this.deckInspectMode === 's' ? '#3b82f6' : '#ef4444', order: 1
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { grid: { color: '#374151' }, title: { display: true, text: 'Streak Length' } },
                    y: { grid: { color: '#374151' }, beginAtZero: true }
                }
            }
        });
    }
}
