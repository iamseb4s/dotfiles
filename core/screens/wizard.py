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
             'validate': lambda v: "ID required." if not v else ("Invalid format." if not re.match(r'^[a-zA-Z0-9_-]+$', v) else ("ID exists." if any(m.id == v for m in self.modules) else None))},
            {'id': 'label', 'label': 'Label', 'type': 'text', 'default': '', 'help': 'Display name in the selection menu.',
             'validate': lambda v: "Label required." if not v else None},
            {'id': 'manager', 'label': 'Package Manager', 'type': 'radio', 'options': self.managers, 'default': 'system', 'help': 'Select the package manager driver.'},
            {'id': 'pkg_name', 'label': 'Package Name', 'type': 'text', 'default': '', 'help': 'Exact package name for the manager. Defaults to ID.'},
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
        for f in os.listdir(self.DRAFTS_DIR):
            if f.endswith(".json"):
                path = os.path.join(self.DRAFTS_DIR, f)
                try:
                    with open(path, 'r') as j: drafts.append((f, json.load(j), os.path.getmtime(path)))
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
        cats = sorted(list(set(m.category for m in self.modules if m.category and m.category != self.CUSTOM_TAG)))
        return cats + [self.CUSTOM_TAG]

    def _get_field_errors(self, field_id):
        """Returns error list for a field using data-driven validation."""
        f = next((f for f in self.fields if f['id'] == field_id), None)
        v_fn = f.get('validate') if f else None
        err = v_fn(self.form.get(field_id)) if v_fn else None
        return [err] if err else []

    def _ensure_focus_visible(self):
        """Adjusts form_offset to keep the focused field in view."""
        lmap, curr, tw = {}, 1, shutil.get_terminal_size().columns
        lw = int(tw * 0.40)
        for i, f in enumerate(self.fields):
            lmap[i] = curr
            if f['type'] == 'radio':
                its = [f"● {o if o != self.CUSTOM_TAG or self.form[f['id']] != self.CUSTOM_TAG else f'Custom: {self.form[self.CUSTOM_FIELD]}'}" for o in f['options']]
                curr += 4 if TUI.visible_len("   ".join(its)) > lw - 6 else 3
            else: curr += 2
        ft, fb = lmap[self.focus_idx], (lmap[self.focus_idx + 1] - 1 if self.focus_idx + 1 < len(self.fields) else curr - 1)
        avail = shutil.get_terminal_size().lines - 7
        if ft < self.form_offset + 1: self.form_offset = max(0, ft - 1)
        elif fb >= self.form_offset + avail: self.form_offset = fb - avail + 1

    def render(self):
        """Draws the triple-box layout (45/55 vertical split on right)."""
        tw, th = shutil.get_terminal_size()
        
        # 1. Header & Footer
        header = f"{Style.mauve(bg=True)}{Style.crust()}{' PACKAGE WIZARD '.center(tw)}{Style.RESET}"
        pills = self._get_footer_pills(); footer_lines = TUI.wrap_pills(pills, tw - 4)
        avail_h = max(10, th - 4 - len(footer_lines))
        lw, rw = int(tw * 0.40), tw - int(tw * 0.40) - 1
        
        
        # 2. Content Sections
        form_lines = self._build_form_lines(lw); content_h = avail_h - 2
        
        scroll = self._get_scrollbar(len(form_lines), content_h, self.form_offset)
        
        # 3. Box Assembly
        left_box = TUI.create_container(form_lines[self.form_offset : self.form_offset + content_h], lw, avail_h, title="FORM", color="", is_focused=(not self.modal), **scroll)
        help_box, preview_box = self._build_right_panels(rw, avail_h)
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 4. Buffer Assembly
        buffer = [header, ""] + main_content + [""]
        for f_line in footer_lines:
            fv = TUI.visible_len(f_line); lp = (tw - fv) // 2; rp = tw - fv - lp
            buffer.append(f"{' ' * lp}{f_line}{' ' * rp}")

        if self.modal:
            ml, my, mx = self.modal.render()
            for i, line in enumerate(ml):
                if 0 <= my + i < len(buffer): buffer[my + i] = TUI.overlay(buffer[my + i], line, mx)
        
        buffer = TUI.draw_notifications(buffer)
        sys.stdout.write("\033[H" + "\n".join([TUI.visible_ljust(l, tw) for l in buffer[:th]]) + "\033[J")
        sys.stdout.flush()

    def _get_footer_pills(self):
        if self.is_editing: return [TUI.pill('ENTER', 'Finish', Theme.GREEN), TUI.pill('ESC', 'Cancel', Theme.RED)]
        f = self.fields[self.focus_idx]
        res = [TUI.pill('h/j/k/l', 'Navigate', Theme.SKY), TUI.pill('PgUp/Dn', 'Scroll Script', Theme.BLUE)]
        if f['type'] == 'text': res.append(TUI.pill('E', 'Edit', Theme.BLUE))
        res.extend([TUI.pill('D', 'Draft', Theme.PEACH)])
        if self.active_draft_path: res.append(TUI.pill('X', 'Delete Draft', Theme.RED))
        res.append(TUI.pill('ENTER', "Select" if f['type'] == 'multi' else "Review & Save", Theme.GREEN))
        res.append(TUI.pill('Q', 'Back', Theme.RED))
        return res

    def _get_scrollbar(self, total, visible, offset):
        if total <= visible: return {'scroll_pos': None, 'scroll_size': None}
        sz = max(1, int(visible**2 / total))
        return {'scroll_pos': int((offset / (total - visible)) * (visible - sz)), 'scroll_size': sz}

    def _build_form_lines(self, width):
        lines = [""]
        for i, field in enumerate(self.fields):
            is_f = (self.focus_idx == i and not self.modal)
            errs = self._get_field_errors(field['id'])
            has_e = errs and (self.show_validation_errors or (field['id'] == 'id' and self.form['id']))
            style = Style.highlight() if is_f else (Style.red() if has_e else Style.normal())
            bold = Style.BOLD if is_f else ""
            if field['type'] == 'radio': lines.extend(self._render_radio_field(field, is_f, style, bold, width))
            else: lines.extend(self._render_standard_field(field, is_f, style, bold, width))
        return lines

    def _render_standard_field(self, field, is_f, style, bold, width):
        h = {'text': 'e to edit', 'check': 'SPACE to toggle', 'multi': 'ENTER to select'}.get(field['type'], '')
        hint = f" {Style.muted()}{h}{Style.RESET}" if is_f and h else ""
        label = f"{style}{bold}{field['label']}{Style.RESET}{hint}"
        val = self.form.get(field['id'], "")
        if field['type'] == 'text':
            if is_f and self.is_editing:
                p, c, st = val[:self.text_cursor_pos], val[self.text_cursor_pos:self.text_cursor_pos+1] or " ", val[self.text_cursor_pos+1:]
                vd = f"{p}{Style.INVERT}{c}{Style.RESET}{style}{bold}{st}"
            else: vd = val
            value = f"{style}{bold}{self.SYM_EDIT} [ {vd}{Style.RESET}{style}{bold} ]{Style.RESET}"
        elif field['type'] == 'check': value = f"{style}{bold}{'YES ' + self.SYM_CHECK if val else 'NO [ ]'}{Style.RESET}"
        elif field['type'] == 'multi': value = f"{style}{bold}{self.SYM_MULTI} [ {len(val)} items ]{Style.RESET}"
        else: value = f"{Style.muted()}[ N/A ]{Style.RESET}"
        return [f"  {TUI.split_line(label, value, width - 6)}", ""]

    def _render_radio_field(self, field, is_f, style, bold, width):
        h_txt = "h/l to select" + (", e to edit" if field['id'] == 'category' and self.form['category'] == self.CUSTOM_TAG else "")
        lines, its = [f"  {style}{bold}{field['label']}{Style.RESET}{f' {Style.muted()}{h_txt}{Style.RESET}' if is_f else ''}"], []
        for opt in field['options']:
            sel = (self.form[field['id']] == opt); mark = self.SYM_RADIO if sel else self.SYM_RADIO_OFF; label = opt
            if opt == self.CUSTOM_TAG and sel:
                cv = self.form[self.CUSTOM_FIELD]
                if is_f and self.is_editing:
                    p, c, st = cv[:self.text_cursor_pos], cv[self.text_cursor_pos:self.text_cursor_pos+1] or " ", cv[self.text_cursor_pos+1:]
                    label = f"Custom: '{p}{Style.INVERT}{c}{Style.RESET}{style}{bold}{st}' {self.SYM_EDIT}"
                else: label = f"Custom: '{cv}' {self.SYM_EDIT}" if cv else self.CUSTOM_TAG
            is_err = (opt == self.CUSTOM_TAG and sel and not self.form[self.CUSTOM_FIELD])
            c = Style.red() if is_err else (Style.highlight() if sel and is_f else (Style.green() if sel else Style.muted()))
            its.append(f"{c}{bold if sel and is_f else ''}{mark} {label}{Style.RESET}")
        row = "   ".join(its)
        if TUI.visible_len(row) > width - 6:
            mid = len(its) // 2
            for l in ["   ".join(its[:mid]), "   ".join(its[mid:])]: lines.append(f"{' ' * ((width - 6 - TUI.visible_len(l)) // 2 + 2)}{l}")
        else: lines.append(f"{' ' * ((width - 6 - TUI.visible_len(row)) // 2 + 2)}{row}")
        return lines + [""]

    def _build_right_panels(self, width, height):
        field = self.fields[self.focus_idx]
        help_l = [f"  {Style.normal()}{l}{Style.RESET}" for l in TUI.wrap_text(field['help'], width - 6)]
        is_c_empty = (field['id'] == 'category' and self.form['category'] == self.CUSTOM_TAG and not self.form[self.CUSTOM_FIELD])
        if self._get_field_errors(field['id']) and (self.show_validation_errors or self.is_editing or (field['id'] == 'id' and self.form['id']) or is_c_empty):
            for e in self._get_field_errors(field['id']): help_l.append(f"  {Style.red()}! {e}{Style.RESET}")
        hh = min(len(help_l) + 2, height // 3); ph = height - hh
        prev_l = [""]
        for line in self._generate_python().split("\n"):
            for wl in TUI.wrap_text(line, width - 6): prev_l.append(f"  {Style.normal()}{wl}{Style.RESET}")
        max_off = max(0, len(prev_l) - (ph - 2)); self.preview_offset = min(self.preview_offset, max_off)
        return TUI.create_container(help_l, width, hh, title="HELP"), \
               TUI.create_container(prev_l[self.preview_offset : self.preview_offset + ph - 2], width, ph, title="PYTHON PREVIEW", color="", is_focused=False, **self._get_scrollbar(len(prev_l), ph - 2, self.preview_offset))

    def save_package(self):
        """Generates the .py module and creates the dots/ folder."""
        fid = self.form['id']
        module_path, dots_path = os.path.join("modules", f"{fid}.py"), os.path.join("dots", fid)
        try:
            # 1. Generate Python Code
            code = "from modules.base import Module\n\n" + self._generate_python()

            # If Manual Mode is enabled, add the install method template
            if self.form['is_incomplete']: code += "\n\n    def install(self):\n        # TODO: Implement custom logic\n        super().install()"
            
            # 2. Write Module File
            with open(module_path, "w") as f: f.write(code + "\n")
            
            # 3. Create Dots Directory
            if not os.path.exists(dots_path): os.makedirs(dots_path)
            
            # 4. Clean up draft if exists
            if self.active_draft_path and os.path.exists(self.active_draft_path): os.remove(self.active_draft_path)
            elif os.path.exists(os.path.join(self.DRAFTS_DIR, f"{fid}.json")): os.remove(os.path.join(self.DRAFTS_DIR, f"{fid}.json"))
            return True
        except Exception as e: TUI.push_notification(f"Save failed: {str(e)}", type="ERROR"); return False

    def _generate_python(self):
        """Generates the Python class code based on form data."""
        fid, lbl = self.form['id'] or "my_package", self.form['label'] or "My Package"
        cls_n = "".join([p.capitalize() for p in fid.replace("-", "_").split("_")]) + "Module"
        cat = self.form[self.CUSTOM_FIELD] if self.form['category'] == self.CUSTOM_TAG else self.form['category']
        code = f"class {cls_n}(Module):\n    id = \"{fid}\"\n    label = \"{lbl}\"\n    category = \"{cat}\"\n    manager = \"{self.form['manager']}\""
        if self.form['pkg_name'] and self.form['pkg_name'] != fid: code += f"\n    package_name = \"{self.form['pkg_name']}\""
        if self.form['stow_target'] != "~": code += f"\n    stow_target = \"{self.form['stow_target']}\""
        if self.form['dependencies']: code += f"\n    dependencies = {self.form['dependencies']}"
        return code

    def handle_input(self, key):
        """Processes input by dispatching to specialized handlers based on state."""
        if self.modal: return self._handle_modal_input(key)
        if self.is_editing: return self._handle_edit_input(key)
        return self._handle_nav_input(key)

    def _handle_modal_input(self, key):
        m = self.modal
        if not m: return None
        res = m.handle_input(key)
        if res == "YES":
            if self.modal_type == "DISCARD": return "WELCOME"
            elif self.modal_type == "DRAFT": self.save_draft(); self.modal = None; return "WELCOME"
            elif self.modal_type == "DELETE_DRAFT":
                if self.active_draft_path and os.path.exists(self.active_draft_path):
                    os.remove(self.active_draft_path); self._reset_form(); TUI.push_notification("Draft deleted", type="INFO")
                self.modal = None
            elif self.modal_type == "DELETE_MODAL_DRAFT":
                path = os.path.join(self.DRAFTS_DIR, self.pending_delete[0])
                if os.path.exists(path): os.remove(path); TUI.push_notification("Draft deleted", type="INFO")
                self.modal = None; self._check_for_drafts(); return None
        elif res == "CONFIRM":
            if isinstance(m, DependencyModal): self.form['dependencies'] = m.get_selected()
            self.modal = None
        elif isinstance(res, tuple):
            if res[0] == "LOAD": self.form.update(res[1][1]); self.active_draft_path = os.path.join(self.DRAFTS_DIR, res[1][0]); self.modal = None
            elif res[0] == "DELETE_REQ":
                self.pending_delete = res[1] # (filename, data, mtime)
                self.modal = ConfirmModal("DELETE DRAFT?", f"Are you sure you want to permanently delete '{res[1][1].get('id', 'unnamed')}' draft?")
                self.modal_type = "DELETE_MODAL_DRAFT"
        elif res == "SAVE":
            if self.save_package(): TUI.push_notification(f"Module '{self.form['id']}' created", type="INFO"); return "RELOAD_AND_WELCOME"
            else: self.modal = None
        elif res in ["FRESH", "NO", "CLOSE", "CANCEL"]:
            if self.modal_type == "DELETE_MODAL_DRAFT": self._check_for_drafts()
            else: self.modal = None
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
        nav = {
            Keys.UP: lambda: self._move_focus(-1), Keys.K: lambda: self._move_focus(-1),
            Keys.DOWN: lambda: self._move_focus(1), Keys.J: lambda: self._move_focus(1),
            Keys.LEFT: lambda: self._cycle_opt(-1), Keys.H: lambda: self._cycle_opt(-1),
            Keys.RIGHT: lambda: self._cycle_opt(1), Keys.L: lambda: self._cycle_opt(1),
            Keys.SPACE: self._toggle_check, ord('e'): self._start_editing, ord('E'): self._start_editing,
            ord('d'): lambda: self._set_modal(ConfirmModal("SAVE DRAFT", "Save progress?"), "DRAFT"),
            ord('x'): self._draft_del_req, Keys.ENTER: self._trigger_enter, Keys.Q: self._back_req,
            Keys.PGUP: lambda: self._scroll_prev(-5), Keys.PGDN: lambda: self._scroll_prev(5)
        }
        action = nav.get(key)
        return action() if action else None

    def _move_focus(self, d): self.focus_idx = (self.focus_idx + d) % len(self.fields); self._ensure_focus_visible()
    def _cycle_opt(self, d):
        f = self.fields[self.focus_idx]
        if f['type'] == 'radio': opts = f['options']; curr = opts.index(self.form[f['id']]); self.form[f['id']] = opts[(curr + d) % len(opts)]
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
        if any(self.form[k] for k in ['id', 'label', 'pkg_name', 'custom_category']) or self.form['stow_target'] != "~":
            self._set_modal(ConfirmModal("DISCARD?", "Discard all changes?"), "DISCARD")
        else: return "WELCOME"
    def _trigger_enter(self):
        f = self.fields[self.focus_idx]
        if f['type'] == 'multi': self.modal = DependencyModal(self.modules, self.form['dependencies'])
        else:
            errs = [e for fid in [f['id'] for f in self.fields] for e in self._get_field_errors(fid)]
            if errs: self.show_validation_errors = True; TUI.push_notification("Fix form errors", type="ERROR")
            else: self.modal = WizardSummaryModal(self.form, custom_tag=self.CUSTOM_TAG, custom_field=self.CUSTOM_FIELD)
    def _scroll_prev(self, d): self.preview_offset = max(0, self.preview_offset + d)
