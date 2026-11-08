/* Lucide icons on the dashboard (moved out of dashboard.html, L-21). */
document.addEventListener('DOMContentLoaded', function() {
    if (typeof lucide === 'undefined') return;
    lucide.createIcons();
    // Icons rendered later by the section scripts are drawn on the next frame.
    let pending = false;
    new MutationObserver(function() {
        if (pending || !document.querySelector('[data-lucide]:not(svg)')) return;
        pending = true;
        requestAnimationFrame(function() {
            pending = false;
            lucide.createIcons();
        });
    }).observe(document.body, { childList: true, subtree: true });
});
