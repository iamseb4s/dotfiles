from modules.base import Module

class FastfetchModule(Module):
    id = "fastfetch"
    label = "Fastfetch"
    description = "A maintained, feature-rich and performance oriented, system information tool"
    category = "Tools"
    
    package_name = {
        "arch": "fastfetch",
        "ubuntu": "fastfetch"
    }

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian:
            if callback: callback("Setting up Fastfetch PPA...")
            # PPA is the best way to get latest fastfetch on Ubuntu
            setup_cmds = [
                "add-apt-repository -y ppa:zhangsongcui3371/fastfetch",
                "apt-get update",
                "apt-get install -y fastfetch"
            ]
            for cmd in setup_cmds:
                if not self.system_manager.run(cmd, shell=True, needs_root=True, callback=callback, input_callback=input_callback, password=password):
                    return False
            return True
        return False
