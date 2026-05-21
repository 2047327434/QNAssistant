"""话术面板 - txt存储、分组展示、点击复制并交给主窗口自动上屏"""
import tkinter as tk
from core.clipboard_ops import ClipboardOps


class PhrasesPanel:
    """话术面板：从工具根目录 phrases.txt 读取，点击话术复制到剪贴板并触发回调。"""

    def __init__(self, parent, phrases_path, on_phrase_click=None):
        self.parent = parent
        self.phrases_path = phrases_path
        self.on_phrase_click = on_phrase_click
        self.clipboard = ClipboardOps()
        self.current_group_index = 0

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
            if not line:
                continue
            if line.startswith("#"):
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
        # 顶部工具栏
        toolbar = tk.Frame(self.parent, bg="#f7f8fa")
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(toolbar, textvariable=self.search_var, font=("Microsoft YaHei UI", 9), relief=tk.FLAT)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.search_entry.insert(0, "搜索话术...")
        self.search_entry.bind("<FocusIn>", self._clear_placeholder)
        self.search_entry.bind("<FocusOut>", self._restore_placeholder)

        tk.Button(toolbar, text="编辑", font=("Microsoft YaHei UI", 9), relief=tk.FLAT, command=self._open_edit_dialog).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(toolbar, text="刷新", font=("Microsoft YaHei UI", 9), relief=tk.FLAT, command=self.reload).pack(side=tk.RIGHT, padx=(6, 0))

        # 内容区
        content = tk.Frame(self.parent, bg="white")
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.group_listbox = tk.Listbox(
            content, width=12, font=("Microsoft YaHei UI", 9), relief=tk.FLAT,
            borderwidth=0, activestyle="none", selectbackground="#2f80ed", selectforeground="white"
        )
        self.group_listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.group_listbox.bind("<<ListboxSelect>>", self._on_group_select)

        right = tk.Frame(content, bg="white")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.items_canvas = tk.Canvas(right, bg="white", highlightthickness=0)
        self.items_scrollbar = tk.Scrollbar(right, orient=tk.VERTICAL, command=self.items_canvas.yview)
        self.items_frame = tk.Frame(self.items_canvas, bg="white")
        self.items_window = self.items_canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        self.items_canvas.configure(yscrollcommand=self.items_scrollbar.set)
        self.items_frame.bind("<Configure>", lambda e: self.items_canvas.configure(scrollregion=self.items_canvas.bbox("all")))
        self.items_canvas.bind("<Configure>", lambda e: self.items_canvas.itemconfigure(self.items_window, width=e.width))
        self.items_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.items_canvas.bind("<Enter>", lambda e: self.items_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.items_canvas.bind("<Leave>", lambda e: self.items_canvas.unbind_all("<MouseWheel>"))
        self.search_var.trace_add("write", self._on_search)

    def _clear_placeholder(self, event):
        if self.search_var.get() == "搜索话术...":
            self.search_var.set("")

    def _restore_placeholder(self, event):
        if not self.search_var.get().strip():
            self.search_var.set("搜索话术...")

    def _on_mousewheel(self, event):
        self.items_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _populate_groups(self):
        self.group_listbox.delete(0, tk.END)
        for group in self.phrases_data.get("groups", []):
            self.group_listbox.insert(tk.END, group["name"])
        if self.phrases_data.get("groups"):
            idx = min(self.current_group_index, len(self.phrases_data["groups"]) - 1)
            self.group_listbox.select_set(idx)
            self.current_group_index = idx
            self._show_items(self.phrases_data["groups"][idx].get("items", []))
        else:
            self._show_items([])

    def _on_group_select(self, event):
        selection = self.group_listbox.curselection()
        if not selection:
            return
        self.current_group_index = selection[0]
        group = self.phrases_data["groups"][self.current_group_index]
        self._show_items(group.get("items", []))

    def _show_items(self, items):
        for widget in self.items_frame.winfo_children():
            widget.destroy()

        if not items:
            tk.Label(self.items_frame, text="暂无话术", font=("Microsoft YaHei UI", 9), fg="#888", bg="white").pack(anchor="w", pady=10)
            return

        for item in items:
            row = tk.Frame(self.items_frame, bg="white", bd=1, relief=tk.SOLID)
            row.pack(fill=tk.X, pady=4)

            title = tk.Label(row, text=item["title"], font=("Microsoft YaHei UI", 9, "bold"), bg="white", anchor="w")
            title.pack(fill=tk.X, padx=8, pady=(6, 1))
            content = tk.Label(row, text=item["content"], font=("Microsoft YaHei UI", 9), bg="white", fg="#333", anchor="w", justify=tk.LEFT, wraplength=160)
            content.pack(fill=tk.X, padx=8, pady=(0, 6))

            for w in (row, title, content):
                w.bind("<Button-1>", lambda e, text=item["content"]: self._copy_phrase(text))
                w.bind("<Enter>", lambda e, r=row: r.configure(bg="#eef6ff"))
                w.bind("<Leave>", lambda e, r=row: r.configure(bg="white"))

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
