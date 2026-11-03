/**
 * NotesTreeView — shared hierarchical-notes list pane.
 *
 * One instance per scope (engagement-general, host). Renders an indented
 * tree, wires the toolbar (sibling/child create, move-up/down,
 * indent/outdent), and supports HTML5 drag-drop reordering.
 *
 * Data model: a flat array of note rows from the server, each with
 *   { id, parent_id, sort_order, content_preview, has_more,
 *     content_length, created_at, updated_at }.
 * The tree is built client-side by grouping on parent_id.
 *
 * The view does not edit note content itself — selection / "edit" /
 * "create" actions navigate to the existing /note/new editor page,
 * passing parent_id when the tree button dictates it.
 */
(function () {
    'use strict';

    /**
     * @typedef {Object} NotesTreeViewConfig
     * @property {string} containerId   - DOM id of the list-pane <div>.
     * @property {string} toolbarId     - DOM id of the toolbar <div>.
     * @property {Object} api           - API namespace (e.g. API.hosts or API.engagements).
     * @property {string} apiNoun       - 'host' | 'engagement' (used by editor URL).
     * @property {() => number|null} scopeId - Returns the current host_id or engagement_id.
     * @property {string} editorReturnTab     - return_tab query param ('notes' typically).
     * @property {string|number} editorReturnHost - return_host param ('general' or host id).
     */

    class NotesTreeView {
        constructor(config) {
            this.cfg = config;
            this.notes = [];
            this.selectedId = null;
            this._dragId = null;
            this._editorTypeFromNoun = {
                'engagement': 'engagement',
                'host': 'host',
            };

            // Inline editor state
            this._editor = null;          // EasyMDE instance
            this._editorNoteId = null;    // note currently loaded into the editor
            this._editorOriginal = '';    // last server-known content for dirty check

            this._bindToolbar();
            this._bindKeyboard();
            this._bindEditorPane();
        }

        async refresh() {
            const sid = this.cfg.scopeId();
            if (sid == null) {
                this._renderEmpty('No scope selected');
                return;
            }
            try {
                const resp = await this.cfg.api.getNotes(sid);
                // /api/hosts/<id>/notes returns {notes:[...]}; /api/engagements/<id>/notes returns the array directly.
                this.notes = Array.isArray(resp) ? resp : (resp.notes || []);
                this._render();
            } catch (err) {
                console.error('NotesTreeView refresh failed:', err);
                this._renderEmpty('Failed to load notes');
            }
        }

        // ---------- internal: rendering ----------

        _container() {
            return document.getElementById(this.cfg.containerId);
        }

        _renderEmpty(msg) {
            const c = this._container();
            if (c) c.innerHTML = `<div class="empty-state"><p>${escapeHtml(msg)}</p></div>`;
        }

        _render() {
            const c = this._container();
            if (!c) return;

            if (this.notes.length === 0) {
                c.innerHTML = '<div class="empty-state"><p>No notes yet</p></div>';
                return;
            }

            // Group children by parent_id
            const childrenByParent = new Map();
            for (const n of this.notes) {
                const pid = n.parent_id == null ? null : n.parent_id;
                if (!childrenByParent.has(pid)) childrenByParent.set(pid, []);
                childrenByParent.get(pid).push(n);
            }
            for (const arr of childrenByParent.values()) {
                arr.sort((a, b) => (a.sort_order - b.sort_order) || (a.id - b.id));
            }

            const html = `<ul class="notes-tree-root" data-depth="0">${this._renderChildren(childrenByParent, null, 0)}</ul>`;
            c.innerHTML = html;
            this._attachItemHandlers();
        }

        _renderChildren(childrenByParent, parentId, depth) {
            const items = childrenByParent.get(parentId) || [];
            return items.map(n => this._renderNode(n, childrenByParent, depth)).join('');
        }

        _renderNode(note, childrenByParent, depth) {
            const isSelected = note.id === this.selectedId;
            const title = this._noteTitle(note);
            const childrenHtml = this._renderChildren(childrenByParent, note.id, depth + 1);
            return `
                <li class="notes-tree-item ${isSelected ? 'is-selected' : ''}"
                    data-note-id="${note.id}"
                    data-parent-id="${note.parent_id == null ? '' : note.parent_id}"
                    data-sort-order="${note.sort_order}"
                    data-depth="${depth}"
                    draggable="true"
                    tabindex="0">
                    <div class="notes-tree-row" title="${escapeHtml(title)}">
                        <span class="notes-tree-indent" style="width:${depth * 16}px;"></span>
                        <span class="notes-tree-icon"><i data-lucide="file-text"></i></span>
                        <span class="notes-tree-title">${escapeHtml(title)}</span>
                        <span class="notes-tree-actions">
                            <button class="btn btn-sm btn-icon" data-act="delete" title="Delete"><i data-lucide="trash-2"></i></button>
                        </span>
                    </div>
                    ${childrenHtml ? `<ul class="notes-tree-children">${childrenHtml}</ul>` : ''}
                </li>
            `;
        }

        _noteTitle(note) {
            if (note.title) return note.title;
            // Fallback for notes without a stored title (legacy data)
            const src = note.content_preview || '';
            const firstLine = (src.split('\n').find(l => l.trim().length > 0) || '').trim();
            return firstLine.replace(/^#+\s*/, '') || '(empty note)';
        }

        // ---------- internal: event wiring ----------

        _attachItemHandlers() {
            const c = this._container();
            if (!c) return;

            c.querySelectorAll('.notes-tree-item').forEach(li => {
                const noteId = parseInt(li.dataset.noteId, 10);

                // Selection on row click (excluding action buttons)
                li.querySelector('.notes-tree-row').addEventListener('click', (e) => {
                    if (e.target.closest('button[data-act]')) return;
                    this._select(noteId);
                });

                // Action buttons
                li.querySelectorAll('button[data-act]').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const act = btn.dataset.act;
                        if (act === 'edit') this._editNote(noteId);
                        else if (act === 'delete') this._deleteNote(noteId);
                    });
                });

                // Drag & drop
                li.addEventListener('dragstart', (e) => {
                    e.stopPropagation();
                    this._dragId = noteId;
                    e.dataTransfer.setData('text/plain', String(noteId));
                    e.dataTransfer.effectAllowed = 'move';
                    li.classList.add('is-dragging');
                });
                li.addEventListener('dragend', () => {
                    li.classList.remove('is-dragging');
                    c.querySelectorAll('.drop-into, .drop-before, .drop-after').forEach(el => {
                        el.classList.remove('drop-into', 'drop-before', 'drop-after');
                    });
                    this._dragId = null;
                });
                li.addEventListener('dragover', (e) => {
                    if (this._dragId == null || this._dragId === noteId) return;
                    if (this._isDescendant(noteId, this._dragId)) return; // can't drop into own subtree
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'move';
                    const rect = li.querySelector('.notes-tree-row').getBoundingClientRect();
                    const y = e.clientY - rect.top;
                    li.classList.remove('drop-into', 'drop-before', 'drop-after');
                    if (y < rect.height * 0.25) li.classList.add('drop-before');
                    else if (y > rect.height * 0.75) li.classList.add('drop-after');
                    else li.classList.add('drop-into');
                });
                li.addEventListener('dragleave', () => {
                    li.classList.remove('drop-into', 'drop-before', 'drop-after');
                });
                li.addEventListener('drop', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (this._dragId == null || this._dragId === noteId) return;
                    if (this._isDescendant(noteId, this._dragId)) return;
                    const dragId = this._dragId;
                    const target = this._findNote(noteId);

                    let parentId, sortOrder;
                    if (li.classList.contains('drop-into')) {
                        parentId = noteId;
                        sortOrder = null;  // append to end of children
                    } else if (li.classList.contains('drop-before')) {
                        parentId = target.parent_id ?? null;
                        sortOrder = target.sort_order;  // insert before; siblings stay >=
                    } else {
                        parentId = target.parent_id ?? null;
                        sortOrder = target.sort_order + 0.5;
                        // Tell server null and let it append below; we'll
                        // refine ordering by passing sort_order = target+1
                        // and bumping target side via reorder is overkill
                        // for v1. Use null = "max+1 at the end" instead.
                        sortOrder = null;
                    }

                    li.classList.remove('drop-into', 'drop-before', 'drop-after');
                    await this._move(dragId, parentId, sortOrder);
                });
            });

            // Restore focus to selected after rerender
            if (this.selectedId) {
                const sel = c.querySelector(`.notes-tree-item[data-note-id="${this.selectedId}"]`);
                if (sel) sel.focus();
            }
        }

        _bindToolbar() {
            const tb = document.getElementById(this.cfg.toolbarId);
            if (!tb) return;
            tb.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-action]');
                if (!btn) return;
                const action = btn.dataset.action;
                this._dispatchAction(action);
            });
        }

        _bindKeyboard() {
            // Tab / Shift-Tab indent/outdent when a tree item has focus
            const c = this._container();
            if (!c) return;
            c.addEventListener('keydown', (e) => {
                const focused = e.target.closest('.notes-tree-item');
                if (!focused) return;
                if (e.key === 'Tab') {
                    e.preventDefault();
                    this._select(parseInt(focused.dataset.noteId, 10));
                    this._dispatchAction(e.shiftKey ? 'outdent' : 'indent');
                }
            });
        }

        _dispatchAction(action) {
            switch (action) {
                case 'add-sibling': return this._createSibling();
                case 'add-child':   return this._createChild();
                case 'move-up':     return this._moveUp();
                case 'move-down':   return this._moveDown();
                case 'indent':      return this._indent();
                case 'outdent':     return this._outdent();
            }
        }

        // ---------- actions ----------

        async _select(noteId) {
            // Confirm dirty state before swapping notes
            if (!await this._confirmIfDirty()) return;

            this.selectedId = noteId;
            const c = this._container();
            if (c) {
                c.querySelectorAll('.notes-tree-item.is-selected')
                    .forEach(el => el.classList.remove('is-selected'));
                const li = c.querySelector(`.notes-tree-item[data-note-id="${noteId}"]`);
                if (li) li.classList.add('is-selected');
            }
            await this._loadIntoEditor(noteId);
        }

        async _createSibling() {
            const sel = this.selectedId ? this._findNote(this.selectedId) : null;
            const parentId = sel ? (sel.parent_id ?? null) : null;
            await this._createInline(parentId);
        }

        async _createChild() {
            if (!this.selectedId) {
                showToast('Select a note first to create a child under it', 'warning');
                return;
            }
            await this._createInline(this.selectedId);
        }

        async _moveUp() {
            const note = this._findNote(this.selectedId);
            if (!note) return;
            const siblings = this._siblingsOf(note);
            const idx = siblings.findIndex(s => s.id === note.id);
            if (idx <= 0) return;
            const above = siblings[idx - 1];
            // Swap by giving us above's sort_order; bump above to ours
            await this._move(note.id, note.parent_id ?? null, above.sort_order - 0.5);
        }

        async _moveDown() {
            const note = this._findNote(this.selectedId);
            if (!note) return;
            const siblings = this._siblingsOf(note);
            const idx = siblings.findIndex(s => s.id === note.id);
            if (idx === -1 || idx >= siblings.length - 1) return;
            const below = siblings[idx + 1];
            await this._move(note.id, note.parent_id ?? null, below.sort_order + 0.5);
        }

        async _indent() {
            const note = this._findNote(this.selectedId);
            if (!note) return;
            const siblings = this._siblingsOf(note);
            const idx = siblings.findIndex(s => s.id === note.id);
            if (idx <= 0) return;
            const newParent = siblings[idx - 1];
            await this._move(note.id, newParent.id, null);  // append under new parent
        }

        async _outdent() {
            const note = this._findNote(this.selectedId);
            if (!note || note.parent_id == null) return;
            const parent = this._findNote(note.parent_id);
            const grandparentId = parent ? (parent.parent_id ?? null) : null;
            await this._move(note.id, grandparentId, null);  // append under grandparent
        }

        async _deleteNote(noteId) {
            const note = this._findNote(noteId);
            if (!note) return;
            const title = this._noteTitle(note);
            if (!confirm(`Delete note "${title}"? This cannot be undone.`)) return;

            const sid = this.cfg.scopeId();
            try {
                await this.cfg.api.deleteNote(sid, noteId);
                if (this.selectedId === noteId) {
                    this.selectedId = null;
                    this._clearEditor();
                }
                await this.refresh();
                showToast('Note deleted', 'success');
            } catch (err) {
                console.error('Delete failed:', err);
                // Surface 409 child-block message verbatim
                showToast(err.message || 'Failed to delete note', 'error');
            }
        }

        async _editNote(noteId) {
            // The "edit" pencil button now just selects the note so it
            // loads into the right-pane editor — no navigation away.
            await this._select(noteId);
        }

        async _createInline(parentId) {
            // Create an empty placeholder note via the API and slot it
            // into the tree at parent. Then select it so the editor pane
            // is ready to type into.
            const sid = this.cfg.scopeId();
            if (sid == null) return;

            if (!await this._confirmIfDirty()) return;

            try {
                const created = await this.cfg.api.createNote(sid, {
                    content: '',
                    title: 'New note',
                    parent_id: parentId,
                });
                await this.refresh();
                if (created && created.id) {
                    await this._select(created.id);
                    // Focus and select the title field so the user can type the name
                    const pane = this._editorPane();
                    const titleInput = pane && pane.querySelector('.notes-editor-title');
                    if (titleInput) {
                        titleInput.focus();
                        titleInput.select();
                    }
                }
            } catch (err) {
                console.error('Create note failed:', err);
                showToast(err.message || 'Failed to create note', 'error');
            }
        }

        async _move(noteId, parentId, sortOrder) {
            const sid = this.cfg.scopeId();
            try {
                await this.cfg.api.moveNote(sid, noteId, {
                    parent_id: parentId,
                    sort_order: sortOrder,
                });
                await this.refresh();
            } catch (err) {
                console.error('Move failed:', err);
                showToast(err.message || 'Failed to move note', 'error');
            }
        }

        // ---------- helpers ----------

        _findNote(id) {
            return this.notes.find(n => n.id === id);
        }

        _siblingsOf(note) {
            return this.notes
                .filter(n => (n.parent_id ?? null) === (note.parent_id ?? null))
                .sort((a, b) => (a.sort_order - b.sort_order) || (a.id - b.id));
        }

        /** True if `descendantId` is anywhere in `ancestorId`'s subtree. */
        _isDescendant(descendantId, ancestorId) {
            // Walk up from descendantId; if we hit ancestorId, return true.
            let current = this._findNote(descendantId);
            const seen = new Set();
            while (current && current.parent_id != null) {
                if (seen.has(current.id)) return false; // defensive
                seen.add(current.id);
                if (current.parent_id === ancestorId) return true;
                current = this._findNote(current.parent_id);
            }
            return false;
        }

        // ---------- inline editor pane ----------

        _editorPane() {
            return this.cfg.editorPaneId
                ? document.getElementById(this.cfg.editorPaneId)
                : null;
        }

        _bindEditorPane() {
            const pane = this._editorPane();
            if (!pane) return;
            const saveBtn = pane.querySelector('button[data-action="save"]');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => this._saveEditor());
            }

            // Title input is independent — editing it does not touch the
            // editor body, and editing the body does not change the title.
            const titleInput = pane.querySelector('.notes-editor-title');
            if (titleInput) {
                titleInput.addEventListener('input', () => {
                    this._updateDirtyIndicator();
                });
            }
        }

        /** Initialize EasyMDE on the pane's textarea (lazy, idempotent). */
        _initEditor() {
            if (this._editor) return this._editor;
            const pane = this._editorPane();
            if (!pane) return null;
            const textarea = pane.querySelector('.notes-editor-textarea');
            if (!textarea || typeof EasyMDE === 'undefined') return null;

            this._editor = new EasyMDE({
                element: textarea,
                placeholder: 'Start typing your note in markdown…',
                spellChecker: false,
                autosave: { enabled: false },
                minHeight: '420px',
                status: false,
                // EasyMDE otherwise injects a maxcdn.bootstrapcdn font-awesome
                // stylesheet that our CSP doesn't allow.
                autoDownloadFontAwesome: false,
                toolbar: [
                    'bold', 'italic', 'heading', '|',
                    'quote', 'code', 'unordered-list', 'ordered-list', '|',
                    'link', 'image', '|',
                    'preview', 'side-by-side', 'fullscreen', '|',
                    'guide',
                ],
                previewRender: function (plainText) {
                    if (typeof marked !== 'undefined') return marked.parse(plainText);
                    return plainText;
                },
            });

            // Clipboard image paste — uploads to /api/evidence, inserts markdown URL.
            if (typeof attachClipboardImagePaste === 'function') {
                const self = this;
                attachClipboardImagePaste(this._editor, {
                    engagementId: function () {
                        return window.AppState && window.AppState.activeEngagement
                            ? window.AppState.activeEngagement.id
                            : null;
                    },
                    hostId: function () {
                        return window.NotesContext && window.NotesContext.hostId != null
                            ? window.NotesContext.hostId
                            : null;
                    },
                    onError: function (msg) {
                        if (window.showToast) window.showToast(msg, 'error');
                        else console.warn(msg);
                    },
                });
            }

            this._editor.codemirror.on('change', () => {
                this._updateDirtyIndicator();
            });

            return this._editor;
        }

        async _loadIntoEditor(noteId) {
            const pane = this._editorPane();
            if (!pane) return;

            // Keep NotesContext.hostId current so clipboard_image_paste.js can
            // route uploads to the correct host (null for engagement-scoped notes).
            window.NotesContext = window.NotesContext || {};
            window.NotesContext.hostId =
                this.cfg.apiNoun === 'host' ? this.cfg.scopeId() : null;

            const sid = this.cfg.scopeId();
            if (sid == null || !noteId) return;

            const note = this._findNote(noteId);
            if (!note) return;

            // Fetch full content (list response only carries a preview)
            let full;
            try {
                full = await this.cfg.api.getNote(sid, noteId);
            } catch (err) {
                console.error('Failed to load note for editor:', err);
                showToast('Failed to load note', 'error');
                return;
            }

            this._initEditor();
            pane.dataset.empty = 'false';
            const titleInput = pane.querySelector('.notes-editor-title');
            if (titleInput) {
                titleInput.value = this._noteTitle(note) || '';
                titleInput.disabled = false;
                titleInput.placeholder = 'Title';
            }

            this._editorNoteId = noteId;
            this._editorOriginal = full.content || '';
            this._titleOriginal = (full.title || titleInput && titleInput.value || '').trim();
            if (this._editor) this._editor.value(this._editorOriginal);
            this._updateDirtyIndicator();

            const saveBtn = pane.querySelector('button[data-action="save"]');
            if (saveBtn) saveBtn.disabled = false;

            // Leave editor in edit mode so clipboard image paste works.
            // User can click the Preview toolbar button to see rendered markdown.
        }

        _clearEditor() {
            const pane = this._editorPane();
            if (!pane) return;
            // No note is active — clear host context so paste uploads don't
            // accidentally route to a stale host.
            window.NotesContext = window.NotesContext || {};
            window.NotesContext.hostId = null;
            this._editorNoteId = null;
            this._editorOriginal = '';
            this._titleOriginal = '';
            if (this._editor) this._editor.value('');
            pane.dataset.empty = 'true';
            const titleInput = pane.querySelector('.notes-editor-title');
            if (titleInput) {
                titleInput.value = '';
                titleInput.placeholder = 'No note selected';
                titleInput.disabled = true;
            }
            const saveBtn = pane.querySelector('button[data-action="save"]');
            if (saveBtn) saveBtn.disabled = true;
            this._updateDirtyIndicator();
        }

        _isDirty() {
            if (!this._editor || this._editorNoteId == null) return false;
            if (this._editor.value() !== this._editorOriginal) return true;
            const pane = this._editorPane();
            const titleInput = pane && pane.querySelector('.notes-editor-title');
            if (titleInput && titleInput.value.trim() !== this._titleOriginal) return true;
            return false;
        }

        _updateDirtyIndicator() {
            const pane = this._editorPane();
            if (!pane) return;
            const dirty = this._isDirty();
            const ind = pane.querySelector('[data-dirty-indicator]');
            if (ind) ind.style.visibility = dirty ? 'visible' : 'hidden';
        }

        async _confirmIfDirty() {
            if (!this._isDirty()) return true;
            return confirm('You have unsaved changes. Discard them?');
        }

        async _saveEditor() {
            if (!this._editor || this._editorNoteId == null) return;
            const sid = this.cfg.scopeId();
            const content = this._editor.value();
            const pane = this._editorPane();
            const titleInput = pane && pane.querySelector('.notes-editor-title');
            const title = titleInput ? titleInput.value.trim() : '';

            try {
                await this.cfg.api.updateNote(sid, this._editorNoteId, content, title);
                this._editorOriginal = content;
                this._titleOriginal = title;
                this._updateDirtyIndicator();
                showToast('Note saved', 'success');
                // Refresh tree so the title in the sidebar reflects the new title
                await this.refresh();
            } catch (err) {
                console.error('Save failed:', err);
                showToast(err.message || 'Failed to save note', 'error');
            }
        }
    }

    window.NotesTreeView = NotesTreeView;
})();
