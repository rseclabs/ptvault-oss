/**
 * Teams API
 *
 * Handles team management and team membership operations.
 */
import { apiRequest } from '../lib/request.js';

export const TeamsAPI = {
    /**
     * Get all teams (admin: all, others: their teams)
     * @returns {Promise<Array>} List of teams
     */
    async getAll() {
        return apiRequest.get('/teams');
    },

    /**
     * Create a new team
     * @param {Object} data - Team data
     * @param {string} data.name - Team name (required)
     * @param {string} data.description - Team description
     * @returns {Promise<Object>} Created team
     */
    async create(data) {
        return apiRequest.post('/teams', data);
    },

    /**
     * Get team detail
     * @param {number} id - Team ID
     * @returns {Promise<Object>} Team object
     */
    async getOne(id) {
        return apiRequest.get(`/teams/${id}`);
    },

    /**
     * Update a team
     * @param {number} id - Team ID
     * @param {Object} data - Fields to update
     * @returns {Promise<Object>} Updated team
     */
    async update(id, data) {
        return apiRequest.put(`/teams/${id}`, data);
    },

    /**
     * Delete a team
     * @param {number} id - Team ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/teams/${id}`);
    },

    // ==================== Team Members ====================

    /**
     * Get all members of a team
     * @param {number} teamId - Team ID
     * @returns {Promise<Array>} List of team members
     */
    async getMembers(teamId) {
        const response = await apiRequest.get(`/teams/${teamId}/members`);
        return response.members || [];
    },

    /**
     * Add a member to a team
     * @param {number} teamId - Team ID
     * @param {Object} data - Member data
     * @param {number} data.user_id - User ID
     * @param {string} data.role - Role: 'lead' or 'member'
     * @returns {Promise<Object>} Created member record
     */
    async addMember(teamId, data) {
        return apiRequest.post(`/teams/${teamId}/members`, data);
    },

    /**
     * Update a team member's role
     * @param {number} teamId - Team ID
     * @param {number} memberId - Member record ID
     * @param {Object} data - Update data
     * @param {string} data.role - New role: 'lead' or 'member'
     * @returns {Promise<Object>} Updated member record
     */
    async updateMember(teamId, memberId, data) {
        return apiRequest.put(`/teams/${teamId}/members/${memberId}`, data);
    },

    /**
     * Remove a member from a team
     * @param {number} teamId - Team ID
     * @param {number} memberId - Member record ID
     * @returns {Promise<void>}
     */
    async removeMember(teamId, memberId) {
        return apiRequest.delete(`/teams/${teamId}/members/${memberId}`);
    }
};
