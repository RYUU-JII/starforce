
export function formatMeso(num) {
    if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
    if (num >= 10000) return (num / 10000).toFixed(1) + '만';
    return num;
}

export function autoCap(meanLen, kind) {
    const m = Math.max(1, Number(meanLen) || 1);
    if (kind === 's') return Math.min(25, Math.max(6, Math.round(m * 6)));
    if (kind === 'f') return Math.min(500, Math.max(50, Math.round(m * 80)));
    return Math.min(50, Math.max(5, Math.round(m * 20)));
}
