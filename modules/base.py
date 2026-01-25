from core.system import System
import shutil
import os

class Module:
    """
    Base class for all modules. Designed to be data-driven.
    """
    # Override these in child classes
    id = None
    label = None
    description = ""
    category = "Uncategorized"
    dependencies = []
    
    # Package Management: 'system', 'cargo', 'bob', 'brew', 'git', 'wget'
    manager = "system"
    package_name = None 
    
    # Dotfiles Configuration
    stow_pkg = None      
    stow_target = None   

    def __init__(self, sys_manager: System):
        self.sys = sys_manager

    def get_package_name(self):
        """Resolves package name based on OS if a dict is provided."""
        if isinstance(self.package_name, dict):
            if self.sys.is_arch: return self.package_name.get("arch")
            if self.sys.is_debian: return self.package_name.get("debian")
        return self.package_name or self.id

    def is_installed(self):
        """Generic installation check."""
        pkg = self.get_package_name()
        if self.manager == "system":
            return shutil.which(pkg) is not None
        elif self.manager == "cargo":
            return os.path.exists(os.path.expanduser(f"~/.cargo/bin/{self.id}"))
        elif self.manager == "brew":
            return shutil.which("brew") and self.sys.run(f"brew list {pkg}", shell=True)
        return False

    def install(self):
        """Generic installation logic."""
        pkg = self.get_package_name()
        if not pkg and self.manager == "system": return True

        if self.manager == "system":
            return self.sys.install_package(pkg if self.sys.is_arch else None, 
                                          pkg if self.sys.is_debian else None)
        elif self.manager == "cargo":
            return self.sys.run(f"cargo install {pkg}", shell=True)
        elif self.manager == "bob":
            return self.sys.run(f"bob use stable", shell=True)
        return True

    def configure(self):
        """Auto-stow if stow_pkg is defined."""
        if self.stow_pkg:
            self.run_stow(self.stow_pkg, self.stow_target)

    def run_stow(self, package_name, target=None):
        """Standard GNU Stow wrapper."""
        dotfiles_dir = os.path.join(os.getcwd(), "dots")
        target_dir = os.path.expanduser(target or "~")
        
        if target and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        print(f"[{self.id}] Stowing {package_name} to {target_dir}...")
        try:
            cmd = ["stow", "--dir", dotfiles_dir, "--target", target_dir, "-R", package_name]
            return self.sys.run(cmd)
        except Exception as e:
            print(f"[{self.id}] Error: {e}")
            return False
