#!/usr/bin/env python3
import sys
import os
import shutil
import importlib
import time
from collections import defaultdict

# Ensure we can import from local directories
sys.path.append(os.getcwd())

from core.system import System
from core.tui import TUI, Keys, WelcomeScreen, Style

# --- MENU SCREEN IMPLEMENTATION ---
class MenuScreen:
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

        # --- MODERN HEADER WITH SELECTION COUNTER ---
        term_width = shutil.get_terminal_size().columns
        title_text = " PACKAGES SELECTOR "
        
        # Calculate selection totals for the counter
        active_total = len(self.selected.union(self.auto_locked))
        counter_text = f" [ {active_total:02} / {len(self.modules):02} ] "
        
        # Colors
        bg_blue = Style.hex("89B4FA", bg=True)
        text_black = "\033[30m"
        
        # Centering logic for title, counter aligned to the right
        padding = (term_width - len(title_text)) // 2
        padding = max(0, padding)
        left_pad = " " * padding
        
        # Dynamic middle padding to push counter to the far right
        mid_pad_len = term_width - len(left_pad) - len(title_text) - len(counter_text)
        mid_pad = " " * max(0, mid_pad_len)
        
        # Render Bar: [BG_BLUE + BLACK]   TITLE   [RESET]
        header_bar = f"{bg_blue}{text_black}{left_pad}{title_text}{mid_pad}{counter_text}{Style.RESET}"
        
        print("\n" + header_bar + "\n")
        print(f"  {Style.DIM}Select the packages you wish to install and configure:{Style.RESET}\n")

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
                
                # Header styling logic
                if is_cursor:
                    # Cursor: Bold + Inverted (Clean highlight, no state color)
                    # Added trailing spaces for visual symmetry
                    sys.stdout.write(f"{Style.BOLD}{Style.INVERT}{line}   {Style.RESET}\n")
                else:
                    # Normal: Bold + State Color
                    sys.stdout.write(f"{Style.BOLD}{header_color}{line}{Style.RESET}\n")

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
                
                # Visual hierarchy style: '  > │     '
                hierarchy_icon = "│"
                line = f"  {cursor_char} {hierarchy_icon}     {mark} {mod.label}{suffix}"
                
                if is_cursor:
                    # In cursor mode, we invert the whole line including hierarchy for better feedback
                    # Added trailing spaces for visual symmetry with the prefix
                    sys.stdout.write(f"{Style.INVERT}{line}   {Style.RESET}\n")
                else:
                    # Normal mode: Dim the hierarchy icon, color the package label
                    styled_line = f"  {cursor_char} {Style.DIM}{hierarchy_icon}{Style.RESET}     {color}{mark} {mod.label}{suffix}{Style.RESET}"
                    sys.stdout.write(f"{styled_line}\n")
        
        # --- FOOTER (Pills) ---
        print("\n")
        
        # Footer Content
        f_move  = TUI.pill("↑/↓/k/j", "Move", "81ECEC") # Cyan
        f_space = TUI.pill("SPACE", "Select", "89B4FA") # Blue
        f_tab   = TUI.pill("TAB", "Group", "CBA6F7")    # Mauve
        f_enter = TUI.pill("ENTER", "Install", "a6e3a1")# Green
        f_back  = TUI.pill("R", "Back", "f9e2af")       # Yellow
        f_quit  = TUI.pill("Q", "Exit", "f38ba8")       # Red
        
        # Status Line
        total_active = len(self.selected.union(self.auto_locked))
        status_text = f"  Selected: {total_active} packages"
        
        # Center the footer pills
        # Add explicit spacing between pills now that internal margin is removed
        pills_line = f"{f_move}    {f_space}    {f_tab}    {f_enter}    {f_back}    {f_quit}"
        p_padding = (term_width - TUI.visible_len(pills_line)) // 2
        p_padding = max(0, p_padding)
        
        print(f"{status_text}\n")
        print(f"{' ' * p_padding}{pills_line}")
        
        if self.exit_pending:
            print(f"\n  {Style.hex('FF5555')}Press ESC again to exit...{Style.RESET}")

    def toggle_selection(self, item):
        """Handles spacebar logic for toggling items/groups."""
        self._resolve_dependencies()
        
        if item['type'] == 'module':
            mod_id = item['obj'].id
            
            # Cannot manually toggle if locked by dependency
            if mod_id in self.auto_locked:
                return 

            if mod_id in self.selected:
                self.selected.remove(mod_id)
            else:
                self.selected.add(mod_id)
                
        elif item['type'] == 'header':
            cat = item['obj']
            mods = self.categories[cat]
            
            # Check if group is effectively fully active
            all_active = all(self.is_active(m.id) for m in mods)
            
            if all_active:
                # Deselect all user choices in this category
                for m in mods: 
                    if m.id in self.selected: self.selected.remove(m.id)
            else:
                # Select all (skipping those already locked)
                for m in mods: 
                    if m.id not in self.auto_locked:
                        self.selected.add(m.id)

    def handle_input(self, key):
        """Processes keyboard events and returns action codes."""
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

        # Navigation
        if key in [Keys.UP, Keys.K] or key == 65: 
            self.cursor_idx = max(0, self.cursor_idx - 1)
        
        elif key in [Keys.DOWN, Keys.J] or key == 66: 
            self.cursor_idx = min(len(self.flat_items) - 1, self.cursor_idx + 1)
            
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
            # Check if there is anything to install (User Selected + Auto Locked)
            if len(self.selected.union(self.auto_locked)) > 0:
                # Merge locked dependencies into the final selection set
                self.selected.update(self.auto_locked)
                return "CONFIRM"
        
        return None

