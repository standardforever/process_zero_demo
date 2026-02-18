# workflow_models.py
from typing import Any, Dict, List, Literal, Optional, Type, Union
from pydantic import BaseModel, Field
from enum import Enum


class WorkflowActionType(str, Enum):
    """Available workflow action types"""
    GO_BACK = "go_back"
    SWITCH = "switch"
    CLOSE = "close"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    
    NAVIGATE = "navigate"
    SEARCH = "search"
    DONE = "done"
    
    EXTRACT = "extract"
    
    FIND_TEXT = "find_text"
    WRITE_FILE = "write_file"
    REPLACE_FILE = "replace_file"
    READ_FILE = "read_file"
    EVALUATE = "evaluate"
    
    
    SEND_KEYS = "send_keys"
    UPLOAD_FILE = "upload_file"
    GET_DROPDOWN_OPTIONS = "get_dropdown_options"
    SELECT_DROPDOWN = "select_dropdown"
    SCROLL = "scroll"
    CLICK = "click"
    INPUT = "input"
    


class WorkflowStep(BaseModel):
    """Individual step in a workflow"""
    name: str = Field(description="Descriptive name for this step")
    action_type: WorkflowActionType
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    description: Optional[str] = Field(default=None, description="Optional step description")
    condition: Optional[str] = Field(default=None, description="Optional condition to execute this step")
    on_error: Optional[str] = Field(
        default="stop", 
        description="Error handling: 'stop', 'continue', or 'retry'"
    )
    max_retries: int = Field(default=0, description="Number of retries on failure")


class WorkflowDefinition(BaseModel):
    """Complete workflow definition"""
    id: Optional[str] = Field(default=None, description="Unique workflow ID")
    name: str = Field(description="Workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    version: str = Field(default="1.0.0", description="Workflow version")
    author: Optional[str] = Field(default=None, description="Workflow creator")
    tags: List[str] = Field(default_factory=list, description="Workflow tags for categorization")
    steps: List[WorkflowStep] = Field(description="Ordered list of workflow steps")
    variables: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Workflow-level variables accessible to all steps"
    )
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowExecutionContext(BaseModel):
    """Runtime context for workflow execution"""
    workflow_id: str
    current_step_index: int = 0
    variables: Dict[str, Any] = Field(default_factory=dict)
    step_results: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "running", "completed", "failed", "paused"] = "pending"
    error_message: Optional[str] = None


class ActionParameterInfo(BaseModel):
    """Information about action parameters"""
    name: str
    type: str
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None


class ActionInfo(BaseModel):
    """Information about an available action"""
    action_type: WorkflowActionType
    display_name: str
    description: str
    parameters: List[ActionParameterInfo]
    category: str = "browser"
    examples: Optional[List[Dict[str, Any]]] = None


# Additional parameter models for actions that were using dict
class WaitAction(BaseModel):
    seconds: int = Field(default=3, ge=0, description="Number of seconds to wait")


class FindTextAction(BaseModel):
    text: str = Field(description="Text to find on the page")


class WriteFileAction(BaseModel):
    file_name: str = Field(description="Name of the file to write")
    content: str = Field(description="Content to write to the file")
    append: bool = Field(default=False, description="Append to file instead of overwriting")
    trailing_newline: bool = Field(default=True, description="Add trailing newline")
    leading_newline: bool = Field(default=False, description="Add leading newline")


class ReplaceFileAction(BaseModel):
    file_name: str = Field(description="Name of the file to modify")
    old_str: str = Field(description="String to replace")
    new_str: str = Field(description="Replacement string")


class ReadFileAction(BaseModel):
    file_name: str = Field(description="Name of the file to read")


class EvaluateAction(BaseModel):
    code: str = Field(description="JavaScript code to execute")