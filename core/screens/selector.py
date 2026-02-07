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
        self._structure_needs_rebuild = True
        self._info_cache = {} # {(index, width): lines}

    def _resolve_dependencies(self):
        """
        Recalculates self.auto_locked using a recursive fixed-point algorithm
        that is aware of specific sub-component selections.
        """
        new_auto_locked_set = set()
        # Worklist of tuples: (module_identifier, component_identifier)
        resolution_queue = []
        
        # 1. Initialize queue with explicitly selected module components
        for module_id in self.selected:
            if module_id not in self.module_map: 
                continue
            module_selections = self.sub_selections.get(module_id, {})
            for component_id, is_component_active in module_selections.items():
                if is_component_active:
                    resolution_queue.append((module_id, component_id))

        processed_component_states = set()
        while resolution_queue:
            current_module_id, current_component_id = resolution_queue.pop(0)
            state_key = (current_module_id, current_component_id)
            if state_key in processed_component_states: 
                continue
            processed_component_states.add(state_key)
            
            module_instance = self.module_map.get(current_module_id)
            if not module_instance: 
                continue
            
            # Get dependencies for THIS specific component (e.g. 'dotfiles' requires 'stow')
            component_dependencies = module_instance.get_component_dependencies(current_component_id)
            for dependency_id in component_dependencies:
                if dependency_id not in self.module_map or dependency_id == current_module_id:
                    continue
                
                new_auto_locked_set.add(dependency_id)
                
                # If the dependency isn't manually selected, we must process its 
                # core binary requirements recursively.
                if dependency_id not in self.selected:
                    resolution_queue.append((dependency_id, "binary"))
                    
                    # Ensure it has basic selection state if it is newly locked
                    if dependency_id not in self.auto_locked:
                        self.expanded[dependency_id] = True
                        if dependency_id not in self.sub_selections:
                            self.sub_selections[dependency_id] = {'binary': True}
                            
                            # Recursively enable mandatory sub-components for the dependency
                            dependency_module = self.module_map[dependency_id]
                            if hasattr(dependency_module, 'sub_components') and dependency_module.sub_components:
                                self._set_sub_selection_recursive(dependency_id, dependency_module.sub_components, True)

        # Cleanup orphaned dependencies and their associated states
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

    def _get_scrollbar(self, total_items_count, visible_window_height, scroll_offset, track_available_height):
        """Returns scroll position and size relative to the provided track height."""
        if total_items_count <= visible_window_height: 
            return {'scroll_pos': None, 'scroll_size': None}
        
        thumb_size = max(1, int(track_available_height * (visible_window_height / total_items_count)))
        
        # Max offset is total items minus visible window
        max_scroll_offset = total_items_count - visible_window_height
        
        # Ratio of current offset to max offset
        scroll_ratio = scroll_offset / max_scroll_offset
        
        # Position within the available track minus the thumb itself
        thumb_position = int(scroll_ratio * (track_available_height - thumb_size))
        
        return {'scroll_pos': thumb_position, 'scroll_size': thumb_size}

    def render(self):
        """Draws the boxed menu interface to the terminal with cursor persistence."""
        # 1. Identify current item to maintain focus after list rebuild
        current_item_marker = None
        if self.flat_items and self.cursor_index < len(self.flat_items):
            item = self.flat_items[self.cursor_index]
            if item['type'] == 'header': current_item_marker = ('header', item['obj'])
            elif item['type'] == 'module': current_item_marker = ('module', item['obj'].id)
            elif item['type'] == 'sub': current_item_marker = ('sub', item['module_id'], item['obj']['id'])

        # 2. Rebuild the list
        if self._structure_needs_rebuild:
            self._resolve_dependencies()
            self.flat_items = self._build_flat_list()
            self._structure_needs_rebuild = False
            self._info_cache.clear()
            
            # 3. Relocate cursor to the previously focused item
            if current_item_marker:
                for index, item in enumerate(self.flat_items):
                    match_found = False
                    if current_item_marker[0] == 'header' and item['type'] == 'header' and item['obj'] == current_item_marker[1]: 
                        match_found = True
                    elif current_item_marker[0] == 'module' and item['type'] == 'module' and item['obj'].id == current_item_marker[1]: 
                        match_found = True
                    elif current_item_marker[0] == 'sub' and item['type'] == 'sub' and item['module_id'] == current_item_marker[1] and item['obj']['id'] == current_item_marker[2]: 
                        match_found = True
                    
                    if match_found:
                        self.cursor_index = index
                        break

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
        # Final rendering pass with overflow protection (Line-wrap shield)
        final_output = "\n".join([TUI.truncate_ansi(line, terminal_width) for line in main_buffer[:terminal_height]])
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
        content_width = width - 6
        scrollable_window_height = height - 4
        
        rendered_content_lines = []
        item_to_line_mapping = {}

        for index, item in enumerate(self.flat_items):
            is_cursor = (index == self.cursor_index)
            
            if item['type'] == 'header':
                # Add spacing before category if it's not the first one
                if len(rendered_content_lines) > 0: 
                    rendered_content_lines.append("")
                
                # The category title itself is the target for the cursor
                item_to_line_mapping[index] = len(rendered_content_lines)
                
                category_label = f" {item['obj'].upper()} "
                padding_gap = content_width - len(category_label)
                left_padding_size = padding_gap // 2
                category_color = Style.highlight() if is_cursor else Style.normal()
                
                header_line = f"  {category_color}{Style.BOLD if is_cursor else ''}{'─' * left_padding_size}{category_label}{'─' * (padding_gap - left_padding_size)}{Style.RESET}"
                rendered_content_lines.append(header_line)
            
            elif item['type'] == 'module':
                item_to_line_mapping[index] = len(rendered_content_lines)
                module = item['obj']
                is_installed = module.is_installed()
                is_supported = module.is_supported()
                
                if not is_supported:
                    status_mark, status_text, semantic_color = self.SYM_EMPTY, "[ NOT SUPPORTED ]", Style.muted()
                elif module.id in self.auto_locked:
                    status_mark, status_text, semantic_color = self.SYM_LOCK, self.STAT_REQUIRED, Style.error()
                elif module.id in self.selected:
                    module_overrides = self.overrides.get(module.id)
                    is_partial = module_overrides and (not module_overrides.get('install_package', True) or (module.stow_package and not module_overrides.get('install_dotfiles', True)))
                    status_mark, status_text, semantic_color = (self.SYM_PART if is_partial else self.SYM_SEL), self.STAT_SEL, (Style.info() if module.id not in self.overrides else Style.warning())
                else:
                    status_mark, status_text, semantic_color = self.SYM_EMPTY, (self.STAT_INST if is_installed else ""), (Style.success() if is_installed else Style.normal())
                
                active_style = Style.highlight() + Style.BOLD if is_cursor else semantic_color
                label_color = active_style if (is_cursor or self.is_active(module.id) or is_installed) else semantic_color
                
                module_label_text = f" {active_style}{status_mark}  {label_color}{Style.BOLD if (self.is_active(module.id) and not is_cursor) else ''}{module.label}{Style.RESET}"
                status_label_text = f'{active_style}{status_text}{Style.RESET}' if status_text else ''
                
                rendered_content_lines.append(f"  {TUI.split_line(module_label_text, status_label_text, content_width)}")

            elif item['type'] == 'sub':
                item_to_line_mapping[index] = len(rendered_content_lines)
                component = item['obj']
                module_id = item['module_id']
                module = self.module_map.get(module_id)
                is_supported = module.is_supported() if module else True
                
                component_is_selected = self.sub_selections.get(module_id, {}).get(component['id'], component.get('default', True)) if is_supported else False
                status_mark = self.SYM_SEL if component_is_selected else self.SYM_EMPTY
                semantic_color = Style.info() if component_is_selected else (Style.normal() if is_supported else Style.muted())
                
                is_required_binary = (component['id'] == 'binary' and module_id in self.auto_locked)
                if is_required_binary: 
                    semantic_color = Style.error()

                active_style = Style.highlight() + Style.BOLD if is_cursor else semantic_color
                indentation = "    " * item['depth']
                lock_icon_suffix = " " if is_required_binary else ""
                
                sub_component_line = f"  {indentation}{active_style}{status_mark}  {component['label']}{lock_icon_suffix}{Style.RESET}"
                rendered_content_lines.append(f"  {TUI.visible_ljust(sub_component_line, content_width)}")

        # Synchronize viewport
        start_line_index = item_to_line_mapping.get(self.cursor_index, 0)
        end_line_index = start_line_index
        
        focused_item = self.flat_items[self.cursor_index] if self.cursor_index < len(self.flat_items) else None
        if focused_item and focused_item['type'] == 'module' and self.expanded.get(focused_item['obj'].id):
            # Look ahead to find the last line of the expanded module's children
            for subsequent_index in range(self.cursor_index + 1, len(self.flat_items)):
                subsequent_item = self.flat_items[subsequent_index]
                if subsequent_item['type'] == 'sub':
                    end_line_index = item_to_line_mapping.get(subsequent_index, end_line_index)
                else:
                    break
        
        # Ensure we always show the top breathing room if we are at the first item
        if start_line_index < self.list_scroll_offset: 
            self.list_scroll_offset = start_line_index
        elif end_line_index >= self.list_scroll_offset + scrollable_window_height: 
            # Scroll down to reveal children, but prioritize keeping the module header in view
            self.list_scroll_offset = min(start_line_index, end_line_index - scrollable_window_height + 1)

        # Clamp list_scroll_offset to prevent orphaned empty space at the end
        maximum_allowable_offset = max(0, len(rendered_content_lines) - scrollable_window_height)
        self.list_scroll_offset = min(self.list_scroll_offset, maximum_allowable_offset)

        # Build final display buffer with FIXED top air
        viewport_lines = [""] # The static top breathing room
        viewport_lines.extend(rendered_content_lines[self.list_scroll_offset : self.list_scroll_offset + scrollable_window_height])
        
        # Pad with empty lines if content is short
        while len(viewport_lines) < height - 3: 
            viewport_lines.append("")
        
        # Footer statistics
        if len(viewport_lines) >= height - 2:
            viewport_lines = viewport_lines[:height - 3]
        active_packages_count = len(self.selected.union(self.auto_locked))
        stats_line_text = f"Selected: {active_packages_count} packages"
        stats_padding = " " * ((width - 2 - len(stats_line_text)) // 2)
        viewport_lines.append(f"{stats_padding}{Style.muted()}{stats_line_text}{Style.RESET}")
        
        # Synchronize scrollbar
        scrollbar_state = self._get_scrollbar(
            len(rendered_content_lines), 
            scrollable_window_height, 
            self.list_scroll_offset, 
            height - 2
        )
        
        return TUI.create_container(
            viewport_lines, width, height, 
            title="PACKAGE LIST", 
            is_focused=(not self.modal), 
            scroll_pos=scrollbar_state['scroll_pos'], 
            scroll_size=scrollbar_state['scroll_size']
        )


    def _draw_right(self, width, height):
        """Internal logic for building the information box."""
        cache_key = (self.cursor_index, width)
        if cache_key in self._info_cache and not self._structure_needs_rebuild:
            info_lines = self._info_cache[cache_key]
        else:
            info_lines = self._get_info_lines(width)
            self._info_cache[cache_key] = info_lines

        scrollable_window_height = height - 4
        max_offset = max(0, len(info_lines) - scrollable_window_height)
        self.info_scroll_offset = min(self.info_scroll_offset, max_offset)
        
        visible_lines = [""]
        visible_lines.extend(info_lines[self.info_scroll_offset : self.info_scroll_offset + scrollable_window_height])
        
        # Pad if needed
        while len(visible_lines) < height - 3:
            visible_lines.append("")
        visible_lines.append("")
            
        scrollbar = self._get_scrollbar(
            len(info_lines), 
            scrollable_window_height, 
            self.info_scroll_offset, 
            height - 2
        )

        return TUI.create_container(
            visible_lines, width, height, 
            title="INFORMATION", 
            is_focused=False, 
            scroll_pos=scrollbar['scroll_pos'], 
            scroll_size=scrollbar['scroll_size']
        )

    def _get_info_lines(self, width):
        """Helper to pre-calculate info lines for scroll limits."""
        info_content_lines = [] 
        if not self.flat_items: 
            return [""]
            
        item = self.flat_items[self.cursor_index]
        content_width = width - 6
        
        if item['type'] == 'module':
            module = item['obj']
            module_overrides = self.overrides.get(module.id, {})
            is_installed = module.is_installed()
            is_supported = module.is_supported()
            
            # Module title color based on state
            status_color = Style.muted() if not is_supported else (Style.error() if module.id in self.auto_locked else (Style.error() if module.id in self.overrides else (Style.info() if module.id in self.selected else (Style.success() if is_installed else Style.highlight()))))
            info_content_lines.extend([f"  {Style.BOLD}{status_color}{module.label.upper()}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}"])

            if module.description:
                for line in TUI.wrap_text(module.description, content_width):
                    info_content_lines.append(f"  {Style.secondary()}{line}{Style.RESET}")
            
            info_content_lines.append("")
            def row(label, value, color_style=""): return f"  {Style.normal()}{label:<13}{Style.RESET} {color_style}{value}{Style.RESET}" 
            
            status_label_text = 'Not Supported' if not is_supported else ('Installed' if is_installed else 'Not Installed')
            status_semantic_style = Style.muted() if not is_supported else (Style.success() if is_installed else Style.secondary())
            info_content_lines.append(row("Status", status_label_text, status_semantic_style))
            
            supported_distros_text = module.get_supported_distros()
            info_content_lines.append(row("Supported OS", supported_distros_text, Style.secondary() if is_supported else Style.muted()))

            # Resolved dependencies for the current distribution
            resolved_dependencies = module.get_dependencies()
            dependency_labels = []
            for dependency_id in resolved_dependencies:
                dependency_module = self.module_map.get(dependency_id)
                dependency_labels.append(dependency_module.label if dependency_module else dependency_id)
            
            dependency_value_text = ", ".join(dependency_labels) if dependency_labels else "None"
            dependency_semantic_style = Style.warning() if (dependency_labels and is_supported) else Style.secondary()
            info_content_lines.append(row("Requires", dependency_value_text, dependency_semantic_style))

            for field_key, field_label in [('manager', 'Manager'), ('package_name', 'Package')]:
                raw_field_value = getattr(module, field_key)
                
                # Handle user overrides first
                if field_key in module_overrides:
                    info_content_lines.append(row(field_label, f"{module_overrides[field_key]}*", Style.secondary()))
                    continue

                if isinstance(raw_field_value, dict):
                    # Find which key matched the current system
                    detected_distro_key = None
                    system_manager = module.system_manager
                    if system_manager.os_id in raw_field_value: 
                        detected_distro_key = system_manager.os_id
                    elif system_manager.is_arch and "arch" in raw_field_value: 
                        detected_distro_key = "arch"
                    elif system_manager.is_debian and "debian" in raw_field_value: 
                        detected_distro_key = "debian"
                    elif "default" in raw_field_value: 
                        detected_distro_key = "default"

                    # Resolve the main value using core logic
                    resolved_system_value = module.get_manager() if field_key == 'manager' else module.get_package_name()
                    
                    if detected_distro_key:
                        primary_distro_info = f"{detected_distro_key.capitalize()}: {resolved_system_value}"
                        other_distro_info_list = [
                            f"{distro_id.capitalize()}: {distro_package_name}" 
                            for distro_id, distro_package_name in raw_field_value.items() 
                            if distro_id != detected_distro_key
                        ]
                        
                        composite_field_value = f"{Style.secondary()}{primary_distro_info}{Style.RESET}"
                        if other_distro_info_list:
                            composite_field_value += f" {Style.muted()}- {' - '.join(other_distro_info_list)}{Style.RESET}"
                        info_content_lines.append(row(field_label, composite_field_value, ""))
                    else:
                        info_content_lines.append(row(field_label, resolved_system_value, Style.secondary() if is_supported else Style.muted()))
                else:
                    # Simple string value
                    display_value = raw_field_value or (module.id if field_key == 'package_name' else "system")
                    info_content_lines.append(row(field_label, display_value, Style.secondary() if is_supported else Style.muted()))
            
            effective_stow_target = module_overrides.get('stow_target', module.stow_target)
            config_tree_lines = module.get_config_tree(target=effective_stow_target)
            if config_tree_lines:
                tree_title_semantic_style = Style.normal() if is_supported else Style.muted()
                info_content_lines.extend(["", f"  {Style.BOLD}{tree_title_semantic_style}CONFIG TREE{Style.RESET}", f"  {Style.muted()}{'─' * 11}{Style.RESET}"])
                for tree_line in config_tree_lines:
                    for wrapped_tree_line in TUI.wrap_text(tree_line, content_width - 2):
                        info_content_lines.append(f"    {wrapped_tree_line}")

        elif item['type'] == 'sub':
            component = item['obj']
            module_id = item['module_id']
            module = self.module_map[module_id]
            is_supported = module.is_supported() if module else True
            component_is_selected = self.sub_selections.get(module_id, {}).get(component['id'], component.get('default', True))
            
            is_required_binary = (component['id'] == 'binary' and module_id in self.auto_locked)
            
            # Determine semantic color and labels based on requirement state
            if is_required_binary:
                status_label_text = "Required"
                status_semantic_color = Style.error()
            else:
                status_label_text = "Selected" if component_is_selected else "Skipped"
                status_semantic_color = Style.info() if component_is_selected else (Style.normal() if is_supported else Style.muted())
            
            lock_icon_suffix = " " if is_required_binary else ""
            info_content_lines.extend([f"  {Style.BOLD}{status_semantic_color}{component['label'].upper()}{lock_icon_suffix}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}"])
            info_content_lines.append(f"  {Style.secondary()}Component of {Style.BOLD}{module.label}{Style.RESET}")
            info_content_lines.append("")
            def row(label, value, color_style=""): return f"  {Style.normal()}{label:<13}{Style.RESET} {color_style}{value}{Style.RESET}"
            info_content_lines.append(row("Status", status_label_text, status_semantic_color))
        else:
            category_name = item['obj']
            info_content_lines.extend([f"  {Style.BOLD}{Style.highlight()}{category_name.upper()}{Style.RESET}", f"  {Style.muted()}{'─' * content_width}{Style.RESET}", f"  {Style.secondary()}Packages in this group:{Style.RESET}", ""])
            for category_module in self.categories[category_name]:
                module_active_mark = "■" if self.is_active(category_module.id) else " "
                module_active_color = Style.info() if self.is_active(category_module.id) else Style.secondary()
                info_content_lines.append(f"    {module_active_color}[{module_active_mark}] {category_module.label}{Style.RESET}")
        
        return info_content_lines

    def handle_input(self, key):
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal: 
            return self._handle_modal_input(key)
        
        # Input Coalescing
        nav_keys = {Keys.UP, Keys.DOWN, Keys.K, Keys.J, Keys.CTRL_K, Keys.CTRL_J}
        if key in nav_keys:
            current_key = key
            while True:
                # Dispatch the current navigation key
                self._dispatch_navigation(current_key)
                # Check if there's another navigation key immediately available
                next_key = TUI.get_key(blocking=False)
                if next_key is None:
                    break
                if next_key in nav_keys:
                    current_key = next_key
                else:
                    return self.handle_input(next_key)
            return None

        terminal_width, terminal_height = shutil.get_terminal_size()
        footer_pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(footer_pills, terminal_width - 4)
        available_height = max(10, terminal_height - 4 - len(footer_lines))
        
        columns_width = terminal_width // 2
        # scrollable_window_height must match the one in _draw_right (available_height - 4)
        scrollable_window_height = available_height - 4
        
        max_info_scroll_offset = max(0, len(self._get_info_lines(columns_width)) - scrollable_window_height)
        
        navigation_map = {
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

    def _dispatch_navigation(self, key):
        """Helper to process navigation keys without full render loop overhead."""
        if key in [Keys.UP, Keys.K]: self._move_cursor(-1)
        elif key in [Keys.DOWN, Keys.J]: self._move_cursor(1)
        elif key == Keys.CTRL_K: self._move_cursor(-5)
        elif key == Keys.CTRL_J: self._move_cursor(5)

    def _handle_modal_input(self, key):
        """Processes results from active modals."""
        modal = self.modal
        if not modal: return None
        result = modal.handle_input(key)
        if isinstance(modal, OptionsModal) and result == "ACCEPT":
            module = self.flat_items[self.cursor_index]['obj']
            override = modal.get_overrides()
            
            # 1. Determine if the module should remain selected (has at least one active component)
            has_active_components = override['install_package'] or (module.has_usable_dotfiles() and override['install_dotfiles'])
            
            if not has_active_components:
                self.selected.discard(module.id)
                self.overrides.pop(module.id, None)
                self.sub_selections.pop(module.id, None)
                self.expanded[module.id] = False
            else:
                self.selected.add(module.id)
                self.expanded[module.id] = True # Fix: Auto-expand to show sub-components
                
                # 2. Sync sub_selections for the recursive dependency engine
                if module.id not in self.sub_selections:
                    self.sub_selections[module.id] = {}
                
                self.sub_selections[module.id]['binary'] = override['install_package']
                if module.has_usable_dotfiles():
                    self.sub_selections[module.id]['dotfiles'] = override['install_dotfiles']
                
                # Enable hierarchical sub-components if it's a first-time selection via modal
                if hasattr(module, 'sub_components') and module.sub_components:
                    # We only force default sub-selections if the module wasn't previously fully configured
                    if not any(k not in ['binary', 'dotfiles'] for k in self.sub_selections[module.id]):
                        self._set_sub_selection_recursive(module.id, module.sub_components, True)

                # 3. Detect if anything was modified compared to defaults to decide color (Yellow vs Blue)
                is_modified = (
                    override['package_name'] != module.get_package_name() or
                    override['manager'] != module.get_manager() or
                    override['stow_target'] != module.stow_target or
                    not override['install_package'] or # Modification: Binary disabled
                    (module.has_usable_dotfiles() and not override['install_dotfiles']) # Modification: Dotfiles disabled
                )
                
                if is_modified:
                    self.overrides[module.id] = override
                else:
                    # If nothing was modified, remove from overrides to revert color to standard Blue
                    self.overrides.pop(module.id, None)

            self.modal = None
            self._structure_needs_rebuild = True
            self._info_cache.clear() # Invalidate cache as state changed
            TUI.push_notification(f"Changes saved for {module.label}", type="INFO")
        elif isinstance(modal, ReviewModal) and result == "INSTALL": self.modal = None; return "CONFIRM"
        elif isinstance(modal, ConfirmModal) and result == "YES":
            self.selected.clear(); self.overrides.clear(); self.sub_selections.clear()
            self.expanded = {cat: True for cat in self.category_names}; self.modal = None; return "WELCOME"
        elif result in ["CANCEL", "CLOSE", "NO"]: self.modal = None
        return None

    def _move_cursor(self, direction): 
        if not self.flat_items: return None
        old_index = self.cursor_index
        self.cursor_index = (self.cursor_index + direction) % len(self.flat_items)
        if old_index != self.cursor_index:
            self.info_scroll_offset = 0
        return None
    def _scroll_info(self, scroll_direction, maximum_offset): 
        self.info_scroll_offset = max(0, min(maximum_offset, self.info_scroll_offset + scroll_direction))
        return None
    def _toggle_sel(self):
        """Handles item selection and group toggling with dependency awareness."""
        self._structure_needs_rebuild = True
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
                if module_id not in self.sub_selections:
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
                if not any(self.sub_selections.get(module_id, {}).values()) and module_id not in self.auto_locked:
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
        if item['type'] == 'header':
            self.expanded[item['obj']] = not self.expanded[item['obj']]
            self._structure_needs_rebuild = True
        elif item['type'] == 'module': self.modal = OptionsModal(item['obj'], self.overrides.get(item['obj'].id))
        return None

    def _collapse(self):
        """Collapses the current header, module or sub-component."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'header':
            self.expanded[item['obj']] = False
            self._structure_needs_rebuild = True
        elif item['type'] == 'module':
            self.expanded[item['obj'].id] = False
            self._structure_needs_rebuild = True
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = False
            self._structure_needs_rebuild = True
        return None

    def _expand(self):
        """Expands the current header, module or sub-component."""
        item = self.flat_items[self.cursor_index]
        if item['type'] == 'header':
            self.expanded[item['obj']] = True
            self._structure_needs_rebuild = True
        elif item['type'] == 'module':
            self.expanded[item['obj'].id] = True
            self._structure_needs_rebuild = True
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = True
            self._structure_needs_rebuild = True
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

