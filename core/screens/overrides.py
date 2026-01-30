import shutil
import os
from core.tui import TUI, Keys, Style, Theme

class OverrideModal:
    """
    Floating window for package-specific installation overrides.
    Features a dashboard layout with smart navigation and split alignment.
    """
    def __init__(self, module, current_overrides=None):
        self.mod = module
        # Determine if module has dotfiles configuration
        self.has_dots = module.stow_pkg is not None
        
        # Internal state
        self.pkg_name = current_overrides.get('pkg_name', module.get_package_name()) if current_overrides else module.get_package_name()
        self.install_pkg = current_overrides.get('install_pkg', True) if current_overrides else True
        self.install_dots = current_overrides.get('install_dots', True) if current_overrides else True
        self.stow_target = current_overrides.get('stow_target', module.stow_target) if current_overrides else module.stow_target
        
        # Resolve available managers
        self.managers = []
        if isinstance(module.manager, dict):
            # 1. Add all managers defined in the module's dictionary
            self.managers = list(set(module.manager.values()))
        else:
            self.managers = [module.manager]
            
        # 2. Always ensure the native system manager is an option
        native_manager = module.get_manager()
        if native_manager not in self.managers:
            self.managers.append(native_manager)
            
        self.managers.sort()
            
        # 3. Resolve current selection (prioritize existing override)
        if current_overrides and 'manager' in current_overrides:
            self.selected_manager = current_overrides['manager']
        else:
            self.selected_manager = native_manager
        
        # UI Focus: 0:Install, 1:Name, 2:Manager, 3:DeployConfig, 4:TargetPath
        self.focus_idx = 0
        self.editing_field = None # 'pkg_name' or 'stow_target'
        self.text_cursor_pos = 0
        self.old_value = ""

    def render(self):
        """Draws the dashboard modal with margins and centered managers."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        width = 68
        # Internal width with 4 spaces margin on each side (4 left + 4 right = 8)
        content_width = width - 10 
        
        inner_lines = [""] # Top spacer
        
        def draw_row(idx, label, value, is_dim=False):
            is_focused = (self.focus_idx == idx)
            # Baseline style
            if is_focused:
                row_style = Style.highlight()
            elif is_dim:
                row_style = Style.muted()
            else:
                row_style = Style.normal()
                
            bold = Style.BOLD if is_focused else ""
            line = TUI.split_line(label, value, content_width)
            return f"    {row_style}{bold}{line}{Style.RESET}"

        # 0. Install Package
        pkg_toggle = "YES [■]" if self.install_pkg else "NO [ ]"
        inner_lines.append(draw_row(0, "Install Package", pkg_toggle))
        
        # 1. Package Name
        is_name_dim = not self.install_pkg
        name_val = self.pkg_name
        if self.editing_field == 'pkg_name':
            pre = name_val[:self.text_cursor_pos]
            char = name_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
            post = name_val[self.text_cursor_pos+1:]
            name_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(1, "Package Name", f"✎ [ {name_val} ]", is_dim=is_name_dim))
        
        # 2. Manager (Grid Layout)
        is_mgr_focused = (self.focus_idx == 2)
        if is_mgr_focused:
            mgr_label_style = Style.highlight() + Style.BOLD
        elif is_name_dim:
            mgr_label_style = Style.muted()
        else:
            mgr_label_style = Style.normal()
            
        inner_lines.append(f"    {mgr_label_style}Package Manager:{Style.RESET}")
        
        mgr_items = []
        for mgr in self.managers:
            is_sel = (self.selected_manager == mgr)
            mark = "●" if is_sel else "○"
            
            # Unified color logic: Focus overrides state color
            if is_mgr_focused:
                # Highlight ONLY the selected one when row is focused
                if is_sel:
                    item = f"{Style.highlight()}{Style.BOLD}{mark} {mgr}{Style.RESET}"
                else:
                    item = f"{Style.muted()}{mark} {mgr}{Style.RESET}"
            elif is_name_dim:
                # Row is disabled - extreme dim
                item = f"{Style.muted()}{mark} {mgr}{Style.RESET}"
            else:
                # Row is active but not focused
                m_color = Style.green() if is_sel else Style.muted()
                item = f"{m_color}{mark} {mgr}{Style.RESET}"
            mgr_items.append(item)
        
        mgrs_raw = "    ".join(mgr_items)
        mgr_vlen = TUI.visible_len(mgrs_raw)
        mgr_pad = (content_width - mgr_vlen) // 2
        mgr_prefix = " " * max(0, mgr_pad + 4)
        inner_lines.append(f"{mgr_prefix}{mgrs_raw}")
        
        inner_lines.append("") # Spacer
        
        # 3. Deploy Config
        dot_toggle = "YES [■]" if self.install_dots else "NO [ ]"
        dot_label = "Copy Configuration Files" if self.mod.id == "refind" else "Deploy Config (Stow)"
        is_dot_disabled = not self.has_dots
        inner_lines.append(draw_row(3, dot_label, dot_toggle, is_dim=is_dot_disabled))
        
        # 4. Target Path
        is_path_dim = not (self.has_dots and self.install_dots)
        path_val = self.stow_target
        if self.editing_field == 'stow_target':
            pre = path_val[:self.text_cursor_pos]
            char = path_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
            post = path_val[self.text_cursor_pos+1:]
            path_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(4, "Target Path", f"✎ [ {path_val} ]", is_dim=is_path_dim))

        inner_lines.append("") # Extra spacer
        inner_lines.append("") # Extra spacer
        
        # Sobere Hints
        h1 = "SPACE: Toggle   E: Edit   h/l: Select"
        h2 = "ENTER: Accept   Q: Cancel"
        
        h1_pad = (width - 2 - TUI.visible_len(h1)) // 2
        h2_pad = (width - 2 - TUI.visible_len(h2)) // 2
        
        inner_lines.append(f"{' ' * h1_pad}{Style.muted()}{h1}{Style.RESET}")
        inner_lines.append(f"{' ' * h2_pad}{Style.muted()}{h2}{Style.RESET}")

        
        height = len(inner_lines) + 2
        # Use clean title, TUI.create_container will add the borders correctly
        title_text = f"OVERRIDE: {self.mod.label.upper()}"
        lines = TUI.create_container(inner_lines, width, height, title=title_text, is_focused=True)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2


    def handle_input(self, key):
        """Processes navigation and dashboard inputs with smart skipping."""
        if self.editing_field:
            curr_val = getattr(self, self.editing_field)
            if key == Keys.ENTER:
                self.editing_field = None
            elif key == Keys.ESC:
                setattr(self, self.editing_field, self.old_value)
                self.editing_field = None
            elif key == Keys.BACKSPACE:
                if self.text_cursor_pos > 0:
                    new_val = curr_val[:self.text_cursor_pos-1] + curr_val[self.text_cursor_pos:]
                    setattr(self, self.editing_field, new_val)
                    self.text_cursor_pos -= 1
            elif key == Keys.DEL:
                if self.text_cursor_pos < len(curr_val):
                    new_val = curr_val[:self.text_cursor_pos] + curr_val[self.text_cursor_pos+1:]
                    setattr(self, self.editing_field, new_val)
            elif key in [Keys.LEFT, Keys.H]:
                self.text_cursor_pos = max(0, self.text_cursor_pos - 1)
            elif key in [Keys.RIGHT, Keys.L]:
                self.text_cursor_pos = min(len(curr_val), self.text_cursor_pos + 1)
            elif 32 <= key <= 126: # Printable chars
                new_val = curr_val[:self.text_cursor_pos] + chr(key) + curr_val[self.text_cursor_pos:]
                setattr(self, self.editing_field, new_val)
                self.text_cursor_pos += 1
            return None

        # Global Actions
        if key in [Keys.Q, Keys.Q_UPPER, Keys.ESC]: return "CANCEL"
        if key == Keys.ENTER: return "ACCEPT"

        # 1. Determine reachable fields based on toggles
        reachable = [0]
        if self.install_pkg:
            reachable.extend([1, 2])
        if self.has_dots:
            reachable.append(3)
            if self.install_dots:
                reachable.append(4)

        # 2. Infinite Circular Navigation
        if key in [Keys.UP, Keys.K]:
            try:
                curr_idx = reachable.index(self.focus_idx)
                self.focus_idx = reachable[(curr_idx - 1) % len(reachable)]
            except ValueError:
                self.focus_idx = 0
                
        elif key in [Keys.DOWN, Keys.J]:
            try:
                curr_idx = reachable.index(self.focus_idx)
                self.focus_idx = reachable[(curr_idx + 1) % len(reachable)]
            except ValueError:
                self.focus_idx = 0
        
        # Action: Toggle
        elif key == Keys.SPACE:
            if self.focus_idx == 0: self.install_pkg = not self.install_pkg
            elif self.focus_idx == 3 and self.has_dots: self.install_dots = not self.install_dots
        
        # Action: Edit
        elif key in [ord('e'), ord('E')]:
            if self.focus_idx == 1 and self.install_pkg:
                self.editing_field = 'pkg_name'
                self.old_value = self.pkg_name
                self.text_cursor_pos = len(self.pkg_name)
            elif self.focus_idx == 4 and self.has_dots and self.install_dots:
                self.editing_field = 'stow_target'
                self.old_value = self.stow_target
                self.text_cursor_pos = len(self.stow_target)

        # Action: Cycle Manager
        elif key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            if self.focus_idx == 2 and self.install_pkg:
                try:
                    curr_idx = self.managers.index(self.selected_manager)
                    step = 1 if key in [Keys.RIGHT, Keys.L] else -1
                    self.selected_manager = self.managers[(curr_idx + step) % len(self.managers)]
                except ValueError:
                    if self.managers: self.selected_manager = self.managers[0]
            
        return None

    def get_overrides(self):
        """Returns the dictionary of chosen overrides."""
        return {
            'pkg_name': self.pkg_name,
            'manager': self.selected_manager,
            'install_pkg': self.install_pkg,
            'install_dots': self.install_dots,
            'stow_target': self.stow_target
        }
