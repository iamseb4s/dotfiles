import os
import shutil
from modules.base import Module

class YayModule(Module):
    """
    Module for automating the installation of 'yay', an AUR helper for Arch Linux.
    """
    id = "yay"
    label = "Yay (AUR Helper)"
    category = "System Core"
    description = "AUR helper written in Go to easily install packages from the Arch User Repository."
    
    package_name = {
        "arch": "yay"
    }
    
    # Dependencies needed to build yay
    dependencies = {
        "arch": {
            "bin_deps": ["base-devel", "git"]
        }
    }

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Custom installation logic for yay on Arch Linux."""
        if not self.system_manager.is_arch:
            if callback: callback("yay installation is only supported on Arch Linux.")
            return True # No-op for other distros
            
        if self.is_installed():
            if callback: callback("yay is already installed.")
            return True

        # Ensure base dependencies are installed via pacman first
        if not super().install(override, callback, input_callback, password):
            return False

        build_dir = "/tmp/yay-build"
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        if callback: callback("Cloning yay repository from AUR...")
        clone_cmd = f"git clone https://aur.archlinux.org/yay.git {build_dir}"
        if not self.system_manager.run(clone_cmd, shell=True, callback=callback, input_callback=input_callback):
            return False

        if callback: callback("Building and installing yay (this may take a while)...")
        # makepkg -si --noconfirm
        # -s: install missing dependencies
        # -i: install the resulting package
        install_cmd = f"cd {build_dir} && makepkg -si --noconfirm"
        success = self.system_manager.run(install_cmd, shell=True, callback=callback, input_callback=input_callback)

        # Cleanup build directory
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        return success

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        """Yay does not require specific dotfile configuration."""
        return True
