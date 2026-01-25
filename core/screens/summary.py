import shutil
from core.tui import TUI, Keys, Style

class SummaryModal:
    """
    Final confirmation modal listing all selected modules and their configurations.
    """
    def __init__(self, modules, selected_ids, overrides):
        # Filter modules that are active (selected or locked)
        self.active_modules = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides
        
        # Build the flat list of content lines once
        self.max_visible_rows = 12
        self.content_lines = self._build_content()
        
        # UI State
        self.focus_idx = 0 # 0: Install, 1: Cancel
        self.scroll_offset = 0

    def _build_content(self):
        """Constructs the tree-like representation of the installation plan."""
        lines = []
        for mod in self.active_modules:
            ovr = self.overrides.get(mod.id)
            is_custom = ovr is not None
            
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
            
            # Child 1: Package/Binary
            mark = "■" if do_pkg else " "
            # Use '├' if there's a second child (config), otherwise '└'
            connector = " ├" if has_config else " └"
            lines.append({'text': f"{connector}[{mark}] Package: '{pkg_name}', Manager: '{manager}'", 'color': Style.RESET})
            
            # Child 2: Configuration (Optional)
            if has_config:
                mark = "■" if do_dots else " "
                label_dots = "Configuration files" if mod.id == "refind" else "Dotfiles (Stow)"
                lines.append({'text': f" └[{mark}] {label_dots}", 'color': Style.RESET})
                
                # Info: Target path (Only if dots are active)
                if do_dots:
                    target = mod.stow_target or "~/"
                    lines.append({'text': f"     Target: {Style.hex('#89B4FA')}{target}", 'color': ""})
                
        return lines

    def render(self):
        """Draws the modal with tree content and dynamic height."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # Modal dimensions
        width = 64
        # Calculate dynamic height based on the tree content to prevent border overflow
        content_rows = min(len(self.content_lines), self.max_visible_rows)
        
        lines = []
        lines.append(f"╔{'═' * (width-2)}╗")
        title = " INSTALLATION SUMMARY "
        lines.append(f"║{title.center(width-2)}║")
        lines.append(f"╠{'═' * (width-2)}╣")
        lines.append(f"║{' ' * (width-2)}║")
        
        # Content Viewport
        visible_content = self.content_lines[self.scroll_offset : self.scroll_offset + self.max_visible_rows]
        
        for item in visible_content:
            text = item['text']
            color = item['color']
            
            # Use visible_len to ensure proper border alignment with ANSI codes
            v_len = TUI.visible_len(text)
            padding = " " * (width - 6 - v_len)
            lines.append(f"║  {color}{text}{Style.RESET}{padding}  ║")
            
        # Fill empty space only up to current visible rows, not fixed maximum
        for _ in range(content_rows - len(visible_content)):
            lines.append(f"║{' ' * (width-2)}║")

        # Scroll / Pagination indicators
        if len(self.content_lines) > self.max_visible_rows:
            remaining = len(self.content_lines) - self.max_visible_rows - self.scroll_offset
            scroll_text = f"--- {max(0, remaining)} more entries ---" if remaining > 0 else "--- End of list ---"
            lines.append(f"║{Style.DIM}{scroll_text.center(width-2)}{Style.RESET}║")
        else:
            lines.append(f"║{' ' * (width-2)}║")
            
        lines.append(f"║{Style.DIM}{'Confirm and start installation?'.center(width-2)}{Style.RESET}║")
        
        # Bottom Buttons
        btn_ins = "  INSTALL  "
        btn_can = "  CANCEL  "
        
        ins_styled = f"{Style.INVERT}{btn_ins}{Style.RESET}" if self.focus_idx == 0 else f"[{btn_ins.strip()}]"
        can_styled = f"{Style.INVERT}{btn_can}{Style.RESET}" if self.focus_idx == 1 else f"[{btn_can.strip()}]"
        
        btn_row = f"{ins_styled}     {can_styled}"
        v_len = TUI.visible_len(btn_row)
        padding = (width - 2 - v_len) // 2
        left_p = " " * padding
        right_p = " " * (width - 2 - padding - v_len)
        
        lines.append(f"║{left_p}{btn_row}{right_p}║")
        lines.append(f"╚{'═' * (width-2)}╝")
        
        # Calculate real vertical position
        height = len(lines)
        start_x = (term_width - width) // 2
        start_y = (term_height - height) // 2
        
        return lines, start_y, start_x

    def handle_input(self, key):
        """Manages modal navigation and confirmation."""
        if key == Keys.ESC or key == Keys.Q:
            return "CANCEL"
            
        # Horizontal button selection
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L]:
            self.focus_idx = 1 if self.focus_idx == 0 else 0
            
        # Vertical Scrolling for long summaries
        elif key in [Keys.UP, Keys.K]:
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                
        elif key in [Keys.DOWN, Keys.J]:
            if self.scroll_offset < len(self.content_lines) - self.max_visible_rows:
                self.scroll_offset += 1
                
        elif key == Keys.ENTER:
            return "INSTALL" if self.focus_idx == 0 else "CANCEL"
            
        return None
