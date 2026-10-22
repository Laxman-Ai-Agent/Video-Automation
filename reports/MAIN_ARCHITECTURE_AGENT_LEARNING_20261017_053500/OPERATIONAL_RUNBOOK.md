# Main Architecture Agent — Operational Runbook

**Audience:** System Operators & Maintenance Engineers  
**Target Subsystem:** `SYSTEM/agents/main_architecture_agent/`  

---

## 1. Inspecting Current Architecture Strategy

To retrieve the currently active strategy and its SHA-256 fingerprint:

```python
from SYSTEM.agents.main_architecture_agent.learning.strategy_manager import strategy_manager

active_strat = strategy_manager.get_active_strategy()
strat_hash = strategy_manager.get_active_strategy_hash()
print(f"Active Version: {active_strat['version']}, Hash: {strat_hash}")
```

Or via agent request:
```python
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import AgentRequest
from pathlib import Path

agent = MainArchitectureAgent()
res = agent.execute(Path("."), AgentRequest(
    agent_id=agent.agent_id,
    parameters={"action": "strategy", "sub_action": "get_active"}
))
print(res.summary)
```

---

## 2. Triggering a Manual Self-Learning Cycle

To analyze all unreflected experiences and trigger proposal generation and verification:

```python
from SYSTEM.agents.main_architecture_agent.learning.learning_scheduler import learning_scheduler

# Force execution regardless of unreflected sample threshold
cycle_report = learning_scheduler.run_learning_cycle(force=True, authorized_by="operator")
print("Cycle Result:", cycle_report)
```

Or via agent request:
```python
agent = MainArchitectureAgent()
res = agent.execute(Path("."), AgentRequest(
    agent_id=agent.agent_id,
    parameters={"action": "learn", "force": True}
))
print(res.summary)
```

---

## 3. Recording User Feedback / Correction

When an operator or user corrects an agent's delegation or routing decision:

```python
from SYSTEM.agents.main_architecture_agent.learning.experience_collector import experience_collector
from SYSTEM.agents.main_architecture_agent.learning.learning_scheduler import learning_scheduler

task_id = "task_xyz123"
feedback = {
    "original_agent": "motion_template_selection",
    "corrected_agent": "motion_planning",
    "comment": "Motion templates are deprecated; use motion planning.",
}

# 1. Record feedback
experience_collector.record_user_feedback(task_id, feedback)

# 2. Trigger feedback-driven cycle
recent_exps = experience_collector.query_experiences(limit=10)
target = next((e for e in recent_exps if e.task_id == task_id), None)
if target:
    learning_scheduler.trigger_on_feedback(target)
```

---

## 4. Emergency Strategy Rollback

If a newly promoted strategy exhibits unexpected runtime regressions, roll back immediately:

```python
from SYSTEM.agents.main_architecture_agent.learning.strategy_manager import strategy_manager

# Roll back to the most recent archived strategy
restored = strategy_manager.rollback(authorized_by="operator", reason="Emergency rollback due to runtime anomaly")
print(f"Restored strategy version: {restored['version']}")
```

Or roll back to a specific version (e.g. `1.0.0`):
```python
restored = strategy_manager.rollback(
    target_version="1.0.0",
    authorized_by="operator",
    reason="Restoring known-good v1.0.0 baseline"
)
```

---

## 5. Reviewing Benchmark Health

To run deterministic benchmarks against the active strategy:

```python
from SYSTEM.agents.main_architecture_agent.evaluations.evaluation_runner import evaluation_runner
from SYSTEM.agents.main_architecture_agent.learning.strategy_manager import strategy_manager

strat = strategy_manager.get_active_strategy()
results = evaluation_runner.evaluate_strategy(strat)

print(f"Composite Score: {results['composite_score']}")
print(f"Planning Score: {results['planning_score']}")
print(f"Routing Score: {results['routing_score']}")
print(f"Hard Gates Passed: {results['hard_gate_passed']}")
```
