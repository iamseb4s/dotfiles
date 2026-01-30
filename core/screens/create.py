import shutil
import os
import sys
import time
import re
import json
from datetime import datetime
from modules.base import Module
from core.tui import TUI, Keys, Style, Theme
from core.screens.welcome import Screen
from core.screens.install import ConfirmModal

class DependencyModal:
    """Multi-select modal for module dependencies."""
    def __init__(self, modules: list[Module], current_deps):
        self.modules = sorted(modules, key=lambda m: str(m.label or m.id or ""))
        self.selected = set(current_deps)
        self.focus_idx = 0
        self.scroll_offset = 0

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 64
        content_width = width - 10
        available_content_height = term_height - 12
        
        max_rows = min(len(self.modules), available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""]
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(self.modules):
                mod = self.modules[idx]
                is_focused = (self.focus_idx == idx)
                is_selected = (mod.id in self.selected)
                
                mark = "[■]" if is_selected else "[ ]"
                label = f"{mod.label} ({mod.id})"
                
                if is_focused:
                    line = TUI.split_line(f"{mark}  {label}", "", content_width)
                    inner_lines.append(f"    {Style.highlight()}{Style.BOLD}{line}{Style.RESET}")
                else:
                    color = Style.green() if is_selected else Style.muted()
                    line = TUI.split_line(f"{mark}  {label}", "", content_width)
                    inner_lines.append(f"    {color}{line}{Style.RESET}")

        inner_lines.append("")
        hint = "SPACE: Toggle   ENTER: Confirm   ESC: Cancel"
        h_pad = (width - 2 - TUI.visible_len(hint)) // 2
        inner_lines.append(f"{' ' * h_pad}{Style.muted()}{hint}{Style.RESET}")
        
        scroll_pos, scroll_size = None, None
        if len(self.modules) > max_rows:
            thumb_size = max(1, int(max_rows**2 / len(self.modules)))
            max_off = len(self.modules) - max_rows
            prog = self.scroll_offset / max_off
            scroll_pos = 1 + int(prog * (max_rows - thumb_size))
            scroll_size = thumb_size

        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="SELECT DEPENDENCIES", is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % len(self.modules)
            if self.focus_idx < self.scroll_offset: self.scroll_offset = self.focus_idx
            if self.focus_idx == len(self.modules) - 1: # Wrap to bottom
                t_lines = shutil.get_terminal_size().lines
                max_rows = max(3, min(len(self.modules), t_lines - 12))
                self.scroll_offset = max(0, len(self.modules) - max_rows)
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % len(self.modules)
            t_lines = shutil.get_terminal_size().lines
            max_rows = max(3, min(len(self.modules), t_lines - 12))
            if self.focus_idx >= self.scroll_offset + max_rows: self.scroll_offset = self.focus_idx - max_rows + 1
            if self.focus_idx == 0: self.scroll_offset = 0
        elif key == Keys.SPACE:
            mid = self.modules[self.focus_idx].id
            if mid in self.selected: self.selected.remove(mid)
            else: self.selected.add(mid)
        elif key == Keys.ENTER: return "CONFIRM"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

    def get_selected(self):
        return list(self.selected)

