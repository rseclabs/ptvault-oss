/**
 * Dashboard API
 *
 * Fetches aggregated metrics for the active engagement.
 */
import { apiRequest } from '../lib/request.js';

export const DashboardAPI = {
    /**
     * Get all dashboard metrics for the active engagement.
     * @returns {Promise<Object>} Full metrics envelope.
     */
    async getMetrics() {
        return apiRequest.get('/dashboard/metrics');
    },
};
