/* Apply the saved theme before first paint (loaded in <head>; moved out of the editors, L-21). */
// Apply theme before first paint to prevent flash
(function() {
    var theme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
})();
