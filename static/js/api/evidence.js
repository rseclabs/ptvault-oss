/**
 * Evidence API
 *
 * Handles evidence management including notes, screenshots, tool output,
 * and search functionality.
 */
import { apiRequest } from '../lib/request.js';

export const EvidenceAPI = {
    /**
     * Get all evidence for active engagement
     * @param {Object} filters - Optional filters (type, tags, host_id, no_host)
     * @returns {Promise<Array>} List of evidence
     */
    async getAll(filters = {}) {
        const params = {};
        if (filters.type) params.type = filters.type;
        if (filters.tags) params.tags = filters.tags;
        if (filters.host_id) params.host_id = filters.host_id;
        if (filters.no_host) params.no_host = 'true';

        return apiRequest.get('/evidence', { params });
    },

    /**
     * Get single evidence by ID
     * @param {number} id - Evidence ID
     * @returns {Promise<Object>} Evidence data
     */
    async get(id) {
        return apiRequest.get(`/evidence/${id}`);
    },

    /**
     * Create new evidence
     * @param {Object} evidenceData - Evidence data
     * @param {File} file - Optional file attachment
     * @returns {Promise<Object>} Created evidence
     */
    async create(evidenceData, file = null) {
        if (file) {
            // Use FormData for file upload
            const formData = new FormData();
            formData.append('title', evidenceData.title);
            formData.append('evidence_type', evidenceData.evidence_type);
            formData.append('content', evidenceData.content || '');
            if (evidenceData.tags) {
                formData.append('tags', evidenceData.tags);
            }
            if (evidenceData.metadata) {
                formData.append('metadata', JSON.stringify(evidenceData.metadata));
            }
            if (evidenceData.host_id) {
                formData.append('host_id', evidenceData.host_id);
            }
            formData.append('file', file);

            return apiRequest.upload('/evidence', formData);
        } else {
            // Use JSON for text-only evidence
            return apiRequest.post('/evidence', evidenceData);
        }
    },

    /**
     * Update evidence
     * @param {number} id - Evidence ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated evidence
     */
    async update(id, updates) {
        return apiRequest.put(`/evidence/${id}`, updates);
    },

    /**
     * Delete evidence
     * @param {number} id - Evidence ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/evidence/${id}`);
    },

    /**
     * Search evidence
     * @param {string} query - Search query
     * @param {number} limit - Max results
     * @returns {Promise<Object>} Search results
     */
    async search(query, limit = 50) {
        return apiRequest.get('/evidence/search', {
            params: { q: query, limit: limit.toString() }
        });
    },

    /**
     * Filter evidence with advanced options
     * @param {Object} filters - Filter options (type, date_from, date_to, tags, tags_any, tool, severity, limit, offset)
     * @returns {Promise<Object>} Filtered results
     */
    async filter(filters) {
        const params = {};
        if (filters.type) params.type = filters.type;
        if (filters.date_from) params.date_from = filters.date_from;
        if (filters.date_to) params.date_to = filters.date_to;
        if (filters.tags) params.tags = filters.tags;
        if (filters.tags_any) params.tags_any = filters.tags_any;
        if (filters.tool) params.tool = filters.tool;
        if (filters.severity) params.severity = filters.severity;
        if (filters.limit) params.limit = filters.limit.toString();
        if (filters.offset) params.offset = filters.offset.toString();

        return apiRequest.get('/evidence/filter', { params });
    },

    /**
     * Perform bulk operation on evidence items
     * @param {string} operation - Operation type: 'tag', 'delete', 'export', 'move_to_host'
     * @param {Array<number>} evidenceIds - Array of evidence IDs
     * @param {Object} params - Operation parameters
     * @returns {Promise<Object>} Operation result
     */
    async bulkOperation(operation, evidenceIds, params = {}) {
        return apiRequest.post('/evidence/bulk', {
            operation,
            evidence_ids: evidenceIds,
            params
        });
    },

    /**
     * Import tool output with parser selection (Q3 Feature)
     * @param {FormData} formData - FormData with file and options
     * @returns {Promise<Object>} Import results with stats
     */
    async importToolOutput(formData) {
        return apiRequest.upload('/evidence/import', formData);
    }
};
