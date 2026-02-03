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
            override = self.overrides.get(mod.id, {})
            mod_results = self.results.get(mod.id, {}) if self.results else {}
            subs = override.get('sub_selections', {})
            
            # 1. Header
            is_custom = False
            for key in ['package_name', 'manager', 'stow_target']:
                default = getattr(mod, key) if key != 'package_name' else mod.get_package_name()
                if override.get(key) != default:
                    is_custom = True; break
            
            color = Style.warning() if is_custom else Style.normal()
            label = mod.label + ("*" if is_custom else "")
            lines.append(f"{Style.muted()}■ {Style.RESET}{color}{label}{Style.RESET}")
            
            # 2. Build recursive tree of active components
            parts = []
            if hasattr(mod, 'sub_components') and mod.sub_components:
                parts = self._get_active_sub_tree(mod.sub_components, subs)
            else:
                if subs.get('binary', True):
                    parts.append({'id': 'binary', 'label': f"{mod.label} Package", 'children': []})
            
            if mod.has_usable_dotfiles() and subs.get('dotfiles', True):
                parts.append({'id': 'dotfiles', 'label': "Deploy Configuration Files", 'children': []})

            # 3. Render recursive tree
            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)
                lines.extend(self._render_node(part, "", is_last, mod, override, subs, mod_results))
                    
        return lines

    def _get_active_sub_tree(self, components, selections):
        """Recursively builds a tree of only selected components."""
        active = []
        for comp in components:
            if selections.get(comp['id'], comp.get('default', True)):
                active.append({
                    'id': comp['id'],
                    'label': comp['label'],
                    'children': self._get_active_sub_tree(comp.get('children', []), selections)
                })
        return active

    def _render_node(self, node, prefix, is_last, mod, override, subs, results):
        """Generates tree lines recursively with proper connectors and styles."""
        lines = []
        char = "└──" if is_last else "├──"
        
        # Icon for results mode only
        res_prefix = ""
        if self.is_results_mode:
            res_key = 'dotfiles' if node['id'] == 'dotfiles' else 'package'
            success = results.get(res_key)
            icon = ("✔" if success else "✘") if success is not None else "○"
            color = (Style.success() if success else Style.error()) if success is not None else Style.muted()
            res_prefix = f"{color}[{icon}]{Style.RESET} "

        # Component Label (Always Normal/White)
        lines.append(f"{Style.muted()}  {prefix}{char}{Style.RESET} {res_prefix}{Style.normal()}{node['label']}{Style.RESET}")
        
        # Children and Metadata prefix
        new_prefix = prefix + ("    " if is_last else "│   ")
        
        # Inject Metadata under specific nodes
        if not self.is_results_mode:
            if node['id'] == 'binary' or (not hasattr(mod, 'sub_components') and "Package" in node['label']):
                p_name = override.get('package_name', mod.get_package_name())
                mgr = override.get('manager', mod.get_manager())
                requires_root = (mgr == "system" and subs.get('binary', True))
                root_mark = f"{Style.normal()}*{Style.RESET}" if requires_root else ""
                
                meta = f"{Style.muted()}  {new_prefix}{Style.RESET}"
                meta += f"{Style.secondary()}Package:{Style.RESET} {Style.normal()}'{p_name}'{Style.RESET}{root_mark}{Style.muted()}, "
                meta += f"{Style.secondary()}Manager:{Style.RESET} {Style.normal()}'{mgr}'{Style.RESET}"
                lines.append(meta)
                
            if node['id'] == 'dotfiles':
                target = override.get('stow_target', mod.stow_target)
                lines.append(f"{Style.muted()}  {new_prefix}{Style.RESET}{Style.secondary()}Target: {Style.RESET}{Style.normal()}{target}{Style.RESET}")

        # Recurse children
        for j, child in enumerate(node['children']):
            lines.extend(self._render_node(child, new_prefix, j == len(node['children'])-1, mod, override, subs, results))
            
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
            inner.append(f"{Style.secondary()}{txt.center(self.width-2)}{Style.RESET}")
        
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
