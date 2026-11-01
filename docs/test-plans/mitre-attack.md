# MITRE ATT&CK Navigator

PTVault integrates with the MITRE ATT&CK Navigator to visualize your testing coverage and plan which techniques to execute.

## What is MITRE ATT&CK?

[MITRE ATT&CK](https://attack.mitre.org) is a globally-accessible knowledge base of adversary tactics, techniques, and procedures (TTPs) based on real-world observations. The ATT&CK Navigator is a web-based tool for visualizing which techniques are covered in a test.

## Importing a Navigator Layer

A Navigator **layer** is a JSON file that defines which ATT&CK techniques are included in your test scope, often with color coding and scores.

### Creating a Layer in MITRE Navigator

1. Visit [https://mitre-attack.github.io/attack-navigator/](https://mitre-attack.github.io/attack-navigator/)
2. Select techniques relevant to your engagement
3. Click **Export** → **Layer** → download the JSON file

### Importing into PTVault

1. Click the **Test Plans** tab
2. Click **Navigator Layers**
3. Click **+ Import Layer**
4. Select your Navigator JSON file
5. Enter a name for the layer
6. Click **Import**

The layer is stored in PTVault and associated with the current engagement.

## Viewing Layers

After importing, click a layer to view:

| Column | Description |
|--------|-------------|
| Technique ID | MITRE ATT&CK identifier (e.g., `T1059.001`) |
| Technique Name | Human-readable name (e.g., `PowerShell`) |
| Tactic | ATT&CK tactic (e.g., Execution, Persistence) |
| Score | Custom score if set in the Navigator |
| Coverage | Whether this technique has associated Atomic Red Team tests |

## Using Layers for Test Planning

1. Import a layer defining your engagement scope
2. Use the technique IDs to search the [Atomic Red Team](./atomic-red-team.md) library
3. Add relevant atomic tests to a test plan
4. Track execution status in [Execution Tracking](./execution-tracking.md)

## Managing Layers

| Action | How |
|--------|-----|
| View layer details | Click a layer in the list |
| Delete a layer | Click the delete icon on the layer row |

Layers are per-engagement — they do not carry over to other engagements.
