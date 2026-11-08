/* Note editor page (moved out of note_editor.html: the CSP allows no inline script, L-21). */
// Get parameters from URL
const urlParams = new URLSearchParams(window.location.search);
const hostId = urlParams.get('host_id');
const noteType = urlParams.get('type') || 'host'; // 'host' or 'engagement'
const noteId = urlParams.get('note_id') ? parseInt(urlParams.get('note_id')) : null;
const returnHost = urlParams.get('return_host');
const returnTab = urlParams.get('return_tab');
// When the tree's add-sibling / add-child buttons land here, they
// pass the intended parent_id so the new note slots into the tree
// correctly. Null/absent => root-level note.
const parentIdParam = urlParams.get('parent_id');
const parentId = parentIdParam ? parseInt(parentIdParam) : null;

// Set page title and button text based on mode
if (noteId) {
    document.querySelector('.page-header h1').textContent = 'Edit Note';
    document.getElementById('saveNoteBtn').textContent = 'Save Changes';
}

function getDashboardReturnUrl() {
    const params = new URLSearchParams();
    if (returnHost) params.set('host', returnHost);
    if (returnTab) params.set('tab', returnTab);
    const qs = params.toString();
    return '/dashboard' + (qs ? '?' + qs : '');
}

// Initialize EasyMDE
const easyMDE = new EasyMDE({
    element: document.getElementById('noteContent'),
    autoDownloadFontAwesome: false,  // vendored in static/vendor; never fetch from a CDN
    placeholder: '# My Note\n\nAdd content here...\n\n**Bold**, *italic*, `code`',
    spellChecker: false,
    autosave: { enabled: false },
    minHeight: '520px',
    toolbar: [
        'bold', 'italic', 'heading', '|',
        'quote', 'code', 'unordered-list', 'ordered-list', '|',
        'link',
        {
            name: 'upload-image',
            action: () => document.getElementById('noteImageInput').click(),
            className: 'fa fa-image',
            title: 'Upload Image'
        },
        '|',
        'preview', 'side-by-side', 'fullscreen', '|',
        'guide'
    ],
    previewRender: plainText => renderMarkdown(plainText)   // sanitized (H-9)
});

// Clipboard image paste — see static/js/clipboard_image_paste.js
attachClipboardImagePaste(easyMDE, {
    engagementId: function () {
        return window.AppState && window.AppState.activeEngagement
            ? window.AppState.activeEngagement.id
            : null;
    },
    hostId: function () {
        // hostId is parsed from the URL (host_id param) at the top of this script.
        // noteType is 'host' when this editor is serving a host-scoped note.
        return noteType === 'host' && hostId ? parseInt(hostId) : null;
    },
    onError: function (msg) {
        if (window.showToast) window.showToast(msg, 'error');
        else console.warn(msg);
    },

});

// Initialize theme and load existing content
document.addEventListener('DOMContentLoaded', async function() {
    ThemeManager.init();

    if (noteId) {
        try {
            let note;
            if (noteType === 'engagement') {
                const activeData = await API.engagements.getActive();
                const engId = activeData.id || activeData.active_engagement_id;
                note = await API.engagements.getNote(engId, noteId);
            } else {
                note = await API.hosts.getNote(parseInt(hostId), noteId);
            }
            if (note && note.content !== undefined) {
                easyMDE.value(note.content);
            }
        } catch (error) {
            console.error('Failed to load note for editing:', error);
        }
    }
});

// Handle image file upload via hidden input
function handleNoteImage() {
    const fileInput = document.getElementById('noteImageInput');
    const file = fileInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const markdown = `\n![image](${e.target.result})\n`;
        easyMDE.codemirror.replaceSelection(markdown);
        fileInput.value = '';
    };
    reader.readAsDataURL(file);
}

async function saveNote() {
    const content = easyMDE.value().trim();

    if (!content) {
        alert('Please enter some content for the note');
        return;
    }

    try {
        if (noteId) {
            // Edit mode — update existing note
            if (noteType === 'engagement') {
                const activeData = await API.engagements.getActive();
                const engId = activeData.id || activeData.active_engagement_id;
                await API.engagements.updateNote(engId, noteId, content);
            } else {
                await API.hosts.updateNote(parseInt(hostId), noteId, content);
            }
        } else {
            // Create mode — new note
            const activeData = await API.engagements.getActive();
            const activeEngagementId = activeData.id || activeData.active_engagement_id || null;

            if (!activeEngagementId) {
                alert('No active engagement. Please select an engagement first.');
                window.location.href = '/dashboard';
                return;
            }

            const payload = parentId
                ? { content, parent_id: parentId }
                : { content };
            if (noteType === 'engagement') {
                await API.engagements.createNote(activeEngagementId, payload);
            } else {
                if (!hostId) {
                    alert('No host selected');
                    return;
                }
                await API.hosts.createNote(parseInt(hostId), payload);
            }
        }

        window.location.href = getDashboardReturnUrl();
    } catch (error) {
        console.error('Failed to save note:', error);
        alert('Failed to save note. Please try again.');
    }
}

function cancelNote() {
    if (confirm('Discard this note?')) {
        window.location.href = getDashboardReturnUrl();
    }
}
