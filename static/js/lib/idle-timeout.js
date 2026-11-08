/**
 * IdleTimeoutManager
 *
 * Tracks user activity and enforces idle timeout with a warning dialog.
 * - Monitors mousemove, keydown, scroll, click, touchstart
 * - Shows a countdown warning 60 seconds before timeout
 * - Sends a heartbeat on activity (at most once a minute) and on "Stay Logged In",
 *   so the server's idle check matches what the user is doing in the page
 * - Forces logout when timeout expires
 */
class IdleTimeoutManager {
    constructor() {
        this.timeoutMinutes = 15; // default, loaded from server
        this.warningSeconds = 60; // show warning this many seconds before timeout
        this.lastActivity = Date.now();
        this.warningTimer = null;
        this.logoutTimer = null;
        this.countdownInterval = null;
        this.activityThrottle = null;
        this.lastHeartbeat = Date.now();
        this.dialogEl = null;
        this.started = false;
    }

    /**
     * Initialize: fetch timeout from server and start tracking.
     */
    async start() {
        if (this.started) return;
        this.started = true;

        try {
            const resp = await fetch('/api/admin/settings/idle-timeout', { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                this.timeoutMinutes = data.idle_timeout_minutes || 15;
            }
        } catch (e) {
            // Use default
        }

        this._bindActivityEvents();
        this._resetTimers();
    }

    /**
     * Stop all tracking and timers.
     */
    stop() {
        this.started = false;
        this._clearTimers();
        this._unbindActivityEvents();
        this._removeDialog();
    }

    /**
     * Bind activity tracking events (throttled).
     */
    _bindActivityEvents() {
        this._activityHandler = () => this._onActivity();
        const events = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'];
        events.forEach(evt => document.addEventListener(evt, this._activityHandler, { passive: true }));
    }

    _unbindActivityEvents() {
        if (!this._activityHandler) return;
        const events = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'];
        events.forEach(evt => document.removeEventListener(evt, this._activityHandler));
        this._activityHandler = null;
    }

    /**
     * Called on user activity. Throttled to avoid excessive timer resets.
     * Ignored while the warning dialog is showing — only "Stay Logged In" resets.
     */
    _onActivity() {
        // Don't reset if the warning dialog is already showing
        if (this.dialogEl) return;

        this.lastActivity = Date.now();

        // Typing or reading makes no API call, so tell the server the session is in use.
        if (this.lastActivity - this.lastHeartbeat >= 60000) {
            this._sendHeartbeat();
        }

        // Throttle timer resets to every 30 seconds
        if (this.activityThrottle) return;
        this.activityThrottle = setTimeout(() => {
            this.activityThrottle = null;
        }, 30000);

        this._resetTimers();
    }

    /**
     * Reset warning and logout timers based on current activity.
     */
    _resetTimers() {
        this._clearTimers();

        const timeoutMs = this.timeoutMinutes * 60 * 1000;
        const warningMs = timeoutMs - (this.warningSeconds * 1000);

        if (warningMs > 0) {
            this.warningTimer = setTimeout(() => this._showWarning(), warningMs);
        }
        this.logoutTimer = setTimeout(() => this._forceLogout(), timeoutMs);
    }

    _clearTimers() {
        if (this.warningTimer) { clearTimeout(this.warningTimer); this.warningTimer = null; }
        if (this.logoutTimer) { clearTimeout(this.logoutTimer); this.logoutTimer = null; }
        if (this.countdownInterval) { clearInterval(this.countdownInterval); this.countdownInterval = null; }
        if (this.activityThrottle) { clearTimeout(this.activityThrottle); this.activityThrottle = null; }
    }

    /**
     * Show the warning dialog with a countdown.
     */
    _showWarning() {
        this._removeDialog();

        let remaining = this.warningSeconds;

        const overlay = document.createElement('div');
        overlay.id = 'idleTimeoutOverlay';
        overlay.style.cssText = `
            position: fixed; inset: 0; z-index: 99999;
            background: rgba(0,0,0,0.6);
            display: flex; align-items: center; justify-content: center;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-secondary, #1e293b); color: var(--text-primary, #e2e8f0);
            border: 1px solid var(--border-color, #334155);
            border-radius: 8px; padding: 2rem; max-width: 400px; width: 90%;
            text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        `;

        dialog.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                     style="color: var(--warning-color, #f59e0b); margin: 0 auto;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
            </div>
            <h3 style="margin: 0 0 0.5rem; font-size: 1.25rem;">Session Expiring</h3>
            <p style="margin: 0 0 1.5rem; color: var(--text-muted, #94a3b8);">
                Your session will expire in <strong id="idleCountdown">${remaining}</strong> seconds due to inactivity.
            </p>
            <button id="idleStayBtn" style="
                background: var(--primary-color, #3b82f6); color: white;
                border: none; border-radius: 6px; padding: 0.625rem 1.5rem;
                font-size: 0.9375rem; cursor: pointer; font-weight: 500;
            ">Stay Logged In</button>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        this.dialogEl = overlay;

        // Countdown
        const countdownEl = document.getElementById('idleCountdown');
        this.countdownInterval = setInterval(() => {
            remaining--;
            if (countdownEl) countdownEl.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
            }
        }, 1000);

        // Stay logged in button
        document.getElementById('idleStayBtn').addEventListener('click', () => this._stayLoggedIn());
    }

    _removeDialog() {
        if (this.dialogEl) {
            this.dialogEl.remove();
            this.dialogEl = null;
        }
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }

    /**
     * User clicked "Stay Logged In" — send heartbeat and reset timers.
     */
    async _stayLoggedIn() {
        this._removeDialog();
        this.lastActivity = Date.now();
        await this._sendHeartbeat();
        this._resetTimers();
    }

    /**
     * Mark the server session active and pick up any timeout change.
     */
    async _sendHeartbeat() {
        this.lastHeartbeat = Date.now();
        try {
            const csrfMatch = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
            const headers = { 'Content-Type': 'application/json' };
            if (csrfMatch) headers['X-CSRF-Token'] = decodeURIComponent(csrfMatch[1]);

            const resp = await fetch('/api/auth/heartbeat', {
                method: 'POST',
                credentials: 'same-origin',
                headers
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.idle_timeout_minutes) {
                    this.timeoutMinutes = data.idle_timeout_minutes;
                }
            }
        } catch (e) {
            // Best effort: local timers still track activity
        }
    }

    /**
     * Force logout: call logout API and redirect to login page.
     */
    async _forceLogout() {
        this.stop();

        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                credentials: 'same-origin'
            });
        } catch (e) {
            // Best effort
        }

        window.location.href = '/?reason=idle';
    }
}

// Singleton instance, available globally
const idleTimeoutManager = new IdleTimeoutManager();
window.idleTimeoutManager = idleTimeoutManager;

export { IdleTimeoutManager, idleTimeoutManager };
