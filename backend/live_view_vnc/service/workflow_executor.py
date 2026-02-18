# workflow_executor.py
from typing import Any, Dict, Optional
import asyncio
from schemas.actions_schemas import (
    WorkflowExecutionContext, WorkflowStep, WorkflowDefinition
)
from registry.workflow_registry import workflow_registry


class WorkflowExecutor:
    """Simple executor - just runs a single action and returns the result"""
    
    def __init__(self, tools, browser_session=None):
        """
        Args:
            tools: Tools instance with registry for executing actions
            browser_session: Browser session for actions that need it
        """
        self.tools = tools
        self.browser_session = browser_session
    
    async def execute_step(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any] = None
    ) -> Any:
        """
        Execute a single action
        
        Args:
            step: WorkflowStep to execute
            variables: Optional variables for {{variable}} substitution
            
        Returns:
            Result of the action execution
        """
        # Substitute variables in parameters
        parameters = self._substitute_variables(step.parameters, variables or {})
        
        # Validate parameters against action schema
        is_valid, error = workflow_registry.validate_parameters(step.action_type, parameters)
        if not is_valid:
            raise ValueError(f"Invalid parameters for action {step.action_type}: {error}")
        
        # Execute action using Tools registry
        action_name = step.action_type.value  # e.g., "wait", "navigate", "click"
        
        result = await self.tools.registry.execute_action(
            action_name=action_name,
            params=parameters,
            browser_session=self.browser_session
        )
        return result
    
    def _substitute_variables(
        self,
        parameters: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Substitute {{variable}} placeholders in parameters
        
        Example:
            parameters: {"text": "{{username}}"}
            variables:  {"username": "admin@example.com"}
            result:     {"text": "admin@example.com"}
        """
        substituted = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                substituted[key] = variables.get(var_name, value)
            elif isinstance(value, dict):
                substituted[key] = self._substitute_variables(value, variables)
            elif isinstance(value, list):
                substituted[key] = [
                    self._substitute_variables(item, variables) if isinstance(item, dict)
                    else variables.get(item[2:-2].strip(), item)
                    if isinstance(item, str) and item.startswith("{{") and item.endswith("}}")
                    else item
                    for item in value
                ]
            else:
                substituted[key] = value
        
        return substituted