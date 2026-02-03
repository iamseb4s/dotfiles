import shutil
from core.tui import TUI, Keys, Style, Theme
from core.screens.shared_modals import BaseModal

class OptionsModal(BaseModal):
    """
    Floating window for package-specific installation options.
    Features a dashboard layout with smart navigation and split alignment.
    """
    # UI Symbols
    SYM_EDIT, SYM_RADIO, SYM_RADIO_OFF, SYM_CHECK = "✎", "●", "○", "[■]"

    def __init__(self, module, current_overrides=None):
        super().__init__(f" PACKAGE OPTIONS: {module.label.upper()} ", width=68)
        self.mod = module
        # Determine if module has usable dotfiles configuration
        self.has_dotfiles = module.has_usable_dotfiles()
        
        # Internal state
        self.package_name = current_overrides.get('package_name', module.get_package_name()) if current_overrides else module.get_package_name()
        self.install_package = current_overrides.get('install_package', True) if current_overrides else True
        self.install_dotfiles = (current_overrides.get('install_dotfiles', True) if current_overrides else True) and self.has_dotfiles
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
        self.editing_field = None # 'package_name' or 'stow_target'
        self.text_cursor_pos = 0
        self.old_value = ""

    def render(self):
        """Draws the dashboard modal with margins and centered managers."""
        content_width = self.width - 10 
        inner_lines = [""] # Top spacer
        
        def draw_row(idx, label, value, is_dim=False, is_main=False):
            is_focused = (self.focus_idx == idx)
            style = Style.highlight() if is_focused else (Style.muted() if is_dim else Style.normal())
            bold = Style.BOLD if is_focused or is_main else ""
            
            # Hierarchical styling
            display_label = label.upper() if is_main else f"╰─ {label}"
            prefix = "    "
            
            hint = ""
            if is_focused:
                h = {0: "SPACE to toggle", 1: "E to edit", 3: "SPACE to toggle", 4: "E to edit"}.get(idx, "")
                if h: hint = f" {Style.muted()}{h}{Style.RESET}{style}{bold}"
            
            label_styled = f"{style}{bold}{display_label}{Style.RESET}{hint}"
            value_styled = f"{style}{bold}{value}{Style.RESET}"
            return f"{prefix}{TUI.split_line(label_styled, value_styled, content_width)}"

        # 0. Install Package
        package_toggle = f"YES {self.SYM_CHECK}" if self.install_package else "NO [ ]"
        inner_lines.append(draw_row(0, "Install Package", package_toggle, is_main=True))
        
        # 1. Package Name
        is_package_name_dim = not self.install_package; name_val = self.package_name
        if self.editing_field == 'package_name':
            pre, char, post = name_val[:self.text_cursor_pos], name_val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", name_val[self.text_cursor_pos+1:]
            name_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(1, "Package Name", f"{self.SYM_EDIT} [ {name_val} ]", is_dim=is_package_name_dim))
        
        # 2. Manager (Grid Layout)
        is_manager_focused = (self.focus_idx == 2)
        manager_label_style = Style.highlight() if is_manager_focused else (Style.muted() if is_package_name_dim else Style.normal())
        manager_hint = f" {Style.muted()}h/l to select{Style.RESET}" if is_manager_focused else ""
        inner_lines.append(f"    {manager_label_style}╰─ Package Manager:{Style.RESET}{manager_hint}")
        
        manager_items = []
        for manager in self.managers:
            is_selected = (self.selected_manager == manager); mark = self.SYM_RADIO if is_selected else self.SYM_RADIO_OFF
            if is_manager_focused: item = f"{Style.highlight() + Style.BOLD if is_selected else Style.muted()}{mark} {manager}{Style.RESET}"
            elif is_package_name_dim: item = f"{Style.muted()}{mark} {manager}{Style.RESET}"
            else: item = f"{Style.success() if is_selected else Style.muted()}{mark} {manager}{Style.RESET}"
            manager_items.append(item)
        
        managers_raw = "    ".join(manager_items); manager_padding = (content_width - TUI.visible_len(managers_raw)) // 2
        inner_lines.append(f"{' ' * max(0, manager_padding + 4)}{managers_raw}")
        inner_lines.append("") # Spacer
        
        # 3. Deploy Config
        dotfiles_toggle = f"YES {self.SYM_CHECK}" if self.install_dotfiles else "NO [ ]"
        dot_label = "Copy Configuration Files" if self.mod.id == "refind" else "Deploy Config (Stow)"
        inner_lines.append(draw_row(3, dot_label, dotfiles_toggle, is_dim=not self.has_dotfiles, is_main=True))
        
        # 4. Target Path
        is_target_path_dim = not (self.has_dotfiles and self.install_dotfiles); path_val = self.stow_target
        if self.editing_field == 'stow_target':
            pre = path_val[:self.text_cursor_pos]
            char = path_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
            post = path_val[self.text_cursor_pos+1:]
            path_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{Style.highlight()}{Style.BOLD}{post}"
        inner_lines.append(draw_row(4, "Target Path", f"{self.SYM_EDIT} [ {path_val} ]", is_dim=is_target_path_dim))

        inner_lines.extend(["", ""])
        hint = "ENTER: Accept   Q: Cancel"
        inner_lines.append(f"{' ' * ((self.width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}")
        
        return self._get_layout(inner_lines)

    def handle_input(self, key):
        """Processes navigation and dashboard inputs with smart skipping."""
        if self.editing_field: return self._handle_editing(key)
        if key in [Keys.Q, Keys.Q_UPPER, Keys.ESC]: return "CANCEL"
        if key == Keys.ENTER: return "ACCEPT"

        # Determine reachable fields
        r = [0]
        if self.install_package: r.extend([1, 2])
        if self.has_dotfiles:
            r.append(3)
            if self.install_dotfiles: r.append(4)

        if key in [Keys.UP, Keys.K, Keys.DOWN, Keys.J]:
            curr = r.index(self.focus_idx) if self.focus_idx in r else 0
            self.focus_idx = r[(curr + (1 if key in [Keys.DOWN, Keys.J] else -1)) % len(r)]
        elif key == Keys.SPACE:
            if self.focus_idx == 0: self.install_package = not self.install_package
            elif self.focus_idx == 3 and self.has_dotfiles: self.install_dotfiles = not self.install_dotfiles
        elif key in [ord('e'), ord('E')]:
            if self.focus_idx == 1 and self.install_package: self._start_edit('package_name')
            elif self.focus_idx == 4 and self.has_dotfiles and self.install_dotfiles: self._start_edit('stow_target')
        elif key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L] and self.focus_idx == 2 and self.install_package:
            try:
                idx = self.managers.index(self.selected_manager)
                step = 1 if key in [Keys.RIGHT, Keys.L] else -1
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
            'package_name': self.package_name, 'manager': self.selected_manager,
            'install_package': self.install_package, 'install_dotfiles': self.install_dotfiles,
            'stow_target': self.stow_target
        }
