import os
from modules.base import Module

class ReflectorModule(Module):
    """
    Module for automating Reflector setup to keep Arch Linux mirrorlist optimized.
    """
    id = "reflector"
    label = "Reflector"
    category = "System Core"
    description = "Arch Linux mirrorlist optimization tool."

    package_name = {
        "arch": "reflector"
    }

    sub_components = [
        {
            "id": "binary",
            "label": "Reflector Package",
            "default": True
        },
        {
            "id": "config",
            "label": "Configuration File",
            "default": True
        },
        {
            "id": "timer",
            "label": "Reflector Timer",
            "default": True
        }
    ]

    # No dotfiles for reflector in this module, handled by direct file creation
    stow_package = None

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if not self.system_manager.is_arch:
            if callback: callback("Reflector is only supported on Arch Linux.")
            return False

        sub_selections = override.get('sub_selections', {}) if override else {}

        # 1. Install base package
        if sub_selections.get("binary", True):
            if not super().install(override, callback, input_callback, password):
                return False

        return True

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        if not self.system_manager.is_arch:
            return True

        sub_selections = override.get('sub_selections', {}) if override else {}
        
        # 1. Setup /etc/xdg/reflector/reflector.conf
        if sub_selections.get("config", True):
            config_dir = "/etc/xdg/reflector"
            config_path = f"{config_dir}/reflector.conf"
            
            if callback: callback(f"Creating configuration at {config_path}...")
            
            config_content = (
                "--save /etc/pacman.d/mirrorlist\n"
                "--protocol https\n"
                "--latest 10\n"
                "--sort rate\n"
            )
            
            try:
                # Ensure directory exists
                self.system_manager.run(f"mkdir -p {config_dir}", needs_root=True, password=password, callback=callback)
                
                # Write to a temporary file first
                temp_path = "/tmp/reflector.conf.tmp"
                with open(temp_path, 'w') as f:
                    f.write(config_content)
                
                # Move to destination
                if not self.system_manager.run(f"mv {temp_path} {config_path}", needs_root=True, password=password, callback=callback):
                    return False
            except Exception as e:
                if callback: callback(f"Warning: Failed to create reflector.conf: {e}")
                return False

        # 2. Enable and start reflector.timer
        if sub_selections.get("timer", True):
            if callback: callback("Enabling and starting reflector.timer...")
            timer_cmd = "systemctl enable --now reflector.timer"
            if not self.system_manager.run(timer_cmd, needs_root=True, password=password, callback=callback):
                return False

        return True
