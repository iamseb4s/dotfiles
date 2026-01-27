import shutil
import os
import sys
import time
from core.tui import TUI, Keys, Style
from core.screens.welcome import Screen

class CreateScreen(Screen):
    """
    Interactive wizard for creating package modules.
    Provides a triple-box interface (Form, Help, Preview).
    """
    def __init__(self, modules):
        self.modules = modules
        # Form data with default values
        self.form = {
            'id': '',
            'label': '',
            'manager': 'system',
            'pkg_name': '',
            'category': 'General',
            'stow_target': '~',
            'dependencies': [],
            'is_incomplete': False
        }
        
        # UI State
        self.focus_idx = 0
        self.preview_offset = 0 # Scroll for preview
        self.fields = [
            {'id': 'id', 'label': 'ID', 'help': 'Unique identifier. Used for filename and dots/ folder.'},
            {'id': 'label', 'label': 'Label', 'help': 'Display name in the selection menu.'},
            {'id': 'manager', 'label': 'Manager', 'help': 'Package manager driver (system, cargo, brew, etc.).'},
            {'id': 'pkg_name', 'label': 'Pkg Name', 'help': 'Exact package name for the manager. Defaults to ID.'},
            {'id': 'category', 'label': 'Category', 'help': 'Group name for the package list.'},
            {'id': 'stow_target', 'label': 'Stow Target', 'help': 'Deployment destination (defaults to ~).'},
            {'id': 'dependencies', 'label': 'Dependencies', 'help': 'Other modules required by this package.'},
            {'id': 'is_incomplete', 'label': 'Manual Mode', 'help': 'Mark as incomplete for custom Python logic.'},
            {'id': 'files', 'label': 'Files', 'help': '[Future] fzf file picker placeholder.'}
        ]
        
        self.modal = None

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
        # Total height overhead: Header(1) + Spacer(1) + Spacer(1) + Pills(1) + Margin(1) = 5
        available_height = term_height - 5
        available_height = max(10, available_height)
        
        safe_width = term_width - 2
        left_width = int(safe_width * 0.40)
        right_width = safe_width - left_width - 1
        
        # 3. Build Right Content First (Help & Preview) to determine dynamic heights
        # Help Section
        help_content = []
        if self.focus_idx < len(self.fields):
            field_help = self.fields[self.focus_idx]['help']
            # Special validation help for ID
            if self.fields[self.focus_idx]['id'] == 'id' and self.form['id']:
                if any(m.id == self.form['id'] for m in self.modules):
                    help_content.append(f"  {Style.hex('#FF6B6B')}ERROR: This ID already exists!{Style.RESET}")
            
            wrapped_help = TUI.wrap_text(field_help, right_width - 4)
            for l in wrapped_help:
                help_content.append(f"  {l}")
        
        # Help height is dynamic: Content lines + Top border + Bottom border
        help_height = len(help_content) + 2
        if help_height < 3: help_height = 3 # Min height for title and empty content
        
        preview_height = available_height - help_height
        
        # Python Preview Section
        preview_raw_lines = [""]
        preview_code = self._generate_python()
        for line in preview_code.split("\n"):
            wrapped_code = TUI.wrap_text(line, right_width - 4)
            for wl in wrapped_code:
                preview_raw_lines.append(f"  {Style.DIM}{wl}{Style.RESET}")
        
        # Apply Scroll to Preview
        max_preview_off = max(0, len(preview_raw_lines) - (preview_height - 2))
        if self.preview_offset > max_preview_off:
            self.preview_offset = max_preview_off
            
        preview_content = preview_raw_lines[self.preview_offset : self.preview_offset + (preview_height - 2)]

        # 4. Build Left Content (Form)
        form_lines = [""]
        for i, field in enumerate(self.fields):
            is_focused = (self.focus_idx == i and not self.modal)
            
            # Label
            field_label = field['label']
            value = self.form.get(field['id'], "")
            
            if field['id'] == 'is_incomplete':
                value = "[X] Yes" if value else "[ ] No"
            elif field['id'] == 'dependencies':
                value = f"{len(value)} selected"
            elif field['id'] == 'files':
                value = Style.DIM + "[Not implemented]" + Style.RESET
            
            # Validation for ID
            color = ""
            if field['id'] == 'id' and value:
                if any(m.id == value for m in self.modules):
                    color = Style.hex("#FF6B6B") # Red Pastel
            
            if is_focused:
                line_style = Style.hex("#CBA6F7") + Style.BOLD
                form_lines.append(f"  {line_style}{field_label:<15}: {value}{Style.RESET}")
            else:
                form_lines.append(f"  {color}{field_label:<15}: {value}{Style.RESET}")
            form_lines.append("") # Spacer

        # 5. Generate Boxes
        left_box = TUI.create_container(form_lines, left_width, available_height, title="FORM", is_focused=(not self.modal))
        help_box = TUI.create_container(help_content, right_width, help_height, title="HELP", is_focused=False)
        
        # Preview Scrollbar calculation
        p_scroll_pos = None
        p_scroll_size = None
        if len(preview_raw_lines) > (preview_height - 2):
            p_thumb_size = max(1, int((preview_height - 2)**2 / len(preview_raw_lines)))
            p_prog = self.preview_offset / max_preview_off
            p_scroll_pos = int(p_prog * (preview_height - 2 - p_thumb_size))
            p_scroll_size = p_thumb_size

        preview_box = TUI.create_container(preview_content, right_width, preview_height, title="PYTHON PREVIEW", is_focused=False, scroll_pos=p_scroll_pos, scroll_size=p_scroll_size)
        
        # Combine right column
        right_column = help_box + preview_box
        
        # Stitch left and right
        main_content = TUI.stitch_containers(left_box, right_column, gap=1)
        
        # 6. Footer
        f_move = TUI.pill("h/j/k/l", "Navigate", "81ECEC")
        f_scroll = TUI.pill("PgUp/Dn", "Scroll Script", "89B4FA")
        f_save = TUI.pill("ENTER", "Summary & Save", "a6e3a1")
        f_draft = TUI.pill("D", "Draft", "CBA6F7")
        f_exit = TUI.pill("Q", "Exit", "f38ba8")
        f_back = TUI.pill("ESC", "Discard", "f9e2af")
        
        pills_line = f"{f_back}    {f_move}    {f_scroll}    {f_save}    {f_draft}    {f_exit}"
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(pills_line)) // 2)}{pills_line}")
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(pills_line)) // 2)}{pills_line}")

        # Final Render
        final_output = "\n".join(buffer[:term_height])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()
        
        buffer = [header_bar, ""]
        buffer.extend(main_content)
        buffer.append("")
        buffer.append(f"{' ' * ((term_width - TUI.visible_len(pills_line)) // 2)}{pills_line}")

        # Final Render
        final_output = "\n".join(buffer[:term_height])
        sys.stdout.write("\033[H" + final_output + "\033[J")
        sys.stdout.flush()

    def _generate_python(self):
        """Generates the Python class code based on form data."""
        fid = self.form['id'] or "my_package"
        label = self.form['label'] or "My Package"
        manager = self.form['manager']
        cat = self.form['category']
        target = self.form['stow_target']
        pkg = self.form['pkg_name']
        
        # Class name in CamelCase
        class_name = "".join([p.capitalize() for p in fid.replace("-", "_").split("_")]) + "Module"
        
        code = f"class {class_name}(Module):\n"
        code += f"    id = \"{fid}\"\n"
        code += f"    label = \"{label}\"\n"
        code += f"    category = \"{cat}\"\n"
        code += f"    manager = \"{manager}\""
        
        if pkg and pkg != fid:
            code += f"\n    package_name = \"{pkg}\""
        if target != "~":
            code += f"\n    stow_target = \"{target}\""
        if self.form['dependencies']:
            code += f"\n    dependencies = {self.form['dependencies']}"
            
        return code

    def handle_input(self, key):
        """Processes navigation and modal triggers."""
        if not self.modal:
            # Exit/Back
            if key in [ord('q'), ord('Q')]:
                return "EXIT"
            if key == Keys.ESC:
                # TODO: Check if dirty for ConfirmModal
                return "WELCOME"
                
            # Vertical Navigation
            if key in [Keys.UP, Keys.K, 65]:
                self.focus_idx = (self.focus_idx - 1) % len(self.fields)
            elif key in [Keys.DOWN, Keys.J, 66]:
                self.focus_idx = (self.focus_idx + 1) % len(self.fields)
            
            # Horizontal Navigation (Placeholder for selectors)
            if key in [Keys.LEFT, Keys.H, 68]:
                pass # Will handle selectors later
            elif key in [Keys.RIGHT, Keys.L, 67]:
                pass # Will handle selectors later

            # Preview Scroll
            if key == Keys.PGUP:
                self.preview_offset = max(0, self.preview_offset - 5)
            elif key == Keys.PGDN:
                self.preview_offset += 5 # Bound check handled in render
                
        return None
