from modules.base import Module

class EzaModule(Module):
    id = "eza"
    label = "Eza"
    description = "A modern, maintained replacement for 'ls'"
    category = "Tools"
    
    manager = {
        "arch": "system",
        "ubuntu": "cargo"
    }
    
    package_name = "eza"
    
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["rust"],
            "dot_deps": ["stow"]
        }
    }
