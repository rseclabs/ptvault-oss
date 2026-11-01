/**
 * Shell One-Liners API
 *
 * Handles shell one-liner database operations.
 */
import { apiRequest } from '../lib/request.js';

export const ShellOnelinersAPI = {
    /**
     * Get all shell one-liners with optional filters
     * @param {Object} filters - { category, subcategory, search }
     * @returns {Promise<Array>} List of one-liners
     */
    async getAll(filters = {}) {
        const params = {};
        if (filters.category && filters.category !== 'all') {
            params.category = filters.category;
        }
        if (filters.subcategory && filters.subcategory !== 'all') {
            params.subcategory = filters.subcategory;
        }
        if (filters.search) {
            params.search = filters.search;
        }

        return apiRequest.get('/shell-oneliners', { params });
    },

    /**
     * Get single one-liner by ID
     * @param {number} id - One-liner ID
     * @returns {Promise<Object>} One-liner object
     */
    async get(id) {
        return apiRequest.get(`/shell-oneliners/${id}`);
    },

    /**
     * Get categories and subcategories with counts
     * @returns {Promise<Object>} { categories, subcategories, total }
     */
    async getCategories() {
        return apiRequest.get('/shell-oneliners/categories');
    },

    // Admin endpoints
    /**
     * Create new one-liner (admin)
     * @param {Object} data - { category, subcategory, name, command, description, variables }
     * @returns {Promise<Object>} Created one-liner
     */
    async create(data) {
        return apiRequest.post('/shell-oneliners/admin', data);
    },

    /**
     * Update one-liner (admin)
     * @param {number} id - One-liner ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated one-liner
     */
    async update(id, updates) {
        return apiRequest.put(`/shell-oneliners/admin/${id}`, updates);
    },

    /**
     * Delete one-liner (admin)
     * @param {number} id - One-liner ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/shell-oneliners/admin/${id}`);
    }
};
