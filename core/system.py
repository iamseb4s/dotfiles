import subprocess
import os
import sys
import select

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

    def run(self, command, needs_root=False, shell=False, callback=None, input_callback=None):
        """
        Executes a shell command with real-time output and keyboard monitoring.
        :param callback: Function to receive output lines.
        :param input_callback: Function to check for keyboard input.
        """
        from core.tui import TUI
        
        if needs_root and os.getuid() != 0:
            if isinstance(command, list):
                if command[0] != "sudo":
                    command.insert(0, "sudo")
            else:
                if not command.startswith("sudo"):
                    command = "sudo " + command
        
        try:
            if callback:
                process = subprocess.Popen(
                    command, 
                    shell=shell, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True,
                    bufsize=0, # Unbuffered for real-time
                    universal_newlines=True
                )
                
                TUI.set_raw_mode(enable=True)
                output_buffer = ""
                try:
                    while True:
                        finished = process.poll() is not None
                        
                        # Monitor process and keyboard via select
                        readable, _, _ = select.select([process.stdout, sys.stdin], [], [], 0.05)
                        
                        for source in readable:
                            if source == process.stdout:
                                try:
                                    # Use direct OS read to bypass Python buffering
                                    chunk = os.read(process.stdout.fileno(), 4096).decode('utf-8', errors='ignore')
                                    if chunk:
                                        lines = (output_buffer + chunk).split('\n')
                                        output_buffer = lines.pop()
                                        for line in lines:
                                            callback(line.rstrip())
                                except (OSError, EOFError):
                                    pass
                            elif source == sys.stdin:
                                if input_callback:
                                    input_callback()
                                    # Force a UI refresh even if no new log line arrived
                                    if callback: callback(None)
                        
                        if finished:
                            if output_buffer: callback(output_buffer.rstrip())
                            break
                finally:
                    TUI.set_raw_mode(enable=False)
                
                return process.returncode == 0

            else:
                subprocess.run(command, shell=shell, check=True)
                return True

        except (subprocess.CalledProcessError, Exception) as e:
            if not callback:
                print(f"\nError executing command: {command}\n{e}")
            else:
                callback(f"ERROR: {str(e)}")
            return False

    def install_package(self, package_name_arch, package_name_debian, callback=None, input_callback=None):
        """Abstracts package installation based on detected OS."""
        if self.is_arch:
            if not package_name_arch: return True
            return self.run(["pacman", "-S", "--noconfirm", "--needed"] + package_name_arch.split(), 
                           needs_root=True, callback=callback, input_callback=input_callback)
        
        elif self.is_debian:
            if not package_name_debian: return True
            self.run(["apt-get", "update"], needs_root=True, callback=callback, input_callback=input_callback)
            return self.run(["apt-get", "install", "-y"] + package_name_debian.split(), 
                           needs_root=True, callback=callback, input_callback=input_callback)
        
        else:
            print(f"OS {self.os_id} not supported for package installation.")
            return False
