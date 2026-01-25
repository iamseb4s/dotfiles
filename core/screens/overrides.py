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
        
        # Modal dimensions
        width = 54
        # Adjust height based on available options
        height = 14 if self.has_dots else 12
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        lines = []
        lines.append(f"╔{'═' * (width-2)}╗")
        title = f" OVERRIDE: {self.mod.label.upper()} "
        lines.append(f"║{title.center(width-2)}║")
        lines.append(f"╠{'═' * (width-2)}╣")
        lines.append(f"║{' ' * (width-2)}║")
        
        # Option 0: Package Toggle
        pkg_mark = "■" if self.install_pkg else " "
        cursor = ">" if self.focus_idx == 0 else " "
        pkg_label = f"{cursor} [{pkg_mark}] Install Package: '{self.pkg_name}'"
        if self.editing_name: pkg_label += " ✎"
        
        # Calculate padding based on visible length to prevent border distortion
        v_len = TUI.visible_len(pkg_label)
        padding = " " * (width - 6 - v_len)
        lines.append(f"║  {pkg_label}{padding}  ║")
        
        # Option 1: Managers (Only if package is enabled)
        if self.install_pkg:
            mgr_content = ""
            for mgr in self.managers:
                mark = "●" if self.selected_manager == mgr else "○"
                is_focused = (self.focus_idx == 1 and self.selected_manager == mgr)
                prefix = f"{Style.BOLD}> {Style.RESET}" if is_focused else "  "
                mgr_content += f"{prefix}{mark} {mgr}   "
            
            # Center the managers line
            v_len = TUI.visible_len(mgr_content)
            padding_total = width - 2 - v_len
            left_p = " " * (padding_total // 2)
            right_p = " " * (padding_total - len(left_p))
            lines.append(f"║{left_p}{mgr_content}{right_p}║")
        else:
            lines.append(f"║{' ' * (width-2)}║")
            
        lines.append(f"║{' ' * (width-2)}║")
        
        # Option 2: Dotfiles Toggle (Conditional)
        if self.has_dots:
            label_text = "Configure Dotfiles (Stow)"
            if self.mod.id == "refind": label_text = "Copy Configuration files"
            
            dot_mark = "■" if self.install_dots else " "
            cursor = ">" if self.focus_idx == 2 else " "
            dot_label = f"{cursor} [{dot_mark}] {label_text}"
            v_len = TUI.visible_len(dot_label)
            padding = " " * (width - 6 - v_len)
            lines.append(f"║  {dot_label}{padding}  ║")
            lines.append(f"║{' ' * (width-2)}║")
        
        # Instructions Line
        instr = "(Press R to rename)" if self.focus_idx == 0 else ""
        lines.append(f"║{Style.DIM}{instr.center(width-2)}{Style.RESET}║")
        
        # Buttons
        btn_acc = "  ACCEPT  "
        btn_can = "  CANCEL  "
        
        # Apply style to focused button
        acc_styled = f"{Style.INVERT}{btn_acc}{Style.RESET}" if self.focus_idx == 3 else f"[{btn_acc.strip()}]"
        can_styled = f"{Style.INVERT}{btn_can}{Style.RESET}" if self.focus_idx == 4 else f"[{btn_can.strip()}]"
        
        btn_row = f"{acc_styled}     {can_styled}"
        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        left_p = " " * padding
        right_p = " " * (width - 2 - padding - v_len)
        
        lines.append(f"║{left_p}{btn_row}{right_p}║")
        lines.append(f"╚{'═' * (width-2)}╝")
        
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
