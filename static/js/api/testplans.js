/**
 * Test Plans API
 *
 * Handles test plans, atomics, navigator layers, and execution tracking.
 */
import { apiRequest } from '../lib/request.js';

export const TestPlansAPI = {
    // ============================================
    // ATOMICS LIBRARY
    // ============================================

    /**
     * Get atomics library status
     * @returns {Promise<Object>} Status info
     */
    async getAtomicsStatus() {
        return apiRequest.get('/testplans/atomics/status');
    },

    /**
     * Download atomics library with progress tracking
     * @param {Function} onProgress - Callback for progress updates (percent, message, stage)
     * @returns {Promise<Object>} Download result
     */
    async downloadAtomics(onProgress) {
        return new Promise((resolve, reject) => {
            const csrfMatch = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : null;
            fetch('/api/testplans/atomics/download', {
                method: 'POST',
                headers: Object.assign(
                    { 'Content-Type': 'application/json' },
                    csrfToken ? { 'X-CSRF-Token': csrfToken } : {}
                )
            }).then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        reject(new Error(data.error || 'Download failed'));
                    });
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let lastProgress = null;

                function processStream() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            if (buffer.trim()) {
                                try {
                                    const data = JSON.parse(buffer.trim());
                                    lastProgress = data;
                                    if (onProgress) onProgress(data);
                                } catch (e) { /* ignore */ }
                            }

                            if (lastProgress && lastProgress.stage === 'complete') {
                                resolve(lastProgress);
                            } else if (lastProgress) {
                                resolve({ success: true, ...lastProgress });
                            } else {
                                resolve({ success: true });
                            }
                            return;
                        }

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop();

                        for (const line of lines) {
                            if (line.trim()) {
                                try {
                                    const data = JSON.parse(line);
                                    lastProgress = data;

                                    if (onProgress) {
                                        onProgress(data);
                                    }

                                    if (data.stage === 'complete') {
                                        resolve(data);
                                        return;
                                    }

                                    if (data.stage === 'error' || data.error) {
                                        reject(new Error(data.error || 'Download failed'));
                                        return;
                                    }
                                } catch (e) {
                                    console.error('Failed to parse progress:', line, e);
                                }
                            }
                        }

                        processStream();
                    }).catch(reject);
                }

                processStream();
            }).catch(reject);
        });
    },

    /**
     * Get atomics with filters
     * @param {Object} params - Filter params (platform, tactic, search, limit, offset)
     * @returns {Promise<Object>} Atomics list with pagination
     */
    async getAtomics(params = {}) {
        return apiRequest.get('/testplans/atomics', { params });
    },

    /**
     * Get every tactic in the library with technique counts
     * @returns {Promise<Array>} [{ tactic, technique_count }]
     */
    async getTactics() {
        return apiRequest.get('/testplans/atomics/tactics');
    },

    /**
     * Get single atomic by ID
     * @param {number} id - Atomic ID
     * @returns {Promise<Object>} Atomic details
     */
    async getAtomic(id) {
        return apiRequest.get(`/testplans/atomics/${id}`);
    },

    /**
     * Get techniques list
     * @returns {Promise<Array>} Techniques with test counts
     */
    async getTechniques() {
        return apiRequest.get('/testplans/atomics/techniques');
    },

    // ============================================
    // NAVIGATOR LAYERS
    // ============================================

    /**
     * Get layers list
     * @returns {Promise<Array>} Imported layers
     */
    async getLayers() {
        return apiRequest.get('/testplans/layers');
    },

    /**
     * Import navigator layer
     * @param {File} file - JSON file
     * @returns {Promise<Object>} Import result
     */
    async importLayer(file) {
        const formData = new FormData();
        formData.append('file', file);
        return apiRequest.upload('/testplans/layers/import', formData);
    },

    /**
     * Get layer by ID
     * @param {number} id - Layer ID
     * @returns {Promise<Object>} Layer details
     */
    async getLayer(id) {
        return apiRequest.get(`/testplans/layers/${id}`);
    },

    /**
     * Delete layer
     * @param {number} id - Layer ID
     * @returns {Promise<Object>} Delete result
     */
    async deleteLayer(id) {
        return apiRequest.delete(`/testplans/layers/${id}`);
    },

    /**
     * Match layer to atomics
     * @param {number} layerId - Layer ID
     * @param {Object} filters - min_score, colors, platform
     * @returns {Promise<Object>} Matched atomics
     */
    async matchLayerToAtomics(layerId, filters = {}) {
        return apiRequest.post(`/testplans/layers/${layerId}/match`, filters);
    },

    // ============================================
    // TEST PLANS
    // ============================================

    /**
     * Get all test plans
     * @returns {Promise<Array>} Test plans list
     */
    async getPlans() {
        return apiRequest.get('/testplans/plans');
    },

    /**
     * Create test plan
     * @param {Object} data - Plan data (name, description, target_platform, tags)
     * @returns {Promise<Object>} Created plan
     */
    async createPlan(data) {
        return apiRequest.post('/testplans/plans', data);
    },

    /**
     * Get plan by ID with items
     * @param {number} id - Plan ID
     * @returns {Promise<Object>} Plan with items
     */
    async getPlan(id) {
        return apiRequest.get(`/testplans/plans/${id}`);
    },

    /**
     * Update plan
     * @param {number} id - Plan ID
     * @param {Object} data - Updated data
     * @returns {Promise<Object>} Updated plan
     */
    async updatePlan(id, data) {
        return apiRequest.put(`/testplans/plans/${id}`, data);
    },

    /**
     * Delete plan
     * @param {number} id - Plan ID
     * @returns {Promise<Object>} Delete result
     */
    async deletePlan(id) {
        return apiRequest.delete(`/testplans/plans/${id}`);
    },

    /**
     * Copy a plan (duplicate, use a template, or save as template)
     * @param {number} id - Plan ID
     * @param {Object} options - { target: 'engagement' | 'template', name }
     *   target omitted = same scope as the source
     * @returns {Promise<Object>} The new plan
     */
    async duplicatePlan(id, options = {}) {
        return apiRequest.post(`/testplans/plans/${id}/duplicate`, options);
    },

    /**
     * Add item to plan
     * @param {number} planId - Plan ID
     * @param {Object} data - Item data (atomic_id or custom fields)
     * @returns {Promise<Object>} Added item
     */
    async addPlanItem(planId, data) {
        return apiRequest.post(`/testplans/plans/${planId}/items`, data);
    },

    /**
     * Add bulk items to plan
     * @param {number} planId - Plan ID
     * @param {Array} atomicIds - Array of atomic IDs
     * @returns {Promise<Object>} Result
     */
    async addBulkItems(planId, atomicIds) {
        return apiRequest.post(`/testplans/plans/${planId}/items/bulk`, {
            atomic_ids: atomicIds
        });
    },

    /**
     * Update plan item
     * @param {number} planId - Plan ID
     * @param {number} itemId - Item ID
     * @param {Object} data - Updated data
     * @returns {Promise<Object>} Update result
     */
    async updatePlanItem(planId, itemId, data) {
        return apiRequest.put(`/testplans/plans/${planId}/items/${itemId}`, data);
    },

    /**
     * Delete plan item
     * @param {number} planId - Plan ID
     * @param {number} itemId - Item ID
     * @returns {Promise<Object>} Delete result
     */
    async deletePlanItem(planId, itemId) {
        return apiRequest.delete(`/testplans/plans/${planId}/items/${itemId}`);
    },

    /**
     * Reorder plan items
     * @param {number} planId - Plan ID
     * @param {Array} itemIds - Array of item IDs in new order
     * @returns {Promise<Object>} Result
     */
    async reorderPlanItems(planId, itemIds) {
        return apiRequest.post(`/testplans/plans/${planId}/items/reorder`, {
            item_ids: itemIds
        });
    },

    /**
     * Generate script from plan
     * @param {number} planId - Plan ID
     * @param {string} platform - windows, linux, macos
     * @param {boolean} includeReadme - Include README in zip (default: true)
     * @returns {Promise<Blob>} Script file as blob (zip if includeReadme)
     */
    async generateScript(planId, platform, includeReadme = true) {
        // Fetch directly so we can always coerce the response to a Blob
        // regardless of Content-Type. The shared apiRequest only recognises
        // pdf / officedocument / image as binary, so application/zip and
        // text/plain fall through and get consumed as text — which then
        // breaks URL.createObjectURL on the caller side.
        const params = new URLSearchParams({
            platform: platform,
            include_readme: includeReadme.toString(),
        });
        const url = `/api/testplans/plans/${planId}/script?${params.toString()}`;

        const csrfMatch = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
        const headers = {};
        if (csrfMatch) headers['X-CSRF-Token'] = decodeURIComponent(csrfMatch[1]);

        const response = await fetch(url, { credentials: 'same-origin', headers });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
            throw new Error(err.error || `HTTP ${response.status}`);
        }
        return await response.blob();
    },

    // ============================================
    // EXECUTIONS
    // ============================================

    /**
     * Get executions for current engagement
     * @returns {Promise<Array>} Executions list
     */
    async getExecutions() {
        return apiRequest.get('/testplans/executions');
    },

    /**
     * Start execution of a plan
     * @param {number} planId - Plan ID
     * @param {number} hostId - Optional target host ID
     * @returns {Promise<Object>} Start result
     */
    async startExecution(planId, hostId = null) {
        return apiRequest.post('/testplans/executions/start', {
            plan_id: planId,
            host_id: hostId
        });
    },

    /**
     * Get single execution
     * @param {number} id - Execution ID
     * @returns {Promise<Object>} Execution details
     */
    async getExecution(id) {
        return apiRequest.get(`/testplans/executions/${id}`);
    },

    /**
     * Update execution status
     * @param {number} id - Execution ID
     * @param {Object} data - Status, output, notes
     * @returns {Promise<Object>} Update result
     */
    async updateExecution(id, data) {
        return apiRequest.put(`/testplans/executions/${id}`, data);
    },

    /**
     * Delete an execution record
     * @param {number} id - Execution ID
     * @returns {Promise<Object>} Delete result
     */
    async deleteExecution(id) {
        return apiRequest.delete(`/testplans/executions/${id}`);
    },

    /**
     * Import a session log from a PTVault-generated script
     * @param {number} planId - Engagement plan the results belong to
     * @param {number|null} hostId - Host the script ran on (null = no specific host)
     * @param {File} file - The captured log
     * @param {boolean} apply - false = preview only, true = write results
     * @returns {Promise<Object>} { preview, summary, results }
     */
    async importSessionLog(planId, hostId, file, apply = false) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('plan_id', planId);
        formData.append('host_id', hostId == null ? '' : hostId);
        formData.append('apply', apply ? 'true' : 'false');
        return apiRequest.upload('/testplans/executions/import-log', formData);
    },

    /**
     * Link evidence to execution
     * @param {number} executionId - Execution ID
     * @param {number} evidenceId - Evidence ID
     * @returns {Promise<Object>} Link result
     */
    async linkEvidence(executionId, evidenceId) {
        return apiRequest.post(`/testplans/executions/${executionId}/link-evidence`, {
            evidence_id: evidenceId
        });
    },

    /**
     * Get plan execution progress
     * @param {number} planId - Plan ID
     * @returns {Promise<Object>} Progress stats
     */
    async getPlanProgress(planId) {
        return apiRequest.get(`/testplans/executions/plan/${planId}/progress`);
    }
};
