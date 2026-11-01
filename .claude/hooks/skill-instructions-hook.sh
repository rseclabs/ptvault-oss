#!/bin/bash
# UserPromptSubmit hook for skill-aware responses

cat <<'EOF'
REQUIRED: SKILL LOADING PROTOCOL

Before writing any code, complete these steps in order:

1. SCAN each skill below and decide: LOAD or SKIP (with brief reason)
   - python
   - flask
   - sqlite
   - javascript
   - tailwind
   - frontend-design
   - jwt
   - argon2
   - xml-parsing
   - docker
   - pytest
   - pynacl

2. For every skill marked LOAD → immediately invoke Skill(name)
   If none need loading → write "Proceeding without skills"

3. Only after step 2 completes may you begin coding.

IMPORTANT: Skipping step 2 invalidates step 1. Always call Skill() for relevant items.

Sample output:
- python: LOAD - building components
- flask: SKIP - not needed for this task
- sqlite: LOAD - building components
- javascript: SKIP - not needed for this task

Then call:
> Skill(python)
> Skill(sqlite)

Now implementation can begin.
EOF
