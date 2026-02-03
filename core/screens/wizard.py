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

class WizardScreen(Screen):
    """
    Interactive wizard for creating package modules.
    Provides a modular triple-box interface (Form, Help, Preview).
    """
    # UI Constants & Symbols
    CUSTOM_TAG = "Custom...✎"
    CUSTOM_FIELD = "custom_category"
    DRAFTS_DIR = "modules/.drafts"
    SYM_EDIT, SYM_RADIO, SYM_RADIO_OFF, SYM_CHECK, SYM_MULTI = "✎", "●", "○", "[■]", "↓"

    def __init__(self, modules: list[Module]):
        self.modules = modules
        self.categories = self._get_categories()
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
        
        # Data-driven field definitions
        self.fields = [
            {'id': 'id', 'label': 'ID', 'type': 'text', 'default': '', 'help': 'Unique identifier. Used for filename and dots/ folder.',
             'validate': lambda value: "ID required." if not value else ("Invalid format." if not re.match(r'^[a-zA-Z0-9_-]+$', value) else ("ID exists." if any(module.id == value for module in self.modules) else None))},
            {'id': 'label', 'label': 'Label', 'type': 'text', 'default': '', 'help': 'Display name in the selection menu.',
             'validate': lambda v: "Label required." if not v else None},
            {'id': 'manager', 'label': 'Package Manager', 'type': 'radio', 'options': self.managers, 'default': 'system', 'help': 'Select the package manager driver.'},
            {'id': 'package_name', 'label': 'Package Name', 'type': 'text', 'default': '', 'help': 'Exact package name for the manager. Defaults to ID.'},
            {'id': 'category', 'label': 'Category', 'type': 'radio', 'options': self.categories, 'default': self.categories[0] if self.categories else 'General', 'help': 'Group name for the package list.',
             'validate': lambda v: "Category name required." if (v == self.CUSTOM_TAG and not self.form[self.CUSTOM_FIELD]) else None},
            {'id': 'stow_target', 'label': 'Target Path', 'type': 'text', 'default': '~', 'help': 'Deployment destination (defaults to ~).'},
            {'id': 'dependencies', 'label': 'Dependencies', 'type': 'multi', 'default': [], 'help': 'Other modules required by this package.'},
            {'id': 'is_incomplete', 'label': 'Manual Mode', 'type': 'check', 'default': False, 'help': 'Mark as incomplete for custom Python logic.'},
            {'id': 'files', 'label': 'Files', 'type': 'placeholder', 'default': [], 'help': '[Future] file picker.'}
        ]
        
        self._reset_form()
        self._check_for_drafts()

    def _reset_form(self):
        """Resets the form to initial clean state based on field defaults."""
        self.form = {f['id']: f.get('default') for f in self.fields}
        self.form[self.CUSTOM_FIELD] = ''
        self.active_draft_path = None

    def _check_for_drafts(self):
        """Scans .drafts/ folder and opens selection modal if any exist."""
        if not os.path.exists(self.DRAFTS_DIR): return
        drafts = []
        for filename in os.listdir(self.DRAFTS_DIR):
            if filename.endswith(".json"):
                path = os.path.join(self.DRAFTS_DIR, filename)
                try:
                    with open(path, 'r') as draft_file: 
                        drafts.append((filename, json.load(draft_file), os.path.getmtime(path)))
                except: continue
        if drafts:
            self.modal = DraftSelectionModal(sorted(drafts, key=lambda x: x[2], reverse=True))
            self.modal_type = "LOAD_DRAFT"

    def save_draft(self):
        """Saves current form data to a JSON draft."""
        TUI._notifications = []
        if not os.path.exists(self.DRAFTS_DIR): os.makedirs(self.DRAFTS_DIR)
        name = self.form['id'] or f"draft_{int(time.time())}"
        path = os.path.join(self.DRAFTS_DIR, f"{name}.json")
        try:
            with open(path, 'w') as f: json.dump(self.form, f, indent=4)
            self.active_draft_path = path
            TUI.push_notification(f"Draft saved: {name}.json", type="INFO")
        except Exception as e: TUI.push_notification(f"Error saving draft: {str(e)}", type="ERROR")

    def _get_categories(self):
        """Extracts existing categories from loaded modules."""
        categories = sorted(list(set(module.category for module in self.modules if module.category and module.category != self.CUSTOM_TAG)))
        return categories + [self.CUSTOM_TAG]

    def _get_field_errors(self, field_id):
        """Returns error list for a field using data-driven validation."""
        field = next((field for field in self.fields if field['id'] == field_id), None)
        validation_function = field.get('validate') if field else None
        error = validation_function(self.form.get(field_id)) if validation_function else None
        return [error] if error else []

    def _ensure_focus_visible(self):
        """Adjusts form_offset to keep the focused field in view."""
        line_map, current_line, terminal_width = {}, 1, shutil.get_terminal_size().columns
        left_panel_width = int(terminal_width * 0.40)
        for index, field in enumerate(self.fields):
            line_map[index] = current_line
            if field['type'] == 'radio':
                radio_items = [f"● {option if option != self.CUSTOM_TAG or self.form[field['id']] != self.CUSTOM_TAG else f'Custom: {self.form[self.CUSTOM_FIELD]}'}" for option in field['options']]
                current_line += 4 if TUI.visible_len("   ".join(radio_items)) > left_panel_width - 6 else 3
            else: 
                current_line += 2
        
        focus_top = line_map[self.focus_idx]
        focus_bottom = (line_map[self.focus_idx + 1] - 1 if self.focus_idx + 1 < len(self.fields) else current_line - 1)
        available_lines = shutil.get_terminal_size().lines - 7
        
        if focus_top < self.form_offset + 1: 
            self.form_offset = max(0, focus_top - 1)
        elif focus_bottom >= self.form_offset + available_lines: 
            self.form_offset = focus_bottom - available_lines + 1

    def render(self):
        """Draws the triple-box layout (45/55 vertical split on right)."""
        terminal_width, terminal_height = shutil.get_terminal_size()
        
        # 1. Header & Footer
        header = f"{Style.header()}{' PACKAGE WIZARD '.center(terminal_width)}{Style.RESET}"
        pills = self._get_footer_pills()
        footer_lines = TUI.wrap_pills(pills, terminal_width - 4)
        available_height = max(10, terminal_height - 4 - len(footer_lines))
        left_width, right_width = int(terminal_width * 0.40), terminal_width - int(terminal_width * 0.40) - 1
        
        # 2. Content Sections
        form_lines = self._build_form_lines(left_width)
        content_height = available_height - 2
        scroll_params = self._get_scrollbar(len(form_lines), content_height, self.form_offset)
        
        # 3. Box Assembly
        left_box = TUI.create_container(form_lines[self.form_offset : self.form_offset + content_height], left_width, available_height, title="FORM", color="", is_focused=(not self.modal), **scroll_params)
        help_box, preview_box = self._build_right_panels(right_width, available_height)
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 4. Buffer Assembly
        buffer = [header, ""] + main_content + [""]
        for footer_line in footer_lines:
            footer_visible_len = TUI.visible_len(footer_line)
            left_padding = (terminal_width - footer_visible_len) // 2
            right_padding = terminal_width - footer_visible_len - left_padding
            buffer.append(f"{' ' * left_padding}{footer_line}{' ' * right_padding}")

        if self.modal:
            modal_lines, modal_y, modal_x = self.modal.render()
            for index, line in enumerate(modal_lines):
                if 0 <= modal_y + index < len(buffer): 
                    buffer[modal_y + index] = TUI.overlay(buffer[modal_y + index], line, modal_x)
        
        buffer = TUI.draw_notifications(buffer)
        final_output = "\n".join([TUI.visible_ljust(line, terminal_width) for line in buffer[:terminal_height]])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        if self.is_editing: 
            return [TUI.pill('ENTER', 'Finish', Theme.GREEN), TUI.pill('ESC', 'Cancel', Theme.RED)]
        
        current_field = self.fields[self.focus_idx]
        pills = [TUI.pill('h/j/k/l', 'Navigate', Theme.SKY), TUI.pill('PgUp/Dn', 'Scroll Script', Theme.BLUE)]
        
        if current_field['type'] == 'text': 
            pills.append(TUI.pill('E', 'Edit', Theme.BLUE))
        
        pills.extend([TUI.pill('D', 'Draft', Theme.PEACH)])
        
        if self.active_draft_path: 
            pills.append(TUI.pill('X', 'Delete Draft', Theme.RED))
        
        enter_label = "Select" if current_field['type'] == 'multi' else "Review & Save"
        pills.append(TUI.pill('ENTER', enter_label, Theme.GREEN))
        pills.append(TUI.pill('Q', 'Back', Theme.RED))
        
        return pills

    def _get_scrollbar(self, total, visible, offset):
        if total <= visible: return {'scroll_pos': None, 'scroll_size': None}
        sz = max(1, int(visible**2 / total))
        return {'scroll_pos': int((offset / (total - visible)) * (visible - sz)), 'scroll_size': sz}

    def _build_form_lines(self, width):
        lines = [""]
        for index, field in enumerate(self.fields):
            is_focused = (self.focus_idx == index and not self.modal)
            errors = self._get_field_errors(field['id'])
            has_errors = errors and (self.show_validation_errors or (field['id'] == 'id' and self.form['id']))
            style = Style.highlight() if is_focused else (Style.error() if has_errors else Style.normal())
            bold = Style.BOLD if is_focused else ""
            
            if field['type'] == 'radio': 
                lines.extend(self._render_radio_field(field, is_focused, style, bold, width))
            else: 
                lines.extend(self._render_standard_field(field, is_focused, style, bold, width))
        return lines

    def _render_standard_field(self, field, is_focused, style, bold, width):
        hint_key = {'text': 'e to edit', 'check': 'SPACE to toggle', 'multi': 'ENTER to select'}.get(field['type'], '')
        hint = f" {Style.muted()}{hint_key}{Style.RESET}" if is_focused and hint_key else ""
        label_text = f"{style}{bold}{field['label']}{Style.RESET}{hint}"
        field_value = self.form.get(field['id'], "")
        
        if field['type'] == 'text':
            if is_focused and self.is_editing:
                prefix, char, suffix = field_value[:self.text_cursor_pos], field_value[self.text_cursor_pos:self.text_cursor_pos+1] or " ", field_value[self.text_cursor_pos+1:]
                value_display = f"{prefix}{Style.INVERT}{char}{Style.RESET}{style}{bold}{suffix}"
            else: 
                value_display = field_value
            value_text = f"{style}{bold}{self.SYM_EDIT} [ {value_display}{Style.RESET}{style}{bold} ]{Style.RESET}"
        elif field['type'] == 'check': 
            value_text = f"{style}{bold}{'YES ' + self.SYM_CHECK if field_value else 'NO [ ]'}{Style.RESET}"
        elif field['type'] == 'multi': 
            value_text = f"{style}{bold}{self.SYM_MULTI} [ {len(field_value)} items ]{Style.RESET}"
        else: 
            value_text = f"{Style.muted()}[ N/A ]{Style.RESET}"
            
        return [f"  {TUI.split_line(label_text, value_text, width - 6)}", ""]

    def _render_radio_field(self, field, is_focused, style, bold, width):
        hint_text = "h/l to select" + (", e to edit" if field['id'] == 'category' and self.form['category'] == self.CUSTOM_TAG else "")
        lines, items = [f"  {style}{bold}{field['label']}{Style.RESET}{f' {Style.muted()}{hint_text}{Style.RESET}' if is_focused else ''}"], []
        for option in field['options']:
            is_selected = (self.form[field['id']] == option)
            mark = self.SYM_RADIO if is_selected else self.SYM_RADIO_OFF
            label = option
            
            if option == self.CUSTOM_TAG and is_selected:
                custom_value = self.form[self.CUSTOM_FIELD]
                if is_focused and self.is_editing:
                    prefix, char, suffix = custom_value[:self.text_cursor_pos], custom_value[self.text_cursor_pos:self.text_cursor_pos+1] or " ", custom_value[self.text_cursor_pos+1:]
                    label = f"Custom: '{prefix}{Style.INVERT}{char}{Style.RESET}{style}{bold}{suffix}' {self.SYM_EDIT}"
                else: 
                    label = f"Custom: '{custom_value}' {self.SYM_EDIT}" if custom_value else self.CUSTOM_TAG
            
            is_error = (option == self.CUSTOM_TAG and is_selected and not self.form[self.CUSTOM_FIELD])
            status_color = Style.error() if is_error else (Style.highlight() if is_selected and is_focused else (Style.success() if is_selected else Style.muted()))
            items.append(f"{status_color}{bold if is_selected and is_focused else ''}{mark} {label}{Style.RESET}")
            
        row_text = "   ".join(items)
        if TUI.visible_len(row_text) > width - 6:
            middle_index = len(items) // 2
            for part_line in ["   ".join(items[:middle_index]), "   ".join(items[middle_index:])]: 
                lines.append(f"{' ' * ((width - 6 - TUI.visible_len(part_line)) // 2 + 2)}{part_line}")
        else: 
            lines.append(f"{' ' * ((width - 6 - TUI.visible_len(row_text)) // 2 + 2)}{row_text}")
            
        return lines + [""]

    def _build_right_panels(self, width, height):
        field = self.fields[self.focus_idx]
        help_lines = [f"  {Style.normal()}{line}{Style.RESET}" for line in TUI.wrap_text(field['help'], width - 6)]
        is_category_empty = (field['id'] == 'category' and self.form['category'] == self.CUSTOM_TAG and not self.form[self.CUSTOM_FIELD])
        
        if self._get_field_errors(field['id']) and (self.show_validation_errors or self.is_editing or (field['id'] == 'id' and self.form['id']) or is_category_empty):
            for error in self._get_field_errors(field['id']): 
                help_lines.append(f"  {Style.error()}! {error}{Style.RESET}")
        
        help_height = min(len(help_lines) + 2, height // 3)
        preview_height = height - help_height
        
        preview_lines = [""]
        for line in self._generate_python().split("\n"):
            for wrapped_line in TUI.wrap_text(line, width - 6): 
                preview_lines.append(f"  {Style.normal()}{wrapped_line}{Style.RESET}")
        
        max_preview_offset = max(0, len(preview_lines) - (preview_height - 2))
        self.preview_offset = min(self.preview_offset, max_preview_offset)
        
        help_box = TUI.create_container(help_lines, width, help_height, title="HELP")
        preview_box = TUI.create_container(preview_lines[self.preview_offset : self.preview_offset + preview_height - 2], width, preview_height, title="PYTHON PREVIEW", color="", is_focused=False, **self._get_scrollbar(len(preview_lines), preview_height - 2, self.preview_offset))
        
        return help_box, preview_box

    def save_package(self):
        """Generates the .py module and creates the dots/ folder."""
        module_id = self.form['id']
        module_path, dots_path = os.path.join("modules", f"{module_id}.py"), os.path.join("dots", module_id)
        try:
            # 1. Generate Python Code
            code = "from modules.base import Module\n\n" + self._generate_python()

            # If Manual Mode is enabled, add the install method template
            if self.form['is_incomplete']: code += "\n\n    def install(self, override=None, callback=None, input_callback=None, password=None):\n        # TODO: Implement custom logic\n        return super().install(override, callback, input_callback, password)"
            
            # 2. Write Module File
            with open(module_path, "w") as f: f.write(code + "\n")
            
            # 3. Create Dots Directory
            if not os.path.exists(dots_path): os.makedirs(dots_path)
            
            # 4. Clean up draft if exists
            if self.active_draft_path and os.path.exists(self.active_draft_path): os.remove(self.active_draft_path)
            elif os.path.exists(os.path.join(self.DRAFTS_DIR, f"{module_id}.json")): os.remove(os.path.join(self.DRAFTS_DIR, f"{module_id}.json"))
            return True
        except Exception as e: TUI.push_notification(f"Save failed: {str(e)}", type="ERROR"); return False

    def _generate_python(self):
        """Generates the Python class code based on form data."""
        module_id, label = self.form['id'] or "my_package", self.form['label'] or "My Package"
        class_name = "".join([p.capitalize() for p in module_id.replace("-", "_").split("_")]) + "Module"
        category = self.form[self.CUSTOM_FIELD] if self.form['category'] == self.CUSTOM_TAG else self.form['category']
        code = f"class {class_name}(Module):\n    id = \"{module_id}\"\n    label = \"{label}\"\n    category = \"{category}\"\n    manager = \"{self.form['manager']}\""
        if self.form['package_name'] and self.form['package_name'] != module_id: code += f"\n    package_name = \"{self.form['package_name']}\""
        if self.form['stow_target'] != "~": code += f"\n    stow_target = \"{self.form['stow_target']}\""
        if self.form['dependencies']: code += f"\n    dependencies = {self.form['dependencies']}"
        return code

    def handle_input(self, key):
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal: return self._handle_modal_input(key)
        if self.is_editing: return self._handle_edit_input(key)
        return self._handle_nav_input(key)

    def _handle_modal_input(self, key):
        modal = self.modal
        if not modal: 
            return None
        result = modal.handle_input(key)
        
        if result == "YES":
            if self.modal_type == "DISCARD": 
                return "WELCOME"
            elif self.modal_type == "DRAFT": 
                self.save_draft()
                self.modal = None
                return "WELCOME"
            elif self.modal_type == "DELETE_DRAFT":
                if self.active_draft_path and os.path.exists(self.active_draft_path):
                    os.remove(self.active_draft_path)
                    self._reset_form()
                    TUI.push_notification("Draft deleted", type="INFO")
                self.modal = None
            elif self.modal_type == "DELETE_MODAL_DRAFT":
                path = os.path.join(self.DRAFTS_DIR, self.pending_delete[0])
                if os.path.exists(path): 
                    os.remove(path)
                    TUI.push_notification("Draft deleted", type="INFO")
                self.modal = None
                self._check_for_drafts()
                return None
        elif result == "CONFIRM":
            if isinstance(modal, DependencyModal): 
                self.form['dependencies'] = modal.get_selected()
            self.modal = None
        elif isinstance(result, tuple):
            if result[0] == "LOAD": 
                self.form.update(result[1][1])
                self.active_draft_path = os.path.join(self.DRAFTS_DIR, result[1][0])
                self.modal = None
            elif result[0] == "DELETE_REQ":
                self.pending_delete = result[1] # (filename, data, mtime)
                draft_id = result[1][1].get('id', 'unnamed')
                self.modal = ConfirmModal("DELETE DRAFT?", f"Are you sure you want to permanently delete '{draft_id}' draft?")
                self.modal_type = "DELETE_MODAL_DRAFT"
        elif result == "SAVE":
            if self.save_package(): 
                TUI.push_notification(f"Module '{self.form['id']}' created", type="INFO")
                return "RELOAD_AND_WELCOME"
            else: 
                self.modal = None
        elif result in ["FRESH", "NO", "CLOSE", "CANCEL"]:
            if self.modal_type == "DELETE_MODAL_DRAFT": 
                self._check_for_drafts()
            else: 
                self.modal = None
        return None

    def _handle_edit_input(self, key):
        f = self.fields[self.focus_idx]; t = f['id'] if f['id'] != 'category' or self.form['category'] != self.CUSTOM_TAG else self.CUSTOM_FIELD
        v = self.form[t]
        if key == Keys.ENTER: self.is_editing = False
        elif key == Keys.ESC: self.form[t] = self.old_value; self.is_editing = False
        elif key == Keys.BACKSPACE and self.text_cursor_pos > 0: self.form[t] = v[:self.text_cursor_pos-1] + v[self.text_cursor_pos:]; self.text_cursor_pos -= 1
        elif key == Keys.DEL and self.text_cursor_pos < len(v): self.form[t] = v[:self.text_cursor_pos] + v[self.text_cursor_pos+1:]
        elif key == Keys.LEFT: self.text_cursor_pos = max(0, self.text_cursor_pos - 1)
        elif key == Keys.RIGHT: self.text_cursor_pos = min(len(v), self.text_cursor_pos + 1)
        elif 32 <= key <= 126: self.form[t] = v[:self.text_cursor_pos] + chr(key) + v[self.text_cursor_pos:]; self.text_cursor_pos += 1
        return None

    def _handle_nav_input(self, key):
        navigation_map = {
            Keys.UP: lambda: self._move_focus(-1), 
            Keys.K: lambda: self._move_focus(-1),
            Keys.DOWN: lambda: self._move_focus(1), 
            Keys.J: lambda: self._move_focus(1),
            Keys.LEFT: lambda: self._cycle_option(-1), 
            Keys.H: lambda: self._cycle_option(-1),
            Keys.RIGHT: lambda: self._cycle_option(1), 
            Keys.L: lambda: self._cycle_option(1),
            Keys.SPACE: self._toggle_check, 
            ord('e'): self._start_editing, 
            ord('E'): self._start_editing,
            ord('d'): lambda: self._set_modal(ConfirmModal("SAVE DRAFT", "Save progress?"), "DRAFT"),
            ord('x'): self._draft_del_req, 
            Keys.ENTER: self._trigger_enter, 
            Keys.Q: self._back_req,
            Keys.PGUP: lambda: self._scroll_preview(-5), 
            Keys.PGDN: lambda: self._scroll_preview(5)
        }
        action = navigation_map.get(key)
        return action() if action else None

    def _move_focus(self, direction): 
        self.focus_idx = (self.focus_idx + direction) % len(self.fields)
        self._ensure_focus_visible()

    def _cycle_option(self, direction):
        field = self.fields[self.focus_idx]
        if field['type'] == 'radio': 
            options = field['options']
            current_index = options.index(self.form[field['id']])
            self.form[field['id']] = options[(current_index + direction) % len(options)]
    def _toggle_check(self):
        f = self.fields[self.focus_idx]
        if f['type'] == 'check': self.form[f['id']] = not self.form[f['id']]
    def _start_editing(self):
        f = self.fields[self.focus_idx]
        if f['type'] == 'text' or (f['id'] == 'category' and self.form['category'] == self.CUSTOM_TAG):
            self.is_editing = True; t = f['id'] if f['type'] == 'text' else self.CUSTOM_FIELD
            self.old_value, self.text_cursor_pos = self.form[t], len(self.form[t])
    def _set_modal(self, m, t): self.modal, self.modal_type = m, t
    def _draft_del_req(self):
        if self.active_draft_path: self._set_modal(ConfirmModal("DELETE DRAFT?", f"Delete '{self.form['id'] or 'unnamed'}'?"), "DELETE_DRAFT")
    def _back_req(self):
        if any(self.form[k] for k in ['id', 'label', 'package_name', 'custom_category']) or self.form['stow_target'] != "~":
            self._set_modal(ConfirmModal("DISCARD?", "Discard all changes?"), "DISCARD")
        else: return "WELCOME"
    def _trigger_enter(self):
        field = self.fields[self.focus_idx]
        if field['type'] == 'multi': 
            self.modal = DependencyModal(self.modules, self.form['dependencies'])
        else:
            all_field_ids = [field_item['id'] for field_item in self.fields]
            form_errors = [error for field_id in all_field_ids for error in self._get_field_errors(field_id)]
            
            if form_errors: 
                self.show_validation_errors = True
                TUI.push_notification("Fix form errors", type="ERROR")
            else: 
                self.modal = WizardSummaryModal(self.form, custom_tag=self.CUSTOM_TAG, custom_field=self.CUSTOM_FIELD)

    def _scroll_preview(self, direction): 
        self.preview_offset = max(0, self.preview_offset + direction)
