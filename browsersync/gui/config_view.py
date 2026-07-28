"""配置管理页面."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .app import COLORS, FONTS, CardFrame
from ..config import save_config


class ConfigFrame(tk.Frame):
    """配置管理页面 — 浏览器管理、偏好设置。"""

    def __init__(self, master, app):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # ── 标题 ──
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 8))
        tk.Label(header, text="配置管理", font=FONTS["title"],
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(header, text="管理浏览器和同步偏好设置",
                font=FONTS["body"], fg=COLORS["text_secondary"],
                bg=COLORS["bg"]).pack(anchor="w", pady=(4, 0))

        # ── 浏览器管理 ──
        browser_card = CardFrame(self, title="浏览器管理")
        browser_card.pack(fill="x", padx=32, pady=(16, 8))

        self._browser_rows = []
        from ..detector import get_enabled_browsers
        browsers = dict(get_enabled_browsers(self.app.cfg))

        for name, info in browsers.items():
            row = self._build_browser_row(browser_card.inner, name, info)
            row.pack(fill="x", pady=4)
            self._browser_rows.append(row)

        # ── 同步偏好设置 ──
        pref_card = CardFrame(self, title="同步偏好设置")
        pref_card.pack(fill="x", padx=32, pady=(8, 24))

        self._build_preferences(pref_card.inner)

    def _build_browser_row(self, master, name, info):
        row = tk.Frame(master, bg=COLORS["surface_light"], padx=12, pady=8)
        row.configure(cursor="hand2")

        # 状态指示
        enabled = self.app.cfg.get("browsers", {}).get(name, {}).get("enabled", False)

        status_canvas = tk.Canvas(row, width=12, height=12,
                                  bg=COLORS["surface_light"],
                                  highlightthickness=0)
        status_canvas.pack(side="left")
        color = COLORS["success"] if enabled else COLORS["text_secondary"]
        status_canvas.create_oval(2, 2, 10, 10, fill=color, outline="")

        # 名称和类型
        tk.Label(row, text=name, font=FONTS["body"],
                fg=COLORS["text"], bg=COLORS["surface_light"],
                width=18, anchor="w").pack(side="left", padx=(8, 4))
        tk.Label(row, text=f"({info['type']})", font=FONTS["small"],
                fg=COLORS["text_secondary"], bg=COLORS["surface_light"],
                width=10, anchor="w").pack(side="left")

        # 路径
        path = info.get("path", "")
        path_label = tk.Label(row, text=path, font=FONTS["mono"],
                             fg=COLORS["text_secondary"],
                             bg=COLORS["surface_light"],
                             anchor="w", padx=8)
        path_label.pack(side="left", fill="x", expand=True)

        # 启用/禁用开关
        var = tk.BooleanVar(value=enabled)
        def make_toggle(n=name, v=var, sc=status_canvas):
            def toggle():
                self.app.cfg["browsers"][n]["enabled"] = v.get()
                save_config(self.app.cfg)
                sc.delete("all")
                c = COLORS["success"] if v.get() else COLORS["text_secondary"]
                sc.create_oval(2, 2, 10, 10, fill=c, outline="")
                self.app.log(f"{'启用' if v.get() else '禁用'}浏览器: {n}", "info")
            return toggle

        toggle_btn = tk.Checkbutton(row, variable=var,
                                    command=make_toggle(name, var, status_canvas),
                                    bg=COLORS["surface_light"],
                                    activebackground=COLORS["surface_light"],
                                    selectcolor=COLORS["surface_light"])
        toggle_btn.pack(side="right")

        return row

    def _build_preferences(self, master):
        # 基准浏览器
        tk.Label(master, text="基准浏览器", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, 8))

        base_frame = tk.Frame(master, bg=COLORS["surface"])
        base_frame.pack(fill="x")

        from ..detector import get_enabled_browsers
        browsers = dict(get_enabled_browsers(self.app.cfg))
        browser_names = list(browsers.keys())

        self._base_var = tk.StringVar(value=self.app.cfg.get("base_browser") or "")
        if self._base_var.get() not in browser_names and browser_names:
            self._base_var.set(browser_names[0])

        for name in browser_names:
            rb = tk.Radiobutton(base_frame, text=f"  {name}",
                               variable=self._base_var, value=name,
                               font=FONTS["body"], fg=COLORS["text"],
                               bg=COLORS["surface"],
                               selectcolor=COLORS["primary"],
                               activebackground=COLORS["surface"],
                               activeforeground=COLORS["text"])
            rb.pack(anchor="w", pady=2)

        ttk.Separator(master, orient="horizontal").pack(fill="x", pady=12)

        # 同步模式
        tk.Label(master, text="默认同步模式", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, 8))

        mode_frame = tk.Frame(master, bg=COLORS["surface"])
        mode_frame.pack(fill="x")

        self._mode_var = tk.StringVar(value=self.app.cfg.get("mode", "merge"))

        for val, label in [("merge", "  合并去重"),
                           ("mirror", "  镜像 (所有浏览器一致)")]:
            rb = tk.Radiobutton(mode_frame, text=label,
                               variable=self._mode_var, value=val,
                               font=FONTS["body"], fg=COLORS["text"],
                               bg=COLORS["surface"],
                               selectcolor=COLORS["primary"],
                               activebackground=COLORS["surface"],
                               activeforeground=COLORS["text"])
            rb.pack(anchor="w", pady=2)

        ttk.Separator(master, orient="horizontal").pack(fill="x", pady=12)

        # 保存按钮
        btn_frame = tk.Frame(master, bg=COLORS["surface"])
        btn_frame.pack(fill="x")

        save_btn = tk.Frame(btn_frame, bg=COLORS["primary"], cursor="hand2",
                           padx=28, pady=10)
        tk.Label(save_btn, text="保存配置", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["primary"]).pack()
        save_btn.pack(side="right")
        save_btn.bind("<Button-1>", lambda e: self._save_config())

    def _save_config(self):
        base = self._base_var.get()
        mode = self._mode_var.get()

        if base:
            self.app.cfg["base_browser"] = base
        self.app.cfg["mode"] = mode

        save_config(self.app.cfg)
        mode_label = "镜像" if mode == "mirror" else "合并去重"
        self.app.log(f"配置已保存: 基准={base}, 模式={mode_label}", "success")
        messagebox.showinfo("配置已保存",
                          f"基准浏览器: {base or '(自动选择)'}\n"
                          f"同步模式: {mode_label}\n\n"
                          "配置已保存成功。")
