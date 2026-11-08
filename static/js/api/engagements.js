/**
 * Engagements API
 *
 * Handles engagement management including CRUD operations, notes, credentials,
 * terminal dumps, and findings.
 */
import { apiRequest } from '../lib/request.js';

export const EngagementsAPI = {
    // ============================================
    // ENGAGEMENT CRUD
    // ============================================

    /**
     * Get all engagements
     * @param {string} status - Optional status filter (active, completed, archived)
     * @returns {Promise<Array>} List of engagements
     */
    async getAll(status = null) {
        const params = status ? { status } : {};
        return apiRequest.get('/engagements', { params });
    },

    /**
     * Get single engagement by ID
     * @param {number} id - Engagement ID
     * @returns {Promise<Object>} Engagement data
     */
    async get(id) {
        return apiRequest.get(`/engagements/${id}`);
    },

    /**
     * Create new engagement
     * @param {Object} engagementData - Engagement data
     * @returns {Promise<Object>} Created engagement
     */
    async create(engagementData) {
        return apiRequest.post('/engagements', engagementData);
    },

    /**
     * Update engagement
     * @param {number} id - Engagement ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated engagement
     */
    async update(id, updates) {
        return apiRequest.put(`/engagements/${id}`, updates);
    },

    /**
     * Delete engagement
     * @param {number} id - Engagement ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/engagements/${id}`);
    },

    /**
     * Set active engagement
     * @param {number} id - Engagement ID
     * @returns {Promise<Object>} Response data
     */
    async setActive(id) {
        return apiRequest.post('/engagements/active', { engagement_id: id });
    },

    /**
     * Get active engagement
     * @returns {Promise<Object|null>} Active engagement or null
     */
    async getActive() {
        return apiRequest.get('/engagements/active');
    },

    /**
     * Clear active engagement
     * @returns {Promise<void>}
     */
    async clearActive() {
        return apiRequest.delete('/engagements/active');
    },

    /**
     * Import engagement from JSON export file
     * @param {File} file - The JSON export file
     * @returns {Promise<Object>} { success, engagement_id, engagement_name, message }
     */
    async importEngagement(file) {
        const formData = new FormData();
        formData.append('file', file);
        return apiRequest.upload('/engagements/import', formData);
    },

    // ============================================
    // ENGAGEMENT NOTES (General section notes)
    // ============================================

    /**
     * Get all notes for an engagement. List items return content_preview/has_more,
     * not the full body — fetch the full content via getNote().
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of notes
     */
    async getNotes(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/notes`);
    },

    /**
     * Get full content for a single engagement note.
     * @param {number} engagementId - Engagement ID
     * @param {number} noteId - Note ID
     * @returns {Promise<Object>}
     */
    async getNote(engagementId, noteId) {
        return apiRequest.get(`/engagements/${engagementId}/notes/${noteId}`);
    },

    /**
     * Create a note for an engagement.
     *
     * @param {number} engagementId
     * @param {string|Object} contentOrPayload - Either a markdown string
     *   (legacy) or a payload object {content, parent_id?, sort_order?}
     *   for placing the new note inside the tree.
     * @returns {Promise<Object>} Created note (includes parent_id, sort_order)
     */
    async createNote(engagementId, contentOrPayload) {
        const body = typeof contentOrPayload === 'string'
            ? { content: contentOrPayload }
            : contentOrPayload;
        return apiRequest.post(`/engagements/${engagementId}/notes`, body);
    },

    /**
     * Move/reorder a note within the engagement's note tree.
     * @param {number} engagementId
     * @param {number} noteId
     * @param {{parent_id: number|null, sort_order: number|null}} payload
     */
    async moveNote(engagementId, noteId, payload) {
        return apiRequest.post(
            `/engagements/${engagementId}/notes/${noteId}/move`,
            payload,
        );
    },

    /**
     * Update an engagement note
     * @param {number} engagementId - Engagement ID
     * @param {number} noteId - Note ID
     * @param {string} content - Updated content
     * @returns {Promise<Object>} Updated note
     */
    async updateNote(engagementId, noteId, content, title) {
        return apiRequest.put(`/engagements/${engagementId}/notes/${noteId}`, { content, title });
    },

    /**
     * Delete an engagement note
     * @param {number} engagementId - Engagement ID
     * @param {number} noteId - Note ID
     * @returns {Promise<void>}
     */
    async deleteNote(engagementId, noteId) {
        return apiRequest.delete(`/engagements/${engagementId}/notes/${noteId}`);
    },

    // ============================================
    // ENGAGEMENT CREDENTIALS (General section)
    // ============================================

    /**
     * Get all credentials for an engagement
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of credentials
     */
    async getCredentials(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/credentials`);
    },

    /**
     * Create a credential for an engagement
     * @param {number} engagementId - Engagement ID
     * @param {Object} credData - { username, password_or_hash, credential_type, description }
     * @returns {Promise<Object>} Created credential
     */
    async createCredential(engagementId, credData) {
        return apiRequest.post(`/engagements/${engagementId}/credentials`, credData);
    },

    /**
     * Update an engagement credential
     * @param {number} engagementId - Engagement ID
     * @param {number} credId - Credential ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated credential
     */
    async updateCredential(engagementId, credId, updates) {
        return apiRequest.put(`/engagements/${engagementId}/credentials/${credId}`, updates);
    },

    /**
     * Reveal one credential's password or hash (editor role; audited)
     * @param {number} engagementId - Engagement ID
     * @param {number} credId - Credential ID
     * @returns {Promise<{secret: string}>}
     */
    async getCredentialSecret(engagementId, credId) {
        return apiRequest.get(`/engagements/${engagementId}/credentials/${credId}/secret`);
    },

    /**
     * Delete an engagement credential
     * @param {number} engagementId - Engagement ID
     * @param {number} credId - Credential ID
     * @returns {Promise<void>}
     */
    async deleteCredential(engagementId, credId) {
        return apiRequest.delete(`/engagements/${engagementId}/credentials/${credId}`);
    },

    // ============================================
    // TERMINAL DUMPS (General section)
    // ============================================

    /**
     * Get all terminal dumps for an engagement. List items return
     * content_preview/has_more, not the full body — fetch full content via
     * getTerminalDump().
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of terminal dumps
     */
    async getTerminalDumps(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/terminal-dumps`);
    },

    /**
     * Get full content for a single terminal dump.
     * @param {number} engagementId - Engagement ID
     * @param {number} dumpId - Terminal dump ID
     * @returns {Promise<Object>}
     */
    async getTerminalDump(engagementId, dumpId) {
        return apiRequest.get(`/engagements/${engagementId}/terminal-dumps/${dumpId}`);
    },

    /**
     * Create a terminal dump for an engagement
     * @param {number} engagementId - Engagement ID
     * @param {Object} dumpData - { title, content, session_datetime }
     * @returns {Promise<Object>} Created terminal dump
     */
    async createTerminalDump(engagementId, dumpData) {
        return apiRequest.post(`/engagements/${engagementId}/terminal-dumps`, dumpData);
    },

    /**
     * Update a terminal dump
     * @param {number} engagementId - Engagement ID
     * @param {number} dumpId - Terminal dump ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated terminal dump
     */
    async updateTerminalDump(engagementId, dumpId, updates) {
        return apiRequest.put(`/engagements/${engagementId}/terminal-dumps/${dumpId}`, updates);
    },

    /**
     * Delete a terminal dump
     * @param {number} engagementId - Engagement ID
     * @param {number} dumpId - Terminal dump ID
     * @returns {Promise<void>}
     */
    async deleteTerminalDump(engagementId, dumpId) {
        return apiRequest.delete(`/engagements/${engagementId}/terminal-dumps/${dumpId}`);
    },

    // ============================================
    // FINDINGS (General section)
    // ============================================

    /**
     * Get all findings for an engagement
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of findings
     */
    async getFindings(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/findings`);
    },

    /**
     * Create a finding for an engagement
     * @param {number} engagementId - Engagement ID
     * @param {Object} findingData - { title, criticality, cvss_score, finding_content, remediation_content, include_in_report }
     * @returns {Promise<Object>} Created finding
     */
    async createFinding(engagementId, findingData) {
        return apiRequest.post(`/engagements/${engagementId}/findings`, findingData);
    },

    /**
     * Update a finding
     * @param {number} engagementId - Engagement ID
     * @param {number} findingId - Finding ID
     * @param {Object} updates - Updated fields
     * @returns {Promise<Object>} Updated finding
     */
    async updateFinding(engagementId, findingId, updates) {
        return apiRequest.put(`/engagements/${engagementId}/findings/${findingId}`, updates);
    },

    /**
     * Delete a finding
     * @param {number} engagementId - Engagement ID
     * @param {number} findingId - Finding ID
     * @returns {Promise<void>}
     */
    async deleteFinding(engagementId, findingId) {
        return apiRequest.delete(`/engagements/${engagementId}/findings/${findingId}`);
    },

    /**
     * Toggle whether a finding is included in the final report
     * @param {number} engagementId - Engagement ID
     * @param {number} findingId - Finding ID
     * @returns {Promise<Object>} { include_in_report: boolean }
     */
    async toggleFindingReport(engagementId, findingId) {
        return apiRequest.post(`/engagements/${engagementId}/findings/${findingId}/toggle-report`, {});
    }
};
