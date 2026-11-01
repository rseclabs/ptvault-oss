/**
 * Filters API
 *
 * Handles saved filter CRUD operations.
 */
import { apiRequest } from '../lib/request.js';

export const FiltersAPI = {
    /**
     * Get all saved filters for active engagement
     * @returns {Promise<Array>} List of saved filters
     */
    async getAll() {
        return apiRequest.get('/filters');
    },

    /**
     * Create a new saved filter
     * @param {string} name - Filter name
     * @param {string} description - Optional description
     * @param {Object} filterData - Filter criteria
     * @returns {Promise<Object>} Created filter
     */
    async create(name, description, filterData) {
        return apiRequest.post('/filters', {
            name: name,
            description: description || '',
            filter_json: filterData
        });
    },

    /**
     * Update a saved filter
     * @param {number} filterId - Filter ID
     * @param {Object} updates - Updated fields (name, description, filter_json)
     * @returns {Promise<Object>} Updated filter
     */
    async update(filterId, updates) {
        return apiRequest.put(`/filters/${filterId}`, updates);
    },

    /**
     * Delete a saved filter
     * @param {number} filterId - Filter ID
     * @returns {Promise<void>}
     */
    async delete(filterId) {
        return apiRequest.delete(`/filters/${filterId}`);
    },

    /**
     * Apply a saved filter and get matching evidence
     * @param {number} filterId - Filter ID
     * @returns {Promise<Array>} Filtered evidence list
     */
    async apply(filterId) {
        return apiRequest.post(`/filters/${filterId}/apply`, {});
    }
};
