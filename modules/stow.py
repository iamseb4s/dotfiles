from modules.base import Module

class StowModule(Module):
    id = "stow"
    label = "GNU Stow"
    description = "Symlink farm manager for dotfiles"
    category = "System Core"
    manager = "system"