class WizardSummaryModal:
    """Final summary modal with 4-space margins."""
    def __init__(self, form_data):
        self.form = form_data
        self.focus_idx = 0 # 0: SAVE, 1: CANCEL
        self.content_lines = self._build_content()

    def _build_content(self):
        lines = []
        def row(label, val): return f"{Style.subtext1()}{label:<12}{Style.RESET} {Style.normal()}{val}{Style.RESET}"
        lines.append(row("ID", self.form['id']))
        lines.append(row("Label", self.form['label']))
        lines.append(row("Manager", self.form['manager']))
        cat = self.form['custom_category'] if self.form['category'] == "Custom...✎" else self.form['category']
        lines.append(row("Category", cat))
        lines.append(row("Target", self.form['stow_target']))
        lines.append(row("Manual", 'Yes' if self.form['is_incomplete'] else 'No'))
        lines.append("")
        lines.append(f"{Style.subtext1()}Dependencies:{Style.RESET}")
        if not self.form['dependencies']:
            lines.append(f"  {Style.muted()}None{Style.RESET}")
        else:
            for dep in sorted(self.form['dependencies']):
                lines.append(f"  {Style.muted()}● {Style.RESET}{dep}")
        return lines

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 60
        inner_lines = [""]
        for l in self.content_lines: inner_lines.append(f"    {l}")
        inner_lines.append("")
        
        btn_s = "  SAVE  "
        btn_c = "  CANCEL  "
        if self.focus_idx == 0:
            s_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_s}{Style.RESET}"
            c_styled = f"{Style.muted()}[{btn_c.strip()}]{Style.RESET}"
        else:
            s_styled = f"{Style.muted()}[{btn_s.strip()}]{Style.RESET}"
            c_styled = f"{Style.highlight(bg=True)}{Style.crust()}{Style.BOLD}{btn_c}{Style.RESET}"
        
        btn_row = f"{s_styled}     {c_styled}"
        pad = (width - 2 - TUI.visible_len(btn_row)) // 2
        inner_lines.append(f"{' ' * pad}{btn_row}")
        inner_lines.append("")
        
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="FINAL SUMMARY", is_focused=True)
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]: self.focus_idx = 1 if self.focus_idx == 0 else 0
        elif key == Keys.ENTER: return "SAVE" if self.focus_idx == 0 else "CANCEL"
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]: return "CANCEL"
        return None

class DraftSelectionModal:
    """Draft selection with 4-space margins."""
    def __init__(self, drafts):
        self.drafts = drafts
        self.focus_idx = 0
        self.scroll_offset = 0

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 64
        options = self.drafts + [("fresh", None, None)]
        available_content_height = term_height - 12
        max_rows = min(len(options), available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""]
        
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(options):
                fname, data, mtime = options[idx]
                is_focused = (self.focus_idx == idx)
                
                if fname == "fresh":
                    label = "[ Start Fresh / New ]"
                else:
                    d_id = data.get('id', 'unnamed')
                    d_time = datetime.fromtimestamp(mtime).strftime("%d %b %H:%M")
                    label = f"{d_id} ({d_time})"
                
                style = Style.mauve() + Style.BOLD if is_focused else Style.text()
                inner_lines.append(f"    {style}{label}{Style.RESET}")

        inner_lines.append("")
        hint = "ENTER: Select   X: Delete   ESC: Start Fresh"
        inner_lines.append(f"{' ' * ((width - 2 - TUI.visible_len(hint)) // 2)}{Style.muted()}{hint}{Style.RESET}")
        
        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="RESUME DRAFT?", is_focused=True)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        opt_len = len(self.drafts) + 1
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % opt_len
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % opt_len
        elif key == Keys.ENTER:
            if self.focus_idx < len(self.drafts):
                return ("LOAD", self.drafts[self.focus_idx])
            return "FRESH"
        elif key in [ord('x'), ord('X'), Keys.DEL]:
            if self.focus_idx < len(self.drafts):
                return ("DELETE_REQ", self.drafts[self.focus_idx])
        elif key in [Keys.ESC, Keys.Q, Keys.Q_UPPER]:
            return "FRESH"
        return None

