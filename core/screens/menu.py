import shutil
import time
import sys
from collections import defaultdict
from core.tui import TUI, Keys, Style
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
        self.modal = None          # Current active modal
        
        self.flat_items = [] 
        self.exit_pending = False
        self.last_esc_time = 0

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

    def _build_bg_line(self, i, visible_list, visible_info, available_height, split_width, safe_width, list_lines, info_lines):
        """Helper to build a single background row for side-by-side view."""
        left = visible_list[i] if i < len(visible_list) else ""
        right = visible_info[i] if i < len(visible_info) else ""
        
        # Left column + Scrollbar L
        l_len = TUI.visible_len(left)
        l_padding = " " * (split_width - 2 - l_len)
        if len(list_lines) > available_height:
            l_prog = self.list_offset / (len(list_lines) - available_height)
            l_indicator_pos = int(l_prog * (available_height - 1))
            scroll_l = f"{Style.hex('#89B4FA')}┃{Style.RESET}" if i == l_indicator_pos else f"{Style.DIM}│{Style.RESET}"
        else:
            scroll_l = " "

        central_sep = f"{Style.DIM}│{Style.RESET}"
        
        # Right column + Scrollbar R
        r_content_width = safe_width - split_width - 4
        r_len = TUI.visible_len(right)
        r_padding = " " * max(0, r_content_width - 2 - r_len)
        if len(info_lines) > available_height:
            r_prog = self.info_offset / (len(info_lines) - available_height)
            r_indicator_pos = int(r_prog * (available_height - 1))
            scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}" if i == r_indicator_pos else f"{Style.DIM}│{Style.RESET}"
        else:
            scroll_r = " "

        return f"{left}{l_padding} {scroll_l} {central_sep} {right}{r_padding} {scroll_r}"

    def _overlay_string(self, bg, fg, start_x):
        """Simple overlay that centers the modal line."""
        # Instead of real overlay, we'll just build a new line:
        # [PADDING_X] [MODAL_LINE] [REMAINING_PADDING]
        # This effectively "hides" the background where the modal is.
        term_width = shutil.get_terminal_size().columns
        fg_visible_len = TUI.visible_len(fg)
        
        left_pad = " " * start_x
        right_pad = " " * (term_width - start_x - fg_visible_len)
        
        return f"{left_pad}{fg}{right_pad}"

    def render(self):
        """Draws the menu interface to the terminal."""
        # Ensure dependencies are up-to-date before drawing
        self._resolve_dependencies()
        self.flat_items = self._build_flat_list()
        
        # Prevent cursor from going out of bounds if list shrinks
        if self.cursor_idx >= len(self.flat_items):
            self.cursor_idx = len(self.flat_items) - 1

        # Viewport logic for vertical scrolling
        term_height = shutil.get_terminal_size().lines
        # Layout reservation: header, status, footer and margin
        available_height = term_height - 9
        available_height = max(1, available_height)

        # Automatic list scroll: keep cursor within visible range
        if self.cursor_idx < self.list_offset:
            self.list_offset = self.cursor_idx
        elif self.cursor_idx >= self.list_offset + available_height:
            self.list_offset = self.cursor_idx - available_height + 1

        # --- MODERN HEADER ---
        term_width = shutil.get_terminal_size().columns
        title_text = " PACKAGES SELECTOR "
        
        # Colors
        bg_blue = Style.hex("89B4FA", bg=True)
        text_black = "\033[30m"
        
        # Centering logic for title
        padding = (term_width - len(title_text)) // 2
        padding = max(0, padding)
        left_pad = " " * padding
        right_pad = " " * (term_width - padding - len(title_text))
        
        # Render Bar: [BG_BLUE + BLACK]   TITLE   [RESET]
        header_bar = f"{bg_blue}{text_black}{left_pad}{title_text}{right_pad}{Style.RESET}"
        
        buffer = []
        buffer.append(header_bar)
        buffer.append("")
        buffer.append(f"  {Style.DIM}Select the packages you wish to install and configure:{Style.RESET}")
        buffer.append("")

        # --- RENDER LOGIC (SPLIT VIEW) ---
        list_lines = []
        for idx, item in enumerate(self.flat_items):
            is_cursor = (idx == self.cursor_idx)
            cursor_char = ">" if is_cursor else " "
            
            # --- RENDER HEADER (CATEGORY) ---
            if item['type'] == 'header':
                cat_name = item['obj']
                icon = "▼" if self.expanded[cat_name] else "►"
                
                mods_in_cat = self.categories[cat_name]
                # Calculate partial selection state
                active_count = sum(1 for m in mods_in_cat if self.is_active(m.id))
                
                if active_count == 0:
                    sel_mark = "[ ]"
                    header_color = ""
                elif active_count == len(mods_in_cat):
                    sel_mark = "[■]"
                    header_color = Style.hex("55E6C1") # Pastel Green (Full)
                else:
                    sel_mark = "[-]" # Partial selection
                    header_color = Style.hex("FDCB6E") # Pastel Yellow (Partial)
                
                # Header line with 2-space global margin
                line = f"  {cursor_char} {icon} {sel_mark} {cat_name.upper()}"
                
                # Draw category headers with status indicators
                if is_cursor:
                    # Cursor highlight: Bold + Inverted
                    list_lines.append(f"{Style.BOLD}{Style.INVERT}{line}   {Style.RESET}")
                else:
                    # Selection state color
                    list_lines.append(f"{Style.BOLD}{header_color}{line}{Style.RESET}")

            # --- RENDER MODULE (PACKAGE) ---
            elif item['type'] == 'module':
                mod = item['obj']
                installed = mod.is_installed()
                has_override = mod.id in self.overrides
                
                # Determine visual state based on selection, overrides and installation
                if mod.id in self.auto_locked:
                    mark = "[■]"        # Locked by dependency
                    color = Style.hex("FF6B6B")  # Pastel Red
                    suffix = " "       # Lock icon suffix
                elif mod.id in self.selected:
                    ovr = self.overrides.get(mod.id)
                    if ovr:
                        # Full if both are selected, or if one is selected and the other doesn't exist
                        is_full = ovr['install_pkg'] and (not mod.stow_pkg or ovr['install_dots'])
                        mark = "[■]" if is_full else "[-]"
                    else:
                        mark = "[■]"
                    color = Style.hex("FDCB6E") if has_override else Style.hex("55E6C1") # Yellow if custom, else Green
                    suffix = "*" if has_override else ""
                elif installed:
                    mark = "[ ]"        # Not selected but installed
                    color = Style.hex("89B4FA") # Pastel Blue
                    suffix = " ●"       # Installed indicator
                else:
                    mark = "[ ]"
                    color = ""
                    suffix = ""
                
                # Tree structure for package listing
                hierarchy_icon = "│"
                line = f"  {cursor_char} {hierarchy_icon}     {mark} {mod.label}{suffix}"
                
                if is_cursor:
                    # Cursor highlight: Invert whole line for better feedback
                    list_lines.append(f"{Style.INVERT}{line}   {Style.RESET}")
                else:
                    # Normal mode: Dim hierarchy icon, color package label
                    styled_line = f"  {cursor_char} {Style.DIM}{hierarchy_icon}{Style.RESET}     {color}{mark} {mod.label}{suffix}{Style.RESET}"
                    list_lines.append(styled_line)

        # --- INFO PANEL (RIGHT COLUMN) ---
        info_lines = []
        current_item = self.flat_items[self.cursor_idx]
        
        # Pre-calculate right panel width for text wrapping
        safe_width = term_width - 2
        split_width = int(safe_width * 0.50)
        # Margin: split_width(left) + padding(1) + sep(1) + padding(1) + [CONTENT] + padding(1) + scroll(1) + margin(1)
        r_panel_width = safe_width - split_width - 6
        
        if current_item['type'] == 'module':
            mod = current_item['obj']
            ovr = self.overrides.get(mod.id, {})
            
            # Header
            is_installed = mod.is_installed()
            status_str = "Installed" if is_installed else "Not Installed"
            status_icon = "●" if is_installed else "○"
            status_color = Style.hex("#89B4FA") if is_installed else ""
            
            info_lines.append(f"{Style.BOLD}{Style.hex('#89B4FA')}{mod.label.upper()}{Style.RESET}")
            if mod.description:
                # Wrap description to panel width
                wrapped_desc = TUI.wrap_text(mod.description, r_panel_width)
                for line in wrapped_desc:
                    info_lines.append(f"{Style.DIM}{line}{Style.RESET}")
            info_lines.append("")
            info_lines.append(f"{Style.BOLD}Status:  {status_color}{status_icon} {status_str}{Style.RESET}")
            
            # Info Panel values: Only yellow if specifically modified
            # Manager detection
            current_mgr = mod.get_manager()
            ovr_mgr = ovr.get('manager', current_mgr)
            is_mgr_mod = 'manager' in ovr and ovr_mgr != current_mgr
            mgr_color = Style.hex("#FDCB6E") if is_mgr_mod else ""
            mgr_suffix = "*" if is_mgr_mod else ""
            info_lines.append(f"{Style.BOLD}Manager: {Style.RESET}{mgr_color}{ovr_mgr}{mgr_suffix}{Style.RESET}")
            
            # Package Name detection
            current_pkg = mod.get_package_name()
            ovr_pkg = ovr.get('pkg_name', current_pkg)
            is_pkg_mod = 'pkg_name' in ovr and ovr_pkg != current_pkg
            pkg_color = Style.hex("#FDCB6E") if is_pkg_mod else ""
            pkg_suffix = "*" if is_pkg_mod else ""
            info_lines.append(f"{Style.BOLD}Package: {Style.RESET}{pkg_color}{ovr_pkg}{pkg_suffix}{Style.RESET}")
            
            # Config Tree
            tree = mod.get_config_tree()
            if tree:
                info_lines.append("")
                info_lines.append(f"{Style.BOLD}CONFIG TREE:{Style.RESET}")
                for l in tree:
                    # Wrap each line of the tree if it exceeds panel width
                    # We subtract 2 for the tree indentation "  "
                    wrapped_tree = TUI.wrap_text(l, r_panel_width - 2)
                    for wl in wrapped_tree:
                        info_lines.append(f"  {wl}")
        else:
            cat_name = current_item['obj']
            info_lines.append(f"{Style.BOLD}{Style.hex('#FDCB6E')}{cat_name.upper()}{Style.RESET}")
            info_lines.append(f"{Style.DIM}Packages in this group:{Style.RESET}")
            info_lines.append("")
            for m in self.categories[cat_name]:
                mark = "●" if m.is_installed() else "○"
                info_lines.append(f"  {mark} {m.label}")

        # Bound check info_offset after possible change
        if self.info_offset > max(0, len(info_lines) - available_height):
            self.info_offset = max(0, len(info_lines) - available_height)

        # --- FINAL RENDER (Side-by-side) ---
        if term_width > 100:
            # Slicing viewports for list and info
            visible_list = list_lines[self.list_offset : self.list_offset + available_height]
            visible_info = info_lines[self.info_offset : self.info_offset + available_height]
            
            for i in range(available_height):
                bg_line = self._build_bg_line(i, visible_list, visible_info, available_height, split_width, safe_width, list_lines, info_lines)
                
                if self.modal:
                    m_lines, m_y, m_x = self.modal.render()
                    terminal_line = i + 6 
                    if m_y <= terminal_line < (m_y + len(m_lines)):
                        m_idx = terminal_line - m_y
                        modal_line = m_lines[m_idx]
                        bg_line = self._overlay_string(bg_line, modal_line, m_x)
                
                buffer.append(bg_line)
        else:
            # Fallback to simple list for narrow terminals
            visible_list = list_lines[self.list_offset : self.list_offset + available_height]
            for line in visible_list:
                buffer.append(line)
            # Fill remaining to keep footer stable
            for _ in range(available_height - len(visible_list)):
                buffer.append("")

        # --- FOOTER (Pills) ---
        buffer.append("")
        total_active = len(self.selected.union(self.auto_locked))
        buffer.append(f"  Selected: {total_active} packages")
        buffer.append("")
        
        # Footer Content
        f_move   = TUI.pill("↑/↓/k/j", "Move", "81ECEC") # Cyan
        f_scroll = TUI.pill("PgUp/Dn", "Scroll Info", "89B4FA") # Blue
        f_space  = TUI.pill("SPACE", "Select", "89B4FA") # Blue
        f_tab    = TUI.pill("TAB", "Overrides", "CBA6F7") # Mauve
        f_enter  = TUI.pill("ENTER", "Install", "a6e3a1")# Green
        f_back   = TUI.pill("R", "Back", "f9e2af")       # Yellow
        f_quit   = TUI.pill("Q", "Exit", "f38ba8")       # Red
        
        pills_line = f"{f_move}    {f_scroll}    {f_space}    {f_tab}    {f_enter}    {f_back}    {f_quit}"
        p_padding = (term_width - TUI.visible_len(pills_line)) // 2
        p_padding = max(0, p_padding)
        buffer.append(f"{' ' * p_padding}{pills_line}")

        # Display exit confirmation message
        if self.exit_pending:
            buffer.append(f"  {Style.hex('FF6B6B')}Press ESC again to exit...{Style.RESET}")

        # Atomic Draw
        sys.stdout.write("\033[H" + "\n".join(buffer) + "\n\033[J")
        sys.stdout.flush()


    def toggle_selection(self, item):
        """Handles item selection and group toggling."""
        self._resolve_dependencies()
        
        if item['type'] == 'module':
            mod_id = item['obj'].id
            
            # Prevent manual toggle if locked by dependency
            if mod_id in self.auto_locked:
                return 

            if mod_id in self.selected:
                self.selected.remove(mod_id)
            else:
                self.selected.add(mod_id)
                
        elif item['type'] == 'header':
            cat = item['obj']
            mods = self.categories[cat]
            
            # Toggle group state
            all_active = all(self.is_active(m.id) for m in mods)
            
            if all_active:
                for m in mods: 
                    if m.id in self.selected: self.selected.remove(m.id)
            else:
                for m in mods: 
                    if m.id not in self.auto_locked:
                        self.selected.add(m.id)

    def handle_input(self, key):
        """Processes keyboard input and returns navigation actions."""
        # Global Exit Keys (Priority when no modal is blocking)
        if not self.modal:
            if key in [Keys.Q, Keys.Q_UPPER]:
                return "EXIT"
                
            # Double ESC safety mechanism
            if key == Keys.ESC:
                now = time.time()
                if now - self.last_esc_time < 1.0: 
                    return "EXIT"
                self.last_esc_time = now
                self.exit_pending = True
                return None
            
            if key != Keys.ESC and self.exit_pending:
                self.exit_pending = False 

        self.flat_items = self._build_flat_list() 
        
        # Priority 1: Handle Active Modal
        if self.modal:
            action = self.modal.handle_input(key)
            
            # Handling OverrideModal
            if isinstance(self.modal, OverrideModal):
                if action == "ACCEPT":
                    mod = self.flat_items[self.cursor_idx]['obj']
                    mod_id = mod.id
                    ovr = self.modal.get_overrides()
                    
                    # Validation based on real module capabilities
                    can_install_pkg = ovr['install_pkg']
                    can_install_dots = ovr['install_dots'] if mod.stow_pkg else False
                    
                    # Intelligent comparison: check if anything actually changed from defaults
                    is_modified = (
                        ovr['pkg_name'] != mod.get_package_name() or
                        ovr['manager'] != mod.get_manager() or
                        not ovr['install_pkg'] or
                        (mod.stow_pkg and not ovr['install_dots'])
                    )
                    
                    # Sincronize selection state
                    if not can_install_pkg and not can_install_dots:
                        # Nothing real to install
                        self.selected.discard(mod_id)
                        self.overrides.pop(mod_id, None)
                    else:
                        self.selected.add(mod_id)
                        if is_modified:
                            self.overrides[mod_id] = ovr
                        else:
                            self.overrides.pop(mod_id, None)
                    
                    self.modal = None
                elif action == "CANCEL":
                    self.modal = None
                    
            # Handling SummaryModal
            elif isinstance(self.modal, SummaryModal):
                if action == "INSTALL":
                    self.modal = None
                    return "CONFIRM"
                elif action == "CANCEL":
                    self.modal = None
                    
            return None

        if key == Keys.R or key == Keys.BACKSPACE:
            return "BACK"


        # List Quick Navigation
        if key == Keys.CTRL_K:
            self.cursor_idx = max(0, self.cursor_idx - 5)
            self.info_offset = 0
        elif key == Keys.CTRL_J:
            self.cursor_idx = min(len(self.flat_items) - 1, self.cursor_idx + 5)
            self.info_offset = 0

        # Detail Panel Scroll
        elif key == Keys.PGUP:
            self.info_offset = max(0, self.info_offset - 3)
        elif key == Keys.PGDN:
            self.info_offset += 3

        # Standard Navigation
        elif key in [Keys.UP, Keys.K] or key == 65: 
            self.cursor_idx = max(0, self.cursor_idx - 1)
            self.info_offset = 0
        
        elif key in [Keys.DOWN, Keys.J] or key == 66: 
            self.cursor_idx = min(len(self.flat_items) - 1, self.cursor_idx + 1)
            self.info_offset = 0
            
        elif key == Keys.SPACE:
            self.toggle_selection(self.flat_items[self.cursor_idx])
            
        elif key == Keys.TAB:
            current = self.flat_items[self.cursor_idx]
            if current['type'] == 'header':
                self.expanded[current['obj']] = not self.expanded[current['obj']]
            elif current['type'] == 'module':
                mod = current['obj']
                self.modal = OverrideModal(mod, self.overrides.get(mod.id))
            
        elif key == Keys.H:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header':
                 self.expanded[current['obj']] = False
                 
        elif key == Keys.L:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header':
                 self.expanded[current['obj']] = True
        
        elif key == Keys.ENTER:
            # Show summary modal before proceeding
            total_selection = self.selected.union(self.auto_locked)
            if len(total_selection) > 0:
                self.modal = SummaryModal(self.modules, total_selection, self.overrides)
        
        return None
