/**
 * Authentication API
 *
 * Handles user authentication, including setup, login, and logout.
 */
import { apiRequest } from '../lib/request.js';

export const AuthAPI = {
    /**
     * Setup first admin account
     * @param {Object} params - Setup parameters
     * @param {string} params.email - Admin email
     * @param {string} params.password - Admin password
     * @param {string} [params.full_name] - Admin full name
     * @returns {Promise<Object>} Response data with status and user_id
     */
    async setup({ email, password, full_name, enable_encryption }) {
        const result = await apiRequest.post('/auth/setup', { email, password, full_name, enable_encryption });
        // Fetch CSRF token after successful setup
        await apiRequest.refreshCsrfToken();
        return result;
    },

    /**
     * Login with email/username and password
     * @param {string} identity - User email or username
     * @param {string} password - User password
     * @returns {Promise<Object>} Response data with message and user_id
     */
    async login(identity, password) {
        const isEmail = identity.includes('@');
        const body = isEmail
            ? { email: identity, password }
            : { username: identity, password };
        const result = await apiRequest.post('/auth/login', body);
        // Fetch CSRF token after successful login
        await apiRequest.refreshCsrfToken();
        return result;
    },

    /**
     * Logout current session
     * @returns {Promise<Object>} Response data with confirmation message
     */
    async logout() {
        return apiRequest.post('/auth/logout', {});
    }
};
