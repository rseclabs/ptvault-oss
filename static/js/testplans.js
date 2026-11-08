/**
 * Test Plans Manager for PTVault
 * Manages MITRE ATT&CK Navigator layers and Atomic Red Team tests integration.
 */

const TestPlansManager = {
    initialized: false,
    activeTab: 'atomics',  // atomics, navigator, plans, executions

    // State
    atomicsStatus: null,
    atomics: [],
    techniques: [],
    layers: [],
    plans: [],
    executions: [],
    selectedPlan: null,
    availableTactics: [],

    // Atomics library paging/load state (server-side pagination)
    atomicsTotal: 0,
    atomicsPageSize: 200,
    atomicsLoading: false,
    atomicsLoaded: false,
    atomicsError: null,
    atomicsRequestSeq: 0,

    // Plans cache is per engagement: templates + the active engagement's plans
    plansLoaded: false,
    plansEngagementId: null,

    // Executions load state and filter
    executionsError: null,
    executionPlanFilter: '',
    executionView: 'grid',        // grid | list
    gridSearch: '',
    gridOutcomeFilter: '',        // '' any, outcome value, or 'none' (not evaluated)
    engagementHosts: null,        // in-scope hosts, cached per engagement
    engagementHostsFor: null,
    panel: null,                  // { exec, dirty } for the open detail panel
    _modalReturnFocus: new Map(), // modal id -> element to refocus on close

    // "Add from Library" modal state (independent of the main browse list)
    libraryModalAtomics: [],
    libraryModalTotal: 0,
    libraryModalError: null,
    librarySelected: new Set(),
    libraryRequestSeq: 0,

    // Filters
    filters: {
        platform: 'all',
        tactic: 'all',
        search: ''
    },

    /**
     * Initialize the Test Plans manager.
     */
    async init() {
        if (this.initialized) return;
        this.watchModals();

        // Load atomics status first so we know if library is installed
        await this.loadAtomicsStatus();

        // Now render with correct status
        this.renderSection();
        this.setupEventListeners();
        this.setupTabKeyboard();

        // Load data for the default tab (atomics)
        if (this.activeTab === 'atomics' && this.atomicsStatus?.installed) {
            await this.loadAtomics();
            this.updateAtomicsList();
            this.setupTabEventListeners();
        }

        this.initialized = true;
    },

    /**
     * Arrow keys / Home / End move focus between the sub-tabs (manual
     * activation: Enter or Space opens a tab, since opening loads data).
     */
    setupTabKeyboard() {
        const list = document.querySelector('#section-testplans .testplans-tabs');
        if (!list || list.dataset.keyboard) return;
        list.dataset.keyboard = '1';
        list.addEventListener('keydown', (e) => {
            const tabs = [...list.querySelectorAll('[role="tab"]')];
            const i = tabs.indexOf(document.activeElement);
            if (i < 0) return;
            const next = { ArrowRight: (i + 1) % tabs.length, ArrowLeft: (i - 1 + tabs.length) % tabs.length,
                           Home: 0, End: tabs.length - 1 }[e.key];
            if (next === undefined) return;
            e.preventDefault();
            tabs[next].focus();
        });
    },

    /**
     * Render the main Test Plans section.
     */
    renderSection() {
        const container = document.getElementById('section-testplans');
        if (!container) return;

        container.innerHTML = `
            <div class="testplans-page">
                <!-- Sub-tabs -->
                <div class="testplans-tabs" role="tablist" aria-label="Test Plans sections">
                    <button class="testplans-tab ${this.activeTab === 'atomics' ? 'active' : ''}" role="tab" id="tp-tab-atomics"
                            aria-selected="${this.activeTab === 'atomics'}" aria-controls="testplansContent"
                            tabindex="${this.activeTab === 'atomics' ? '0' : '-1'}"
                            data-tab="atomics" ${on('click', 'TestPlansManager.switchTab', 'atomics')}>
                        <span class="tab-icon" aria-hidden="true"><i data-lucide="library"></i></span>
                        <span>Atomics Library</span>
                    </button>
                    <button class="testplans-tab ${this.activeTab === 'navigator' ? 'active' : ''}" role="tab" id="tp-tab-navigator"
                            aria-selected="${this.activeTab === 'navigator'}" aria-controls="testplansContent"
                            tabindex="${this.activeTab === 'navigator' ? '0' : '-1'}"
                            data-tab="navigator" ${on('click', 'TestPlansManager.switchTab', 'navigator')}>
                        <span class="tab-icon" aria-hidden="true"><i data-lucide="map"></i></span>
                        <span>Navigator Import</span>
                    </button>
                    <button class="testplans-tab ${this.activeTab === 'plans' ? 'active' : ''}" role="tab" id="tp-tab-plans"
                            aria-selected="${this.activeTab === 'plans'}" aria-controls="testplansContent"
                            tabindex="${this.activeTab === 'plans' ? '0' : '-1'}"
                            data-tab="plans" ${on('click', 'TestPlansManager.switchTab', 'plans')}>
                        <span class="tab-icon" aria-hidden="true"><i data-lucide="clipboard-list"></i></span>
                        <span>Plans</span>
                    </button>
                    <button class="testplans-tab ${this.activeTab === 'executions' ? 'active' : ''}" role="tab" id="tp-tab-executions"
                            aria-selected="${this.activeTab === 'executions'}" aria-controls="testplansContent"
                            tabindex="${this.activeTab === 'executions' ? '0' : '-1'}"
                            data-tab="executions" ${on('click', 'TestPlansManager.switchTab', 'executions')}>
                        <span class="tab-icon" aria-hidden="true"><i data-lucide="play"></i></span>
                        <span>Executions</span>
                    </button>
                </div>

                <!-- Tab Content -->
                <div class="testplans-content" id="testplansContent" role="tabpanel" aria-labelledby="tp-tab-${this.activeTab}">
                    ${this.renderActiveTabContent()}
                </div>
            </div>
        `;
    },

    /**
     * Switch between sub-tabs.
     */
    async switchTab(tabId) {
        // Re-rendering a tab drops the execution panel; don't lose edits silently
        if (!this.confirmDiscardPanel()) return;
        if (this.panel) this.panel.dirty = false;
        this.activeTab = tabId;

        // Update tab buttons
        document.querySelectorAll('.testplans-tab').forEach(tab => {
            const selected = tab.dataset.tab === tabId;
            tab.classList.toggle('active', selected);
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
        });
        document.getElementById('testplansContent')?.setAttribute('aria-labelledby', `tp-tab-${tabId}`);

        // Load data for the tab
        if (tabId === 'atomics' && this.atomics.length === 0) {
            await this.loadAtomics();
        } else if (tabId === 'navigator' && this.layers.length === 0) {
            await this.loadLayers();
        } else if (tabId === 'plans') {
            await this.ensurePlansLoaded();
        } else if (tabId === 'executions') {
            // Plans feed Start Execution; hosts feed the grid's "Add host" column
            await Promise.all([this.loadExecutions(), this.ensurePlansLoaded(), this.ensureEngagementHosts()]);
        }

        // Render content
        const content = document.getElementById('testplansContent');
        if (content) {
            content.innerHTML = this.renderActiveTabContent();
            this.setupTabEventListeners();
        }
    },

    /**
     * Render content for the active tab.
     */
    renderActiveTabContent() {
        switch (this.activeTab) {
            case 'atomics':
                return this.renderAtomicsTab();
            case 'navigator':
                return this.renderNavigatorTab();
            case 'plans':
                return this.renderPlansTab();
            case 'executions':
                return this.renderExecutionsTab();
            default:
                return '<p>Unknown tab</p>';
        }
    },

    /**
     * Setup event listeners for the section.
     */
    setupEventListeners() {
        // Global event listeners
    },

    /**
     * Setup event listeners specific to the current tab.
     */
    setupTabEventListeners() {
        // Tab-specific event listeners
        const searchInput = document.getElementById('atomicsSearch');
        if (searchInput) {
            searchInput.addEventListener('input', debounce((e) => {
                this.filters.search = e.target.value;
                this.loadAtomics();
            }, 300));
        }

        const platformFilter = document.getElementById('platformFilter');
        if (platformFilter) {
            platformFilter.addEventListener('change', (e) => {
                this.filters.platform = e.target.value;
                this.loadAtomics();
            });
        }

        const tacticFilter = document.getElementById('tacticFilter');
        if (tacticFilter) {
            tacticFilter.addEventListener('change', (e) => {
                this.filters.tactic = e.target.value;
                this.loadAtomics();
            });

            // Populate tactics if already loaded
            if (this.availableTactics.length > 0) {
                this.populateTacticFilter();
            }
        }

        // Executions tab - grid keyboard navigation (delegated; survives re-renders of the grid)
        const executionsMain = document.getElementById('executionsMain');
        if (executionsMain) {
            executionsMain.addEventListener('keydown', (e) => this.onGridKeydown(e));
        }

        // Executions tab - plan filter
        const executionPlanFilter = document.getElementById('executionPlanFilter');
        if (executionPlanFilter) {
            executionPlanFilter.addEventListener('change', (e) => {
                if (!this.confirmDiscardPanel()) {
                    e.target.value = String(this.executionView === 'grid' ? this.gridPlanId() : (this.executionPlanFilter || ''));
                    return;
                }
                this.executionPlanFilter = e.target.value;
                if (this.panel) {
                    this.panel.dirty = false;
                    this.closeExecutionPanel();
                }
                this.refreshExecutionsMain();
            });
        }

        // Navigator tab - setup drag-drop
        this.setupNavigatorDropzone();

        // Initialize Lucide icons for atomics list
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Setup drag-drop functionality for Navigator tab.
     */
    setupNavigatorDropzone() {
        const dropzone = document.getElementById('layerDropzone');
        const fileInput = document.getElementById('layerFileInput');

        if (!dropzone || !fileInput) return;

        // Click to browse
        dropzone.addEventListener('click', () => fileInput.click());
        dropzone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.uploadLayerFile(file);
        });

        // Drag events
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) this.uploadLayerFile(file);
        });
    },

    /**
     * Upload a layer file to the server.
     */
    async uploadLayerFile(file) {
        if (!file.name.endsWith('.json')) {
            showToast('Please upload a JSON file', 'error');
            return;
        }

        try {
            showToast('Uploading layer...', 'info');
            const result = await API.testPlans.importLayer(file);

            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast(`Imported "${result.name}" with ${result.technique_count} techniques`, 'success');
                await this.loadLayers();
                this.switchTab('navigator');
            }
        } catch (error) {
            showToast('Failed to upload layer', 'error');
            console.error(error);
        }
    },

    // ========================================
    // ATOMICS LIBRARY TAB
    // ========================================

    renderAtomicsTab() {
        const status = this.atomicsStatus;
        const isInstalled = status && status.installed;
        // Downloading replaces the shared library, so only admins can (M-6)
        const isAdmin = AppState.currentUser?.role === 'admin';

        return `
            <div class="atomics-library">
                <div class="atomics-header">
                    <h2>Atomic Red Team Library</h2>
                    <p class="atomics-description">
                        Browse and search tests from the Atomic Red Team repository.
                        <a href="https://github.com/redcanaryco/atomic-red-team" target="_blank">Learn more</a>
                    </p>
                </div>

                <div class="atomics-status-bar">
                    ${isInstalled ? `
                        <div class="status-installed">
                            <span class="status-icon"><i data-lucide="circle-check"></i></span>
                            <span>Library installed</span>
                            <span class="status-meta">${status.total_tests || 0} tests | ${status.total_techniques || 0} techniques</span>
                            <span class="status-meta">Updated: ${status.last_updated ? new Date(status.last_updated).toLocaleDateString() : 'Unknown'}</span>
                            ${status.version ? `<span class="status-meta" title="Pinned Atomic Red Team commit">Version: ${escapeHtml(String(status.version).slice(0, 12))}</span>` : ''}
                        </div>
                        ${isAdmin ? `<button class="btn btn-secondary" ${on('click', 'TestPlansManager.downloadAtomics')}>
                            Update Library
                        </button>` : ''}
                    ` : `
                        <div class="status-not-installed">
                            <span class="status-icon"><i data-lucide="triangle-alert"></i></span>
                            <span>Library not installed</span>
                            <span class="status-meta">${isAdmin ? 'Download the Atomic Red Team tests to get started' : 'Ask an administrator to download the Atomic Red Team tests'}</span>
                        </div>
                        ${isAdmin ? `<button class="btn btn-primary" ${on('click', 'TestPlansManager.downloadAtomics')}>
                            Download Library (~170 MB, pinned and verified)
                        </button>` : ''}
                    `}
                </div>

                ${isInstalled ? `
                    <div class="atomics-filters">
                        <div class="filter-row">
                            <input type="text" id="atomicsSearch" class="form-input" aria-label="Search atomics by technique ID or name"
                                   placeholder="Search techniques, tests, descriptions..."
                                   value="${escapeHtml(this.filters.search)}">

                            <select id="platformFilter" class="form-select" aria-label="Filter by platform">
                                <option value="all" ${this.filters.platform === 'all' ? 'selected' : ''}>All Platforms</option>
                                <option value="windows" ${this.filters.platform === 'windows' ? 'selected' : ''}>Windows</option>
                                <option value="linux" ${this.filters.platform === 'linux' ? 'selected' : ''}>Linux</option>
                                <option value="macos" ${this.filters.platform === 'macos' ? 'selected' : ''}>macOS</option>
                            </select>

                            <select id="tacticFilter" class="form-select" aria-label="Filter by tactic">
                                <option value="all" ${this.filters.tactic === 'all' ? 'selected' : ''}>All Tactics</option>
                                <!-- Populated dynamically -->
                            </select>
                        </div>
                    </div>

                    <div class="atomics-list" id="atomicsList">
                        ${this.renderAtomicsList()}
                    </div>
                ` : `
                    <div class="atomics-empty">
                        <div class="empty-icon" aria-hidden="true"><i data-lucide="library"></i></div>
                        <h3>No atomics library found</h3>
                        <p>Download the Atomic Red Team library to browse and use MITRE ATT&CK tests.</p>
                    </div>
                `}
            </div>
        `;
    },

    renderAtomicsList() {
        if (this.atomicsError) {
            return `
                <div class="atomics-empty" role="alert">
                    <p>Failed to load atomics: ${escapeHtml(this.atomicsError)}</p>
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.loadAtomics')}>Retry</button>
                </div>
            `;
        }

        if (this.atomics.length === 0) {
            if (!this.atomicsLoaded || this.atomicsLoading) {
                return '<div class="loading">Loading atomics...</div>';
            }
            return '<div class="atomics-empty"><p>No tests match your filters</p></div>';
        }

        // Tactic icons mapping
        const tacticIcons = {
            'reconnaissance': '<i data-lucide="search"></i>',
            'resource-development': '<i data-lucide="wrench"></i>',
            'initial-access': '<i data-lucide="door-open"></i>',
            'execution': '<i data-lucide="zap"></i>',
            'persistence': '<i data-lucide="pin"></i>',
            'privilege-escalation': '<i data-lucide="arrow-big-up"></i>',
            'defense-evasion': '<i data-lucide="shield"></i>',
            'credential-access': '<i data-lucide="key-round"></i>',
            'discovery': '<i data-lucide="telescope"></i>',
            'lateral-movement': '<i data-lucide="arrow-left-right"></i>',
            'collection': '<i data-lucide="package"></i>',
            'command-and-control': '<i data-lucide="radio-tower"></i>',
            'exfiltration': '<i data-lucide="upload"></i>',
            'impact': '<i data-lucide="bomb"></i>',
            'unknown': '<i data-lucide="circle-help"></i>'
        };

        return `
            <div class="atomics-list-compact">
                ${this.atomics.map(atomic => {
                    const tacticIcon = tacticIcons[atomic.tactic] || tacticIcons['unknown'];
                    const platforms = atomic.supported_platforms || [];
                    const platformStr = platforms.slice(0, 2).join(', ') + (platforms.length > 2 ? '...' : '');

                    return `
                        <div class="atomic-row" data-atomic-id="${atomic.id}">
                            <div class="atomic-row-technique">
                                <span class="atomic-row-id">${escapeHtml(atomic.technique_id)}</span>
                                <span class="atomic-row-tactic" role="img" aria-label="Tactic: ${escapeHtml((atomic.tactic || 'unknown').replace(/-/g, ' '))}" title="${escapeHtml(atomic.tactic || '')}">${tacticIcon}</span>
                            </div>
                            <div class="atomic-row-name" title="${escapeHtml(atomic.atomic_test_name)}">${escapeHtml(atomic.atomic_test_name)}</div>
                            <div class="atomic-row-meta">
                                <span class="atomic-executor">${escapeHtml(atomic.executor_name || 'manual')}</span>
                                <span class="atomic-platforms">${escapeHtml(platformStr)}</span>
                            </div>
                            <div class="atomic-row-actions">
                                <button class="btn btn-icon btn-xs" ${on('click', 'TestPlansManager.viewAtomic', atomic.id)} title="View Details" aria-label="View details for ${escapeHtml(atomic.technique_id)} ${escapeHtml(atomic.atomic_test_name)}">
                                    <i data-lucide="eye"></i>
                                </button>
                                <button class="btn btn-icon btn-xs btn-primary" ${on('click', 'TestPlansManager.addAtomicToPlan', atomic.id)} title="Add to Plan" aria-label="Add ${escapeHtml(atomic.technique_id)} ${escapeHtml(atomic.atomic_test_name)} to a plan">
                                    <i data-lucide="plus"></i>
                                </button>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
            ${this.renderAtomicsPager()}
        `;
    },

    /**
     * "Showing N of M" counter plus a Load more button when more pages exist.
     */
    renderAtomicsPager() {
        const shown = this.atomics.length;
        const total = this.atomicsTotal || shown;
        const hasMore = shown < total;
        return `
            <div class="atomics-pager" aria-live="polite">
                <span class="atomics-count">Showing ${shown.toLocaleString()} of ${total.toLocaleString()} tests</span>
                ${hasMore ? `
                    <button class="btn btn-secondary btn-sm" ${on('click', 'TestPlansManager.loadMoreAtomics')} ${this.atomicsLoading ? 'disabled' : ''}>
                        ${this.atomicsLoading ? 'Loading...' : `Load ${Math.min(this.atomicsPageSize, total - shown)} more`}
                    </button>
                ` : ''}
            </div>
        `;
    },

    // Re-render just the list and reinitialize icons
    updateAtomicsList() {
        const listContainer = document.getElementById('atomicsList');
        if (listContainer) {
            // Keep scroll position when appending a page via "Load more"
            const scrollTop = listContainer.scrollTop;
            listContainer.innerHTML = this.renderAtomicsList();
            listContainer.scrollTop = scrollTop;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    toggleTechnique(techniqueId) {
        const testsDiv = document.getElementById(`tests-${techniqueId}`);
        if (testsDiv) {
            const isHidden = testsDiv.style.display === 'none';
            testsDiv.style.display = isHidden ? 'block' : 'none';

            // Update expand icon
            const header = testsDiv.previousElementSibling;
            const icon = header.querySelector('.expand-icon');
            if (icon) {
                icon.innerHTML = isHidden ? '&#x25BC;' : '&#x25B6;';
            }
        }
    },

    // ========================================
    // NAVIGATOR IMPORT TAB
    // ========================================

    renderNavigatorTab() {
        return `
            <div class="navigator-import">
                <div class="navigator-header">
                    <h2>Navigator Layer Import</h2>
                    <p class="navigator-description">
                        Upload MITRE ATT&CK Navigator layers to create test plans from selected techniques.
                        <a href="https://mitre-attack.github.io/attack-navigator/" target="_blank">Open Navigator</a>
                    </p>
                </div>

                <div class="navigator-upload">
                    <div class="upload-dropzone ${this.layers.length ? 'is-compact' : ''}" id="layerDropzone" role="button" tabindex="0" aria-label="Upload a Navigator layer JSON file">
                        <div class="dropzone-icon" aria-hidden="true"><i data-lucide="folder-open"></i></div>
                        <p>Drop a Navigator layer JSON file here</p>
                        <p class="dropzone-hint">or click to browse</p>
                        <input type="file" id="layerFileInput" accept=".json" style="display: none;">
                    </div>
                </div>

                <div class="layers-list">
                    <h3>Imported Layers</h3>
                    ${this.layers.length === 0 ? `
                        <div class="layers-empty">
                            <p>No layers imported yet</p>
                        </div>
                    ` : `
                        <div class="layers-list-compact">
                            ${this.layers.map(layer => `
                                <div class="layer-row" data-layer-id="${layer.id}">
                                    <div class="layer-row-info">
                                        <span class="layer-row-name">${escapeHtml(layer.name)}</span>
                                        <span class="layer-row-domain">${escapeHtml(layer.domain)}</span>
                                    </div>
                                    <div class="layer-row-meta">
                                        <span class="layer-row-techniques">${layer.technique_count} techniques</span>
                                        <span class="layer-row-date">${new Date(layer.created_at).toLocaleDateString()}</span>
                                    </div>
                                    <div class="layer-row-actions">
                                        <button class="btn btn-xs btn-primary" ${on('click', 'TestPlansManager.matchLayerToAtomics', layer.id)} aria-label="Create a test plan from layer ${escapeHtml(layer.name || '')}">
                                            Create plan
                                        </button>
                                        <button class="btn btn-icon btn-xs btn-danger" ${on('click', 'TestPlansManager.deleteLayer', layer.id)} title="Delete" aria-label="Delete layer ${escapeHtml(layer.name || '')}">
                                            <i data-lucide="trash-2"></i>
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>
            </div>
        `;
    },

    // ========================================
    // TEST PLANS TAB
    // ========================================

    renderPlansTab() {
        const hasEngagement = this.currentEngagementId() !== null;
        const engagementName = hasEngagement ? (AppState.activeEngagement.name || '') : '';
        const engagementPlans = this.engagementPlans();
        const templates = this.templatePlans();

        return `
            <div class="test-plans">
                <div class="plans-header">
                    <h2>Test Plans</h2>
                    <button class="btn btn-primary" ${on('click', 'TestPlansManager.createPlan')}>
                        + New Test Plan
                    </button>
                </div>

                <section class="plans-section" aria-labelledby="plansEngagementHeading">
                    <div class="plans-section-header">
                        <h3 id="plansEngagementHeading">This engagement</h3>
                        ${hasEngagement ? `<span class="plans-section-context">${escapeHtml(engagementName)}</span>` : ''}
                    </div>
                    ${!hasEngagement ? `
                        <p class="plans-section-empty">Select an engagement to see and run its plans. Templates below stay available.</p>
                    ` : engagementPlans.length === 0 ? `
                        <p class="plans-section-empty">
                            No plans in this engagement yet. Pick a template below and choose <strong>Use</strong>,
                            or <button type="button" class="btn-link" ${on('click', 'TestPlansManager.createPlan', 'engagement')}>create a new plan</button>.
                        </p>
                    ` : `
                        <div class="plans-list-compact">
                            ${engagementPlans.map(plan => this.renderPlanRow(plan, hasEngagement)).join('')}
                        </div>
                    `}
                </section>

                <section class="plans-section" aria-labelledby="plansTemplatesHeading">
                    <div class="plans-section-header">
                        <h3 id="plansTemplatesHeading">Templates</h3>
                        <span class="plans-section-hint">Reusable across engagements. Using one copies it into the active engagement; the template is unchanged.</span>
                    </div>
                    ${templates.length === 0 ? `
                        <p class="plans-section-empty">
                            No templates yet. Save an engagement plan as a template, or
                            <button type="button" class="btn-link" ${on('click', 'TestPlansManager.createPlan', 'template')}>create a template</button>.
                        </p>
                    ` : `
                        <div class="plans-list-compact">
                            ${templates.map(plan => this.renderPlanRow(plan, hasEngagement)).join('')}
                        </div>
                    `}
                </section>
            </div>
        `;
    },

    renderPlanRow(plan, hasEngagement) {
        const name = escapeHtml(plan.name);
        const scopeActions = plan.is_template ? `
            <button class="btn btn-xs btn-primary" ${on('click', 'TestPlansManager.useTemplate', plan.id)}
                    ${hasEngagement ? '' : 'disabled'}
                    title="${hasEngagement ? 'Copy into this engagement' : 'Select an engagement first'}"
                    aria-label="Use template ${name} in this engagement">
                Use
            </button>
            <button class="btn btn-xs" ${on('click', 'TestPlansManager.duplicatePlan', plan.id)} title="Duplicate template" aria-label="Duplicate template ${name}">
                <i data-lucide="copy"></i>
            </button>
        ` : `
            <button class="btn btn-xs" ${on('click', 'TestPlansManager.saveAsTemplate', plan.id)} title="Save as template" aria-label="Save ${name} as a template">
                <i data-lucide="bookmark-plus"></i>
            </button>
        `;

        return `
            <div class="plan-row" data-plan-id="${plan.id}">
                <div class="plan-row-info">
                    <span class="plan-row-name">${name}</span>
                    <span class="plan-row-platform platform-${escapeHtml(plan.target_platform || 'all')}">${escapeHtml(plan.target_platform || 'all')}</span>
                </div>
                <div class="plan-row-meta">
                    <span class="plan-row-tests">${plan.item_count || 0} tests</span>
                    ${!plan.is_template && plan.exec_total ? `<span class="plan-row-progress" title="${plan.exec_done} of ${plan.exec_total} executions run; ${plan.exec_evaluated} have an outcome">${plan.exec_done}/${plan.exec_total} run &middot; ${plan.exec_evaluated} evaluated</span>` : ''}
                    ${plan.missing_count ? `<span class="plan-row-missing" title="These tests are no longer in the Atomics library and are skipped in generated scripts">${plan.missing_count} missing</span>` : ''}
                    <span class="plan-row-desc">${escapeHtml(plan.description || '')}</span>
                </div>
                <div class="plan-row-actions">
                    ${scopeActions}
                    <button class="btn btn-xs" ${on('click', 'TestPlansManager.editPlan', plan.id)} title="Edit" aria-label="Edit ${name}">
                        <i data-lucide="edit-2"></i>
                    </button>
                    <button class="btn btn-xs" ${on('click', 'TestPlansManager.generateScript', plan.id)} title="Generate Script" aria-label="Generate script for ${name}">
                        <i data-lucide="file-code"></i>
                    </button>
                    <button class="btn btn-xs btn-danger" ${on('click', 'TestPlansManager.deletePlan', plan.id)} title="Delete" aria-label="Delete ${name}">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Plan <option>s grouped by scope, for selects that pick a plan.
     * @param {Object} opts - { includeTemplates, templateSuffix, showCounts }
     */
    renderPlanOptions({ includeTemplates = true, templateSuffix = '', showCounts = false } = {}) {
        const option = p => `<option value="${p.id}">${escapeHtml(p.name)}${showCounts ? ` (${p.item_count || 0} tests)` : ''}${p.is_template ? templateSuffix : ''}</option>`;
        const engagementPlans = this.engagementPlans();
        const templates = includeTemplates ? this.templatePlans() : [];
        return [
            engagementPlans.length ? `<optgroup label="This engagement">${engagementPlans.map(option).join('')}</optgroup>` : '',
            templates.length ? `<optgroup label="Templates">${templates.map(option).join('')}</optgroup>` : ''
        ].join('');
    },

    // ========================================
    // EXECUTIONS TAB
    // ========================================

    renderExecutionsTab() {
        // Check if engagement is active
        if (!AppState || !AppState.activeEngagement) {
            return `
                <div class="executions-no-engagement">
                    <div class="empty-icon" aria-hidden="true"><i data-lucide="triangle-alert"></i></div>
                    <h3>No Active Engagement</h3>
                    <p>Select an engagement to track test executions.</p>
                </div>
            `;
        }

        // A full tab render discards any open detail panel
        this.panel = null;
        const isGrid = this.executionView === 'grid';
        const runPlans = this.executionRunPlans();
        const selectedPlanId = isGrid ? String(this.gridPlanId() || '') : String(this.executionPlanFilter || '');

        return `
            <div class="test-executions">
                <div class="executions-header">
                    <h2>Test Executions</h2>
                    <div class="executions-actions">
                        ${this.executions.length ? `
                            <div class="exec-view-toggle" role="group" aria-label="Executions view">
                                <button type="button" class="${isGrid ? 'active' : ''}" aria-pressed="${isGrid}"
                                        ${on('click', 'TestPlansManager.setExecutionView', 'grid')}>Grid</button>
                                <button type="button" class="${isGrid ? '' : 'active'}" aria-pressed="${!isGrid}"
                                        ${on('click', 'TestPlansManager.setExecutionView', 'list')}>List</button>
                            </div>
                            <select id="executionPlanFilter" class="form-select" aria-label="${isGrid ? 'Plan shown in the grid' : 'Filter executions by plan'}">
                                ${isGrid ? '' : '<option value="">All Plans</option>'}
                                ${runPlans.map(plan => `
                                    <option value="${plan.id}" ${String(plan.id) === selectedPlanId ? 'selected' : ''}>${escapeHtml(plan.name)}</option>
                                `).join('')}
                            </select>
                        ` : ''}
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.startNewExecution')}>
                            Start Execution
                        </button>
                    </div>
                </div>

                <div class="exec-layout" id="execLayout">
                    <div class="exec-main" id="executionsMain">
                        ${this.renderExecutionsMain()}
                    </div>
                    <aside class="exec-panel" id="executionPanel" aria-label="Execution details" hidden></aside>
                </div>
            </div>
        `;
    },

    /**
     * Plans that have executions in this engagement (derived from the
     * executions themselves, so it is always in sync with the grid).
     */
    executionRunPlans() {
        const byId = new Map();
        this.executions.forEach(e => {
            if (!byId.has(e.test_plan_id)) byId.set(e.test_plan_id, { id: e.test_plan_id, name: e.plan_name || `Plan ${e.test_plan_id}` });
        });
        return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
    },

    /** Plan shown in the grid: the selected plan, else the first run plan. */
    gridPlanId() {
        const plans = this.executionRunPlans();
        const selected = plans.find(p => String(p.id) === String(this.executionPlanFilter));
        return selected ? selected.id : (plans[0] ? plans[0].id : null);
    },

    /**
     * Body of the Executions tab: error, empty, grid, or list.
     */
    renderExecutionsMain() {
        if (this.executionsError) {
            return `
                <div class="executions-empty" role="alert">
                    <div class="empty-icon" aria-hidden="true"><i data-lucide="triangle-alert"></i></div>
                    <h3>Couldn't load executions</h3>
                    <p>${escapeHtml(this.executionsError)}</p>
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.switchTab', 'executions')}>Retry</button>
                </div>
            `;
        }

        if (this.executions.length === 0) {
            return `
                <div class="executions-empty">
                    <div class="empty-icon" aria-hidden="true"><i data-lucide="play"></i></div>
                    <h3>No executions yet</h3>
                    <p>Start a test plan execution to track your testing progress.</p>
                    <button class="btn btn-primary" ${on('click', 'TestPlansManager.startNewExecution')}>Start Execution</button>
                </div>
            `;
        }

        return this.executionView === 'grid' ? this.renderExecutionGrid() : this.renderExecutionsList();
    },

    // ---------- Outcome / status vocabulary ----------

    OUTCOMES: [
        { value: 'prevented', label: 'Prevented', short: 'PREV', hint: 'Blocked before it completed' },
        { value: 'alerted', label: 'Alerted', short: 'ALRT', hint: 'Raised an alert to defenders' },
        { value: 'logged', label: 'Logged', short: 'LOG', hint: 'Telemetry recorded, no alert' },
        { value: 'not_detected', label: 'Not detected', short: 'MISS', hint: 'No block, alert, or log' }
    ],

    STATUSES: [
        { value: 'pending', label: 'Pending' },
        { value: 'in_progress', label: 'In progress' },
        { value: 'completed', label: 'Completed' },
        { value: 'failed', label: 'Failed' },
        { value: 'skipped', label: 'Skipped' }
    ],

    outcomeLabel(outcome) {
        const o = this.OUTCOMES.find(x => x.value === outcome);
        return o ? o.label : 'Not evaluated';
    },

    statusLabel(status) {
        const s = this.STATUSES.find(x => x.value === status);
        return s ? s.label : 'Pending';
    },

    /** Small authored status glyphs (inline SVG, no icon render pass needed). */
    statusSvg(status) {
        const paths = {
            pending: '<circle cx="8" cy="8" r="5.5"/>',
            in_progress: '<circle cx="8" cy="8" r="5.5"/><path d="M8 5v3l2 1.5"/>',
            completed: '<path d="M3.5 8.5l3 3 6-7"/>',
            failed: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
            skipped: '<path d="M4 4l5 4-5 4zM12 4v8"/>'
        };
        return `<svg class="exec-status-svg exec-st-${status || 'pending'}" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[status] || paths.pending}</svg>`;
    },

    compareHostAddress(a, b) {
        const pa = String(a || '').split('.').map(Number);
        const pb = String(b || '').split('.').map(Number);
        if (pa.length === 4 && pb.length === 4 && pa.every(n => !isNaN(n)) && pb.every(n => !isNaN(n))) {
            for (let i = 0; i < 4; i++) if (pa[i] !== pb[i]) return pa[i] - pb[i];
            return 0;
        }
        return String(a || '').localeCompare(String(b || ''));
    },

    // ---------- Grid ----------

    /**
     * Build rows (plan items), columns (hosts) and cells for one plan.
     */
    buildGridModel(planId) {
        const execs = this.executions.filter(e => String(e.test_plan_id) === String(planId));

        const hostMap = new Map();
        const rowMap = new Map();
        const cells = new Map();
        execs.forEach(e => {
            const hostKey = e.host_id == null ? 'none' : String(e.host_id);
            if (!hostMap.has(hostKey)) {
                hostMap.set(hostKey, { key: hostKey, id: e.host_id, ip: e.host_ip, hostname: e.host_hostname });
            }
            if (!rowMap.has(e.test_plan_item_id)) {
                rowMap.set(e.test_plan_item_id, {
                    itemId: e.test_plan_item_id,
                    technique: e.technique_id || '',
                    name: e.atomic_test_name || e.custom_name || (e.atomic_id ? 'Missing from Atomics library' : 'Unknown test'),
                    tactic: e.tactic || '',
                    sort: e.item_sort_order ?? 0
                });
            }
            cells.set(`${e.test_plan_item_id}|${hostKey}`, e);
        });

        const hosts = [...hostMap.values()].sort((a, b) => {
            if (a.key === 'none') return 1;
            if (b.key === 'none') return -1;
            return this.compareHostAddress(a.ip || a.hostname, b.ip || b.hostname);
        });
        const rows = [...rowMap.values()].sort((a, b) => (a.sort - b.sort) || a.technique.localeCompare(b.technique));

        return { planId, execs, hosts, rows, cells };
    },

    hostLabel(host) {
        if (!host || host.key === 'none') return 'No specific host';
        return host.ip || host.hostname || `Host ${host.id}`;
    },

    gridVisibleRows(model) {
        const q = (this.gridSearch || '').trim().toLowerCase();
        const outcome = this.gridOutcomeFilter;
        return model.rows.filter(row => {
            if (q && !`${row.technique} ${row.name} ${row.tactic}`.toLowerCase().includes(q)) return false;
            if (outcome) {
                const match = model.hosts.some(h => {
                    const e = model.cells.get(`${row.itemId}|${h.key}`);
                    if (!e) return false;
                    return outcome === 'none' ? !e.outcome : e.outcome === outcome;
                });
                if (!match) return false;
            }
            return true;
        });
    },

    renderExecutionGrid() {
        const planId = this.gridPlanId();
        const model = this.buildGridModel(planId);

        return `
            ${this.renderOutcomeSummary(model.execs)}
            <div class="exec-grid-toolbar">
                <input type="search" id="execGridSearch" class="form-input" placeholder="Filter tests by technique, name, or tactic"
                       aria-label="Filter tests" value="${escapeHtml(this.gridSearch || '')}"
                       ${on('input', 'TestPlansManager.setGridSearch', ARG.value)}>
                <select id="execGridOutcome" class="form-select" aria-label="Show tests with outcome"
                        ${on('change', 'TestPlansManager.setGridOutcomeFilter', ARG.value)}>
                    <option value="">Any outcome</option>
                    ${this.OUTCOMES.map(o => `<option value="${o.value}" ${this.gridOutcomeFilter === o.value ? 'selected' : ''}>${o.label}</option>`).join('')}
                    <option value="none" ${this.gridOutcomeFilter === 'none' ? 'selected' : ''}>Not evaluated</option>
                </select>
                <button type="button" class="btn btn-secondary" ${on('click', 'TestPlansManager.showImportLogModal')}
                        title="Fill in status and output from the log your PTVault script wrote">
                    Import log
                </button>
            </div>
            <div id="execGridTable">
                ${this.renderExecutionGridTable(model)}
            </div>
        `;
    },

    renderExecutionGridTable(model) {
        const rows = this.gridVisibleRows(model);
        const selectedId = this.panel?.exec?.id;
        const usedHostKeys = new Set(model.hosts.map(h => h.key));
        const addableHosts = (this.engagementHosts || []).filter(h => !usedHostKeys.has(String(h.id)));
        const canAddNoHost = !usedHostKeys.has('none');

        const addHost = `
            <div class="exec-add-host">
                <select id="execAddHostSelect" class="form-select" aria-label="Run this plan on another host">
                    <option value="">+ Add host</option>
                    ${addableHosts.map(h => `<option value="${h.id}">${escapeHtml(h.ip || h.hostname || `Host ${h.id}`)}${h.ip && h.hostname ? ` (${escapeHtml(h.hostname)})` : ''}</option>`).join('')}
                    ${canAddNoHost ? '<option value="none">No specific host</option>' : ''}
                </select>
                <button type="button" class="btn btn-xs btn-primary" ${on('click', 'TestPlansManager.addHostToGrid')}>Run</button>
            </div>
        `;

        // Roving tabindex: one cell in the Tab order, arrows move between cells
        const visibleIds = [];
        rows.forEach(row => model.hosts.forEach(h => {
            const e = model.cells.get(`${row.itemId}|${h.key}`);
            if (e) visibleIds.push(e.id);
        }));
        const rovingId = visibleIds.includes(selectedId) ? selectedId : visibleIds[0];

        const cell = (row, host) => {
            const e = model.cells.get(`${row.itemId}|${host.key}`);
            if (!e) {
                return `<td class="exec-grid-cell"><span class="exec-cell-empty" title="Not part of this run">&middot;</span></td>`;
            }
            const outcome = this.OUTCOMES.find(o => o.value === e.outcome);
            const label = `${row.technique ? row.technique + ' ' : ''}${row.name} on ${this.hostLabel(host)}: ${this.statusLabel(e.status)}, ${this.outcomeLabel(e.outcome)}`;
            return `
                <td class="exec-grid-cell">
                    <button type="button" class="exec-cell outcome-${e.outcome || 'none'} ${e.id === selectedId ? 'is-selected' : ''}"
                            data-exec-id="${e.id}" tabindex="${e.id === rovingId ? 0 : -1}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}"
                            ${on('click', 'TestPlansManager.openExecution', e.id)}>
                        ${this.statusSvg(e.status)}
                        <span class="exec-cell-label">${outcome ? outcome.short : '&ndash;'}</span>
                    </button>
                </td>
            `;
        };

        return `
            <div class="exec-grid-scroll" id="execGridScroll">
                <table class="exec-grid">
                    <caption class="exec-sr-only">Tests by host. Each cell shows run status and detection outcome; select a cell to record results. Use the arrow keys to move between cells.</caption>
                    <thead>
                        <tr>
                            <th scope="col" class="exec-grid-test-col">Test <span class="exec-grid-count">${rows.length === model.rows.length ? model.rows.length : `${rows.length} of ${model.rows.length}`}</span></th>
                            ${model.hosts.map(h => `
                                <th scope="col" class="exec-grid-host">
                                    <span class="exec-grid-host-ip">${escapeHtml(this.hostLabel(h))}</span>
                                    ${h.key !== 'none' && h.hostname && h.ip ? `<span class="exec-grid-host-name">${escapeHtml(h.hostname)}</span>` : ''}
                                </th>
                            `).join('')}
                            <th scope="col" class="exec-grid-add-col">${addHost}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.length === 0 ? `
                            <tr><td class="exec-grid-nomatch" colspan="${model.hosts.length + 2}">No tests match these filters.</td></tr>
                        ` : rows.map(row => `
                            <tr>
                                <th scope="row" class="exec-grid-test-col">
                                    ${row.technique ? `<span class="exec-grid-technique">${escapeHtml(row.technique)}</span>` : '<span class="exec-grid-technique is-custom">Custom</span>'}
                                    <span class="exec-grid-test-name">${escapeHtml(row.name)}</span>
                                </th>
                                ${model.hosts.map(h => cell(row, h)).join('')}
                                <td class="exec-grid-add-col"></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    renderOutcomeSummary(execs) {
        const counts = { none: 0 };
        this.OUTCOMES.forEach(o => { counts[o.value] = 0; });
        execs.forEach(e => {
            if (e.outcome && counts[e.outcome] !== undefined) counts[e.outcome]++;
            else counts.none++;
        });
        const evaluated = execs.length - counts.none;
        const visible = counts.prevented + counts.alerted + counts.logged;
        const pct = evaluated ? Math.round((visible / evaluated) * 100) : 0;
        const segments = [...this.OUTCOMES.map(o => ({ key: o.value, label: o.label, n: counts[o.value] })),
            { key: 'none', label: 'Not evaluated', n: counts.none }];
        const description = segments.map(s => `${s.label} ${s.n}`).join(', ');

        return `
            <div class="exec-summary">
                <div class="exec-summary-bar" role="img" aria-label="Outcomes: ${description}">
                    ${segments.filter(s => s.n > 0).map(s => `<span class="exec-summary-seg outcome-${s.key}" style="flex-grow: ${s.n}"></span>`).join('')}
                </div>
                <div class="exec-summary-row">
                    <ul class="exec-summary-legend">
                        ${segments.map(s => `
                            <li><span class="exec-swatch outcome-${s.key}" aria-hidden="true"></span>${s.label} <strong>${s.n}</strong></li>
                        `).join('')}
                    </ul>
                    <p class="exec-summary-coverage" aria-live="polite">
                        ${evaluated
                            ? `Visible to defenders: <strong>${visible} of ${evaluated}</strong> evaluated (${pct}%)`
                            : 'No outcomes recorded yet. Select a cell to record one.'}
                    </p>
                </div>
            </div>
        `;
    },

    // ---------- List ----------

    renderExecutionsList() {
        const filtered = this.executionPlanFilter
            ? this.executions.filter(e => String(e.test_plan_id) === String(this.executionPlanFilter))
            : this.executions;

        if (filtered.length === 0) {
            return `
                <div class="executions-empty">
                    <p>No executions for this plan.</p>
                </div>
            `;
        }

        const selectedId = this.panel?.exec?.id;
        return `
                        <div class="executions-list-compact">
                            ${filtered.map(exec => `
                                <div class="exec-row status-${exec.status} ${exec.id === selectedId ? 'is-selected' : ''}" data-exec-id="${exec.id}">
                                    <div class="exec-row-status" title="${this.statusLabel(exec.status)}">
                                        ${this.statusSvg(exec.status)}
                                    </div>
                                    <div class="exec-row-info">
                                        ${exec.technique_id ? `<span class="exec-row-technique">${escapeHtml(exec.technique_id)}</span>` : ''}
                                        <span class="exec-row-name">${escapeHtml(exec.atomic_test_name || exec.custom_name || 'Unknown')}</span>
                                    </div>
                                    <div class="exec-row-meta">
                                        <span class="exec-outcome-chip outcome-${exec.outcome || 'none'}">${this.outcomeLabel(exec.outcome)}</span>
                                        <span class="exec-row-plan">${escapeHtml(exec.plan_name)}</span>
                                        ${exec.host_ip ? `<span class="exec-row-host">${escapeHtml(exec.host_ip)}</span>` : ''}
                                        <span class="exec-row-date">${exec.execution_started_at ? new Date(exec.execution_started_at).toLocaleDateString() : '-'}</span>
                                    </div>
                                    <div class="exec-row-actions">
                                        <button class="btn btn-xs btn-primary" ${on('click', 'TestPlansManager.openExecution', exec.id)}
                                                aria-label="Record results for ${escapeHtml(exec.technique_id || '')} ${escapeHtml(exec.atomic_test_name || exec.custom_name || 'test')}">
                                            Record
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
        `;
    },

    // ---------- View state ----------

    async setExecutionView(view) {
        if (this.executionView === view) return;
        if (!this.confirmDiscardPanel()) return;
        if (this.panel) this.panel.dirty = false;  // already confirmed; switchTab won't ask again
        this.executionView = view;
        await this.switchTab('executions');
    },

    setGridSearch(value) {
        this.gridSearch = value;
        clearTimeout(this._gridSearchTimer);
        this._gridSearchTimer = setTimeout(() => this.refreshGridTable(), 200);
    },

    setGridOutcomeFilter(value) {
        this.gridOutcomeFilter = value;
        this.refreshGridTable();
    },

    /** Re-render only the grid table (keeps toolbar focus and the panel). */
    refreshGridTable() {
        const wrap = document.getElementById('execGridTable');
        if (!wrap) return;
        const scroll = document.getElementById('execGridScroll');
        const pos = scroll ? [scroll.scrollTop, scroll.scrollLeft] : [0, 0];
        wrap.innerHTML = this.renderExecutionGridTable(this.buildGridModel(this.gridPlanId()));
        const next = document.getElementById('execGridScroll');
        if (next) [next.scrollTop, next.scrollLeft] = pos;
    },

    /** Re-render the main area (summary + grid/list), preserving scroll. */
    refreshExecutionsMain() {
        const main = document.getElementById('executionsMain');
        if (!main) return;
        const scroll = document.getElementById('execGridScroll');
        const pos = scroll ? [scroll.scrollTop, scroll.scrollLeft] : null;
        const pagePos = window.scrollY;
        main.innerHTML = this.renderExecutionsMain();
        const next = document.getElementById('execGridScroll');
        if (next && pos) [next.scrollTop, next.scrollLeft] = pos;
        window.scrollTo(0, pagePos);
    },

    async ensureEngagementHosts() {
        const engagementId = this.currentEngagementId();
        if (this.engagementHosts && this.engagementHostsFor === engagementId) return;
        try {
            const result = await API.hosts.getAll();
            const hosts = Array.isArray(result) ? result : (result?.hosts || []);
            this.engagementHosts = hosts
                .filter(h => !h.out_of_scope)
                .sort((a, b) => this.compareHostAddress(a.ip || a.hostname, b.ip || b.hostname));
            this.engagementHostsFor = engagementId;
        } catch (error) {
            console.error('Failed to load hosts:', error);
            this.engagementHosts = [];
        }
    },

    async addHostToGrid() {
        const select = document.getElementById('execAddHostSelect');
        if (!select || !select.value) {
            showToast('Choose a host to run this plan on', 'warning');
            select?.focus();
            return;
        }
        const planId = this.gridPlanId();
        const hostId = select.value === 'none' ? null : select.value;
        try {
            const result = await API.testPlans.startExecution(planId, hostId);
            showToast(`Added ${result.count} tests for ${select.options[select.selectedIndex].text}`, 'success');
            await this.loadExecutions();
            this.refreshExecutionsMain();
        } catch (error) {
            showToast(error.message || 'Failed to add host', 'error');
        }
    },

    // ========================================
    // API CALLS
    // ========================================

    async loadAtomicsStatus() {
        try {
            const result = await API.testPlans.getAtomicsStatus();
            if (!result.error) {
                this.atomicsStatus = result;
            }
        } catch (error) {
            console.error('Failed to load atomics status:', error);
        }
    },

    /**
     * Load the atomics browse list from the server, one page at a time.
     * @param {boolean} append - true to fetch the next page and append it,
     *                           false to reset (new filters / first load)
     */
    async loadAtomics(append = false) {
        const params = {};
        if (this.filters.platform !== 'all') {
            params.platform = this.filters.platform;
        }
        if (this.filters.tactic !== 'all') {
            params.tactic = this.filters.tactic;
        }
        if (this.filters.search) {
            params.search = this.filters.search;
        }
        params.limit = this.atomicsPageSize;
        params.offset = append ? this.atomics.length : 0;

        // Ignore responses from superseded requests (fast typing in search)
        const seq = ++this.atomicsRequestSeq;
        this.atomicsLoading = true;
        this.atomicsError = null;
        if (append) this.updateAtomicsList();

        // Tactic list comes from the full library, not the current page
        if (this.availableTactics.length === 0) {
            this.loadAvailableTactics();
        }

        try {
            const result = await API.testPlans.getAtomics(params);
            if (seq !== this.atomicsRequestSeq) return;

            if (result.error) {
                this.atomicsError = result.error;
                if (!append) this.atomics = [];
            } else {
                const page = result.atomics || [];
                this.atomics = append ? this.atomics.concat(page) : page;
                this.atomicsTotal = result.total ?? this.atomics.length;
            }
        } catch (error) {
            if (seq !== this.atomicsRequestSeq) return;
            console.error('Failed to load atomics:', error);
            this.atomicsError = error.message || 'Network error';
            if (!append) this.atomics = [];
        }

        this.atomicsLoading = false;
        this.atomicsLoaded = true;
        this.updateAtomicsList();
    },

    async loadMoreAtomics() {
        if (this.atomicsLoading || this.atomics.length >= this.atomicsTotal) return;
        await this.loadAtomics(true);
    },

    /**
     * Load every tactic in the library (not just the loaded page) and
     * populate the filter dropdown.
     */
    async loadAvailableTactics() {
        try {
            const result = await API.testPlans.getTactics();
            if (Array.isArray(result)) {
                this.availableTactics = result.map(t => t.tactic).filter(Boolean).sort();
                this.populateTacticFilter();
            } else if (result?.error) {
                console.error('Failed to load tactics:', result.error);
            }
        } catch (error) {
            console.error('Failed to load tactics:', error);
        }
    },

    /**
     * Populate the tactic filter dropdown with available tactics
     */
    populateTacticFilter() {
        const tacticFilter = document.getElementById('tacticFilter');
        if (!tacticFilter) return;

        // Tactic display names
        const tacticNames = {
            'reconnaissance': 'Reconnaissance',
            'resource-development': 'Resource Development',
            'initial-access': 'Initial Access',
            'execution': 'Execution',
            'persistence': 'Persistence',
            'privilege-escalation': 'Privilege Escalation',
            'defense-evasion': 'Defense Evasion',
            'credential-access': 'Credential Access',
            'discovery': 'Discovery',
            'lateral-movement': 'Lateral Movement',
            'collection': 'Collection',
            'command-and-control': 'Command and Control',
            'exfiltration': 'Exfiltration',
            'impact': 'Impact'
        };

        // Keep the "All Tactics" option and add the rest
        tacticFilter.innerHTML = `
            <option value="all" ${this.filters.tactic === 'all' ? 'selected' : ''}>All Tactics</option>
            ${this.availableTactics.map(tactic => {
                const displayName = tacticNames[tactic] || tactic;
                return `<option value="${tactic}" ${this.filters.tactic === tactic ? 'selected' : ''}>${escapeHtml(displayName)}</option>`;
            }).join('')}
        `;
    },

    async downloadAtomics() {
        // Show progress bar UI
        this.showDownloadProgress(0, 'Starting download...');

        try {
            const result = await API.testPlans.downloadAtomics((progress) => {
                // Update progress bar on each SSE event
                this.showDownloadProgress(progress.percent, progress.message);
            });

            if (result.error) {
                this.hideDownloadProgress();
                showToast(result.error, 'error');
            } else {
                this.hideDownloadProgress();
                showToast('Atomics library downloaded successfully!', 'success');
                await this.loadAtomicsStatus();
                await this.loadAtomics();
                this.switchTab('atomics');
            }
        } catch (error) {
            this.hideDownloadProgress();
            showToast(error.message || 'Failed to download atomics library', 'error');
            console.error(error);
        }
    },

    showDownloadProgress(percent, message) {
        let progressContainer = document.getElementById('atomics-download-progress');

        if (!progressContainer) {
            // Create progress container
            const statusBar = document.querySelector('.atomics-status-bar');
            if (statusBar) {
                progressContainer = document.createElement('div');
                progressContainer.id = 'atomics-download-progress';
                progressContainer.className = 'download-progress-container';
                progressContainer.innerHTML = `
                    <div class="progress-info">
                        <span class="progress-message"></span>
                        <span class="progress-percent"></span>
                    </div>
                    <div class="progress-bar-wrapper">
                        <div class="progress-bar-fill"></div>
                    </div>
                `;
                statusBar.parentNode.insertBefore(progressContainer, statusBar.nextSibling);

                // Hide the status bar buttons during download
                statusBar.style.display = 'none';
            }
        }

        if (progressContainer) {
            progressContainer.querySelector('.progress-message').textContent = message;
            progressContainer.querySelector('.progress-percent').textContent = `${percent}%`;
            progressContainer.querySelector('.progress-bar-fill').style.width = `${percent}%`;
        }
    },

    hideDownloadProgress() {
        const progressContainer = document.getElementById('atomics-download-progress');
        if (progressContainer) {
            progressContainer.remove();
        }

        // Show the status bar buttons again
        const statusBar = document.querySelector('.atomics-status-bar');
        if (statusBar) {
            statusBar.style.display = '';
        }
    },

    async loadLayers() {
        try {
            const result = await API.testPlans.getLayers();
            if (!result.error) {
                this.layers = result;
            }
        } catch (error) {
            console.error('Failed to load layers:', error);
        }
    },

    async loadPlans() {
        const engagementId = this.currentEngagementId();
        try {
            const result = await API.testPlans.getPlans();
            if (Array.isArray(result)) {
                this.plans = result;
                this.plansLoaded = true;
                this.plansEngagementId = engagementId;
            }
        } catch (error) {
            console.error('Failed to load plans:', error);
        }
    },

    currentEngagementId() {
        return (typeof AppState !== 'undefined' && AppState.activeEngagement)
            ? AppState.activeEngagement.id
            : null;
    },

    engagementPlans() {
        return this.plans.filter(p => !p.is_template);
    },

    templatePlans() {
        return this.plans.filter(p => p.is_template);
    },

    /**
     * Called each time the Test Plans section is shown. Plans are scoped to
     * the active engagement, so re-render plan-dependent tabs if the
     * engagement changed while the section was hidden.
     */
    async onShow() {
        if (!this.initialized) return;
        if (this.plansLoaded && this.plansEngagementId !== this.currentEngagementId()) {
            // switchTab re-renders the tab, replacing any open plan editor
            if (this.activeTab === 'plans' || this.activeTab === 'executions') {
                await this.switchTab(this.activeTab);
            } else {
                this.plansLoaded = false;
            }
        }
    },

    async loadExecutions() {
        this.executionsError = null;
        try {
            const result = await API.testPlans.getExecutions();
            if (Array.isArray(result)) {
                this.executions = result;
            } else {
                this.executions = [];
                this.executionsError = result?.error || 'Unexpected response from server';
            }
        } catch (error) {
            console.error('Failed to load executions:', error);
            this.executions = [];
            this.executionsError = error.message || 'Network error';
        }
    },

    /**
     * Make sure the plan list is loaded (the Executions tab and the
     * Start Execution modal need it even if the Plans tab was never opened).
     */
    async ensurePlansLoaded() {
        if (!this.plansLoaded || this.plansEngagementId !== this.currentEngagementId()) {
            await this.loadPlans();
        }
    },

    // ========================================
    // ACTIONS
    // ========================================

    async viewAtomic(atomicId) {
        try {
            const atomic = await API.testPlans.getAtomic(atomicId);
            if (atomic.error) {
                showToast(atomic.error, 'error');
                return;
            }
            this.showAtomicDetailModal(atomic);
        } catch (error) {
            showToast('Failed to load atomic details', 'error');
            console.error(error);
        }
    },

    showAtomicDetailModal(atomic) {
        const platforms = (atomic.supported_platforms || []).map(p =>
            `<span class="platform-badge platform-${p}">${p}</span>`
        ).join('');

        const inputArgs = atomic.input_arguments || {};
        const inputArgsHtml = Object.keys(inputArgs).length > 0 ? `
            <div class="detail-section">
                <h4>Input Arguments</h4>
                <div class="input-args-list">
                    ${Object.entries(inputArgs).map(([key, val]) => `
                        <div class="input-arg">
                            <span class="arg-name">${escapeHtml(key)}</span>
                            <span class="arg-desc">${escapeHtml(val.description || '')}</span>
                            <code class="arg-default">${escapeHtml(String(val.default || ''))}</code>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';

        const modalHtml = `
            <div class="modal-overlay" id="atomicDetailModal">
                <div class="modal-content modal-large">
                    <div class="modal-header">
                        <div class="modal-title-group">
                            <span class="technique-id">${escapeHtml(atomic.technique_id)}</span>
                            <h3>${escapeHtml(atomic.atomic_test_name)}</h3>
                        </div>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'atomicDetailModal')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="detail-section">
                            <div class="detail-meta">
                                <span class="technique-name">${escapeHtml(atomic.technique_name)}</span>
                                <span class="tactic-badge">${escapeHtml(atomic.tactic || '')}</span>
                                ${platforms}
                                ${atomic.elevation_required ? '<span class="elevation-badge">Requires Elevation</span>' : ''}
                            </div>
                        </div>

                        <div class="detail-section">
                            <h4>Description</h4>
                            <p class="atomic-description">${escapeHtml(atomic.description || 'No description')}</p>
                        </div>

                        ${inputArgsHtml}

                        <div class="detail-section">
                            <h4>Executor: ${escapeHtml(atomic.executor_name || 'manual')}</h4>
                            <div class="command-block">
                                <pre><code>${escapeHtml(atomic.executor_command || 'No command defined')}</code></pre>
                            </div>
                        </div>

                        ${atomic.executor_cleanup ? `
                        <div class="detail-section">
                            <h4>Cleanup Command</h4>
                            <div class="command-block cleanup">
                                <pre><code>${escapeHtml(atomic.executor_cleanup)}</code></pre>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.addAtomicToPlan', atomic.id)}>Add to Plan</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'atomicDetailModal')}>Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    async addAtomicToPlan(atomicId) {
        // Close any open atomic detail modal
        this.closeModal('atomicDetailModal');

        await this.ensurePlansLoaded();

        if (this.plans.length === 0) {
            showToast('No test plans exist. Create a plan first.', 'warning');
            return;
        }

        const modalHtml = `
            <div class="modal-overlay" id="addToPlanModal">
                <div class="modal-content modal-small">
                    <div class="modal-header">
                        <h3>Add to Test Plan</h3>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'addToPlanModal')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="selectPlanForAtomic">Select a plan:</label>
                            <select id="selectPlanForAtomic" class="form-select">
                                ${this.renderPlanOptions({ templateSuffix: ' (template)' })}
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.confirmAddToPlan', atomicId)}>Add</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'addToPlanModal')}>Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    async confirmAddToPlan(atomicId) {
        const planId = document.getElementById('selectPlanForAtomic').value;
        if (!planId) return;

        try {
            const result = await API.testPlans.addPlanItem(planId, { atomic_id: atomicId });
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Added to plan!', 'success');
                this.closeModal('addToPlanModal');
                // Update plans data in background (for item counts) without switching tabs
                this.loadPlans();  // Don't await - just update in background
            }
        } catch (error) {
            showToast('Failed to add to plan', 'error');
            console.error(error);
        }
    },

    /**
     * @param {'engagement'|'template'} [scope] - preselected scope for the new plan
     */
    createPlan(scope) {
        this.newPlanScope = scope || (this.currentEngagementId() !== null ? 'engagement' : 'template');
        this.showPlanModal(null);
    },

    async editPlan(planId) {
        try {
            const plan = await API.testPlans.getPlan(planId);
            if (plan.error) {
                showToast(plan.error, 'error');
                return;
            }
            this.showPlanEditor(plan);
        } catch (error) {
            showToast('Failed to load plan', 'error');
            console.error(error);
        }
    },

    /** Edit button in the plan detail view (L-21). */
    editCurrentPlan() {
        this.showPlanModal(this.currentEditPlan);
    },

    showPlanModal(plan) {
        const isEdit = plan !== null;
        const hasEngagement = this.currentEngagementId() !== null;
        const scope = (!hasEngagement || this.newPlanScope === 'template') ? 'template' : 'engagement';
        const engagementName = hasEngagement ? escapeHtml(AppState.activeEngagement.name || 'the active engagement') : '';
        const scopeField = isEdit ? `
                        <p class="plan-scope-note">${plan.is_template
                            ? 'Template: changes apply to future uses, not to plans already copied into engagements.'
                            : `Belongs to ${engagementName || 'its engagement'}.`}</p>
        ` : `
                        <fieldset class="form-group plan-scope-field">
                            <legend>Save to</legend>
                            <label class="plan-scope-option">
                                <input type="radio" name="planScope" value="engagement" ${scope === 'engagement' ? 'checked' : ''} ${hasEngagement ? '' : 'disabled'}>
                                <span>This engagement${hasEngagement ? ` <span class="plan-scope-context">${engagementName}</span>` : ' (select an engagement first)'}</span>
                            </label>
                            <label class="plan-scope-option">
                                <input type="radio" name="planScope" value="template" ${scope === 'template' ? 'checked' : ''}>
                                <span>Template library <span class="plan-scope-context">reusable across engagements</span></span>
                            </label>
                        </fieldset>
        `;
        const modalHtml = `
            <div class="modal-overlay" id="planModal">
                <div class="modal-content modal-medium">
                    <div class="modal-header">
                        <h3>${isEdit ? `Edit ${plan.is_template ? 'Template' : 'Test Plan'}` : 'Create Test Plan'}</h3>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'planModal')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        ${scopeField}
                        <div class="form-group">
                            <label for="planName">Plan Name *</label>
                            <input type="text" id="planName" class="form-input" value="${isEdit ? escapeHtml(plan.name) : ''}" placeholder="e.g., Windows Lateral Movement Tests">
                        </div>
                        <div class="form-group">
                            <label for="planDescription">Description</label>
                            <textarea id="planDescription" class="form-textarea" rows="3" placeholder="Describe the purpose of this test plan">${isEdit ? escapeHtml(plan.description || '') : ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label for="planPlatform">Target Platform</label>
                            <select id="planPlatform" class="form-select">
                                <option value="all" ${!isEdit || plan.target_platform === 'all' ? 'selected' : ''}>All Platforms</option>
                                <option value="windows" ${isEdit && plan.target_platform === 'windows' ? 'selected' : ''}>Windows</option>
                                <option value="linux" ${isEdit && plan.target_platform === 'linux' ? 'selected' : ''}>Linux</option>
                                <option value="macos" ${isEdit && plan.target_platform === 'macos' ? 'selected' : ''}>macOS</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="planTags">Tags</label>
                            <input type="text" id="planTags" class="form-input" value="${isEdit ? escapeHtml(plan.tags || '') : ''}" placeholder="e.g., lateral-movement, windows, critical">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.savePlan', isEdit ? plan.id : 'null')}>${isEdit ? 'Save Changes' : 'Create Plan'}</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'planModal')}>Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('planName').focus();
    },

    async savePlan(planId) {
        const name = document.getElementById('planName').value.trim();
        const description = document.getElementById('planDescription').value.trim();
        const platform = document.getElementById('planPlatform').value;
        const tags = document.getElementById('planTags').value.trim();

        if (!name) {
            showToast('Plan name is required', 'error');
            return;
        }

        const data = {
            name,
            description,
            target_platform: platform,
            tags
        };

        let isTemplate = false;
        if (!planId) {
            const scopeInput = document.querySelector('input[name="planScope"]:checked');
            isTemplate = !scopeInput || scopeInput.value === 'template';
            data.is_template = isTemplate;
        }

        try {
            let result;
            if (planId) {
                result = await API.testPlans.updatePlan(planId, data);
            } else {
                result = await API.testPlans.createPlan(data);
            }

            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast(planId ? 'Plan updated!' : (isTemplate ? 'Template created!' : 'Plan created!'), 'success');
                this.closeModal('planModal');
                await this.loadPlans();
                // Editing from inside the plan editor: refresh the editor, not the list
                if (planId && this.currentEditPlan && this.currentEditPlan.id === planId) {
                    await this.editPlan(planId);
                } else {
                    this.switchTab('plans');
                }
            }
        } catch (error) {
            showToast('Failed to save plan', 'error');
            console.error(error);
        }
    },

    showPlanEditor(plan) {
        // The item filter belongs to one plan; opening another plan clears it
        if (this._filterPlanId !== plan.id) {
            this.planItemFilter = '';
            this._filterPlanId = plan.id;
        }
        this.currentEditPlan = plan;
        const items = plan.items || [];

        const content = document.getElementById('testplansContent');
        content.innerHTML = `
            <div class="plan-editor">
                <div class="editor-header">
                    <div class="editor-title">
                        <button class="btn btn-secondary btn-back" ${on('click', 'TestPlansManager.closePlanEditor')}>
                            &larr; Back to Plans
                        </button>
                        <h2>${escapeHtml(plan.name)}</h2>
                        <span class="plan-scope-badge ${plan.is_template ? 'is-template' : ''}">${plan.is_template ? 'Template' : 'Engagement plan'}</span>
                        <button class="btn btn-sm btn-secondary" ${on('click', 'TestPlansManager.editCurrentPlan')}>
                            Edit Details
                        </button>
                    </div>
                    <div class="editor-actions">
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.showAddFromLibraryModal')}>
                            + Add from Library
                        </button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.showAddCustomTestModal')}>
                            + Add Custom Test
                        </button>
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.generateScript', plan.id)}>
                            Generate Script
                        </button>
                    </div>
                </div>

                ${items.some(i => i.atomic_missing) ? `
                    <div class="plan-missing-banner" role="status">
                        <strong>${items.filter(i => i.atomic_missing).length} of ${items.length} tests are missing from the Atomics library.</strong>
                        Their library entries were replaced when the library was re-downloaded. They are skipped in generated
                        scripts; remove them, or rebuild this plan from its Navigator layer.
                    </div>
                ` : ''}
                <div class="editor-meta">
                    <span class="meta-item"><strong>Platform:</strong> ${escapeHtml(plan.target_platform || 'all')}</span>
                    <span class="meta-item" id="planItemCounts">${this.planCountsText(items)}</span>
                    ${plan.description ? `<span class="meta-item meta-desc">${escapeHtml(plan.description)}</span>` : ''}
                </div>

                ${items.length > 10 ? `
                    <div class="editor-filter">
                        <input type="search" id="planItemFilter" class="form-input" placeholder="Filter by technique, test name, executor or platform"
                               aria-label="Filter tests in this plan" value="${escapeHtml(this.planItemFilter || '')}"
                               ${on('input', 'TestPlansManager.setPlanItemFilter', ARG.value)}>
                        <span class="editor-filter-count" id="planItemFilterCount" aria-live="polite"></span>
                    </div>
                ` : ''}

                <div class="editor-items" id="planItemsList">
                    ${items.length === 0 ? `
                        <div class="items-empty">
                            <p>No tests in this plan yet.</p>
                            <p>Add tests from the Atomics Library or create custom tests.</p>
                        </div>
                    ` : `
                        <div class="items-list-compact">
                            ${items.map((item, index) => this.renderPlanItem(item, index, plan.id)).join('')}
                        </div>
                    `}
                </div>
            </div>
        `;

        // Initialize Lucide icons for the action buttons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        this.applyPlanItemFilter();
    },

    planCountsText(items) {
        const excluded = items.filter(i => i.enabled === 0).length;
        return `<strong>Tests:</strong> ${items.length}${excluded ? ` (${excluded} excluded from scripts)` : ''}`;
    },

    setPlanItemFilter(value) {
        this.planItemFilter = value;
        clearTimeout(this._planFilterTimer);
        this._planFilterTimer = setTimeout(() => this.applyPlanItemFilter(), 150);
    },

    /** Hide plan rows that don't match the editor filter (client-side; no re-render). */
    applyPlanItemFilter() {
        const rows = document.querySelectorAll('#planItemsList .item-row');
        const q = (this.planItemFilter || '').trim().toLowerCase();
        let shown = 0;
        rows.forEach(row => {
            const match = !q || (row.dataset.search || '').includes(q);
            row.hidden = !match;
            if (match) shown++;
        });
        const count = document.getElementById('planItemFilterCount');
        if (count) count.textContent = q ? `Showing ${shown} of ${rows.length}` : '';
    },

    /** Re-fetch the open plan and redraw the editor without losing scroll or filter. */
    async refreshPlanEditor(planId) {
        const scrollY = window.scrollY;
        const plan = await API.testPlans.getPlan(planId);
        if (plan && !plan.error) {
            this.showPlanEditor(plan);
            window.scrollTo(0, scrollY);
        }
    },

    renderPlanItem(item, index, planId) {
        const isCustom = !item.atomic_id;
        const name = item.atomic_missing
            ? 'Missing from Atomics library'
            : (item.atomic_test_name || item.custom_name || 'Unnamed Test');
        const techniqueId = item.technique_id || '';
        const platforms = item.supported_platforms || [];
        const isEnabled = item.enabled !== 0;

        return `
            <div class="item-row ${!isEnabled ? 'item-disabled' : ''} ${item.atomic_missing ? 'item-missing' : ''} ${item.needs_review ? 'item-needs-review' : ''}" data-item-id="${item.id}"
                 data-search="${escapeHtml(`${techniqueId} ${name} ${item.executor_name || ''} ${platforms.join(' ')}`.toLowerCase())}">
                <div class="item-row-order">${index + 1}</div>
                <div class="item-row-info">
                    ${techniqueId ? `<span class="item-row-technique">${escapeHtml(techniqueId)}</span>` : ''}
                    <span class="item-row-name">${escapeHtml(name)}</span>
                    ${isCustom ? '<span class="item-row-custom">Custom</span>' : ''}
                    ${item.needs_review ? '<span class="item-row-review" title="The Atomics refresh changed what this test runs. Check its command, then mark it reviewed.">Changed upstream &mdash; review</span>' : ''}
                </div>
                <div class="item-row-meta">
                    ${item.executor_name ? `<span class="item-row-executor">${escapeHtml(item.executor_name)}</span>` : ''}
                    ${platforms.slice(0, 2).map(p => `<span class="item-row-platform">${escapeHtml(p)}</span>`).join('')}
                    ${item.notes ? `<span class="item-row-notes" role="img" aria-label="Has notes" title="${escapeHtml(item.notes)}"><i data-lucide="notebook-pen"></i></span>` : ''}
                </div>
                <div class="item-row-actions">
                    ${item.needs_review ? `<button class="btn btn-secondary btn-xs" ${on('click', 'TestPlansManager.markItemReviewed', planId, item.id)} title="I have checked this test's current command">Mark reviewed</button>` : ''}
                    <button class="btn btn-icon btn-xs" ${on('click', 'TestPlansManager.editPlanItem', planId, item.id)} title="Edit" aria-label="Edit ${escapeHtml(name)}">
                        <i data-lucide="edit-2"></i>
                    </button>
                    <label class="item-include" title="Include in generated scripts and executions">
                        <input type="checkbox" ${isEnabled ? 'checked' : ''}
                               ${on('change', 'TestPlansManager.toggleItemEnabledFromCheckbox', planId, item.id, ARG.el)}
                               aria-label="Include ${escapeHtml(name)} in scripts">
                        <span>Include</span>
                    </label>
                    <button class="btn btn-icon btn-xs btn-danger" ${on('click', 'TestPlansManager.removePlanItem', planId, item.id)} title="Remove" aria-label="Remove ${escapeHtml(name)} from plan">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        `;
    },

    closePlanEditor() {
        this.currentEditPlan = null;
        this.planItemFilter = '';
        this.switchTab('plans');
    },

    async showAddFromLibraryModal() {
        // The modal queries the server itself so it can reach the whole
        // library, independent of what the browse tab has loaded.
        this.librarySelected = new Set();
        this.libraryModalAtomics = [];
        this.libraryModalTotal = 0;
        this.libraryModalError = null;

        const modalHtml = `
            <div class="modal-overlay" id="addFromLibraryModal">
                <div class="modal-content modal-large">
                    <div class="modal-header">
                        <h3>Add from Atomics Library</h3>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'addFromLibraryModal')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="library-search">
                            <input type="text" id="librarySearchInput" class="form-input" placeholder="Search techniques, tests..." aria-label="Search atomics library" ${on('input', 'TestPlansManager.filterLibraryModal')}>
                            <select id="libraryPlatformFilter" class="form-select" aria-label="Filter by platform" ${on('change', 'TestPlansManager.searchLibraryModal')}>
                                <option value="">All Platforms</option>
                                <option value="windows">Windows</option>
                                <option value="linux">Linux</option>
                                <option value="macos">macOS</option>
                            </select>
                        </div>
                        <div class="library-list" id="libraryModalList">
                            <div class="loading">Loading atomics...</div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <span class="selection-count" id="librarySelectionCount">0 selected</span>
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.addSelectedAtomics')}>Add Selected</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'addFromLibraryModal')}>Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        await this.searchLibraryModal();
    },

    renderLibraryModalList(atomics) {
        if (this.libraryModalError) {
            return `<p class="library-empty" role="alert">Failed to load atomics: ${escapeHtml(this.libraryModalError)}</p>`;
        }
        if (atomics.length === 0) {
            const hasQuery = document.getElementById('librarySearchInput')?.value ||
                document.getElementById('libraryPlatformFilter')?.value;
            return hasQuery
                ? '<p class="library-empty">No tests match your search.</p>'
                : '<p class="library-empty">No atomics available. Download the library first.</p>';
        }

        // Group by technique
        const grouped = {};
        atomics.forEach(a => {
            if (!grouped[a.technique_id]) {
                grouped[a.technique_id] = {
                    technique_id: a.technique_id,
                    technique_name: a.technique_name,
                    tests: []
                };
            }
            grouped[a.technique_id].tests.push(a);
        });

        return Object.values(grouped).slice(0, 50).map(t => `
            <div class="library-technique">
                <div class="library-technique-header" ${on('click', 'this.classList.toggle', 'expanded')}>
                    <span class="technique-id">${escapeHtml(t.technique_id)}</span>
                    <span class="technique-name">${escapeHtml(t.technique_name)}</span>
                    <span class="test-count">${t.tests.length} tests</span>
                </div>
                <div class="library-technique-tests">
                    ${t.tests.map(test => `
                        <label class="library-test-item">
                            <input type="checkbox" name="libraryAtomic" value="${test.id}" ${this.librarySelected.has(test.id) ? 'checked' : ''} ${on('change', 'TestPlansManager.toggleLibrarySelection', test.id, ARG.checked)}>
                            <span class="test-name">${escapeHtml(test.atomic_test_name)}</span>
                            <span class="test-platforms">${(test.supported_platforms || []).join(', ')}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `).join('') + (Object.keys(grouped).length > 50 || this.libraryModalTotal > atomics.length
            ? `<p class="more-hint">Showing ${Math.min(50, Object.keys(grouped).length)} techniques (${atomics.length.toLocaleString()} of ${this.libraryModalTotal.toLocaleString()} matching tests). Use search to narrow results.</p>`
            : '');
    },

    /**
     * Debounced entry point for the modal's search box.
     */
    filterLibraryModal() {
        if (!this._debouncedLibrarySearch) {
            this._debouncedLibrarySearch = debounce(() => this.searchLibraryModal(), 300);
        }
        this._debouncedLibrarySearch();
    },

    /**
     * Query the server for the modal list so it covers the whole library.
     */
    async searchLibraryModal() {
        const list = document.getElementById('libraryModalList');
        if (!list) return;

        const search = document.getElementById('librarySearchInput')?.value.trim() || '';
        const platform = document.getElementById('libraryPlatformFilter')?.value || '';
        const params = { limit: 500, offset: 0 };
        if (search) params.search = search;
        if (platform) params.platform = platform;

        const seq = ++this.libraryRequestSeq;
        this.libraryModalError = null;
        try {
            const result = await API.testPlans.getAtomics(params);
            if (seq !== this.libraryRequestSeq) return;
            this.libraryModalAtomics = result.atomics || [];
            this.libraryModalTotal = result.total ?? this.libraryModalAtomics.length;
        } catch (error) {
            if (seq !== this.libraryRequestSeq) return;
            console.error('Failed to search atomics:', error);
            this.libraryModalAtomics = [];
            this.libraryModalTotal = 0;
            this.libraryModalError = error.message || 'Network error';
        }

        // Modal may have been closed while the request was in flight
        const current = document.getElementById('libraryModalList');
        if (current) {
            current.innerHTML = this.renderLibraryModalList(this.libraryModalAtomics);
        }
    },

    toggleLibrarySelection(atomicId, checked) {
        if (checked) {
            this.librarySelected.add(atomicId);
        } else {
            this.librarySelected.delete(atomicId);
        }
        this.updateLibrarySelectionCount();
    },

    updateLibrarySelectionCount() {
        const el = document.getElementById('librarySelectionCount');
        if (el) el.textContent = `${this.librarySelected.size} selected`;
    },

    async addSelectedAtomics() {
        // Selections persist across searches, so read from state, not the DOM
        const atomicIds = Array.from(this.librarySelected);

        if (atomicIds.length === 0) {
            showToast('Select at least one test', 'warning');
            return;
        }

        if (!this.currentEditPlan) {
            showToast('No plan selected', 'error');
            return;
        }

        try {
            const result = await API.testPlans.addBulkItems(this.currentEditPlan.id, atomicIds);
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast(`Added ${atomicIds.length} tests to plan`, 'success');
                this.closeModal('addFromLibraryModal');
                // Reload plan to show new items
                const plan = await API.testPlans.getPlan(this.currentEditPlan.id);
                if (!plan.error) {
                    this.showPlanEditor(plan);
                }
            }
        } catch (error) {
            showToast('Failed to add tests', 'error');
            console.error(error);
        }
    },

    showAddCustomTestModal() {
        const modalHtml = `
            <div class="modal-overlay" id="addCustomTestModal">
                <div class="modal-content modal-medium">
                    <div class="modal-header">
                        <h3>Add Custom Test</h3>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'addCustomTestModal')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="customTestName">Test Name *</label>
                            <input type="text" id="customTestName" class="form-input" placeholder="e.g., Custom Persistence Check">
                        </div>
                        <div class="form-group">
                            <label for="customTestPlatform">Platform</label>
                            <select id="customTestPlatform" class="form-select">
                                <option value="windows">Windows</option>
                                <option value="linux">Linux</option>
                                <option value="macos">macOS</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="customTestCommand">Command</label>
                            <textarea id="customTestCommand" class="form-textarea code-textarea" rows="6" placeholder="Enter the command to execute..."></textarea>
                        </div>
                        <div class="form-group">
                            <label for="customTestNotes">Notes</label>
                            <textarea id="customTestNotes" class="form-textarea" rows="2" placeholder="Optional notes about this test..."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.saveCustomTest')}>Add Test</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'addCustomTestModal')}>Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('customTestName').focus();
    },

    async saveCustomTest() {
        const name = document.getElementById('customTestName').value.trim();
        const platform = document.getElementById('customTestPlatform').value;
        const command = document.getElementById('customTestCommand').value.trim();
        const notes = document.getElementById('customTestNotes').value.trim();

        if (!name) {
            showToast('Test name is required', 'error');
            return;
        }

        if (!this.currentEditPlan) {
            showToast('No plan selected', 'error');
            return;
        }

        try {
            const result = await API.testPlans.addPlanItem(this.currentEditPlan.id, {
                custom_name: name,
                custom_platform: platform,
                custom_command: command,
                notes: notes
            });

            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Custom test added!', 'success');
                this.closeModal('addCustomTestModal');
                // Reload plan
                const plan = await API.testPlans.getPlan(this.currentEditPlan.id);
                if (!plan.error) {
                    this.showPlanEditor(plan);
                }
            }
        } catch (error) {
            showToast('Failed to add custom test', 'error');
            console.error(error);
        }
    },

    async editPlanItem(planId, itemId) {
        // Get the current plan to find the item
        try {
            const plan = await API.testPlans.getPlan(planId);
            if (plan.error) {
                showToast(plan.error, 'error');
                return;
            }

            const item = plan.items.find(i => i.id === itemId);
            if (!item) {
                showToast('Item not found', 'error');
                return;
            }

            this.showEditItemModal(planId, item);
        } catch (error) {
            showToast('Failed to load item', 'error');
            console.error(error);
        }
    },

    showEditItemModal(planId, item) {
        const isCustom = !item.atomic_id;
        const originalName = item.atomic_test_name || '';
        const originalCommand = item.executor_command || '';
        const displayName = item.custom_name || originalName || 'Unnamed Test';
        const displayCommand = item.custom_command || originalCommand || '';
        const techniqueId = item.technique_id || 'Custom';

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'editItemModal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 700px;">
                <div class="modal-header">
                    <h3>Edit Test Item</h3>
                    <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'editItemModal')}>&times;</button>
                </div>
                <div class="modal-body">
                    <div class="item-info" style="background: var(--bg-secondary); padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                        <div style="font-weight: 600; margin-bottom: 4px;">${escapeHtml(techniqueId)}</div>
                        ${!isCustom ? `<div style="font-size: 0.9em; color: var(--text-secondary);">Original: ${escapeHtml(originalName)}</div>` : ''}
                    </div>

                    <div class="form-group">
                        <label for="editItemName">Test Name ${!isCustom ? '(leave blank to use original)' : ''}</label>
                        <input type="text" id="editItemName" class="form-control"
                               value="${escapeHtml(item.custom_name || '')}"
                               placeholder="${escapeHtml(originalName || 'Enter test name')}">
                    </div>

                    <div class="form-group">
                        <label for="editItemCommand">Command ${!isCustom ? '(leave blank to use original)' : ''}</label>
                        <textarea id="editItemCommand" class="form-control" rows="6"
                                  placeholder="${escapeHtml(originalCommand || 'Enter command')}">${escapeHtml(item.custom_command || '')}</textarea>
                        ${!isCustom && originalCommand ? `
                            <div style="margin-top: 12px;">
                                <label style="margin-bottom: 8px; display: block;">Original Command:</label>
                                <pre id="originalCommandDisplay" style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; font-size: 0.85em; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; margin: 0 0 8px 0;">${escapeHtml(originalCommand)}</pre>
                                <div style="display: flex; gap: 8px;">
                                    <button class="btn btn-sm btn-secondary" data-action="copy-original-command" data-command="${escapeHtml(originalCommand)}">
                                        Copy to Clipboard
                                    </button>
                                    <button class="btn btn-sm btn-secondary" data-action="use-original-command" data-command="${escapeHtml(originalCommand)}">
                                        Use as Custom Command
                                    </button>
                                </div>
                            </div>
                        ` : ''}
                    </div>

                    <div class="form-group">
                        <label for="editItemNotes">Notes</label>
                        <textarea id="editItemNotes" class="form-control" rows="3"
                                  placeholder="Add notes about this test...">${escapeHtml(item.notes || '')}</textarea>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="editItemEnabled" ${item.enabled ? 'checked' : ''}>
                            Enabled (include in script generation)
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'editItemModal')}>Cancel</button>
                    <button class="btn btn-primary" ${on('click', 'TestPlansManager.saveItemEdit', planId, item.id)}>
                        Save Changes
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    async saveItemEdit(planId, itemId) {
        const customName = document.getElementById('editItemName').value.trim();
        const customCommand = document.getElementById('editItemCommand').value.trim();
        const notes = document.getElementById('editItemNotes').value.trim();
        const enabled = document.getElementById('editItemEnabled').checked ? 1 : 0;

        try {
            const result = await API.testPlans.updatePlanItem(planId, itemId, {
                custom_name: customName || null,
                custom_command: customCommand || null,
                notes: notes || null,
                enabled: enabled
            });

            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Item updated', 'success');
                this.closeModal('editItemModal');

                // Reload plan editor
                const plan = await API.testPlans.getPlan(planId);
                if (!plan.error) {
                    this.showPlanEditor(plan);
                }
            }
        } catch (error) {
            showToast('Failed to update item', 'error');
            console.error(error);
        }
    },

    /**
     * Clear the re-review flag an Atomics refresh set on this item (M-6).
     */
    async markItemReviewed(planId, itemId) {
        try {
            const result = await API.testPlans.updatePlanItem(planId, itemId, { reviewed: true });
            if (result && result.error) throw new Error(result.error);
        } catch (error) {
            showToast(error.message || 'Failed to mark the test reviewed', 'error');
            return;
        }
        const item = this.currentEditPlan?.items?.find(i => i.id === itemId);
        if (item) item.needs_review = 0;
        const row = document.querySelector(`#planItemsList .item-row[data-item-id="${itemId}"]`);
        if (row && item) {
            row.outerHTML = this.renderPlanItem(item, this.currentEditPlan.items.indexOf(item), planId);
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        showToast('Marked reviewed', 'success');
    },

    /** Plan item checkbox (L-21). */
    toggleItemEnabledFromCheckbox(planId, itemId, checkbox) {
        return this.toggleItemEnabled(planId, itemId, checkbox.checked ? 1 : 0, checkbox);
    },

    async toggleItemEnabled(planId, itemId, enabled, checkbox) {
        try {
            const result = await API.testPlans.updatePlanItem(planId, itemId, { enabled });
            if (result && result.error) throw new Error(result.error);
        } catch (error) {
            showToast(error.message || 'Failed to update test', 'error');
            if (checkbox) checkbox.checked = !enabled;   // revert the control
            return;
        }

        // Update in place: re-rendering an 800-row plan would lose scroll and focus
        const item = this.currentEditPlan?.items?.find(i => i.id === itemId);
        if (item) item.enabled = enabled;
        document.querySelector(`#planItemsList .item-row[data-item-id="${itemId}"]`)?.classList.toggle('item-disabled', !enabled);
        const counts = document.getElementById('planItemCounts');
        if (counts && this.currentEditPlan) counts.innerHTML = this.planCountsText(this.currentEditPlan.items || []);
    },

    async removePlanItem(planId, itemId) {
        if (!confirm('Remove this test from the plan?')) return;

        try {
            const result = await API.testPlans.deletePlanItem(planId, itemId);
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Test removed', 'success');
                await this.refreshPlanEditor(planId);
            }
        } catch (error) {
            showToast('Failed to remove test', 'error');
        }
    },

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        const returnTo = this._modalReturnFocus.get(modalId);
        this._modalReturnFocus.delete(modalId);
        modal.remove();
        if (returnTo && returnTo.isConnected) returnTo.focus();
    },

    // ---------- Dialog accessibility ----------
    // Every Test Plans modal gets role/label, initial focus, Esc to close,
    // Tab kept inside, and focus returned to its opener. A MutationObserver
    // applies this so the individual modal builders stay as they are.

    watchModals() {
        if (this._modalObserver || typeof MutationObserver === 'undefined') return;
        this._modalObserver = new MutationObserver(mutations => {
            mutations.forEach(m => m.addedNodes.forEach(node => {
                if (node.nodeType === 1 && node.classList.contains('modal-overlay')
                        && node.id && node.innerHTML.includes('TestPlansManager.')) {
                    this.enhanceModal(node);
                }
            }));
        });
        this._modalObserver.observe(document.body, { childList: true });

        // Builders often focus a field synchronously, before the observer
        // runs, so remember recent focus to find the real opener.
        this._focusHistory = [];
        document.addEventListener('focusin', (e) => {
            this._focusHistory.push(e.target);
            if (this._focusHistory.length > 6) this._focusHistory.shift();
        }, true);
    },

    modalFocusables(root) {
        return [...root.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
            'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )].filter(el => el.offsetParent !== null || el === document.activeElement);
    },

    enhanceModal(overlay) {
        if (overlay.dataset.a11y) return;
        overlay.dataset.a11y = '1';

        const dialog = overlay.querySelector('.modal-content') || overlay;
        if (!dialog.hasAttribute('role')) dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        if (!dialog.hasAttribute('aria-labelledby')) {
            const heading = dialog.querySelector('.modal-header h2, .modal-header h3, h2, h3');
            if (heading) {
                if (!heading.id) heading.id = `${overlay.id}-title`;
                dialog.setAttribute('aria-labelledby', heading.id);
            }
        }
        overlay.querySelectorAll('.modal-close').forEach(btn => {
            if (!btn.hasAttribute('aria-label')) btn.setAttribute('aria-label', 'Close');
        });

        const candidates = [document.activeElement, ...[...(this._focusHistory || [])].reverse()];
        const opener = candidates.find(el => el && el !== document.body && el.isConnected && !overlay.contains(el));
        if (opener) this._modalReturnFocus.set(overlay.id, opener);

        overlay.addEventListener('keydown', (e) => this.onModalKeydown(e, overlay, dialog));

        // Builders that focus a field themselves win; otherwise focus the
        // first control (not the close button), else the dialog itself.
        requestAnimationFrame(() => {
            if (!overlay.isConnected || overlay.contains(document.activeElement)) return;
            const target = overlay.querySelector('[autofocus]')
                || this.modalFocusables(overlay).find(el => !el.classList.contains('modal-close'));
            if (target) {
                target.focus();
            } else {
                dialog.tabIndex = -1;
                dialog.focus();
            }
        });
    },

    onModalKeydown(e, overlay, dialog) {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            // Use the modal's own close button so custom close logic runs
            const closeBtn = overlay.querySelector('.modal-close');
            if (closeBtn) closeBtn.click();
            else this.closeModal(overlay.id);
            return;
        }
        if (e.key !== 'Tab') return;
        const focusables = this.modalFocusables(dialog);
        if (focusables.length === 0) {
            e.preventDefault();
            return;
        }
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    },

    /**
     * Copy a plan. target: undefined (same scope), 'engagement', or 'template'.
     */
    async copyPlan(planId, target, successMessage, failureMessage) {
        try {
            const result = await API.testPlans.duplicatePlan(planId, target ? { target } : {});
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast(successMessage(result), 'success');
                await this.loadPlans();
                this.switchTab('plans');
            }
        } catch (error) {
            showToast(error.message || failureMessage, 'error');
        }
    },

    async duplicatePlan(planId) {
        await this.copyPlan(planId, undefined, () => 'Plan duplicated!', 'Failed to duplicate plan');
    },

    async useTemplate(planId) {
        const engagementName = AppState?.activeEngagement?.name || 'this engagement';
        await this.copyPlan(planId, 'engagement',
            plan => `Added "${plan.name}" to ${engagementName}`,
            'Failed to copy template');
    },

    async saveAsTemplate(planId) {
        await this.copyPlan(planId, 'template',
            plan => `Saved "${plan.name}" as a template`,
            'Failed to save template');
    },

    async deletePlan(planId) {
        const plan = this.plans.find(p => p.id === planId);
        const message = plan?.is_template
            ? 'Delete this template? Plans already copied into engagements are kept.'
            : 'Delete this plan? Its execution records in this engagement are deleted too. This cannot be undone.';
        if (!confirm(message)) return;

        try {
            const result = await API.testPlans.deletePlan(planId);
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Plan deleted', 'success');
                await this.loadPlans();
                this.switchTab('plans');
            }
        } catch (error) {
            showToast('Failed to delete plan', 'error');
        }
    },

    async generateScript(planId) {
        // Get plan details to show name in modal
        try {
            const plan = await API.testPlans.getPlan(planId);
            if (plan.error) {
                showToast(plan.error, 'error');
                return;
            }

            const enabledCount = (plan.items || []).filter(i => i.enabled).length;
            if (enabledCount === 0) {
                showToast('No enabled tests in this plan', 'error');
                return;
            }

            this.showGenerateScriptModal(plan);
        } catch (error) {
            showToast('Failed to load plan', 'error');
            console.error(error);
        }
    },

    showGenerateScriptModal(plan) {
        const enabledItems = (plan.items || []).filter(i => i.enabled);

        // Count items by platform compatibility
        let linuxCount = 0, windowsCount = 0;
        enabledItems.forEach(item => {
            const platforms = item.supported_platforms || [];
            if (platforms.length === 0) {
                // Custom test - count for both
                linuxCount++;
                windowsCount++;
            } else {
                if (platforms.includes('linux') || platforms.includes('macos')) linuxCount++;
                if (platforms.includes('windows')) windowsCount++;
            }
        });

        // Auto-select platform with most compatible tests
        const defaultPlatform = linuxCount >= windowsCount ? 'linux' : 'windows';

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'generateScriptModal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 700px;">
                <div class="modal-header">
                    <h3>Generate Script - Platform Matching</h3>
                    <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'generateScriptModal')}>&times;</button>
                </div>
                <div class="modal-body">
                    <p style="margin-bottom: 12px;">Generate an executable script for: <strong>${escapeHtml(plan.name)}</strong></p>

                    <!-- Tabs -->
                    <div class="script-modal-tabs" style="display: flex; border-bottom: 1px solid var(--border-color); margin-bottom: 12px;">
                        <button class="script-tab active" data-tab="platform" ${on('click', 'TestPlansManager.switchScriptTab', 'platform')} style="padding: 8px 16px; border: none; background: none; cursor: pointer; border-bottom: 2px solid var(--primary-color); color: var(--text-color); font-weight: 600;">
                            Platform
                        </button>
                        <button class="script-tab" data-tab="instructions" ${on('click', 'TestPlansManager.switchScriptTab', 'instructions')} style="padding: 8px 16px; border: none; background: none; cursor: pointer; border-bottom: 2px solid transparent; color: var(--text-muted);">
                            Instructions
                        </button>
                    </div>

                    <!-- Platform Tab -->
                    <div id="scriptTabPlatform" class="script-tab-content">
                        <!-- Auto-match summary -->
                        <div style="background: var(--bg-tertiary); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                            <i data-lucide="check-circle" style="width: 18px; height: 18px; color: var(--success-color); flex-shrink: 0;"></i>
                            <div>
                                <strong style="font-size: 0.95em;">Auto-matched to ${defaultPlatform === 'linux' ? 'Bash (Linux/macOS)' : 'PowerShell (Windows)'}</strong>
                                <span style="font-size: 0.85em; color: var(--text-muted); margin-left: 8px;">${defaultPlatform === 'linux' ? linuxCount : windowsCount} compatible tests</span>
                            </div>
                        </div>

                        <!-- Platform Selection - List Layout -->
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="font-size: 0.9em; font-weight: 600; margin-bottom: 8px; display: block;">Platform Selection:</label>
                            <div class="platform-options" style="display: flex; flex-direction: column; gap: 8px;">
                                <label class="platform-option" style="display: flex; align-items: center; padding: 10px 12px; border: 2px solid ${defaultPlatform === 'linux' ? '#4f46e5' : 'var(--color-border)'}; border-radius: 6px; cursor: pointer; background: ${defaultPlatform === 'linux' ? 'rgba(79, 70, 229, 0.05)' : 'transparent'}; transition: all 0.2s;">
                                    <input type="radio" name="scriptPlatform" value="linux" ${defaultPlatform === 'linux' ? 'checked' : ''} ${linuxCount === 0 ? 'disabled' : ''} style="margin-right: 10px;">
                                    <span class="platform-icon"><i data-lucide="terminal"></i></span>
                                    <span style="font-weight: 600; font-size: 0.95em;">Bash (Linux/macOS)</span>
                                    <span style="font-size: 0.85em; color: var(--color-text-tertiary); margin-left: auto;">${linuxCount} tests</span>
                                </label>
                                <label class="platform-option" style="display: flex; align-items: center; padding: 10px 12px; border: 2px solid ${defaultPlatform === 'windows' ? '#4f46e5' : 'var(--color-border)'}; border-radius: 6px; cursor: pointer; background: ${defaultPlatform === 'windows' ? 'rgba(79, 70, 229, 0.05)' : 'transparent'}; transition: all 0.2s;">
                                    <input type="radio" name="scriptPlatform" value="windows" ${defaultPlatform === 'windows' ? 'checked' : ''} ${windowsCount === 0 ? 'disabled' : ''} style="margin-right: 10px;">
                                    <span class="platform-icon"><i data-lucide="square-terminal"></i></span>
                                    <span style="font-weight: 600; font-size: 0.95em;">PowerShell (Windows)</span>
                                    <span style="font-size: 0.85em; color: var(--color-text-tertiary); margin-left: auto;">${windowsCount} tests</span>
                                </label>
                            </div>
                        </div>

                        <!-- Warning -->
                        <div class="script-warning" style="background: rgba(255, 193, 7, 0.08); border: 1px solid rgba(255, 193, 7, 0.4); border-radius: 6px; padding: 8px 10px; margin-bottom: 12px; font-size: 0.85em;">
                            <strong class="script-warning-label"><i data-lucide="triangle-alert"></i> Warning:</strong>
                            <span style="color: #856404; margin-left: 4px;">Contains commands that may modify system state. The script asks you to type the target's hostname before anything runs.</span>
                        </div>

                        <!-- README Option -->
                        <div style="padding: 8px 10px; background: var(--bg-tertiary); border-radius: 6px;">
                            <label style="display: flex; align-items: center; cursor: pointer;">
                                <input type="checkbox" id="includeReadme" checked style="margin-right: 8px;">
                                <div style="flex: 1;">
                                    <span style="font-weight: 600; font-size: 0.9em;">Include README with instructions</span>
                                    <span style="font-size: 0.8em; color: var(--text-muted); margin-left: 6px;">(Downloads as ZIP)</span>
                                </div>
                            </label>
                        </div>
                    </div>

                    <!-- Instructions Tab -->
                    <div id="scriptTabInstructions" class="script-tab-content" style="display: none;">
                        <div style="max-height: 450px; overflow-y: auto; padding-right: 8px;">
                            <!-- Bash Instructions -->
                            <div class="instructions-section" style="margin-bottom: 15px;">
                                <h4 style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px; font-size: 1em;">
                                    <i data-lucide="terminal"></i> Bash Script (Linux/macOS)
                                </h4>
                                <div style="background: var(--bg-tertiary); border-radius: 6px; padding: 10px 12px;">
                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Prerequisites:</p>
                                    <ul style="margin: 0 0 10px 18px; font-size: 0.85em; color: var(--text-muted);">
                                        <li>Bash 4.0+ (for associative arrays)</li>
                                        <li>Root/sudo access may be required</li>
                                    </ul>

                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Quick Start:</p>
                                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px; font-size: 0.8em; overflow-x: auto; margin: 0 0 10px 0;"><code># Make executable and run
