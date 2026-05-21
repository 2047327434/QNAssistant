"""话术编辑对话框 - 分组和话术增删改"""
import tkinter as tk
from tkinter import ttk, messagebox


class EditDialog:
    """编辑分组名称和话术内容。"""

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
        self.top.geometry("560x460")
        self.top.minsize(500, 400)
        self.top.grab_set()

        self._build_ui()

    def _build_ui(self):
        group_frame = tk.LabelFrame(self.top, text="分组", font=("Microsoft YaHei UI", 9))
        group_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.group_listbox = tk.Listbox(group_frame, height=5, font=("Microsoft YaHei UI", 9), activestyle="none")
        self.group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)
        self.group_listbox.bind("<<ListboxSelect>>", lambda e: self._refresh_items())

        group_buttons = tk.Frame(group_frame)
        group_buttons.pack(side=tk.RIGHT, padx=(4, 8), pady=8)
        tk.Button(group_buttons, text="新增", width=6, command=self._add_group).pack(pady=2)
        tk.Button(group_buttons, text="改名", width=6, command=self._rename_group).pack(pady=2)
        tk.Button(group_buttons, text="删除", width=6, command=self._delete_group).pack(pady=2)

        item_frame = tk.LabelFrame(self.top, text="话术", font=("Microsoft YaHei UI", 9))
        item_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("title", "content")
        self.item_tree = ttk.Treeview(item_frame, columns=columns, show="headings", height=10)
        self.item_tree.heading("title", text="标题")
        self.item_tree.heading("content", text="内容")
        self.item_tree.column("title", width=120, anchor="w")
        self.item_tree.column("content", width=330, anchor="w")
        self.item_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)

        scroll = ttk.Scrollbar(item_frame, orient=tk.VERTICAL, command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.LEFT, fill=tk.Y, pady=8)

        item_buttons = tk.Frame(item_frame)
        item_buttons.pack(side=tk.RIGHT, padx=(4, 8), pady=8)
        tk.Button(item_buttons, text="新增", width=6, command=self._add_item).pack(pady=2)
        tk.Button(item_buttons, text="编辑", width=6, command=self._edit_item).pack(pady=2)
        tk.Button(item_buttons, text="删除", width=6, command=self._delete_item).pack(pady=2)

        bottom = tk.Frame(self.top)
        bottom.pack(fill=tk.X, padx=10, pady=(5, 10))
        tk.Label(bottom, text="保存后会写入工具根目录 phrases.txt", fg="#666", font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT)
        tk.Button(bottom, text="保存", width=10, command=self._save).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom, text="取消", width=10, command=self.top.destroy).pack(side=tk.RIGHT)

        self._refresh_groups()

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
            self.item_tree.insert("", tk.END, values=(item.get("title", ""), item.get("content", "")[:80]))

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
        dialog.geometry("320x130")
        dialog.grab_set()
        tk.Label(dialog, text=label, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=12, pady=(12, 4))
        entry = tk.Entry(dialog, font=("Microsoft YaHei UI", 10))
        entry.pack(fill=tk.X, padx=12)
        entry.insert(0, initial)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def ok():
            result["value"] = entry.get().strip()
            dialog.destroy()

        entry.bind("<Return>", lambda e: ok())
        tk.Button(dialog, text="确定", command=ok).pack(pady=10)
        self.top.wait_window(dialog)
        return result["value"]

    def _ask_phrase(self, title, initial_title="", initial_content=""):
        result = {"value": None}
        dialog = tk.Toplevel(self.top)
        dialog.title(title)
        dialog.geometry("430x280")
        dialog.grab_set()

        tk.Label(dialog, text="标题：", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=12, pady=(12, 4))
        title_entry = tk.Entry(dialog, font=("Microsoft YaHei UI", 10))
        title_entry.pack(fill=tk.X, padx=12)
        title_entry.insert(0, initial_title)

        tk.Label(dialog, text="内容：", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=12, pady=(10, 4))
        content_text = tk.Text(dialog, font=("Microsoft YaHei UI", 10), height=6)
        content_text.pack(fill=tk.BOTH, expand=True, padx=12)
        content_text.insert("1.0", initial_content)

        def ok():
            title_value = title_entry.get().strip()
            content_value = content_text.get("1.0", tk.END).strip()
            if not content_value:
                messagebox.showwarning("提示", "话术内容不能为空")
                return
            result["value"] = {"title": title_value or content_value[:20], "content": content_value}
            dialog.destroy()

        tk.Button(dialog, text="确定", command=ok).pack(pady=10)
        self.top.wait_window(dialog)
        return result["value"]

    def _save(self):
        self.result = self.phrases_data
        self.top.destroy()
