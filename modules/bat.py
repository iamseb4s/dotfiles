from modules.base import Module

class BatModule(Module):
    id = "bat"
    label = "Bat"
    description = "A cat clone with syntax highlighting and Git integration"
    category = "Tools"
    
    manager = {
        "arch": "system",
        "ubuntu": "cargo"
    }
    
    package_name = "bat"
    
    dependencies = {
        "arch": [],
        "ubuntu": ["rust"]
    }
