import shutil
from datetime import datetime
from modules.base import Module
from core.tui import TUI, Keys, Style, Theme

class BaseModal:
    """Base class for all modals to centralize layout and button logic."""
    def __init__(self, title, width=64):
        self.title = title
        self.width = width

    def _get_layout(self, inner_lines, scroll_pos=None, scroll_size=None):
        """Standardizes centering and container creation."""
        terminal_width, terminal_height = shutil.get_terminal_size()
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, self.width, height, title=self.title, color="", is_focused=True, 
                                    scroll_pos=scroll_pos, scroll_size=scroll_size)
        return lines, (terminal_height - height) // 2, (terminal_width - self.width) // 2

    def _render_button_row(self, buttons, focus_idx):
        """Unifies the visual style of button rows."""
        styled_buttons = []
        for index, button in enumerate(buttons):
            if index == focus_idx:
                styled_buttons.append(f"{Style.button_focused()}{button}{Style.RESET}")
            else:
                styled_buttons.append(f"{Style.muted()}[ {button.strip()} ]{Style.RESET}")
        button_row = "     ".join(styled_buttons)
        return f"{' ' * ((self.width - 2 - TUI.visible_len(button_row)) // 2)}{button_row}"

    def _get_scroll_params(self, total, visible, offset):
        """Generic scrollbar thumb position and size calculation."""
        if total <= visible: return None, None
        sz = max(1, int(visible**2 / total))
        return int((offset / (total - visible)) * (visible - sz)), sz

class DependencyModal(BaseModal):
    """Multi-select modal for module dependencies."""
    def __init__(self, modules: list[Module], current_deps):
        super().__init__("SELECT DEPENDENCIES", width=64)
        self.modules = sorted(modules, key=lambda m: str(m.label or m.id or ""))
        self.selected = set(current_deps)
        self.focus_idx = 0
        self.scroll_offset = 0

    def render(self):
        terminal_height = shutil.get_terminal_size().lines
        window_height = max(3, min(len(self.modules), terminal_height - 12))
        inner = [""]
        for i in range(window_height):
            module_index = self.scroll_offset + i
            if module_index < len(self.modules):
                module = self.modules[module_index]
                is_focused = (self.focus_idx == module_index)
                is_selected = (module.id in self.selected)
                
                mark = "[■]" if is_selected else "[ ]"
                label = f"{module.label} ({module.id})"
                style = Style.highlight() + Style.BOLD if is_focused else (Style.success() if is_selected else Style.muted())
                inner.append(f"    {style}{TUI.split_line(f'{mark}  {label}', '', self.width - 10)}{Style.RESET}")
        
        hint = "SPACE: Toggle   ENTER: Confirm   ESC: Cancel"
        inner.extend(["", f"{' ' * ((self.width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}"])
        scroll_position, scroll_size = self._get_scroll_params(len(self.modules), window_height, self.scroll_offset)
        return self._get_layout(inner, scroll_pos=scroll_position, scroll_size=scroll_size)

    def handle_input(self, key):
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % len(self.modules)
            if self.focus_idx < self.scroll_offset: self.scroll_offset = self.focus_idx
            elif self.focus_idx == len(self.modules)-1: 
                window_height = max(3, min(len(self.modules), shutil.get_terminal_size().lines - 12))
                self.scroll_offset = max(0, len(self.modules) - window_height)
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % len(self.modules)
            window_height = max(3, min(len(self.modules), shutil.get_terminal_size().lines - 12))
            if self.focus_idx >= self.scroll_offset + window_height: 
                self.scroll_offset = self.focus_idx - window_height + 1
            elif self.focus_idx == 0: self.scroll_offset = 0
        elif key == Keys.SPACE:
            module_id = self.modules[self.focus_idx].id
            if module_id in self.selected: 
                self.selected.remove(module_id)
            else: 
                self.selected.add(module_id)
        elif key == Keys.ENTER: return "CONFIRM"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

    def get_selected(self): return list(self.selected)

class WizardSummaryModal(BaseModal):
    """Final summary modal with 4-space margins."""
    def __init__(self, form_data, custom_tag="Custom...✎", custom_field="custom_category"):
        super().__init__("FINAL SUMMARY", width=60)
        self.form, self.custom_tag, self.custom_field = form_data, custom_tag, custom_field
        self.focus_idx = 0 # 0: SAVE, 1: CANCEL

    def render(self):
        inner = [""]
        def row(l, v): inner.append(f"    {Style.subtext1()}{l:<12}{Style.RESET} {Style.normal()}{v}{Style.RESET}")
        for k, l in [('id', 'ID'), ('label', 'Label'), ('manager', 'Manager')]: row(l, self.form[k])
        cat = self.form[self.custom_field] if self.form['category'] == self.custom_tag else self.form['category']
        row("Category", cat); row("Target", self.form['stow_target']); row("Manual", 'Yes' if self.form['is_incomplete'] else 'No')
        inner.extend(["", f"    {Style.subtext1()}Dependencies:{Style.RESET}"])
        if not self.form['dependencies']: inner.append(f"      {Style.muted()}None{Style.RESET}")
        else:
            for dep in sorted(self.form['dependencies']): inner.append(f"      {Style.muted()}● {Style.RESET}{dep}")
        inner.extend(["", self._render_button_row(["  SAVE  ", "  CANCEL  "], self.focus_idx), ""])
        return self._get_layout(inner)

    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.focus_idx = 1 - self.focus_idx
        elif key == Keys.ENTER: return "SAVE" if self.focus_idx == 0 else "CANCEL"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

