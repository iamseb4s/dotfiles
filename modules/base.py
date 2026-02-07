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
    # Optional mapping for binary names (string or list) to improve detection
    binary_names = None
    
    # Stow configuration
    stow_target = "~"   
    
    # Hierarchical sub-components
    sub_components = []

    def __init__(self, system_manager: System):
        self.system_manager = system_manager
        # Auto-resolve stow_package to match module id
        self.stow_package = self.id
        self._cache = {}

    def clear_cache(self):
        """Clears all memoized results."""
        self._cache = {}

    def has_usable_dotfiles(self):
        """
        Recursively checks if the dotfiles directory exists and contains at least one file.
        """
        if "has_dotfiles" in self._cache:
            return self._cache["has_dotfiles"]
            
        if not self.stow_package:
            self._cache["has_dotfiles"] = False
            return False
            
        package_path = os.path.join(os.getcwd(), "dots", self.stow_package)
        if not os.path.exists(package_path) or not os.path.isdir(package_path):
            self._cache["has_dotfiles"] = False
            return False
            
        for root, dirs, files in os.walk(package_path):
            if files:
                self._cache["has_dotfiles"] = True
                return True
        
        self._cache["has_dotfiles"] = False
        return False

    def _resolve_distro_value(self, value, default=None):
        """
        Generic helper to resolve values from a dictionary based on distribution.
        """
        if value is None:
            return default

        if not isinstance(value, dict):
            return value

        # 1. Specific OS ID (e.g., 'ubuntu', 'manjaro')
        if self.system_manager.os_id in value:
            return value[self.system_manager.os_id]
        
        # 2. Family ID ('arch' or 'debian')
        if self.system_manager.is_arch and "arch" in value:
            return value["arch"]
        if self.system_manager.is_debian and "debian" in value:
            return value["debian"]
            
        # 3. Default fallback
        return value.get("default", default)

    def get_package_name(self):
        """Resolves package name based on OS if a dict is provided."""
        return self._resolve_distro_value(self.package_name, default=self.id)

    def get_binary_names(self):
        """
        Resolves the list of possible binary names for detection.
        Returns a list of strings.
        """
        resolved_names = self._resolve_distro_value(self.binary_names)
        
        # 1. Handle case where binary_names is explicitly defined
        if resolved_names:
            if isinstance(resolved_names, list):
                return resolved_names
            return [resolved_names]
            
        # 2. Fallback to package_name
        package_name = self.get_package_name()
        # We take the first part as a heuristic for the main executable
        if package_name:
            main_name = package_name.split()[0]
            return [main_name]
            
        return [self.id]

    def get_dependencies(self):
        """Resolves dependencies based on OS if a dict is provided."""
        return self._resolve_distro_value(self.dependencies, default=[])

    def get_flat_dependencies(self):
        """Returns a flattened list of all dependency IDs for the current distribution."""
        resolved = self.get_dependencies()
        if isinstance(resolved, dict):
            flattened = []
            for value in resolved.values():
                if isinstance(value, list):
                    flattened.extend(value)
            return list(set(flattened))
        return resolved if isinstance(resolved, list) else []

    def get_component_dependencies(self, component_id):
        """
        Resolves dependencies for a specific sub-component, binary, or dotfiles.
        """
        # 1. Handle primary components
        if component_id == "binary":
            resolved_deps = self.get_dependencies()
            # Support granular dictionary format: {"bin_deps": [...], "dot_deps": [...]}
            if isinstance(resolved_deps, dict):
                return resolved_deps.get("bin_deps", [])
            return resolved_deps

        if component_id == "dotfiles":
            resolved_deps = self.get_dependencies()
            dot_deps = []
            if isinstance(resolved_deps, dict):
                dot_deps.extend(resolved_deps.get("dot_deps", []))
            return list(set(dot_deps))

        # 2. Handle sub-components defined in self.sub_components
        def find_component(components):
            for component in components:
                if component.get("id") == component_id:
                    return component
                if "children" in component:
                    found = find_component(component["children"])
                    if found: return found
            return None

        component = find_component(self.sub_components)
        if component and "dependencies" in component:
            return self._resolve_distro_value(component["dependencies"], default=[])

        return []

    def get_manager(self):
        """Resolves the package manager based on OS or direct value."""
        return self._resolve_distro_value(self.manager, default="system")

    def is_supported(self):
        """
        Determines if the module is supported on the current distribution.
        Checks both package_name and manager dictionaries.
        """
        # 1. Check package_name mapping
        if isinstance(self.package_name, dict):
            has_specific = self.system_manager.os_id in self.package_name
            has_family = (self.system_manager.is_arch and "arch" in self.package_name) or (self.system_manager.is_debian and "debian" in self.package_name)
            if not has_specific and not has_family:
                return False
        
        # 2. Check manager mapping
        if isinstance(self.manager, dict):
            has_specific = self.system_manager.os_id in self.manager
            has_family = (self.system_manager.is_arch and "arch" in self.manager) or (self.system_manager.is_debian and "debian" in self.manager)
            has_default = "default" in self.manager
            if not has_specific and not has_family and not has_default:
                return False
            
        return True

    def get_supported_distros(self):
        """Returns a string list of supported distributions."""
        supported_distributions = []
        
        # Combine keys from all relevant dictionaries
        all_keys = set()
        if isinstance(self.package_name, dict): all_keys.update(self.package_name.keys())
        if isinstance(self.manager, dict): all_keys.update(self.manager.keys())
        if isinstance(self.dependencies, dict): all_keys.update(self.dependencies.keys())
        
        if not all_keys:
            return "All Distros"
            
        if "arch" in all_keys: supported_distributions.append("Arch Linux")
        if "debian" in all_keys: supported_distributions.append("Debian/Ubuntu")
        
        # Add specific ones if they are not already covered by family names (simple heuristic)
        for key in sorted(all_keys):
            if key in ["arch", "debian", "default"]: continue
            pretty_name = key.capitalize()
            if pretty_name not in supported_distributions:
                supported_distributions.append(pretty_name)
        
        if "default" in all_keys and not supported_distributions:
            return "All Distros"
            
        return ", ".join(supported_distributions) if supported_distributions else "All Distros"

    def is_installed(self):
        """Detection logic based on the package manager type."""
        if "is_installed" in self._cache:
            return self._cache["is_installed"]

        package = self.get_package_name()
        manager = self.get_manager()
        
        result = False
        # 1. Manager-specific detection
        if manager == "system":
            # Try robust OS package manager detection
            if self.system_manager.is_package_installed(package):
                result = True
        elif manager == "cargo":
            result = os.path.exists(os.path.expanduser(f"~/.cargo/bin/{self.id}"))
        elif manager == "bob":
            result = shutil.which("nvim") is not None
        elif manager == "brew":
            result = shutil.which("brew") and self.system_manager.run(f"brew list {package}", shell=True)
        
        # 2. Universal PATH fallback
        if not result:
            for binary_name in self.get_binary_names():
                if shutil.which(binary_name) is not None:
                    result = True
                    break
        
        self._cache["is_installed"] = result
        return result

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
        Recursively scans the dotfiles source directory to generate a visual file tree.
        """
        cache_key = f"tree_{target}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.stow_package:
            return []
            
        if not self.has_usable_dotfiles():
            result = [f"No source files found in dots/{self.stow_package}"]
            self._cache[cache_key] = result
            return result
            
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
            except FileNotFoundError:
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
        self._cache[cache_key] = tree
        return tree
