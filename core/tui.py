import sys
import termios
import tty
import os
import time
import re
import shutil

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
    # Scroll keys
    PGUP = 53
    PGDN = 54
    # Ctrl keys
    CTRL_K = 11
    CTRL_J = 10
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
                # Determine if ESC or multi-byte sequence
                r, w, x = select.select([fd], [], [], 0.2)
                if r:
                    ch2_bytes = os.read(fd, 1)
                    ch2 = ch2_bytes.decode('utf-8', errors='ignore')
                    
                    if ch2 == '[' or ch2 == 'O':
                         ch3_bytes = os.read(fd, 1)
                         ch3 = ch3_bytes.decode('utf-8', errors='ignore')
                         
                         # Capture extended sequences like PageUp/PageDown
                         if ch3 in ['5', '6']:
                             os.read(fd, 1) # consume terminator
                             return ord(ch3)
                             
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
    def draw_box(lines, title="", center=False):
        """Draws a bordered box around text lines with bold labels."""
        if not lines: return
        
        term_width = shutil.get_terminal_size().columns
        # Calculate width based on content
        content_width = max(len(line) for line in lines)
        width = max(content_width + 4, len(title) + 6)
        
        # Centering margin
        margin = (term_width - width) // 2 if center else 2
        margin = max(0, margin)
        indent = " " * margin
            
        print(f"{indent}┌" + "─" * (width - 2) + "┐")
        if title:
            padding = (width - 2 - len(title) - 2) // 2
            padding = max(0, padding)
            print(f"{indent}│" + " " * padding + f" {Style.BOLD}{title}{Style.RESET} " + " " * (width - 2 - padding - len(title) - 2) + "│")
            print(f"{indent}├" + "─" * (width - 2) + "┤")
            
        for line in lines:
            # Check if line has a label (contains ':')
            if ":" in line:
                label, value = line.split(":", 1)
                formatted_line = f"{Style.BOLD}{label}:{Style.RESET}{value}"
                # Padding must account for invisible ANSI codes from Style
                padding_needed = width - 4 - len(line)
                print(f"{indent}│ {formatted_line}{' ' * padding_needed} │")
            else:
                print(f"{indent}│ {line:<{width-4}} │")
        print(f"{indent}└" + "─" * (width - 2) + "┘")

    @staticmethod
    def visible_len(text):
        """Calculates visible character count, excluding ANSI control codes."""
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        return len(ansi_escape.sub('', text))

    @staticmethod
    def hex_to_ansi(hex_color, bg=False):
        """Interface for HEX to ANSI conversion."""
        return Style.hex(hex_color, bg)

    @staticmethod
    def pill(key, action, color_hex):
        """Renders a styled command shortcut pill."""
        bg = Style.hex(color_hex, bg=True)
        fg = Style.hex(color_hex, bg=False)
        # Structure: [BG_COLOR][BLACK_TEXT] KEY [RESET] [COLOR_TEXT] Action
        return f"{bg}\033[30m {key} {Style.RESET} {fg}{action}{Style.RESET}"


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
        term_width = shutil.get_terminal_size().columns
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
        
        # Render Centered Banner
        print(f"{Style.hex('#81ECEC')}") # Cyan
        for line in banner:
            padding = (term_width - len(line)) // 2
            padding = max(0, padding)
            print(f"{' ' * padding}{line}")
        print(f"{Style.RESET}")
        
        # Render Polished Subtitle
        subtitle = "─ Dotfiles & Packages Installer ─"
        s_padding = (term_width - len(subtitle)) // 2
        print(f"{Style.DIM}{' ' * max(0, s_padding)}{subtitle}{Style.RESET}\n\n")
        
        # Render Centered Box
        TUI.draw_box(sys_info, "SYSTEM INFORMATION", center=True)
        
        # Footer Centered Pills
        p_enter = TUI.pill("ENTER", "Start Installation", "a6e3a1") # Green
        p_quit  = TUI.pill("Q", "Exit", "f38ba8")               # Red
        
        pills_line = f"{p_enter}     {p_quit}"
        p_padding = (term_width - TUI.visible_len(pills_line)) // 2
        p_padding = max(0, p_padding)
        
        print(f"\n\n{' ' * p_padding}{pills_line}")
        
    def handle_input(self, key):
        if key == Keys.ENTER:
            return "MENU"
        if key == Keys.ESC or key == Keys.Q:
            return "EXIT"
        return None
