from core.system import System
import shutil
import os

class Module:
    def __init__(self, sys_manager: System):
        self.sys = sys_manager
    
    @property
    def id(self):
        """Unique identifier (e.g. 'git')"""
        raise NotImplementedError
        
    @property
    def label(self):
        """Human readable name (e.g. 'Git & GitHub CLI')"""
        raise NotImplementedError

    @property
    def category(self):
        """Returns category name (e.g. 'System', 'Dev Tools', 'Apps'). Default: 'Uncategorized'"""
        return "Uncategorized"

    @property
    def dependencies(self):
        """List of module IDs that this module depends on."""
        return []

    def install(self):
        """Installs binaries/dependencies."""
        raise NotImplementedError
    
    def configure(self):
        """Sets up configuration files (Stow or Copy)."""
        pass # Optional

    def run_stow(self, package_name):
        """Helper to run GNU stow."""
        # Check if stow is installed?
        dotfiles_dir = os.path.join(os.getcwd(), "dots")
        target_dir = os.path.expanduser("~")
        
        # Only print log, don't use print() directly if we want to capture output later
        # For now we use print, but TUI will handle this later.
        print(f"[{self.id}] Stowing {package_name}...")
        try:
            # We assume we are in the root of the repo
            self.sys.run(
                ["stow", "--dir", dotfiles_dir, "--target", target_dir, "-R", package_name]
            )
            print(f"[{self.id}] Symlinks created.")
        except Exception:
            print(f"[{self.id}] Error running stow.")
