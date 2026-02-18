o# workflow_manager.py
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os
from schemas.actions_schemas import WorkflowDefinition, WorkflowStep
from registry.workflow_registry import workflow_registry


class WorkflowManager:
    """Manage workflow creation, storage, and retrieval"""
    
    def __init__(self, storage_path: str = "./workflows"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    def create_workflow(
        self,
        name: str,
        steps: List[WorkflowStep],
        description: Optional[str] = None,
        tags: List[str] = None,
        variables: Dict[str, Any] = None
    ) -> WorkflowDefinition:
        """Create a new workflow"""
        
        workflow = WorkflowDefinition(
            id=self._generate_id(name),
            name=name,
            description=description,
            tags=tags or [],
            steps=steps,
            variables=variables or {},
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        return workflow
    
    def save_workflow(self, workflow: WorkflowDefinition) -> str:
        """Save workflow to disk"""
        workflow.updated_at = datetime.utcnow().isoformat()
        
        file_path = os.path.join(self.storage_path, f"{workflow.id}.json")
        
        with open(file_path, 'w') as f:
            json.dump(workflow.model_dump(), f, indent=2)
        
        return file_path
    
    def load_workflow(self, workflow_id: str) -> WorkflowDefinition:
        """Load workflow from disk"""
        file_path = os.path.join(self.storage_path, f"{workflow_id}.json")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Workflow not found: {workflow_id}")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return WorkflowDefinition(**data)
    
    def list_workflows(self, tag: Optional[str] = None) -> List[WorkflowDefinition]:
        """List all workflows, optionally filtered by tag"""
        workflows = []
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                file_path = os.path.join(self.storage_path, filename)
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    workflow = WorkflowDefinition(**data)
                    
                    if tag is None or tag in workflow.tags:
                        workflows.append(workflow)
        
        return workflows
    
    def delete_workflow(self, workflow_id: str):
        """Delete a workflow"""
        file_path = os.path.join(self.storage_path, f"{workflow_id}.json")
        
        if os.path.exists(file_path):
            os.remove(file_path)
    
    def _generate_id(self, name: str) -> str:
        """Generate workflow ID from name"""
        import hashlib
        timestamp = datetime.utcnow().isoformat()
        return hashlib.md5(f"{name}{timestamp}".encode()).hexdigest()[:12]
    
    @staticmethod
    def get_available_actions() -> List[Dict[str, Any]]:
        """Get all available actions with parameters"""
        actions = workflow_registry.get_all_actions()
        
        return [
            {
                "action_type": action.action_type,
                "display_name": action.display_name,
                "description": action.description,
                "category": action.category,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "required": param.required,
                        "default": param.default,
                        "description": param.description,
                        "constraints": param.constraints
                    }
                    for param in action.parameters
                ],
                "examples": action.examples
            }
            for action in actions
        ]