class CreateScreen(Screen):
    """
    Interactive wizard for creating package modules.
    Provides a triple-box interface (Form, Help, Preview).
    """
    def __init__(self, modules: list[Module]):
        self.modules = modules
        self.categories = self._get_categories()
        self.drafts_dir = "modules/.drafts"
        self.active_draft_path = None
        
        # Form data with default values
        self._reset_form()
        
        # Available options
        self.managers = ['system', 'cargo', 'brew', 'bob', 'custom']
        
        # UI State
        self.focus_idx = 0
        self.form_offset = 0    # Scroll for form fields
        self.preview_offset = 0 # Scroll for preview
        self.is_editing = False # Text input mode
        self.text_cursor_pos = 0 # Cursor position within string
        self.old_value = ""     # To restore on ESC
        self.modal = None
        self.modal_type = None # "DISCARD", "SAVE", "DRAFT", "LOAD_DRAFT", "DELETE_DRAFT"
        self.status_msg = ""
        self.status_time = 0
        self.show_validation_errors = False
        
        self.fields = [
            {'id': 'id', 'label': 'ID', 'type': 'text', 'help': 'Unique identifier. Used for filename and dots/ folder.'},
            {'id': 'label', 'label': 'Label', 'type': 'text', 'help': 'Display name in the selection menu.'},
            {'id': 'manager', 'label': 'Package Manager', 'type': 'radio', 'options': self.managers, 'help': 'Select the package manager driver.'},
            {'id': 'pkg_name', 'label': 'Package Name', 'type': 'text', 'help': 'Exact package name for the manager. Defaults to ID.'},
            {'id': 'category', 'label': 'Category', 'type': 'radio', 'options': self.categories, 'help': 'Group name for the package list.'},
            {'id': 'stow_target', 'label': 'Target Path', 'type': 'text', 'help': 'Deployment destination (defaults to ~).'},
            {'id': 'dependencies', 'label': 'Dependencies', 'type': 'multi', 'help': 'Other modules required by this package.'},
            {'id': 'is_incomplete', 'label': 'Manual Mode', 'type': 'check', 'help': 'Mark as incomplete for custom Python logic.'},
            {'id': 'files', 'label': 'Files', 'type': 'placeholder', 'help': '[Future] file picker.'}
        ]

        # Check for drafts
        self._check_for_drafts()

    def _reset_form(self):
        """Resets the form to initial clean state."""
        self.form = {
            'id': '',
            'label': '',
            'manager': 'system',
            'pkg_name': '',
            'category': self.categories[0] if self.categories else 'General',
            'custom_category': '',
            'stow_target': '~',
            'dependencies': [],
            'is_incomplete': False,
            'files': []
        }
        self.active_draft_path = None

    def _check_for_drafts(self):
        """Scans .drafts/ folder and opens selection modal if any exist."""
        if not os.path.exists(self.drafts_dir):
            return
            
        draft_files = []
        for f in os.listdir(self.drafts_dir):
            if f.endswith(".json"):
                path = os.path.join(self.drafts_dir, f)
                try:
                    with open(path, 'r') as j:
                        data = json.load(j)
                        mtime = os.path.getmtime(path)
                        draft_files.append((f, data, mtime))
                except:
                    continue
        
        if draft_files:
            # Sort by mtime descending (newest first)
            draft_files.sort(key=lambda x: x[2], reverse=True)
            self.modal = DraftSelectionModal(draft_files)
            self.modal_type = "LOAD_DRAFT"

    def save_draft(self):
        """Saves current form data to a JSON draft."""
        if not os.path.exists(self.drafts_dir):
            os.makedirs(self.drafts_dir)
            
        name = self.form['id'] if self.form['id'] else f"draft_temp_{int(time.time())}"
        path = os.path.join(self.drafts_dir, f"{name}.json")
        
        try:
            with open(path, 'w') as f:
                json.dump(self.form, f, indent=4)
            self.active_draft_path = path
            self.status_msg = f"{Style.green()}Draft saved: {name}.json{Style.RESET}"
            self.status_time = time.time()
        except Exception as e:
            self.status_msg = f"{Style.red()}Error saving draft: {str(e)}{Style.RESET}"
            self.status_time = time.time()

    def _get_categories(self):
        """Extracts existing categories from loaded modules."""
        cats = sorted(list(set(m.category for m in self.modules if m.category and m.category != "Custom...✎")))
        cats.append("Custom...✎")
        return cats

    def _get_field_errors(self, field_id):
        """Returns a list of error messages for a specific field."""
        errors = []
        val = self.form.get(field_id, "")
        
        if field_id == 'id':
            if not val:
                errors.append("ID cannot be empty.")
            elif not re.match(r'^[a-zA-Z0-9_-]+$', val):
                errors.append("Invalid format! Use letters, numbers, - or _ only.")
            elif any(m.id == val for m in self.modules):
                errors.append("This ID already exists!")
        
        elif field_id == 'label':
            if not val:
                errors.append("Label cannot be empty.")
        
        elif field_id == 'category':
            if val == "Custom...✎" and not self.form['custom_category']:
                errors.append("Custom category name cannot be empty.")

        return errors

    def _ensure_focus_visible(self):
        """Adjusts form_offset to keep the focused field in view."""
        reachable = self._get_reachable_indices()
        line_map = {}
        curr = 1 # Initial blank
        term_width = shutil.get_terminal_size().columns
        left_width = int(term_width * 0.40)
        
        for idx in reachable:
            line_map[idx] = curr
            f = self.fields[idx]
            if f['type'] == 'radio':
                # Replicate render wrapping logic
                items = []
                for opt in f['options']:
                    lbl = opt
                    if opt == "Custom...✎" and self.form[f['id']] == "Custom...✎":
                        c_val = self.form['custom_category']
                        lbl = f"Custom: '{c_val}' ✎" if c_val else "Custom...✎"
                    items.append(f"● {lbl}")
                
                vlen = TUI.visible_len("   ".join(items))
                if vlen > left_width - 6: curr += 4 # Label + 2 lines of options + spacer
                else: curr += 3 # Label + 1 line of options + spacer
            else:
                curr += 2 # Content line + spacer
            
        field_top = line_map.get(self.focus_idx, 0)
        # Determine field bottom
        idx_in_reach = reachable.index(self.focus_idx)
        if idx_in_reach + 1 < len(reachable):
            field_bottom = line_map[reachable[idx_in_reach + 1]] - 1
        else:
            field_bottom = curr - 1
        
        term_height = shutil.get_terminal_size().lines
        available_height = term_height - 5
        content_height = available_height - 2
        
        # Adjust offset
        if field_top < self.form_offset + 1:
            self.form_offset = max(0, field_top - 1)
        elif field_bottom >= self.form_offset + content_height:
            self.form_offset = field_bottom - content_height + 1

    def _get_reachable_indices(self):
        """Returns indices of fields that should be accessible based on form state."""
        return [0, 1, 2, 3, 4, 5, 6, 7, 8] # ID, Label, Manager, PkgName, Category, Target, Deps, Manual, Files

    def render(self):
        """Draws the triple-box layout (45/55 vertical split on right)."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Header
        title_text = " PACKAGE WIZARD "
        padding = (term_width - len(title_text)) // 2
        header_bar = f"{Style.mauve(bg=True)}{Style.crust()}{' '*padding}{title_text}{' '*(term_width-padding-len(title_text))}{Style.RESET}"
        
        available_height = term_height - 5
        left_width = int(term_width * 0.40)
        right_width = term_width - left_width - 1
        
        # 2. Build Left Content (Form)
        form_lines = [""]
        reachable = self._get_reachable_indices()
        
        for i, field in enumerate(self.fields):
            if i not in reachable:
                continue
                
            is_focused = (self.focus_idx == i and not self.modal)
            
            f_errors = self._get_field_errors(field['id'])
            has_error = len(f_errors) > 0 and (self.show_validation_errors or (field['id'] == 'id' and self.form['id']))
            
            # Row styling
            if is_focused: row_style = Style.highlight()
            elif has_error: row_style = Style.red()
            else: row_style = Style.normal()
            
            # Apply bold only to focused labels, not to hints
            label_bold = Style.BOLD if is_focused else ""
            
            if field['type'] in ['text', 'check', 'multi', 'placeholder']:
                # Split Layout
                label_text = field['label']
                if is_focused:
                    hint = ""
                    if field['type'] == 'text': hint = "e to edit"
                    elif field['type'] == 'check': hint = "SPACE to toggle"
                    elif field['type'] == 'multi': hint = "ENTER to select"
                    # Hint is added WITHOUT bold
                    label_display = f"{row_style}{label_bold}{label_text}{Style.RESET} {Style.muted()}{hint}{Style.RESET}"
                else:
                    label_display = f"{row_style}{label_text}{Style.RESET}"

                if field['type'] == 'text':
                    val = self.form[field['id']]
                    if is_focused and self.is_editing:
                        pre = val[:self.text_cursor_pos]
                        char = val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                        post = val[self.text_cursor_pos+1:]
                        val_display = f"{pre}{Style.INVERT}{char}{Style.RESET}{row_style}{label_bold}{post}"
                    else:
                        val_display = val
                    value_display = f"{row_style}{label_bold}✎ [ {val_display}{Style.RESET}{row_style}{label_bold} ]{Style.RESET}"
                elif field['type'] == 'check':
                    value_display = f"{row_style}{label_bold}{'YES [■]' if self.form[field['id']] else 'NO [ ]'}{Style.RESET}"
                elif field['type'] == 'multi':
                    value_display = f"{row_style}{label_bold}↓ [ {len(self.form[field['id']])} items ]{Style.RESET}"
                else: # placeholder
                    value_display = f"{Style.muted()}[ Not implemented ]{Style.RESET}"
                
                line = TUI.split_line(label_display, value_display, left_width - 6)
                form_lines.append(f"  {line}")
                form_lines.append("") 
                
            elif field['type'] == 'radio':
                # Centered Radio Group
                label_text = field['label']
                if is_focused:
                    h_txt = "h/l to select"
                    if field['id'] == 'category' and self.form['category'] == 'Custom...✎':
                        h_txt = "h/l to select, e to edit"
                    label_display = f"{row_style}{label_bold}{label_text}{Style.RESET} {Style.muted()}{h_txt}{Style.RESET}"
                else:
                    label_display = f"{row_style}{label_text}{Style.RESET}"
                
                form_lines.append(f"  {label_display}")
                
                items = []
                current_val = self.form[field['id']]
                for opt in field['options']:
                    is_sel = (current_val == opt)
                    mark = "●" if is_sel else "○"
                    
                    label_txt = opt
                    is_custom_empty = (opt == "Custom...✎" and is_sel and not self.form['custom_category'])
                    
                    if opt == "Custom...✎" and is_sel:
                        c_val = self.form['custom_category']
                        if is_focused and self.is_editing:
                            pre = c_val[:self.text_cursor_pos]
                            char = c_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                            post = c_val[self.text_cursor_pos+1:]
                            label_txt = f"Custom: '{pre}{Style.INVERT}{char}{Style.RESET}{row_style}{label_bold}{post}' ✎"
                        else:
                            label_txt = f"Custom: '{c_val}' ✎" if c_val else "Custom...✎"
                    
                    if is_custom_empty:
                        # Alert state for empty custom category
                        color = Style.red()
                        if is_focused: item = f"{color}{Style.BOLD}{mark} {label_txt}{Style.RESET}"
                        else: item = f"{color}{mark} {label_txt}{Style.RESET}"
                    elif is_focused:
                        if is_sel: item = f"{Style.highlight()}{Style.BOLD}{mark} {label_txt}{Style.RESET}"
                        else: item = f"{Style.muted()}{mark} {label_txt}{Style.RESET}"
                    else:
                        color = Style.green() if is_sel else Style.muted()
                        item = f"{color}{mark} {label_txt}{Style.RESET}"
                    items.append(item)
                
                radio_raw = "   ".join(items)
                vlen = TUI.visible_len(radio_raw)
                if vlen > left_width - 6:
                    mid = len(items) // 2
                    l1 = "   ".join(items[:mid]); l2 = "   ".join(items[mid:])
                    for l in [l1, l2]:
                        pad = (left_width - 6 - TUI.visible_len(l)) // 2
                        form_lines.append(f"{' '*(pad+2)}{l}")
                else:
                    pad = (left_width - 6 - vlen) // 2
                    form_lines.append(f"{' '*(pad+2)}{radio_raw}")
                form_lines.append("")

        # 3. Right Content (Help & Preview)
        help_content = []
        curr_field = self.fields[self.focus_idx]
        for l in TUI.wrap_text(curr_field['help'], right_width - 6): help_content.append(f"  {Style.normal()}{l}{Style.RESET}")
        
        errors = self._get_field_errors(curr_field['id'])
        # Show errors if: 
        # 1. Global validation triggered (show_validation_errors)
        # 2. We are currently editing the field
        # 3. It's the ID field and has content (proactive validation)
        # 4. It's the Category field, Custom is selected but empty
        is_custom_cat_empty = (curr_field['id'] == 'category' and self.form['category'] == 'Custom...✎' and not self.form['custom_category'])
        
        if errors and (self.show_validation_errors or self.is_editing or (curr_field['id'] == 'id' and self.form['id']) or is_custom_cat_empty):
            for e in errors: help_content.append(f"  {Style.red()}! {e}{Style.RESET}")
        
        help_height = min(len(help_content) + 2, available_height // 3)
        preview_height = available_height - help_height
        
        # Python Preview
        preview_code = self._generate_python()
        preview_lines = [""]
        for line in preview_code.split("\n"):
            for wl in TUI.wrap_text(line, right_width - 6): preview_lines.append(f"  {Style.normal()}{wl}{Style.RESET}")
        
        max_p_off = max(0, len(preview_lines) - (preview_height - 2))
        if self.preview_offset > max_p_off: self.preview_offset = max_p_off
        visible_preview = preview_lines[self.preview_offset : self.preview_offset + (preview_height - 2)]

        # 4. Assembly
        content_height = available_height - 2
        visible_form = form_lines[self.form_offset : self.form_offset + content_height]
        
        f_scroll_pos, f_scroll_size = None, None
        if len(form_lines) > content_height:
            thumb_size = max(1, int(content_height**2 / len(form_lines)))
            max_off = len(form_lines) - content_height
            prog = self.form_offset / max_off if max_off > 0 else 0
            f_scroll_pos = int(prog * (content_height - thumb_size))
            f_scroll_size = thumb_size
            
        left_box = TUI.create_container(visible_form, left_width, available_height, title="FORM", is_focused=(not self.modal), scroll_pos=f_scroll_pos, scroll_size=f_scroll_size)
        help_box = TUI.create_container(help_content, right_width, help_height, title="HELP", is_focused=False)
        
        p_scroll = None
        if len(preview_lines) > (preview_height - 2):
            ts = max(1, int((preview_height - 2)**2 / len(preview_lines)))
            p_scroll = (int((self.preview_offset / max_p_off) * (preview_height - 2 - ts)), ts) if max_p_off > 0 else (0, ts)

        preview_box = TUI.create_container(visible_preview, right_width, preview_height, title="PYTHON PREVIEW", is_focused=False, 
                                         scroll_pos=p_scroll[0] if p_scroll else None, scroll_size=p_scroll[1] if p_scroll else None)
        
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 5. Footer (Pills preserved)
        if self.is_editing:
            p_line = f"{TUI.pill('ENTER', 'Finish', Theme.GREEN)}    {TUI.pill('ESC', 'Cancel', Theme.RED)}"
        else:
            field = self.fields[self.focus_idx]
            f_pills = [
                TUI.pill('h/j/k/l', 'Navigate', Theme.SKY),
                TUI.pill('PgUp/Dn', 'Scroll Script', Theme.BLUE),
            ]
            
            if field['type'] == 'text':
                f_pills.append(TUI.pill('E', 'Edit', Theme.BLUE))
            
            enter_label = "Select" if field['type'] == 'multi' else "Summary & Save"
            f_pills.append(TUI.pill('ENTER', enter_label, Theme.GREEN))
            f_pills.append(TUI.pill('Q', 'Back', Theme.RED))
            
            p_line = "    ".join(f_pills)
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(p_line)) // 2)}{p_line}")

        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            for i, ml in enumerate(m_lines):
                if 0 <= m_y + i < len(buffer): buffer[m_y + i] = TUI.overlay(buffer[m_y + i], ml, m_x)
        
        buffer = TUI.draw_notifications(buffer)

        # Final Render
        final_output = "\n".join([TUI.visible_ljust(line, term_width) for line in buffer[:term_height]])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def save_package(self):

        """Generates the .py module and creates the dots/ folder."""
        fid = self.form['id']
        module_path = os.path.join("modules", f"{fid}.py")
        dots_path = os.path.join("dots", fid)
        
        try:
            # 1. Generate Python Code
            code = "from modules.base import Module\n\n"
            code += self._generate_python()
            
            # If Manual Mode is enabled, add the install method template
            if self.form['is_incomplete']:
                code += "\n\n    def install(self):\n        # TODO: Implement custom logic\n        super().install()"
            
            # 2. Write Module File
            with open(module_path, "w") as f:
                f.write(code + "\n")
            
            # 3. Create Dots Directory
            if not os.path.exists(dots_path):
                os.makedirs(dots_path)
            
            # 4. Clean up draft if exists
            if self.active_draft_path and os.path.exists(self.active_draft_path):
                os.remove(self.active_draft_path)
            elif os.path.exists(os.path.join(self.drafts_dir, f"{fid}.json")):
                os.remove(os.path.join(self.drafts_dir, f"{fid}.json"))
                
            return True
        except Exception as e:
            self.status_msg = f"{Style.red()}Save failed: {str(e)}{Style.RESET}"
            self.status_time = time.time()
            return False

    def _generate_python(self):
        """Generates the Python class code based on form data."""
        fid = self.form['id'] or "my_package"
        label = self.form['label'] or "My Package"
        class_name = "".join([p.capitalize() for p in fid.replace("-", "_").split("_")]) + "Module"
        cat = self.form['custom_category'] if self.form['category'] == "Custom...✎" else self.form['category']
        
        code = f"class {class_name}(Module):\n"
        code += f"    id = \"{fid}\"\n    label = \"{label}\"\n    category = \"{cat}\"\n    manager = \"{self.form['manager']}\""
        if self.form['pkg_name'] and self.form['pkg_name'] != fid:
            code += f"\n    package_name = \"{self.form['pkg_name']}\""
        if self.form['stow_target'] != "~":
            code += f"\n    stow_target = \"{self.form['stow_target']}\""
        if self.form['dependencies']:
            code += f"\n    dependencies = {self.form['dependencies']}"
            
        return code

    def handle_input(self, key):
        """Processes navigation and editing."""
        if self.modal:
            res = self.modal.handle_input(key)
            if res == "YES":
                if self.modal_type == "DISCARD": 
                    TUI.push_notification("Changes discarded", type="INFO")
                    return "WELCOME"
                elif self.modal_type == "DRAFT":
                    self.save_draft()
                    self.modal = None
                    TUI.push_notification("Draft saved successfully", type="INFO")
                    return "WELCOME"
                elif self.modal_type == "DELETE_DRAFT":
                    if self.active_draft_path and os.path.exists(self.active_draft_path):
                        os.remove(self.active_draft_path)
                        self._reset_form()
                        TUI.push_notification("Draft deleted successfully", type="INFO")
                    self.modal = None
                elif self.modal_type == "DELETE_MODAL_DRAFT":
                    path = os.path.join(self.drafts_dir, self.pending_delete[0])
                    if os.path.exists(path):
                        os.remove(path)
                        TUI.push_notification("Draft deleted successfully", type="INFO")
                    self.modal = None
                    self._check_for_drafts() # Refresh list
                    return None
            elif res == "CONFIRM":
                if isinstance(self.modal, DependencyModal):
                    self.form['dependencies'] = self.modal.get_selected()
                self.modal = None
            elif isinstance(res, tuple):
                if res[0] == "LOAD":
                    filename, data, mtime = res[1]
                    self.form.update(data)
                    self.active_draft_path = os.path.join(self.drafts_dir, filename)
                    self.modal = None
                elif res[0] == "DELETE_REQ":
                    self.pending_delete = res[1] # (filename, data, mtime)
                    self.modal = ConfirmModal("DELETE DRAFT?", f"Are you sure you want to permanently delete '{res[1][1].get('id', 'unnamed')}' draft?")
                    self.modal_type = "DELETE_MODAL_DRAFT"
            elif res == "SAVE":
                if self.save_package():
                    TUI.push_notification(f"Module '{self.form['id']}' created", type="INFO")
                    return "RELOAD_AND_WELCOME"
                else:
                    self.modal = None
            elif res == "FRESH":
                self.modal = None
            elif res in ["NO", "CLOSE", "CANCEL"]:
                if self.modal_type == "DELETE_MODAL_DRAFT":
                    self._check_for_drafts() # Return to selection modal
                else:
                    self.modal = None
            return None

        field = self.fields[self.focus_idx]
        
        # --- EDIT MODE ---
        if self.is_editing:
            target = field['id']
            if field['id'] == 'category' and self.form['category'] == 'Custom...✎':
                target = 'custom_category'
            
            curr_val = self.form[target]
            if key == Keys.ENTER: self.is_editing = False
            elif key == Keys.ESC:
                self.form[target] = self.old_value
                self.is_editing = False
            elif key == Keys.BACKSPACE:
                if self.text_cursor_pos > 0:
                    self.form[target] = curr_val[:self.text_cursor_pos-1] + curr_val[self.text_cursor_pos:]
                    self.text_cursor_pos -= 1
            elif key == Keys.DEL:
                if self.text_cursor_pos < len(curr_val):
                    self.form[target] = curr_val[:self.text_cursor_pos] + curr_val[self.text_cursor_pos+1:]
            elif key == Keys.LEFT:
                self.text_cursor_pos = max(0, self.text_cursor_pos - 1)
            elif key == Keys.RIGHT:
                self.text_cursor_pos = min(len(curr_val), self.text_cursor_pos + 1)
            elif 32 <= key <= 126:
                self.form[target] = curr_val[:self.text_cursor_pos] + chr(key) + curr_val[self.text_cursor_pos:]
                self.text_cursor_pos += 1
            return None

        # --- NAVIGATION MODE ---
        if key in [ord('d'), ord('D')]:
            self.modal = ConfirmModal("SAVE DRAFT", "Do you want to save the current progress as a draft?")
            self.modal_type = "DRAFT"
            return None
        
        if key in [ord('x'), ord('X')] and self.active_draft_path:
            d_id = self.form['id'] or "unnamed"
            self.modal = ConfirmModal("DELETE ACTIVE DRAFT?", f"Are you sure you want to permanently delete '{d_id}' draft?")
            self.modal_type = "DELETE_DRAFT"
            return None

        # --- NAVIGATION MODE ---
        if key in [Keys.Q, Keys.Q_UPPER]:
            is_dirty = any(self.form[k] for k in ['id', 'label', 'pkg_name', 'custom_category']) or self.form['stow_target'] != "~" or self.form['dependencies']
            if is_dirty:
                self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?")
                self.modal_type = "DISCARD"
            else: return "WELCOME"
                
        reachable = self._get_reachable_indices()
        if key in [Keys.UP, Keys.K]:
            try:
                curr_pos = reachable.index(self.focus_idx)
                self.focus_idx = reachable[(curr_pos - 1) % len(reachable)]
            except ValueError:
                self.focus_idx = 0
            self._ensure_focus_visible()
        elif key in [Keys.DOWN, Keys.J]:
            try:
                curr_pos = reachable.index(self.focus_idx)
                self.focus_idx = reachable[(curr_pos + 1) % len(reachable)]
            except ValueError:
                self.focus_idx = 0
            self._ensure_focus_visible()
        
        elif key in [Keys.LEFT, Keys.H]:
            if field['type'] == 'radio':
                opts = field['options']
                curr_idx = opts.index(self.form[field['id']])
                self.form[field['id']] = opts[(curr_idx - 1) % len(opts)]
        elif key in [Keys.RIGHT, Keys.L]:
            if field['type'] == 'radio':
                opts = field['options']
                curr_idx = opts.index(self.form[field['id']])
                self.form[field['id']] = opts[(curr_idx + 1) % len(opts)]

        elif key == Keys.SPACE:
            if field['type'] == 'check': self.form[field['id']] = not self.form[field['id']]
        elif key in [ord('e'), ord('E')]:
            if field['type'] == 'text':
                self.is_editing = True
                self.old_value = self.form[field['id']]
                self.text_cursor_pos = len(self.old_value)
            elif field['id'] == 'category' and self.form['category'] == 'Custom...✎':
                self.is_editing = True
                self.old_value = self.form['custom_category']
                self.text_cursor_pos = len(self.old_value)
            return None
            
        elif key == Keys.ENTER:
            # Check if field opens a modal
            if field['type'] == 'multi':
                self.modal = DependencyModal(self.modules, self.form['dependencies'])
                return None

            # GLOBAL SUMMARY TRIGGER
            all_errors = []
            for f in self.fields:
                if f['id'] in self.form:
                    all_errors.extend(self._get_field_errors(f['id']))
            
            if all_errors:
                self.show_validation_errors = True
                TUI.push_notification("Please fix form errors before saving", type="ERROR")
            else:
                self.modal = WizardSummaryModal(self.form)
            return None

        elif key == Keys.PGUP: self.preview_offset = max(0, self.preview_offset - 5)
        elif key == Keys.PGDN: self.preview_offset += 5 
        return None
