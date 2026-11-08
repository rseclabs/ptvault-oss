/**
 * PTVault User Management
 * Handles user administration and engagement team member management
 */
const UserManager = {
    users: [],
    currentEngagementMembers: [],
    currentEngagementId: null,

    /**
     * Initialize user manager
     */
    async init() {
        await this.loadUsers();
        this.setupEventListeners();
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Add member button (engagement members - still modal-based)
        const addMemberBtn = document.getElementById('addMemberBtn');
        if (addMemberBtn) {
            addMemberBtn.addEventListener('click', () => this.showAddMemberModal());
        }

        // Member form submit
        const memberForm = document.getElementById('memberForm');
        if (memberForm) {
            memberForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveMember();
            });
        }
    },

    /**
     * Load all users
     */
    async loadUsers() {
        try {
            this.users = await API.users.getAll();
            this.renderUsersList();
        } catch (error) {
            console.error('Failed to load users:', error);
            showToast('Failed to load users', 'error');
        }
    },

    /**
     * Render users list
     */
    renderUsersList() {
        const container = document.getElementById('usersList');
        if (!container) return;

        if (this.users.length === 0) {
            container.innerHTML = '<p class="empty-text">No users found</p>';
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Last Login</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.users.map(user => `
                        <tr>
                            <td>${escapeHtml(user.username)}</td>
                            <td>${escapeHtml(user.email || 'N/A')}</td>
                            <td>${this.renderRoleBadge(user.role)}</td>
                            <td>${this.renderStatusBadge(user.is_active)}</td>
                            <td>${user.last_login ? formatDate(user.last_login) : 'Never'}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn btn-icon btn-sm" ${on('click', 'UserManager.editUser', user.id)} title="Edit">
                                        <i data-lucide="edit-2" class="icon-sm"></i>
                                    </button>
                                    ${user.is_active ? `
                                        <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'UserManager.deleteUser', user.id)} title="Delete">
                                            <i data-lucide="trash-2" class="icon-sm"></i>
                                        </button>
                                    ` : `
                                        <button class="btn btn-icon btn-sm btn-success" ${on('click', 'UserManager.reactivateUser', user.id)} title="Reactivate">
                                            <i data-lucide="user-check" class="icon-sm"></i>
                                        </button>
                                    `}
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        container.innerHTML = html;

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render role badge
     */
    renderRoleBadge(role) {
        const badges = {
            admin: '<span class="badge badge-danger">Admin</span>',
            tester: '<span class="badge badge-primary">Tester</span>',
            viewer: '<span class="badge badge-secondary">Viewer</span>'
        };
        return badges[role] || '<span class="badge badge-secondary">Unknown</span>';
    },

    /**
     * Render status badge
     */
    renderStatusBadge(isActive) {
        if (isActive) {
            return '<span class="badge badge-success">Active</span>';
        }
        return '<span class="badge badge-secondary">Inactive</span>';
    },

    /**
     * Show inline user form for adding
     */
    showUserForm(userId) {
        const formCard = document.getElementById('userFormCard');
        if (!formCard) return;

        if (userId) {
            // Edit mode
            const user = this.users.find(u => u.id === userId);
            if (!user) return;

            document.getElementById('userFormTitle').textContent = 'Edit User';
            document.getElementById('userId').value = user.id;
            document.getElementById('username').value = user.username;
            document.getElementById('username').disabled = true;
            document.getElementById('email').value = user.email || '';
            document.getElementById('userRole').value = user.role;
            document.getElementById('password').value = '';
            this.setCurrentPasswordVisible(user.id === AppState.currentUser?.id);

            const passwordLabel = document.querySelector('#passwordGroup label');
            if (passwordLabel) {
                passwordLabel.textContent = 'Password (leave blank to keep current)';
            }
        } else {
            // Add mode
            document.getElementById('userFormTitle').textContent = 'Add User';
            document.getElementById('userId').value = '';
            document.getElementById('username').value = '';
            document.getElementById('username').disabled = false;
            document.getElementById('email').value = '';
            document.getElementById('userRole').value = 'tester';
            document.getElementById('password').value = '';
            this.setCurrentPasswordVisible(false);

            const passwordLabel = document.querySelector('#passwordGroup label');
            if (passwordLabel) {
                passwordLabel.textContent = 'Password *';
            }
        }

        formCard.style.display = 'block';
    },

    /**
     * Show the current-password field only when editing your own account
     */
    setCurrentPasswordVisible(visible) {
        const group = document.getElementById('currentPasswordGroup');
        const input = document.getElementById('currentPassword');
        if (group) group.style.display = visible ? 'flex' : 'none';
        if (input) input.value = '';
    },

    /**
     * Hide inline user form
     */
    hideUserForm() {
        const formCard = document.getElementById('userFormCard');
        if (formCard) {
            formCard.style.display = 'none';
        }
        // Reset username field
        const usernameField = document.getElementById('username');
        if (usernameField) usernameField.disabled = false;
    },

    /**
     * Edit user - show inline form
     */
    editUser(userId) {
        this.showUserForm(userId);
    },

    /**
     * Save user (create or update)
     */
    async saveUser() {
        const userId = document.getElementById('userId').value;
        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const role = document.getElementById('userRole').value;
        const password = document.getElementById('password').value;

        if (!username || !email || !role) {
            showToast('Username, email, and role are required', 'error');
            return;
        }

        const data = { username, email, role };

        if (password) {
            data.password = password;
            if (userId && parseInt(userId) === AppState.currentUser?.id) {
                const currentPassword = document.getElementById('currentPassword')?.value || '';
                if (!currentPassword) {
                    showToast('Enter your current password to change it', 'error');
                    return;
                }
                data.current_password = currentPassword;
            }
        } else if (!userId) {
            showToast('Password is required for new users', 'error');
            return;
        }

        try {
            if (userId) {
                await API.users.update(parseInt(userId), data);
                showToast('User updated successfully', 'success');
            } else {
                await API.users.create(data);
                showToast('User created successfully', 'success');
            }

            this.hideUserForm();
            await this.loadUsers();
        } catch (error) {
            console.error('Failed to save user:', error);
            showToast(error.message || 'Failed to save user', 'error');
        }
    },

    /**
     * Permanently delete user
     */
    async deleteUser(userId) {
        const user = this.users.find(u => u.id === userId);
        const label = user ? user.username : 'this user';
        if (!confirm(`Permanently delete ${label}? This cannot be undone.`)) {
            return;
        }

        try {
            await API.users.delete(userId);
            showToast('User deleted', 'success');
            await this.loadUsers();
        } catch (error) {
            console.error('Failed to delete user:', error);
            showToast(error.message || 'Failed to delete user', 'error');
        }
    },

    /**
     * Reactivate user
     */
    async reactivateUser(userId) {
        try {
            await API.users.reactivate(userId);
            showToast('User reactivated', 'success');
            await this.loadUsers();
        } catch (error) {
            console.error('Failed to reactivate user:', error);
            showToast('Failed to reactivate user', 'error');
        }
    },

    // ==================== Engagement Team Members ====================

    /**
     * Load engagement members
     */
    async loadEngagementMembers(engagementId) {
        this.currentEngagementId = engagementId;

        try {
            this.currentEngagementMembers = await API.users.getEngagementMembers(engagementId);
            this.renderMembersList();
        } catch (error) {
            console.error('Failed to load engagement members:', error);
            showToast('Failed to load team members', 'error');
        }
    },

    /**
     * Render engagement members list
     */
    renderMembersList() {
        const container = document.getElementById('membersList');
        if (!container) return;

        if (this.currentEngagementMembers.length === 0) {
            container.innerHTML = '<p class="empty-text">No team members assigned</p>';
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.currentEngagementMembers.map(member => `
                        <tr>
                            <td>${escapeHtml(member.username)}</td>
                            <td>${escapeHtml(member.email || 'N/A')}</td>
                            <td>
                                <select class="form-input form-input-sm"
                                        ${on('change', 'UserManager.updateMemberRoleInline', member.member_id, ARG.value)}
                                        style="width: auto;">
                                    <option value="owner" ${member.member_role === 'owner' ? 'selected' : ''}>Owner</option>
                                    <option value="editor" ${member.member_role === 'editor' ? 'selected' : ''}>Editor</option>
                                    <option value="viewer" ${member.member_role === 'viewer' ? 'selected' : ''}>Viewer</option>
                                </select>
                            </td>
                            <td>
                                <button class="btn btn-icon btn-sm btn-danger"
                                        ${on('click', 'UserManager.removeMember', member.member_id)}
                                        title="Remove from team">
                                    <i data-lucide="user-minus" class="icon-sm"></i>
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        container.innerHTML = html;

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Show add member modal (engagement members - still uses modal)
     */
    showAddMemberModal() {
        if (!this.currentEngagementId) {
            showToast('No engagement selected', 'error');
            return;
        }

        const memberUserIds = this.currentEngagementMembers.map(m => m.user_id);
        const availableUsers = this.users.filter(u => !memberUserIds.includes(u.id) && u.is_active);

        if (availableUsers.length === 0) {
            showToast('All active users are already team members', 'info');
            return;
        }

        const userSelect = document.getElementById('memberUserId');
        userSelect.innerHTML = availableUsers.map(user =>
            `<option value="${user.id}">${escapeHtml(user.username)} (${escapeHtml(user.email || 'No email')})</option>`
        ).join('');

        document.getElementById('memberRole').value = 'editor';
        openModal('memberModal');
    },

    /**
     * Save member (add to engagement)
     */
    async saveMember() {
        const userId = parseInt(document.getElementById('memberUserId').value);
        const role = document.getElementById('memberRole').value;

        if (!userId || !role) {
            showToast('User and role are required', 'error');
            return;
        }

        try {
            await API.users.addEngagementMember(this.currentEngagementId, {
                user_id: userId,
                role: role
            });

            showToast('Team member added', 'success');
            closeModal('memberModal');
            await this.loadEngagementMembers(this.currentEngagementId);
        } catch (error) {
            console.error('Failed to add member:', error);
            showToast(error.message || 'Failed to add team member', 'error');
        }
    },

    /**
     * Update member role inline
     */
    async updateMemberRoleInline(memberId, newRole) {
        try {
            await API.users.updateMemberRole(this.currentEngagementId, memberId, { role: newRole });
            showToast('Role updated', 'success');
            await this.loadEngagementMembers(this.currentEngagementId);
        } catch (error) {
            console.error('Failed to update role:', error);
            showToast('Failed to update role', 'error');
            await this.loadEngagementMembers(this.currentEngagementId);
        }
    },

    /**
     * Remove member from engagement
     */
    async removeMember(memberId) {
        if (!confirm('Remove this team member from the engagement?')) {
            return;
        }

        try {
            await API.users.removeMember(this.currentEngagementId, memberId);
            showToast('Team member removed', 'success');
            await this.loadEngagementMembers(this.currentEngagementId);
        } catch (error) {
            console.error('Failed to remove member:', error);
            showToast('Failed to remove team member', 'error');
        }
    }
};

// Make available globally
window.UserManager = UserManager;
