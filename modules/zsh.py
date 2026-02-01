import os
import shutil
from core.tui import TUI
from modules.base import Module

class ZshModule(Module):
    id = "zsh"
    label = "Zsh & Oh-My-Zsh"
    category = "Terminal"
    manager = "system"
    description = "Zsh shell with Oh-My-Zsh, Powerlevel10k theme, and productivity plugins."

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Full automated installation of Zsh ecosystem."""
        # 1. Install Zsh binary
        if not super().install(override, callback, input_callback, password):
            return False

        # 2. Install Oh-My-Zsh (unattended)
        omz_dir = os.path.expanduser("~/.oh-my-zsh")
        if not os.path.exists(omz_dir):
            if callback: callback("Installing Oh-My-Zsh...")
            cmd = 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'
            if not self.system_manager.run(cmd, shell=True, callback=callback, input_callback=input_callback):
                return False

        # 3. Clone Plugins and Themes
        custom_dir = os.path.join(omz_dir, "custom")
        components = [
            ("https://github.com/romkatv/powerlevel10k.git", os.path.join(custom_dir, "themes", "powerlevel10k")),
            ("https://github.com/zsh-users/zsh-autosuggestions", os.path.join(custom_dir, "plugins", "zsh-autosuggestions")),
            ("https://github.com/zsh-users/zsh-syntax-highlighting.git", os.path.join(custom_dir, "plugins", "zsh-syntax-highlighting"))
        ]

        for repo_url, dest in components:
            if not os.path.exists(dest):
                if callback: callback(f"Cloning {os.path.basename(dest)}...")
                if not self.system_manager.run(f"git clone --depth=1 {repo_url} {dest}", shell=True, callback=callback, input_callback=input_callback):
                    return False

        # 4. Install Catppuccin Mocha theme for syntax highlighting
        theme_dir = os.path.join(custom_dir, "plugins", "zsh-syntax-highlighting", "themes")
        theme_file = os.path.join(theme_dir, "catppuccin_mocha-zsh-syntax-highlighting.zsh")
        if not os.path.exists(theme_file):
            if callback: callback("Downloading Catppuccin Mocha syntax highlighting theme...")
            os.makedirs(theme_dir, exist_ok=True)
            raw_url = "https://raw.githubusercontent.com/catppuccin/zsh-syntax-highlighting/main/themes/catppuccin_mocha-zsh-syntax-highlighting.zsh"
            if not self.system_manager.run(f"curl -fsSL {raw_url} -o {theme_file}", shell=True, callback=callback, input_callback=input_callback):
                return False

        # 5. Change default shell to Zsh
        zsh_path = shutil.which("zsh")
        if zsh_path:
            if callback: callback(f"Changing default shell to {zsh_path}...")
            # Use chsh with the captured password
            self.system_manager.run(f"chsh -s {zsh_path}", needs_root=True, password=password, callback=callback, input_callback=input_callback)

        return True
