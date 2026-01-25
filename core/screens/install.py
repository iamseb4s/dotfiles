import time
import shutil
import sys
import select
from core.tui import TUI, Style, Keys
from core.screens.welcome import Screen
from core.screens.summary import SummaryModal

class ConfirmModal:
    """Simple confirmation modal for cancellation."""
    def __init__(self, title, message):
        self.title = title
        self.message = message
        self.focus_idx = 1 # Default to NO (Cancel)

    def render(self):
        width = 50
        height = 8
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        lines = []
        lines.append(f"╔{'═' * (width-2)}╗")
        lines.append(f"║{self.title.center(width-2)}║")
        lines.append(f"╠{'═' * (width-2)}╣")
        lines.append(f"║{' ' * (width-2)}║")
        lines.append(f"║{self.message.center(width-2)}║")
        lines.append(f"║{' ' * (width-2)}║")
        
        btn_y = f"  YES  "
        btn_n = f"  NO   "
        if self.focus_idx == 0: btn_y = f"{Style.INVERT}{btn_y}{Style.RESET}"
        else: btn_y = f"[{btn_y.strip()}]"
        if self.focus_idx == 1: btn_n = f"{Style.INVERT}{btn_n}{Style.RESET}"
        else: btn_n = f"[{btn_n.strip()}]"
        
        btn_row = f"{btn_y}     {btn_n}"
        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        lines.append(f"║{' ' * padding}{btn_row}{' ' * (width - 2 - padding - v_len)}║")
        lines.append(f"╚{'═' * (width-2)}╝")
        
        return lines, start_y, start_x

    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            self.focus_idx = 1 if self.focus_idx == 0 else 0
        elif key == Keys.ENTER:
            return "YES" if self.focus_idx == 0 else "NO"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]:
            return "NO"
        return None

