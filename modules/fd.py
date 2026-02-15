from modules.base import Module

class FdModule(Module):
    """
    Module for installing 'fd' (fd-find), a fast alternative to 'find'.
    """
    id = "fd"
    label = "fd-find"
    category = "CLI Tools"
    description = "A simple, fast and user-friendly alternative to 'find'."
    
    package_name = {
        "arch": "fd",
        "ubuntu": "fd-find"
    }
    
    binary_names = ["fd", "fdfind"]
