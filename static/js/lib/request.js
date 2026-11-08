/**
 * Base API request handler with standardized error handling
 *
 * Provides a consistent interface for all HTTP requests with:
 * - Automatic JSON/FormData handling
 * - Standardized error handling
 * - Response type detection (JSON, Blob, Text)
 * - Credential management
 */
class APIRequest {
    /**
     * Create a new API request handler
     * @param {string} baseURL - Base URL for all API requests (default: '/api')
     */
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }

    /**
     * Make an HTTP request
     * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
     * @param {string} endpoint - API endpoint path
     * @param {Object} options - Request options
     * @param {Object} options.body - Request body (will be JSON stringified)
     * @param {FormData} options.formData - FormData for file uploads
     * @param {Object} options.headers - Additional headers
     * @param {Object} options.params - URL query parameters
     * @returns {Promise<any>} Response data
     */
    async request(method, endpoint, options = {}) {
        // Build URL with query parameters
        let url = `${this.baseURL}${endpoint}`;
        if (options.params) {
            const queryString = new URLSearchParams(options.params).toString();
            url += `?${queryString}`;
        }

        // Build request config
        const config = {
            method,
            headers: {
                ...options.headers
            },
            credentials: 'same-origin'
        };

        // Add CSRF token for mutating requests (login and setup included; L-8)
        const mutating = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);
        if (mutating) {
            let csrfToken = this._getCsrfToken();
            if (!csrfToken) {
                csrfToken = await this.refreshCsrfToken().catch(() => null);
            }
            if (csrfToken) {
                config.headers['X-CSRF-Token'] = csrfToken;
            }
        }

        // Handle different body types
        if (options.body) {
            config.headers['Content-Type'] = 'application/json';
            config.body = JSON.stringify(options.body);
        }

        if (options.formData) {
            // Let browser set Content-Type with boundary for multipart/form-data
            delete config.headers['Content-Type'];
            config.body = options.formData;
        }

        try {
            let response = await fetch(url, config);
            // A token from before this session (e.g. issued before login) is refused:
            // fetch the session's token once and retry.
            if (mutating && response.status === 403) {
                const body = await response.clone().json().catch(() => ({}));
                if (/^CSRF token/.test(body.error || '')) {
                    const fresh = await this.refreshCsrfToken().catch(() => null);
                    if (fresh) {
                        config.headers['X-CSRF-Token'] = fresh;
                        response = await fetch(url, config);
                    }
                }
            }
            const data = await this.handleResponse(response);
            return data;
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * Handle response based on content type
     * @param {Response} response - Fetch API response
     * @returns {Promise<any>} Parsed response data
     * @throws {Error} If response is not ok
     */
    async handleResponse(response) {
        if (!response.ok) {
            // Try to extract error message from JSON response
            const error = await response.json().catch(() => ({
                error: `HTTP ${response.status}: ${response.statusText}`
            }));

            // Handle 401 — redirect to login with reason. Skip for the
            // auth endpoints themselves: a 401 from /auth/login means the
            // user typed the wrong credentials, not that an existing
            // session expired. Letting the form catch the error keeps the
            // user on the login page so they can retry.
            if (response.status === 401) {
                const url = response.url || '';
                const isAuthEndpoint = /\/auth\/(login|setup)\b/.test(url);
                if (!isAuthEndpoint) {
                    const errorMsg = error.error || '';
                    if (errorMsg === 'session_idle_timeout') {
                        window.location.href = '/?reason=idle';
                    } else {
                        window.location.href = '/?reason=expired';
                    }
                    // Return a never-resolving promise to stop further processing
                    return new Promise(() => {});
                }
            }

            throw new Error(error.error || `HTTP ${response.status}`);
        }

        const contentType = response.headers.get('content-type');

        // Handle JSON responses
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        }

        // Handle binary responses (PDF, images, etc.)
        if (contentType && (
            contentType.includes('application/pdf') ||
            contentType.includes('application/vnd.openxmlformats-officedocument') ||
            contentType.includes('image/')
        )) {
            return await response.blob();
        }

        // Handle text responses (plain text, HTML, etc.)
        return await response.text();
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint path
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    get(endpoint, options = {}) {
        return this.request('GET', endpoint, options);
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint path
     * @param {Object} body - Request body (will be JSON stringified)
     * @param {Object} options - Additional request options
     * @returns {Promise<any>} Response data
     */
    post(endpoint, body, options = {}) {
        return this.request('POST', endpoint, { ...options, body });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint path
     * @param {Object} body - Request body (will be JSON stringified)
     * @param {Object} options - Additional request options
     * @returns {Promise<any>} Response data
     */
    put(endpoint, body, options = {}) {
        return this.request('PUT', endpoint, { ...options, body });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint path
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, options);
    }

    /**
     * Upload file(s) using FormData
     * @param {string} endpoint - API endpoint path
     * @param {FormData} formData - FormData with files and other fields
     * @param {Object} options - Additional request options
     * @returns {Promise<any>} Response data
     */
    upload(endpoint, formData, options = {}) {
        return this.request('POST', endpoint, { ...options, formData });
    }

    /**
     * Get CSRF token from cookie
     * @returns {string|null} CSRF token or null
     */
    _getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
        return match ? decodeURIComponent(match[1]) : null;
    }

    /**
     * Fetch a fresh CSRF token from the server
     * @returns {Promise<string>} The CSRF token
     */
    async refreshCsrfToken() {
        const response = await fetch(`${this.baseURL}/auth/csrf-token`, {
            credentials: 'same-origin'
        });
        const data = await response.json();
        return data.csrf_token;
    }
}

// Export singleton instance
const apiRequest = new APIRequest();

export { APIRequest, apiRequest };