class InstallScreen(Screen):
    """
    Advanced installation dashboard with split-view, real-time logs,
    and soft-cancellation support.
    """
    def __init__(self, modules, selected_ids, overrides=None):
        self.modules = modules
        self.queue = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides or {}
        self.total = len(self.queue)
        
        # Execution State
        self.current_idx = -1
        self.results = {} # {mod_id: {'pkg': bool, 'dots': bool}}
        self.status = {}  # {mod_id: {'pkg': 'pending', 'dots': 'pending'}}
        for m in self.queue:
            self.status[m.id] = {'pkg': 'pending', 'dots': 'pending'}
            
        self.logs = []
        self.is_finished = False
        self.is_cancelled = False
        
        # UI State
        self.log_offset = 0
        self.auto_scroll = True
        self.last_render_time = 0
        self.render_throttle = 0.03 # Max ~30 FPS for logs
        self.modal = None # Used for cancel confirmation or final results
        self.spinner_chars = ["|", "/", "-", "\\"]
        self.spinner_idx = 0
        
        # Unified Layout Metric
        self.reserved_height = 9

    def add_log(self, message):
        """Adds a line to the log buffer and handles auto-scroll."""
        if message is None:
            self.render() # Refresh call
            return
            
        self.logs.append(message)
        if self.auto_scroll:
            term_height = shutil.get_terminal_size().lines
            available_height = term_height - self.reserved_height
            if len(self.logs) > available_height:
                self.log_offset = len(self.logs) - available_height

        # Throttled render during high-volume logs
        now = time.time()
        if now - self.last_render_time > self.render_throttle:
            self.render()
            self.last_render_time = now

    def render(self):
        """Draws the split-view dashboard with bottom progress bar and scrolls."""
        # Use a buffer to avoid flickering and partial draws
        buffer = []
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # Security margin to prevent line wrapping
        safe_width = term_width - 2
        
        # 1. Header (Pinned to top)
        title = " DEPLOYING PACKAGES "
        bg_blue = Style.hex("89B4FA", bg=True)
        text_black = "\033[30m"
        padding = (term_width - len(title)) // 2
        header_bar = f"{bg_blue}{text_black}{' '*padding}{title}{' '*(term_width-padding-len(title))}{Style.RESET}"
        buffer.append(header_bar)
        buffer.append("")
        
        # Centered Subtitle
        task_label = self.queue[self.current_idx].label if self.current_idx >= 0 else 'Initializing'
        sub_text = f"Deployment in progress. Current task: {task_label}"
        sub_pad = (term_width - TUI.visible_len(sub_text)) // 2
        buffer.append(f"{' ' * max(0, sub_pad)}{Style.DIM}{sub_text}{Style.RESET}")
        buffer.append("")
        
        # 2. Split View Area
        self.reserved_height = 9
        available_height = term_height - self.reserved_height
        left_width = int(safe_width * 0.30)
        
        # Build Left Column (Task Tree)
        left_lines = []
        for mod in self.queue:
            state = self.status[mod.id]
            is_current = (self.current_idx >= 0 and self.queue[self.current_idx].id == mod.id)
            
            # Icons and colors
            all_done = all(v in ['success', 'skipped'] for v in state.values())
            has_error = any(v == 'error' for v in state.values())
            
            if is_current and not self.is_finished: icon = "⟳"
            elif has_error: icon = "✘"
            elif all_done: icon = "✔"
            else: icon = "○"
            
            color = Style.hex("#89B4FA") if is_current else (Style.hex("#55E6C1") if icon == "✔" else (Style.hex("#FF6B6B") if icon == "✘" else ""))
            left_lines.append(f"  {color}{icon} {mod.label}{Style.RESET}")
            
            ovr = self.overrides.get(mod.id, {})
            has_dots = mod.stow_pkg is not None
            
            def get_icon(s):
                if s == 'running': return self.spinner_chars[self.spinner_idx]
                if s == 'success': return "✔"
                if s == 'error': return "✘"
                return "○"

            if ovr.get('install_pkg', True):
                left_lines.append(f"  {Style.DIM}{'├' if has_dots else '└'}{Style.RESET} {get_icon(state['pkg'])} Package")
            if has_dots and ovr.get('install_dots', True):
                left_lines.append(f"  {Style.DIM}└{Style.RESET} {get_icon(state['dots'])} Dotfiles")

        # Position status line at the absolute bottom of the split view
        status_line = f"  {Style.DIM}Selected: {len(self.queue)} packages{Style.RESET}"
        while len(left_lines) < available_height - 1:
            left_lines.append("")
        left_lines.append(status_line)

        # Draw exactly available_height rows
        visible_logs = self.logs[self.log_offset : self.log_offset + available_height]
        
        for i in range(available_height):
            l_content = left_lines[i] if i < len(left_lines) else ""
            r_content = visible_logs[i] if i < len(visible_logs) else ""
            
            l_len = TUI.visible_len(l_content)
            l_pad = " " * max(0, left_width - l_len)
            sep = f"{Style.DIM}│{Style.RESET}"
            
            r_area_width = safe_width - left_width - 5
            if TUI.visible_len(r_content) > r_area_width:
                r_content = r_content[:r_area_width-3] + "..."
            r_len = TUI.visible_len(r_content)
            r_pad = " " * max(0, r_area_width - r_len)
            
            scroll_r = f"{Style.DIM}│{Style.RESET}"
            if len(self.logs) > available_height:
                thumb_size = max(1, int(available_height * (available_height / len(self.logs))))
                max_offset = len(self.logs) - available_height
                progress = self.log_offset / max_offset
                start_pos = int(progress * (available_height - thumb_size))
                if start_pos <= i < start_pos + thumb_size:
                    scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}"
            elif len(self.logs) > 0:
                scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}"
            
            buffer.append(f"{l_content}{l_pad} {sep} {r_content}{r_pad} {scroll_r}")

        # 3. Progress Bar
        buffer.append("")
        progress_val = self.current_idx / self.total if self.total > 0 else 0
        if self.is_finished: progress_val = 1
        
        bar_len = int(safe_width * 0.5)
        filled = int(bar_len * progress_val)
        bar_color = Style.hex("#55E6C1") if not self.is_cancelled else Style.hex("#FF6B6B")
        bar_content = f"{bar_color}█" * filled + f"{Style.DIM}░" * (bar_len - filled) + Style.RESET
        p_padding = (term_width - bar_len - 6) // 2
        buffer.append(f"{' ' * max(0, p_padding)}[ {bar_content} ] {int(progress_val*100)}%")
        buffer.append("")

        # 4. Footer
        if self.is_finished:
            footer = f"{TUI.pill('ENTER', 'Finish', '#a6e3a1')}    {TUI.pill('R', 'Summary', '#FDCB6E')}    {TUI.pill('PgUp/Dn', 'Scroll', '#89B4FA')}    {TUI.pill('Q', 'Quit', '#f38ba8')}"
        elif self.is_cancelled:
            footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'CANCELING...', '#FDCB6E')}"
        else:
            footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'INSTALLING...', '#FDCB6E')}    {TUI.pill('Q/ESC', 'Stop', '#f38ba8')}"
        
        f_len = TUI.visible_len(footer)
        buffer.append(" " * max(0, (term_width - f_len) // 2) + footer)

        # 5. Modal Overlay (Final Pass on buffer)
        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            for i, m_line in enumerate(m_lines):
                target_y = m_y + i
                if 0 <= target_y < len(buffer):
                    bg = buffer[target_y]
                    # Simple centering overlay logic
                    m_v_len = TUI.visible_len(m_line)
                    buffer[target_y] = " " * m_x + m_line + " " * max(0, term_width - m_x - m_v_len)

        # Atomic Draw
        sys.stdout.write("\033[H" + "\n".join(buffer) + "\n\033[J")
        sys.stdout.flush()

    def run(self):
        """Main installation loop with real-time interruption handling."""
        for idx, mod in enumerate(self.queue):
            if self.is_cancelled: break
            
            self.current_idx = idx
            ovr = self.overrides.get(mod.id, {})
            do_pkg = ovr.get('install_pkg', True)
            do_dots = ovr.get('install_dots', True) if mod.stow_pkg else False
            
            self.results[mod.id] = {'pkg': True, 'dots': True}
            
            # Sub-tasks execution
            tasks = []
            if do_pkg: tasks.append(('pkg', mod.install))
            else: self.status[mod.id]['pkg'] = 'skipped'
            
            if do_dots: tasks.append(('dots', mod.configure))
            else: self.status[mod.id]['dots'] = 'skipped'

            for task_type, func in tasks:
                if self.is_cancelled: break
                
                self.status[mod.id][task_type] = 'running'
                
                def live_callback(line):
                    self.add_log(line)
                    self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
                    # Every log line triggers a keyboard poll for instant Q/ESC detection
                    input_handler()
                
                def input_handler():
                    # Check for keyboard input when select() says stdin is ready
                    key = TUI.get_key()
                    if key is None: return

                    if not self.modal:
                        if key in [Keys.Q, Keys.Q_UPPER, Keys.ESC]:
                            self.modal = ConfirmModal("STOP INSTALLATION", "Finish current task and stop?")
                    else:
                        res = self.modal.handle_input(key)
                        if res == "YES":
                            self.is_cancelled = True
                            self.modal = None
                        elif res == "NO":
                            self.modal = None
                    
                    self.render()

                # Execute with dual monitoring (logs + keyboard)
                success = func(ovr, callback=live_callback, input_callback=input_handler)
                self.status[mod.id][task_type] = 'success' if success else 'error'
                self.results[mod.id][task_type] = success
                
                if not success and task_type == 'pkg':
                    self.status[mod.id]['dots'] = 'skipped'
                    break

        self.is_finished = True
        # Always force SummaryModal on completion, overwriting any pending ConfirmModal
        self.modal = SummaryModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
        
        while True:
            self.render()
            key = TUI.get_key(blocking=True)
            if key is None: continue

            if self.modal:
                action = self.modal.handle_input(key)
                if action == "FINISH": return "WELCOME"
                if action == "CLOSE": self.modal = None
                if action == "CANCEL" and not self.is_finished:
                    self.modal = None
                # If in summary modal and user press Q, let it exit
                if key in [Keys.Q, Keys.Q_UPPER] and self.is_finished:
                    sys.exit(0)
            else:
                if key == Keys.ENTER: return "WELCOME"
                if key in [Keys.Q, Keys.Q_UPPER]:
                    if self.is_finished:
                        sys.exit(0)
                    else:
                        self.modal = ConfirmModal("EXIT", "Are you sure you want to exit?")
                
                if key == Keys.R:
                    self.modal = SummaryModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
                
                # Manual Scroll
                term_height = shutil.get_terminal_size().lines
                available_height = term_height - self.reserved_height
                max_off = max(0, len(self.logs) - available_height)
                
                if key == Keys.PGUP:
                    self.auto_scroll = False
                    self.log_offset = max(0, self.log_offset - 5)
                if key == Keys.PGDN:
                    self.log_offset = min(max_off, self.log_offset + 5)
                    # Re-enable auto-scroll if hit bottom
                    if self.log_offset >= max_off:
                        self.auto_scroll = True

    def handle_input(self, key):
        return None
