/**
 * PTVault Host Manager
 * Handles host-centric evidence view
 */

// Burp Suite confidence values; anything else gets no class suffix (H-13)
const VULN_CONFIDENCE = ['certain', 'firm', 'tentative'];

const HostManager = {
    selectedHostId: null,  // null = nothing selected, 'general' = General section, number = host ID
    hosts: [],
    generalCount: 0,
    currentEvidence: [],
    currentNotes: [],
    currentPorts: [],
    currentCredentials: [],
    currentVulnerabilities: [],  // Vulnerabilities extracted from Nessus/scan metadata
    vulnFilter: 'all',  // Current vulnerability filter
    engagementNotes: [],  // Notes for General section (engagement-level)
    engagementCredentials: [],  // Credentials for General section (engagement-level)
    terminalDumps: [],  // Terminal dumps for General section (engagement-level)
    engagementFindings: [],  // Findings for General section (engagement-level)
    currentGeneralTab: 'notes',  // Current sub-tab in General section: 'notes', 'credentials', 'terminal', 'findings'
    portGridFilter: null,  // Port filter: null or { port: number, protocol: string }
    portGridData: null,    // Cached port data for filtering
    hostSeverityMap: {},   // Map of hostId -> { critical: count, high: count, medium: count, low: count }
    severityFilter: null,  // Severity filter: null or 'critical' | 'high' | 'medium' | 'low'
    currentHostTab: 'notes',  // Current sub-tab in Host sections: 'notes', 'ports', 'findings', 'credentials' (Indicators moved to persistent bar)
    selectedEvidenceIds: new Set(),  // Set of selected evidence IDs for bulk operations
    bulkOperationInProgress: false,  // Flag to prevent multiple concurrent bulk operations
    keywordSearchResults: null,  // Set of host IDs from keyword search, or null if no search active
    keywordSearchQuery: '',  // Current keyword search text
    _keywordSearchTimer: null,  // Debounce timer for keyword search
    colorFilters: new Set(),  // Set of selected color_category values (OR within set, AND with other filters)

    /**
     * Initialize host manager
     */
    async init() {
        if (AppState.activeEngagement) {
            // Clear cached data from previous engagement
            this.engagementNotes = [];
            this.engagementCredentials = [];
            this.terminalDumps = [];
            this.engagementFindings = [];
            this.currentNotes = [];
            this.currentPorts = [];
            this.currentCredentials = [];
            this.currentEvidence = [];
            this.portGridFilter = null;
            this.portGridData = null;
            this.hostSeverityMap = {};
            this.severityFilter = null;
            this.keywordSearchResults = null;
            this.keywordSearchQuery = '';
            this.colorFilters = new Set();
            this.currentHostTab = 'notes';

            await this.loadHosts();
            await this.loadSavedFilters();

            // If something was selected, re-select to load fresh data
            if (this.selectedHostId !== null) {
                await this.selectHost(this.selectedHostId);
            }
        }
    },

    /**
     * Load hosts for active engagement
     */
    async loadHosts() {
        try {
            const data = await API.hosts.getAll();
            this.hosts = data.hosts || [];
            this.generalCount = data.general_count || 0;
            this.renderHostList();
        } catch (error) {
            console.error('Failed to load hosts:', error);
            // Show empty state
            this.hosts = [];
            this.generalCount = 0;
            this.renderHostList();
        }
    },

    /**
     * Render host list in sidebar
     */
    renderHostList() {
        const container = document.getElementById('hostsList');
        if (!container) return;

        // Update general count
        const generalCountEl = document.getElementById('generalCount');
        if (generalCountEl) {
            generalCountEl.textContent = this.generalCount;
        }

        // Update general item active state
        const generalItem = document.querySelector('.host-item.general');
        if (generalItem) {
            generalItem.classList.toggle('active', this.selectedHostId === 'general');
        }

        if (this.hosts.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No hosts yet</p></div>';
            return;
        }

        container.innerHTML = this.hosts.map(host => `
            <div class="host-item ${this.selectedHostId === host.id ? 'active' : ''}"
                 data-host-id="${host.id}"
                 ${on('click', 'HostManager.selectHost', host.id)}>
                ${host.color_category ? `<div class="host-color-badge" data-color="${escapeHtml(host.color_category)}"></div>` : ''}
                <span class="host-icon">${this.getHostIcon(host)}</span>
                <div class="host-info">
                    <span class="host-name measured">${escapeHtml(host.ip)}</span>
                    <span class="host-meta">${escapeHtml(host.hostname || host.os || '')}</span>
                    ${this.renderIndicatorBadges(host)}
                </div>
                ${host.evidence_count ? `<span class="evidence-count measured" title="${host.evidence_count} evidence items">${host.evidence_count}</span>` : ''}
            </div>
        `).join('');

        // Initialize Lucide icons for the rendered content
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Re-apply filters after rendering to maintain filter state
        this.applyFilters();
    },

    /**
     * Get icon for host based on OS or type
     */
    getHostIcon(host) {
        if (!host.os) return '<i data-lucide="monitor"></i>';
        const os = host.os.toLowerCase();
        if (os.includes('windows')) return '<i data-lucide="monitor"></i>';
        if (os.includes('linux') || os.includes('ubuntu') || os.includes('debian')) return '<i data-lucide="hard-drive"></i>';
        if (os.includes('mac') || os.includes('darwin')) return '<i data-lucide="laptop"></i>';
        if (os.includes('router') || os.includes('cisco')) return '<i data-lucide="router"></i>';
        if (os.includes('firewall')) return '<i data-lucide="shield"></i>';
        return '<i data-lucide="monitor"></i>';
    },

    /**
     * Select a host and load its evidence
     */
    async selectHost(hostId) {
        this.selectedHostId = hostId;
        this.renderHostList();
        // On phones and tablets the list and the detail are one screen each.
        document.querySelector('.host-view-container')?.classList.add('has-selection');

        // Update header
        const headerEl = document.getElementById('hostHeader');
        if (headerEl) {
            if (hostId === 'general') {
                headerEl.innerHTML = `
                    <button type="button" class="host-back-btn" ${on('click', 'HostManager.showHostList')} aria-label="Back to hosts">
                        <i data-lucide="arrow-left"></i><span>Hosts</span>
                    </button>
                    <div class="host-detail-header">
                        <h2>General</h2>
                        <p>Evidence without host assignment</p>
                    </div>
                `;
            } else {
                const host = this.hosts.find(h => h.id === hostId);
                if (host) {
                    headerEl.innerHTML = `
                        <button type="button" class="host-back-btn" ${on('click', 'HostManager.showHostList')} aria-label="Back to hosts">
                            <i data-lucide="arrow-left"></i><span>Hosts</span>
                        </button>
                        <div class="host-detail-header host-record">
                            <h2 class="host-record-ip measured">${escapeHtml(host.ip)}</h2>
                            <dl class="host-record-facts">
                                ${host.hostname ? `<div><dt>Hostname</dt><dd class="measured">${escapeHtml(host.hostname)}</dd></div>` : ''}
                                ${host.os ? `<div><dt>OS</dt><dd>${escapeHtml(host.os)}</dd></div>` : ''}
                            </dl>
                        </div>
                        <div class="host-actions">
                            <button class="btn btn-sm btn-secondary" ${on('click', 'HostManager.editHost', host.id)}>Edit</button>
                            <button class="btn btn-sm btn-quiet-danger" ${on('click', 'HostManager.deleteHost', host.id)}>Delete</button>
                        </div>
                    `;
                }
            }
        }

        // Load evidence for this host
        await this.loadEvidenceForHost(hostId);

        // Load host-specific sections (not for 'general')
        if (hostId !== 'general') {
            await Promise.all([
                this.loadNotes(hostId),
                this.loadPorts(hostId),
                this.loadCredentials(hostId),
                this.loadVulnerabilities(hostId)
            ]);
            // Show host sections, hide engagement notes
            this.showHostSections(true);
            this.showEngagementNotesSection(false);
        } else {
            // Hide host sections for General
            this.showHostSections(false);
            // Show General section container and load data for current tab
            this.showGeneralSectionContainer(true);
            await this.loadGeneralTabData(this.currentGeneralTab);
        }
    },

    /**
     * Phones and tablets: return from a host's detail to the host list.
     */
    showHostList() {
        document.querySelector('.host-view-container')?.classList.remove('has-selection');
        document.getElementById('hostsList')?.scrollIntoView({ block: 'start' });
    },

    /**
     * Show/hide host-specific sections
     */
    showHostSections(show) {
        const container = document.getElementById('hostSectionsContainer');
        if (container) {
            container.classList.toggle('active', show);
        }
        // Hide General section container when showing host sections
        if (show) {
            this.showGeneralSectionContainer(false);
            // Ensure correct tab is shown
            this.switchHostTab(this.currentHostTab);
        }
        // Populate indicators if showing and a host is selected
        if (show && this.selectedHostId && this.selectedHostId !== 'general') {
            this.populateIndicators();
        }
    },

    /**
     * Show/hide engagement notes section (for General view) - legacy, kept for compatibility
     */
    showEngagementNotesSection(show) {
        // Now handled by generalSectionContainer
    },

    /**
     * Show/hide the General section container
     */
    showGeneralSectionContainer(show) {
        const el = document.getElementById('generalSectionContainer');
        if (el) {
            el.style.display = show ? 'block' : 'none';
        }
    },

    /**
     * Switch between General sub-tabs (Notes, Credentials, Terminal Dumps)
     */
    async switchGeneralTab(tabName) {
        this.currentGeneralTab = tabName;

        // Update tab button states
        document.querySelectorAll('.general-sub-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.subtab === tabName);
        });

        // Update sub-page visibility
        document.querySelectorAll('.general-sub-page').forEach(page => {
            page.classList.remove('active');
        });

        const tabMap = {
            'notes': 'generalSubNotes',
            'credentials': 'generalSubCredentials',
            'terminal': 'generalSubTerminal',
            'findings': 'generalSubFindings'
        };

        const activePageId = tabMap[tabName];
        if (activePageId) {
            const activePage = document.getElementById(activePageId);
            if (activePage) {
                activePage.classList.add('active');
            }
        }

        // Load data for the selected tab
        await this.loadGeneralTabData(tabName);
    },

    /**
     * Switch between Host sub-tabs (Indicators, Notes, Ports, Findings, Credentials)
     */
    switchHostTab(tabName) {
        this.currentHostTab = tabName;

        // Update tab button states
        document.querySelectorAll('.host-sub-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.subtab === tabName);
        });

        // Map tab names to section IDs (Indicators moved out of tab system into a persistent bar)
        const tabMap = {
            'notes': 'notesSection',
            'ports': 'portsSection',
            'findings': 'vulnerabilitiesSection',
            'credentials': 'credentialsSection'
        };

        // Hide all sections, show only the active one
        Object.values(tabMap).forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) {
                section.classList.remove('active');
            }
        });

        const activeSectionId = tabMap[tabName];
        if (activeSectionId) {
            const activeSection = document.getElementById(activeSectionId);
            if (activeSection) {
                activeSection.classList.add('active');
            }
        }

    },

    /**
     * Load data for a specific General tab
     */
    async loadGeneralTabData(tabName) {
        switch (tabName) {
            case 'notes':
                await this.loadEngagementNotes();
                break;
            case 'credentials':
                await this.loadEngagementCredentials();
                break;
            case 'terminal':
                await this.loadTerminalDumps();
                break;
            case 'findings':
                await this.loadEngagementFindings();
                break;
        }
    },

    /**
     * Load evidence for selected host
     */
    async loadEvidenceForHost(hostId) {
        const container = document.getElementById('evidenceList');
        if (!container) return;

        container.innerHTML = '<div class="loading">Loading evidence...</div>';

        try {
            let evidence;
            if (hostId === 'general') {
                evidence = await API.evidence.getAll({ no_host: true });
            } else {
                evidence = await API.evidence.getAll({ host_id: hostId });
            }

            this.currentEvidence = evidence;
            this.renderEvidenceDetails(evidence);
        } catch (error) {
            console.error('Failed to load evidence:', error);
            container.innerHTML = '<div class="empty-state"><p>Failed to load evidence</p></div>';
        }
    },

    /**
     * Render evidence details inline (no modal)
     */
    renderEvidenceDetails(evidence) {
        const container = document.getElementById('evidenceList');
        if (!container) return;

        // Update count
        const countEl = document.getElementById('evidenceCount');
        if (countEl) {
            countEl.textContent = evidence.length;
        }

        if (evidence.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No evidence for this host</p></div>';
            this.updateBulkActionToolbar();
            return;
        }

        container.innerHTML = evidence.map(ev => {
            const tags = parseTags(ev.tags);
            const severityBadge = ev.severity_level
                ? `<span class="severity-badge ${getSeverityColor(ev.severity_level)}">${getSeverityIcon(ev.severity_level)} ${ev.severity_level}</span>`
                : '';
            const isSelected = this.selectedEvidenceIds.has(ev.id);

            return `
                <div class="evidence-detail-inline ${isSelected ? 'selected' : ''}" data-id="${ev.id}">
                    <div class="evidence-header">
                        <div class="flex items-center gap-2">
                            <input type="checkbox"
                                   class="evidence-checkbox"
                                   data-evidence-id="${ev.id}"
                                   ${isSelected ? 'checked' : ''}
                                   ${on('change', 'HostManager.toggleEvidenceSelection', ev.id, ARG.checked)}>
                            <div class="evidence-title">
                                <h3>${escapeHtml(ev.title)}</h3>
                                ${severityBadge}
                            </div>
                        </div>
                        <div class="evidence-actions">
                            <span class="evidence-type ${ev.evidence_type === 'tool_output' ? 'is-tool' : 'is-tester'}" title="${ev.evidence_type === 'tool_output' ? 'Imported from a tool' : 'Written by a tester'}">${getEvidenceTypeDisplay(ev.evidence_type)}</span>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.toggleEvidence', ev.id)} title="Expand">
                                <span class="expand-icon">▼</span>
                            </button>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editEvidence', ev.id)} title="Edit"><i data-lucide="pencil"></i></button>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteEvidence', ev.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                        </div>
                    </div>
                    <div class="evidence-preview">
                        ${escapeHtml(truncate(ev.content, 200))}
                    </div>
                    <div class="evidence-expanded" style="display: none;">
                        <div class="evidence-content-full">
                            <pre>${escapeHtml(ev.content || '')}</pre>
                        </div>
                        ${ev.file_name ? `
                            <div class="evidence-attachment">
                                <a href="/api/evidence/${ev.id}/download" class="btn btn-sm btn-secondary">
                                    <i data-lucide="paperclip"></i> ${escapeHtml(ev.file_name)}
                                </a>
                            </div>
                        ` : ''}
                        ${ev.metadata ? `
                            <div class="evidence-metadata">
                                <details>
                                    <summary>Parsed Metadata</summary>
                                    <pre>${escapeHtml(JSON.stringify(JSON.parse(ev.metadata), null, 2))}</pre>
                                </details>
                            </div>
                        ` : ''}
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

        // Update bulk action toolbar visibility
        this.updateBulkActionToolbar();
    },

    /**
     * Toggle evidence expanded/collapsed state
     */
    toggleEvidence(evidenceId) {
        const card = document.querySelector(`.evidence-detail-inline[data-id="${evidenceId}"]`);
        if (!card) return;

        const expanded = card.querySelector('.evidence-expanded');
        const preview = card.querySelector('.evidence-preview');
        const icon = card.querySelector('.expand-icon');

        if (expanded.style.display === 'none') {
            expanded.style.display = 'block';
            preview.style.display = 'none';
            icon.textContent = '▲';
            card.classList.add('expanded');
        } else {
            expanded.style.display = 'none';
            preview.style.display = 'block';
            icon.textContent = '▼';
            card.classList.remove('expanded');
        }
    },

    /**
     * Edit evidence (open modal)
     */
    editEvidence(evidenceId) {
        const evidence = this.currentEvidence.find(e => e.id === evidenceId);
        if (!evidence) return;

        // Populate edit modal
        document.getElementById('editEvId').value = evidence.id;
        document.getElementById('editEvTitle').value = evidence.title;
        document.getElementById('editEvContent').value = evidence.content || '';
        document.getElementById('editEvTags').value = evidence.tags || '';

        SlideOver.open('editEvidence');
    },

    /**
     * Delete evidence
     */
    async deleteEvidence(evidenceId) {
        if (!confirm('Are you sure you want to delete this evidence?')) {
            return;
        }

        try {
            await API.evidence.delete(evidenceId);
            showToast('Evidence deleted', 'success');

            // Reload evidence list
            if (this.selectedHostId) {
                await this.loadEvidenceForHost(this.selectedHostId);
            }
            // Reload hosts to update counts
            await this.loadHosts();

            // Refresh engagement card stats
            if (AppState.activeEngagement) {
                await refreshEngagementCardStats(AppState.activeEngagement.id);
            }

            // Refresh left panel evidence stats
            await refreshEvidenceStats();
        } catch (error) {
            console.error('Failed to delete evidence:', error);
            showToast('Failed to delete evidence: ' + error.message, 'error');
        }
    },

    /**
     * Toggle evidence selection for bulk operations
     */
    toggleEvidenceSelection(evidenceId, isSelected) {
        if (isSelected) {
            this.selectedEvidenceIds.add(evidenceId);
        } else {
            this.selectedEvidenceIds.delete(evidenceId);
        }
        this.updateBulkActionToolbar();

        // Update visual state of the evidence card
        const card = document.querySelector(`.evidence-detail-inline[data-id="${evidenceId}"]`);
        if (card) {
            card.classList.toggle('selected', isSelected);
        }
    },

    /**
     * Select all evidence items
     */
    selectAllEvidence() {
        this.currentEvidence.forEach(ev => {
            this.selectedEvidenceIds.add(ev.id);
        });
        this.renderEvidenceDetails(this.currentEvidence);
    },

    /**
     * Clear all evidence selections
     */
    clearEvidenceSelection() {
        this.selectedEvidenceIds.clear();
        this.renderEvidenceDetails(this.currentEvidence);
    },

    /**
     * Update bulk action toolbar visibility and count
     */
    updateBulkActionToolbar() {
        const toolbar = document.getElementById('bulkActionToolbar');
        const countEl = document.getElementById('bulkSelectedCount');

        if (!toolbar || !countEl) return;

        const count = this.selectedEvidenceIds.size;

        if (count > 0) {
            toolbar.classList.remove('hidden');
            countEl.textContent = count;
        } else {
            toolbar.classList.add('hidden');
        }
    },

    /**
     * Perform bulk tag operation
     */
    async bulkTagEvidence() {
        const tags = prompt('Enter tags to add (comma-separated):');
        if (!tags || tags.trim() === '') return;

        await this.performBulkOperation('tag', { tags: tags.trim() });
    },

    /**
     * Perform bulk delete operation
     */
    async bulkDeleteEvidence() {
        const count = this.selectedEvidenceIds.size;
        if (!confirm(`Are you sure you want to delete ${count} evidence item${count > 1 ? 's' : ''}?`)) {
            return;
        }

        await this.performBulkOperation('delete');
    },

    /**
     * Perform bulk export operation
     */
    async bulkExportEvidence() {
        try {
            if (this.bulkOperationInProgress) return;
            this.bulkOperationInProgress = true;
            this.setBulkActionButtonsDisabled(true);

            const evidenceIds = Array.from(this.selectedEvidenceIds);
            const result = await API.evidence.bulkOperation('export', evidenceIds);

            // Download the exported data as JSON
            const dataStr = JSON.stringify(result.data, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `evidence-export-${Date.now()}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast(result.message || `Exported ${result.success} items`, 'success');
        } catch (error) {
            console.error('Bulk export failed:', error);
            showToast('Bulk export failed: ' + error.message, 'error');
        } finally {
            this.bulkOperationInProgress = false;
            this.setBulkActionButtonsDisabled(false);
        }
    },

    /**
     * Perform bulk move to host operation
     */
    async bulkMoveToHost() {
        // Get list of hosts for selection
        const hostOptions = this.hosts.map(h =>
            `<option value="${h.id}">${escapeHtml(h.ip)}${h.hostname ? ' (' + escapeHtml(h.hostname) + ')' : ''}</option>`
        ).join('');

        // Show simple prompt with host selection
        const hostId = prompt(`Enter host ID to move evidence to:\n\nAvailable hosts:\n${this.hosts.map(h => `${h.id}: ${h.ip}${h.hostname ? ' (' + h.hostname + ')' : ''}`).join('\n')}`);

        if (!hostId || hostId.trim() === '') return;

        const parsedHostId = parseInt(hostId.trim());
        if (isNaN(parsedHostId) || !this.hosts.find(h => h.id === parsedHostId)) {
            showToast('Invalid host ID', 'error');
            return;
        }

        await this.performBulkOperation('move_to_host', { host_id: parsedHostId });
    },

    /**
     * Perform bulk operation with loading state
     */
    async performBulkOperation(operation, params = {}) {
        try {
            if (this.bulkOperationInProgress) return;
            this.bulkOperationInProgress = true;
            this.setBulkActionButtonsDisabled(true);

            const evidenceIds = Array.from(this.selectedEvidenceIds);
            const result = await API.evidence.bulkOperation(operation, evidenceIds, params);

            showToast(result.message || 'Operation completed', 'success');

            // Clear selection
            this.clearEvidenceSelection();

            // Reload evidence list
            if (this.selectedHostId) {
                await this.loadEvidenceForHost(this.selectedHostId);
            }

            // Reload hosts to update counts
            await this.loadHosts();

            // Refresh engagement card stats
            if (AppState.activeEngagement) {
                await refreshEngagementCardStats(AppState.activeEngagement.id);
            }

            // Refresh left panel evidence stats
            await refreshEvidenceStats();

        } catch (error) {
            console.error('Bulk operation failed:', error);
            showToast('Bulk operation failed: ' + error.message, 'error');
        } finally {
            this.bulkOperationInProgress = false;
            this.setBulkActionButtonsDisabled(false);
        }
    },

    /**
     * Enable/disable bulk action buttons during operations
     */
    setBulkActionButtonsDisabled(disabled) {
        const buttons = document.querySelectorAll('#bulkActionToolbar button');
        buttons.forEach(btn => {
            btn.disabled = disabled;
        });
    },

    /**
     * Edit host (open modal)
     */
    editHost(hostId) {
        const host = this.hosts.find(h => h.id === hostId);
        if (!host) return;

        document.getElementById('editHostId').value = host.id;
        document.getElementById('editHostIp').value = host.ip;
        document.getElementById('editHostHostname').value = host.hostname || '';
        document.getElementById('editHostOs').value = host.os || '';
        document.getElementById('editHostNotes').value = host.notes || '';

        openModal('editHostModal');
    },

    /**
     * Delete host
     */
    async deleteHost(hostId) {
        if (!confirm('Are you sure you want to delete this host? Evidence will be unlinked but not deleted.')) {
            return;
        }

        try {
            await API.hosts.delete(hostId);
            showToast('Host deleted', 'success');

            // Clear selection and reload
            this.selectedHostId = null;
            await this.loadHosts();

            // Clear evidence panel
            const container = document.getElementById('evidenceList');
            if (container) {
                container.innerHTML = '<div class="empty-state"><p>Select a host to view evidence</p></div>';
            }
            const headerEl = document.getElementById('hostHeader');
            if (headerEl) {
                headerEl.innerHTML = '';
            }
        } catch (error) {
            console.error('Failed to delete host:', error);
            showToast('Failed to delete host: ' + error.message, 'error');
        }
    },

    /**
     * Handle add host form submission
     */
    async handleAddHost(e) {
        e.preventDefault();

        const ip = document.getElementById('newHostIp').value.trim();
        const hostname = document.getElementById('newHostHostname').value.trim() || null;
        const os = document.getElementById('newHostOs').value.trim() || null;
        const notes = document.getElementById('newHostNotes').value.trim() || null;

        if (!ip) {
            showToast('IP address is required', 'error');
            return;
        }

        try {
            const newHost = await API.hosts.create({ ip, hostname, os, notes });
            showToast('Host added', 'success');

            closeModal('addHostModal');
            document.getElementById('addHostForm').reset();

            // Reload hosts and select the new one
            await this.loadHosts();
            await this.selectHost(newHost.id);
        } catch (error) {
            console.error('Failed to add host:', error);
            showToast('Failed to add host: ' + error.message, 'error');
        }
    },

    /**
     * Handle edit host form submission
     */
    async handleEditHost(e) {
        e.preventDefault();

        const hostId = parseInt(document.getElementById('editHostId').value);
        const hostname = document.getElementById('editHostHostname').value.trim() || null;
        const os = document.getElementById('editHostOs').value.trim() || null;
        const notes = document.getElementById('editHostNotes').value.trim() || null;

        try {
            await API.hosts.update(hostId, { hostname, os, notes });
            showToast('Host updated', 'success');

            closeModal('editHostModal');

            // Reload hosts and re-select
            await this.loadHosts();
            await this.selectHost(hostId);
        } catch (error) {
            console.error('Failed to update host:', error);
            showToast('Failed to update host: ' + error.message, 'error');
        }
    },

    /**
     * Handle edit evidence form submission
     */
    async handleEditEvidence(e) {
        e.preventDefault();

        const evidenceId = parseInt(document.getElementById('editEvId').value);
        const title = document.getElementById('editEvTitle').value.trim();
        const content = document.getElementById('editEvContent').value;
        const tags = document.getElementById('editEvTags').value.trim() || null;

        if (!title) {
            showToast('Title is required', 'error');
            return;
        }

        try {
            await API.evidence.update(evidenceId, { title, content, tags });
            showToast('Evidence updated', 'success');

            SlideOver.close('editEvidence');

            // Reload evidence
            if (this.selectedHostId) {
                await this.loadEvidenceForHost(this.selectedHostId);
            }
        } catch (error) {
            console.error('Failed to update evidence:', error);
            showToast('Failed to update evidence: ' + error.message, 'error');
        }
    },

    // ============================================
    // NOTES FUNCTIONS
    // ============================================

    /**
     * Load notes for a host
     */
    async loadNotes(hostId) {
        const container = document.getElementById('notesList');
        if (!container) return;

        // Lazily build a NotesTreeView for this host scope. Tree handles
        // its own fetching, rendering, drag-drop, and toolbar wiring.
        if (!this._hostNotesTree && typeof NotesTreeView !== 'undefined') {
            this._hostNotesTree = new NotesTreeView({
                containerId: 'notesList',
                toolbarId: 'hostNotesToolbar',
                editorPaneId: 'hostNotesEditorPane',
                api: API.hosts,
                apiNoun: 'host',
                scopeId: () => this.selectedHostId,
                editorReturnTab: 'notes',
                editorReturnHost: () => this.selectedHostId,
            });
        }
        if (this._hostNotesTree) {
            await this._hostNotesTree.refresh();
        }
    },

    /**
     * Extract plain-text first line for note list title (max 70 chars)
     */
    noteFirstLine(content) {
        if (!content) return 'Untitled note';
        const first = content.split('\n').find(l => l.trim()) || '';
        const plain = first.replace(/^#{1,6}\s+/, '').replace(/\*{1,2}(.+?)\*{1,2}/g, '$1').trim();
        if (!plain) return 'Untitled note';
        return escapeHtml(plain.length > 70 ? plain.substring(0, 70) + '…' : plain);
    },

    /**
     * Strip markdown and return full plain-text preview. The preview block is
     * height-capped + scrollable in CSS, so we render the entire note.
     */
    notePreviewText(content) {
        if (!content) return '';
        const plain = content
            .replace(/!\[.*?\]\(data:[^)]+\)/g, '[image]')
            .replace(/!\[.*?\]\(.*?\)/g, '[image]')
            .replace(/\[(.+?)\]\(.*?\)/g, '$1')
            .replace(/#{1,6}\s+/g, '')
            .replace(/\*{1,2}(.+?)\*{1,2}/g, '$1')
            .replace(/`{1,3}[^`\n]+`{1,3}/g, '')
            .replace(/^\s*[-*+]\s+/gm, '• ')
            .replace(/^\s*\d+\.\s+/gm, '')
            .replace(/>\s*/g, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
        return escapeHtml(plain);
    },

    /**
     * Render notes list
     */
    renderNotes() {
        const container = document.getElementById('notesList');
        if (!container) return;

        if (this.currentNotes.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No notes yet</p></div>';
            return;
        }

        container.innerHTML = this.currentNotes.map(note => {
            const source = note.content !== undefined ? note.content : note.content_preview;
            const preview = this.notePreviewText(source);
            const showMore = note.has_more && note.content === undefined
                ? `<button class="btn btn-sm btn-link note-show-more" ${on('click', 'HostManager.expandNote', note.id)}>Show full note</button>`
                : '';
            return `
            <div class="note-list-item" data-id="${note.id}">
                <div class="note-list-item-header">
                    <span class="note-list-item-icon"><i data-lucide="file-text"></i></span>
                    <span class="note-list-item-title">${this.noteFirstLine(source)}</span>
                    <span class="note-list-item-meta">${timeSince(note.created_at)}</span>
                    <div class="note-list-item-actions">
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editNote', note.id)} title="Edit"><i data-lucide="pencil"></i></button>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteNote', note.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                    </div>
                </div>
                ${preview ? `<div class="note-list-item-preview" data-note-preview="${note.id}">${preview}</div>` : ''}
                ${showMore}
            </div>
        `;
        }).join('');
    },

    /**
     * Lazy-fetch the full body of a host note and replace the preview block.
     * Caches the result on the in-memory note so re-expand is a no-op.
     */
    async expandNote(noteId) {
        const note = this.currentNotes.find(n => n.id === noteId);
        if (!note) return;
        try {
            if (note.content === undefined) {
                const full = await API.hosts.getNote(this.selectedHostId, noteId);
                note.content = full.content || '';
            }
            this.renderNotes();
        } catch (error) {
            console.error('Failed to load full note:', error);
            showToast('Failed to load full note', 'error');
        }
    },

    /**
     * Navigate to add note page
     */
    showAddNote() {
        // Navigate to the note editor page with host_id parameter and return context
        window.location.href = `/note/new?host_id=${this.selectedHostId}&type=host&return_host=${this.selectedHostId}&return_tab=notes`;
    },

    /**
     * Setup paste event listener for image clipboard support
     */
    setupPasteListener(textareaId, previewId) {
        const textarea = document.getElementById(textareaId);
        if (!textarea || textarea.dataset.pasteSetup) return;

        textarea.dataset.pasteSetup = 'true';
        textarea.addEventListener('paste', (e) => {
            const items = e.clipboardData?.items;
            if (!items) return;

            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        this.insertImageFromFile(file, textareaId, previewId);
                    }
                    break;
                }
            }
        });
    },

    /**
     * Insert image from file (used by both paste and file upload)
     */
    insertImageFromFile(file, textareaId, previewId) {
        const textarea = document.getElementById(textareaId);
        if (!textarea) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const base64 = e.target.result;
            const altText = file.name ? file.name.replace(/\.[^/.]+$/, '') : 'screenshot';
            const markdown = `\n![${altText}](${base64})\n`;

            // Insert at cursor position
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = textarea.value;
            textarea.value = text.substring(0, start) + markdown + text.substring(end);

            // Move cursor after inserted image
            textarea.selectionStart = textarea.selectionEnd = start + markdown.length;
            textarea.focus();

            // Update preview
            this.updateNotePreview(textareaId, previewId);
        };
        reader.readAsDataURL(file);
    },

    /**
     * Handle add note form submission
     */
    async handleAddNote(e) {
        e.preventDefault();

        const content = document.getElementById('noteContent').value.trim();
        if (!content) {
            showToast('Note content is required', 'error');
            return;
        }

        try {
            await API.hosts.createNote(this.selectedHostId, content);
            showToast('Note added', 'success');
            closeModal('addNoteModal');
            await this.loadNotes(this.selectedHostId);
        } catch (error) {
            console.error('Failed to add note:', error);
            showToast('Failed to add note: ' + error.message, 'error');
        }
    },

    /**
     * Edit note
     */
    editNote(noteId) {
        window.location.href = `/note/new?host_id=${this.selectedHostId}&note_id=${noteId}&type=host&return_host=${this.selectedHostId}&return_tab=notes`;
    },

    /**
     * Delete note
     */
    async deleteNote(noteId) {
        if (!confirm('Delete this note?')) return;

        try {
            await API.hosts.deleteNote(this.selectedHostId, noteId);
            showToast('Note deleted', 'success');
            await this.loadNotes(this.selectedHostId);
        } catch (error) {
            console.error('Failed to delete note:', error);
            showToast('Failed to delete note: ' + error.message, 'error');
        }
    },

    /**
     * Update note preview (for markdown)
     */
    updateNotePreview(textareaId, previewId) {
        const textarea = document.getElementById(textareaId);
        const preview = document.getElementById(previewId);
        if (!textarea || !preview) return;

        const content = textarea.value;
        preview.innerHTML = renderMarkdown(content);
    },

    /**
     * Handle image upload for note (file input)
     */
    handleNoteImage(inputId, textareaId) {
        const input = document.getElementById(inputId);
        if (!input || !input.files[0]) return;

        const previewId = textareaId.replace('Content', 'Preview');
        this.insertImageFromFile(input.files[0], textareaId, previewId);

        // Clear input for next upload
        input.value = '';
    },

    // ============================================
    // PORTS FUNCTIONS
    // ============================================

    /**
     * Load ports for a host
     */
    async loadPorts(hostId) {
        const container = document.getElementById('portsTableBody');
        if (!container) return;

        try {
            const data = await API.hosts.getPorts(hostId);
            this.currentPorts = data.ports || [];
            this.renderPorts();
        } catch (error) {
            console.error('Failed to load ports:', error);
            this.currentPorts = [];
            this.renderPorts();
        }
    },

    /**
     * Render ports table
     */
    renderPorts() {
        const container = document.getElementById('portsTableBody');
        if (!container) return;

        if (this.currentPorts.length === 0) {
            container.innerHTML = '<tr><td colspan="7" class="empty-cell">No ports discovered</td></tr>';
            return;
        }

        container.innerHTML = this.currentPorts.map(port => `
            <tr data-id="${port.id}">
                <td>${escapeHtml(port.port)}</td>
                <td>${escapeHtml(port.protocol)}</td>
                <td>${escapeHtml(port.service || '-')}</td>
                <td>${escapeHtml(port.version || '-')}</td>
                <td><span class="state-badge state-${escapeHtml(port.state)}">${escapeHtml(port.state)}</span></td>
                <td><span class="source-badge source-${escapeHtml(port.source)}">${escapeHtml(port.source)}</span></td>
                <td>
                    <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editPort', port.id)} title="Edit"><i data-lucide="pencil"></i></button>
                    <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deletePort', port.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                </td>
            </tr>
        `).join('');
    },

    /**
     * Show add port modal
     */
    showAddPort() {
        document.getElementById('addPortForm').reset();
        openModal('addPortModal');
    },

    /**
     * Handle add port form submission
     */
    async handleAddPort(e) {
        e.preventDefault();

        const portData = {
            port: parseInt(document.getElementById('newPortNumber').value),
            protocol: document.getElementById('newPortProtocol').value,
            state: document.getElementById('newPortState').value,
            service: document.getElementById('newPortService').value.trim() || null,
            version: document.getElementById('newPortVersion').value.trim() || null
        };

        if (!portData.port || isNaN(portData.port)) {
            showToast('Port number is required', 'error');
            return;
        }

        try {
            await API.hosts.createPort(this.selectedHostId, portData);
            showToast('Port added', 'success');
            closeModal('addPortModal');
            await this.loadPorts(this.selectedHostId);
        } catch (error) {
            console.error('Failed to add port:', error);
            showToast('Failed to add port: ' + error.message, 'error');
        }
    },

    /**
     * Edit port
     */
    editPort(portId) {
        const port = this.currentPorts.find(p => p.id === portId);
        if (!port) return;

        document.getElementById('editPortId').value = port.id;
        document.getElementById('editPortNumber').value = port.port;
        document.getElementById('editPortProtocol').value = port.protocol;
        document.getElementById('editPortState').value = port.state;
        document.getElementById('editPortService').value = port.service || '';
        document.getElementById('editPortVersion').value = port.version || '';

        openModal('editPortModal');
    },

    /**
     * Handle edit port form submission
     */
    async handleEditPort(e) {
        e.preventDefault();

        const portId = parseInt(document.getElementById('editPortId').value);
        const updates = {
            state: document.getElementById('editPortState').value,
            service: document.getElementById('editPortService').value.trim() || null,
            version: document.getElementById('editPortVersion').value.trim() || null
        };

        try {
            await API.hosts.updatePort(this.selectedHostId, portId, updates);
            showToast('Port updated', 'success');
            closeModal('editPortModal');
            await this.loadPorts(this.selectedHostId);
        } catch (error) {
            console.error('Failed to update port:', error);
            showToast('Failed to update port: ' + error.message, 'error');
        }
    },

    /**
     * Delete port
     */
    async deletePort(portId) {
        if (!confirm('Delete this port entry?')) return;

        try {
            await API.hosts.deletePort(this.selectedHostId, portId);
            showToast('Port deleted', 'success');
            await this.loadPorts(this.selectedHostId);
        } catch (error) {
            console.error('Failed to delete port:', error);
            showToast('Failed to delete port: ' + error.message, 'error');
        }
    },

    // ============================================
    // CREDENTIALS FUNCTIONS
    // ============================================

    /**
     * Load credentials for a host
     */
    async loadCredentials(hostId) {
        const container = document.getElementById('credentialsTableBody');
        if (!container) return;

        try {
            const data = await API.hosts.getCredentials(hostId);
            this.currentCredentials = data.credentials || [];
            this.renderCredentials();
        } catch (error) {
            console.error('Failed to load credentials:', error);
            this.currentCredentials = [];
            this.renderCredentials();
        }
    },

    /**
     * Render credentials table
     */
    renderCredentials() {
        const container = document.getElementById('credentialsTableBody');
        if (!container) return;

        if (this.currentCredentials.length === 0) {
            container.innerHTML = '<tr><td colspan="6" class="empty-cell">No credentials found</td></tr>';
            return;
        }

        container.innerHTML = this.currentCredentials.map(cred => {
            // Secrets are not in the list (M-9); clicking the mask fetches one (audited).
            const masked = cred.has_secret
                ? `<span class="password-hidden" data-visible="false" data-cred-id="${Number(cred.id)}" ${on('click', 'HostManager.togglePassword', ARG.el)}>${'•'.repeat(8)}</span>`
                : '-';
            const passwordDisplay = cred.password_type === 'hash'
                ? `${masked} <span class="hash-badge">${escapeHtml(cred.hash_type || 'hash')}</span>`
                : masked;

            return `
                <tr data-id="${cred.id}">
                    <td>${escapeHtml(cred.username || '-')}</td>
                    <td>${passwordDisplay}</td>
                    <td>${escapeHtml(cred.password_type)}</td>
                    <td>${escapeHtml(cred.service || '-')}</td>
                    <td>${escapeHtml(truncate(cred.notes || '', 50))}</td>
                    <td>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editCredential', cred.id)} title="Edit"><i data-lucide="pencil"></i></button>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteCredential', cred.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                    </td>
                </tr>
            `;
        }).join('');
    },

    /**
     * Toggle password visibility
     */
    async togglePassword(el) {
        if (el.dataset.visible === 'false') {
            let secret;
            try {
                secret = (await API.hosts.getCredentialSecret(this.selectedHostId, Number(el.dataset.credId))).secret;
            } catch (error) {
                showToast('Cannot reveal credential: ' + error.message, 'error');
                return;
            }
            el.textContent = secret || '';
            el.dataset.visible = 'true';
            el.classList.remove('password-hidden');
            el.classList.add('password-visible');
        } else {
            el.textContent = '•'.repeat(8);
            el.dataset.visible = 'false';
            el.classList.remove('password-visible');
            el.classList.add('password-hidden');
        }
    },

    /**
     * Show add credential modal
     */
    showAddCredential() {
        document.getElementById('addCredentialForm').reset();
        this.toggleHashType('newCredPasswordType', 'newCredHashTypeGroup');
        openModal('addCredentialModal');
    },

    /**
     * Toggle hash type field visibility
     */
    toggleHashType(selectId, groupId) {
        const select = document.getElementById(selectId);
        const group = document.getElementById(groupId);
        if (!select || !group) return;

        group.style.display = select.value === 'hash' ? 'block' : 'none';
    },

    /**
     * Handle add credential form submission
     */
    async handleAddCredential(e) {
        e.preventDefault();

        const credData = {
            username: document.getElementById('newCredUsername').value.trim() || null,
            password: document.getElementById('newCredPassword').value || null,
            password_type: document.getElementById('newCredPasswordType').value,
            hash_type: document.getElementById('newCredHashType').value.trim() || null,
            service: document.getElementById('newCredService').value.trim() || null,
            notes: document.getElementById('newCredNotes').value.trim() || null
        };

        try {
            await API.hosts.createCredential(this.selectedHostId, credData);
            showToast('Credential added', 'success');
            closeModal('addCredentialModal');
            await this.loadCredentials(this.selectedHostId);
        } catch (error) {
            console.error('Failed to add credential:', error);
            showToast('Failed to add credential: ' + error.message, 'error');
        }
    },

    /**
     * Edit credential
     */
    editCredential(credId) {
        const cred = this.currentCredentials.find(c => c.id === credId);
        if (!cred) return;

        document.getElementById('editCredId').value = cred.id;
        document.getElementById('editCredUsername').value = cred.username || '';
        // The secret is not loaded; leaving the field empty keeps it.
        const editPassword = document.getElementById('editCredPassword');
        editPassword.value = '';
        editPassword.placeholder = cred.has_secret ? 'Leave blank to keep the current value' : '';
        document.getElementById('editCredPasswordType').value = cred.password_type;
        document.getElementById('editCredHashType').value = cred.hash_type || '';
        document.getElementById('editCredService').value = cred.service || '';
        document.getElementById('editCredNotes').value = cred.notes || '';

        this.toggleHashType('editCredPasswordType', 'editCredHashTypeGroup');
        openModal('editCredentialModal');
    },

    /**
     * Handle edit credential form submission
     */
    async handleEditCredential(e) {
        e.preventDefault();

        const credId = parseInt(document.getElementById('editCredId').value);
        const updates = {
            username: document.getElementById('editCredUsername').value.trim() || null,
            password_type: document.getElementById('editCredPasswordType').value,
            hash_type: document.getElementById('editCredHashType').value.trim() || null,
            service: document.getElementById('editCredService').value.trim() || null,
            notes: document.getElementById('editCredNotes').value.trim() || null
        };
        const newPassword = document.getElementById('editCredPassword').value;
        if (newPassword) updates.password = newPassword;

        try {
            await API.hosts.updateCredential(this.selectedHostId, credId, updates);
            showToast('Credential updated', 'success');
            closeModal('editCredentialModal');
            await this.loadCredentials(this.selectedHostId);
        } catch (error) {
            console.error('Failed to update credential:', error);
            showToast('Failed to update credential: ' + error.message, 'error');
        }
    },

    /**
     * Delete credential
     */
    async deleteCredential(credId) {
        if (!confirm('Delete this credential?')) return;

        try {
            await API.hosts.deleteCredential(this.selectedHostId, credId);
            showToast('Credential deleted', 'success');
            await this.loadCredentials(this.selectedHostId);
        } catch (error) {
            console.error('Failed to delete credential:', error);
            showToast('Failed to delete credential: ' + error.message, 'error');
        }
    },

    // ============================================
    // VULNERABILITIES FUNCTIONS
    // ============================================

    /**
     * Load vulnerabilities for a host from evidence metadata
     * Supports: Nessus, Nmap, and Burp Suite scan data
     */
    async loadVulnerabilities(hostId) {
        const container = document.getElementById('vulnerabilitiesList');
        if (!container) return;

        // Get the host IP to match in metadata
        const host = this.hosts.find(h => h.id === hostId);
        if (!host) {
            container.innerHTML = '<div class="empty-state"><p>No vulnerabilities found</p></div>';
            return;
        }

        // Extract vulnerabilities from all evidence metadata for this engagement
        const vulnerabilities = [];

        try {
            // Get all evidence for the engagement (not filtered by host)
            const allEvidence = await API.evidence.getAll({});

            for (const ev of allEvidence) {
                if (!ev.metadata) continue;

                let metadata;
                try {
                    metadata = typeof ev.metadata === 'string' ? JSON.parse(ev.metadata) : ev.metadata;
                } catch (e) {
                    continue;
                }

                const tool = (metadata.tool || '').toLowerCase();

                // Handle Nessus data (vulnerabilities per host)
                if (tool === 'nessus' && metadata.hosts && Array.isArray(metadata.hosts)) {
                    for (const metaHost of metadata.hosts) {
                        if (metaHost.ip === host.ip) {
                            if (metaHost.vulnerabilities && Array.isArray(metaHost.vulnerabilities)) {
                                for (const vuln of metaHost.vulnerabilities) {
                                    vulnerabilities.push({
                                        ...vuln,
                                        // Metadata never poses as an editable engagement finding (H-13)
                                        id: undefined,
                                        is_engagement_finding: false,
                                        source_tool: 'Nessus',
                                        evidence_id: ev.id,
                                        evidence_title: ev.title
                                    });
                                }
                            }
                        }
                    }
                }

                // Handle Nmap data (open ports as potential findings)
                if (tool === 'nmap' && metadata.hosts && Array.isArray(metadata.hosts)) {
                    for (const metaHost of metadata.hosts) {
                        if (metaHost.ip === host.ip) {
                            if (metaHost.open_ports && Array.isArray(metaHost.open_ports)) {
                                for (const port of metaHost.open_ports) {
                                    // Create a finding entry for each open port/service
                                    const serviceName = port.service || 'unknown';
                                    const version = [port.product, port.version, port.extrainfo]
                                        .filter(Boolean).join(' ');

                                    vulnerabilities.push({
                                        plugin_name: `Open Port: ${port.port}/${port.protocol} - ${serviceName}`,
                                        name: `${serviceName} service detected`,
                                        severity: 0, // Info level for open ports
                                        port: port.port,
                                        protocol: port.protocol,
                                        synopsis: version ? `Service: ${serviceName} (${version})` : `Service: ${serviceName}`,
                                        description: `Port ${port.port}/${port.protocol} is open with ${serviceName} service${version ? ': ' + version : ''}.`,
                                        source_tool: 'Nmap',
                                        evidence_id: ev.id,
                                        evidence_title: ev.title
                                    });
                                }
                            }
                        }
                    }
                }

                // Handle Burp Suite data (issues array at top level)
                if ((tool === 'burp_suite' || tool === 'burp') && metadata.issues && Array.isArray(metadata.issues)) {
                    for (const issue of metadata.issues) {
                        // Match by host - Burp stores full URL, we need to check if IP is in the host
                        const issueHost = issue.host || '';
                        const hostMatches = issueHost.includes(host.ip) ||
                                          (host.hostname && issueHost.includes(host.hostname));

                        if (hostMatches) {
                            // Convert Burp severity to numeric (High=3, Medium=2, Low=1, Information=0)
                            const severityMap = { 'High': 3, 'Medium': 2, 'Low': 1, 'Information': 0, 'Info': 0 };
                            const severity = severityMap[issue.severity] ?? 1;

                            vulnerabilities.push({
                                plugin_name: issue.name || 'Unknown Issue',
                                name: issue.name,
                                severity: severity,
                                port: this._extractPortFromUrl(issueHost),
                                protocol: 'tcp',
                                synopsis: issue.path ? `Path: ${issue.path}` : null,
                                description: issue.issue_detail || issue.issueDetail || '',
                                solution: issue.remediation || issue.remediationDetail || '',
                                confidence: issue.confidence,
                                location: issue.location,
                                source_tool: 'Burp Suite',
                                evidence_id: ev.id,
                                evidence_title: ev.title
                            });
                        }
                    }
                }
            }

            // Also fetch manually created engagement findings that match this host
            if (AppState.activeEngagement) {
                try {
                    const engagementFindings = await API.engagements.getFindings(AppState.activeEngagement.id);
                    const hostIp = (host.ip || '').trim().toLowerCase();
                    const hostHostname = (host.hostname || '').trim().toLowerCase();

                    for (const finding of engagementFindings) {
                        // Match by IP address or hostname (case-insensitive, trimmed)
                        const findingIp = (finding.ip_address || '').trim().toLowerCase();
                        const findingHostname = (finding.hostname || '').trim().toLowerCase();

                        const matchesIp = findingIp && hostIp && findingIp === hostIp;
                        const matchesHostname = findingHostname && hostHostname && findingHostname === hostHostname;

                        if (matchesIp || matchesHostname) {
                            // Convert criticality to numeric severity
                            const criticalityMap = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0 };
                            const severity = criticalityMap[finding.criticality] ?? 2;

                            vulnerabilities.push({
                                id: finding.id,
                                plugin_name: finding.title,
                                name: finding.title,
                                severity: severity,
                                description: finding.finding_content || '',
                                solution: finding.remediation_content || '',
                                cvss_base_score: finding.cvss_score,
                                source_tool: 'Manual',
                                is_engagement_finding: true,
                                include_in_report: finding.include_in_report
                            });
                        }
                    }
                } catch (e) {
                    console.error('Failed to load engagement findings:', e);
                }
            }

            // Sort by severity (Critical first)
            vulnerabilities.sort((a, b) => (b.severity || 0) - (a.severity || 0));

            this.currentVulnerabilities = vulnerabilities;
            this.vulnFilter = 'all';
            this.renderVulnerabilities();
        } catch (error) {
            console.error('Failed to load vulnerabilities:', error);
            this.currentVulnerabilities = [];
            this.renderVulnerabilities();
        }
    },

    /**
     * Extract port from URL (e.g., http://example.com:8080 -> 8080)
     */
    _extractPortFromUrl(url) {
        if (!url) return null;
        try {
            const match = url.match(/:(\d+)/);
            if (match) return match[1];
            if (url.startsWith('https://')) return '443';
            if (url.startsWith('http://')) return '80';
        } catch (e) {}
        return null;
    },

    /**
     * Render vulnerabilities list
     */
    renderVulnerabilities() {
        const container = document.getElementById('vulnerabilitiesList');
        if (!container) return;

        // Apply filter
        let filtered = this.currentVulnerabilities;
        if (this.vulnFilter !== 'all') {
            const severityMap = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0 };
            const targetSeverity = severityMap[this.vulnFilter];
            filtered = this.currentVulnerabilities.filter(v => v.severity === targetSeverity);
        }

        // Update filter button states
        document.querySelectorAll('.vuln-filter').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.severity === this.vulnFilter);
        });

        if (filtered.length === 0) {
            const noVulnsMsg = this.currentVulnerabilities.length === 0
                ? 'No findings found'
                : 'No findings match the current filter';
            container.innerHTML = `<div class="empty-state"><p>${noVulnsMsg}</p></div>`;
            return;
        }

        container.innerHTML = filtered.map((vuln, index) => {
            const severityName = this.getSeverityName(vuln.severity);
            const severityClass = severityName.toLowerCase();
            const cves = vuln.cves && vuln.cves.length > 0
                ? vuln.cves.map(cve => `<span class="cve-badge">${escapeHtml(cve)}</span>`).join('')
                : '';
            // Scan metadata is attacker-supplied: numbers are parsed, the class suffix is allow-listed (H-13)
            const score = Number.parseFloat(vuln.cvss_base_score);
            const cvssScore = Number.isFinite(score) && score >= 0 && score <= 10
                ? `<span class="cvss-score">CVSS: ${score.toFixed(1)}</span>` : '';
            const confidenceKey = String(vuln.confidence || '').toLowerCase();
            const confidence = vuln.confidence
                ? `<span class="confidence-badge${VULN_CONFIDENCE.includes(confidenceKey) ? ' confidence-' + confidenceKey : ''}">${escapeHtml(vuln.confidence)}</span>`
                : '';
            const port = vuln.port ? `${escapeHtml(vuln.port)}/${escapeHtml(vuln.protocol || 'tcp')}` : '';
            const toolBadge = `<span class="tool-badge tool-${vuln.source_tool.toLowerCase().replace(' ', '-')}">${escapeHtml(vuln.source_tool)}</span>`;

            return `
                <div class="vuln-card vuln-${severityClass}" data-index="${index}">
                    <div class="vuln-header">
                        <div class="vuln-severity">
                            <span class="severity-indicator severity-${severityClass}">${this.getSeverityIcon(vuln.severity)}</span>
                            <span class="severity-label">${severityName}</span>
                            ${toolBadge}
                        </div>
                        <div class="vuln-meta">
                            ${cvssScore}
                            ${confidence}
                            <span class="vuln-port">${port}</span>
                            ${vuln.is_engagement_finding && Number.isInteger(vuln.id) ? `<button class="btn-send-to-report"
                                    ${on('click', 'stopAndCall', ARG.event, 'HostManager.editEngagementFinding', vuln.id)}
                                    title="Edit Finding">
                                <i data-lucide="pencil"></i>
                            </button>` : ''}
                            <button class="btn-send-to-report"
                                    ${on('click', 'stopAndCall', ARG.event, 'HostManager.sendVulnToReport', index)}
                                    title="Send to Report">
                                <i data-lucide="file-plus-2"></i>
                            </button>
                        </div>
                    </div>
                    <div class="vuln-title">
                        <h5>${escapeHtml(vuln.plugin_name || vuln.name || 'Unknown Finding')}</h5>
                    </div>
                    <div class="vuln-details">
                        ${vuln.synopsis ? `<p class="vuln-synopsis">${escapeHtml(vuln.synopsis)}</p>` : ''}
                        ${vuln.location ? `<p class="vuln-location">Location: ${escapeHtml(vuln.location)}</p>` : ''}
                        <div class="vuln-cves">${cves}</div>
                    </div>
                    <details class="vuln-more">
                        <summary>More Details</summary>
                        <div class="vuln-description">
                            ${vuln.description ? `<p>${escapeHtml(vuln.description)}</p>` : ''}
                            ${vuln.solution ? `<div class="vuln-solution"><strong>Solution:</strong> ${escapeHtml(vuln.solution)}</div>` : ''}
                            ${vuln.plugin_output ? `<div class="vuln-output"><strong>Output:</strong><pre>${escapeHtml(vuln.plugin_output)}</pre></div>` : ''}
                            <div class="vuln-source">Source: ${escapeHtml(vuln.source_tool)}${vuln.evidence_title ? ' - ' + escapeHtml(vuln.evidence_title) : ''}</div>
                        </div>
                    </details>
                </div>
            `;
        }).join('');

        // Initialize lucide icons for the send-to-report buttons
        lucide.createIcons();
    },

    /**
     * Filter vulnerabilities by severity
     */
    filterVulnerabilities(severity) {
        this.vulnFilter = severity;
        this.renderVulnerabilities();
    },

    /**
     * Get severity name from numeric value
     */
    getSeverityName(severity) {
        const names = { 4: 'Critical', 3: 'High', 2: 'Medium', 1: 'Low', 0: 'Info' };
        return names[severity] || 'Unknown';
    },

    /**
     * Get severity icon
     */
    getSeverityIcon(severity) {
        // The label beside it and the card's colour carry severity; no decorative dot.
        return '';
    },

    /**
     * Send vulnerability finding to report builder
     */
    async sendVulnToReport(vulnIndex) {
        // Get the vulnerability from the filtered list
        let filtered = this.currentVulnerabilities;
        if (this.vulnFilter !== 'all') {
            const severityMap = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0 };
            const targetSeverity = severityMap[this.vulnFilter];
            filtered = this.currentVulnerabilities.filter(v => v.severity === targetSeverity);
        }

        const vuln = filtered[vulnIndex];
        if (!vuln) {
            showToast('Vulnerability not found', 'error');
            return;
        }

        // Check for active engagement
        if (!AppState.activeEngagement) {
            showToast('No active engagement selected', 'error');
            return;
        }

        // Get host info
        const host = this.hosts.find(h => h.id === this.selectedHostId);
        const ipAddress = host ? host.ip : '';
        const hostname = host ? (host.hostname || '') : '';

        // Map severity to criticality
        const criticalityMap = { 4: 'critical', 3: 'high', 2: 'medium', 1: 'low', 0: 'low' };
        const criticality = criticalityMap[vuln.severity] || 'medium';

        // Build markdown content
        const findingContent = this._buildFindingMarkdown(vuln);
        const remediationContent = this._buildRemediationMarkdown(vuln);

        const findingData = {
            title: vuln.plugin_name || vuln.name || 'Unknown Finding',
            ip_address: ipAddress || null,
            hostname: hostname || null,
            criticality: criticality,
            cvss_score: vuln.cvss_base_score ? parseFloat(vuln.cvss_base_score) : null,
            finding_content: findingContent,
            remediation_content: remediationContent,
            include_in_report: true
        };

        try {
            await API.engagements.createFinding(AppState.activeEngagement.id, findingData);
            showToast('Finding sent to report', 'success');
            // Refresh engagement findings if on General tab
            if (this.selectedHostId === 'general' && this.currentGeneralTab === 'findings') {
                await this.loadEngagementFindings();
            }
        } catch (error) {
            console.error('Failed to send finding to report:', error);
            showToast('Failed to send finding: ' + error.message, 'error');
        }
    },

    /**
     * Build finding markdown from vulnerability data
     */
    _buildFindingMarkdown(vuln) {
        // Scanner text quotes target responses, so it is attacker-influenced (H-9):
        // markup and backticks are escaped so it shows as text, and tool output is
        // fenced with more backticks than it contains so it cannot close the fence.
        const text = value => escapeHtml(value);
        const sections = [];

        // Summary section
        if (vuln.synopsis) {
            sections.push(`## Summary\n${text(vuln.synopsis)}`);
        }

        // Description section
        if (vuln.description) {
            sections.push(`## Description\n${text(vuln.description)}`);
        }

        // Technical details section
        const details = [];
        if (vuln.port) {
            details.push(`- **Port**: ${text(vuln.port)}/${text(vuln.protocol || 'tcp')}`);
        }
        if (vuln.location) {
            details.push(`- **Location**: ${text(vuln.location)}`);
        }
        if (vuln.source_tool) {
            details.push(`- **Detected By**: ${text(vuln.source_tool)}`);
        }
        if (details.length > 0) {
            sections.push(`## Technical Details\n${details.join('\n')}`);
        }

        // CVE References section
        if (vuln.cves && vuln.cves.length > 0) {
            const cveLinks = vuln.cves.map(cve => /^CVE-\d{4}-\d{4,}$/i.test(String(cve))
                ? `- [${cve}](https://nvd.nist.gov/vuln/detail/${cve})`
                : `- ${text(cve)}`
            ).join('\n');
            sections.push(`## CVE References\n${cveLinks}`);
        }

        // Tool output section
        if (vuln.plugin_output) {
            const output = String(vuln.plugin_output);
            const longestRun = Math.max(0, ...(output.match(/`+/g) || []).map(run => run.length));
            const fence = '`'.repeat(Math.max(3, longestRun + 1));
            sections.push(`## Tool Output\n${fence}\n${output}\n${fence}`);
        }

        return sections.join('\n\n');
    },

    /**
     * Build remediation markdown from vulnerability data
     */
    _buildRemediationMarkdown(vuln) {
        if (vuln.solution) {
            return escapeHtml(vuln.solution);   // scanner text, shown as text (H-9)
        }
        return '';
    },

    // ============================================
    // PORT GRID FUNCTIONS
    // ============================================

    /**
     * Show port grid modal
     */
    async showPortGrid() {
        const container = document.getElementById('portGridContainer');
        if (!container) return;

        container.innerHTML = '<div class="loading">Loading port data...</div>';
        openModal('portGridModal');

        try {
            // Use bulk API endpoint for better performance
            const portData = await API.hosts.getPortGrid();
            this.renderPortGrid(portData);
        } catch (error) {
            console.error('Failed to load port grid:', error);
            container.innerHTML = '<div class="empty-state"><p>Failed to load port data</p></div>';
        }
    },

    /**
     * Collect port data from all hosts
     */
    async collectAllPortData() {
        const hosts = this.hosts;
        const portMap = {}; // port -> { service, hosts: { hostId: state } }
        const hostList = [];

        for (const host of hosts) {
            hostList.push({ id: host.id, ip: host.ip, hostname: host.hostname });

            try {
                const data = await API.hosts.getPorts(host.id);
                const ports = data.ports || [];

                for (const port of ports) {
                    const portKey = `${port.port}/${port.protocol}`;

                    if (!portMap[portKey]) {
                        portMap[portKey] = {
                            port: port.port,
                            protocol: port.protocol,
                            service: port.service || '',
                            hosts: {}
                        };
                    }

                    portMap[portKey].hosts[host.id] = port.state;

                    // Update service name if we have a better one
                    if (port.service && !portMap[portKey].service) {
                        portMap[portKey].service = port.service;
                    }
                }
            } catch (error) {
                console.error(`Failed to load ports for host ${host.id}:`, error);
            }
        }

        // Sort ports by port number
        const sortedPorts = Object.values(portMap).sort((a, b) => a.port - b.port);

        return { hosts: hostList, ports: sortedPorts };
    },

    /**
     * Render port grid table
     */
    renderPortGrid(data) {
        const container = document.getElementById('portGridContainer');
        if (!container) return;

        const { hosts, ports } = data;

        if (hosts.length === 0 || ports.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No port data available</p></div>';
            return;
        }

        // Build table HTML
        let html = '<div class="port-grid-wrapper"><table class="port-grid-table">';

        // Header row - port numbers with service names
        html += '<thead><tr><th class="host-column">Host</th>';
        for (const port of ports) {
            const serviceName = port.service ? `<br><span class="port-service">${escapeHtml(port.service)}</span>` : '';
            html += `<th class="port-column">${escapeHtml(port.port)}/${escapeHtml(port.protocol)}${serviceName}</th>`;
        }
        html += '</tr></thead>';

        // Data rows - one per host
        html += '<tbody>';
        for (const host of hosts) {
            html += `<tr>`;
            html += `<td class="host-column"><span class="host-ip">${escapeHtml(host.ip)}</span>`;
            if (host.hostname) {
                html += `<br><span class="host-hostname">${escapeHtml(host.hostname)}</span>`;
            }
            html += '</td>';

            for (const port of ports) {
                const state = port.hosts[host.id];
                if (state === 'open') {
                    html += '<td class="port-cell"><span class="port-dot port-open" title="Open"></span></td>';
                } else if (state === 'filtered') {
                    html += '<td class="port-cell"><span class="port-dot port-filtered" title="Filtered"></span></td>';
                } else {
                    html += '<td class="port-cell"></td>';
                }
            }
            html += '</tr>';
        }
        html += '</tbody></table></div>';

        container.innerHTML = html;
    },

    /**
     * Load port grid page (full page version)
     */
    async loadPortGridPage() {
        const container = document.getElementById('portGridPageContainer');
        if (!container) return;

        container.innerHTML = '<div class="loading">Loading port data...</div>';

        try {
            // Use bulk API endpoint for better performance (single request instead of N requests)
            const portData = await API.hosts.getPortGrid();
            this.portGridData = portData;  // Cache for filtering
            this.portGridFilter = null;    // Reset filter on reload
            this.renderPortGridPage(portData);
        } catch (error) {
            console.error('Failed to load port grid:', error);
            container.innerHTML = '<div class="empty-state"><p>Failed to load port data</p></div>';
        }
    },

    /**
     * Render port grid table for page view
     */
    renderPortGridPage(data) {
        const container = document.getElementById('portGridPageContainer');
        if (!container) return;

        const { hosts, ports } = data;

        if (hosts.length === 0 || ports.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No port data available</p></div>';
            return;
        }

        // Filter hosts if a port filter is active
        let filteredHosts = hosts;
        if (this.portGridFilter) {
            const filterPort = ports.find(p =>
                p.port === this.portGridFilter.port &&
                p.protocol === this.portGridFilter.protocol
            );
            if (filterPort) {
                filteredHosts = hosts.filter(host => filterPort.hosts[host.id] === 'open');
            }
        }

        // Build table HTML
        let html = '';

        // Filter status indicator
        if (this.portGridFilter) {
            html += `<div class="port-filter-status">
                Showing ${filteredHosts.length} host${filteredHosts.length !== 1 ? 's' : ''} with port ${escapeHtml(this.portGridFilter.port)}/${escapeHtml(this.portGridFilter.protocol)} open
                <button class="btn-text-sm" ${on('click', 'HostManager.clearPortFilter')}>Clear filter</button>
            </div>`;
        }

        html += '<div class="port-grid-wrapper"><table class="port-grid-table">';

        // Header row - port numbers with service names (clickable for filtering)
        html += '<thead><tr><th class="host-column">Host</th>';
        for (const port of ports) {
            const isActive = this.portGridFilter &&
                this.portGridFilter.port === port.port &&
                this.portGridFilter.protocol === port.protocol;
            const activeClass = isActive ? ' port-filter-active' : '';
            const serviceName = port.service ? `<br><span class="port-service">${escapeHtml(port.service)}</span>` : '';
            const portLabel = `${escapeHtml(port.port)}/${escapeHtml(port.protocol)}`;
            html += `<th class="port-column port-filter${activeClass}" data-action="toggle-port-filter" data-port="${escapeHtml(port.port)}" data-protocol="${escapeHtml(port.protocol)}" title="Click to filter by port ${portLabel}">${portLabel}${serviceName}</th>`;
        }
        html += '</tr></thead>';

        // Data rows - one per host
        html += '<tbody>';
        if (filteredHosts.length === 0) {
            html += `<tr><td colspan="${ports.length + 1}" class="empty-state">No hosts match the current filter</td></tr>`;
        } else {
            for (const host of filteredHosts) {
                html += `<tr>`;
                html += `<td class="host-column"><span class="host-ip host-link" ${on('click', 'HostManager.navigateToHostEvidence', host.id)} title="View evidence for ${escapeHtml(host.ip)}">${escapeHtml(host.ip)}</span>`;
                if (host.hostname) {
                    html += `<br><span class="host-hostname">${escapeHtml(host.hostname)}</span>`;
                }
                html += '</td>';

                for (const port of ports) {
                    const state = port.hosts[host.id];
                    if (state === 'open') {
                        html += '<td class="port-cell"><span class="port-dot port-open" title="Open"></span></td>';
                    } else if (state === 'filtered') {
                        html += '<td class="port-cell"><span class="port-dot port-filtered" title="Filtered"></span></td>';
                    } else {
                        html += '<td class="port-cell"></td>';
                    }
                }
                html += '</tr>';
            }
        }
        html += '</tbody></table></div>';

        container.innerHTML = html;
    },

    /**
     * Navigate to Evidence section and select a specific host
     */
    navigateToHostEvidence(hostId) {
        switchSection('hosts');
        this.selectHost(hostId);
    },

    /**
     * Toggle port filter in port grid
     */
    togglePortFilter(port, protocol) {
        // If already filtering by this port, clear filter
        if (this.portGridFilter &&
            this.portGridFilter.port === port &&
            this.portGridFilter.protocol === protocol) {
            this.portGridFilter = null;
        } else {
            this.portGridFilter = { port, protocol };
        }

        // Re-render with filter applied
        this.applyPortGridFilter();
    },

    /**
     * Clear port filter
     */
    clearPortFilter() {
        this.portGridFilter = null;
        this.applyPortGridFilter();
    },

    /**
     * Apply current port filter by re-rendering
     */
    applyPortGridFilter() {
        if (this.portGridData) {
            this.renderPortGridPage(this.portGridData);
        }
    },

    // ============================================
    // ENGAGEMENT NOTES FUNCTIONS (General section)
    // ============================================

    /**
     * Load engagement notes for the General section
     */
    async loadEngagementNotes() {
        const container = document.getElementById('engagementNotesList');
        if (!container || !AppState.activeEngagement) return;

        if (!this._engagementNotesTree && typeof NotesTreeView !== 'undefined') {
            this._engagementNotesTree = new NotesTreeView({
                containerId: 'engagementNotesList',
                toolbarId: 'engagementNotesToolbar',
                editorPaneId: 'engagementNotesEditorPane',
                api: API.engagements,
                apiNoun: 'engagement',
                scopeId: () => AppState.activeEngagement?.id ?? null,
                editorReturnTab: 'notes',
                editorReturnHost: 'general',
            });
        }
        if (this._engagementNotesTree) {
            await this._engagementNotesTree.refresh();
        }
    },

    /**
     * Render engagement notes list
     */
    renderEngagementNotes() {
        const container = document.getElementById('engagementNotesList');
        if (!container) return;

        if (this.engagementNotes.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No notes yet</p></div>';
            return;
        }

        container.innerHTML = this.engagementNotes.map(note => {
            const source = note.content !== undefined ? note.content : note.content_preview;
            const preview = this.notePreviewText(source);
            const showMore = note.has_more && note.content === undefined
                ? `<button class="btn btn-sm btn-link note-show-more" ${on('click', 'HostManager.expandEngagementNote', note.id)}>Show full note</button>`
                : '';
            return `
            <div class="note-list-item" data-id="${note.id}">
                <div class="note-list-item-header">
                    <span class="note-list-item-icon"><i data-lucide="file-text"></i></span>
                    <span class="note-list-item-title">${this.noteFirstLine(source)}</span>
                    <span class="note-list-item-meta">${timeSince(note.created_at)}</span>
                    <div class="note-list-item-actions">
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editEngagementNote', note.id)} title="Edit"><i data-lucide="pencil"></i></button>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteEngagementNote', note.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                    </div>
                </div>
                ${preview ? `<div class="note-list-item-preview" data-note-preview="${note.id}">${preview}</div>` : ''}
                ${showMore}
            </div>
        `;
        }).join('');
    },

    /**
     * Lazy-fetch the full body of an engagement note and replace the preview.
     */
    async expandEngagementNote(noteId) {
        const note = this.engagementNotes.find(n => n.id === noteId);
        if (!note || !AppState.activeEngagement) return;
        try {
            if (note.content === undefined) {
                const full = await API.engagements.getNote(AppState.activeEngagement.id, noteId);
                note.content = full.content || '';
            }
            this.renderEngagementNotes();
        } catch (error) {
            console.error('Failed to load full engagement note:', error);
            showToast('Failed to load full note', 'error');
        }
    },

    /**
     * Navigate to add engagement note page
     */
    showAddEngagementNote() {
        // Navigate to the note editor page for engagement notes with return context
        window.location.href = '/note/new?type=engagement&return_host=general&return_tab=notes';
    },

    /**
     * Handle add engagement note form submission
     */
    async handleAddEngagementNote(e) {
        e.preventDefault();

        const content = document.getElementById('engagementNoteContent').value.trim();
        if (!content) {
            showToast('Note content is required', 'error');
            return;
        }

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.createNote(AppState.activeEngagement.id, content);
            showToast('Note added', 'success');
            closeModal('addEngagementNoteModal');
            await this.loadEngagementNotes();
        } catch (error) {
            console.error('Failed to add engagement note:', error);
            showToast('Failed to add note: ' + error.message, 'error');
        }
    },

    /**
     * Edit engagement note
     */
    editEngagementNote(noteId) {
        window.location.href = `/note/new?type=engagement&note_id=${noteId}&return_host=general&return_tab=notes`;
    },

    /**
     * Delete engagement note
     */
    async deleteEngagementNote(noteId) {
        if (!confirm('Delete this note?')) return;

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.deleteNote(AppState.activeEngagement.id, noteId);
            showToast('Note deleted', 'success');
            await this.loadEngagementNotes();
        } catch (error) {
            console.error('Failed to delete engagement note:', error);
            showToast('Failed to delete note: ' + error.message, 'error');
        }
    },

    /**
     * Update engagement note preview (for markdown)
     */
    updateEngagementNotePreview(textareaId, previewId) {
        this.updateNotePreview(textareaId, previewId);
    },

    // ============================================
    // ENGAGEMENT CREDENTIALS FUNCTIONS (General section)
    // ============================================

    /**
     * Load engagement credentials for the General section
     */
    async loadEngagementCredentials() {
        const container = document.getElementById('engagementCredentialsTableBody');
        if (!container || !AppState.activeEngagement) return;

        try {
            const credentials = await API.engagements.getCredentials(AppState.activeEngagement.id);
            this.engagementCredentials = credentials || [];
            this.renderEngagementCredentials();
        } catch (error) {
            console.error('Failed to load engagement credentials:', error);
            this.engagementCredentials = [];
            this.renderEngagementCredentials();
        }
    },

    /**
     * Render engagement credentials table
     */
    renderEngagementCredentials() {
        const container = document.getElementById('engagementCredentialsTableBody');
        if (!container) return;

        if (this.engagementCredentials.length === 0) {
            container.innerHTML = '<tr><td colspan="5" class="empty-cell">No credentials found</td></tr>';
            return;
        }

        const typeLabels = {
            'clear_text': 'Clear Text',
            'ntlm': 'NTLM',
            'ntlmv2': 'NTLMv2',
            'krbtgt': 'KRBTGT',
            'md5': 'MD5',
            'sha': 'SHA'
        };

        container.innerHTML = this.engagementCredentials.map(cred => {
            // Known types only in the class; an unknown stored type is shown escaped (H-17).
            const known = Object.hasOwn(typeLabels, cred.credential_type);
            const typeLabel = known ? typeLabels[cred.credential_type] : escapeHtml(cred.credential_type || '');
            const typeClass = known ? cred.credential_type : 'clear_text';

            return `
                <tr data-id="${cred.id}">
                    <td>${escapeHtml(cred.username || '-')}</td>
                    <td>${cred.has_secret
                        ? `<span class="password-hidden" data-visible="false" data-cred-id="${Number(cred.id)}" ${on('click', 'HostManager.toggleEngagementCredPassword', ARG.el)}>${'•'.repeat(8)}</span>`
                        : '-'}</td>
                    <td><span class="credential-type-badge type-${typeClass}">${typeLabel}</span></td>
                    <td>${escapeHtml(truncate(cred.description || '', 80))}</td>
                    <td>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editEngagementCredential', cred.id)} title="Edit"><i data-lucide="pencil"></i></button>
                        <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteEngagementCredential', cred.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                    </td>
                </tr>
            `;
        }).join('');
    },

    /**
     * Toggle engagement credential password visibility
     */
    async toggleEngagementCredPassword(el) {
        if (el.dataset.visible === 'false') {
            if (!AppState.activeEngagement) return;
            let secret;
            try {
                secret = (await API.engagements.getCredentialSecret(
                    AppState.activeEngagement.id, Number(el.dataset.credId))).secret;
            } catch (error) {
                showToast('Cannot reveal credential: ' + error.message, 'error');
                return;
            }
            el.textContent = secret || '';
            el.dataset.visible = 'true';
            el.classList.remove('password-hidden');
            el.classList.add('password-visible');
        } else {
            el.textContent = '•'.repeat(8);
            el.dataset.visible = 'false';
            el.classList.remove('password-visible');
            el.classList.add('password-hidden');
        }
    },

    /**
     * Show add engagement credential modal
     */
    showAddEngagementCredential() {
        document.getElementById('addEngagementCredentialForm').reset();
        openModal('addEngagementCredentialModal');
    },

    /**
     * Handle add engagement credential form submission
     */
    async handleAddEngagementCredential(e) {
        e.preventDefault();

        const credData = {
            username: document.getElementById('engCredUsername').value.trim() || null,
            password_or_hash: document.getElementById('engCredPasswordOrHash').value || null,
            credential_type: document.getElementById('engCredType').value,
            description: document.getElementById('engCredDescription').value.trim() || null
        };

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.createCredential(AppState.activeEngagement.id, credData);
            showToast('Credential added', 'success');
            closeModal('addEngagementCredentialModal');
            await this.loadEngagementCredentials();
        } catch (error) {
            console.error('Failed to add engagement credential:', error);
            showToast('Failed to add credential: ' + error.message, 'error');
        }
    },

    /**
     * Edit engagement credential
     */
    editEngagementCredential(credId) {
        const cred = this.engagementCredentials.find(c => c.id === credId);
        if (!cred) return;

        document.getElementById('editEngCredId').value = cred.id;
        document.getElementById('editEngCredUsername').value = cred.username || '';
        // The secret is not loaded; leaving the field empty keeps it.
        const editSecret = document.getElementById('editEngCredPasswordOrHash');
        editSecret.value = '';
        editSecret.placeholder = cred.has_secret ? 'Leave blank to keep the current value' : '';
        document.getElementById('editEngCredType').value = cred.credential_type || 'clear_text';
        document.getElementById('editEngCredDescription').value = cred.description || '';

        openModal('editEngagementCredentialModal');
    },

    /**
     * Handle edit engagement credential form submission
     */
    async handleEditEngagementCredential(e) {
        e.preventDefault();

        const credId = parseInt(document.getElementById('editEngCredId').value);
        const updates = {
            username: document.getElementById('editEngCredUsername').value.trim() || null,
            credential_type: document.getElementById('editEngCredType').value,
            description: document.getElementById('editEngCredDescription').value.trim() || null
        };
        const newSecret = document.getElementById('editEngCredPasswordOrHash').value;
        if (newSecret) updates.password_or_hash = newSecret;

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.updateCredential(AppState.activeEngagement.id, credId, updates);
            showToast('Credential updated', 'success');
            closeModal('editEngagementCredentialModal');
            await this.loadEngagementCredentials();
        } catch (error) {
            console.error('Failed to update engagement credential:', error);
            showToast('Failed to update credential: ' + error.message, 'error');
        }
    },

    /**
     * Delete engagement credential
     */
    async deleteEngagementCredential(credId) {
        if (!confirm('Delete this credential?')) return;

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.deleteCredential(AppState.activeEngagement.id, credId);
            showToast('Credential deleted', 'success');
            await this.loadEngagementCredentials();
        } catch (error) {
            console.error('Failed to delete engagement credential:', error);
            showToast('Failed to delete credential: ' + error.message, 'error');
        }
    },

    // ============================================
    // TERMINAL DUMPS FUNCTIONS (General section)
    // ============================================

    /**
     * Load terminal dumps for the General section
     */
    async loadTerminalDumps() {
        const container = document.getElementById('terminalDumpsList');
        if (!container || !AppState.activeEngagement) return;

        try {
            const dumps = await API.engagements.getTerminalDumps(AppState.activeEngagement.id);
            this.terminalDumps = dumps || [];
            this.renderTerminalDumps();
        } catch (error) {
            console.error('Failed to load terminal dumps:', error);
            this.terminalDumps = [];
            this.renderTerminalDumps();
        }
    },

    /**
     * Render terminal dumps list
     */
    renderTerminalDumps() {
        const container = document.getElementById('terminalDumpsList');
        if (!container) return;

        if (this.terminalDumps.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No terminal dumps yet</p></div>';
            return;
        }

        container.innerHTML = this.terminalDumps.map(dump => {
            const sessionTime = dump.session_datetime
                ? new Date(dump.session_datetime).toLocaleString()
                : 'No session time';
            const body = dump.content !== undefined ? dump.content : (dump.content_preview || '');
            const showMore = dump.has_more && dump.content === undefined
                ? `<button class="btn btn-sm btn-link" ${on('click', 'HostManager.expandTerminalDump', dump.id)}>Show full output</button>`
                : '';

            return `
                <div class="terminal-dump-card" data-id="${dump.id}">
                    <div class="terminal-dump-header">
                        <div class="terminal-dump-title">
                            <h5>${escapeHtml(dump.title)}</h5>
                            <span class="terminal-dump-datetime">${sessionTime}</span>
                        </div>
                        <div class="terminal-dump-actions">
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editTerminalDump', dump.id)} title="Edit"><i data-lucide="pencil"></i></button>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteTerminalDump', dump.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                        </div>
                    </div>
                    <div class="terminal-dump-content">
                        <pre>${escapeHtml(body)}</pre>
                    </div>
                    ${showMore}
                    <div class="terminal-dump-footer">
                        <span class="terminal-dump-meta">Added ${timeSince(dump.created_at)}</span>
                    </div>
                </div>
            `;
        }).join('');
    },

    /**
     * Lazy-fetch the full body of a terminal dump and re-render so the
     * content block shows the entire output.
     */
    async expandTerminalDump(dumpId) {
        const dump = this.terminalDumps.find(d => d.id === dumpId);
        if (!dump || !AppState.activeEngagement) return;
        try {
            if (dump.content === undefined) {
                const full = await API.engagements.getTerminalDump(AppState.activeEngagement.id, dumpId);
                dump.content = full.content || '';
            }
            this.renderTerminalDumps();
        } catch (error) {
            console.error('Failed to load full terminal dump:', error);
            showToast('Failed to load full output', 'error');
        }
    },

    /**
     * Show add terminal dump modal
     */
    showAddTerminalDump() {
        document.getElementById('addTerminalDumpForm').reset();
        // Set default session datetime to now
        const now = new Date();
        const localDatetime = now.toISOString().slice(0, 16);
        document.getElementById('dumpSessionDatetime').value = localDatetime;
        openModal('addTerminalDumpModal');
    },

    /**
     * Handle add terminal dump form submission
     */
    async handleAddTerminalDump(e) {
        e.preventDefault();

        const title = document.getElementById('dumpTitle').value.trim();
        const content = document.getElementById('dumpContent').value;
        const sessionDatetime = document.getElementById('dumpSessionDatetime').value || null;

        if (!title) {
            showToast('Title is required', 'error');
            return;
        }

        if (!content) {
            showToast('Terminal content is required', 'error');
            return;
        }

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        const dumpData = {
            title,
            content,
            session_datetime: sessionDatetime
        };

        try {
            await API.engagements.createTerminalDump(AppState.activeEngagement.id, dumpData);
            showToast('Terminal dump added', 'success');
            closeModal('addTerminalDumpModal');
            await this.loadTerminalDumps();
        } catch (error) {
            console.error('Failed to add terminal dump:', error);
            showToast('Failed to add terminal dump: ' + error.message, 'error');
        }
    },

    /**
     * Edit terminal dump
     */
    async editTerminalDump(dumpId) {
        const dump = this.terminalDumps.find(d => d.id === dumpId);
        if (!dump) return;

        // List response only carries content_preview; fetch the full body
        // before opening the edit modal so the textarea reflects the real note.
        if (dump.content === undefined && AppState.activeEngagement) {
            try {
                const full = await API.engagements.getTerminalDump(AppState.activeEngagement.id, dumpId);
                dump.content = full.content || '';
            } catch (error) {
                console.error('Failed to load terminal dump for editing:', error);
                showToast('Failed to load terminal dump', 'error');
                return;
            }
        }

        document.getElementById('editDumpId').value = dump.id;
        document.getElementById('editDumpTitle').value = dump.title;
        document.getElementById('editDumpContent').value = dump.content || '';

        // Format datetime for input
        if (dump.session_datetime) {
            const dt = new Date(dump.session_datetime);
            document.getElementById('editDumpSessionDatetime').value = dt.toISOString().slice(0, 16);
        } else {
            document.getElementById('editDumpSessionDatetime').value = '';
        }

        openModal('editTerminalDumpModal');
    },

    /**
     * Handle edit terminal dump form submission
     */
    async handleEditTerminalDump(e) {
        e.preventDefault();

        const dumpId = parseInt(document.getElementById('editDumpId').value);
        const title = document.getElementById('editDumpTitle').value.trim();
        const content = document.getElementById('editDumpContent').value;
        const sessionDatetime = document.getElementById('editDumpSessionDatetime').value || null;

        if (!title) {
            showToast('Title is required', 'error');
            return;
        }

        if (!content) {
            showToast('Terminal content is required', 'error');
            return;
        }

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        const updates = {
            title,
            content,
            session_datetime: sessionDatetime
        };

        try {
            await API.engagements.updateTerminalDump(AppState.activeEngagement.id, dumpId, updates);
            showToast('Terminal dump updated', 'success');
            closeModal('editTerminalDumpModal');
            await this.loadTerminalDumps();
        } catch (error) {
            console.error('Failed to update terminal dump:', error);
            showToast('Failed to update terminal dump: ' + error.message, 'error');
        }
    },

    /**
     * Delete terminal dump
     */
    async deleteTerminalDump(dumpId) {
        if (!confirm('Delete this terminal dump?')) return;

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.deleteTerminalDump(AppState.activeEngagement.id, dumpId);
            showToast('Terminal dump deleted', 'success');
            await this.loadTerminalDumps();
        } catch (error) {
            console.error('Failed to delete terminal dump:', error);
            showToast('Failed to delete terminal dump: ' + error.message, 'error');
        }
    },

    // ============================================
    // ENGAGEMENT FINDINGS FUNCTIONS (General section)
    // ============================================

    /**
     * Load engagement findings for the General section
     */
    async loadEngagementFindings() {
        const container = document.getElementById('engagementFindingsList');
        if (!container || !AppState.activeEngagement) return;

        try {
            const findings = await API.engagements.getFindings(AppState.activeEngagement.id);
            this.engagementFindings = findings || [];
            this.renderEngagementFindings();
        } catch (error) {
            console.error('Failed to load engagement findings:', error);
            this.engagementFindings = [];
            this.renderEngagementFindings();
        }
    },

    /**
     * Render engagement findings list
     */
    renderEngagementFindings() {
        const container = document.getElementById('engagementFindingsList');
        if (!container) return;

        if (this.engagementFindings.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No findings yet</p></div>';
            return;
        }

        const criticalityLabels = {
            'critical': { label: 'Critical', cardClass: 'criticality-critical', badgeClass: 'critical' },
            'high': { label: 'High', cardClass: 'criticality-high', badgeClass: 'high' },
            'medium': { label: 'Medium', cardClass: 'criticality-medium', badgeClass: 'medium' },
            'low': { label: 'Low', cardClass: 'criticality-low', badgeClass: 'low' }
        };

        container.innerHTML = this.engagementFindings.map(finding => {
            const crit = Object.hasOwn(criticalityLabels, finding.criticality)
                ? criticalityLabels[finding.criticality] : criticalityLabels['medium'];
            const cvss = Number.parseFloat(finding.cvss_score);
            const cvssDisplay = Number.isFinite(cvss) && cvss >= 0 && cvss <= 10 ? cvss.toFixed(1) : '-';
            const findingHtml = finding.finding_content ? renderMarkdown(finding.finding_content) : '<em>No description</em>';
            const remediationHtml = finding.remediation_content ? renderMarkdown(finding.remediation_content) : '<em>No remediation notes</em>';

            // Build host info display
            let hostInfo = '';
            if (finding.ip_address || finding.hostname) {
                const parts = [];
                if (finding.ip_address) parts.push(escapeHtml(finding.ip_address));
                if (finding.hostname) parts.push(escapeHtml(finding.hostname));
                hostInfo = `<span class="finding-host-info" title="Affected Host">${parts.join(' / ')}</span>`;
            }

            return `
                <div class="finding-card ${crit.cardClass}" data-id="${finding.id}">
                    <div class="finding-header">
                        <div class="finding-title-row">
                            <span class="criticality-badge ${crit.badgeClass}">${crit.label}</span>
                            <span class="finding-cvss" title="CVSS Score">CVSS: ${cvssDisplay}</span>
                            ${hostInfo}
                            <h5 class="finding-title">${escapeHtml(finding.title)}</h5>
                        </div>
                        <div class="finding-actions">
                            <label class="finding-report-toggle" title="Include in final report">
                                <input type="checkbox" ${finding.include_in_report ? 'checked' : ''} ${on('change', 'HostManager.toggleFindingReport', finding.id)}>
                                <span class="report-toggle-label">Report</span>
                            </label>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.saveToWriteups', finding.id)} title="Save to Writeups Database"><i data-lucide="book-plus"></i></button>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.editEngagementFinding', finding.id)} title="Edit"><i data-lucide="pencil"></i></button>
                            <button class="btn btn-sm btn-icon" ${on('click', 'HostManager.deleteEngagementFinding', finding.id)} title="Delete"><i data-lucide="trash-2"></i></button>
                        </div>
                    </div>
                    <div class="finding-body">
                        <div class="finding-section">
                            <h6>Finding</h6>
                            <div class="finding-content markdown-preview">${findingHtml}</div>
                        </div>
                        <div class="finding-section">
                            <h6>Remediation</h6>
                            <div class="finding-remediation markdown-preview">${remediationHtml}</div>
                        </div>
                    </div>
                    <div class="finding-footer">
                        <span class="finding-meta">Added ${timeSince(finding.created_at)}</span>
                    </div>
                </div>
            `;
        }).join('');
    },

    /**
     * Navigate to add finding page (General view)
     */
    showAddEngagementFinding() {
        const params = new URLSearchParams();
        params.set('return_host', 'general');
        params.set('return_tab', 'findings');
        window.location.href = '/finding/new?' + params.toString();
    },

    /**
     * Navigate to add finding page with host pre-populated
     */
    showAddHostFinding() {
        if (!this.selectedHostId || this.selectedHostId === 'general') {
            showToast('No host selected', 'error');
            return;
        }

        const host = this.hosts.find(h => h.id === this.selectedHostId);
        if (!host) {
            showToast('Host not found', 'error');
            return;
        }

        const params = new URLSearchParams();
        if (host.ip) params.set('host_ip', host.ip);
        if (host.hostname) params.set('host_hostname', host.hostname);
        params.set('return_host', this.selectedHostId);
        params.set('return_tab', 'findings');
        window.location.href = '/finding/new?' + params.toString();
    },

    /**
     * Navigate to edit finding page
     */
    editEngagementFinding(findingId) {
        const params = new URLSearchParams();
        params.set('finding_id', findingId);

        // Determine return context
        if (this.selectedHostId && this.selectedHostId !== 'general') {
            params.set('return_host', this.selectedHostId);
            params.set('return_tab', 'findings');
        } else {
            params.set('return_host', 'general');
            params.set('return_tab', 'findings');
        }

        window.location.href = '/finding/new?' + params.toString();
    },


    /**
     * Delete finding
     */
    async deleteEngagementFinding(findingId) {
        if (!confirm('Delete this finding?')) return;

        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.deleteFinding(AppState.activeEngagement.id, findingId);
            showToast('Finding deleted', 'success');
            await this.loadEngagementFindings();
        } catch (error) {
            console.error('Failed to delete finding:', error);
            showToast('Failed to delete finding: ' + error.message, 'error');
        }
    },

    /**
     * Toggle finding report inclusion
     */
    async toggleFindingReport(findingId) {
        if (!AppState.activeEngagement) {
            showToast('No active engagement', 'error');
            return;
        }

        try {
            await API.engagements.toggleFindingReport(AppState.activeEngagement.id, findingId);
            await this.loadEngagementFindings();
        } catch (error) {
            console.error('Failed to toggle finding report:', error);
            showToast('Failed to update finding: ' + error.message, 'error');
        }
    },

    /**
     * Save a finding to the Writeups Database
     * Shows warning modal then opens add writeup modal with prefilled data
     */
    saveToWriteups(findingId) {
        const finding = this.engagementFindings.find(f => f.id === findingId);
        if (!finding) {
            showToast('Finding not found', 'error');
            return;
        }

        // Prepare data for the writeup, mapping finding fields to writeup fields
        const writeupData = {
            name: finding.title,
            criticality: finding.criticality,
            cvss_score: finding.cvss_score,
            description: finding.finding_content,
            remediation: finding.remediation_content,
            category: '', // User can fill this in
            tags: ''      // User can fill this in
        };

        // Show the sensitive warning modal
        if (typeof ReportingManager !== 'undefined') {
            ReportingManager.showSensitiveWarningModal(writeupData);
        } else {
            showToast('Reporting module not loaded', 'error');
        }
    },

    /**
     * Update finding/remediation markdown preview
     */
    updateFindingPreview(textareaId, previewId) {
        const textarea = document.getElementById(textareaId);
        const preview = document.getElementById(previewId);
        if (!textarea || !preview) return;

        const content = textarea.value;
        preview.innerHTML = renderMarkdown(content);
    },

    // ============================================
    // HOST INDICATORS FEATURE
    // ============================================

    /**
     * Render indicator badges for a host in the host list
     */
    renderIndicatorBadges(host) {
        const indicators = [];
        const iconMap = {
            rooted: 'hash',
            shell: 'terminal',
            interested: 'star',
            not_interested: 'x-circle',
            out_of_scope: 'ban',
            flagged: 'flag',
            reviewed: 'check-circle'
        };

        for (const [key, icon] of Object.entries(iconMap)) {
            if (host[key]) {
                indicators.push(`<span class="host-indicator-badge" title="${key.replace('_', ' ')}"><i data-lucide="${icon}"></i></span>`);
            }
        }

        if (indicators.length === 0) return '';
        return `<div class="host-indicators">${indicators.join('')}</div>`;
    },

    /**
     * Populate indicator checkboxes when a host is selected
     */
    populateIndicators() {
        if (!this.selectedHostId || this.selectedHostId === 'general') return;

        const host = this.hosts.find(h => h.id === this.selectedHostId);
        if (!host) return;

        // Set checkbox states
        const indicators = ['rooted', 'shell', 'interested', 'not_interested', 'out_of_scope', 'flagged', 'reviewed'];
        indicators.forEach(indicator => {
            const checkbox = document.getElementById(`indicator-${indicator.replace('_', '-')}`);
            if (checkbox) {
                checkbox.checked = host[indicator] || false;
            }
        });

        // Set color category active state
        document.querySelectorAll('.color-option').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.color === host.color_category);
        });
    },

    /**
     * Update an indicator for the current host
     */
    async updateIndicator(indicator, value) {
        if (!this.selectedHostId || this.selectedHostId === 'general') return;

        try {
            const updateData = {};
            updateData[indicator] = value;

            await API.hosts.update(this.selectedHostId, updateData);

            // Update local cache
            const host = this.hosts.find(h => h.id === this.selectedHostId);
            if (host) {
                host[indicator] = value;
                this.renderHostList();
                // Re-initialize Lucide icons after re-render
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }
        } catch (error) {
            console.error('Failed to update indicator:', error);
            showMessage('Failed to update indicator', 'error');
        }
    },

    /**
     * Update color category for the current host
     */
    async updateColorCategory(color) {
        if (!this.selectedHostId || this.selectedHostId === 'general') return;

        try {
            await API.hosts.update(this.selectedHostId, { color_category: color });

            // Update local cache
            const host = this.hosts.find(h => h.id === this.selectedHostId);
            if (host) {
                host.color_category = color;
                this.renderHostList();
            }

            // Update active state
            document.querySelectorAll('.color-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.color === color);
            });
        } catch (error) {
            console.error('Failed to update color category:', error);
            showMessage('Failed to update color category', 'error');
        }
    },

    /**
     * Toggle filter panel visibility
     */
    toggleFilters() {
        const panel = document.getElementById('hostFiltersPanel');
        if (panel) {
            const isHidden = panel.style.display === 'none';
            panel.style.display = isHidden ? 'block' : 'none';

            // Re-initialize Lucide icons after showing
            if (isHidden && typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    /**
     * Validate and parse CIDR notation
     * Returns {network, mask, isValid} or null if invalid
     */
    parseCIDR(cidr) {
        cidr = cidr.trim();

        // Check if it's a single IP (no slash)
        if (!cidr.includes('/')) {
            // Validate single IP
            if (this.isValidIP(cidr)) {
                return {
                    network: cidr,
                    mask: 32,
                    isValid: true,
                    isSingleIP: true
                };
            }
            return { isValid: false, error: 'Invalid IP address' };
        }

        // Parse CIDR notation (e.g., 192.168.1.0/24)
        const parts = cidr.split('/');
        if (parts.length !== 2) {
            return { isValid: false, error: 'Invalid CIDR format. Use IP/mask (e.g., 192.168.1.0/24)' };
        }

        const [network, maskStr] = parts;
        const mask = parseInt(maskStr, 10);

        // Validate IP address
        if (!this.isValidIP(network)) {
            return { isValid: false, error: 'Invalid IP address in CIDR' };
        }

        // Validate mask (0-32)
        if (isNaN(mask) || mask < 0 || mask > 32) {
            return { isValid: false, error: 'Subnet mask must be between 0 and 32' };
        }

        return {
            network,
            mask,
            isValid: true,
            isSingleIP: false
        };
    },

    /**
     * Validate IPv4 address
     */
    isValidIP(ip) {
        const parts = ip.split('.');
        if (parts.length !== 4) return false;

        return parts.every(part => {
            const num = parseInt(part, 10);
            return !isNaN(num) && num >= 0 && num <= 255 && part === num.toString();
        });
    },

    /**
     * Convert IP address to 32-bit integer
     */
    ipToInt(ip) {
        const parts = ip.split('.');
        return (parseInt(parts[0]) << 24) +
               (parseInt(parts[1]) << 16) +
               (parseInt(parts[2]) << 8) +
               parseInt(parts[3]);
    },

    /**
     * Check if an IP is in a CIDR range
     */
    ipInCIDR(ip, cidrInfo) {
        if (!cidrInfo.isValid) return false;

        const ipInt = this.ipToInt(ip);
        const networkInt = this.ipToInt(cidrInfo.network);

        // If it's a single IP, do exact match
        if (cidrInfo.isSingleIP) {
            return ipInt === networkInt;
        }

        // Calculate network mask
        const mask = 0xFFFFFFFF << (32 - cidrInfo.mask);

        // Check if IP is in the network
        return (ipInt & mask) === (networkInt & mask);
    },

    /**
     * Handle CIDR filter input with validation
     */
    applyCIDRFilter() {
        const cidrInput = document.getElementById('filter-cidr');
        const cidrError = document.getElementById('cidr-error');

        if (!cidrInput || !cidrError) return;

        const cidr = cidrInput.value.trim();

        // Clear error if input is empty
        if (!cidr) {
            cidrError.style.display = 'none';
            cidrError.textContent = '';
            this.applyFilters();
            return;
        }

        // Validate CIDR
        const cidrInfo = this.parseCIDR(cidr);

        if (!cidrInfo.isValid) {
            cidrError.style.display = 'block';
            cidrError.textContent = cidrInfo.error || 'Invalid CIDR notation';
            return;
        }

        // Clear error and apply filter
        cidrError.style.display = 'none';
        cidrError.textContent = '';
        this.applyFilters();
    },

    /**
     * Apply filters to host list
     */
    applyFilters() {
        const activeFilters = [];
        const filterCheckboxes = {
            'filter-rooted': 'rooted',
            'filter-shell': 'shell',
            'filter-interested': 'interested',
            'filter-not-interested': 'not_interested',
            'filter-out-of-scope': 'out_of_scope',
            'filter-flagged': 'flagged',
            'filter-reviewed': 'reviewed',
            'filter-has-notes': 'has_notes',
            'filter-has-findings': 'has_findings'
        };

        // Collect active indicator filters
        for (const [checkboxId, indicator] of Object.entries(filterCheckboxes)) {
            const checkbox = document.getElementById(checkboxId);
            if (checkbox && checkbox.checked) {
                activeFilters.push(indicator);
            }
        }

        // Check for CIDR filter
        const cidrInput = document.getElementById('filter-cidr');
        const cidrValue = cidrInput ? cidrInput.value.trim() : '';
        let cidrInfo = null;
        if (cidrValue) {
            cidrInfo = this.parseCIDR(cidrValue);
            // Only use CIDR filter if valid
            if (!cidrInfo.isValid) {
                cidrInfo = null;
            }
        }

        const hasSeverityFilter = this.severityFilter !== null;
        const hasIndicatorFilters = activeFilters.length > 0;
        const hasCIDRFilter = cidrInfo !== null;
        const hasKeywordSearch = this.keywordSearchResults !== null;
        const hasColorFilter = this.colorFilters && this.colorFilters.size > 0;

        // Update clear button visibility
        this.updateClearButtonVisibility(hasSeverityFilter || hasIndicatorFilters || hasCIDRFilter || hasKeywordSearch || hasColorFilter);

        // Update stat item active states
        this.updateStatActiveStates();

        // Filter hosts
        const hostItems = document.querySelectorAll('.host-item[data-host-id]');
        hostItems.forEach(item => {
            const hostId = parseInt(item.dataset.hostId);
            if (isNaN(hostId)) return; // Skip non-numeric (like 'general')

            const host = this.hosts.find(h => h.id === hostId);
            if (!host) return;

            // If no search criteria active, show all hosts
            if (!hasSeverityFilter && !hasIndicatorFilters && !hasCIDRFilter && !hasKeywordSearch && !hasColorFilter) {
                item.style.display = '';
                return;
            }

            // Check indicator match (OR logic within indicators)
            let matchesIndicator = !hasIndicatorFilters;
            if (hasIndicatorFilters) {
                matchesIndicator = activeFilters.some(indicator => host[indicator]);
            }

            // Check severity match
            let matchesSeverity = !hasSeverityFilter;
            if (hasSeverityFilter) {
                const hostSeverity = this.hostSeverityMap[host.ip];
                matchesSeverity = hostSeverity && hostSeverity[this.severityFilter] > 0;
            }

            // Check CIDR match
            let matchesCIDR = !hasCIDRFilter;
            if (hasCIDRFilter && host.ip) {
                matchesCIDR = this.ipInCIDR(host.ip, cidrInfo);
            }

            // Check keyword search match
            let matchesKeyword = !hasKeywordSearch;
            if (hasKeywordSearch) {
                matchesKeyword = this.keywordSearchResults.has(hostId);
            }

            // Check color match (OR within selected colors)
            let matchesColor = !hasColorFilter;
            if (hasColorFilter) {
                matchesColor = host.color_category && this.colorFilters.has(host.color_category);
            }

            // Show host if it matches ALL active criteria (AND logic)
            item.style.display = (matchesIndicator && matchesSeverity && matchesCIDR && matchesKeyword && matchesColor) ? '' : 'none';
        });
    },

    /**
     * Toggle a color filter on/off and re-apply.
     */
    toggleColorFilter(color) {
        if (!this.colorFilters) this.colorFilters = new Set();
        if (this.colorFilters.has(color)) {
            this.colorFilters.delete(color);
        } else {
            this.colorFilters.add(color);
        }
        // Sync visual active state on the filter swatches
        document.querySelectorAll('.color-option[data-filter-color]').forEach(btn => {
            btn.classList.toggle('active', this.colorFilters.has(btn.dataset.filterColor));
        });
        this.applyFilters();
    },

    /**
     * Filter hosts by vulnerability severity
     */
    filterBySeverity(severity) {
        // Toggle: if same severity clicked again, clear it
        if (this.severityFilter === severity) {
            this.severityFilter = null;
        } else {
            this.severityFilter = severity;
        }
        this.applyFilters();
    },

    /**
     * Update visibility of clear all filters button
     */
    updateClearButtonVisibility(hasActiveFilters) {
        const clearBtn = document.getElementById('clearAllFiltersBtn');
        if (clearBtn) {
            clearBtn.style.display = hasActiveFilters ? '' : 'none';
            // Re-render lucide icons for the button
            if (hasActiveFilters && typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    /**
     * Update active state of stat items based on current severity filter
     */
    updateStatActiveStates() {
        const severities = ['critical', 'high', 'medium', 'low'];
        for (const sev of severities) {
            const statItem = document.querySelector(`.ribbon-stat[onclick*="'${sev}'"], .stat-item[onclick*="'${sev}'"]`);
            if (statItem) {
                if (this.severityFilter === sev) {
                    statItem.classList.add('stat-active');
                } else {
                    statItem.classList.remove('stat-active');
                }
            }
        }
    },

    /**
     * Clear indicator filters only (for backward compatibility with existing Clear All in filter panel)
     */
    clearFilters() {
        // Clear keyword search
        this.keywordSearchResults = null;
        this.keywordSearchQuery = '';
        const keywordInput = document.getElementById('search-keyword');
        if (keywordInput) {
            keywordInput.value = '';
        }

        // Uncheck all filter checkboxes
        document.querySelectorAll('[id^="filter-"]').forEach(element => {
            if (element.type === 'checkbox') {
                element.checked = false;
            } else if (element.type === 'text' && element.id === 'filter-cidr') {
                element.value = '';
            }
        });

        // Clear CIDR error message
        const cidrError = document.getElementById('cidr-error');
        if (cidrError) {
            cidrError.style.display = 'none';
            cidrError.textContent = '';
        }

        // Clear color filter swatches
        if (this.colorFilters) this.colorFilters.clear();
        document.querySelectorAll('.color-option[data-filter-color]').forEach(btn => {
            btn.classList.remove('active');
        });

        // Show all hosts
        this.applyFilters();
    },

    /**
     * Clear all filters including severity filter
     */
    clearAllFilters() {
        // Clear severity filter
        this.severityFilter = null;

        // Clear keyword search
        this.keywordSearchResults = null;
        this.keywordSearchQuery = '';
        const keywordInput = document.getElementById('search-keyword');
        if (keywordInput) {
            keywordInput.value = '';
        }

        // Uncheck all filter checkboxes and clear text inputs
        document.querySelectorAll('[id^="filter-"]').forEach(element => {
            if (element.type === 'checkbox') {
                element.checked = false;
            } else if (element.type === 'text' && element.id === 'filter-cidr') {
                element.value = '';
            }
        });

        // Clear CIDR error message
        const cidrError = document.getElementById('cidr-error');
        if (cidrError) {
            cidrError.style.display = 'none';
            cidrError.textContent = '';
        }

        // Clear color filter swatches
        if (this.colorFilters) this.colorFilters.clear();
        document.querySelectorAll('.color-option[data-filter-color]').forEach(btn => {
            btn.classList.remove('active');
        });

        // Apply (will show all hosts)
        this.applyFilters();
    },

    // ============================================
    // KEYWORD SEARCH
    // ============================================

    debounceKeywordSearch() {
        if (this._keywordSearchTimer) {
            clearTimeout(this._keywordSearchTimer);
        }
        this._keywordSearchTimer = setTimeout(() => {
            this.performKeywordSearch();
        }, 300);
    },

    async performKeywordSearch() {
        const input = document.getElementById('search-keyword');
        const query = input ? input.value.trim() : '';
        this.keywordSearchQuery = query;

        if (!query) {
            this.keywordSearchResults = null;
            this.applyFilters();
            return;
        }

        try {
            const result = await API.hosts.search(query);
            this.keywordSearchResults = new Set(result.host_ids);
            this.applyFilters();
        } catch (error) {
            console.error('Keyword search failed:', error);
            this.keywordSearchResults = null;
            this.applyFilters();
        }
    },

    // ============================================
    // SAVED SEARCHES
    // ============================================

    savedFilters: [],
    activeSavedFilter: null,

    /**
     * Load saved filters for active engagement
     */
    async loadSavedFilters() {
        try {
            this.savedFilters = await API.filters.getAll();
            this.renderSavedFiltersDropdown();
        } catch (error) {
            console.error('Failed to load saved searches:', error);
            this.savedFilters = [];
        }
    },

    /**
     * Render saved filters dropdown
     */
    renderSavedFiltersDropdown() {
        const container = document.getElementById('savedFiltersDropdown');
        if (!container) return;

        if (this.savedFilters.length === 0) {
            container.innerHTML = '<option value="">No saved searches</option>';
            return;
        }

        container.innerHTML = '<option value="">Select a saved search...</option>' +
            this.savedFilters.map(filter =>
                `<option value="${Number(filter.id)}">${escapeHtml(filter.name)}</option>`
            ).join('');
    },

    /**
     * Apply a saved filter
     */
    async applySavedFilter(filterId) {
        if (!filterId) {
            this.activeSavedFilter = null;
            const activeFilterNameEl = document.getElementById('activeFilterName');
            if (activeFilterNameEl) {
                activeFilterNameEl.style.display = 'none';
            }
            const saveBtn = document.getElementById('saveFilterBtn');
            if (saveBtn) {
                saveBtn.style.display = '';
            }
            return;
        }

        try {
            const filter = this.savedFilters.find(f => f.id === parseInt(filterId));
            if (!filter) {
                throw new Error('Search not found');
            }

            this.activeSavedFilter = filter;

            // Display active search name
            const activeFilterNameEl = document.getElementById('activeFilterName');
            if (activeFilterNameEl) {
                activeFilterNameEl.textContent = `Active Search: ${filter.name}`;
                activeFilterNameEl.style.display = 'block';
            }

            // Hide save button when a saved search is active
            const saveBtn = document.getElementById('saveFilterBtn');
            if (saveBtn) {
                saveBtn.style.display = 'none';
            }

            // Parse and apply the saved filter_json client-side
            const filterData = typeof filter.filter_json === 'string'
                ? JSON.parse(filter.filter_json) : (filter.filter_json || {});

            // Clear existing state first
            this.severityFilter = null;
            this.keywordSearchResults = null;
            this.keywordSearchQuery = '';

            // Restore indicator checkboxes
            const indicatorMap = {
                'rooted': 'filter-rooted',
                'shell': 'filter-shell',
                'interested': 'filter-interested',
                'not_interested': 'filter-not-interested',
                'out_of_scope': 'filter-out-of-scope',
                'flagged': 'filter-flagged',
                'reviewed': 'filter-reviewed',
                'has_notes': 'filter-has-notes',
                'has_findings': 'filter-has-findings'
            };
            for (const [indicator, checkboxId] of Object.entries(indicatorMap)) {
                const cb = document.getElementById(checkboxId);
                if (cb) {
                    cb.checked = filterData.indicators && filterData.indicators.includes(indicator);
                }
            }

            // Restore CIDR
            const cidrInput = document.getElementById('filter-cidr');
            if (cidrInput) {
                cidrInput.value = filterData.cidr || '';
            }

            // Restore severity
            if (filterData.severity) {
                this.severityFilter = filterData.severity;
            }

            // Restore color filters
            this.colorFilters = new Set(filterData.colors || []);
            document.querySelectorAll('.color-option[data-filter-color]').forEach(btn => {
                btn.classList.toggle('active', this.colorFilters.has(btn.dataset.filterColor));
            });

            // Restore keyword search
            const keywordInput = document.getElementById('search-keyword');
            if (keywordInput) {
                keywordInput.value = filterData.search_query || '';
            }
            if (filterData.search_query) {
                this.keywordSearchQuery = filterData.search_query;
                await this.performKeywordSearch();
            } else {
                this.applyFilters();
            }

            // Make sure the search panel is visible
            const panel = document.getElementById('hostFiltersPanel');
            if (panel) {
                panel.style.display = 'block';
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }

            showToast(`Applied search: ${filter.name}`, 'success');
        } catch (error) {
            console.error('Failed to apply saved search:', error);
            showToast('Failed to apply search: ' + error.message, 'error');
        }
    },

    /**
     * Show save filter modal
     */
    showSaveFilterModal() {
        // Get current filter state
        const currentFilter = this.getCurrentFilterState();

        if (!this.hasActiveFilters(currentFilter)) {
            showToast('No search criteria active to save', 'info');
            return;
        }

        // Show modal
        openModal('saveFilterModal');
    },

    /**
     * Get current filter state
     */
    getCurrentFilterState() {
        const filterState = {};

        // Collect indicator filters
        const indicators = [];
        const filterCheckboxes = {
            'filter-rooted': 'rooted',
            'filter-shell': 'shell',
            'filter-interested': 'interested',
            'filter-not-interested': 'not_interested',
            'filter-out-of-scope': 'out_of_scope',
            'filter-flagged': 'flagged',
            'filter-reviewed': 'reviewed',
            'filter-has-notes': 'has_notes',
            'filter-has-findings': 'has_findings'
        };

        for (const [checkboxId, indicator] of Object.entries(filterCheckboxes)) {
            const checkbox = document.getElementById(checkboxId);
            if (checkbox && checkbox.checked) {
                indicators.push(indicator);
            }
        }

        if (indicators.length > 0) {
            filterState.indicators = indicators;
        }

        // Collect severity filter
        if (this.severityFilter) {
            filterState.severity = this.severityFilter;
        }

        // Collect CIDR filter
        const cidrInput = document.getElementById('filter-cidr');
        if (cidrInput && cidrInput.value.trim()) {
            filterState.cidr = cidrInput.value.trim();
        }

        // Collect keyword search
        const keywordInput = document.getElementById('search-keyword');
        if (keywordInput && keywordInput.value.trim()) {
            filterState.search_query = keywordInput.value.trim();
        }

        // Collect color filters
        if (this.colorFilters && this.colorFilters.size > 0) {
            filterState.colors = Array.from(this.colorFilters);
        }

        return filterState;
    },

    /**
     * Check if there are active filters
     */
    hasActiveFilters(filterState) {
        return Object.keys(filterState).length > 0 &&
               Object.values(filterState).some(val =>
                   val !== null && val !== undefined && val !== '' &&
                   (Array.isArray(val) ? val.length > 0 : true)
               );
    },

    /**
     * Save current filter
     */
    async handleSaveFilter(e) {
        e.preventDefault();

        const name = document.getElementById('filterName').value.trim();
        const description = document.getElementById('filterDescription').value.trim();

        if (!name) {
            showToast('Search name is required', 'error');
            return;
        }

        const filterData = this.getCurrentFilterState();

        try {
            const savedFilter = await API.filters.create(name, description, filterData);
            showToast('Search saved successfully', 'success');

            // Reload saved filters
            await this.loadSavedFilters();

            // Close modal and reset form
            closeModal('saveFilterModal');
            document.getElementById('saveFilterForm').reset();

        } catch (error) {
            console.error('Failed to save search:', error);
            showToast('Failed to save search: ' + error.message, 'error');
        }
    },

    /**
     * Delete a saved filter
     */
    async deleteSavedFilter(filterId) {
        const filter = this.savedFilters.find(f => f.id === filterId);
        if (!filter) return;

        if (!confirm(`Delete saved search "${filter.name}"?`)) {
            return;
        }

        try {
            await API.filters.delete(filterId);
            showToast('Search deleted', 'success');

            // If this was the active filter, clear it
            if (this.activeSavedFilter && this.activeSavedFilter.id === filterId) {
                this.activeSavedFilter = null;
                const activeFilterNameEl = document.getElementById('activeFilterName');
                if (activeFilterNameEl) {
                    activeFilterNameEl.style.display = 'none';
                }
            }

            // Reload saved filters
            await this.loadSavedFilters();

        } catch (error) {
            console.error('Failed to delete search:', error);
            showToast('Failed to delete search: ' + error.message, 'error');
        }
    },

    /**
     * Clear active saved filter
     */
    clearActiveSavedFilter() {
        this.activeSavedFilter = null;

        const dropdown = document.getElementById('savedFiltersDropdown');
        if (dropdown) {
            dropdown.value = '';
        }

        const activeFilterNameEl = document.getElementById('activeFilterName');
        if (activeFilterNameEl) {
            activeFilterNameEl.style.display = 'none';
        }

        const saveBtn = document.getElementById('saveFilterBtn');
        if (saveBtn) {
            saveBtn.style.display = '';
        }
    }
};

// Make HostManager available globally
window.HostManager = HostManager;

// Port values travel in data-* attributes, never inside handler code (H-10).
registerAction('toggle-port-filter', el =>
    HostManager.togglePortFilter(Number(el.dataset.port), el.dataset.protocol));
