"""话术面板 - txt存储、分组展示、点击复制并交给主窗口自动上屏"""
import tkinter as tk
from core.clipboard_ops import ClipboardOps


class PhrasesPanel:
    """话术面板：从工具根目录 phrases.txt 读取，点击话术复制到剪贴板并触发回调。"""

    COLOR_PRIMARY = "#1677ff"
    COLOR_PRIMARY_LIGHT = "#e8f2ff"
    COLOR_BG = "#f5f8fc"
    COLOR_CARD = "#ffffff"
    COLOR_TEXT = "#111827"
    COLOR_MUTED = "#6b7280"
    COLOR_BORDER = "#e2e8f0"
    COLOR_HOVER = "#f0f7ff"

    def __init__(self, parent, phrases_path, on_phrase_click=None):
        self.parent = parent
        self.phrases_path = phrases_path
        self.on_phrase_click = on_phrase_click
        self.clipboard = ClipboardOps()
        self.current_group_index = 0
        self.group_buttons = []

        self.phrases_data = self._load_phrases()
        self._build_ui()
        self._populate_groups()

    def _load_phrases(self):
        """读取 phrases.txt。

        支持格式：
        [分组名]
        标题 = 话术内容
        也支持无等号行，标题自动取内容前20字。
        """
        groups = []
        current = None

        try:
            with open(self.phrases_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {"groups": []}

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                current = {"name": line[1:-1].strip() or "未命名分组", "items": []}
                groups.append(current)
                continue

            if current is None:
                current = {"name": "默认分组", "items": []}
                groups.append(current)

            if "=" in line:
                title, content = line.split("=", 1)
                title = title.strip() or content.strip()[:20]
                content = content.strip()
            else:
                content = line
                title = line[:20]

            if content:
                current["items"].append({"title": title, "content": content})

        return {"groups": groups}

    def _save_phrases(self):
        """保存为 phrases.txt。"""
        parts = []
        for group in self.phrases_data.get("groups", []):
            parts.append(f"[{group['name']}]")
            for item in group.get("items", []):
                title = item.get("title", "").replace("\n", " ").strip()
                content = item.get("content", "").replace("\n", " ").strip()
                if content:
                    parts.append(f"{title} = {content}")
            parts.append("")

        with open(self.phrases_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts).strip() + "\n")

    def _build_ui(self):
        self.container = tk.Frame(self.parent, bg=self.COLOR_BG)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        toolbar = tk.Frame(self.container, bg=self.COLOR_BG)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        search_wrap = tk.Frame(
            toolbar,
            bg=self.COLOR_CARD,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            highlightcolor=self.COLOR_PRIMARY
        )
        search_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=1)

        tk.Label(
            search_wrap,
            text="搜",
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=self.COLOR_CARD,
            fg=self.COLOR_MUTED
        ).pack(side=tk.LEFT, padx=(9, 0))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search_var,
            font=("Microsoft YaHei UI", 9),
            relief=tk.FLAT,
            bd=0,
            bg=self.COLOR_CARD,
            fg=self.COLOR_MUTED,
            insertbackground=self.COLOR_PRIMARY
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=7, ipady=7)
        self.search_entry.insert(0, "搜索话术...")
        self.search_entry.bind("<FocusIn>", self._clear_placeholder)
        self.search_entry.bind("<FocusOut>", self._restore_placeholder)

        self._make_toolbar_button(toolbar, "刷新", self.reload).pack(side=tk.RIGHT, padx=(7, 0))
        self._make_toolbar_button(toolbar, "编辑", self._open_edit_dialog, primary=True).pack(side=tk.RIGHT, padx=(7, 0))

        content = tk.Frame(self.container, bg=self.COLOR_BG)
        content.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(content, bg=self.COLOR_CARD, width=86, highlightthickness=1, highlightbackground=self.COLOR_BORDER)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        group_header = tk.Label(
            left,
            text="分组",
            font=("Microsoft YaHei UI", 8, "bold"),
            bg=self.COLOR_CARD,
            fg=self.COLOR_MUTED,
            anchor="w"
        )
        group_header.pack(fill=tk.X, padx=10, pady=(10, 6))

        self.group_frame = tk.Frame(left, bg=self.COLOR_CARD)
        self.group_frame.pack(fill=tk.BOTH, expand=True, padx=7, pady=(0, 8))

        right = tk.Frame(content, bg=self.COLOR_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self.items_canvas = tk.Canvas(right, bg=self.COLOR_BG, highlightthickness=0, bd=0)
        self.items_scrollbar = tk.Scrollbar(right, orient=tk.VERTICAL, command=self.items_canvas.yview, relief=tk.FLAT, bd=0)
        self.items_frame = tk.Frame(self.items_canvas, bg=self.COLOR_BG)
        self.items_window = self.items_canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        self.items_canvas.configure(yscrollcommand=self.items_scrollbar.set)
        self.items_frame.bind("<Configure>", lambda e: self.items_canvas.configure(scrollregion=self.items_canvas.bbox("all")))
        self.items_canvas.bind("<Configure>", lambda e: self.items_canvas.itemconfigure(self.items_window, width=e.width))
        self.items_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.items_canvas.bind("<Enter>", lambda e: self.items_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.items_canvas.bind("<Leave>", lambda e: self.items_canvas.unbind_all("<MouseWheel>"))
        self.search_var.trace_add("write", self._on_search)

    def _make_toolbar_button(self, parent, text, command, primary=False):
        bg = self.COLOR_PRIMARY if primary else self.COLOR_CARD
        fg = "white" if primary else self.COLOR_TEXT
        hover = "#0f5fd7" if primary else self.COLOR_HOVER
        btn = tk.Button(
            parent,
            text=text,
            font=("Microsoft YaHei UI", 9, "bold" if primary else "normal"),
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief=tk.FLAT,
            bd=0,
            command=command,
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=hover))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=bg))
        return btn

    def _clear_placeholder(self, event):
        if self.search_var.get() == "搜索话术...":
            self.search_entry.config(fg=self.COLOR_TEXT)
            self.search_var.set("")

    def _restore_placeholder(self, event):
        if not self.search_var.get().strip():
            self.search_entry.config(fg=self.COLOR_MUTED)
            self.search_var.set("搜索话术...")

    def _on_mousewheel(self, event):
        self.items_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _populate_groups(self):
        for widget in self.group_frame.winfo_children():
            widget.destroy()
        self.group_buttons = []

        groups = self.phrases_data.get("groups", [])
        for idx, group in enumerate(groups):
            btn = tk.Label(
                self.group_frame,
                text=group["name"],
                font=("Microsoft YaHei UI", 8, "bold" if idx == self.current_group_index else "normal"),
                bg=self.COLOR_PRIMARY if idx == self.current_group_index else self.COLOR_CARD,
                fg="white" if idx == self.current_group_index else self.COLOR_TEXT,
                anchor="w",
                cursor="hand2",
                padx=8,
                pady=7
            )
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Button-1>", lambda e, i=idx: self._select_group(i))
            btn.bind("<Enter>", lambda e, b=btn, i=idx: self._hover_group(b, i, True))
            btn.bind("<Leave>", lambda e, b=btn, i=idx: self._hover_group(b, i, False))
            self.group_buttons.append(btn)

        if groups:
            self.current_group_index = min(self.current_group_index, len(groups) - 1)
            self._select_group(self.current_group_index, refresh_buttons=True)
        else:
            self._show_items([])

    def _hover_group(self, button, idx, enter):
        if idx == self.current_group_index:
            return
        button.configure(bg=self.COLOR_HOVER if enter else self.COLOR_CARD)

    def _select_group(self, idx, refresh_buttons=True):
        self.current_group_index = idx
        if refresh_buttons:
            for i, btn in enumerate(self.group_buttons):
                selected = i == idx
                btn.configure(
                    bg=self.COLOR_PRIMARY if selected else self.COLOR_CARD,
                    fg="white" if selected else self.COLOR_TEXT,
                    font=("Microsoft YaHei UI", 8, "bold" if selected else "normal")
                )
        group = self.phrases_data["groups"][idx]
        self._show_items(group.get("items", []))

    def _show_items(self, items):
        for widget in self.items_frame.winfo_children():
            widget.destroy()

        if not items:
            empty = tk.Frame(self.items_frame, bg=self.COLOR_CARD, highlightthickness=1, highlightbackground=self.COLOR_BORDER)
            empty.pack(fill=tk.X, pady=4)
            tk.Label(
                empty,
                text="暂无话术",
                font=("Microsoft YaHei UI", 10, "bold"),
                fg=self.COLOR_MUTED,
                bg=self.COLOR_CARD
            ).pack(anchor="w", padx=14, pady=(14, 2))
            tk.Label(
                empty,
                text="点击“编辑”添加常用回复",
                font=("Microsoft YaHei UI", 8),
                fg=self.COLOR_MUTED,
                bg=self.COLOR_CARD
            ).pack(anchor="w", padx=14, pady=(0, 14))
            return

        for item in items:
            self._create_phrase_card(item)

    def _create_phrase_card(self, item):
        row = tk.Frame(
            self.items_frame,
            bg=self.COLOR_CARD,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            highlightcolor=self.COLOR_PRIMARY,
            cursor="hand2"
        )
        row.pack(fill=tk.X, pady=(0, 8))

        title = tk.Label(
            row,
            text=item["title"],
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=self.COLOR_CARD,
            fg=self.COLOR_TEXT,
            anchor="w",
            cursor="hand2"
        )
        title.pack(fill=tk.X, padx=12, pady=(10, 3))

        content = tk.Label(
            row,
            text=item["content"],
            font=("Microsoft YaHei UI", 8),
            bg=self.COLOR_CARD,
            fg="#374151",
            anchor="w",
            justify=tk.LEFT,
            wraplength=168,
            cursor="hand2"
        )
        content.pack(fill=tk.X, padx=12, pady=(0, 9))

        hint = tk.Label(
            row,
            text="点击上屏",
            font=("Microsoft YaHei UI", 7),
            bg=self.COLOR_CARD,
            fg=self.COLOR_PRIMARY,
            anchor="e",
            cursor="hand2"
        )
        hint.pack(fill=tk.X, padx=12, pady=(0, 9))

        widgets = (row, title, content, hint)
        for w in widgets:
            w.bind("<Button-1>", lambda e, text=item["content"]: self._copy_phrase(text))
            w.bind("<Enter>", lambda e, widgets=widgets: self._set_card_hover(widgets, True))
            w.bind("<Leave>", lambda e, widgets=widgets: self._set_card_hover(widgets, False))

    def _set_card_hover(self, widgets, hover):
        bg = self.COLOR_HOVER if hover else self.COLOR_CARD
        for w in widgets:
            w.configure(bg=bg)

    def _copy_phrase(self, content):
        self.clipboard.write(content)
        if self.on_phrase_click:
            self.on_phrase_click(content)

    def _on_search(self, *args):
        query = self.search_var.get().strip()
        if not query or query == "搜索话术...":
            if self.phrases_data.get("groups"):
                self._show_items(self.phrases_data["groups"][self.current_group_index].get("items", []))
            return

        found = []
        for group in self.phrases_data.get("groups", []):
            for item in group.get("items", []):
                if query.lower() in item["title"].lower() or query.lower() in item["content"].lower():
                    found.append({"title": f"[{group['name']}] {item['title']}", "content": item["content"]})
        self._show_items(found)

    def _open_edit_dialog(self):
        from .edit_dialog import EditDialog
        dialog = EditDialog(self.parent, self.phrases_data)
        self.parent.wait_window(dialog.top)
        if dialog.result:
            self.phrases_data = dialog.result
            self._save_phrases()
            self._populate_groups()

    def reload(self):
        self.phrases_data = self._load_phrases()
        self._populate_groups()
