"""Agent Router for Main Architecture Agent.

Selects the best registered agent for each subtask using Strategy preferences,
fallback routing rules, capability verification against AgentRegistry, and
historical experience heuristics.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("main_architecture_agent.agent_router")


class AgentRouter:
    """Capability-driven, experience-informed router for subtask delegations."""

    def __init__(self) -> None:
        pass

    def _get_strategy_manager(self) -> Any:
        from ..learning.strategy_manager import strategy_manager
        return strategy_manager

    def _get_collector(self) -> Any:
        from ..learning.experience_collector import experience_collector
        return experience_collector

    def _get_registry(self) -> Any:
        try:
            from SYSTEM.registries.agent_registry import AgentRegistry
            return AgentRegistry()
        except Exception as e:
            logger.warning(f"Could not load AgentRegistry: {e}")
            return None

    def route_subtask(
        self,
        subtask: dict[str, Any],
        strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Determines the optimal agent assignment for a single subtask."""
        strat = strategy or self._get_strategy_manager().get_active_strategy()
        prefs = strat.get("agent_routing_preferences", {})
        fallbacks = strat.get("fallback_routes", {})

        registry = self._get_registry()
        action = subtask.get("action", "")
        requested_agent = subtask.get("assigned_agent_id", "")
        subtask_title = subtask.get("title", "").lower()

        # Step 1: Check Strategy Routing Preferences based on action / title keywords
        preferred_candidates: list[str] = []
        for key, candidates in prefs.items():
            if key in action.lower() or key in subtask_title:
                preferred_candidates.extend(candidates)

        if requested_agent and requested_agent not in preferred_candidates:
            preferred_candidates.insert(0, requested_agent)

        # Fallback to general capability finder if no candidate found
        if not preferred_candidates:
            preferred_candidates = ["capability_finder"]

        # Step 2: Validate candidates against AgentRegistry and historical failure heuristics
        chosen_agent: str | None = None
        routing_reason = "Preferred strategy match"
        fallback_used = False

        # Check explicit fallback routes from strategy
        if action in fallbacks:
            chosen_agent = fallbacks[action]
            routing_reason = f"Action fallback route applied ({action} -> {chosen_agent})"
            fallback_used = True
        elif requested_agent in fallbacks and not any(k in action.lower() for k in prefs):
            chosen_agent = fallbacks[requested_agent]
            routing_reason = f"Agent fallback route applied ({requested_agent} -> {chosen_agent})"
            fallback_used = True

        if not chosen_agent:
            # Check historical failures from experience collector
            historical_experiences = self._get_collector().get_experiences(limit=100)
            recent_failures_per_agent: dict[str, int] = {}
            for exp in historical_experiences:
                if exp.status in ("failed", "blocked"):
                    for ag in exp.selected_agents:
                        recent_failures_per_agent[ag] = recent_failures_per_agent.get(ag, 0) + 1

            for candidate in preferred_candidates:
                # Check if agent exists in registry
                if registry and not registry.get(candidate):
                    # If agent not registered, check fallback routes
                    if candidate in fallbacks:
                        alt = fallbacks[candidate]
                        if not registry or registry.get(alt):
                            chosen_agent = alt
                            routing_reason = f"Fallback route used ({candidate} -> {alt})"
                            fallback_used = True
                            break
                    continue

                # Check if candidate has excessive recent failures (e.g. >= 3) and a fallback is configured
                if candidate in fallbacks and recent_failures_per_agent.get(candidate, 0) >= 3:
                    chosen_agent = fallbacks[candidate]
                    routing_reason = (
                        f"Selected fallback {chosen_agent} due to {recent_failures_per_agent[candidate]} "
                        f"recent failures on {candidate}"
                    )
                    fallback_used = True
                    break

                chosen_agent = candidate
                routing_reason = f"Matched registered candidate: {candidate}"
                break

        if not chosen_agent:
            # Final fallback
            default_fallback = fallbacks.get("unregistered_fallback", "capability_finder")
            chosen_agent = default_fallback
            routing_reason = f"Default unregistered fallback applied -> {default_fallback}"
            fallback_used = True

        return {
            "chosen_agent_id": chosen_agent,
            "routing_reason": routing_reason,
            "fallback_used": fallback_used,
            "alternatives_considered": preferred_candidates,
        }

    def route_plan(
        self,
        plan: dict[str, Any],
        strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Routes and annotates all subtasks in a task decomposition plan."""
        strat = strategy or self._get_strategy_manager().get_active_strategy()
        subtasks = plan.get("subtasks", [])

        for subtask in subtasks:
            decision = self.route_subtask(subtask, strategy=strat)
            subtask["assigned_agent_id"] = decision["chosen_agent_id"]
            subtask["routing_metadata"] = decision

        return plan


agent_router = AgentRouter()
