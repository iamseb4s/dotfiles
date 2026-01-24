from modules.base import Module
import os

class RefindModule(Module):
    @property
    def id(self):
        return "refind"
    
    @property
    def label(self):
        return "rEFInd Boot Manager (with Catppuccin Theme)"

    @property
    def category(self):
        return "System Core"

    def install(self):
        # 1. Install System Packages
        # Arch: refind, gdisk
        # Ubuntu: refind, gdisk (usually available)
        if not self.sys.install_package("refind gdisk", "refind gdisk"):
            return False
        
        # 2. Run refind-install
        print("[refind] Running 'refind-install' (Requires Root)...")
        # We need to detect if we are in a chroot/container to avoid errors, 
        # but for now we assume a real run or the user knows.
        try:
            self.sys.run("refind-install", needs_root=True)
        except Exception:
            print("[refind] refind-install failed. Skipping configuration.")
            return False
        return True

    def configure(self):
        # rEFInd config logic is special (Copy, don't Stow)
        print("[refind] Configuring rEFInd...")
        
        # Paths
        repo_root = os.getcwd()
        theme_source = os.path.join(repo_root, "dots", "refind", "themes")
        conf_template = os.path.join(repo_root, "dots", "refind", "refind.conf")
        
        # Destination Paths (Standard EFI mount point)
        # TODO: Auto-detect EFI partition path if it's not /boot/EFI
        efi_base = "/boot/EFI/refind"
        theme_dest = os.path.join(efi_base, "themes")
        conf_dest = os.path.join(efi_base, "refind.conf")
        
        if not os.path.exists(efi_base):
            print(f"[refind] Error: {efi_base} not found. Is rEFInd installed?")
            return

        # 1. Get Root Partition UUID for the config
        # Getting the partition UUID where / is mounted
        try:
            # Equivalent to: findmnt -n -o SOURCE /
            # Then lsblk -no PARTUUID device
            # This is a bit complex in pure Python without root, 
            # so we'll use subprocess to be safe and leverage existing tools.
            root_dev_cmd = subprocess.run("findmnt -n -o SOURCE /", shell=True, capture_output=True, text=True)
            root_dev = root_dev_cmd.stdout.strip()
            
            uuid_cmd = subprocess.run(f"lsblk -no PARTUUID {root_dev}", shell=True, capture_output=True, text=True)
            root_partuuid = uuid_cmd.stdout.strip()
            
            if not root_partuuid:
                print("[refind] Could not detect root PARTUUID. Skipping config generation.")
                return

            print(f"[refind] Detected Root PARTUUID: {root_partuuid}")
            
            # Read template
            with open(conf_template, 'r') as f:
                config_content = f.read()
            
            # Replace placeholder
            final_config = config_content.replace("__ROOT_PARTUUID__", root_partuuid)
            
            # Write to temporary file then move with sudo
            tmp_conf = "/tmp/refind.conf.generated"
            with open(tmp_conf, 'w') as f:
                f.write(final_config)
            
            # Move config
            self.sys.run(f"mv {tmp_conf} {conf_dest}", needs_root=True, shell=True)
            print("[refind] Configuration updated.")

        except Exception as e:
            print(f"[refind] Error generating config: {e}")

        # 2. Copy Themes
        if os.path.exists(theme_source):
            print("[refind] Installing themes...")
            # Remove existing themes folder to ensure clean state
            if os.path.exists(theme_dest) or os.path.isdir(theme_dest): # Check if dest exists (as root dir)
                 self.sys.run(f"rm -rf {theme_dest}", needs_root=True, shell=True)
            
            # Copy recursively
            self.sys.run(f"cp -r {theme_source} {theme_dest}", needs_root=True, shell=True)
            print("[refind] Themes installed successfully.")
        else:
            print(f"[refind] Warning: Theme source {theme_source} not found.")

import subprocess # Need this import for the UUID logic