class DraftSelectionModal(BaseModal):
    """Draft selection with 4-space margins."""
    def __init__(self, drafts):
        super().__init__("RESUME DRAFT?", width=64)
        self.drafts = drafts; self.focus_idx, self.scroll_offset = 0, 0

    def render(self):
        options = self.drafts + [("fresh", None, None)]
        terminal_height = shutil.get_terminal_size().lines
        window_height = max(3, min(len(options), terminal_height - 12))
        inner = [""]
        for i in range(window_height):
            index = self.scroll_offset + i
            if index < len(options):
                file_name, data, modification_time = options[index]
                is_focused = (self.focus_idx == index)
                if file_name == "fresh": 
                    label = "[ Start Fresh / New ]"
                else:
                    draft_id = data.get('id', 'unnamed')
                    draft_time = datetime.fromtimestamp(modification_time).strftime("%d %b %H:%M")
                    label = f"{draft_id} ({draft_time})"
                inner.append(f"    {Style.highlight() + Style.BOLD if is_focused else Style.normal()}{label}{Style.RESET}")
        hint = "ENTER: Select   X: Delete   ESC: Start Fresh"
        inner.extend(["", f"{' ' * ((self.width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}"])
        return self._get_layout(inner)

    def handle_input(self, key):
        options_length = len(self.drafts) + 1
        if key in [Keys.UP, Keys.K]: self.focus_idx = (self.focus_idx - 1) % options_length
        elif key in [Keys.DOWN, Keys.J]: self.focus_idx = (self.focus_idx + 1) % options_length
        elif key == Keys.ENTER: return ("LOAD", self.drafts[self.focus_idx]) if self.focus_idx < len(self.drafts) else "FRESH"
        elif key in [ord('x'), ord('X'), Keys.DEL] and self.focus_idx < len(self.drafts): return ("DELETE_REQ", self.drafts[self.focus_idx])
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "FRESH"
        return None

class ConfirmModal(BaseModal):
    """Simple confirmation modal for cancellation."""
    def __init__(self, title, message):
        super().__init__(title, width=54)
        self.message = message; self.focus_idx = 1 # Default NO

    def render(self):
        wrapped = TUI.wrap_text(self.message, self.width - 6)
        inner = [""] + [f"  {Style.normal()}{line.center(self.width - 6)}{Style.RESET}" for line in wrapped]
        inner.extend(["", self._render_button_row(["  YES  ", "  NO  "], self.focus_idx)])
        return self._get_layout(inner)

    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.focus_idx = 1 - self.focus_idx
        elif key == Keys.ENTER: return "YES" if self.focus_idx == 0 else "NO"
        elif key == Keys.ESC:
            if self.focus_idx != 1: self.focus_idx = 1
            else: return "NO"
        elif key in [Keys.Q, Keys.Q_UPPER]: return "NO"
        return None

class PasswordModal(BaseModal):
    """Secure modal for password entry (e.g., sudo)."""
    def __init__(self, title="PASSWORD REQUIRED", message="Please enter your sudo password:"):
        super().__init__(title, width=54)
        self.message = message
        self.password = ""

    def render(self):
        wrapped = TUI.wrap_text(self.message, self.width - 10)
        inner = [""] + [f"{Style.normal()}{line.center(self.width-2)}{Style.RESET}" for line in wrapped]
        
        # Password field
        pwd_display = "*" * len(self.password)
        # Style the field box with a fixed width for the input area
        field_width = self.width - 12
        field = f" {Style.highlight()}{pwd_display}{Style.RESET}" + " " * (field_width - len(pwd_display) - 1)
        inner.append(f"    {Style.muted()}╭{'─' * field_width}╮{Style.RESET}")
        inner.append(f"    {Style.muted()}│{Style.RESET}{field}{Style.muted()}│{Style.RESET}")
        inner.append(f"    {Style.muted()}╰{'─' * field_width}╯{Style.RESET}")
        
        hint = "ENTER: Confirm   ESC: Cancel"
        inner.extend(["", f"{' ' * ((self.width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}"])
        return self._get_layout(inner)

    def handle_input(self, key):
        if key == Keys.ENTER:
            return ("SUBMIT", self.password)
        elif key == Keys.ESC:
            return "CANCEL"
        elif key == Keys.BACKSPACE:
            self.password = self.password[:-1]
        elif 32 <= key <= 126: # Standard printable characters
            if len(self.password) < 32: # Safety limit
                self.password += chr(key)
        return None
