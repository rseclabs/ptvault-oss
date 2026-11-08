/**
 * PTVault Dashboard Application
 * Main application logic for the dashboard
 */

// Application state
const AppState = {
    activeEngagement: null,
    engagements: [],
    evidence: [],
    searchQuery: '',
    filters: {
        severity: [],
        type: []
    },
    pendingSwitchEngagementId: null,
    currentUser: null
};

/**
 * Initialize application
 */
document.addEventListener('DOMContentLoaded', async () => {
    // Get this session's CSRF token (it is bound to the session; an older cookie is refused)
    try { await fetch('/api/auth/csrf-token', { credentials: 'same-origin' }); } catch (e) { /* ignore */ }

    // Initialize theme
    ThemeManager.init();

    // Initialize keyboard shortcuts
    initKeyboardShortcuts();

    // Setup event listeners
    setupEventListeners();

    // Load initial data
    await loadEngagements();
    await loadActiveEngagement();

    // Fetch current user info for role-based UI
    try {
        AppState.currentUser = await API.users.getMe();
    } catch (e) {
        console.warn('Failed to fetch current user:', e);
    }

    // Start idle timeout tracking
    if (window.idleTimeoutManager) {
        window.idleTimeoutManager.start();
    }

    // Load hosts and evidence stats if there's an active engagement
    if (AppState.activeEngagement) {
        await HostManager.init();
        await refreshEvidenceStats();

        // Restore view context from URL params (e.g., returning from note editor)
        const urlParams = new URLSearchParams(window.location.search);
        const returnHost = urlParams.get('host');
        const returnTab = urlParams.get('tab');
        const sectionParam = urlParams.get('section');
        const initialHash = (window.location.hash || '').replace(/^#/, '');

        if (returnHost) {
            switchSection('hosts');
            const hostId = returnHost === 'general' ? 'general' : parseInt(returnHost);
            await HostManager.selectHost(hostId);
            if (returnTab) {
                if (hostId === 'general') {
                    HostManager.switchGeneralTab(returnTab);
                } else {
                    HostManager.switchHostTab(returnTab);
                }
            }
            // Clean up URL params without reload
            window.history.replaceState({}, '', '/dashboard');
        }

        // Handle section/tool deep linking (e.g., ?section=tools&tool=markdown)
        if (sectionParam) {
            switchSection(sectionParam);
            const toolParam = urlParams.get('tool');
            if (sectionParam === 'tools' && toolParam && typeof ToolsManager !== 'undefined') {
                setTimeout(() => ToolsManager.switchTool(toolParam), 100);
            }
            window.history.replaceState({}, '', '/dashboard');
        }

        // Honor an existing #section hash on page load so refreshes and the
        // Back button can drop the user back where they were instead of the
        // default Engagements landing.
        if (initialHash) {
            switchSection(initialHash);
        }

        // Default landing: when no URL params or hash specify a section,
        // land on the Dashboard for an at-a-glance view of the engagement.
        if (!returnHost && !sectionParam && !initialHash) {
            switchSection('dashboard');
        }
    } else {
        // Clear stats if no active engagement
        updateEvidenceStats({ critical: 0, high: 0, medium: 0, low: 0 });
    }
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Theme toggle
    const toggleThemeBtn = document.getElementById('toggleTheme');
    if (toggleThemeBtn) {
        toggleThemeBtn.addEventListener('click', () => {
            ThemeManager.toggleTheme();
        });
    }

    // Host ribbon toggle (formerly the left-sidebar toggle)
    const ribbonToggle = document.getElementById('hostRibbonToggle');
    const ribbon = document.getElementById('hostRibbon');
    if (ribbonToggle && ribbon) {
        const stored = localStorage.getItem('hostRibbonCollapsed');
        const collapsed = stored === null
            ? window.matchMedia('(max-width: 60rem)').matches
            : stored === 'true';
        if (collapsed) {
            ribbon.classList.add('host-ribbon-collapsed');
            ribbonToggle.setAttribute('aria-expanded', 'false');
        }

        ribbonToggle.addEventListener('click', () => {
            ribbon.classList.toggle('host-ribbon-collapsed');
            const isCollapsed = ribbon.classList.contains('host-ribbon-collapsed');
            localStorage.setItem('hostRibbonCollapsed', isCollapsed);
            ribbonToggle.setAttribute('aria-expanded', String(!isCollapsed));
        });
    }

    // Main navigation tabs
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const sectionId = tab.dataset.section;
            switchSection(sectionId);
        });
    });

    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to log out?')) return;
            try {
                // Stop idle timeout tracking
                if (window.idleTimeoutManager) {
                    window.idleTimeoutManager.stop();
                }
                await API.auth.logout();
                window.location.href = '/';
            } catch (error) {
                showToast('Logout failed: ' + error.message, 'error');
            }
        });
    }

    // New engagement button
    const newEngagementBtn = document.getElementById('newEngagementBtn');
    if (newEngagementBtn) {
        newEngagementBtn.addEventListener('click', async () => {
            // Reset modal to create mode
            document.getElementById('engagementModalTitle').textContent = 'New Engagement';
            document.getElementById('engagementSubmitBtn').textContent = 'Create Engagement';
            document.getElementById('engEditId').value = '';
            document.getElementById('engagementForm').reset();
            // Populate dropdowns
            await populateTeamDropdown();
            await populateClientDropdown(null, null);
            openModal('engagementModal');
        });
    }

    // New evidence button
    const newEvidenceBtn = document.getElementById('newEvidenceBtn');
    if (newEvidenceBtn) {
        newEvidenceBtn.addEventListener('click', () => {
            if (!AppState.activeEngagement) {
                showToast('Please select an engagement first', 'warning');
                return;
            }
            openModal('evidenceModal');
        });
    }

    // Restore file input (Import / Export / Restore buttons themselves are
    // rendered dynamically inside the Tools → Data sub-tab and use inline
    // onclick → dataImportClicked / dataExportClicked / dataRestoreClicked).
    const restoreFileInput = document.getElementById('restoreFileInput');
    if (restoreFileInput) {
        restoreFileInput.addEventListener('change', handleRestoreEngagement);
    }

    // Add Host button
    const addHostBtn = document.getElementById('addHostBtn');
    if (addHostBtn) {
        addHostBtn.addEventListener('click', () => {
            if (!AppState.activeEngagement) {
                showToast('Please select an engagement first', 'warning');
                return;
            }
            openModal('addHostModal');
        });
    }

    // Search input
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
    }

    // Engagement form
    const engagementForm = document.getElementById('engagementForm');
    if (engagementForm) {
        engagementForm.addEventListener('submit', handleEngagementSubmit);
    }

    // Evidence form
    const evidenceForm = document.getElementById('evidenceForm');
    if (evidenceForm) {
        evidenceForm.addEventListener('submit', handleEvidenceSubmit);
    }

    // Confirm switch engagement button
    const confirmSwitchBtn = document.getElementById('confirmSwitchBtn');
    if (confirmSwitchBtn) {
        confirmSwitchBtn.addEventListener('click', confirmEngagementSwitch);
    }
}

