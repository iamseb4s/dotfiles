import sys
import termios
import tty
import os
import time
import re
import shutil

class Keys:
    """Keyboard scan code mapping for terminal navigation."""
    UP = 1001
    DOWN = 1002
    RIGHT = 1003
    LEFT = 1004
    SPACE = 32
    ENTER = 13
    ESC = 27
    TAB = 9
    BACKSPACE = 127
    DEL = 301
    # Scroll keys
    PGUP = 1005
    PGDN = 1006
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
    RESIZE = -2 # Virtual key for terminal resize

class Theme:
    """Catppuccin Mocha Color Palette"""
    ROSEWATER = "#f5e0dc"
    FLAMINGO  = "#f2cdcd"
    PINK      = "#f5c2e7"
    MAUVE     = "#cba6f7"
    RED       = "#f38ba8"
    MAROON    = "#eba0ac"
    PEACH     = "#fab387"
    YELLOW    = "#f9e2af"
    GREEN     = "#a6e3a1"
    TEAL      = "#94e2d5"
    SKY       = "#89dceb"
    SAPPHIRE  = "#74c7ec"
    BLUE      = "#89b4fa"
    LAVENDER  = "#b4befe"
    TEXT      = "#cdd6f4"
    SUBTEXT1  = "#bac2de"
    SUBTEXT0  = "#a6adc8"
    OVERLAY2  = "#9399b2"
    OVERLAY1  = "#7f849c"
    OVERLAY0  = "#6c7086"
    SURFACE2  = "#585b70"
    SURFACE1  = "#45475a"
    SURFACE0  = "#313244"
    BASE      = "#1e1e2e"
    MANTLE    = "#181825"
    CRUST     = "#11111b"

