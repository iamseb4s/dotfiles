import os
from modules.base import Module

class VscodeModule(Module):
    id = "vscode"
    label = "Visual Studio Code"
    category = "Development"
    description = "Microsoft's powerful code editor with custom settings and extensions."
    
    package_name = {
        "arch": "visual-studio-code-bin"
    }

    manager = {
        "arch": "yay",
        "default": "system"
    }

    dependencies = {
        "arch": {
            "bin_deps": ["yay"],
            "dot_deps": ["stow"]
        },
        "default": {
            "dot_deps": ["stow"]
        }
    }

    sub_components = [
        {
            "id": "binary",
            "label": "VS Code Package",
            "default": True
        },
        {
            "id": "dotfiles",
            "label": "User Configuration",
            "default": True
        },
        {
            "id": "extensions",
            "label": "Install VS Code Extensions",
            "default": True
        }
    ]

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        """Deploy dotfiles and install extensions."""
        # 1. Deploy dotfiles using stow
        if not super().configure(override, callback, input_callback, password):
            return False

        # 2. Install extensions
        sub_selections = override.get('sub_selections', {}) if override else {}
        if not sub_selections.get('extensions', True):
            return True

        extensions_file = os.path.join(os.getcwd(), "dots/vscode/.config/Code/User/extensions.txt")
        if not os.path.exists(extensions_file):
            if callback: callback("No extensions.txt found, skipping extensions installation.")
            return True

        if callback: callback("Installing VS Code extensions...")
        try:
            with open(extensions_file, 'r') as f:
                extensions = [line.strip() for line in f if line.strip()]
            
            for ext in extensions:
                if callback: callback(f"Installing extension: {ext}")
                self.system_manager.run(f"code --install-extension {ext}", shell=True, callback=callback, input_callback=input_callback)
        except Exception as e:
            if callback: callback(f"Error installing extensions: {str(e)}")
            return False

        return True
