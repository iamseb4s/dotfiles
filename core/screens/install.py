import time
from core.tui import TUI, Style
from core.screens.welcome import Screen

class InstallScreen(Screen):
    """
    Manages the installation progress screen, including progress bars and live logs.
    """
    def __init__(self, modules, selected_ids, overrides=None):
        self.queue = [m for m in modules if m.id in selected_ids]
        self.overrides = overrides or {}
        self.total = len(self.queue)
        self.current = 0
        self.logs = []
    
    def render_progress(self, current_pkg_name):
        """Draws the global installation progress bar and recent logs."""
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
        # Show only recent logs to avoid terminal overflow
        for log in self.logs[-10:]:
            print(f"  > {log}")
            
    def run(self):
        """Orchestrates the sequential installation of queued modules with overrides."""
        for mod in self.queue:
            self.current += 1
            ovr = self.overrides.get(mod.id)
            
            # Resolve execution flags from overrides
            do_pkg = ovr.get('install_pkg', True) if ovr else True
            do_dots = ovr.get('install_dots', True) if ovr else True
            
            self.render_progress(mod.label)
            
            try:
                # 1. Binary/Package Installation
                if do_pkg:
                    self.logs.append(f"Installing package: {mod.id}...")
                    if not mod.install(ovr):
                        self.logs.append(f"ERROR: {mod.id} installation failed.")
                        continue # Skip configuration if package fails
                    self.logs.append(f"Package {mod.id} installed.")
                
                # 2. Configuration Deployment
                if do_dots and mod.stow_pkg:
                    self.logs.append(f"Configuring {mod.id}...")
                    mod.configure(ovr)
                    self.logs.append(f"{mod.id} configuration applied.")
                    
            except Exception as e:
                self.logs.append(f"EXCEPTION in {mod.id}: {e}")
                
            # Final pause for visual feedback
            time.sleep(0.5)
        
        # Final summary screen
        TUI.clear_screen()
        print("\n  INSTALLATION COMPLETE")
        print("  " + "="*30)
        for log in self.logs:
             # Highlight failures in red
             if "ERROR" in log or "EXCEPTION" in log:
                 print(f"  {Style.hex('FF5555')}{log}{Style.RESET}")
             else:
                 print(f"  {log}")
        print("\n  Press ANY KEY to exit.")
        TUI.get_key()

    def render(self):
        """Interface requirement - logic is handled in run()."""
        pass

    def handle_input(self, key):
        """Interface requirement."""
        return None
