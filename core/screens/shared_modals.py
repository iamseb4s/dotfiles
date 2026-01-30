import shutil
from datetime import datetime
from modules.base import Module
from core.tui import TUI, Keys, Style, Theme

class DependencyModal:
    """Multi-select modal for module dependencies."""
    def __init__(self, modules: list[Module], current_deps):
        self.modules = sorted(modules, key=lambda m: str(m.label or m.id or ""))
        self.selected = set(current_deps)
        self.focus_idx = 0
        self.scroll_offset = 0

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 64
        content_width = width - 10
        available_content_height = term_height - 12
        
        max_rows = min(len(self.modules), available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""]
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(self.modules):
                mod = self.modules[idx]
                is_focused = (self.focus_idx == idx)
                is_selected = (mod.id in self.selected)
                
                mark = "[■]" if is_selected else "[ ]"
                label = f"{mod.label} ({mod.id})"
                
                if is_focused:
                    line = TUI.split_line(f"{mark}  {label}", "", content_width)
                    inner_lines.append(f"    {Style.highlight()}{Style.BOLD}{line}{Style.RESET}")
                else:
                    color = Style.green() if is_selected else Style.muted()
                    line = TUI.split_line(f"{mark}  {label}", "", content_width)
                    inner_lines.append(f"    {color}{line}{Style.RESET}")

        inner_lines.append("")
        hint = "SPACE: Toggle   ENTER: Confirm   ESC: Cancel"
        h_pad = (width - 2 - TUI.visible_len(hint)) // 2
        inner_lines.append(f"{' ' * h_pad}{Style.muted()}{hint}{Style.RESET}")
        
        scroll_pos, scroll_size = None, None
        if len(self.modules) > max_rows:
            thumb_size = max(1, int(max_rows**2 / len(self.modules)))
            max_off = len(self.modules) - max_rows
            prog = self.scroll_offset / max_off
            scroll_pos = 1 + int(prog * (max_rows - thumb_size))
            scroll_size = thumb_size

        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="SELECT DEPENDENCIES", is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % len(self.modules)
            if self.focus_idx < self.scroll_offset: self.scroll_offset = self.focus_idx
            if self.focus_idx == len(self.modules) - 1: # Wrap to bottom
                t_lines = shutil.get_terminal_size().lines
                max_rows = max(3, min(len(self.modules), t_lines - 12))
                self.scroll_offset = max(0, len(self.modules) - max_rows)
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % len(self.modules)
            t_lines = shutil.get_terminal_size().lines
            max_rows = max(3, min(len(self.modules), t_lines - 12))
            if self.focus_idx >= self.scroll_offset + max_rows: self.scroll_offset = self.focus_idx - max_rows + 1
            if self.focus_idx == 0: self.scroll_offset = 0
        elif key == Keys.SPACE:
            mid = self.modules[self.focus_idx].id
            if mid in self.selected: self.selected.remove(mid)
            else: self.selected.add(mid)
        elif key == Keys.ENTER: return "CONFIRM"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

    def get_selected(self):
        return list(self.selected)

class WizardSummaryModal:
    """Final summary modal with 4-space margins."""
    def __init__(self, form_data):
        self.form = form_data
        self.focus_idx = 0 # 0: SAVE, 1: CANCEL
        self.content_lines = self._build_content()

    def _build_content(self):
        lines = []
        def row(label, val): return f"{Style.subtext1()}{label:<12}{Style.RESET} {Style.normal()}{val}{Style.RESET}"
        lines.append(row("ID", self.form['id']))
        lines.append(row("Label", self.form['label']))
        lines.append(row("Manager", self.form['manager']))
        cat = self.form['custom_category'] if self.form['category'] == "Custom...✎" else self.form['category']
        lines.append(row("Category", cat))
        lines.append(row("Target", self.form['stow_target']))
        lines.append(row("Manual", 'Yes' if self.form['is_incomplete'] else 'No'))
        lines.append("")
        lines.append(f"{Style.subtext1()}Dependencies:{Style.RESET}")
        if not self.form['dependencies']:
            lines.append(f"  {Style.muted()}None{Style.RESET}")
        else:
            for dep in sorted(self.form['dependencies']):
                lines.append(f"  {Style.muted()}● {Style.RESET}{dep}")
        return lines

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 60
        inner_lines = [""]
        for l in self.content_lines: inner_lines.append(f"    {l}")
        inner_lines.append("")
        
        btn_s = "  SAVE  "
        btn_c = "  CANCEL  "
        if self.focus_idx == 0:
            s_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_s}{Style.RESET}"
            c_styled = f"{Style.muted()}[ {btn_c.strip()} ]{Style.RESET}"
        else:
            s_styled = f"{Style.muted()}[ {btn_s.strip()} ]{Style.RESET}"
            c_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_c}{Style.RESET}"
        
        btn_row = f"{s_styled}     {c_styled}"
        pad = (width - 2 - TUI.visible_len(btn_row)) // 2
        inner_lines.append(f"{' ' * pad}{btn_row}")
        inner_lines.append("")
        
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="FINAL SUMMARY", is_focused=True)
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.focus_idx = 1 if self.focus_idx == 0 else 0
        elif key == Keys.ENTER: return "SAVE" if self.focus_idx == 0 else "CANCEL"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

class DraftSelectionModal:
    """Draft selection with 4-space margins."""
    def __init__(self, drafts):
        self.drafts = drafts
        self.focus_idx = 0
        self.scroll_offset = 0

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 64
        options = self.drafts + [("fresh", None, None)]
        available_content_height = term_height - 12
        max_rows = min(len(options), available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""]
        
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(options):
                fname, data, mtime = options[idx]
                is_focused = (self.focus_idx == idx)
                
                if fname == "fresh":
                    label = "[ Start Fresh / New ]"
                else:
                    d_id = data.get('id', 'unnamed')
                    d_time = datetime.fromtimestamp(mtime).strftime("%d %b %H:%M")
                    label = f"{d_id} ({d_time})"
                
                style = Style.mauve() + Style.BOLD if is_focused else Style.text()
                inner_lines.append(f"    {style}{label}{Style.RESET}")

        inner_lines.append("")
        hint = "ENTER: Select   X: Delete   ESC: Start Fresh"
        inner_lines.append(f"{' ' * ((width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}")
        
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="RESUME DRAFT?", is_focused=True)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        opt_len = len(self.drafts) + 1
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % opt_len
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % opt_len
        elif key == Keys.ENTER:
            if self.focus_idx < len(self.drafts):
                return ("LOAD", self.drafts[self.focus_idx])
            return "FRESH"
        elif key in [ord('x'), ord('X'), Keys.DEL]:
            if self.focus_idx < len(self.drafts):
                return ("DELETE_REQ", self.drafts[self.focus_idx])
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]:
            return "FRESH"
        return None

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
            inner_lines.append(f"  {Style.normal()}{line.center(width - 6)}{Style.RESET}")
        inner_lines.append("")
        
        # Button labels
        btn_y = "  YES  "
        btn_n = "  NO  "
        
        if self.focus_idx == 0:
            y_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_y}{Style.RESET}"
            # Length of btn_y is 7. "[ YES ]" is also 7.
            n_styled = f"{Style.muted()}[ {btn_n.strip()} ]{Style.RESET}"
        else:
            y_styled = f"{Style.muted()}[ {btn_y.strip()} ]{Style.RESET}"
            n_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_n}{Style.RESET}"
        
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