/**
 * Load engagements
 */
async function loadEngagements() {
    try {
        const engagements = await API.engagements.getAll();
        AppState.engagements = engagements;

        await renderEngagementsGrid(engagements);
    } catch (error) {
        console.error('Failed to load engagements:', error);
        showToast('Failed to load engagements: ' + error.message, 'error');
    }
}

/**
 * Mark the active engagement's row in the ledger (it can render before the
 * active engagement has loaded).
 */
function markActiveEngagementRow(engagementId) {
    document.querySelectorAll('#engagementsGrid .engagement-card').forEach(row => {
        const isActive = Number(row.dataset.id) === Number(engagementId);
        row.classList.toggle('active', isActive);
        row.setAttribute('aria-current', isActive ? 'true' : 'false');
    });
}

/**
 * Load active engagement
 */
async function loadActiveEngagement() {
    try {
        const response = await API.engagements.getActive();

        if (response && response.id) {
            AppState.activeEngagement = response;
            updateActiveEngagementDisplay(response);
            markActiveEngagementRow(response.id);
        }
    } catch (error) {
        console.error('Failed to load active engagement:', error);
    }
}

/**
 * Load evidence
 */
async function loadEvidence() {
    try {
        const evidence = await API.evidence.getAll();
        AppState.evidence = evidence;

        renderEvidenceList(evidence);
        // Stats are refreshed by refreshEvidenceStats() which parses metadata
    } catch (error) {
        console.error('Failed to load evidence:', error);
        showToast('Failed to load evidence: ' + error.message, 'error');

        // Show empty state
        const evidenceList = document.getElementById('evidenceList');
        if (evidenceList) {
            evidenceList.innerHTML = '<div class="empty-state"><p>Failed to load evidence</p></div>';
        }
    }
}

/**
 * Render engagements grid
 */
