from modules.base import Module
import os
import shutil

class OpencodeModule(Module):
    id = "opencode"
    label = "OpenCode"
    description = "Official OpenCode CLI - The interactive agent for software engineering"
    category = "CLI Tools"
    
    # The installation script is universal for Unix-like systems
    manager = "wget" 
    package_name = "opencode"
    
    dependencies = {
        "default": {
            "bin_deps": ["curl"],
            "dot_deps": ["stow"]
        }
    }

    def is_installed(self):
        """Checks for the official binary location."""
        binary_path = os.path.expanduser("~/.opencode/bin/opencode")
        return os.path.exists(binary_path)

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if callback: callback("Downloading and running official OpenCode installer...")
        
        # Official one-liner installation
        install_cmd = "curl -fsSL https://opencode.ai/install | bash"
        
        success = self.system_manager.run(install_cmd, shell=True, callback=callback, input_callback=input_callback)
        
        if success and callback:
            callback("OpenCode installed successfully in ~/.opencode/bin/")
            
        return success
