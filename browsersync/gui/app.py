"""BrowserSync GUI 主应用程序."""

from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

from ..config import load_config, save_config, default_config, ensure_dirs
from ..detector import detect_browsers, get_enabled_browsers
from ..merger import merge_collections, mirror_collections
from ..models import BookmarkCollection
from ..readers import ChromiumReader, SafariReader
from ..writers import ChromiumWriter, SafariWriter

# ── Color Theme ──────────────────────────────────────────────────────────
COLORS = {
    "bg": "#0F172A",
    "surface": "#1E293B",
    "surface_light": "#334155",
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#F43F5E",
    "text": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "border": "#334155",
    "sidebar_bg": "#0B1121",
    "sidebar_hover": "#1E293B",
    "sidebar_active": "#1E3A5F",
    "console_bg": "#0A0E1A",
}

FONTS = {
    "heading": ("Helvetica", 18, "bold"),
    "subheading": ("Helvetica", 13, "bold"),
    "body": ("Helvetica", 11),
    "small": ("Helvetica", 10),
    "mono": ("Menlo", 10),
    "sidebar": ("Helvetica", 12),
    "title": ("Helvetica", 24, "bold"),
}


def _get_reader(browser_type: str):
    if browser_type == "chromium":
        return ChromiumReader()
    elif browser_type == "safari":
        return SafariReader()
    raise ValueError(f"Unknown browser type: {browser_type}")


def _get_writer(browser_type: str):
    if browser_type == "chromium":
        return ChromiumWriter()
    elif browser_type == "safari":
        return SafariWriter()
    raise ValueError(f"Unknown browser type: {browser_type}")


# ── Styled Widgets ───────────────────────────────────────────────────────

class StyledButton(tk.Canvas):
    """Custom styled button with hover effects."""

    def __init__(self, master, text, command=None, bg_color=COLORS["primary"],
                 fg_color=COLORS["text"], width=160, height=38, font=FONTS["body"],
                 corner_radius=8, **kwargs):
        super().__init__(master, width=width, height=height,
                        bg=COLORS["bg"], highlightthickness=0, **kwargs)
        self.text = text
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.width = width
        self.height = height
        self.font = font
        self.corner_radius = corner_radius
        self._hover = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.draw()

    def draw(self):
        self.delete("all")
        color = self._lighten_color(self.bg_color, 0.15) if self._hover else self.bg_color
        self.create_rounded_rect(2, 2, self.width - 2, self.height - 2,
                                self.corner_radius, fill=color, outline="")
        self.create_text(self.width // 2, self.height // 2,
                        text=self.text, fill=self.fg_color,
                        font=self.font)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = []
        for cx, cy, dx, dy in [
            (x1 + r, y1 + r, -1, -1),
            (x2 - r, y1 + r, 1, -1),
            (x2 - r, y2 - r, 1, 1),
            (x1 + r, y2 - r, -1, 1),
        ]:
            for angle in range(0, 90, 10):
                rad = (angle * dx * dy + (0 if dx == -1 else 180)) if dy == -1 else \
                       (angle * dx * dy + (180 if dx == -1 else 0)) if dx == 1 else \
                       (angle * dx * dy + 90)
                import math
                rad = math.radians(angle + (0 if dx == -1 and dy == -1 else
                                           90 if dx == 1 and dy == -1 else
                                           180 if dx == 1 and dy == 1 else 270))
                points.extend([cx + r * math.cos(rad), cy + r * math.sin(rad)])
        return self.create_polygon(points, **kwargs, smooth=True)

    def _lighten_color(self, color, amount):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_enter(self, e):
        self._hover = True
        self.draw()

    def _on_leave(self, e):
        self._hover = False
        self.draw()

    def _on_click(self, e):
        if self.command:
            self.command()

    def configure(self, **kwargs):
        if "state" in kwargs:
            self._state = kwargs.pop("state", "normal")
        super().configure(**kwargs)


