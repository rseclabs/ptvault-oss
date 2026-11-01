/**
 * Commands API
 *
 * Handles command database CRUD operations and management.
 */
import { apiRequest } from '../lib/request.js';

export const CommandsAPI = {
    /**
     * Get all commands with optional filters
     * @param {Object} filters - { category, search, is_favorite }
     * @returns {Promise<Array>} List of commands
     */
    async getAll(filters = {}) {
        const params = {};
        if (filters.category && filters.category !== 'all') {
            params.category = filters.category;
        }
        if (filters.search) {
            params.search = filters.search;
        }
        if (filters.is_favorite) {
            params.is_favorite = 'true';
        }

        return apiRequest.get('/commands', { params });
    },

    /**
     * Get single command by ID
     * @param {number} id - Command ID
     * @returns {Promise<Object>} Command object
     */
    async get(id) {
        return apiRequest.get(`/commands/${id}`);
    },

    /**
     * Create new command
     * @param {Object} commandData - { category, name, command, description, variables }
     * @returns {Promise<Object>} Created command
     */
    async create(commandData) {
        return apiRequest.post('/commands', commandData);
    },

    /**
     * Update command
     * @param {number} id - Command ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated command
     */
    async update(id, updates) {
        return apiRequest.put(`/commands/${id}`, updates);
    },

    /**
     * Delete command
     * @param {number} id - Command ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/commands/${id}`);
    },

    /**
     * Toggle favorite status
     * @param {number} id - Command ID
     * @returns {Promise<Object>} { is_favorite: 0|1 }
     */
    async toggleFavorite(id) {
        return apiRequest.post(`/commands/${id}/favorite`, {});
    },

    /**
     * Track command usage (increment counter)
     * @param {number} id - Command ID
     * @returns {Promise<void>}
     */
    async trackUsage(id) {
        return apiRequest.post(`/commands/${id}/usage`, {});
    },

    /**
     * Get categories with counts
     * @returns {Promise<Object>} { categories: [...], total: number }
     */
    async getCategories() {
        return apiRequest.get('/commands/categories');
    }
};
