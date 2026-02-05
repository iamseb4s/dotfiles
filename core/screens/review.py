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
        title = "INSTALLATION RESULTS" if self.is_results_mode else "INSTALLATION REVIEW"
        super().__init__(title, width=64)
        
        self.active_modules = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides
        self.results = results # { 'module_id': {'package': True, 'dotfiles': True} }
        
        # Build the flat list of content lines once
        self.tree_content_lines = self._build_content()
        
        # UI State
        self.button_focus_index = 0 # 0: Install/Finish, 1: Cancel/Logs
        self.scroll_offset = 0

    def _build_content(self):
        """Constructs the tree-like representation of the installation plan or results."""
        tree_lines = []
        for module in self.active_modules:
            override = self.overrides.get(module.id, {})
            module_results = self.results.get(module.id, {}) if self.results else {}
            sub_selections = override.get('sub_selections', {})
            
            # 1. Header
            is_customized = False
            for key in ['package_name', 'manager', 'stow_target']:
                default_value = getattr(module, key) if key != 'package_name' else module.get_package_name()
                if override.get(key) != default_value:
                    is_customized = True; break
            
            color = Style.warning() if is_customized else Style.normal()
            label = module.label + ("*" if is_customized else "")
            tree_lines.append(f"{Style.muted()}■ {Style.RESET}{color}{label}{Style.RESET}")
            
            # 2. Build recursive tree of active components
            parts = []
            if hasattr(module, 'sub_components') and module.sub_components:
                parts = self._get_active_sub_tree(module.sub_components, sub_selections)
            else:
                if sub_selections.get('binary', True):
                    parts.append({'id': 'binary', 'label': f"{module.label} Package", 'children': []})
            
            if module.has_usable_dotfiles() and sub_selections.get('dotfiles', True):
                parts.append({'id': 'dotfiles', 'label': "Deploy Configuration Files", 'children': []})

            # 3. Render recursive tree
            for index, part in enumerate(parts):
                is_last = (index == len(parts) - 1)
                tree_lines.extend(self._render_node(part, "", is_last, module, override, sub_selections, module_results))
                    
        return tree_lines

    def _get_active_sub_tree(self, components, selections):
        """Recursively builds a tree of only selected components."""
        active_components = []
        for component in components:
            if selections.get(component['id'], component.get('default', True)):
                active_components.append({
                    'id': component['id'],
                    'label': component['label'],
                    'children': self._get_active_sub_tree(component.get('children', []), selections)
                })
        return active_components

    def _render_node(self, node, prefix, is_last, module, override, sub_selections, results):
        """Generates tree lines recursively with proper connectors and styles."""
        lines = []
        connector_char = "└── " if is_last else "├── "
        
        # Determine if this node represents a system package installation (requires root)
        is_package_node = node['id'] == 'binary' or (not hasattr(module, 'sub_components') and "Package" in node['label'])
        requires_root = False
        if is_package_node and not self.is_results_mode:
            manager = override.get('manager', module.get_manager())
            requires_root = (manager == "system" and sub_selections.get('binary', True))
        
        root_indicator = f"{Style.error()}*{Style.RESET}" if requires_root else ""

        # Icon for results mode only
        results_prefix = ""
        if self.is_results_mode:
            result_key = 'dotfiles' if node['id'] == 'dotfiles' else 'package'
            success = results.get(result_key)
            icon = ("✔" if success else "✘") if success is not None else "○"
            status_color = (Style.success() if success else Style.error()) if success is not None else Style.muted()
            results_prefix = f"{status_color}[{icon}]{Style.RESET} "

        # Component Label
        lines.append(f"{Style.muted()}  {prefix}{connector_char}{Style.RESET}{results_prefix}{Style.normal()}{node['label']}{root_indicator}{Style.RESET}")
        
        # Children and Metadata prefix
        new_prefix = prefix + ("    " if is_last else "│   ")
        
        # Inject Metadata under specific nodes
        if not self.is_results_mode:
            if is_package_node:
                package_name = override.get('package_name', module.get_package_name())
                manager = override.get('manager', module.get_manager())
                
                metadata_line = f"{Style.muted()}  {new_prefix}{Style.RESET}"
                metadata_line += f"{Style.secondary()}Package:{Style.RESET} {Style.normal()}'{package_name}'{Style.RESET}{Style.muted()}, "
                metadata_line += f"{Style.secondary()}Manager:{Style.RESET} {Style.normal()}'{manager}'{Style.RESET}"
                lines.append(metadata_line)
                
            if node['id'] == 'dotfiles':
                target_path = override.get('stow_target', module.stow_target)
                lines.append(f"{Style.muted()}  {new_prefix}{Style.RESET}{Style.secondary()}Target: {Style.RESET}{Style.normal()}{target_path}{Style.RESET}")

        # Recurse children
        for child_index, child in enumerate(node['children']):
            lines.extend(self._render_node(child, new_prefix, child_index == len(node['children'])-1, module, override, sub_selections, results))
            
        return lines


    def _get_summary_stats(self):
        """Calculates totals for installed, cancelled and failed modules."""
        stats = {'installed': 0, 'cancelled': 0, 'failed': 0}
        if not self.results: 
            return stats
        for module in self.active_modules:
            override = self.overrides.get(module.id, {})
            module_results = self.results.get(module.id, {})
            tasks = []
            if override.get('install_package', True): 
                tasks.append(module_results.get('package'))
            if module.has_usable_dotfiles() and override.get('install_dotfiles', True): 
                tasks.append(module_results.get('dotfiles'))
            if not tasks: 
                continue
            if any(result is False for result in tasks): 
                stats['failed'] += 1
            elif all(result is True for result in tasks): 
                stats['installed'] += 1
            else: 
                stats['cancelled'] += 1
        return stats

    def render(self):
        """Draws the modal with tree content and dynamic height."""
        width = self.effective_width
        terminal_height = shutil.get_terminal_size().lines
        
        # Max height for the tree area
        max_tree_height = max(3, terminal_height - 14)
        actual_tree_height = min(len(self.tree_content_lines), max_tree_height)
        
        
        # Internal Padding: top weight
        inner_buffer = [""]

        visible_tree_lines = self.tree_content_lines[self.scroll_offset : self.scroll_offset + actual_tree_height]
        for tree_line in visible_tree_lines: 
            inner_buffer.append(f"  {tree_line}")
        
        # Internal Padding: bottom weight
        inner_buffer.append("")
        
        if self.is_results_mode:
            # 2. Results stats
            stats = self._get_summary_stats()
            summary_text = f"{Style.success()}{stats['installed']} installed{Style.RESET}, {Style.info()}{stats['cancelled']} cancelled{Style.RESET}, {Style.error()}{stats['failed']} failed{Style.RESET}"
            inner_buffer.append(f"{' ' * ((width - 2 - TUI.visible_len(summary_text)) // 2)}{summary_text}")
        else:
            # 2. Root requirement check or empty line
            any_root_required = any(f"{Style.error()}*" in line for line in self.tree_content_lines)
            if any_root_required:
                root_message = f"{Style.error()}*root required{Style.RESET}"
                padding_size = max(0, (width - 2 - TUI.visible_len(root_message)) // 2)
                inner_buffer.append(f"{' ' * padding_size}{root_message}")
            else:
                inner_buffer.append("")
            
        # 3. Confirmation text / spacing
        if self.is_results_mode:
            inner_buffer.append("")
        else:
            confirmation_text = "Confirm and start installation?"
            padding_size = max(0, (width - 2 - TUI.visible_len(confirmation_text)) // 2)
            inner_buffer.append(f"{Style.secondary()}{' ' * padding_size}{confirmation_text}{Style.RESET}")
        
        # 4. Buttons row
        buttons = ["  INSTALL  ", "  CANCEL  "]
        if self.is_results_mode:
            buttons = ["  FINISH  ", "  VIEW LOGS  "]
        inner_buffer.append(self._render_button_row(buttons, self.button_focus_index))
        
        # Scrollbar
        total_interior_items = len(self.tree_content_lines) + 5
        visible_interior_items = actual_tree_height + 5
        scroll_pos, scroll_size = self._get_scroll_params(total_interior_items, visible_interior_items, self.scroll_offset)
        
        return self._get_layout(inner_buffer, scroll_pos=scroll_pos, scroll_size=scroll_size)

    def handle_input(self, key):
        """Manages modal navigation and confirmation with synchronized scroll limits."""
        if key in [Keys.Q, Keys.Q_UPPER]: return "CLOSE" if self.is_results_mode else "CANCEL"
        if key == Keys.ESC:
            if self.button_focus_index != 1: self.button_focus_index = 1
            else: return "CLOSE" if self.is_results_mode else "CANCEL"

        terminal_height = shutil.get_terminal_size().lines
        max_tree_height = max(3, terminal_height - 14)
        
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.button_focus_index = 1 - self.button_focus_index
        elif key in [Keys.UP, Keys.K]: self.scroll_offset = max(0, self.scroll_offset - 3)
        elif key in [Keys.DOWN, Keys.J]:
            self.scroll_offset = min(max(0, len(self.tree_content_lines) - max_tree_height), self.scroll_offset + 3)
        elif key == Keys.PGUP: self.scroll_offset = max(0, self.scroll_offset - 10)
        elif key == Keys.PGDN: self.scroll_offset = min(max(0, len(self.tree_content_lines) - max_tree_height), self.scroll_offset + 10)
        elif key == Keys.ENTER:
            if self.is_results_mode: return "FINISH" if self.button_focus_index == 0 else "CLOSE"
            return "INSTALL" if self.button_focus_index == 0 else "CANCEL"
        return None
