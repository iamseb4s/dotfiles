import sys
import termios
import tty
import os
import time

class Keys:
    UP = 65
    DOWN = 66
    RIGHT = 67
    LEFT = 68
    SPACE = 32
    ENTER = 13
    ESC = 27
    TAB = 9
    BACKSPACE = 127
    # Vim keys
    K = 107 # Up
    J = 106 # Down
    H = 104 # Collapse/Left
    L = 108 # Expand/Right
    Q = 113 # q
    R = 114 # Refresh/Back

class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    INVERT = "\033[7m"

    @staticmethod
    def hex(hex_color, bg=False):
        """Converts HEX to ANSI TrueColor."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            layer = 48 if bg else 38
            return f"\033[{layer};2;{r};{g};{b}m"
        except ValueError:
            return ""

class TUI:
    """
    Advanced Terminal User Interface with State Management.
    """
    
    @staticmethod
    def get_key():
        """Reads a single keypress from stdin."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch_bytes = os.read(fd, 1)
            if not ch_bytes: return None
            ch = ch_bytes.decode('utf-8', errors='ignore')
            
            if ch == '\x1b':  # ESC sequence
                import select
                # Wait up to 0.2s to distinguish single ESC from escape sequences
                r, w, x = select.select([fd], [], [], 0.2)
                if r:
                    ch2_bytes = os.read(fd, 1)
                    ch2 = ch2_bytes.decode('utf-8', errors='ignore')
                    
                    if ch2 == '[' or ch2 == 'O':
                         ch3_bytes = os.read(fd, 1)
                         ch3 = ch3_bytes.decode('utf-8', errors='ignore')
                         return ord(ch3) 
                    
                    return Keys.ESC 
                else:
                    return Keys.ESC
            
            return ord(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def hide_cursor():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @staticmethod
    def clear_screen():
        # Clear entire screen and move cursor to home (0,0)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def draw_box(lines, title=""):
        """Draws a bordered box around text lines."""
        if not lines: return
        width = max(len(line) for line in lines) + 4
        if title:
            width = max(width, len(title) + 6)
            
        print("  ┌" + "─" * (width - 2) + "┐")
        if title:
            padding = (width - 2 - len(title) - 2) // 2
            # Ensure padding is not negative
            padding = max(0, padding)
            print("  │" + " " * padding + f" {title} " + " " * (width - 2 - padding - len(title) - 2) + "│")
            print("  ├" + "─" * (width - 2) + "┤")
            
        for line in lines:
            print(f"  │ {line:<{width-4}} │")
        print("  └" + "─" * (width - 2) + "┘")

class Screen:
    def render(self):
        raise NotImplementedError
    
    def handle_input(self, key):
        raise NotImplementedError

class WelcomeScreen(Screen):
    def __init__(self, sys_mgr=None):
        self.sys_mgr = sys_mgr

    def render(self):
        TUI.clear_screen()
        print("\n\n")
        
        banner = [
            "▄▄                             ▄▄                                     ",
            "▀▀                             ██                      ██             ",
            "██   ▀▀█▄ ███▄███▄ ▄█▀▀▀ ▄█▀█▄ ████▄  ▀▀█▄ ▄█▀▀▀    ▄████ ▄█▀█▄ ██ ██ ",
            "██  ▄█▀██ ██ ██ ██ ▀███▄ ██▄█▀ ██ ██ ▄█▀██ ▀███▄    ██ ██ ██▄█▀ ██▄██ ",
            "██▄ ▀█▄██ ██ ██ ██ ▄▄▄█▀ ▀█▄▄▄ ████▀ ▀█▄██ ▄▄▄█▀ ██ ▀████ ▀█▄▄▄  ▀█▀  "
        ]
        
        # System Info
        import platform
        os_name = self.sys_mgr.get_os_pretty_name() if self.sys_mgr else f"{platform.system()} {platform.release()}"
        
        sys_info = [
            f"OS: {os_name}",
            f"Host: {platform.node()}",
            f"User: {os.getenv('USER', 'unknown')}"
        ]
        
        # Colorize banner
        print(f"{Style.hex('#81ECEC')}") # Cyan
        for line in banner:
            print(f"   {line}")
        print(f"{Style.RESET}\n")
        
        TUI.draw_box(sys_info, "System Information")
        
        print("\n\n   [ ENTER ]  Start Installation")
        print("   [  ESC  ]  Exit")
        
    def handle_input(self, key):
        if key == Keys.ENTER:
            return "MENU"
        if key == Keys.ESC or key == Keys.Q:
            return "EXIT"
        return None

# We will implement MenuScreen and others in install.py or separate files
# but for now, TUI class provides the primitives.
