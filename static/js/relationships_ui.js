/**
 * Evidence Relationships UI Manager
 * Handles the UI for adding, managing, and visualizing evidence relationships
 */
const RelationshipsUI = {
    currentEvidenceItems: [],
    pathSelectionMode: null,

    /**
     * Initialize relationships UI
     */
    async init() {
        console.log('[RelationshipsUI] Initializing...');
        await this.loadEvidenceItems();
        console.log('[RelationshipsUI] Loaded', this.currentEvidenceItems.length, 'evidence items');
        this.setupEventListeners();
        console.log('[RelationshipsUI] Setup complete');
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Add relationship button
        const addRelBtn = document.getElementById('addRelationshipBtn');
        if (addRelBtn) {
            addRelBtn.addEventListener('click', () => this.showAddRelationshipModal());
        }

        // Find path button
        const findPathBtn = document.getElementById('findPathBtn');
        if (findPathBtn) {
            findPathBtn.addEventListener('click', () => this.startPathSelection());
        }

        // Relationship form submit
        const relForm = document.getElementById('relationshipForm');
        if (relForm) {
            relForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveRelationship();
            });
        }

        // Relationship type change
        const typeSelect = document.getElementById('relationshipType');
        if (typeSelect) {
            typeSelect.addEventListener('change', (e) => {
                this.toggleCustomTypeInput(e.target.value);
            });
        }

        // Export graph button
        const exportBtn = document.getElementById('exportGraphBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => RelationshipGraph.exportGraph());
        }
    },

    /**
     * Load evidence items and findings for dropdowns
     */
    async loadEvidenceItems() {
        try {
            // Get all nodes (evidence + findings) from the graph endpoint
            const graphData = await API.relationships.getGraph();
            this.currentEvidenceItems = graphData.nodes || [];
            console.log('[RelationshipsUI] Loaded', this.currentEvidenceItems.length, 'items:', {
                evidence: this.currentEvidenceItems.filter(n => n.node_type === 'evidence').length,
                findings: this.currentEvidenceItems.filter(n => n.node_type === 'finding').length
            });
        } catch (error) {
            console.error('Failed to load evidence items:', error);
            showToast('Failed to load evidence items', 'error');
            this.currentEvidenceItems = [];
        }
    },

    /**
     * Initialize the graph visualization
     */
    async initGraph() {
        console.log('[RelationshipsUI] Initializing graph...');
        const container = document.getElementById('relationshipGraphContainer');
        if (!container) {
            console.error('[RelationshipsUI] Graph container not found');
            return;
        }

        console.log('[RelationshipsUI] Container found:', container);

        // Check if d3 is loaded
        if (typeof d3 === 'undefined') {
            console.error('[RelationshipsUI] D3.js not loaded');
            showToast('d3.js library is required for graph visualization', 'error');
            return;
        }

        console.log('[RelationshipsUI] D3.js version:', d3.version);

        // Always reload evidence items and graph data to get latest
        await this.loadEvidenceItems();

        console.log('[RelationshipsUI] Calling RelationshipGraph.init...');
        await RelationshipGraph.init('relationshipGraphContainer');
        console.log('[RelationshipsUI] Graph initialized');
    },

    /**
     * Refresh graph data (call this when evidence is added/deleted)
     */
    async refreshGraph() {
        console.log('[RelationshipsUI] Refreshing graph...');
        await this.loadEvidenceItems();
        if (typeof RelationshipGraph !== 'undefined' && RelationshipGraph.svg) {
            await RelationshipGraph.loadGraph();
        }
    },

    /**
     * Show add relationship modal
     */
    showAddRelationshipModal() {
        // Populate dropdowns - ALL node types (evidence, findings, notes, credentials)
        const sourceSelect = document.getElementById('relationshipSource');
        const targetSelect = document.getElementById('relationshipTarget');

        if (this.currentEvidenceItems.length < 2) {
            showToast('Need at least 2 items to create a relationship', 'info');
            return;
        }

        // Group items by type for better organization
        const nodeTypeLabels = {
            'evidence': 'Evidence',
            'finding': 'Finding',
            'note': 'Note',
            'credential': 'Credential'
        };

        const optionsHtml = this.currentEvidenceItems.map(item => {
            const typeLabel = nodeTypeLabels[item.node_type] || item.node_type;
            const uniqueId = item.unique_id || `${item.node_type}_${item.id}`;
            return `<option value="${uniqueId}" data-node-type="${item.node_type}" data-node-id="${item.id}">${escapeHtml(item.title)} [${typeLabel}]</option>`;
        }).join('');

        sourceSelect.innerHTML = optionsHtml;
        targetSelect.innerHTML = optionsHtml;

        // Reset form
        document.getElementById('relationshipType').value = 'leads_to';
        document.getElementById('relationshipLabel').value = '';
        document.getElementById('relationshipDescription').value = '';
        this.toggleCustomTypeInput('leads_to');

        openModal('relationshipModal');
    },

    /**
     * Toggle custom type input
     */
    toggleCustomTypeInput(type) {
        const customInput = document.getElementById('customTypeGroup');
        if (customInput) {
            customInput.style.display = type === 'custom' ? 'block' : 'none';
        }
    },

    /**
     * Save relationship
     */
    async saveRelationship() {
        const sourceSelect = document.getElementById('relationshipSource');
        const targetSelect = document.getElementById('relationshipTarget');

        const sourceOption = sourceSelect.options[sourceSelect.selectedIndex];
        const targetOption = targetSelect.options[targetSelect.selectedIndex];

        const sourceNodeType = sourceOption.getAttribute('data-node-type');
        const sourceNodeId = parseInt(sourceOption.getAttribute('data-node-id'));
        const targetNodeType = targetOption.getAttribute('data-node-type');
        const targetNodeId = parseInt(targetOption.getAttribute('data-node-id'));

        let type = document.getElementById('relationshipType').value;
        let label = document.getElementById('relationshipLabel').value.trim();
        const description = document.getElementById('relationshipDescription').value.trim();

        // Validation
        if (!sourceNodeType || !sourceNodeId || !targetNodeType || !targetNodeId) {
            showToast('Source and target are required', 'error');
            return;
        }

        // Check if same node
        if (sourceNodeType === targetNodeType && sourceNodeId === targetNodeId) {
            showToast('Source and target must be different', 'error');
            return;
        }

        // Handle custom type
        if (type === 'custom') {
            const customType = document.getElementById('customTypeName').value.trim();
            if (!customType) {
                showToast('Custom type name is required', 'error');
                return;
            }
            type = customType;
        }

        // Use custom label if provided, otherwise use default
        if (!label) {
            label = this.getDefaultLabel(type);
        }

        try {
            await RelationshipGraph.addRelationship(
                sourceNodeType, sourceNodeId,
                targetNodeType, targetNodeId,
                type, label, description
            );
            closeModal('relationshipModal');
        } catch (error) {
            console.error('Failed to save relationship:', error);
            showToast(error.message || 'Failed to create relationship', 'error');
        }
    },

    /**
     * Get default label for relationship type
     */
    getDefaultLabel(type) {
        const labels = {
            'leads_to': 'Leads To',
            'uses': 'Uses',
            'discovers': 'Discovers',
            'exploits': 'Exploits',
            'escalates': 'Escalates',
            'custom': 'Related'
        };
        return labels[type] || type;
    },

    /**
     * Start path selection mode
     */
    startPathSelection() {
        if (this.currentEvidenceItems.length < 2) {
            showToast('Need at least 2 evidence items to build a path', 'info');
            return;
        }

        // Reset path selection - now using an array for multi-node paths
        RelationshipGraph.attackPath = [];
        RelationshipGraph.pathSelectionMode = 'building';

        // Show status panel
        this.showPathSelectionStatus('building');

        // Update button state
        const btn = document.getElementById('findPathBtn');
        btn.disabled = true;
        btn.style.opacity = '0.5';
    },

    /**
     * Show path selection status panel
     */
    showPathSelectionStatus(step) {
        const panel = document.getElementById('pathSelectionStatus');
        const stepNumber = document.getElementById('pathStepNumber');
        const stepTitle = document.getElementById('pathStepTitle');
        const stepInstructions = document.getElementById('pathStepInstructions');
        const progressBar = document.getElementById('pathProgressBar');
        const progressText = document.getElementById('pathProgressText');

        if (step === 'building') {
            const pathLength = RelationshipGraph.attackPath ? RelationshipGraph.attackPath.length : 0;
            panel.style.display = 'block';
            stepNumber.textContent = pathLength + 1;

            if (pathLength === 0) {
                stepTitle.textContent = 'Build Attack Path';
                stepInstructions.textContent = 'Click nodes in sequence to build your attack path. Click "Finish Path" when done (minimum 2 nodes).';
            } else {
                stepTitle.textContent = `Step ${pathLength + 1}`;
                stepInstructions.textContent = `${pathLength} node${pathLength > 1 ? 's' : ''} selected. Click next node to continue, or "Finish Path" to complete (minimum 2 nodes).`;
            }

            progressBar.style.width = '33%';
            progressText.textContent = `${pathLength} nodes selected`;
        }
    },

    /**
     * Hide path selection status panel
     */
    hidePathSelectionStatus() {
        const panel = document.getElementById('pathSelectionStatus');
        panel.style.display = 'none';

        // Re-enable button
        const btn = document.getElementById('findPathBtn');
        btn.disabled = false;
        btn.style.opacity = '1';
    },

    /**
     * Cancel path selection
     */
    cancelPathSelection() {
        RelationshipGraph.attackPath = [];
        RelationshipGraph.pathSelectionMode = null;
        RelationshipGraph.clearPathHighlights();
        this.hidePathSelectionStatus();
        showToast('Path building cancelled', 'info');
    },

    /**
     * Handle node selection during path building
     */
    onNodeSelected(nodeId, nodeTitle) {
        if (RelationshipGraph.pathSelectionMode === 'building') {
            // Check if node already in path
            if (RelationshipGraph.attackPath.some(node => node.id === nodeId)) {
                showToast('Node already in path', 'warning');
                return;
            }

            // Find the full node data
            const nodeData = RelationshipGraph.nodes.find(n => (n.unique_id || n.id) === nodeId);
            if (!nodeData) {
                showToast('Node not found', 'error');
                return;
            }

            // Add to path
            RelationshipGraph.attackPath.push({
                id: nodeId,
                title: nodeTitle,
                node: nodeData
            });

            const stepNum = RelationshipGraph.attackPath.length;
            showToast(`Step ${stepNum}: ${nodeTitle}`, 'success');

            // Highlight the node with step number
            RelationshipGraph.highlightPathNode(nodeId, stepNum);

            // Update status panel
            this.showPathSelectionStatus('building');
        }
    },

    /**
     * Finish building the attack path
     */
    finishPath() {
        const pathLength = RelationshipGraph.attackPath ? RelationshipGraph.attackPath.length : 0;

        if (pathLength < 2) {
            showToast('Need at least 2 nodes to create an attack path', 'warning');
            return;
        }

        // Hide status panel
        this.hidePathSelectionStatus();

        // Show the completed path
        RelationshipGraph.showCompletedPath();

        // Reset mode
        RelationshipGraph.pathSelectionMode = null;

        showToast(`Attack path with ${pathLength} steps created successfully!`, 'success');
    },

    /**
     * Show relationship list view (alternative to graph)
     */
    async showRelationshipList() {
        try {
            const relationships = await API.relationships.getAll();
            const container = document.getElementById('relationshipsList');

            if (!container) return;

            if (relationships.length === 0) {
                container.innerHTML = '<p class="empty-text">No relationships created yet</p>';
                return;
            }

            const html = `
                <div class="relationships-list">
                    ${relationships.map(rel => `
                        <div class="relationship-card">
                            <div class="relationship-header">
                                <span class="relationship-type-badge badge badge-primary">
                                    ${escapeHtml(rel.label || rel.relationship_type)}
                                </span>
                                <button class="btn btn-icon btn-sm btn-danger"
                                        ${on('click', 'RelationshipGraph.deleteRelationship', rel.id)}
                                        title="Delete">
                                    <i data-lucide="trash-2" class="icon-sm"></i>
                                </button>
                            </div>
                            <div class="relationship-body">
                                <div class="relationship-flow">
                                    <div class="flow-item">
                                        <span class="flow-label">From:</span>
                                        <span class="flow-value">${escapeHtml(rel.source_title)}</span>
                                    </div>
                                    <i data-lucide="arrow-right" class="flow-arrow"></i>
                                    <div class="flow-item">
                                        <span class="flow-label">To:</span>
                                        <span class="flow-value">${escapeHtml(rel.target_title)}</span>
                                    </div>
                                </div>
                                ${rel.description ? `
                                    <div class="relationship-description">
                                        ${escapeHtml(rel.description)}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;

            container.innerHTML = html;

            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        } catch (error) {
            console.error('Failed to load relationships:', error);
            showToast('Failed to load relationships', 'error');
        }
    }
};

// Make available globally
window.RelationshipsUI = RelationshipsUI;
