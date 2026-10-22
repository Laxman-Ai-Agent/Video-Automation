# Task Planning & Decomposition Prompt

Given a user objective and environmental constraints:
1. Break down the objective into ordered, independent subtasks.
2. Establish explicit dependency chains (Task B requires Task A output).
3. Query `AgentRegistry` to match subtask capabilities to qualified agents.
4. Check prerequisite readiness (tools, libraries, checkpoints).
5. Output structured JSON adhering to the SubTask schema:
   - `title`: Short descriptive task title
   - `assigned_agent_id`: Valid registered agent ID
   - `action`: Specific execution action
   - `parameters`: Execution parameters
   - `dependencies`: List of preceding task IDs
