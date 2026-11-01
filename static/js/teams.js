/**
 * PTVault Team Management
 * Handles team administration and team membership management
 */
const TeamManager = {
    teams: [],
    allUsers: [],
    currentTeamId: null,
    currentMembers: [],

    /**
     * Initialize team manager
     */
    async init() {
        await this.loadTeams();
    },

    /**
     * Load all teams
     */
    async loadTeams() {
        try {
            this.teams = await API.teams.getAll();
            this.renderTeamsList();
        } catch (error) {
            console.error('Failed to load teams:', error);
            showToast('Failed to load teams', 'error');
        }
    },

    /**
     * Load all users for member assignment
     */
    async loadAllUsers() {
        try {
            this.allUsers = await API.users.getAll();
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    },

    /**
     * Render teams list
     */
    renderTeamsList() {
        const container = document.getElementById('teamsList');
        if (!container) return;

        if (this.teams.length === 0) {
            container.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No teams created yet</p>';
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Description</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.teams.map(team => `
                        <tr>
                            <td>
                                <button class="text-blue-600 dark:text-blue-400 hover:underline font-medium"
                                        onclick="TeamManager.showTeamMembers(${team.id})">
                                    ${escapeHtml(team.name)}
                                </button>
                            </td>
                            <td>${escapeHtml(team.description || '')}</td>
                            <td>${team.created_at ? formatDate(team.created_at) : ''}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn btn-icon btn-sm" onclick="TeamManager.editTeam(${team.id})" title="Edit">
                                        <i data-lucide="edit-2" class="icon-sm"></i>
                                    </button>
                                    <button class="btn btn-icon btn-sm" onclick="TeamManager.showTeamMembers(${team.id})" title="Members">
                                        <i data-lucide="users" class="icon-sm"></i>
                                    </button>
                                    <button class="btn btn-icon btn-sm btn-danger" onclick="TeamManager.deleteTeam(${team.id})" title="Delete">
                                        <i data-lucide="trash-2" class="icon-sm"></i>
                                    </button>
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
     * Show inline team form for adding
     */
    showTeamForm(teamId) {
        const formCard = document.getElementById('teamFormCard');
        if (!formCard) return;

        if (teamId) {
            const team = this.teams.find(t => t.id === teamId);
            if (!team) return;

            document.getElementById('teamFormTitle').textContent = 'Edit Team';
            document.getElementById('teamId').value = team.id;
            document.getElementById('teamName').value = team.name;
            document.getElementById('teamDescription').value = team.description || '';
        } else {
            document.getElementById('teamFormTitle').textContent = 'Create Team';
            document.getElementById('teamId').value = '';
            document.getElementById('teamName').value = '';
            document.getElementById('teamDescription').value = '';
        }

        formCard.style.display = 'block';
    },

    /**
     * Hide inline team form
     */
    hideTeamForm() {
        const formCard = document.getElementById('teamFormCard');
        if (formCard) {
            formCard.style.display = 'none';
        }
    },

    /**
     * Edit team - show inline form
     */
    editTeam(teamId) {
        this.showTeamForm(teamId);
    },

    /**
     * Save team (create or update)
     */
    async saveTeam() {
        const teamId = document.getElementById('teamId').value;
        const name = document.getElementById('teamName').value.trim();
        const description = document.getElementById('teamDescription').value.trim();

        if (!name) {
            showToast('Team name is required', 'error');
            return;
        }

        const data = { name, description };

        try {
            if (teamId) {
                await API.teams.update(parseInt(teamId), data);
                showToast('Team updated', 'success');
            } else {
                await API.teams.create(data);
                showToast('Team created', 'success');
            }

            this.hideTeamForm();
            await this.loadTeams();
        } catch (error) {
            console.error('Failed to save team:', error);
            showToast(error.message || 'Failed to save team', 'error');
        }
    },

    /**
     * Delete team
     */
    async deleteTeam(teamId) {
        const team = this.teams.find(t => t.id === teamId);
        if (!team) return;

        if (!confirm(`Delete team "${team.name}"? Engagements assigned to this team will become unassigned.`)) {
            return;
        }

        try {
            await API.teams.delete(teamId);
            showToast('Team deleted', 'success');
            await this.loadTeams();

            // Clear members panel if viewing this team
            if (this.currentTeamId === teamId) {
                this.currentTeamId = null;
                const panel = document.getElementById('teamMembersPanel');
                if (panel) panel.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to delete team:', error);
            showToast('Failed to delete team', 'error');
        }
    },

    /**
     * Show team members panel
     */
    async showTeamMembers(teamId) {
        this.currentTeamId = teamId;
        const team = this.teams.find(t => t.id === teamId);

        const panel = document.getElementById('teamMembersPanel');
        if (panel) panel.style.display = 'block';

        const title = document.getElementById('teamMembersPanelTitle');
        if (title) title.textContent = `Members: ${team ? team.name : ''}`;

        await this.loadAllUsers();
        await this.loadTeamMembers(teamId);
    },

    /**
     * Load team members
     */
    async loadTeamMembers(teamId) {
        try {
            this.currentMembers = await API.teams.getMembers(teamId);
            this.renderTeamMembers();
        } catch (error) {
            console.error('Failed to load team members:', error);
            showToast('Failed to load team members', 'error');
        }
    },

    /**
     * Render team members
     */
    renderTeamMembers() {
        const container = document.getElementById('teamMembersList');
        if (!container) return;

        if (this.currentMembers.length === 0) {
            container.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No members in this team</p>';
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
                    ${this.currentMembers.map(member => `
                        <tr>
                            <td>${escapeHtml(member.username || '')}</td>
                            <td>${escapeHtml(member.email || 'N/A')}</td>
                            <td>
                                <select class="form-input form-input-sm"
                                        onchange="TeamManager.updateMemberRole(${member.id}, this.value)"
                                        style="width: auto;">
                                    <option value="lead" ${member.role === 'lead' ? 'selected' : ''}>Lead</option>
                                    <option value="member" ${member.role === 'member' ? 'selected' : ''}>Member</option>
                                </select>
                            </td>
                            <td>
                                <button class="btn btn-icon btn-sm btn-danger"
                                        onclick="TeamManager.removeMember(${member.id})"
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
     * Show inline member form
     */
    showMemberForm() {
        if (!this.currentTeamId) {
            showToast('No team selected', 'error');
            return;
        }

        const memberUserIds = this.currentMembers.map(m => m.user_id);
        const availableUsers = this.allUsers.filter(u => !memberUserIds.includes(u.id) && u.is_active);

        if (availableUsers.length === 0) {
            showToast('All active users are already team members', 'info');
            return;
        }

        const userSelect = document.getElementById('teamMemberUserId');
        userSelect.innerHTML = availableUsers.map(user =>
            `<option value="${user.id}">${escapeHtml(user.username)} (${escapeHtml(user.email || 'No email')})</option>`
        ).join('');

        document.getElementById('teamMemberRole').value = 'member';

        const formCard = document.getElementById('teamMemberFormCard');
        if (formCard) formCard.style.display = 'block';
    },

    /**
     * Hide inline member form
     */
    hideMemberForm() {
        const formCard = document.getElementById('teamMemberFormCard');
        if (formCard) formCard.style.display = 'none';
    },

    /**
     * Save team member (add to team)
     */
    async saveTeamMember() {
        const userId = parseInt(document.getElementById('teamMemberUserId').value);
        const role = document.getElementById('teamMemberRole').value;

        if (!userId || !role) {
            showToast('User and role are required', 'error');
            return;
        }

        try {
            await API.teams.addMember(this.currentTeamId, {
                user_id: userId,
                role: role
            });

            showToast('Member added to team', 'success');
            this.hideMemberForm();
            await this.loadTeamMembers(this.currentTeamId);
        } catch (error) {
            console.error('Failed to add team member:', error);
            showToast(error.message || 'Failed to add team member', 'error');
        }
    },

    /**
     * Update team member role
     */
    async updateMemberRole(memberId, newRole) {
        try {
            await API.teams.updateMember(this.currentTeamId, memberId, { role: newRole });
            showToast('Role updated', 'success');
            await this.loadTeamMembers(this.currentTeamId);
        } catch (error) {
            console.error('Failed to update role:', error);
            showToast('Failed to update role', 'error');
            await this.loadTeamMembers(this.currentTeamId);
        }
    },

    /**
     * Remove member from team
     */
    async removeMember(memberId) {
        if (!confirm('Remove this member from the team?')) {
            return;
        }

        try {
            await API.teams.removeMember(this.currentTeamId, memberId);
            showToast('Member removed', 'success');
            await this.loadTeamMembers(this.currentTeamId);
        } catch (error) {
            console.error('Failed to remove member:', error);
            showToast('Failed to remove member', 'error');
        }
    },

    /**
     * Get teams for dropdown population (e.g., engagement create/edit)
     */
    getTeamsForSelect() {
        return this.teams;
    }
};

// Make available globally
window.TeamManager = TeamManager;
