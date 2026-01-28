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
        self.max_visible_rows = 10 # Adjusted in render

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        width = 60
        # Dynamic height calculation
        content_len = len(self.modules)
        # Margin: 3 lines top + 3 lines bottom = 6.
        available_content_height = term_height - 11
        
        self.max_visible_rows = min(content_len, available_content_height)
        self.max_visible_rows = max(3, self.max_visible_rows)
        
        inner_lines = [""] # Top spacer
        
        for i in range(self.max_visible_rows):
            idx = self.scroll_offset + i
            if idx < content_len:
                mod = self.modules[idx]
                is_focused = (self.focus_idx == idx)
                is_selected = (mod.id in self.selected)
                
                mark = "[■]" if is_selected else "[ ]"
                label = f"{mod.label} ({mod.id})"
                
                # Colors
                color = Style.mauve() + Style.BOLD if is_focused else ""
                sel_color = Style.green() if is_selected else ""
                
                inner_lines.append(f"  {color}{mark} {sel_color if not is_focused else ''}{label}{Style.RESET}")

        inner_lines.append("")
        hint = f"{Style.DIM}SPACE to toggle, ENTER to confirm{Style.RESET}"
        inner_lines.append(f"{' ' * ((width - 2 - TUI.visible_len(hint)) // 2)}{hint}")
        
        # Scroll calculation
        scroll_pos, scroll_size = None, None
        if content_len > self.max_visible_rows:
            thumb_size = max(1, int(self.max_visible_rows**2 / content_len))
            max_off = content_len - self.max_visible_rows
            prog = self.scroll_offset / max_off if max_off > 0 else 0
            scroll_pos = 1 + int(prog * (self.max_visible_rows - thumb_size))
            scroll_size = thumb_size

        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="SELECT DEPENDENCIES", is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = max(0, self.focus_idx - 1)
            if self.focus_idx < self.scroll_offset:
                self.scroll_offset = self.focus_idx
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = min(len(self.modules) - 1, self.focus_idx + 1)
            if self.focus_idx >= self.scroll_offset + self.max_visible_rows:
                self.scroll_offset = self.focus_idx - self.max_visible_rows + 1
        elif key == Keys.SPACE:
            mid = self.modules[self.focus_idx].id
            if mid in self.selected: self.selected.remove(mid)
            else: self.selected.add(mid)
        elif key == Keys.ENTER:
            return "CONFIRM"
        elif key == Keys.ESC:
            return "CANCEL"
        elif key in [Keys.Q, Keys.Q_UPPER]:
            return "CANCEL"
        return None

    def get_selected(self):
        return list(self.selected)

class WizardSummaryModal:
    """Final vertical summary modal before saving."""
    def __init__(self, form_data):
        self.form = form_data
        self.focus_idx = 0 # 0: SAVE, 1: CANCEL
        self.scroll_offset = 0
        self.content_lines = self._build_content()

    def _build_content(self):
        lines = []
        lines.append(f"{Style.BOLD}ID:{Style.RESET} {self.form['id']}")
        lines.append(f"{Style.BOLD}Label:{Style.RESET} {self.form['label']}")
        lines.append(f"{Style.BOLD}Manager:{Style.RESET} {self.form['manager']}")
        cat = self.form['custom_category'] if self.form['category'] == "Custom..." else self.form['category']
        lines.append(f"{Style.BOLD}Category:{Style.RESET} {cat}")
        lines.append(f"{Style.BOLD}Target:{Style.RESET} {self.form['stow_target']}")
        lines.append(f"{Style.BOLD}Manual Mode:{Style.RESET} {'Yes' if self.form['is_incomplete'] else 'No'}")
        
        lines.append("")
        lines.append(f"{Style.BOLD}Dependencies:{Style.RESET}")
        if not self.form['dependencies']:
            lines.append(f"  {Style.DIM}None{Style.RESET}")
        else:
            for dep in sorted(self.form['dependencies']):
                lines.append(f"  - {dep}")
        return lines

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 64
        
        # Max rows based on terminal height
        available_content_height = term_height - 11
        max_rows = min(len(self.content_lines), available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""] # Top spacer
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(self.content_lines):
                inner_lines.append(f"  {self.content_lines[idx]}")
            
        inner_lines.append("")
        
        # Buttons
        purple_bg = Style.mauve(bg=True)
        btn_s = "  SAVE  "
        btn_c = "  CANCEL  "
        
        if self.focus_idx == 0:
            s_styled = f"{purple_bg}{Style.crust()}{btn_s}{Style.RESET}"
            c_styled = f"[{btn_c.strip().center(len(btn_c)-2)}]"
        else:
            s_styled = f"[{btn_s.strip().center(len(btn_s)-2)}]"
            c_styled = f"{purple_bg}{Style.crust()}{btn_c}{Style.RESET}"
        
        btn_row = f"{s_styled}     {c_styled}"
        pad = (width - 2 - TUI.visible_len(btn_row)) // 2
        inner_lines.append(f"{' ' * pad}{btn_row}")


        # Scroll
        scroll_pos, scroll_size = None, None
        if len(self.content_lines) > max_rows:
            thumb_size = max(1, int(max_rows**2 / len(self.content_lines)))
            max_off = len(self.content_lines) - max_rows
            prog = self.scroll_offset / max_off if max_off > 0 else 0
            scroll_pos = 1 + int(prog * (max_rows - thumb_size))
            scroll_size = thumb_size

        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="FINAL SUMMARY", is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        if key in [Keys.UP, Keys.K]:
            self.scroll_offset = max(0, self.scroll_offset - 1)
        elif key in [Keys.DOWN, Keys.J]:
            max_off = len(self.content_lines) - max(5, shutil.get_terminal_size().lines - 12)
            if self.scroll_offset < max_off:
                self.scroll_offset += 1
        elif key in [Keys.LEFT, Keys.H, Keys.RIGHT, Keys.L, Keys.TAB]:
            self.focus_idx = 1 if self.focus_idx == 0 else 0
        elif key == Keys.ENTER:
            return "SAVE" if self.focus_idx == 0 else "CANCEL"
        elif key == Keys.ESC:
            if self.focus_idx != 1:
                self.focus_idx = 1 # Focus CANCEL
            else:
                return "CANCEL"
        elif key in [Keys.Q, Keys.Q_UPPER]:
            return "CANCEL"
        return None

