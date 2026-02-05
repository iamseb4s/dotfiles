from modules.base import Module
import os
import shutil

class RustModule(Module):
    id = "rust"
    label = "Rust & Cargo"
    description = "Rust programming language and Cargo package manager via rustup"
    category = "Infrastructure"
    
    # On Arch we use the official repo; on Ubuntu we use the rustup installer
    package_name = {
        "arch": "rust",
        "ubuntu": "curl" 
    }
    
    dependencies = {
        "arch": [],
        "ubuntu": ["build_tools", "openssl", "curl", "git"]
    }

    def is_installed(self):
        """Custom detection for Rust/Cargo."""
        # 1. Check if cargo is in PATH (universal)
        if shutil.which("cargo"):
            return True
            
        # 2. Check standard rustup location
        cargo_bin = os.path.expanduser("~/.cargo/bin/cargo")
        return os.path.exists(cargo_bin)

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian: # Covers Ubuntu
            if callback: callback("Downloading and running rustup installer...")
            
            # Non-interactive installation (-y)
            install_cmd = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
            success = self.system_manager.run(install_cmd, shell=True, callback=callback, input_callback=input_callback)
            
            if success and callback:
                callback("Rust installed successfully. Note: You might need to restart your shell or source ~/.cargo/env")
            
            return success
            
        return False
