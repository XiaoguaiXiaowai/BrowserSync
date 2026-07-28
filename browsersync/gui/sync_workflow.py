"""同步工作台 - 三步流程引导界面."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .app import COLORS, FONTS, CardFrame


class SyncWorkflowFrame(tk.Frame):
    """同步工作台页面 — 一站式 collect → merge/mirror → push。"""

    def __init__(self, master, app):
        super().__init__(master, bg=COLORS["bg"])
        self.app = app
        self._step = 0  # 0=准备, 1=collect, 2=merge, 3=push
        self._mode_var = tk.StringVar(value=app.cfg.get("mode", "merge"))
        self._dry_run_var = tk.BooleanVar(value=False)
        self._selected_browsers = []
        self._collections = {}
        self._merged = None
        self._base_browser = None

        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # ── 标题 ──
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 8))
        tk.Label(header, text="同步工作台", font=FONTS["title"],
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(header, text="三步完成跨浏览器书签同步",
                font=FONTS["body"], fg=COLORS["text_secondary"],
                bg=COLORS["bg"]).pack(anchor="w", pady=(4, 0))

        # ── 步骤指示器 ──
        self._step_frame = tk.Frame(self, bg=COLORS["bg"])
        self._step_frame.pack(fill="x", padx=32, pady=(16, 8))

        self._step_labels = []
        steps = [
            ("📥", "Step 1", "收集书签"),
            ("🔄", "Step 2", "合并/镜像"),
            ("📤", "Step 3", "推送结果"),
        ]
        for i, (icon, title, desc) in enumerate(steps):
            step_item = tk.Frame(self._step_frame, bg=COLORS["bg"])
            step_item.pack(side="left", fill="x", expand=True)

            circle = tk.Canvas(step_item, width=36, height=36,
                              bg=COLORS["bg"], highlightthickness=0)
            circle.pack()
            self._step_labels.append({
                "circle": circle,
                "icon": icon,
                "title": title,
                "desc": desc,
                "active": False,
            })

            tk.Label(step_item, text=title, font=FONTS["small"],
                    fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack()
            tk.Label(step_item, text=desc, font=FONTS["body"],
                    fg=COLORS["text"], bg=COLORS["bg"]).pack()

            if i < len(steps) - 1:
                sep = tk.Frame(step_item, height=2, bg=COLORS["border"])
                sep.pack(side="right", fill="x", expand=True, padx=8)

        self._update_steps()

        # ── 内容区域 ──
        self._content = tk.Frame(self, bg=COLORS["bg"])
        self._content.pack(fill="both", expand=True, padx=32, pady=(8, 24))

        self._show_step(0)

    def _update_steps(self):
        for i, s in enumerate(self._step_labels):
            s["circle"].delete("all")
            active = i < self._step
            color = COLORS["success"] if active else \
                    COLORS["primary"] if i == self._step else COLORS["surface_light"]
            text_color = COLORS["text"] if i <= self._step else COLORS["text_secondary"]
            s["circle"].create_oval(4, 4, 32, 32, fill=color, outline="")
            s["circle"].create_text(18, 18, text=s["icon"], fill=COLORS["text"],
                                   font=("Helvetica", 12))
            # 更新下方的文字颜色
            for widget in s["circle"].master.winfo_children():
                if isinstance(widget, tk.Label):
                    if widget.cget("text") in (s["title"], s["desc"]):
                        widget.configure(fg=text_color)

    def _show_step(self, step):
        for w in self._content.winfo_children():
            w.destroy()

        if step == 0:
            self._show_prepare()
        elif step == 1:
            self._show_collect()
        elif step == 2:
            self._show_merge()
        elif step == 3:
            self._show_push()

    # ── Step 0: 准备 ─────────────────────────────────────────────────

    def _show_prepare(self):
        card = CardFrame(self._content, title="同步参数配置")
        card.pack(fill="both", expand=True)

        # 浏览器选择
        tk.Label(card.inner, text="目标浏览器", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, 8))

        self._browser_vars = {}
        from ..detector import get_enabled_browsers
        targets = dict(get_enabled_browsers(self.app.cfg))
        for name, info in targets.items():
            var = tk.BooleanVar(value=True)
            self._browser_vars[name] = var
            cb = tk.Checkbutton(card.inner, text=f"  {name} ({info['type']})",
                               variable=var, font=FONTS["body"],
                               fg=COLORS["text"], bg=COLORS["surface"],
                               selectcolor=COLORS["surface"],
                               activebackground=COLORS["surface"],
                               activeforeground=COLORS["text"],
                               padx=8, pady=2)
            cb.pack(anchor="w")

        ttk.Separator(card.inner, orient="horizontal").pack(fill="x", pady=12)

        # 模式选择
        tk.Label(card.inner, text="同步模式", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, 8))

        mode_frame = tk.Frame(card.inner, bg=COLORS["surface"])
        mode_frame.pack(fill="x")

        for val, label in [("merge", "合并去重 (保留各浏览器的增量)"),
                           ("mirror", "镜像 (所有浏览器与基准浏览器完全一致)")]:
            rb = tk.Radiobutton(mode_frame, text=f"  {label}", variable=self._mode_var,
                               value=val, font=FONTS["body"],
                               fg=COLORS["text"], bg=COLORS["surface"],
                               selectcolor=COLORS["primary"],
                               activebackground=COLORS["surface"],
                               activeforeground=COLORS["text"])
            rb.pack(anchor="w", pady=2)

        ttk.Separator(card.inner, orient="horizontal").pack(fill="x", pady=12)

        # Dry-run 选项
        dry_frame = tk.Frame(card.inner, bg=COLORS["surface"])
        dry_frame.pack(fill="x")
        tk.Checkbutton(dry_frame, text="  Dry-run (仅预览，不实际写入)",
                      variable=self._dry_run_var, font=FONTS["body"],
                      fg=COLORS["text"], bg=COLORS["surface"],
                      selectcolor=COLORS["surface"],
                      activebackground=COLORS["surface"],
                      activeforeground=COLORS["text"]).pack(anchor="w")

        # 按钮
        btn_frame = tk.Frame(self._content, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(12, 0))

        start_btn = tk.Frame(btn_frame, bg=COLORS["primary"], cursor="hand2",
                            padx=28, pady=10)
        tk.Label(start_btn, text="开始同步 →", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["primary"]).pack()
        start_btn.pack(side="right")
        start_btn.bind("<Button-1>", lambda e: self._start_sync())

    def _start_sync(self):
        self._selected_browsers = [
            name for name, var in self._browser_vars.items() if var.get()
        ]
        if not self._selected_browsers:
            self.app.log("请至少选择一个浏览器", "warning")
            return
        self._step = 1
        self._update_steps()
        self._show_step(1)

    # ── Step 1: Collect ──────────────────────────────────────────────

    def _show_collect(self):
        card = CardFrame(self._content, title="Step 1: 收集书签")
        card.pack(fill="both", expand=True)

        info = tk.Label(card.inner,
                       text=f"正在从 {len(self._selected_browsers)} 个浏览器收集书签...",
                       font=FONTS["body"], fg=COLORS["text_secondary"],
                       bg=COLORS["surface"])
        info.pack(pady=20)

        btn_frame = tk.Frame(self._content, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(12, 0))

        self.app.run_collect(
            browser_names=self._selected_browsers,
            callback=lambda collections: self._on_collect_done(collections))

    def _on_collect_done(self, collections):
        self._collections = collections
        self._step = 2
        self._update_steps()
        self._show_step(2)

    # ── Step 2: Merge/Mirror ─────────────────────────────────────────

    def _show_merge(self):
        card = CardFrame(self._content, title="Step 2: 合并/镜像")
        card.pack(fill="both", expand=True)

        from ..detector import get_enabled_browsers
        targets = dict(get_enabled_browsers(self.app.cfg))
        available = [n for n in targets if n in self._collections]

        tk.Label(card.inner, text="选择基准浏览器:", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, 8))

        self._base_var = tk.StringVar(value=available[0] if available else "")
        for name in available:
            rb = tk.Radiobutton(card.inner, text=name,
                               variable=self._base_var, value=name,
                               font=FONTS["body"], fg=COLORS["text"],
                               bg=COLORS["surface"],
                               selectcolor=COLORS["primary"],
                               activebackground=COLORS["surface"],
                               activeforeground=COLORS["text"])
            rb.pack(anchor="w", pady=2)

        mode_label = "镜像" if self._mode_var.get() == "mirror" else "合并去重"
        tk.Label(card.inner,
                text=f"模式: {mode_label}",
                font=FONTS["body"], fg=COLORS["text_secondary"],
                bg=COLORS["surface"]).pack(anchor="w", pady=(12, 0))

        btn_frame = tk.Frame(self._content, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(12, 0))

        exec_btn = tk.Frame(btn_frame, bg=COLORS["primary"], cursor="hand2",
                           padx=28, pady=10)
        tk.Label(exec_btn, text=f"执行{mode_label}", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["primary"]).pack()
        exec_btn.pack(side="right")
        exec_btn.bind("<Button-1>", lambda e: self._do_merge())

        back_btn = tk.Frame(btn_frame, bg=COLORS["surface_light"], cursor="hand2",
                           padx=20, pady=10)
        tk.Label(back_btn, text="← 返回", font=FONTS["body"],
                fg=COLORS["text"], bg=COLORS["surface_light"]).pack()
        back_btn.pack(side="left")
        back_btn.bind("<Button-1>", lambda e: self._go_back(1))

    def _do_merge(self):
        self.app.run_merge(
            mode=self._mode_var.get(),
            base_browser=self._base_var.get(),
            callback=lambda result: self._on_merge_done(result))

    def _on_merge_done(self, result):
        self._merged = result["merged"]
        self._base_browser = result["base_browser"]
        self._step = 3
        self._update_steps()
        self._show_step(3)

    # ── Step 3: Push ─────────────────────────────────────────────────

    def _show_push(self):
        card = CardFrame(self._content, title="Step 3: 推送结果")
        card.pack(fill="both", expand=True)

        if self._merged:
            tk.Label(card.inner,
                    text=f"将推送 {self._merged.total_bookmarks()} 条书签到以下浏览器",
                    font=FONTS["body"], fg=COLORS["text"],
                    bg=COLORS["surface"]).pack(anchor="w", pady=(0, 12))

            # 目标浏览器列表
            from ..detector import get_enabled_browsers
            targets = dict(get_enabled_browsers(self.app.cfg))
            for name in self._selected_browsers:
                if name in targets:
                    frame = tk.Frame(card.inner, bg=COLORS["surface_light"], padx=12, pady=6)
                    frame.pack(fill="x", pady=3)
                    tk.Label(frame, text=name, font=FONTS["body"],
                            fg=COLORS["text"], bg=COLORS["surface_light"]).pack(side="left")
                    tk.Label(frame, text=f"→ {self._merged.total_bookmarks()} 条",
                            font=FONTS["body"], fg=COLORS["primary"],
                            bg=COLORS["surface_light"]).pack(side="right")

        # 操作按钮
        btn_frame = tk.Frame(self._content, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(16, 0))

        push_btn = tk.Frame(btn_frame, bg=COLORS["success"], cursor="hand2",
                           padx=28, pady=10)
        dry_text = " (Dry-run)" if self._dry_run_var.get() else ""
        tk.Label(push_btn, text=f"确认推送{dry_text} →", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["success"]).pack()
        push_btn.pack(side="right")
        push_btn.bind("<Button-1>", lambda e: self._do_push())

        retry_btn = tk.Frame(btn_frame, bg=COLORS["surface_light"], cursor="hand2",
                            padx=20, pady=10)
        tk.Label(retry_btn, text="← 返回重试", font=FONTS["body"],
                fg=COLORS["text"], bg=COLORS["surface_light"]).pack()
        retry_btn.pack(side="left")
        retry_btn.bind("<Button-1>", lambda e: self._go_back(2))

    def _do_push(self):
        self.app.run_push(
            browser_names=self._selected_browsers,
            dry_run=self._dry_run_var.get(),
            callback=lambda results: self._on_push_done(results))

    def _on_push_done(self, results):
        self.app.log("同步工作流完成！", "success")

        # 完成后回到准备步骤
        self._step = 0
        self._update_steps()
        self._show_step(0)

    def _go_back(self, step):
        self._step = step
        self._update_steps()
        self._show_step(step)
