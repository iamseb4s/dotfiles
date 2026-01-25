import shutil
from core.tui import TUI, Keys, Style

class SummaryModal:
    """
    Final confirmation modal listing all selected modules and their configurations
    using a tree-like hierarchical structure.
    Supports 'Audit' mode (pre-install) and 'Results' mode (post-install).
    """
    def __init__(self, modules, selected_ids, overrides, results=None):
        self.active_modules = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides
        self.results = results # { 'mod_id': {'pkg': True, 'dots': True} }
        self.is_results_mode = results is not None
        
        # Build the flat list of content lines once
        self.max_visible_rows = 12
        self.content_lines = self._build_content()
        
        # UI State
        self.focus_idx = 0 # 0: Install/Finish, 1: Cancel/Logs
        self.scroll_offset = 0

    def _build_content(self):
        """Constructs the tree-like representation of the installation plan or results."""
        lines = []
        for mod in self.active_modules:
            ovr = self.overrides.get(mod.id)
            is_custom = ovr is not None
            res = self.results.get(mod.id, {}) if self.results else {}
            
            # Root Node: - Package Label
            label = mod.label
            if is_custom:
                label += "*"
                color = Style.hex("#FDCB6E") # Yellow for custom
            else:
                color = Style.hex("#55E6C1") # Green for standard
            
            lines.append({'text': f"- {label}", 'color': color})
            
            # Children data resolution
            pkg_name = ovr['pkg_name'] if is_custom else mod.get_package_name()
            manager = ovr['manager'] if is_custom else mod.get_manager()
            do_pkg = ovr['install_pkg'] if is_custom else True
            do_dots = ovr['install_dots'] if is_custom else True
            
            has_config = mod.stow_pkg is not None
            
            # Icons and colors based on mode
            if self.is_results_mode:
                # Package result icon
                success_pkg = res.get('pkg')
                if not do_pkg or success_pkg is None: 
                    pkg_icon, pkg_color = "○", Style.DIM
                else: 
                    pkg_icon = "✔" if success_pkg else "✘"
                    pkg_color = Style.hex("#55E6C1") if success_pkg else Style.hex("#FF6B6B")
                
                # Dots result icon
                success_dots = res.get('dots')
                if not do_dots or not has_config or success_dots is None: 
                    dots_icon, dots_color = "○", Style.DIM
                else: 
                    dots_icon = "✔" if success_dots else "✘"
                    dots_color = Style.hex("#55E6C1") if success_dots else Style.hex("#FF6B6B")
            else:
                pkg_icon = "■" if do_pkg else " "
                dots_icon = "■" if do_dots else " "
                pkg_color = dots_color = Style.RESET

            # Child 1: Package/Binary
            connector = " ├" if has_config else " └"
            text_pkg = f"{connector}[{pkg_icon}] Package: '{pkg_name}', Manager: '{manager}'"
            lines.append({'text': text_pkg, 'color': pkg_color})
            
            # Child 2: Configuration (Optional)
            if has_config:
                label_dots = "Configuration files" if mod.id == "refind" else "Dotfiles (Stow)"
                text_dots = f" └[{dots_icon}] {label_dots}"
                lines.append({'text': text_dots, 'color': dots_color})
                
                # Info: Target path (Only in audit mode and if dots are active)
                if not self.is_results_mode and do_dots:
                    target = mod.stow_target or "~/"
                    lines.append({'text': f"     Target: {Style.hex('#89B4FA')}{target}", 'color': ""})
                
        return lines

    def render(self):
        """Draws the modal with tree content and dynamic height."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Modal dimensions
        width = 64
        title = "INSTALLATION RESULTS" if self.is_results_mode else "INSTALLATION SUMMARY"
        
        # 2. Build Inner Content
        inner_lines = []
        inner_lines.append("") # Top spacer
        
        # Viewport logic
        visible_content = self.content_lines[self.scroll_offset : self.scroll_offset + self.max_visible_rows]
        
        for item in visible_content:
            text = item['text']
            color = item['color']
            inner_lines.append(f"  {color}{text}{Style.RESET}")
            
        # Fill empty space if content is shorter than max rows
        for _ in range(self.max_visible_rows - len(visible_content)):
            inner_lines.append("")

        # Scroll indicator line (internal)
        if len(self.content_lines) > self.max_visible_rows:
            remaining = len(self.content_lines) - self.max_visible_rows - self.scroll_offset
            scroll_text = f"--- {max(0, remaining)} more entries ---" if remaining > 0 else "--- End of list ---"
            inner_lines.append(f"{Style.DIM}{scroll_text.center(width-2)}{Style.RESET}")
        else:
            inner_lines.append("")
            
        footer_msg = "Process finished." if self.is_results_mode else "Confirm and start installation?"
        inner_lines.append(f"{Style.DIM}{footer_msg.center(width-2)}{Style.RESET}")
        
        # Buttons
        if self.is_results_mode:
            btn_left, btn_right = "  FINISH  ", "  VIEW LOGS  "
        else:
            btn_left, btn_right = "  INSTALL  ", "  CANCEL  "
        
        l_styled = f"{Style.INVERT}{btn_left}{Style.RESET}" if self.focus_idx == 0 else f"[{btn_left.strip()}]"
        r_styled = f"{Style.INVERT}{btn_right}{Style.RESET}" if self.focus_idx == 1 else f"[{btn_right.strip()}]"
        
        btn_row = f"{l_styled}     {r_styled}"
        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        inner_lines.append(f"{' ' * padding}{btn_row}")

        # 3. Calculate Scroll Parameters for the Border
        scroll_pos = None
        scroll_size = None
        if len(self.content_lines) > self.max_visible_rows:
            # Scroll thumb size relative to the content area (max_visible_rows)
            # We offset the position by 1 because of the top spacer in inner_lines
            thumb_size = max(1, int(self.max_visible_rows**2 / len(self.content_lines)))
            prog = self.scroll_offset / (len(self.content_lines) - self.max_visible_rows)
            scroll_pos = 1 + int(prog * (self.max_visible_rows - thumb_size))
            scroll_size = thumb_size

        # 4. Wrap in Container
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title=title, is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        return lines, start_y, start_x

    def handle_input(self, key):
        """Manages modal navigation and confirmation."""
        if key == Keys.ESC or key in [Keys.Q, Keys.Q_UPPER]:
            if self.is_results_mode:
                return "CLOSE"
            return "CANCEL"
            
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            self.focus_idx = 1 if self.focus_idx == 0 else 0
            
        elif key in [Keys.UP, Keys.K]:
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                
        elif key in [Keys.DOWN, Keys.J]:
            if self.scroll_offset < len(self.content_lines) - self.max_visible_rows:
                self.scroll_offset += 1
                
        elif key == Keys.ENTER:
            if self.is_results_mode:
                return "FINISH" if self.focus_idx == 0 else "CLOSE"
            else:
                return "INSTALL" if self.focus_idx == 0 else "CANCEL"
            
        return None
