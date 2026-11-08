/**
 * PTVault Reporting Manager
 * Handles the Reporting section with Writeups Database
 */

const ReportingManager = {
    initialized: false,
    activeTab: 'writeups',
    writeups: [],
    categories: [],
    filters: {
        category: 'all',
        criticality: 'all',
        writeup_type: 'all',
        search: ''
    },

    // Report Generator State
    currentReport: null,           // Currently editing report { id, name, structure }
    savedReports: [],              // List of saved reports for dropdown
    workspaceItems: [],            // Array of report items in workspace
    engagementFindings: [],        // Findings from current engagement
    dragState: {
        draggedItem: null,
        draggedFrom: null,         // 'source' | 'workspace'
        draggedIndex: null
    },
    sourceCollapsed: {
        findings: false,
        writeups: false,
        formatTools: false
    },

    // Templates State (Q3)
    templates: [],
    activeTemplate: null,
    templateFilters: {
        category: 'all'
    },

    /**
     * Initialize the Reporting Manager
     */
    async init() {
        // Only load data if not already initialized
        if (!this.initialized) {
            await this.loadWriteups();
            await this.loadCategories();
            this.initialized = true;
        }
        // Always render the section
        this.renderReportingSection();
        this.setupEventListeners();
    },

    /**
     * Load writeups from API
     */
    async loadWriteups() {
        try {
            this.writeups = await API.reporting.getWriteups(this.filters);
        } catch (error) {
            console.error('Failed to load writeups:', error);
            this.writeups = [];
        }
    },

    /**
     * Load categories from API
     */
    async loadCategories() {
        try {
            const data = await API.reporting.getCategories();
            this.categories = data.categories || [];
        } catch (error) {
            console.error('Failed to load categories:', error);
            this.categories = [];
        }
    },

    /**
     * Render the main reporting section
     */
    renderReportingSection() {
        const container = document.getElementById('section-reporting');
        if (!container) return;

        container.innerHTML = `
            <div class="reporting-page">
                <!-- Sub-tabs -->
                <div class="reporting-tabs">
                    <button class="reporting-tab ${this.activeTab === 'writeups' ? 'active' : ''}"
                            data-tab="writeups" ${on('click', 'ReportingManager.switchTab', 'writeups')}>
                        <span class="tab-icon"><i data-lucide="notebook-pen"></i></span>
                        <span>Writeups Database</span>
                    </button>
                    <button class="reporting-tab ${this.activeTab === 'generation' ? 'active' : ''}"
                            data-tab="generation" ${on('click', 'ReportingManager.switchTab', 'generation')}>
                        <span class="tab-icon"><i data-lucide="file-chart-column"></i></span>
                        <span>Report Generation</span>
                    </button>
                    <button class="reporting-tab ${this.activeTab === 'templates' ? 'active' : ''}"
                            data-tab="templates" ${on('click', 'ReportingManager.switchTab', 'templates')}>
                        <span class="tab-icon"><i data-lucide="layout-template"></i></span>
                        <span>Templates</span>
                    </button>
                </div>

                <!-- Content Area -->
                <div class="reporting-content" id="reportingContent">
                    ${this.renderActiveTabContent()}
                </div>
            </div>
        `;

        // Reinitialize lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Switch between sub-tabs
     */
    async switchTab(tabId) {
        this.activeTab = tabId;

        // Update tab buttons
        document.querySelectorAll('.reporting-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update content
        const content = document.getElementById('reportingContent');
        if (content) {
            // Initialize data before rendering for generation tab
            if (tabId === 'generation') {
                await this.initReportGenerator();
            } else if (tabId === 'templates') {
                await this.loadTemplates();
            }
            content.innerHTML = this.renderActiveTabContent();
            this.setupEventListeners();
            if (tabId === 'generation') {
                this.setupGeneratorEventListeners();
            }
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    /**
     * Render content for active tab
     */
    renderActiveTabContent() {
        switch (this.activeTab) {
            case 'writeups':
                return this.renderWriteupsContent();
            case 'generation':
                return this.renderGenerationContent();
            case 'templates':
                return this.renderTemplatesContent();
            default:
                return this.renderWriteupsContent();
        }
    },

    /**
     * Render Writeups Database content
     */
    renderWriteupsContent() {
        return `
            <div class="writeups-page">
                <!-- Sidebar with filters -->
                <aside class="writeups-sidebar">
                    <div class="writeups-sidebar-header">
                        <h3>Filters</h3>
                    </div>

                    <!-- Category Filter -->
                    <div class="filter-section">
                        <label>Category</label>
                        <select id="categoryFilter" ${on('change', 'ReportingManager.applyFilters')}>
                            <option value="all">All Categories</option>
                            ${this.categories.map(cat => `
                                <option value="${escapeHtml(cat.name)}" ${this.filters.category === cat.name ? 'selected' : ''}>
                                    ${escapeHtml(cat.name)} (${cat.count})
                                </option>
                            `).join('')}
                        </select>
                    </div>

                    <!-- Type Filter -->
                    <div class="filter-section">
                        <label>Type</label>
                        <select id="typeFilter" ${on('change', 'ReportingManager.applyFilters')}>
                            <option value="all" ${this.filters.writeup_type === 'all' ? 'selected' : ''}>All Types</option>
                            <option value="finding" ${this.filters.writeup_type === 'finding' ? 'selected' : ''}>Findings</option>
                            <option value="narrative" ${this.filters.writeup_type === 'narrative' ? 'selected' : ''}>Narratives</option>
                        </select>
                    </div>

                    <!-- Criticality Filter -->
                    <div class="filter-section">
                        <label>Criticality</label>
                        <select id="criticalityFilter" ${on('change', 'ReportingManager.applyFilters')}>
                            <option value="all">All Levels</option>
                            <option value="critical" ${this.filters.criticality === 'critical' ? 'selected' : ''}>Critical</option>
                            <option value="high" ${this.filters.criticality === 'high' ? 'selected' : ''}>High</option>
                            <option value="medium" ${this.filters.criticality === 'medium' ? 'selected' : ''}>Medium</option>
                            <option value="low" ${this.filters.criticality === 'low' ? 'selected' : ''}>Low</option>
                        </select>
                    </div>

                    <div class="writeups-sidebar-footer">
                        <button class="btn btn-primary btn-block" ${on('click', 'ReportingManager.showAddWriteupModal')}>
                            + Add Writeup
                        </button>
                    </div>
                </aside>

                <!-- Main Content -->
                <main class="writeups-main">
                    <div class="writeups-header">
                        <div class="writeups-search">
                            <i data-lucide="search" class="search-icon"></i>
                            <input type="text" id="writeupSearch" placeholder="Search writeups..."
                                   value="${escapeHtml(this.filters.search)}" autocomplete="off">
                        </div>
                        <div class="writeups-header-actions">
                            <button class="btn btn-secondary" ${on('click', 'ReportingManager.showComparisonModal')} title="Compare multiple engagements">
                                <i data-lucide="bar-chart-2"></i>
                                Compare Engagements
                            </button>
                            <span class="writeups-count">${this.writeups.length} writeup${this.writeups.length !== 1 ? 's' : ''}</span>
                        </div>
                    </div>

                    <div class="writeups-list" id="writeupsList">
                        ${this.renderWriteupsList()}
                    </div>
                </main>
            </div>
        `;
    },

    /**
     * Render the list of writeups
     */
    renderWriteupsList() {
        if (this.writeups.length === 0) {
            return `
                <div class="empty-state">
                    <div class="empty-icon"><i data-lucide="notebook-pen"></i></div>
                    <h3>No writeups found</h3>
                    <p>Create your first writeup to build your vulnerability database.</p>
                    <button class="btn btn-primary" ${on('click', 'ReportingManager.showAddWriteupModal')}>
                        + Add Writeup
                    </button>
                </div>
            `;
        }

        return this.writeups.map(writeup => this.renderWriteupCard(writeup)).join('');
    },

    /**
     * Render a single writeup row (compact layout)
     */
    renderWriteupCard(writeup) {
        const isNarrative = writeup.writeup_type === 'narrative';
        const criticalityClass = isNarrative ? 'type-narrative' : `criticality-${this._criticality(writeup.criticality)}`;

        // Type badge
        const typeBadge = isNarrative
            ? '<span class="type-badge narrative">Narrative</span>'
            : '<span class="type-badge finding">Finding</span>';

        // Criticality badge (only for findings)
        const criticalityBadge = !isNarrative && writeup.criticality
            ? `<span class="criticality-badge criticality-${this._criticality(writeup.criticality)}">${escapeHtml(writeup.criticality)}</span>`
            : '';

        return `
            <div class="writeup-card ${criticalityClass}" data-writeup-id="${writeup.id}"
                 ${on('click', 'ReportingManager.showEditWriteupModal', writeup.id)}
                 title="${escapeHtml(writeup.description || writeup.name)}">
                <div class="writeup-header">
                    <div class="writeup-title-row">
                        ${typeBadge}
                        ${criticalityBadge}
                        <span class="writeup-title">${escapeHtml(writeup.name)}</span>
                    </div>
                </div>

                <div class="writeup-meta">
                    ${writeup.category ? `<span class="writeup-category">${escapeHtml(writeup.category)}</span>` : ''}
                    ${!isNarrative && writeup.cvss_score !== null ? `<span class="writeup-cvss">CVSS: ${escapeHtml(writeup.cvss_score)}</span>` : ''}
                    ${writeup.tags ? `<span class="writeup-tags">${escapeHtml(writeup.tags)}</span>` : ''}
                </div>

                <div class="writeup-actions" ${on('click', 'event.stopPropagation')}>
                    <button class="btn btn-icon btn-sm" ${on('click', 'ReportingManager.showEditWriteupModal', writeup.id)} title="Edit">
                        <i data-lucide="edit-2"></i>
                    </button>
                    <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.deleteWriteup', writeup.id)} title="Delete">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Render Report Generation - Three Panel Layout
     */
    renderGenerationContent() {
        // Check if we have an active engagement
        const engagementId = typeof AppState !== 'undefined' ? AppState.activeEngagement?.id : null;

        if (!engagementId) {
            return `
                <div class="generation-placeholder">
                    <div class="placeholder-content">
                        <div class="placeholder-icon"><i data-lucide="file-chart-column"></i></div>
                        <h2>Report Generation</h2>
                        <p>Please select an engagement to generate reports.</p>
                    </div>
                </div>
            `;
        }

        return `
            <div class="report-generator">
                <!-- Toolbar -->
                <div class="report-toolbar">
                    <div class="report-selector">
                        <select id="reportSelect" ${on('change', 'ReportingManager.loadReport', ARG.value)}>
                            <option value="">-- New Report --</option>
                            ${this.savedReports.map(r => `
                                <option value="${r.id}" ${this.currentReport?.id === r.id ? 'selected' : ''}>
                                    ${escapeHtml(r.name)}
                                </option>
                            `).join('')}
                        </select>
                        <input type="text" id="reportName" placeholder="Report name..."
                               value="${escapeHtml(this.currentReport?.name || '')}"
                               ${on('change', 'ReportingManager.updateReportName', ARG.value)}>
                        <button class="btn btn-primary btn-sm" ${on('click', 'ReportingManager.saveReport')}>
                            <i data-lucide="save"></i> Save
                        </button>
                        <button class="btn btn-sm btn-new" ${on('click', 'ReportingManager.newReport')}>
                            <i data-lucide="file-plus"></i> New
                        </button>
                        ${this.currentReport?.id ? `
                            <button class="btn btn-danger btn-sm" ${on('click', 'ReportingManager.deleteReport')}>
                                <i data-lucide="trash-2"></i>
                            </button>
                        ` : ''}
                        ${this.savedReports.length > 0 ? `
                            <button class="btn btn-sm btn-gear" ${on('click', 'ReportingManager.showManageReportsModal')} title="Manage Reports">
                                <i data-lucide="settings"></i>
                            </button>
                        ` : ''}
                    </div>
                    <div class="export-buttons">
                        <span class="export-label">Export:</span>
                        <button class="btn btn-sm btn-export-html" ${on('click', 'ReportingManager.exportReport', 'html')} title="Export as HTML">HTML</button>
                        <button class="btn btn-sm btn-export-md" ${on('click', 'ReportingManager.exportReport', 'markdown')} title="Export as Markdown">MD</button>
                        <button class="btn btn-sm btn-export-pdf" ${on('click', 'ReportingManager.exportReport', 'pdf')} title="Export as PDF with cover page">PDF</button>
                        <button class="btn btn-sm btn-export-word" ${on('click', 'ReportingManager.exportReport', 'docx')} title="Export as Word">Word</button>
                    </div>
                </div>

                <!-- Three Panel Layout -->
                <div class="report-panels">
                    <!-- LEFT: Source Items -->
                    <div class="report-panel source-panel">
                        <div class="panel-header">
                            <h4>Available Items</h4>
                        </div>
                        <div class="source-sections">
                            ${this.renderSourceFindings()}
                            ${this.renderSourceWriteups()}
                            ${this.renderFormatTools()}
                        </div>
                    </div>

                    <!-- MIDDLE: Workspace -->
                    <div class="report-panel workspace-panel"
                         ${on('dragover', 'ReportingManager.handleDragOver', ARG.event, ARG.el)}
                         ${on('drop', 'ReportingManager.handleWorkspaceDrop', ARG.event, ARG.el)}
                         ${on('dragleave', 'ReportingManager.handleDragLeave', ARG.event, ARG.el)}>
                        <div class="panel-header">
                            <h4>Report Workspace</h4>
                            <span class="item-count">${this.workspaceItems.length} item${this.workspaceItems.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="workspace-items" id="workspaceItems">
                            ${this.renderWorkspaceItems()}
                        </div>
                    </div>

                    <!-- RIGHT: Preview -->
                    <div class="report-panel preview-panel">
                        <div class="panel-header">
                            <h4>Live Preview</h4>
                        </div>
                        <div class="preview-content" id="reportPreview">
                            ${this.renderPreview()}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render source findings from current engagement
     */
    renderSourceFindings() {
        const isCollapsed = this.sourceCollapsed.findings;
        const findingsHtml = this.engagementFindings.map(finding => `
            <div class="source-item criticality-${this._criticality(finding.criticality)}"
                 draggable="true"
                 data-type="engagement_finding"
                 data-id="${finding.id}"
                 ${on('dragstart', 'ReportingManager.handleDragStart', ARG.event, 'engagement_finding', finding.id)}
                 ${on('dragend', 'ReportingManager.handleDragEnd', ARG.event)}>
                <span class="drag-handle">⋮⋮</span>
                <div class="source-item-content">
                    <span class="criticality-badge criticality-${this._criticality(finding.criticality)}">${this._criticality(finding.criticality)}</span>
                    <span class="item-title">${escapeHtml(finding.title)}</span>
                </div>
            </div>
        `).join('');

        return `
            <div class="source-section ${isCollapsed ? 'collapsed' : ''}">
                <div class="section-header" ${on('click', 'ReportingManager.toggleSourceSection', 'findings')}>
                    <span class="collapse-icon">${isCollapsed ? '▶' : '▼'}</span>
                    <h5>Engagement Findings (${this.engagementFindings.length})</h5>
                </div>
                <div class="section-content">
                    ${this.engagementFindings.length === 0 ? '<p class="empty-hint">No findings in this engagement</p>' : findingsHtml}
                </div>
            </div>
        `;
    },

    /**
     * Render source writeups from database
     */
    renderSourceWriteups() {
        const isCollapsed = this.sourceCollapsed.writeups;
        const findings = this.writeups.filter(w => w.writeup_type !== 'narrative');
        const narratives = this.writeups.filter(w => w.writeup_type === 'narrative');

        const renderWriteupItem = (writeup) => `
            <div class="source-item ${writeup.writeup_type === 'narrative' ? 'narrative' : 'criticality-' + this._criticality(writeup.criticality)}"
                 draggable="true"
                 data-type="writeup"
                 data-id="${writeup.id}"
                 ${on('dragstart', 'ReportingManager.handleDragStart', ARG.event, 'writeup', writeup.id)}
                 ${on('dragend', 'ReportingManager.handleDragEnd', ARG.event)}>
                <span class="drag-handle">⋮⋮</span>
                <div class="source-item-content">
                    ${writeup.writeup_type === 'narrative'
                        ? '<span class="type-badge narrative">N</span>'
                        : `<span class="criticality-badge criticality-${this._criticality(writeup.criticality)}">${this._criticality(writeup.criticality)}</span>`
                    }
                    <span class="item-title">${escapeHtml(writeup.name)}</span>
                </div>
            </div>
        `;

        const writeupsHtml = `
            ${narratives.length > 0 ? `
                <div class="writeup-group">
                    <span class="group-label">Narratives</span>
                    ${narratives.map(renderWriteupItem).join('')}
                </div>
            ` : ''}
            ${findings.length > 0 ? `
                <div class="writeup-group">
                    <span class="group-label">Findings</span>
                    ${findings.map(renderWriteupItem).join('')}
                </div>
            ` : ''}
        `;

        return `
            <div class="source-section ${isCollapsed ? 'collapsed' : ''}">
                <div class="section-header" ${on('click', 'ReportingManager.toggleSourceSection', 'writeups')}>
                    <span class="collapse-icon">${isCollapsed ? '▶' : '▼'}</span>
                    <h5>Writeups Database (${this.writeups.length})</h5>
                </div>
                <div class="section-content">
                    ${this.writeups.length === 0 ? '<p class="empty-hint">No writeups in database</p>' : writeupsHtml}
                </div>
            </div>
        `;
    },

    /**
     * Render format tools section
     */
    renderFormatTools() {
        const isCollapsed = this.sourceCollapsed.formatTools;

        const formatTools = [
            // Basic tools
            { id: 'spacer', name: 'Spacer', icon: '↕', description: 'Add blank space' },
            { id: 'divider', name: 'Divider', icon: '―', description: 'Horizontal line' },
            { id: 'pagebreak', name: 'Page Break', icon: '↧', description: 'Page break for print' },
            // Text content tools
            { id: 'sectionheader', name: 'Section Header', icon: 'H', description: 'Heading with level' },
            { id: 'textblock', name: 'Text Block', icon: '¶', description: 'Rich text paragraph' },
            { id: 'quote', name: 'Quote Block', icon: '❝', description: 'Blockquote with attribution' },
            // List tools
            { id: 'bulletlist', name: 'Bullet List', icon: '•', description: 'Unordered list' },
            { id: 'numberedlist', name: 'Numbered List', icon: '1.', description: 'Ordered list' },
            { id: 'checklist', name: 'Checklist', icon: '☑', description: 'Checkbox list' },
            // Code/Terminal tools
            { id: 'codeblock', name: 'Code Block', icon: '<>', description: 'Syntax highlighted code' },
            { id: 'commandoutput', name: 'Command Output', icon: '$_', description: 'Terminal command + output' },
            // Callout tools
            { id: 'alertbox', name: 'Alert Box', icon: '⚠', description: 'Info/warning/danger box' },
            { id: 'keyfinding', name: 'Key Finding', icon: '★', description: 'Highlighted summary' },
            { id: 'evidence', name: 'Evidence Block', icon: '◩', description: 'Image + description' },
            { id: 'imageplaceholder', name: 'Image Placeholder', icon: '▭', description: 'Image placeholder' },
            // Complex tools
            { id: 'table', name: 'Table', icon: '▦', description: '3-column table' },
            { id: 'twocolumn', name: 'Two-Column', icon: '▐▌', description: 'Side-by-side layout' },
            { id: 'timeline', name: 'Timeline', icon: '→', description: 'Vertical timeline' },
            { id: 'riskmatrix', name: 'Risk Matrix', icon: '▣', description: 'Likelihood × Impact' },
            { id: 'cvsscard', name: 'CVSS Card', icon: '◉', description: 'CVSS score breakdown' },
            { id: 'attackmap', name: 'Attack Map', icon: '⌖', description: 'Embedded attack map' },
            { id: 'coloredtable', name: 'Findings Table', icon: '▤', description: 'Color-coded findings table' }
        ];

        const toolsHtml = formatTools.map(tool => `
            <div class="source-item format-tool"
                 draggable="true"
                 data-type="format_tool"
                 data-id="${tool.id}"
                 ${on('dragstart', 'ReportingManager.handleDragStart', ARG.event, 'format_tool', String(tool.id))}
                 ${on('dragend', 'ReportingManager.handleDragEnd', ARG.event)}>
                <span class="drag-handle">⋮⋮</span>
                <div class="source-item-content">
                    <span class="format-tool-icon">${tool.icon}</span>
                    <span class="item-title">${tool.name}</span>
                    <span class="item-description">${tool.description}</span>
                </div>
            </div>
        `).join('');

        return `
            <div class="source-section ${isCollapsed ? 'collapsed' : ''}">
                <div class="section-header" ${on('click', 'ReportingManager.toggleSourceSection', 'formatTools')}>
                    <span class="collapse-icon">${isCollapsed ? '▶' : '▼'}</span>
                    <h5>Format Tools</h5>
                </div>
                <div class="section-content">
                    ${toolsHtml}
                </div>
            </div>
        `;
    },

    /**
     * Render workspace items
     */
    renderWorkspaceItems() {
        if (this.workspaceItems.length === 0) {
            return `
                <div class="workspace-empty">
                    <div class="empty-icon"><i data-lucide="file-plus"></i></div>
                    <p>Drag items here to build your report</p>
                    <p class="hint">Items can be reordered by dragging</p>
                </div>
            `;
        }

        return this.workspaceItems.map((item, index) => {
            const isFormatTool = item.writeup_type === 'format_tool';
            const isNarrative = item.writeup_type === 'narrative';

            if (isFormatTool) {
                const toolId = item.format_tool_id || item.source_id;
                const isTable = toolId === 'table';
                const tableInfo = isTable && item.tableData
                    ? `${item.tableData.headers.length} cols, ${item.tableData.rows.length} rows`
                    : '';

                // Determine if tool is editable and get info text
                const editableTools = ['table', 'coloredtable', 'sectionheader', 'textblock', 'quote', 'bulletlist', 'numberedlist',
                                       'checklist', 'codeblock', 'commandoutput', 'alertbox', 'keyfinding',
                                       'evidence', 'imageplaceholder', 'twocolumn', 'timeline', 'riskmatrix', 'cvsscard', 'attackmap'];
                const isEditable = editableTools.includes(toolId);

                // Get brief info for workspace display
                let itemInfo = '<span class="item-source">Format</span>';
                if (isTable) {
                    itemInfo = `<span class="table-info">${tableInfo}</span>`;
                } else if (toolId === 'sectionheader' && item.toolData) {
                    itemInfo = `<span class="tool-info">H${Math.trunc(this._number(item.toolData.level, 2, 1, 6))}</span>`;
                } else if (toolId === 'alertbox' && item.toolData) {
                    itemInfo = `<span class="tool-info alert-type-${escapeHtml(item.toolData.type)}">${escapeHtml(item.toolData.type)}</span>`;
                } else if (toolId === 'cvsscard' && item.toolData) {
                    itemInfo = `<span class="tool-info cvss-score">${escapeHtml(item.toolData.score)}</span>`;
                } else if (toolId === 'riskmatrix' && item.toolData) {
                    itemInfo = `<span class="tool-info">${escapeHtml(item.toolData.size)}×${escapeHtml(item.toolData.size)}</span>`;
                } else if ((toolId === 'bulletlist' || toolId === 'numberedlist') && item.toolData) {
                    itemInfo = `<span class="tool-info">${item.toolData.items.length} items</span>`;
                } else if (toolId === 'checklist' && item.toolData) {
                    itemInfo = `<span class="tool-info">${item.toolData.items.length} items</span>`;
                } else if (toolId === 'timeline' && item.toolData) {
                    itemInfo = `<span class="tool-info">${item.toolData.steps.length} steps</span>`;
                } else if (toolId === 'attackmap' && item.toolData) {
                    itemInfo = `<span class="tool-info">${escapeHtml(item.toolData.mapName || 'No map')}</span>`;
                } else if (toolId === 'coloredtable' && item.toolData) {
                    itemInfo = `<span class="table-info">${item.toolData.headers.length} cols, ${item.toolData.rows.length} rows</span>`;
                }

                return `
                    <div class="workspace-item format-tool-item"
                         draggable="true"
                         data-position="${index}"
                         data-uuid="${escapeHtml(item.id)}"
                         ${on('dragstart', 'ReportingManager.handleWorkspaceDragStart', ARG.event, index)}
                         ${on('dragend', 'ReportingManager.handleDragEnd', ARG.event)}
                         ${on('dragover', 'ReportingManager.handleItemDragOver', ARG.event, index, ARG.el)}
                         ${on('drop', 'ReportingManager.handleItemDrop', ARG.event, index, ARG.el)}>
                        <span class="drag-handle">⋮⋮</span>
                        <div class="workspace-item-content">
                            <span class="format-tool-badge">${escapeHtml(item.icon || '?')}</span>
                            <span class="item-title">${escapeHtml(item.title || 'Format Tool')}</span>
                            ${itemInfo}
                        </div>
                        <div class="workspace-item-actions">
                            ${isEditable ? `
                                <button class="btn btn-icon btn-sm" ${on('click', 'ReportingManager.showFormatToolEditor', String(item.id), String(toolId))} title="Edit">
                                    <i data-lucide="edit-2"></i>
                                </button>
                            ` : ''}
                            <button class="btn btn-icon btn-sm" ${on('click', 'ReportingManager.removeWorkspaceItem', String(item.id))} title="Remove">
                                <i data-lucide="x"></i>
                            </button>
                        </div>
                    </div>
                `;
            }

            const cust = item.customizations || {};
            const showTitle = cust.show_title !== false;
            const headingLevel = this._headingTag(cust.heading_level);
            const isExpanded = this._expandedWriteupId === item.id;

            return `
                <div class="workspace-item ${isNarrative ? 'narrative' : `criticality-${this._criticality(item.criticality)}`}"
                     draggable="true"
                     data-position="${index}"
                     data-uuid="${escapeHtml(item.id)}"
                     ${on('dragstart', 'ReportingManager.handleWorkspaceDragStart', ARG.event, index)}
                     ${on('dragend', 'ReportingManager.handleDragEnd', ARG.event)}
                     ${on('dragover', 'ReportingManager.handleItemDragOver', ARG.event, index, ARG.el)}
                     ${on('drop', 'ReportingManager.handleItemDrop', ARG.event, index, ARG.el)}>
                    <span class="drag-handle">⋮⋮</span>
                    <div class="workspace-item-content">
                        ${isNarrative
                            ? '<span class="type-badge narrative">Narrative</span>'
                            : `<span class="criticality-badge criticality-${this._criticality(item.criticality)}">${this._criticality(item.criticality)}</span>`
                        }
                        <span class="item-title">${escapeHtml(item.title || 'Untitled')}</span>
                        <span class="item-source">${item.type === 'engagement_finding' ? 'Finding' : 'Writeup'}</span>
                        ${!showTitle ? '<span class="tool-info" title="Title hidden">No Title</span>' : headingLevel !== 'h3' ? `<span class="tool-info" title="Heading level">${headingLevel.toUpperCase()}</span>` : ''}
                    </div>
                    <div class="workspace-item-actions">
                        <button class="btn btn-icon btn-sm ${isExpanded ? 'active' : ''}" ${on('click', 'ReportingManager.toggleWriteupTitleEditor', String(item.id))} title="Title Settings">
                            <i data-lucide="edit-2"></i>
                        </button>
                        <button class="btn btn-icon btn-sm" ${on('click', 'ReportingManager.removeWorkspaceItem', String(item.id))} title="Remove">
                            <i data-lucide="x"></i>
                        </button>
                    </div>
                </div>
                ${isExpanded ? `
                <div class="workspace-item-editor" data-editor-for="${escapeHtml(item.id)}">
                    <div class="editor-row">
                        <label class="toggle-label">
                            <input type="checkbox" ${showTitle ? 'checked' : ''}
                                   ${on('change', 'ReportingManager.updateWriteupTitleSetting', String(item.id), 'show_title', ARG.checked)}>
                            <span>Show title in report</span>
                        </label>
                        <div class="editor-field">
                            <label>Heading</label>
                            <select class="form-input form-input-sm"
                                    ${on('change', 'ReportingManager.updateWriteupTitleSetting', String(item.id), 'heading_level', ARG.value)}
                                    style="width: auto;">
                                <option value="h1" ${headingLevel === 'h1' ? 'selected' : ''}>H1</option>
                                <option value="h2" ${headingLevel === 'h2' ? 'selected' : ''}>H2</option>
                                <option value="h3" ${headingLevel === 'h3' ? 'selected' : ''}>H3</option>
                                <option value="h4" ${headingLevel === 'h4' ? 'selected' : ''}>H4</option>
                            </select>
                        </div>
                    </div>
                </div>
                ` : ''}
            `;
        }).join('');
    },

    /**
     * Render live preview
     */
    renderPreview() {
        if (this.workspaceItems.length === 0) {
            return '<p class="preview-empty">Drag items to the workspace to build your report</p>';
        }

        let html = '<div class="report-preview-content">';

        for (const item of this.workspaceItems) {
            const isFormatTool = item.writeup_type === 'format_tool';
            const isNarrative = item.writeup_type === 'narrative';

            if (isFormatTool) {
                // Render format tool based on type
                const toolId = item.format_tool_id || item.source_id;
                const toolData = item.toolData || {};

                if (toolId === 'spacer') {
                    html += `<div class="preview-spacer"><br><br></div>`;
                } else if (toolId === 'divider') {
                    html += `<hr class="preview-divider">`;
                } else if (toolId === 'pagebreak') {
                    html += `<div class="preview-pagebreak"><span>— Page Break —</span></div>`;
                } else if (toolId === 'sectionheader') {
                    const level = Math.trunc(this._number(toolData.level, 2, 1, 6));
                    const text = toolData.text || 'Section Title';
                    const number = toolData.numbered && toolData.number ? `${toolData.number} ` : '';
                    html += `<h${level} class="preview-sectionheader">${escapeHtml(number)}${escapeHtml(text)}</h${level}>`;
                } else if (toolId === 'textblock') {
                    const content = toolData.content || 'Enter your text here...';
                    html += `<div class="preview-textblock">${this.renderMarkdown(content)}</div>`;
                } else if (toolId === 'quote') {
                    const text = toolData.text || 'Enter quote text here...';
                    const attribution = toolData.attribution || '';
                    html += `
                        <blockquote class="preview-quote">
                            <p>${escapeHtml(text)}</p>
                            ${attribution ? `<footer>— ${escapeHtml(attribution)}</footer>` : ''}
                        </blockquote>
                    `;
                } else if (toolId === 'bulletlist') {
                    const items = toolData.items || ['Item 1', 'Item 2', 'Item 3'];
                    html += `
                        <ul class="preview-bulletlist">
                            ${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                        </ul>
                    `;
                } else if (toolId === 'numberedlist') {
                    const items = toolData.items || ['Step 1', 'Step 2', 'Step 3'];
                    html += `
                        <ol class="preview-numberedlist">
                            ${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                        </ol>
                    `;
                } else if (toolId === 'checklist') {
                    const title = toolData.title || 'Checklist';
                    const items = toolData.items || [{ text: 'Item 1', checked: false }];
                    html += `
                        <div class="preview-checklist">
                            <h4>${escapeHtml(title)}</h4>
                            <ul>
                                ${items.map(item => `
                                    <li class="${item.checked ? 'checked' : ''}">
                                        <span class="checkbox">${item.checked ? '☑' : '☐'}</span>
                                        <span>${escapeHtml(item.text)}</span>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    `;
                } else if (toolId === 'codeblock') {
                    const code = toolData.code || '# Enter code here';
                    const language = toolData.language || 'bash';
                    const title = toolData.title || '';
                    html += `
                        <div class="preview-codeblock">
                            ${title ? `<div class="code-title">${escapeHtml(title)}</div>` : ''}
                            <pre class="language-${escapeHtml(language)}"><code>${escapeHtml(code)}</code></pre>
                        </div>
                    `;
                } else if (toolId === 'commandoutput') {
                    const command = toolData.command || '$ whoami';
                    const output = toolData.output || 'root';
                    html += `
                        <div class="preview-commandoutput">
                            <div class="command-line">${escapeHtml(command)}</div>
                            <div class="command-output">${escapeHtml(output)}</div>
                        </div>
                    `;
                } else if (toolId === 'alertbox') {
                    const type = toolData.type || 'warning';
                    const title = toolData.title || 'Warning';
                    const content = toolData.content || 'Important information here.';
                    const icons = { info: 'ℹ', warning: '⚠', danger: '⛔', success: '✓' };
                    html += `
                        <div class="preview-alertbox alert-${escapeHtml(type)}">
                            <div class="alert-icon">${icons[type] || '⚠'}</div>
                            <div class="alert-content">
                                <div class="alert-title">${escapeHtml(title)}</div>
                                <div class="alert-body">${escapeHtml(content)}</div>
                            </div>
                        </div>
                    `;
                } else if (toolId === 'keyfinding') {
                    const title = toolData.title || 'Key Finding';
                    const content = toolData.content || 'Summary of critical discovery.';
                    html += `
                        <div class="preview-keyfinding">
                            <div class="keyfinding-icon">★</div>
                            <div class="keyfinding-content">
                                <div class="keyfinding-title">${escapeHtml(title)}</div>
                                <div class="keyfinding-body">${escapeHtml(content)}</div>
                            </div>
                        </div>
                    `;
                } else if (toolId === 'evidence') {
                    const imageCaption = toolData.imageCaption || 'Screenshot description';
                    const description = toolData.description || 'Evidence details...';
                    const impact = toolData.impact || 'Impact statement...';
                    html += `
                        <div class="preview-evidence">
                            <div class="evidence-image-placeholder">
                                <span class="placeholder-icon">📷</span>
                                <span class="placeholder-text">${escapeHtml(imageCaption)}</span>
                            </div>
                            <div class="evidence-description">
                                <strong>Description:</strong> ${escapeHtml(description)}
                            </div>
                            <div class="evidence-impact">
                                <strong>Impact:</strong> ${escapeHtml(impact)}
                            </div>
                        </div>
                    `;
                } else if (toolId === 'imageplaceholder') {
                    const caption = toolData.caption || 'Figure 1: Description';
                    const width = ['100%', '75%', '50%', '25%'].includes(toolData.width) ? toolData.width : '100%';
                    html += `
                        <div class="preview-imageplaceholder" style="width: ${escapeHtml(width)}">
                            <div class="placeholder-box">
                                <span class="placeholder-icon">🖼</span>
                                <span class="placeholder-text">Insert Image Here</span>
                            </div>
                            <div class="image-caption">${escapeHtml(caption)}</div>
                        </div>
                    `;
                } else if (toolId === 'table') {
                    const tableData = item.tableData || {
                        headers: ['Column 1', 'Column 2', 'Column 3'],
                        rows: [['Data 1', 'Data 2', 'Data 3'], ['Data 4', 'Data 5', 'Data 6']]
                    };
                    html += `
                        <div class="preview-table">
                            <table>
                                <thead>
                                    <tr>
                                        ${tableData.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tableData.rows.map(row => `
                                        <tr>
                                            ${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else if (toolId === 'coloredtable') {
                    const ctData = item.toolData || { headers: ['Finding', 'Severity', 'Status'], rows: [] };
                    // Same scale as every other severity view: purple critical, red high,
                    // orange medium, yellow low (--sev-* tokens); green is the theme's ok.
                    const cellColors = {
                        purple: { bg: 'var(--sev-critical-soft)', text: 'var(--sev-critical-text)' },
                        red:    { bg: 'var(--sev-high-soft)',     text: 'var(--sev-high-text)' },
                        orange: { bg: 'var(--sev-medium-soft)',   text: 'var(--sev-medium-text)' },
                        yellow: { bg: 'var(--sev-low-soft)',      text: 'var(--sev-low-text)' },
                        green:  { bg: 'var(--color-ok-soft)',     text: 'var(--color-ok)' }
                    };
                    html += `
                        <div class="preview-table preview-colored-table">
                            <table>
                                <thead>
                                    <tr>
                                        ${ctData.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${ctData.rows.map(row => `
                                        <tr>
                                            ${row.map(cell => {
                                                const c = typeof cell === 'object' ? cell : { text: cell, color: null };
                                                const colorStyle = c.color && cellColors[c.color]
                                                    ? `background:${cellColors[c.color].bg};color:${cellColors[c.color].text};font-weight:600;`
                                                    : '';
                                                return `<td style="${colorStyle}">${escapeHtml(c.text || '')}</td>`;
                                            }).join('')}
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else if (toolId === 'twocolumn') {
                    const leftTitle = toolData.leftTitle || 'Before';
                    const leftContent = toolData.leftContent || 'Left column content...';
                    const rightTitle = toolData.rightTitle || 'After';
                    const rightContent = toolData.rightContent || 'Right column content...';
                    html += `
                        <div class="preview-twocolumn">
                            <div class="column">
                                <h4>${escapeHtml(leftTitle)}</h4>
                                <div class="column-content">${this.renderMarkdown(leftContent)}</div>
                            </div>
                            <div class="column">
                                <h4>${escapeHtml(rightTitle)}</h4>
                                <div class="column-content">${this.renderMarkdown(rightContent)}</div>
                            </div>
                        </div>
                    `;
                } else if (toolId === 'timeline') {
                    const steps = toolData.steps || [{ time: '10:00', title: 'Step 1', description: 'Description' }];
                    html += `
                        <div class="preview-timeline">
                            ${steps.map((step, idx) => `
                                <div class="timeline-step">
                                    <div class="timeline-marker">
                                        <span class="step-number">${idx + 1}</span>
                                    </div>
                                    <div class="timeline-content">
                                        <div class="step-time">${escapeHtml(step.time)}</div>
                                        <div class="step-title">${escapeHtml(step.title)}</div>
                                        <div class="step-description">${escapeHtml(step.description)}</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else if (toolId === 'riskmatrix') {
                    const size = Number(toolData.size) === 5 ? 5 : 3;
                    const highlighted = toolData.highlighted || { row: 1, col: 2 };
                    const labels = size === 3
                        ? { rows: ['High', 'Medium', 'Low'], cols: ['Low', 'Medium', 'High'] }
                        : { rows: ['Critical', 'High', 'Medium', 'Low', 'Info'], cols: ['Rare', 'Unlikely', 'Possible', 'Likely', 'Certain'] };
                    html += `
                        <div class="preview-riskmatrix">
                            <div class="matrix-ylabel">Likelihood</div>
                            <table class="risk-matrix size-${size}">
                                <thead>
                                    <tr>
                                        <th></th>
                                        ${labels.cols.map(c => `<th>${c}</th>`).join('')}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${labels.rows.map((row, rowIdx) => `
                                        <tr>
                                            <th>${row}</th>
                                            ${labels.cols.map((col, colIdx) => {
                                                const isHighlighted = highlighted.row === rowIdx && highlighted.col === colIdx;
                                                const risk = this.getRiskLevel(rowIdx, colIdx, size);
                                                return `<td class="risk-${risk} ${isHighlighted ? 'highlighted' : ''}"></td>`;
                                            }).join('')}
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                            <div class="matrix-xlabel">Impact</div>
                        </div>
                    `;
                } else if (toolId === 'cvsscard') {
                    const score = this._number(toolData.score, 7.5, 0, 10);
                    const vector = toolData.vector || 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N';
                    const severity = this.getCvssSeverity(score);
                    html += `
                        <div class="preview-cvsscard">
                            <div class="cvss-score-badge severity-${severity.toLowerCase()}">
                                <span class="score">${score}</span>
                                <span class="severity">${severity}</span>
                            </div>
                            <div class="cvss-details">
                                <div class="cvss-vector">${escapeHtml(vector)}</div>
                                ${this.renderCvssBreakdown(vector)}
                            </div>
                        </div>
                    `;
                } else if (toolId === 'attackmap') {
                    const mapId = toolData.mapId;
                    const mapName = toolData.mapName || 'Attack Map';
                    if (mapId) {
                        html += `
                            <div class="preview-attackmap" data-map-id="${Number(mapId)}">
                                <div style="text-align:center;padding:20px;background:#1e1e2e;border-radius:8px;border:1px solid #374151;">
                                    <div class="preview-attackmap-icon"><i data-lucide="map"></i></div>
                                    <div style="color:#e2e8f0;font-weight:600;">${escapeHtml(mapName)}</div>
                                    <div style="color:#94a3b8;font-size:12px;margin-top:4px;">Attack Map (embedded in export)</div>
                                </div>
                            </div>
                        `;
                    } else {
                        html += `
                            <div class="preview-attackmap">
                                <div style="text-align:center;padding:20px;background:#2a2a3e;border-radius:8px;border:1px dashed #374151;">
                                    <div style="color:#64748b;">No map selected — edit to choose</div>
                                </div>
                            </div>
                        `;
                    }
                }
            } else if (isNarrative) {
                const customizations = item.customizations || {};
                const showTitle = customizations.show_title !== false;
                const headingLevel = this._headingTag(customizations.heading_level);
                const titleHtml = showTitle ? `<${headingLevel}>${escapeHtml(item.title || 'Untitled')}</${headingLevel}>` : '';
                html += `
                    <div class="preview-narrative">
                        ${titleHtml}
                        <div class="preview-body">${this.renderMarkdown(item.finding_content || item.description || '')}</div>
                    </div>
                `;
            } else {
                const customizations = item.customizations || {};
                const showTitle = customizations.show_title !== false;
                const headingLevel = this._headingTag(customizations.heading_level);
                const titleHtml = showTitle ? `<${headingLevel}>${escapeHtml(item.title || 'Untitled')}</${headingLevel}>` : '';
                html += `
                    <div class="preview-finding criticality-${this._criticality(item.criticality)}">
                        ${titleHtml}
                        <div class="preview-meta">
                            <span class="criticality-badge criticality-${this._criticality(item.criticality)}">${this._criticality(item.criticality)}</span>
                            ${item.cvss_score ? `<span class="cvss">CVSS: ${escapeHtml(item.cvss_score)}</span>` : ''}
                        </div>
                        <div class="preview-body">${this.renderMarkdown(item.finding_content || item.description || '')}</div>
                        ${item.remediation_content || item.remediation ? `
                            <div class="preview-remediation">
                                <h4>Remediation</h4>
                                ${this.renderMarkdown(item.remediation_content || item.remediation || '')}
                            </div>
                        ` : ''}
                    </div>
                `;
            }
        }

        html += '</div>';
        return html;
    },

    /**
     * Render markdown content
     */
    renderMarkdown(content) {
        return renderMarkdown(content);   // sanitized (static/js/lib/markdown.js, H-9)
    },

    /**
     * Toggle source section collapse
     */
    toggleSourceSection(section) {
        this.sourceCollapsed[section] = !this.sourceCollapsed[section];
        const isCollapsed = this.sourceCollapsed[section];

        // Find the section element by looking at the onclick handler
        const sectionHeaders = document.querySelectorAll('.source-section .section-header');
        let sectionEl = null;
        sectionHeaders.forEach(header => {
            const onclick = header.getAttribute('onclick');
            if (onclick && onclick.includes(`'${section}'`)) {
                sectionEl = header.closest('.source-section');
            }
        });

        if (sectionEl) {
            // Toggle the collapsed class
            sectionEl.classList.toggle('collapsed', isCollapsed);

            // Update the collapse icon
            const icon = sectionEl.querySelector('.collapse-icon');
            if (icon) {
                icon.textContent = isCollapsed ? '▶' : '▼';
            }
        }
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Search input
        const searchInput = document.getElementById('writeupSearch');
        if (searchInput) {
            searchInput.addEventListener('input', debounce(() => {
                this.filters.search = searchInput.value;
                this.applyFilters();
            }, 300));
        }
    },

    /**
     * Apply filters and reload writeups
     */
    async applyFilters() {
        const categorySelect = document.getElementById('categoryFilter');
        const criticalitySelect = document.getElementById('criticalityFilter');
        const typeSelect = document.getElementById('typeFilter');
        const searchInput = document.getElementById('writeupSearch');

        if (categorySelect) this.filters.category = categorySelect.value;
        if (criticalitySelect) this.filters.criticality = criticalitySelect.value;
        if (typeSelect) this.filters.writeup_type = typeSelect.value;
        if (searchInput) this.filters.search = searchInput.value;

        await this.loadWriteups();

        const list = document.getElementById('writeupsList');
        if (list) {
            list.innerHTML = this.renderWriteupsList();
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }

        // Update count
        const countEl = document.querySelector('.writeups-count');
        if (countEl) {
            countEl.textContent = `${this.writeups.length} writeup${this.writeups.length !== 1 ? 's' : ''}`;
        }
    },

    /**
     * Toggle writeup type (finding vs narrative) in inline form
     */
    toggleWriteupType(mode, type) {
        // Update hidden field
        const typeInput = document.getElementById('writeupFormType');
        if (typeInput) typeInput.value = type;

        // Update toggle button states
        const toggleContainer = document.querySelector('#writeupFormCard .writeup-type-toggle');
        if (toggleContainer) {
            toggleContainer.querySelectorAll('.type-toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.type === type);
            });
        }

        // Update type hint
        const typeHint = document.getElementById('writeupFormTypeHint');
        if (typeHint) {
            typeHint.textContent = type === 'finding'
                ? 'Findings include criticality, CVSS score, and remediation information.'
                : 'Narratives are for introductions, methodology, executive summaries, etc.';
        }

        // Show/hide finding-specific fields
        const findingFields = document.getElementById('writeupFormFindingFields');
        const narrativeTags = document.getElementById('writeupFormNarrativeTags');
        const remediationGroup = document.getElementById('writeupFormRemediationGroup');

        if (findingFields) findingFields.style.display = type === 'finding' ? 'block' : 'none';
        if (narrativeTags) narrativeTags.style.display = type === 'narrative' ? 'block' : 'none';
        if (remediationGroup) remediationGroup.style.display = type === 'finding' ? 'block' : 'none';
    },

    /**
     * Show inline writeup form (add or edit)
     */
    async showWriteupForm(writeupId = null, prefillData = null) {
        const mainArea = document.querySelector('.writeups-main');
        if (!mainArea) return;

        // Determine if editing
        let writeup = null;
        if (writeupId) {
            try {
                writeup = await API.reporting.getWriteup(writeupId);
            } catch (error) {
                showToast('Failed to load writeup', 'error');
                return;
            }
        }

        const isEdit = !!writeup;
        const wt = writeup ? (writeup.writeup_type || 'finding') : 'finding';
        const isFinding = wt === 'finding';

        // Build prefill values
        const name = prefillData?.name || (writeup?.name || '');
        const category = prefillData?.category || (writeup?.category || '');
        const criticality = prefillData?.criticality || (writeup?.criticality || 'medium');
        const cvss = prefillData?.cvss_score || (writeup?.cvss_score ?? '');
        const description = prefillData?.description || (writeup?.description || '');
        const remediation = prefillData?.remediation || (writeup?.remediation || '');
        const tags = prefillData?.tags || (writeup?.tags || '');
        const showTitle = writeup ? writeup.show_title_in_report !== 0 : true;
        const headingLevel = writeup?.report_heading_level || 'h3';

        mainArea.innerHTML = `
            <div id="writeupFormCard" class="inline-form-card">
                <div class="inline-form-header">
                    <h3>${isEdit ? 'Edit Writeup' : 'Add Writeup'}</h3>
                    <button class="btn btn-icon" ${on('click', 'ReportingManager.hideWriteupForm')} title="Cancel">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="sensitive-warning" style="margin-bottom: var(--spacing-md);">
                    <span class="warning-icon"><i data-lucide="triangle-alert"></i></span>
                    <span>Writeups are shared across all engagements. Do not include sensitive client information, IP addresses, or engagement-specific details.</span>
                </div>
                <form id="writeupForm" ${on('submit', 'ReportingManager.handleWriteupFormSubmit', ARG.event)}>
                    <input type="hidden" id="writeupFormId" value="${isEdit ? writeup.id : ''}">

                    <!-- Type Toggle -->
                    <div class="form-group">
                        <label>Writeup Type</label>
                        <div class="writeup-type-toggle">
                            <button type="button" class="type-toggle-btn ${isFinding ? 'active' : ''}" data-type="finding" ${on('click', 'ReportingManager.toggleWriteupType', 'form', 'finding')}>Finding</button>
                            <button type="button" class="type-toggle-btn ${!isFinding ? 'active' : ''}" data-type="narrative" ${on('click', 'ReportingManager.toggleWriteupType', 'form', 'narrative')}>Narrative</button>
                        </div>
                        <input type="hidden" id="writeupFormType" name="writeup_type" value="${wt}">
                        <p class="type-hint" id="writeupFormTypeHint">${isFinding ? 'Findings include criticality, CVSS score, and remediation information.' : 'Narratives are for introductions, methodology, executive summaries, etc.'}</p>
                    </div>

                    <div class="form-row">
                        <div class="form-group flex-2">
                            <label for="writeupFormName">Name *</label>
                            <input type="text" id="writeupFormName" name="name" required value="${escapeHtml(name)}" placeholder="e.g., SQL Injection in Login Form">
                        </div>
                        <div class="form-group flex-1">
                            <label for="writeupFormCategory">Category</label>
                            <input type="text" id="writeupFormCategory" name="category" list="categoryOptions" value="${escapeHtml(category)}" placeholder="e.g., SQL Injection">
                            <datalist id="categoryOptions"></datalist>
                        </div>
                    </div>

                    <!-- Title Display Settings -->
                    <div class="form-row" style="align-items: flex-end;">
                        <div class="form-group flex-1">
                            <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                                <input type="checkbox" id="writeupFormShowTitle" name="show_title_in_report" ${showTitle ? 'checked' : ''}>
                                <span>Show title in report</span>
                            </label>
                        </div>
                        <div class="form-group flex-1">
                            <label for="writeupFormHeadingLevel">Title Heading Level</label>
                            <select id="writeupFormHeadingLevel" name="report_heading_level">
                                <option value="h1" ${headingLevel === 'h1' ? 'selected' : ''}>H1 - Title</option>
                                <option value="h2" ${headingLevel === 'h2' ? 'selected' : ''}>H2 - Section</option>
                                <option value="h3" ${headingLevel === 'h3' ? 'selected' : ''}>H3 - Subsection</option>
                                <option value="h4" ${headingLevel === 'h4' ? 'selected' : ''}>H4 - Minor</option>
                            </select>
                        </div>
                    </div>

                    <!-- Finding-specific fields -->
                    <div id="writeupFormFindingFields" style="display: ${isFinding ? 'block' : 'none'};">
                        <div class="form-row">
                            <div class="form-group flex-1">
                                <label for="writeupFormCriticality">Criticality *</label>
                                <select id="writeupFormCriticality" name="criticality">
                                    <option value="critical" ${criticality === 'critical' ? 'selected' : ''}>Critical</option>
                                    <option value="high" ${criticality === 'high' ? 'selected' : ''}>High</option>
                                    <option value="medium" ${criticality === 'medium' ? 'selected' : ''}>Medium</option>
                                    <option value="low" ${criticality === 'low' ? 'selected' : ''}>Low</option>
                                </select>
                            </div>
                            <div class="form-group flex-1">
                                <label for="writeupFormCvss">CVSS Score</label>
                                <input type="number" id="writeupFormCvss" name="cvss_score" min="0" max="10" step="0.1" value="${cvss}" placeholder="0.0 - 10.0">
                            </div>
                            <div class="form-group flex-2">
                                <label for="writeupFormTags">Tags</label>
                                <input type="text" id="writeupFormTags" name="tags" value="${escapeHtml(tags)}" placeholder="Comma-separated tags">
                            </div>
                        </div>
                    </div>

                    <!-- Tags for narrative -->
                    <div id="writeupFormNarrativeTags" style="display: ${!isFinding ? 'block' : 'none'};">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="writeupFormTagsNarrative">Tags</label>
                                <input type="text" id="writeupFormTagsNarrative" name="tags_narrative" value="${escapeHtml(!isFinding ? tags : '')}" placeholder="Comma-separated tags">
                            </div>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="writeupFormDescription">Description</label>
                        <textarea id="writeupFormDescription" name="description" placeholder="Describe the vulnerability...">${escapeHtml(description)}</textarea>
                    </div>

                    <!-- Remediation (finding-only) -->
                    <div class="form-group" id="writeupFormRemediationGroup" style="display: ${isFinding ? 'block' : 'none'};">
                        <label for="writeupFormRemediation">Remediation</label>
                        <textarea id="writeupFormRemediation" name="remediation" placeholder="How to fix this vulnerability...">${escapeHtml(remediation)}</textarea>
                    </div>

                    <div class="inline-form-footer">
                        <button type="button" class="btn btn-secondary" ${on('click', 'ReportingManager.hideWriteupForm')}>Cancel</button>
                        <button type="submit" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Save Writeup'}</button>
                    </div>
                </form>
            </div>
        `;

        // Populate category datalist
        this.populateCategoryDatalist();

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        this._initWriteupMDE();
    },

    _mdeDesc: null,
    _mdeRem: null,

    _initWriteupMDE() {
        this._destroyWriteupMDE();
        const mdeConfig = (placeholder) => ({
            spellChecker: false,
            autosave: { enabled: false },
            status: false,
            autoDownloadFontAwesome: false,
            placeholder,
            toolbar: [
                'bold', 'italic', 'heading', '|',
                'quote', 'code', 'unordered-list', 'ordered-list', '|',
                'link', 'image', '|',
                'preview', 'side-by-side', 'fullscreen', '|',
                'guide',
            ],
            previewRender(plainText) { return renderMarkdown(plainText); },
        });

        const descEl = document.getElementById('writeupFormDescription');
        if (descEl && typeof EasyMDE !== 'undefined') {
            this._mdeDesc = new EasyMDE({ element: descEl, ...mdeConfig('Describe the vulnerability…') });
        }

        const remEl = document.getElementById('writeupFormRemediation');
        if (remEl && typeof EasyMDE !== 'undefined') {
            this._mdeRem = new EasyMDE({ element: remEl, ...mdeConfig('How to fix this vulnerability…') });
        }
    },

    _destroyWriteupMDE() {
        if (this._mdeDesc) { try { this._mdeDesc.toTextArea(); this._mdeDesc.cleanup(); } catch (_) {} this._mdeDesc = null; }
        if (this._mdeRem)  { try { this._mdeRem.toTextArea();  this._mdeRem.cleanup();  } catch (_) {} this._mdeRem  = null; }
    },

    /**
     * Hide inline writeup form and restore the list
     */
    hideWriteupForm() {
        this._destroyWriteupMDE();
        const mainArea = document.querySelector('.writeups-main');
        if (!mainArea) return;

        mainArea.innerHTML = `
            <div class="writeups-header">
                <div class="writeups-search">
                    <i data-lucide="search" class="search-icon"></i>
                    <input type="text" id="writeupSearch" placeholder="Search writeups..."
                           value="${escapeHtml(this.filters.search)}" autocomplete="off">
                </div>
                <div class="writeups-header-actions">
                    <button class="btn btn-secondary" ${on('click', 'ReportingManager.showComparisonModal')} title="Compare multiple engagements">
                        <i data-lucide="bar-chart-2"></i>
                        Compare Engagements
                    </button>
                    <span class="writeups-count">${this.writeups.length} writeup${this.writeups.length !== 1 ? 's' : ''}</span>
                </div>
            </div>
            <div class="writeups-list" id="writeupsList">
                ${this.renderWriteupsList()}
            </div>
        `;

        this.setupEventListeners();
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Handle unified writeup form submission (add or edit)
     */
    async handleWriteupFormSubmit(e) {
        e.preventDefault();

        const writeupId = document.getElementById('writeupFormId')?.value;
        const isEdit = !!writeupId;
        const form = document.getElementById('writeupForm');
        const formData = new FormData(form);
        const writeupType = formData.get('writeup_type') || 'finding';

        const tags = writeupType === 'finding'
            ? formData.get('tags')
            : formData.get('tags_narrative');

        const data = {
            name: formData.get('name'),
            category: formData.get('category'),
            writeup_type: writeupType,
            description: this._mdeDesc ? this._mdeDesc.value() : formData.get('description'),
            tags: tags || '',
            show_title_in_report: document.getElementById('writeupFormShowTitle')?.checked ? 1 : 0,
            report_heading_level: document.getElementById('writeupFormHeadingLevel')?.value || 'h3'
        };

        if (writeupType === 'finding') {
            data.criticality = formData.get('criticality');
            data.cvss_score = formData.get('cvss_score') || null;
            data.remediation = this._mdeRem ? this._mdeRem.value() : formData.get('remediation');
        }

        try {
            if (isEdit) {
                await API.reporting.updateWriteup(writeupId, data);
                showToast('Writeup updated successfully', 'success');
            } else {
                await API.reporting.createWriteup(data);
                showToast('Writeup created successfully', 'success');
            }

            // Reset filters for new writeups
            if (!isEdit) {
                this.filters = { category: 'all', criticality: 'all', writeup_type: 'all', search: '' };
            }

            // Reload and re-render
            await this.loadWriteups();
            await this.loadCategories();
            this.hideWriteupForm();

        } catch (error) {
            showToast(error.message || 'Failed to save writeup', 'error');
        }
    },

    /**
     * Backward-compatible aliases
     */
    showAddWriteupModal(prefillData = null) {
        this.showWriteupForm(null, prefillData);
    },

    showEditWriteupModal(writeupId) {
        this.showWriteupForm(writeupId);
    },

    /**
     * Populate category datalist with existing categories
     */
    populateCategoryDatalist() {
        const datalist = document.getElementById('categoryOptions');
        if (datalist) {
            datalist.innerHTML = this.categories.map(cat =>
                `<option value="${escapeHtml(cat.name)}">`
            ).join('');
        }
    },


    /**
     * Delete a writeup
     */
    async deleteWriteup(writeupId) {
        if (!confirm('Are you sure you want to delete this writeup? This action cannot be undone.')) {
            return;
        }

        try {
            await API.reporting.deleteWriteup(writeupId);
            showToast('Writeup deleted successfully', 'success');

            // Reload writeups and categories
            await this.loadWriteups();
            await this.loadCategories();

            // Re-render the list
            const list = document.getElementById('writeupsList');
            if (list) {
                list.innerHTML = this.renderWriteupsList();
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }

            // Update count
            const countEl = document.querySelector('.writeups-count');
            if (countEl) {
                countEl.textContent = `${this.writeups.length} writeup${this.writeups.length !== 1 ? 's' : ''}`;
            }
        } catch (error) {
            showToast(error.message || 'Failed to delete writeup', 'error');
        }
    },

    /**
     * Update markdown preview
     */
    updatePreview(textareaId, previewId) {
        const textarea = document.getElementById(textareaId);
        const preview = document.getElementById(previewId);
        if (!textarea || !preview) return;

        const content = textarea.value;
        preview.innerHTML = renderMarkdown(content);
    },

    /**
     * Show sensitive info warning modal before saving to writeups
     * Used when saving a finding to the writeups database
     */
    showSensitiveWarningModal(findingData) {
        const modal = document.getElementById('sensitiveWarningModal');
        if (!modal) return;

        // Store the finding data for later use
        this.pendingFindingData = findingData;

        modal.style.display = 'flex';
    },

    /**
     * Confirm and proceed to add writeup from finding
     */
    confirmSaveToWriteups() {
        closeModal('sensitiveWarningModal');

        if (this.pendingFindingData) {
            this.showAddWriteupModal(this.pendingFindingData);
            this.pendingFindingData = null;
        }
    },

    // ============================================
    // REPORT GENERATOR METHODS
    // ============================================

    /**
     * Initialize report generator when switching to generation tab
     */
    async initReportGenerator() {
        const engagementId = typeof AppState !== 'undefined' ? AppState.activeEngagement?.id : null;
        if (!engagementId) return;

        try {
            // Load engagement findings
            this.engagementFindings = await API.engagements.getFindings(engagementId);

            // Load saved reports for this engagement
            this.savedReports = await API.reporting.getReports(engagementId);

            // Load writeups (already loaded, but refresh)
            await this.loadWriteups();
        } catch (error) {
            console.error('Failed to initialize report generator:', error);
        }
    },

    /**
     * Setup event listeners for report generator
     */
    setupGeneratorEventListeners() {
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    // ============================================
    // DRAG AND DROP HANDLERS
    // ============================================

    /**
     * Handle drag start from source panel
     */
    handleDragStart(event, type, sourceId) {
        this.dragState.draggedItem = { type, sourceId };
        this.dragState.draggedFrom = 'source';
        this.dragState.draggedIndex = null;

        event.dataTransfer.setData('text/plain', JSON.stringify({ type, sourceId }));
        event.dataTransfer.effectAllowed = 'copy';
        event.target.classList.add('dragging');
    },

    /**
     * Handle drag start from workspace (reordering)
     */
    handleWorkspaceDragStart(event, position) {
        this.dragState.draggedItem = this.workspaceItems[position];
        this.dragState.draggedFrom = 'workspace';
        this.dragState.draggedIndex = position;

        event.dataTransfer.setData('text/plain', JSON.stringify({ position }));
        event.dataTransfer.effectAllowed = 'move';
        event.target.classList.add('dragging');
    },

    /**
     * Handle drag over workspace
     */
    handleDragOver(event, el = event.currentTarget) {
        event.preventDefault();
        event.dataTransfer.dropEffect = this.dragState.draggedFrom === 'source' ? 'copy' : 'move';

        const workspacePanel = el;
        if (workspacePanel) {
            workspacePanel.classList.add('drag-over');
        }
    },

    /**
     * Handle drag leave workspace
     */
    handleDragLeave(event, el = event.currentTarget) {
        const workspacePanel = el;
        if (workspacePanel) {
            workspacePanel.classList.remove('drag-over');
        }
    },

    /**
     * Handle drag over individual workspace item
     */
    handleItemDragOver(event, targetPosition, el = event.currentTarget) {
        event.preventDefault();
        event.stopPropagation();

        // Remove drop-target class from all items
        document.querySelectorAll('.workspace-item').forEach(el => {
            el.classList.remove('drop-target', 'drop-target-after');
        });

        // Add drop target indicator
        const item = el;
        if (item) {
            const rect = item.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            if (event.clientY < midY) {
                item.classList.add('drop-target');
            } else {
                item.classList.add('drop-target-after');
            }
        }
    },

    /**
     * Handle drop on workspace (add new item at end)
     */
    async handleWorkspaceDrop(event, el = event.currentTarget) {
        event.preventDefault();

        const workspacePanel = el;
        if (workspacePanel) {
            workspacePanel.classList.remove('drag-over');
        }

        if (this.dragState.draggedFrom === 'source') {
            await this.addItemToWorkspace(this.dragState.draggedItem.type, this.dragState.draggedItem.sourceId);
        }

        this.clearDragState();
        this.refreshGenerator();
    },

    /**
     * Handle drop on workspace item (insert at position)
     */
    async handleItemDrop(event, targetPosition, el = event.currentTarget) {
        event.preventDefault();
        event.stopPropagation();

        // Determine insert position based on drop position
        const item = el;
        let insertPosition = targetPosition;
        if (item && item.classList.contains('drop-target-after')) {
            insertPosition = targetPosition + 1;
        }

        // Remove drop target indicators
        document.querySelectorAll('.workspace-item').forEach(el => {
            el.classList.remove('drop-target', 'drop-target-after');
        });

        if (this.dragState.draggedFrom === 'workspace') {
            // Reorder within workspace
            const currentPosition = this.dragState.draggedIndex;
            if (currentPosition !== insertPosition && currentPosition !== insertPosition - 1) {
                const movedItem = this.workspaceItems.splice(currentPosition, 1)[0];
                // Adjust insert position if moving forward
                if (currentPosition < insertPosition) {
                    insertPosition--;
                }
                this.workspaceItems.splice(insertPosition, 0, movedItem);
            }
        } else if (this.dragState.draggedFrom === 'source') {
            // Insert copy at specific position
            await this.addItemToWorkspace(
                this.dragState.draggedItem.type,
                this.dragState.draggedItem.sourceId,
                insertPosition
            );
        }

        this.clearDragState();
        this.refreshGenerator();
    },

    /**
     * Handle drag end
     */
    handleDragEnd(event) {
        event.target.classList.remove('dragging');
        document.querySelectorAll('.workspace-item').forEach(el => {
            el.classList.remove('drop-target', 'drop-target-after');
        });
        document.querySelectorAll('.workspace-panel').forEach(el => {
            el.classList.remove('drag-over');
        });
    },

    /**
     * Clear drag state
     */
    clearDragState() {
        this.dragState = {
            draggedItem: null,
            draggedFrom: null,
            draggedIndex: null
        };
    },

    // ============================================
    // WORKSPACE ITEM MANAGEMENT
    // ============================================

    /**
     * Add item to workspace
     */
    async addItemToWorkspace(type, sourceId, position = null) {
        // Get source data
        let sourceData;
        if (type === 'engagement_finding') {
            sourceData = this.engagementFindings.find(f => f.id === sourceId);
            if (sourceData) {
                sourceData = {
                    ...sourceData,
                    writeup_type: 'finding'
                };
            }
        } else if (type === 'writeup') {
            const writeup = this.writeups.find(w => w.id === sourceId);
            if (writeup) {
                sourceData = {
                    title: writeup.name,
                    criticality: writeup.criticality,
                    cvss_score: writeup.cvss_score,
                    finding_content: writeup.description,
                    remediation_content: writeup.remediation,
                    writeup_type: writeup.writeup_type || 'finding',
                    show_title_in_report: writeup.show_title_in_report,
                    report_heading_level: writeup.report_heading_level
                };
            }
        } else if (type === 'format_tool') {
            // Format tools don't need database lookup
            const formatToolMeta = {
                spacer: { title: 'Spacer', icon: '↕' },
                divider: { title: 'Divider', icon: '―' },
                pagebreak: { title: 'Page Break', icon: '↧' },
                sectionheader: { title: 'Section Header', icon: 'H' },
                textblock: { title: 'Text Block', icon: '¶' },
                quote: { title: 'Quote Block', icon: '❝' },
                bulletlist: { title: 'Bullet List', icon: '•' },
                numberedlist: { title: 'Numbered List', icon: '1.' },
                checklist: { title: 'Checklist', icon: '☑' },
                codeblock: { title: 'Code Block', icon: '<>' },
                commandoutput: { title: 'Command Output', icon: '$_' },
                alertbox: { title: 'Alert Box', icon: '⚠' },
                keyfinding: { title: 'Key Finding', icon: '★' },
                evidence: { title: 'Evidence Block', icon: '◩' },
                imageplaceholder: { title: 'Image Placeholder', icon: '▭' },
                table: { title: 'Table', icon: '▦' },
                twocolumn: { title: 'Two-Column', icon: '▐▌' },
                timeline: { title: 'Timeline', icon: '→' },
                riskmatrix: { title: 'Risk Matrix', icon: '▣' },
                cvsscard: { title: 'CVSS Card', icon: '◉' },
                attackmap: { title: 'Attack Map', icon: '⌖' },
                coloredtable: { title: 'Findings Table', icon: '▤' }
            };
            const meta = formatToolMeta[sourceId] || { title: sourceId, icon: '?' };
            sourceData = {
                title: meta.title,
                icon: meta.icon,
                format_tool_id: sourceId,
                writeup_type: 'format_tool'
            };

            // Add default data for tools that need it
            if (sourceId === 'table') {
                sourceData.tableData = {
                    headers: ['Column 1', 'Column 2', 'Column 3'],
                    rows: [
                        ['Data 1', 'Data 2', 'Data 3'],
                        ['Data 4', 'Data 5', 'Data 6']
                    ]
                };
            } else if (sourceId === 'sectionheader') {
                sourceData.toolData = { text: 'Section Title', level: 2, numbered: false, number: '' };
            } else if (sourceId === 'textblock') {
                sourceData.toolData = { content: 'Enter your text here. Supports **markdown** formatting.' };
            } else if (sourceId === 'quote') {
                sourceData.toolData = { text: 'Enter quote text here...', attribution: '' };
            } else if (sourceId === 'bulletlist') {
                sourceData.toolData = { items: ['Item 1', 'Item 2', 'Item 3'] };
            } else if (sourceId === 'numberedlist') {
                sourceData.toolData = { items: ['Step 1', 'Step 2', 'Step 3'] };
            } else if (sourceId === 'checklist') {
                sourceData.toolData = { title: 'Checklist', items: [{ text: 'Item 1', checked: false }, { text: 'Item 2', checked: false }, { text: 'Item 3', checked: false }] };
            } else if (sourceId === 'codeblock') {
                sourceData.toolData = { code: '# Enter code here', language: 'bash', title: '' };
            } else if (sourceId === 'commandoutput') {
                sourceData.toolData = { command: '$ whoami', output: 'root' };
            } else if (sourceId === 'alertbox') {
                sourceData.toolData = { type: 'warning', title: 'Warning', content: 'Important information here.' };
            } else if (sourceId === 'keyfinding') {
                sourceData.toolData = { title: 'Key Finding', content: 'Summary of critical discovery.' };
            } else if (sourceId === 'evidence') {
                sourceData.toolData = { imageCaption: 'Screenshot description', description: 'Evidence details...', impact: 'Impact statement...' };
            } else if (sourceId === 'imageplaceholder') {
                sourceData.toolData = { caption: 'Figure 1: Description', width: '100%' };
            } else if (sourceId === 'twocolumn') {
                sourceData.toolData = { leftTitle: 'Before', leftContent: 'Left column content...', rightTitle: 'After', rightContent: 'Right column content...' };
            } else if (sourceId === 'timeline') {
                sourceData.toolData = { steps: [{ time: '10:00', title: 'Step 1', description: 'Initial access' }, { time: '10:15', title: 'Step 2', description: 'Privilege escalation' }, { time: '10:30', title: 'Step 3', description: 'Data exfiltration' }] };
            } else if (sourceId === 'riskmatrix') {
                sourceData.toolData = { size: 3, highlighted: { row: 1, col: 2 } };
            } else if (sourceId === 'cvsscard') {
                sourceData.toolData = { score: 7.5, vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N' };
            } else if (sourceId === 'attackmap') {
                sourceData.toolData = { mapId: null, mapName: '' };
            } else if (sourceId === 'coloredtable') {
                sourceData.toolData = {
                    headers: ['Finding', 'Severity', 'Status', 'Notes'],
                    rows: [
                        [{ text: 'SQL Injection', color: null }, { text: 'Critical', color: 'red' }, { text: 'Open', color: 'orange' }, { text: '', color: null }],
                        [{ text: 'XSS Vulnerability', color: null }, { text: 'High', color: 'orange' }, { text: 'Open', color: 'orange' }, { text: '', color: null }],
                        [{ text: 'Weak Passwords', color: null }, { text: 'Medium', color: 'yellow' }, { text: 'Remediated', color: 'green' }, { text: '', color: null }]
                    ]
                };
            }
        }

        if (!sourceData) {
            showToast('Source item not found', 'error');
            return;
        }

        // Build initial customizations from writeup defaults
        const initialCustomizations = {};
        if (sourceData.show_title_in_report !== undefined) {
            initialCustomizations.show_title = !!sourceData.show_title_in_report;
        }
        if (sourceData.report_heading_level) {
            initialCustomizations.heading_level = sourceData.report_heading_level;
        }

        const newItem = {
            id: this.generateUUID(),
            type: type,
            source_id: sourceId,
            position: position !== null ? position : this.workspaceItems.length,
            customizations: initialCustomizations,
            // Pre-populated display data
            title: sourceData.title,
            icon: sourceData.icon,
            criticality: sourceData.criticality,
            cvss_score: sourceData.cvss_score,
            finding_content: sourceData.finding_content,
            remediation_content: sourceData.remediation_content,
            description: sourceData.description,
            remediation: sourceData.remediation,
            writeup_type: sourceData.writeup_type,
            format_tool_id: sourceData.format_tool_id,
            tableData: sourceData.tableData,
            toolData: sourceData.toolData
        };

        if (position !== null) {
            this.workspaceItems.splice(position, 0, newItem);
        } else {
            this.workspaceItems.push(newItem);
        }

        // Update positions
        this.workspaceItems.forEach((item, idx) => item.position = idx);
    },

    /**
     * Remove item from workspace
     */
    removeWorkspaceItem(itemId) {
        this.workspaceItems = this.workspaceItems.filter(item => item.id !== itemId);
        this.workspaceItems.forEach((item, idx) => item.position = idx);
        this.refreshGenerator();
    },

    /**
     * Refresh the generator UI
     */
    refreshGenerator() {
        const workspaceEl = document.getElementById('workspaceItems');
        if (workspaceEl) {
            workspaceEl.innerHTML = this.renderWorkspaceItems();
        }

        const previewEl = document.getElementById('reportPreview');
        if (previewEl) {
            previewEl.innerHTML = this.renderPreview();
        }

        const countEl = document.querySelector('.item-count');
        if (countEl) {
            countEl.textContent = `${this.workspaceItems.length} item${this.workspaceItems.length !== 1 ? 's' : ''}`;
        }

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    // ============================================
    // REPORT PERSISTENCE
    // ============================================

    /**
     * Update report name
     */
    updateReportName(name) {
        if (this.currentReport) {
            this.currentReport.name = name;
        } else {
            this.currentReport = { name, structure: [] };
        }
    },

    /**
     * Create new report
     */
    newReport() {
        this.currentReport = null;
        this.workspaceItems = [];
        document.getElementById('reportName').value = '';
        document.getElementById('reportSelect').value = '';
        this.refreshGenerator();
    },

    /**
     * Save current report
     */
    async saveReport() {
        const nameInput = document.getElementById('reportName');
        const name = nameInput?.value?.trim();

        if (!name) {
            showToast('Please enter a report name', 'warning');
            nameInput?.focus();
            return;
        }

        const engagementId = typeof AppState !== 'undefined' ? AppState.activeEngagement?.id : null;
        if (!engagementId) {
            showToast('No active engagement', 'error');
            return;
        }

        // Build structure for saving
        const structure = this.workspaceItems.map((item, idx) => {
            const saved = {
                id: item.id,
                type: item.type,
                source_id: item.source_id,
                position: idx,
                customizations: item.customizations || {}
            };

            // Preserve format tool specific data
            if (item.writeup_type === 'format_tool') {
                saved.writeup_type = 'format_tool';
                saved.format_tool_id = item.format_tool_id || item.source_id;
                if (item.toolData) saved.toolData = item.toolData;
                if (item.tableData) saved.tableData = item.tableData;
                if (item.title) saved.title = item.title;
            }

            // Preserve writeup_type for narratives
            if (item.writeup_type === 'narrative') {
                saved.writeup_type = 'narrative';
            }

            return saved;
        });

        try {
            if (this.currentReport?.id) {
                // Update existing report
                const updated = await API.reporting.updateReport(this.currentReport.id, {
                    name,
                    structure
                });
                this.currentReport = updated;
                showToast('Report saved', 'success');
            } else {
                // Create new report
                const created = await API.reporting.createReport({
                    engagement_id: engagementId,
                    name,
                    structure
                });
                this.currentReport = created;
                this.savedReports.unshift(created);
                showToast('Report created', 'success');
            }

            // Refresh the report selector
            this.renderReportingSection();
            this.setupGeneratorEventListeners();
        } catch (error) {
            showToast(error.message || 'Failed to save report', 'error');
        }
    },

    /**
     * Load a report
     */
    async loadReport(reportId) {
        if (!reportId) {
            this.newReport();
            return;
        }

        try {
            const report = await API.reporting.getReport(reportId);
            this.currentReport = report;

            // Build workspace items from hydrated items
            this.workspaceItems = (report.hydrated_items || []).map((item, idx) => ({
                ...item,
                id: /^[A-Za-z0-9_-]{1,64}$/.test(String(item.id)) ? String(item.id) : this.generateUUID(),
                position: idx
            }));

            this.refreshGenerator();

            // Update name input
            const nameInput = document.getElementById('reportName');
            if (nameInput) {
                nameInput.value = report.name || '';
            }
        } catch (error) {
            showToast(error.message || 'Failed to load report', 'error');
        }
    },

    /**
     * Delete current report
     */
    async deleteReport() {
        if (!this.currentReport?.id) return;

        if (!confirm('Are you sure you want to delete this report?')) {
            return;
        }

        try {
            await API.reporting.deleteReport(this.currentReport.id);
            this.savedReports = this.savedReports.filter(r => r.id !== this.currentReport.id);
            showToast('Report deleted', 'success');
            this.newReport();
            this.renderReportingSection();
            this.setupGeneratorEventListeners();
        } catch (error) {
            showToast(error.message || 'Failed to delete report', 'error');
        }
    },

    /**
     * Show modal to manage reports
     */
    showManageReportsModal() {
        // Remove existing modal if any
        this.closeManageReportsModal();

        const modalHtml = `
            <div class="modal-overlay" id="manageReportsModal">
                <div class="modal-content" style="max-width: 500px;">
                    <div class="modal-header">
                        <h3>Manage Reports</h3>
                        <button class="modal-close" id="closeManageReportsBtn">&times;</button>
                    </div>
                    <div class="modal-body" id="manageReportsBody">
                        ${this.renderManageReportsList()}
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="closeManageReportsBtn2">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Setup event listeners
        const modal = document.getElementById('manageReportsModal');
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.closeManageReportsModal();
        });

        document.getElementById('closeManageReportsBtn').addEventListener('click', () => this.closeManageReportsModal());
        document.getElementById('closeManageReportsBtn2').addEventListener('click', () => this.closeManageReportsModal());

        // Setup delete buttons
        this.setupManageReportsDeleteButtons();

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render the reports list for the manage modal
     */
    renderManageReportsList() {
        const reports = this.savedReports || [];

        if (reports.length === 0) {
            return '<p>No saved reports.</p>';
        }

        // Simple escape function
        const esc = (text) => {
            if (!text) return '';
            return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        };

        const items = reports.map(r => {
            const name = esc(r.name || 'Untitled');
            return `
                <li class="manage-report-item" data-report-id="${r.id}">
                    <span class="report-name">${name}</span>
                    <button class="btn btn-danger btn-sm delete-report-btn" data-report-id="${r.id}" data-report-name="${name}">
                        <i data-lucide="trash-2"></i> Delete
                    </button>
                </li>
            `;
        }).join('');

        return `<ul class="manage-reports-list">${items}</ul>`;
    },

    /**
     * Setup delete button event listeners in manage modal
     */
    setupManageReportsDeleteButtons() {
        const buttons = document.querySelectorAll('#manageReportsModal .delete-report-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const reportId = parseInt(btn.dataset.reportId);
                const reportName = btn.dataset.reportName;
                await this.deleteReportById(reportId, reportName);
            });
        });
    },

    /**
     * Close manage reports modal
     */
    closeManageReportsModal() {
        const modal = document.getElementById('manageReportsModal');
        if (modal) {
            modal.remove();
        }
    },

    /**
     * Refresh the manage reports modal list
     */
    refreshManageReportsModal() {
        const body = document.getElementById('manageReportsBody');
        if (body) {
            body.innerHTML = this.renderManageReportsList();
            this.setupManageReportsDeleteButtons();
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    /**
     * Delete a report by ID (from manage modal)
     */
    async deleteReportById(reportId, reportName) {
        if (!confirm(`Are you sure you want to delete "${reportName}"?`)) {
            return;
        }

        try {
            await API.reporting.deleteReport(reportId);
            this.savedReports = this.savedReports.filter(r => r.id !== reportId);

            // If this was the current report, clear it
            if (this.currentReport?.id === reportId) {
                this.newReport();
            }

            showToast('Report deleted', 'success');

            // Refresh the modal list
            if (this.savedReports.length > 0) {
                this.refreshManageReportsModal();
            } else {
                this.closeManageReportsModal();
            }

            // Re-render to update dropdown
            this.renderReportingSection();
            this.setupGeneratorEventListeners();
        } catch (error) {
            showToast(error.message || 'Failed to delete report', 'error');
        }
    },

    // ============================================
    // EXPORT METHODS
    // ============================================

    /**
     * Export report in specified format
     */
    async exportReport(format) {
        if (this.workspaceItems.length === 0) {
            showToast('No items in report', 'warning');
            return;
        }

        // Save first if needed
        if (!this.currentReport?.id) {
            const nameInput = document.getElementById('reportName');
            if (!nameInput?.value?.trim()) {
                showToast('Please save the report first', 'warning');
                return;
            }
            await this.saveReport();
        }

        if (!this.currentReport?.id) {
            showToast('Please save the report first', 'warning');
            return;
        }

        try {
            // Show loading indicator for PDF generation
            if (format === 'pdf') {
                showToast('Generating PDF...', 'info');
            }

            const result = await API.reporting.exportReport(this.currentReport.id, format);

            if (format === 'pdf') {
                // Check if we got a Blob (proper PDF) or string (HTML fallback)
                if (result instanceof Blob) {
                    // Proper PDF - download it
                    this.downloadBlob(result, `${this.currentReport.name || 'report'}.pdf`);
                    showToast('PDF downloaded successfully', 'success');
                } else {
                    // HTML fallback - open print dialog
                    this._printHtml(result);
                    showToast('Opening print dialog...', 'info');
                }
            } else {
                // Download as file
                const extension = format === 'docx' ? 'docx' : (format === 'markdown' ? 'md' : 'html');
                this.downloadBlob(result, `${this.currentReport.name || 'report'}.${extension}`);
                showToast(`${format.toUpperCase()} exported successfully`, 'success');
            }
        } catch (error) {
            showToast(error.message || 'Export failed', 'error');
        }
    },

    /**
     * Print report HTML from the server's fallback (no WeasyPrint).
     *
     * The HTML holds teammate and scanner content, so it is never written into a
     * same-origin window. It renders in a sandboxed iframe: allow-same-origin
     * lets this page call print() on it, and without allow-scripts nothing in
     * the report can run (M-4).
     */
    _printHtml(html) {
        document.querySelectorAll('iframe[data-print-frame]').forEach(f => f.remove());
        const frame = document.createElement('iframe');
        frame.setAttribute('data-print-frame', '');
        frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
        frame.setAttribute('aria-hidden', 'true');
        frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
        frame.addEventListener('load', () => {
            try {
                frame.contentWindow.focus();
                frame.contentWindow.print();
            } catch (e) {
                showToast('Could not open the print dialog', 'error');
            }
        }, { once: true });
        frame.srcdoc = html;
        document.body.appendChild(frame);
    },

    /**
     * Download blob as file
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    // ============================================
    // TABLE EDITOR METHODS
    // ============================================

    /**
     * Current table being edited
     */
    editingTableId: null,
    editingTableData: null,

    /**
     * Show table editor modal
     */
    showTableEditor(itemId) {
        const item = this.workspaceItems.find(i => i.id === itemId);
        if (!item || !item.tableData) {
            showToast('Table not found', 'error');
            return;
        }

        this.editingTableId = itemId;
        // Deep clone the table data
        this.editingTableData = JSON.parse(JSON.stringify(item.tableData));

        // Create modal if it doesn't exist
        let modal = document.getElementById('tableEditorModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'tableEditorModal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }

        modal.innerHTML = `
            <div class="modal-content table-editor-modal">
                <div class="modal-header">
                    <h3>Edit Table</h3>
                    <button class="btn btn-icon" ${on('click', 'closeModal', 'tableEditorModal')}>
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="table-editor-controls">
                        <div class="control-group">
                            <label>Columns:</label>
                            <button class="btn btn-sm" ${on('click', 'ReportingManager.addTableColumn')}>+ Add Column</button>
                            <button class="btn btn-sm btn-danger" ${on('click', 'ReportingManager.removeTableColumn')}>- Remove</button>
                        </div>
                        <div class="control-group">
                            <label>Rows:</label>
                            <button class="btn btn-sm" ${on('click', 'ReportingManager.addTableRow')}>+ Add Row</button>
                            <button class="btn btn-sm btn-danger" ${on('click', 'ReportingManager.removeTableRow')}>- Remove</button>
                        </div>
                    </div>
                    <div class="table-editor-grid" id="tableEditorGrid">
                        ${this.renderTableEditorGrid()}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn" ${on('click', 'closeModal', 'tableEditorModal')}>Cancel</button>
                    <button class="btn btn-primary" ${on('click', 'ReportingManager.saveTableEdits')}>Save Changes</button>
                </div>
            </div>
        `;

        modal.style.display = 'flex';
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render the editable table grid
     */
    renderTableEditorGrid() {
        if (!this.editingTableData) return '';

        const { headers, rows } = this.editingTableData;

        return `
            <table class="editable-table">
                <thead>
                    <tr>
                        ${headers.map((h, i) => `
                            <th>
                                <input type="text" value="${escapeHtml(h)}"
                                       ${on('change', 'ReportingManager.updateTableHeader', i, ARG.value)}
                                       placeholder="Header ${i + 1}">
                            </th>
                        `).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${rows.map((row, rowIdx) => `
                        <tr>
                            ${row.map((cell, colIdx) => `
                                <td>
                                    <input type="text" value="${escapeHtml(cell)}"
                                           ${on('change', 'ReportingManager.updateTableCell', rowIdx, colIdx, ARG.value)}
                                           placeholder="Data">
                                </td>
                            `).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    /**
     * Update table header
     */
    updateTableHeader(colIndex, value) {
        if (this.editingTableData) {
            this.editingTableData.headers[colIndex] = value;
        }
    },

    /**
     * Update table cell
     */
    updateTableCell(rowIndex, colIndex, value) {
        if (this.editingTableData) {
            this.editingTableData.rows[rowIndex][colIndex] = value;
        }
    },

    /**
     * Add a column to the table
     */
    addTableColumn() {
        if (!this.editingTableData) return;

        const colNum = this.editingTableData.headers.length + 1;
        this.editingTableData.headers.push(`Column ${colNum}`);
        this.editingTableData.rows.forEach(row => row.push(''));

        this.refreshTableEditorGrid();
    },

    /**
     * Remove the last column from the table
     */
    removeTableColumn() {
        if (!this.editingTableData || this.editingTableData.headers.length <= 1) {
            showToast('Table must have at least one column', 'warning');
            return;
        }

        this.editingTableData.headers.pop();
        this.editingTableData.rows.forEach(row => row.pop());

        this.refreshTableEditorGrid();
    },

    /**
     * Add a row to the table
     */
    addTableRow() {
        if (!this.editingTableData) return;

        const newRow = this.editingTableData.headers.map(() => '');
        this.editingTableData.rows.push(newRow);

        this.refreshTableEditorGrid();
    },

    /**
     * Remove the last row from the table
     */
    removeTableRow() {
        if (!this.editingTableData || this.editingTableData.rows.length <= 1) {
            showToast('Table must have at least one row', 'warning');
            return;
        }

        this.editingTableData.rows.pop();

        this.refreshTableEditorGrid();
    },

    /**
     * Refresh the table editor grid
     */
    refreshTableEditorGrid() {
        const grid = document.getElementById('tableEditorGrid');
        if (grid) {
            grid.innerHTML = this.renderTableEditorGrid();
        }
    },

    /**
     * Save table edits
     */
    saveTableEdits() {
        if (!this.editingTableId || !this.editingTableData) return;

        const item = this.workspaceItems.find(i => i.id === this.editingTableId);
        if (item) {
            item.tableData = this.editingTableData;
        }

        this.editingTableId = null;
        this.editingTableData = null;

        closeModal('tableEditorModal');
        this.refreshGenerator();
        showToast('Table updated', 'success');
    },

    // ============================================
    // COLORED TABLE EDITOR METHODS
    // ============================================

    editingCtableId: null,
    editingCtableData: null,

    /**
     * Show the colored table editor modal
     */
    showColoredTableEditor(itemId) {
        const item = this.workspaceItems.find(i => i.id === itemId);
        if (!item) { showToast('Item not found', 'error'); return; }

        this.editingCtableId = itemId;
        this.editingCtableData = JSON.parse(JSON.stringify(item.toolData || {
            headers: ['Finding', 'Severity', 'Status', 'Notes'],
            rows: []
        }));

        let modal = document.getElementById('coloredTableEditorModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'coloredTableEditorModal';
            modal.className = 'modal modal-xl';
            document.body.appendChild(modal);
        }

        modal.innerHTML = this._renderCtableEditorContent();
        modal.style.display = 'flex';
    },

    /**
     * Render the full modal HTML for the colored table editor
     */
    _renderCtableEditorContent() {
        const d = this.editingCtableData;
        const colors = ['purple', 'red', 'orange', 'yellow', 'green'];
        const colorLabels = { purple: 'var(--sev-critical)', red: 'var(--sev-high)', orange: 'var(--sev-medium)',
                              yellow: 'var(--sev-low)', green: 'var(--color-ok)' };

        const headerInputs = d.headers.map((h, ci) => `
            <th>
                <input type="text" class="ctable-header-input" data-col="${ci}"
                       value="${escapeHtml(h)}" placeholder="Header"
                       ${on('change', 'ReportingManager.setCtableHeader', ci, ARG.value)}>
            </th>
        `).join('');

        const bodyRows = d.rows.map((row, ri) => {
            const cells = row.map((cell, ci) => {
                const c = typeof cell === 'object' ? cell : { text: cell, color: null };
                const swatches = colors.map(col => `
                    <button class="ctable-swatch${c.color === col ? ' active' : ''}"
                            style="background:${colorLabels[col]};"
                            title="${col}"
                            ${on('click', 'ReportingManager.setCtableColorFlushed', ri, ci, String(col))}
                            type="button"></button>
                `).join('');
                return `
                    <td>
                        <input type="text" class="ctable-cell-input" data-row="${ri}" data-col="${ci}"
                               value="${escapeHtml(c.text || '')}" placeholder="Cell text"
                               style="${c.color ? `border-color:${colorLabels[c.color]};` : ''}">
                        <div class="ctable-swatches">
                            <button class="ctable-swatch ctable-swatch-none${!c.color ? ' active' : ''}"
                                    title="No color"
                                    ${on('click', 'ReportingManager.setCtableColorFlushed', ri, ci, null)}
                                    type="button">✕</button>
                            ${swatches}
                        </div>
                    </td>
                `;
            }).join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        return `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Edit Findings Table</h3>
                    <button ${on('click', 'closeModal', 'coloredTableEditorModal')} class="btn btn-sm btn-secondary">✕</button>
                </div>
                <div class="modal-body">
                    <div class="ctable-editor-controls">
                        <button ${on('click', 'ReportingManager.ctableAddRow')} class="btn btn-sm btn-secondary" type="button">+ Add Row</button>
                        <button ${on('click', 'ReportingManager.ctableRemoveRow')} class="btn btn-sm btn-secondary" type="button">- Remove Row</button>
                        <button ${on('click', 'ReportingManager.ctableAddCol')} class="btn btn-sm btn-secondary" type="button">+ Add Column</button>
                        <button ${on('click', 'ReportingManager.ctableRemoveCol')} class="btn btn-sm btn-secondary" type="button">- Remove Column</button>
                    </div>
                    <div class="ctable-editor-wrap">
                        <table class="ctable-editor-table">
                            <thead><tr>${headerInputs}</tr></thead>
                            <tbody>${bodyRows}</tbody>
                        </table>
                    </div>
                    <p class="ctable-hint">Click a color swatch to set cell background. Click ✕ to clear color.</p>
                </div>
                <div class="modal-footer">
                    <button ${on('click', 'closeModal', 'coloredTableEditorModal')} class="btn btn-secondary">Cancel</button>
                    <button ${on('click', 'ReportingManager.saveColoredTableEdits')} class="btn btn-primary">Save Table</button>
                </div>
            </div>
        `;
    },

    /**
     * Read all current input values from the DOM into editingCtableData
     */
    _flushCtableInputs() {
        const modal = document.getElementById('coloredTableEditorModal');
        if (!modal) return;

        // Flush header inputs
        modal.querySelectorAll('.ctable-header-input').forEach(input => {
            const ci = parseInt(input.dataset.col);
            if (!isNaN(ci) && ci < this.editingCtableData.headers.length) {
                this.editingCtableData.headers[ci] = input.value;
            }
        });

        // Flush cell inputs
        modal.querySelectorAll('.ctable-cell-input').forEach(input => {
            const ri = parseInt(input.dataset.row);
            const ci = parseInt(input.dataset.col);
            if (!isNaN(ri) && !isNaN(ci) &&
                ri < this.editingCtableData.rows.length &&
                ci < this.editingCtableData.rows[ri].length) {
                const cell = this.editingCtableData.rows[ri][ci];
                if (typeof cell === 'object') {
                    cell.text = input.value;
                } else {
                    this.editingCtableData.rows[ri][ci] = { text: input.value, color: null };
                }
            }
        });
    },

    /**
     * Set color on a specific cell and re-render editor
     */
    /** Coloured-table header edit: keep typed cell values, then set the header (L-21). */
    setCtableHeader(ci, value) {
        this._flushCtableInputs();
        this.editingCtableData.headers[ci] = value;
    },

    /** Colour picker: keep typed cell values, then set the colour (L-21). */
    setCtableColorFlushed(ri, ci, color) {
        this._flushCtableInputs();
        this.setCtableColor(ri, ci, color);
    },

    setCtableColor(ri, ci, color) {
        if (!this.editingCtableData) return;
        const cell = this.editingCtableData.rows[ri][ci];
        if (typeof cell === 'object') {
            cell.color = color;
        } else {
            this.editingCtableData.rows[ri][ci] = { text: cell, color };
        }
        this._refreshCtableEditor();
    },

    /**
     * Re-render the colored table editor in place
     */
    _refreshCtableEditor() {
        const modal = document.getElementById('coloredTableEditorModal');
        if (!modal) return;
        modal.innerHTML = this._renderCtableEditorContent();
    },

    /**
     * Add a row to the colored table
     */
    ctableAddRow() {
        this._flushCtableInputs();
        const numCols = this.editingCtableData.headers.length;
        const newRow = Array.from({ length: numCols }, () => ({ text: '', color: null }));
        this.editingCtableData.rows.push(newRow);
        this._refreshCtableEditor();
    },

    /**
     * Remove the last row from the colored table
     */
    ctableRemoveRow() {
        this._flushCtableInputs();
        if (this.editingCtableData.rows.length <= 1) {
            showToast('Table must have at least one row', 'warning');
            return;
        }
        this.editingCtableData.rows.pop();
        this._refreshCtableEditor();
    },

    /**
     * Add a column to the colored table
     */
    ctableAddCol() {
        this._flushCtableInputs();
        this.editingCtableData.headers.push('Column');
        this.editingCtableData.rows.forEach(row => row.push({ text: '', color: null }));
        this._refreshCtableEditor();
    },

    /**
     * Remove the last column from the colored table
     */
    ctableRemoveCol() {
        this._flushCtableInputs();
        if (this.editingCtableData.headers.length <= 1) {
            showToast('Table must have at least one column', 'warning');
            return;
        }
        this.editingCtableData.headers.pop();
        this.editingCtableData.rows.forEach(row => row.pop());
        this._refreshCtableEditor();
    },

    /**
     * Save colored table edits back to the workspace item
     */
    saveColoredTableEdits() {
        this._flushCtableInputs();
        if (!this.editingCtableId || !this.editingCtableData) return;

        const item = this.workspaceItems.find(i => i.id === this.editingCtableId);
        if (item) {
            item.toolData = this.editingCtableData;
        }

        this.editingCtableId = null;
        this.editingCtableData = null;

        closeModal('coloredTableEditorModal');
        this.refreshGenerator();
        showToast('Findings table updated', 'success');
    },

    // ============================================
    // FORMAT TOOL EDITOR METHODS
    // ============================================

    /**
     * Track which writeup item has its inline editor expanded
     */
    _expandedWriteupId: null,

    /**
     * Toggle inline writeup title settings editor
     */
    toggleWriteupTitleEditor(itemId) {
        this._expandedWriteupId = this._expandedWriteupId === itemId ? null : itemId;
        this.refreshGenerator();
    },

    /**
     * Update a writeup title setting immediately (inline)
     */
    updateWriteupTitleSetting(itemId, key, value) {
        const item = this.workspaceItems.find(i => i.id === itemId);
        if (!item) return;

        if (!item.customizations) item.customizations = {};
        item.customizations[key] = value;

        // Update preview immediately without collapsing editor
        const previewEl = document.getElementById('reportPreview');
        if (previewEl) {
            previewEl.innerHTML = this.renderPreview();
        }

        // Update workspace item info badges without full refresh (to keep editor open)
        const wsItem = document.querySelector(`[data-uuid="${itemId}"] .workspace-item-content`);
        if (wsItem) {
            const showTitle = item.customizations.show_title !== false;
            const headingLevel = item.customizations.heading_level || 'h3';
            const existingInfo = wsItem.querySelector('.tool-info');
            if (existingInfo) existingInfo.remove();
            if (!showTitle) {
                wsItem.insertAdjacentHTML('beforeend', '<span class="tool-info" title="Title hidden">No Title</span>');
            } else if (headingLevel !== 'h3') {
                wsItem.insertAdjacentHTML('beforeend', `<span class="tool-info" title="Heading level">${headingLevel.toUpperCase()}</span>`);
            }
        }
    },

    /**
     * Current format tool being edited
     */
    editingToolId: null,
    editingToolData: null,
    editingToolType: null,

    /**
     * Show format tool editor - unified editor dispatcher
     */
    showFormatToolEditor(itemId, toolType) {
        // Table has its own editor
        if (toolType === 'table') {
            this.showTableEditor(itemId);
            return;
        }
        // Colored table has its own editor
        if (toolType === 'coloredtable') {
            this.showColoredTableEditor(itemId);
            return;
        }

        const item = this.workspaceItems.find(i => i.id === itemId);
        if (!item) {
            showToast('Item not found', 'error');
            return;
        }

        this.editingToolId = itemId;
        this.editingToolType = toolType;
        this.editingToolData = JSON.parse(JSON.stringify(item.toolData || {}));

        // Create modal if doesn't exist
        let modal = document.getElementById('formatToolEditorModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'formatToolEditorModal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }

        modal.innerHTML = this.getFormatToolEditorContent(toolType);
        modal.style.display = 'flex';
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Get editor content based on tool type
     */
    getFormatToolEditorContent(toolType) {
        const titles = {
            sectionheader: 'Edit Section Header',
            textblock: 'Edit Text Block',
            quote: 'Edit Quote Block',
            bulletlist: 'Edit Bullet List',
            numberedlist: 'Edit Numbered List',
            checklist: 'Edit Checklist',
            codeblock: 'Edit Code Block',
            commandoutput: 'Edit Command Output',
            alertbox: 'Edit Alert Box',
            keyfinding: 'Edit Key Finding',
            evidence: 'Edit Evidence Block',
            imageplaceholder: 'Edit Image Placeholder',
            twocolumn: 'Edit Two-Column Layout',
            timeline: 'Edit Timeline',
            riskmatrix: 'Edit Risk Matrix',
            cvsscard: 'Edit CVSS Card',
            attackmap: 'Select Attack Map'
        };

        const title = titles[toolType] || 'Edit Format Tool';
        const editorBody = this.getEditorBodyForTool(toolType);

        return `
            <div class="modal-content format-tool-editor-modal">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="btn btn-icon" ${on('click', 'closeModal', 'formatToolEditorModal')}>
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body">
                    ${editorBody}
                </div>
                <div class="modal-footer">
                    <button class="btn" ${on('click', 'closeModal', 'formatToolEditorModal')}>Cancel</button>
                    <button class="btn btn-primary" ${on('click', 'ReportingManager.saveFormatToolEdits')}>Save Changes</button>
                </div>
            </div>
        `;
    },

    /**
     * Get editor body content for specific tool type
     */
    getEditorBodyForTool(toolType) {
        const d = this.editingToolData;

        switch (toolType) {
            case 'sectionheader':
                return `
                    <div class="form-group">
                        <label>Header Text</label>
                        <input type="text" id="editorText" value="${escapeHtml(d.text || '')}" class="form-control">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Level</label>
                            <select id="editorLevel" class="form-control">
                                <option value="1" ${d.level === 1 ? 'selected' : ''}>H1 - Title</option>
                                <option value="2" ${d.level === 2 ? 'selected' : ''}>H2 - Section</option>
                                <option value="3" ${d.level === 3 ? 'selected' : ''}>H3 - Subsection</option>
                                <option value="4" ${d.level === 4 ? 'selected' : ''}>H4 - Minor</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Numbered</label>
                            <div class="checkbox-group">
                                <input type="checkbox" id="editorNumbered" ${d.numbered ? 'checked' : ''}>
                                <input type="text" id="editorNumber" value="${escapeHtml(d.number || '')}" placeholder="e.g., 1.1" class="form-control" style="width: 80px; margin-left: 8px;">
                            </div>
                        </div>
                    </div>
                `;

            case 'textblock':
                return `
                    <div class="form-group">
                        <label>Content (supports Markdown)</label>
                        <textarea id="editorContent" class="form-control" rows="8">${escapeHtml(d.content || '')}</textarea>
                    </div>
                    <div class="preview-hint">Use **bold**, *italic*, \`code\`, and [links](url)</div>
                `;

            case 'quote':
                return `
                    <div class="form-group">
                        <label>Quote Text</label>
                        <textarea id="editorText" class="form-control" rows="4">${escapeHtml(d.text || '')}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Attribution (optional)</label>
                        <input type="text" id="editorAttribution" value="${escapeHtml(d.attribution || '')}" class="form-control" placeholder="e.g., Author Name">
                    </div>
                `;

            case 'bulletlist':
            case 'numberedlist':
                const items = d.items || [];
                return `
                    <div class="list-editor">
                        <div class="list-items" id="listEditorItems">
                            ${items.map((item, idx) => `
                                <div class="list-item-row" data-index="${idx}">
                                    <span class="drag-handle">⋮⋮</span>
                                    <input type="text" value="${escapeHtml(item)}" class="form-control" ${on('change', 'ReportingManager.updateListItem', idx, ARG.value)}>
                                    <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeListItem', idx)}>
                                        <i data-lucide="x"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                        <button class="btn btn-sm" ${on('click', 'ReportingManager.addListItem')}>+ Add Item</button>
                    </div>
                `;

            case 'checklist':
                const checkItems = d.items || [];
                return `
                    <div class="form-group">
                        <label>Checklist Title</label>
                        <input type="text" id="editorTitle" value="${escapeHtml(d.title || '')}" class="form-control">
                    </div>
                    <div class="list-editor">
                        <div class="list-items" id="listEditorItems">
                            ${checkItems.map((item, idx) => `
                                <div class="list-item-row" data-index="${idx}">
                                    <input type="checkbox" ${item.checked ? 'checked' : ''} ${on('change', 'ReportingManager.updateChecklistItem', idx, 'checked', ARG.checked)}>
                                    <input type="text" value="${escapeHtml(item.text)}" class="form-control" ${on('change', 'ReportingManager.updateChecklistItem', idx, 'text', ARG.value)}>
                                    <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeChecklistItem', idx)}>
                                        <i data-lucide="x"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                        <button class="btn btn-sm" ${on('click', 'ReportingManager.addChecklistItem')}>+ Add Item</button>
                    </div>
                `;

            case 'codeblock':
                return `
                    <div class="form-group">
                        <label>Title (optional)</label>
                        <input type="text" id="editorTitle" value="${escapeHtml(d.title || '')}" class="form-control" placeholder="e.g., exploit.py">
                    </div>
                    <div class="form-group">
                        <label>Language</label>
                        <select id="editorLanguage" class="form-control">
                            <option value="bash" ${d.language === 'bash' ? 'selected' : ''}>Bash</option>
                            <option value="python" ${d.language === 'python' ? 'selected' : ''}>Python</option>
                            <option value="javascript" ${d.language === 'javascript' ? 'selected' : ''}>JavaScript</option>
                            <option value="powershell" ${d.language === 'powershell' ? 'selected' : ''}>PowerShell</option>
                            <option value="sql" ${d.language === 'sql' ? 'selected' : ''}>SQL</option>
                            <option value="php" ${d.language === 'php' ? 'selected' : ''}>PHP</option>
                            <option value="java" ${d.language === 'java' ? 'selected' : ''}>Java</option>
                            <option value="csharp" ${d.language === 'csharp' ? 'selected' : ''}>C#</option>
                            <option value="xml" ${d.language === 'xml' ? 'selected' : ''}>XML/HTML</option>
                            <option value="json" ${d.language === 'json' ? 'selected' : ''}>JSON</option>
                            <option value="yaml" ${d.language === 'yaml' ? 'selected' : ''}>YAML</option>
                            <option value="text" ${d.language === 'text' ? 'selected' : ''}>Plain Text</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Code</label>
                        <textarea id="editorCode" class="form-control code-textarea" rows="10">${escapeHtml(d.code || '')}</textarea>
                    </div>
                `;

            case 'commandoutput':
                return `
                    <div class="form-group">
                        <label>Command</label>
                        <input type="text" id="editorCommand" value="${escapeHtml(d.command || '')}" class="form-control code-input" placeholder="$ whoami">
                    </div>
                    <div class="form-group">
                        <label>Output</label>
                        <textarea id="editorOutput" class="form-control code-textarea" rows="6">${escapeHtml(d.output || '')}</textarea>
                    </div>
                `;

            case 'alertbox':
                return `
                    <div class="form-group">
                        <label>Alert Type</label>
                        <div class="alert-type-selector">
                            <label class="alert-option ${d.type === 'info' ? 'selected' : ''}">
                                <input type="radio" name="alertType" value="info" ${d.type === 'info' ? 'checked' : ''} ${on('change', 'ReportingManager.updateAlertTypePreview')}>
                                <span class="alert-preview alert-info">ℹ Info</span>
                            </label>
                            <label class="alert-option ${d.type === 'warning' ? 'selected' : ''}">
                                <input type="radio" name="alertType" value="warning" ${d.type === 'warning' ? 'checked' : ''} ${on('change', 'ReportingManager.updateAlertTypePreview')}>
                                <span class="alert-preview alert-warning">⚠ Warning</span>
                            </label>
                            <label class="alert-option ${d.type === 'danger' ? 'selected' : ''}">
                                <input type="radio" name="alertType" value="danger" ${d.type === 'danger' ? 'checked' : ''} ${on('change', 'ReportingManager.updateAlertTypePreview')}>
                                <span class="alert-preview alert-danger">⛔ Danger</span>
                            </label>
                            <label class="alert-option ${d.type === 'success' ? 'selected' : ''}">
                                <input type="radio" name="alertType" value="success" ${d.type === 'success' ? 'checked' : ''} ${on('change', 'ReportingManager.updateAlertTypePreview')}>
                                <span class="alert-preview alert-success">✓ Success</span>
                            </label>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Title</label>
                        <input type="text" id="editorTitle" value="${escapeHtml(d.title || '')}" class="form-control">
                    </div>
                    <div class="form-group">
                        <label>Content</label>
                        <textarea id="editorContent" class="form-control" rows="4">${escapeHtml(d.content || '')}</textarea>
                    </div>
                `;

            case 'keyfinding':
                return `
                    <div class="form-group">
                        <label>Title</label>
                        <input type="text" id="editorTitle" value="${escapeHtml(d.title || '')}" class="form-control">
                    </div>
                    <div class="form-group">
                        <label>Content</label>
                        <textarea id="editorContent" class="form-control" rows="4">${escapeHtml(d.content || '')}</textarea>
                    </div>
                `;

            case 'evidence':
                return `
                    <div class="form-group">
                        <label>Image Caption</label>
                        <input type="text" id="editorImageCaption" value="${escapeHtml(d.imageCaption || '')}" class="form-control" placeholder="Screenshot showing...">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea id="editorDescription" class="form-control" rows="4">${escapeHtml(d.description || '')}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Impact</label>
                        <textarea id="editorImpact" class="form-control" rows="3">${escapeHtml(d.impact || '')}</textarea>
                    </div>
                `;

            case 'imageplaceholder':
                return `
                    <div class="form-group">
                        <label>Caption</label>
                        <input type="text" id="editorCaption" value="${escapeHtml(d.caption || '')}" class="form-control" placeholder="Figure 1: Description">
                    </div>
                    <div class="form-group">
                        <label>Width</label>
                        <select id="editorWidth" class="form-control">
                            <option value="100%" ${d.width === '100%' ? 'selected' : ''}>Full Width (100%)</option>
                            <option value="75%" ${d.width === '75%' ? 'selected' : ''}>Large (75%)</option>
                            <option value="50%" ${d.width === '50%' ? 'selected' : ''}>Medium (50%)</option>
                            <option value="25%" ${d.width === '25%' ? 'selected' : ''}>Small (25%)</option>
                        </select>
                    </div>
                `;

            case 'twocolumn':
                return `
                    <div class="two-column-editor">
                        <div class="column-editor">
                            <div class="form-group">
                                <label>Left Column Title</label>
                                <input type="text" id="editorLeftTitle" value="${escapeHtml(d.leftTitle || '')}" class="form-control">
                            </div>
                            <div class="form-group">
                                <label>Left Column Content</label>
                                <textarea id="editorLeftContent" class="form-control" rows="6">${escapeHtml(d.leftContent || '')}</textarea>
                            </div>
                        </div>
                        <div class="column-editor">
                            <div class="form-group">
                                <label>Right Column Title</label>
                                <input type="text" id="editorRightTitle" value="${escapeHtml(d.rightTitle || '')}" class="form-control">
                            </div>
                            <div class="form-group">
                                <label>Right Column Content</label>
                                <textarea id="editorRightContent" class="form-control" rows="6">${escapeHtml(d.rightContent || '')}</textarea>
                            </div>
                        </div>
                    </div>
                `;

            case 'timeline':
                const steps = d.steps || [];
                return `
                    <div class="timeline-editor">
                        <div class="timeline-steps" id="timelineEditorSteps">
                            ${steps.map((step, idx) => `
                                <div class="timeline-step-row" data-index="${idx}">
                                    <div class="step-number">${idx + 1}</div>
                                    <div class="step-fields">
                                        <input type="text" value="${escapeHtml(step.time)}" placeholder="Time" class="form-control time-input" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'time', ARG.value)}>
                                        <input type="text" value="${escapeHtml(step.title)}" placeholder="Title" class="form-control" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'title', ARG.value)}>
                                        <input type="text" value="${escapeHtml(step.description)}" placeholder="Description" class="form-control" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'description', ARG.value)}>
                                    </div>
                                    <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeTimelineStep', idx)}>
                                        <i data-lucide="x"></i>
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                        <button class="btn btn-sm" ${on('click', 'ReportingManager.addTimelineStep')}>+ Add Step</button>
                    </div>
                `;

            case 'riskmatrix':
                const size = d.size || 3;
                const highlighted = d.highlighted || { row: 1, col: 2 };
                return `
                    <div class="form-group">
                        <label>Matrix Size</label>
                        <select id="editorSize" class="form-control" ${on('change', 'ReportingManager.updateRiskMatrixPreview')}>
                            <option value="3" ${size === 3 ? 'selected' : ''}>3×3 (Simple)</option>
                            <option value="5" ${size === 5 ? 'selected' : ''}>5×5 (Detailed)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Click to highlight a cell</label>
                        <div class="risk-matrix-editor" id="riskMatrixEditor">
                            ${this.renderRiskMatrixEditor(size, highlighted)}
                        </div>
                    </div>
                `;

            case 'cvsscard':
                return `
                    <div class="form-row">
                        <div class="form-group">
                            <label>CVSS Score</label>
                            <input type="number" id="editorScore" value="${this._number(d.score, 0, 0, 10)}" min="0" max="10" step="0.1" class="form-control" ${on('change', 'ReportingManager.updateCvssPreview')}>
                        </div>
                        <div class="form-group cvss-severity-display">
                            <label>Severity</label>
                            <span id="cvssSeverityBadge" class="severity-badge severity-${this.getCvssSeverity(this._number(d.score, 0, 0, 10)).toLowerCase()}">${this.getCvssSeverity(this._number(d.score, 0, 0, 10))}</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>CVSS Vector String</label>
                        <input type="text" id="editorVector" value="${escapeHtml(d.vector || '')}" class="form-control code-input" placeholder="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N">
                    </div>
                    <div class="cvss-vector-preview" id="cvssVectorPreview">
                        ${this.renderCvssBreakdown(d.vector || '')}
                    </div>
                `;

            case 'attackmap':
                // Load maps asynchronously and populate dropdown
                setTimeout(async () => {
                    try {
                        const maps = await API.attackMaps.list();
                        const select = document.getElementById('editorMapId');
                        if (select) {
                            select.innerHTML = '<option value="">-- Select a map --</option>' +
                                maps.map(m => `<option value="${m.id}" ${m.id == (d.mapId || '') ? 'selected' : ''}>${escapeHtml(m.name)}</option>`).join('');
                        }
                    } catch(e) {
                        console.error('Failed to load maps for editor:', e);
                    }
                }, 0);
                return `
                    <div class="form-group">
                        <label>Attack Map</label>
                        <select id="editorMapId" class="form-control">
                            <option value="">Loading maps...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <p style="font-size:12px;color:#94a3b8;">The selected map will be embedded as an SVG in the exported report.</p>
                    </div>
                `;

            default:
                return '<p>No editor available for this tool type.</p>';
        }
    },

    /**
     * Save format tool edits
     */
    saveFormatToolEdits() {
        if (!this.editingToolId || !this.editingToolType) return;

        const item = this.workspaceItems.find(i => i.id === this.editingToolId);
        if (!item) return;

        // Gather data based on tool type
        const toolType = this.editingToolType;
        let newData = {};

        switch (toolType) {
            case 'sectionheader':
                newData = {
                    text: document.getElementById('editorText')?.value || '',
                    level: parseInt(document.getElementById('editorLevel')?.value || 2),
                    numbered: document.getElementById('editorNumbered')?.checked || false,
                    number: document.getElementById('editorNumber')?.value || ''
                };
                break;

            case 'textblock':
                newData = { content: document.getElementById('editorContent')?.value || '' };
                break;

            case 'quote':
                newData = {
                    text: document.getElementById('editorText')?.value || '',
                    attribution: document.getElementById('editorAttribution')?.value || ''
                };
                break;

            case 'bulletlist':
            case 'numberedlist':
                newData = { items: this.editingToolData.items || [] };
                break;

            case 'checklist':
                newData = {
                    title: document.getElementById('editorTitle')?.value || '',
                    items: this.editingToolData.items || []
                };
                break;

            case 'codeblock':
                newData = {
                    title: document.getElementById('editorTitle')?.value || '',
                    language: document.getElementById('editorLanguage')?.value || 'bash',
                    code: document.getElementById('editorCode')?.value || ''
                };
                break;

            case 'commandoutput':
                newData = {
                    command: document.getElementById('editorCommand')?.value || '',
                    output: document.getElementById('editorOutput')?.value || ''
                };
                break;

            case 'alertbox':
                newData = {
                    type: document.querySelector('input[name="alertType"]:checked')?.value || 'warning',
                    title: document.getElementById('editorTitle')?.value || '',
                    content: document.getElementById('editorContent')?.value || ''
                };
                break;

            case 'keyfinding':
                newData = {
                    title: document.getElementById('editorTitle')?.value || '',
                    content: document.getElementById('editorContent')?.value || ''
                };
                break;

            case 'evidence':
                newData = {
                    imageCaption: document.getElementById('editorImageCaption')?.value || '',
                    description: document.getElementById('editorDescription')?.value || '',
                    impact: document.getElementById('editorImpact')?.value || ''
                };
                break;

            case 'imageplaceholder':
                newData = {
                    caption: document.getElementById('editorCaption')?.value || '',
                    width: document.getElementById('editorWidth')?.value || '100%'
                };
                break;

            case 'twocolumn':
                newData = {
                    leftTitle: document.getElementById('editorLeftTitle')?.value || '',
                    leftContent: document.getElementById('editorLeftContent')?.value || '',
                    rightTitle: document.getElementById('editorRightTitle')?.value || '',
                    rightContent: document.getElementById('editorRightContent')?.value || ''
                };
                break;

            case 'timeline':
                newData = { steps: this.editingToolData.steps || [] };
                break;

            case 'riskmatrix':
                newData = {
                    size: parseInt(document.getElementById('editorSize')?.value || 3),
                    highlighted: this.editingToolData.highlighted || { row: 1, col: 2 }
                };
                break;

            case 'cvsscard':
                newData = {
                    score: parseFloat(document.getElementById('editorScore')?.value || 0),
                    vector: document.getElementById('editorVector')?.value || ''
                };
                break;

            case 'attackmap': {
                const select = document.getElementById('editorMapId');
                const mapId = select?.value ? parseInt(select.value) : null;
                const mapName = select?.selectedOptions?.[0]?.text || '';
                newData = { mapId, mapName };
                break;
            }
        }

        item.toolData = newData;

        this.editingToolId = null;
        this.editingToolData = null;
        this.editingToolType = null;

        closeModal('formatToolEditorModal');
        this.refreshGenerator();
        showToast('Changes saved', 'success');
    },

    // List editor helpers
    updateListItem(index, value) {
        if (this.editingToolData && this.editingToolData.items) {
            this.editingToolData.items[index] = value;
        }
    },

    addListItem() {
        if (!this.editingToolData) return;
        if (!this.editingToolData.items) this.editingToolData.items = [];
        this.editingToolData.items.push('New item');
        this.refreshListEditor();
    },

    removeListItem(index) {
        if (this.editingToolData && this.editingToolData.items && this.editingToolData.items.length > 1) {
            this.editingToolData.items.splice(index, 1);
            this.refreshListEditor();
        } else {
            showToast('List must have at least one item', 'warning');
        }
    },

    refreshListEditor() {
        const container = document.getElementById('listEditorItems');
        if (!container || !this.editingToolData) return;

        const items = this.editingToolData.items || [];
        container.innerHTML = items.map((item, idx) => `
            <div class="list-item-row" data-index="${idx}">
                <span class="drag-handle">⋮⋮</span>
                <input type="text" value="${escapeHtml(item)}" class="form-control" ${on('change', 'ReportingManager.updateListItem', idx, ARG.value)}>
                <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeListItem', idx)}>
                    <i data-lucide="x"></i>
                </button>
            </div>
        `).join('');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    // Checklist editor helpers
    updateChecklistItem(index, field, value) {
        if (this.editingToolData && this.editingToolData.items && this.editingToolData.items[index]) {
            this.editingToolData.items[index][field] = value;
        }
    },

    addChecklistItem() {
        if (!this.editingToolData) return;
        if (!this.editingToolData.items) this.editingToolData.items = [];
        this.editingToolData.items.push({ text: 'New item', checked: false });
        this.refreshChecklistEditor();
    },

    removeChecklistItem(index) {
        if (this.editingToolData && this.editingToolData.items && this.editingToolData.items.length > 1) {
            this.editingToolData.items.splice(index, 1);
            this.refreshChecklistEditor();
        } else {
            showToast('Checklist must have at least one item', 'warning');
        }
    },

    refreshChecklistEditor() {
        const container = document.getElementById('listEditorItems');
        if (!container || !this.editingToolData) return;

        const items = this.editingToolData.items || [];
        container.innerHTML = items.map((item, idx) => `
            <div class="list-item-row" data-index="${idx}">
                <input type="checkbox" ${item.checked ? 'checked' : ''} ${on('change', 'ReportingManager.updateChecklistItem', idx, 'checked', ARG.checked)}>
                <input type="text" value="${escapeHtml(item.text)}" class="form-control" ${on('change', 'ReportingManager.updateChecklistItem', idx, 'text', ARG.value)}>
                <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeChecklistItem', idx)}>
                    <i data-lucide="x"></i>
                </button>
            </div>
        `).join('');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    // Timeline editor helpers
    updateTimelineStep(index, field, value) {
        if (this.editingToolData && this.editingToolData.steps && this.editingToolData.steps[index]) {
            this.editingToolData.steps[index][field] = value;
        }
    },

    addTimelineStep() {
        if (!this.editingToolData) return;
        if (!this.editingToolData.steps) this.editingToolData.steps = [];
        this.editingToolData.steps.push({ time: '', title: 'New Step', description: '' });
        this.refreshTimelineEditor();
    },

    removeTimelineStep(index) {
        if (this.editingToolData && this.editingToolData.steps && this.editingToolData.steps.length > 1) {
            this.editingToolData.steps.splice(index, 1);
            this.refreshTimelineEditor();
        } else {
            showToast('Timeline must have at least one step', 'warning');
        }
    },

    refreshTimelineEditor() {
        const container = document.getElementById('timelineEditorSteps');
        if (!container || !this.editingToolData) return;

        const steps = this.editingToolData.steps || [];
        container.innerHTML = steps.map((step, idx) => `
            <div class="timeline-step-row" data-index="${idx}">
                <div class="step-number">${idx + 1}</div>
                <div class="step-fields">
                    <input type="text" value="${escapeHtml(step.time)}" placeholder="Time" class="form-control time-input" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'time', ARG.value)}>
                    <input type="text" value="${escapeHtml(step.title)}" placeholder="Title" class="form-control" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'title', ARG.value)}>
                    <input type="text" value="${escapeHtml(step.description)}" placeholder="Description" class="form-control" ${on('change', 'ReportingManager.updateTimelineStep', idx, 'description', ARG.value)}>
                </div>
                <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ReportingManager.removeTimelineStep', idx)}>
                    <i data-lucide="x"></i>
                </button>
            </div>
        `).join('');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    // Alert type preview helper
    updateAlertTypePreview() {
        document.querySelectorAll('.alert-option').forEach(opt => {
            const radio = opt.querySelector('input[type="radio"]');
            opt.classList.toggle('selected', radio?.checked);
        });
    },

    // Risk matrix editor helpers
    renderRiskMatrixEditor(size, highlighted) {
        const labels = size === 3
            ? { rows: ['High', 'Medium', 'Low'], cols: ['Low', 'Medium', 'High'] }
            : { rows: ['Critical', 'High', 'Medium', 'Low', 'Info'], cols: ['Rare', 'Unlikely', 'Possible', 'Likely', 'Certain'] };

        return `
            <table class="risk-matrix-edit size-${size}">
                <thead>
                    <tr>
                        <th></th>
                        ${labels.cols.map(c => `<th>${c}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${labels.rows.map((row, rowIdx) => `
                        <tr>
                            <th>${row}</th>
                            ${labels.cols.map((col, colIdx) => {
                                const isHighlighted = highlighted.row === rowIdx && highlighted.col === colIdx;
                                const risk = this.getRiskLevel(rowIdx, colIdx, size);
                                return `<td class="risk-${risk} ${isHighlighted ? 'highlighted' : ''}" ${on('click', 'ReportingManager.selectRiskCell', rowIdx, colIdx)}></td>`;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    selectRiskCell(row, col) {
        if (this.editingToolData) {
            this.editingToolData.highlighted = { row, col };
            const size = parseInt(document.getElementById('editorSize')?.value || 3);
            document.getElementById('riskMatrixEditor').innerHTML = this.renderRiskMatrixEditor(size, { row, col });
        }
    },

    updateRiskMatrixPreview() {
        const size = parseInt(document.getElementById('editorSize')?.value || 3);
        const highlighted = this.editingToolData?.highlighted || { row: 0, col: 0 };
        // Adjust highlighted cell if it's out of bounds for new size
        if (highlighted.row >= size) highlighted.row = size - 1;
        if (highlighted.col >= size) highlighted.col = size - 1;
        if (this.editingToolData) this.editingToolData.highlighted = highlighted;
        document.getElementById('riskMatrixEditor').innerHTML = this.renderRiskMatrixEditor(size, highlighted);
    },

    // CVSS helpers
    updateCvssPreview() {
        const score = parseFloat(document.getElementById('editorScore')?.value || 0);
        const severity = this.getCvssSeverity(score);
        const badge = document.getElementById('cvssSeverityBadge');
        if (badge) {
            badge.textContent = severity;
            badge.className = `severity-badge severity-${severity.toLowerCase()}`;
        }
    },

    // ============================================
    // UTILITY METHODS
    // ============================================

    /**
     * Get risk level for matrix cell
     */
    getRiskLevel(rowIdx, colIdx, size) {
        if (size === 3) {
            const matrix = [
                ['high', 'critical', 'critical'],
                ['medium', 'high', 'critical'],
                ['low', 'medium', 'high']
            ];
            return matrix[rowIdx]?.[colIdx] || 'low';
        } else {
            const matrix = [
                ['medium', 'high', 'critical', 'critical', 'critical'],
                ['low', 'medium', 'high', 'critical', 'critical'],
                ['low', 'low', 'medium', 'high', 'critical'],
                ['info', 'low', 'low', 'medium', 'high'],
                ['info', 'info', 'low', 'low', 'medium']
            ];
            return matrix[rowIdx]?.[colIdx] || 'info';
        }
    },

    /**
     * Get CVSS severity label
     */
    getCvssSeverity(score) {
        if (score === 0) return 'None';
        if (score < 4) return 'Low';
        if (score < 7) return 'Medium';
        if (score < 9) return 'High';
        return 'Critical';
    },

    /**
     * Render CVSS breakdown from vector string
     */
    renderCvssBreakdown(vector) {
        if (!vector || !vector.startsWith('CVSS:')) return '';

        const parts = vector.split('/').slice(1);
        const labels = {
            'AV': { name: 'Attack Vector', values: { 'N': 'Network', 'A': 'Adjacent', 'L': 'Local', 'P': 'Physical' } },
            'AC': { name: 'Attack Complexity', values: { 'L': 'Low', 'H': 'High' } },
            'PR': { name: 'Privileges Required', values: { 'N': 'None', 'L': 'Low', 'H': 'High' } },
            'UI': { name: 'User Interaction', values: { 'N': 'None', 'R': 'Required' } },
            'S': { name: 'Scope', values: { 'U': 'Unchanged', 'C': 'Changed' } },
            'C': { name: 'Confidentiality', values: { 'N': 'None', 'L': 'Low', 'H': 'High' } },
            'I': { name: 'Integrity', values: { 'N': 'None', 'L': 'Low', 'H': 'High' } },
            'A': { name: 'Availability', values: { 'N': 'None', 'L': 'Low', 'H': 'High' } }
        };

        // The vector is stored text: look metrics up as own properties only
        // (not "constructor" or "__proto__"), and escape what is shown (H-16).
        const breakdown = parts.map(part => {
            const [key, val] = part.split(':');
            if (!Object.hasOwn(labels, key)) return null;
            const label = labels[key];
            const valueName = Object.hasOwn(label.values, val) ? label.values[val] : val;
            return `<span class="cvss-metric"><span class="metric-name">${escapeHtml(label.name)}:</span> <span class="metric-value">${escapeHtml(valueName)}</span></span>`;
        }).filter(Boolean).join('');

        return `<div class="cvss-breakdown">${breakdown}</div>`;
    },

    /**
     * Structural report values become tag names, class names and numbers in
     * markup, where escaping is not enough: accept only known values (H-10).
     */
    _headingTag(value, fallback = 'h3') {
        const tag = String(value || '').trim().toLowerCase();
        return ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag) ? tag : fallback;
    },

    _criticality(value) {
        const level = String(value || '').trim().toLowerCase();
        return ['critical', 'high', 'medium', 'low', 'info', 'informational'].includes(level) ? level : 'medium';
    },

    _number(value, fallback, low, high) {
        const n = Number(value);
        return Number.isFinite(n) && n >= low && n <= high && String(value).trim() !== '' ? n : fallback;
    },

    /**
     * Generate UUID
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    // ============================================
    // TEMPLATES (Q3 FEATURE)
    // ============================================

    /**
     * Load templates from API
     */
    async loadTemplates() {
        try {
            const data = await API.reporting.getTemplates();
            this.templates = data.templates || [];
        } catch (error) {
            console.error('Failed to load templates:', error);
            this.templates = [];
            showToast('Failed to load templates', 'error');
        }
    },

    /**
     * Render templates content
     */
    renderTemplatesContent() {
        const filtered = this.filterTemplates();

        return `
            <div class="templates-page">
                <div class="templates-header">
                    <h3>Report Templates</h3>
                    <div class="templates-header-actions">
                        <select id="templateCategoryFilter" ${on('change', 'ReportingManager.applyTemplateFilters')} class="form-control">
                            <option value="all">All Categories</option>
                            <option value="executive">Executive</option>
                            <option value="technical">Technical</option>
                            <option value="compliance">Compliance</option>
                            <option value="custom">Custom</option>
                        </select>
                        <button class="btn btn-primary" ${on('click', 'ReportingManager.showNewTemplateModal')}>
                            <i data-lucide="plus"></i>
                            Create Template
                        </button>
                    </div>
                </div>

                <div class="templates-grid">
                    ${filtered.length === 0 ? '<div class="empty-state"><p>No templates found</p></div>' : filtered.map(template => this.renderTemplateCard(template)).join('')}
                </div>
            </div>
        `;
    },

    /**
     * Render single template card
     */
    renderTemplateCard(template) {
        return `
            <div class="template-card" data-template-id="${template.id}">
                <div class="template-header">
                    <h4>${escapeHtml(template.name)}</h4>
                    <span class="badge badge-${template.category}">${template.category}</span>
                </div>
                <p class="template-description">${escapeHtml(template.description || 'No description')}</p>
                <div class="template-meta">
                    <span class="text-muted">
                        <i data-lucide="clock"></i>
                        ${new Date(template.created_at).toLocaleDateString()}
                    </span>
                    ${template.is_default ? '<span class="badge badge-info">Default</span>' : ''}
                </div>
                <div class="template-actions">
                    <button class="btn btn-sm btn-secondary" ${on('click', 'ReportingManager.previewTemplate', template.id)}>
                        <i data-lucide="eye"></i> Preview
                    </button>
                    <button class="btn btn-sm btn-primary" ${on('click', 'ReportingManager.useTemplate', template.id)}>
                        <i data-lucide="file-plus"></i> Use Template
                    </button>
                    ${!template.is_default ? `
                        <button class="btn btn-sm btn-icon" ${on('click', 'ReportingManager.editTemplate', template.id)} title="Edit">
                            <i data-lucide="edit"></i>
                        </button>
                        <button class="btn btn-sm btn-icon text-danger" ${on('click', 'ReportingManager.deleteTemplate', template.id)} title="Delete">
                            <i data-lucide="trash-2"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    },

    /**
     * Filter templates by category
     */
    filterTemplates() {
        if (this.templateFilters.category === 'all') {
            return this.templates;
        }
        return this.templates.filter(t => t.category === this.templateFilters.category);
    },

    /**
     * Apply template filters
     */
    applyTemplateFilters() {
        const categoryFilter = document.getElementById('templateCategoryFilter');
        if (categoryFilter) {
            this.templateFilters.category = categoryFilter.value;
        }

        // Re-render
        const content = document.getElementById('reportingContent');
        if (content) {
            content.innerHTML = this.renderTemplatesContent();
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },

    /**
     * Use template to create a new report
     */
    async useTemplate(templateId) {
        try {
            if (!AppState.activeEngagement) {
                showToast('Please select an engagement first', 'error');
                return;
            }
            showToast('Applying template...', 'info');
            const data = await API.reporting.applyTemplate(templateId, AppState.activeEngagement.id);
            showToast('Report created from template', 'success');

            // Switch to generation tab and reload saved reports list
            await this.switchTab('generation');
            await this.initReportGenerator();
            if (data.report_id) {
                await this.loadReport(data.report_id);
            }
        } catch (error) {
            console.error('Failed to apply template:', error);
            showToast('Failed to apply template: ' + error.message, 'error');
        }
    },

    /**
     * Preview template content
     */
    async previewTemplate(templateId) {
        try {
            if (!AppState.activeEngagement) {
                showToast('Please select an engagement first', 'error');
                return;
            }
            const preview = await API.reporting.previewTemplate(templateId, AppState.activeEngagement.id);
            this.showTemplatePreviewModal(preview);
        } catch (error) {
            console.error('Failed to preview template:', error);
            showToast('Failed to preview template: ' + error.message, 'error');
        }
    },

    /**
     * Show template preview modal
     */
    showTemplatePreviewModal(preview) {
        const templateInfo = preview.template || {};
        const sections = preview.sections || [];

        // Render sections into HTML, converting markdown content
        const sectionsHtml = sections.length > 0
            ? sections.map(s => {
                const renderedContent = s.content ? this.renderMarkdown(s.content) : '<em>No content</em>';
                return `
                    <div class="template-preview-section">
                        ${s.title ? `<h3>${escapeHtml(s.title)}</h3>` : ''}
                        <div class="template-preview-section-content">${renderedContent}</div>
                    </div>
                `;
            }).join('<hr style="margin: 1rem 0; border-color: var(--color-border);">')
            : '<p>No sections in this template</p>';

        // Remove any existing preview modal first
        const existing = document.getElementById('templatePreviewModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'templatePreviewModal';
        modal.style.display = 'flex';

        const dismissModal = () => modal.remove();

        modal.innerHTML = `
            <div class="modal-content modal-lg">
                <div class="modal-header">
                    <h3>Template Preview: ${escapeHtml(templateInfo.name || 'Untitled')}</h3>
                    <button class="btn btn-icon" id="templatePreviewClose">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                    ${templateInfo.description ? `<p style="color: var(--color-text-secondary); margin-bottom: 1rem;">${escapeHtml(templateInfo.description)}</p>` : ''}
                    <div class="template-preview-content">
                        ${sectionsHtml}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn" id="templatePreviewCancel">Close</button>
                    <button class="btn btn-primary" id="templatePreviewUse">
                        Use This Template
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Bind close/dismiss handlers
        modal.querySelector('#templatePreviewClose').addEventListener('click', dismissModal);
        modal.querySelector('#templatePreviewCancel').addEventListener('click', dismissModal);
        modal.querySelector('#templatePreviewUse').addEventListener('click', () => {
            dismissModal();
            ReportingManager.useTemplate(templateInfo.id);
        });
        // Click on backdrop to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) dismissModal();
        });

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Show new template modal
     */
    showNewTemplateModal() {
        showToast('Template creation UI coming soon', 'info');
    },

    /**
     * Edit existing template
     */
    editTemplate(templateId) {
        showToast('Template editing UI coming soon', 'info');
    },

    /**
     * Delete template
     */
    async deleteTemplate(templateId) {
        if (!confirm('Are you sure you want to delete this template? This action cannot be undone.')) {
            return;
        }

        try {
            await API.reporting.deleteTemplate(templateId);
            showToast('Template deleted successfully', 'success');
            await this.loadTemplates();

            // Re-render
            const content = document.getElementById('reportingContent');
            if (content) {
                content.innerHTML = this.renderTemplatesContent();
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }
        } catch (error) {
            console.error('Failed to delete template:', error);
            showToast('Failed to delete template: ' + error.message, 'error');
        }
    },

    // ============================================
    // ENGAGEMENT COMPARISON (Q3 FEATURE)
    // ============================================

    /**
     * Show comparison modal
     */
    async showComparisonModal() {
        try {
            // Load all engagements
            const engagements = await API.engagements.list();

            // Render checkboxes
            const container = document.getElementById('engagementCheckboxes');
            if (!container) return;

            container.innerHTML = engagements.map(eng => `
                <label class="checkbox-label">
                    <input type="checkbox" class="comparison-engagement" value="${eng.id}">
                    <span>${escapeHtml(eng.name)} (${escapeHtml(eng.client || 'No Client')})</span>
                </label>
            `).join('');

            // Show modal
            const modal = document.getElementById('comparisonModal');
            if (modal) {
                modal.style.display = 'flex';
            }

            // Hide results initially
            const results = document.getElementById('comparisonResults');
            if (results) {
                results.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to load engagements for comparison:', error);
            showToast('Failed to load engagements', 'error');
        }
    },

    /**
     * Run comparison
     */
    async runComparison() {
        const checkboxes = document.querySelectorAll('.comparison-engagement:checked');
        const engagementIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

        if (engagementIds.length < 2) {
            showToast('Please select at least 2 engagements', 'warning');
            return;
        }

        if (engagementIds.length > 10) {
            showToast('Please select no more than 10 engagements', 'warning');
            return;
        }

        try {
            showToast('Running comparison...', 'info');
            const data = await API.reporting.compareEngagements(engagementIds);

            // Display results
            this.displayComparisonResults(data);

            showToast('Comparison completed', 'success');
        } catch (error) {
            console.error('Comparison failed:', error);
            showToast('Comparison failed: ' + error.message, 'error');
        }
    },

    /**
     * Display comparison results
     */
    displayComparisonResults(data) {
        const results = document.getElementById('comparisonResults');
        if (!results) return;

        results.style.display = 'block';

        // Update summary metrics
        const avgFindings = document.getElementById('avgFindings');
        const avgHosts = document.getElementById('avgHosts');
        const totalCritical = document.getElementById('totalCritical');
        const engagementCount = document.getElementById('engagementCount');

        if (avgFindings) avgFindings.textContent = data.statistics?.avg_findings?.toFixed(1) || '0';
        if (avgHosts) avgHosts.textContent = data.statistics?.avg_hosts?.toFixed(1) || '0';
        if (totalCritical) totalCritical.textContent = data.statistics?.total_critical || '0';
        if (engagementCount) engagementCount.textContent = data.statistics?.engagement_count || '0';

        // Populate table
        const tbody = document.getElementById('comparisonTableBody');
        if (!tbody) return;

        tbody.innerHTML = data.engagements.map(eng => `
            <tr>
                <td><strong>${escapeHtml(eng.name)}</strong></td>
                <td>${escapeHtml(eng.client || '-')}</td>
                <td>${eng.statistics?.host_count || 0}</td>
                <td>${eng.statistics?.finding_count || 0}</td>
                <td><span class="badge badge-critical">${eng.statistics?.critical_count || 0}</span></td>
                <td><span class="badge badge-high">${eng.statistics?.high_count || 0}</span></td>
                <td><span class="badge badge-medium">${eng.statistics?.medium_count || 0}</span></td>
                <td><span class="badge badge-low">${eng.statistics?.low_count || 0}</span></td>
            </tr>
        `).join('');
    }
};

// Make ReportingManager available globally
window.ReportingManager = ReportingManager;
