# Host Notes

Each host has its own notes section for recording observations, attack narratives, and findings specific to that system. Notes are organized as a **hierarchical tree** — each note can have sibling notes at the same level or child notes nested beneath it.

The General section (top of the host list) has the same notes tree for engagement-wide observations not tied to any specific host.

## Accessing Notes

1. Select a host from the host list (or click **General** for engagement-level notes)
2. Click the **Notes** tab in the host detail panel

The panel is split into two areas: the **notes tree** on the left and the **editor** on the right.

---

## The Notes Tree

The tree pane lists all notes for the selected host in an indented hierarchy. Click any note in the tree to open it in the editor.

### Toolbar Actions

The toolbar above the tree provides the following actions:

| Button | Keyboard | Action |
|--------|----------|--------|
| **New sibling** | — | Create a new note at the same level as the currently selected note |
| **New child** | — | Create a new note nested one level below the currently selected note |
| **Move up** | — | Move the selected note up one position among its siblings |
| **Move down** | — | Move the selected note down one position among its siblings |
| **Indent** | **Tab** (in title field) | Make the selected note a child of the note immediately above it |
| **Outdent** | **Shift+Tab** (in title field) | Move the selected note up one level in the hierarchy |

### Drag-and-Drop Reordering

Notes can also be reordered by dragging them within the tree:
- **Drop between notes** — reorders at the same level
- **Drop onto a note** — nests the dragged note as a child of the target

PTVault prevents circular nesting: you cannot drop a parent note into one of its own descendants.

---

## The Note Editor

When you click a note in the tree, the right pane opens with two fields:

- **Title** — a short name for the note (shown in the tree list). Editable independently from the body content.
- **Body** — the full Markdown content, edited in the EasyMDE editor.

The title and body are stored separately. Changing the title does not modify the body, and vice versa.

## Writing Notes

The body editor uses **EasyMDE / CodeMirror** and supports full Markdown syntax. The editor opens in **edit mode** by default.

| Markdown | Renders As |
|----------|-----------|
| `# Heading` | Large heading |
| `**bold**` | **bold** |
| `*italic*` | *italic* |
| `` `code` `` | `inline code` |
| ` ```bash ... ``` ` | Fenced code block |
| `- item` | Bullet list |
| `1. item` | Numbered list |
| `[text](url)` | Hyperlink |
| `> quote` | Blockquote |

To see the rendered output, click the **Preview** button in the editor toolbar. Click it again to return to edit mode.

---

## Pasting Images from the Clipboard

You can paste screenshots and images directly into the notes editor without saving them to disk first.

1. Copy an image to your clipboard (screenshot tool, browser, or image editor)
2. Click inside the editor to focus it
3. Press **Ctrl+V** (Windows/Linux) or **Cmd+V** (macOS)

PTVault automatically:
- Uploads the image to the server
- Inserts a Markdown image tag at the cursor position: `![image](url)`

The image is stored as an evidence file attached to the current engagement. After pasting, switch to Preview mode to confirm the image renders correctly.

> **Note:** Clipboard paste works in host notes, General section notes, and the standalone note editor.

---

## Saving Notes

Notes are saved when you click **Save** in the editor or when you navigate to a different note in the tree. Changes are not auto-saved — save before closing the tab.

---

## General Section Notes

Click **General** at the top of the host list and open the **Notes** tab to access engagement-level notes. The same tree, toolbar, editor, and clipboard paste features are available here.

---

## Tips

- Use the hierarchy to mirror your attack phases: create top-level notes for each phase (Recon, Exploitation, Post-Exploitation) and child notes for individual techniques or findings
- Paste screenshots directly from your screen-capture tool using clipboard paste — no intermediate file save required
- Write notes in a form that translates easily into report sections; the content can be referenced when building your final report in the Report Builder
- Use code blocks for command output so it remains readable and searchable
