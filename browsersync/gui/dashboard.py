"""仪表盘页面 - 浏览器概览与快捷操作."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .app import COLORS, FONTS, CardFrame


class DashboardFrame(tk.Frame):
    """仪表盘主页面."""

    def __init__(self, master, app):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # ── 欢迎区域 ──
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 8))
        tk.Label(header, text="仪表盘", font=FONTS["title"],
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(header, text="跨浏览器书签同步工具 — 概览与快捷操作",
                font=FONTS["body"], fg=COLORS["text_secondary"],
                bg=COLORS["bg"]).pack(anchor="w", pady=(4, 0))

        # ── 快捷操作 ──
        actions_card = CardFrame(self, title="快捷操作")
        actions_card.pack(fill="x", padx=32, pady=(16, 8))

        btn_frame = tk.Frame(actions_card.inner, bg=COLORS["surface"])
        btn_frame.pack(fill="x")

        scan_btn = self._make_action_btn(btn_frame, "📡  扫描浏览器", COLORS["primary"])
        scan_btn.pack(side="left", padx=(0, 12))
        scan_btn.bind("<Button-1>", lambda e: self._do_scan())

        sync_btn = self._make_action_btn(btn_frame, "🚀  一键同步", COLORS["success"])
        sync_btn.pack(side="left", padx=(0, 12))
        sync_btn.bind("<Button-1>", lambda e: self._do_fast_sync())

        config_btn = self._make_action_btn(btn_frame, "⚙️   打开配置", COLORS["warning"])
        config_btn.pack(side="left")
        config_btn.bind("<Button-1>", lambda e: self.app._navigate_to("config"))

        # ── 浏览器概览 ──
        self.browser_card = CardFrame(self, title="浏览器书签概览")
        self.browser_card.pack(fill="both", expand=True, padx=32, pady=(8, 24))

        self._browser_inner = self.browser_card.inner
        self._loading_label = tk.Label(self._browser_inner,
                                       text="点击上方「扫描浏览器」查看书签状态",
                                       font=FONTS["body"],
                                       fg=COLORS["text_secondary"],
                                       bg=COLORS["surface"])
        self._loading_label.pack(pady=40)

    def _make_action_btn(self, master, text, color):
        frame = tk.Frame(master, bg=color, cursor="hand2", padx=20, pady=10)
        lbl = tk.Label(frame, text=text, font=FONTS["body"],
                      fg=COLORS["text"], bg=color)
        lbl.pack()

        def on_enter(e):
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            r = min(255, int(r * 1.15))
            g = min(255, int(g * 1.15))
            b = min(255, int(b * 1.15))
            frame.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
            lbl.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
        def on_leave(e):
            frame.configure(bg=color)
            lbl.configure(bg=color)

        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)
        return frame

    def _do_scan(self):
        self._loading_label.configure(text="扫描中...")
        self.app.run_scan(callback=self._on_scan_result)

    def _on_scan_result(self, results):
        # 清除旧内容
        for w in self._browser_inner.winfo_children():
            w.destroy()

        if not results:
            tk.Label(self._browser_inner, text="没有检测到浏览器或读取失败",
                    font=FONTS["body"], fg=COLORS["text_secondary"],
                    bg=COLORS["surface"]).pack(pady=40)
            return

        # 标题行
        header = tk.Frame(self._browser_inner, bg=COLORS["surface"])
        header.pack(fill="x", pady=(0, 8))
        for col, w, align in [("浏览器", 200, "w"), ("类型", 100, "w"),
                              ("书签数量", 120, "e"), ("状态", 100, "w")]:
            lbl = tk.Label(header, text=col, font=FONTS["small"],
                          fg=COLORS["text_secondary"], bg=COLORS["surface"],
                          width=w//8, anchor=align)
            lbl.pack(side="left")

        ttk.Separator(self._browser_inner, orient="horizontal").pack(fill="x")

        # 数据行
        for name, count, status in results:
            row = tk.Frame(self._browser_inner, bg=COLORS["surface"])
            row.pack(fill="x", pady=4)

            icon = "🔵" if "chrom" in self.app.cfg.get("browsers", {}).get(name, {}).get("type", "") else "🟡"
            type_str = self.app.cfg.get("browsers", {}).get(name, {}).get("type", "unknown")

            color = COLORS["success"] if status == "ok" else \
                    COLORS["warning"] if status == "permission_error" else COLORS["error"]
            status_text = "✅" if status == "ok" else \
                         "⚠️" if status == "permission_error" else "❌"

            tk.Label(row, text=f"  {icon} {name}", font=FONTS["body"],
                    fg=COLORS["text"], bg=COLORS["surface"],
                    width=25, anchor="w").pack(side="left")
            tk.Label(row, text=type_str, font=FONTS["small"],
                    fg=COLORS["text_secondary"], bg=COLORS["surface"],
                    width=12, anchor="w").pack(side="left")
            tk.Label(row, text=str(count) if status == "ok" else "-",
                    font=FONTS["body"], fg=COLORS["text"],
                    bg=COLORS["surface"], width=15, anchor="e").pack(side="left")
            tk.Label(row, text=status_text, font=FONTS["body"],
                    fg=color, bg=COLORS["surface"],
                    width=10, anchor="w").pack(side="left")

        # 总计
        ttk.Separator(self._browser_inner, orient="horizontal").pack(fill="x", pady=(8, 0))
        total = sum(c for _, c, s in results if s == "ok")
        total_frame = tk.Frame(self._browser_inner, bg=COLORS["surface"])
        total_frame.pack(fill="x", pady=8)
        tk.Label(total_frame, text=f"  总计: {total} 书签 (来自 {len(results)} 个浏览器)",
                font=FONTS["subheading"], fg=COLORS["primary"],
                bg=COLORS["surface"]).pack(anchor="w")

    def _do_fast_sync(self):
        # 快速同步：使用配置中的设置
        mode = self.app.cfg.get("mode", "merge")
        self.app.run_full_sync(mode=mode)
