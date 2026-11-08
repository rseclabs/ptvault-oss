/**
 * Evidence Relationship Graph Visualization
 *
 * Uses d3.js for force-directed graph layout showing relationships between
 * evidence items. Supports drag-and-drop, zoom, and path finding.
 */

const RelationshipGraph = {
    svg: null,
    simulation: null,
    nodes: [],
    edges: [],
    container: null,
    width: 0,
    height: 600,
    selectedNode: null,
    attackPath: [],  // Array of nodes in the attack path
    pathSelectionMode: null,  // 'building' when user is selecting nodes

    /**
     * Initialize the graph visualization
     * @param {string} containerId - DOM element ID for the graph container
     */
    async init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Graph container not found:', containerId);
            return;
        }

        // Check if d3 is loaded
        if (typeof d3 === 'undefined') {
            console.error('d3.js not loaded');
            showToast('d3.js library is required for graph visualization', 'error');
            return;
        }

        this.width = this.container.clientWidth;

        // Create SVG
        this.svg = d3.select(`#${containerId}`)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height)
            .attr('class', 'relationship-graph');

        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.svg.select('.graph-container').attr('transform', event.transform);
            });

        this.svg.call(zoom);

        // Create main container group
        this.svg.append('g').attr('class', 'graph-container');

        // Create arrow marker for directed edges
        this.svg.select('.graph-container')
            .append('defs')
            .append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('orient', 'auto')
            .attr('markerWidth', 8)
            .attr('markerHeight', 8)
            .append('svg:path')
            .attr('d', 'M 0,-5 L 10,0 L 0,5')
            .attr('fill', '#999');

        // Create layers
        this.svg.select('.graph-container').append('g').attr('class', 'edges-layer');
        this.svg.select('.graph-container').append('g').attr('class', 'nodes-layer');

        // Load data
        await this.loadGraph();

        // Setup event listeners
        this.setupEventListeners();
    },

    /**
     * Load graph data from API
     */
    async loadGraph() {
        try {
            const data = await API.relationships.getGraph();
            this.nodes = data.nodes || [];

            // Transform edges to use 'source' and 'target' with unique_id format
            // D3.js requires these specific property names and they must match node IDs
            this.edges = (data.edges || []).map(edge => ({
                ...edge,
                source: `${edge.source_node_type}_${edge.source_node_id}`,
                target: `${edge.target_node_type}_${edge.target_node_id}`
            }));

            console.log(`Loaded graph: ${this.nodes.length} nodes, ${this.edges.length} edges`);

            if (this.nodes.length === 0) {
                this.showEmptyState();
                return;
            }

            this.render();
        } catch (error) {
            console.error('Failed to load graph:', error);
            showToast('Failed to load relationship graph', 'error');
        }
    },

    /**
     * Render the graph
     */
    render() {
        if (!this.svg || this.nodes.length === 0) return;

        // Create force simulation
        this.simulation = d3.forceSimulation(this.nodes)
            .force('link', d3.forceLink(this.edges)
                .id(d => d.unique_id || d.id)
                .distance(150))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(40));

        // Render edges
        const link = this.svg.select('.edges-layer')
            .selectAll('line.relationship-edge')
            .data(this.edges)
            .join('line')
            .attr('class', 'relationship-edge')
            .attr('stroke', '#94a3b8')
            .attr('stroke-width', 2)
            .attr('marker-end', 'url(#arrowhead)')
            .attr('data-type', d => d.relationship_type);

        // Add edge labels
        const edgeLabels = this.svg.select('.edges-layer')
            .selectAll('text.edge-label')
            .data(this.edges)
            .join('text')
            .attr('class', 'edge-label')
            .attr('font-size', '10px')
            .attr('fill', '#64748b')
            .text(d => d.label || this.formatRelationType(d.relationship_type));

        // Render nodes
        const nodeGroup = this.svg.select('.nodes-layer')
            .selectAll('g.node')
            .data(this.nodes)
            .join('g')
            .attr('class', 'node')
            .attr('data-node-id', d => d.id)
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)))
            .on('click', (event, d) => this.nodeClicked(event, d));

        // Add circles for nodes
        nodeGroup.append('circle')
            .attr('r', 20)
            .attr('fill', d => this.getNodeColor(d))
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        // Add node labels
        nodeGroup.append('text')
            .text(d => this.truncateText(d.title, 20))
            .attr('x', 25)
            .attr('y', 5)
            .attr('font-size', '12px')
            .attr('fill', '#1e293b');

        // Update positions on simulation tick
        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            edgeLabels
                .attr('x', d => (d.source.x + d.target.x) / 2)
                .attr('y', d => (d.source.y + d.target.y) / 2);

            nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
        });
    },

    /**
     * Get color for node based on type
     */
    getNodeColor(node) {
        // If it's a finding node, use criticality colors
        if (node.node_type === 'finding') {
            // Severity scale: critical purple, high red, medium orange, low yellow
            // (the --sev-* tokens in tokens.css; hex fallbacks match the report table).
            const css = getComputedStyle(document.documentElement);
            const token = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
            const criticalityColors = {
                'critical': token('--sev-critical', '#9333ea'),
                'high': token('--sev-high', '#ef4444'),
                'medium': token('--sev-medium', '#f97316'),
                'low': token('--sev-low', '#eab308'),
                'info': token('--color-cool', '#3b82f6')
            };
            return criticalityColors[node.type] || criticalityColors['medium'];
        }

        // If it's a note node
        if (node.node_type === 'note') {
            return '#8b5cf6';  // purple-500
        }

        // If it's a credential node
        if (node.node_type === 'credential') {
            return '#ec4899';  // pink-500
        }

        // Otherwise use evidence type colors
        const evidenceColors = {
            'note': '#3b82f6',
            'screenshot': '#10b981',
            'command_output': '#f59e0b',
            'tool_output': '#ef4444',
            'other': '#6b7280'
        };
        return evidenceColors[node.type] || evidenceColors['other'];
    },

    /**
     * Format relationship type for display
     */
    formatRelationType(type) {
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
     * Truncate text to max length
     */
    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    },

    /**
     * Show empty state message
     */
    showEmptyState() {
        this.svg.select('.graph-container')
            .append('text')
            .attr('x', this.width / 2)
            .attr('y', this.height / 2)
            .attr('text-anchor', 'middle')
            .attr('font-size', '18px')
            .attr('fill', '#94a3b8')
            .text('No evidence items or relationships to display');
    },

    /**
     * Drag event handlers
     */
    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    },

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    },

    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    },

    /**
     * Node click handler
     */
    nodeClicked(event, d) {
        event.stopPropagation();

        // If in path building mode, delegate to RelationshipsUI
        if (this.pathSelectionMode === 'building') {
            const nodeId = d.unique_id || d.id;

            // Notify the UI manager
            if (window.RelationshipsUI && typeof RelationshipsUI.onNodeSelected === 'function') {
                RelationshipsUI.onNodeSelected(nodeId, d.title);
            }
            return;
        }

        // Normal click - show node details
        this.showNodeDetails(d);
    },

    /**
     * Highlight a node
     */
    highlightNode(nodeId, color) {
        this.svg.selectAll('.node circle')
            .attr('stroke', d => (d.unique_id || d.id) === nodeId ? color : '#fff')
            .attr('stroke-width', d => (d.unique_id || d.id) === nodeId ? 4 : 2);
    },

    /**
     * Show node details
     */
    showNodeDetails(node) {
        // Update details panel if it exists
        const detailsPanel = document.getElementById('nodeDetails');
        if (!detailsPanel) return;

        detailsPanel.innerHTML = `
            <h4 class="text-lg font-semibold mb-2">${escapeHtml(node.title)}</h4>
            <p class="text-sm text-gray-600 mb-2">Type: ${node.evidence_type}</p>
            ${node.tags ? `<p class="text-sm mb-2">Tags: ${escapeHtml(node.tags)}</p>` : ''}
            <button class="btn btn-sm btn-primary" ${on('click', 'RelationshipGraph.showRelationshipsFor', node.id)}>
                View Relationships
            </button>
        `;
    },

    /**
     * Show relationships for a specific node
     */
    async showRelationshipsFor(nodeId) {
        try {
            const data = await API.relationships.getForEvidence(nodeId);
            console.log('Relationships for evidence', nodeId, data);

            // Update UI with relationship list
            const listContainer = document.getElementById('relationshipsList');
            if (!listContainer) return;

            if (data.relationships.length === 0) {
                listContainer.innerHTML = '<p class="text-gray-500">No relationships</p>';
                return;
            }

            listContainer.innerHTML = data.relationships.map(rel => `
                <div class="relationship-item p-2 border-b">
                    <div class="flex justify-between">
                        <span class="font-medium">${this.formatRelationType(rel.relationship_type)}</span>
                        <button class="text-red-600 hover:text-red-800"
                                ${on('click', 'RelationshipGraph.deleteRelationship', rel.id)}>
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                    <p class="text-sm text-gray-600">
                        ${rel.source_evidence_id === nodeId ? 'To:' : 'From:'}
                        ${escapeHtml(rel.source_evidence_id === nodeId ? rel.target_title : rel.source_title)}
                    </p>
                    ${rel.description ? `<p class="text-xs text-gray-500 mt-1">${escapeHtml(rel.description)}</p>` : ''}
                </div>
            `).join('');

            lucide.createIcons();
        } catch (error) {
            console.error('Error fetching relationships:', error);
            showToast('Failed to load relationships', 'error');
        }
    },

    /**
     * Add a new relationship
     */
    async addRelationship(sourceNodeType, sourceNodeId, targetNodeType, targetNodeId, type, label, description) {
        try {
            await API.relationships.create({
                source_node_type: sourceNodeType,
                source_node_id: sourceNodeId,
                target_node_type: targetNodeType,
                target_node_id: targetNodeId,
                type: type,
                label: label,
                description: description
            });

            showToast('Relationship added', 'success');
            await this.loadGraph();
        } catch (error) {
            console.error('Error adding relationship:', error);
            showToast('Failed to add relationship: ' + error.message, 'error');
        }
    },

    /**
     * Delete a relationship
     */
    async deleteRelationship(relationshipId) {
        if (!confirm('Delete this relationship?')) return;

        try {
            await API.relationships.delete(relationshipId);
            showToast('Relationship deleted', 'success');
            await this.loadGraph();
        } catch (error) {
            console.error('Error deleting relationship:', error);
            showToast('Failed to delete relationship', 'error');
        }
    },

    /**
     * Find and highlight path between two nodes
     */
    async findPath() {
        if (!this.pathStart || !this.pathEnd) {
            showToast('Please select start and end nodes', 'warning');
            return;
        }

        try {
            const result = await API.relationships.findPath(this.pathStart, this.pathEnd);

            if (result.path.length === 0) {
                showToast('No path found between selected nodes', 'info');
                return;
            }

            showToast(`Found path with ${result.length} steps`, 'success');
            this.highlightPath(result.path);

            // Show path details
            this.showPathDetails(result.path);

        } catch (error) {
            console.error('Error finding path:', error);
            showToast('Failed to find path', 'error');
        }
    },

    /**
     * Highlight path on graph
     */
    highlightPath(path) {
        const pathNodeIds = path.map(p => p.id);

        // Highlight path nodes
        this.svg.selectAll('.node circle')
            .attr('stroke', d => pathNodeIds.includes(d.id) ? '#10b981' : '#fff')
            .attr('stroke-width', d => pathNodeIds.includes(d.id) ? 4 : 2);

        // Highlight path edges
        this.svg.selectAll('.relationship-edge')
            .attr('stroke', d => {
                const sourceInPath = pathNodeIds.includes(d.source.id || d.source);
                const targetInPath = pathNodeIds.includes(d.target.id || d.target);
                return (sourceInPath && targetInPath) ? '#10b981' : '#94a3b8';
            })
            .attr('stroke-width', d => {
                const sourceInPath = pathNodeIds.includes(d.source.id || d.source);
                const targetInPath = pathNodeIds.includes(d.target.id || d.target);
                return (sourceInPath && targetInPath) ? 4 : 2;
            });
    },

    /**
     * Show path details
     */
    showPathDetails(path) {
        const detailsPanel = document.getElementById('pathDetails');
        if (!detailsPanel) return;

        detailsPanel.innerHTML = `
            <h4 class="text-lg font-semibold mb-3">Attack Path (${path.length} steps)</h4>
            <div class="space-y-2">
                ${path.map((step, i) => `
                    <div class="path-step p-2 border-l-4 border-blue-500">
                        <div class="font-medium">${i + 1}. ${escapeHtml(step.title)}</div>
                        <div class="text-sm text-gray-600">${step.evidence_type}</div>
                        ${step.edge_type ? `
                            <div class="text-xs text-gray-500 mt-1">
                                <i data-lucide="arrow-right" class="w-3 h-3 inline"></i>
                                ${this.formatRelationType(step.edge_type)}
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
            <button class="btn btn-sm btn-primary mt-3" ${on('click', 'RelationshipGraph.saveCurrentPath')}>
                Save Path
            </button>
        `;

        lucide.createIcons();
    },

    /**
     * Export graph as SVG
     */
    exportGraph() {
        const svg = this.container.querySelector('svg');
        if (!svg) return;

        const serializer = new XMLSerializer();
        const svgString = serializer.serializeToString(svg);

        const blob = new Blob([svgString], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = 'attack-path.svg';
        link.click();

        URL.revokeObjectURL(url);
        showToast('Graph exported as SVG', 'success');
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Listen for window resize
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.width = this.container.clientWidth;
            this.svg.attr('width', this.width);
            if (this.simulation) {
                this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2));
                this.simulation.alpha(0.3).restart();
            }
        });
    },

    /**
     * Highlight a path node with step number
     */
    highlightPathNode(nodeId, stepNumber) {
        this.svg.selectAll('.node')
            .each((d, i, nodes) => {
                const node = d3.select(nodes[i]);
                const uniqueId = d.unique_id || d.id;

                if (uniqueId === nodeId) {
                    // Highlight the circle
                    node.select('circle')
                        .attr('stroke', '#10b981')
                        .attr('stroke-width', 4);

                    // Add step number label
                    node.append('text')
                        .attr('class', 'path-step-number')
                        .attr('dy', -30)
                        .attr('text-anchor', 'middle')
                        .style('font-size', '14px')
                        .style('font-weight', 'bold')
                        .style('fill', '#10b981')
                        .style('pointer-events', 'none')
                        .text(`Step ${stepNumber}`);
                }
            });
    },

    /**
     * Clear all path highlights
     */
    clearPathHighlights() {
        this.svg.selectAll('.node circle')
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        this.svg.selectAll('.path-step-number').remove();
        this.svg.selectAll('.path-connection').remove();
    },

    /**
     * Show the completed attack path with connections
     */
    showCompletedPath() {
        if (!this.attackPath || this.attackPath.length < 2) return;

        // Clear previous highlights
        this.clearPathHighlights();

        // Highlight all nodes in the path
        this.attackPath.forEach((pathNode, index) => {
            this.highlightPathNode(pathNode.id, index + 1);
        });

        // Draw connections between sequential nodes - bind data to lines
        const pathConnections = this.svg.select('.edges-layer')
            .selectAll('line.path-connection')
            .data(this.attackPath.slice(0, -1))  // All nodes except the last
            .join('line')
            .attr('class', 'path-connection')
            .attr('stroke', '#10b981')
            .attr('stroke-width', 4)
            .attr('stroke-dasharray', '5,5')
            .style('pointer-events', 'none');

        // Function to update path connection positions
        const updatePathConnections = () => {
            pathConnections.each(function(d, i) {
                const sourceNode = RelationshipGraph.attackPath[i].node;
                const targetNode = RelationshipGraph.attackPath[i + 1].node;

                if (sourceNode && targetNode && sourceNode.x !== undefined && targetNode.x !== undefined) {
                    d3.select(this)
                        .attr('x1', sourceNode.x)
                        .attr('y1', sourceNode.y)
                        .attr('x2', targetNode.x)
                        .attr('y2', targetNode.y);
                }
            });
        };

        // Initial draw
        updatePathConnections();

        // Update on every tick
        if (this.simulation) {
            this.simulation.on('tick.pathConnections', updatePathConnections);
        }
    },

    /**
     * Cleanup
     */
    destroy() {
        if (this.simulation) {
            this.simulation.stop();
        }
        if (this.svg) {
            this.svg.remove();
        }
    }
};

window.RelationshipGraph = RelationshipGraph;   // named in data-on-* attributes (L-21)
