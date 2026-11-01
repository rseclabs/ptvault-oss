# Execution Tracking

Execution tracking lets you record the outcome of each atomic test or test plan item for a specific engagement. This creates an auditable record of what was tested, when, and what the result was.

## How Execution Records Work

An **execution record** connects:
- A **test plan item** (the test to run)
- An **engagement** (the current context)
- Optionally, a **host** (the target system)

Each record tracks the status, timing, output, and linked evidence.

## Execution Statuses

| Status | Description |
|--------|-------------|
| **Pending** | Test has not been started |
| **Running** | Test is currently in progress |
| **Passed** | Test completed successfully — technique was successfully simulated |
| **Failed** | Test did not complete as expected (blocked, not applicable, error) |
| **Skipped** | Test was intentionally skipped (out of scope, tool not available) |

## Creating an Execution Record

1. Navigate to **Test Plans** → **Executions**
2. Click **+ New Execution**
3. Select the test plan item
4. Optionally select a target host
5. Set the initial status (usually `Pending` or `Running`)
6. Click **Create**

## Updating Execution Status

1. Find the execution record in the list
2. Click **Edit**
3. Update:
   - **Status**: Change from Pending → Running → Passed/Failed/Skipped
   - **Output**: Paste the actual command output
   - **Start Time / End Time**: Record execution timing
   - **Notes**: Add observations, deviations, or context
4. Click **Save**

## Linking Evidence to Executions

Connect evidence you collected (screenshots, command output, tool results) to the execution record:

1. Open an execution record
2. Click **+ Link Evidence**
3. Select evidence items from the active engagement
4. Click **Link**

Linked evidence provides the proof for each test, creating a complete audit trail.

## Viewing Execution History

The executions list shows all records for the active engagement. Filter by:
- Status (Pending, Running, Passed, Failed, Skipped)
- Target host
- Test plan

This gives a clear picture of overall test coverage and progress.

## Reporting on Executions

Execution data can inform your report:
- Show which ATT&CK techniques were tested
- Document evidence of successful technique simulation
- Note where defenses blocked execution (useful for demonstrating control effectiveness)
