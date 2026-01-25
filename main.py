#!/usr/bin/env python3
import sys
import os
import importlib

# Sourcing local modules
sys.path.append(os.getcwd())

from core.system import System
from core.tui import TUI
from core.screens.welcome import WelcomeScreen
from core.screens.menu import MenuScreen
from core.screens.install import InstallScreen

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
    try:
        TUI.hide_cursor()
        sys_mgr = System()
        modules = load_modules(sys_mgr)
        
        # Global state machine
        state = "WELCOME"
        menu_screen = MenuScreen(modules)
        
        while True:
            if state == "WELCOME":
                scr = WelcomeScreen(sys_mgr)
                scr.render()
                action = scr.handle_input(TUI.get_key())
                if action == "MENU": 
                    TUI.clear_screen()
                    state = "MENU"
                if action == "EXIT": sys.exit(0)
                
            elif state == "MENU":
                menu_screen.render()
                action = menu_screen.handle_input(TUI.get_key())
                if action == "EXIT": sys.exit(0)
                if action == "BACK": 
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
        TUI.clear_screen()
        TUI.show_cursor()

if __name__ == "__main__":
    main()