class CardFrame(tk.Frame):
    """A card-like container with border."""

    def __init__(self, master, title=None, **kwargs):
        super().__init__(master, bg=COLORS["surface"], **kwargs)
        self._build(title)

    def _build(self, title):
        inner = tk.Frame(self, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        if title:
            header = tk.Frame(inner, bg=COLORS["surface"])
            header.pack(fill="x", padx=16, pady=(14, 8))
            tk.Label(header, text=title, font=FONTS["subheading"],
                    fg=COLORS["text"], bg=COLORS["surface"]).pack(anchor="w")
            ttk.Separator(inner, orient="horizontal").pack(fill="x", padx=12)
        self.inner = tk.Frame(inner, bg=COLORS["surface"])
        self.inner.pack(fill="both", expand=True, padx=16, pady=12)

    def add_widget(self, widget):
        widget.pack(in_=self.inner)


# ── Main Application ────────────────────────────────────────────────────

class BrowserSyncGUI:
    """BrowserSync 图形化主界面."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BrowserSync - 跨浏览器书签同步工具")
        self.root.geometry("1200x780")
        self.root.minsize(960, 640)
        self.root.configure(bg=COLORS["bg"])

        # 加载配置
        self.cfg = load_config()

        # 当前页面跟踪
        self._current_page = None
        self._content_frame = None
        self._console_visible = False
        self._executing = False
        self._execution_log = []

        # 构建 UI
        self._setup_styles()
        self._build_layout()

        # 初始化后刷新仪表盘
        self.root.after(300, self._navigate_to, "dashboard")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=COLORS["surface"],
                       fieldbackground=COLORS["surface"],
                       foreground=COLORS["text"], rowheight=28,
                       borderwidth=0, font=FONTS["body"])
        style.configure("Treeview.Heading", background=COLORS["surface_light"],
                       foreground=COLORS["text"], font=FONTS["subheading"],
                       borderwidth=0)
        style.map("Treeview", background=[("selected", COLORS["primary"])])
        style.configure("TSeparator", background=COLORS["border"])

    def _build_layout(self):
        # ── 主容器 ──
        main_container = tk.Frame(self.root, bg=COLORS["bg"])
        main_container.pack(fill="both", expand=True)

        # ── 侧边栏 ──
        self._build_sidebar(main_container)

        # ── 右侧内容区 ──
        right_area = tk.Frame(main_container, bg=COLORS["bg"])
        right_area.pack(side="left", fill="both", expand=True)

        # 内容帧
        self._content_frame = tk.Frame(right_area, bg=COLORS["bg"])
        self._content_frame.pack(fill="both", expand=True)

        # ── 底部控制台 ──
        self._build_console(right_area)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, width=200, bg=COLORS["sidebar_bg"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo / 标题
        logo_frame = tk.Frame(sidebar, bg=COLORS["sidebar_bg"])
        logo_frame.pack(fill="x", pady=(24, 20))

        tk.Label(logo_frame, text="⬡", font=("Helvetica", 28),
                fg=COLORS["primary"], bg=COLORS["sidebar_bg"]).pack()
        tk.Label(logo_frame, text="BrowserSync", font=FONTS["subheading"],
                fg=COLORS["text"], bg=COLORS["sidebar_bg"]).pack(pady=(2, 0))

        # 导航项
        self._nav_items = {}
        nav_entries = [
            ("dashboard", "📊  仪表盘"),
            ("sync", "🔄  同步工作台"),
            ("config", "⚙️  配置管理"),
        ]
        nav_frame = tk.Frame(sidebar, bg=COLORS["sidebar_bg"])
        nav_frame.pack(fill="x", padx=8, pady=8)

        for page_id, label in nav_entries:
            item = tk.Frame(nav_frame, bg=COLORS["sidebar_bg"], cursor="hand2")
            item.pack(fill="x", pady=2)

            lbl = tk.Label(item, text=label, font=FONTS["sidebar"],
                          fg=COLORS["text_secondary"], bg=COLORS["sidebar_bg"],
                          anchor="w", padx=16, pady=10)
            lbl.pack(fill="x")

            # Hover effects
            def make_hover(f=item, l=lbl):
                def on_enter(e):
                    if f != self._get_active_nav():
                        f.configure(bg=COLORS["sidebar_hover"])
                        l.configure(bg=COLORS["sidebar_hover"])
                def on_leave(e):
                    if f != self._get_active_nav():
                        f.configure(bg=COLORS["sidebar_bg"])
                        l.configure(bg=COLORS["sidebar_bg"])
                return on_enter, on_leave
            ent, lev = make_hover(item, lbl)
            item.bind("<Enter>", ent)
            item.bind("<Leave>", lev)

            def make_click(p=page_id):
                return lambda e: self._navigate_to(p)
            item.bind("<Button-1>", make_click(page_id))
            lbl.bind("<Button-1>", make_click(page_id))

            self._nav_items[page_id] = (item, lbl)

        # 底部版本号
        tk.Label(sidebar, text="v0.1.0", font=FONTS["small"],
                fg=COLORS["text_secondary"], bg=COLORS["sidebar_bg"],
                anchor="center").pack(side="bottom", fill="x", pady=12)

    def _get_active_nav(self):
        for pid, (frame, _) in self._nav_items.items():
            if frame.cget("bg") == COLORS["sidebar_active"]:
                return frame
        return None

    def _navigate_to(self, page_id):
        # 更新导航高亮
        for pid, (frame, lbl) in self._nav_items.items():
            if pid == page_id:
                frame.configure(bg=COLORS["sidebar_active"])
                lbl.configure(bg=COLORS["sidebar_active"], fg=COLORS["text"])
            else:
                frame.configure(bg=COLORS["sidebar_bg"])
                lbl.configure(bg=COLORS["sidebar_bg"], fg=COLORS["text_secondary"])

        # 清除内容
        for w in self._content_frame.winfo_children():
            w.destroy()

        # 加载页面
        if page_id == "dashboard":
            from .dashboard import DashboardFrame
            DashboardFrame(self._content_frame, self)
        elif page_id == "sync":
            from .sync_workflow import SyncWorkflowFrame
            SyncWorkflowFrame(self._content_frame, self)
        elif page_id == "config":
            from .config_view import ConfigFrame
            ConfigFrame(self._content_frame, self)

    def _build_console(self, parent):
        self._console_frame = tk.Frame(parent, height=180, bg=COLORS["console_bg"])
        # 默认隐藏，通过 toggle 显示

        # 控制台头部
        console_header = tk.Frame(self._console_frame, bg=COLORS["surface_light"], height=28)
        console_header.pack(fill="x")
        console_header.pack_propagate(False)

        tk.Label(console_header, text="  控制台输出", font=FONTS["small"],
                fg=COLORS["text_secondary"], bg=COLORS["surface_light"]).pack(side="left")

        clear_btn = tk.Label(console_header, text="清空", font=FONTS["small"],
                            fg=COLORS["text_secondary"], bg=COLORS["surface_light"],
                            cursor="hand2", padx=8)
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self._clear_console())

        toggle_btn = tk.Label(console_header, text="关闭 ✕", font=FONTS["small"],
                             fg=COLORS["text_secondary"], bg=COLORS["surface_light"],
                             cursor="hand2", padx=8)
        toggle_btn.pack(side="right")
        toggle_btn.bind("<Button-1>", lambda e: self.toggle_console())

        # 日志文本区域
        log_frame = tk.Frame(self._console_frame, bg=COLORS["console_bg"])
        log_frame.pack(fill="both", expand=True)

        self._console_text = tk.Text(log_frame, bg=COLORS["console_bg"],
                                     fg=COLORS["success"], font=FONTS["mono"],
                                     wrap="word", state="disabled",
                                     borderwidth=0, highlightthickness=0,
                                     padx=12, pady=8, insertbackground=COLORS["primary"])
        self._console_text.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical",
                                  command=self._console_text.yview)
        scrollbar.pack(side="right", fill="y")
        self._console_text.configure(yscrollcommand=scrollbar.set)

    def show_console(self):
        if not self._console_visible:
            self._console_frame.pack(fill="x", side="bottom")
            self._console_visible = True

    def toggle_console(self):
        if self._console_visible:
            self._console_frame.pack_forget()
            self._console_visible = False
        else:
            self._console_frame.pack(fill="x", side="bottom")
            self._console_visible = True

    def log(self, message: str, level: str = "info"):
        """向控制台输出日志（线程安全）。"""
        self._execution_log.append((datetime.now(), level, message))
        # 通过 after() 将 UI 操作调度到主线程
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self._log_ui, message, level)
        else:
            self._log_ui(message, level)

    def _log_ui(self, message: str, level: str):
        """在 UI 线程中执行日志渲染。"""
        self._console_text.configure(state="normal")

        ts = datetime.now().strftime("%H:%M:%S")
        self._console_text.insert("end", f"[{ts}] ", "timestamp")

        level_tags = {
            "info": (" ℹ️ ", COLORS["primary"]),
            "success": (" ✅ ", COLORS["success"]),
            "warning": (" ⚠️ ", COLORS["warning"]),
            "error": (" ❌ ", COLORS["error"]),
        }
        tag, color = level_tags.get(level, ("   ", COLORS["text"]))
        self._console_text.insert("end", tag, (f"level_{level}",))
        self._console_text.tag_config("timestamp", foreground=COLORS["text_secondary"])
        self._console_text.tag_config(f"level_{level}", foreground=color)

        self._console_text.insert("end", f"{message}\n", "message")
        self._console_text.tag_config("message", foreground=COLORS["text"])
        self._console_text.see("end")
        self._console_text.configure(state="disabled")
        self.show_console()

    def log_raw(self, text: str):
        """输出原始文本到控制台（线程安全）。"""
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self._log_raw_ui, text)
        else:
            self._log_raw_ui(text)

    def _log_raw_ui(self, text: str):
        """在 UI 线程中执行原始文本渲染。"""
        self._console_text.configure(state="normal")
        self._console_text.insert("end", text + "\n", "raw")
        self._console_text.tag_config("raw", foreground=COLORS["text"])
        self._console_text.see("end")
        self._console_text.configure(state="disabled")

    def _clear_console(self):
        self._console_text.configure(state="normal")
        self._console_text.delete("1.0", "end")
        self._console_text.configure(state="disabled")
        self._execution_log.clear()

    # ── CLI 操作（在线程中执行） ────────────────────────────────────────

    def run_scan(self, browser_names=None, callback=None):
        """扫描浏览器书签。"""
        def task():
            self.log("开始扫描浏览器...", "info")
            try:
                targets = get_enabled_browsers(self.cfg)
                results = []
                for name, info in targets.items():
                    if browser_names and name not in browser_names:
                        continue
                    try:
                        reader = _get_reader(info["type"])
                        collection = reader.read(info["path"], browser_name=name)
                        count = collection.total_bookmarks()
                        results.append((name, count, "ok"))
                        self.log(f"{name}: {count} 条书签", "success")
                    except PermissionError:
                        results.append((name, 0, "permission_error"))
                        self.log(f"{name}: 权限不足（Safari 需要 Full Disk Access）", "warning")
                    except Exception as e:
                        results.append((name, 0, "error"))
                        self.log(f"{name}: 读取失败 - {e}", "error")
                self.log(f"扫描完成，共扫描 {len(results)} 个浏览器", "success")
                if callback:
                    self.root.after(0, callback, results)
            except Exception as e:
                self.log(f"扫描失败: {e}", "error")
        self._run_threaded(task)

    def run_collect(self, browser_names=None, callback=None):
        """收集书签。"""
        def task():
            self.log("开始收集书签...", "info")
            output_path = os.path.expanduser(self.cfg.get("merge_output",
                                                        "~/.browsersync/merged.json"))
            try:
                targets = dict(get_enabled_browsers(self.cfg))
                all_collections = {}
                for name, info in targets.items():
                    if browser_names and name not in browser_names:
                        continue
                    try:
                        reader = _get_reader(info["type"])
                        collection = reader.read(info["path"], browser_name=name)
                        all_collections[name] = collection
                        self.log(f"✅ {name}: {collection.total_bookmarks()} 条书签", "success")
                    except PermissionError:
                        self.log(f"⚠️  {name}: 权限不足", "warning")
                    except Exception as e:
                        self.log(f"❌ {name}: 读取失败 - {e}", "error")

                if not all_collections:
                    self.log("没有读取到任何书签", "error")
                    return

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                raw_data = {
                    "collected_at": datetime.now().isoformat(),
                    "browsers": {n: c.to_dict() for n, c in all_collections.items()},
                }
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)

                total = sum(c.total_bookmarks() for c in all_collections.values())
                self.log(f"收集完成，共 {total} 条书签 → {output_path}", "success")
                if callback:
                    self.root.after(0, callback, all_collections)
            except Exception as e:
                self.log(f"收集失败: {e}", "error")
        self._run_threaded(task)

    def run_merge(self, mode="merge", base_browser=None, callback=None):
        """执行合并/镜像。"""
        def task():
            mode_label = "镜像" if mode == "mirror" else "合并去重"
            self.log(f"开始{mode_label}...", "info")
            input_path = os.path.expanduser(self.cfg.get("merge_output",
                                                       "~/.browsersync/merged.json"))
            try:
                if not os.path.exists(input_path):
                    self.log("未找到收集数据，请先收集书签", "error")
                    return

                with open(input_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                collections = {}
                for name, data in raw_data.get("browsers", {}).items():
                    collections[name] = BookmarkCollection.from_dict(data)

                if not collections:
                    self.log("没有书签数据可合并", "error")
                    return

                base = base_browser or self.cfg.get("base_browser")
                if base and base not in collections:
                    self.log(f"指定基准浏览器 '{base}' 不可用，将自动选择", "warning")
                    base = None
                if base is None:
                    base = max(collections, key=lambda b: collections[b].total_bookmarks())

                self.log(f"基准浏览器: {base} ({collections[base].total_bookmarks()} 条)", "info")
                self.log(f"模式: {mode_label}", "info")

                if mode == "mirror":
                    merged = mirror_collections(collections, base_browser=base)
                    saved = 0
                else:
                    merged = merge_collections(collections, base_browser=base)
                    total_before = sum(c.total_bookmarks() for c in collections.values())
                    saved = total_before - merged.total_bookmarks()
                    self.log(f"去重移除: {saved} 条", "info")

                merged.save_json(input_path)
                self.log(f"{mode_label}完成，共 {merged.total_bookmarks()} 条书签", "success")

                if callback:
                    self.root.after(0, callback, {
                        "collections": collections,
                        "merged": merged,
                        "base_browser": base,
                        "saved": saved,
                        "mode": mode,
                    })
            except Exception as e:
                self.log(f"{mode_label}失败: {e}", "error")
        self._run_threaded(task)

    def run_push(self, browser_names=None, dry_run=False, callback=None):
        """推送书签到浏览器。"""
        def task():
            self.log("开始推送书签..." + (" (Dry-run)" if dry_run else ""), "info")
            input_path = os.path.expanduser(self.cfg.get("merge_output",
                                                       "~/.browsersync/merged.json"))
            try:
                if not os.path.exists(input_path):
                    self.log("未找到合并数据，请先执行合并", "error")
                    return

                merged = BookmarkCollection.load_json(input_path)
                targets = dict(get_enabled_browsers(self.cfg))
                results = []

                for name, info in targets.items():
                    if browser_names and name not in browser_names:
                        continue
                    try:
                        writer = _get_writer(info["type"])
                        if dry_run:
                            results.append((name, merged.total_bookmarks(), "dry_run"))
                            self.log(f"📋 {name}: 将推送 {merged.total_bookmarks()} 条 (dry-run)", "info")
                        else:
                            writer.write(merged, info["path"])
                            results.append((name, merged.total_bookmarks(), "ok"))
                            self.log(f"✅ {name}: 已更新 {merged.total_bookmarks()} 条书签", "success")
                    except PermissionError as e:
                        results.append((name, 0, "permission_error"))
                        self.log(f"⚠️  {name}: 权限不足 - {e}", "warning")
                    except Exception as e:
                        results.append((name, 0, "error"))
                        self.log(f"❌ {name}: 写入失败 - {e}", "error")

                if not dry_run:
                    self.log("同步完成！请重启浏览器以查看变更。", "success")
                else:
                    self.log("Dry-run 模式，未实际写入。", "info")

                if callback:
                    self.root.after(0, callback, results)
            except Exception as e:
                self.log(f"推送失败: {e}", "error")
        self._run_threaded(task)

    def run_full_sync(self, mode="merge", base_browser=None, dry_run=False,
                      browser_names=None, callback=None):
        """一键同步：collect → merge → push。"""
        def task():
            self.log("=" * 50, "info")
            self.log("开始一键同步...", "info")
            self.log(f"模式: {'镜像' if mode == 'mirror' else '合并去重'}", "info")

            # Step 1: Collect
            self.log("─" * 30, "info")
            self.log("Step 1/3: 收集书签", "info")
            output_path = os.path.expanduser(self.cfg.get("merge_output",
                                                        "~/.browsersync/merged.json"))
            try:
                targets = dict(get_enabled_browsers(self.cfg))
                all_collections = {}
                for name, info in targets.items():
                    if browser_names and name not in browser_names:
                        continue
                    try:
                        reader = _get_reader(info["type"])
                        collection = reader.read(info["path"], browser_name=name)
                        all_collections[name] = collection
                        self.log(f"✅ {name}: {collection.total_bookmarks()} 条", "success")
                    except PermissionError:
                        self.log(f"⚠️  {name}: 权限不足", "warning")
                    except Exception as e:
                        self.log(f"❌ {name}: 读取失败 - {e}", "error")

                if not all_collections:
                    self.log("没有读取到任何书签，同步终止", "error")
                    return

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                raw_data = {
                    "collected_at": datetime.now().isoformat(),
                    "browsers": {n: c.to_dict() for n, c in all_collections.items()},
                }
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)

                # Step 2: Merge/Mirror
                self.log("─" * 30, "info")
                self.log("Step 2/3: " + ("镜像" if mode == "mirror" else "合并去重"), "info")

                base = base_browser or self.cfg.get("base_browser")
                if base and base not in all_collections:
                    base = max(all_collections,
                              key=lambda b: all_collections[b].total_bookmarks())

                if mode == "mirror":
                    merged = mirror_collections(all_collections, base_browser=base)
                else:
                    merged = merge_collections(all_collections, base_browser=base)

                merged.save_json(output_path)
                self.log(f"结果: {merged.total_bookmarks()} 条书签", "success")

                # Step 3: Push
                self.log("─" * 30, "info")
                self.log("Step 3/3: 推送书签", "info")

                for name, info in targets.items():
                    if browser_names and name not in browser_names:
                        continue
                    try:
                        writer = _get_writer(info["type"])
                        if dry_run:
                            self.log(f"📋 {name}: {merged.total_bookmarks()} 条 (dry-run)", "info")
                        else:
                            writer.write(merged, info["path"])
                            self.log(f"✅ {name}: 已更新 {merged.total_bookmarks()} 条", "success")
                    except PermissionError as e:
                        self.log(f"⚠️  {name}: 权限不足 - {e}", "warning")
                    except Exception as e:
                        self.log(f"❌ {name}: 写入失败 - {e}", "error")

                if not dry_run:
                    self.log("✅ 同步完成！请重启浏览器以查看变更。", "success")
                else:
                    self.log("Dry-run 模式，未实际写入。", "info")

                self.log("=" * 50, "info")

                if callback:
                    self.root.after(0, callback, {
                        "collections": all_collections,
                        "merged": merged,
                        "base_browser": base,
                        "dry_run": dry_run,
                    })
            except Exception as e:
                self.log(f"同步失败: {e}", "error")
        self._run_threaded(task)

    def _run_threaded(self, task_func):
        """在后台线程中执行任务。"""
        if self._executing:
            self.log("已有任务正在执行，请等待完成", "warning")
            return
        self._executing = True
        def wrapper():
            try:
                task_func()
            finally:
                self._executing = False
        t = threading.Thread(target=wrapper, daemon=True)
        t.start()

    def run(self):
        self.root.mainloop()


def launch_gui():
    """启动 GUI 界面。"""
    app = BrowserSyncGUI()
    app.run()
