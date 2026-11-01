/**
 * Tags API
 *
 * Handles tag autocomplete functionality.
 */
import { apiRequest } from '../lib/request.js';

export const TagsAPI = {
    /**
     * Get tag autocomplete suggestions
     * @param {string} prefix - Tag prefix to search for
     * @param {number} limit - Maximum number of suggestions (default: 10)
     * @returns {Promise<Array>} List of matching tags
     */
    async autocomplete(prefix = '', limit = 10) {
        return apiRequest.get('/tags/autocomplete', {
            params: { q: prefix, limit: limit.toString() }
        });
    }
};
