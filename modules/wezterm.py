from modules.base import Module
import os

class WezTermModule(Module):
    id = "wezterm"
    label = "WezTerm"
    description = "A GPU-accelerated cross-platform terminal emulator and multiplexer"
    category = "Tools"
    
    package_name = "wezterm"
    
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["curl"],
            "dot_deps": ["stow"]
        }
    }

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Modular installation for WezTerm."""
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian:
            if callback: callback("Setting up official WezTerm repository...")
            
            keyring_path = "/usr/share/keyrings/wezterm-fury.gpg"
            repo_list_path = "/etc/apt/sources.list.d/wezterm.list"
            
            # Use bash -c to ensure pipes and redirections run with root privileges
            setup_commands = [
                # 1. Download and dearmor GPG key
                f"bash -c 'curl -fsSL https://apt.fury.io/wez/gpg.key | gpg --yes --dearmor -o {keyring_path}'",
                # 2. Fix permissions for the keyring
                f"chmod 644 {keyring_path}",
                # 3. Add the repository to sources list
                f"bash -c 'echo \"deb [signed-by={keyring_path}] https://apt.fury.io/wez/ * *\" | tee {repo_list_path}'",
                # 4. Update apt cache
                "apt-get update"
            ]
            
            for command in setup_commands:
                if not self.system_manager.run(command, shell=True, needs_root=True, callback=callback, input_callback=input_callback, password=password):
                    return False
            
            # 5. Final installation via system manager
            return super().install(override, callback, input_callback, password)
            
        return False