async function renderEngagementsGrid(engagements) {
    const container = document.getElementById('engagementsGrid');
    if (!container) return;

    if (engagements.length === 0) {
        container.innerHTML = `
            <div class="empty-state-large">
                <div class="empty-icon"><i data-lucide="folder"></i></div>
                <h3>No Engagements Yet</h3>
                <p>Create your first engagement to get started</p>
            </div>
        `;
        return;
    }

    // Fetch stats for all engagements in parallel
    const statsPromises = engagements.map(eng => getStatsForEngagement(eng.id));
    const allStats = await Promise.all(statsPromises);

    const ledgerHead = `
        <div class="engagement-ledger-head" aria-hidden="true">
            <span>Engagement</span><span>Client and dates</span><span>Vulnerabilities</span>
        </div>`;
    container.innerHTML = ledgerHead + engagements.map((eng, index) => {
        // Stored values: the class takes only a known status, the label is escaped (H-17).
        const statusClass = ['active', 'completed', 'archived'].includes(eng.status) ? eng.status : 'active';
        const statusLabel = eng.status ? escapeHtml(eng.status.charAt(0).toUpperCase() + eng.status.slice(1)) : 'Active';
        const stats = allStats[index];
        const totalVulns = stats.critical + stats.high + stats.medium + stats.low;

        return `
            <div class="engagement-card ${AppState.activeEngagement?.id === eng.id ? 'active' : ''}"
                 data-id="${eng.id}" role="button" tabindex="0"
                 aria-current="${AppState.activeEngagement?.id === eng.id ? 'true' : 'false'}"
                 ${on('click', 'handleEngagementCardClick', eng.id)}
                 ${on('keydown', 'handleEngagementCardKey', ARG.event, eng.id)}>
                <div class="engagement-card-header">
                    <h3>${escapeHtml(eng.name)}</h3>
                    <div style="display:flex;gap:4px;align-items:center;">
                        ${eng.team_name ? `<span class="status-badge team-badge" title="Team: ${escapeHtml(eng.team_name)}">${escapeHtml(eng.team_name)}</span>` : ''}
                        <span class="status-badge status-${statusClass}">${statusLabel}</span>
                    </div>
                </div>
                <div class="engagement-card-body">
                    <div class="engagement-client">
                        <span class="label">Client:</span>
                        <span class="value">${eng.client_name ? escapeHtml(eng.client_name) : 'Not specified'}</span>
                    </div>
                    ${eng.contact_name || eng.contact_email ? `
                    <div class="engagement-contact">
                        <span class="label">Contact:</span>
                        <div class="contact-info">
                            ${eng.contact_name ? `<span class="contact-name">${escapeHtml(eng.contact_name)}</span>` : ''}
                            ${eng.contact_email ? `<span class="contact-email">${escapeHtml(eng.contact_email)}</span>` : ''}
                        </div>
                    </div>
                    ` : ''}
                    ${eng.start_date || eng.end_date ? `
                    <div class="engagement-dates">
                        <span class="label">Dates:</span>
                        <span class="value measured">${escapeHtml(eng.start_date || '?')} to ${escapeHtml(eng.end_date || '?')}</span>
                    </div>
                    ` : ''}
                </div>
                <div class="engagement-card-stats">
                    <span class="stats-label">Vulnerabilities:</span>
                    <div class="stats-badges">
                        ${stats.critical > 0 ? `<span class="stat-badge stat-critical" title="Critical"><span class="measured">${stats.critical}</span> critical</span>` : ''}
                        ${stats.high > 0 ? `<span class="stat-badge stat-high" title="High"><span class="measured">${stats.high}</span> high</span>` : ''}
                        ${stats.medium > 0 ? `<span class="stat-badge stat-medium" title="Medium"><span class="measured">${stats.medium}</span> medium</span>` : ''}
                        ${stats.low > 0 ? `<span class="stat-badge stat-low" title="Low"><span class="measured">${stats.low}</span> low</span>` : ''}
                        ${totalVulns === 0 ? `<span class="stat-badge stat-none">None</span>` : ''}
                    </div>
                </div>
                <div class="engagement-card-footer">
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Handle engagement card click - switch immediately without confirmation
 */
/** Enter or Space on a focused engagement card opens it, as a click does. */
function handleEngagementCardKey(event, engagementId) {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleEngagementCardClick(engagementId);
    }
}

async function handleEngagementCardClick(engagementId) {
    const engagement = AppState.engagements.find(e => e.id === engagementId);
    if (!engagement) return;

    // If already active, just switch to evidence view
    if (AppState.activeEngagement?.id === engagementId) {
        switchSection('hosts');
        return;
    }

    try {
        await API.engagements.setActive(engagementId);

        AppState.activeEngagement = AppState.engagements.find(e => e.id === engagementId);

        updateActiveEngagementDisplay(AppState.activeEngagement);
        await renderEngagementsGrid(AppState.engagements);

        await HostManager.init();
        await refreshEvidenceStats();

        if (typeof Dashboard !== 'undefined') {
            Dashboard.state.data = null;
            Dashboard.state.lastFetch = null;
        }

        switchSection('dashboard');

        showToast('Engagement activated', 'success');
    } catch (error) {
        console.error('Failed to set active engagement:', error);
        showToast('Failed to activate engagement: ' + error.message, 'error');
    }
}

/**
 * Confirm engagement switch (kept for backward compatibility)
 */
async function confirmEngagementSwitch() {
    const engagementId = AppState.pendingSwitchEngagementId;
    if (!engagementId) return;
    await handleEngagementCardClick(engagementId);
    AppState.pendingSwitchEngagementId = null;
}

/**
 * Handle edit engagement - opens modal pre-populated with engagement data
 */
async function handleEditEngagement(engagementId) {
    const engagement = AppState.engagements.find(e => e.id === engagementId);
    if (!engagement) {
        showToast('Engagement not found', 'error');
        return;
    }

    // Set modal to edit mode
    document.getElementById('engagementModalTitle').textContent = 'Edit Engagement';
    document.getElementById('engagementSubmitBtn').textContent = 'Save Changes';
    document.getElementById('engEditId').value = engagementId;

    // Populate form fields
    document.getElementById('engName').value = engagement.name || '';
    document.getElementById('engStatus').value = engagement.status || 'active';
    document.getElementById('engStartDate').value = engagement.start_date || '';
    document.getElementById('engEndDate').value = engagement.end_date || '';
    document.getElementById('engScope').value = engagement.description || '';
    document.getElementById('engContactName').value = engagement.contact_name || '';
    document.getElementById('engContactEmail').value = engagement.contact_email || '';
    document.getElementById('engNotes').value = engagement.notes || '';

    // Populate dropdowns with current selections
    await populateTeamDropdown(engagement.team_id);
    await populateClientDropdown(engagement.client_id, engagement.client_name);

    openModal('engagementModal');
}

/**
 * Handle engagement deletion
 */
async function handleDeleteEngagement(engagementId, engagementName) {
    const confirmed = confirm(`Are you sure you want to delete "${engagementName}"?\n\nThis will permanently delete ALL data including:\n- All hosts\n- All evidence\n- All notes, ports, and credentials\n\nThis action cannot be undone.`);

    if (!confirmed) return;

    try {
        await API.engagements.delete(engagementId);

        // Delete succeeded - immediately update UI

        // Remove the engagement card from DOM
        const engagementCard = document.querySelector(`.engagement-card[data-id="${engagementId}"]`);
        if (engagementCard) {
            engagementCard.remove();
        }

        // Remove from local state
        AppState.engagements = AppState.engagements.filter(e => e.id !== engagementId);

        // If we deleted the active engagement, clear it
        if (AppState.activeEngagement?.id === engagementId) {
            AppState.activeEngagement = null;
            updateActiveEngagementDisplay(null);
            // Clear hosts view
            document.getElementById('hostsList').innerHTML = '<div class="empty-state"><p>Select an engagement</p></div>';
            document.getElementById('evidenceList').innerHTML = '<div class="empty-state"><p>Select an engagement</p></div>';
        }

        // Show success immediately
        showToast('Engagement deleted successfully', 'success');

        // Refresh engagements list in background (don't let errors here affect success message)
        loadEngagements().catch(err => console.warn('Error refreshing engagements list:', err));
    } catch (error) {
        console.error('Failed to delete engagement:', error);
        showToast('Failed to delete engagement: ' + error.message, 'error');
    }
}

/**
 * Render evidence list
 */
function renderEvidenceList(evidence) {
    const container = document.getElementById('evidenceList');
    if (!container) return;

    // Update count badge
    const countBadge = document.getElementById('evidenceCount');
    if (countBadge) {
        countBadge.textContent = evidence.length;
    }

    if (evidence.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No evidence yet. Create your first entry!</p></div>';
        return;
    }

    container.innerHTML = evidence.map(ev => {
        const tags = parseTags(ev.tags);
        const severityBadge = ev.severity_level
            ? `<span class="severity-badge ${getSeverityColor(ev.severity_level)}">${getSeverityIcon(ev.severity_level)} ${ev.severity_level}</span>`
            : '';

        return `
            <div class="evidence-card" data-id="${ev.id}">
                <div class="evidence-header">
                    <div class="evidence-title">
                        <h3>${escapeHtml(ev.title)}</h3>
                        ${severityBadge}
                    </div>
                    <span class="evidence-type">${getEvidenceTypeDisplay(ev.evidence_type)}</span>
                </div>
                <div class="evidence-content">
                    ${escapeHtml(truncate(ev.content, 200))}
                </div>
                <div class="evidence-footer">
                    <div class="evidence-tags">
                        ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                    <div class="evidence-meta">
                        ${timeSince(ev.created_at)}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update evidence statistics display
 */
function updateEvidenceStats(stats) {
    const criticalEl = document.getElementById('statCritical');
    const highEl = document.getElementById('statHigh');
    const mediumEl = document.getElementById('statMedium');
    const lowEl = document.getElementById('statLow');

    if (criticalEl) criticalEl.textContent = stats.critical || 0;
    if (highEl) highEl.textContent = stats.high || 0;
    if (mediumEl) mediumEl.textContent = stats.medium || 0;
    if (lowEl) lowEl.textContent = stats.low || 0;
}

/**
 * Refresh evidence stats for the current active engagement
 * Counts vulnerabilities from scan metadata (Nessus, Burp, etc.)
 */
async function refreshEvidenceStats() {
    if (!AppState.activeEngagement) {
        updateEvidenceStats({ critical: 0, high: 0, medium: 0, low: 0 });
        HostManager.hostSeverityMap = {};
        return;
    }

    try {
        // Get all evidence for the active engagement
        const evidence = await API.evidence.getAll({});
        AppState.evidence = evidence;

        // Count vulnerabilities from scan metadata
        const stats = { critical: 0, high: 0, medium: 0, low: 0 };
        // Build per-host severity map (keyed by IP address)
        const hostSeverityByIP = {};

        for (const ev of evidence) {
            if (!ev.metadata) continue;

            let metadata;
            try {
                metadata = typeof ev.metadata === 'string' ? JSON.parse(ev.metadata) : ev.metadata;
            } catch (e) {
                continue;
            }

            const tool = (metadata.tool || '').toLowerCase();

            // For Nessus: count individual vulnerabilities from hosts
            if (tool === 'nessus' && metadata.hosts && Array.isArray(metadata.hosts)) {
                for (const host of metadata.hosts) {
                    const hostIP = host.ip;
                    if (!hostSeverityByIP[hostIP]) {
                        hostSeverityByIP[hostIP] = { critical: 0, high: 0, medium: 0, low: 0 };
                    }
                    if (host.vulnerabilities && Array.isArray(host.vulnerabilities)) {
                        for (const vuln of host.vulnerabilities) {
                            if (vuln.severity === 4) {
                                stats.critical++;
                                hostSeverityByIP[hostIP].critical++;
                            } else if (vuln.severity === 3) {
                                stats.high++;
                                hostSeverityByIP[hostIP].high++;
                            } else if (vuln.severity === 2) {
                                stats.medium++;
                                hostSeverityByIP[hostIP].medium++;
                            } else if (vuln.severity === 1) {
                                stats.low++;
                                hostSeverityByIP[hostIP].low++;
                            }
                        }
                    }
                }
            }

            // For Burp: count from summary (avoids double-counting issues array)
            if ((tool === 'burp_suite' || tool === 'burp') && metadata.summary && metadata.summary.by_severity) {
                const sev = metadata.summary.by_severity;
                stats.high += sev.High || 0;
                stats.medium += sev.Medium || 0;
                stats.low += sev.Low || 0;
            }
        }

        // Update the HostManager's severity map
        HostManager.hostSeverityMap = hostSeverityByIP;

        updateEvidenceStats(stats);
    } catch (error) {
        console.error('Failed to refresh evidence stats:', error);
        updateEvidenceStats({ critical: 0, high: 0, medium: 0, low: 0 });
        HostManager.hostSeverityMap = {};
    }
}

/**
 * Get vulnerability stats for a specific engagement
 */
async function getStatsForEngagement(engagementId) {
    const stats = { critical: 0, high: 0, medium: 0, low: 0 };

    try {
        // Fetch evidence for this specific engagement
        const response = await fetch(`/api/evidence?engagement_id=${engagementId}`);
        if (!response.ok) return stats;

        const evidence = await response.json();

        for (const ev of evidence) {
            if (!ev.metadata) continue;

            let metadata;
            try {
                metadata = typeof ev.metadata === 'string' ? JSON.parse(ev.metadata) : ev.metadata;
            } catch (e) {
                continue;
            }

            const tool = (metadata.tool || '').toLowerCase();

            // For Nessus: count individual vulnerabilities from hosts
            if (tool === 'nessus' && metadata.hosts && Array.isArray(metadata.hosts)) {
                for (const host of metadata.hosts) {
                    if (host.vulnerabilities && Array.isArray(host.vulnerabilities)) {
                        for (const vuln of host.vulnerabilities) {
                            if (vuln.severity === 4) stats.critical++;
                            else if (vuln.severity === 3) stats.high++;
                            else if (vuln.severity === 2) stats.medium++;
                            else if (vuln.severity === 1) stats.low++;
                        }
                    }
                }
            }

            // For Burp: count from summary
            if ((tool === 'burp_suite' || tool === 'burp') && metadata.summary && metadata.summary.by_severity) {
                const sev = metadata.summary.by_severity;
                stats.high += sev.High || 0;
                stats.medium += sev.Medium || 0;
                stats.low += sev.Low || 0;
            }
        }
    } catch (error) {
        console.error(`Failed to get stats for engagement ${engagementId}:`, error);
    }

    return stats;
}

/**
 * Refresh stats for a single engagement card (without re-rendering the entire grid)
 */
async function refreshEngagementCardStats(engagementId) {
    const card = document.querySelector(`.engagement-card[data-id="${engagementId}"]`);
    if (!card) return;

    const stats = await getStatsForEngagement(engagementId);
    const totalVulns = stats.critical + stats.high + stats.medium + stats.low;

    const statsContainer = card.querySelector('.engagement-card-stats .stats-badges');
    if (statsContainer) {
        statsContainer.innerHTML = `
            ${stats.critical > 0 ? `<span class="stat-badge stat-critical" title="Critical">${stats.critical}</span>` : ''}
            ${stats.high > 0 ? `<span class="stat-badge stat-high" title="High">${stats.high}</span>` : ''}
            ${stats.medium > 0 ? `<span class="stat-badge stat-medium" title="Medium">${stats.medium}</span>` : ''}
            ${stats.low > 0 ? `<span class="stat-badge stat-low" title="Low">${stats.low}</span>` : ''}
            ${totalVulns === 0 ? `<span class="stat-badge stat-none">None</span>` : ''}
        `;
    }
}

/**
 * Update active engagement display
 */
function updateActiveEngagementDisplay(engagement) {
    const display = document.getElementById('activeEngagement');
    if (display) {
        display.textContent = engagement ? engagement.name : '';
    }
    // Update import button state when engagement changes
    updateImportButtonState();
}

/**
 * Update import button enabled/disabled state based on active engagement.
 * The Import button now lives in Tools → Data (rendered on demand by
 * ToolsManager) — when present, this still keeps it in sync.
 */
function updateImportButtonState() {
    const importBtn = document.getElementById('importToolBtn');
    if (!importBtn) return;
    if (AppState.activeEngagement) {
        importBtn.disabled = false;
        importBtn.title = 'Import tool output';
    } else {
        importBtn.disabled = true;
        importBtn.title = 'Select an engagement first to import';
    }
}

/* ------------------------------------------------------------------
 * Data action helpers (Tools → Data sub-tab inline onclick targets)
 * ------------------------------------------------------------------ */

function dataImportClicked() {
    if (!AppState.activeEngagement) {
        showToast('Please select an engagement first', 'warning');
        return;
    }
    openImportModal();
}

function dataExportClicked() {
    if (!AppState.activeEngagement) {
        showToast('Please select an engagement first', 'warning');
        return;
    }
    openModal('exportModal');
}

function dataRestoreClicked() {
    const input = document.getElementById('restoreFileInput');
    if (input) input.click();
}

/**
 * Handle engagement click (legacy - redirects to card click)
 */
async function handleEngagementClick(engagementId) {
    handleEngagementCardClick(engagementId);
}

/**
 * Handle engagement form submission (create or update)
 */
/**
 * Populate the team dropdown in the engagement modal
 */
async function populateTeamDropdown(selectedTeamId) {
    const select = document.getElementById('engTeam');
    if (!select) return;

    try {
        const teams = await API.teams.getAll();
        select.innerHTML = '<option value="">No Team</option>' +
            teams.map(t =>
                `<option value="${t.id}" ${t.id === selectedTeamId ? 'selected' : ''}>${escapeHtml(t.name)}</option>`
            ).join('');
    } catch (error) {
        console.error('Failed to load teams for dropdown:', error);
        select.innerHTML = '<option value="">No Team</option>';
    }
}

/**
 * Populate the client dropdown in the engagement modal.
 * Also syncs the hidden engClientId / engClient text fields when an
 * option is preselected (edit mode) so the form submit picks them up.
 */
async function populateClientDropdown(selectedClientId, selectedClientName) {
    const select = document.getElementById('engClientSelect');
    if (!select) return;

    let clients = [];
    try {
        clients = await API.clients.getOptions();
    } catch (error) {
        console.error('Failed to load clients for dropdown:', error);
    }

    const options = [
        '<option value="">— Select client —</option>',
        ...clients.map(c =>
            `<option value="${c.id}" ${Number(c.id) === Number(selectedClientId) ? 'selected' : ''}>${escapeHtml(c.name)}</option>`
        ),
        '<option value="__new__">+ New Client…</option>',
    ];
    select.innerHTML = options.join('');

    // Hide the inline new-client card if it was open from a previous edit
    const card = document.getElementById('engNewClientCard');
    if (card) card.style.display = 'none';

    // Sync the hidden text field so the form submit handler still gets a
    // client_name even though the visible input is gone.
    const hiddenName = document.getElementById('engClient');
    const hiddenId = document.getElementById('engClientId');
    if (selectedClientId) {
        const match = clients.find(c => Number(c.id) === Number(selectedClientId));
        if (hiddenName) hiddenName.value = match ? match.name : (selectedClientName || '');
        if (hiddenId) hiddenId.value = String(selectedClientId);
    } else {
        if (hiddenName) hiddenName.value = selectedClientName || '';
        if (hiddenId) hiddenId.value = '';
    }
}

/**
 * Dropdown change handler: either reveal the inline new-client card
 * or sync the hidden client_id + client_name from the chosen option.
 */
function onEngagementClientChange(selectEl) {
    const card = document.getElementById('engNewClientCard');
    const hiddenId = document.getElementById('engClientId');
    const hiddenName = document.getElementById('engClient');

    if (selectEl.value === '__new__') {
        if (card) card.style.display = 'block';
        if (hiddenId) hiddenId.value = '';
        if (hiddenName) hiddenName.value = '';
        const nameInput = document.getElementById('engNewClientName');
        if (nameInput) nameInput.focus();
    } else {
        if (card) card.style.display = 'none';
        if (selectEl.value) {
            if (hiddenId) hiddenId.value = selectEl.value;
            if (hiddenName) hiddenName.value = selectEl.options[selectEl.selectedIndex].text;
        } else {
            if (hiddenId) hiddenId.value = '';
            if (hiddenName) hiddenName.value = '';
        }
    }
}

function cancelEngagementNewClient() {
    const card = document.getElementById('engNewClientCard');
    if (card) card.style.display = 'none';
    const select = document.getElementById('engClientSelect');
    if (select) select.value = '';
    const nameInput = document.getElementById('engNewClientName');
    if (nameInput) nameInput.value = '';
    const emailInput = document.getElementById('engNewClientEmail');
    if (emailInput) emailInput.value = '';
}

async function createEngagementNewClient() {
    const name = document.getElementById('engNewClientName').value.trim();
    const email = document.getElementById('engNewClientEmail').value.trim();

    if (!name) {
        showToast('Client name is required', 'error');
        return;
    }

    try {
        const created = await API.clients.create({
            name,
            admin_contact_email: email || null,
        });
        // Re-populate dropdown with the newly created client preselected
        await populateClientDropdown(created.id, created.name);
        const select = document.getElementById('engClientSelect');
        if (select) select.value = String(created.id);
        // Sync hidden fields explicitly in case the option ordering shifted
        document.getElementById('engClientId').value = String(created.id);
        document.getElementById('engClient').value = created.name;
        const card = document.getElementById('engNewClientCard');
        if (card) card.style.display = 'none';
        showToast(`Client "${created.name}" created`, 'success');
    } catch (error) {
        console.error('Failed to create client inline:', error);
        showToast(error.message || 'Failed to create client', 'error');
    }
}

// Handlers named in data-on-* attributes (utils.js on(), L-21)
window.handleEngagementCardKey = handleEngagementCardKey;
window.onEngagementClientChange = onEngagementClientChange;
window.cancelEngagementNewClient = cancelEngagementNewClient;
window.createEngagementNewClient = createEngagementNewClient;

async function handleEngagementSubmit(e) {
    e.preventDefault();

    const editId = document.getElementById('engEditId').value;
    const isEdit = editId && editId !== '';

    const teamSelect = document.getElementById('engTeam');
    const teamIdVal = teamSelect ? teamSelect.value : '';

    const clientIdRaw = document.getElementById('engClientId').value;
    const formData = {
        name: document.getElementById('engName').value,
        client_name: document.getElementById('engClient').value || null,
        client_id: clientIdRaw ? parseInt(clientIdRaw, 10) : null,
        status: document.getElementById('engStatus').value,
        start_date: document.getElementById('engStartDate').value || null,
        end_date: document.getElementById('engEndDate').value || null,
        description: document.getElementById('engScope').value || null,
        contact_name: document.getElementById('engContactName').value || null,
        contact_email: document.getElementById('engContactEmail').value || null,
        notes: document.getElementById('engNotes').value || null,
        team_id: teamIdVal ? parseInt(teamIdVal) : null
    };

    try {
        if (isEdit) {
            // Update existing engagement
            const updatedEngagement = await API.engagements.update(parseInt(editId), formData);

            // Reload engagements
            await loadEngagements();

            // Update active engagement display if this was the active one
            if (AppState.activeEngagement?.id === parseInt(editId)) {
                AppState.activeEngagement = updatedEngagement;
                updateActiveEngagementDisplay(updatedEngagement);
            }

            await renderEngagementsGrid(AppState.engagements);

            // Close modal and reset form
            closeModal('engagementModal');
            document.getElementById('engEditId').value = '';

            showToast('Engagement updated successfully', 'success');

            // Refresh admin engagements table if it's the active admin tab
            if (typeof AdminPanel !== 'undefined' && AdminPanel.activeTab === 'engagements') {
                AdminPanel.loadEngagementsList();
            }
        } else {
            // Create new engagement
            const newEngagement = await API.engagements.create(formData);

            // Reload engagements
            await loadEngagements();

            // Set as active
            await API.engagements.setActive(newEngagement.id);
            AppState.activeEngagement = newEngagement;
            updateActiveEngagementDisplay(newEngagement);
            await renderEngagementsGrid(AppState.engagements);

            // Close modal
            closeModal('engagementModal');

            // Initialize hosts and refresh stats (stats will be empty for new engagement)
            await HostManager.init();
            await refreshEvidenceStats();

            // Switch to evidence section
            switchSection('hosts');

            showToast('Engagement created successfully', 'success');
        }
    } catch (error) {
        console.error(`Failed to ${isEdit ? 'update' : 'create'} engagement:`, error);
        showToast(`Failed to ${isEdit ? 'update' : 'create'} engagement: ` + error.message, 'error');
    }
}

/**
 * Handle evidence form submission
 */
async function handleEvidenceSubmit(e) {
    e.preventDefault();

    if (!AppState.activeEngagement) {
        showToast('No active engagement selected', 'error');
        return;
    }

    const formData = {
        evidence_type: document.getElementById('evType').value,
        title: document.getElementById('evTitle').value,
        content: document.getElementById('evContent').value,
        tags: document.getElementById('evTags').value || null,
        severity_level: document.getElementById('evSeverity').value || null
    };

    // Get file if present
    const fileInput = document.getElementById('evFile');
    const file = fileInput.files[0] || null;

    try {
        await API.evidence.create(formData, file);

        // Reload hosts (will update evidence counts and may have new hosts from parsed metadata)
        await HostManager.loadHosts();

        // Reload evidence for current selection
        if (HostManager.selectedHostId) {
            await HostManager.loadEvidenceForHost(HostManager.selectedHostId);
        }

        // Refresh engagement card stats
        if (AppState.activeEngagement) {
            await refreshEngagementCardStats(AppState.activeEngagement.id);
        }

        // Refresh left panel evidence stats
        await refreshEvidenceStats();

        // Close modal
        closeModal('evidenceModal');

        // Reset form
        document.getElementById('evidenceForm').reset();

        showToast('Evidence added successfully', 'success');
    } catch (error) {
        console.error('Failed to create evidence:', error);
        showToast('Failed to add evidence: ' + error.message, 'error');
    }
}

/**
 * Handle search
 */
async function handleSearch(e) {
    const query = e.target.value.trim();

    if (!query) {
        // Reset to full list
        await loadEvidence();
        return;
    }

    if (!AppState.activeEngagement) {
        return;
    }

    try {
        const results = await API.evidence.search(query);
        AppState.evidence = results.results || [];

        renderEvidenceList(AppState.evidence);
        // Stats reflect all evidence, not just search results
    } catch (error) {
        console.error('Search failed:', error);
        showToast('Search failed: ' + error.message, 'error');
    }
}

/**
 * Export data
 */
async function exportData(format, templateName = null) {
    if (!AppState.activeEngagement) {
        showToast('No active engagement selected', 'error');
        return;
    }

    try {
        let blob;
        let filename;

        if (format === 'json') {
            const data = await API.export.exportJSON(AppState.activeEngagement.id);
            const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
            blob = new Blob([text], { type: 'application/json' });
            filename = `ptvault-export-${AppState.activeEngagement.id}.json`;
        } else if (format === 'markdown') {
            const text = await API.export.exportMarkdown(AppState.activeEngagement.id);
            blob = new Blob([text], { type: 'text/markdown' });
            filename = `report-${AppState.activeEngagement.id}.md`;
        } else if (format === 'template' && templateName) {
            const text = await API.export.exportTemplate(AppState.activeEngagement.id, templateName);
            blob = new Blob([text], { type: 'text/markdown' });
            filename = `report-${templateName}-${AppState.activeEngagement.id}.md`;
        } else {
            throw new Error('Invalid export format');
        }

        // Download the file
        downloadBlob(blob, filename);

        // Close modal
        closeModal('exportModal');

        showToast('Export successful', 'success');
    } catch (error) {
        console.error('Export failed:', error);
        showToast('Export failed: ' + error.message, 'error');
    }
}

/**
 * Handle restore engagement from JSON file
 */
async function handleRestoreEngagement(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Reset file input for future use
    e.target.value = '';

    // Validate file type
    if (!file.name.endsWith('.json')) {
        showToast('Please select a JSON file', 'error');
        return;
    }

    // Confirm restore
    const confirmed = confirm(`Are you sure you want to restore engagement from "${file.name}"?\n\nThis will create a new engagement with "(Restored)" suffix containing all the data from the backup.`);
    if (!confirmed) return;

    try {
        showToast('Restoring engagement...', 'info');

        const result = await API.engagements.importEngagement(file);

        // Reload engagements list
        await loadEngagements();

        showToast(`Successfully restored: ${result.engagement_name}`, 'success');

        // Optionally switch to the restored engagement
        if (result.engagement_id) {
            const switchTo = confirm('Would you like to switch to the restored engagement?');
            if (switchTo) {
                await API.engagements.setActive(result.engagement_id);
                AppState.activeEngagement = AppState.engagements.find(e => e.id === result.engagement_id);
                updateActiveEngagementDisplay(AppState.activeEngagement);
                await renderEngagementsGrid(AppState.engagements);
                await HostManager.init();
                await refreshEvidenceStats();
                switchSection('hosts');
            }
        }
    } catch (error) {
        console.error('Restore failed:', error);
        showToast('Restore failed: ' + error.message, 'error');
    }
}

// ============================================
// TOOL IMPORT FUNCTIONALITY
// ============================================

let importSelectedFile = null;

/**
 * Setup import tool event listeners
 */
function setupImportListeners() {
    // Import button itself lives in Tools → Data and uses inline onclick
    // (dataImportClicked). Dropzone + file input are always present in the
    // import modal markup, so their handlers are still wired here.
    const dropzone = document.getElementById('importDropzone');
    const fileInput = document.getElementById('importFile');

    if (dropzone && fileInput) {
        // Click to browse
        dropzone.addEventListener('click', () => fileInput.click());

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleImportFile(e.target.files[0]);
            }
        });

        // Drag and drop
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleImportFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Form submit
    const importForm = document.getElementById('importToolForm');
    if (importForm) {
        importForm.addEventListener('submit', handleImportSubmit);
    }

    // Set initial button state based on whether engagement is selected
    updateImportButtonState();
}

/**
 * Open import modal
 */
function openImportModal() {
    // Reset state
    importSelectedFile = null;
    document.getElementById('importFile').value = '';
    document.getElementById('importDropzone').classList.remove('hidden');
    document.getElementById('importFileInfo').style.display = 'none';
    document.getElementById('importDetectedTool').style.display = 'none';
    document.getElementById('importResults').style.display = 'none';
    document.getElementById('importSubmitBtn').disabled = true;
    document.getElementById('importTitle').value = '';
    document.getElementById('importTags').value = '';

    openModal('importToolModal');
}

/**
 * Handle selected file
 */
function handleImportFile(file) {
    // Validate extension
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xml', 'nessus'].includes(ext)) {
        showToast('Unsupported file type. Please use .xml or .nessus files.', 'error');
        return;
    }

    importSelectedFile = file;

    // Update UI
    document.getElementById('importDropzone').classList.add('hidden');
    document.getElementById('importFileInfo').style.display = 'block';
    document.getElementById('importFileName').textContent = file.name;
    document.getElementById('importFileSize').textContent = formatFileSize(file.size);
    document.getElementById('importSubmitBtn').disabled = false;

    // Try to detect tool type from file content
    detectToolType(file);
}

