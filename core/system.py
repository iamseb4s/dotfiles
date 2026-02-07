import subprocess
import os
import sys
import select
import shlex

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

    def run(self, command, needs_root=False, shell=False, callback=None, input_callback=None, password=None):
        """
        Executes a shell command with real-time output and keyboard monitoring.
        :param callback: Function to receive output lines.
        :param input_callback: Function to check for keyboard input.
        :param password: Optional password for sudo -S.
        """
        from core.tui import TUI
        
        if needs_root and os.getuid() != 0:
            sudo_prefix = ["sudo", "-S"] if password else ["sudo"]
            if isinstance(command, list):
                if command[0] == "sudo":
                    if password and "-S" not in command:
                        command.insert(1, "-S")
                elif password:
                    command = ["sudo", "-S"] + command
                else:
                    command = ["sudo"] + command
            else:
                if not command.startswith("sudo"):
                    command = (" ".join(sudo_prefix)) + " " + command
                elif password and "sudo -S" not in command:
                    command = command.replace("sudo", "sudo -S", 1)
        
        # If command is a string and shell=False, we must split it to avoid [Errno 2]
        if isinstance(command, str) and not shell:
            command = shlex.split(command)

        try:
            if callback:
                # Use binary mode to avoid TextIOWrapper buffering issues
                process = subprocess.Popen(
                    command, 
                    shell=shell, 
                    stdin=subprocess.PIPE if password else None,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=False,
                    bufsize=0
                )
                
                if password and process.stdin:
                    process.stdin.write(f"{password}\n".encode())
                    process.stdin.flush()
                
                TUI.set_raw_mode(enable=True)
                output_buffer = b""
                try:
                    while True:
                        finished = process.poll() is not None
                        
                        # Monitor process and keyboard via select
                        try:
                            readable, _, _ = select.select([process.stdout, sys.stdin], [], [], 0.02)
                        except (select.error, InterruptedError):
                            # Handle terminal resize (SIGWINCH) or other interrupts
                            if input_callback: input_callback()
                            continue
                        
                        for source in readable:
                            if source == process.stdout and process.stdout:
                                try:
                                    # Direct binary read
                                    chunk = os.read(process.stdout.fileno(), 4096)
                                    if chunk:
                                        # Process both \n and \r to prevent terminal cursor jumps
                                        raw_content = output_buffer + chunk
                                        lines = raw_content.replace(b'\r', b'\n').split(b'\n')
                                        output_buffer = lines.pop()
                                        for line in lines:
                                            content = line.decode('utf-8', errors='ignore').rstrip()
                                            if content:
                                                callback(content)
                                except (OSError, EOFError):
                                    pass
                            elif source == sys.stdin:
                                if input_callback:
                                    input_callback()
                        
                        if finished:
                            # Final flush of output
                            remaining = output_buffer.decode('utf-8', errors='ignore').strip()
                            if remaining: callback(remaining)
                            
                            # CRITICAL: Check if there's pending input one last time 
                            # before returning, to avoid leaking keys to the next screen.
                            ready_to_read, _, _ = select.select([sys.stdin], [], [], 0.01)
                            if ready_to_read and input_callback:
                                input_callback()
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

    def install_package(self, package_name_arch, package_name_debian, callback=None, input_callback=None, password=None):
        """Abstracts package installation based on detected OS."""
        if self.is_arch:
            if not package_name_arch: return True
            return self.run(["pacman", "-S", "--noconfirm", "--needed"] + package_name_arch.split(), 
                           needs_root=True, callback=callback, input_callback=input_callback, password=password)
        
        elif self.is_debian:
            if not package_name_debian: return True
            self.run(["apt-get", "update"], needs_root=True, callback=callback, input_callback=input_callback, password=password)
            return self.run(["apt-get", "install", "-y"] + package_name_debian.split(), 
                           needs_root=True, callback=callback, input_callback=input_callback, password=password)
        
        else:
            print(f"OS {self.os_id} not supported for package installation.")
            return False

    def is_package_installed(self, package_name):
        """Checks if a system package is installed using the OS package manager."""
        if not package_name: return False
        
        try:
            if self.is_arch:
                # pacman -Qq returns 0 if installed, 1 if not
                result = subprocess.run(["pacman", "-Qq", package_name], 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return result.returncode == 0
            
            elif self.is_debian:
                # dpkg -s returns detailed status. We check for 'install ok installed'
                result = subprocess.run(["dpkg", "-s", package_name], 
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                for line in result.stdout.splitlines():
                    if line.startswith("Status:"):
                        return "ok installed" in line
        except:
            return False
            
        return False
