/**
 * Export API
 *
 * Handles engagement exports in various formats.
 */
import { apiRequest } from '../lib/request.js';

export const ExportAPI = {
    /**
     * Export engagement as JSON
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Blob>} JSON file
     */
    async exportJSON(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/export/json`);
    },

    /**
     * Export engagement as Markdown
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Blob>} Markdown file
     */
    async exportMarkdown(engagementId) {
        return apiRequest.get(`/engagements/${engagementId}/export/markdown`);
    },

    /**
     * Export engagement using a template
     * @param {number} engagementId - Engagement ID
     * @param {string} templateName - Template name (e.g., 'default', 'executive')
     * @returns {Promise<Blob>} Exported file
     */
    async exportTemplate(engagementId, templateName) {
        return apiRequest.get(`/engagements/${engagementId}/export/template/${templateName}`);
    }
};
