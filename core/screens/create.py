import shutil
import os
import sys
import time
import re
from core.tui import TUI, Keys, Style
from core.screens.welcome import Screen
from core.screens.install import ConfirmModal

class CreateScreen(Screen):
    """
    Interactive wizard for creating package modules.
    Provides a triple-box interface (Form, Help, Preview).
    """
    def __init__(self, modules):
        self.modules = modules
        self.categories = self._get_categories()
        
        # Form data with default values
        self.form = {
            'id': '',
            'label': '',
            'manager': 'system',
            'pkg_name': '',
            'category': self.categories[0] if self.categories else 'General',
            'custom_category': '',
            'stow_target': '~',
            'dependencies': [],
            'is_incomplete': False
        }
        
        # Available options
        self.managers = ['system', 'cargo', 'brew', 'bob', 'custom']
        
        # UI State
        self.focus_idx = 0
        self.preview_offset = 0 # Scroll for preview
        self.is_editing = False # Text input mode
        self.text_cursor_pos = 0 # Cursor position within string
        self.old_value = ""     # To restore on ESC
        self.modal = None
        self.modal_type = None # "DISCARD", "SAVE", "DRAFT"
        
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

    def _get_categories(self):
        """Extracts existing categories from loaded modules."""
        cats = sorted(list(set(m.category for m in self.modules)))
        if "Custom..." not in cats:
            cats.append("Custom...")
        return cats

    def render(self):
        """Draws the triple-box layout (40/60 vertical split on right)."""
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        
        # 1. Header
        title_text = " PACKAGE WIZARD "
        bg_purple = Style.hex("CBA6F7", bg=True)
        text_black = "\033[30m"
        padding = (term_width - len(title_text)) // 2
        header_bar = f"{bg_purple}{text_black}{' '*padding}{title_text}{' '*(term_width-padding-len(title_text))}{Style.RESET}"
        
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
            
            wrapped_help = TUI.wrap_text(help_text, right_width - 4)
            for l in wrapped_help:
                help_content.append(f"  {l}")
            
            # Special validation help for ID
            if field['id'] == 'id' and self.form['id']:
                # 1. Regex validation (No dots, no special chars except - and _)
                if not re.match(r'^[a-zA-Z0-9_-]+$', self.form['id']):
                    help_content.append(f"  {Style.hex('#f38ba8')}ERROR: Invalid format! Use letters, numbers, - or _ only.{Style.RESET}")
                # 2. Existing ID validation
                elif any(m.id == self.form['id'] for m in self.modules):
                    help_content.append(f"  {Style.hex('#f38ba8')}ERROR: This ID already exists!{Style.RESET}")
        
        # Help height is dynamic
        help_height = len(help_content) + 2
        if help_height < 3: help_height = 3
        
        preview_height = available_height - help_height
        
        # Python Preview Section
        preview_raw_lines = [""]
        preview_code = self._generate_python()
        for line in preview_code.split("\n"):
            wrapped_code = TUI.wrap_text(line, right_width - 4)
            for wl in wrapped_code:
                preview_raw_lines.append(f"  {wl}")
        
        # Apply Scroll to Preview
        max_preview_off = max(0, len(preview_raw_lines) - (preview_height - 2))
        if self.preview_offset > max_preview_off:
            self.preview_offset = max_preview_off
            
        preview_content = preview_raw_lines[self.preview_offset : self.preview_offset + (preview_height - 2)]

        # 4. Build Left Content (Form)
        form_lines = [""]
        for i, field in enumerate(self.fields):
            is_focused = (self.focus_idx == i and not self.modal)
            
            # Label Row
            color = Style.hex("#CBA6F7") if is_focused else ""
            bold = Style.BOLD if is_focused else ""
            form_lines.append(f"  {color}{bold}{field['label']}:{Style.RESET}")
            
            # Value Row
            value_line = "  "
            field_id = field['id']
            val = self.form.get(field_id, "")
            
            if field['type'] == 'text':
                # Text Input style: [ value ] ✎
                display_val = val if val else ""
                if is_focused and self.is_editing:
                    # Show block cursor at correct position
                    pre = display_val[:self.text_cursor_pos]
                    char = display_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                    post = display_val[self.text_cursor_pos+1:]
                    display_val = f"{pre}{Style.INVERT}{char}{Style.RESET}{color if is_focused else ''}{bold if is_focused else ''}{post}"
                
                # Validation color for ID (Regex or Duplicated)
                txt_color = ""
                if field_id == 'id' and val:
                    if not re.match(r'^[a-zA-Z0-9_-]+$', val) or any(m.id == val for m in self.modules):
                        txt_color = Style.hex("#f38ba8")
                
                hint = f" {Style.DIM}(ENTER to edit){Style.RESET}" if is_focused and not self.is_editing else ""
                value_line += f"[{txt_color}{display_val}{Style.RESET}{color if is_focused else ''}{bold if is_focused else ''}] ✎{hint}"
                
            elif field['type'] == 'select':
                # Horizontal Selector style: ○ opt1   ● opt2
                styled_opts = []
                for opt in field['options']:
                    is_sel = (val == opt)
                    mark = "●" if is_sel else "○"
                    
                    # Special case for Custom...
                    if opt == "Custom...":
                        custom_txt = f"Custom: '{self.form['custom_category']}'" if self.form['custom_category'] else "Custom..."
                        if is_sel and self.is_editing:
                            c_val = self.form['custom_category']
                            pre = c_val[:self.text_cursor_pos]
                            char = c_val[self.text_cursor_pos:self.text_cursor_pos+1] or " "
                            post = c_val[self.text_cursor_pos+1:]
                            custom_txt = f"Custom: '{pre}{Style.INVERT}{char}{Style.RESET}{color if is_focused else ''}{bold if is_focused else ''}{post}'"
                        styled_opts.append(f"{mark} {custom_txt} ✎")
                    else:
                        styled_opts.append(f"{mark} {opt}")
                
                hint_txt = "(ENTER to edit)" if val == "Custom..." and not self.is_editing else "(h/l to select)"
                hint = f" {Style.DIM}{hint_txt}{Style.RESET}" if is_focused else ""
                value_line += "   ".join(styled_opts) + hint
                
            elif field['type'] == 'check':
                mark = "■" if val else " "
                hint = f" {Style.DIM}(SPACE to toggle){Style.RESET}" if is_focused else ""
                value_line += f"[{mark}] {'Yes' if val else 'No'}{hint}"
                
            elif field['type'] == 'multi':
                hint = f" {Style.DIM}(ENTER to select){Style.RESET}" if is_focused else ""
                value_line += f"{len(val)} selected{hint}"
            elif field['type'] == 'placeholder':
                value_line += f"{Style.DIM}[Not implemented]{Style.RESET}"

            # Apply focus color to value line too if focused
            if is_focused:
                form_lines.append(f"{color}{bold}{value_line}{Style.RESET}")
            else:
                form_lines.append(value_line)
                
            form_lines.append("") # Spacer between fields

        # 5. Generate Boxes
        left_box = TUI.create_container(form_lines, left_width, available_height, title="FORM", is_focused=(not self.modal))
        help_box = TUI.create_container(help_content, right_width, help_height, title="HELP", is_focused=False)
        
        # Preview Scrollbar calculation
        p_scroll_pos, p_scroll_size = None, None
        if len(preview_raw_lines) > (preview_height - 2):
            thumb_size = max(1, int((preview_height - 2)**2 / len(preview_raw_lines)))
            prog = self.preview_offset / max_preview_off
            p_scroll_pos = int(prog * (preview_height - 2 - thumb_size))
            p_scroll_size = thumb_size

        preview_box = TUI.create_container(preview_raw_lines[self.preview_offset : self.preview_offset + (preview_height - 2)], 
                                         right_width, preview_height, title="PYTHON PREVIEW", is_focused=False, 
                                         scroll_pos=p_scroll_pos, scroll_size=p_scroll_size)
        
        main_content = TUI.stitch_containers(left_box, help_box + preview_box, gap=1)
        
        # 6. Footer
        if self.is_editing:
            p_line = f"{TUI.pill('ENTER', 'Finish', 'a6e3a1')}    {TUI.pill('ESC', 'Cancel', 'f38ba8')}"
        else:
            f_pills = [
                TUI.pill('ESC', 'Discard', 'f9e2af'),
                TUI.pill('h/j/k/l', 'Navigate', '81ECEC'),
                TUI.pill('PgUp/Dn', 'Scroll Script', '89B4FA'),
                TUI.pill('ENTER', 'Summary & Save', 'a6e3a1'),
                TUI.pill('D', 'Draft', 'CBA6F7'),
                TUI.pill('Q', 'Exit', 'f38ba8')
            ]
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

        # Final Render
        final_output = "\n".join(buffer[:term_height])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

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
                if self.modal_type == "DISCARD": return "WELCOME"
            elif res in ["NO", "CLOSE"]: self.modal = None
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
            elif 32 <= key <= 126 and key not in [65, 66, 67, 68]:
                self.form[target] = curr_val[:self.text_cursor_pos] + chr(key) + curr_val[self.text_cursor_pos:]
                self.text_cursor_pos += 1
            return None

        # --- NAVIGATION MODE ---
        if key in [ord('q'), ord('Q')]: return "EXIT"
        
        if key == Keys.ESC:
            is_dirty = any(v for k, v in self.form.items() if k not in ['manager', 'category', 'stow_target', 'dependencies', 'is_incomplete', 'custom_category']) or self.form['stow_target'] != "~"
            if is_dirty:
                self.modal = ConfirmModal("DISCARD CHANGES", "Are you sure you want to discard all changes?")
                self.modal_type = "DISCARD"
            else: return "WELCOME"
                
        if key in [Keys.UP, Keys.K, 65]: self.focus_idx = (self.focus_idx - 1) % len(self.fields)
        elif key in [Keys.DOWN, Keys.J, 66]: self.focus_idx = (self.focus_idx + 1) % len(self.fields)
        
        elif key in [Keys.LEFT, Keys.H, 68]:
            if field['type'] == 'select':
                opts = field['options']
                self.form[field['id']] = opts[(opts.index(self.form[field['id']]) - 1) % len(opts)]
        elif key in [Keys.RIGHT, Keys.L, 67]:
            if field['type'] == 'select':
                opts = field['options']
                self.form[field['id']] = opts[(opts.index(self.form[field['id']]) + 1) % len(opts)]

        elif key == Keys.SPACE:
            if field['type'] == 'check': self.form[field['id']] = not self.form[field['id']]
        elif key == Keys.ENTER or key in [ord('e'), ord('E')]:
            if field['type'] in ['text'] or (field['type'] == 'select' and self.form[field['id']] == 'Custom...'):
                self.is_editing = True
                target = 'custom_category' if (field['id'] == 'category' and self.form['category'] == 'Custom...') else field['id']
                self.old_value = self.form[target]
                self.text_cursor_pos = len(self.old_value)
            elif field['type'] == 'check':
                pass
        elif key == Keys.PGUP: self.preview_offset = max(0, self.preview_offset - 5)
        elif key == Keys.PGDN: self.preview_offset += 5 
        return None
