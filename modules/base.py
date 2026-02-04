from core.system import System
from core.tui import Style
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
    
    # Hierarchical sub-components
    sub_components = []

    def __init__(self, system_manager: System):
        self.system_manager = system_manager
        # Auto-resolve stow_package to match module id
        self.stow_package = self.id

    def has_usable_dotfiles(self):
        """
        Recursively checks if the dotfiles directory exists and contains at least one file.
        """
        if not self.stow_package:
            return False
            
        package_path = os.path.join(os.getcwd(), "dots", self.stow_package)
        if not os.path.exists(package_path) or not os.path.isdir(package_path):
            return False
            
        for root, dirs, files in os.walk(package_path):
            if files:
                return True
        return False

    def get_package_name(self):
        """Resolves package name based on OS if a dict is provided."""
        if isinstance(self.package_name, dict):
            if self.system_manager.is_arch: return self.package_name.get("arch")
            if self.system_manager.is_debian: return self.package_name.get("debian")
        return self.package_name or self.id

    def get_dependencies(self):
        """Resolves dependencies based on OS if a dict is provided."""
        if isinstance(self.dependencies, dict):
            if self.system_manager.is_arch: 
                return self.dependencies.get("arch", self.dependencies.get("default", []))
            if self.system_manager.is_debian: 
                return self.dependencies.get("debian", self.dependencies.get("default", []))
            return self.dependencies.get("default", [])
        return self.dependencies or []

    def get_manager(self):
        """Resolves the package manager based on OS or direct value."""
        if isinstance(self.manager, dict):
            if self.system_manager.is_arch: return self.manager.get("arch", "system")
            if self.system_manager.is_debian: return self.manager.get("debian", "system")
            return self.manager.get("default", "system")
        return self.manager or "system"

    def is_supported(self):
        """
        Determines if the module is supported on the current distribution.
        Checks both package_name and manager dictionaries.
        """
        # 1. Check package_name mapping
        if isinstance(self.package_name, dict):
            if self.system_manager.is_arch and "arch" not in self.package_name: return False
            if self.system_manager.is_debian and "debian" not in self.package_name: return False
        
        # 2. Check manager mapping
        if isinstance(self.manager, dict):
            if self.system_manager.is_arch and "arch" not in self.manager and "default" not in self.manager: return False
            if self.system_manager.is_debian and "debian" not in self.manager and "default" not in self.manager: return False
            
        return True

    def get_supported_distros(self):
        """Returns a string list of supported distributions."""
        supported_distributions = []
        if isinstance(self.package_name, dict):
            if "arch" in self.package_name: supported_distributions.append("Arch Linux")
            if "debian" in self.package_name: supported_distributions.append("Debian/Ubuntu")
        elif isinstance(self.manager, dict):
            if "arch" in self.manager: supported_distributions.append("Arch Linux")
            if "debian" in self.manager: supported_distributions.append("Debian/Ubuntu")
            if "default" in self.manager and len(supported_distributions) == 0: return "All Distros"
        else:
            return "All Distros"
            
        return ", ".join(supported_distributions) if supported_distributions else "All Distros"

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
        """Generic installation logic supporting modular user selections."""
        # Check sub-selections for binary installation (id: 'binary')
        sub_selections = override.get('sub_selections', {}) if override else {}
        if not sub_selections.get('binary', True):
            if callback: callback(f"Skipping {self.label} package installation as requested...")
            return True

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
        """Auto-stow if dotfiles directory exists, supporting modular user selections."""
        if not self.stow_package:
            return True

        # Check sub-selections for dotfiles deployment (id: 'dotfiles')
        sub_selections = override.get('sub_selections', {}) if override else {}
        if not sub_selections.get('dotfiles', True):
            if callback: callback("Skipping configuration deployment...")
            return True
            
        # Check if source directory exists before stowing to avoid errors
        package_path = os.path.join(os.getcwd(), "dots", self.stow_package)
        if not os.path.exists(package_path):
            return True # Nothing to stow, not an error
            
        return self.run_stow(self.stow_package, self.stow_target, callback=callback, input_callback=input_callback, password=password)

    def run_stow(self, package_name, target=None, callback=None, input_callback=None, password=None):
        """Standard GNU Stow wrapper with cleanup of existing files."""
        dotfiles_directory = os.path.join(os.getcwd(), "dots")
        package_source_directory = os.path.join(dotfiles_directory, package_name)
        target_directory = os.path.expanduser(target or "~")
        
        if not os.path.exists(package_source_directory):
            return True

        if not os.path.exists(target_directory):
            os.makedirs(target_directory, exist_ok=True)

        # Cleanup: Remove existing files/dirs or broken symlinks that would cause Stow conflicts
        try:
            for entry in os.listdir(package_source_directory):
                target_path = os.path.join(target_directory, entry)
                if os.path.lexists(target_path) and (not os.path.islink(target_path) or not os.path.exists(target_path)):
                    if callback: callback(f"Cleaning up existing {entry} in target...")
                    if os.path.isdir(target_path) and not os.path.islink(target_path):
                        shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)
        except Exception as error:
            if callback: callback(f"Cleanup warning: {error}")

        message = f"Stowing {package_name} to {target_directory}..."
        if callback: callback(message)
        else: print(f"[{self.id}] {message}")

        try:
            command = ["stow", "--dir", dotfiles_directory, "--target", target_directory, "-R", package_name]
            return self.system_manager.run(command, callback=callback, input_callback=input_callback, password=password)
        except Exception as error:
            error_message = f"Error: {error}"
            if callback: callback(error_message)
            else: print(f"[{self.id}] {error_message}")
            return False

    def get_config_tree(self, target=None):
        """
        Recursively scans the dotfiles source directory to generate 
        a visual file tree.
        """
        if not self.stow_package:
            return []
            
        if not self.has_usable_dotfiles():
            return [f"No source files found in dots/{self.stow_package}"]
            
        package_path = os.path.join(os.getcwd(), "dots", self.stow_package)
        tree = []
        # Add extra spacing before tree info
        tree.append("")
        
        is_supported = self.is_supported()
        label_style = Style.normal() if is_supported else Style.muted()
        value_style = Style.secondary() if is_supported else Style.muted()
        
        display_target = target or self.stow_target or "~/"
        tree.append(f"{label_style}Target:  {value_style}{display_target}{Style.RESET}")
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
                tree.append(f"{value_style}{prefix}{connector}{entry}{Style.RESET}")
                
                if os.path.isdir(full_path):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    scan(full_path, new_prefix, depth + 1)
                    
        scan(package_path)
        return tree
