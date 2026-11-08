/**
 * PTVault Client Management
 *
 * Admin-only CRUD for the Clients database. Uses the same inline-form +
 * table pattern as UserManager / TeamManager so the look matches the
 * rest of the admin panel.
 */
const ClientManager = {
    clients: [],

    async loadClients() {
        try {
            this.clients = await API.clients.getAll();
            this.renderClientsList();
        } catch (error) {
            console.error('Failed to load clients:', error);
            showToast('Failed to load clients', 'error');
        }
    },

    renderClientsList() {
        const container = document.getElementById('clientsList');
        if (!container) return;

        if (this.clients.length === 0) {
            container.innerHTML = '<p class="empty-text">No clients yet. Click + Add Client to create one.</p>';
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Admin Contact</th>
                        <th>Technical Contact</th>
                        <th>Website</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.clients.map(client => `
                        <tr>
                            <td><strong>${escapeHtml(client.name)}</strong></td>
                            <td>${this.renderContactCell(client.admin_contact_name, client.admin_contact_email)}</td>
                            <td>${this.renderContactCell(client.technical_contact_name, client.technical_contact_email)}</td>
                            <td>${client.website ? `<a href="${escapeHtml(safeUrl(client.website))}" target="_blank" rel="noopener noreferrer">${escapeHtml(client.website)}</a>` : '<span class="text-muted">—</span>'}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn btn-icon btn-sm" ${on('click', 'ClientManager.editClient', client.id)} title="Edit">
                                        <i data-lucide="edit-2" class="icon-sm"></i>
                                    </button>
                                    <button class="btn btn-icon btn-sm btn-danger" ${on('click', 'ClientManager.deleteClient', client.id)} title="Delete">
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

    renderContactCell(name, email) {
        if (!name && !email) return '<span class="text-muted">—</span>';
        const parts = [];
        if (name) parts.push(escapeHtml(name));
        if (email) parts.push(`<a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>`);
        return parts.join('<br>');
    },

    showClientForm(clientId) {
        const formCard = document.getElementById('clientFormCard');
        if (!formCard) return;

        if (clientId) {
            const client = this.clients.find(c => c.id === clientId);
            if (!client) return;

            document.getElementById('clientFormTitle').textContent = 'Edit Client';
            document.getElementById('clientId').value = client.id;
            document.getElementById('clientName').value = client.name || '';
            document.getElementById('clientAdminName').value = client.admin_contact_name || '';
            document.getElementById('clientAdminEmail').value = client.admin_contact_email || '';
            document.getElementById('clientAdminPhone').value = client.admin_contact_phone || '';
            document.getElementById('clientTechName').value = client.technical_contact_name || '';
            document.getElementById('clientTechEmail').value = client.technical_contact_email || '';
            document.getElementById('clientTechPhone').value = client.technical_contact_phone || '';
            document.getElementById('clientAddress').value = client.address || '';
            document.getElementById('clientWebsite').value = client.website || '';
            document.getElementById('clientNotes').value = client.notes || '';
        } else {
            document.getElementById('clientFormTitle').textContent = 'Add Client';
            document.getElementById('clientId').value = '';
            ['clientName', 'clientAdminName', 'clientAdminEmail', 'clientAdminPhone',
             'clientTechName', 'clientTechEmail', 'clientTechPhone',
             'clientAddress', 'clientWebsite', 'clientNotes'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        }

        formCard.style.display = 'block';
        document.getElementById('clientName').focus();
    },

    hideClientForm() {
        const formCard = document.getElementById('clientFormCard');
        if (formCard) formCard.style.display = 'none';
    },

    editClient(clientId) {
        this.showClientForm(clientId);
    },

    async saveClient() {
        const id = document.getElementById('clientId').value;
        const name = document.getElementById('clientName').value.trim();

        if (!name) {
            showToast('Name is required', 'error');
            return;
        }

        const payload = {
            name,
            admin_contact_name: document.getElementById('clientAdminName').value.trim(),
            admin_contact_email: document.getElementById('clientAdminEmail').value.trim(),
            admin_contact_phone: document.getElementById('clientAdminPhone').value.trim(),
            technical_contact_name: document.getElementById('clientTechName').value.trim(),
            technical_contact_email: document.getElementById('clientTechEmail').value.trim(),
            technical_contact_phone: document.getElementById('clientTechPhone').value.trim(),
            address: document.getElementById('clientAddress').value.trim(),
            website: document.getElementById('clientWebsite').value.trim(),
            notes: document.getElementById('clientNotes').value.trim(),
        };

        try {
            if (id) {
                await API.clients.update(parseInt(id, 10), payload);
                showToast('Client updated', 'success');
            } else {
                await API.clients.create(payload);
                showToast('Client created', 'success');
            }
            this.hideClientForm();
            await this.loadClients();
        } catch (error) {
            console.error('Failed to save client:', error);
            showToast(error.message || 'Failed to save client', 'error');
        }
    },

    async deleteClient(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        if (!confirm(`Delete client "${client.name}"? This cannot be undone.`)) {
            return;
        }

        try {
            await API.clients.delete(clientId);
            showToast('Client deleted', 'success');
            await this.loadClients();
        } catch (error) {
            // The route returns 409 with engagement_count when blocked.
            // Surface the full message so the admin knows what to do.
            console.error('Failed to delete client:', error);
            const msg = error.message || 'Failed to delete client';
            showToast(msg, 'error');
        }
    },
};

// Make available globally
window.ClientManager = ClientManager;
