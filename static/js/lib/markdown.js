/**
 * The one Markdown renderer (H-9).
 *
 * marked passes raw HTML through, and Markdown here includes imported scan
 * output and text any teammate can write, so marked's output is always
 * sanitized with the vendored DOMPurify before it reaches the DOM. Nothing
 * else calls marked; tests/test_markdown_xss.py enforces that.
 *
 * Load order: marked, then DOMPurify, then this file.
 */
(function () {
    'use strict';

    const SANITIZE = {
        USE_PROFILES: { html: true },      // no SVG or MathML
        // No forms, frames or styles; ids/names could clobber the app's own elements.
        FORBID_TAGS: ['style', 'form', 'button', 'textarea', 'select', 'option', 'iframe', 'frame',
                      'object', 'embed', 'link', 'meta', 'base'],
        FORBID_ATTR: ['style', 'id', 'name', 'formaction', 'action', 'srcset'],
        // data-* would let Markdown trigger registerAction() handlers (data-action).
        ALLOW_DATA_ATTR: false,
    };

    if (typeof marked !== 'undefined') {
        // GFM line breaks: single newline = <br>, double newline = paragraph.
        marked.use({ breaks: true, gfm: true });
    }

    if (window.DOMPurify && window.DOMPurify.addHook) {
        window.DOMPurify.addHook('afterSanitizeAttributes', node => {
            if (node.tagName === 'A' && /^https?:/i.test(node.getAttribute('href') || '')) {
                node.setAttribute('target', '_blank');
                node.setAttribute('rel', 'noopener noreferrer');
            }
            // GFM task lists render as checkboxes; any other input becomes an inert one.
            if (node.tagName === 'INPUT') {
                node.setAttribute('type', 'checkbox');
                node.setAttribute('disabled', '');
            }
        });
    }

    function escapeText(text) {
        return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    }

    /**
     * Render Markdown to sanitized HTML. Without marked or DOMPurify it returns
     * escaped text (fails closed), never unsanitized HTML.
     * @param {string} text
     * @returns {string}
     */
    function renderMarkdown(text) {
        if (text === null || text === undefined || text === '') return '';
        const source = String(text);
        const purify = window.DOMPurify;
        if (typeof marked === 'undefined' || !purify || !purify.isSupported) {
            return escapeText(source).replace(/\n/g, '<br>');
        }
        return purify.sanitize(marked.parse(source), SANITIZE);
    }

    window.renderMarkdown = renderMarkdown;
})();
