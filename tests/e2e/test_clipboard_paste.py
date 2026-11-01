"""End-to-end: paste an image into a note → uploads → inline markdown inserted.

Requires PTVault running locally at $PT_APP_URL (default http://localhost:5001)
with the DEMO-ACME engagement seeded (Sample Data/seed_demo_engagement.py).

Run:
    pytest tests/e2e/test_clipboard_paste.py -v

Exclude from default suite (requires live app):
    pytest tests/ --ignore=tests/e2e
"""

import base64
import os
import re

import pytest
from playwright.sync_api import sync_playwright

APP_URL = os.environ.get('PT_APP_URL', 'http://localhost:5001')
USERNAME = os.environ.get('PT_USERNAME', 'admin@example.com')
PASSWORD = os.environ.get('PT_PASSWORD', '')
DEMO_SHORT = os.environ.get('PT_ENGAGEMENT', 'DEMO-ACME')

pytestmark = pytest.mark.skipif(
    not PASSWORD, reason='set PT_USERNAME / PT_PASSWORD for a running PTVault instance'
)

# 1x1 transparent PNG — smallest valid image we can synthesize for the clipboard
PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
)


def _login(page):
    """Log in and wait for the main SPA to load."""
    page.goto(f'{APP_URL}/login')
    # The login form uses name="identity" (email or username), type="text"
    page.fill('input[name=identity]', USERNAME)
    page.fill('input[name=password]', PASSWORD)
    page.click('button[type=submit]')
    # After auth the SPA loads at / or /dashboard; wait for the nav tabs to appear
    page.wait_for_selector('.nav-tab[data-section="engagements"]', timeout=10_000)


def _open_engagement(page, short_name):
    """Click the engagement card matching short_name in the engagements grid."""
    # The app starts on the engagements section (active by default).
    # Cards are rendered as .engagement-card divs with onclick=handleEngagementCardClick(id).
    # We match by visible text (the short_name / title shown on the card).
    page.get_by_text(short_name, exact=False).first.click()
    # Wait for engagement-level content to load (e.g. hosts table or notes pane)
    page.wait_for_load_state('networkidle')


def _switch_to_general_notes(page):
    """Click the General nav-tab and ensure the Notes sub-pane is visible."""
    # nav-tab is a <button> with data-section="general"
    page.click('.nav-tab[data-section="general"]')
    # The general section container becomes visible
    page.wait_for_selector('#generalSectionContainer', state='visible', timeout=5_000)
    # The Notes sub-tab is active by default; ensure the notes tree pane is present
    page.wait_for_selector('#engagementNotesList', timeout=5_000)


def _create_or_select_note(page):
    """Create a new note if the tree is empty, or select the first existing note.

    Returns once the EasyMDE CodeMirror editor is visible and active.
    """
    # Check whether the tree already has a note item we can click
    first_item = page.locator('#engagementNotesList .notes-tree-item').first
    if first_item.count() > 0:
        first_item.click()
    else:
        # Tree is empty — click the "add sibling" toolbar button to create a note
        page.click(
            '#engagementNotesToolbar .notes-toolbar-btn[data-action="add-sibling"]'
        )
        # A new item should now appear; click it to open the editor
        page.wait_for_selector(
            '#engagementNotesList .notes-tree-item', timeout=5_000
        )
        page.locator('#engagementNotesList .notes-tree-item').first.click()

    # Wait for EasyMDE to initialise — it creates a .CodeMirror wrapper inside
    # the #engagementNotesEditorPane.
    page.wait_for_selector(
        '#engagementNotesEditorPane .CodeMirror', timeout=8_000
    )


@pytest.mark.e2e
def test_paste_png_into_general_note():
    """Synthesize a PNG ClipboardEvent → assert the paste module uploads it and
    inserts the final markdown image reference into the CodeMirror editor."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()

        _login(page)
        _open_engagement(page, DEMO_SHORT)
        _switch_to_general_notes(page)
        _create_or_select_note(page)

        # Synthesize a ClipboardEvent carrying our PNG and dispatch it to the
        # CodeMirror instance.
        #
        # clipboard_image_paste.js hooks cm.on('paste', ...) which listens on
        # the CodeMirror internal wrapper div (not the hidden textarea).
        # We dispatch the event on the .CodeMirror element so it bubbles
        # through CodeMirror's own event delegation correctly.
        #
        # Browsers block programmatic access to the OS clipboard, so we forge
        # a DataTransfer with our PNG file attached and build a synthetic
        # ClipboardEvent from it.
        b64 = base64.b64encode(PNG_1X1).decode()
        page.evaluate(
            """async (b64) => {
              // Decode base64 → Uint8Array
              const bin = atob(b64);
              const buf = new Uint8Array(bin.length);
              for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);

              const file = new File([buf], 'pasted.png', { type: 'image/png' });
              const dt = new DataTransfer();
              dt.items.add(file);

              // clipboard_image_paste.js hooks cm.on('paste', ...).
              // CodeMirror adds its own listener to the .CodeMirror-code textarea,
              // so we dispatch there to trigger the normal CodeMirror event path.
              const cmEl = document.querySelector(
                '#engagementNotesEditorPane .CodeMirror-code'
              );
              if (!cmEl) {
                throw new Error('CodeMirror editor element not found in engagementNotesEditorPane');
              }

              const ev = new ClipboardEvent('paste', {
                clipboardData: dt,
                bubbles: true,
                cancelable: true,
              });
              cmEl.dispatchEvent(ev);
            }""",
            b64,
        )

        # Within 10 s the placeholder should be replaced by the final markdown.
        # The regex matches: ![pasted screenshot](/api/evidence/<id>/file)
        page.wait_for_function(
            r"""() => {
              const pane = document.querySelector('#engagementNotesEditorPane .CodeMirror');
              if (!pane || !pane.CodeMirror) return false;
              const val = pane.CodeMirror.getValue();
              return /!\[pasted screenshot\]\(\/api\/evidence\/\d+\/file\)/.test(val);
            }""",
            timeout=10_000,
        )

        # Retrieve the final editor value and confirm the URL is reachable.
        cm_value = page.evaluate(
            """() => {
              const pane = document.querySelector('#engagementNotesEditorPane .CodeMirror');
              return pane ? pane.CodeMirror.getValue() : '';
            }"""
        )
        m = re.search(r'/api/evidence/(\d+)/file', cm_value)
        assert m, (
            f'Expected /api/evidence/<id>/file URL in note content; got: {cm_value!r}'
        )

        # Confirm the uploaded file is actually fetchable (status 200).
        resp = page.request.get(f'{APP_URL}{m.group(0)}')
        assert resp.status == 200, (
            f'Inline image fetch returned HTTP {resp.status} for {m.group(0)!r}'
        )

        browser.close()
