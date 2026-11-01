/**
 * Clients API
 *
 * Admin-only CRUD for the Clients database, plus a lightweight
 * /options endpoint that any authenticated user can call to populate
 * the engagement-create dropdown.
 */
import { apiRequest } from '../lib/request.js';

export const ClientsAPI = {
    /**
     * Get all clients with full detail (admin only).
     * @returns {Promise<Array>} List of client records
     */
    async getAll() {
        const response = await apiRequest.get('/clients');
        return response.clients || [];
    },

    /**
     * Get id+name pairs for dropdown population.
     * Available to any authenticated user.
     * @returns {Promise<Array<{id: number, name: string}>>}
     */
    async getOptions() {
        const response = await apiRequest.get('/clients/options');
        return response.clients || [];
    },

    /**
     * Get a single client.
     * @param {number} id - Client ID
     * @returns {Promise<Object>}
     */
    async getOne(id) {
        return apiRequest.get(`/clients/${id}`);
    },

    /**
     * Create a new client (admin only).
     * @param {Object} data - { name, admin_contact_*, technical_contact_*, address, website, notes }
     * @returns {Promise<Object>} Created client
     */
    async create(data) {
        return apiRequest.post('/clients', data);
    },

    /**
     * Update an existing client (admin only).
     * @param {number} id
     * @param {Object} data
     * @returns {Promise<Object>}
     */
    async update(id, data) {
        return apiRequest.put(`/clients/${id}`, data);
    },

    /**
     * Delete a client (admin only). Returns 409 if the client still
     * has engagements; the caller should surface the engagement_count
     * from the error body.
     * @param {number} id
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/clients/${id}`);
    }
};
