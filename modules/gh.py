from modules.base import Module

class GitHubCLIModule(Module):
    id = "gh"
    label = "GitHub CLI"
    description = "GitHub's official command line tool"
    category = "Tools"
    
    package_name = {"arch": "github-cli", "ubuntu": "gh"}
    dependencies = {
        "arch": {
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "bin_deps": ["wget"],
            "dot_deps": ["stow"]
        }
    }

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian:
            if callback: callback("Setting up official GitHub CLI repository...")
            
            # Official setup commands for Debian/Ubuntu
            setup_commands = [
                "mkdir -p -m 755 /etc/apt/keyrings",
                "wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null",
                "chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg",
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null',
                "apt-get update",
                "apt-get install -y gh"
            ]
            
            for command in setup_commands:
                if not self.system_manager.run(command, shell=True, needs_root=True, callback=callback, input_callback=input_callback, password=password):
                    return False
            return True
        return False
