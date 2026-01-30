import shutil
from core.tui import TUI, Keys, Style, Theme
from core.screens.shared_modals import BaseModal

class OverrideModal(BaseModal):
    """
    Floating window for package-specific installation overrides.
    Features a dashboard layout with smart navigation and split alignment.
    """
    # UI Symbols
    SYM_EDIT, SYM_RADIO, SYM_RADIO_OFF, SYM_CHECK = "✎", "●", "○", "[■]"

    def __init__(self, module, current_overrides=None):
        super().__init__(f"OVERRIDE: {module.label.upper()}", width=68)
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
        content_width = self.width - 10 
        inner_lines = [""] # Top spacer
        
        def draw_row(idx, label, value, is_dim=False):
            is_focused = (self.focus_idx == idx)
            style = Style.highlight() if is_focused else (Style.muted() if is_dim else Style.normal())
            bold = Style.BOLD if is_focused else ""
            return f"    {style}{bold}{TUI.split_line(label, value, content_width)}{Style.RESET}"

        # 0. Install Package
        pkg_toggle = f"YES {self.SYM_CHECK}" if self.install_pkg else "NO [ ]"
        inner_lines.append(draw_row(0, "Install Package", pkg_toggle))
        
        # 1. Package Name
        is_name_dim = not self.install_pkg; name_val = self.pkg_name
        if self.editing_field == 'pkg_name':
            pre, char, post = name_val[:self.text_cursor_pos], name_val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", name_val[self.text_cursor_pos+1:]
            name_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(1, "Package Name", f"{self.SYM_EDIT} [ {name_val} ]", is_dim=is_name_dim))
        
        # 2. Manager (Grid Layout)
        is_mgr_f = (self.focus_idx == 2)
        m_lbl_style = Style.highlight() + Style.BOLD if is_mgr_f else (Style.muted() if is_name_dim else Style.normal())
        inner_lines.append(f"    {m_lbl_style}Package Manager:{Style.RESET}")
        
        mgr_items = []
        for mgr in self.managers:
            is_sel = (self.selected_manager == mgr); mark = self.SYM_RADIO if is_sel else self.SYM_RADIO_OFF
            if is_mgr_f: item = f"{Style.highlight() + Style.BOLD if is_sel else Style.muted()}{mark} {mgr}{Style.RESET}"
            elif is_name_dim: item = f"{Style.muted()}{mark} {mgr}{Style.RESET}"
            else: item = f"{Style.green() if is_sel else Style.muted()}{mark} {mgr}{Style.RESET}"
            mgr_items.append(item)
        
        mgrs_raw = "    ".join(mgr_items); mgr_pad = (content_width - TUI.visible_len(mgrs_raw)) // 2
        inner_lines.append(f"{' ' * max(0, mgr_pad + 4)}{mgrs_raw}")
        inner_lines.append("") # Spacer
        dot_toggle = f"YES {self.SYM_CHECK}" if self.install_dots else "NO [ ]"
        dot_label = "Copy Configuration Files" if self.mod.id == "refind" else "Deploy Config (Stow)"
        inner_lines.append(draw_row(3, dot_label, dot_toggle, is_dim=not self.has_dots))
        
        # 4. Target Path
        is_path_dim = not (self.has_dots and self.install_dots); path_val = self.stow_target
        if self.editing_field == 'stow_target':
            pre, char, post = path_val[:self.text_cursor_pos], path_val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", path_val[self.text_cursor_pos+1:]
            path_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(4, "Target Path", f"{self.SYM_EDIT} [ {path_val} ]", is_dim=is_path_dim))

        inner_lines.extend(["", ""])
        h1, h2 = "SPACE: Toggle   E: Edit   h/l: Select", "ENTER: Accept   Q: Cancel"
        for h in [h1, h2]:
            inner_lines.append(f"{' ' * ((self.width - 2 - TUI.visible_len(h)) // 2)}{Style.muted()}{h}{Style.RESET}")
        
        return self._get_layout(inner_lines)

    def handle_input(self, key):
        """Processes navigation and dashboard inputs with smart skipping."""
        if self.editing_field: return self._handle_editing(key)
        if key in [Keys.Q, Keys.Q_UPPER, Keys.ESC]: return "CANCEL"
        if key == Keys.ENTER: return "ACCEPT"

        # 1. Determine reachable fields based on toggles
        r = [0]
        if self.install_pkg: r.extend([1, 2])
        if self.has_dots:
            r.append(3)
            if self.install_dots: r.append(4)

        if key in [Keys.UP, Keys.K, Keys.DOWN, Keys.J]:
            curr = r.index(self.focus_idx) if self.focus_idx in r else 0
            self.focus_idx = r[(curr + (1 if key in [Keys.DOWN, Keys.J] else -1)) % len(r)]
        elif key == Keys.SPACE:
            if self.focus_idx == 0: self.install_pkg = not self.install_pkg
            elif self.focus_idx == 3 and self.has_dots: self.install_dots = not self.install_dots
        elif key in [ord('e'), ord('E')]:
            if self.focus_idx == 1 and self.install_pkg: self._start_edit('pkg_name')
            elif self.focus_idx == 4 and self.has_dots and self.install_dots: self._start_edit('stow_target')
        elif key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L] and self.focus_idx == 2 and self.install_pkg:
            try:
                idx = self.managers.index(self.selected_manager); step = 1 if key in [Keys.RIGHT, Keys.L] else -1
                self.selected_manager = self.managers[(idx + step) % len(self.managers)]
            except: self.selected_manager = self.managers[0] if self.managers else self.selected_manager
        return None

    def _start_edit(self, field):
        self.editing_field = field; self.old_value = getattr(self, field); self.text_cursor_pos = len(self.old_value)

    def _handle_editing(self, key):
        f = self.editing_field
        if not f: return None
        v = getattr(self, f)
        if key == Keys.ENTER: self.editing_field = None
        elif key == Keys.ESC: setattr(self, f, self.old_value); self.editing_field = None
        elif key == Keys.BACKSPACE and self.text_cursor_pos > 0:
            setattr(self, f, v[:self.text_cursor_pos-1] + v[self.text_cursor_pos:]); self.text_cursor_pos -= 1
        elif key == Keys.DEL and self.text_cursor_pos < len(v):
            setattr(self, f, v[:self.text_cursor_pos] + v[self.text_cursor_pos+1:])
        elif key in [Keys.LEFT, Keys.H]: self.text_cursor_pos = max(0, self.text_cursor_pos - 1)
        elif key in [Keys.RIGHT, Keys.L]: self.text_cursor_pos = min(len(v), self.text_cursor_pos + 1)
        elif 32 <= key <= 126:
            setattr(self, f, v[:self.text_cursor_pos] + chr(key) + v[self.text_cursor_pos:]); self.text_cursor_pos += 1
        return None

    def get_overrides(self):
        """Returns the dictionary of chosen overrides."""
        return {
            'pkg_name': self.pkg_name, 'manager': self.selected_manager,
            'install_pkg': self.install_pkg, 'install_dots': self.install_dots,
            'stow_target': self.stow_target
        }
