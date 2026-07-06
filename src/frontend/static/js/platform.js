// ============================================
// Trident Unified Platform — Tab Controller
// ============================================

(function () {
    'use strict';

    const TAB_IDS = ['sos', 'dashboard', 'analytics'];

    // Map URL paths to tab ids
    const PATH_TO_TAB = {
        '/': 'sos',
        '/dashboard': 'dashboard',
        '/analytics': 'analytics'
    };

    let activeTab = null;
    let dashboardInitialized = false;
    let analyticsInitialized = false;

    // ---- Boot ----
    document.addEventListener('DOMContentLoaded', () => {
        // Determine initial tab from URL path or hash
        const hash = window.location.hash.replace('#', '');
        const path = window.location.pathname;
        let startTab = 'sos';

        if (hash && TAB_IDS.includes(hash)) {
            startTab = hash;
        } else if (PATH_TO_TAB[path]) {
            startTab = PATH_TO_TAB[path];
        }

        switchTab(startTab);

        // Listen for hash changes (back/forward)
        window.addEventListener('hashchange', () => {
            const h = window.location.hash.replace('#', '');
            if (h && TAB_IDS.includes(h) && h !== activeTab) {
                switchTab(h);
            }
        });
    });

    // ---- Tab Switching ----
    window.switchTab = function (tabId) {
        if (!TAB_IDS.includes(tabId)) return;
        activeTab = tabId;

        // Toggle pane visibility
        TAB_IDS.forEach(id => {
            const pane = document.getElementById('pane-' + id);
            if (pane) pane.style.display = id === tabId ? 'block' : 'none';
        });

        // Toggle nav-link active class
        document.querySelectorAll('.platform-nav .nav-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });

        // Update browser URL without reload
        history.replaceState(null, '', '#' + tabId);

        // Lazy-init heavy tabs
        if (tabId === 'dashboard' && !dashboardInitialized) {
            dashboardInitialized = true;
            if (typeof initializeDashboard === 'function') initializeDashboard();
        }
        if (tabId === 'analytics' && !analyticsInitialized) {
            analyticsInitialized = true;
            if (typeof initializeAnalytics === 'function') initializeAnalytics();
        }
    };
})();