class Style:
    """ANSI TrueColor and text attribute escape sequences."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    INVERT = "\033[7m"

    @staticmethod
    def hex(hex_color, bg=False):
        """Converts a HEX string to a 24-bit ANSI escape sequence."""
        if not hex_color: return ""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        try:
            red_value = int(hex_color[0:2], 16)
            green_value = int(hex_color[2:4], 16)
            blue_value = int(hex_color[4:6], 16)
            layer = 48 if bg else 38
            return f"\033[{layer};2;{red_value};{green_value};{blue_value}m"
        except ValueError:
            return ""

    # --- Semantic Levels ---
    @classmethod
    def highlight(cls, bg=False): return cls.mauve(bg)
    @classmethod
    def normal(cls, bg=False): return cls.text(bg)
    @classmethod
    def secondary(cls, bg=False): return cls.subtext0(bg)
    @classmethod
    def muted(cls, bg=False): return cls.surface2(bg)
    @classmethod
    def success(cls, bg=False): return cls.green(bg)
    @classmethod
    def error(cls, bg=False): return cls.red(bg)
    @classmethod
    def warning(cls, bg=False): return cls.yellow(bg)
    @classmethod
    def info(cls, bg=False): return cls.blue(bg)
    @classmethod
    def header(cls): return cls.blue(bg=True) + cls.crust()
    @classmethod
    def button_focused(cls): return cls.highlight(bg=True) + cls.crust() + cls.BOLD

    # --- Theme Helpers ---
    @classmethod
    def mauve(cls, bg=False): return cls.hex(Theme.MAUVE, bg)
    @classmethod
    def red(cls, bg=False): return cls.hex(Theme.RED, bg)
    @classmethod
    def green(cls, bg=False): return cls.hex(Theme.GREEN, bg)
    @classmethod
    def yellow(cls, bg=False): return cls.hex(Theme.YELLOW, bg)
    @classmethod
    def blue(cls, bg=False): return cls.hex(Theme.BLUE, bg)
    @classmethod
    def sky(cls, bg=False): return cls.hex(Theme.SKY, bg)
    @classmethod
    def teal(cls, bg=False): return cls.hex(Theme.TEAL, bg)
    @classmethod
    def peach(cls, bg=False): return cls.hex(Theme.PEACH, bg)
    @classmethod
    def surface2(cls, bg=False): return cls.hex(Theme.SURFACE2, bg)
    @classmethod
    def surface1(cls, bg=False): return cls.hex(Theme.SURFACE1, bg)
    @classmethod
    def surface0(cls, bg=False): return cls.hex(Theme.SURFACE0, bg)
    @classmethod
    def overlay2(cls, bg=False): return cls.hex(Theme.OVERLAY2, bg)
    @classmethod
    def overlay1(cls, bg=False): return cls.hex(Theme.OVERLAY1, bg)
    @classmethod
    def overlay0(cls, bg=False): return cls.hex(Theme.OVERLAY0, bg)
    @classmethod
    def crust(cls, bg=False): return cls.hex(Theme.CRUST, bg)
    @classmethod
    def mantle(cls, bg=False): return cls.hex(Theme.MANTLE, bg)
    @classmethod
    def base(cls, bg=False): return cls.hex(Theme.BASE, bg)
    @classmethod
    def text(cls, bg=False): return cls.hex(Theme.TEXT, bg)
    @classmethod
    def subtext1(cls, bg=False): return cls.hex(Theme.SUBTEXT1, bg)
    @classmethod
    def subtext0(cls, bg=False): return cls.hex(Theme.SUBTEXT0, bg)

class TUI:
    """
    Core utility for low-level terminal manipulation and input capture.
    """
    _old_settings = None
    _raw_ref_count = 0
    _resize_pending = False
    
    # Notification System State
    _notifications = [] # List of {'msg': str, 'type': str, 'time': float}

    @staticmethod
    def init_signal_handler():
        """Initializes SIGWINCH handler for terminal resizing."""
        import signal
        def handler(sig, frame):
            TUI._resize_pending = True
        signal.signal(signal.SIGWINCH, handler)

    @staticmethod
    def is_resize_pending():
        """Checks and resets the resize pending flag."""
        if TUI._resize_pending:
            TUI._resize_pending = False
            return True
        return False

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
    def get_key(blocking=False, timeout=None):
        """Captures a single keypress, handling multi-byte escape sequences."""
        if not sys.stdin.isatty():
            return None
            
        # Immediate check for resize signal
        if TUI._resize_pending:
            TUI._resize_pending = False
            return Keys.RESIZE

        fd = sys.stdin.fileno()
        
        # Determine the correct timeout for select
        # - If blocking with no timeout: 0.1s (to allow signal handling)
        # - If not blocking: 0 (immediate poll)
        # - Otherwise: use provided timeout
        if timeout is not None:
            actual_timeout = timeout
        else:
            actual_timeout = 0.1 if blocking else 0
            
        import select
        try:
            ready_to_read, _, _ = select.select([fd], [], [], actual_timeout)
            if not ready_to_read:
                return None
        except (select.error, InterruptedError):
            # This happens on SIGWINCH or other signals
            return Keys.RESIZE

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
            char_bytes = os.read(fd, 1)
            if not char_bytes: return None
            char = char_bytes.decode('utf-8', errors='ignore')
            
            if char == '\x1b':  # ESC sequence
                import select
                # Wait for the next byte (like '[')
                ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                if not ready_to_read: return Keys.ESC # standalone ESC
                
                char2_bytes = os.read(fd, 1)
                char2 = char2_bytes.decode('utf-8', errors='ignore')
                
                if char2 == '[' or char2 == 'O':
                    # Wait for the sequence specifier (like 'A', 'B', etc.)
                    ready_to_read, _, _ = select.select([fd], [], [], 0.1)
                    if not ready_to_read: return ord(char2)
                    
                    char3_bytes = os.read(fd, 1)
                    char3 = char3_bytes.decode('utf-8', errors='ignore')
                    
                    # Arrow keys: \x1b[A, B, C, D
                    if char3 == 'A': return Keys.UP
                    if char3 == 'B': return Keys.DOWN
                    if char3 == 'C': return Keys.RIGHT
                    if char3 == 'D': return Keys.LEFT

                    # DEL key sequence: \x1b[3~
                    if char3 == '3':
                        ready_to_read, _, _ = select.select([fd], [], [], 0.05)
                        if ready_to_read: os.read(fd, 1) # consume ~
                        return Keys.DEL
 
                    # Capture extended sequences like PageUp/PageDown: \x1b[5~, \x1b[6~
                    if char3 == '5':
                        ready_to_read, _, _ = select.select([fd], [], [], 0.05)
                        if ready_to_read: os.read(fd, 1) # consume ~
                        return Keys.PGUP
                    if char3 == '6':
                        ready_to_read, _, _ = select.select([fd], [], [], 0.05)
                        if ready_to_read: os.read(fd, 1) # consume ~
                        return Keys.PGDN
                               
                    return ord(char3) 
                
                return Keys.ESC 
            
            return ord(char)
        except Exception:
            return None

    @staticmethod
    def push_notification(message, type="INFO"):
        """Adds a new notification to the global stack."""
        TUI._notifications.append({
            'msg': message,
            'type': type,
            'time': time.time()
        })

    @staticmethod
    def _clean_notifications():
        """Removes expired notifications (3 seconds)."""
        now = time.time()
        TUI._notifications = [n for n in TUI._notifications if now - n['time'] < 5.0]

    @staticmethod
    def draw_notifications(buffer):
        """Overlays active notifications onto the provided buffer."""
        TUI._clean_notifications()
        
        term_size = shutil.get_terminal_size()
        term_width = term_size.columns
        term_height = term_size.lines

        # Prevent ghosting
        if len(buffer) < term_height:
            buffer.extend([""] * (term_height - len(buffer)))

        if not TUI._notifications:
            return buffer

        width = 40
        margin_right = 2
        current_y = 1
        
        for n in TUI._notifications:
            border_color = Style.info() if n['type'] == "INFO" else Style.error()
            title = " [i] INFO " if n['type'] == "INFO" else " [!] ERROR "
                
            # Wrap message
            wrapped = TUI.wrap_text(n['msg'], width - 4)
            height = len(wrapped) + 2
            
            # Build notification lines
            n_lines = []
            
            # Top Border (Exactly 40 chars)
            title_len = len(title)
            # ╭─ (2) + title (11) + ─ * (40 - 11 - 3 = 26) + ╮ (1) = 40
            top_str = "╭─" + title + "─" * (width - title_len - 3) + "╮"
            n_lines.append(f"{border_color}{top_str}{Style.RESET}")
            
            # Content
            # Width calculation: │ (1) + " " (1) + line + padding + │ (1) = 40
            for line in wrapped:
                padding = " " * (37 - TUI.visible_len(line))
                n_lines.append(f"{border_color}│{Style.RESET} {Style.normal()}{line}{Style.RESET}{padding}{border_color}│{Style.RESET}")
            
            # Bottom Border
            bot_str = "╰" + "─" * (width - 2) + "╯"
            n_lines.append(f"{border_color}{bot_str}{Style.RESET}")
            
            # Overlay onto buffer
            start_x = term_width - width - margin_right
            for i, line in enumerate(n_lines):
                target_y = current_y + i
                if 0 <= target_y < len(buffer):
                    buffer[target_y] = TUI.overlay(buffer[target_y], line, start_x)
            
            current_y += len(n_lines) + 1
            
        return buffer

        term_width = shutil.get_terminal_size().columns

    @staticmethod
    def truncate_ansi(text, max_len):
        """Truncates a string containing ANSI codes without breaking them, while stripping layout-breaking control chars."""
        # Pre-clean the text from carriage returns
        text = text.replace('\r', '')
        
        if TUI.visible_len(text) <= max_len:
            return text
            
        # Pattern to match ANSI escape sequences
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        
        result = ""
        current_visible_len = 0
        last_match_end = 0
        
        for match in ansi_escape.finditer(text):
            # Text before the ANSI code
            pre_ansi = text[last_match_end:match.start()]
            for char in pre_ansi:
                if current_visible_len < max_len - 3: # Leave room for "..."
                    result += char
                    current_visible_len += 1
                else:
                    return result + Style.RESET + "..."
            
            # The ANSI code itself (doesn't count toward length)
            result += match.group()
            last_match_end = match.end()
            
        # Final bit of text after last ANSI code
        post_ansi = text[last_match_end:]
        for char in post_ansi:
            if current_visible_len < max_len - 3:
                result += char
                current_visible_len += 1
            else:
                return result + Style.RESET + "..."
                
        return result

    @staticmethod
    def ansi_slice(text, start, end=None):
        """Slices a string by its visible length, preserving necessary ANSI codes."""
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        result = ""
        current_visible_pos = 0
        last_match_end = 0
        
        for match in ansi_escape.finditer(text):
            # Process plain text before the ANSI sequence
            pre_text = text[last_match_end:match.start()]
            for char in pre_text:
                if current_visible_pos >= start and (end is None or current_visible_pos < end):
                    result += char
                current_visible_pos += 1
            
            # Only include ANSI sequence
            if end is None or current_visible_pos < end:
                result += match.group()
                
            last_match_end = match.end()
            
        # Process remaining plain text
        post_text = text[last_match_end:]
        for char in post_text:
            if current_visible_pos >= start and (end is None or current_visible_pos < end):
                result += char
            current_visible_pos += 1
            
        return result

    @staticmethod
    def overlay(bg, fg, x):
        """Composites foreground text onto background text at a specific x-offset."""
        bg_vlen = TUI.visible_len(bg)
        if bg_vlen < x:
            left = bg + " " * (x - bg_vlen)
        else:
            left = TUI.ansi_slice(bg, 0, x)
            
        fg_vlen = TUI.visible_len(fg)
        right = TUI.ansi_slice(bg, x + fg_vlen)
        
        return left + fg + right

    @staticmethod
    def create_container(lines, width, height, title="", color="", is_focused=False, scroll_pos=None, scroll_size=None):
        """Wraps a list of lines in a rounded box with an optional title and integrated scrollbar."""
        base_border_color = color if color else (Style.highlight() if is_focused else Style.muted())
        thumb_color = Style.highlight() if is_focused else Style.blue()
        reset = Style.RESET
        
        # 1. Top border with title
        top = "╭─"
        if title:
            display_title = title.upper()
            max_title_len = width - 6
            if len(display_title) > max_title_len:
                display_title = display_title[:max_title_len-1] + "…"
            top += f" {Style.BOLD}{display_title}{Style.RESET}{base_border_color} ─"
        remaining = width - TUI.visible_len(top) - 1
        top += "─" * max(0, remaining) + "╮"
        output = [f"{base_border_color}{top}{reset}"]
        
        # 2. Content lines
        internal_width = width - 2
        for i in range(height - 2):
            content = lines[i] if i < len(lines) else ""
            
            # Truncate safely if it exceeds internal width
            if TUI.visible_len(content) > internal_width:
                content = TUI.truncate_ansi(content, internal_width)
            
            v_len = TUI.visible_len(content)
            padding = " " * max(0, internal_width - v_len)
            
            # Integrated Scrollbar logic
            r_char = "│"
            r_color = base_border_color
            if scroll_pos is not None and scroll_size is not None:
                if scroll_pos <= i < scroll_pos + scroll_size:
                    r_char = "┃"
                    r_color = thumb_color
            output.append(f"{base_border_color}│{reset}{content}{padding}{r_color}{r_char}{reset}")
            
        # 3. Bottom border
        bottom = "╰" + "─" * (width - 2) + "╯"
        output.append(f"{base_border_color}{bottom}{reset}")
        return output

    @staticmethod
    def stitch_containers(left_box, right_box, gap=1):
        """Combines two container buffers line by line with a gap."""
        max_lines = max(len(left_box), len(right_box))
        combined = []
        spacer = " " * gap
        
        for i in range(max_lines):
            l_line = left_box[i] if i < len(left_box) else " " * TUI.visible_len(left_box[0])
            r_line = right_box[i] if i < len(right_box) else " " * TUI.visible_len(right_box[0])
            combined.append(f"{l_line}{spacer}{r_line}")
            
        return combined

    @staticmethod
    def wrap_text(text, width):
        """Wraps text to a specific width using textwrap."""
        import textwrap
        if not text: return []
        return textwrap.wrap(text, width)

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
            
        print(f"{indent}{Style.normal()}╭" + "─" * (width - 2) + f"╮{Style.RESET}")
        if title:
            padding = (width - 2 - len(title) - 2) // 2
            padding = max(0, padding)
            print(f"{indent}{Style.normal()}│{Style.RESET}" + " " * padding + f" {Style.normal()}{Style.BOLD}{title}{Style.RESET} " + " " * (width - 2 - padding - len(title) - 2) + f"{Style.normal()}│{Style.RESET}")
            print(f"{indent}{Style.normal()}├" + "─" * (width - 2) + f"┤{Style.RESET}")
            
        for line in lines:
            # Calculate visible length to handle padding correctly
            v_len = TUI.visible_len(line)
            padding_total = (width - 4) - v_len
            left_pad = padding_total // 2
            right_pad = padding_total - left_pad
            
            if ":" in line:
                label, value = line.split(":", 1)
                formatted_line = f"{Style.normal()}{Style.BOLD}{label}:{Style.RESET}{Style.normal()}{value}{Style.RESET}"
                print(f"{indent}{Style.normal()}│{Style.RESET} {' ' * left_pad}{formatted_line}{' ' * right_pad} {Style.normal()}│{Style.RESET}")
            else:
                print(f"{indent}{Style.normal()}│{Style.RESET} {' ' * left_pad}{Style.normal()}{line}{Style.RESET}{' ' * right_pad} {Style.normal()}│{Style.RESET}")
        print(f"{indent}{Style.normal()}╰" + "─" * (width - 2) + f"╯{Style.RESET}")

    @staticmethod
    def wrap_pills(pills, width, gap=4):
        """Groups pills into multiple lines based on available width."""
        lines = []
        current_line = []
        current_len = 0
        
        for pill in pills:
            p_len = TUI.visible_len(pill)
            if not current_line:
                current_line.append(pill)
                current_len = p_len
            elif current_len + gap + p_len <= width:
                current_line.append(pill)
                current_len += gap + p_len
            else:
                lines.append((" " * gap).join(current_line))
                current_line = [pill]
                current_len = p_len
        
        if current_line:
            lines.append((" " * gap).join(current_line))
        return lines

    @staticmethod
    def visible_len(text):
        """Calculates character count excluding ANSI control codes and non-printable characters."""
        if not text: return 0
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        clean_text = ansi_escape.sub('', text)
        # Remove or replace other control characters that might break layout
        clean_text = clean_text.replace('\r', '').replace('\t', '    ')
        return len(clean_text)

    @staticmethod
    def visible_ljust(text, width):
        """Pads string to width based on visible characters, truncating if necessary to prevent overflow."""
        v_len = TUI.visible_len(text)
        if v_len > width:
            return TUI.truncate_ansi(text, width)
        return text + " " * max(0, width - v_len)

    @staticmethod
    def split_line(left, right, width, fill=' '):
        """Creates a line with 'left' aligned left and 'right' aligned right."""
        l_vlen = TUI.visible_len(left)
        r_vlen = TUI.visible_len(right)
        gap = width - l_vlen - r_vlen
        if gap < 0:
            left = TUI.truncate_ansi(left, max(0, width - r_vlen - 1))
            l_vlen = TUI.visible_len(left)
            gap = width - l_vlen - r_vlen
        return left + (fill * gap) + right

    @staticmethod
    def hex_to_ansi(hex_color, bg=False):
        """Interface for HEX to ANSI conversion."""
        return Style.hex(hex_color, bg)

    @staticmethod
    def pill(key, action, color_hex):
        """Renders a styled command shortcut pill."""
        bg = Style.hex(color_hex, bg=True)
        fg = Style.hex(color_hex, bg=False)
        # Structure: [BG_COLOR][CRUST_TEXT] KEY [RESET] [COLOR_TEXT] Action
        return f"{bg}{Style.crust()} {key} {Style.RESET} {fg}{action}{Style.RESET}"