chmod +x script.sh
./script.sh

# Or run directly with bash
bash script.sh</code></pre>

                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Save Output for Evidence:</p>
                                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px; font-size: 0.8em; overflow-x: auto; margin: 0;"><code># Capture full session
script -c "./script.sh" session.log

# Or use tee
./script.sh 2>&1 | tee output.log</code></pre>
                                </div>
                            </div>

                            <!-- PowerShell Instructions -->
                            <div class="instructions-section" style="margin-bottom: 15px;">
                                <h4 style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px; font-size: 1em;">
                                    <i data-lucide="square-terminal"></i> PowerShell Script (Windows)
                                </h4>
                                <div style="background: var(--bg-tertiary); border-radius: 6px; padding: 10px 12px;">
                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Prerequisites:</p>
                                    <ul style="margin: 0 0 10px 18px; font-size: 0.85em; color: var(--text-muted);">
                                        <li>PowerShell 5.1+ (Windows 10/11, Server 2016+)</li>
                                        <li>Administrator privileges may be required</li>
                                        <li>Execution policy must allow scripts</li>
                                    </ul>

                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Quick Start:</p>
                                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px; font-size: 0.8em; overflow-x: auto; margin: 0 0 10px 0;"><code># Run the script
.\\script.ps1

# If execution policy blocks:
powershell -ExecutionPolicy Bypass -File ".\\script.ps1"</code></pre>

                                    <p style="margin-bottom: 6px; font-weight: 600; font-size: 0.9em;">Save Output for Evidence:</p>
                                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px; font-size: 0.8em; overflow-x: auto; margin: 0;"><code># Capture full session
