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
from core.screens.shared_modals import DependencyModal, WizardSummaryModal, DraftSelectionModal, ConfirmModal

# Internal Constants
CUSTOM_TAG = "Custom...✎"
CUSTOM_FIELD = "custom_category"
DRAFTS_DIR = "modules/.drafts"

class CreateScreen(Screen):
    """
    Interactive wizard for creating package modules.
    Provides a triple-box interface (Form, Help, Preview).
    """
    def __init__(self, modules: list[Module]):
        self.modules = modules
        self.categories = self._get_categories()
        
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
        if not os.path.exists(DRAFTS_DIR):
            return
            
        draft_files = []
        for f in os.listdir(DRAFTS_DIR):
            if f.endswith(".json"):
                path = os.path.join(DRAFTS_DIR, f)
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
        TUI._notifications = []
        if not os.path.exists(DRAFTS_DIR):
            os.makedirs(DRAFTS_DIR)
            
        name = self.form['id'] if self.form['id'] else f"draft_temp_{int(time.time())}"
        path = os.path.join(DRAFTS_DIR, f"{name}.json")
        
        try:
            with open(path, 'w') as f:
                json.dump(self.form, f, indent=4)
            self.active_draft_path = path
            TUI.push_notification(f"Draft saved: {name}.json", type="INFO")
        except Exception as e:
            TUI.push_notification(f"Error saving draft: {str(e)}", type="ERROR")

    def _get_categories(self):
        """Extracts existing categories from loaded modules."""
        cats = sorted(list(set(m.category for m in self.modules if m.category and m.category != CUSTOM_TAG)))
        cats.append(CUSTOM_TAG)
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
            if val == CUSTOM_TAG and not self.form[CUSTOM_FIELD]:
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
                    if opt == CUSTOM_TAG and self.form[f['id']] == CUSTOM_TAG:
                        c_val = self.form[CUSTOM_FIELD]
                        lbl = f"Custom: '{c_val}' ✎" if c_val else CUSTOM_TAG
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
        available_height = term_height - 7
        
        # Adjust offset
        if field_top < self.form_offset + 1:
            self.form_offset = max(0, field_top - 1)
        elif field_bottom >= self.form_offset + available_height:
            self.form_offset = field_bottom - available_height + 1

    def _get_reachable_indices(self):
        """Returns indices of fields that should be accessible based on form state."""
        return list(range(len(self.fields)))

    def render(self):
        """Draws the triple-box layout (45/55 vertical split on right)."""
        tw, th = shutil.get_terminal_size()
        
        # 1. Header & Footer
        header = f"{Style.mauve(bg=True)}{Style.crust()}{' PACKAGE WIZARD '.center(tw)}{Style.RESET}"
        footer_pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(footer_pills, tw - 4)
        available_h = max(10, th - 4 - len(footer_lines))
        
        lw = int(tw * 0.40)
        rw = tw - lw - 1
        
        # 2. Content Sections
        form_lines = self._build_form_lines(lw)
        content_h = available_h - 2
        visible_form = form_lines[self.form_offset : self.form_offset + content_h]
        
        # 3. Box Assembly
        f_scroll = self._get_scrollbar(len(form_lines), content_h, self.form_offset)
        left_box = TUI.create_container(
            visible_form, lw, available_h, title="FORM", color="", is_focused=(not self.modal), 
            scroll_pos=f_scroll['scroll_pos'], scroll_size=f_scroll['scroll_size']
        )
        
        help_box, preview_box = self._build_right_panels(rw, available_h)
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 4. Buffer Assembly
        buffer = [header, ""] + main_content + [""]
        for f_line in footer_lines:
            f_pad = max(0, (tw - TUI.visible_len(f_line)) // 2)
            buffer.append(f"{' ' * f_pad}{f_line}")

        if self.modal:
            m_lines, my, mx = self.modal.render()
            for i, ml in enumerate(m_lines):
                if 0 <= my + i < len(buffer): buffer[my + i] = TUI.overlay(buffer[my + i], ml, mx)
        
        buffer = TUI.draw_notifications(buffer)
        final_output = "\n".join([TUI.visible_ljust(l, tw) for l in buffer[:th]])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        if self.is_editing:
            return [TUI.pill('ENTER', 'Finish', Theme.GREEN), TUI.pill('ESC', 'Cancel', Theme.RED)]
        
        field = self.fields[self.focus_idx]
        pills = [TUI.pill('h/j/k/l', 'Navigate', Theme.SKY), TUI.pill('PgUp/Dn', 'Scroll Script', Theme.BLUE)]
        if field['type'] == 'text': pills.append(TUI.pill('E', 'Edit', Theme.BLUE))
        pills.append(TUI.pill('D', 'Draft', Theme.PEACH))
        if self.active_draft_path: pills.append(TUI.pill('X', 'Delete Draft', Theme.RED))
        pills.append(TUI.pill('ENTER', "Select" if field['type'] == 'multi' else "Summary & Save", Theme.GREEN))
        pills.append(TUI.pill('Q', 'Back', Theme.RED))
        return pills

    def _get_scrollbar(self, total_lines, visible_h, offset):
        if total_lines <= visible_h: return {'scroll_pos': None, 'scroll_size': None}
        size = max(1, int(visible_h**2 / total_lines))
        pos = int((offset / (total_lines - visible_h)) * (visible_h - size))
        return {'scroll_pos': pos, 'scroll_size': size}

    def _build_form_lines(self, width):
        lines = [""]
        reachable = self._get_reachable_indices()
        for i, field in enumerate(self.fields):
            if i not in reachable: continue
            is_focused = (self.focus_idx == i and not self.modal)
            errors = self._get_field_errors(field['id'])
            has_error = errors and (self.show_validation_errors or (field['id'] == 'id' and self.form['id']))
            
            style = Style.highlight() if is_focused else (Style.red() if has_error else Style.normal())
            bold = Style.BOLD if is_focused else ""
            
            if field['type'] == 'radio':
                lines.extend(self._render_radio_field(field, is_focused, style, bold, width))
            else:
                lines.extend(self._render_standard_field(field, is_focused, style, bold, width))
        return lines

    def _render_standard_field(self, field, is_focused, style, bold, width):
        hints = {'text': 'e to edit', 'check': 'SPACE to toggle', 'multi': 'ENTER to select'}
        hint = f" {Style.muted()}{hints.get(field['type'], '')}{Style.RESET}" if is_focused else ""
        label = f"{style}{bold}{field['label']}{Style.RESET}{hint}"
        
        val = self.form.get(field['id'], "")
        if field['type'] == 'text':
            if is_focused and self.is_editing:
                pre, char, post = val[:self.text_cursor_pos], val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", val[self.text_cursor_pos+1:]
                val_display = f"{pre}{Style.INVERT}{char}{Style.RESET}{style}{bold}{post}"
            else: val_display = val
            value = f"{style}{bold}✎ [ {val_display}{Style.RESET}{style}{bold} ]{Style.RESET}"
        elif field['type'] == 'check':
            value = f"{style}{bold}{'YES [■]' if val else 'NO [ ]'}{Style.RESET}"
        elif field['type'] == 'multi':
            value = f"{style}{bold}↓ [ {len(val)} items ]{Style.RESET}"
        else:
            value = f"{Style.muted()}[ Not implemented ]{Style.RESET}"
            
        return [f"  {TUI.split_line(label, value, width - 6)}", ""]

    def _render_radio_field(self, field, is_focused, style, bold, width):
        h_txt = "h/l to select" + (", e to edit" if field['id'] == 'category' and self.form['category'] == CUSTOM_TAG else "")
        hint = f" {Style.muted()}{h_txt}{Style.RESET}" if is_focused else ""
        lines = [f"  {style}{bold}{field['label']}{Style.RESET}{hint}"]
        
        items = []
        for opt in field['options']:
            is_sel = (self.form[field['id']] == opt)
            mark = "●" if is_sel else "○"
            label = opt
            if opt == CUSTOM_TAG and is_sel:
                c_val = self.form[CUSTOM_FIELD]
                if is_focused and self.is_editing:
                    pre, char, post = c_val[:self.text_cursor_pos], c_val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", c_val[self.text_cursor_pos+1:]
                    label = f"Custom: '{pre}{Style.INVERT}{char}{Style.RESET}{style}{bold}{post}' ✎"
                else: label = f"Custom: '{c_val}' ✎" if c_val else CUSTOM_TAG
            
            is_err = (opt == CUSTOM_TAG and is_sel and not self.form[CUSTOM_FIELD])
            c = Style.red() if is_err else (Style.highlight() if is_sel and is_focused else (Style.green() if is_sel else Style.muted()))
            items.append(f"{c}{bold if is_sel and is_focused else ''}{mark} {label}{Style.RESET}")

        radio_row = "   ".join(items)
        if TUI.visible_len(radio_row) > width - 6:
            mid = len(items) // 2
            for l in ["   ".join(items[:mid]), "   ".join(items[mid:])]:
                lines.append(f"{' ' * ((width - 6 - TUI.visible_len(l)) // 2 + 2)}{l}")
        else:
            lines.append(f"{' ' * ((width - 6 - TUI.visible_len(radio_row)) // 2 + 2)}{radio_row}")
        lines.append("")
        return lines

    def _build_right_panels(self, width, height):
        field = self.fields[self.focus_idx]
        help_lines = [f"  {Style.normal()}{l}{Style.RESET}" for l in TUI.wrap_text(field['help'], width - 6)]
        
        is_custom_cat_empty = (field['id'] == 'category' and self.form['category'] == CUSTOM_TAG and not self.form[CUSTOM_FIELD])
        if self._get_field_errors(field['id']) and (self.show_validation_errors or self.is_editing or (field['id'] == 'id' and self.form['id']) or is_custom_cat_empty):
            for e in self._get_field_errors(field['id']): help_lines.append(f"  {Style.red()}! {e}{Style.RESET}")
            
        h_height = min(len(help_lines) + 2, height // 3)
        p_height = height - h_height
        
        preview_lines = [""]
        for line in self._generate_python().split("\n"):
            for wl in TUI.wrap_text(line, width - 6): preview_lines.append(f"  {Style.normal()}{wl}{Style.RESET}")
        
        max_p_off = max(0, len(preview_lines) - (p_height - 2))
        self.preview_offset = min(self.preview_offset, max_p_off)
        visible_preview = preview_lines[self.preview_offset : self.preview_offset + (p_height - 2)]
        
        p_scroll = self._get_scrollbar(len(preview_lines), p_height - 2, self.preview_offset)
        return TUI.create_container(help_lines, width, h_height, title="HELP"), \
               TUI.create_container(
                   visible_preview, width, p_height, title="PYTHON PREVIEW", color="", is_focused=False, 
                   scroll_pos=p_scroll['scroll_pos'], scroll_size=p_scroll['scroll_size']
               )

    def save_package(self):
        """Generates the .py module and creates the dots/ folder."""
        fid = self.form['id']
        module_path = os.path.join("modules", f"{fid}.py")
        dots_path = os.path.join("dots", fid)
        
        try:
            # 1. Generate Python Code
            code = "from modules.base import Module\n\n" + self._generate_python()

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
            elif os.path.exists(os.path.join(DRAFTS_DIR, f"{fid}.json")):
                os.remove(os.path.join(DRAFTS_DIR, f"{fid}.json"))
                
            return True
        except Exception as e:
            TUI.push_notification(f"Save failed: {str(e)}", type="ERROR")
            return False

    def _generate_python(self):
        """Generates the Python class code based on form data."""
        fid = self.form['id'] or "my_package"
        label = self.form['label'] or "My Package"
        class_name = "".join([p.capitalize() for p in fid.replace("-", "_").split("_")]) + "Module"
        cat = self.form[CUSTOM_FIELD] if self.form['category'] == CUSTOM_TAG else self.form['category']
        
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
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal:
            return self._handle_modal_input(key)
        if self.is_editing:
            return self._handle_edit_input(key)
        return self._handle_nav_input(key)

    def _handle_modal_input(self, key):
        if not self.modal: return None
        res = self.modal.handle_input(key)
        if res == "YES":
            if self.modal_type == "DISCARD": 
                TUI.push_notification("Changes discarded", type="INFO")
                return "WELCOME"
            elif self.modal_type == "DRAFT":
                self.save_draft()
                self.modal = None
                return "WELCOME"
            elif self.modal_type == "DELETE_DRAFT":
                if self.active_draft_path and os.path.exists(self.active_draft_path):
                    os.remove(self.active_draft_path)
                    self._reset_form()
                    TUI.push_notification("Draft deleted successfully", type="INFO")
                self.modal = None
            elif self.modal_type == "DELETE_MODAL_DRAFT":
                path = os.path.join(DRAFTS_DIR, self.pending_delete[0])
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
                self.active_draft_path = os.path.join(DRAFTS_DIR, filename)
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

    def _handle_edit_input(self, key):
        field = self.fields[self.focus_idx]
        target = field['id']
        if field['id'] == 'category' and self.form['category'] == CUSTOM_TAG:
            target = CUSTOM_FIELD
        
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

    def _handle_nav_input(self, key):
        # Command Pattern Mapping
        nav_map = {
            Keys.UP: self._focus_prev, Keys.K: self._focus_prev,
            Keys.DOWN: self._focus_next, Keys.J: self._focus_next,
            Keys.LEFT: self._prev_option, Keys.H: self._prev_option,
            Keys.RIGHT: self._next_option, Keys.L: self._next_option,
            Keys.SPACE: self._toggle_check,
            ord('e'): self._start_editing, ord('E'): self._start_editing,
            ord('d'): self._trigger_draft_save, ord('D'): self._trigger_draft_save,
            ord('x'): self._trigger_draft_delete, ord('X'): self._trigger_draft_delete,
            Keys.Q: self._back_to_welcome, Keys.Q_UPPER: self._back_to_welcome,
            Keys.ENTER: self._trigger_summary,
            Keys.PGUP: lambda: self._scroll_preview(-5),
            Keys.PGDN: lambda: self._scroll_preview(5)
        }
        
        action = nav_map.get(key)
        return action() if action else None

    def _focus_prev(self):
        reachable = self._get_reachable_indices()
        try:
            curr_pos = reachable.index(self.focus_idx)
            self.focus_idx = reachable[(curr_pos - 1) % len(reachable)]
        except ValueError:
            self.focus_idx = 0
        self._ensure_focus_visible()
        return None

    def _focus_next(self):
        reachable = self._get_reachable_indices()
        try:
            curr_pos = reachable.index(self.focus_idx)
            self.focus_idx = reachable[(curr_pos + 1) % len(reachable)]
        except ValueError:
            self.focus_idx = 0
        self._ensure_focus_visible()
        return None

    def _prev_option(self):
        field = self.fields[self.focus_idx]
        if field['type'] == 'radio':
            opts = field['options']
            curr_idx = opts.index(self.form[field['id']])
            self.form[field['id']] = opts[(curr_idx - 1) % len(opts)]
        return None

    def _next_option(self):
        field = self.fields[self.focus_idx]
        if field['type'] == 'radio':
            opts = field['options']
            curr_idx = opts.index(self.form[field['id']])
            self.form[field['id']] = opts[(curr_idx + 1) % len(opts)]
        return None

    def _toggle_check(self):
        field = self.fields[self.focus_idx]
        if field['type'] == 'check': 
            self.form[field['id']] = not self.form[field['id']]
        return None

    def _start_editing(self):
        field = self.fields[self.focus_idx]
        if field['type'] == 'text':
            self.is_editing = True
            self.old_value = self.form[field['id']]
            self.text_cursor_pos = len(self.old_value)
        elif field['id'] == 'category' and self.form['category'] == CUSTOM_TAG:
            self.is_editing = True
            self.old_value = self.form[CUSTOM_FIELD]
            self.text_cursor_pos = len(self.old_value)
        return None

    def _trigger_draft_save(self):
        self.modal = ConfirmModal("SAVE DRAFT", "Do you want to save the current progress as a draft?")
        self.modal_type = "DRAFT"
        return None

    def _trigger_draft_delete(self):
        if self.active_draft_path:
            d_id = self.form['id'] or "unnamed"
            self.modal = ConfirmModal("DELETE ACTIVE DRAFT?", f"Are you sure you want to permanently delete '{d_id}' draft?")
            self.modal_type = "DELETE_DRAFT"
        return None

    def _back_to_welcome(self):
        is_dirty = any(self.form[k] for k in ['id', 'label', 'pkg_name', 'custom_category']) or self.form['stow_target'] != "~" or self.form['dependencies']
        if is_dirty:
            self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?")
            self.modal_type = "DISCARD"
            return None
        return "WELCOME"

    def _trigger_summary(self):
        field = self.fields[self.focus_idx]
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
            self.modal = WizardSummaryModal(self.form, custom_tag=CUSTOM_TAG, custom_field=CUSTOM_FIELD)
        return None

    def _scroll_preview(self, delta):
        self.preview_offset = max(0, self.preview_offset + delta)
        return None
