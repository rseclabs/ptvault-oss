/**
 * Relationships API
 *
 * Handles evidence relationship management and attack path visualization.
 */
import { apiRequest } from '../lib/request.js';

export const RelationshipsAPI = {
    /**
     * Get all relationships for active engagement
     * @returns {Promise<Array>} List of relationships
     */
    async getAll() {
        const response = await apiRequest.get('/relationships');
        return response.relationships || [];
    },

    /**
     * Create new relationship
     * @param {Object} data - Relationship data
     * @param {number} data.source_id - Source evidence ID
     * @param {number} data.target_id - Target evidence ID
     * @param {string} data.type - Relationship type (leads_to, uses, discovers, exploits, escalates, custom)
     * @param {string} data.label - Optional custom label
     * @param {string} data.description - Optional description
     * @returns {Promise<Object>} Created relationship
     */
    async create(data) {
        return apiRequest.post('/relationships', data);
    },

    /**
     * Delete relationship
     * @param {number} id - Relationship ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/relationships/${id}`);
    },

    /**
     * Get all relationships for specific evidence item
     * @param {number} evidenceId - Evidence ID
     * @returns {Promise<Object>} Object with relationships, incoming count, outgoing count
     */
    async getForEvidence(evidenceId) {
        return apiRequest.get(`/relationships/evidence/${evidenceId}`);
    },

    /**
     * Delete all relationships for an evidence item
     * @param {number} evidenceId - Evidence ID
     * @returns {Promise<Object>} Object with deleted count
     */
    async deleteForEvidence(evidenceId) {
        return apiRequest.delete(`/relationships/evidence/${evidenceId}`);
    },

    /**
     * Find attack path between two evidence items
     * @param {number} startId - Starting evidence ID
     * @param {number} endId - Target evidence ID
     * @returns {Promise<Object>} Object with path array and length
     */
    async findPath(startId, endId) {
        return apiRequest.post('/relationships/path', {
            start_id: startId,
            end_id: endId
        });
    },

    /**
     * Get complete relationship graph for visualization
     * @returns {Promise<Object>} Object with nodes (evidence), edges (relationships), and stats
     */
    async getGraph() {
        return apiRequest.get('/relationships/graph');
    },

    /**
     * Get relationship statistics
     * @returns {Promise<Object>} Statistics with counts by type
     */
    async getStats() {
        return apiRequest.get('/relationships/stats');
    },

    // Attack Paths

    /**
     * List all saved attack paths
     * @returns {Promise<Array>} List of saved paths
     */
    async listPaths() {
        const response = await apiRequest.get('/relationships/paths');
        return response.paths || [];
    },

    /**
     * Save an attack path
     * @param {Object} data - Path data
     * @param {string} data.name - Path name
     * @param {string} data.description - Optional description
     * @param {number} data.start_id - Starting evidence ID
     * @param {number} data.end_id - Target evidence ID
     * @param {Array} data.path_data - Array of evidence items in path
     * @returns {Promise<Object>} Created path with ID
     */
    async savePath(data) {
        return apiRequest.post('/relationships/paths', data);
    },

    /**
     * Get saved attack path
     * @param {number} pathId - Path ID
     * @returns {Promise<Object>} Path details with parsed path_data
     */
    async getPath(pathId) {
        return apiRequest.get(`/relationships/paths/${pathId}`);
    },

    /**
     * Delete saved attack path
     * @param {number} pathId - Path ID
     * @returns {Promise<void>}
     */
    async deletePath(pathId) {
        return apiRequest.delete(`/relationships/paths/${pathId}`);
    }
};
