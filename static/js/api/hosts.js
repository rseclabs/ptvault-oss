/**
 * Hosts API
 *
 * Handles host management including notes, ports, credentials, and evidence linking.
 */
import { apiRequest } from '../lib/request.js';

export const HostsAPI = {
    // ============================================
    // HOST CRUD
    // ============================================

    /**
     * Get all hosts for active engagement
     * @returns {Promise<Object>} { hosts: [], general_count: number }
     */
    async getAll() {
        return apiRequest.get('/hosts');
    },

    /**
     * Get single host by ID with evidence
     * @param {number} id - Host ID
     * @returns {Promise<Object>} Host data with evidence
     */
    async get(id) {
        return apiRequest.get(`/hosts/${id}`);
    },

    /**
     * Create new host
     * @param {Object} hostData - Host data (ip required, hostname/os/notes optional)
     * @returns {Promise<Object>} Created host
     */
    async create(hostData) {
        return apiRequest.post('/hosts', hostData);
    },

    /**
     * Update host
     * @param {number} id - Host ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated host
     */
    async update(id, updates) {
        return apiRequest.put(`/hosts/${id}`, updates);
    },

    /**
     * Delete host
     * @param {number} id - Host ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/hosts/${id}`);
    },

    /**
     * Search hosts by keyword across notes, evidence, ports, credentials
     * @param {string} query - Search keyword
     * @returns {Promise<Object>} { host_ids: [] }
     */
    async search(query) {
        return apiRequest.get(`/hosts/search?q=${encodeURIComponent(query)}`);
    },

    /**
     * Link evidence to host
     * @param {number} hostId - Host ID
     * @param {number} evidenceId - Evidence ID
     * @returns {Promise<Object>} Response
     */
    async linkEvidence(hostId, evidenceId) {
        return apiRequest.post(`/hosts/${hostId}/evidence`, { evidence_id: evidenceId });
    },

    /**
     * Unlink evidence from host
     * @param {number} hostId - Host ID
     * @param {number} evidenceId - Evidence ID
     * @returns {Promise<void>}
     */
    async unlinkEvidence(hostId, evidenceId) {
        return apiRequest.delete(`/hosts/${hostId}/evidence/${evidenceId}`);
    },

    // ============================================
    // HOST NOTES
    // ============================================

    /**
     * Get all notes for a host. List items return content_preview/has_more,
     * not the full body — fetch the full content via getNote().
     * @param {number} hostId - Host ID
     * @returns {Promise<Object>} { notes: [] }
     */
    async getNotes(hostId) {
        return apiRequest.get(`/hosts/${hostId}/notes`);
    },

    /**
     * Get full content for a single host note.
     * @param {number} hostId - Host ID
     * @param {number} noteId - Note ID
     * @returns {Promise<Object>} { id, host_id, content, created_at, updated_at }
     */
    async getNote(hostId, noteId) {
        return apiRequest.get(`/hosts/${hostId}/notes/${noteId}`);
    },

    /**
     * Create a note for a host.
     *
     * @param {number} hostId
     * @param {string|Object} contentOrPayload - Either a markdown string
     *   (legacy) or a payload object {content, parent_id?, sort_order?}
     *   for placing the new note inside the tree.
     * @returns {Promise<Object>} Created note (includes parent_id, sort_order)
     */
    async createNote(hostId, contentOrPayload) {
        const body = typeof contentOrPayload === 'string'
            ? { content: contentOrPayload }
            : contentOrPayload;
        return apiRequest.post(`/hosts/${hostId}/notes`, body);
    },

    /**
     * Move/reorder a note within the host's note tree.
     * @param {number} hostId
     * @param {number} noteId
     * @param {{parent_id: number|null, sort_order: number|null}} payload
     */
    async moveNote(hostId, noteId, payload) {
        return apiRequest.post(`/hosts/${hostId}/notes/${noteId}/move`, payload);
    },

    /**
     * Update a note
     * @param {number} hostId - Host ID
     * @param {number} noteId - Note ID
     * @param {string} content - Updated content
     * @returns {Promise<Object>} Updated note
     */
    async updateNote(hostId, noteId, content, title) {
        return apiRequest.put(`/hosts/${hostId}/notes/${noteId}`, { content, title });
    },

    /**
     * Delete a note
     * @param {number} hostId - Host ID
     * @param {number} noteId - Note ID
     * @returns {Promise<void>}
     */
    async deleteNote(hostId, noteId) {
        return apiRequest.delete(`/hosts/${hostId}/notes/${noteId}`);
    },

    // ============================================
    // HOST PORTS
    // ============================================

    /**
     * Get all ports for a host
     * @param {number} hostId - Host ID
     * @returns {Promise<Object>} { ports: [] }
     */
    async getPorts(hostId) {
        return apiRequest.get(`/hosts/${hostId}/ports`);
    },

    /**
     * Get all port data for the engagement (for port grid view)
     * @returns {Promise<Object>} { hosts: [], ports: [] }
     */
    async getPortGrid() {
        return apiRequest.get('/hosts/port-grid');
    },

    /**
     * Create a port entry for a host
     * @param {number} hostId - Host ID
     * @param {Object} portData - { port, protocol, state, service, version }
     * @returns {Promise<Object>} Created port
     */
    async createPort(hostId, portData) {
        return apiRequest.post(`/hosts/${hostId}/ports`, portData);
    },

    /**
     * Update a port entry
     * @param {number} hostId - Host ID
     * @param {number} portId - Port entry ID
     * @param {Object} updates - { state, service, version }
     * @returns {Promise<Object>} Updated port
     */
    async updatePort(hostId, portId, updates) {
        return apiRequest.put(`/hosts/${hostId}/ports/${portId}`, updates);
    },

    /**
     * Delete a port entry
     * @param {number} hostId - Host ID
     * @param {number} portId - Port entry ID
     * @returns {Promise<void>}
     */
    async deletePort(hostId, portId) {
        return apiRequest.delete(`/hosts/${hostId}/ports/${portId}`);
    },

    // ============================================
    // HOST CREDENTIALS
    // ============================================

    /**
     * Get all credentials for a host
     * @param {number} hostId - Host ID
     * @returns {Promise<Object>} { credentials: [] }
     */
    async getCredentials(hostId) {
        return apiRequest.get(`/hosts/${hostId}/credentials`);
    },

    /**
     * Create a credential entry for a host
     * @param {number} hostId - Host ID
     * @param {Object} credData - { username, password, password_type, hash_type, service, notes }
     * @returns {Promise<Object>} Created credential
     */
    async createCredential(hostId, credData) {
        return apiRequest.post(`/hosts/${hostId}/credentials`, credData);
    },

    /**
     * Update a credential entry
     * @param {number} hostId - Host ID
     * @param {number} credId - Credential ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated credential
     */
    async updateCredential(hostId, credId, updates) {
        return apiRequest.put(`/hosts/${hostId}/credentials/${credId}`, updates);
    },

    /**
     * Delete a credential entry
     * @param {number} hostId - Host ID
     * @param {number} credId - Credential ID
     * @returns {Promise<void>}
     */
    async deleteCredential(hostId, credId) {
        return apiRequest.delete(`/hosts/${hostId}/credentials/${credId}`);
    }
};
