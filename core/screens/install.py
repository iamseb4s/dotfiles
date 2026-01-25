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
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Build Inner Lines
        inner_lines = ["", self.message.center(48), ""]
        
        btn_y = "  YES  "
        btn_n = "  NO   "
        
        purple_bg = Style.hex("#CBA6F7", bg=True)
        text_black = "\033[30m"
        
        if self.focus_idx == 0:
            btn_y = f"{purple_bg}{text_black}{btn_y}{Style.RESET}"
        else:
            btn_y = f"[{btn_y.strip()}]"
            
        if self.focus_idx == 1:
            btn_n = f"{purple_bg}{text_black}{btn_n}{Style.RESET}"
        else:
            btn_n = f"[{btn_n.strip()}]"
        
        btn_row = f"{btn_y}     {btn_n}"
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
            available_height = term_height - self.reserved_height
            if len(self.logs) > available_height:
                self.log_offset = len(self.logs) - available_height

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
        bg_blue = Style.hex("89B4FA", bg=True)
        text_black = "\033[30m"
        padding = (term_width - len(title)) // 2
        header_bar = f"{bg_blue}{text_black}{' '*padding}{title}{' '*(term_width-padding-len(title))}{Style.RESET}"
        
        # Space for boxes: Top(2), Bottom(4)
        available_height = term_height - 7
        available_height = max(10, available_height)
        
        safe_width = term_width - 2
        left_width = int(safe_width * 0.30)
        right_width = safe_width - left_width - 1
        
        # 2. Build Left Content (Task Tree)
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
            left_lines.append(f" {color}{icon} {mod.label}{Style.RESET}")
            
            ovr = self.overrides.get(mod.id, {})
            has_dots = mod.stow_pkg is not None
            
            def get_icon(s):
                if s == 'running': return self.spinner_chars[self.spinner_idx]
                return "✔" if s == 'success' else ("✘" if s == 'error' else "○")

            if ovr.get('install_pkg', True):
                left_lines.append(f" {Style.DIM}{'├' if has_dots else '└'}{Style.RESET} {get_icon(state['pkg'])} Package")
            if has_dots and ovr.get('install_dots', True):
                left_lines.append(f" {Style.DIM}└{Style.RESET} {get_icon(state['dots'])} Dotfiles")

        # 3. Build Right Content (Logs)
        if self.auto_scroll:
            if len(self.logs) > (available_height - 2):
                self.log_offset = len(self.logs) - (available_height - 2)
        
        visible_logs = self.logs[self.log_offset : self.log_offset + (available_height - 2)]
        
        # 4. Generate Boxes
        # Focus: Left during installation, Right if scrolling
        # Background boxes lose focus if a modal is visible
        left_box = TUI.create_container(left_lines, left_width, available_height, title="TASKS", is_focused=(not self.is_finished and not self.modal))
        right_box = TUI.create_container(visible_logs, right_width, available_height, title="LOGS", is_focused=(self.is_finished and not self.modal))
        
        # Integrated Scrollbar for Logs
        if len(self.logs) > (available_height - 2):
            max_off = len(self.logs) - (available_height - 2)
            prog = self.log_offset / max_off
            thumb_size = max(1, int((available_height - 2) * (available_height - 2) / len(self.logs)))
            start_pos = int(prog * (available_height - 2 - thumb_size))
            
            # Inject thumb into the right border of the right box
            for i in range(available_height - 2):
                is_focus = self.is_finished and not self.modal
                border_color = Style.hex("#CBA6F7") if is_focus else Style.hex("#585B70")
                thumb_color = Style.hex("#CBA6F7") if is_focus else Style.hex("#89B4FA")
                
                char = f"{thumb_color}┃{Style.RESET}" if start_pos <= i < start_pos + thumb_size else f"{border_color}│{Style.RESET}"
                
                # Replace the last character of the content line (the border)
                line = right_box[i+1]
                right_box[i+1] = line[:-10] + char + Style.RESET

        main_content = TUI.stitch_containers(left_box, right_box, gap=1)
        
        # 5. Progress Bar & Footer
        progress_val = self.current_idx / self.total if self.total > 0 else 0
        if self.is_finished: progress_val = 1
        bar_len = int(safe_width * 0.5)
        filled = int(bar_len * progress_val)
        bar_color = Style.hex("#55E6C1") if not self.is_cancelled else Style.hex("#FF6B6B")
        bar_content = f"{bar_color}█" * filled + f"{Style.DIM}░" * (bar_len - filled) + Style.RESET
        
        if self.is_finished: footer = f"{TUI.pill('ENTER', 'Finish', '#a6e3a1')}    {TUI.pill('R', 'Summary', '#FDCB6E')}    {TUI.pill('Q', 'Quit', '#f38ba8')}"
        elif self.is_cancelled: footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'CANCELING...', '#FDCB6E')}"
        else: footer = f"{TUI.pill(self.spinner_chars[self.spinner_idx], 'INSTALLING...', '#FDCB6E')}    {TUI.pill('Q/ESC', 'Stop', '#f38ba8')}"

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
                    # Every log line triggers a keyboard poll for instant Q/ESC detection
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
            
            if key == Keys.RESIZE:
                TUI.clear_screen()
                continue

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
                available_height = term_height - 7
                available_height = max(10, available_height)
                max_off = max(0, len(self.logs) - (available_height - 2))
                
                if key == Keys.PGUP:
                    self.auto_scroll = False
                    self.log_offset = max(0, self.log_offset - 5)
                if key == Keys.PGDN:
                    self.log_offset = min(max_off, self.log_offset + 5)
                    if self.log_offset >= max_off:
                        self.auto_scroll = True

    def handle_input(self, key):
        return None
