import shutil
import time
import sys
from collections import defaultdict
from core.tui import TUI, Keys, Style, Theme
from core.screens.welcome import Screen
from core.screens.overrides import OverrideModal
from core.screens.summary import SummaryModal

class MenuScreen(Screen):
    """
    Manages the interactive selection menu, including category grouping,
    dependency resolution, and rendering state.
    """
    def __init__(self, modules):
        self.modules = modules
        self.categories = defaultdict(list)
        # Quick lookup map for dependency resolution
        self.mod_map = {m.id: m for m in modules}
        
        # Group modules by category
        for m in modules:
            self.categories[m.category].append(m)
        
        self.category_names = sorted(self.categories.keys())
        self.expanded = {cat: True for cat in self.category_names}
        
        # State tracking
        self.selected = set()      # Manually selected modules
        self.auto_locked = set()   # Modules forced by dependencies (read-only in UI)
        self.overrides = {}        # Custom config for specific modules
        
        # UI State
        self.cursor_idx = 0
        self.list_offset = 0       # Automatic scroll for the list
        self.info_offset = 0       # Manual scroll for the info panel
        self.active_panel = 0      # 0: PACKAGES, 1: INFORMATION
        self.modal = None          # Current active modal
        
        self.flat_items = [] 

    def _resolve_dependencies(self):
        """
        Recalculates self.auto_locked based on the dependencies of 
        currently selected modules.
        """
        locked = set()
        # Iterate through manually selected modules to find their requirements
        for mod_id in self.selected:
            if mod_id in self.mod_map:
                deps = self.mod_map[mod_id].dependencies
                for dep in deps:
                    if dep in self.mod_map:
                        locked.add(dep)
        self.auto_locked = locked

    def _build_flat_list(self):
        """
        Flattens the hierarchical category structure into a linear list
        for rendering based on the expansion state of each category.
        """
        items = []
        for cat in self.category_names:
            items.append({'type': 'header', 'label': cat, 'obj': cat})
            if self.expanded[cat]:
                for mod in self.categories[cat]:
                    items.append({'type': 'module', 'label': mod.label, 'obj': mod})
        return items

    def is_active(self, mod_id):
        """Returns True if module is either selected or locked by dependency."""
        return (mod_id in self.selected) or (mod_id in self.auto_locked)

    def _overlay_string(self, bg, fg, start_x):
        """Composites the modal line onto the background line non-destructively."""
        return TUI.overlay(bg, fg, start_x)

    def _get_info_lines(self, right_width):
        """Helper to pre-calculate info lines for scroll limits."""
        info_lines = [""]
        if not self.flat_items: return info_lines
        
        current_item = self.flat_items[self.cursor_idx]
        r_content_width = right_width - 4
        
        if current_item['type'] == 'module':
            mod = current_item['obj']
            ovr = self.overrides.get(mod.id, {})
            is_inst = mod.is_installed()
            status_color = Style.blue() if is_inst else ""
            
            info_lines.append(f"  {Style.BOLD}{Style.blue()}{mod.label.upper()}{Style.RESET}")
            if mod.description:
                for l in TUI.wrap_text(mod.description, r_content_width):
                    info_lines.append(f"  {Style.DIM}{l}{Style.RESET}")
            info_lines.append("")
            info_lines.append(f"  {Style.BOLD}Status:  {status_color}{('●' if is_inst else '○')} {('Installed' if is_inst else 'Not Installed')}{Style.RESET}")
            
            cur_mgr = mod.get_manager()
            ovr_mgr = ovr.get('manager', cur_mgr)
            is_mgr_mod = 'manager' in ovr and ovr_mgr != cur_mgr
            info_lines.append(f"  {Style.BOLD}Manager: {Style.RESET}{Style.yellow() if is_mgr_mod else ''}{ovr_mgr}{'*' if is_mgr_mod else ''}{Style.RESET}")
            
            cur_pkg = mod.get_package_name()
            ovr_pkg = ovr.get('pkg_name', cur_pkg)
            is_pkg_mod = 'pkg_name' in ovr and ovr_pkg != cur_pkg
            info_lines.append(f"  {Style.BOLD}Package: {Style.RESET}{Style.yellow() if is_pkg_mod else ''}{ovr_pkg}{'*' if is_pkg_mod else ''}{Style.RESET}")
            
            tree = mod.get_config_tree()
            if tree:
                info_lines.append("")
                info_lines.append(f"  {Style.BOLD}CONFIG TREE:{Style.RESET}")
                for l in tree:
                    for wl in TUI.wrap_text(l, r_content_width - 2):
                        info_lines.append(f"    {wl}")
        else:
            cat_name = current_item['obj']
            info_lines.append(f"  {Style.BOLD}{Style.yellow()}{cat_name.upper()}{Style.RESET}")
            info_lines.append(f"  {Style.DIM}Packages in this group:{Style.RESET}")
            info_lines.append("")
            for m in self.categories[cat_name]:
                info_lines.append(f"    {('●' if m.is_installed() else '○')} {m.label}")
        return info_lines

    def render(self):
        """Draws the boxed menu interface to the terminal."""
        self._resolve_dependencies()
        self.flat_items = self._build_flat_list()
        
        if self.cursor_idx >= len(self.flat_items):
            self.cursor_idx = len(self.flat_items) - 1

        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Header & Layout Metrics
        title_text = " PACKAGES SELECTOR "
        bg_blue = Style.blue(bg=True)
        padding = (term_width - len(title_text)) // 2
        header_bar = f"{bg_blue}{Style.crust()}{' '*padding}{title_text}{' '*(term_width-padding-len(title_text))}{Style.RESET}"
        
        # Available space for boxes
        # Overhead calculation: Header(1) + Spacer(1) + Spacer(1) + Pills(1) = 4 lines
        available_height = term_height - 5
        available_height = max(10, available_height)
        
        # Box Widths
        safe_width = term_width - 2
        left_width = int(safe_width * 0.50)
        right_width = safe_width - left_width - 1
        
        # Build Left Content
        # Window size for items is available_height - 3 (excluding header, footer, pills, and status line)
        window_size = available_height - 3
        # First item is at list_lines[1] due to top spacer
        item_line_idx = self.cursor_idx + 1
        
        if item_line_idx < self.list_offset + 1:
            self.list_offset = max(0, item_line_idx - 1)
        elif item_line_idx >= self.list_offset + window_size:
            self.list_offset = item_line_idx - window_size + 1

        list_lines = [""]
        for idx, item in enumerate(self.flat_items):
            is_cursor = (idx == self.cursor_idx)
            
            if item['type'] == 'header':
                cat_name = item['obj']
                icon = "▼" if self.expanded[cat_name] else "►"
                mods_in_cat = self.categories[cat_name]
                active_count = sum(1 for m in mods_in_cat if self.is_active(m.id))
                
                if active_count == 0: sel_mark, header_color = "[ ]", ""
                elif active_count == len(mods_in_cat): sel_mark, header_color = "[■]", Style.green()
                else: sel_mark, header_color = "[-]", Style.yellow()
                
                line = f"  {icon} {sel_mark} {cat_name.upper()}"
                # If cursor is here, use Purple + BOLD
                if is_cursor: 
                    style = Style.mauve() + Style.BOLD
                    list_lines.append(f"{style}{line}{Style.RESET}")
                else: 
                    list_lines.append(f"{Style.BOLD}{header_color}{line}{Style.RESET}")

            elif item['type'] == 'module':
                mod = item['obj']
                installed = mod.is_installed()
                has_override = mod.id in self.overrides
                
                if mod.id in self.auto_locked: mark, color, suffix = "[■]", Style.red(), " "
                elif mod.id in self.selected:
                    ovr = self.overrides.get(mod.id)
                    is_full = ovr['install_pkg'] and (not mod.stow_pkg or ovr['install_dots']) if ovr else True
                    mark, color, suffix = ("[■]" if is_full else "[-]"), (Style.yellow() if has_override else Style.green()), ("*" if has_override else "")
                elif installed: mark, color, suffix = "[ ]", Style.blue(), " ●"
                else: mark, color, suffix = "[ ]", "", ""
                
                line = f"    │     {mark} {mod.label}{suffix}"
                # If cursor is here, use Purple + BOLD
                if is_cursor: 
                    style = Style.mauve() + Style.BOLD
                    list_lines.append(f"{style}{line}{Style.RESET}")
                else: 
                    list_lines.append(f"    {Style.DIM}│{Style.RESET}     {color}{mark} {mod.label}{suffix}{Style.RESET}")

        visible_list = list_lines[self.list_offset : self.list_offset + (available_height - 3)]

        while len(visible_list) < (available_height - 3):
            visible_list.append("")
        
        status_text = f"  {Style.DIM}Selected: {len(self.selected.union(self.auto_locked))} packages{Style.RESET}"
        visible_list.append(status_text)

        # Build Right Content
        info_lines = self._get_info_lines(right_width)
        if self.info_offset > max(0, len(info_lines) - (available_height - 2)):
            self.info_offset = max(0, len(info_lines) - (available_height - 2))
        visible_info = info_lines[self.info_offset : self.info_offset + (available_height - 2)]

        # 4. Generate Boxes
        # Calculate Scroll Parameters
        l_scroll_pos, l_scroll_size = None, None
        if len(list_lines) > (available_height - 2):
            thumb_size = max(1, int((available_height - 2)**2 / len(list_lines)))
            max_off = len(list_lines) - (available_height - 2)
            prog = self.list_offset / max_off
            l_scroll_pos = int(prog * (available_height - 2 - thumb_size))
            l_scroll_size = thumb_size

        r_scroll_pos, r_scroll_size = None, None
        if len(info_lines) > (available_height - 2):
            thumb_size = max(1, int((available_height - 2)**2 / len(info_lines)))
            max_off = len(info_lines) - (available_height - 2)
            prog = self.info_offset / max_off
            r_scroll_pos = int(prog * (available_height - 2 - thumb_size))
            r_scroll_size = thumb_size

        left_box = TUI.create_container(visible_list, left_width, available_height, title="PACKAGES", is_focused=(self.active_panel == 0 and not self.modal), scroll_pos=l_scroll_pos, scroll_size=l_scroll_size)
        right_box = TUI.create_container(visible_info, right_width, available_height, title="INFORMATION", is_focused=(self.active_panel == 1 and not self.modal), scroll_pos=r_scroll_pos, scroll_size=r_scroll_size)
 
        main_content = TUI.stitch_containers(left_box, right_box, gap=1)
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        
        # Footer
        f_move = TUI.pill("h/j/k/l", "Navigate", Theme.SKY)
        f_scroll = TUI.pill("PgUp/Dn", "Scroll Info", Theme.BLUE)
        f_space = TUI.pill("SPACE", "Select", Theme.BLUE)
        f_tab = TUI.pill("TAB", "Overrides", Theme.MAUVE)
        f_enter = TUI.pill("ENTER", "Install", Theme.GREEN)
        f_quit = TUI.pill("Q", "Back", Theme.RED)
        pills_line = f"{f_move}    {f_scroll}    {f_space}    {f_tab}    {f_enter}    {f_quit}"
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(pills_line)) // 2)}{pills_line}")

        # Modal Overlay
        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            for i, m_line in enumerate(m_lines):
                target_y = m_y + i
                if 0 <= target_y < len(buffer):
                    buffer[target_y] = self._overlay_string(buffer[target_y], m_line, m_x)

        # Final buffer management
        final_output = "\n".join(buffer[:term_height])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def toggle_selection(self, item):
        """Handles item selection and group toggling."""
        self._resolve_dependencies()
        if item['type'] == 'module':
            mod_id = item['obj'].id
            if mod_id in self.auto_locked: return 
            if mod_id in self.selected:
                self.selected.remove(mod_id)
                self.overrides.pop(mod_id, None)
            else:
                self.selected.add(mod_id)
        elif item['type'] == 'header':
            cat = item['obj']
            mods = self.categories[cat]
            all_active = all(self.is_active(m.id) for m in mods)
            if all_active:
                for m in mods: 
                    if m.id in self.selected: 
                        self.selected.remove(m.id)
                        self.overrides.pop(m.id, None)
            else:
                for m in mods: 
                    if m.id not in self.auto_locked:
                        self.selected.add(m.id)

    def handle_input(self, key):
        """Processes keyboard input and returns navigation actions."""
        # Priority 1: Handle Active Modal
        if self.modal:
            action = self.modal.handle_input(key)
            
            # Handling OverrideModal
            if isinstance(self.modal, OverrideModal):
                if action == "ACCEPT":
                    mod = self.flat_items[self.cursor_idx]['obj']
                    ovr = self.modal.get_overrides()
                    if not ovr['install_pkg'] and not (mod.stow_pkg and ovr['install_dots']):
                        self.selected.discard(mod.id)
                        self.overrides.pop(mod.id, None)
                    else:
                        self.selected.add(mod.id)
                        self.overrides[mod.id] = ovr
                    self.modal = None
                elif action == "CANCEL":
                    self.modal = None
                    
            # Handling SummaryModal
            elif isinstance(self.modal, SummaryModal):
                if action == "INSTALL":
                    self.modal = None
                    return "CONFIRM"
                elif action in ["CANCEL", "CLOSE"]:
                    self.modal = None
            return None

        # Global Back Key
        if key in [Keys.Q, Keys.Q_UPPER]:
            return "WELCOME"


        # --- PANEL-SPECIFIC LOGIC ---
        
        # Determine info panel scroll limit for shared use
        term_height = shutil.get_terminal_size().lines
        available_height = max(10, term_height - 5)
        right_width = int((shutil.get_terminal_size().columns - 2) * 0.5)
        info_lines = self._get_info_lines(right_width)
        max_info_off = max(0, len(info_lines) - (available_height - 2))

        if self.active_panel == 1:
            # INFORMATION PANEL FOCUS
            if key in [Keys.UP, Keys.K]:
                self.info_offset = max(0, self.info_offset - 1)
            elif key in [Keys.DOWN, Keys.J]:
                self.info_offset = min(max_info_off, self.info_offset + 1)
            elif key in [Keys.H, Keys.LEFT]:
                self.active_panel = 0
            elif key == Keys.PGUP:
                self.info_offset = max(0, self.info_offset - 5)
            elif key == Keys.PGDN:
                self.info_offset = min(max_info_off, self.info_offset + 5)
            return None

        # PACKAGES PANEL FOCUS (active_panel == 0)
        if key in [Keys.UP, Keys.K]: 
            self.cursor_idx = max(0, self.cursor_idx - 1)
            self.info_offset = 0
        
        elif key in [Keys.DOWN, Keys.J]: 
            self.cursor_idx = min(len(self.flat_items) - 1, self.cursor_idx + 1)
            self.info_offset = 0

        # Detail Panel Scroll (Available even when focus is on Packages)
        elif key == Keys.PGUP:
            self.info_offset = max(0, self.info_offset - 5)
        elif key == Keys.PGDN:
            self.info_offset = min(max_info_off, self.info_offset + 5)
        elif key == Keys.CTRL_K: self.cursor_idx = max(0, self.cursor_idx - 5)
        elif key == Keys.CTRL_J: self.cursor_idx = min(len(self.flat_items) - 1, self.cursor_idx + 5)
        elif key == Keys.SPACE: self.toggle_selection(self.flat_items[self.cursor_idx])
        elif key == Keys.TAB:
            current = self.flat_items[self.cursor_idx]
            if current['type'] == 'header': self.expanded[current['obj']] = not self.expanded[current['obj']]
            elif current['type'] == 'module':
                self.modal = OverrideModal(current['obj'], self.overrides.get(current['obj'].id))
        elif key in [Keys.H, Keys.LEFT]:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header': self.expanded[current['obj']] = False
        elif key in [Keys.L, Keys.RIGHT]:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header': self.expanded[current['obj']] = True
             else: self.active_panel = 1
        elif key == Keys.ENTER:
            total_selection = self.selected.union(self.auto_locked)
            if len(total_selection) > 0: self.modal = SummaryModal(self.modules, total_selection, self.overrides)
        
        return None
