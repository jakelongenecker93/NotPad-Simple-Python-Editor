import tkinter as tk
from tkinter import filedialog, messagebox
import keyword
import re
import os
import sys
import bisect


class CodeEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NotPad Editor")
        self.geometry("900x700")
        self.indent_width = 4  # change this if you want a different default
        self.current_file = None

        # Syntax coloring toggle (on by default)
        self.syntax_enabled = tk.BooleanVar(value=True)

        self._create_widgets()
        self._create_menu()
        self._bind_events()

        # Open file passed on command line, if any (for right-click -> Open with)
        if len(sys.argv) > 1:
            path = sys.argv[1]
            if os.path.isfile(path):
                self._open_file(path)

    def _create_widgets(self):
        font_family = "Consolas"
        font_size = 11

        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Vertical scrollbar shared by gutter and text
        self.v_scroll = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Gutter showing indentation counts
        self.gutter = tk.Text(
            self.main_frame,
            width=4,  # enough for "##|"
            padx=2,
            takefocus=0,
            state=tk.DISABLED,
            wrap="none",
            font=(font_family, font_size),
            background="#f0f0f0",
            foreground="#606060",
            borderwidth=0,
            highlightthickness=0,
        )
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)

        # Main text area
        self.text = tk.Text(
            self.main_frame,
            undo=True,
            wrap="none",
            font=(font_family, font_size),
            borderwidth=0,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Make selected text white so it is readable regardless of syntax scheme
        self.text.tag_configure("sel", foreground="white")

        # Connect scrollbar
        self.text.config(yscrollcommand=self._on_textscroll)
        self.gutter.config(yscrollcommand=self._on_gutterscroll)
        self.v_scroll.config(command=self._on_scrollbar)

        # Basic syntax highlight tags
        self.text.tag_configure("py_keyword", foreground="#0000cc")
        self.text.tag_configure("py_builtin", foreground="#0066aa")
        self.text.tag_configure("py_comment", foreground="#008000")
        self.text.tag_configure("py_string", foreground="#aa5500")
        self.text.tag_configure("py_number", foreground="#990099")

        # Ensure selection tag is on top of other tags so white text wins
        self.text.tag_raise("sel")

        self._update_gutter()

    def _create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New", accelerator="Ctrl+N", command=self._new_file)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self._open_dialog)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._save_file)
        file_menu.add_command(label="Save As...", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        tools = tk.Menu(menubar, tearoff=False)
        tools.add_checkbutton(
            label="Enable Python syntax coloring",
            variable=self.syntax_enabled,
            command=self._toggle_syntax_coloring,
        )
        tools.add_command(
            label="Color Python syntax now",
            accelerator="F5",
            command=self._color_python_now,
        )
        menubar.add_cascade(label="Tools", menu=tools)

        # Info / help dropdown
        info_menu = tk.Menu(menubar, tearoff=False)
        info_menu.add_command(label="Editor info / shortcuts", command=self._show_info)
        menubar.add_cascade(label="Info", menu=info_menu)

        self.config(menu=menubar)

    def _show_info(self):
        """Show a small help/about dialog with shortcuts and features."""
        info_text = (
            "MiniPy / NotPad Editor – quick reference\n\n"
            "Basic file operations:\n"
            "  Ctrl+N   – New file\n"
            "  Ctrl+O   – Open file\n"
            "  Ctrl+S   – Save file\n\n"
            "Indentation:\n"
            "  Tab / Ctrl+Tab          – Indent selection (or insert spaces if no selection)\n"
            "  Shift+Tab / Ctrl+Shift+Tab  – Outdent selection\n\n"
            "Syntax coloring:\n"
            "  Tools → Enable Python syntax coloring   – Turn color on/off (default: on)\n"
            "  F5 or Tools → Color Python syntax now   – Apply/refresh coloring\n\n"
            "Other notes:\n"
            "  • Selected text is always shown in white so it stays readable.\n"
            "  • The left gutter shows the number of leading spaces on each line.\n"
        )
        messagebox.showinfo("Editor info / shortcuts", info_text)

    def _bind_events(self):
        # Keep gutter updated when text changes or widget resizes
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<Configure>", lambda e: self._update_gutter())

        # Tab / Shift-Tab for indent / outdent (and Ctrl+Tab variants)
        self.text.bind("<Tab>", self._indent_selection)
        self.text.bind("<Shift-Tab>", self._outdent_selection)
        self.text.bind("<Control-Tab>", self._indent_selection)
        self.text.bind("<Control-Shift-Tab>", self._outdent_selection)

        # Keyboard shortcuts
        self.bind("<Control-n>", lambda e: (self._new_file(), "break"))
        self.bind("<Control-o>", lambda e: (self._open_dialog(), "break"))
        self.bind("<Control-s>", lambda e: (self._save_file(), "break"))
        self.bind("<F5>",       lambda e: (self._color_python_now(), "break"))

    # --- Scrolling sync ---

    def _on_textscroll(self, *args):
        self.gutter.yview_moveto(args[0])
        self.v_scroll.set(*args)

    def _on_gutterscroll(self, *args):
        self.text.yview_moveto(args[0])
        self.v_scroll.set(*args)

    def _on_scrollbar(self, *args):
        self.text.yview(*args)
        self.gutter.yview(*args)

    # --- File operations ---

    def _new_file(self):
        if not self._ok_to_discard():
            return
        self.text.delete("1.0", tk.END)
        self.current_file = None
        self.title("MiniPy Editor")
        self._clear_syntax()
        self._update_gutter()

    def _open_dialog(self):
        if not self._ok_to_discard():
            return
        path = filedialog.askopenfilename(
            filetypes=[
                ("Python files", "*.py *.pyw"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self._open_file(path)

    def _open_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()
        except OSError as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")
            return

        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.current_file = path
        self.title(f"MiniPy Editor - {os.path.basename(path)}")
        self.text.edit_reset()
        self.text.edit_modified(False)
        # Clear any old syntax colors and re-apply depending on toggle
        if self.syntax_enabled.get():
            self._highlight_python()
        else:
            self._clear_syntax()
        self._update_gutter()

    def _save_file(self):
        if self.current_file is None:
            return self._save_as()
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except OSError as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")
            return
        self.text.edit_modified(False)

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[
                ("Python files", "*.py *.pyw"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.current_file = path
        self._save_file()
        self.title(f"MiniPy Editor - {os.path.basename(path)}")

    def _ok_to_discard(self):
        if self.text.edit_modified():
            response = messagebox.askyesnocancel(
                "Unsaved changes", "Save changes before continuing?"
            )
            if response is None:  # Cancel
                return False
            if response:  # Yes
                self._save_file()
        return True

    # --- Gutter / indentation display ---

    def _on_modified(self, event=None):
        if self.text.edit_modified():
            self._update_gutter()
            self.text.edit_modified(False)

    def _update_gutter(self):
        # Preserve current vertical scroll position so Tab / Shift-Tab don't jump
        yview = self.text.yview()

        # Build indentation counts for each line
        content = self.text.get("1.0", "end-1c")
        lines = content.split("\n")
        gutter_lines = []
        for line in lines:
            # Count leading spaces only
            stripped = line.lstrip(" ")
            indent_spaces = len(line) - len(stripped)
            if line == "":
                display = "  |"  # empty line
            else:
                if indent_spaces == 0:
                    display = "  |"
                else:
                    # Clamp to two characters; for large indents just show last 2 digits
                    num_str = str(indent_spaces)[-2:]
                    display = f"{num_str:>2}|"
            gutter_lines.append(display)

        # Ensure at least one line
        if not gutter_lines:
            gutter_lines = ["  |"]
        gutter_text = "\n".join(gutter_lines)

        self.gutter.config(state=tk.NORMAL)
        self.gutter.delete("1.0", tk.END)
        self.gutter.insert("1.0", gutter_text)
        self.gutter.config(state=tk.DISABLED)

        # Restore vertical scroll position
        if yview:
            self.text.yview_moveto(yview[0])
            self.gutter.yview_moveto(yview[0])

    # --- Indent / outdent ---

    def _indent_selection(self, event=None):
        try:
            # Expand selection to full lines
            start = self.text.index("sel.first linestart")
            end = self.text.index("sel.last lineend")
            multi = True
        except tk.TclError:
            multi = False

        indent = " " * self.indent_width

        if not multi:
            # No selection: just insert spaces
            self.text.insert("insert", indent)
        else:
            # Indent all selected lines
            text_block = self.text.get(start, end)
            lines = text_block.split("\n")
            lines = [indent + line for line in lines]
            new_block = "\n".join(lines)

            self.text.delete(start, end)
            self.text.insert(start, new_block)

            # Keep the (updated) block selected
            new_end = self.text.index(f"{start} + {len(new_block)}c")
            self.text.tag_remove("sel", "1.0", "end")
            self.text.tag_add("sel", start, new_end)

        self._update_gutter()
        return "break"  # prevent default Tab behavior

    def _outdent_selection(self, event=None):
        try:
            start = self.text.index("sel.first linestart")
            end = self.text.index("sel.last lineend")
            multi = True
        except tk.TclError:
            multi = False

        if not multi:
            # No selection: remove up to indent_width spaces before cursor
            line_start = self.text.index("insert linestart")
            line_to_cursor = self.text.get(line_start, "insert")
            removable = min(
                self.indent_width, len(line_to_cursor) - len(line_to_cursor.lstrip(" "))
            )
            if removable > 0:
                self.text.delete(f"insert - {removable}c", "insert")
            self._update_gutter()
            return "break"

        # Outdent all selected lines
        text_block = self.text.get(start, end)
        lines = text_block.split("\n")
        new_lines = []
        for line in lines:
            removed = 0
            while removed < self.indent_width and line.startswith(" "):
                line = line[1:]
                removed += 1
            new_lines.append(line)

        new_block = "\n".join(new_lines)
        self.text.delete(start, end)
        self.text.insert(start, new_block)

        # Keep the (updated) block selected
        new_end = self.text.index(f"{start} + {len(new_block)}c")
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", start, new_end)

        self._update_gutter()
        return "break"

    # --- Syntax highlighting ---

    def _clear_syntax(self):
        for tag in ("py_keyword", "py_builtin", "py_comment", "py_string", "py_number"):
            self.text.tag_remove(tag, "1.0", tk.END)

    def _toggle_syntax_coloring(self):
        """Turn syntax coloring on/off via the Tools menu."""
        if self.syntax_enabled.get():
            self._highlight_python()
        else:
            self._clear_syntax()

    def _color_python_now(self):
        """Apply or clear syntax coloring when F5 (or menu) is used."""
        if self.syntax_enabled.get():
            self._highlight_python()
        else:
            self._clear_syntax()

    def _highlight_python(self):
        content = self.text.get("1.0", "end-1c")
        self._clear_syntax()
        if not content.strip():
            return

        # Precompute line start offsets to convert absolute offsets to Tk indices
        line_starts = [0]
        for m in re.finditer(r"\n", content):
            line_starts.append(m.end())

        def offset_to_index(offset):
            # Find rightmost line_start <= offset
            line_no = bisect.bisect_right(line_starts, offset) - 1
            col = offset - line_starts[line_no]
            return f"{line_no + 1}.{col}"

        taken_ranges = []

        def mark(pattern, tag, skip_existing=False):
            for m in pattern.finditer(content):
                start_off, end_off = m.span()
                if skip_existing and any(
                    (start_off < e and end_off > s) for s, e in taken_ranges
                ):
                    continue
                start_idx = offset_to_index(start_off)
                end_idx = offset_to_index(end_off)
                self.text.tag_add(tag, start_idx, end_idx)
                taken_ranges.append((start_off, end_off))

        # Strings (single, double) – simple approximation
        string_pattern = re.compile(
            r"('[^'\\\n]*(?:\\.[^'\\\n]*)*'|\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\")"
        )
        mark(string_pattern, "py_string")

        # Comments
        comment_pattern = re.compile(r"#.*")
        mark(comment_pattern, "py_comment")

        # Keywords
        kw_pattern = re.compile(r"\b(" + "|".join(keyword.kwlist) + r")\b")
        mark(kw_pattern, "py_keyword", skip_existing=True)

        # Builtins
        builtin_names = dir(__builtins__)
        builtin_pattern = re.compile(
            r"\b(" + "|".join(map(re.escape, builtin_names)) + r")\b"
        )
        mark(builtin_pattern, "py_builtin", skip_existing=True)

        # Numbers
        number_pattern = re.compile(r"\b\d+(\.\d+)?\b")
        mark(number_pattern, "py_number", skip_existing=True)


def main():
    app = CodeEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
