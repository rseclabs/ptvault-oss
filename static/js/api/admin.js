/**
 * Admin API
 *
 * Handles administrative functions including CyberChef management and settings.
 */
import { apiRequest } from '../lib/request.js';

export const AdminAPI = {
    /**
     * Get CyberChef installation status
     * @returns {Promise<Object>} { installed, version, installed_at }
     */
    async getCyberChefStatus() {
        return apiRequest.get('/admin/cyberchef/status');
    },

    /**
     * Check for CyberChef updates
     * @returns {Promise<Object>} { current_version, latest_version, update_available, download_url }
     */
    async checkCyberChefUpdate() {
        return apiRequest.get('/admin/cyberchef/check-update');
    },

    /**
     * Install CyberChef
     * @returns {Promise<Object>} { success, version }
     */
    async installCyberChef() {
        return apiRequest.post('/admin/cyberchef/install', {});
    },

    /**
     * Update CyberChef to latest version
     * @returns {Promise<Object>} { success, old_version, new_version }
     */
    async updateCyberChef() {
        return apiRequest.post('/admin/cyberchef/update', {});
    },

    /**
     * Get encryption status
     * @returns {Promise<Object>} { available, enabled, key_file_exists, salt_file_exists, encryption_required }
     */
    async getEncryptionStatus() {
        return apiRequest.get('/admin/encryption/status');
    },

    /**
     * Enable database encryption
     * @param {string} password - Database passphrase; the key is derived from it and held in memory
     * @returns {Promise<Object>} { success, message, salt_file }
     */
    async enableEncryption(password) {
        return apiRequest.post('/admin/encryption/enable', { password });
    },

    /**
     * Disable database encryption
     * @returns {Promise<Object>} { success, message }
     */
    async disableEncryption() {
        return apiRequest.post('/admin/encryption/disable', {});
    },

    /**
     * Recover encryption key from password
     * @param {string} password - Admin password
     * @returns {Promise<Object>} { success, message }
     */
    async recoverEncryptionKey(password) {
        return apiRequest.post('/admin/encryption/recover', { password });
    },

    /**
     * Get admin settings
     * @returns {Promise<Object>} Settings object
     */
    async getSettings() {
        return apiRequest.get('/admin/settings');
    },

    /**
     * Update admin settings
     * @param {Object} settings - Settings to update
     * @returns {Promise<Object>} Updated settings
     */
    async updateSettings(settings) {
        return apiRequest.put('/admin/settings', settings);
    },

    /**
     * Get idle timeout setting (available to all authenticated users)
     * @returns {Promise<Object>} { idle_timeout_minutes }
     */
    async getIdleTimeout() {
        return apiRequest.get('/admin/settings/idle-timeout');
    }
};
