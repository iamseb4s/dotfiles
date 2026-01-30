import shutil
import sys
import time
from collections import defaultdict
from core.tui import TUI, Keys, Style, Theme
from core.screens.welcome import Screen
from core.screens.overrides import OverrideModal
from core.screens.summary import SummaryModal
from core.screens.shared_modals import ConfirmModal

class MenuScreen(Screen):
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
        for rendering based on the expansion state of each category.
        """
        items = []
        for cat in self.category_names:
            items.append({'type': 'header', 'obj': cat})
            if self.expanded[cat]:
                for m in self.categories[cat]: items.append({'type': 'module', 'obj': m})
        return items

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
        pills = [TUI.pill("h/j/k/l", "Navigate", Theme.SKY), TUI.pill("PgUp/Dn", "Scroll Info", Theme.BLUE), TUI.pill("SPACE", "Select", Theme.BLUE), TUI.pill("TAB", "Overrides", Theme.MAUVE), TUI.pill("ENTER", "Install", Theme.GREEN), TUI.pill("Q", "Back", Theme.RED)]
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

    def _draw_left(self, w, h):
        """Internal logic for building the package list box."""
        cw, win = w - 6, h - 3
        if self.cursor_idx + 1 < self.list_offset + 1: self.list_offset = max(0, self.cursor_idx)
        elif self.cursor_idx + 1 >= self.list_offset + win: self.list_offset = self.cursor_idx - win + 1

        lines = [""]
        for idx, item in enumerate(self.flat_items):
            is_c = (idx == self.cursor_idx)
            if item['type'] == 'header':
                if idx > 0: lines.append("")
                lbl = f" {item['obj'].upper()} "; gap = cw - len(lbl); lp = gap // 2
                c = Style.highlight() if is_c else Style.normal()
                lines.append(f"  {c}{Style.BOLD if is_c else ''}{'─' * lp}{lbl}{'─' * (gap - lp)}{Style.RESET}")
            else:
                m = item['obj']; inst = m.is_installed()
                if m.id in self.auto_locked: mark, stat, c = self.SYM_LOCK, self.STAT_LOCKED, Style.red()
                elif m.id in self.selected:
                    ovr = self.overrides.get(m.id); part = ovr and (not ovr.get('install_pkg', True) or (m.stow_pkg and not ovr.get('install_dots', True)))
                    mark, stat, c = (self.SYM_PART if part else self.SYM_SEL), self.STAT_SEL, (Style.green() if m.id not in self.overrides else Style.yellow())
                else: mark, stat, c = self.SYM_EMPTY, (self.STAT_INST if inst else ""), (Style.blue() if inst else Style.muted())
                
                sty = Style.highlight() + Style.BOLD if is_c else (c if (self.is_active(m.id) or inst) else Style.muted())
                label_c = Style.normal() if not (is_c or self.is_active(m.id) or inst) else sty
                l_txt = f" {sty}{mark}  {label_c}{Style.BOLD if (self.is_active(m.id) and not is_c) else ''}{m.label}{Style.RESET}"
                lines.append(f"  {TUI.split_line(l_txt, f'{sty}{stat}{Style.RESET}' if stat else '', cw)}")

        vis = lines[self.list_offset : self.list_offset + win]
        while len(vis) < win: vis.append("")
        st = f"Selected: {len(self.selected.union(self.auto_locked))} packages"
        vis.append(f"{' ' * ((w - 2 - len(st)) // 2)}{Style.muted()}{st}{Style.RESET}")
        
        sc = self._get_scrollbar(len(lines), h - 2, self.list_offset)
        return TUI.create_container(vis, w, h, title="PACKAGES", is_focused=(not self.modal), scroll_pos=sc['scroll_pos'], scroll_size=sc['scroll_size'])

    def _draw_right(self, w, h):
        """Internal logic for building the information box."""
        info = self._get_info_lines(w); max_o = max(0, len(info) - (h - 2))
        self.info_offset = min(self.info_offset, max_o)
        sc = self._get_scrollbar(len(info), h - 2, self.info_offset)
        return TUI.create_container(info[self.info_offset : self.info_offset + h - 2], w, h, title="INFORMATION", is_focused=False, scroll_pos=sc['scroll_pos'], scroll_size=sc['scroll_size'])

    def _get_info_lines(self, w):
        """Helper to pre-calculate info lines for scroll limits."""
        lines = [""]
        if not self.flat_items: return lines
        item = self.flat_items[self.cursor_idx]; cw = w - 6
        if item['type'] == 'module':
            m = item['obj']; ovr = self.overrides.get(m.id, {}); inst = m.is_installed()
            c = Style.red() if m.id in self.auto_locked else (Style.yellow() if m.id in self.overrides else (Style.green() if m.id in self.selected else (Style.blue() if inst else Style.highlight())))
            lines.extend([f"  {Style.BOLD}{c}{m.label.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * cw}{Style.RESET}"])
            if m.description:
                for l in TUI.wrap_text(m.description, cw): lines.append(f"  {Style.muted()}{l}{Style.RESET}")
            lines.append("")
            def row(l, v, cl=""): return f"  {Style.subtext1()}{l:<10}{Style.RESET} {cl}{v}{Style.RESET}"
            lines.append(row("Status", 'Installed' if inst else 'Not Installed', Style.blue() if inst else Style.muted()))
            for k, lbl in [('manager', 'Manager'), ('pkg_name', 'Package'), ('stow_target', 'Target')]:
                curr = getattr(m, k) if k != 'pkg_name' else m.get_package_name()
                val = ovr.get(k, curr); lines.append(row(lbl, f"{val}{'*' if val != curr else ''}"))
            tree = m.get_config_tree()
            if tree:
                lines.extend(["", f"  {Style.BOLD}{Style.subtext0()}CONFIG TREE{Style.RESET}", f"  {Style.surface1()}{'─' * 11}{Style.RESET}"])
                for l in tree:
                    for wl in TUI.wrap_text(l, cw - 2): lines.append(f"    {Style.muted()}{wl}{Style.RESET}")
        else:
            cat = item['obj']; lines.extend([f"  {Style.BOLD}{Style.highlight()}{cat.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * cw}{Style.RESET}", f"  {Style.muted()}Packages in this group:{Style.RESET}", ""])
            for m in self.categories[cat]:
                m_stat = "■" if self.is_active(m.id) else " "; color = Style.green() if self.is_active(m.id) else Style.muted()
                lines.append(f"    {color}[{m_stat}] {m.label}{Style.RESET}")
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
        m = self.modal
        if not m: return None
        res = m.handle_input(key)
        if isinstance(m, OverrideModal) and res == "ACCEPT":
            mod = self.flat_items[self.cursor_idx]['obj']; ovr = m.get_overrides()
            if not ovr['install_pkg'] and not (mod.stow_pkg and ovr['install_dots']):
                self.selected.discard(mod.id); self.overrides.pop(mod.id, None)
            else: self.selected.add(mod.id); self.overrides[mod.id] = ovr
            self.modal = None; TUI.push_notification(f"Changes saved for {mod.label}", type="INFO")
        elif isinstance(m, SummaryModal) and res == "INSTALL": self.modal = None; return "CONFIRM"
        elif isinstance(m, ConfirmModal) and res == "YES":
            self.selected.clear(); self.overrides.clear(); self.modal = None; return "WELCOME"
        elif res in ["CANCEL", "CLOSE", "NO"]: self.modal = None
        return None

    def _move_cursor(self, d): self.cursor_idx = max(0, min(len(self.flat_items) - 1, self.cursor_idx + d)); self.info_offset = 0; return None
    def _scroll_info(self, d, mx): self.info_offset = max(0, min(mx, self.info_offset + d)); return None
    def _toggle_sel(self):
        """Handles item selection and group toggling."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'module':
            mid = item['obj'].id
            if mid in self.auto_locked: return
            if mid in self.selected: self.selected.remove(mid); self.overrides.pop(mid, None)
            else: self.selected.add(mid)
        elif item['type'] == 'header':
            cat = item['obj']; mods = self.categories[cat]
            if all(self.is_active(m.id) for m in mods):
                for m in mods:
                    if m.id in self.selected: self.selected.remove(m.id); self.overrides.pop(m.id, None)
            else:
                for m in mods:
                    if m.id not in self.auto_locked: self.selected.add(m.id)
        return None

    def _handle_tab(self):
        """Handles TAB key for expanding headers or opening overrides."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = not self.expanded[item['obj']]
        elif item['type'] == 'module': self.modal = OverrideModal(item['obj'], self.overrides.get(item['obj'].id))
        return None

    def _collapse(self):
        """Collapses the current header."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = False
        return None

    def _expand(self):
        """Expands the current header."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = True
        return None

    def _trigger_install(self):
        """Shows the installation summary modal."""
        all_s = self.selected.union(self.auto_locked)
        if all_s: self.modal = SummaryModal(self.modules, all_s, self.overrides)
        else: TUI.push_notification("Select at least one package to install", type="ERROR")
        return None

    def _back(self):
        """Returns to the welcome screen, with confirmation if changes exist."""
        if self.selected: self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?"); return None
        return "WELCOME"
