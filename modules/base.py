from core.system import System
import shutil
import os

class Module:
    """
    Base class for all installation modules.
    """
    # Unique identifier
    id = None
    # User-facing label
    label = None
    # Functional description
    description = ""
    category = "Uncategorized"
    dependencies = []
    
    # Supported drivers: 'system', 'cargo', 'bob', 'brew', 'git', 'wget'
    manager = "system"
    # Mapping for OS-specific package names
    package_name = None 
    
    # Stow configuration
    stow_target = "~"   

    def __init__(self, system_manager: System):
        self.system_manager = system_manager
        # Auto-resolve stow_pkg to match id
        self.stow_pkg = self.id

    def has_usable_dotfiles(self):
        """
        Recursively checks if the dotfiles directory exists and contains at least one file.
        """
        if not self.stow_pkg:
            return False
            
        pkg_path = os.path.join(os.getcwd(), "dots", self.stow_pkg)
        if not os.path.exists(pkg_path) or not os.path.isdir(pkg_path):
            return False
            
        for root, dirs, files in os.walk(pkg_path):
            if files:
                return True
        return False

    def get_package_name(self):
        """Resolves package name based on OS if a dict is provided."""
        if isinstance(self.package_name, dict):
            if self.system_manager.is_arch: return self.package_name.get("arch")
            if self.system_manager.is_debian: return self.package_name.get("debian")
        return self.package_name or self.id

    def get_manager(self):
        """Resolves the package manager based on OS or direct value."""
        if isinstance(self.manager, dict):
            if self.system_manager.is_arch: return self.manager.get("arch", "system")
            if self.system_manager.is_debian: return self.manager.get("debian", "system")
            return self.manager.get("default", "system")
        return self.manager or "system"

    def is_installed(self):
        """Detection logic based on the package manager type."""
        package = self.get_package_name()
        if self.manager == "system":
            return shutil.which(package or "") is not None
        elif self.manager == "cargo":
            return os.path.exists(os.path.expanduser(f"~/.cargo/bin/{self.id}"))
        elif self.manager == "brew":
            return shutil.which("brew") and self.system_manager.run(f"brew list {package}", shell=True)
        return False

    def install(self, override=None, callback=None, input_callback=None, password=None):
        """Generic installation logic supporting user overrides and real-time feedback."""
        package = override['package_name'] if override else self.get_package_name()
        manager = override['manager'] if override else self.get_manager()
        
        if not package and manager == "system": return True

        if manager == "system":
            return self.system_manager.install_package(package if self.system_manager.is_arch else None,
            package if self.system_manager.is_debian else None,
            callback=callback,
            input_callback=input_callback,
            password=password)
        elif manager == "cargo":
            return self.system_manager.run(f"cargo install {package}", shell=True, callback=callback, input_callback=input_callback)
        elif manager == "bob":
            return self.system_manager.run(f"bob use stable", shell=True, callback=callback, input_callback=input_callback)
        return True

    def configure(self, override=None, callback=None, input_callback=None, password=None):
        """Auto-stow if dotfiles directory exists, supporting user overrides."""
        if not self.stow_pkg:
            return True
            
        # Check if source directory exists before stowing to avoid errors
        pkg_path = os.path.join(os.getcwd(), "dots", self.stow_pkg)
        if not os.path.exists(pkg_path):
            return True # Nothing to stow, not an error
            
        return self.run_stow(self.stow_pkg, self.stow_target, callback=callback, input_callback=input_callback, password=password)

    def run_stow(self, package_name, target=None, callback=None, input_callback=None, password=None):
        """Standard GNU Stow wrapper."""
        dotfiles_dir = os.path.join(os.getcwd(), "dots")
        target_dir = os.path.expanduser(target or "~")
        
        if target and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        msg = f"Stowing {package_name} to {target_dir}..."
        if callback: callback(msg)
        else: print(f"[{self.id}] {msg}")

        try:
            cmd = ["stow", "--dir", dotfiles_dir, "--target", target_dir, "-R", package_name]
            return self.system_manager.run(cmd, callback=callback, input_callback=input_callback, password=password)
        except Exception as e:
            err = f"Error: {e}"
            if callback: callback(err)
            else: print(f"[{self.id}] {err}")
            return False

    def get_config_tree(self):
        """
        Recursively scans the dotfiles source directory to generate 
        a visual file tree.
        """
        if not self.stow_pkg:
            return []
            
        if not self.has_usable_dotfiles():
            return [f"No source files found in dots/{self.stow_pkg}"]
            
        pkg_path = os.path.join(os.getcwd(), "dots", self.stow_pkg)
        tree = []
        target = self.stow_target or "~/"
        tree.append(f"Target: {target}")
        tree.append("")
        
        def scan(path, prefix="", depth=0):
            # Enforce depth limit for UI stability
            if not os.path.isdir(path) or depth > 2:
                if depth > 2:
                    tree.append(f"{prefix}└── ...")
                return
            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                tree.append(f"{prefix}└── [Permission Denied]")
                return

            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                full_path = os.path.join(path, entry)
                
                connector = "└── " if is_last else "├── "
                tree.append(f"{prefix}{connector}{entry}")
                
                if os.path.isdir(full_path):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    scan(full_path, new_prefix, depth + 1)
                    
        scan(pkg_path)
        return tree
