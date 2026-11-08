/* Slide-over drawers (moved out of dashboard.html: the CSP allows no inline script, L-21). */
const SlideOver = {
    open(name) {
        const backdrop = document.getElementById(name + 'Backdrop');
        const drawer = document.getElementById(name + 'Drawer');
        if (backdrop) backdrop.classList.add('is-open');
        if (drawer) {
            drawer.classList.add('is-open');
            // Focus first focusable element
            const focusable = drawer.querySelector('input, textarea, select, button');
            if (focusable) setTimeout(() => focusable.focus(), 50);
        }
        document.body.classList.add('slide-over-open');
    },
    close(name) {
        const backdrop = document.getElementById(name + 'Backdrop');
        const drawer = document.getElementById(name + 'Drawer');
        if (backdrop) backdrop.classList.remove('is-open');
        if (drawer) drawer.classList.remove('is-open');
        document.body.classList.remove('slide-over-open');
    }
};

// Close active slide-over on Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.slide-over.is-open').forEach(drawer => {
            const name = drawer.id.replace('Drawer', '');
            SlideOver.close(name);
        });
    }
});

window.SlideOver = SlideOver;   // named in data-on-click attributes (L-21)
