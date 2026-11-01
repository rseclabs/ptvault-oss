// static/js/clipboard_image_paste.js
//
// Hooks EasyMDE/CodeMirror paste events to upload pasted images via
// /api/evidence and insert inline markdown image syntax.
//
// Usage:
//   attachClipboardImagePaste(easyMDE, {
//     engagementId: () => AppState.activeEngagement?.id,
//     hostId:       () => NotesContext?.hostId ?? null,
//     onError:      (msg) => showToast(msg, 'error'),
//   });
//
// See docs/superpowers/specs/2026-05-14-clipboard-image-paste.md for the design.

(function (global) {
  'use strict';

  const DEFAULT_ALLOWED = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
  const DEFAULT_MAX = 10 * 1024 * 1024; // 10 MB
  let pasteCounter = 0;

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function isoStamp() {
    return new Date().toISOString().replace(/[:.]/g, '-');
  }

  function mimeToExt(mime) {
    const map = {
      'image/png': 'png',
      'image/jpeg': 'jpg',
      'image/gif': 'gif',
      'image/webp': 'webp',
    };
    return map[mime] || 'png';
  }

  function attachClipboardImagePaste(easyMDE, opts) {
    opts = opts || {};
    const apiBase = opts.apiBase || '/api/evidence';
    const maxBytes = opts.maxSizeBytes || DEFAULT_MAX;
    const allowed = opts.allowedMimeTypes || DEFAULT_ALLOWED;
    const source = opts.source || 'note_paste';
    const onError = opts.onError || function (msg) { console.warn(msg); };
    const onUploaded = opts.onUploaded || function () {};

    if (!easyMDE || !easyMDE.codemirror) {
      console.warn('[clipboard_image_paste] easyMDE.codemirror is missing; nothing wired');
      return;
    }

    const cm = easyMDE.codemirror;

    cm.on('paste', function (cmInstance, event) {
      const items = (event.clipboardData && event.clipboardData.items) || [];
      const imageItems = [];
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.kind === 'file' && allowed.indexOf(it.type) !== -1) {
          imageItems.push(it);
        }
      }
      if (imageItems.length === 0) return; // fall through to native paste

      event.preventDefault();

      imageItems.forEach(function (item) {
        const blob = item.getAsFile();
        if (!blob) return;
        if (blob.size > maxBytes) {
          onError('Image is ' + fmtSize(blob.size) + ', max ' + fmtSize(maxBytes));
          return;
        }

        const token = '__paste_' + (++pasteCounter) + '__';
        const placeholder = '![Uploading screenshot ' + token + '…]()';
        // Insert placeholder + newline at cursor, advance cursor below.
        cmInstance.replaceSelection(placeholder + '\n');

        uploadOne(blob, token);
      });
    });

    function uploadOne(blob, token) {
      const stamp = isoStamp();
      const filename = 'pasted-' + stamp + '.' + mimeToExt(blob.type);
      const metadataObj = { source: source };
      const hid = opts.hostId ? opts.hostId() : null;
      if (hid) metadataObj.host_id = hid;

      const fd = new FormData();
      fd.append('file', blob, filename);
      fd.append('evidence_type', 'screenshot');
      fd.append('title', 'Pasted screenshot ' + stamp);
      const eid = opts.engagementId ? opts.engagementId() : null;
      if (eid != null) fd.append('engagement_id', String(eid));
      fd.append('metadata', JSON.stringify(metadataObj));

      const csrfMatch = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
      const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : null;
      const headers = csrfToken ? { 'X-CSRF-Token': csrfToken } : {};

      fetch(apiBase, {
        method: 'POST',
        headers: headers,
        body: fd,
        credentials: 'include',
      })
        .then(function (resp) {
          if (!resp.ok) {
            return resp
              .json()
              .catch(function () { return { error: 'HTTP ' + resp.status }; })
              .then(function (body) { throw new Error(body.error || ('HTTP ' + resp.status)); });
          }
          return resp.json();
        })
        .then(function (evidence) {
          replacePlaceholder(token, '![pasted screenshot](' + apiBase + '/' + evidence.id + '/file)');
          onUploaded(evidence);
        })
        .catch(function (err) {
          const msg = err && err.message ? err.message : 'connection error';
          replacePlaceholder(token, '*(upload failed: ' + msg + ')*');
          onError('Screenshot upload failed: ' + msg);
        });
    }

    function replacePlaceholder(token, replacement) {
      const doc = cm.getDoc();
      const text = doc.getValue();
      const needle = '![Uploading screenshot ' + token + '…]()';
      const idx = text.indexOf(needle);
      if (idx === -1) {
        // Placeholder was deleted by the user before upload completed.
        return false;
      }
      // Convert string index to {line, ch} positions
      const before = text.slice(0, idx);
      const startLine = (before.match(/\n/g) || []).length;
      const lastNL = before.lastIndexOf('\n');
      const startCh = lastNL === -1 ? idx : idx - lastNL - 1;
      const endCh = startCh + needle.length;
      doc.replaceRange(
        replacement,
        { line: startLine, ch: startCh },
        { line: startLine, ch: endCh },
      );
      return true;
    }
  }

  global.attachClipboardImagePaste = attachClipboardImagePaste;
})(window);
