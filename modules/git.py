from modules.base import Module

class GitModule(Module):
    id = "git"
    label = "Git"
    description = "Distributed version control system"
    category = "Infrastructure"
    
    package_name = {
        "arch": "git",
        "ubuntu": "git"
    }
    
    dependencies = {
        "default": {
            "dot_deps": ["stow"]
        }
    }