class DraftSelectionModal:
    """Modal to select an existing draft or start fresh."""
    def __init__(self, drafts, delete_callback=None):
        self.drafts = drafts # List of (filename, data, mtime)
        self.focus_idx = 0
        self.scroll_offset = 0
        self.delete_callback = delete_callback

    def render(self):
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        width = 60
        
        # Max rows based on terminal height
        available_content_height = term_height - 11
        max_rows = min(len(self.drafts) + 1, available_content_height)
        max_rows = max(3, max_rows)
        
        inner_lines = [""] # Top spacer
        
        # Options: Drafts + "Start Fresh"
        options = self.drafts + [("fresh", None, None)]
        
        for i in range(max_rows):
            idx = self.scroll_offset + i
            if idx < len(options):
                fname, data, mtime = options[idx]
                is_focused = (self.focus_idx == idx)
                color = Style.mauve() + Style.BOLD if is_focused else ""
                
                if fname == "fresh":
                    label = " [ Start Fresh / New ] "
                else:
                    d_id = data.get('id', 'unnamed')
                    d_time = datetime.fromtimestamp(mtime).strftime("%d %b %H:%M")
                    label = f" {d_id} ({d_time})"
                
                inner_lines.append(f"  {color}{label}{Style.RESET}")

        inner_lines.append("")
        hint = f"{Style.DIM}ENTER to select, X to delete{Style.RESET}"
        inner_lines.append(f"{' ' * ((width - 2 - TUI.visible_len(hint)) // 2)}{hint}")
        
        # Scroll calculation
        scroll_pos, scroll_size = None, None
        if len(options) > max_rows:
            thumb_size = max(1, int(max_rows**2 / len(options)))
            max_off = len(options) - max_rows
            prog = self.scroll_offset / max_off if max_off > 0 else 0
            scroll_pos = 1 + int(prog * (max_rows - thumb_size))
            scroll_size = thumb_size

        height = len(inner_lines) + 2
        lines = TUI.create_container(inner_lines, width, height, title="RESUME DRAFT?", is_focused=True, scroll_pos=scroll_pos, scroll_size=scroll_size)
        
        return lines, (term_height - height) // 2, (term_width - width) // 2

    def handle_input(self, key):
        options_len = len(self.drafts) + 1
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = max(0, self.focus_idx - 1)
            if self.focus_idx < self.scroll_offset:
                self.scroll_offset = self.focus_idx
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = min(options_len - 1, self.focus_idx + 1)
            term_height = shutil.get_terminal_size().lines
            max_rows = min(options_len, term_height - 11)
            max_rows = max(3, max_rows)
            if self.focus_idx >= self.scroll_offset + max_rows:
                self.scroll_offset = self.focus_idx - max_rows + 1
        elif key == Keys.ENTER:
            if self.focus_idx < len(self.drafts):
                return ("LOAD", self.drafts[self.focus_idx])
            return "FRESH"
        elif key in [ord('x'), ord('X'), Keys.DEL]:
            if self.focus_idx < len(self.drafts):
                return ("DELETE_REQ", self.drafts[self.focus_idx])
        elif key == Keys.ESC:
            if self.focus_idx != options_len - 1:
                self.focus_idx = options_len - 1 # Focus "Start Fresh"
            else:
                return "FRESH"
        elif key in [Keys.Q, Keys.Q_UPPER]:
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
            {'id': 'manager', 'label': 'Manager', 'type': 'select', 'options': self.managers, 'help': 'Package manager driver (system, cargo, brew, etc.).'},
            {'id': 'pkg_name', 'label': 'Pkg Name', 'type': 'text', 'help': 'Exact package name for the manager. Defaults to ID.'},
            {'id': 'category', 'label': 'Category', 'type': 'select', 'options': self.categories, 'help': 'Group name for the package list. Use existing or Custom.'},
            {'id': 'stow_target', 'label': 'Stow Target', 'type': 'text', 'help': 'Deployment destination (defaults to ~).'},
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
            'category': self.categories[0] if hasattr(self, 'categories') and self.categories else 'General',
            'custom_category': '',
            'stow_target': '~',
            'dependencies': [],
            'is_incomplete': False
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
        cats = sorted(list(set(m.category for m in self.modules)))
        if "Custom..." not in cats:
            cats.append("Custom...")
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
            if val == "Custom..." and not self.form['custom_category']:
                errors.append("Custom category name cannot be empty.")

        return errors

    def _ensure_focus_visible(self):
        """Adjusts form_offset to keep the focused field in view."""
        field_top = 1 + (self.focus_idx * 3)
        field_bottom = field_top + 2

        if self.focus_idx == 0:
            self.form_offset = 0
            return

        term_height = shutil.get_terminal_size().lines
        available_height = max(10, term_height - 5)
        content_height = available_height - 2
        
        if field_top - 1 < self.form_offset:
            self.form_offset = max(0, field_top - 1)
            
        # Scroll down if field bottom (spacer) is hidden
        if field_bottom >= self.form_offset + content_height:
            self.form_offset = field_bottom - content_height + 1
            
        # Safety bound
        self.form_offset = max(0, self.form_offset)

    def render(self):
        """Draws the triple-box layout (40/60 vertical split on right)."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Header
        title_text = " PACKAGE WIZARD "
        bg_purple = Style.mauve(bg=True)
        padding = (term_width - len(title_text)) // 2
        header_bar = f"{bg_purple}{Style.crust()}{' '*padding}{title_text}{' '*(term_width-padding-len(title_text))}{Style.RESET}"
        
        # 2. Layout Metrics
        # Overhead: Header(1), Spacer(1), Spacer(1), Footer(1)
        available_height = term_height - 5
        available_height = max(10, available_height)
        
        safe_width = term_width - 2
        left_width = int(safe_width * 0.40)
        right_width = safe_width - left_width - 1
        
        # 3. Build Right Content (Help & Preview)
        help_content = []
        
        if self.focus_idx < len(self.fields):
            field = self.fields[self.focus_idx]
            help_text = field['help']
            val = self.form.get(field['id'], "")
            
            wrapped_help = TUI.wrap_text(help_text, right_width - 4)
            for l in wrapped_help:
                help_content.append(f"  {l}")
            
            # Show errors in HELP box
            f_errors = self._get_field_errors(field['id'])
            for err in f_errors:
                is_empty_err = "empty" in err.lower()
                # Special Case: Custom Category error always shows if selected
                is_custom_cat_empty = field['id'] == 'category' and val == "Custom..." and not self.form['custom_category']
                
                should_show = self.show_validation_errors or not is_empty_err or self.is_editing or is_custom_cat_empty
                if should_show:
                    help_content.append(f"  {Style.red()}ERROR: {err}{Style.RESET}")
        
        # Show status message if recent (AT THE BOTTOM)
        if self.status_msg and time.time() - self.status_time < 3:
            if help_content: help_content.append("")
            help_content.append(f"  {self.status_msg}")
        
        # Help height is dynamic
        help_height = len(help_content) + 2
        if help_height < 3: help_height = 3
        
        preview_height = available_height - help_height
        
        # Python Preview Section
        preview_raw_lines = [""]
        preview_code = self._generate_python()
        for line in preview_code.split("\n"):
            for wl in TUI.wrap_text(line, right_width - 4):
                preview_raw_lines.append(f"  {wl}")
        
        # Apply Scroll to Preview
        max_preview_off = max(0, len(preview_raw_lines) - (preview_height - 2))
        if self.preview_offset > max_preview_off: self.preview_offset = max_preview_off
        visible_preview = preview_raw_lines[self.preview_offset : self.preview_offset + (preview_height - 2)]
 
        # 4. Build Left Content (Form)
        form_lines = [""]
        for i, field in enumerate(self.fields):
            is_focused = (self.focus_idx == i and not self.modal)
            f_errors = self._get_field_errors(field['id'])
            has_error = len(f_errors) > 0
            val = self.form.get(field['id'], "")
            
            # --- COLOR LOGIC ---
            # Default state: Dimmed if not focused
            base_color = ""
            if is_focused:
                base_color = Style.mauve() # Pastel Purple (Mauve)
            
            # Error state (Red)
            # Show red label if global validation triggered or it's a "live" error
            show_label_red = self.show_validation_errors
            if field['id'] == 'id' and val and has_error: show_label_red = True
            if field['id'] == 'category' and val == "Custom..." and not self.form['custom_category']: show_label_red = True
            
            label_color = base_color
            if has_error and show_label_red:
                label_color = Style.red() # Pastel Red
            
            bold = Style.BOLD if is_focused else ""
            
            # 1. Append Label
            form_lines.append(f"  {label_color}{bold}{field['label']}:{Style.RESET}")
            
            # 2. Build Value Line
            value_line = "" # Start clean
            
            # Text Color for the value itself
            value_color = ""
            if field['id'] == 'id' and val and has_error:
                value_color = Style.red()
            elif is_focused:
                value_color = label_color # Match label (Red)

            
            if field['type'] == 'text':
                # Text Input style: [ value ] ✎
                display_val = val if val else ""
                if is_focused and self.is_editing:
                    # Show block cursor at correct position
                    pre = display_val[:self.text_cursor_pos]
                    char = display_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                    post = display_val[self.text_cursor_pos+1:]
                    display_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{value_color}{bold}{post}"
                
                hint = f" {Style.DIM}(E to edit){Style.RESET}" if is_focused and not self.is_editing else ""
                value_line = f"{value_color}{bold}[{Style.RESET}{value_color}{display_val}{Style.RESET}{value_color}{bold}] ✎{Style.RESET}{hint}"
                
            elif field['type'] == 'select':
                # Horizontal Selector style: ○ opt1   ● opt2
                styled_opts = []
                for opt in field['options']:
                    is_sel = (val == opt)
                    mark = "●" if is_sel else "○"
                    
                    # Determine option color
                    opt_color = ""
                    if is_sel:
                        if opt == "Custom..." and not self.form['custom_category']:
                            opt_color = Style.red() # RED IMMEDIATELY
                        elif is_focused:
                            opt_color = Style.mauve()
                        else:
                            opt_color = "" # Default White
                    else:
                        opt_color = Style.DIM

                    # Special case for Custom...
                    if opt == "Custom...":
                        c_val = self.form['custom_category']
                        custom_txt = f"Custom: '{c_val}'" if c_val else "Custom..."
                        
                        if is_sel and self.is_editing:
                            pre = c_val[:self.text_cursor_pos]
                            char = c_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                            post = c_val[self.text_cursor_pos+1:]
                            # Nested colors for cursor during editing
                            custom_txt = f"Custom: '{pre}{Style.INVERT}{char}{Style.RESET}{opt_color}{post}'"
                        
                        styled_opts.append(f"{opt_color}{mark} {custom_txt} ✎{Style.RESET}")
                    else:
                        styled_opts.append(f"{opt_color}{mark} {opt}{Style.RESET}")
                
                hint_txt = "(E to edit)" if val == "Custom..." and not self.is_editing else "(h/l to select)"
                hint = f" {Style.DIM}{hint_txt}{Style.RESET}" if is_focused else ""
                value_line = "   ".join(styled_opts) + hint
                
            elif field['type'] == 'check':
                mark = '■' if val else ' '
                label_txt = 'Yes' if val else 'No'
                hint = f" {Style.DIM}(SPACE to toggle){Style.RESET}" if is_focused else ""
                value_line = f"{value_color}{bold}[{mark}] {label_txt}{Style.RESET}{hint}"
                
            elif field['type'] == 'multi':
                hint = f" {Style.DIM}(E to select){Style.RESET}" if is_focused else ""
                value_line = f"{value_color}{bold}{len(val)} selected{Style.RESET}{hint}"
                
            elif field['type'] == 'placeholder':
                value_line = f"{Style.DIM}[Not implemented]{Style.RESET}"
 
            # 3. Append Value Line (Indented)
            form_lines.append(f"    {value_line}")
            form_lines.append("") # Spacer

        # 5. Generate Boxes
        # Calculate Form Scroll
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
        
        # Preview Scrollbar calculation
        p_scroll_pos, p_scroll_size = None, None
        if len(preview_raw_lines) > (preview_height - 2):
            thumb_size = max(1, int((preview_height - 2)**2 / len(preview_raw_lines)))
            prog = self.preview_offset / max_preview_off if max_preview_off > 0 else 0
            p_scroll_pos = int(prog * (preview_height - 2 - thumb_size))
            p_scroll_size = thumb_size

        preview_box = TUI.create_container(visible_preview, right_width, preview_height, title="PYTHON PREVIEW", is_focused=False, scroll_pos=p_scroll_pos, scroll_size=p_scroll_size)
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 6. Footer
        if self.is_editing:
            p_line = f"{TUI.pill('ENTER', 'Finish', Theme.GREEN)}    {TUI.pill('ESC', 'Cancel', Theme.RED)}"
        else:
            f_pills = [
                TUI.pill('h/j/k/l', 'Navigate', Theme.SKY),
                TUI.pill('PgUp/Dn', 'Scroll Script', Theme.BLUE),
                TUI.pill('E', 'Edit', Theme.BLUE),
                TUI.pill('ENTER', 'Summary & Save', Theme.GREEN),
                TUI.pill('D', 'Draft', Theme.MAUVE),
            ]
            
            if self.active_draft_path:
                f_pills.append(TUI.pill('X', 'Delete Draft', Theme.RED))
            f_pills.append(TUI.pill('Q', 'Back', Theme.RED))
            
            p_line = "    ".join(f_pills)
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(p_line)) // 2)}{p_line}")

        if self.modal:
            m_lines, m_y, m_x = self.modal.render()
            for i, m_line in enumerate(m_lines):
                if 0 <= m_y + i < len(buffer):
                    buffer[m_y + i] = TUI.overlay(buffer[m_y + i], m_line, m_x)

        # 7. Global Notifications Overlay
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
        cat = self.form['custom_category'] if self.form['category'] == "Custom..." else self.form['category']
        
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
            target = 'custom_category' if (field['id'] == 'category' and self.form['category'] == 'Custom...') else field['id']
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
                # Correct DEL behavior: remove character AT the cursor position
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
            is_dirty = any(v for k, v in self.form.items() if k not in ['manager', 'category', 'stow_target', 'dependencies', 'is_incomplete', 'custom_category']) or self.form['stow_target'] != "~"
            if is_dirty:
                self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?")
                self.modal_type = "DISCARD"
            else: return "WELCOME"
                
        if key in [Keys.UP, Keys.K]:
            self.focus_idx = (self.focus_idx - 1) % len(self.fields)
            self._ensure_focus_visible()
        elif key in [Keys.DOWN, Keys.J]:
            self.focus_idx = (self.focus_idx + 1) % len(self.fields)
            self._ensure_focus_visible()
        
        elif key in [Keys.LEFT, Keys.H]:
            if field['type'] == 'select':
                opts = field['options']
                self.form[field['id']] = opts[(opts.index(self.form[field['id']]) - 1) % len(opts)]
        elif key in [Keys.RIGHT, Keys.L]:
            if field['type'] == 'select':
                opts = field['options']
                self.form[field['id']] = opts[(opts.index(self.form[field['id']]) + 1) % len(opts)]

        elif key == Keys.SPACE:
            if field['type'] == 'check': self.form[field['id']] = not self.form[field['id']]
        elif key in [ord('e'), ord('E')]:
            if field['type'] in ['text'] or (field['type'] == 'select' and self.form[field['id']] == 'Custom...'):
                self.is_editing = True
                target = 'custom_category' if (field['id'] == 'category' and self.form['category'] == 'Custom...') else field['id']
                self.old_value = self.form[target]
                self.text_cursor_pos = len(self.old_value)
            elif field['type'] == 'multi':
                self.modal = DependencyModal(self.modules, self.form['dependencies'])
            return None
            
        elif key == Keys.ENTER:
            # GLOBAL SUMMARY TRIGGER
            all_errors = []
            for f in self.fields:
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
