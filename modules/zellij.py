from modules.base import Module

class ZellijModule(Module):
    id = "zellij"
    label = "Zellij"
    description = "A terminal workspace with batteries included"
    category = "Terminal"
    
    manager = {
        "arch": "system",
        "ubuntu": "cargo"
    }
    
    package_name = "zellij"
    
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["rust"],
            "dot_deps": ["stow"]
        }
    }
