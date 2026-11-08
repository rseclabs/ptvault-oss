/* Login page (moved out of login.html: the CSP allows no inline script, L-21). */
// Show idle timeout message if redirected with ?reason=idle
(function() {
    const params = new URLSearchParams(window.location.search);
    const reason = params.get('reason');
    if (reason === 'idle') {
        const msg = document.getElementById('idleMessage');
        if (msg) msg.style.display = 'block';
    }
})();
