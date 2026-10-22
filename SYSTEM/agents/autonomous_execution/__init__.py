"""Autonomous Execution & Recovery Package."""
from .agent import AutonomousExecutionAgent
from .checkpoint_manager import CheckpointManager, CorruptCheckpointError, StaleCheckpointError
from .contracts import (
    ExecutionReport,
    FailureCategory,
    StepExecutionRecord,
    TaskCheckpoint,
    TaskLifecycleState,
    TaskRequirementSpec,
)
from .recovery_manager import RecoveryManager
from .task_runner import TaskRunner

__all__ = [
    "AutonomousExecutionAgent",
    "CheckpointManager",
    "CorruptCheckpointError",
    "ExecutionReport",
    "FailureCategory",
    "RecoveryManager",
    "StaleCheckpointError",
    "StepExecutionRecord",
    "TaskCheckpoint",
    "TaskLifecycleState",
    "TaskRequirementSpec",
    "TaskRunner",
]
