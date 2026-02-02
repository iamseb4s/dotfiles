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

    sub_components = [
        {
            "id": "binary",
            "label": "Zsh Package",
            "default": True,
            "children": [
                {"id": "chsh", "label": "Mark as default shell", "default": True},
                {
                    "id": "omz",
                    "label": "Oh-My-Zsh",
                    "default": True,
                    "children": [
                        {"id": "autosuggestions", "label": "zsh-autosuggestions", "default": True},
                        {"id": "syntax_highlighting", "label": "zsh-syntax-highlighting + Catppuccin Mocha theme", "default": True},
                        {"id": "p10k", "label": "Powerlevel10k Theme", "default": True}
                    ]
                }
            ]
        }
    ]

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Modular installation of Zsh ecosystem."""
        subs = override.get('sub_selections', {}) if override else {}
        
        # 1. System Package
        if not super().install(override, callback, input_callback, password):
            return False

        # 2. Oh-My-Zsh & Components
        omz_dir = os.path.expanduser("~/.oh-my-zsh")
        if subs.get("omz", True):
            if not os.path.exists(omz_dir):
                if callback: callback("Installing Oh-My-Zsh...")
                cmd = 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'
                self.system_manager.run(cmd, shell=True, callback=callback, input_callback=input_callback)

            # 3. Clone Custom Repos (Plugins/Themes)
            custom = os.path.join(omz_dir, "custom")
            repos = {
                "p10k": ("https://github.com/romkatv/powerlevel10k.git", "themes/powerlevel10k"),
                "autosuggestions": ("https://github.com/zsh-users/zsh-autosuggestions", "plugins/zsh-autosuggestions"),
                "syntax_highlighting": ("https://github.com/zsh-users/zsh-syntax-highlighting.git", "plugins/zsh-syntax-highlighting")
            }
            
            for cid, (url, rel_path) in repos.items():
                dest = os.path.join(custom, rel_path)
                if subs.get(cid, True) and not os.path.exists(dest):
                    if callback: callback(f"Cloning {cid}...")
                    self.system_manager.run(f"git clone --depth=1 {url} {dest}", shell=True, callback=callback, input_callback=input_callback)

            # 4. Catppuccin Theme for Syntax Highlighting
            theme_file = os.path.join(custom, "plugins/zsh-syntax-highlighting/themes/catppuccin_mocha-zsh-syntax-highlighting.zsh")
            if subs.get("syntax_highlighting", True) and not os.path.exists(theme_file):
                if callback: callback("Downloading Catppuccin Mocha syntax highlighting theme...")
                os.makedirs(os.path.dirname(theme_file), exist_ok=True)
                url = "https://raw.githubusercontent.com/catppuccin/zsh-syntax-highlighting/main/themes/catppuccin_mocha-zsh-syntax-highlighting.zsh"
                self.system_manager.run(f"curl -fsSL {url} -o {theme_file}", shell=True, callback=callback, input_callback=input_callback)

        # 5. Default Shell
        if subs.get("chsh", True):
            zsh_path = shutil.which("zsh")
            if zsh_path:
                if callback: callback(f"Changing default shell to {zsh_path}...")
                self.system_manager.run(f"chsh -s {zsh_path}", needs_root=True, password=password, callback=callback, input_callback=input_callback)

        return True
