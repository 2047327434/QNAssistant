"""话术编辑对话框 - 分组和话术增删改"""
import tkinter as tk
from tkinter import ttk, messagebox


class EditDialog:
    """编辑分组名称和话术内容。"""

    COLOR_PRIMARY = "#1677ff"
    COLOR_BG = "#f5f8fc"
    COLOR_CARD = "#ffffff"
    COLOR_TEXT = "#111827"
    COLOR_MUTED = "#6b7280"
    COLOR_BORDER = "#d8e2ef"

    def __init__(self, parent, phrases_data):
        self.result = None
        self.phrases_data = {
            "groups": [
                {
                    "name": g.get("name", "未命名分组"),
                    "items": [
                        {"title": i.get("title", ""), "content": i.get("content", "")}
                        for i in g.get("items", [])
                    ]
                }
                for g in phrases_data.get("groups", [])
            ]
        }

        self.top = tk.Toplevel(parent)
        self.top.title("编辑话术")
        self.top.geometry("620x500")
        self.top.minsize(560, 430)
        self.top.configure(bg=self.COLOR_BG)
        self.top.grab_set()

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style(self.top)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            font=("Microsoft YaHei UI", 9),
            rowheight=28,
            background=self.COLOR_CARD,
            fieldbackground=self.COLOR_CARD,
            foreground=self.COLOR_TEXT,
            bordercolor=self.COLOR_BORDER,
            lightcolor=self.COLOR_BORDER,
            darkcolor=self.COLOR_BORDER
        )
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#edf3fb", foreground=self.COLOR_TEXT)
        style.map("Treeview", background=[("selected", self.COLOR_PRIMARY)], foreground=[("selected", "white")])

    def _build_ui(self):
        header = tk.Frame(self.top, bg=self.COLOR_BG)
        header.pack(fill=tk.X, padx=16, pady=(14, 8))
        tk.Label(header, text="编辑话术库", font=("Microsoft YaHei UI", 14, "bold"), bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(anchor="w")
        tk.Label(header, text="分组和话术会保存到工具根目录 phrases.txt", font=("Microsoft YaHei UI", 8), bg=self.COLOR_BG, fg=self.COLOR_MUTED).pack(anchor="w", pady=(2, 0))

        group_frame = self._make_section(self.top, "分组")
        group_frame.pack(fill=tk.X, padx=16, pady=(0, 10))

        self.group_listbox = tk.Listbox(
            group_frame,
            height=5,
            font=("Microsoft YaHei UI", 9),
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            bg=self.COLOR_CARD,
            fg=self.COLOR_TEXT,
            selectbackground=self.COLOR_PRIMARY,
            selectforeground="white"
        )
        self.group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 8), pady=12)
        self.group_listbox.bind("<<ListboxSelect>>", lambda e: self._refresh_items())

        group_buttons = tk.Frame(group_frame, bg=self.COLOR_CARD)
        group_buttons.pack(side=tk.RIGHT, padx=(0, 12), pady=12)
        self._make_button(group_buttons, "新增", self._add_group).pack(fill=tk.X, pady=2)
        self._make_button(group_buttons, "改名", self._rename_group).pack(fill=tk.X, pady=2)
        self._make_button(group_buttons, "删除", self._delete_group, danger=True).pack(fill=tk.X, pady=2)

        item_frame = self._make_section(self.top, "话术")
        item_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        columns = ("title", "content")
        self.item_tree = ttk.Treeview(item_frame, columns=columns, show="headings", height=10)
        self.item_tree.heading("title", text="标题")
        self.item_tree.heading("content", text="内容预览")
        self.item_tree.column("title", width=150, anchor="w")
        self.item_tree.column("content", width=360, anchor="w")
        self.item_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 6), pady=12)

        scroll = ttk.Scrollbar(item_frame, orient=tk.VERTICAL, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.LEFT, fill=tk.Y, pady=12)

        item_buttons = tk.Frame(item_frame, bg=self.COLOR_CARD)
        item_buttons.pack(side=tk.RIGHT, padx=(8, 12), pady=12)
        self._make_button(item_buttons, "新增", self._add_item).pack(fill=tk.X, pady=2)
        self._make_button(item_buttons, "编辑", self._edit_item).pack(fill=tk.X, pady=2)
        self._make_button(item_buttons, "删除", self._delete_item, danger=True).pack(fill=tk.X, pady=2)

        bottom = tk.Frame(self.top, bg=self.COLOR_BG)
        bottom.pack(fill=tk.X, padx=16, pady=(0, 14))
        tk.Label(bottom, text="保存后立即写入 phrases.txt", fg=self.COLOR_MUTED, bg=self.COLOR_BG, font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT)
        self._make_button(bottom, "保存", self._save, primary=True, width=10).pack(side=tk.RIGHT, padx=(8, 0))
        self._make_button(bottom, "取消", self.top.destroy, width=10).pack(side=tk.RIGHT)

        self._refresh_groups()

    def _make_section(self, parent, title):
        outer = tk.Frame(parent, bg=self.COLOR_CARD, highlightthickness=1, highlightbackground=self.COLOR_BORDER)
        tk.Label(outer, text=title, font=("Microsoft YaHei UI", 9, "bold"), bg=self.COLOR_CARD, fg=self.COLOR_TEXT, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 0))
        return outer

    def _make_button(self, parent, text, command, primary=False, danger=False, width=7):
        bg = self.COLOR_PRIMARY if primary else ("#fee2e2" if danger else "#eef4fb")
        fg = "white" if primary else ("#b91c1c" if danger else self.COLOR_TEXT)
        active = "#0f5fd7" if primary else ("#fecaca" if danger else "#dde9f7")
        return tk.Button(
            parent,
            text=text,
            width=width,
            command=command,
            relief=tk.FLAT,
            bd=0,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            padx=8,
            pady=5
        )

    def _refresh_groups(self, select_index=0):
        self.group_listbox.delete(0, tk.END)
        for group in self.phrases_data["groups"]:
            self.group_listbox.insert(tk.END, group["name"])
        if self.phrases_data["groups"]:
            idx = min(select_index, len(self.phrases_data["groups"]) - 1)
            self.group_listbox.select_set(idx)
        self._refresh_items()

    def _refresh_items(self):
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)
        group, _ = self._selected_group()
        if not group:
            return
        for item in group.get("items", []):
            self.item_tree.insert("", tk.END, values=(item.get("title", ""), item.get("content", "")[:90]))

    def _selected_group(self):
        selection = self.group_listbox.curselection()
        if not selection:
            return None, -1
        idx = selection[0]
        if idx >= len(self.phrases_data["groups"]):
            return None, -1
        return self.phrases_data["groups"][idx], idx

    def _selected_item(self):
        group, group_idx = self._selected_group()
        if not group:
            return None, -1, group, group_idx
        selection = self.item_tree.selection()
        if not selection:
            return None, -1, group, group_idx
        idx = self.item_tree.index(selection[0])
        if idx >= len(group.get("items", [])):
            return None, -1, group, group_idx
        return group["items"][idx], idx, group, group_idx

    def _add_group(self):
        name = self._ask_text("新增分组", "分组名称：")
        if name:
            self.phrases_data["groups"].append({"name": name, "items": []})
            self._refresh_groups(len(self.phrases_data["groups"]) - 1)

    def _rename_group(self):
        group, idx = self._selected_group()
        if not group:
            return
        name = self._ask_text("分组改名", "新的分组名称：", group["name"])
        if name:
            group["name"] = name
            self._refresh_groups(idx)

    def _delete_group(self):
        group, idx = self._selected_group()
        if not group:
            return
        if messagebox.askyesno("确认删除", f"删除分组「{group['name']}」及其所有话术？"):
            self.phrases_data["groups"].pop(idx)
            self._refresh_groups(max(0, idx - 1))

    def _add_item(self):
        group, _ = self._selected_group()
        if not group:
            messagebox.showwarning("提示", "请先选择分组")
            return
        result = self._ask_phrase("新增话术")
        if result:
            group.setdefault("items", []).append(result)
            self._refresh_items()

    def _edit_item(self):
        item, idx, group, _ = self._selected_item()
        if not item:
            return
        result = self._ask_phrase("编辑话术", item.get("title", ""), item.get("content", ""))
        if result:
            group["items"][idx] = result
            self._refresh_items()

    def _delete_item(self):
        item, idx, group, _ = self._selected_item()
        if not item:
            return
        if messagebox.askyesno("确认删除", f"删除话术「{item.get('title', '')}」？"):
            group["items"].pop(idx)
            self._refresh_items()

    def _ask_text(self, title, label, initial=""):
        result = {"value": None}
        dialog = tk.Toplevel(self.top)
        dialog.title(title)
        dialog.geometry("340x150")
        dialog.configure(bg=self.COLOR_BG)
        dialog.grab_set()
        tk.Label(dialog, text=label, font=("Microsoft YaHei UI", 9), bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(anchor="w", padx=14, pady=(14, 5))
        entry = tk.Entry(dialog, font=("Microsoft YaHei UI", 10), relief=tk.FLAT, bd=0, bg="white")
        entry.pack(fill=tk.X, padx=14, ipady=6)
        entry.insert(0, initial)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def ok():
            result["value"] = entry.get().strip()
            dialog.destroy()

        entry.bind("<Return>", lambda e: ok())
        self._make_button(dialog, "确定", ok, primary=True, width=10).pack(pady=12)
        self.top.wait_window(dialog)
        return result["value"]

    def _ask_phrase(self, title, initial_title="", initial_content=""):
        result = {"value": None}
        dialog = tk.Toplevel(self.top)
        dialog.title(title)
        dialog.geometry("460x320")
        dialog.configure(bg=self.COLOR_BG)
        dialog.grab_set()

        tk.Label(dialog, text="标题：", font=("Microsoft YaHei UI", 9), bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(anchor="w", padx=14, pady=(14, 5))
        title_entry = tk.Entry(dialog, font=("Microsoft YaHei UI", 10), relief=tk.FLAT, bd=0, bg="white")
        title_entry.pack(fill=tk.X, padx=14, ipady=6)
        title_entry.insert(0, initial_title)

        tk.Label(dialog, text="内容：", font=("Microsoft YaHei UI", 9), bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(anchor="w", padx=14, pady=(12, 5))
        content_text = tk.Text(dialog, font=("Microsoft YaHei UI", 10), height=7, relief=tk.FLAT, bd=0, bg="white", wrap=tk.WORD)
        content_text.pack(fill=tk.BOTH, expand=True, padx=14)
        content_text.insert("1.0", initial_content)

        def ok():
            title_value = title_entry.get().strip()
            content_value = content_text.get("1.0", tk.END).strip()
            if not content_value:
                messagebox.showwarning("提示", "话术内容不能为空")
                return
            result["value"] = {"title": title_value or content_value[:20], "content": content_value}
            dialog.destroy()

        self._make_button(dialog, "确定", ok, primary=True, width=10).pack(pady=12)
        self.top.wait_window(dialog)
        return result["value"]

    def _save(self):
        self.result = self.phrases_data
        self.top.destroy()
