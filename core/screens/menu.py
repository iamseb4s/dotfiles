import shutil
import time
from collections import defaultdict
from core.tui import TUI, Keys, Style
from core.screens.welcome import Screen

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
        
        self.cursor_idx = 0
        self.list_offset = 0       # Automatic scroll for the list
        self.info_offset = 0       # Manual scroll for the info panel
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

    def render(self):
        """Draws the menu interface to the terminal."""
        TUI.clear_screen()
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
        
        header_bar = f"{bg_blue}{text_black}{left_pad}{title_text}{right_pad}{Style.RESET}"
        
        print("\n" + header_bar + "\n")
        print(f"  {Style.DIM}Select the packages you wish to install and configure:{Style.RESET}\n")

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
                
                # Determine visual state based on selection and installation
                if mod.id in self.auto_locked:
                    mark = "[■]"        # Locked by dependency
                    color = Style.hex("FF6B6B")  # Pastel Red
                    suffix = " "       # Lock icon suffix
                elif mod.id in self.selected:
                    mark = "[■]"        # User selected
                    color = Style.hex("55E6C1") # Pastel Green
                    suffix = ""
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
        
        if current_item['type'] == 'module':
            mod = current_item['obj']
            # Header
            is_installed = mod.is_installed()
            status_str = "Installed" if is_installed else "Not Installed"
            status_icon = "●" if is_installed else "○"
            status_color = Style.hex("#89B4FA") if is_installed else ""
            
            info_lines.append(f"{Style.BOLD}{Style.hex('#89B4FA')}{mod.label.upper()}{Style.RESET}")
            if mod.description:
                info_lines.append(f"{Style.DIM}{mod.description}{Style.RESET}")
            info_lines.append("")
            info_lines.append(f"{Style.BOLD}Status:  {status_color}{status_icon} {status_str}{Style.RESET}")
            info_lines.append(f"{Style.BOLD}Manager: {Style.RESET}{mod.manager}")
            
            # Config Tree
            tree = mod.get_config_tree()
            if tree:
                info_lines.append("")
                info_lines.append(f"{Style.BOLD}CONFIG TREE:{Style.RESET}")
                info_lines.extend([f"  {l}" for l in tree])
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
            # Leave a safety margin to prevent line wrapping
            safe_width = term_width - 2
            split_width = int(safe_width * 0.60)
            
            # Slicing viewports for list and info
            visible_list = list_lines[self.list_offset : self.list_offset + available_height]
            visible_info = info_lines[self.info_offset : self.info_offset + available_height]
            
            max_rows = max(len(visible_list), len(visible_info))
            
            for i in range(max_rows):
                # Get current lines or empty strings
                left = visible_list[i] if i < len(visible_list) else ""
                right = visible_info[i] if i < len(visible_info) else ""
                
                # --- LEFT COLUMN (List) ---
                l_len = TUI.visible_len(left)
                l_padding = " " * (split_width - 2 - l_len)
                
                # Scrollbar Left (List) with proportional indicator
                if len(list_lines) > available_height:
                    max_l_off = len(list_lines) - available_height
                    l_prog = self.list_offset / max_l_off
                    l_indicator_pos = int(l_prog * (available_height - 1))
                    scroll_l = f"{Style.hex('#89B4FA')}┃{Style.RESET}" if i == l_indicator_pos else f"{Style.DIM}│{Style.RESET}"
                else:
                    scroll_l = " "

                # Central Separator
                central_sep = f"{Style.DIM}│{Style.RESET}"
                
                # --- RIGHT COLUMN (Info) ---
                # Calculate remaining width for info text, leaving 2 spaces for scrollbar
                r_content_width = safe_width - split_width - 4
                r_len = TUI.visible_len(right)
                r_padding = " " * max(0, r_content_width - 2 - r_len)
                
                # Scrollbar Right (Info) with proportional indicator
                if len(info_lines) > available_height:
                    max_r_off = len(info_lines) - available_height
                    r_prog = self.info_offset / max_r_off
                    r_indicator_pos = int(r_prog * (available_height - 1))
                    scroll_r = f"{Style.hex('#89B4FA')}┃{Style.RESET}" if i == r_indicator_pos else f"{Style.DIM}│{Style.RESET}"
                else:
                    scroll_r = " "

                # Final Row Construction
                print(f"{left}{l_padding} {scroll_l} {central_sep} {right}{r_padding} {scroll_r}")
            
            # Fill remaining height
            remaining = available_height - max_rows
            for _ in range(remaining):
                s_l = f"{Style.DIM}│{Style.RESET}" if len(list_lines) > available_height else " "
                s_r = f"{Style.DIM}│{Style.RESET}" if len(info_lines) > available_height else " "
                empty_l = " " * (split_width - 2)
                empty_r = " " * (safe_width - split_width - 4 - 2)
                print(f"{empty_l} {s_l} {Style.DIM}│{Style.RESET} {empty_r}  {s_r}")
        else:
            # Fallback to simple list for narrow terminals
            visible_list = list_lines[self.list_offset : self.list_offset + available_height]
            for line in visible_list:
                print(line)
            # Fill remaining to keep footer stable
            for _ in range(available_height - len(visible_list)):
                print()

        # --- FOOTER (Pills) ---
        print()
        
        # Status Line
        total_active = len(self.selected.union(self.auto_locked))
        status_text = f"  Selected: {total_active} packages"
        
        # Footer Content
        f_move   = TUI.pill("↑/↓/k/j", "Move", "81ECEC") # Cyan
        f_scroll = TUI.pill("PgUp/Dn", "Scroll Info", "89B4FA") # Blue
        f_space  = TUI.pill("SPACE", "Select", "89B4FA") # Blue
        f_tab    = TUI.pill("TAB", "Group", "CBA6F7")    # Mauve
        f_enter  = TUI.pill("ENTER", "Install", "a6e3a1")# Green
        f_back   = TUI.pill("R", "Back", "f9e2af")       # Yellow
        f_quit   = TUI.pill("Q", "Exit", "f38ba8")       # Red
        
        # Center the footer pills
        pills_line = f"{f_move}    {f_scroll}    {f_space}    {f_tab}    {f_enter}    {f_back}    {f_quit}"
        p_padding = (term_width - TUI.visible_len(pills_line)) // 2
        p_padding = max(0, p_padding)
        
        print(f"{status_text}\n")
        
        # User interface command hints
        print(f"{' ' * p_padding}{pills_line}")

        if self.exit_pending:
            print(f"\n  {Style.hex('FF5555')}Press ESC again to exit...{Style.RESET}")

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
        self.flat_items = self._build_flat_list() 
        
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

        if key == Keys.Q:
            return "EXIT"

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
            
        elif key == Keys.H:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header':
                 self.expanded[current['obj']] = False
                 
        elif key == Keys.L:
             current = self.flat_items[self.cursor_idx]
             if current['type'] == 'header':
                 self.expanded[current['obj']] = True
        
        elif key == Keys.ENTER:
            if len(self.selected.union(self.auto_locked)) > 0:
                self.selected.update(self.auto_locked)
                return "CONFIRM"
        
        return None
