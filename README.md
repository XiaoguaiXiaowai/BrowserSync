# BrowserSync

跨浏览器书签同步工具 for macOS

从多个浏览器中收集书签，去重合并（或镜像同步）后写回所有或指定浏览器，实现书签统一。

## 支持的浏览器

| 浏览器 | 格式 | 状态 |
|--------|------|------|
| Tabbit | Chromium JSON | ✅ 自动读写 |
| Tabbit Browser | Chromium JSON | ✅ 自动读写 |
| Quark（夸克） | Chromium JSON | ✅ 安装后自动发现 |
| Google Chrome | Chromium JSON | ✅ 安装后自动发现 |
| Microsoft Edge | Chromium JSON | ✅ 安装后自动发现 |
| Safari | Binary Plist | ✅ 需授予终端 Full Disk Access |

## 安装

```bash
pip3 install -e /path/to/BrowserSync
```

安装后可直接使用 `browsersync` 命令或 `python3 -m browsersync`。

## 快速入门

```bash
# 1. 初始化配置，自动检测已安装浏览器
browsersync init

# 2. 查看检测结果
browsersync scan

# 3. 一键同步（含合并预览 + 确认提示）
browsersync sync

# 首次建议先 dry-run 预览
browsersync sync --dry-run
```

## 命令参考

### `scan` — 扫描浏览器书签

```bash
browsersync scan
browsersync scan -b Safari -b Tabbit          # 只扫指定浏览器
browsersync scan --json                        # JSON 格式输出
```

### `collect` — 收集书签

从各浏览器读取书签，保存为统一的 JSON 文件。

```bash
browsersync collect
browsersync collect -b Safari                  # 只收集 Safari
browsersync collect -o ~/my-backup.json        # 指定输出路径
browsersync collect --json                     # JSON 格式输出
```

### `merge` — 合并/镜像去重

读取 collect 生成的 JSON 文件，按策略合并或镜像。

```bash
browsersync merge                                        # 合并去重（默认模式）
browsersync merge --mode mirror                          # 镜像模式（与基准浏览器完全一致）
browsersync merge --base "Tabbit Browser"                # 指定基准浏览器
browsersync merge --dry-run                              # 预览不保存
browsersync merge --json                                 # JSON 格式输出
```

合并模式（`--mode merge`）：以基准浏览器文件夹结构为准，其他浏览器的新 URL 并入，重复项去重。

镜像模式（`--mode mirror`）：所有浏览器的书签完全替换为基准浏览器内容，不做任何合并。

### `push` — 推送书签到浏览器

将合并结果写回各浏览器的原生书签文件（自动备份原文件）。

```bash
browsersync push                              # 推送到全部已启用浏览器
browsersync push -b Safari                    # 只推送到 Safari
browsersync push --dry-run                    # 预览不实际写入
browsersync push --json                       # JSON 格式输出
```

安全机制：
- 写回前自动备份原文件为 `.browsersync.bak`
- 合并结果为空时拒绝写入并报错
- `--dry-run` 可预览变更

### `sync` — 一键同步

按 collect → merge → push 顺序完整执行，推送前显示合并预览并确认。

```bash
browsersync sync                                        # 完整同步流程
browsersync sync --dry-run                              # 预览模式
browsersync sync -b Safari                              # 只同步 Safari
browsersync sync --base "Tabbit"                        # 指定基准浏览器
browsersync sync --mode mirror                          # 镜像模式
browsersync sync --json                                 # JSON 格式输出
```

### `init` — 初始化配置

```bash
browsersync init
browsersync init --json                        # JSON 格式输出
```

首次运行自动检测已安装的浏览器并生成配置文件。

### `set-base` — 设置基准浏览器

设定合并时以哪个浏览器的文件夹结构为基准（永久保存到配置）。

```bash
browsersync set-base "Tabbit Browser"
```

也可在 `sync` / `merge` 中用 `--base` 临时覆盖。

### `set-mode` — 设置同步模式

```bash
browsersync set-mode merge      # 合并去重模式（默认）
browsersync set-mode mirror     # 镜像模式
```

也可在 `sync` / `merge` 中用 `--mode` 临时覆盖。

### `show-config` — 显示当前配置

```bash
browsersync show-config
browsersync show-config --json                 # JSON 格式输出
```

### `gui` — 启动图形界面

```bash
browsersync gui
```

## 指定目标浏览器

所有操作都支持 `-b` / `--browser` 参数，可多次使用：

```bash
browsersync sync -b Safari                     # 只操作 Safari
browsersync scan -b Tabbit -b "Tabbit Browser" # 只扫这两个
browsersync push -b Safari                     # 只推送到 Safari
```

不指定则操作所有已安装且启用的浏览器。

## 基准浏览器

合并时以哪个浏览器的**文件夹结构**为基准。有三种方式指定：

1. **永久设定**：`browsersync set-base "Tabbit Browser"`
2. **单次覆盖**：`browsersync sync --base "Tabbit"`
3. **自动选择**：不指定则选书签最多的浏览器

## `--json` 输出

供外部 GUI（如 React 前端、Electron 应用）通过子进程调用时解析结构化数据。

```bash
# 扫描结果
browsersync scan --json
# → {"command":"scan","results":[{"name":"Tabbit","count":247,"status":"ok"},...],"total":986}

# 完整同步结果
browsersync sync --json --dry-run
# → {"command":"sync","mode":"merge","base_browser":"Tabbit","total_after":256,...}
```

## 数据文件

| 文件 | 说明 |
|------|------|
| `~/.browsersync/config.yaml` | 配置文件（浏览器列表、基准、模式等） |
| `~/.browsersync/merged.json` | 合并结果（含各浏览器原始数据） |
| `~/.browsersync/backups/` | 备份目录 |
| `~/.browsersync/logs/` | 日志目录 |
| `<browser>/Default/Bookmarks.browsersync.bak` | 推送时自动备份的原书签文件 |

## 安全机制

- **自动备份**：每次推送前备份原书签文件
- **空数据保护**：合并结果为 0 时拒绝写入
- **Dry-run**：预览变更，不实际写入
- **确认提示**：推送前需用户确认

## 去重策略

- 按 URL 精确匹配去重（忽略大小写和尾部斜杠）
- 以基准浏览器的文件夹结构为基准
- 其他浏览器独有的书签保持原文件夹结构
- 合并结果中自动去重，统计显示去重数量

## 同步模式

| 模式 | 效果 |
|------|------|
| `merge`（默认） | 保留各浏览器增量，去重合并，以基准浏览器结构为准 |
| `mirror` | 所有浏览器与基准浏览器完全一致，不做合并 |

## 开发

```bash
# 安装开发依赖
pip3 install -e ".[dev]"

# 运行测试
python3 -m pytest tests/ -v

# 测试 JSON 输出
python3 -m browsersync scan --json | python3 -m json.tool
```
