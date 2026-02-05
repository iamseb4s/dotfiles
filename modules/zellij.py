from modules.base import Module

class ZellijModule(Module):
    id = "zellij"
    label = "Zellij"
    description = "A terminal workspace with batteries included"
    category = "Tools"
    
    manager = {
        "arch": "system",
        "ubuntu": "cargo"
    }
    
    package_name = "zellij"
    
    dependencies = {
        "arch": [],
        "ubuntu": ["rust"]
    }