/**
 * Detect tool type from file content (client-side heuristic)
 */
async function detectToolType(file) {
    try {
        const text = await file.slice(0, 2000).text();

        let toolName = null;
        if (text.includes('<nmaprun')) {
            toolName = 'Nmap';
        } else if (text.includes('<issues') || text.includes('burp')) {
            toolName = 'Burp Suite';
        } else if (text.includes('NessusClientData') || file.name.endsWith('.nessus')) {
            toolName = 'Nessus';
        }

        if (toolName) {
            document.getElementById('importDetectedTool').style.display = 'flex';
            document.getElementById('detectedToolName').textContent = toolName;
        }
    } catch (e) {
        console.log('Could not detect tool type:', e);
    }
}

/**
 * Clear selected import file
 */
function clearImportFile() {
    importSelectedFile = null;
    document.getElementById('importFile').value = '';
    document.getElementById('importDropzone').classList.remove('hidden');
    document.getElementById('importFileInfo').style.display = 'none';
    document.getElementById('importDetectedTool').style.display = 'none';
    document.getElementById('importSubmitBtn').disabled = true;
}

/**
 * Handle import form submission
 */
async function handleImportSubmit(e) {
    e.preventDefault();

    if (!importSelectedFile) {
        showToast('Please select a file first', 'error');
        return;
    }

    if (!AppState.activeEngagement) {
        showToast('No active engagement selected', 'error');
        return;
    }

    const submitBtn = document.getElementById('importSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Importing...';

    try {
        // Build title
        let title = document.getElementById('importTitle').value.trim();
        if (!title) {
            // Auto-generate title from filename
            title = importSelectedFile.name.replace(/\.[^/.]+$/, '');
        }

        // Build evidence data
        const evidenceData = {
            evidence_type: 'tool_output',
            title: title,
            content: `Imported from ${importSelectedFile.name}`,
            tags: document.getElementById('importTags').value.trim() || null
        };

        // Upload
        const result = await API.evidence.create(evidenceData, importSelectedFile);

        // Parse metadata for summary
        let metadata = null;
        if (result.metadata) {
            try {
                metadata = typeof result.metadata === 'string' ? JSON.parse(result.metadata) : result.metadata;
            } catch (e) {}
        }

        // Show results
        if (metadata) {
            document.getElementById('importResults').style.display = 'block';

            // Count hosts
            const hostCount = metadata.hosts?.length || 0;
            document.getElementById('importHostCount').textContent = hostCount;

            // Count ports
            let portCount = 0;
            if (metadata.hosts) {
                metadata.hosts.forEach(h => {
                    portCount += h.open_ports?.length || 0;
                });
            }
            document.getElementById('importPortCount').textContent = portCount;

            // Count findings (for Nessus/Burp)
            let vulnCount = 0;
            if (metadata.summary?.total_issues) {
                vulnCount = metadata.summary.total_issues;
            } else if (metadata.summary?.hosts_total) {
                vulnCount = metadata.summary.hosts_up || 0;
            }
            document.getElementById('importVulnCount').textContent = vulnCount;
        }

        // Refresh hosts list
        await HostManager.loadHosts();

        // Refresh engagement card stats
        if (AppState.activeEngagement) {
            await refreshEngagementCardStats(AppState.activeEngagement.id);
        }

        // Refresh left panel evidence stats
        await refreshEvidenceStats();

        showToast(`Successfully imported ${importSelectedFile.name}`, 'success');

        // Close modal after brief delay to show results
        setTimeout(() => {
            closeModal('importToolModal');
        }, 1500);

    } catch (error) {
        console.error('Import failed:', error);
        showToast('Import failed: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Import';
    }
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Initialize import listeners on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    setupImportListeners();
});

/**
 * Switch between main app sections
 */
function switchSection(sectionId) {
    // Sections that require an active engagement
    const engagementSections = ['hosts', 'general', 'portgrid', 'reporting', 'testplans'];
    if (engagementSections.includes(sectionId) && !AppState.activeEngagement) {
        showEngagementRequiredModal();
        return;
    }

    // The "General" tab is a top-level shortcut into the Hosts section's
    // engagement-level view. It marks the General nav tab active but renders
    // inside section-hosts.
    const isGeneral = sectionId === 'general';
    const targetSectionId = isGeneral ? 'hosts' : sectionId;

    // Update tab states
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        if (tab.dataset.section === sectionId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update section visibility
    const sections = document.querySelectorAll('.app-section');
    sections.forEach(section => {
        if (section.id === `section-${targetSectionId}`) {
            section.classList.add('active');
        } else {
            section.classList.remove('active');
        }
    });

    // Hide the host-list panel and the left sidebar (vuln stats + host
    // search) when viewing General; both are filtering UIs that only make
    // sense alongside the Hosts list. Collapse the inner grid track too so
    // the details panel fills the row instead of leaving empty columns.
    const hostListPanel = document.querySelector('#section-hosts .host-list-panel');
    if (hostListPanel) {
        hostListPanel.style.display = isGeneral ? 'none' : '';
    }
    const hostsSidebar = document.querySelector('#section-hosts .sidebar');
    if (hostsSidebar) {
        hostsSidebar.style.display = isGeneral ? 'none' : '';
    }
    const hostViewContainer = document.querySelector('#section-hosts .host-view-container');
    if (hostViewContainer) {
        hostViewContainer.style.gridTemplateColumns = isGeneral ? '1fr' : '';
    }
    // Outer container has its own 280px | 1fr grid track for the sidebar.
    // Hiding the sidebar with display:none doesn't collapse that track —
    // we have to flatten it to 1fr so the General view fills the row.
    const evidenceContainer = document.getElementById('evidenceContainer');
    if (evidenceContainer) {
        evidenceContainer.style.gridTemplateColumns = isGeneral ? '1fr' : '';
    }
    const hostRibbon = document.getElementById('hostRibbon');
    if (hostRibbon) {
        hostRibbon.style.display = isGeneral ? 'none' : '';
    }

    if (isGeneral && typeof HostManager !== 'undefined') {
        HostManager.selectHost('general');
    } else if (sectionId === 'hosts' && typeof HostManager !== 'undefined'
               && HostManager.selectedHostId === 'general') {
        // Coming back to Hosts proper after viewing General — drop the
        // General view so the user sees the host-list landing state.
        HostManager.selectedHostId = null;
        HostManager.showGeneralSectionContainer(false);
        HostManager.showHostSections(false);
        const headerEl = document.getElementById('hostHeader');
        if (headerEl) {
            headerEl.innerHTML = '<h2>Host Details</h2>';
        }
        if (typeof HostManager.renderHostList === 'function') {
            HostManager.renderHostList();
        }
    }

    // Load dashboard metrics when switching to that section
    if (sectionId === 'dashboard') {
        if (typeof Dashboard !== 'undefined') {
            Dashboard.init();
            Dashboard.load();
        }
    }

    // Load port grid when switching to that section
    if (sectionId === 'portgrid' && AppState.activeEngagement) {
        HostManager.loadPortGridPage();
    }

    // Initialize commands when switching to that section
    if (sectionId === 'commands') {
        if (typeof CommandManager !== 'undefined' && !CommandManager.initialized) {
            CommandManager.init();
            CommandManager.initialized = true;
        }
    }

    // Initialize tools when switching to that section
    if (sectionId === 'tools') {
        if (typeof ToolsManager !== 'undefined' && !ToolsManager.initialized) {
            ToolsManager.init();
        }
    }

    // Initialize reporting when switching to that section
    if (sectionId === 'reporting') {
        if (typeof ReportingManager !== 'undefined' && !ReportingManager.initialized) {
            ReportingManager.init();
        }
    }

    // Initialize test plans when switching to that section
    if (sectionId === 'testplans') {
        if (typeof TestPlansManager !== 'undefined') {
            if (!TestPlansManager.initialized) {
                TestPlansManager.init();
            } else {
                // Plans are per engagement; refresh if it changed meanwhile
                TestPlansManager.onShow();
            }
        }
    }

    // Initialize admin when switching to that section
    if (sectionId === 'admin') {
        if (typeof AdminPanel !== 'undefined') {
            AdminPanel.init();
        }
    }

    // Push the section into the browser history so the Back button walks
    // through the user's in-app navigation instead of jumping straight back
    // to the login screen. _suppressHashPush is set when the navigation was
    // itself triggered by popstate (i.e. the user pressed Back).
    if (!_suppressHashPush) {
        const targetHash = '#' + sectionId;
        if (window.location.hash !== targetHash) {
            window.history.pushState({ section: sectionId }, '', targetHash);
        }
    }
}

/**
 * Browser history integration for in-app section navigation.
 *
 * The dashboard is a SPA — clicking the navbar tabs runs switchSection()
 * but never changes the URL, so the browser back-stack only contains
 * `login → /dashboard`. Pushing a hash on each section change gives the
 * Back button real entries to walk through, and the popstate listener
 * restores the corresponding section when the user navigates history.
 */
let _suppressHashPush = false;

window.addEventListener('popstate', (e) => {
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    _suppressHashPush = true;
    try {
        switchSection(hash);
    } finally {
        _suppressHashPush = false;
    }
});

/**
 * Show a modal telling the user to select an engagement first.
 */
function showEngagementRequiredModal() {
    // Remove any existing instance
    const existing = document.getElementById('engagementRequiredOverlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'engagementRequiredOverlay';
    overlay.style.cssText = `
        position: fixed; inset: 0; z-index: 99999;
        background: rgba(0,0,0,0.6);
        display: flex; align-items: center; justify-content: center;
    `;

    const dialog = document.createElement('div');
    dialog.style.cssText = `
        background: var(--bg-secondary, #1e293b); color: var(--text-primary, #e2e8f0);
        border: 1px solid var(--border-color, #334155);
        border-radius: 8px; padding: 2rem; max-width: 400px; width: 90%;
        text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    `;

    dialog.innerHTML = `
        <div style="margin-bottom: 1rem;">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="color: var(--warning-color, #f59e0b); margin: 0 auto;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
        </div>
        <h3 style="margin: 0 0 0.5rem; font-size: 1.25rem;">No Engagement Selected</h3>
        <p style="margin: 0 0 1.5rem; color: var(--text-muted, #94a3b8);">
            You need to select an engagement first.
        </p>
        <button id="engagementRequiredOkBtn" style="
            background: var(--primary-color, #3b82f6); color: white;
            border: none; border-radius: 6px; padding: 0.625rem 1.5rem;
            font-size: 0.9375rem; cursor: pointer; font-weight: 500;
        ">OK</button>
    `;

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    document.getElementById('engagementRequiredOkBtn').addEventListener('click', () => {
        overlay.remove();
        switchSection('engagements');
    });
}

// Make functions globally available
window.handleEngagementCardClick = handleEngagementCardClick;
window.handleEditEngagement = handleEditEngagement;
window.handleDeleteEngagement = handleDeleteEngagement;
window.confirmEngagementSwitch = confirmEngagementSwitch;
window.exportData = exportData;
window.clearImportFile = clearImportFile;
window.switchSection = switchSection;
window.handleRestoreEngagement = handleRestoreEngagement;
