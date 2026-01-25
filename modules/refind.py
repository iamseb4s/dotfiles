from modules.base import Module
import os
import subprocess

class RefindModule(Module):
    id = "refind"
    label = "rEFInd Boot Manager"
    description = "Boot manager with Catppuccin theme"
    category = "System Core"
    manager = "system"
    package_name = "refind gdisk"
    
    # Package metadata
    stow_pkg = "refind"
    stow_target = "/boot/EFI/refind"

    def is_installed(self):
        """Checks for rEFInd configuration in the EFI partition."""
        return os.path.exists("/boot/EFI/refind/refind.conf")

    def configure(self):
        """Performs custom rEFInd deployment, including theme installation and PARTUUID resolution."""
        print("[refind] Executing custom configuration sequence...")
        repo_root = os.getcwd()
        theme_source = os.path.join(repo_root, "dots", "refind", "themes")
        conf_template = os.path.join(repo_root, "dots", "refind", "refind.conf")
        efi_base = "/boot/EFI/refind"
        theme_dest = os.path.join(efi_base, "themes")
        conf_dest = os.path.join(efi_base, "refind.conf")

        # Core installation via system tools
        if not os.path.exists(efi_base):
            self.sys.run("refind-install", needs_root=True)

        # Config generation and deployment
        try:
            root_dev = subprocess.check_output("findmnt -n -o SOURCE /", shell=True, text=True).strip()
            root_partuuid = subprocess.check_output(f"lsblk -no PARTUUID {root_dev}", shell=True, text=True).strip()
            
            with open(conf_template, 'r') as f:
                config_content = f.read().replace("__ROOT_PARTUUID__", root_partuuid)
            
            tmp_conf = "/tmp/refind.conf.generated"
            with open(tmp_conf, 'w') as f: f.write(config_content)
            
            self.sys.run(f"mv {tmp_conf} {conf_dest}", needs_root=True, shell=True)
        except Exception as e:
            print(f"[refind] Error config: {e}")

        # 3. Copy Themes
        if os.path.exists(theme_source):
            self.sys.run(f"rm -rf {theme_dest}", needs_root=True, shell=True)
            self.sys.run(f"cp -r {theme_source} {theme_dest}", needs_root=True, shell=True)
