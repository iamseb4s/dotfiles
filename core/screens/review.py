import shutil
from core.tui import TUI, Keys, Style, Theme
from core.screens.shared_modals import BaseModal

class ReviewModal(BaseModal):
    """
    Final review modal listing all selected modules and their configurations
    using a tree-like hierarchical structure.
    Supports 'Audit' mode (pre-install) and 'Results' mode (post-install).
    """
    def __init__(self, modules, selected_ids, overrides, results=None):
        self.is_results_mode = results is not None
        title = " INSTALLATION RESULTS " if self.is_results_mode else " FINAL REVIEW "
        super().__init__(title, width=64)
        
        self.active_modules = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides
        self.results = results # { 'module_id': {'package': True, 'dotfiles': True} }
        
        # Build the flat list of content lines once
        self.content_lines = self._build_content()
        
        # UI State
        self.focus_idx = 0 # 0: Install/Finish, 1: Cancel/Logs
        self.scroll_offset = 0

    def _build_content(self):
        """Constructs the tree-like representation of the installation plan or results."""
        lines = []
        for mod in self.active_modules:
            override = self.overrides.get(mod.id)
            is_custom = override is not None
            mod_results = self.results.get(mod.id, {}) if self.results else {}
            
            label = mod.label + ("*" if is_custom else "")
            color = Style.warning() if is_custom else Style.success()
            lines.append(f"{Style.muted()}- {Style.RESET}{color}{label}{Style.RESET}")
            
            package_name = override['package_name'] if is_custom else mod.get_package_name()
            manager = override['manager'] if is_custom else mod.get_manager()
            do_package = override['install_package'] if is_custom else True
            do_dotfiles = override['install_dotfiles'] if is_custom else True
            has_config = mod.has_usable_dotfiles()
            
            if self.is_results_mode:
                def get_res_icon(success, active):
                    if not active or success is None: return "○", Style.muted()
                    return ("✔" if success else "✘"), (Style.success() if success else Style.error())
                package_icon, package_color = get_res_icon(mod_results.get('package'), do_package)
                dotfiles_icon, dotfiles_color = get_res_icon(mod_results.get('dotfiles'), do_dotfiles and has_config)
            else:
                package_icon, dotfiles_icon = ("■" if do_package else " "), ("■" if do_dotfiles else " ")
                package_color = dotfiles_color = Style.normal()

            # Check for root requirement (Package installation via 'system' driver)
            requires_root = (manager == "system" and do_package)
            root_mark = f"{Style.normal()}*{Style.RESET}" if requires_root else ""
            
            conn = f"{Style.muted()} ├{Style.RESET}" if has_config else f"{Style.muted()} └{Style.RESET}"
            lines.append(f"{conn}{package_color}[{package_icon}]{Style.RESET} {root_mark}{Style.muted()}Package:{Style.RESET} {Style.normal()}'{package_name}'{Style.RESET}{Style.muted()}, Manager:{Style.RESET} {Style.normal()}'{manager}'{Style.RESET}")
            
            if has_config:
                lbl_d = "Configuration files" if mod.id == "refind" else "Dotfiles (Stow)"
                lines.append(f"{Style.muted()} └{Style.RESET}{dotfiles_color}[{dotfiles_icon}]{Style.RESET} {Style.normal()}{lbl_d}{Style.RESET}")
                if not self.is_results_mode and do_dotfiles:
                    lines.append(f"     {Style.muted()}Target: {Style.normal()}{mod.stow_target or '~/'}{Style.RESET}")
        return lines

    def _get_summary_stats(self):
        """Calculates totals for installed, cancelled and failed modules."""
        stats = {'installed': 0, 'cancelled': 0, 'failed': 0}
        if not self.results: return stats
        for mod in self.active_modules:
            override = self.overrides.get(mod.id, {})
            mod_results = self.results.get(mod.id, {})
            tasks = []
            if override.get('install_package', True): tasks.append(mod_results.get('package'))
            if mod.has_usable_dotfiles() and override.get('install_dotfiles', True): tasks.append(mod_results.get('dotfiles'))
            if not tasks: continue
            if any(r is False for r in tasks): stats['failed'] += 1
            elif all(r is True for r in tasks): stats['installed'] += 1
            else: stats['cancelled'] += 1
        return stats

    def render(self):
        """Draws the modal with tree content and dynamic height."""
        th = shutil.get_terminal_size().lines
        max_win_h = min(15, th - 12)
        actual_win_h = min(len(self.content_lines), max_win_h)
        inner = [""]
        
        vis = self.content_lines[self.scroll_offset : self.scroll_offset + actual_win_h]
        for l in vis: inner.append(f"  {l}")
        inner.append("")
        
        if self.is_results_mode:
            st = self._get_summary_stats()
            txt = f"{Style.success()}{st['installed']} installed{Style.RESET}, {Style.info()}{st['cancelled']} cancelled{Style.RESET}, {Style.error()}{st['failed']} failed{Style.RESET}"
            inner.append(f"{' ' * ((self.width - 2 - TUI.visible_len(txt)) // 2)}{txt}")
        else:
            # Check if any task requires root by searching for the normal asterisk in the content
            any_root = any(f"{Style.normal()}*{Style.RESET}" in line for line in self.content_lines)
            if any_root:
                root_msg = f"{Style.error()}*root required{Style.RESET}"
                inner.append(f"{' ' * ((self.width - 2 - TUI.visible_len(root_msg)) // 2)}{root_msg}")
            
            txt = "Confirm and start installation?"
            inner.append(f"{Style.muted()}{txt.center(self.width-2)}{Style.RESET}")
        
        btns = ["  FINISH  ", "  VIEW LOGS  "] if self.is_results_mode else ["  INSTALL  ", "  CANCEL  "]
        inner.append(self._render_button_row(btns, self.focus_idx))
        
        sp, ss = self._get_scroll_params(len(self.content_lines), actual_win_h, self.scroll_offset)
        return self._get_layout(inner, scroll_pos=sp, scroll_size=ss)

    def handle_input(self, key):
        """Manages modal navigation and confirmation."""
        if key in [Keys.Q, Keys.Q_UPPER]: return "CLOSE" if self.is_results_mode else "CANCEL"
        if key == Keys.ESC:
            if self.focus_idx != 1: self.focus_idx = 1
            else: return "CLOSE" if self.is_results_mode else "CANCEL"

        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.focus_idx = 1 - self.focus_idx
        elif key in [Keys.UP, Keys.K]: self.scroll_offset = max(0, self.scroll_offset - 1)
        elif key in [Keys.DOWN, Keys.J]:
            th = shutil.get_terminal_size().lines
            max_win_h = min(15, th - 12)
            self.scroll_offset = min(max(0, len(self.content_lines) - max_win_h), self.scroll_offset + 1)
        elif key == Keys.ENTER:
            if self.is_results_mode: return "FINISH" if self.focus_idx == 0 else "CLOSE"
            return "INSTALL" if self.focus_idx == 0 else "CANCEL"
        return None
