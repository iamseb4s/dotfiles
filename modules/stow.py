from modules.base import Module

class StowModule(Module):
    """
    Module for installing GNU Stow, the symlink farm manager used
    to manage dotfiles.
    """
    @property
    def id(self):
        return "stow"
    
    @property
    def label(self):
        return "GNU Stow (Dotfiles Manager)"

    @property
    def category(self):
        return "System Core"

    def install(self):
        """Installs stow via system package manager."""
        return self.sys.install_package("stow", "stow")
