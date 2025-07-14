import yaml
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from .prompt import CustomPrompt

logger = logging.getLogger(__name__)

class YAMLPromptStorage:
    """
    Manages the persistence of CustomPrompt objects to YAML files.
    Each prompt is stored in its own file within the configured directory.
    """
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        if not self.storage_path.exists():
            logger.info(f"Creating prompt storage directory at: {self.storage_path}")
            self.storage_path.mkdir(parents=True)

    def _get_filepath(self, prompt_id: str) -> Path:
        """Constructs the full path for a given prompt ID."""
        return self.storage_path / f"{prompt_id}.yaml"

    def save(self, prompt: CustomPrompt) -> None:
        """Saves a single prompt to a YAML file."""
        filepath = self._get_filepath(prompt.id)
        prompt.updated_at = datetime.utcnow().isoformat()
        try:
            with open(filepath, 'w') as f:
                yaml.dump(prompt.to_dict(), f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved prompt '{prompt.id}' to {filepath}")
        except IOError as e:
            logger.error(f"Error saving prompt '{prompt.id}' to {filepath}: {e}")
            raise

    def get(self, prompt_id: str) -> Optional[CustomPrompt]:
        """Retrieves a single prompt by its ID."""
        filepath = self._get_filepath(prompt_id)
        if not filepath.exists():
            return None
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)
                return CustomPrompt.from_dict(data)
        except (IOError, yaml.YAMLError) as e:
            logger.error(f"Error reading or parsing prompt file {filepath}: {e}")
            return None

    def get_all(self) -> List[CustomPrompt]:
        """Retrieves all prompts from the storage directory."""
        prompts = []
        for filepath in self.storage_path.glob('*.yaml'):
            prompt_id = filepath.stem
            prompt = self.get(prompt_id)
            if prompt:
                prompts.append(prompt)
        # Sort prompts by name for consistent ordering
        prompts.sort(key=lambda p: p.name.lower())
        return prompts

    def delete(self, prompt_id: str) -> bool:
        """Deletes a prompt's YAML file."""
        filepath = self._get_filepath(prompt_id)
        if not filepath.exists():
            logger.warning(f"Attempted to delete non-existent prompt: {prompt_id}")
            return False
        try:
            os.remove(filepath)
            logger.info(f"Deleted prompt file: {filepath}")
            return True
        except OSError as e:
            logger.error(f"Error deleting prompt file {filepath}: {e}")
            return False 