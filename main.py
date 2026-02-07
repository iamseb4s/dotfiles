#!/usr/bin/env python3
import sys
import os
import importlib

# Sourcing local modules
sys.path.append(os.getcwd())

from core.system import System
from core.tui import TUI, Keys
from core.screens.welcome import WelcomeScreen
from core.screens.selector import SelectorScreen
from core.screens.installer import InstallerScreen
from core.screens.wizard import WizardScreen

def load_modules(system_manager):
    """Scan and initialize all available installation modules."""
    modules = []
    modules_dir = os.path.join(os.getcwd(), "modules")
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "base.py"]:
            module_name = filename[:-3]
            try:
                # Import module
                module_package = importlib.import_module(f"modules.{module_name}")
                for attribute_name in dir(module_package):
                    attribute = getattr(module_package, attribute_name)
                    if isinstance(attribute, type) and attribute.__name__.endswith("Module") and attribute.__name__ != "Module":
                        instance = attribute(system_manager)
                        modules.append(instance)
                        break
            except Exception as error:
                print(f"Failed to load module {filename}: {error}")
                
    return modules

def main():
    """Main execution loop controlling application state."""
    
    TUI.init_signal_handler()

    try:
        TUI.set_raw_mode(True)
        TUI.hide_cursor()
        TUI.clear_screen()
        system_manager = System()
        modules = load_modules(system_manager)
        
        # Global state machine
        state = "WELCOME"
        selector_screen = SelectorScreen(modules)
        
        while True:
            if TUI.is_resize_pending():
                TUI.clear_screen()

            if state == "WELCOME":
                welcome_screen = WelcomeScreen(system_manager)
                # Wait for input
                while True:
                    welcome_screen.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is not None: break
                
                action = welcome_screen.handle_input(key)
                if action == "SELECTOR": 
                    TUI.clear_screen()
                    state = "SELECTOR"
                elif action == "WIZARD":
                    TUI.clear_screen()
                    state = "WIZARD"
                if action == "EXIT": sys.exit(0)
                
            elif state == "WIZARD":
                wizard_screen = WizardScreen(modules)
                while True:
                    wizard_screen.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is None: continue
                    
                    action = wizard_screen.handle_input(key)
                    if action == "WELCOME":
                        state = "WELCOME"
                        TUI.clear_screen()
                        break
                    elif action == "RELOAD_AND_WELCOME":
                        # Reload all modules to include the new one
                        modules = load_modules(system_manager)
                        selector_screen = SelectorScreen(modules) # Refresh selector too
                        state = "WELCOME"
                        TUI.clear_screen()
                        break
                    if action == "EXIT": sys.exit(0)
                
            elif state == "SELECTOR":
                while True:
                    selector_screen.render()
                    key = TUI.get_key(blocking=True)
                    if key == Keys.RESIZE:
                        TUI.clear_screen()
                        continue
                    if key is not None: break
                
                action = selector_screen.handle_input(key)
                if action == "EXIT": sys.exit(0)
                if action in ["WELCOME"]: 
                    TUI.clear_screen()
                    state = "WELCOME"
                if action == "CONFIRM": 
                    TUI.clear_screen()
                    state = "INSTALL"
            
            elif state == "INSTALL":
                # Transfer control to the installation runner with merged effective overrides
                effective_overrides = selector_screen.get_effective_overrides()
                installer = InstallerScreen(modules, selector_screen.selected, effective_overrides)
                result = installer.run()
                
                if result == "WELCOME":
                    # Reset state and selector for a clean start
                    state = "WELCOME"
                    TUI.clear_screen()
                    for module in modules: module.clear_cache()
                    selector_screen = SelectorScreen(modules)
                elif result == "SELECTOR":
                    state = "SELECTOR"
                    TUI.clear_screen()
                    for module in modules: module.clear_cache()
                    selector_screen._structure_needs_rebuild = True
                else:
                    sys.exit(0)
    finally:
        # Restore terminal state on exit
        TUI.set_raw_mode(False)
        TUI.clear_screen()
        TUI.show_cursor()

if __name__ == "__main__":
    main()
