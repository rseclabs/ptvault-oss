/**
 * PTVault Command Manager
 * Handles command database feature
 */

const CommandManager = {
    commands: [],
    categories: [],
    selectedCategory: 'all',
    searchQuery: '',
    showFavoritesOnly: false,
    activeCommand: null,  // For variable substitution modal
    initialized: false,   // Track initialization state

    // Category definitions with icons
    CATEGORIES: {
        'Recon': { icon: '🔍', description: 'Reconnaissance and information gathering' },
        'Enumeration': { icon: '📋', description: 'Service and user enumeration' },
        'Exploitation': { icon: '💥', description: 'Exploitation and access' },
        'Post-exploitation': { icon: '🔓', description: 'Privilege escalation and persistence' },
        'Reporting': { icon: '📝', description: 'Documentation and reporting' }
    },

    /**
     * Initialize command manager
     */
    async init() {
        try {
            await this.loadCommands();
            await this.loadCategories();
            this.renderCategoryTabs();
            this.renderCommandList();
            this.setupEventListeners();
        } catch (error) {
            console.error('Failed to initialize CommandManager:', error);
            showToast('Failed to load commands', 'error');
        }
    },

    /**
     * Load commands from API
     */
    async loadCommands() {
        const filters = {
            category: this.selectedCategory,
            search: this.searchQuery,
            is_favorite: this.showFavoritesOnly
        };
        this.commands = await API.commands.getAll(filters);
    },

    /**
     * Load categories from API
     */
    async loadCategories() {
        const result = await API.commands.getCategories();
        this.categories = result.categories;
        this.totalCount = result.total;
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Search input
        const searchInput = document.getElementById('commandSearch');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.handleSearch(e.target.value);
            }, 300));
        }

        // Command form
        const commandForm = document.getElementById('commandForm');
        if (commandForm) {
            commandForm.addEventListener('submit', (e) => this.handleCommandSubmit(e));
        }

        // Variable form
        const variableForm = document.getElementById('variableForm');
        if (variableForm) {
            variableForm.addEventListener('submit', (e) => this.handleVariableSubmit(e));
        }
    },

    /**
     * Debounce helper
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Render category tabs/sidebar
     */
    renderCategoryTabs() {
        const container = document.getElementById('commandCategories');
        if (!container) return;

        let html = `
            <div class="category-item ${this.selectedCategory === 'all' ? 'active' : ''}"
                 onclick="CommandManager.filterByCategory('all')">
                <span class="category-icon">📚</span>
                <span class="category-name">All Commands</span>
                <span class="category-count">${this.totalCount || 0}</span>
            </div>
        `;

        for (const cat of this.categories) {
            const catInfo = this.CATEGORIES[cat.name] || { icon: '📁' };
            const isActive = this.selectedCategory === cat.name;
            html += `
                <div class="category-item ${isActive ? 'active' : ''}"
                     onclick="CommandManager.filterByCategory('${cat.name}')">
                    <span class="category-icon">${catInfo.icon}</span>
                    <span class="category-name">${cat.name}</span>
                    <span class="category-count">${cat.count}</span>
                </div>
            `;
        }

        container.innerHTML = html;
    },

    /**
     * Render command list as compact rows
     */
    renderCommandList() {
        const container = document.getElementById('commandsList');
        const countEl = document.getElementById('commandsCount');
        if (!container) return;

        if (countEl) {
            countEl.textContent = `${this.commands.length} command${this.commands.length !== 1 ? 's' : ''}`;
        }

        if (this.commands.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No commands found</p>
                    ${this.searchQuery ? '<p class="hint">Try a different search term</p>' : ''}
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="commands-list-compact">
                ${this.commands.map(cmd => this.renderCommandRow(cmd)).join('')}
            </div>
        `;

        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render single command as compact row
     */
    renderCommandRow(cmd) {
        const catInfo = this.CATEGORIES[cmd.category] || { icon: '📁' };
        const isCustom = cmd.is_custom === 1;
        const isFavorite = cmd.is_favorite === 1;

        // Escape command for display, highlight variables
        const displayCommand = this.highlightVariables(escapeHtml(cmd.command));

        return `
            <div class="command-row" data-command-id="${cmd.id}">
                <div class="command-row-info">
                    <span class="command-row-name">${escapeHtml(cmd.name)}</span>
                    <span class="command-row-category">${catInfo.icon}</span>
                </div>
                <div class="command-row-cmd">${displayCommand}</div>
                <div class="command-row-actions">
                    <button class="btn btn-icon btn-xs ${isFavorite ? 'favorite-active' : ''}"
                            onclick="CommandManager.toggleFavorite(${cmd.id})"
                            title="${isFavorite ? 'Remove from favorites' : 'Add to favorites'}">
                        <i data-lucide="star" class="${isFavorite ? 'filled' : ''}"></i>
                    </button>
                    <button class="btn btn-icon btn-xs" onclick="CommandManager.editCommand(${cmd.id})" title="Edit">
                        <i data-lucide="edit-2"></i>
                    </button>
                    ${isCustom ? `
                        <button class="btn btn-icon btn-xs btn-danger" onclick="CommandManager.deleteCommand(${cmd.id})" title="Delete">
                            <i data-lucide="trash-2"></i>
                        </button>
                    ` : ''}
                    <button class="btn btn-xs btn-primary" onclick="CommandManager.copyCommand(${cmd.id})" title="Copy command">
                        <i data-lucide="copy"></i>
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Highlight variables in command string
     */
    highlightVariables(commandStr) {
        return commandStr.replace(/\{([A-Z_]+)\}/g, '<span class="command-variable">{$1}</span>');
    },

    /**
     * Extract variables from command string
     */
    extractVariables(commandStr) {
        const regex = /\{([A-Z_]+)\}/g;
        const matches = [];
        let match;
        while ((match = regex.exec(commandStr)) !== null) {
            if (!matches.includes(match[1])) {
                matches.push(match[1]);
            }
        }
        return matches;
    },

    /**
     * Handle copy with variable substitution
     */
    async copyCommand(commandId) {
        const command = this.commands.find(c => c.id === commandId);
        if (!command) return;

        // Extract variables from command string
        const variables = this.extractVariables(command.command);

        if (variables.length > 0) {
            // Show substitution modal
            this.showSubstitutionModal(command, variables);
        } else {
            // Direct copy
            await this.copyToClipboard(command.command);
            await API.commands.trackUsage(commandId);
            showToast('Command copied to clipboard', 'success');
        }
    },

    /**
     * Show variable substitution modal
     */
    showSubstitutionModal(command, variables) {
        this.activeCommand = command;

        // Build variable definitions from stored JSON or infer from command
        const varDefs = command.variables || [];
        const varDefMap = {};
        for (const v of varDefs) {
            varDefMap[v.name] = v;
        }

        // Build input fields
        const inputsContainer = document.getElementById('variableInputs');
        inputsContainer.innerHTML = variables.map(varName => {
            const def = varDefMap[varName] || {};

            // Auto-fill IP from selected host if available
            let defaultValue = def.default || '';
            if (varName === 'IP' && typeof HostManager !== 'undefined' && HostManager.selectedHostId) {
                const host = HostManager.hosts.find(h => h.id === HostManager.selectedHostId);
                if (host && host.ip) {
                    defaultValue = host.ip;
                }
            }

            return `
                <div class="variable-input-group">
                    <label for="var_${varName}">{${varName}}</label>
                    <input type="text" id="var_${varName}" data-variable="${varName}"
                           value="${escapeHtml(defaultValue)}"
                           placeholder="${escapeHtml(def.description || `Enter ${varName}`)}"
                           oninput="CommandManager.updatePreview()">
                    ${def.description ? `<small>${escapeHtml(def.description)}</small>` : ''}
                </div>
            `;
        }).join('');

        // Show initial preview
        this.updatePreview();

        // Open modal
        openModal('variableModal');
    },

    /**
     * Update command preview in variable modal
     */
    updatePreview() {
        if (!this.activeCommand) return;

        let preview = this.activeCommand.command;

        // Get all variable inputs
        const inputs = document.querySelectorAll('#variableInputs input');
        inputs.forEach(input => {
            const varName = input.dataset.variable;
            const value = input.value || `{${varName}}`;
            preview = preview.replace(new RegExp(`\\{${varName}\\}`, 'g'), value);
        });

        const previewEl = document.getElementById('commandPreview');
        if (previewEl) {
            previewEl.textContent = preview;
        }
    },

    /**
     * Handle variable form submit
     */
    async handleVariableSubmit(e) {
        e.preventDefault();

        if (!this.activeCommand) return;

        let finalCommand = this.activeCommand.command;

        // Replace all variables
        const inputs = document.querySelectorAll('#variableInputs input');
        inputs.forEach(input => {
            const varName = input.dataset.variable;
            const value = input.value || '';
            finalCommand = finalCommand.replace(new RegExp(`\\{${varName}\\}`, 'g'), value);
        });

        // Copy to clipboard
        const success = await this.copyToClipboard(finalCommand);
        if (success) {
            await API.commands.trackUsage(this.activeCommand.id);
            showToast('Command copied to clipboard', 'success');
            closeModal('variableModal');
        }

        this.activeCommand = null;
    },

    /**
     * Copy text to clipboard
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
            return false;
        }
    },

    /**
     * Filter by category
     */
    async filterByCategory(category) {
        this.selectedCategory = category;
        await this.loadCommands();
        this.renderCategoryTabs();
        this.renderCommandList();
    },

    /**
     * Handle search
     */
    async handleSearch(query) {
        this.searchQuery = query.trim();
        await this.loadCommands();
        this.renderCommandList();
    },

    /**
     * Toggle favorites filter
     */
    async toggleFavoritesFilter() {
        this.showFavoritesOnly = !this.showFavoritesOnly;

        const icon = document.getElementById('favoritesFilterIcon');
        if (icon) {
            icon.textContent = this.showFavoritesOnly ? '⭐' : '☆';
            icon.parentElement.classList.toggle('active', this.showFavoritesOnly);
        }

        await this.loadCommands();
        this.renderCommandList();
    },

    /**
     * Toggle favorite for a command
     */
    async toggleFavorite(commandId) {
        try {
            const result = await API.commands.toggleFavorite(commandId);

            // Update local state
            const cmd = this.commands.find(c => c.id === commandId);
            if (cmd) {
                cmd.is_favorite = result.is_favorite;
            }

            // Re-render
            await this.loadCategories();
            this.renderCategoryTabs();
            this.renderCommandList();

            showToast(result.is_favorite ? 'Added to favorites' : 'Removed from favorites', 'success');
        } catch (error) {
            console.error('Failed to toggle favorite:', error);
            showToast('Failed to update favorite', 'error');
        }
    },

    /**
     * Open add command modal
     */
    openAddModal() {
        document.getElementById('commandModalTitle').textContent = 'New Command';
        document.getElementById('commandForm').reset();
        document.getElementById('cmdId').value = '';
        openModal('commandModal');
    },

    /**
     * Edit command (or clone if pre-built)
     */
    async editCommand(commandId) {
        try {
            const command = await API.commands.get(commandId);
            const isCustom = command.is_custom === 1;

            if (isCustom) {
                // Edit existing custom command
                document.getElementById('commandModalTitle').textContent = 'Edit Command';
                document.getElementById('cmdId').value = command.id;
            } else {
                // Clone pre-built command as new custom command
                document.getElementById('commandModalTitle').textContent = 'Clone Command';
                document.getElementById('cmdId').value = '';  // Clear ID to create new
            }

            document.getElementById('cmdCategory').value = command.category;
            document.getElementById('cmdName').value = command.name;
            document.getElementById('cmdCommand').value = command.command;
            document.getElementById('cmdDescription').value = command.description || '';

            openModal('commandModal');
        } catch (error) {
            console.error('Failed to load command:', error);
            showToast('Failed to load command', 'error');
        }
    },

    /**
     * Handle command form submit
     */
    async handleCommandSubmit(e) {
        e.preventDefault();

        const id = document.getElementById('cmdId').value;
        const data = {
            category: document.getElementById('cmdCategory').value,
            name: document.getElementById('cmdName').value,
            command: document.getElementById('cmdCommand').value,
            description: document.getElementById('cmdDescription').value
        };

        // Extract variables from command
        const variables = this.extractVariables(data.command);
        data.variables = variables.map(v => ({ name: v, description: '', default: '' }));

        try {
            if (id) {
                await API.commands.update(parseInt(id), data);
                showToast('Command updated', 'success');
            } else {
                await API.commands.create(data);
                showToast('Command created', 'success');
            }

            closeModal('commandModal');
            await this.loadCommands();
            await this.loadCategories();
            this.renderCategoryTabs();
            this.renderCommandList();
        } catch (error) {
            console.error('Failed to save command:', error);
            showToast(error.message || 'Failed to save command', 'error');
        }
    },

    /**
     * Delete command
     */
    async deleteCommand(commandId) {
        if (!confirm('Are you sure you want to delete this command?')) {
            return;
        }

        try {
            await API.commands.delete(commandId);
            showToast('Command deleted', 'success');

            await this.loadCommands();
            await this.loadCategories();
            this.renderCategoryTabs();
            this.renderCommandList();
        } catch (error) {
            console.error('Failed to delete command:', error);
            showToast(error.message || 'Failed to delete command', 'error');
        }
    }
};

// Make CommandManager available globally
window.CommandManager = CommandManager;
