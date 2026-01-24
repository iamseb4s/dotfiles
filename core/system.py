import subprocess
import os
import sys

class System:
    """
    Handles OS detection and command execution.
    """
    def __init__(self):
        self.os_id = self._detect_os()
        self.is_arch = self.os_id in ["arch", "manjaro", "endeavouros"]
        self.is_debian = self.os_id in ["ubuntu", "debian", "pop", "linuxmint"]

    def _detect_os(self):
        """Read /etc/os-release to identify the distro."""
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        return line.strip().split("=")[1].strip('"')
        except FileNotFoundError:
            return "unknown"
        return "unknown"

    def get_os_pretty_name(self):
        """Returns the PRETTY_NAME from os-release or falls back to ID."""
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.strip().split("=")[1].strip('"')
        except FileNotFoundError:
            pass
        return self.os_id.capitalize()

    def run(self, command, needs_root=False, shell=False):
        """
        Executes a shell command.
        :param command: List of strings (['ls', '-l']) or string ('ls -l') if shell=True
        :param needs_root: If True, prepends 'sudo' if not running as root.
        """
        if needs_root and os.geteuid() != 0:
            if isinstance(command, list):
                command.insert(0, "sudo")
            else:
                command = "sudo " + command
        
        try:
            # We use check=True to raise exception on failure
            subprocess.run(command, shell=shell, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\nError executing command: {command}\n{e}")
            return False

    def install_package(self, package_name_arch, package_name_debian):
        """Abstracts package installation based on detected OS."""
        if self.is_arch:
            if not package_name_arch: return True # Nothing to install
            print(f"Installing {package_name_arch} via pacman...")
            return self.run(["pacman", "-S", "--noconfirm", "--needed"] + package_name_arch.split(), needs_root=True)
        
        elif self.is_debian:
            if not package_name_debian: return True
            print(f"Installing {package_name_debian} via apt...")
            return self.run(["apt-get", "install", "-y"] + package_name_debian.split(), needs_root=True)
        
        else:
            print(f"OS {self.os_id} not supported for package installation.")
            return False
