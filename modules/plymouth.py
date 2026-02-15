import os
import re
from modules.base import Module

class PlymouthModule(Module):
    """
    Module for automating Plymouth setup and Catppuccin Mocha theme integration.
    """
    id = "plymouth"
    label = "Plymouth Boot Splash"
    category = "System Core"
    description = "Graphical boot splash screen with Catppuccin Mocha theme."

    package_name = {
        "arch": "plymouth"
    }

    sub_components = [
        {
            "id": "binary",
            "label": "Plymouth Package",
            "default": True
        },
        {
            "id": "theme",
            "label": "Catppuccin Mocha Theme",
            "default": True,
            "dependencies": {
                "arch": ["yay"]
            }
        }
    ]

    stow_package = None

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if not self.system_manager.is_arch:
            if callback: callback("Plymouth automation currently only supported on Arch Linux.")
            return False

        sub_selections = override.get('sub_selections', {}) if override else {}

        # 1. Install base package
        if sub_selections.get("binary", True):
            if not super().install(override, callback, input_callback, password):
                return False

        # 2. Install Catppuccin theme from AUR
        if sub_selections.get("theme", True):
            theme_pkg = "plymouth-theme-catppuccin-mocha-git"
            if callback: callback(f"Installing {theme_pkg} from AUR...")
            if not self.system_manager.install_aur_package(theme_pkg, callback=callback, input_callback=input_callback):
                return False

        return True

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        if not self.system_manager.is_arch:
            return True

        sub_selections = override.get('sub_selections', {}) if override else {}
        
        # 1. Configure /etc/mkinitcpio.conf hooks
        if sub_selections.get("binary", True):
            mkinitcpio_path = "/etc/mkinitcpio.conf"
            if os.path.exists(mkinitcpio_path):
                if callback: callback("Configuring mkinitcpio hooks...")
                try:
                    with open(mkinitcpio_path, 'r') as f:
                        content = f.read()

                    # Robust hook insertion
                    if 'plymouth' not in content:
                        hooks_match = re.search(r'^HOOKS=\((.*?)\)', content, re.MULTILINE)
                        if hooks_match:
                            current_hooks = hooks_match.group(1).split()
                            if 'plymouth' not in current_hooks:
                                # Insert after kms if present, otherwise after udev or systemd
                                if 'kms' in current_hooks:
                                    idx = current_hooks.index('kms') + 1
                                elif 'udev' in current_hooks:
                                    idx = current_hooks.index('udev') + 1
                                elif 'systemd' in current_hooks:
                                    idx = current_hooks.index('systemd') + 1
                                else:
                                    idx = len(current_hooks)
                                
                                current_hooks.insert(idx, 'plymouth')
                                new_hooks_line = f"HOOKS=({' '.join(current_hooks)})"
                                new_content = re.sub(r'^HOOKS=\(.*\)', new_hooks_line, content, flags=re.MULTILINE)
                                
                                temp_path = "/tmp/mkinitcpio.conf.tmp"
                                with open(temp_path, 'w') as f_tmp:
                                    f_tmp.write(new_content)
                                
                                if not self.system_manager.run(["mv", temp_path, mkinitcpio_path], needs_root=True, password=password, callback=callback):
                                    return False
                except Exception as e:
                    if callback: callback(f"Warning: Failed to edit mkinitcpio.conf: {e}")

        # 2. Set default theme
        if sub_selections.get("theme", True):
            if callback: callback("Setting Plymouth default theme to catppuccin-mocha...")
            set_theme_cmd = "plymouth-set-default-theme catppuccin-mocha"
            if not self.system_manager.run(set_theme_cmd, needs_root=True, password=password, callback=callback):
                return False

        # 3. Regenerate initramfs (Always if binary is selected, to apply hooks or theme changes)
        if sub_selections.get("binary", True):
            if callback: callback("Regenerating initramfs (mkinitcpio -P)...")
            return self.system_manager.run("mkinitcpio -P", needs_root=True, password=password, callback=callback)

        return True