Start-Transcript -Path "session.log"
.\\script.ps1
Stop-Transcript

# Or use Tee-Object
.\\script.ps1 | Tee-Object -FilePath "output.log"</code></pre>
                                </div>
                            </div>

                            <!-- Execution Modes -->
                            <div class="instructions-section" style="margin-bottom: 15px;">
                                <h4 style="margin-bottom: 10px; font-size: 1em;">Execution Modes</h4>
                                <div style="background: var(--bg-tertiary); border-radius: 6px; padding: 10px 12px;">
                                    <p style="margin-bottom: 8px; font-size: 0.85em; color: var(--text-muted);">
                                        The script first asks you to type this machine's hostname to confirm it is in scope
                                        (or set <code>PTVAULT_AUTHORIZED_HOST</code> for unattended runs), then asks for an execution mode:
                                    </p>
                                    <table style="width: 100%; font-size: 0.85em; border-collapse: collapse;">
                                        <tr style="border-bottom: 1px solid var(--border-color);">
                                            <td style="padding: 6px 0; font-weight: 600; width: 45%;">[1] Run ALL automatically</td>
                                            <td style="padding: 6px 0; color: var(--text-muted);">Type RUN ALL to confirm. Uses default inputs, skips tests needing root/Administrator when not elevated, runs cleanup after each test</td>
                                        </tr>
                                        <tr style="border-bottom: 1px solid var(--border-color);">
                                            <td style="padding: 6px 0; font-weight: 600;">[2] Run ONE AT A TIME</td>
                                            <td style="padding: 6px 0; color: var(--text-muted);">Prompt before each test; cleanup defaults to yes (recommended)</td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 6px 0; font-weight: 600;">[3] Interactive menu</td>
                                            <td style="padding: 6px 0; color: var(--text-muted);">Select individual tests from menu</td>
                                        </tr>
                                    </table>
                                </div>
                            </div>

                            <!-- Log Format -->
                            <div class="instructions-section">
                                <h4 style="margin-bottom: 10px; font-size: 1em;">Understanding Output</h4>
                                <div style="background: var(--bg-tertiary); border-radius: 6px; padding: 10px 12px;">
                                    <p style="margin-bottom: 8px; font-size: 0.85em; color: var(--text-muted);">
                                        Scripts produce timestamped, color-coded output for SIEM correlation:
                                    </p>
                                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px; font-size: 0.75em; overflow-x: auto; margin: 0;"><code><span style="color: #b48ead;">[2024-01-15 10:30:45]</span> <span style="color: #a3be8c;">[START]</span> Executing test 1: T1059.001
