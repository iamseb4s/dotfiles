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
    STAT_LOCKED, STAT_SEL, STAT_INST = "[ LOCKED ]", "[ SELECTED ]", "[ INSTALLED ]"

    def __init__(self, modules):
        self.modules, self.mod_map = modules, {m.id: m for m in modules}
        self.categories = defaultdict(list)
        for m in modules: self.categories[m.category].append(m)
        self.category_names = sorted(self.categories.keys())
        self.expanded = {cat: True for cat in self.category_names}
        
        # State tracking
        self.selected, self.auto_locked, self.overrides = set(), set(), {}
        self.sub_selections = {} # {module_id: {sub_id: bool}}
        
        # UI State
        self.cursor_idx, self.list_offset, self.info_offset, self.modal = 0, 0, 0, None
        self.flat_items = []

    def _resolve_dependencies(self):
        """
        Recalculates self.auto_locked based on the dependencies of 
        currently selected modules.
        """
        locked = set()
        for mid in self.selected:
            if mid in self.mod_map:
                for dep in self.mod_map[mid].dependencies:
                    if dep in self.mod_map: locked.add(dep)
        self.auto_locked = locked

    def _build_flat_list(self):
        """
        Flattens the hierarchical category structure into a linear list
        for rendering including sub-components.
        """
        items = []
        for cat in self.category_names:
            items.append({'type': 'header', 'obj': cat})
            if self.expanded.get(cat, True):
                for m in self.categories[cat]:
                    items.append({'type': 'module', 'obj': m, 'depth': 0})
                    # Only show sub-components if module is expanded
                    if self.expanded.get(m.id, False):
                        has_manual_components = hasattr(m, 'sub_components') and m.sub_components
                        
                        if has_manual_components:
                            self._flatten_sub_components(m.sub_components, items, 1, m.id)
                        else:
                            # Inject Package component if no sub_components defined
                            bin_comp = {"id": "binary", "label": f"{m.label} Package", "default": True}
                            items.append({'type': 'sub', 'obj': bin_comp, 'depth': 1, 'module_id': m.id})
                        
                        # Inject Dotfiles component if usable and not explicitly in sub_components
                        if m.has_usable_dotfiles():
                            has_manual_dot = any(c.get('id') == 'dotfiles' for c in getattr(m, 'sub_components', []))
                            if not has_manual_dot:
                                dot_comp = {"id": "dotfiles", "label": "Deploy Configuration Files", "default": True}
                                items.append({'type': 'sub', 'obj': dot_comp, 'depth': 1, 'module_id': m.id})
        return items

    def _flatten_sub_components(self, components, items, depth, module_id):
        for comp in components:
            items.append({'type': 'sub', 'obj': comp, 'depth': depth, 'module_id': module_id})
            # Sub-components are expanded by default if they have children
            if self.expanded.get(f"{module_id}:{comp['id']}", True) and comp.get('children'):
                self._flatten_sub_components(comp['children'], items, depth + 1, module_id)

    def is_active(self, mid):
        """Returns True if module is either selected or locked by dependency."""
        return (mid in self.selected) or (mid in self.auto_locked)

    def _get_scrollbar(self, total, visible, offset):
        """Returns scroll position and size for create_container."""
        if total <= visible: return {'scroll_pos': None, 'scroll_size': None}
        sz = max(1, int(visible**2 / total))
        return {'scroll_pos': int((offset / (total - visible)) * (visible - sz)), 'scroll_size': sz}

    def render(self):
        """Draws the boxed menu interface to the terminal."""
        self._resolve_dependencies(); self.flat_items = self._build_flat_list()
        self.cursor_idx = min(self.cursor_idx, len(self.flat_items) - 1)
        tw, th = shutil.get_terminal_size()
        
        header = f"{Style.blue(bg=True)}{Style.crust()}{' PACKAGES SELECTOR '.center(tw)}{Style.RESET}"
        pills = self._get_footer_pills()
        footer = TUI.wrap_pills(pills, tw - 4)
        av_h = max(10, th - 4 - len(footer))
        lw, rw = tw // 2, tw - (tw // 2) - 1
        
        # Build panels and assemble
        left = self._draw_left(lw, av_h)
        right = self._draw_right(rw, av_h)
        buffer = [header, ""] + TUI.stitch_containers(left, right, gap=1) + [""]
        
        for fl in footer:
            fv = TUI.visible_len(fl); lp = (tw - fv) // 2
            rp = tw - fv - lp
            buffer.append(f"{' ' * lp}{fl}{' ' * rp}")

        if self.modal:
            ml, my, mx = self.modal.render()
            for i, l in enumerate(ml):
                if 0 <= my+i < len(buffer): buffer[my+i] = TUI.overlay(buffer[my+i], l, mx)
        
        buffer = TUI.draw_notifications(buffer)
        sys.stdout.write("\033[H" + "\n".join([TUI.visible_ljust(l, tw) for l in buffer[:th]]) + "\033[J")
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
        if self.cursor_idx + 1 < self.list_offset + 1: self.list_offset = max(0, self.cursor_idx)
        elif self.cursor_idx + 1 >= self.list_offset + window_height: self.list_offset = self.cursor_idx - window_height + 1

        lines = [""]
        for idx, item in enumerate(self.flat_items):
            is_cursor = (idx == self.cursor_idx)
            if item['type'] == 'header':
                if idx > 0: lines.append("")
                label = f" {item['obj'].upper()} "; gap = content_width - len(label); left_pad = gap // 2
                color = Style.highlight() if is_cursor else Style.normal()
                lines.append(f"  {color}{Style.BOLD if is_cursor else ''}{'─' * left_pad}{label}{'─' * (gap - left_pad)}{Style.RESET}")
            elif item['type'] == 'module':
                module = item['obj']; is_installed = module.is_installed(); is_supported = module.is_supported()
                
                if not is_supported:
                    mark, status_text, color = self.SYM_EMPTY, "[ NOT SUPPORTED ]", Style.muted()
                elif module.id in self.auto_locked:
                    mark, status_text, color = self.SYM_LOCK, self.STAT_LOCKED, Style.red()
                elif module.id in self.selected:
                    override = self.overrides.get(module.id); part = override and (not override.get('install_package', True) or (module.stow_pkg and not override.get('install_dotfiles', True)))
                    mark, status_text, color = (self.SYM_PART if part else self.SYM_SEL), self.STAT_SEL, (Style.green() if module.id not in self.overrides else Style.yellow())
                else:
                    mark, status_text, color = self.SYM_EMPTY, (self.STAT_INST if is_installed else ""), (Style.blue() if is_installed else Style.normal())
                
                style = Style.highlight() + Style.BOLD if is_cursor else color
                label_color = style if (is_cursor or self.is_active(module.id) or is_installed) else color
                
                label_text = f" {style}{mark}  {label_color}{Style.BOLD if (self.is_active(module.id) and not is_cursor) else ''}{module.label}{Style.RESET}"
                lines.append(f"  {TUI.split_line(label_text, f'{style}{status_text}{Style.RESET}' if status_text else '', content_width)}")

            elif item['type'] == 'sub':
                comp = item['obj']
                module_id = item['module_id']
                module = self.mod_map.get(module_id)
                is_supported = module.is_supported() if module else True
                
                # Check if it's selected in sub_selections, fallback to its own default
                is_sel = self.sub_selections.get(module_id, {}).get(comp['id'], comp.get('default', True)) if is_supported else False
                mark = self.SYM_SEL if is_sel else self.SYM_EMPTY
                
                style = Style.highlight() + Style.BOLD if is_cursor else (Style.green() if is_sel else Style.muted())
                label_style = style if is_supported else Style.muted()
                
                # Use spaces for indentation as requested
                indent = "    " * item['depth']
                label_text = f"  {indent}{label_style}{mark}  {comp['label']}{Style.RESET}"
                lines.append(f"  {TUI.visible_ljust(label_text, content_width)}")

        visible_lines = lines[self.list_offset : self.list_offset + window_height]
        while len(visible_lines) < window_height: visible_lines.append("")
        stats_text = f"Selected: {len(self.selected.union(self.auto_locked))} packages"
        visible_lines.append(f"{' ' * ((width - 2 - len(stats_text)) // 2)}{Style.muted()}{stats_text}{Style.RESET}")
        
        scrollbar = self._get_scrollbar(len(lines), height - 2, self.list_offset)
        return TUI.create_container(visible_lines, width, height, title="PACKAGES", is_focused=(not self.modal), scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _draw_right(self, width, height):
        """Internal logic for building the information box."""
        info_lines = self._get_info_lines(width); max_offset = max(0, len(info_lines) - (height - 2))
        self.info_offset = min(self.info_offset, max_offset)
        scrollbar = self._get_scrollbar(len(info_lines), height - 2, self.info_offset)
        return TUI.create_container(info_lines[self.info_offset : self.info_offset + height - 2], width, height, title="INFORMATION", is_focused=False, scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _get_info_lines(self, width):
        """Helper to pre-calculate info lines for scroll limits."""
        lines = [""]
        if not self.flat_items: return lines
        item = self.flat_items[self.cursor_idx]; content_width = width - 6
        if item['type'] == 'module':
            module = item['obj']; override = self.overrides.get(module.id, {}); is_installed = module.is_installed(); is_supported = module.is_supported()
            color = Style.muted() if not is_supported else (Style.red() if module.id in self.auto_locked else (Style.yellow() if module.id in self.overrides else (Style.green() if module.id in self.selected else (Style.blue() if is_installed else Style.highlight()))))
            lines.extend([f"  {Style.BOLD}{color}{module.label.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * content_width}{Style.RESET}"])
            if module.description:
                for line in TUI.wrap_text(module.description, content_width): lines.append(f"  {Style.muted()}{line}{Style.RESET}")
            lines.append("")
            def row(label, value, color_style=""): return f"  {Style.subtext1()}{label:<13}{Style.RESET} {color_style}{value}{Style.RESET}"
            
            status_text = 'Not Supported' if not is_supported else ('Installed' if is_installed else 'Not Installed')
            status_style = Style.muted() if not is_supported else (Style.blue() if is_installed else Style.muted())
            lines.append(row("Status", status_text, status_style))
            
            supported_os = module.get_supported_distros()
            lines.append(row("Supported OS", supported_os, Style.normal() if is_supported else Style.muted()))

            for key, label in [('manager', 'Manager'), ('package_name', 'Package')]:
                current_value = getattr(module, key) if key != 'package_name' else module.get_package_name()
                value = override.get(key, current_value)
                lines.append(row(label, f"{value}{'*' if value != current_value else ''}", Style.muted() if not is_supported else ""))
            
            current_target = override.get('stow_target', module.stow_target)
            tree = module.get_config_tree(target=current_target)
            if tree:
                lines.extend(["", f"  {Style.BOLD}{Style.subtext0()}CONFIG TREE{Style.RESET}", f"  {Style.surface1()}{'─' * 11}{Style.RESET}"])
                for line in tree:
                    for wrapped_line in TUI.wrap_text(line, content_width - 2): lines.append(f"    {Style.muted()}{wrapped_line}{Style.RESET}")
        elif item['type'] == 'sub':
            comp = item['obj']; module_id = item['module_id']
            module = self.mod_map[module_id]
            is_sel = self.sub_selections.get(module_id, {}).get(comp['id'], comp.get('default', True))
            color = Style.green() if is_sel else Style.muted()
            lines.extend([f"  {Style.BOLD}{color}{comp['label'].upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * content_width}{Style.RESET}"])
            lines.append(f"  {Style.muted()}Component of {Style.BOLD}{module.label}{Style.RESET}")
            lines.append("")
            lines.append(f"  {Style.subtext1()}Status:    {Style.RESET}{color}{'Selected' if is_sel else 'Skipped'}{Style.RESET}")
        else:
            category = item['obj']; lines.extend([f"  {Style.BOLD}{Style.highlight()}{category.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * content_width}{Style.RESET}", f"  {Style.muted()}Packages in this group:{Style.RESET}", ""])
            for module in self.categories[category]:
                module_status = "■" if self.is_active(module.id) else " "; color = Style.green() if self.is_active(module.id) else Style.muted()
                lines.append(f"    {color}[{module_status}] {module.label}{Style.RESET}")
        return lines

    def handle_input(self, key):
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal: return self._handle_modal_input(key)
        
        cw = shutil.get_terminal_size().columns // 2; win = max(10, shutil.get_terminal_size().lines - 5) - 2
        max_info = max(0, len(self._get_info_lines(cw)) - win)
        
        nav = {
            Keys.UP: lambda: self._move_cursor(-1), Keys.K: lambda: self._move_cursor(-1),
            Keys.DOWN: lambda: self._move_cursor(1), Keys.J: lambda: self._move_cursor(1),
            Keys.CTRL_K: lambda: self._move_cursor(-5), Keys.CTRL_J: lambda: self._move_cursor(5),
            Keys.PGUP: lambda: self._scroll_info(-5, max_info), Keys.PGDN: lambda: self._scroll_info(5, max_info),
            Keys.SPACE: self._toggle_sel, Keys.TAB: self._handle_tab,
            Keys.LEFT: self._collapse, Keys.H: self._collapse,
            Keys.RIGHT: self._expand, Keys.L: self._expand,
            Keys.ENTER: self._trigger_install, Keys.Q: self._back, Keys.Q_UPPER: self._back
        }
        return nav[key]() if key in nav else None

    def _handle_modal_input(self, key):
        """Processes results from active modals."""
        modal = self.modal
        if not modal: return None
        result = modal.handle_input(key)
        if isinstance(modal, OptionsModal) and result == "ACCEPT":
            module = self.flat_items[self.cursor_idx]['obj']; override = modal.get_overrides()
            if not override['install_package'] and not (module.stow_pkg and override['install_dotfiles']):
                self.selected.discard(module.id); self.overrides.pop(module.id, None)
            else: self.selected.add(module.id); self.overrides[module.id] = override
            self.modal = None; TUI.push_notification(f"Changes saved for {module.label}", type="INFO")
        elif isinstance(modal, ReviewModal) and result == "INSTALL": self.modal = None; return "CONFIRM"
        elif isinstance(modal, ConfirmModal) and result == "YES":
            self.selected.clear(); self.overrides.clear(); self.modal = None; return "WELCOME"
        elif result in ["CANCEL", "CLOSE", "NO"]: self.modal = None
        return None

    def _move_cursor(self, direction): self.cursor_idx = max(0, min(len(self.flat_items) - 1, self.cursor_idx + direction)); self.info_offset = 0; return None
    def _scroll_info(self, direction, max_offset): self.info_offset = max(0, min(max_offset, self.info_offset + direction)); return None
    def _toggle_sel(self):
        """Handles item selection and group toggling."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'module':
            module = item['obj']
            if not module.is_supported():
                TUI.push_notification(f"{module.label} is not available for your OS", type="ERROR")
                return
            if module.id in self.auto_locked: return
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
            comp = item['obj']
            if module_id not in self.selected:
                self.selected.add(module_id)
                self.expanded[module_id] = True # Ensure expanded if a child is picked
                self.sub_selections[module_id] = {}
            
            # Get current state or default
            current_state = self.sub_selections[module_id].get(comp['id'], comp.get('default', True))
            new_state = not current_state
            
            # Update this component and its children
            self.sub_selections[module_id][comp['id']] = new_state
            if 'children' in comp:
                self._set_sub_selection_recursive(module_id, comp['children'], new_state)
            
            # If we enable a child, we must ensure parents are enabled
            if new_state:
                self._ensure_parent_path_enabled(module_id, comp['id'])

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
        for comp in components:
            if module_id not in self.sub_selections: self.sub_selections[module_id] = {}
            self.sub_selections[module_id][comp['id']] = state
            if 'children' in comp:
                self._set_sub_selection_recursive(module_id, comp['children'], state)

    def _ensure_parent_path_enabled(self, module_id, target_comp_id):
        """Ensures that all parents of a sub-component are enabled."""
        module = self.mod_map.get(module_id)
        if not module or not hasattr(module, 'sub_components'): return

        def find_and_enable_parents(components, path):
            for comp in components:
                if comp['id'] == target_comp_id:
                    for p_id in path:
                        self.sub_selections[module_id][p_id] = True
                    return True
                if 'children' in comp:
                    if find_and_enable_parents(comp['children'], path + [comp['id']]):
                        return True
            return False

        find_and_enable_parents(module.sub_components, [])

    def _handle_tab(self):
        """Handles TAB key for expanding headers or opening options."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = not self.expanded[item['obj']]
        elif item['type'] == 'module': self.modal = OptionsModal(item['obj'], self.overrides.get(item['obj'].id))
        return None

    def _collapse(self):
        """Collapses the current header, module or sub-component."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = False
        elif item['type'] == 'module': self.expanded[item['obj'].id] = False
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = False
        return None

    def _expand(self):
        """Expands the current header, module or sub-component."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = True
        elif item['type'] == 'module': self.expanded[item['obj'].id] = True
        elif item['type'] == 'sub':
            self.expanded[f"{item['module_id']}:{item['obj']['id']}"] = True
        return None

    def _trigger_install(self):
        """Shows the installation review modal."""
        all_s = self.selected.union(self.auto_locked)
        
        # Inject sub-selections into overrides before passing to Review/Installer
        for mid in self.selected:
            if mid not in self.overrides:
                mod = self.mod_map[mid]
                self.overrides[mid] = {
                    'package_name': mod.get_package_name(),
                    'manager': mod.get_manager(),
                    'install_package': True,
                    'install_dotfiles': mod.has_usable_dotfiles(),
                    'stow_target': mod.stow_target
                }
            self.overrides[mid]['sub_selections'] = self.sub_selections.get(mid, {})

        if all_s: self.modal = ReviewModal(self.modules, all_s, self.overrides)
        else: TUI.push_notification("Select at least one package to install", type="ERROR")
        return None

    def _back(self):
        """Returns to the welcome screen, with confirmation if changes exist."""
        if self.selected: self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?"); return None
        return "WELCOME"

