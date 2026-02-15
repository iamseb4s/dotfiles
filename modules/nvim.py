from modules.base import Module

class NeovimModule(Module):
    id = "nvim"
    label = "Neovim"
    description = "Hyperextensible Vim-based text editor with LazyVim starter"
    category = "Development"
    
    manager = {
        "arch": "system",
        "ubuntu": "bob"
    }
    
    # Neovim is just 'nvim' for the bob manager or system
    package_name = {
        "arch": "neovim",
        "ubuntu": "nvim"
    }
    
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["bob", "unzip"],
            "dot_deps": ["stow"]
        }
    }
