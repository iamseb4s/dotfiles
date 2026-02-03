import time
import shutil
import sys
from core.tui import TUI, Style, Keys, Theme
from core.screens.welcome import Screen
from core.screens.review import ReviewModal
from core.screens.shared_modals import ConfirmModal, PasswordModal

class InstallerScreen(Screen):
    """
    Advanced installation dashboard with split-view, real-time logs,
    and soft-cancellation support.
    """
    # UI Symbols
    SYM_PENDING, SYM_RUNNING, SYM_SUCCESS, SYM_ERROR = "○", "⟳", "✔", "✘"
    
    def __init__(self, modules, selected_ids, overrides=None):
        self.modules = modules
        self.task_queue = [module for module in modules if module.id in selected_ids]
        self.overrides = overrides or {}
        self.total_modules = len(self.task_queue)
        
        # Calculate total work units (package + dotfiles for each module)
        self.total_units = 0
        for module in self.task_queue:
            override = self.overrides.get(module.id, {})
            if override.get('install_package', True): self.total_units += 1
            if module.has_usable_dotfiles() and override.get('install_dotfiles', True): self.total_units += 1
        
        # Execution State
        self.current_module_index = -1
        self.completed_units = 0
        self.current_unit_progress = 0.0
        self.results = {} # {module_id: {'package': bool, 'dotfiles': bool}}
        self.status = {}  # {module_id: {'package': 'pending', 'dotfiles': 'pending'}}
        for module in self.task_queue:
            self.status[module.id] = {'package': 'pending', 'dotfiles': 'pending'}
            # Initialize results as None (not attempted)
            self.results[module.id] = {'package': None, 'dotfiles': None}
            
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

    def add_log(self, message):
        """Adds a line to the log buffer and handles auto-scroll."""
        if message is None:
            self.render() # Refresh call
            return
            
        self.logs.append(message)
        if self.auto_scroll:
            terminal_height = shutil.get_terminal_size().lines
            window_size = max(10, terminal_height - 7) - 4
            if len(self.logs) > window_size:
                self.log_offset = len(self.logs) - window_size

        now = time.time()
        if now - self.last_render_time > self.render_throttle:
            self.render()
            self.last_render_time = now

    def _get_scrollbar(self, total, visible, offset):
        """Returns scroll position and size for containers."""
        if total <= visible: return {'scroll_pos': None, 'scroll_size': None}
        sz = max(1, int(visible**2 / total))
        return {'scroll_pos': int((offset / (total - visible)) * (visible - sz)), 'scroll_size': sz}

    def render(self):
        """Draws the boxed split-view dashboard with bottom progress bar."""
        terminal_width, terminal_height = shutil.get_terminal_size()
        
        # 1. Header & Footer
        header = f"{Style.header()}{' DEPLOYMENT PROGRESS '.center(terminal_width)}{Style.RESET}"
        pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(pills, terminal_width - 4)
        available_height = max(10, terminal_height - 6 - len(footer_lines))
        left_width, right_width = int(terminal_width * 0.30), terminal_width - int(terminal_width * 0.30) - 1
        
        # 2. Panels
        left_panel = self._draw_task_tree(left_width, available_height)
        right_panel = self._draw_log_panel(right_width, available_height)
        main_content = TUI.stitch_containers(left_panel, right_panel, gap=1)
        
        # 3. Progress Bar
        bar_line = self._draw_progress_bar(terminal_width)
        
        # 4. Assembly
        buffer = [header, ""] + main_content + ["", bar_line, ""]
        for footer_line in footer_lines:
            footer_visible_len = TUI.visible_len(footer_line)
            left_padding = (terminal_width - footer_visible_len) // 2
            buffer.append(f"{' ' * left_padding}{footer_line}{' ' * (terminal_width - footer_visible_len - left_padding)}")

        if self.modal:
            modal_lines, modal_y, modal_x = self.modal.render()
            for index, line in enumerate(modal_lines):
                if 0 <= modal_y + index < len(buffer): 
                    buffer[modal_y + index] = TUI.overlay(buffer[modal_y + index], line, modal_x)
        
        buffer = TUI.draw_notifications(buffer)
        final_output = "\n".join([TUI.visible_ljust(line, terminal_width) for line in buffer[:terminal_height]])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        if self.is_finished: return [TUI.pill('ENTER', 'Results', Theme.GREEN), TUI.pill('Q', 'Finish', Theme.RED)]
        spin = self.spinner_chars[self.spinner_idx]
        if self.is_cancelled: return [TUI.pill(spin, 'CANCELING...', Theme.YELLOW)]
        return [TUI.pill(spin, 'INSTALLING...', Theme.YELLOW), TUI.pill('Q', 'Stop', Theme.RED)]

    def _draw_task_tree(self, width, height):
        lines = [""]
        for module in self.task_queue:
            module_status = self.status[module.id]
            is_current = (self.current_module_index >= 0 and self.task_queue[self.current_module_index].id == module.id)
            has_error = any(status == 'error' for status in module_status.values())
            is_done = all(status in ['success', 'skipped'] for status in module_status.values())
            
            icon = self.SYM_RUNNING if (is_current and not self.is_finished) else (self.SYM_ERROR if has_error else (self.SYM_SUCCESS if is_done else self.SYM_PENDING))
            status_color = Style.highlight() if is_current else (Style.success() if icon == self.SYM_SUCCESS else (Style.error() if icon == self.SYM_ERROR else Style.muted()))
            lines.append(f"  {status_color}{icon} {Style.BOLD if is_current else ''}{module.label}{Style.RESET}")
            
            override = self.overrides.get(module.id, {})
            has_dotfiles = module.has_usable_dotfiles()
            def get_sub_icon(status):
                if status == 'running': 
                    return f"{Style.highlight()}{self.spinner_chars[self.spinner_idx]}{Style.RESET}"
                return f"{Style.success() if status == 'success' else (Style.error() if status == 'error' else Style.muted())}{self.SYM_SUCCESS if status == 'success' else (self.SYM_ERROR if status == 'error' else self.SYM_PENDING)}{Style.RESET}"

            if override.get('install_package', True):
                connector = '├' if (has_dotfiles and override.get('install_dotfiles', True)) else '└'
                lines.append(f"  {Style.muted()}{connector} {get_sub_icon(module_status['package'])} {Style.normal()}Package{Style.RESET}")
            if has_dotfiles and override.get('install_dotfiles', True):
                lines.append(f"  {Style.muted()}└ {get_sub_icon(module_status['dotfiles'])} {Style.normal()}Dotfiles{Style.RESET}")
        
        return TUI.create_container(lines, width, height, title="TASKS", color="", is_focused=(not self.is_finished and not self.modal))

    def _draw_log_panel(self, width, height):
        window_size = height - 4
        if self.auto_scroll and len(self.logs) > window_size: 
            self.log_offset = len(self.logs) - window_size
        
        visible_logs = [""] + [f"  {Style.normal()}{line}{Style.RESET}" for line in self.logs[self.log_offset : self.log_offset + window_size]] + [""]
        scrollbar = self._get_scrollbar(len(self.logs), height - 2, self.log_offset)
        return TUI.create_container(visible_logs, width, height, title="LOGS", color="", is_focused=(self.is_finished and not self.modal), scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _draw_progress_bar(self, terminal_width):
        progress = (self.completed_units + self.current_unit_progress) / self.total_units if self.total_units > 0 else 0
        if self.is_finished: 
            progress = 1
            
        bar_width = int(terminal_width * 0.5)
        filled_length = int(bar_width * progress)
        status_color = Style.highlight() if not self.is_cancelled else Style.error()
        
        bar = f"{status_color}{'█' * filled_length}{Style.muted()}{'░' * (bar_width - filled_length)}{Style.RESET}"
        percentage_text = f"{Style.normal()}{Style.BOLD} {int(progress * 100)}% {Style.RESET}"
        
        bar_with_text = TUI.overlay(bar, percentage_text, (bar_width - TUI.visible_len(percentage_text)) // 2)
        progress_line = f"[ {bar_with_text} ]"
        return f"{' ' * ((terminal_width - TUI.visible_len(progress_line)) // 2)}{progress_line}"

    def run(self):
        """Main installation loop with real-time interruption handling."""
        # 1. Check if sudo is needed and prompt
        needs_sudo = False
        for module in self.task_queue:
            override = self.overrides.get(module.id, {})
            if override.get('install_package', True):
                needs_sudo = True
                break
        
        self.password = None
        if needs_sudo:
            self.modal = PasswordModal()
            while True:
                self.render()
                key = TUI.get_key(blocking=True)
                if key is None: continue
                res = self.modal.handle_input(key)
                if isinstance(res, tuple) and res[0] == "SUBMIT":
                    self.password = res[1]
                    self.modal = None
                    break
                elif res == "CANCEL":
                    return "SELECTOR"

        # 2. Execution Loop
        for module_index, module in enumerate(self.task_queue):
            if self.is_cancelled: 
                break
            
            self.current_module_index = module_index
            override = self.overrides.get(module.id, {})
            do_package = override.get('install_package', True)
            do_dotfiles = override.get('install_dotfiles', True) if module.has_usable_dotfiles() else False
            
            # Sub-tasks execution
            tasks = []
            if do_package: 
                tasks.append(('package', module.install))
            else: 
                self.status[module.id]['package'] = 'skipped'
            
            if do_dotfiles: 
                tasks.append(('dotfiles', module.configure))
            else: 
                self.status[module.id]['dotfiles'] = 'skipped'

            for task_type, func in tasks:
                if self.is_cancelled: 
                    break
                self.status[module.id][task_type], self.current_unit_progress = 'running', 0.0
                
                def live_callback(log_line):
                    self.add_log(log_line)
                    self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
                    self.current_unit_progress = min(0.95, self.current_unit_progress + 0.005)
                    self._input_step()
                
                success = func(override, callback=live_callback, input_callback=self._input_step, password=self.password)
                self.status[module.id][task_type] = ('success' if success else 'error')
                self.results[module.id][task_type] = success
                self.completed_units += 1
                self.current_unit_progress = 0.0
                
                if not success and task_type == 'package': 
                    self.status[module.id]['dotfiles'] = 'skipped'
                    break

        self.is_finished = True
        # Always force ReviewModal on completion, overwriting any pending ConfirmModal
        active_module_ids = [module.id for module in self.task_queue]
        self.modal = ReviewModal(self.modules, active_module_ids, self.overrides, self.results)
        
        while True:
            self.render()
            key = TUI.get_key(blocking=True)
            if key is None: continue
            res = self.handle_input(key)
            if res: return res

    def _input_step(self):
        key = TUI.get_key()
        if key is None: return
        if key == Keys.RESIZE: TUI.clear_screen(); self.render(); return
        
        if not self.modal:
            if key in [Keys.Q, Keys.Q_UPPER]: self.modal = ConfirmModal("STOP INSTALLATION", "Finish current task and stop?")
        else:
            res = self.modal.handle_input(key)
            if res == "YES": self.is_cancelled, self.modal = True, None; TUI.push_notification("Stopped by user", "ERROR")
            elif res == "NO": self.modal = None
        self.render()

    def handle_input(self, key):
        if key == Keys.RESIZE: TUI.clear_screen(); return None
        if self.modal:
            action = self.modal.handle_input(key)
            if action == "FINISH": return "WELCOME"
            if action in ["CLOSE", "NO", "CANCEL"]: self.modal = None
            return None

        if key == Keys.ENTER:
            active_module_ids = [module.id for module in self.task_queue]
            self.modal = ReviewModal(self.modules, active_module_ids, self.overrides, self.results)
        elif key in [Keys.Q, Keys.Q_UPPER]:
            if self.is_finished: return "WELCOME"
            self.modal = ConfirmModal("EXIT", "Are you sure you want to stop?")
        
        window_height = max(10, shutil.get_terminal_size().lines - 7)
        max_offset = max(0, len(self.logs) - (window_height - 4))
        if key == Keys.PGUP: 
            self.auto_scroll, self.log_offset = False, max(0, self.log_offset - 5)
        elif key == Keys.PGDN:
            self.log_offset = min(max_offset, self.log_offset + 5)
            if self.log_offset >= max_offset: 
                self.auto_scroll = True
        return None
