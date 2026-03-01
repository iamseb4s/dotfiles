from modules.base import Module

class HackNerdFontModule(Module):
    """
    Module for installing Hack Nerd Font, a high-quality font for terminal and UI.
    """
    id = "ttf-hack-nerd"
    label = "Hack Nerd Font"
    category = "Infrastructure"
    description = "Hack Nerd Font for a better terminal and UI experience."

    package_name = {
        "arch": "ttf-hack-nerd"
    }
