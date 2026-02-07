from modules.base import Module
import os
import subprocess

class RefindModule(Module):
    id = "refind"
    label = "rEFInd Boot Manager"
    description = "Boot manager with Catppuccin theme"
    category = "System Core"
    manager = "system"
    package_name = "refind"
    
    dependencies = {
        "default": {
            "bin_deps": ["gdisk"]
        }
    }
    
    # Package metadata
    stow_target = "/boot/EFI/refind"

    def is_installed(self):
        """Checks for rEFInd configuration in the EFI partition."""
        return os.path.exists("/boot/EFI/refind/refind.conf")

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        """Performs custom rEFInd deployment, including theme installation and PARTUUID resolution."""
        message = "Executing custom configuration sequence..."
        if callback: callback(message)
        else: print(f"[refind] {message}")
        
        repo_root = os.getcwd()
        theme_source = os.path.join(repo_root, "dots", "refind", "themes")
        conf_template = os.path.join(repo_root, "dots", "refind", "refind.conf")
        efi_base = "/boot/EFI/refind"
        theme_dest = os.path.join(efi_base, "themes")
        conf_dest = os.path.join(efi_base, "refind.conf")

        # Core installation via system tools
        if not os.path.exists(efi_base):
            self.system_manager.run("refind-install", needs_root=True, callback=callback, input_callback=input_callback, password=password)
 
        # Config generation and deployment
        try:
            root_device = subprocess.check_output("findmnt -n -o SOURCE /", shell=True, text=True).strip()
            root_partuuid = subprocess.check_output(f"lsblk -no PARTUUID {root_device}", shell=True, text=True).strip()
            
            with open(conf_template, 'r') as config_file:
                config_content = config_file.read().replace("__ROOT_PARTUUID__", root_partuuid)
            
            tmp_conf = "/tmp/refind.conf.generated"
            with open(tmp_conf, 'w') as temporary_config: 
                temporary_config.write(config_content)
            
            self.system_manager.run(f"mv {tmp_conf} {conf_dest}", needs_root=True, shell=True, callback=callback, input_callback=input_callback, password=password)
        except Exception as error:
            error_message = f"Error config: {error}"
            if callback: callback(error_message)
            else: print(f"[refind] {error_message}")
 
        # 3. Copy Themes
        if os.path.exists(theme_source):
            self.system_manager.run(f"rm -rf {theme_dest}", needs_root=True, shell=True, callback=callback, input_callback=input_callback, password=password)
            return self.system_manager.run(f"cp -r {theme_source} {theme_dest}", needs_root=True, shell=True, callback=callback, input_callback=input_callback, password=password)
        return True
