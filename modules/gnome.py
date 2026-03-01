import os
import re
import shutil
import subprocess
import urllib.request
import json
from modules.base import Module

class GnomeModule(Module):
    """
    Module for automating GNOME desktop restoration, including themes, icons, 
    extensions, and dconf settings.
    """
    id = "gnome"
    label = "GNOME Desktop"
    category = "Desktop"
    description = "Full GNOME environment restoration (Themes, Icons, Extensions, Settings)."

    def __init__(self, system_manager):
        super().__init__(system_manager)
        # GNOME module handles its own config loading, no stow needed
        self.stow_package = None

    def has_usable_dotfiles(self):
        """Overrides base logic. GNOME restoration doesn't use Stow but 
        needs to run the configure method to load dconf files.
        """
        return True

    # Standard package dependencies
    dependencies = {
        "arch": ["wget", "git", "unzip", "curl", "extension-manager", "ttf-hack-nerd"],
        "ubuntu": ["wget", "git", "unzip", "curl", "extension-manager"]
    }

    # Package name for the system package manager driver
    package_name = {
        "arch": "extension-manager",
        "ubuntu": "gnome-shell-extension-manager"
    }

    sub_components = [
        {"id": "papirus", "label": "Papirus Icon Theme", "default": True, "dependencies": ["wget"]},
        {"id": "orchis", "label": "Orchis GTK Theme", "default": True, "dependencies": ["git"]},
        {
            "id": "extensions", 
            "label": "Extensions Management", 
            "default": True,
            "children": [
                {"id": "extension_manager", "label": "Extension Manager (Application)", "default": True},
                {"id": "extensions_install", "label": "GNOME Extensions (Download/Install)", "default": True, "dependencies": ["curl", "unzip"]},
            ]
        },
        {
            "id": "config",
            "label": "Restore Configuration",
            "default": True,
            "children": [
                {
                    "id": "appearance", 
                    "label": "Appearance", 
                    "default": True, 
                    "dependencies": ["orchis", "papirus", "ttf-hack-nerd"]
                },
                {"id": "shell", "label": "Shell UI", "default": True},
                {
                    "id": "extensions_config", 
                    "label": "Extensions Settings", 
                    "default": True, 
                    "dependencies": ["extensions_install"]
                },
                {"id": "keybindings", "label": "Keybindings", "default": True},
                {"id": "window_manager", "label": "Window Manager", "default": True},
                {"id": "nautilus", "label": "Nautilus", "default": True},
                {"id": "privacy_search", "label": "Privacy & Search", "default": True},
                {"id": "system", "label": "System (Power/Color)", "default": True},
            ]
        }
    ]

    def install(self, override=None, callback=None, input_callback=None, password=None):
        sub_selections = override.get('sub_selections', {}) if override else {}

        # 1. Install Papirus Icon Theme
        if sub_selections.get("papirus", True):
            if callback: callback("Installing Papirus Icon Theme...")
            # Official installer script
            cmd = 'wget -qO- https://git.io/papirus-icon-theme-install | sh'
            if not self.system_manager.run(cmd, needs_root=True, shell=True, password=password, callback=callback):
                if callback: callback("Warning: Papirus installation failed.")

        # 2. Install Orchis GTK Theme
        if sub_selections.get("orchis", True):
            if callback: callback("Installing Orchis GTK Theme...")
            repo_url = "https://github.com/vinceliuice/Orchis-theme.git"
            tmp_dir = "/tmp/orchis-theme"
            if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
            
            if self.system_manager.run(f"git clone --depth 1 {repo_url} {tmp_dir}", callback=callback):
                install_cmd = "./install.sh -c dark -s standard -i arch -l -f --tweaks compact macos"
                if not self.system_manager.run(f"bash -c 'cd {tmp_dir} && {install_cmd}'", shell=True, callback=callback):
                    if callback: callback("Warning: Orchis installation script failed.")
                shutil.rmtree(tmp_dir)
            else:
                if callback: callback("Warning: Failed to clone Orchis theme repository.")

        # 3. Install Extension Manager (App)
        if sub_selections.get("extension_manager", True):
            if callback: callback("Installing Extension Manager application...")
            # Use super().install to handle package installation via system manager
            if not super().install(override, callback, input_callback, password):
                if callback: callback("Warning: extension-manager package installation failed.")

        # 4. Install GNOME Extensions (Physical files)
        if sub_selections.get("extensions_install", True):
            self._install_gnome_extensions(callback)

        return True

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        sub_selections = override.get('sub_selections', {}) if override else {}
        
        # Check if master configuration toggle is enabled
        if not sub_selections.get("config", True):
            return True

        dconf_base_path = os.path.join(os.getcwd(), "dots/gnome/dconf")
        
        # Map sub-component IDs to their .dconf files
        mapping = {
            "appearance": "appearance.dconf",
            "shell": "shell.dconf",
            "extensions_config": "extensions.dconf",
            "keybindings": "keybindings.dconf",
            "window_manager": "window_manager.dconf",
            "nautilus": "nautilus.dconf",
            "privacy_search": "privacy_and_search.dconf",
            "system": "system.dconf"
        }

        for comp_id, filename in mapping.items():
            if sub_selections.get(comp_id, True):
                file_path = os.path.join(dconf_base_path, filename)
                if os.path.exists(file_path):
                    if callback: callback(f"Restoring {comp_id} configuration...")
                    # dconf load / < file.dconf restores absolute paths
                    self.system_manager.run(f"dconf load / < {file_path}", shell=True, callback=callback)
                else:
                    if callback: callback(f"Notice: Backup file {filename} not found, skipping...")

        return True

    def _get_shell_version(self):
        """Helper to get current GNOME Shell major version."""
        try:
            result = subprocess.check_output(["gnome-shell", "--version"]).decode()
            match = re.search(r"GNOME Shell (\d+)", result)
            return match.group(1) if match else "49"
        except:
            return "49"

    def _install_gnome_extensions(self, callback):
        """
        Parses shell.dconf to find required extensions and downloads them 
        directly from GNOME Extensions using their direct download API.
        """
        shell_dconf = os.path.join(os.getcwd(), "dots/gnome/dconf/shell.dconf")
        if not os.path.exists(shell_dconf):
            if callback: callback("Notice: shell.dconf not found, cannot auto-install extensions.")
            return

        with open(shell_dconf, 'r') as f:
            lines = f.readlines()
        
        # Extract IDs from enabled-extensions and disabled-extensions lists
        ext_ids = []
        for line in lines:
            if line.startswith('enabled-extensions=') or line.startswith('disabled-extensions='):
                found = re.findall(r"'([^']+)'", line)
                # Filter out obvious non-extension IDs
                ext_ids.extend([id for id in found if ("@" in id or "." in id) and not id.endswith(".desktop")])
        
        ext_ids = list(set(ext_ids)) # Deduplicate
        
        if not ext_ids:
            if callback: callback("No valid extensions found in backup.")
            return

        shell_version = self._get_shell_version()
        ext_dir = os.path.expanduser("~/.local/share/gnome-shell/extensions")
        os.makedirs(ext_dir, exist_ok=True)

        for uuid in ext_ids:
            # Skip if already installed physically
            if os.path.exists(os.path.join(ext_dir, uuid)):
                continue
                
            if callback: callback(f"Downloading extension: {uuid}...")
            try:
                # Use the direct download URL with the shell_version parameter
                # This is more reliable than querying extension-info first
                download_url = f"https://extensions.gnome.org/download-extension/{uuid}.shell-extension.zip?shell_version={shell_version}"
                tmp_zip = f"/tmp/{uuid}.zip"
                
                if self.system_manager.run(f"curl -L -o {tmp_zip} {download_url}", callback=callback):
                    # Verify if ZIP is valid before extracting
                    if self.system_manager.run(f"unzip -t {tmp_zip}", callback=callback):
                        target_path = os.path.join(ext_dir, uuid)
                        os.makedirs(target_path, exist_ok=True)
                        self.system_manager.run(f"unzip -o {tmp_zip} -d {target_path}", callback=callback)
                    else:
                        if callback: callback(f"Warning: Downloaded file for {uuid} is not a valid ZIP.")
                    
                    if os.path.exists(tmp_zip): os.remove(tmp_zip)
                else:
                    if callback: callback(f"Failed to download {uuid}")
            except Exception as e:
                if callback: callback(f"Error processing extension {uuid}: {e}")
