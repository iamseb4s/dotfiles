#!/usr/bin/env python3
import sys
import os
import importlib

# Sourcing local modules
sys.path.append(os.getcwd())

from core.system import System
from core.tui import TUI, Keys
from core.screens.welcome import WelcomeScreen
from core.screens.menu import MenuScreen
from core.screens.install import InstallScreen
from core.screens.create import CreateScreen

def load_modules(sys_manager):
    """Scan and initialize all available installation modules."""
    modules = []
    modules_dir = os.path.join(os.getcwd(), "modules")
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "base.py"]:
            module_name = filename[:-3]
            try:
                # Import module
                mod = importlib.import_module(f"modules.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and attr.__name__.endswith("Module") and attr.__name__ != "Module":
                        instance = attr(sys_manager)
                        modules.append(instance)
                        break
            except Exception as e:
                print(f"Failed to load module {filename}: {e}")
                
    return modules

def main():
    """Main execution loop controlling application state."""
    
    TUI.init_signal_handler()

    try:
        TUI.set_raw_mode(True)
        TUI.hide_cursor()
        TUI.clear_screen()
        sys_mgr = System()
        modules = load_modules(sys_mgr)
        
        # Global state machine
        state = "WELCOME"
        menu_screen = MenuScreen(modules)
        
        while True:
            if TUI.is_resize_pending():
                TUI.clear_screen()

            if state == "WELCOME":
                scr = WelcomeScreen(sys_mgr)
                # Wait for input
                while True:
                    scr.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is not None: break
                
                action = scr.handle_input(key)
                if action == "MENU": 
                    TUI.clear_screen()
                    state = "MENU"
                elif action == "CREATE":
                    TUI.clear_screen()
                    state = "CREATE"
                if action == "EXIT": sys.exit(0)
                
            elif state == "CREATE":
                create_screen = CreateScreen(modules)
                while True:
                    create_screen.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is None: continue
                    
                    action = create_screen.handle_input(key)
                    if action == "WELCOME":
                        state = "WELCOME"
                        TUI.clear_screen()
                        break
                    elif action == "RELOAD_AND_WELCOME":
                        # Reload all modules to include the new one
                        modules = load_modules(sys_mgr)
                        menu_screen = MenuScreen(modules) # Refresh menu too
                        state = "WELCOME"
                        TUI.clear_screen()
                        break
                    if action == "EXIT": sys.exit(0)
                
            elif state == "MENU":
                while True:
                    menu_screen.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is not None: break
                
                action = menu_screen.handle_input(key)
                if action == "EXIT": sys.exit(0)
                if action in ["WELCOME"]: 
                    TUI.clear_screen()
                    state = "WELCOME"
                if action == "CONFIRM": 
                    TUI.clear_screen()
                    state = "INSTALL"
            
            elif state == "INSTALL":
                # Transfer control to the installation runner with user overrides
                installer = InstallScreen(modules, menu_screen.selected, menu_screen.overrides)
                result = installer.run()
                
                if result == "WELCOME":
                    # Reset state and menu for a clean start
                    state = "WELCOME"
                    TUI.clear_screen()
                    menu_screen = MenuScreen(modules)
                else:
                    sys.exit(0)
    finally:
        # Restore terminal state on exit
        TUI.set_raw_mode(False)
        TUI.clear_screen()
        TUI.show_cursor()

if __name__ == "__main__":
    main()
