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
        elif key == Keys.ESC or key == Keys.Q:
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
        self.last_scroll_time = 0
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

    def render(self):
        """Draws the split-view dashboard with bottom progress bar and scrolls."""
        TUI.clear_screen()
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # Security margin to prevent line wrapping and scrolling
        safe_width = term_width - 2
        
        # 1. Header (Pinned to top)
        title = " DEPLOYING PACKAGES "
        bg_blue = Style.hex("89B4FA", bg=True)
        text_black = "\033[30m"
        padding = (term_width - len(title)) // 2
        header_bar = f"{bg_blue}{text_black}{' '*padding}{title}{' '*(term_width-padding-len(title))}{Style.RESET}"
        sys.stdout.write(header_bar + "\n")
        print()
        
        # Centered Subtitle
        task_label = self.queue[self.current_idx].label if self.current_idx >= 0 else 'Initializing'
        sub_text = f"Deployment in progress. Current task: {task_label}"
        sub_pad = (term_width - TUI.visible_len(sub_text)) // 2
        sys.stdout.write(f"{' ' * max(0, sub_pad)}{Style.DIM}{sub_text}{Style.RESET}\n")
        
        print()
        
        # 2. Split View
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
        
        current_rows = 0
        for i in range(available_height):
            self._draw_row(i, left_lines, visible_logs, left_width, safe_width, available_height)
            current_rows += 1

        # 3. Progress Bar
        print() 
        progress_val = self.current_idx / self.total if self.total > 0 else 0
        if self.is_finished: progress_val = 1
        
        bar_len = int(safe_width * 0.5)
        filled = int(bar_len * progress_val)
        bar_color = Style.hex("#55E6C1") if not self.is_cancelled else Style.hex("#FF6B6B")
        bar_content = f"{bar_color}█" * filled + f"{Style.DIM}░" * (bar_len - filled) + Style.RESET
        
        p_padding = (term_width - bar_len - 6) // 2
        print(f"{' ' * max(0, p_padding)}[ {bar_content} ] {int(progress_val*100)}%")
        
        print()

        # 4. Footer
        if self.is_finished:
            line = f"{TUI.pill('ENTER', 'Finish', '#a6e3a1')}    {TUI.pill('R', 'Summary', '#FDCB6E')}    {TUI.pill('PgUp/Dn', 'Scroll', '#89B4FA')}    {TUI.pill('Q', 'Quit', '#f38ba8')}"
        elif self.is_cancelled:
            line = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'CANCELING...', '#FDCB6E')}"
        else:
            line = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'INSTALLING...', '#FDCB6E')}    {TUI.pill('Q/ESC', 'Stop', '#f38ba8')}"
            
        p_len = TUI.visible_len(line)
        print(" " * max(0, (term_width - p_len) // 2) + line)


    def _draw_row(self, i, visible_left, visible_logs, left_width, safe_width, available_height):
        """Helper to build a single row of the split view with scalable scrollbar and modal overlay."""
        l_content = visible_left[i] if i < len(visible_left) else ""
        r_content = visible_logs[i] if i < len(visible_logs) else ""
        
        l_len = TUI.visible_len(l_content)
        l_pad = " " * max(0, left_width - l_len)
        sep = f"{Style.DIM}│{Style.RESET}"
        
        # Log area with strict truncation
        r_area_width = safe_width - left_width - 5
        if TUI.visible_len(r_content) > r_area_width:
            r_content = r_content[:r_area_width-3] + "..."
            
        r_len = TUI.visible_len(r_content)
        r_pad = " " * max(0, r_area_width - r_len)
        
        # Proportional Scrollbar thumb
        scroll_r = f"{Style.DIM}│{Style.RESET}"
        if len(self.logs) > available_height:
            thumb_size = max(1, int(available_height * (available_height / len(self.logs))))
            max_offset = len(self.logs) - available_height
            progress = self.log_offset / max_offset
            start_pos = int(progress * (available_height - thumb_size))
            
            if start_pos <= i < start_pos + thumb_size:
                scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}"
        elif len(self.logs) > 0:
            # If everything fits, show a full bar
            scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}"
        
        row = f"{l_content}{l_pad} {sep} {r_content}{r_pad} {scroll_r}"
        
        # Modal Overlay
        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            current_y = i + 4 # Title(1) + Subtitle(1) + Spacer(1) + 1
            if m_y <= current_y < (m_y + len(m_lines)):
                m_idx = current_y - m_y
                modal_line = m_lines[m_idx]
                
                # Simple string replacement for overlay
                # Build a new line: [PAD] [MODAL] [PAD]
                m_v_len = TUI.visible_len(modal_line)
                row = " " * m_x + modal_line + " " * max(0, safe_width + 2 - m_x - m_v_len)
                
        print(row)

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
                    self.render()
                
                def input_handler():
                    # select.select is now inside System.run, so this is called when stdin is ready
                    key = TUI.get_key()
                    if not self.modal:
                        if key in [Keys.Q, Keys.ESC]:
                            self.modal = ConfirmModal("STOP INSTALLATION", "Finish current task and stop?")
                    else:
                        res = self.modal.handle_input(key)
                        if res == "YES":
                            self.is_cancelled = True
                            self.modal = None
                        elif res == "NO":
                            self.modal = None

                # Execute with dual monitoring (logs + keyboard)
                success = func(ovr, callback=live_callback, input_callback=input_handler)
                self.status[mod.id][task_type] = 'success' if success else 'error'
                self.results[mod.id][task_type] = success
                
                if not success and task_type == 'pkg':
                    self.status[mod.id]['dots'] = 'skipped'
                    break

        self.is_finished = True
        self.modal = SummaryModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
        
        while True:
            self.render()
            key = TUI.get_key()
            if self.modal:
                action = self.modal.handle_input(key)
                if action == "FINISH": return "WELCOME"
                if action == "CLOSE": self.modal = None
            else:
                if key == Keys.ENTER: return "WELCOME"
                if key == Keys.Q: sys.exit(0)
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
