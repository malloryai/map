from typing import List, Optional, Dict, Any
import re
from slugify import slugify

from .prompt import CustomPrompt
from .storage import YAMLPromptStorage

class PromptManager:
    """
    Handles the business logic for managing custom prompts.
    This class acts as the main interface for the UI and API layers.
    """
    def __init__(self, storage: YAMLPromptStorage):
        self.storage = storage

    def create_prompt(self, name: str, description: str, prompt_template: str, category: str) -> CustomPrompt:
        """
        Creates a new prompt, generates a unique ID, and saves it.
        """
        if not name or not name.strip():
            raise ValueError("Prompt name is required.")
        
        prompt_id = self.generate_id(name)
        if self.storage.get(prompt_id):
            raise ValueError(f"A prompt with the ID '{prompt_id}' already exists.")

        prompt = CustomPrompt(
            id=prompt_id,
            name=name,
            description=description,
            prompt_template=prompt_template,
            category=category or "default"
        )
        self.storage.save(prompt)
        return prompt

    def update_prompt(self, prompt_id: str, updates: Dict[str, Any]) -> Optional[CustomPrompt]:
        """
        Updates an existing prompt with new data.
        """
        prompt = self.storage.get(prompt_id)
        if not prompt:
            return None

        # You can't change the ID, but you can change the name, which might affect future ID generations
        # but the existing file remains with the old ID. This is a design choice for stability.
        prompt.name = updates.get("name", prompt.name)
        prompt.description = updates.get("description", prompt.description)
        prompt.prompt_template = updates.get("prompt_template", prompt.prompt_template)
        prompt.category = updates.get("category", prompt.category)

        self.storage.save(prompt)
        return prompt

    def delete_prompt(self, prompt_id: str) -> bool:
        """Deletes a prompt."""
        return self.storage.delete(prompt_id)

    def get_prompt(self, prompt_id: str) -> Optional[CustomPrompt]:
        """Retrieves a single prompt by its ID."""
        return self.storage.get(prompt_id)

    def get_all_prompts(self) -> List[CustomPrompt]:
        """Retrieves all prompts."""
        return self.storage.get_all()

    def generate_id(self, name: str) -> str:
        """
        Generates a URL-friendly and filesystem-safe ID from a prompt name.
        Uses python-slugify for robust slug generation.
        """
        return slugify(name, lowercase=True, separator='-') 