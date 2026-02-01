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
        self.queue = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides or {}
        self.total = len(self.queue)
        
        # Calculate total work units (pkg + dots for each module)
        self.total_units = 0
        for mod in self.queue:
            ovr = self.overrides.get(mod.id, {})
            if ovr.get('install_pkg', True): self.total_units += 1
            if mod.has_usable_dotfiles() and ovr.get('install_dots', True): self.total_units += 1
        
        # Execution State
        self.current_idx = -1
        self.completed_units = 0
        self.current_unit_progress = 0.0
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

    def add_log(self, message):
        """Adds a line to the log buffer and handles auto-scroll."""
        if message is None:
            self.render() # Refresh call
            return
            
        self.logs.append(message)
        if self.auto_scroll:
            th = shutil.get_terminal_size().lines
            win_sz = max(10, th - 7) - 4
            if len(self.logs) > win_sz:
                self.log_offset = len(self.logs) - win_sz

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
        tw, th = shutil.get_terminal_size()
        
        # 1. Header & Footer
        header = f"{Style.blue(bg=True)}{Style.crust()}{' DEPLOYMENT PROGRESS '.center(tw)}{Style.RESET}"
        pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(pills, tw - 4)
        avail_h = max(10, th - 6 - len(footer_lines))
        lw, rw = int(tw * 0.30), tw - int(tw * 0.30) - 1
        
        # 2. Panels
        left = self._draw_task_tree(lw, avail_h)
        right = self._draw_log_panel(rw, avail_h)
        main_content = TUI.stitch_containers(left, right, gap=1)
        
        # 3. Progress Bar
        bar_line = self._draw_progress_bar(tw)
        
        # 4. Assembly
        buffer = [header, ""] + main_content + ["", bar_line, ""]
        for fl in footer_lines:
            fv = TUI.visible_len(fl); lp = (tw - fv) // 2
            buffer.append(f"{' ' * lp}{fl}{' ' * (tw - fv - lp)}")

        if self.modal:
            ml, my, mx = self.modal.render()
            for i, line in enumerate(ml):
                if 0 <= my+i < len(buffer): buffer[my+i] = TUI.overlay(buffer[my+i], line, mx)
        
        buffer = TUI.draw_notifications(buffer)
        final = "\n".join([TUI.visible_ljust(l, tw) for l in buffer[:th]])
        sys.stdout.write("\033[H" + final + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        if self.is_finished: return [TUI.pill('ENTER', 'Results', Theme.GREEN), TUI.pill('Q', 'Finish', Theme.RED)]
        spin = self.spinner_chars[self.spinner_idx]
        if self.is_cancelled: return [TUI.pill(spin, 'CANCELING...', Theme.YELLOW)]
        return [TUI.pill(spin, 'INSTALLING...', Theme.YELLOW), TUI.pill('Q', 'Stop', Theme.RED)]

    def _draw_task_tree(self, w, h):
        lines = [""]
        for mod in self.queue:
            st = self.status[mod.id]
            is_curr = (self.current_idx >= 0 and self.queue[self.current_idx].id == mod.id)
            err = any(v == 'error' for v in st.values())
            done = all(v in ['success', 'skipped'] for v in st.values())
            
            icon = self.SYM_RUNNING if (is_curr and not self.is_finished) else (self.SYM_ERROR if err else (self.SYM_SUCCESS if done else self.SYM_PENDING))
            c = Style.highlight() if is_curr else (Style.green() if icon == self.SYM_SUCCESS else (Style.red() if icon == self.SYM_ERROR else Style.muted()))
            lines.append(f"  {c}{icon} {Style.BOLD if is_curr else ''}{mod.label}{Style.RESET}")
            
            ovr = self.overrides.get(mod.id, {})
            has_dots = mod.has_usable_dotfiles()
            def get_sub_icon(s):
                if s == 'running': return f"{Style.highlight()}{self.spinner_chars[self.spinner_idx]}{Style.RESET}"
                return f"{Style.green() if s == 'success' else (Style.red() if s == 'error' else Style.muted())}{self.SYM_SUCCESS if s == 'success' else (self.SYM_ERROR if s == 'error' else self.SYM_PENDING)}{Style.RESET}"

            if ovr.get('install_pkg', True):
                lines.append(f"  {Style.muted()}{'├' if (has_dots and ovr.get('install_dots', True)) else '└'} {get_sub_icon(st['pkg'])} {Style.normal()}Package{Style.RESET}")
            if has_dots and ovr.get('install_dots', True):
                lines.append(f"  {Style.muted()}└ {get_sub_icon(st['dots'])} {Style.normal()}Dotfiles{Style.RESET}")
        
        return TUI.create_container(lines, w, h, title="TASKS", color="", is_focused=(not self.is_finished and not self.modal))

    def _draw_log_panel(self, w, h):
        win_sz = h - 4
        if self.auto_scroll and len(self.logs) > win_sz: self.log_offset = len(self.logs) - win_sz
        vis_logs = [""] + [f"  {Style.normal()}{l}{Style.RESET}" for l in self.logs[self.log_offset : self.log_offset + win_sz]] + [""]
        sc = self._get_scrollbar(len(self.logs), h - 2, self.log_offset)
        return TUI.create_container(vis_logs, w, h, title="LOGS", color="", is_focused=(self.is_finished and not self.modal), scroll_pos=sc['scroll_pos'], scroll_size=sc['scroll_size'])

    def _draw_progress_bar(self, tw):
        prog = (self.completed_units + self.current_unit_progress) / self.total_units if self.total_units > 0 else 0
        if self.is_finished: prog = 1
        bw = int(tw * 0.5); filled = int(bw * prog)
        c = Style.highlight() if not self.is_cancelled else Style.red()
        bar = f"{c}{'█' * filled}{Style.muted()}{'░' * (bw - filled)}{Style.RESET}"
        perc = f"{Style.normal()}{Style.BOLD} {int(prog * 100)}% {Style.RESET}"
        bar_ovr = TUI.overlay(bar, perc, (bw - TUI.visible_len(perc)) // 2)
        line = f"[ {bar_ovr} ]"
        return f"{' ' * ((tw - TUI.visible_len(line)) // 2)}{line}"

    def run(self):
        """Main installation loop with real-time interruption handling."""
        # 1. Check if sudo is needed and prompt
        needs_sudo = False
        for mod in self.queue:
            ovr = self.overrides.get(mod.id, {})
            if ovr.get('install_pkg', True):
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
        for idx, mod in enumerate(self.queue):
            if self.is_cancelled: break
            
            self.current_idx = idx
            ovr = self.overrides.get(mod.id, {})
            do_pkg = ovr.get('install_pkg', True)
            do_dots = ovr.get('install_dots', True) if mod.has_usable_dotfiles() else False
            
            # Sub-tasks execution
            tasks = []
            if do_pkg: tasks.append(('pkg', mod.install))
            else: self.status[mod.id]['pkg'] = 'skipped'
            
            if do_dots: tasks.append(('dots', mod.configure))
            else: self.status[mod.id]['dots'] = 'skipped'

            for t_type, func in tasks:
                if self.is_cancelled: break
                self.status[mod.id][t_type], self.current_unit_progress = 'running', 0.0
                
                def live_cb(l):
                    self.add_log(l); self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
                    self.current_unit_progress = min(0.95, self.current_unit_progress + 0.005)
                    self._input_step()
                
                success = func(ovr, callback=live_cb, input_callback=self._input_step, password=self.password)
                self.status[mod.id][t_type], self.results[mod.id][t_type] = ('success' if success else 'error'), success
                self.completed_units += 1; self.current_unit_progress = 0.0
                if not success and t_type == 'pkg': self.status[mod.id]['dots'] = 'skipped'; break

        self.is_finished = True
        # Always force ReviewModal on completion, overwriting any pending ConfirmModal
        self.modal = ReviewModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
        
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
            self.modal = ReviewModal(self.modules, [m.id for m in self.queue], self.overrides, self.results)
        elif key in [Keys.Q, Keys.Q_UPPER]:
            if self.is_finished: return "WELCOME"
            self.modal = ConfirmModal("EXIT", "Are you sure you want to stop?")
        
        win_h = max(10, shutil.get_terminal_size().lines - 7)
        max_off = max(0, len(self.logs) - (win_h - 4))
        if key == Keys.PGUP: self.auto_scroll, self.log_offset = False, max(0, self.log_offset - 5)
        elif key == Keys.PGDN:
            self.log_offset = min(max_off, self.log_offset + 5)
            if self.log_offset >= max_off: self.auto_scroll = True
        return None
