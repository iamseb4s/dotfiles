import time
from core.tui import TUI, Style
from core.screens.welcome import Screen

class InstallScreen(Screen):
    """
    Manages the installation progress screen, including progress bars and live logs.
    """
    def __init__(self, modules, selected_ids):
        self.queue = [m for m in modules if m.id in selected_ids]
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
        """Orchestrates the sequential installation of queued modules."""
        for mod in self.queue:
            self.current += 1
            self.render_progress(mod.label)
            
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
                
            # Controlled pause for visual feedback
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