# --- INSTALL SCREEN ---
class InstallScreen:
    def __init__(self, modules, selected_ids):
        self.queue = [m for m in modules if m.id in selected_ids]
        self.total = len(self.queue)
        self.current = 0
        self.logs = []
    
    def render_progress(self, current_pkg_name):
        TUI.clear_screen()
        percent = int((self.current / self.total) * 100)
        bar_len = 30
        filled = int(bar_len * percent / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        print("\n  INSTALLATION IN PROGRESS")
        print(f"  [{bar}] {percent}%")
        print(f"  Processing: {current_pkg_name}\n")
        
        print("  LOGS:")
        print("  " + "-"*40)
        # Show last 10 log lines
        for log in self.logs[-10:]:
            print(f"  > {log}")
            
    def run(self):
        for mod in self.queue:
            self.current += 1
            self.render_progress(mod.label)
            
            # TODO: Redirect stdout capture so we can show logs in UI
            # For now we just append start/end messages
            self.logs.append(f"Installing {mod.id}...")
            
            try:
                if mod.install():
                    self.logs.append(f"{mod.id} installed.")
                    mod.configure()
                    self.logs.append(f"{mod.id} configured.")
                else:
                    self.logs.append(f"ERROR: {mod.id} installation failed.")
            except Exception as e:
                self.logs.append(f"EXCEPTION: {e}")
                
            time.sleep(0.5) # Fake delay for UX (remove in production if slow)
        
        # Final Screen
        TUI.clear_screen()
        print("\n  INSTALLATION COMPLETE")
        print("  " + "="*30)
        for log in self.logs:
             # Basic color highlighting
             if "ERROR" in log or "EXCEPTION" in log:
                 print(f"  {Style.hex('FF5555')}{log}{Style.RESET}")
             else:
                 print(f"  {log}")
        print("\n  Press ANY KEY to exit.")
        TUI.get_key()


# --- MAIN APP LOADER ---
def load_modules(sys_manager):
    """Dynamically load modules from the modules/ directory."""
    modules = []
    modules_dir = os.path.join(os.getcwd(), "modules")
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "base.py"]:
            module_name = filename[:-3]
            try:
                # Import module
                mod = importlib.import_module(f"modules.{module_name}")
                
                # Find class inheriting from Module
                # We assume the class name usually matches the file (e.g. RefindModule)
                # or just inspect all attributes.
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    # Check if it's a class, inherits from Module, and is not Module itself
                    if isinstance(attr, type) and attr.__name__.endswith("Module") and attr.__name__ != "Module":
                        instance = attr(sys_manager)
                        modules.append(instance)
                        break
            except Exception as e:
                print(f"Failed to load module {filename}: {e}")
                
    return modules

def main():
    try:
        TUI.hide_cursor()
        sys_mgr = System()
        modules = load_modules(sys_mgr)
        
        # State Machine
        state = "WELCOME"
        menu_screen = MenuScreen(modules)
        
        while True:
            if state == "WELCOME":
                scr = WelcomeScreen(sys_mgr)
                scr.render()
                action = scr.handle_input(TUI.get_key())
                if action == "MENU": state = "MENU"
                if action == "EXIT": sys.exit(0)
                
            elif state == "MENU":
                menu_screen.render()
                action = menu_screen.handle_input(TUI.get_key())
                if action == "EXIT": sys.exit(0)
                if action == "BACK": state = "WELCOME"
                if action == "CONFIRM": state = "INSTALL"
            
            elif state == "INSTALL":
                # Pass control to Install Runner
                installer = InstallScreen(modules, menu_screen.selected)
                installer.run()
                sys.exit(0)
    finally:
        TUI.show_cursor()

if __name__ == "__main__":
    main()
