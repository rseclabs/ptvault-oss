/**
 * Dashboard — per-engagement metrics overview.
 *
 * Renders eight inline-SVG charts using D3 v7. Theme colors are read
 * at render time from CSS custom properties so dark/light themes work
 * without a JS palette swap. Layout/chrome lives in dashboard.css; this
 * module only injects data-bound elements with semantic class names.
 */
const Dashboard = {
    state: {
        loading: false,
        data: null,
        lastFetch: null,
        initialized: false,
    },

    SEVERITY_ORDER: ['critical', 'high', 'medium', 'low', 'info'],

    /** Severity slice colors come from --color-{critical,high,medium,low}; info falls back. */
    severityColor(label) {
        if (label === 'info') return this.themeColor('--color-text-tertiary');
        return this.themeColor('--color-' + label);
    },

    /** Color-category swatches (host indicators) — themed for both light/dark. */
    COLOR_CATEGORY_HEX: {
        white:  '#e2e8f0', yellow: '#facc15', green:  '#22c55e',
        blue:   '#3b82f6', red:    '#ef4444', purple: '#a855f7',
        orange: '#f97316', teal:   '#14b8a6', cyan:   '#06b6d4',
        brown:  '#a16207',
    },

    /** Read a CSS custom property from the document root, return its trimmed value. */
    themeColor(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    },

    init() {
        if (this.state.initialized) return;
        this.state.initialized = true;

        const refreshBtn = document.getElementById('dashboardRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.load());
        }
    },

    async load() {
        const grid = document.getElementById('dashboardGrid');
        const empty = document.getElementById('dashboardEmpty');
        const errBox = document.getElementById('dashboardError');

        if (typeof AppState === 'undefined' || !AppState.activeEngagement) {
            if (grid) grid.style.display = 'none';
            if (empty) empty.style.display = 'block';
            if (errBox) errBox.style.display = 'none';
            return;
        }

        if (empty) empty.style.display = 'none';
        if (grid) grid.style.display = 'grid';
        if (errBox) errBox.style.display = 'none';

        this.state.loading = true;
        try {
            const data = await API.dashboard.getMetrics();
            this.state.data = data;
            this.state.lastFetch = new Date();
            this.render(data);
            const ts = document.getElementById('dashboardLastUpdated');
            if (ts) ts.textContent = 'Last updated ' + this.state.lastFetch.toLocaleTimeString();
        } catch (err) {
            console.error('Dashboard load failed:', err);
            if (errBox) {
                errBox.textContent = 'Unable to load dashboard. ' + (err.message || '');
                errBox.style.display = 'block';
            }
        } finally {
            this.state.loading = false;
        }
    },

    render(data) {
        const safe = (label, fn) => {
            try { fn(); } catch (e) { console.error(`Dashboard ${label} failed:`, e); }
        };
        safe('kpis',          () => this.renderKpis(data.kpis));
        safe('severity',      () => this.renderSeverityDonut(data.severity));
        safe('scanVulns',     () => this.renderScanVulnerabilities(data.scan_vulnerabilities));
        safe('topPorts',      () => this.renderTopPorts(data.top_ports));
        safe('hostStatus',    () => this.renderHostStatus(data.host_status));
        safe('topServices',   () => this.renderTopServices(data.top_services));
        safe('findingsTime',  () => this.renderFindingsOverTime(data.findings_over_time));
        safe('colors',        () => this.renderColorCategories(data.color_categories));
        safe('testExec',      () => this.renderTestExecutions(data.test_executions));
    },

    /* ---------- Helpers ---------- */

    escape(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    },

    emptyState(rootEl, message) {
        rootEl.innerHTML = `<div class="chart-empty">${this.escape(message)}</div>`;
    },

    legendHTML(items) {
        // items: [{label, color, count}]
        return `<div class="chart-legend">${items.map(i => `
            <span class="legend-item">
                <span class="legend-swatch" style="background:${i.color};"></span>
                <span>${this.escape(i.label)}</span>
                <span class="legend-count">${this.escape(i.count)}</span>
            </span>
        `).join('')}</div>`;
    },

    stackedBarHTML(segments, total) {
        // segments: [{label, color, count}], drops zero-count entries; total used for width.
        const visible = segments.filter(s => s.count > 0);
        const bar = `<div class="stacked-bar">${visible.map(s => {
            const pct = (s.count / total * 100);
            const showLabel = pct > 8;  // hide text on tiny segments
            return `<div class="stacked-bar-segment"
                style="width:${pct}%;background:${s.color};color:${s.ink || 'var(--ink-on-bright)'};"
                title="${this.escape(s.label)}: ${s.count} (${pct.toFixed(1)}%)">
                ${showLabel ? this.escape(s.count) : ''}
            </div>`;
        }).join('')}</div>`;
        return bar;
    },

    /* ---------- 1. KPI strip ---------- */

    renderKpis(kpis) {
        const root = document.getElementById('kpiStrip');
        if (!root) return;
        const tiles = [
            { label: 'Hosts',          value: kpis.hosts },
            { label: 'Open ports',     value: kpis.open_ports },
            { label: 'Findings',       value: kpis.findings,
              accent: kpis.findings > 0 ? 'critical' : null },
            { label: 'Credentials',    value: kpis.credentials },
            { label: 'Compromised',    value: kpis.compromised_hosts,
              accent: kpis.compromised_hosts > 0 ? 'success' : null },
            { label: 'Days remaining', value: kpis.days_remaining == null ? '—' : kpis.days_remaining,
              muted: kpis.days_remaining == null },
        ];
        root.innerHTML = tiles.map(t => `
            <div class="kpi-tile${t.accent ? ' accent-' + t.accent : ''}">
                <div class="kpi-label">${this.escape(t.label)}</div>
                <div class="kpi-value measured${t.muted ? ' muted' : ''}">${this.escape(t.value)}</div>
            </div>
        `).join('');
    },

    /* ---------- 2. Severity donut ---------- */

    renderSeverityDonut(rows) {
        const root = document.getElementById('chartSeverity');
        if (!root) return;
        root.innerHTML = '';

        const counts = Object.fromEntries(this.SEVERITY_ORDER.map(k => [k, 0]));
        rows.forEach(r => {
            const k = this.SEVERITY_ORDER.includes(r.label) ? r.label : 'info';
            counts[k] += r.count;
        });
        const total = this.SEVERITY_ORDER.reduce((a, k) => a + counts[k], 0);

        if (total === 0) { this.emptyState(root, 'No findings recorded yet'); return; }

        const frame = document.createElement('div');
        frame.className = 'chart-frame';
        root.appendChild(frame);

        const width = 280, height = 220;
        const radius = Math.min(width, height) / 2 - 8;

        const svg = d3.select(frame).append('svg')
            .attr('class', 'chart-svg')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('width', width).attr('height', height)
            .style('max-width', width + 'px')
            .style('margin', '0 auto');

        const g = svg.append('g').attr('transform', `translate(${width/2},${height/2})`);
        const pie = d3.pie().value(d => d[1]).sort(null).padAngle(0.012);
        const arc = d3.arc().innerRadius(radius * 0.62).outerRadius(radius).cornerRadius(2);
        const data = this.SEVERITY_ORDER.map(k => [k, counts[k]]).filter(d => d[1] > 0);

        g.selectAll('path').data(pie(data)).enter().append('path')
            .attr('d', arc)
            .attr('fill', d => this.severityColor(d.data[0]))
            .append('title').text(d => `${d.data[0]}: ${d.data[1]}`);

        g.append('text').attr('class', 'donut-center-value')
            .attr('text-anchor', 'middle').attr('dy', '0.05em').text(total);
        g.append('text').attr('class', 'donut-center-label')
            .attr('text-anchor', 'middle').attr('dy', '1.7em').text('findings');

        const legend = this.SEVERITY_ORDER.map(k => ({
            label: k, color: this.severityColor(k), count: counts[k],
        }));
        frame.insertAdjacentHTML('beforeend', this.legendHTML(legend));
    },

    /* ---------- 2b. Scan Vulnerabilities (raw counts from imports) ---------- */

    renderScanVulnerabilities(counts) {
        const root = document.getElementById('chartScanVulns');
        if (!root) return;
        root.innerHTML = '';

        const safeCounts = counts || { critical: 0, high: 0, medium: 0, low: 0 };
        const total = (safeCounts.critical || 0)
                    + (safeCounts.high || 0)
                    + (safeCounts.medium || 0)
                    + (safeCounts.low || 0);

        if (total === 0) {
            this.emptyState(root, 'No vulnerability scans imported. Bring in Nessus or Burp output from Tools, then Data.');
            return;
        }

        const tiles = [
            { label: 'Critical', key: 'critical', value: safeCounts.critical || 0 },
            { label: 'High',     key: 'high',     value: safeCounts.high     || 0 },
            { label: 'Medium',   key: 'medium',   value: safeCounts.medium   || 0 },
            { label: 'Low',      key: 'low',      value: safeCounts.low      || 0 },
        ];
        root.innerHTML = `
            <div class="scan-vuln-grid">
                ${tiles.map(t => `
                    <div class="scan-vuln-tile sev-${t.key}">
                        <div class="scan-vuln-value measured">${this.escape(t.value)}</div>
                        <div class="scan-vuln-label">${this.escape(t.label)}</div>
                    </div>
                `).join('')}
            </div>
            <div class="scan-vuln-total"><span class="measured">${total}</span> vulnerabilities across all imported scans</div>
        `;
    },

    /* ---------- 3. Top 15 ports histogram ---------- */

    renderTopPorts(rows) {
        const root = document.getElementById('chartTopPorts');
        if (!root) return;
        root.innerHTML = '';
        if (!rows || rows.length === 0) {
            this.emptyState(root, 'No open ports recorded — import an Nmap scan or add ports manually');
            return;
        }

        const frame = document.createElement('div');
        frame.className = 'chart-frame';
        root.appendChild(frame);

        const margin = { top: 8, right: 8, bottom: 44, left: 36 };
        const width = root.clientWidth || 420;
        const height = 240;
        const innerW = width - margin.left - margin.right;
        const innerH = height - margin.top - margin.bottom;

        const svg = d3.select(frame).append('svg')
            .attr('class', 'chart-svg axis')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('width', width).attr('height', height);
        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleBand().domain(rows.map(r => r.port)).range([0, innerW]).padding(0.18);
        const y = d3.scaleLinear().domain([0, d3.max(rows, r => r.host_count)]).nice().range([innerH, 0]);

        const barColor = this.themeColor('--color-cool');

        g.selectAll('rect').data(rows).enter().append('rect')
            .attr('x', d => x(d.port) + (x.bandwidth() - Math.min(x.bandwidth(), 40)) / 2).attr('y', d => y(d.host_count))
            .attr('width', Math.min(x.bandwidth(), 40)).attr('height', d => innerH - y(d.host_count))
            .attr('rx', 2)
            .attr('fill', barColor)
            .append('title').text(d => `Port ${d.port}${d.service ? ' · ' + d.service : ''}: ${d.host_count} host(s)`);

        g.append('g')
            .attr('transform', `translate(0,${innerH})`)
            .call(d3.axisBottom(x).tickSize(0).tickPadding(6))
            .selectAll('text')
                .attr('transform', 'translate(-4,4) rotate(-45)')
                .style('text-anchor', 'end');
        g.append('g')
            .call(d3.axisLeft(y).ticks(Math.min(4, y.domain()[1])).tickFormat(d3.format('d')).tickSize(0).tickPadding(6))
            .call(g => g.select('.domain').remove());
    },

    /* ---------- 4. Host status stacked bar ---------- */

    renderHostStatus(s) {
        const root = document.getElementById('chartHostStatus');
        if (!root) return;
        root.innerHTML = '';
        if (!s || s.total === 0) {
            this.emptyState(root, 'No hosts in this engagement yet');
            return;
        }

        const segments = [
            { label: 'Rooted',       color: this.themeColor('--color-critical'), count: s.rooted },
            { label: 'Shell Only',   color: this.themeColor('--color-high'),     count: s.shell_only },
            { label: 'Reviewed',     color: this.themeColor('--color-success'),  count: s.reviewed },
            { label: 'Flagged',      color: this.themeColor('--color-medium'),   count: s.flagged },
            { label: 'Out of Scope', color: this.themeColor('--color-text-tertiary'), count: s.out_of_scope, ink: 'var(--color-paper)' },
            { label: 'Untouched',    color: this.themeColor('--color-bg-tertiary'),   count: s.untouched, ink: 'var(--color-ink)' },
        ];

        root.insertAdjacentHTML('beforeend', this.stackedBarHTML(segments, s.total));
        root.insertAdjacentHTML('beforeend', this.legendHTML(segments.filter(seg => seg.count > 0)));
    },

    /* ---------- 5. Top services bar ---------- */

    renderTopServices(rows) {
        const root = document.getElementById('chartTopServices');
        if (!root) return;
        root.innerHTML = '';
        if (!rows || rows.length === 0) {
            this.emptyState(root, 'No services discovered yet');
            return;
        }

        const frame = document.createElement('div');
        frame.className = 'chart-frame';
        root.appendChild(frame);

        const margin = { top: 4, right: 28, bottom: 4, left: 86 };
        const width = root.clientWidth || 420;
        const rowH = 22;
        const innerW = width - margin.left - margin.right;
        const innerH = rows.length * rowH;
        const height = margin.top + margin.bottom + innerH;

        const svg = d3.select(frame).append('svg')
            .attr('class', 'chart-svg axis')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('width', width).attr('height', height);
        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const y = d3.scaleBand().domain(rows.map(r => r.service)).range([0, innerH]).padding(0.25);
        const x = d3.scaleLinear().domain([0, d3.max(rows, r => r.host_count)]).nice().range([0, innerW]);

        const barColor = this.themeColor('--color-cool');

        g.selectAll('rect').data(rows).enter().append('rect')
            .attr('y', d => y(d.service)).attr('x', 0)
            .attr('width', d => Math.max(2, x(d.host_count))).attr('height', y.bandwidth())
            .attr('rx', 2)
            .attr('fill', barColor)
            .attr('opacity', 0.85)
            .append('title').text(d => `${d.service}: ${d.host_count} host(s)`);

        g.selectAll('text.svc-label').data(rows).enter().append('text')
            .attr('class', 'svc-label')
            .attr('y', d => y(d.service) + y.bandwidth()/2 + 3)
            .attr('x', -10).attr('text-anchor', 'end')
            .style('font-size', '11px')
            .style('fill', this.themeColor('--color-text-secondary'))
            .text(d => d.service.length > 14 ? d.service.slice(0, 13) + '…' : d.service);

        g.selectAll('text.svc-value').data(rows).enter().append('text')
            .attr('class', 'svc-value')
            .attr('y', d => y(d.service) + y.bandwidth()/2 + 3)
            .attr('x', d => x(d.host_count) + 6)
            .style('font-size', '11px')
            .style('font-variant-numeric', 'tabular-nums')
            .style('fill', this.themeColor('--color-text-tertiary'))
            .text(d => d.host_count);
    },

    /* ---------- 6. Findings over time line ---------- */

    renderFindingsOverTime(rows) {
        const root = document.getElementById('chartFindingsTime');
        if (!root) return;
        root.innerHTML = '';
        if (!rows || rows.length === 0) {
            this.emptyState(root, 'No findings logged yet');
            return;
        }

        const frame = document.createElement('div');
        frame.className = 'chart-frame';
        root.appendChild(frame);

        const parsed = rows.map(r => ({ day: new Date(r.day + 'T00:00:00'), cumulative: r.cumulative }));

        const margin = { top: 8, right: 12, bottom: 28, left: 32 };
        const width = root.clientWidth || 420;
        const height = 220;
        const innerW = width - margin.left - margin.right;
        const innerH = height - margin.top - margin.bottom;

        const svg = d3.select(frame).append('svg')
            .attr('class', 'chart-svg axis')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('width', width).attr('height', height);
        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        // For a single-day series, give the line some horizontal extent.
        const xDomain = parsed.length === 1
            ? [d3.timeDay.offset(parsed[0].day, -1), d3.timeDay.offset(parsed[0].day, 1)]
            : d3.extent(parsed, d => d.day);

        const x = d3.scaleTime().domain(xDomain).range([0, innerW]);
        const y = d3.scaleLinear().domain([0, d3.max(parsed, d => d.cumulative) || 1]).nice().range([innerH, 0]);

        const line = d3.line().x(d => x(d.day)).y(d => y(d.cumulative)).curve(d3.curveMonotoneX);
        const area = d3.area().x(d => x(d.day)).y0(innerH).y1(d => y(d.cumulative)).curve(d3.curveMonotoneX);

        const accent = this.themeColor('--color-primary');

        // Soft area fill via gradient
        const gradId = 'dashFindingsFill';
        const defs = svg.append('defs');
        const gradient = defs.append('linearGradient')
            .attr('id', gradId).attr('x1', 0).attr('x2', 0).attr('y1', 0).attr('y2', 1);
        gradient.append('stop').attr('offset', '0%').attr('stop-color', accent).attr('stop-opacity', 0.35);
        gradient.append('stop').attr('offset', '100%').attr('stop-color', accent).attr('stop-opacity', 0);

        g.append('path').datum(parsed).attr('fill', `url(#${gradId})`).attr('d', area);
        g.append('path').datum(parsed)
            .attr('fill', 'none').attr('stroke', accent).attr('stroke-width', 2).attr('d', line);

        g.selectAll('circle').data(parsed).enter().append('circle')
            .attr('cx', d => x(d.day)).attr('cy', d => y(d.cumulative))
            .attr('r', 3).attr('fill', this.themeColor('--color-bg-primary'))
            .attr('stroke', accent).attr('stroke-width', 2)
            .append('title').text(d => `${d.day.toISOString().slice(0,10)}: ${d.cumulative} cumulative`);

        g.append('g').attr('transform', `translate(0,${innerH})`)
            .call(d3.axisBottom(x).ticks(Math.min(parsed.length, 5)).tickSize(0).tickPadding(6).tickFormat(d3.timeFormat('%b %d')))
            .call(g => g.select('.domain').remove());
        g.append('g')
            .call(d3.axisLeft(y).ticks(Math.min(d3.max(parsed, d => d.cumulative) || 1, 4)).tickSize(0).tickPadding(6))
            .call(g => g.select('.domain').remove());
    },

    /* ---------- 7. Color categories ---------- */

    renderColorCategories(rows) {
        const root = document.getElementById('chartColors');
        if (!root) return;
        root.innerHTML = '';

        const total = rows.reduce((a, r) => a + r.count, 0);
        if (total === 0) {
            this.emptyState(root, 'No hosts in this engagement');
            return;
        }

        const segments = rows.map(r => ({
            label: r.color || 'Uncategorized',
            color: r.color
                ? (this.COLOR_CATEGORY_HEX[r.color] || this.themeColor('--color-text-tertiary'))
                : this.themeColor('--color-bg-tertiary'),
            count: r.count,
        }));

        root.insertAdjacentHTML('beforeend', this.stackedBarHTML(segments, total));
        root.insertAdjacentHTML('beforeend', this.legendHTML(segments));
    },

    /* ---------- 8. Test execution progress ---------- */

    renderTestExecutions(t) {
        const card = document.getElementById('cardTestExec');
        const root = document.getElementById('chartTestExec');
        if (!card || !root) return;

        if (!t || t.total === 0) {
            card.style.display = 'none';
            return;
        }
        card.style.display = '';
        root.innerHTML = '';

        const STATUS_COLORS = {
            pending:     this.themeColor('--color-text-tertiary'),
            in_progress: this.themeColor('--color-primary'),
            passed:      this.themeColor('--color-success'),
            failed:      this.themeColor('--color-critical'),
            skipped:     this.themeColor('--color-warning'),
        };

        const segments = t.by_status.map(s => ({
            label: s.status,
            count: s.count,
            color: STATUS_COLORS[s.status] || this.themeColor('--color-text-tertiary'),
        }));

        const completed = (t.by_status.find(s => s.status === 'passed')?.count || 0)
                        + (t.by_status.find(s => s.status === 'failed')?.count || 0);
        const pct = t.total > 0 ? Math.round((completed / t.total) * 100) : 0;

        root.insertAdjacentHTML('beforeend', this.stackedBarHTML(segments, t.total));
        root.insertAdjacentHTML('beforeend',
            `<div class="test-exec-summary"><strong>${completed}</strong> of <strong>${t.total}</strong> tests completed (${pct}%)</div>`);
        root.insertAdjacentHTML('beforeend', this.legendHTML(segments));
    },
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => Dashboard.init());
} else {
    Dashboard.init();
}
