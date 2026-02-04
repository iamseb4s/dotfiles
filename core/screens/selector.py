import shutil
import sys
from collections import defaultdict
from core.tui import TUI, Keys, Style, Theme
from core.screens.welcome import Screen
from core.screens.options import OptionsModal
from core.screens.review import ReviewModal
from core.screens.shared_modals import ConfirmModal

class SelectorScreen(Screen):
    """
    Manages the interactive selection menu, including category grouping,
    dependency resolution, and rendering state.
    """
    # UI Symbols and Constants
    SYM_SEL, SYM_LOCK, SYM_PART, SYM_EMPTY = "[■]", "[■]", "[-]", "[ ]"
    STAT_REQUIRED, STAT_SEL, STAT_INST = "[ REQUIRED ]", "[ SELECTED ]", "[ INSTALLED ]"

    def __init__(self, modules):
        self.modules = modules
        self.module_map = {module.id: module for module in modules}
        self.categories = defaultdict(list)
        for module in modules: 
            self.categories[module.category].append(module)
        
        self.category_names = sorted(self.categories.keys())
        self.expanded = {category: True for category in self.category_names}
        
        # State tracking
        self.selected, self.auto_locked, self.overrides = set(), set(), {}
        self.sub_selections = {} # {module_id: {sub_id: bool}}
        
        # UI State
        self.cursor_index, self.list_scroll_offset, self.info_scroll_offset, self.modal = 0, 0, 0, None
        self.flat_items = []

    def _resolve_dependencies(self):
        """
        Recalculates self.auto_locked based on the dependencies of 
        currently selected modules.
        """
        new_auto_locked_set = set()
        for module_id in self.selected:
            if module_id in self.module_map:
                module = self.module_map[module_id]
                for dependency_id in module.get_dependencies():
                    if dependency_id in self.module_map: 
                        new_auto_locked_set.add(dependency_id)
                        
                        # Auto-expand if it's a requirement
                        if dependency_id not in self.auto_locked and dependency_id not in self.selected:
                            self.expanded[dependency_id] = True
                            if dependency_id not in self.sub_selections:
                                self.sub_selections[dependency_id] = {}
                                # Default to all components ON
                                dependency_module = self.module_map[dependency_id]
                                self.sub_selections[dependency_id]['binary'] = True
                                if hasattr(dependency_module, 'sub_components') and dependency_module.sub_components:
                                    self._set_sub_selection_recursive(dependency_id, dependency_module.sub_components, True)
                                if dependency_module.has_usable_dotfiles():
                                    self.sub_selections[dependency_id]['dotfiles'] = True
        
        # Cleanup orphaned dependencies
        orphaned_dependency_ids = self.auto_locked - new_auto_locked_set - self.selected
        for module_id in orphaned_dependency_ids:
            self.expanded[module_id] = False
            self.sub_selections.pop(module_id, None)

        self.auto_locked = new_auto_locked_set


    def _build_flat_list(self):
        """
        Flattens the hierarchical category structure into a linear list
        for rendering including sub-components.
        """
        items = []
        for category in self.category_names:
            items.append({'type': 'header', 'obj': category})
            if self.expanded.get(category, True):
                for module in self.categories[category]:
                    items.append({'type': 'module', 'obj': module, 'depth': 0})
                    
                    # Only show sub-components if module is expanded
                    if self.expanded.get(module.id, False):
                        has_manual_components = hasattr(module, 'sub_components') and module.sub_components
                        
                        if has_manual_components:
                            self._flatten_sub_components(module.sub_components, items, 1, module.id)
                        else:
                            # Automatically inject Package component if no sub_components defined
                            binary_component = {"id": "binary", "label": f"{module.label} Package", "default": True}
                            items.append({'type': 'sub', 'obj': binary_component, 'depth': 1, 'module_id': module.id})
                        
                        # Automatically inject Dotfiles component if usable and not explicitly in sub_components
                        if module.has_usable_dotfiles():
                            has_manual_dot = any(component.get('id') == 'dotfiles' for component in getattr(module, 'sub_components', []))
                            if not has_manual_dot:
                                dotfiles_component = {"id": "dotfiles", "label": "Deploy Configuration Files", "default": True}
                                items.append({'type': 'sub', 'obj': dotfiles_component, 'depth': 1, 'module_id': module.id})
        return items

    def _flatten_sub_components(self, components, items, depth, module_id):
        for component in components:
            items.append({'type': 'sub', 'obj': component, 'depth': depth, 'module_id': module_id})
            # Sub-components are expanded by default if they have children
            if self.expanded.get(f"{module_id}:{component['id']}", True) and component.get('children'):
                self._flatten_sub_components(component['children'], items, depth + 1, module_id)

    def is_active(self, module_id):
        """Returns True if module is either selected or locked by dependency."""
        return (module_id in self.selected) or (module_id in self.auto_locked)

    def _get_requirers_msg(self, module_id):
        """Returns a formatted message listing modules that require the given module."""
        requiring_module_labels = []
        for selected_id in self.selected:
            requiring_module = self.module_map.get(selected_id)
            if requiring_module and module_id in requiring_module.get_dependencies():
                requiring_module_labels.append(requiring_module.label)

        message_prefix = "Core package is required by"
        return f"{message_prefix}: {', '.join(requiring_module_labels)}" if requiring_module_labels else f"{message_prefix} system configuration"

    def _get_scrollbar(self, total, visible, offset):
        """Returns scroll position and size for create_container."""
        if total <= visible: return {'scroll_pos': None, 'scroll_size': None}
        sz = max(1, int(visible**2 / total))
        return {'scroll_pos': int((offset / (total - visible)) * (visible - sz)), 'scroll_size': sz}

    def render(self):
        """Draws the boxed menu interface to the terminal."""
        self._resolve_dependencies()
        self.flat_items = self._build_flat_list()
        self.cursor_index = min(self.cursor_index, len(self.flat_items) - 1)
        terminal_width, terminal_height = shutil.get_terminal_size()
        
        header = f"{Style.header()}{' PACKAGES SELECTOR '.center(terminal_width)}{Style.RESET}"
        footer_pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(footer_pills, terminal_width - 4)
        available_height = max(10, terminal_height - 4 - len(footer_lines))
        left_panel_width, right_panel_width = terminal_width // 2, terminal_width - (terminal_width // 2) - 1
        
        # Build panels and assemble
        left_panel = self._draw_left(left_panel_width, available_height)
        right_panel = self._draw_right(right_panel_width, available_height)
        main_buffer = [header, ""] + TUI.stitch_containers(left_panel, right_panel, gap=1) + [""]
        
        for footer_line in footer_lines:
            visible_len = TUI.visible_len(footer_line)
            left_padding = (terminal_width - visible_len) // 2
            right_padding = terminal_width - visible_len - left_padding
            main_buffer.append(f"{' ' * left_padding}{footer_line}{' ' * right_padding}")

        if self.modal:
            modal_lines, modal_y, modal_x = self.modal.render()
            for index, line in enumerate(modal_lines):
                if 0 <= modal_y + index < len(main_buffer): 
                    main_buffer[modal_y + index] = TUI.overlay(main_buffer[modal_y + index], line, modal_x)
        
        main_buffer = TUI.draw_notifications(main_buffer)
        final_output = "\n".join([TUI.visible_ljust(line, terminal_width) for line in main_buffer[:terminal_height]])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        """Dynamic footer pills based on screen state and active modals."""
        if isinstance(self.modal, OptionsModal) and self.modal.editing_field:
            return [TUI.pill("ENTER", "Finish", Theme.GREEN), TUI.pill("ESC", "Cancel", Theme.RED)]
            
        return [
            TUI.pill("h/j/k/l", "Navigate", Theme.SKY),
            TUI.pill("PgUp/Dn", "Scroll Info", Theme.BLUE),
            TUI.pill("SPACE", "Select", Theme.BLUE),
            TUI.pill("TAB", "Options", Theme.MAUVE),
            TUI.pill("ENTER", "Install", Theme.GREEN),
            TUI.pill("Q", "Back", Theme.RED)
        ]

    def _draw_left(self, width, height):
        """Internal logic for building the package list box."""
        content_width, window_height = width - 6, height - 3
        if self.cursor_index + 1 < self.list_scroll_offset + 1: 
            self.list_scroll_offset = max(0, self.cursor_index)
        elif self.cursor_index + 1 >= self.list_scroll_offset + window_height: 
            self.list_scroll_offset = self.cursor_index - window_height + 1

        lines = [""]
        for index, item in enumerate(self.flat_items):
            is_cursor = (index == self.cursor_index)
            if item['type'] == 'header':
                if index > 0: 
                    lines.append("")
                label = f" {item['obj'].upper()} "
                gap = content_width - len(label)
                left_padding = gap // 2
                color = Style.highlight() if is_cursor else Style.normal()
                lines.append(f"  {color}{Style.BOLD if is_cursor else ''}{'─' * left_padding}{label}{'─' * (gap - left_padding)}{Style.RESET}")
            elif item['type'] == 'module':
                module = item['obj']; is_installed = module.is_installed(); is_supported = module.is_supported()
                
                if not is_supported:
                    mark, status_text, color = self.SYM_EMPTY, "[ NOT SUPPORTED ]", Style.muted()
                elif module.id in self.auto_locked:
                    mark, status_text, color = self.SYM_LOCK, self.STAT_REQUIRED, Style.error()
                elif module.id in self.selected:
                    override = self.overrides.get(module.id); part = override and (not override.get('install_package', True) or (module.stow_pkg and not override.get('install_dotfiles', True)))
                    mark, status_text, color = (self.SYM_PART if part else self.SYM_SEL), self.STAT_SEL, (Style.info() if module.id not in self.overrides else Style.warning())
                else:
                    mark, status_text, color = self.SYM_EMPTY, (self.STAT_INST if is_installed else ""), (Style.success() if is_installed else Style.normal())
                
                style = Style.highlight() + Style.BOLD if is_cursor else color
                label_color = style if (is_cursor or self.is_active(module.id) or is_installed) else color
                
                label_text = f" {style}{mark}  {label_color}{Style.BOLD if (self.is_active(module.id) and not is_cursor) else ''}{module.label}{Style.RESET}"
                lines.append(f"  {TUI.split_line(label_text, f'{style}{status_text}{Style.RESET}' if status_text else '', content_width)}")

            elif item['type'] == 'sub':
                component = item['obj']
                module_id = item['module_id']
                module = self.module_map.get(module_id)
                is_supported = module.is_supported() if module else True
                
                # Check if it's selected in sub_selections, fallback to its own default
                is_selected = self.sub_selections.get(module_id, {}).get(component['id'], component.get('default', True)) if is_supported else False
                mark = self.SYM_SEL if is_selected else self.SYM_EMPTY
                
                color = Style.info() if is_selected else (Style.normal() if is_supported else Style.muted())
                
                # Core binary restriction for required modules visual feedback
                is_required_binary = (component['id'] == 'binary' and module_id in self.auto_locked)
                if is_required_binary:
                    color = Style.error()

                style = Style.highlight() + Style.BOLD if is_cursor else color
                label_style = style
                
                # Use spaces for indentation as requested
                indent = "    " * item['depth']
                label_suffix = " 🔒︎" if is_required_binary else ""
                label_text = f"  {indent}{label_style}{mark}  {component['label']}{label_suffix}{Style.RESET}"
                lines.append(f"  {TUI.visible_ljust(label_text, content_width)}")

        visible_lines = lines[self.list_scroll_offset : self.list_scroll_offset + window_height]
        while len(visible_lines) < window_height: visible_lines.append("")
        stats_text = f"Selected: {len(self.selected.union(self.auto_locked))} packages"
        visible_lines.append(f"{' ' * ((width - 2 - len(stats_text)) // 2)}{Style.muted()}{stats_text}{Style.RESET}")
        
        scrollbar = self._get_scrollbar(len(lines), height - 2, self.list_scroll_offset)
        return TUI.create_container(visible_lines, width, height, title="PACKAGES", is_focused=(not self.modal), scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _draw_right(self, width, height):
        """Internal logic for building the information box."""
        info_lines = self._get_info_lines(width); max_offset = max(0, len(info_lines) - (height - 2))
        self.info_scroll_offset = min(self.info_scroll_offset, max_offset)
        scrollbar = self._get_scrollbar(len(info_lines), height - 2, self.info_scroll_offset)
        return TUI.create_container(info_lines[self.info_scroll_offset : self.info_scroll_offset + height - 2], width, height, title="INFORMATION", is_focused=False, scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _get_info_lines(self, width):
        """Helper to pre-calculate info lines for scroll limits."""
        lines = [""]
        if not self.flat_items: return lines
        item = self.flat_items[self.cursor_index]; content_width = width - 6
        if item['type'] == 'module':
            module = item['obj']; override = self.overrides.get(module.id, {}); is_installed = module.is_installed(); is_supported = module.is_supported()
            
            # Module title color based on state
            color = Style.muted() if not is_supported else (Style.error() if module.id in self.auto_locked else (Style.error() if module.id in self.overrides else (Style.info() if module.id in self.selected else (Style.success() if is_installed else Style.highlight()))))
            lines.extend([f"  {Style.BOLD}{color}{module.label.upper()}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}"])

            if module.description:
                for line in TUI.wrap_text(module.description, content_width): lines.append(f"  {Style.secondary()}{line}{Style.RESET}")
            lines.append("")
            def row(label, value, color_style=""): return f"  {Style.normal()}{label:<13}{Style.RESET} {color_style}{value}{Style.RESET}" 
            
            status_text = 'Not Supported' if not is_supported else ('Installed' if is_installed else 'Not Installed')
            status_style = Style.muted() if not is_supported else (Style.success() if is_installed else Style.secondary())
            lines.append(row("Status", status_text, status_style))
            
            supported_os = module.get_supported_distros()
            lines.append(row("Supported OS", supported_os, Style.secondary() if is_supported else Style.muted()))

            # Resolved dependencies for the current distribution
            resolved_dependencies = module.get_dependencies()
            dependency_labels = []
            for dependency_id in resolved_dependencies:
                dependency_module = self.module_map.get(dependency_id)
                dependency_labels.append(dependency_module.label if dependency_module else dependency_id)
            
            dependency_value = ", ".join(dependency_labels) if dependency_labels else "None"
            dependency_style = Style.warning() if (dependency_labels and is_supported) else Style.secondary()
            lines.append(row("Requires", dependency_value, dependency_style))

            for key, label in [('manager', 'Manager'), ('package_name', 'Package')]:
                current_value = getattr(module, key) if key != 'package_name' else module.get_package_name()
                value = override.get(key, current_value)
                color_value = Style.secondary() if is_supported else Style.muted()
                lines.append(row(label, f"{value}{'*' if value != current_value else ''}", color_value))
            
            current_target = override.get('stow_target', module.stow_target)
            tree = module.get_config_tree(target=current_target)
            if tree:
                tree_title_style = Style.normal() if is_supported else Style.muted()
                lines.extend(["", f"  {Style.BOLD}{tree_title_style}CONFIG TREE{Style.RESET}", f"  {Style.muted()}{'─' * 11}{Style.RESET}"])
                for line in tree:
                    for wrapped_line in TUI.wrap_text(line, content_width - 2): lines.append(f"    {wrapped_line}")

        elif item['type'] == 'sub':
            component = item['obj']
            module_id = item['module_id']
            module = self.module_map[module_id]
            is_supported = module.is_supported() if module else True
            is_selected = self.sub_selections.get(module_id, {}).get(component['id'], component.get('default', True))
            
            is_required_binary = (component['id'] == 'binary' and module_id in self.auto_locked)
            
            # Determine semantic color and labels based on requirement state
            if is_required_binary:
                status_text = "Required"
                status_color = Style.error()
            else:
                status_text = "Selected" if is_selected else "Skipped"
                status_color = Style.info() if is_selected else (Style.normal() if is_supported else Style.muted())
            
            label_suffix = " 🔒︎" if is_required_binary else ""
            lines.extend([f"  {Style.BOLD}{status_color}{component['label'].upper()}{label_suffix}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}"])
            lines.append(f"  {Style.secondary()}Component of {Style.BOLD}{module.label}{Style.RESET}")
            lines.append("")
            def row(label, value, color_style=""): return f"  {Style.normal()}{label:<13}{Style.RESET} {color_style}{value}{Style.RESET}"
            lines.append(row("Status", status_text, status_color))
        else:
            category = item['obj']; lines.extend([f"  {Style.BOLD}{Style.highlight()}{category.upper()}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}", f"  {Style.secondary()}Packages in this group:{Style.RESET}", ""])
            for module in self.categories[category]:
                module_status = "■" if self.is_active(module.id) else " "; color = Style.info() if self.is_active(module.id) else Style.secondary()
                lines.append(f"    {color}[{module_status}] {module.label}{Style.RESET}")
        return lines

    def handle_input(self, key):
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal: 
            return self._handle_modal_input(key)
        
        columns_width = shutil.get_terminal_size().columns // 2
        window_height = max(10, shutil.get_terminal_size().lines - 5) - 2
        max_info_scroll_offset = max(0, len(self._get_info_lines(columns_width)) - window_height)
        
        navigation_map = {
            Keys.UP: lambda: self._move_cursor(-1), 
            Keys.K: lambda: self._move_cursor(-1),
            Keys.DOWN: lambda: self._move_cursor(1), 
            Keys.J: lambda: self._move_cursor(1),
            Keys.CTRL_K: lambda: self._move_cursor(-5), 
            Keys.CTRL_J: lambda: self._move_cursor(5),
            Keys.PGUP: lambda: self._scroll_info(-5, max_info_scroll_offset), 
            Keys.PGDN: lambda: self._scroll_info(5, max_info_scroll_offset),
            Keys.SPACE: self._toggle_sel, 
            Keys.TAB: self._handle_tab,
            Keys.LEFT: self._collapse, 
            Keys.H: self._collapse,
            Keys.RIGHT: self._expand, 
            Keys.L: self._expand,
            Keys.ENTER: self._trigger_install, 
            Keys.Q: self._back, 
            Keys.Q_UPPER: self._back
        }
        return navigation_map[key]() if key in navigation_map else None

    def _handle_modal_input(self, key):
        """Processes results from active modals."""
        modal = self.modal
        if not modal: return None
        result = modal.handle_input(key)
        if isinstance(modal, OptionsModal) and result == "ACCEPT":
            module = self.flat_items[self.cursor_index]['obj']; override = modal.get_overrides()
            if not override['install_package'] and not (module.stow_pkg and override['install_dotfiles']):
                self.selected.discard(module.id); self.overrides.pop(module.id, None)
            else: self.selected.add(module.id); self.overrides[module.id] = override
            self.modal = None; TUI.push_notification(f"Changes saved for {module.label}", type="INFO")
        elif isinstance(modal, ReviewModal) and result == "INSTALL": self.modal = None; return "CONFIRM"
        elif isinstance(modal, ConfirmModal) and result == "YES":
            self.selected.clear(); self.overrides.clear(); self.sub_selections.clear()
            self.expanded = {cat: True for cat in self.category_names}; self.modal = None; return "WELCOME"
        elif result in ["CANCEL", "CLOSE", "NO"]: self.modal = None
        return None

    def _move_cursor(self, direction): 
        if not self.flat_items: return None
        self.cursor_index = (self.cursor_index + direction) % len(self.flat_items)
        self.info_scroll_offset = 0
        return None
    def _scroll_info(self, direction, max_offset): self.info_scroll_offset = max(0, min(max_offset, self.info_scroll_offset + direction)); return None
    def _toggle_sel(self):
        """Handles item selection and group toggling with dependency awareness."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'module':
            module = item['obj']
            if not module.is_supported():
                TUI.push_notification(f"{module.label} is not available for your OS", type="ERROR")
                return
            
            if module.id in self.auto_locked:
                TUI.push_notification(self._get_requirers_msg(module.id), type="ERROR")
                return

            if module.id in self.selected:
                self.selected.remove(module.id)
                self.overrides.pop(module.id, None)
                self.sub_selections.pop(module.id, None)
                self.expanded[module.id] = False # Auto-collapse on deselect
            else:
                self.selected.add(module.id)
                self.expanded[module.id] = True  # Auto-expand on select
                if module.id not in self.sub_selections: self.sub_selections[module.id] = {}
                
                # Auto-select binary package by default
                self.sub_selections[module.id]['binary'] = True
                
                # Auto-select all sub-components by default
                if hasattr(module, 'sub_components') and module.sub_components:
                    self._set_sub_selection_recursive(module.id, module.sub_components, True)
                
                # Auto-select dotfiles by default if they exist
                if module.has_usable_dotfiles():
                    self.sub_selections[module.id]['dotfiles'] = True
        
        elif item['type'] == 'sub':
            module_id = item['module_id']
            component = item['obj']

            # Core binary restriction for required modules
            if component['id'] == 'binary' and module_id in self.auto_locked:
                TUI.push_notification(self._get_requirers_msg(module_id), type="ERROR")
                return

            if module_id not in self.selected:
                self.selected.add(module_id)
                self.expanded[module_id] = True # Ensure expanded if a child is picked
                self.sub_selections[module_id] = {}
            
            # Get current state or default
            current_state = self.sub_selections[module_id].get(component['id'], component.get('default', True))
            new_state = not current_state
            
            # Update this component and its children
            self.sub_selections[module_id][component['id']] = new_state
            if 'children' in component:
                self._set_sub_selection_recursive(module_id, component['children'], new_state)
            
            # If we enable a child, we must ensure parents are enabled
            if new_state:
                self._ensure_parent_path_enabled(module_id, component['id'])
            else:
                if not any(self.sub_selections[module_id].values()):
                    self.selected.discard(module_id)
                    self.expanded[module_id] = False

        elif item['type'] == 'header':
            category = item['obj']; modules = self.categories[category]
            if all(self.is_active(m.id) for m in modules if m.is_supported()):
                for module in modules:
                    if module.id in self.selected:
                        self.selected.remove(module.id)
                        self.overrides.pop(module.id, None)
                        self.sub_selections.pop(module.id, None)
                        self.expanded[module.id] = False # Sync collapse
            else:
                for module in modules:
                    if module.id not in self.auto_locked and module.is_supported():
                        self.selected.add(module.id)
                        self.expanded[module.id] = True # Sync expansion
                        if hasattr(module, 'sub_components') and module.sub_components:
                            if module.id not in self.sub_selections: self.sub_selections[module.id] = {}
                            self._set_sub_selection_recursive(module.id, module.sub_components, True)
                        
                        # Auto-select binary package by default
                        if module.id not in self.sub_selections: self.sub_selections[module.id] = {}
                        self.sub_selections[module.id]['binary'] = True
                        
                        # Auto-select dotfiles by default if they exist
                        if module.has_usable_dotfiles():
                            self.sub_selections[module.id]['dotfiles'] = True
        return None

    def _set_sub_selection_recursive(self, module_id, components, state):
        for component in components:
            if module_id not in self.sub_selections: 
                self.sub_selections[module_id] = {}
            self.sub_selections[module_id][component['id']] = state
            if 'children' in component:
                self._set_sub_selection_recursive(module_id, component['children'], state)

    def _ensure_parent_path_enabled(self, module_id, target_component_id):
        """Ensures that all parents of a sub-component are enabled."""
        module = self.module_map.get(module_id)
        if not module or not hasattr(module, 'sub_components'): 
            return

        def find_and_enable_parents(components, path):
            for component in components:
                if component['id'] == target_component_id:
                    for parent_id in path:
                        self.sub_selections[module_id][parent_id] = True
                    return True
                if 'children' in component:
                    if find_and_enable_parents(component['children'], path + [component['id']]):
                        return True
            return False

        find_and_enable_parents(module.sub_components, [])

    def _handle_tab(self):
        """Handles TAB key for expanding headers or opening options."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'header': self.expanded[item['obj']] = not self.expanded[item['obj']]
        elif item['type'] == 'module': self.modal = OptionsModal(item['obj'], self.overrides.get(item['obj'].id))
        return None

    def _collapse(self):
        """Collapses the current header, module or sub-component."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'header': self.expanded[item['obj']] = False
        elif item['type'] == 'module': self.expanded[item['obj'].id] = False
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = False
        return None

    def _expand(self):
        """Expands the current header, module or sub-component."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'header': self.expanded[item['obj']] = True
        elif item['type'] == 'module': self.expanded[item['obj'].id] = True
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = True
        return None

    def get_effective_overrides(self):
        """
        Merges explicit user overrides with calculated defaults and sub-selections.
        Used by ReviewModal and InstallerScreen.
        """
        all_selected = self.selected.union(self.auto_locked)
        effective = self.overrides.copy()
        
        for module_id in all_selected:
            if module_id not in effective:
                module = self.module_map[module_id]
                effective[module_id] = {
                    'package_name': module.get_package_name(),
                    'manager': module.get_manager(),
                    'install_package': True,
                    'install_dotfiles': module.has_usable_dotfiles(),
                    'stow_target': module.stow_target
                }
            # Inject current sub-selections state (essential for modular Zsh, etc.)
            effective[module_id]['sub_selections'] = self.sub_selections.get(module_id, {})
            
        return effective

    def _trigger_install(self):
        """Shows the installation review modal."""
        all_selected = self.selected.union(self.auto_locked)
        if all_selected:
            effective_overrides = self.get_effective_overrides()
            self.modal = ReviewModal(self.modules, all_selected, effective_overrides)
        else:
            TUI.push_notification("Select at least one package to install", type="ERROR")
        return None

    def _back(self):
        """Returns to the welcome screen, with confirmation if changes exist."""
        if self.selected: self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?"); return None
        return "WELCOME"

