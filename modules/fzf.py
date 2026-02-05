from modules.base import Module
import os
import shutil

class FzfModule(Module):
    id = "fzf"
    label = "Fzf"
    description = "A command-line fuzzy finder"
    category = "Tools"
    
    manager = {
        "arch": "system",
        "ubuntu": "git"
    }
    
    package_name = "fzf"
    
    dependencies = {
        "arch": [],
        "ubuntu": ["git"]
    }

    def is_installed(self):
        """Custom detection for fzf."""
        # 1. Check if fzf is in PATH
        if shutil.which("fzf"):
            return True
            
        # 2. Check standard git installation location
        fzf_bin = os.path.expanduser("~/.fzf/bin/fzf")
        return os.path.exists(fzf_bin)

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian:
            install_dir = os.path.expanduser("~/.fzf")
            
            # 1. Clone or update repository
            if not os.path.exists(install_dir):
                if callback: callback("Cloning fzf repository...")
                clone_cmd = f"git clone --depth 1 https://github.com/junegunn/fzf.git {install_dir}"
                if not self.system_manager.run(clone_cmd, shell=True, callback=callback, input_callback=input_callback):
                    return False
            else:
                if callback: callback("Updating fzf repository...")
                update_cmd = f"cd {install_dir} && git pull"
                self.system_manager.run(update_cmd, shell=True, callback=callback, input_callback=input_callback)

            # 2. Run install script
            # --all: install completions and key-bindings
            # --no-update-rc: DO NOT touch .zshrc or .bashrc
            if callback: callback("Running fzf installation script...")
            install_script = os.path.join(install_dir, "install")
            install_cmd = f"{install_script} --all --no-update-rc"
            return self.system_manager.run(install_cmd, shell=True, callback=callback, input_callback=input_callback)
            
        return False
