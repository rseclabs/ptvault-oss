/**
 * Unlock page (M-8): send the database passphrase to /api/unlock.
 * The page loads before anyone can log in, so it does not use the API module.
 */
(function () {
    'use strict';

    const form = document.getElementById('unlockForm');
    const input = document.getElementById('passphrase');
    const errorEl = document.getElementById('errorMessage');
    const button = form.querySelector('button[type="submit"]');

    function csrfFromCookie() {
        const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
        return match ? decodeURIComponent(match[1]) : null;
    }

    async function csrfToken() {
        const existing = csrfFromCookie();
        if (existing) return existing;
        const resp = await fetch('/api/auth/csrf-token', { credentials: 'same-origin' });
        return (await resp.json()).csrf_token;
    }

    function setBusy(busy) {
        button.disabled = busy;
        button.querySelector('.btn-text').style.display = busy ? 'none' : '';
        button.querySelector('.btn-loading').style.display = busy ? '' : 'none';
    }

    function showError(message) {
        errorEl.textContent = message;
        errorEl.style.display = '';
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.style.display = 'none';
        setBusy(true);
        try {
            const resp = await fetch('/api/unlock', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await csrfToken() },
                body: JSON.stringify({ passphrase: input.value }),
            });
            if (resp.ok) {
                window.location.href = '/';
                return;
            }
            const data = await resp.json().catch(() => ({}));
            showError(resp.status === 429 ? 'Too many attempts. Wait a minute and try again.'
                                          : (data.error || 'Could not unlock the database'));
        } catch (e) {
            showError('Could not reach PTVault');
        } finally {
            input.value = '';
            setBusy(false);
            input.focus();
        }
    });
})();
