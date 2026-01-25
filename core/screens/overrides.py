import shutil
import os
from core.tui import TUI, Keys, Style

class OverrideModal:
    """
    Floating window for package-specific installation overrides.
    Allows toggling bin/dots and selecting alternative package managers.
    """
    def __init__(self, module, current_overrides=None):
        self.mod = module
        # Determine if module has dotfiles configuration
        self.has_dots = module.stow_pkg is not None
        
        # Internal state
        self.pkg_name = current_overrides.get('pkg_name', module.get_package_name()) if current_overrides else module.get_package_name()
        self.install_pkg = current_overrides.get('install_pkg', True) if current_overrides else True
        self.install_dots = current_overrides.get('install_dots', True) if current_overrides else True
        
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


        
        # UI Focus: 0:Package, 1:Manager, 2:Dotfiles, 3:Accept, 4:Cancel
        self.focus_idx = 0
        self.editing_name = False

    def render(self):
        """Draws the modal on top of the existing screen."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Prepare Content and Measure Width
        title_text = f"OVERRIDE: {self.mod.label.upper()}"
        pkg_measure = f"> [ ] Install Package: '{self.pkg_name}' ✎"
        
        # Prepare managers line for measurement
        mgr_styled_items = []
        for mgr in self.managers:
            mark = "●" if self.selected_manager == mgr else "○"
            is_focused = (self.focus_idx == 1 and self.selected_manager == mgr)

            if is_focused:
                # Purple + BOLD for selection
                style = Style.hex("#CBA6F7") + Style.BOLD
                mgr_styled_items.append(f"{style}{mark} {mgr}{Style.RESET}")
            else:
                mgr_styled_items.append(f"{mark} {mgr}")
        
        mgr_content = "   ".join(mgr_styled_items)
        mgr_v_len = TUI.visible_len(mgr_content)
        
        # Determine optimal modal width
        width = max(54, len(title_text) + 10, TUI.visible_len(pkg_measure) + 6, mgr_v_len + 6)
        width = min(width, term_width - 4)
        
        # 2. Build Inner Lines (without borders)
        inner_lines = []
        inner_lines.append("") # Top spacer
        
        # Option 0: Package Toggle
        pkg_mark = "■" if self.install_pkg else " "
        is_focused = (self.focus_idx == 0)
        label = f"  [{pkg_mark}] Install Package: '{self.pkg_name}'"
        if self.editing_name: label += " ✎"
        
        if is_focused:
            style = Style.hex("#CBA6F7") + Style.BOLD
            inner_lines.append(f"{style}{label}{Style.RESET}")
        else:
            inner_lines.append(label)
        
        # Option 1: Managers
        if self.install_pkg:
            padding_total = width - 2 - mgr_v_len
            l_p = " " * (padding_total // 2)
            inner_lines.append(f"{l_p}{mgr_content}")
        else:
            inner_lines.append("")
            
        inner_lines.append("") # Spacer
        
        # Option 2: Dotfiles
        if self.has_dots:
            label_text = "Configure Dotfiles (Stow)"
            if self.mod.id == "refind": label_text = "Copy Configuration files"
            
            dot_mark = "■" if self.install_dots else " "
            is_focused = (self.focus_idx == 2)
            label = f"  [{dot_mark}] {label_text}"
            
            if is_focused:
                style = Style.hex("#CBA6F7") + Style.BOLD
                inner_lines.append(f"{style}{label}{Style.RESET}")
            else:
                inner_lines.append(label)
            inner_lines.append("")
        
        # Instructions
        instr = "(Press R to rename)" if self.focus_idx == 0 else ""
        inner_lines.append(f"{Style.DIM}{instr.center(width-2)}{Style.RESET}")
        
        # Buttons
        btn_acc = "  ACCEPT  "
        btn_can = "  CANCEL  "
        
        purple_bg = Style.hex("#CBA6F7", bg=True)
        text_black = "\033[30m"
        
        if self.focus_idx == 3:
            acc_styled = f"{purple_bg}{text_black}{btn_acc}{Style.RESET}"
        else:
            acc_styled = f"[{btn_acc.strip()}]"
            
        if self.focus_idx == 4:
            can_styled = f"{purple_bg}{text_black}{btn_can}{Style.RESET}"
        else:
            can_styled = f"[{btn_can.strip()}]"
        
        btn_row = f"{acc_styled}     {can_styled}"
        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        inner_lines.append(f"{' ' * padding}{btn_row}")

        # 3. Wrap in Container
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title=title_text, is_focused=True)
        
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        return lines, start_y, start_x

    def handle_input(self, key):
        """Internal logic for modal navigation."""
        if self.editing_name:
            if key == Keys.ENTER:
                self.editing_name = False
            elif key == Keys.BACKSPACE:
                self.pkg_name = self.pkg_name[:-1]
            elif 32 <= key <= 126: # Printable chars
                self.pkg_name += chr(key)
            return None

        # Modal close keys
        if key == Keys.ESC or key == Keys.Q:
            return "CANCEL"
            
        # Vertical Navigation
        if key in [Keys.UP, Keys.K]:
            if self.focus_idx in [3, 4]: # From buttons row
                self.focus_idx = 2 if self.has_dots else 0
            elif self.focus_idx == 2:
                self.focus_idx = 1 if self.install_pkg else 0
            elif self.focus_idx == 1:
                self.focus_idx = 0
            else:
                # Wrap from Top to Buttons row (Standard entry: ACCEPT)
                self.focus_idx = 3
                
        elif key in [Keys.DOWN, Keys.J]:
            if self.focus_idx == 0:
                self.focus_idx = 1 if self.install_pkg else (2 if self.has_dots else 3)
            elif self.focus_idx == 1:
                self.focus_idx = 2 if self.has_dots else 3
            elif self.focus_idx == 2:
                # From Bottom list item to Buttons row
                self.focus_idx = 3
            else:
                # Wrap from Buttons row to Top
                self.focus_idx = 0

                
        # Horizontal Navigation (Strictly for Managers and Buttons)
        elif key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            if self.focus_idx == 1: # Managers list
                try:
                    curr_idx = self.managers.index(self.selected_manager)
                    step = 1 if key in [Keys.RIGHT, Keys.L] else -1
                    self.selected_manager = self.managers[(curr_idx + step) % len(self.managers)]
                except ValueError:
                    if self.managers: self.selected_manager = self.managers[0]
            elif self.focus_idx in [3, 4]: # Buttons row
                self.focus_idx = 4 if self.focus_idx == 3 else 3
            
        elif key == Keys.SPACE:
            if self.focus_idx == 0: self.install_pkg = not self.install_pkg
            elif self.focus_idx == 2: self.install_dots = not self.install_dots
            
        elif key == Keys.R and self.focus_idx == 0:
            self.editing_name = True
            
        elif key == Keys.ENTER:
            if self.focus_idx == 3: return "ACCEPT"
            if self.focus_idx == 4: return "CANCEL"
            
        return None

    def get_overrides(self):
        """Returns the dictionary of chosen overrides."""
        return {
            'pkg_name': self.pkg_name,
            'manager': self.selected_manager,
            'install_pkg': self.install_pkg,
            'install_dots': self.install_dots
        }
