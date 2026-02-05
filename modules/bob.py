from modules.base import Module

class BobModule(Module):
    id = "bob"
    label = "Bob (Neovim Manager)"
    description = "Version manager for Neovim written in Rust"
    category = "Infrastructure"
    
    manager = "cargo"
    package_name = {
        "ubuntu": "bob-nvim"
    }
    
    dependencies = {
        "ubuntu": ["rust"]
    }
