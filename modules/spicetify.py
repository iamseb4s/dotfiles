import os
from modules.base import Module

class SpicetifyModule(Module):
    """
    Module for installing and configuring Spicetify to theme Spotify.
    """
    id = "spicetify"
    label = "Spicetify"
    category = "Desktop"
    description = "Command-line tool to customize the official Spotify client."

    # Spicetify is installed via a script, not a package manager package directly
    # although it can be in AUR, user requested the curl installation.
    package_name = "spicetify"
    
    dependencies = {
        "default": {
            "bin_deps": ["spotify", "curl"],
            "dot_deps": ["stow"]
        }
    }

    def is_installed(self):
        """Checks if spicetify binary exists in the standard location or PATH."""
        if super().is_installed():
            return True
        return os.path.exists(os.path.expanduser("~/.spicetify/spicetify"))

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Installs Spicetify via the official script."""
        if self.is_installed():
            if callback: callback("Spicetify is already installed.")
            return True

        if callback: callback("Downloading and running official Spicetify installer...")
        install_cmd = "curl -fsSL https://raw.githubusercontent.com/spicetify/cli/main/install.sh | sh"
        
        success = self.system_manager.run(install_cmd, shell=True, callback=callback, input_callback=input_callback)
        
        if success and callback:
            callback("Spicetify installed successfully in ~/.spicetify/")
            
        return success

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        """Deploys dotfiles and applies spicetify configuration."""
        # 1. Run stow via base class
        if not super().configure(override, callback, input_callback, password):
            return False

        # 2. Dynamic INI updates (Portability and Extension Auto-discovery)
        config_path = os.path.expanduser("~/.config/spicetify/config-xpui.ini")
        ext_dir = os.path.expanduser("~/.config/spicetify/Extensions")
        theme_dir = os.path.expanduser("~/.config/spicetify/Themes/sleek")
        sync_script = os.path.expanduser("~/.config/spicetify/scripts/sync.sh")

        # Bootstrap: If theme or extensions are missing, run sync script
        if os.path.exists(sync_script) and (not os.path.exists(theme_dir) or not os.path.exists(ext_dir) or not os.listdir(ext_dir)):
            if callback: callback("Missing Spicetify assets. Running initial synchronization...")
            self.system_manager.run(f"bash {sync_script}", shell=True, callback=callback, input_callback=input_callback)
        
        if os.path.exists(config_path):
            if callback: callback("Updating config-xpui.ini for portability and sync...")
            try:
                import configparser
                # Use interpolation=None to avoid issues with special characters in paths/tokens
                config = configparser.ConfigParser(interpolation=None)
                config.read(config_path)
                
                # Ensure correct sections exist
                if 'Setting' not in config: config.add_section('Setting')
                if 'AdditionalOptions' not in config: config.add_section('AdditionalOptions')
                
                # Set portable paths
                config['Setting']['prefs_path'] = os.path.expanduser("~/.config/spotify/prefs")
                
                # Auto-detect extensions in the folder
                if os.path.exists(ext_dir):
                    extensions = [f for f in os.listdir(ext_dir) if f.endswith(('.js', '.mjs'))]
                    if extensions:
                        config['AdditionalOptions']['extensions'] = "|".join(extensions)
                
                with open(config_path, 'w') as f:
                    config.write(f, space_around_delimiters=True)
            except Exception as e:
                if callback: callback(f"Warning: Failed to update config-xpui.ini: {e}")

        # 3. Apply Spicetify configuration
        if callback: callback("Applying Spicetify configuration (backup apply)...")
        
        # We try to use the binary from its default installation path
        spicetify_bin = os.path.expanduser("~/.spicetify/spicetify")
        if not os.path.exists(spicetify_bin):
            spicetify_bin = "spicetify" # Try from PATH

        # Spicetify needs to backup and apply the theme
        # Note: This requires Spotify to be installed and closed.
        apply_cmd = f"{spicetify_bin} backup apply"
        self.system_manager.run(apply_cmd, shell=True, callback=callback, input_callback=input_callback)
        
        return True
