import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class GitManager:
    """Manages Git operations for cloning and updating repositories."""

    def ensure_repo(self, repo_url: str, branch: str, local_path: Path) -> bool:
        """
        Ensures a GitHub repository is cloned or updated to the specified branch.
        Returns True if successful, False otherwise.
        """
        if local_path.exists():
            logger.info(f"Updating existing GitHub repository: {local_path.name}")
            return self._update_repo(branch, local_path)
        else:
            logger.info(f"Cloning new GitHub repository: {local_path.name}")
            return self._clone_repo(repo_url, branch, local_path)

    def _clone_repo(self, repo_url: str, branch: str, local_path: Path) -> bool:
        """Clones a new GitHub repository."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--branch", branch, repo_url, str(local_path)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Successfully cloned {local_path.name} to {local_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error cloning {repo_url}: {e.stderr}")
            return False

    def _update_repo(self, branch: str, local_path: Path) -> bool:
        """Updates an existing GitHub repository."""
        try:
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=local_path,
                check=True,
                capture_output=True,
                text=True
            )
            subprocess.run(
                ["git", "checkout", branch],
                cwd=local_path,
                check=True,
                capture_output=True,
                text=True
            )
            subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=local_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Successfully updated {local_path.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repo {local_path.name}: {e.stderr}")
            return False 