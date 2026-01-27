import time
import shutil
import sys
import select
from core.tui import TUI, Style, Keys, Theme
from core.screens.welcome import Screen
from core.screens.summary import SummaryModal

class ConfirmModal:
    """Simple confirmation modal for cancellation."""
    def __init__(self, title, message):
        self.title = title
        self.message = message
        self.focus_idx = 1 # Default to NO (Cancel)

    def render(self):
        width = 54 # Increased width
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Build Inner Lines with padding
        # Wrap message to ensure it doesn't hit edges
        wrapped = TUI.wrap_text(self.message, width - 6)
        inner_lines = [""]
        for line in wrapped:
            inner_lines.append(line.center(width - 2))
        inner_lines.append("")
        
        # Button labels
        btn_y = "  YES  "
        btn_n = "  NO  "
        
        purple_bg = Style.mauve(bg=True)
        
        if self.focus_idx == 0:
            y_styled = f"{purple_bg}{Style.crust()}{btn_y}{Style.RESET}"
            n_styled = f"[{btn_n.strip().center(len(btn_n)-2)}]"
        else:
            y_styled = f"[{btn_y.strip().center(len(btn_y)-2)}]"
            n_styled = f"{purple_bg}{Style.crust()}{btn_n}{Style.RESET}"
        
        btn_row = f"{y_styled}     {n_styled}"


        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        inner_lines.append(f"{' ' * padding}{btn_row}")
        
        # 2. Wrap in Container
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title=self.title, is_focused=True)
        
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        return lines, start_y, start_x


    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            self.focus_idx = 1 if self.focus_idx == 0 else 0
        elif key == Keys.ENTER:
            return "YES" if self.focus_idx == 0 else "NO"
        elif key == Keys.ESC:
            if self.focus_idx != 1:
                self.focus_idx = 1 # Focus NO
            else:
                return "NO"
        elif key in [Keys.Q, Keys.Q_UPPER]:
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
            # Initialize results as None (not attempted)
            self.results[m.id] = {'pkg': None, 'dots': None}
            
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
            available_height = max(10, term_height - 7)
            log_window_size = available_height - 4 # Margin top(1) + bottom(1)
            if len(self.logs) > log_window_size:
                self.log_offset = len(self.logs) - log_window_size

        # Throttled render during high-volume logs
        now = time.time()
        if now - self.last_render_time > self.render_throttle:
            self.render()
            self.last_render_time = now

    def render(self):
        """Draws the boxed split-view dashboard with bottom progress bar and integrated scrolls."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Header & Layout Metrics
        title = " DEPLOYING PACKAGES "
        bg_blue = Style.blue(bg=True)
        padding = (term_width - len(title)) // 2
        header_bar = f"{bg_blue}{Style.crust()}{' '*padding}{title}{' '*(term_width-padding-len(title))}{Style.RESET}"
        
        # Space for boxes: Top(2), Bottom(4)
        available_height = term_height - 7
        available_height = max(10, available_height)
        
        safe_width = term_width - 2
        left_width = int(safe_width * 0.30)
        right_width = safe_width - left_width - 1
        
        # 2. Build Left Content (Task Tree)
        left_lines = [""]
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
            
            color = Style.blue() if is_current else (Style.green() if icon == "✔" else (Style.red() if icon == "✘" else ""))
            left_lines.append(f"  {color}{icon} {mod.label}{Style.RESET}")
            
            ovr = self.overrides.get(mod.id, {})
            has_dots = mod.stow_pkg is not None
            
            def get_icon(s):
                if s == 'running': return self.spinner_chars[self.spinner_idx]
                return "✔" if s == 'success' else ("✘" if s == 'error' else "○")

            if ovr.get('install_pkg', True):
                left_lines.append(f"  {Style.DIM}{'├' if has_dots else '└'}{Style.RESET} {get_icon(state['pkg'])} Package")
            if has_dots and ovr.get('install_dots', True):
                left_lines.append(f"  {Style.DIM}└{Style.RESET} {get_icon(state['dots'])} Dotfiles")


        # 3. Build Right Content (Logs)
        log_window_size = available_height - 4
        if self.auto_scroll:
            if len(self.logs) > log_window_size:
                self.log_offset = len(self.logs) - log_window_size
        
        visible_logs = [""] + [f"  {l}" for l in self.logs[self.log_offset : self.log_offset + log_window_size]] + [""]
        
        # 4. Generate Boxes
        # Calculate Scroll Parameters for Logs
        l_scroll_pos, l_scroll_size = None, None
        if len(self.logs) > log_window_size:
            thumb_size = max(1, int((available_height - 2)**2 / (len(self.logs) + 2)))
            max_off = len(self.logs) - log_window_size
            prog = self.log_offset / max_off
            l_scroll_pos = int(prog * (available_height - 2 - thumb_size))
            l_scroll_size = thumb_size

        left_box = TUI.create_container(left_lines, left_width, available_height, title="TASKS", is_focused=(not self.is_finished and not self.modal))
        right_box = TUI.create_container(visible_logs, right_width, available_height, title="LOGS", is_focused=(self.is_finished and not self.modal), scroll_pos=l_scroll_pos, scroll_size=l_scroll_size)
        
        main_content = TUI.stitch_containers(left_box, right_box, gap=1)

        
        # 5. Progress Bar & Footer
        progress_val = self.current_idx / self.total if self.total > 0 else 0
        if self.is_finished: progress_val = 1
        bar_len = int(safe_width * 0.5)
        filled = int(bar_len * progress_val)
        bar_color = Style.green() if not self.is_cancelled else Style.red()
        bar_content = f"{bar_color}█" * filled + f"{Style.DIM}░" * (bar_len - filled) + Style.RESET
        
        if self.is_finished: footer = f"{TUI.pill('ENTER', 'Results', Theme.GREEN)}    {TUI.pill('Q', 'Finish', Theme.RED)}"
        elif self.is_cancelled: footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'CANCELING...', Theme.YELLOW)}"
        else: footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'INSTALLING...', Theme.YELLOW)}    {TUI.pill('Q', 'Stop', Theme.RED)}"

        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - bar_len - 10) // 2)}[ {bar_content} ] {int(progress_val*100)}%")
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(footer)) // 2)}{footer}")

        # Modal Overlay
        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            for i, m_line in enumerate(m_lines):
                target_y = m_y + i
                if 0 <= target_y < len(buffer):
                    buffer[target_y] = TUI.overlay(buffer[target_y], m_line, m_x)

        # Final buffer management to prevent terminal scroll
        final_output = "\n".join(buffer[:term_height])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def run(self):
        """Main installation loop with real-time interruption handling."""
        for idx, mod in enumerate(self.queue):
            if self.is_cancelled: break
            
            self.current_idx = idx
            ovr = self.overrides.get(mod.id, {})
            do_pkg = ovr.get('install_pkg', True)
            do_dots = ovr.get('install_dots', True) if mod.stow_pkg else False
            
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
                    input_handler()
                
                def input_handler():
                    # Check for keyboard input when select() says stdin is ready
                    key = TUI.get_key()
                    if key is None: return
                    
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        self.render()
                        return

                    if not self.modal:
                        if key in [Keys.Q, Keys.Q_UPPER]:
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
            
            if key == Keys.RESIZE:
                TUI.clear_screen()
                continue

            if self.modal:
                action = self.modal.handle_input(key)
                if action == "FINISH": return "WELCOME"
                if action in ["CLOSE", "NO", "CANCEL"]:
                    self.modal = None
            else:
                if key == Keys.ENTER:
                    if not self.modal:
                        self.modal = SummaryModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
                    continue
                if key in [Keys.Q, Keys.Q_UPPER]:
                    if self.is_finished:
                        return "WELCOME"
                    else:
                        self.modal = ConfirmModal("EXIT", "Are you sure you want to stop?")
                
                # Manual Scroll
                term_height = shutil.get_terminal_size().lines
                available_height = term_height - 7
                available_height = max(10, available_height)
                max_off = max(0, len(self.logs) - (available_height - 4))
                
                if key == Keys.PGUP:
                    self.auto_scroll = False
                    self.log_offset = max(0, self.log_offset - 5)
                if key == Keys.PGDN:
                    self.log_offset = min(max_off, self.log_offset + 5)
                    if self.log_offset >= max_off:
                        self.auto_scroll = True

    def handle_input(self, key):
        return None
