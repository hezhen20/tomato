# Tomato Timer

一个轻量的桌面时间追踪工具，用于在工作、学习等不同模式之间快速切换并记录投入时间。应用以本地 SQLite 数据库存储记录，支持全局快捷键、系统托盘、悬浮球、历史统计和自定义模式。

> 当前主要面向 Windows 桌面使用；macOS / Linux 可运行源码版，但全局快捷键、托盘和打包效果可能因系统权限与桌面环境而异。

## 功能特性

- 多模式计时：默认包含“工作”模式，可在设置页新增、编辑、删除模式。
- 累积统计：同一天内同一模式的多段计时会自动累积。
- 历史记录：支持按日、周、月查看不同模式的投入时长。
- 全局快捷键：窗口不在前台时也能暂停、结束或切换模式。
- 悬浮球：最小化后显示当前计时状态，双击可恢复主窗口。
- 系统托盘：关闭窗口时默认最小化到托盘，退出时自动保存当前计时。
- 本地存储：数据保存在用户本机，不依赖云服务。

## 项目结构

```text
tomato/
├── app/
│   ├── database.py          # SQLite 数据库与数据访问
│   ├── hotkeys.py           # 全局快捷键管理
│   └── ui/
│       ├── main_window.py   # 主窗口、导航、托盘
│       ├── main_page.py     # 计时主页
│       ├── history_page.py  # 历史统计页
│       ├── settings_page.py # 设置页
│       ├── floating_ball.py # 悬浮球
│       └── style.qss        # 深色主题样式
├── tests/                   # 核心逻辑测试
├── dev.py                   # 开发热重载入口
├── main.py                  # 源码运行入口
├── main.pyw                 # Windows 无控制台入口
├── build.bat                # Windows 打包脚本
├── build.sh                 # macOS / Linux 打包脚本
├── requirements.txt         # 运行依赖
└── requirements-dev.txt     # 开发依赖
```

## 环境要求

- Python 3.10+（本项目开发环境为 Python 3.13）
- Windows 10/11 推荐
- 依赖：PySide6、pynput

## 快速开始

1. 克隆仓库：

   ```bash
   git clone https://github.com/hezhen20/tomato.git
   cd tomato
   ```

2. 创建并激活虚拟环境：

   Windows PowerShell：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS / Linux：

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

4. 启动应用：

   ```bash
   python main.py
   ```

   Windows 下如果不想显示控制台窗口，也可以运行：

   ```powershell
   python main.pyw
   ```

   应用只允许一个实例运行。重复启动时不会创建第二个窗口，而会恢复并聚焦已经运行的窗口。

## 使用说明

### 首次登录

首次输入任意用户名和密码会自动注册本地用户；之后使用相同用户名和密码登录。密码只保存在本机数据库中。

### 计时

- 点击“开始”后开始记录当前模式时间。
- 点击“暂停”可暂停或恢复计时。
- 点击“结束”会保存当前计时段，但不会清空当天累计显示。
- 切换模式时，应用会先保存当前模式的本段时间，再开始新模式计时。

### 模式管理

在设置页可以新增模式、修改模式名称和颜色。模式颜色会用于主页、历史统计和悬浮球状态显示。

### 快捷键

默认快捷键：

| 操作 | 默认快捷键 |
| --- | --- |
| 暂停 / 恢复 | `Ctrl + Alt + P` |
| 结束当前计时 | `Ctrl + Alt + Q` |

每个模式也可以在设置页绑定独立快捷键：

- 未计时时按模式快捷键：开始该模式。
- 正在该模式计时时按模式快捷键：暂停 / 恢复。
- 正在其他模式计时时按模式快捷键：保存当前模式并切换到目标模式。

### 托盘与悬浮球

- 关闭主窗口会最小化到系统托盘，不会直接退出。
- 右键托盘图标可以显示窗口或退出应用。
- 最小化后会显示悬浮球，双击悬浮球恢复窗口。

## 数据存储位置

应用数据默认存储在当前用户的系统数据目录：

| 系统 | 路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\TomatoTimer\tomato.db` |
| macOS | `~/Library/Application Support/TomatoTimer/tomato.db` |
| Linux | `$XDG_DATA_HOME/TomatoTimer/tomato.db` 或 `~/.local/share/TomatoTimer/tomato.db` |

注意：数据库中包含本地用户、模式、快捷键配置和时间记录。仓库不会提交这些个人数据。

## 打包

### Windows

```powershell
.\build.bat
```

打包完成后，输出目录为：

```text
dist\TomatoTimer\
```

把整个 `dist\TomatoTimer` 文件夹复制到其他 Windows 电脑即可运行。

### macOS / Linux

```bash
chmod +x build.sh
./build.sh
```

不同系统的图形界面、托盘和全局快捷键权限差异较大，如遇到快捷键失效，请先检查系统辅助功能、输入监听或窗口管理权限。

## 测试

项目使用 Python 内置的 `unittest`：

```bash
python -m unittest discover -s tests
```

测试会使用临时数据库，不会影响正式计时数据。

## 注意事项

- 当前是本地单机工具，不支持云同步。
- 密码哈希仅用于本地轻量登录，不适合作为高安全等级账户系统。
- 全局快捷键可能与其他软件冲突，建议在设置页检查并调整。
- 如果应用被强制结束，最多可能丢失最近约 30 秒的计时进度。
- `build/`、`dist/`、`__pycache__/`、本地数据库和虚拟环境等文件不会提交到 Git。

## 开发说明

安装开发依赖：

```bash
python -m venv .venv
pip install -r requirements-dev.txt
```

使用热重载模式启动：

```bash
python dev.py
```

修改 Python 源码或 QSS 样式后，开发进程会自动结束旧应用并启动新应用。这个机制采用完整进程重启，正在进行但尚未自动保存的最近计时可能丢失，因此热重载只用于开发调试。

运行测试：

```bash
python -m unittest discover -s tests
```

新增非代码资源后，如果需要随应用一起打包，请同步更新 `build.bat` 和 `build.sh` 里的 PyInstaller `--add-data` 参数。
