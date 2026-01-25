import sys
import termios
import tty
import os
import time
import re
import shutil

class Keys:
    """Keyboard scan code mapping for terminal navigation."""
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
    """ANSI TrueColor and text attribute escape sequences."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    INVERT = "\033[7m"

    @staticmethod
    def hex(hex_color, bg=False):
        """Converts a HEX string to a 24-bit ANSI escape sequence."""
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
    Core utility for low-level terminal manipulation and input capture.
    """
    _old_settings = None

    @staticmethod
    def set_raw_mode(enable=True):
        """Toggles terminal RAW mode globally and disables echo."""
        fd = sys.stdin.fileno()
        if enable:
            if TUI._old_settings is None:
                TUI._old_settings = termios.tcgetattr(fd)
            # Set raw mode and ensure ECHO is off
            tty.setraw(fd)
            os.system("stty -echo")
        else:
            if TUI._old_settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, TUI._old_settings)
                os.system("stty echo")
                TUI._old_settings = None

    @staticmethod
    def get_key():
        """Captures a single keypress, handling multi-byte escape sequences."""
        fd = sys.stdin.fileno()
        # If we are already in raw mode (managed externally), just read
        if TUI._old_settings is not None:
            return TUI._read_key_internal(fd)
            
        # Otherwise, toggle raw mode just for this read
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return TUI._read_key_internal(fd)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def _read_key_internal(fd):
        """Internal key reading logic."""
        try:
            ch_bytes = os.read(fd, 1)
            if not ch_bytes: return None
            ch = ch_bytes.decode('utf-8', errors='ignore')
            
            if ch == '\x1b':  # ESC sequence
                import select
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
        except Exception:
            return None

    @staticmethod
    def hide_cursor():
        """Hides the terminal cursor."""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor():
        """Restores terminal cursor visibility."""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @staticmethod
    def clear_screen():
        """Clears the entire terminal window and resets scrollback buffer."""
        sys.stdout.write("\033[H\033[2J\033[3J")
        sys.stdout.flush()

    @staticmethod
    def draw_box(lines, title="", center=False):
        """Renders a bordered container with optional centering and bold titles."""
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
                padding_needed = width - 4 - len(line)
                print(f"{indent}│ {formatted_line}{' ' * padding_needed} │")
            else:
                print(f"{indent}│ {line:<{width-4}} │")
        print(f"{indent}└" + "─" * (width - 2) + "┘")

    @staticmethod
    def visible_len(text):
        """Calculates character count excluding ANSI control codes."""
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
