"""CLI entry point for BrowserSync."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .config import default_config, ensure_dirs, load_config, save_config
from .detector import get_enabled_browsers
from .merger import merge_collections, mirror_collections
from .models import BookmarkCollection
from .readers import ChromiumReader, SafariReader
from .writers import ChromiumWriter, SafariWriter


# ── Shared helpers ──────────────────────────────────────────────────────────


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


def _resolve_target_browsers(cfg, browser_names: list[str]):
    """Resolve which browsers to operate on."""
    all_enabled = dict(get_enabled_browsers(cfg))
    if not browser_names:
        return all_enabled
    resolved = {}
    for name in browser_names:
        if name in all_enabled:
            resolved[name] = all_enabled[name]
        elif name in cfg.get("browsers", {}):
            info = cfg["browsers"][name]
            if not info.get("enabled"):
                click.echo(f"⚠️ '{name}' 未启用，跳过", err=True)
            else:
                click.echo(f"⚠️ '{name}' 书签文件不存在，跳过", err=True)
        else:
            click.echo(f"⚠️ 未知浏览器 '{name}'", err=True)
    return resolved


def _echo_json(data: dict) -> None:
    """Print JSON to stdout (for machine-readable output)."""
    click.echo(json.dumps(data, ensure_ascii=False, default=str))


def _show_text_preview(
    all_collections, merged, base_browser, saved, mode="merge"
) -> None:
    """Human-readable merge preview."""
    mode_label = "镜像" if mode == "mirror" else "合并"
    click.echo(click.style(f"\n📋 {mode_label}预览\n", bold=True))
    click.echo("  " + click.style(f"{mode_label}前各浏览器书签:", underline=True))
    for name, coll in sorted(
        all_collections.items(), key=lambda x: x[1].total_bookmarks(), reverse=True
    ):
        marker = "🏠" if name == base_browser else "  "
        click.echo(f"    {marker} {name:<20} {coll.total_bookmarks():>4} 条")
    click.echo(f"    {'─' * 35}")
    total_before = sum(c.total_bookmarks() for c in all_collections.values())
    click.echo(f"    {'  ':<3} {'总计':<20} {total_before:>4} 条")
    click.echo(f"\n  🏠 基准文件夹结构: {base_browser}")
    if mode == "mirror":
        click.echo(f"  🔄 模式:         镜像 (所有浏览器与基准浏览器保持一致)")
    else:
        click.echo(f"  🗑️  去重移除:      {saved} 条")
    click.echo(f"  📦 结果:          {merged.total_bookmarks()} 条")
    click.echo(f"     ├─ 导航栏(bookmark_bar): {merged.bookmark_bar.total_bookmarks()} 条")
    click.echo(f"     ├─ 收藏夹(other):        {merged.other_bookmarks.total_bookmarks()} 条")
    click.echo(f"     └─ 移动设备(synced):     {merged.synced_bookmarks.total_bookmarks()} 条")


def _confirm_push(dry_run: bool) -> bool:
    if dry_run:
        return True
    click.echo("")
    return click.confirm(
        click.style("  是否确认推送以上结果到所有浏览器？", bold=True), default=True
    )


# ── Shared options ──────────────────────────────────────────────────────────

_BROWSER_OPTION = click.option(
    "--browser", "-b", type=str, multiple=True,
    help="指定目标浏览器（可多次使用），不指定则操作全部",
)
_JSON_OPTION = click.option(
    "--json", "json_output", is_flag=True, help="以 JSON 格式输出（供外部程序调用）",
)


# ── CLI group ───────────────────────────────────────────────────────────────

@click.group()
@click.option("--config", "-c", type=click.Path(), help="Config file path")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, config):
    """BrowserSync - 跨浏览器书签同步工具"""
    ctx.ensure_object(dict)
    if config:
        cfg = load_config(Path(config))
    else:
        cfg = load_config()
    ctx.obj["cfg"] = cfg
    ensure_dirs(cfg)


# ── scan ────────────────────────────────────────────────────────────────────

@cli.command()
@_BROWSER_OPTION
@_JSON_OPTION
@click.pass_context
def scan(ctx, browser, json_output):
    """扫描浏览器书签"""
    cfg = ctx.obj["cfg"]
    targets = _resolve_target_browsers(cfg, browser)
    results = []

    for name, info in targets.items():
        try:
            reader = _get_reader(info["type"])
            collection = reader.read(info["path"], browser_name=name)
            results.append({
                "name": name, "type": info["type"],
                "count": collection.total_bookmarks(), "status": "ok",
            })
        except PermissionError:
            results.append({
                "name": name, "type": info["type"],
                "count": 0, "status": "permission_error",
            })
        except Exception as e:
            results.append({
                "name": name, "type": info["type"],
                "count": 0, "status": "error", "error": str(e),
            })

    if json_output:
        _echo_json({"command": "scan", "results": results, "total": sum(r["count"] for r in results)})
        return

    # Human output
    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n📡 扫描浏览器...\n", bold=True))
    for r in results:
        icon = "🔵" if r["type"] == "chromium" else "🟡"
        if r["status"] == "ok":
            click.echo(f"  {icon} {r['name']:<20} {r['count']:>4} 书签")
        elif r["status"] == "permission_error":
            click.echo(f"  ⚠️  {r['name']:<20} 权限不足 - Safari 需要 Full Disk Access")
        else:
            click.echo(f"  ❌ {r['name']:<20} 读取失败: {r.get('error', '')}")
    click.echo(f"\n  📊 总计: {sum(r['count'] for r in results)} 书签 (来自 {len(results)} 个浏览器)")


# ── collect ─────────────────────────────────────────────────────────────────

@cli.command()
@_BROWSER_OPTION
@_JSON_OPTION
@click.option("--output", "-o", type=click.Path(), default=None, help="输出文件路径")
@click.pass_context
def collect(ctx, browser, json_output, output):
    """收集书签"""
    cfg = ctx.obj["cfg"]
    output_path = output or cfg.get("merge_output", "~/.browsersync/merged.json")
    targets = _resolve_target_browsers(cfg, browser)

    all_collections = {}
    errors = []
    for name, info in targets.items():
        try:
            reader = _get_reader(info["type"])
            collection = reader.read(info["path"], browser_name=name)
            all_collections[name] = collection
        except PermissionError:
            errors.append({"browser": name, "error": "permission_denied"})
        except Exception as e:
            errors.append({"browser": name, "error": str(e)})

    output_path = os.path.expanduser(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    raw_data = {
        "collected_at": datetime.now().isoformat(),
        "browsers": {n: c.to_dict() for n, c in all_collections.items()},
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    total = sum(c.total_bookmarks() for c in all_collections.values())

    if json_output:
        _echo_json({
            "command": "collect",
            "file": output_path,
            "total": total,
            "browsers": list(all_collections.keys()),
            "counts": {n: c.total_bookmarks() for n, c in all_collections.items()},
            "errors": errors,
        })
        return

    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n📥 收集书签...\n", bold=True))
    for name, coll in all_collections.items():
        click.echo(f"  ✅ {name:<20} {coll.total_bookmarks():>4} 书签")
    for e in errors:
        click.echo(f"  ⚠️  {e['browser']:<20} 跳过: {e['error']}")
    click.echo(f"\n  📁 已保存到: {output_path}")
    click.echo(f"  📊 总计: {total} 书签")


# ── merge ───────────────────────────────────────────────────────────────────

@cli.command()
@_JSON_OPTION
@click.option("--input", "-i", type=click.Path(), default=None, help="收集的 JSON 输入文件")
@click.option("--output", "-o", type=click.Path(), default=None, help="合并后的 JSON 输出文件")
@click.option("--base", type=str, default=None, help="以哪个浏览器的文件夹结构为基准")
@click.option("--mode", type=click.Choice(["merge", "mirror"]), default=None, help="同步模式")
@click.option("--dry-run", is_flag=True, help="仅预览不写文件")
@click.pass_context
def merge(ctx, json_output, input, output, base, mode, dry_run):
    """合并/镜像去重"""
    cfg = ctx.obj["cfg"]
    mode = mode or cfg.get("mode", "merge")
    input_path = input or cfg.get("merge_output", "~/.browsersync/merged.json")
    input_path = os.path.expanduser(input_path)

    if not os.path.exists(input_path):
        click.echo("未找到收集数据，请先运行 browsersync collect", err=True)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    collections = {}
    for name, data in raw_data.get("browsers", {}).items():
        collections[name] = BookmarkCollection.from_dict(data)

    if not collections:
        click.echo("没有书签数据可合并", err=True)
        sys.exit(1)

    base_browser = base or cfg.get("base_browser")
    if base_browser and base_browser not in collections:
        base_browser = None
    if base_browser is None:
        base_browser = max(collections, key=lambda b: collections[b].total_bookmarks())

    if mode == "mirror":
        merged = mirror_collections(collections, base_browser=base_browser)
        saved = 0
    else:
        merged = merge_collections(collections, base_browser=base_browser)
        total_before = sum(c.total_bookmarks() for c in collections.values())
        saved = total_before - merged.total_bookmarks()

    if json_output:
        _echo_json({
            "command": "merge",
            "mode": mode,
            "base_browser": base_browser,
            "total_before": sum(c.total_bookmarks() for c in collections.values()),
            "saved": saved,
            "total_after": merged.total_bookmarks(),
            "breakdown": {
                "bookmark_bar": merged.bookmark_bar.total_bookmarks(),
                "other_bookmarks": merged.other_bookmarks.total_bookmarks(),
                "synced_bookmarks": merged.synced_bookmarks.total_bookmarks(),
            },
            "per_browser": {n: c.total_bookmarks() for n, c in collections.items()},
        })
        return

    if not dry_run:
        output_path = output or input_path
        merged.save_json(output_path)

    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n🔄 " + ("镜像" if mode == "mirror" else "合并去重") + "...\n", bold=True))
    click.echo(f"  🏠 基准浏览器: {base_browser} ({collections[base_browser].total_bookmarks()} 书签)")
    _show_text_preview(collections, merged, base_browser, saved, mode)
    if dry_run:
        click.echo("\n  ℹ️  Dry-run 模式，未写文件")
    else:
        click.echo(f"\n  📁 已保存到: {output_path or input_path}")


# ── push ────────────────────────────────────────────────────────────────────

@cli.command()
@_BROWSER_OPTION
@_JSON_OPTION
@click.option("--dry-run", is_flag=True, help="仅预览不实际写入")
@click.pass_context
def push(ctx, browser, json_output, dry_run):
    """推送书签到浏览器"""
    cfg = ctx.obj["cfg"]
    targets = _resolve_target_browsers(cfg, browser)
    merge_path = os.path.expanduser(cfg.get("merge_output", "~/.browsersync/merged.json"))

    if not os.path.exists(merge_path):
        click.echo("未找到合并数据，请先运行 browsersync merge", err=True)
        sys.exit(1)

    merged = BookmarkCollection.load_json(merge_path)

    # Safety: refuse to write empty collection
    if merged.total_bookmarks() == 0:
        click.echo("  ❌ 合并结果为空，请先运行 browsersync sync 或检查 merged.json")
        sys.exit(1)

    results = []

    for name, info in targets.items():
        try:
            writer = _get_writer(info["type"])
            if not dry_run:
                writer.write(merged, info["path"])
            results.append({
                "browser": name, "count": merged.total_bookmarks(),
                "status": "ok" if not dry_run else "dry_run",
            })
        except PermissionError as e:
            results.append({"browser": name, "count": 0, "status": "permission_error", "error": str(e)})
        except Exception as e:
            results.append({"browser": name, "count": 0, "status": "error", "error": str(e)})

    if json_output:
        _echo_json({"command": "push", "results": results, "dry_run": dry_run})
        return

    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n📤 推送书签到浏览器...\n", bold=True))
    for r in results:
        if r["status"] == "ok":
            click.echo(f"  ✅ {r['browser']:<20} 已更新 {r['count']} 书签")
        elif r["status"] == "dry_run":
            click.echo(f"  📋 {r['browser']:<20} 推送 {r['count']} 书签 (dry-run)")
        elif r["status"] == "permission_error":
            click.echo(f"  ⚠️  {r['browser']:<20} 权限不足: {r['error']}")
        else:
            click.echo(f"  ❌ {r['browser']:<20} 写入失败: {r['error']}")
    if not dry_run:
        click.echo(f"\n  ✅ 同步完成！请重启浏览器以查看变更。")
    else:
        click.echo(f"\n  ℹ️  Dry-run 模式，未实际写入。")


# ── sync ────────────────────────────────────────────────────────────────────

@cli.command()
@_BROWSER_OPTION
@_JSON_OPTION
@click.option("--dry-run", is_flag=True, help="仅预览不实际写入")
@click.option("--base", type=str, default=None, help="以哪个浏览器的文件夹结构为基准")
@click.option("--mode", type=click.Choice(["merge", "mirror"]), default=None, help="同步模式")
@click.pass_context
def sync(ctx, browser, json_output, dry_run, base, mode):
    """一键 collect → merge → push"""
    cfg = ctx.obj["cfg"]
    mode = mode or cfg.get("mode", "merge")
    targets = _resolve_target_browsers(cfg, browser)
    merge_path = os.path.expanduser(cfg.get("merge_output", "~/.browsersync/merged.json"))

    # Step 1: Collect
    all_collections = {}
    collect_errors = []
    for name, info in targets.items():
        try:
            reader = _get_reader(info["type"])
            collection = reader.read(info["path"], browser_name=name)
            all_collections[name] = collection
        except PermissionError:
            collect_errors.append({"browser": name, "error": "permission_denied"})
        except Exception as e:
            collect_errors.append({"browser": name, "error": str(e)})

    if not all_collections:
        _echo_json({"command": "sync", "error": "no_bookmarks", "collect_errors": collect_errors})
        sys.exit(1)

    raw_data = {
        "collected_at": datetime.now().isoformat(),
        "browsers": {n: c.to_dict() for n, c in all_collections.items()},
    }
    os.makedirs(os.path.dirname(merge_path), exist_ok=True)
    with open(merge_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    # Step 2: Merge
    base_browser = base or cfg.get("base_browser")
    if base_browser and base_browser not in all_collections:
        base_browser = None
    if base_browser is None:
        base_browser = max(all_collections, key=lambda b: all_collections[b].total_bookmarks())

    if mode == "mirror":
        merged = mirror_collections(all_collections, base_browser=base_browser)
        saved = 0
    else:
        merged = merge_collections(all_collections, base_browser=base_browser)
        total_original = sum(c.total_bookmarks() for c in all_collections.values())
        saved = total_original - merged.total_bookmarks()

    merged.save_json(merge_path)

    # Step 3: Push
    push_results = []
    for name, info in targets.items():
        try:
            writer = _get_writer(info["type"])
            if not dry_run:
                writer.write(merged, info["path"])
            push_results.append({
                "browser": name, "count": merged.total_bookmarks(),
                "status": "ok" if not dry_run else "dry_run",
            })
        except PermissionError as e:
            push_results.append({"browser": name, "count": 0, "status": "permission_error", "error": str(e)})
        except Exception as e:
            push_results.append({"browser": name, "count": 0, "status": "error", "error": str(e)})

    if json_output:
        _echo_json({
            "command": "sync",
            "mode": mode,
            "dry_run": dry_run,
            "base_browser": base_browser,
            "total_after": merged.total_bookmarks(),
            "saved": saved if mode == "merge" else 0,
            "per_browser_before": {n: c.total_bookmarks() for n, c in all_collections.items()},
            "breakdown": {
                "bookmark_bar": merged.bookmark_bar.total_bookmarks(),
                "other_bookmarks": merged.other_bookmarks.total_bookmarks(),
                "synced_bookmarks": merged.synced_bookmarks.total_bookmarks(),
            },
            "push_results": push_results,
            "collect_errors": collect_errors,
        })
        return

    # Human output
    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n🚀 开始一键同步...\n", bold=True))
    click.echo(click.style("Step 1/3: 收集书签\n", bold=True))
    for name, coll in all_collections.items():
        click.echo(f"  ✅ {name:<20} {coll.total_bookmarks():>4} 书签")
    for e in collect_errors:
        click.echo(f"  ⚠️  {e['browser']:<20} 跳过: {e['error']}")
    click.echo(click.style("\nStep 2/3: " + ("镜像" if mode == "mirror" else "合并去重") + "\n", bold=True))
    click.echo(f"  🏠 基准浏览器: {base_browser} ({all_collections[base_browser].total_bookmarks()} 书签)")
    _show_text_preview(all_collections, merged, base_browser, saved, mode)
    click.echo(click.style("\nStep 3/3: 推送书签\n", bold=True))
    for r in push_results:
        if r["status"] == "ok":
            click.echo(f"  ✅ {r['browser']:<20} 已更新 {r['count']} 书签")
        elif r["status"] == "dry_run":
            click.echo(f"  📋 {r['browser']:<20} 推送 {r['count']} 书签 (dry-run)")
        elif r["status"] == "permission_error":
            click.echo(f"  ⚠️  {r['browser']:<20} 权限不足: {r['error']}")
        else:
            click.echo(f"  ❌ {r['browser']:<20} 写入失败: {r['error']}")
    if not dry_run:
        click.echo(f"\n  ✅ 同步完成！请重启浏览器以查看变更。")
    else:
        click.echo(f"\n  ℹ️  Dry-run 模式，未实际写入。")


# ── config / admin commands ─────────────────────────────────────────────────

@cli.command()
@_JSON_OPTION
@click.pass_context
def init(ctx, json_output):
    """初始化配置文件"""
    cfg = default_config()
    path = save_config(cfg)
    ensure_dirs(cfg)
    browser_count = sum(1 for b in cfg["browsers"].values() if b["enabled"])

    if json_output:
        _echo_json({"command": "init", "config_path": str(path), "browser_count": browser_count})
        return

    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n✅ 初始化完成\n", bold=True))
    click.echo(f"  📁 配置文件: {path}")
    click.echo(f"  🔄 已检测到 {browser_count} 个浏览器")
    for name, info in cfg["browsers"].items():
        status = "✅ 已安装" if info["enabled"] else "⬜ 未安装"
        click.echo(f"     {status} {name}")


@cli.command()
@click.argument("browser_name", required=True)
@click.pass_context
def set_base(ctx, browser_name):
    """设置基准浏览器（永久保存到配置）"""
    cfg = ctx.obj["cfg"]
    valid_names = list(cfg.get("browsers", {}).keys())
    if browser_name not in valid_names:
        click.echo(f"❌ 未知浏览器: '{browser_name}'，可用: {', '.join(valid_names)}", err=True)
        sys.exit(1)
    cfg["base_browser"] = browser_name
    save_config(cfg)
    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style(f"\n✅ 基准浏览器已设置为: {browser_name}", bold=True))


@cli.command()
@click.argument("mode_name", type=click.Choice(["merge", "mirror"]))
@click.pass_context
def set_mode(ctx, mode_name):
    """设置同步模式（永久保存到配置）"""
    cfg = ctx.obj["cfg"]
    cfg["mode"] = mode_name
    save_config(cfg)
    label = "镜像" if mode_name == "mirror" else "合并去重"
    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style(f"\n✅ 同步模式已设置为: {label}", bold=True))


@cli.command()
@_JSON_OPTION
@click.pass_context
def show_config(ctx, json_output):
    """显示当前配置"""
    cfg = ctx.obj["cfg"]
    base = cfg.get("base_browser")
    mode = cfg.get("mode", "merge")
    browsers = {}
    for name, info in cfg.get("browsers", {}).items():
        browsers[name] = {
            "enabled": info.get("enabled", False),
            "type": info.get("type", ""),
            "path": info.get("path", ""),
        }

    if json_output:
        _echo_json({
            "command": "show_config",
            "base_browser": base or "(auto)",
            "mode": mode,
            "browsers": browsers,
            "backup_dir": cfg.get("backup_dir", ""),
            "log_dir": cfg.get("log_dir", ""),
            "merge_output": cfg.get("merge_output", ""),
        })
        return

    mode_label = "镜像" if mode == "mirror" else "合并去重"
    click.echo(click.style("BrowserSync", fg="blue", bold=True) + f" v{__version__}")
    click.echo("─" * 40)
    click.echo(click.style("\n📋 当前配置\n", bold=True))
    click.echo(f"  🏠 基准浏览器: {base or '(自动选择书签最多的)'}")
    click.echo(f"  ⚙️  同步模式:    {mode_label}")
    click.echo(f"  📁 配置文件: {Path.home() / '.browsersync/config.yaml'}")
    click.echo("")
    click.echo("  🔄 浏览器列表:")
    for name, info in browsers.items():
        status_sym = "✅" if info["enabled"] else "⬜"
        marker = "🏠" if name == base else "  "
        click.echo(f"    {marker} {status_sym} {name}")


@cli.command()
def gui():
    """启动图形化用户界面"""
    from .gui import launch_gui
    launch_gui()


def main():
    cli()

if __name__ == "__main__":
    main()
