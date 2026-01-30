
/**
 * Fetches simulation comparison results from the server.
 * @param {Object} payload - The simulation configuration payload.
 * @returns {Promise<Object>} - The simulation results.
 */
export async function fetchCompareSimulation(payload) {
    const res = await fetch('/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
    }
    return await res.json();
}
