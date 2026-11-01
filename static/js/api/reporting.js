/**
 * Reporting API
 *
 * Handles writeups database and report generation.
 */
import { apiRequest } from '../lib/request.js';

export const ReportingAPI = {
    // ============================================
    // WRITEUPS DATABASE
    // ============================================

    /**
     * Get all writeups with optional filters
     * @param {Object} filters - { category, criticality, search, tags }
     * @returns {Promise<Array>} List of writeups
     */
    async getWriteups(filters = {}) {
        const params = {};
        if (filters.category && filters.category !== 'all') {
            params.category = filters.category;
        }
        if (filters.criticality && filters.criticality !== 'all') {
            params.criticality = filters.criticality;
        }
        if (filters.search) {
            params.search = filters.search;
        }
        if (filters.tags) {
            params.tags = filters.tags;
        }

        return apiRequest.get('/reporting/writeups', { params });
    },

    /**
     * Get single writeup by ID
     * @param {number} id - Writeup ID
     * @returns {Promise<Object>} Writeup object
     */
    async getWriteup(id) {
        return apiRequest.get(`/reporting/writeups/${id}`);
    },

    /**
     * Get categories with counts
     * @returns {Promise<Object>} { categories, criticalities, total }
     */
    async getCategories() {
        return apiRequest.get('/reporting/writeups/categories');
    },

    /**
     * Create new writeup
     * @param {Object} writeupData - { name, category, criticality, cvss_score, description, remediation, tags }
     * @returns {Promise<Object>} Created writeup
     */
    async createWriteup(writeupData) {
        return apiRequest.post('/reporting/writeups', writeupData);
    },

    /**
     * Update writeup
     * @param {number} id - Writeup ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated writeup
     */
    async updateWriteup(id, updates) {
        return apiRequest.put(`/reporting/writeups/${id}`, updates);
    },

    /**
     * Delete writeup
     * @param {number} id - Writeup ID
     * @returns {Promise<void>}
     */
    async deleteWriteup(id) {
        return apiRequest.delete(`/reporting/writeups/${id}`);
    },

    // ============================================
    // REPORT GENERATOR
    // ============================================

    /**
     * Get all reports for an engagement
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of reports
     */
    async getReports(engagementId) {
        return apiRequest.get('/reporting/reports', {
            params: { engagement_id: engagementId }
        });
    },

    /**
     * Get single report by ID (with hydrated items)
     * @param {number} id - Report ID
     * @returns {Promise<Object>} Report object with hydrated_items
     */
    async getReport(id) {
        return apiRequest.get(`/reporting/reports/${id}`);
    },

    /**
     * Create new report
     * @param {Object} reportData - { engagement_id, name, structure? }
     * @returns {Promise<Object>} Created report
     */
    async createReport(reportData) {
        return apiRequest.post('/reporting/reports', reportData);
    },

    /**
     * Update report
     * @param {number} id - Report ID
     * @param {Object} updates - { name?, structure? }
     * @returns {Promise<Object>} Updated report
     */
    async updateReport(id, updates) {
        return apiRequest.put(`/reporting/reports/${id}`, updates);
    },

    /**
     * Delete report
     * @param {number} id - Report ID
     * @returns {Promise<void>}
     */
    async deleteReport(id) {
        return apiRequest.delete(`/reporting/reports/${id}`);
    },

    /**
     * Export report in various formats
     * @param {number} id - Report ID
     * @param {string} format - 'html', 'markdown', 'pdf', 'docx'
     * @returns {Promise<Blob|string>} Export content
     */
    async exportReport(id, format) {
        const response = await fetch(`/api/reporting/reports/${id}/export?format=${format}`, {
            method: 'GET'
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({
                error: 'Failed to export report'
            }));
            throw new Error(error.error || 'Failed to export report');
        }

        const contentType = response.headers.get('content-type');

        if (format === 'pdf') {
            // If we got application/pdf, return as blob for download
            if (contentType && contentType.includes('application/pdf')) {
                return await response.blob();
            }
            // Otherwise it's HTML fallback for browser print
            return await response.text();
        } else if (format === 'docx') {
            // Return blob for download
            return await response.blob();
        } else {
            // HTML and Markdown return as blob for download
            return await response.blob();
        }
    },

    // ============================================
    // TEMPLATES (Q3 FEATURE)
    // ============================================

    /**
     * Get all templates
     * @returns {Promise<Object>} { templates: Array }
     */
    async getTemplates() {
        return apiRequest.get('/reporting/templates');
    },

    /**
     * Get single template by ID
     * @param {number} id - Template ID
     * @returns {Promise<Object>} Template object
     */
    async getTemplate(id) {
        return apiRequest.get(`/reporting/templates/${id}`);
    },

    /**
     * Create new template
     * @param {Object} templateData - { name, description, category, structure }
     * @returns {Promise<Object>} Created template
     */
    async createTemplate(templateData) {
        return apiRequest.post('/reporting/templates', templateData);
    },

    /**
     * Update template
     * @param {number} id - Template ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated template
     */
    async updateTemplate(id, updates) {
        return apiRequest.put(`/reporting/templates/${id}`, updates);
    },

    /**
     * Delete template
     * @param {number} id - Template ID
     * @returns {Promise<void>}
     */
    async deleteTemplate(id) {
        return apiRequest.delete(`/reporting/templates/${id}`);
    },

    /**
     * Apply template to create a new report
     * @param {number} templateId - Template ID
     * @param {number} engagementId - Optional engagement ID (uses active if not provided)
     * @returns {Promise<Object>} { report_id: number }
     */
    async applyTemplate(templateId, engagementId = null) {
        return apiRequest.post(`/reporting/templates/${templateId}/apply`, {
            engagement_id: engagementId
        });
    },

    /**
     * Preview template with sample data
     * @param {number} templateId - Template ID
     * @returns {Promise<Object>} { id, name, preview_html }
     */
    async previewTemplate(templateId, engagementId) {
        return apiRequest.get(`/reporting/templates/${templateId}/preview?engagement_id=${engagementId}`);
    },

    /**
     * Compare multiple engagements
     * @param {Array<number>} engagementIds - Array of engagement IDs
     * @returns {Promise<Object>} Comparison data
     */
    async compareEngagements(engagementIds) {
        return apiRequest.post('/reporting/compare', {
            engagement_ids: engagementIds
        });
    }
};