<span style="color: #b48ead;">[2024-01-15 10:30:46]</span> <span style="color: #a3be8c;">[PASS]</span> Test 1 completed (exit: 0, 1s)
<span style="color: #b48ead;">[2024-01-15 10:30:46]</span> <span style="color: #81a1c1;">[END]</span> Finished test 1</code></pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer" style="display: flex; gap: 8px; justify-content: flex-start; flex-wrap: wrap;">
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'generateScriptModal')} style="padding: 8px 16px;">Cancel</button>
                    <button class="btn btn-info" ${on('click', 'TestPlansManager.showMatchPreview', plan.id)} title="Preview which tests match each platform" style="padding: 8px 16px;">
                        <i data-lucide="eye" style="width: 14px; height: 14px; margin-right: 5px;"></i>
                        Preview Matched Atomics
                    </button>
                    <button class="btn btn-primary" ${on('click', 'TestPlansManager.downloadScript', plan.id)} style="padding: 8px 16px;">
                        <i data-lucide="download" style="width: 14px; height: 14px; margin-right: 5px;"></i>
                        Download Script
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Store plan data for preview
        modal.dataset.planData = JSON.stringify(plan);

        // Add hover effects and click behavior for platform options
        const platformOptions = modal.querySelectorAll('.platform-option');
        platformOptions.forEach(option => {
            const radio = option.querySelector('input[type="radio"]');

            // Handle label click to update selection
            option.addEventListener('click', function(e) {
                if (radio.disabled) return;

                // Update all options
                platformOptions.forEach(opt => {
                    const optRadio = opt.querySelector('input[type="radio"]');
                    const isSelected = optRadio.checked;
                    // Update border
                    opt.style.borderColor = isSelected ? '#4f46e5' : 'var(--color-border)';
                    // Update background
                    opt.style.background = isSelected ? 'rgba(79, 70, 229, 0.05)' : 'transparent';
                });
            });

            // Hover effects for list items
            if (!radio.disabled) {
                option.addEventListener('mouseenter', function() {
                    if (!radio.checked) {
                        option.style.borderColor = '#4f46e5';
                        option.style.background = 'rgba(79, 70, 229, 0.02)';
                    }
                });

                option.addEventListener('mouseleave', function() {
                    if (!radio.checked) {
                        option.style.borderColor = 'var(--color-border)';
                        option.style.background = 'transparent';
                    }
                });
            } else {
                option.style.opacity = '0.5';
                option.style.cursor = 'not-allowed';
            }
        });

        // Initialize Lucide icons in the modal
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    switchScriptTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.script-tab').forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
                btn.style.borderBottomColor = 'var(--primary-color)';
                btn.style.color = 'var(--text-color)';
                btn.style.fontWeight = '600';
            } else {
                btn.classList.remove('active');
                btn.style.borderBottomColor = 'transparent';
                btn.style.color = 'var(--text-muted)';
                btn.style.fontWeight = 'normal';
            }
        });

        // Show/hide content
        document.getElementById('scriptTabPlatform').style.display = tabName === 'platform' ? 'block' : 'none';
        document.getElementById('scriptTabInstructions').style.display = tabName === 'instructions' ? 'block' : 'none';
    },

    async downloadScriptQuick(planId) {
        // Quick download with auto-selected platform and default options
        const platformInput = document.querySelector('input[name="scriptPlatform"]:checked');
        if (!platformInput) {
            showToast('Please select a platform', 'error');
            return;
        }

        const platform = platformInput.value;
        const includeReadme = true; // Always include README for quick generation

        try {
            showToast('Generating script with README...', 'info');

            const blob = await API.testPlans.generateScript(planId, platform, includeReadme);

            // Always ZIP format for quick generation
            const filename = `test_plan_${planId}.zip`;

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.closeModal('generateScriptModal');
            showToast('Script and README downloaded!', 'success');
        } catch (error) {
            console.error('Failed to generate script:', error);
            showToast('Failed to generate script: ' + error.message, 'error');
        }
    },

    showMatchPreview(planId) {
        // Get plan data from the current modal
        const currentModal = document.getElementById('generateScriptModal');
        const plan = JSON.parse(currentModal.dataset.planData);
        const enabledItems = (plan.items || []).filter(i => i.enabled);

        // Categorize tests by platform
        const linuxTests = [];
        const windowsTests = [];
        const bothTests = [];
        const excludedTests = [];

        enabledItems.forEach(item => {
            const platforms = item.supported_platforms || [];
            const testName = item.custom_name || item.atomic_test_name || item.technique_id || 'Unnamed Test';
            const techniqueId = item.technique_id || 'Custom';

            if (platforms.length === 0) {
                // Custom test - works on both
                bothTests.push({ name: testName, techniqueId });
            } else {
                const hasLinux = platforms.includes('linux') || platforms.includes('macos');
                const hasWindows = platforms.includes('windows');

                if (hasLinux && hasWindows) {
                    bothTests.push({ name: testName, techniqueId });
                } else if (hasLinux) {
                    linuxTests.push({ name: testName, techniqueId });
                } else if (hasWindows) {
                    windowsTests.push({ name: testName, techniqueId });
                } else {
                    excludedTests.push({ name: testName, techniqueId });
                }
            }
        });

        // Hide current modal content and show preview
        currentModal.querySelector('.modal-content').style.display = 'none';

        const previewContent = document.createElement('div');
        previewContent.className = 'modal-content';
        previewContent.id = 'matchPreviewContent';
        previewContent.style.maxWidth = '800px';
        previewContent.innerHTML = `
            <div class="modal-header">
                <h3>Preview Matched Atomics</h3>
                <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'generateScriptModal')}>&times;</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 20px;">Platform compatibility breakdown for: <strong>${escapeHtml(plan.name)}</strong></p>

                <!-- Summary Cards -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px;">
                    <div style="background: rgba(0, 123, 255, 0.1); border: 2px solid #007bff; border-radius: 8px; padding: 15px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #007bff;">${linuxTests.length + bothTests.length}</div>
                        <div style="font-size: 0.9em; color: var(--text-muted); margin-top: 5px;">Bash compatible</div>
                    </div>
                    <div style="background: rgba(0, 123, 255, 0.1); border: 2px solid #0099ff; border-radius: 8px; padding: 15px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #0099ff;">${windowsTests.length + bothTests.length}</div>
                        <div style="font-size: 0.9em; color: var(--text-muted); margin-top: 5px;">PowerShell compatible</div>
                    </div>
                    <div style="background: rgba(40, 167, 69, 0.1); border: 2px solid #28a745; border-radius: 8px; padding: 15px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #28a745;">${bothTests.length}</div>
                        <div style="font-size: 0.9em; color: var(--text-muted); margin-top: 5px;">✓ Both Platforms</div>
                    </div>
                </div>

                <!-- Tabs for detailed view -->
                <div style="border-bottom: 1px solid var(--border-color); margin-bottom: 15px;">
                    <button class="preview-tab active" data-tab="linux" ${on('click', 'TestPlansManager.switchPreviewTab', 'linux')} style="padding: 10px 20px; border: none; background: none; cursor: pointer; border-bottom: 2px solid var(--primary-color); color: var(--text-color); font-weight: 600;">
                        <i data-lucide="terminal"></i> Bash (${linuxTests.length + bothTests.length})
                    </button>
                    <button class="preview-tab" data-tab="windows" ${on('click', 'TestPlansManager.switchPreviewTab', 'windows')} style="padding: 10px 20px; border: none; background: none; cursor: pointer; border-bottom: 2px solid transparent; color: var(--text-muted);">
                        <i data-lucide="square-terminal"></i> PowerShell (${windowsTests.length + bothTests.length})
                    </button>
                    <button class="preview-tab" data-tab="both" ${on('click', 'TestPlansManager.switchPreviewTab', 'both')} style="padding: 10px 20px; border: none; background: none; cursor: pointer; border-bottom: 2px solid transparent; color: var(--text-muted);">
                        ✓ Both (${bothTests.length})
                    </button>
                </div>

                <!-- Linux Tests -->
                <div id="previewTabLinux" class="preview-tab-content" style="max-height: 400px; overflow-y: auto;">
                    ${this.renderTestList(linuxTests, 'Linux/macOS Only', '#007bff')}
                    ${this.renderTestList(bothTests, 'Works on Both Platforms', '#28a745')}
                </div>

                <!-- Windows Tests -->
                <div id="previewTabWindows" class="preview-tab-content" style="display: none; max-height: 400px; overflow-y: auto;">
                    ${this.renderTestList(windowsTests, 'Windows Only', '#0099ff')}
                    ${this.renderTestList(bothTests, 'Works on Both Platforms', '#28a745')}
                </div>

                <!-- Both Platforms Tests -->
                <div id="previewTabBoth" class="preview-tab-content" style="display: none; max-height: 400px; overflow-y: auto;">
                    ${this.renderTestList(bothTests, 'Cross-Platform Tests', '#28a745')}
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" ${on('click', 'TestPlansManager.hideMatchPreview')}>
                    <i data-lucide="arrow-left" style="width: 16px; height: 16px; margin-right: 6px;"></i>
                    Back
                </button>
            </div>
        `;

        currentModal.appendChild(previewContent);

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    renderTestList(tests, title, color) {
        if (tests.length === 0) {
            return '';
        }

        return `
            <div style="margin-bottom: 20px;">
                <h4 style="color: ${color}; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                    <span style="width: 4px; height: 20px; background: ${color}; border-radius: 2px;"></span>
                    ${title} (${tests.length})
                </h4>
                <div style="background: var(--bg-tertiary); border-radius: 8px; padding: 15px;">
                    ${tests.map(test => `
                        <div style="padding: 8px 0; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; gap: 10px;">
                            <span style="font-family: monospace; font-size: 0.85em; color: var(--text-muted); min-width: 80px;">${escapeHtml(test.techniqueId)}</span>
                            <span style="flex: 1;">${escapeHtml(test.name)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    },

    switchPreviewTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.preview-tab').forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
                btn.style.borderBottomColor = 'var(--primary-color)';
                btn.style.color = 'var(--text-color)';
                btn.style.fontWeight = '600';
            } else {
                btn.classList.remove('active');
                btn.style.borderBottomColor = 'transparent';
                btn.style.color = 'var(--text-muted)';
                btn.style.fontWeight = 'normal';
            }
        });

        // Show/hide content
        document.getElementById('previewTabLinux').style.display = tabName === 'linux' ? 'block' : 'none';
        document.getElementById('previewTabWindows').style.display = tabName === 'windows' ? 'block' : 'none';
        document.getElementById('previewTabBoth').style.display = tabName === 'both' ? 'block' : 'none';
    },

    hideMatchPreview() {
        const modal = document.getElementById('generateScriptModal');
        const previewContent = document.getElementById('matchPreviewContent');

        if (previewContent) {
            previewContent.remove();
        }

        // Show original modal content
        modal.querySelector('.modal-content').style.display = 'block';
    },

    async downloadScript(planId) {
        const platformInput = document.querySelector('input[name="scriptPlatform"]:checked');
        if (!platformInput) {
            showToast('Please select a platform', 'error');
            return;
        }

        const platform = platformInput.value;
        const includeReadme = document.getElementById('includeReadme')?.checked ?? true;

        try {
            showToast('Generating script...', 'info');

            const blob = await API.testPlans.generateScript(planId, platform, includeReadme);

            // Determine file extension based on options
            let filename;
            if (includeReadme) {
                filename = `test_plan_${planId}.zip`;
            } else {
                filename = `test_plan_${planId}.${platform === 'windows' ? 'ps1' : 'sh'}`;
            }

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.closeModal('generateScriptModal');

            if (includeReadme) {
                showToast('Script and README downloaded!', 'success');
            } else {
                showToast('Script downloaded!', 'success');
            }
        } catch (error) {
            showToast(error.message || 'Failed to generate script', 'error');
            console.error(error);
        }
    },

    async matchLayerToAtomics(layerId) {
        // Get layer details first
        try {
            const layer = await API.testPlans.getLayer(layerId);
            if (layer.error) {
                showToast(layer.error, 'error');
                return;
            }

            // Store current layer for the match dialog
            this.currentMatchLayer = layer;
            this.showMatchFilterDialog(layer);
        } catch (error) {
            showToast('Failed to load layer', 'error');
            console.error(error);
        }
    },

    /**
     * Show the filter dialog for matching layer techniques to atomics.
     */
    showMatchFilterDialog(layer) {
        const layerData = layer.layer_data || {};
        const techniques = layerData.techniques || [];

        // Extract unique colors and score range from techniques
        const colors = new Set();
        let minScore = 100, maxScore = 0;
        techniques.forEach(t => {
            if (t.color) colors.add(t.color);
            const score = t.score || 0;
            if (score < minScore) minScore = score;
            if (score > maxScore) maxScore = score;
        });
        if (minScore > maxScore) { minScore = 0; maxScore = 100; }

        const colorOptions = Array.from(colors).map(c => `
            <label class="filter-checkbox">
                <input type="checkbox" name="matchColor" value="${escapeHtml(c)}" checked>
                <span class="color-swatch" style="background-color: ${escapeHtml(c)}"></span>
                <span>${escapeHtml(c)}</span>
            </label>
        `).join('');

        const modalHtml = `
            <div class="modal-overlay" id="matchFilterModal">
                <div class="modal-content modal-medium">
                    <div class="modal-header">
                        <h3>Match "${escapeHtml(layer.name)}" to Atomics</h3>
                        <button class="modal-close" ${on('click', 'TestPlansManager.closeMatchFilterDialog')}>&times;</button>
                    </div>
                    <div class="modal-body">
                        <p class="modal-description">
                            Filter which techniques from the layer to match with available Atomic Red Team tests.
                            ${techniques.length} techniques in layer.
                        </p>

                        <div class="filter-section">
                            <h4>Score Filter</h4>
                            <div class="score-filter">
                                <label>
                                    Minimum Score:
                                    <input type="number" id="matchMinScore" value="${minScore}" min="0" max="100" class="form-input score-input">
                                </label>
                                <span class="score-range-display">Layer range: ${minScore} - ${maxScore}</span>
                            </div>
                        </div>

                        ${colors.size > 0 ? `
                        <div class="filter-section">
                            <h4>Color Filter</h4>
                            <p class="filter-hint">Only include techniques with selected colors:</p>
                            <div class="color-filter-grid">
                                ${colorOptions}
                            </div>
                            <div class="filter-actions">
                                <button class="btn btn-sm btn-secondary" ${on('click', 'TestPlansManager.selectAllColors', true)}>Select All</button>
                                <button class="btn btn-sm btn-secondary" ${on('click', 'TestPlansManager.selectAllColors', false)}>Select None</button>
                            </div>
                        </div>
                        ` : ''}

                        <div class="filter-section">
                            <h4>Platform Filter</h4>
                            <select id="matchPlatform" class="form-select" aria-label="Platform filter">
                                <option value="">All Platforms</option>
                                <option value="windows">Windows</option>
                                <option value="linux">Linux</option>
                                <option value="macos">macOS</option>
                            </select>
                        </div>

                        <div class="filter-section match-plan-fields">
                            <h4>New Plan</h4>
                            <div class="form-group">
                                <label for="matchPlanName">Plan name</label>
                                <input type="text" id="matchPlanName" class="form-input" value="${escapeHtml(layer.name)} - Test Plan">
                            </div>
                            <div class="form-group">
                                <label for="matchPlanScope">Save to</label>
                                <select id="matchPlanScope" class="form-select">
                                    <option value="template" ${this.currentEngagementId() === null ? 'selected' : ''}>Template library (reusable)</option>
                                    ${this.currentEngagementId() !== null ? `<option value="engagement" selected>This engagement (${escapeHtml(AppState.activeEngagement.name || '')})</option>` : ''}
                                </select>
                            </div>
                        </div>

                        <div class="match-preview" id="matchPreview" aria-live="polite">
                            <p>Click "Preview Matches" to see results</p>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.previewMatches', layer.id)}>Preview Matches</button>
                        <button class="btn btn-primary" ${on('click', 'TestPlansManager.createPlanFromMatches', layer.id)} id="createPlanBtn" disabled>Create Test Plan</button>
                        <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeMatchFilterDialog')}>Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    closeMatchFilterDialog() {
        this.closeModal('matchFilterModal');
        this.currentMatchResults = null;
    },

    selectAllColors(select) {
        document.querySelectorAll('input[name="matchColor"]').forEach(cb => {
            cb.checked = select;
        });
    },

    /**
     * Preview matches based on current filter settings.
     */
    async previewMatches(layerId) {
        const minScore = parseInt(document.getElementById('matchMinScore').value) || 0;
        const platform = document.getElementById('matchPlatform').value;

        // Get selected colors
        const colorCheckboxes = document.querySelectorAll('input[name="matchColor"]:checked');
        const colors = Array.from(colorCheckboxes).map(cb => cb.value);

        const preview = document.getElementById('matchPreview');
        preview.innerHTML = '<p class="loading">Matching techniques...</p>';

        try {
            const result = await API.testPlans.matchLayerToAtomics(layerId, {
                min_score: minScore,
                colors: colors.length > 0 ? colors : undefined,
                platform: platform || undefined
            });

            if (result.error) {
                preview.innerHTML = `<p class="error">${escapeHtml(result.error)}</p>`;
                return;
            }

            this.currentMatchResults = result;
            this.currentMatchFilters = { minScore, colors, platform };
            const atomics = result.matched_atomics || [];

            if (atomics.length === 0) {
                preview.innerHTML = `
                    <div class="match-empty">
                        <p>No matching atomics found for the selected criteria.</p>
                        <p class="hint">Try adjusting your filters.</p>
                    </div>
                `;
                document.getElementById('createPlanBtn').disabled = true;
            } else {
                // Group by technique
                const grouped = {};
                atomics.forEach(a => {
                    if (!grouped[a.technique_id]) {
                        grouped[a.technique_id] = {
                            technique_id: a.technique_id,
                            technique_name: a.technique_name,
                            tests: []
                        };
                    }
                    grouped[a.technique_id].tests.push(a);
                });

                const techniqueCount = Object.keys(grouped).length;

                preview.innerHTML = `
                    <div class="match-results">
                        <div class="match-summary">
                            <span class="match-count">${atomics.length} tests</span> from
                            <span class="technique-count">${techniqueCount} techniques</span>
                        </div>
                        <div class="match-list">
                            ${Object.values(grouped).slice(0, 10).map(t => `
                                <div class="match-item">
                                    <span class="technique-id">${escapeHtml(t.technique_id)}</span>
                                    <span class="technique-name">${escapeHtml(t.technique_name)}</span>
                                    <span class="test-count">${t.tests.length} tests</span>
                                </div>
                            `).join('')}
                            ${techniqueCount > 10 ? `<p class="more-hint">...and ${techniqueCount - 10} more techniques</p>` : ''}
                        </div>
                    </div>
                `;
                document.getElementById('createPlanBtn').disabled = false;
            }
        } catch (error) {
            preview.innerHTML = `<p class="error">Failed to match: ${escapeHtml(error.message)}</p>`;
            console.error(error);
        }
    },

    /**
     * Create a test plan from the current match results.
     */
    async createPlanFromMatches(layerId) {
        if (!this.currentMatchResults || !this.currentMatchResults.matched_atomics.length) {
            showToast('No matches to create plan from', 'error');
            return;
        }

        const layer = this.currentMatchLayer;
        const atomics = this.currentMatchResults.matched_atomics;

        const nameInput = document.getElementById('matchPlanName');
        const planName = (nameInput?.value || '').trim();
        if (!planName) {
            showToast('Give the new plan a name', 'warning');
            nameInput?.focus();
            return;
        }
        const scope = document.getElementById('matchPlanScope')?.value || 'template';

        // Record the filters so the plan can be rebuilt exactly later
        const f = this.currentMatchFilters || {};
        const filterNote = [
            f.minScore ? `min score ${f.minScore}` : null,
            f.colors && f.colors.length ? `colors ${f.colors.join(', ')}` : null,
            f.platform ? `platform ${f.platform}` : null
        ].filter(Boolean).join('; ');

        try {
            const planResult = await API.testPlans.createPlan({
                name: planName,
                description: `Generated from Navigator layer "${layer.name}" with ${atomics.length} tests` +
                    (filterNote ? ` (filters: ${filterNote})` : ' (no filters)'),
                target_platform: (f.platform || document.getElementById('matchPlatform').value) || 'all',
                is_template: scope === 'template'
            });

            if (planResult.error) {
                showToast(planResult.error, 'error');
                return;
            }

            // Add all matched atomics as items
            const atomicIds = atomics.map(atomic => atomic.id);
            const itemsResult = await API.testPlans.addBulkItems(planResult.id, atomicIds);

            if (itemsResult.error) {
                showToast(`Plan created but failed to add items: ${itemsResult.error}`, 'warning');
            } else {
                showToast(`Created plan "${planName}" with ${atomics.length} tests`, 'success');
            }

            this.closeMatchFilterDialog();
            await this.loadPlans();
            this.switchTab('plans');
        } catch (error) {
            showToast('Failed to create plan', 'error');
            console.error(error);
        }
    },

    async deleteLayer(layerId) {
        if (!confirm('Delete this layer?')) return;

        try {
            const result = await API.testPlans.deleteLayer(layerId);
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast('Layer deleted', 'success');
                await this.loadLayers();
                this.switchTab('navigator');
            }
        } catch (error) {
            showToast('Failed to delete layer', 'error');
        }
    },

    async startNewExecution() {
        // Plans may not be loaded if the Plans tab was never opened
        await this.ensurePlansLoaded();
        if (this.plans.length === 0) {
            showToast('No test plans available. Create a plan first.', 'error');
            return;
        }

        // Get hosts for the current engagement
        // (GET /api/hosts returns { hosts: [...], general_count })
        let hosts = [];
        let hostsError = null;
        try {
            const hostsResult = await API.hosts.getAll();
            hosts = Array.isArray(hostsResult) ? hostsResult : (hostsResult?.hosts || []);
        } catch (error) {
            console.error('Failed to load hosts:', error);
            hostsError = error.message || 'Network error';
        }
        // Out-of-scope hosts must never be offered as execution targets
        const outOfScopeCount = hosts.filter(h => h.out_of_scope).length;
        hosts = hosts.filter(h => !h.out_of_scope);

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'startExecutionModal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h3>Start Test Execution</h3>
                    <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'startExecutionModal')}>&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label for="executionPlanSelect">Select Test Plan:</label>
                        <select id="executionPlanSelect" class="form-control">
                            ${this.renderPlanOptions({ showCounts: true, templateSuffix: ' (template)' })}
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="executionHostSelect">Target Host (optional):</label>
                        <select id="executionHostSelect" class="form-control">
                            <option value="">No specific host</option>
                            ${hosts.map(host => `
                                <option value="${host.id}">${escapeHtml(host.ip || host.hostname || 'Unknown')}${host.ip && host.hostname ? ` (${escapeHtml(host.hostname)})` : ''}</option>
                            `).join('')}
                        </select>
                        <small class="form-text">
                            ${hostsError
                                ? `Couldn't load hosts: ${escapeHtml(hostsError)}`
                                : hosts.length === 0
                                    ? 'No in-scope hosts in this engagement yet. Add hosts on the Evidence tab.'
                                    : 'Optionally associate this execution with a specific target host.'}
                            ${outOfScopeCount ? ` ${outOfScopeCount} out-of-scope host${outOfScopeCount === 1 ? '' : 's'} hidden.` : ''}
                        </small>
                    </div>

                    <div class="execution-info" style="background: var(--bg-secondary); padding: 12px; border-radius: 8px; margin-top: 15px;">
                        <p style="margin: 0; font-size: 0.9em;">
                            This will create execution records for all enabled tests in the selected plan.
                            You can then track the status of each test as you run them.
                            Picking a template copies it into this engagement first; the template itself is unchanged.
                        </p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'startExecutionModal')}>Cancel</button>
                    <button class="btn btn-primary" ${on('click', 'TestPlansManager.confirmStartExecution')}>
                        Start Execution
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    async confirmStartExecution() {
        const planId = document.getElementById('executionPlanSelect').value;
        const hostId = document.getElementById('executionHostSelect').value;

        if (!planId) {
            showToast('Please select a test plan', 'error');
            return;
        }

        try {
            const result = await API.testPlans.startExecution(planId, hostId || null);
            if (result.error) {
                showToast(result.error, 'error');
            } else {
                showToast(result.copied_from_template
                    ? `Copied template into this engagement and started ${result.count} tests`
                    : `Started execution with ${result.count} tests`, 'success');
                this.closeModal('startExecutionModal');
                if (result.copied_from_template) {
                    await this.loadPlans();
                }
                // Show the run that was just started
                this.executionPlanFilter = String(result.plan_id);
                await this.loadExecutions();
                this.switchTab('executions');
            }
        } catch (error) {
            showToast('Failed to start execution', 'error');
            console.error(error);
        }
    },

    // ========================================
    // SESSION LOG IMPORT
    // ========================================
    // Reads the log captured while running a PTVault-generated script and
    // fills in run status, output, and timestamps. Detection outcomes are
    // never inferred from a log.

    async showImportLogModal() {
        const planId = this.gridPlanId();
        if (!planId) return;
        await this.ensureEngagementHosts();

        const model = this.buildGridModel(planId);
        const plan = this.executionRunPlans().find(p => String(p.id) === String(planId));
        const columnHosts = model.hosts.filter(h => h.key !== 'none');
        const columnIds = new Set(columnHosts.map(h => String(h.id)));
        const otherHosts = (this.engagementHosts || []).filter(h => !columnIds.has(String(h.id)));
        const hostOption = h => `<option value="${h.id}">${escapeHtml(h.ip || h.hostname || `Host ${h.id}`)}${h.ip && h.hostname ? ` (${escapeHtml(h.hostname)})` : ''}</option>`;
        const defaultHost = model.hosts[0] ? (model.hosts[0].key === 'none' ? '' : String(model.hosts[0].id)) : '';

        this.importLog = { planId, file: null, preview: null, requestSeq: 0 };

        const modal = document.createElement('div');
        modal.className = 'modal-overlay import-log-modal';
        modal.id = 'importLogModal';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="importLogTitle" style="max-width: 680px;">
                <div class="modal-header">
                    <h3 id="importLogTitle">Import session log</h3>
                    <button class="modal-close" ${on('click', 'TestPlansManager.closeModal', 'importLogModal')} aria-label="Close">&times;</button>
                </div>
                <div class="modal-body">
                    <p class="import-log-intro">
                        Fills in status, output and timestamps for <strong>${escapeHtml(plan ? plan.name : 'this plan')}</strong>
                        from the log you captured while running its PTVault script
                        (<code>tee</code>, <code>script</code>, <code>Tee-Object</code> or <code>Start-Transcript</code>).
                        Outcomes stay as you recorded them.
                    </p>
                    <div class="import-log-fields">
                        <div class="import-log-field">
                            <label for="importLogHost">Ran on</label>
                            <select id="importLogHost" class="form-select" ${on('change', 'TestPlansManager.runImportPreview')}>
                                ${columnHosts.length ? `<optgroup label="In this grid">${columnHosts.map(h => hostOption(h)).join('')}</optgroup>` : ''}
                                ${otherHosts.length ? `<optgroup label="Other in-scope hosts">${otherHosts.map(hostOption).join('')}</optgroup>` : ''}
                                <option value="">No specific host</option>
                            </select>
                        </div>
                        <div class="import-log-field">
                            <label for="importLogFile">Log file</label>
                            <input type="file" id="importLogFile" accept=".log,.txt,text/plain"
                                   ${on('change', 'TestPlansManager.onImportLogFile', ARG.file)}>
                        </div>
                    </div>
                    <div id="importLogPreview" class="import-log-preview" aria-live="polite"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" ${on('click', 'TestPlansManager.closeModal', 'importLogModal')}>Cancel</button>
                    <button class="btn btn-primary" id="importLogApply" ${on('click', 'TestPlansManager.confirmImportLog')} disabled>Import results</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        document.getElementById('importLogHost').value = defaultHost;
        document.getElementById('importLogFile').focus();
    },

    onImportLogFile(file) {
        if (!this.importLog) return;
        this.importLog.file = file || null;
        this.runImportPreview();
    },

    importHostValue() {
        const value = document.getElementById('importLogHost')?.value || '';
        return value ? Number(value) : null;
    },

    async runImportPreview() {
        const state = this.importLog;
        const target = document.getElementById('importLogPreview');
        const applyBtn = document.getElementById('importLogApply');
        if (!state || !target) return;
        state.preview = null;
        if (applyBtn) applyBtn.disabled = true;
        if (!state.file) {
            target.innerHTML = '';
            return;
        }

        const seq = ++state.requestSeq;
        target.innerHTML = '<p class="import-log-status">Reading log&hellip;</p>';
        let result;
        try {
            result = await API.testPlans.importSessionLog(state.planId, this.importHostValue(), state.file, false);
        } catch (error) {
            if (seq !== state.requestSeq) return;
            target.innerHTML = `<p class="import-log-status is-error" role="alert">${escapeHtml(error.message || 'Could not read this log')}</p>`;
            return;
        }
        if (seq !== state.requestSeq) return;   // a newer preview is in flight

        state.preview = result;
        target.innerHTML = this.renderImportPreview(result);
        if (applyBtn) {
            applyBtn.disabled = result.summary.matched === 0;
            applyBtn.textContent = result.summary.matched
                ? `Import ${result.summary.matched} result${result.summary.matched === 1 ? '' : 's'}`
                : 'Nothing to import';
        }
    },

    renderImportPreview(result) {
        const { summary, results } = result;
        const reasonText = {
            not_in_plan: 'Not in this plan',
            ambiguous: 'Matches more than one test'
        };
        const statusText = r => r.status === 'in_progress'
            ? 'Started, no result (log ended mid-test)'
            : `${this.statusLabel(r.status)}${r.exit_code != null && r.status !== 'skipped' ? ` (exit ${r.exit_code})` : ''}`;

        return `
            <p class="import-log-status">
                Found <strong>${summary.total}</strong> test result${summary.total === 1 ? '' : 's'}:
                <strong>${summary.matched}</strong> match this plan${summary.unmatched ? `, <strong>${summary.unmatched}</strong> will be skipped` : ''}${summary.new_executions ? `; ${summary.new_executions} new on this host` : ''}.
            </p>
            <div class="import-log-table-wrap">
                <table class="import-log-table">
                    <thead>
                        <tr><th scope="col">#</th><th scope="col">Test</th><th scope="col">Result</th><th scope="col">Imports to</th></tr>
                    </thead>
                    <tbody>
                        ${results.map(r => `
                            <tr class="${r.item_id ? '' : 'is-unmatched'}">
                                <td class="num">${r.test_number}</td>
                                <td>
                                    ${r.technique_id ? `<span class="exec-grid-technique">${escapeHtml(r.technique_id)}</span>` : ''}
                                    ${escapeHtml(r.test_name || 'Unnamed test')}
                                </td>
                                <td>${this.statusSvg(r.status)} ${statusText(r)}</td>
                                <td>${r.item_id
                                    ? (r.execution_id ? 'Existing row' : 'New row')
                                    : `<span class="import-log-skip">${reasonText[r.unmatched_reason] || 'Skipped'}</span>`}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    async confirmImportLog() {
        const state = this.importLog;
        if (!state || !state.preview || !state.file) return;
        const applyBtn = document.getElementById('importLogApply');
        if (applyBtn) {
            applyBtn.disabled = true;
            applyBtn.textContent = 'Importing…';
        }

        let result;
        try {
            result = await API.testPlans.importSessionLog(state.planId, this.importHostValue(), state.file, true);
        } catch (error) {
            showToast(error.message || 'Import failed', 'error');
            if (applyBtn) {
                applyBtn.disabled = false;
                applyBtn.textContent = 'Try again';
            }
            return;
        }

        const { updated, created, unmatched } = result.summary;
        showToast(`Imported ${updated} result${updated === 1 ? '' : 's'}${created ? ` (${created} new)` : ''}${unmatched ? `; ${unmatched} skipped` : ''}`, 'success');
        this.closeModal('importLogModal');
        this.importLog = null;
        await this.loadExecutions();
        this.refreshExecutionsMain();
    },

    // ========================================
    // EXECUTION DETAIL PANEL
    // ========================================
    // Opens beside the grid/list so results can be recorded cell by cell.
    // Linking evidence happens inside the panel and never discards
    // unsaved form edits.

    /** Kept for existing callers. */
    async updateExecutionStatus(executionId) {
        await this.openExecution(executionId);
    },

    confirmDiscardPanel() {
        if (!this.panel || !this.panel.dirty) return true;
        return confirm('Discard unsaved changes to this execution?');
    },

    async openExecution(executionId) {
        if (this.panel && this.panel.exec.id === executionId) {
            document.getElementById('execPanelHeading')?.focus();
            return;
        }
        if (!this.confirmDiscardPanel()) return;

        let exec;
        try {
            exec = await API.testPlans.getExecution(executionId);
        } catch (error) {
            showToast(`Couldn't load execution: ${error.message || 'Network error'}`, 'error');
            return;
        }

        this.panel = { exec, dirty: false };
        const panelEl = document.getElementById('executionPanel');
        if (!panelEl) return;
        panelEl.innerHTML = this.renderExecutionPanel(exec);
        panelEl.hidden = false;
        document.getElementById('execLayout')?.classList.add('has-panel');
        this.markSelectedExecution(exec.id);
        document.getElementById('execPanelHeading')?.focus();
    },

    /** Execution panel form: save without moving to the next test (L-21). */
    submitExecutionPanel(event) {
        event.preventDefault();
        this.saveExecutionPanel(false);
    },

    /** Escape in the execution panel closes it (L-21). */
    onExecutionPanelKey(event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            this.closeExecutionPanel();
        }
    },

    closeExecutionPanel() {
        if (!this.confirmDiscardPanel()) return;
        const previousId = this.panel?.exec?.id;
        this.panel = null;
        const panelEl = document.getElementById('executionPanel');
        if (panelEl) {
            panelEl.hidden = true;
            panelEl.innerHTML = '';
        }
        document.getElementById('execLayout')?.classList.remove('has-panel');
        this.markSelectedExecution(null);
        // Return focus to the cell/row that opened the panel
        if (previousId) document.querySelector(`[data-exec-id="${previousId}"] button, button[data-exec-id="${previousId}"]`)?.focus();
    },

    markSelectedExecution(executionId) {
        document.querySelectorAll('#executionsMain .is-selected').forEach(el => el.classList.remove('is-selected'));
        if (executionId == null) return;
        document.querySelectorAll(`#executionsMain [data-exec-id="${executionId}"]`).forEach(el => el.classList.add('is-selected'));
        // Keep the grid's single Tab stop on the selected cell
        const selectedCell = document.querySelector(`#executionsMain button.exec-cell[data-exec-id="${executionId}"]`);
        if (selectedCell) {
            document.querySelectorAll('#executionsMain button.exec-cell[tabindex="0"]').forEach(el => { el.tabIndex = -1; });
            selectedCell.tabIndex = 0;
        }
    },

    /** Arrow / Home / End navigation between grid cells. */
    onGridKeydown(e) {
        const cell = e.target.closest ? e.target.closest('button.exec-cell') : null;
        if (!cell || !['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) return;
        const td = cell.closest('td');
        const tr = td.parentElement;
        const col = [...tr.children].indexOf(td);
        const cellAt = (row, c) => (row && row.children[c]) ? row.children[c].querySelector('button.exec-cell') : null;
        let target = null;

        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            const step = e.key === 'ArrowRight' ? 1 : -1;
            for (let c = col + step; c >= 0 && c < tr.children.length && !target; c += step) target = cellAt(tr, c);
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            const next = r => (e.key === 'ArrowDown' ? r.nextElementSibling : r.previousElementSibling);
            for (let row = next(tr); row && !target; row = next(row)) target = cellAt(row, col);
        } else {
            const cells = [...tr.querySelectorAll('button.exec-cell')];
            target = e.key === 'Home' ? cells[0] : cells[cells.length - 1];
        }

        e.preventDefault();
        if (target && target !== cell) {
            cell.tabIndex = -1;
            target.tabIndex = 0;
            target.focus();
            target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
    },

    markPanelDirty() {
        if (!this.panel) return;
        this.panel.dirty = true;
        const note = document.getElementById('execPanelDirty');
        if (note) note.textContent = 'Unsaved changes';
    },

    renderExecutionPanel(exec) {
        const testName = exec.atomic_test_name || exec.custom_name || 'Unknown test';
        const host = exec.host_ip ? `${exec.host_ip}${exec.host_hostname ? ` (${exec.host_hostname})` : ''}` : 'No specific host';
        const command = exec.executor_command || exec.custom_command || '';
        const outcome = exec.outcome || '';

        return `
            <div class="exec-panel-header">
                <h3 id="execPanelHeading" tabindex="-1">
                    ${exec.technique_id ? `<span class="exec-panel-technique">${escapeHtml(exec.technique_id)}</span>` : ''}
                    ${escapeHtml(testName)}
                </h3>
                <button type="button" class="exec-panel-close" ${on('click', 'TestPlansManager.closeExecutionPanel')} aria-label="Close execution details">&times;</button>
            </div>
            <p class="exec-panel-meta">${escapeHtml(host)} &middot; ${escapeHtml(exec.plan_name || '')}</p>

            <form id="execPanelForm" class="exec-panel-form"
                  ${on('input', 'TestPlansManager.markPanelDirty')} ${on('change', 'TestPlansManager.markPanelDirty')}
                  ${on('submit', 'TestPlansManager.submitExecutionPanel', ARG.event)}
                  ${on('keydown', 'TestPlansManager.onExecutionPanelKey', ARG.event)}>
                <fieldset class="exec-field">
                    <legend>Status</legend>
                    <div class="exec-segmented">
                        ${this.STATUSES.map(s => `
                            <label class="exec-segment">
                                <input type="radio" name="execStatus" value="${s.value}" ${exec.status === s.value ? 'checked' : ''}>
                                <span>${s.label}</span>
                            </label>
                        `).join('')}
                    </div>
                </fieldset>

                <fieldset class="exec-field">
                    <legend>Outcome</legend>
                    <p class="exec-field-hint">The furthest the defenders got.</p>
                    <div class="exec-outcome-options">
                        ${[...this.OUTCOMES, { value: '', label: 'Not evaluated', hint: 'No result recorded yet' }].map(o => `
                            <label class="exec-outcome-option">
                                <input type="radio" name="execOutcome" value="${o.value}" ${outcome === o.value ? 'checked' : ''}>
                                <span class="exec-swatch outcome-${o.value || 'none'}" aria-hidden="true"></span>
                                <span class="exec-outcome-text">
                                    <span class="exec-outcome-name">${o.label}</span>
                                    <span class="exec-outcome-hint">${o.hint}</span>
                                </span>
                            </label>
                        `).join('')}
                    </div>
                </fieldset>

                <div class="exec-field">
                    <label for="execDetectedBy">Detected by</label>
                    <input type="text" id="execDetectedBy" class="form-input" value="${escapeHtml(exec.detected_by || '')}"
                           placeholder="e.g., CrowdStrike, Sysmon to Splunk rule">
                </div>

                ${command ? `
                    <details class="exec-command">
                        <summary>Command</summary>
                        <pre><code>${escapeHtml(command)}</code></pre>
                    </details>
                ` : ''}

                <div class="exec-field">
                    <label for="execOutput">Output</label>
                    <textarea id="execOutput" class="form-textarea" rows="3" placeholder="Paste command output or results">${escapeHtml(exec.execution_output || '')}</textarea>
                </div>

                <div class="exec-field">
                    <label for="execNotes">Notes</label>
                    <textarea id="execNotes" class="form-textarea" rows="2" placeholder="What the blue team saw, timing, follow-ups">${escapeHtml(exec.execution_notes || '')}</textarea>
                </div>

                <div class="exec-field" id="execEvidenceField">
                    ${this.renderPanelEvidence(exec)}
                </div>

                <div class="exec-panel-actions">
                    <button type="button" class="btn btn-sm btn-danger" ${on('click', 'TestPlansManager.deleteExecution', exec.id)}>Delete</button>
                    <span class="exec-panel-dirty" id="execPanelDirty" aria-live="polite"></span>
                    <button type="submit" class="btn btn-sm btn-secondary">Save</button>
                    <button type="button" class="btn btn-sm btn-primary" ${on('click', 'TestPlansManager.saveExecutionPanel', true)}>Save &amp; next</button>
                </div>
            </form>
        `;
    },

    renderPanelEvidence(exec) {
        return `
            <span class="exec-field-label" id="execEvidenceLabel">Evidence</span>
            <div class="exec-evidence-row" aria-labelledby="execEvidenceLabel">
                ${exec.evidence_id
                    ? `<span class="exec-evidence-linked">${escapeHtml(exec.evidence_title || `Evidence #${exec.evidence_id}`)}</span>
                       <button type="button" class="btn btn-xs btn-secondary" ${on('click', 'TestPlansManager.showEvidencePicker')}>Change</button>`
                    : `<span class="exec-evidence-none">None linked</span>
                       <button type="button" class="btn btn-xs btn-secondary" ${on('click', 'TestPlansManager.showEvidencePicker')}>Link evidence</button>`}
            </div>
        `;
    },

    async showEvidencePicker() {
        const field = document.getElementById('execEvidenceField');
        if (!field || !this.panel) return;

        let evidence = [];
        try {
            const result = await API.evidence.getAll();
            evidence = Array.isArray(result) ? result : (result?.evidence || []);
        } catch (error) {
            showToast(`Couldn't load evidence: ${error.message || 'Network error'}`, 'error');
            return;
        }

        if (evidence.length === 0) {
            showToast('No evidence in this engagement yet', 'info');
            return;
        }

        field.innerHTML = `
            <label for="evidenceSelect">Evidence</label>
            <div class="exec-evidence-row">
                <select id="evidenceSelect" class="form-select">
                    ${evidence.map(e => `
                        <option value="${e.id}" ${e.id === this.panel.exec.evidence_id ? 'selected' : ''}>${escapeHtml(e.title || 'Untitled')} (${escapeHtml((e.evidence_type || e.type || 'unknown').replace(/_/g, ' '))})</option>
                    `).join('')}
                </select>
                <button type="button" class="btn btn-xs btn-primary" ${on('click', 'TestPlansManager.confirmLinkEvidence')}>Link</button>
                <button type="button" class="btn btn-xs btn-secondary" ${on('click', 'TestPlansManager.cancelEvidencePicker')}>Cancel</button>
            </div>
        `;
        document.getElementById('evidenceSelect')?.focus();
    },

    cancelEvidencePicker() {
        const field = document.getElementById('execEvidenceField');
        if (field && this.panel) field.innerHTML = this.renderPanelEvidence(this.panel.exec);
    },

    async confirmLinkEvidence() {
        const select = document.getElementById('evidenceSelect');
        if (!select || !select.value || !this.panel) return;
        const exec = this.panel.exec;
        const evidenceId = Number(select.value);
        const evidenceTitle = select.options[select.selectedIndex].text.replace(/\s*\([^)]*\)$/, '');

        try {
            await API.testPlans.linkEvidence(exec.id, evidenceId);
        } catch (error) {
            showToast(error.message || 'Failed to link evidence', 'error');
            return;
        }

        // Update in place: the rest of the form (and its unsaved edits) stays as is
        exec.evidence_id = evidenceId;
        exec.evidence_title = evidenceTitle;
        const row = this.executions.find(e => e.id === exec.id);
        if (row) Object.assign(row, { evidence_id: evidenceId, evidence_title: evidenceTitle });
        this.cancelEvidencePicker();
        showToast('Evidence linked', 'success');
    },

    async saveExecutionPanel(goNext) {
        if (!this.panel) return;
        const exec = this.panel.exec;
        const statusInput = document.querySelector('#execPanelForm input[name="execStatus"]:checked');
        const outcomeInput = document.querySelector('#execPanelForm input[name="execOutcome"]:checked');
        const data = {
            status: statusInput ? statusInput.value : exec.status,
            outcome: outcomeInput ? (outcomeInput.value || null) : null,
            detected_by: document.getElementById('execDetectedBy').value.trim(),
            execution_output: document.getElementById('execOutput').value,
            execution_notes: document.getElementById('execNotes').value
        };

        try {
            await API.testPlans.updateExecution(exec.id, data);
        } catch (error) {
            showToast(error.message || 'Failed to save execution', 'error');
            return;
        }

        const update = { ...data, detected_by: data.detected_by || null };
        Object.assign(exec, update);
        const row = this.executions.find(e => e.id === exec.id);
        if (row) Object.assign(row, update);
        this.panel.dirty = false;

        const nextId = goNext ? this.nextExecutionId(exec.id) : null;
        this.refreshExecutionsMain();

        if (goNext && nextId) {
            await this.openExecution(nextId);
            document.querySelector(`button[data-exec-id="${nextId}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        } else {
            this.markSelectedExecution(exec.id);
            const note = document.getElementById('execPanelDirty');
            if (note) note.textContent = 'Saved';
            showToast(goNext ? 'Saved. That was the last test.' : 'Execution saved', 'success');
        }
    },

    /**
     * Next execution after this one, in on-screen order: down the same host
     * column in the grid, or the next row in the list.
     */
    nextExecutionId(executionId) {
        if (this.executionView === 'grid') {
            const model = this.buildGridModel(this.gridPlanId());
            const rows = this.gridVisibleRows(model);
            const current = model.execs.find(e => e.id === executionId);
            if (!current) return null;
            const hostKey = current.host_id == null ? 'none' : String(current.host_id);
            const idx = rows.findIndex(r => r.itemId === current.test_plan_item_id);
            for (let i = idx + 1; i < rows.length; i++) {
                const next = model.cells.get(`${rows[i].itemId}|${hostKey}`);
                if (next) return next.id;
            }
            return null;
        }
        const list = this.executionPlanFilter
            ? this.executions.filter(e => String(e.test_plan_id) === String(this.executionPlanFilter))
            : this.executions;
        const idx = list.findIndex(e => e.id === executionId);
        return idx >= 0 && idx + 1 < list.length ? list[idx + 1].id : null;
    },

    async deleteExecution(executionId) {
        if (!confirm('Delete this execution record? Its status, outcome, and notes are removed.')) {
            return;
        }

        try {
            await API.testPlans.deleteExecution(executionId);
        } catch (error) {
            showToast(error.message || 'Failed to delete execution', 'error');
            return;
        }

        showToast('Execution deleted', 'success');
        this.executions = this.executions.filter(e => e.id !== executionId);
        if (this.panel && this.panel.exec.id === executionId) {
            this.panel.dirty = false;
            this.closeExecutionPanel();
        }
        if (this.executions.length === 0) {
            await this.switchTab('executions');
        } else {
            this.refreshExecutionsMain();
        }
    }

};

// Helper function - use from utils.js or define here
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Make globally accessible
window.TestPlansManager = TestPlansManager;

// Commands travel in data-* attributes, never inside handler code (H-10).
registerAction('copy-original-command', el => {
    navigator.clipboard.writeText(el.dataset.command)
        .then(() => showToast('Copied to clipboard', 'success'))
        .catch(() => showToast('Failed to copy', 'error'));
});
registerAction('use-original-command', el => {
    const field = document.getElementById('editItemCommand');
    if (field) field.value = el.dataset.command;
});
