from modules.base import Module
import os
import shutil

class LazygitModule(Module):
    id = "lazygit"
    label = "Lazygit"
    description = "A simple terminal UI for git commands"
    category = "Tools"
    
    # On Arch we use pacman; on Ubuntu we use a custom binary installer
    manager = {
        "arch": "system",
        "ubuntu": "wget" # We use wget/curl to fetch the binary
    }
    
    package_name = "lazygit"
    
    dependencies = {
        "arch": [],
        "ubuntu": ["curl", "git", "unzip"]
    }

    def install(self, override=None, callback=None, input_callback=None, password=None):
        if self.system_manager.is_arch:
            return super().install(override, callback, input_callback, password)
            
        if self.system_manager.is_debian:
            if callback: callback("Fetching latest Lazygit version from GitHub...")
            
            # 1. Get latest version download URL
            # Using grep -i to be case-insensitive and handle version strings in the filename
            api_url = "https://api.github.com/repos/jesseduffield/lazygit/releases/latest"
            get_url_cmd = f"curl -s {api_url} | grep -i 'browser_download_url.*linux_x86_64.tar.gz' | cut -d '\"' -f 4"
            
            # Using a temporary file to capture the URL
            import subprocess
            try:
                download_url = subprocess.check_output(get_url_cmd, shell=True, text=True).strip()
            except Exception as error:
                if callback: callback(f"Error fetching version: {error}")
                return False

            if not download_url:
                if callback: callback("Could not find download URL for your architecture.")
                return False

            # 2. Download and Extract
            temp_dir = "/tmp/lazygit_install"
            os.makedirs(temp_dir, exist_ok=True)
            tar_path = os.path.join(temp_dir, "lazygit.tar.gz")
            
            if callback: callback(f"Downloading Lazygit from {download_url}...")
            download_cmd = f"curl -Lo {tar_path} {download_url}"
            if not self.system_manager.run(download_cmd, shell=True, callback=callback, input_callback=input_callback):
                return False
                
            if callback: callback("Extracting binary...")
            extract_cmd = f"tar -C {temp_dir} -xzf {tar_path} lazygit"
            if not self.system_manager.run(extract_cmd, shell=True, callback=callback, input_callback=input_callback):
                return False

            # 3. Move to /usr/local/bin
            if callback: callback("Installing binary to /usr/local/bin...")
            install_cmd = ["install", os.path.join(temp_dir, 'lazygit'), "/usr/local/bin/lazygit"]
            
            success = self.system_manager.run(install_cmd, needs_root=True, callback=callback, input_callback=input_callback, password=password)
            
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return success
            
        return False
