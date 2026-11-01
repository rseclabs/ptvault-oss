# Bulk Operations

Bulk operations let you perform actions on multiple evidence items at once, saving time when managing large amounts of evidence.

## Selecting Items

1. Check the **checkbox** next to each evidence item you want to include
2. Use the **Select All** checkbox at the top of the list to select all visible items
3. The number of selected items is shown in the bulk action toolbar

---

## Available Bulk Actions

Once one or more items are selected, the bulk action toolbar appears at the top of the evidence list.

### Bulk Tag

Add a tag to all selected items simultaneously.

1. Select items
2. Click **Tag** in the bulk actions toolbar
3. Enter a tag name (autocomplete suggestions appear)
4. Click **Apply**

The tag is added to all selected items. Existing tags are preserved.

**Use case:** You have collected 20 evidence items during a web application test and want to tag them all with `web-app` at once.

---

### Bulk Move to Host

Reassign multiple evidence items to a different host.

1. Select items
2. Click **Move to Host**
3. Choose the target host from the dropdown (or select **General** for unlinked evidence)
4. Click **Move**

**Use case:** You collected evidence in the General section and later want to associate it with a specific host after attribution.

---

### Bulk Export

Export the selected evidence items as a JSON file.

1. Select items
2. Click **Export**
3. A JSON file downloads with all selected evidence metadata and content

**Use case:** Extract a subset of evidence for sharing with a colleague or importing into another tool.

---

### Bulk Delete

Permanently delete all selected evidence items and their attached files.

1. Select items
2. Click **Delete**
3. A confirmation dialog appears showing the count of items to be deleted
4. Confirm to proceed

> **Warning:** Bulk delete is permanent and cannot be undone. Attached files are also removed from disk.

**Use case:** Clean up test artifacts, temporary notes, or incorrectly imported data.

---

## Tips

- Use [Advanced Filtering](./searching-filtering.md) first to narrow down items, then use **Select All** to operate on the filtered set
- Bulk tag before bulk delete so you can search for the tags and verify before deleting
- Bulk export is useful for creating backups of specific finding categories before restructuring
