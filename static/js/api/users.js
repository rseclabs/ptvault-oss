/**
 * Users API
 *
 * Handles user management and team member operations.
 */
import { apiRequest } from '../lib/request.js';

export const UsersAPI = {
    /**
     * Get current user info
     * @returns {Promise<Object>} Current user object with role
     */
    async getMe() {
        return apiRequest.get('/users/me');
    },

    /**
     * Get all users
     * @returns {Promise<Array>} List of users
     */
    async getAll() {
        const response = await apiRequest.get('/users');
        return response.users || [];
    },

    /**
     * Get single user by ID
     * @param {number} id - User ID
     * @returns {Promise<Object>} User object
     */
    async getOne(id) {
        return apiRequest.get(`/users/${id}`);
    },

    /**
     * Create new user
     * @param {Object} data - User data
     * @param {string} data.username - Username (required)
     * @param {string} data.email - Email address (required)
     * @param {string} data.password - Password (required)
     * @param {string} data.role - Role: admin, tester, viewer (required)
     * @returns {Promise<Object>} Created user
     */
    async create(data) {
        return apiRequest.post('/users', data);
    },

    /**
     * Update user
     * @param {number} id - User ID
     * @param {Object} data - User data to update
     * @param {string} data.email - Email address
     * @param {string} data.role - Role: admin, tester, viewer
     * @param {string} data.password - New password (optional)
     * @returns {Promise<Object>} Updated user
     */
    async update(id, data) {
        return apiRequest.put(`/users/${id}`, data);
    },

    /**
     * Permanently delete user
     * @param {number} id - User ID
     * @returns {Promise<void>}
     */
    async delete(id) {
        return apiRequest.delete(`/users/${id}`);
    },

    /**
     * Reactivate user (admin endpoint for users that were soft-deactivated
     * before delete became a hard delete)
     * @param {number} id - User ID
     * @returns {Promise<void>}
     */
    async reactivate(id) {
        return apiRequest.post(`/users/${id}/activate`);
    },

    // ==================== Engagement Team Members ====================

    /**
     * Get all team members for an engagement
     * @param {number} engagementId - Engagement ID
     * @returns {Promise<Array>} List of engagement members with roles
     */
    async getEngagementMembers(engagementId) {
        const response = await apiRequest.get(`/engagements/${engagementId}/members`);
        return response.members || [];
    },

    /**
     * Add member to engagement
     * @param {number} engagementId - Engagement ID
     * @param {Object} data - Member data
     * @param {number} data.user_id - User ID
     * @param {string} data.role - Role: owner, editor, viewer
     * @returns {Promise<Object>} Created member record
     */
    async addEngagementMember(engagementId, data) {
        return apiRequest.post(`/engagements/${engagementId}/members`, data);
    },

    /**
     * Update member role
     * @param {number} engagementId - Engagement ID
     * @param {number} memberId - Member ID
     * @param {Object} data - Update data
     * @param {string} data.role - New role: owner, editor, viewer
     * @returns {Promise<Object>} Updated member record
     */
    async updateMemberRole(engagementId, memberId, data) {
        return apiRequest.put(`/engagements/${engagementId}/members/${memberId}`, data);
    },

    /**
     * Remove member from engagement
     * @param {number} engagementId - Engagement ID
     * @param {number} memberId - Member ID
     * @returns {Promise<void>}
     */
    async removeMember(engagementId, memberId) {
        return apiRequest.delete(`/engagements/${engagementId}/members/${memberId}`);
    }
};
