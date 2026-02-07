from modules.base import Module
import os

class AtuinModule(Module):
    id = "atuin"
    label = "Atuin"
    description = "Magical shell history replaced with a SQLite database"
    category = "Tools"
    
    manager = {
        "arch": "system",
        "ubuntu": "cargo"
    }
    
    package_name = "atuin"
    
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["rust"],
            "dot_deps": ["stow"]
        }
    }

    sub_components = [
        {'id': 'binary', 'label': 'Atuin Package', 'default': True},
        {'id': 'import_history', 'label': 'Import Shell History', 'default': True}
    ]

    def install(self, override=None, callback=None, input_callback=None, password=None):
        # 1. Base installation (Binary)
        success = super().install(override, callback, input_callback, password)
        if not success:
            return False

        # 2. History Import (Sub-component)
        sub_selections = override.get('sub_selections', {}) if override else {}
        if sub_selections.get('import_history', True):
            if callback: callback("Importing shell history into Atuin...")
            
            # Resolve binary path for the import command
            # If installed via cargo, it might not be in PATH yet in the current session
            binary_path = "atuin"
            if self.get_manager() == "cargo":
                cargo_bin = os.path.expanduser("~/.cargo/bin/atuin")
                if os.path.exists(cargo_bin):
                    binary_path = cargo_bin
            
            import_cmd = f"{binary_path} import auto"
            # Run import. We don't strictly return False on failure here as the app is already installed.
            self.system_manager.run(import_cmd, shell=True, callback=callback, input_callback=input_callback)
            
        return True
