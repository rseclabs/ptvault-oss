/**
 * PTVault Utility Functions
 * Helper functions for UI and data formatting
 */

/**
 * Format date to human-readable string
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';

    const date = new Date(dateString);
    const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };

    return date.toLocaleDateString('en-US', options);
}

/**
 * Get relative time string (e.g., "2 hours ago")
 * @param {string} dateString - ISO date string
 * @returns {string} Relative time string
 */
function timeSince(dateString) {
    if (!dateString) return 'N/A';

    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    let interval = Math.floor(seconds / 31536000);
    if (interval >= 1) {
        return interval === 1 ? '1 year ago' : `${interval} years ago`;
    }

    interval = Math.floor(seconds / 2592000);
    if (interval >= 1) {
        return interval === 1 ? '1 month ago' : `${interval} months ago`;
    }

    interval = Math.floor(seconds / 86400);
    if (interval >= 1) {
        return interval === 1 ? '1 day ago' : `${interval} days ago`;
    }

    interval = Math.floor(seconds / 3600);
    if (interval >= 1) {
        return interval === 1 ? '1 hour ago' : `${interval} hours ago`;
    }

    interval = Math.floor(seconds / 60);
    if (interval >= 1) {
        return interval === 1 ? '1 minute ago' : `${interval} minutes ago`;
    }

    return 'just now';
}

/**
 * Get severity icon/emoji
 * @param {string} severity - Severity level (critical, high, medium, low)
 * @returns {string} Emoji icon
 */
function getSeverityIcon(severity) {
    const icons = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🔵'
    };

    return icons[severity?.toLowerCase()] || '';
}

/**
 * Get severity color class
 * @param {string} severity - Severity level
 * @returns {string} CSS class name
 */
function getSeverityColor(severity) {
    const colors = {
        'critical': 'critical',
        'high': 'high',
        'medium': 'medium',
        'low': 'low'
    };

    return colors[severity?.toLowerCase()] || '';
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';

    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Toast type (success, error, warning, info)
 * @param {number} duration - Duration in ms (default 3000)
 */
function showToast(message, type = 'info', duration = 3000) {
    // Create toast container if it doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    // Add to container
    container.appendChild(toast);

    // Remove after duration
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(400px)';

        setTimeout(() => {
            container.removeChild(toast);

            // Remove container if empty
            if (container.children.length === 0) {
                document.body.removeChild(container);
            }
        }, 300);
    }, duration);
}

/**
 * Theme management
 */
const ThemeManager = {
    /**
     * Get current theme
     * @returns {string} 'light' or 'dark'
     */
    getTheme() {
        return localStorage.getItem('theme') || 'dark'; // Default to dark for pentesters
    },

    /**
     * Set theme
     * @param {string} theme - 'light' or 'dark'
     */
    setTheme(theme) {
        localStorage.setItem('theme', theme);
        document.documentElement.setAttribute('data-theme', theme);

        // Update theme icon
        const themeIcon = document.querySelector('.theme-icon');
        if (themeIcon) {
            themeIcon.textContent = theme === 'dark' ? '🌙' : '☀️';
        }
    },

    /**
     * Toggle theme
     */
    toggleTheme() {
        const currentTheme = this.getTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },

    /**
     * Initialize theme
     */
    init() {
        const theme = this.getTheme();
        this.setTheme(theme);
    }
};

/**
 * Modal management
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';

        // Focus first input
        const firstInput = modal.querySelector('input, textarea, select');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';

        // Reset form if present
        const form = modal.querySelector('form');
        if (form) {
            form.reset();

            // Clear error messages
            const errorMsg = modal.querySelector('.error-message');
            if (errorMsg) {
                errorMsg.style.display = 'none';
                errorMsg.textContent = '';
            }
        }
    }
}

// Close modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
});

/**
 * Download blob as file
 * @param {Blob} blob - File blob
 * @param {string} filename - Filename
 */
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

/**
 * Format file size
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted size
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Truncate text
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
function truncate(text, maxLength = 100) {
    if (!text) return '';
    if (text.length <= maxLength) return text;

    return text.substring(0, maxLength) + '...';
}

/**
 * Parse tags from comma-separated string
 * @param {string} tagsString - Comma-separated tags
 * @returns {Array} Array of tag strings
 */
function parseTags(tagsString) {
    if (!tagsString) return [];

    return tagsString
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0);
}

/**
 * Get evidence type display name
 * @param {string} type - Evidence type
 * @returns {string} Display name
 */
function getEvidenceTypeDisplay(type) {
    const types = {
        'note': 'Note',
        'screenshot': 'Screenshot',
        'command_output': 'Command Output',
        'tool_output': 'Tool Output',
        'other': 'Other'
    };

    return types[type] || type;
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;

    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };

        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Handle keyboard shortcuts
 */
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+N: New evidence
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            const newEvidenceBtn = document.getElementById('newEvidenceBtn');
            if (newEvidenceBtn) {
                newEvidenceBtn.click();
            }
        }

        // Ctrl+F: Focus search
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
    });
}

// Make utilities available globally
window.formatDate = formatDate;
window.timeSince = timeSince;
window.getSeverityIcon = getSeverityIcon;
window.getSeverityColor = getSeverityColor;
window.escapeHtml = escapeHtml;
window.showToast = showToast;
window.ThemeManager = ThemeManager;
window.openModal = openModal;
window.closeModal = closeModal;
window.downloadBlob = downloadBlob;
window.formatFileSize = formatFileSize;
window.truncate = truncate;
window.parseTags = parseTags;
window.getEvidenceTypeDisplay = getEvidenceTypeDisplay;
window.debounce = debounce;
window.initKeyboardShortcuts = initKeyboardShortcuts;
