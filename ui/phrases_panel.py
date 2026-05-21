"""话术面板 - txt存储、分组展示、动态宽度换行、点击上屏"""
import tkinter as tk
from core.clipboard_ops import ClipboardOps


class PhrasesPanel:
    """话术面板：从工具根目录 phrases.txt 读取，点击话术自动上屏。"""

    COLOR_PRIMARY = "#5b6af0"
    COLOR_PRIMARY_LIGHT = "#edeffb"
    COLOR_BG = "#eef0f6"
    COLOR_CARD = "#ffffff"
    COLOR_TEXT = "#1e1f2a"
    COLOR_MUTED = "#8c8ea3"
    COLOR_BORDER = "#e4e5ee"
    COLOR_HOVER = "#f4f5ff"
    COLOR_TAG_BG = "#f2f3f7"
    COLOR_TAG_FG = "#5f6173"
    COLOR_ACTIVE_BG = "#e9eafa"

    CARD_PAD_X = 12                        # 卡片内部左右 padding

    def __init__(self, parent, phrases_path, on_phrase_click=None):
        self.parent = parent
        self.phrases_path = phrases_path
        self.on_phrase_click = on_phrase_click
        self.clipboard = ClipboardOps()
        self.current_group_index = 0
        self.group_buttons = []
        self._content_widgets = []          # 记录每张卡片的 content label，用于动态更新 wraplength

        self.phrases_data = self._load_phrases()
        self._build_ui()
        self._populate_groups()

    # ---------- 文件读写 ----------

    def _load_phrases(self):
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

    # ---------- UI 构建 ----------

    def _build_ui(self):
        self.container = tk.Frame(self.parent, bg=self.COLOR_BG)
        self.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 工具栏 - 搜索 + 按钮
        toolbar = tk.Frame(self.container, bg=self.COLOR_BG)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        search_shadow = tk.Frame(toolbar, bg="#d9dbe8", bd=0)
        search_shadow.pack(side=tk.LEFT, fill=tk.X, expand=True, ipadx=1, ipady=1)

        search_inner = tk.Frame(search_shadow, bg=self.COLOR_CARD)
        search_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._icon_label(search_inner, "\u2315").pack(side=tk.LEFT, padx=(10, 4))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_inner,
            textvariable=self.search_var,
            font=("Microsoft YaHei UI", 9),
            relief=tk.FLAT, bd=0,
            bg=self.COLOR_CARD, fg=self.COLOR_MUTED,
            insertbackground=self.COLOR_PRIMARY,
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=7)
        self.search_entry.insert(0, "搜索话术...")
        self.search_entry.bind("<FocusIn>", self._clear_placeholder)
        self.search_entry.bind("<FocusOut>", self._restore_placeholder)

        self._make_tool_btn(toolbar, "\u27f3", self.reload, "hint").pack(side=tk.RIGHT, padx=(6, 0))
        self._make_tool_btn(toolbar, "\u270e 编辑", self._open_edit_dialog, "primary").pack(side=tk.RIGHT, padx=(6, 0))

        # 主体：左侧分组 + 右侧话术
        body = tk.Frame(self.container, bg=self.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        # 左侧分组栏
        left = tk.Frame(body, bg=self.COLOR_CARD, width=80,
                        highlightthickness=1, highlightbackground=self.COLOR_BORDER)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        tk.Label(left, text="分组", font=("Microsoft YaHei UI", 7),
                 bg=self.COLOR_CARD, fg=self.COLOR_MUTED, anchor="w"
                 ).pack(fill=tk.X, padx=10, pady=(10, 4))

        self.group_frame = tk.Frame(left, bg=self.COLOR_CARD)
        self.group_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 6))

        # 右侧话术列表
        right = tk.Frame(body, bg=self.COLOR_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.items_canvas = tk.Canvas(right, bg=self.COLOR_BG, highlightthickness=0, bd=0)
        self.items_scrollbar = tk.Scrollbar(right, orient=tk.VERTICAL,
                                            command=self.items_canvas.yview, relief=tk.FLAT, bd=0)
        self.items_frame = tk.Frame(self.items_canvas, bg=self.COLOR_BG)
        self.items_window = self.items_canvas.create_window((0, 0), window=self.items_frame, anchor="nw")

        self.items_canvas.configure(yscrollcommand=self.items_scrollbar.set)
        self.items_frame.bind("<Configure>", self._on_items_configure)
        # 关键：canvas 宽度变化时更新所有卡片的 wraplength
        self.items_canvas.bind("<Configure>", self._on_canvas_configure)
        self.items_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮
        self.items_canvas.bind("<Enter>", lambda e: self.items_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.items_canvas.bind("<Leave>", lambda e: self.items_canvas.unbind_all("<MouseWheel>"))

        self.search_var.trace_add("write", self._on_search)

    def _on_items_configure(self, event):
        self.items_canvas.configure(scrollregion=self.items_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """canvas 宽度变化时同步更新 items_window 宽度并刷新所有卡片 wraplength。"""
        cw = event.width
        self.items_canvas.itemconfigure(self.items_window, width=cw)
        self._sync_wraplengths(cw)

    def _card_wraplength(self, canvas_width):
        """根据当前 canvas 宽度计算内容标签的 wraplength。"""
        w = canvas_width - self.CARD_PAD_X * 2 - 4
        return max(w, 80)

    def _sync_wraplengths(self, canvas_width=None):
        """批量更新所有已渲染卡片的 content 标签 wraplength。"""
        if canvas_width is None:
            canvas_width = self.items_canvas.winfo_width()
        if canvas_width < 60:
            return
        wl = self._card_wraplength(canvas_width)
        for lbl in self._content_widgets:
            try:
                lbl.configure(wraplength=wl)
            except tk.TclError:
                pass

    def _icon_label(self, parent, char):
        return tk.Label(parent, text=char, font=("Segoe UI Symbol", 11),
                        bg=self.COLOR_CARD, fg=self.COLOR_MUTED)

    def _make_tool_btn(self, parent, text, command, style="hint"):
        if style == "primary":
            bg = self.COLOR_PRIMARY
            fg = "#ffffff"
            hover = "#4a5ad9"
            font = ("Microsoft YaHei UI", 9, "bold")
        else:
            bg = self.COLOR_TAG_BG
            fg = self.COLOR_TAG_FG
            hover = "#e4e5ee"
            font = ("Microsoft YaHei UI", 9)
        btn = tk.Button(parent, text=text, font=font, bg=bg, fg=fg,
                        activebackground=hover, activeforeground=fg,
                        relief=tk.FLAT, bd=0, command=command,
                        padx=10, pady=5, cursor="hand2")
        btn.bind("<Enter>", lambda e, b=btn, h=hover: b.configure(bg=h))
        btn.bind("<Leave>", lambda e, b=btn, bg=bg: b.configure(bg=bg))
        return btn

    # ---------- 搜索 ----------

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

    # ---------- 分组 ----------

    def _populate_groups(self):
        for widget in self.group_frame.winfo_children():
            widget.destroy()
        self.group_buttons = []

        groups = self.phrases_data.get("groups", [])
        for idx, group in enumerate(groups):
            is_sel = idx == self.current_group_index
            btn = tk.Label(
                self.group_frame, text=group["name"],
                font=("Microsoft YaHei UI", 8, "bold" if is_sel else "normal"),
                bg=self.COLOR_PRIMARY if is_sel else self.COLOR_CARD,
                fg="white" if is_sel else self.COLOR_TEXT,
                anchor="w", cursor="hand2", padx=8, pady=6,
            )
            btn.pack(fill=tk.X, pady=1)
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
        button.configure(bg=self.COLOR_ACTIVE_BG if enter else self.COLOR_CARD)

    def _select_group(self, idx, refresh_buttons=True):
        self.current_group_index = idx
        if refresh_buttons:
            for i, btn in enumerate(self.group_buttons):
                sel = i == idx
                btn.configure(
                    bg=self.COLOR_PRIMARY if sel else self.COLOR_CARD,
                    fg="white" if sel else self.COLOR_TEXT,
                    font=("Microsoft YaHei UI", 8, "bold" if sel else "normal"),
                )
        group = self.phrases_data["groups"][idx]
        self._show_items(group.get("items", []))

    # ---------- 话术卡片 ----------

    def _show_items(self, items):
        for widget in self.items_frame.winfo_children():
            widget.destroy()
        self._content_widgets = []

        if not items:
            empty = tk.Frame(self.items_frame, bg=self.COLOR_CARD,
                             highlightthickness=1, highlightbackground=self.COLOR_BORDER)
            empty.pack(fill=tk.X, pady=4)
            tk.Label(empty, text="暂无话术", font=("Microsoft YaHei UI", 10, "bold"),
                     fg=self.COLOR_MUTED, bg=self.COLOR_CARD
                     ).pack(anchor="w", padx=14, pady=(14, 2))
            tk.Label(empty, text="点击编辑添加常用回复", font=("Microsoft YaHei UI", 8),
                     fg=self.COLOR_MUTED, bg=self.COLOR_CARD
                     ).pack(anchor="w", padx=14, pady=(0, 14))
            return

        for item in items:
            self._create_phrase_card(item)

        # 渲染完后立即同步一次 wraplength
        self.items_frame.update_idletasks()
        self._sync_wraplengths()

    def _create_phrase_card(self, item):
        """创建一张可点击的话术卡片，宽度撑满，内容动态换行。"""
        row = tk.Frame(
            self.items_frame, bg=self.COLOR_CARD, bd=0,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            highlightcolor=self.COLOR_PRIMARY,
            cursor="hand2",
        )
        row.pack(fill=tk.X, pady=(0, 6))

        # 标题
        title = tk.Label(row, text=item["title"],
                         font=("Microsoft YaHei UI", 9, "bold"),
                         bg=self.COLOR_CARD, fg=self.COLOR_TEXT,
                         anchor="w", cursor="hand2")
        title.pack(fill=tk.X, padx=self.CARD_PAD_X, pady=(9, 2))

        # 内容 — wraplength 初始给一个合理的默认值，之后由 _sync_wraplengths 动态更新
        cw = self.items_canvas.winfo_width()
        init_wl = self._card_wraplength(cw) if cw > 60 else 180

        content = tk.Label(row, text=item["content"],
                           font=("Microsoft YaHei UI", 8),
                           bg=self.COLOR_CARD, fg="#4b4d5c",
                           anchor="w", justify=tk.LEFT,
                           wraplength=init_wl, cursor="hand2")
        content.pack(fill=tk.X, padx=self.CARD_PAD_X, pady=(0, 3))
        self._content_widgets.append(content)

        # 底部提示行
        hint = tk.Label(row, text="点击上屏  \u2192",
                        font=("Microsoft YaHei UI", 7),
                        bg=self.COLOR_CARD, fg=self.COLOR_PRIMARY,
                        anchor="e", cursor="hand2")
        hint.pack(fill=tk.X, padx=self.CARD_PAD_X, pady=(0, 8))

        widgets = (row, title, content, hint)
        for w in widgets:
            w.bind("<Button-1>", lambda e, text=item["content"]: self._copy_phrase(text))
            w.bind("<Enter>", lambda e, ws=widgets: self._card_hover(ws, True))
            w.bind("<Leave>", lambda e, ws=widgets: self._card_hover(ws, False))

    def _card_hover(self, widgets, hover):
        bg = self.COLOR_HOVER if hover else self.COLOR_CARD
        for w in widgets:
            w.configure(bg=bg)

    def _copy_phrase(self, content):
        self.clipboard.write(content)
        if self.on_phrase_click:
            self.on_phrase_click(content)

    # ---------- 搜索 ----------

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

    # ---------- 编辑 ----------

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