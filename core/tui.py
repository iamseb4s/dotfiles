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
    Q_UPPER = 81 # Q
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
    _raw_ref_count = 0

    @staticmethod
    def set_raw_mode(enable=True):
        """Toggles terminal RAW mode globally and disables echo."""
        if not sys.stdin.isatty():
            return
        fd = sys.stdin.fileno()
        
        if enable:
            TUI._raw_ref_count += 1
            if TUI._raw_ref_count > 1:
                return # Already in raw mode
                
            if TUI._old_settings is None:
                TUI._old_settings = termios.tcgetattr(fd)
            
            # Create raw mode settings
            raw = termios.tcgetattr(fd)
            # lflags: Disable ICANON (buffered), ECHO, and ISIG
            raw[3] &= ~(termios.ICANON | termios.ECHO | termios.IEXTEN | termios.ISIG)
            # iflags: Disable flow control and translation of CR to NL
            raw[0] &= ~(termios.IXON | termios.ICRNL)
            # oflags: Keep OPOST for standard \n -> \r\n conversion
            raw[1] |= (termios.OPOST)
            # cflags: 8-bit chars
            raw[2] &= ~(termios.CSIZE | termios.PARENB)
            raw[2] |= termios.CS8
            # cc: Blocking read (wait for at least 1 byte)
            raw[6][termios.VMIN] = 1
            raw[6][termios.VTIME] = 0
            
            termios.tcsetattr(fd, termios.TCSADRAIN, raw)
        else:
            TUI._raw_ref_count = max(0, TUI._raw_ref_count - 1)
            if TUI._raw_ref_count == 0 and TUI._old_settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, TUI._old_settings)
                TUI._old_settings = None

    @staticmethod
    def get_key(blocking=False):
        """Captures a single keypress, handling multi-byte escape sequences."""
        if not sys.stdin.isatty():
            return None
            
        fd = sys.stdin.fileno()
        
        # If not blocking, check if there is data to read
        if not blocking:
            import select
            r, _, _ = select.select([fd], [], [], 0)
            if not r:
                return None

        # If we are NOT in global raw mode, we MUST toggle it for this read
        # to ensure ECHO is off and ICANON is off.
        is_global = TUI._old_settings is not None
        
        if not is_global:
            old = termios.tcgetattr(fd)
            raw = termios.tcgetattr(fd)
            raw[3] &= ~(termios.ICANON | termios.ECHO)
            raw[6][termios.VMIN] = 1
            raw[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, raw)
            try:
                return TUI._read_key_internal(fd)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        else:
            # Already in raw mode, just read
            return TUI._read_key_internal(fd)


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
    def reset_cursor():
        """Moves the cursor to the top-left corner without clearing the screen."""
        sys.stdout.write("\033[H")
        sys.stdout.flush()

    @staticmethod
    def clear_screen():
        """Clears the entire terminal window and resets scrollback buffer."""
        sys.stdout.write("\033[H\033[2J\033[3J")
        sys.stdout.flush()

    @staticmethod
    def draw_box(lines, title="", center=False, width=None):
        """Renders a bordered container with optional centering and bold titles."""
        if not lines: return
        
        term_width = shutil.get_terminal_size().columns
        # Calculate width based on content if not provided
        if width is None:
            content_width = max(len(line) for line in lines)
            # Increased default padding for a more spacious look
            width = max(content_width + 12, len(title) + 14)
        
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
            # Calculate visible length to handle padding correctly
            v_len = TUI.visible_len(line)
            padding_total = (width - 4) - v_len
            left_pad = padding_total // 2
            right_pad = padding_total - left_pad
            
            if ":" in line:
                label, value = line.split(":", 1)
                formatted_line = f"{Style.BOLD}{label}:{Style.RESET}{value}"
                print(f"{indent}│ {' ' * left_pad}{formatted_line}{' ' * right_pad} │")
            else:
                print(f"{indent}│ {' ' * left_pad}{line}{' ' * right_pad} │")
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
