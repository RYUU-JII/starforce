import { ui } from './audit/ui.js';
import { filters } from './audit/filters.js';
import { gapAnalysis } from './audit/gapAnalysis.js';

// Global exports for HTML event handlers
window.switchAuditTab = function (btn, tabId) {
    ui.activateTab(btn, tabId);
};

window.filters = filters;
window.ui = ui;
window.gapAnalysis = gapAnalysis;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('audit-root')) {
        filters.init();
    }
});
