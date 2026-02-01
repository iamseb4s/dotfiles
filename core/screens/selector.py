import shutil
import sys
from collections import defaultdict
from core.tui import TUI, Keys, Style, Theme
from core.screens.welcome import Screen
from core.screens.options import OptionsModal
from core.screens.review import ReviewModal
from core.screens.shared_modals import ConfirmModal

class SelectorScreen(Screen):
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
        pills = self._get_footer_pills()
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

    def _get_footer_pills(self):
        """Dynamic footer pills based on screen state and active modals."""
        if isinstance(self.modal, OptionsModal) and self.modal.editing_field:
            return [TUI.pill("ENTER", "Finish", Theme.GREEN), TUI.pill("ESC", "Cancel", Theme.RED)]
            
        return [
            TUI.pill("h/j/k/l", "Navigate", Theme.SKY),
            TUI.pill("PgUp/Dn", "Scroll Info", Theme.BLUE),
            TUI.pill("SPACE", "Select", Theme.BLUE),
            TUI.pill("TAB", "Options", Theme.MAUVE),
            TUI.pill("ENTER", "Install", Theme.GREEN),
            TUI.pill("Q", "Back", Theme.RED)
        ]

    def _draw_left(self, width, height):
        """Internal logic for building the package list box."""
        content_width, window_height = width - 6, height - 3
        if self.cursor_idx + 1 < self.list_offset + 1: self.list_offset = max(0, self.cursor_idx)
        elif self.cursor_idx + 1 >= self.list_offset + window_height: self.list_offset = self.cursor_idx - window_height + 1

        lines = [""]
        for idx, item in enumerate(self.flat_items):
            is_cursor = (idx == self.cursor_idx)
            if item['type'] == 'header':
                if idx > 0: lines.append("")
                label = f" {item['obj'].upper()} "; gap = content_width - len(label); left_pad = gap // 2
                color = Style.highlight() if is_cursor else Style.normal()
                lines.append(f"  {color}{Style.BOLD if is_cursor else ''}{'─' * left_pad}{label}{'─' * (gap - left_pad)}{Style.RESET}")
            else:
                module = item['obj']; is_installed = module.is_installed()
                if module.id in self.auto_locked: mark, status_text, color = self.SYM_LOCK, self.STAT_LOCKED, Style.red()
                elif module.id in self.selected:
                    override = self.overrides.get(module.id); part = override and (not override.get('install_package', True) or (module.stow_pkg and not override.get('install_dotfiles', True)))
                    mark, status_text, color = (self.SYM_PART if part else self.SYM_SEL), self.STAT_SEL, (Style.green() if module.id not in self.overrides else Style.yellow())
                else: mark, status_text, color = self.SYM_EMPTY, (self.STAT_INST if is_installed else ""), (Style.blue() if is_installed else Style.muted())
                
                style = Style.highlight() + Style.BOLD if is_cursor else (color if (self.is_active(module.id) or is_installed) else Style.muted())
                label_color = Style.normal() if not (is_cursor or self.is_active(module.id) or is_installed) else style
                label_text = f" {style}{mark}  {label_color}{Style.BOLD if (self.is_active(module.id) and not is_cursor) else ''}{module.label}{Style.RESET}"
                lines.append(f"  {TUI.split_line(label_text, f'{style}{status_text}{Style.RESET}' if status_text else '', content_width)}")

        visible_lines = lines[self.list_offset : self.list_offset + window_height]
        while len(visible_lines) < window_height: visible_lines.append("")
        stats_text = f"Selected: {len(self.selected.union(self.auto_locked))} packages"
        visible_lines.append(f"{' ' * ((width - 2 - len(stats_text)) // 2)}{Style.muted()}{stats_text}{Style.RESET}")
        
        scrollbar = self._get_scrollbar(len(lines), height - 2, self.list_offset)
        return TUI.create_container(visible_lines, width, height, title="PACKAGES", is_focused=(not self.modal), scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _draw_right(self, width, height):
        """Internal logic for building the information box."""
        info_lines = self._get_info_lines(width); max_offset = max(0, len(info_lines) - (height - 2))
        self.info_offset = min(self.info_offset, max_offset)
        scrollbar = self._get_scrollbar(len(info_lines), height - 2, self.info_offset)
        return TUI.create_container(info_lines[self.info_offset : self.info_offset + height - 2], width, height, title="INFORMATION", is_focused=False, scroll_pos=scrollbar['scroll_pos'], scroll_size=scrollbar['scroll_size'])

    def _get_info_lines(self, width):
        """Helper to pre-calculate info lines for scroll limits."""
        lines = [""]
        if not self.flat_items: return lines
        item = self.flat_items[self.cursor_idx]; content_width = width - 6
        if item['type'] == 'module':
            module = item['obj']; override = self.overrides.get(module.id, {}); is_installed = module.is_installed()
            color = Style.red() if module.id in self.auto_locked else (Style.yellow() if module.id in self.overrides else (Style.green() if module.id in self.selected else (Style.blue() if is_installed else Style.highlight())))
            lines.extend([f"  {Style.BOLD}{color}{module.label.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * content_width}{Style.RESET}"])
            if module.description:
                for line in TUI.wrap_text(module.description, content_width): lines.append(f"  {Style.muted()}{line}{Style.RESET}")
            lines.append("")
            def row(label, value, color_style=""): return f"  {Style.subtext1()}{label:<10}{Style.RESET} {color_style}{value}{Style.RESET}"
            lines.append(row("Status", 'Installed' if is_installed else 'Not Installed', Style.blue() if is_installed else Style.muted()))
            for key, label in [('manager', 'Manager'), ('package_name', 'Package'), ('stow_target', 'Target')]:
                current_value = getattr(module, key) if key != 'package_name' else module.get_package_name()
                value = override.get(key, current_value); lines.append(row(label, f"{value}{'*' if value != current_value else ''}"))
            tree = module.get_config_tree()
            if tree:
                lines.extend(["", f"  {Style.BOLD}{Style.subtext0()}CONFIG TREE{Style.RESET}", f"  {Style.surface1()}{'─' * 11}{Style.RESET}"])
                for line in tree:
                    for wrapped_line in TUI.wrap_text(line, content_width - 2): lines.append(f"    {Style.muted()}{wrapped_line}{Style.RESET}")
        else:
            category = item['obj']; lines.extend([f"  {Style.BOLD}{Style.highlight()}{category.upper()}{Style.RESET}", f"  {Style.surface1()}{'─' * content_width}{Style.RESET}", f"  {Style.muted()}Packages in this group:{Style.RESET}", ""])
            for module in self.categories[category]:
                module_status = "■" if self.is_active(module.id) else " "; color = Style.green() if self.is_active(module.id) else Style.muted()
                lines.append(f"    {color}[{module_status}] {module.label}{Style.RESET}")
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
        modal = self.modal
        if not modal: return None
        result = modal.handle_input(key)
        if isinstance(modal, OptionsModal) and result == "ACCEPT":
            module = self.flat_items[self.cursor_idx]['obj']; override = modal.get_overrides()
            if not override['install_package'] and not (module.stow_pkg and override['install_dotfiles']):
                self.selected.discard(module.id); self.overrides.pop(module.id, None)
            else: self.selected.add(module.id); self.overrides[module.id] = override
            self.modal = None; TUI.push_notification(f"Changes saved for {module.label}", type="INFO")
        elif isinstance(modal, ReviewModal) and result == "INSTALL": self.modal = None; return "CONFIRM"
        elif isinstance(modal, ConfirmModal) and result == "YES":
            self.selected.clear(); self.overrides.clear(); self.modal = None; return "WELCOME"
        elif result in ["CANCEL", "CLOSE", "NO"]: self.modal = None
        return None

    def _move_cursor(self, direction): self.cursor_idx = max(0, min(len(self.flat_items) - 1, self.cursor_idx + direction)); self.info_offset = 0; return None
    def _scroll_info(self, direction, max_offset): self.info_offset = max(0, min(max_offset, self.info_offset + direction)); return None
    def _toggle_sel(self):
        """Handles item selection and group toggling."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'module':
            module_id = item['obj'].id
            if module_id in self.auto_locked: return
            if module_id in self.selected: self.selected.remove(module_id); self.overrides.pop(module_id, None)
            else: self.selected.add(module_id)
        elif item['type'] == 'header':
            category = item['obj']; modules = self.categories[category]
            if all(self.is_active(m.id) for m in modules):
                for module in modules:
                    if module.id in self.selected: self.selected.remove(module.id); self.overrides.pop(module.id, None)
            else:
                for module in modules:
                    if module.id not in self.auto_locked: self.selected.add(module.id)
        return None

    def _handle_tab(self):
        """Handles TAB key for expanding headers or opening options."""
        item = self.flat_items[self.cursor_idx]
        if item['type'] == 'header': self.expanded[item['obj']] = not self.expanded[item['obj']]
        elif item['type'] == 'module': self.modal = OptionsModal(item['obj'], self.overrides.get(item['obj'].id))
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
        """Shows the installation review modal."""
        all_s = self.selected.union(self.auto_locked)
        if all_s: self.modal = ReviewModal(self.modules, all_s, self.overrides)
        else: TUI.push_notification("Select at least one package to install", type="ERROR")
        return None

    def _back(self):
        """Returns to the welcome screen, with confirmation if changes exist."""
        if self.selected: self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?"); return None
        return "WELCOME"

