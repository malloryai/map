import re
from datetime import datetime
from typing import List, Dict, Any

class CustomPrompt:
    """
    Represents a reusable, parameterizable prompt that can be exposed as a tool.
    """
    def __init__(self,
                 id: str,
                 name: str,
                 description: str,
                 prompt_template: str,
                 category: str = "default",
                 created_at: str = None,
                 updated_at: str = None):
        if not id or not id.strip():
            raise ValueError("Prompt ID cannot be empty.")
        if not name or not name.strip():
            raise ValueError("Prompt name cannot be empty.")

        self.id = id
        self.name = name
        self.description = description
        self.prompt_template = prompt_template
        self.category = category
        
        now = datetime.utcnow().isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    @property
    def input_variables(self) -> List[str]:
        """
        Parses the prompt template to find all unique input variables.
        Variables are identified by the pattern {{variable_name}}.
        """
        if not self.prompt_template:
            return []
        
        # Find all occurrences of {{variable}}
        variables = re.findall(r'\{\{([a-zA-Z0-9_]+)\}\}', self.prompt_template)
        
        # Return a list of unique variable names
        return sorted(list(set(variables)))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the prompt object to a dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "prompt_template": self.prompt_template,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomPrompt':
        """Deserializes a dictionary into a CustomPrompt object."""
        if not data.get("id"):
            raise ValueError("ID is missing from prompt data.")
        
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "default"),
            prompt_template=data.get("prompt_template", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def __repr__(self):
        return f"<CustomPrompt(id='{self.id}', name='{self.name}')>" 