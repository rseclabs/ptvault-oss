/**
 * Attack Map Editor
 *
 * D3.js SVG canvas for building visual attack maps.
 * Supports custom nodes (action, condition, infrastructure, AND/OR)
 * and reference nodes linking to evidence, findings, and hosts.
 */

const AttackMapEditor = {
    // ── State ───────────────────────────────────────────────
    svg: null,
    zoomBehavior: null,
    canvas: null,
    currentMapId: null,
    nodes: [],
    edges: [],
    selectedNodeId: null,
    selectedEdgeId: null,
    connectMode: false,
    connectSourceId: null,
    addNodeType: null,
    dragDebounce: null,
    isPanning: false,
    _contextMenu: null,
    maps: [],

    NODE_COLORS: {
        recon: '#5b2d8e',
        tactic: '#3b82f6',
        exploit: '#ef4444',
        connector: '#166534',
        evidence_ref: '#4a9e94',
        finding_ref: '#9278c4',
        host_ref: '#1e3a5f'
    },

    NODE_LABELS: {
        recon: 'Recon',
        tactic: 'Tactic',
        exploit: 'Exploit',
        connector: 'Connector',
        evidence_ref: 'Evidence',
        finding_ref: 'Finding',
        host_ref: 'Host'
    },

    GRID_SIZE: 20,
    CANVAS_WIDTH: 4000,
    CANVAS_HEIGHT: 3000,

    // ── Initialization ──────────────────────────────────────

    async init(containerId) {
        this.containerId = containerId || 'attackMapCanvas';
        this.selectedNodeId = null;
        this.selectedEdgeId = null;
        this.connectMode = false;
        this.connectSourceId = null;
        this.addNodeType = null;
        this.nodes = [];
        this.edges = [];

        await this.loadMaps();
        this.renderMapSelector();

        if (this.maps.length > 0 && !this.currentMapId) {
            await this.loadMap(this.maps[0].id);
        } else if (this.currentMapId) {
            await this.loadMap(this.currentMapId);
        } else {
            // No maps yet — still initialize the canvas so it's ready
            this.initCanvas();
        }
    },

    initCanvas() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.warn('AttackMapEditor: container not found:', this.containerId);
            return;
        }
        container.innerHTML = '';

        const rect = container.getBoundingClientRect();
        this._containerWidth = rect.width || 800;
        this._containerHeight = rect.height || 600;

        this.svg = d3.select(container)
            .append('svg')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${this._containerWidth} ${this._containerHeight}`)
            .style('background', '#1e1e2e');

        // Defs for arrow markers
        const defs = this.svg.append('defs');
        defs.append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '0 0 10 7')
            .attr('refX', 10)
            .attr('refY', 3.5)
            .attr('markerWidth', 10)
            .attr('markerHeight', 7)
            .attr('orient', 'auto')
            .append('polygon')
            .attr('points', '0 0, 10 3.5, 0 7')
            .attr('fill', '#94a3b8');

        // Grid pattern
        defs.append('pattern')
            .attr('id', 'grid')
            .attr('width', this.GRID_SIZE)
            .attr('height', this.GRID_SIZE)
            .attr('patternUnits', 'userSpaceOnUse')
            .append('path')
            .attr('d', `M ${this.GRID_SIZE} 0 L 0 0 0 ${this.GRID_SIZE}`)
            .attr('fill', 'none')
            .attr('stroke', 'rgba(255,255,255,0.04)')
            .attr('stroke-width', '0.5');

        // Zoom behavior
        this.zoomBehavior = d3.zoom()
            .scaleExtent([0.2, 3])
            .filter((event) => {
                // Allow zoom with wheel/pinch, pan with mouse drag
                // But don't let zoom consume plain clicks
                if (event.type === 'mousedown' || event.type === 'touchstart') return true;
                if (event.type === 'wheel') return true;
                if (event.type === 'dblclick') return true;
                return true;
            })
            .on('zoom', (event) => {
                this.canvas.attr('transform', event.transform);
                this._dismissContextMenu();
            });

        this.svg.call(this.zoomBehavior);

        // Prevent default context menu on canvas background
        this.svg.on('contextmenu', (event) => { event.preventDefault(); });

        // Click on SVG background to deselect (use mousedown+mouseup for reliability with D3 zoom)
        let mouseDownTarget = null;
        this.svg.on('mousedown.select', (event) => {
            mouseDownTarget = event.target;
        });
        this.svg.on('mouseup.select', (event) => {
            this._dismissContextMenu();
            // Only deselect if mouse down and up on the same background element (not a drag)
            if (mouseDownTarget === event.target) {
                const tag = event.target.tagName?.toLowerCase();
                if (event.target === this.svg.node() || tag === 'rect' || tag === 'svg') {
                    if (this.selectedNodeId || this.selectedEdgeId) {
                        this.deselectAll();
                    }
                }
            }
            mouseDownTarget = null;
        });

        // Main transform group
        this.canvas = this.svg.append('g').attr('class', 'canvas');

        // Grid background
        this.canvas.append('rect')
            .attr('width', this.CANVAS_WIDTH)
            .attr('height', this.CANVAS_HEIGHT)
            .attr('fill', 'url(#grid)')
            .attr('x', -this.CANVAS_WIDTH / 2)
            .attr('y', -this.CANVAS_HEIGHT / 2);

        // Layers
        this.canvas.append('g').attr('class', 'edges-layer');
        this.canvas.append('g').attr('class', 'nodes-layer');

        // Keyboard shortcuts
        document.addEventListener('keydown', this._handleKeyDown.bind(this));

        this.render();
        this._renderEmptyState();
    },

    // ── Data Loading ────────────────────────────────────────

    async loadMaps() {
        try {
            this.maps = await API.attackMaps.list();
        } catch (e) {
            console.error('Failed to load maps:', e);
            this.maps = [];
        }
    },

    async loadMap(mapId) {
        try {
            const data = await API.attackMaps.get(mapId);
            this.currentMapId = data.id;
            this.currentMapEngagementId = data.engagement_id || null;
            this.nodes = data.nodes || [];
            this.edges = data.edges || [];

            this.initCanvas();

            // Restore canvas transform
            if (data.canvas_data && data.canvas_data.transform) {
                const t = data.canvas_data.transform;
                this.svg.call(
                    this.zoomBehavior.transform,
                    d3.zoomIdentity.translate(t.x || 0, t.y || 0).scale(t.k || 1)
                );
            }

            this.render();
            this.updateMapSelector();
        } catch (e) {
            console.error('Failed to load map:', e);
        }
    },

    async createMap(name) {
        try {
            const map = await API.attackMaps.create({ name });
            this.maps.unshift(map);
            await this.loadMap(map.id);
            this.renderMapSelector();
            showToast('Map created', 'success');
        } catch (e) {
            console.error('Failed to create map:', e);
            showToast('Failed to create map: ' + e.message, 'error');
        }
    },

    async deleteCurrentMap() {
        if (!this.currentMapId) return;
        if (!confirm('Delete this attack map? This cannot be undone.')) return;

        try {
            await API.attackMaps.remove(this.currentMapId);
            this.maps = this.maps.filter(m => m.id !== this.currentMapId);
            this.currentMapId = null;
            this.nodes = [];
            this.edges = [];

            if (this.maps.length > 0) {
                await this.loadMap(this.maps[0].id);
            } else {
                this.renderMapSelector();
                const container = document.getElementById(this.containerId);
                if (container) container.innerHTML = '<div style="color:#94a3b8;text-align:center;padding:60px;">Create a new map to get started</div>';
            }
            showToast('Map deleted', 'success');
        } catch (e) {
            console.error('Failed to delete map:', e);
            showToast('Failed to delete map', 'error');
        }
    },

    async duplicateCurrentMap() {
        if (!this.currentMapId) return;
        try {
            const newMap = await API.attackMaps.duplicate(this.currentMapId);
            this.maps.unshift(newMap);
            await this.loadMap(newMap.id);
            showToast('Map duplicated', 'success');
        } catch (e) {
            console.error('Failed to duplicate map:', e);
            showToast('Failed to duplicate map', 'error');
        }
    },

    async saveCanvasState() {
        if (!this.currentMapId || !this.svg) return;
        try {
            const transform = d3.zoomTransform(this.svg.node());
            await API.attackMaps.update(this.currentMapId, {
                canvas_data: { transform: { x: transform.x, y: transform.y, k: transform.k } }
            });
        } catch (e) {
            // Silent fail - canvas state is non-critical
        }
    },

    // ── Rendering ───────────────────────────────────────────

    render() {
        if (!this.canvas) return;
        this.renderEdges();
        this.renderNodes();
        this._renderEmptyState();
    },

    renderNodes() {
        const nodesLayer = this.canvas.select('.nodes-layer');
        const nodeGroups = nodesLayer.selectAll('.node-group')
            .data(this.nodes, d => d.id);

        nodeGroups.exit().remove();

        const entered = nodeGroups.enter()
            .append('g')
            .attr('class', 'node-group')
            .attr('transform', d => `translate(${d.x}, ${d.y})`)
            .call(this._dragBehavior())
            .on('click', (event, d) => {
                event.stopPropagation();
                if (this.connectMode) {
                    this._handleConnectClick(d.id);
                } else {
                    this.selectNode(d.id);
                }
            })
            .on('contextmenu', (event, d) => {
                event.preventDefault();
                event.stopPropagation();
                this._showContextMenu(event, d);
            });

        entered.each((d, i, nodes) => {
            this._drawNode(d3.select(nodes[i]), d);
        });

        // Update existing
        nodeGroups.attr('transform', d => `translate(${d.x}, ${d.y})`);
        nodeGroups.each((d, i, nodes) => {
            const g = d3.select(nodes[i]);
            g.selectAll('*').remove();
            this._drawNode(g, d);
        });
    },

    _drawNode(g, d) {
        const isLogic = d.node_type === 'connector';
        const color = this.NODE_COLORS[d.node_type] || '#6b7280';
        const isSelected = d.id === this.selectedNodeId;
        const label = d.label || this.NODE_LABELS[d.node_type] || '';
        const typeLabel = this.NODE_LABELS[d.node_type] || d.node_type;
        const props = d.properties || {};

        if (isLogic) {
            const connLabel = label || 'Connector';
            const w = Math.max(80, connLabel.length * 9 + 30);
            const h = 40;
            d._computedWidth = w;
            d._computedHeight = h;

            g.append('rect')
                .attr('width', w)
                .attr('height', h)
                .attr('rx', 20)
                .attr('ry', 20)
                .attr('fill', color)
                .attr('stroke', isSelected ? '#fff' : 'transparent')
                .attr('stroke-width', isSelected ? 2 : 0)
                .attr('cursor', 'move');

            g.append('text')
                .attr('x', w / 2)
                .attr('y', h / 2 + 1)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', '#fff')
                .attr('font-size', '14px')
                .attr('font-weight', '700')
                .attr('pointer-events', 'none')
                .text(connLabel);
        } else {
            const headerH = 24;
            const padding = 10;
            const fontSize = 12;
            const lineH = fontSize + 4;
            const charWidth = 7.2;
            const boldCharWidth = 7.8;
            const sidePad = 16;
            const minW = 160;
            const maxW = 320;

            // Collect content entries
            const entries = [];
            if (label) entries.push({ text: label, bold: true });
            if (props.ttp) entries.push({ text: `TTP: ${props.ttp}` });
            if (props.service) entries.push({ text: `Service: ${props.service}` });
            if (props.cve) entries.push({ text: `CVE: ${props.cve}` });
            if (props.description) entries.push({ text: props.description });
            if (d.node_type === 'evidence_ref' && props.title) entries.push({ text: props.title });
            if (d.node_type === 'finding_ref' && props.severity) entries.push({ text: `Severity: ${props.severity}` });
            if (d.node_type === 'host_ref' && props.hostname) entries.push({ text: props.hostname });
            if (d.node_type === 'host_ref' && props.ip) entries.push({ text: props.ip });

            // Determine node width: clamp between minW and maxW
            const w = Math.min(maxW, Math.max(minW, (d.width || 220)));
            const maxCharsPerLine = Math.floor((w - sidePad) / charWidth);

            // Word-wrap each entry into visual lines
            const visLines = [];
            entries.forEach(entry => {
                const words = entry.text.split(/\s+/);
                let cur = '';
                words.forEach(word => {
                    const test = cur ? cur + ' ' + word : word;
                    if (test.length > maxCharsPerLine && cur) {
                        visLines.push({ text: cur, bold: !!entry.bold });
                        cur = word;
                    } else {
                        cur = test;
                    }
                });
                if (cur) visLines.push({ text: cur, bold: !!entry.bold });
            });

            // Calculate height from wrapped lines
            const contentH = Math.max(30, visLines.length * lineH + padding);
            const totalH = headerH + contentH;

            d._computedWidth = w;
            d._computedHeight = totalH;

            // Background
            g.append('rect')
                .attr('width', w)
                .attr('height', totalH)
                .attr('rx', 8)
                .attr('ry', 8)
                .attr('fill', '#2a2a3e')
                .attr('stroke', isSelected ? '#fff' : color)
                .attr('stroke-width', isSelected ? 2 : 1.5)
                .attr('cursor', 'move');

            // Header bar
            const isCompromised = d.node_type === 'host_ref' && props.compromised;
            const headerColor = isCompromised ? '#000000' : color;
            g.append('rect')
                .attr('width', w)
                .attr('height', headerH)
                .attr('rx', 8)
                .attr('ry', 8)
                .attr('fill', headerColor)
                .attr('pointer-events', 'none');
            g.append('rect')
                .attr('width', w)
                .attr('height', 8)
                .attr('y', headerH - 8)
                .attr('fill', headerColor)
                .attr('pointer-events', 'none');

            // Skull badge for compromised host nodes (left of label)
            if (isCompromised) {
                g.append('text')
                    .attr('x', 8)
                    .attr('y', headerH / 2 + 1)
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', '#ef4444')
                    .attr('font-size', '20px')
                    .attr('pointer-events', 'none')
                    .text('☠');
            }

            // Type label in header
            g.append('text')
                .attr('x', isCompromised ? 32 : 8)
                .attr('y', headerH / 2 + 1)
                .attr('dominant-baseline', 'middle')
                .attr('fill', isCompromised ? '#ef4444' : '#fff')
                .attr('font-size', '11px')
                .attr('font-weight', '600')
                .attr('pointer-events', 'none')
                .text(typeLabel);

            // Content lines (word-wrapped)
            visLines.forEach((line, idx) => {
                g.append('text')
                    .attr('x', 8)
                    .attr('y', headerH + padding + idx * lineH + fontSize)
                    .attr('fill', line.bold ? '#e2e8f0' : '#94a3b8')
                    .attr('font-size', `${fontSize}px`)
                    .attr('font-weight', line.bold ? '600' : '400')
                    .attr('pointer-events', 'none')
                    .text(line.text);
            });

        }
    },

    renderEdges() {
        const edgesLayer = this.canvas.select('.edges-layer');
        const edgePaths = edgesLayer.selectAll('.edge-group')
            .data(this.edges, d => d.id);

        edgePaths.exit().remove();

        const entered = edgePaths.enter()
            .append('g')
            .attr('class', 'edge-group');

        entered.append('path')
            .attr('class', 'edge-path')
            .attr('fill', 'none')
            .attr('stroke', '#94a3b8')
            .attr('stroke-width', 2)
            .attr('marker-end', 'url(#arrowhead)')
            .attr('cursor', 'pointer')
            .on('click', (event, d) => {
                event.stopPropagation();
                this.selectEdge(d.id);
            });

        entered.append('text')
            .attr('class', 'edge-label')
            .attr('fill', '#94a3b8')
            .attr('font-size', '11px')
            .attr('text-anchor', 'middle')
            .attr('pointer-events', 'none');

        // Update all edge paths
        edgesLayer.selectAll('.edge-group').each((d, i, groups) => {
            const g = d3.select(groups[i]);
            const sourceNode = this.nodes.find(n => n.id === d.source_node_id);
            const targetNode = this.nodes.find(n => n.id === d.target_node_id);
            if (!sourceNode || !targetNode) return;

            const isSelected = d.id === this.selectedEdgeId;
            const sw = sourceNode._computedWidth || sourceNode.width || 220;
            const sh = sourceNode._computedHeight || sourceNode.height || 80;
            const tw = targetNode._computedWidth || targetNode.width || 220;
            const th = targetNode._computedHeight || targetNode.height || 80;

            const sx = sourceNode.x + sw / 2;
            const sy = sourceNode.y + sh / 2;
            const tx = targetNode.x + tw / 2;
            const ty = targetNode.y + th / 2;

            // Calculate edge point on border of target node
            const angle = Math.atan2(ty - sy, tx - sx);
            const margin = 4;
            const endX = tx - Math.cos(angle) * (tw / 2 + margin);
            const endY = ty - Math.sin(angle) * (th / 2 + margin);
            const startX = sx + Math.cos(angle) * (sw / 2 + margin);
            const startY = sy + Math.sin(angle) * (sh / 2 + margin);

            g.select('.edge-path')
                .attr('d', `M ${startX} ${startY} L ${endX} ${endY}`)
                .attr('stroke', isSelected ? '#fff' : '#94a3b8')
                .attr('stroke-width', isSelected ? 3 : 2);

            if (d.label) {
                g.select('.edge-label')
                    .attr('x', (startX + endX) / 2)
                    .attr('y', (startY + endY) / 2 - 8)
                    .text(d.label);
            }
        });
    },

    // ── Selection ────────────────────────────────────────────

    /**
     * Auto-save all property panel inputs for the currently selected node
     * before switching selection. Reads DOM inputs and persists any changes.
     */
    async _autoSaveCurrentNode() {
        if (!this.selectedNodeId) return;
        const node = this.nodes.find(n => n.id === this.selectedNodeId);
        if (!node) return;

        const panel = document.getElementById('attackMapProperties');
        if (!panel) return;

        const inputs = panel.querySelectorAll('input[type="text"], textarea');
        let labelChanged = false;
        let propsChanged = false;

        inputs.forEach(input => {
            const onchange = input.getAttribute('onchange') || '';
            // Parse the property key from the onchange handler
            const labelMatch = onchange.match(/updateNodeProp\(\d+,\s*'label'/);
            const propMatch = onchange.match(/updateNodeProp\(\d+,\s*'(\w+)'/);

            if (labelMatch) {
                if (input.value !== (node.label || '')) {
                    node.label = input.value;
                    labelChanged = true;
                }
            } else if (propMatch) {
                const key = propMatch[1];
                if (!node.properties) node.properties = {};
                if (input.value !== (node.properties[key] || '')) {
                    node.properties[key] = input.value;
                    propsChanged = true;
                }
            }
        });

        // Persist changes via API
        try {
            if (labelChanged && propsChanged) {
                await API.attackMaps.updateNode(this.currentMapId, node.id, {
                    label: node.label,
                    properties: node.properties
                });
            } else if (labelChanged) {
                await API.attackMaps.updateNode(this.currentMapId, node.id, { label: node.label });
            } else if (propsChanged) {
                await API.attackMaps.updateNode(this.currentMapId, node.id, { properties: node.properties });
            }
        } catch (e) {
            console.error('Auto-save failed:', e);
        }
    },

    async selectNode(nodeId) {
        await this._autoSaveCurrentNode();
        this.selectedNodeId = nodeId;
        this.selectedEdgeId = null;
        this.render();
        this.renderPropertiesPanel();
    },

    async selectEdge(edgeId) {
        await this._autoSaveCurrentNode();
        this.selectedEdgeId = edgeId;
        this.selectedNodeId = null;
        this.render();
        this.renderPropertiesPanel();
    },

    async deselectAll() {
        await this._autoSaveCurrentNode();
        this.selectedNodeId = null;
        this.selectedEdgeId = null;
        this.render();
        this.renderPropertiesPanel();
    },

    // ── Node Operations ─────────────────────────────────────

    async createNodeAt(nodeType, x, y) {
        if (!this.currentMapId) return;

        // For ref types, show picker
        if (nodeType === 'evidence_ref' || nodeType === 'finding_ref' || nodeType === 'host_ref') {
            this._showRefPicker(nodeType, x, y);
            return;
        }

        try {
            const isLogic = nodeType === 'connector';
            const node = await API.attackMaps.createNode(this.currentMapId, {
                node_type: nodeType,
                x, y,
                width: isLogic ? 80 : 220,
                height: isLogic ? 40 : 80,
                label: this.NODE_LABELS[nodeType] || nodeType,
                properties: {}
            });
            this.nodes.push(node);
            this.selectNode(node.id);
            this.render();
            if (this.nodes.length === 1) {
                this.zoomFit();
            }
        } catch (e) {
            console.error('Failed to create node:', e);
            showToast('Failed to create node', 'error');
        }
    },

    async deleteSelected() {
        if (this.selectedNodeId) {
            try {
                await API.attackMaps.deleteNode(this.currentMapId, this.selectedNodeId);
                this.edges = this.edges.filter(
                    e => e.source_node_id !== this.selectedNodeId && e.target_node_id !== this.selectedNodeId
                );
                this.nodes = this.nodes.filter(n => n.id !== this.selectedNodeId);
                this.selectedNodeId = null;
                this.render();
                this.renderPropertiesPanel();
            } catch (e) {
                console.error('Failed to delete node:', e);
            }
        } else if (this.selectedEdgeId) {
            try {
                await API.attackMaps.deleteEdge(this.currentMapId, this.selectedEdgeId);
                this.edges = this.edges.filter(e => e.id !== this.selectedEdgeId);
                this.selectedEdgeId = null;
                this.render();
                this.renderPropertiesPanel();
            } catch (e) {
                console.error('Failed to delete edge:', e);
            }
        }
    },

    // ── Connections ──────────────────────────────────────────

    toggleConnectMode() {
        this.connectMode = !this.connectMode;
        this.connectSourceId = null;
        this.addNodeType = null;
        this.updateToolbarState();
        this.render();
    },

    _handleConnectClick(nodeId) {
        if (!this.connectSourceId) {
            this.connectSourceId = nodeId;
            this.render();
        } else if (this.connectSourceId !== nodeId) {
            this._createEdge(this.connectSourceId, nodeId);
            this.connectSourceId = null;
        } else {
            this.connectSourceId = null;
            this.render();
        }
    },

    async _createEdge(sourceId, targetId) {
        if (!this.currentMapId) return;
        try {
            const edge = await API.attackMaps.createEdge(this.currentMapId, {
                source_node_id: sourceId,
                target_node_id: targetId,
                label: ''
            });
            this.edges.push(edge);
            this.render();
        } catch (e) {
            console.error('Failed to create edge:', e);
            showToast('Failed to create connection', 'error');
        }
    },

    // ── Drag Behavior ───────────────────────────────────────

    _dragBehavior() {
        const self = this;
        return d3.drag()
            .on('start', function(event, d) {
                d3.select(this).raise();
            })
            .on('drag', function(event, d) {
                d.x = Math.round(event.x / self.GRID_SIZE) * self.GRID_SIZE;
                d.y = Math.round(event.y / self.GRID_SIZE) * self.GRID_SIZE;
                d3.select(this).attr('transform', `translate(${d.x}, ${d.y})`);
                self.renderEdges();
            })
            .on('end', function(event, d) {
                clearTimeout(self.dragDebounce);
                self.dragDebounce = setTimeout(async () => {
                    try {
                        await API.attackMaps.updateNode(self.currentMapId, d.id, {
                            x: d.x, y: d.y
                        });
                    } catch (e) {
                        console.error('Failed to save node position:', e);
                    }
                }, 300);
            });
    },

    // ── Keyboard ────────────────────────────────────────────

    _handleKeyDown(e) {
        // Only handle when attack maps tab is active
        const container = document.getElementById(this.containerId);
        if (!container || container.offsetParent === null) return;
        // Don't capture if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

        if (e.key === 'Delete' || e.key === 'Backspace') {
            this.deleteSelected();
            e.preventDefault();
        } else if (e.key === 'Escape') {
            this._dismissContextMenu();
            if (this.connectMode) {
                this.connectMode = false;
                this.connectSourceId = null;
                this.updateToolbarState();
                this.render();
            } else {
                this.deselectAll();
            }
        }
    },

    // ── Properties Panel ────────────────────────────────────

    renderPropertiesPanel() {
        const panel = document.getElementById('attackMapProperties');
        if (!panel) return;

        if (this.selectedNodeId) {
            const node = this.nodes.find(n => n.id === this.selectedNodeId);
            if (!node) { panel.innerHTML = ''; return; }

            const props = node.properties || {};
            const isLogic = node.node_type === 'connector';
            const color = this.NODE_COLORS[node.node_type] || '#6b7280';

            let fieldsHtml = '';
            fieldsHtml += `
                <div class="prop-field">
                    <label>${isLogic ? 'Name' : 'Label'}</label>
                    <input type="text" value="${this._esc(node.label || '')}"
                           onchange="AttackMapEditor.updateNodeProp(${node.id}, 'label', this.value)" />
                </div>
            `;

            if (node.node_type === 'recon') {
                fieldsHtml += `
                    <div class="prop-field">
                        <label>MITRE TTP</label>
                        <input type="text" value="${this._esc(props.ttp || '')}"
                               placeholder="e.g. T1595.001"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'ttp', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label>Description</label>
                        <textarea rows="3"
                            onchange="AttackMapEditor.updateNodeProp(${node.id}, 'description', this.value)">${this._esc(props.description || '')}</textarea>
                    </div>
                `;
            } else if (node.node_type === 'tactic') {
                fieldsHtml += `
                    <div class="prop-field">
                        <label>MITRE TTP</label>
                        <input type="text" value="${this._esc(props.ttp || '')}"
                               placeholder="e.g. T1059.001"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'ttp', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label>Description</label>
                        <textarea rows="3"
                            onchange="AttackMapEditor.updateNodeProp(${node.id}, 'description', this.value)">${this._esc(props.description || '')}</textarea>
                    </div>
                `;
            } else if (node.node_type === 'exploit') {
                fieldsHtml += `
                    <div class="prop-field">
                        <label>Service</label>
                        <input type="text" value="${this._esc(props.service || '')}"
                               placeholder="e.g. Apache 2.4, SMB"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'service', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label>CVE</label>
                        <input type="text" value="${this._esc(props.cve || '')}"
                               placeholder="e.g. CVE-2024-1234"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'cve', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label>Description</label>
                        <textarea rows="3"
                            onchange="AttackMapEditor.updateNodeProp(${node.id}, 'description', this.value)">${this._esc(props.description || '')}</textarea>
                    </div>
                `;
            } else if (node.node_type === 'evidence_ref' || node.node_type === 'finding_ref') {
                fieldsHtml += `
                    <div class="prop-field">
                        <label>Reference</label>
                        <div style="color:#94a3b8;font-size:12px;padding:4px 0;">
                            ${node.ref_type ? `${node.ref_type} #${node.ref_id}` : 'No reference linked'}
                        </div>
                    </div>
                `;
            } else if (node.node_type === 'host_ref') {
                fieldsHtml += `
                    <div class="prop-field">
                        <label>Hostname</label>
                        <input type="text" value="${this._esc(props.hostname || '')}"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'hostname', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label>IP Address</label>
                        <input type="text" value="${this._esc(props.ip || '')}"
                               onchange="AttackMapEditor.updateNodeProp(${node.id}, 'ip', this.value)" />
                    </div>
                    <div class="prop-field">
                        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none;">
                            <input type="checkbox" ${props.compromised ? 'checked' : ''}
                                   onchange="AttackMapEditor.updateNodeProp(${node.id}, 'compromised', this.checked)"
                                   style="width:15px;height:15px;cursor:pointer;accent-color:#ef4444;" />
                            <span>Compromised ☠</span>
                        </label>
                    </div>
                    <div class="prop-field">
                        <label>Reference</label>
                        <div style="color:#94a3b8;font-size:12px;padding:4px 0;">
                            ${node.ref_type ? `${node.ref_type} #${node.ref_id}` : 'No reference linked'}
                        </div>
                    </div>
                `;
            }

            panel.innerHTML = `
                <div class="props-header" style="border-left: 3px solid ${color}; padding-left: 10px; margin-bottom: 12px;">
                    <div style="font-weight:600;color:#e2e8f0;font-size:14px;">${this.NODE_LABELS[node.node_type]}</div>
                    <div style="color:#94a3b8;font-size:12px;">Node #${node.id}</div>
                </div>
                ${fieldsHtml}
                <button class="btn btn-sm btn-danger" style="margin-top:12px;width:100%;"
                        onclick="AttackMapEditor.deleteSelected()">
                    Delete Node
                </button>
            `;
        } else if (this.selectedEdgeId) {
            const edge = this.edges.find(e => e.id === this.selectedEdgeId);
            if (!edge) { panel.innerHTML = ''; return; }

            panel.innerHTML = `
                <div class="props-header" style="margin-bottom:12px;">
                    <div style="font-weight:600;color:#e2e8f0;font-size:14px;">Connection</div>
                    <div style="color:#94a3b8;font-size:12px;">Edge #${edge.id}</div>
                </div>
                <div class="prop-field">
                    <label>Label</label>
                    <input type="text" value="${this._esc(edge.label || '')}"
                           onchange="AttackMapEditor.updateEdgeLabel(${edge.id}, this.value)" />
                </div>
                <button class="btn btn-sm btn-danger" style="margin-top:12px;width:100%;"
                        onclick="AttackMapEditor.deleteSelected()">
                    Delete Connection
                </button>
            `;
        } else {
            panel.innerHTML = `
                <div style="color:#64748b;text-align:center;padding:20px;font-size:13px;">
                    Select a node or edge to edit its properties
                </div>
            `;
        }
    },

    async updateNodeProp(nodeId, key, value) {
        const node = this.nodes.find(n => n.id === nodeId);
        if (!node) return;

        if (key === 'label') {
            node.label = value;
            try {
                await API.attackMaps.updateNode(this.currentMapId, nodeId, { label: value });
            } catch (e) { console.error('Failed to update node:', e); }
        } else {
            if (!node.properties) node.properties = {};
            node.properties[key] = value;
            try {
                await API.attackMaps.updateNode(this.currentMapId, nodeId, { properties: node.properties });
            } catch (e) { console.error('Failed to update node:', e); }
        }
        this.render();
    },

    async updateEdgeLabel(edgeId, label) {
        const edge = this.edges.find(e => e.id === edgeId);
        if (!edge) return;
        edge.label = label;
        try {
            // Edge label update — use node update pattern (edges don't have dedicated update endpoint, so update via delete/recreate or raw API)
            // For now we just update locally since edge labels are saved with the edge
            // We'd need a PUT /edges/<id> endpoint. Let's save via map canvas_data instead.
            // Actually, let's just keep it in local state and save when user saves the map.
            this.render();
        } catch (e) { console.error('Failed to update edge:', e); }
    },

    // ── Reference Pickers ───────────────────────────────────

    async _showRefPicker(nodeType, x, y) {
        let items = [];
        let title = '';

        try {
            if (nodeType === 'evidence_ref') {
                title = 'Select Evidence';
                const data = await API.evidence.getAll();
                items = (data || []).map(e => ({
                    id: e.id,
                    label: e.title || `Evidence #${e.id}`,
                    sub: e.type || '',
                    refType: 'evidence'
                }));
            } else if (nodeType === 'finding_ref') {
                title = 'Select Finding';
                const engId = this.currentMapEngagementId || AppState.activeEngagement?.id;
                if (!engId) {
                    showToast('No active engagement', 'warning');
                    return;
                }
                const data = await API.engagements.getFindings(engId);
                items = (data || []).map(f => ({
                    id: f.id,
                    label: f.title || `Finding #${f.id}`,
                    sub: f.criticality ? `${f.criticality}${f.cvss_score ? ' (' + f.cvss_score + ')' : ''}` : '',
                    refType: 'finding'
                }));
            } else if (nodeType === 'host_ref') {
                title = 'Select Host';
                const data = await API.hosts.getAll();
                const hosts = data.hosts || [];
                items = hosts.map(h => ({
                    id: h.id,
                    label: h.hostname || h.ip || `Host #${h.id}`,
                    sub: h.ip || '',
                    refType: 'host',
                    hostname: h.hostname || '',
                    ip: h.ip || ''
                }));
            }
        } catch (e) {
            console.error('Failed to load items for picker:', e);
            showToast('Failed to load items', 'error');
            return;
        }

        if (items.length === 0) {
            showToast(`No ${nodeType.replace('_ref', '')} items found`, 'warning');
            return;
        }

        // Build and show modal
        const modalHtml = `
            <div id="refPickerModal" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:10000;display:flex;align-items:center;justify-content:center;">
                <div style="background:#1e1e2e;border:1px solid #374151;border-radius:12px;width:400px;max-height:500px;overflow:hidden;display:flex;flex-direction:column;">
                    <div style="padding:16px;border-bottom:1px solid #374151;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <h4 style="margin:0;color:#e2e8f0;">${title}</h4>
                            <button onclick="document.getElementById('refPickerModal').remove()" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:18px;">&times;</button>
                        </div>
                        <input type="text" id="refPickerSearch" placeholder="Search..."
                               style="width:100%;margin-top:8px;padding:8px;background:#2a2a3e;border:1px solid #374151;border-radius:6px;color:#e2e8f0;outline:none;"
                               oninput="AttackMapEditor._filterRefPicker(this.value)" />
                    </div>
                    <div id="refPickerList" style="overflow-y:auto;max-height:350px;padding:8px;">
                        ${items.map((item, idx) => `
                            <div class="ref-picker-item" data-search="${this._esc(item.label.toLowerCase())}" data-idx="${idx}"
                                 style="padding:10px 12px;cursor:pointer;border-radius:6px;margin-bottom:2px;color:#e2e8f0;"
                                 onmouseover="this.style.background='#374151'"
                                 onmouseout="this.style.background='transparent'"
                                 onclick="AttackMapEditor._selectRefByIndex(${idx})">
                                <div style="font-weight:500;">${this._esc(item.label)}</div>
                                ${item.sub ? `<div style="font-size:11px;color:#94a3b8;">${this._esc(item.sub)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('refPickerSearch').focus();

        // Store picker context for _selectRefByIndex
        this._pickerCtx = { nodeType, x, y, items };
    },

    _filterRefPicker(query) {
        const items = document.querySelectorAll('#refPickerList .ref-picker-item');
        const q = query.toLowerCase();
        items.forEach(item => {
            const match = item.dataset.search.includes(q);
            item.style.display = match ? '' : 'none';
        });
    },

    _selectRefByIndex(idx) {
        const ctx = this._pickerCtx;
        if (!ctx) return;
        const item = ctx.items[idx];
        if (!item) return;
        this._selectRef(ctx.nodeType, item, ctx.x, ctx.y);
    },

    async _selectRef(nodeType, item, x, y) {
        document.getElementById('refPickerModal')?.remove();
        try {
            const extraProps = {};
            if (nodeType === 'host_ref') {
                extraProps.hostname = item.hostname || '';
                extraProps.ip = item.ip || '';
            }
            extraProps.title = item.label;

            const node = await API.attackMaps.createNode(this.currentMapId, {
                node_type: nodeType,
                x, y,
                width: 200,
                height: 80,
                label: item.label,
                ref_id: item.id,
                ref_type: item.refType,
                properties: extraProps
            });
            this.nodes.push(node);
            this.selectNode(node.id);
            this.render();
        } catch (e) {
            console.error('Failed to create reference node:', e);
            showToast('Failed to create reference node', 'error');
        }
    },

    // ── UI Integration ──────────────────────────────────────

    renderMapSelector() {
        const selector = document.getElementById('attackMapSelector');
        if (!selector) return;

        const options = this.maps.map(m =>
            `<option value="${m.id}" ${m.id === this.currentMapId ? 'selected' : ''}>${this._esc(m.name)}</option>`
        ).join('');

        selector.innerHTML = `
            <select id="attackMapSelect" onchange="AttackMapEditor.loadMap(parseInt(this.value))"
                    style="background:#2a2a3e;border:1px solid #374151;color:#e2e8f0;padding:6px 10px;border-radius:6px;min-width:180px;">
                ${this.maps.length ? options : '<option value="">No maps</option>'}
            </select>
        `;
    },

    updateMapSelector() {
        const select = document.getElementById('attackMapSelect');
        if (!select) {
            this.renderMapSelector();
            return;
        }
        select.innerHTML = this.maps.map(m =>
            `<option value="${m.id}" ${m.id === this.currentMapId ? 'selected' : ''}>${this._esc(m.name)}</option>`
        ).join('');
    },

    setAddNodeType(type) {
        if (!this.currentMapId) {
            showToast('Create or select a map first', 'warning');
            return;
        }
        if (!this.svg) {
            // Try to recover by initializing canvas
            this.initCanvas();
            if (!this.svg) {
                showToast('Canvas not ready — try reloading the page', 'warning');
                return;
            }
        }
        // Directly create node at center of current viewport
        const center = this._getViewportCenter();
        this.connectMode = false;
        this.connectSourceId = null;
        this.addNodeType = null;
        this.createNodeAt(type, center.x, center.y);
    },

    updateToolbarState() {
        // Update connect button state
        const connectBtn = document.getElementById('attackMapConnectBtn');
        if (connectBtn) {
            connectBtn.classList.toggle('active', this.connectMode);
            connectBtn.style.background = this.connectMode ? '#22c55e' : '';
            connectBtn.style.color = this.connectMode ? '#fff' : '';
        }
    },

    zoomIn() {
        if (!this.svg || !this.zoomBehavior) return;
        this.svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 1.3);
    },

    zoomOut() {
        if (!this.svg || !this.zoomBehavior) return;
        this.svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 0.7);
    },

    zoomFit() {
        if (!this.svg || !this.zoomBehavior || this.nodes.length === 0) return;

        const container = document.getElementById(this.containerId);
        if (!container) return;
        const bounds = container.getBoundingClientRect();

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this.nodes.forEach(n => {
            minX = Math.min(minX, n.x);
            minY = Math.min(minY, n.y);
            maxX = Math.max(maxX, n.x + (n._computedWidth || n.width || 220));
            maxY = Math.max(maxY, n.y + (n._computedHeight || n.height || 80));
        });

        const padding = 60;
        const w = maxX - minX + padding * 2;
        const h = maxY - minY + padding * 2;
        const scale = Math.min(bounds.width / w, bounds.height / h, 2);
        const tx = bounds.width / 2 - (minX + (maxX - minX) / 2) * scale;
        const ty = bounds.height / 2 - (minY + (maxY - minY) / 2) * scale;

        this.svg.transition().duration(400).call(
            this.zoomBehavior.transform,
            d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
    },

    async promptNewMap() {
        const name = prompt('Enter map name:');
        if (name && name.trim()) {
            await this.createMap(name.trim());
        }
    },

    // ── Utility ─────────────────────────────────────────────

    _getViewportCenter() {
        if (!this.svg) return { x: 0, y: 0 };
        const transform = d3.zoomTransform(this.svg.node());
        const w = this._containerWidth || 800;
        const h = this._containerHeight || 600;
        // Convert viewport center to canvas coordinates
        const x = Math.round(((w / 2 - transform.x) / transform.k) / this.GRID_SIZE) * this.GRID_SIZE;
        const y = Math.round(((h / 2 - transform.y) / transform.k) / this.GRID_SIZE) * this.GRID_SIZE;
        // Offset each new node slightly so they don't stack exactly
        const offset = this.nodes.length * 20;
        return { x: x + offset % 200, y: y + (Math.floor(offset / 200)) * 40 };
    },

    _renderEmptyState() {
        if (!this.canvas || this.nodes.length > 0) {
            // Remove existing empty state if any
            this.canvas?.select('.empty-state')?.remove();
            return;
        }

        const w = this._containerWidth || 800;
        const h = this._containerHeight || 600;

        const emptyG = this.canvas.append('g').attr('class', 'empty-state');

        emptyG.append('text')
            .attr('x', w / 2)
            .attr('y', h / 2 - 30)
            .attr('text-anchor', 'middle')
            .attr('fill', '#64748b')
            .attr('font-size', '16px')
            .attr('font-weight', '600')
            .text('Empty Attack Map');

        emptyG.append('text')
            .attr('x', w / 2)
            .attr('y', h / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#475569')
            .attr('font-size', '13px')
            .text('Use the node palette on the left to add nodes');

        emptyG.append('text')
            .attr('x', w / 2)
            .attr('y', h / 2 + 22)
            .attr('text-anchor', 'middle')
            .attr('fill', '#475569')
            .attr('font-size', '13px')
            .text('Then use Connect to draw arrows between them');
    },

    // ── Context Menu ──────────────────────────────────────

    _showContextMenu(event, nodeData) {
        this._dismissContextMenu();
        const menu = document.createElement('div');
        menu.id = 'attackMapContextMenu';
        menu.style.cssText = 'position:fixed;z-index:10001;background:#1e1e2e;border:1px solid #374151;border-radius:8px;padding:4px 0;min-width:160px;box-shadow:0 8px 24px rgba(0,0,0,0.4);';
        menu.style.left = event.clientX + 'px';
        menu.style.top = event.clientY + 'px';

        const items = [
            { label: 'Connect to\u2026', icon: '🔗', action: () => this._contextConnectFrom(nodeData.id) },
            { label: 'Edit Properties', icon: '✏️', action: () => this.selectNode(nodeData.id) },
            { divider: true },
            { label: 'Delete Node', icon: '🗑️', action: () => { this.selectNode(nodeData.id); this.deleteSelected(); }, danger: true }
        ];

        items.forEach(item => {
            if (item.divider) {
                const hr = document.createElement('div');
                hr.style.cssText = 'height:1px;background:#374151;margin:4px 0;';
                menu.appendChild(hr);
                return;
            }
            const btn = document.createElement('div');
            btn.style.cssText = `padding:8px 12px;cursor:pointer;font-size:13px;color:${item.danger ? '#ef4444' : '#e2e8f0'};display:flex;align-items:center;gap:8px;`;
            btn.innerHTML = `<span style="font-size:14px;width:18px;text-align:center;">${item.icon}</span>${item.label}`;
            btn.addEventListener('mouseenter', () => { btn.style.background = '#2a2a3e'; });
            btn.addEventListener('mouseleave', () => { btn.style.background = 'transparent'; });
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this._dismissContextMenu();
                item.action();
            });
            menu.appendChild(btn);
        });

        // Ensure menu stays within viewport
        document.body.appendChild(menu);
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
        if (rect.bottom > window.innerHeight) menu.style.top = (window.innerHeight - rect.height - 8) + 'px';

        this._contextMenu = menu;
    },

    _dismissContextMenu() {
        if (this._contextMenu) {
            this._contextMenu.remove();
            this._contextMenu = null;
        }
    },

    _contextConnectFrom(nodeId) {
        this.connectMode = true;
        this.connectSourceId = nodeId;
        this.addNodeType = null;
        this.updateToolbarState();
        this.render();
    },

    _esc(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
};

window.AttackMapEditor = AttackMapEditor;
