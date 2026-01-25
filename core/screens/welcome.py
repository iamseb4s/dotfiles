import shutil
import platform
import os
import sys
from core.tui import TUI, Keys, Style

class Screen:
    """Interface for terminal screens."""
    def render(self):
        """Displays the screen content."""
        raise NotImplementedError
    
    def handle_input(self, key):
        """Processes keyboard input."""
        raise NotImplementedError

class WelcomeScreen(Screen):
    """
    Landing screen displaying system information and primary actions.
    """
    def __init__(self, sys_mgr=None):
        self.sys_mgr = sys_mgr

    def render(self):
        """Displays the splash screen with centered logo and system metrics."""
        term_size = shutil.get_terminal_size()
        term_width = term_size.columns
        term_height = term_size.lines
        
        # 1. Content Generation
        banner = [
            "▄▄                             ▄▄                                     ",
            "▀▀                             ██                      ██             ",
            "██   ▀▀█▄ ███▄███▄ ▄█▀▀▀ ▄█▀█▄ ████▄  ▀▀█▄ ▄█▀▀▀    ▄████ ▄█▀█▄ ██ ██ ",
            "██  ▄█▀██ ██ ██ ██ ▀███▄ ██▄█▀ ██ ██ ▄█▀██ ▀███▄    ██ ██ ██▄█▀ ██▄██ ",
            "██▄ ▀█▄██ ██ ██ ██ ▄▄▄█▀ ▀█▄▄▄ ████▀ ▀█▄██ ▄▄▄█▀ ██ ▀████ ▀█▄▄▄  ▀█▀  "
        ]
        
        # Resolve OS name for display
        os_name = self.sys_mgr.get_os_pretty_name() if self.sys_mgr else f"{platform.system()} {platform.release()}"
        
        sys_info = [
            f"OS: {os_name}",
            f"Host: {platform.node()}",
            f"User: {os.getenv('USER', 'unknown')}"
        ]
        
        content = []
        # Banner
        content.append(f"{Style.hex('#81ECEC')}") # Cyan accent
        for line in banner:
            padding = (term_width - len(line)) // 2
            padding = max(0, padding)
            content.append(f"{' ' * padding}{line}")
        content.append(f"{Style.RESET}")
        
        # Subtitle
        subtitle = "─ Dotfiles & Packages Installer ─"
        s_padding = (term_width - len(subtitle)) // 2
        content.append("")
        content.append(f"{Style.DIM}{' ' * max(0, s_padding)}{subtitle}{Style.RESET}")
        content.append("")
        
        # Information Box
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            TUI.draw_box(sys_info, "SYSTEM INFORMATION", center=True)
        content.append(f.getvalue().strip("\n"))
        
        # Navigation Hints
        p_enter = TUI.pill("ENTER", "Start Installation", "a6e3a1") # Success Green
        p_quit  = TUI.pill("Q", "Exit", "f38ba8")               # Danger Red
        
        pills_line = f"{p_enter}     {p_quit}"
        p_padding = (term_width - TUI.visible_len(pills_line)) // 2
        p_padding = max(0, p_padding)
        
        content.append("")
        content.append(f"{' ' * p_padding}{pills_line}")

        # 2. Vertical Centering
        real_lines = []
        for item in content:
            real_lines.extend(item.split("\n"))
            
        content_height = len(real_lines)
        top_pad = max(0, (term_height - content_height) // 2)
        
        buffer = [""] * top_pad
        buffer.extend(real_lines)

        # Atomic Draw
        sys.stdout.write("\033[H" + "\n".join(buffer) + "\n\033[J")
        sys.stdout.flush()

        
    def handle_input(self, key):
        """Maps key events to screen transitions."""
        if key == Keys.ENTER:
            return "MENU"
        if key == Keys.ESC or key in [Keys.Q, Keys.Q_UPPER]:
            return "EXIT"
        return None
