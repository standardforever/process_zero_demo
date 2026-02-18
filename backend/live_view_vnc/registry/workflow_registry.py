# workflow_registry.py
from typing import Any, Callable, Dict, List, Type, Union, Optional
from pydantic import BaseModel

from browser_use.tools.views import (
    ExtractAction, SearchAction, NavigateAction, ClickElementAction,
    InputTextAction, DoneAction, SwitchTabAction, CloseTabAction,
    ScrollAction, SendKeysAction, UploadFileAction, NoParamsAction,
    GetDropdownOptionsAction, SelectDropdownOptionAction
)

from schemas.actions_schemas import (
    WorkflowActionType, FindTextAction, WriteFileAction, ReplaceFileAction, EvaluateAction, WaitAction,
    ActionParameterInfo, ReadFileAction, ActionInfo
)

class WorkflowRegistry:
    """Registry for all available workflow actions"""
    
    def __init__(self):
        self._actions: Dict[WorkflowActionType, Dict[str, Any]] = {}
        self._register_default_actions()
    
    def _register_default_actions(self):
        """Register all default actions"""
        
        # Navigation actions
        self.register(
            WorkflowActionType.NAVIGATE,
            NavigateAction,
            "Navigate to URL",
            "Navigate to a specific URL with option to open in new tab",
            "navigation",
            examples=[
                {"url": "https://example.com", "new_tab": False},
                {"url": "https://google.com", "new_tab": True}
            ]
        )
        
        self.register(
            WorkflowActionType.SEARCH,
            SearchAction,
            "Search",
            "Search using specified search engine",
            "navigation",
            examples=[
                {"query": "python tutorial", "engine": "duckduckgo"},
                {"query": "weather today", "engine": "google"}
            ]
        )
        
        self.register(
            WorkflowActionType.GO_BACK,
            NoParamsAction,
            "Go Back",
            "Navigate back in browser history",
            "navigation"
        )
        
        # Interaction actions
        self.register(
            WorkflowActionType.CLICK,
            ClickElementAction,
            "Click Element",
            "Click on an interactive element by index",
            "interaction",
            examples=[{"index": 1}, {"index": 5}]
        )
        
        self.register(
            WorkflowActionType.INPUT,
            InputTextAction,
            "Input Text",
            "Input text into a field",
            "interaction",
            examples=[
                {"index": 1, "text": "hello@example.com", "clear": True},
                {"index": 2, "text": "additional text", "clear": False}
            ]
        )
        
        self.register(
            WorkflowActionType.SCROLL,
            ScrollAction,
            "Scroll",
            "Scroll page or specific element",
            "interaction",
            examples=[
                {"down": True, "pages": 1.0},
                {"down": False, "pages": 0.5, "index": 3}
            ]
        )
        
        self.register(
            WorkflowActionType.SEND_KEYS,
            SendKeysAction,
            "Send Keys",
            "Send keyboard keys or shortcuts",
            "interaction",
            examples=[
                {"keys": "Enter"},
                {"keys": "Control+s"},
                {"keys": "Escape"}
            ]
        )
        
        # Extraction actions
        self.register(
            WorkflowActionType.EXTRACT,
            ExtractAction,
            "Extract Content",
            "Extract content from page using LLM",
            "extraction",
            examples=[
                {"query": "Extract all product names", "extract_links": False},
                {"query": "Find all navigation links", "extract_links": True}
            ]
        )
        
        self.register(
            WorkflowActionType.FIND_TEXT,
            FindTextAction,
            "Find Text",
            "Find specific text on page",
            "extraction",
            examples=[
                {"text": "Sign in"},
                {"text": "Add to cart"}
            ]
        )
        
        # Tab management
        self.register(
            WorkflowActionType.SWITCH,
            SwitchTabAction,
            "Switch Tab",
            "Switch to another browser tab",
            "tabs",
            examples=[{"tab_id": "a1b2"}]
        )
        
        self.register(
            WorkflowActionType.CLOSE,
            CloseTabAction,
            "Close Tab",
            "Close a browser tab",
            "tabs",
            examples=[{"tab_id": "a1b2"}]
        )
        
        # File actions
        self.register(
            WorkflowActionType.UPLOAD_FILE,
            UploadFileAction,
            "Upload File",
            "Upload file to input element",
            "files",
            examples=[{"index": 1, "path": "/path/to/file.pdf"}]
        )
        
        self.register(
            WorkflowActionType.WRITE_FILE,
            WriteFileAction,
            "Write File",
            "Write content to file",
            "files",
            examples=[
                {"file_name": "output.txt", "content": "Hello World", "append": False},
                {"file_name": "log.txt", "content": "New entry", "append": True}
            ]
        )
        
        self.register(
            WorkflowActionType.REPLACE_FILE,
            ReplaceFileAction,
            "Replace in File",
            "Replace text in file",
            "files",
            examples=[
                {"file_name": "config.txt", "old_str": "localhost", "new_str": "production.com"}
            ]
        )
        
        self.register(
            WorkflowActionType.READ_FILE,
            ReadFileAction,
            "Read File",
            "Read file contents",
            "files",
            examples=[
                {"file_name": "data.txt"}
            ]
        )
        
        # Dropdown actions
        self.register(
            WorkflowActionType.GET_DROPDOWN_OPTIONS,
            GetDropdownOptionsAction,
            "Get Dropdown Options",
            "Get options from dropdown element",
            "interaction",
            examples=[{"index": 3}]
        )
        
        self.register(
            WorkflowActionType.SELECT_DROPDOWN,
            SelectDropdownOptionAction,
            "Select Dropdown Option",
            "Select option from dropdown",
            "interaction",
            examples=[{"index": 3, "text": "Option 1"}]
        )
        
        # Utility actions
        self.register(
            WorkflowActionType.WAIT,
            WaitAction,
            "Wait",
            "Wait for specified seconds",
            "utility",
            examples=[{"seconds": 3}, {"seconds": 5}]
        )
        
        self.register(
            WorkflowActionType.SCREENSHOT,
            NoParamsAction,
            "Take Screenshot",
            "Capture page screenshot",
            "utility"
        )
        
        self.register(
            WorkflowActionType.EVALUATE,
            EvaluateAction,
            "Evaluate JavaScript",
            "Execute JavaScript code",
            "utility",
            examples=[
                {"code": "document.title"},
                {"code": "window.scrollTo(0, 0)"}
            ]
        )
        
        self.register(
            WorkflowActionType.DONE,
            DoneAction,
            "Mark Complete",
            "Mark workflow as complete",
            "utility",
            examples=[
                {"text": "Task completed successfully", "success": True},
                {"text": "Failed to complete", "success": False}
            ]
        )
    
    def register(
        self,
        action_type: WorkflowActionType,
        parameter_model: Type[BaseModel],
        display_name: str,
        description: str,
        category: str = "browser",
        examples: List[Dict[str, Any]] | None = None
    ):
        """Register an action with its parameter schema"""
        parameters = self._extract_parameters(parameter_model)
        
        self._actions[action_type] = {
            "parameter_model": parameter_model,
            "display_name": display_name,
            "description": description,
            "category": category,
            "parameters": parameters,
            "examples": examples or []
        }
    
    def _extract_parameters(self, model: Type[BaseModel]) -> List[ActionParameterInfo]:
        """Extract parameter information from Pydantic model"""
        # Handle NoParamsAction
        if model == NoParamsAction or not hasattr(model, 'model_fields'):
            return []
        
        parameters = []
        
        try:
            for field_name, field_info in model.model_fields.items():
                # Skip model_config and other non-parameter fields
                if field_name.startswith('_') or field_name == 'model_config':
                    continue
                
                param_info = ActionParameterInfo(
                    name=field_name,
                    type=self._get_type_string(field_info.annotation),
                    required=field_info.is_required(),
                    default=field_info.default if not field_info.is_required() else None,
                    description=field_info.description,
                    constraints=self._extract_constraints(field_info)
                )
                parameters.append(param_info)
        except Exception as e:
            print(f"Error extracting parameters from {model.__name__}: {e}")
        
        return parameters
    
    def _get_type_string(self, annotation) -> str:
        """Convert type annotation to readable string"""
        if hasattr(annotation, '__origin__'):
            # Handle Union, Optional, List, etc.
            origin = annotation.__origin__
            if origin is Union:
                args = annotation.__args__
                # Filter out NoneType for Optional
                non_none_args = [arg for arg in args if arg is not type(None)]
                if len(non_none_args) == 1:
                    return self._get_type_string(non_none_args[0])
                return ' | '.join(self._get_type_string(arg) for arg in non_none_args)
            elif origin is list:
                if hasattr(annotation, '__args__'):
                    return f"List[{self._get_type_string(annotation.__args__[0])}]"
                return "List"
            elif origin is dict:
                return "Dict"
            return str(origin.__name__)
        
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        
        return str(annotation)
    
    def _extract_constraints(self, field_info) -> Dict[str, Any] | None:
        """Extract validation constraints from field"""
        constraints = {}
        
        # Get metadata if available
        if hasattr(field_info, 'metadata'):
            for metadata in field_info.metadata:
                if hasattr(metadata, 'ge'):
                    constraints['min'] = metadata.ge
                if hasattr(metadata, 'le'):
                    constraints['max'] = metadata.le
                if hasattr(metadata, 'gt'):
                    constraints['greater_than'] = metadata.gt
                if hasattr(metadata, 'lt'):
                    constraints['less_than'] = metadata.lt
                if hasattr(metadata, 'min_length'):
                    constraints['min_length'] = metadata.min_length
                if hasattr(metadata, 'max_length'):
                    constraints['max_length'] = metadata.max_length
                if hasattr(metadata, 'pattern'):
                    constraints['pattern'] = metadata.pattern
        
        return constraints if constraints else None
    
    def get_action_info(self, action_type: WorkflowActionType) -> ActionInfo:
        """Get information about a specific action"""
        if action_type not in self._actions:
            raise ValueError(f"Unknown action type: {action_type}")
        
        action = self._actions[action_type]
        
        return ActionInfo(
            action_type=action_type,
            display_name=action["display_name"],
            description=action["description"],
            parameters=action["parameters"],
            category=action["category"],
            examples=action["examples"]
        )
    
    def get_all_actions(self) -> List[ActionInfo]:
        """Get information about all available actions"""
        return [self.get_action_info(action_type) for action_type in self._actions.keys()]
    
    def get_actions_by_category(self, category: str) -> List[ActionInfo]:
        """Get actions filtered by category"""
        return [
            self.get_action_info(action_type)
            for action_type, action in self._actions.items()
            if action["category"] == category
        ]
    
    def get_parameter_model(self, action_type: WorkflowActionType) -> Type[BaseModel]:
        """Get the parameter model for an action"""
        if action_type not in self._actions:
            raise ValueError(f"Unknown action type: {action_type}")
        
        return self._actions[action_type]["parameter_model"]
    
    def validate_parameters(self, action_type: WorkflowActionType, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters against the action's model
        
        Returns:
            tuple: (is_valid, error_message)
        """
        model = self.get_parameter_model(action_type)
        
        if model == NoParamsAction:
            return True, None
        
        try:
            model(**parameters)
            return True, None
        except Exception as e:
            return False, str(e)


# Global registry instance
workflow_registry = WorkflowRegistry()