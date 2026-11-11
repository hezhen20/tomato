# Tomato Timer

一个轻量的桌面时间追踪工具，用于在工作、学习等不同模式之间快速切换并记录投入时间。应用以本地 SQLite 数据库存储记录，支持全局快捷键、系统托盘、悬浮球、历史统计和自定义模式。

> 当前主要面向 Windows 桌面使用；macOS / Linux 可运行源码版，但全局快捷键、托盘和打包效果可能因系统权限与桌面环境而异。

## 界面与外观

界面是「纸与光」：一张暖色纸、一支墨、一枚朱砂。没有侧边栏，顶部是一行目录式导航；主页面由一枚居中的刻度圆环、左侧的今日账本和右侧的本周投入组成，模式沉淀为底部一枚悬浮胶囊。

- 明暗两套纸张：白天是米色纸（`#F3ECDE`），夜里是中性近黑（`#0A0E0D`），同一套颜色令牌互换；暗色只让圆环与模式胶囊带强调色的柔光，底色保持中性不发棕。
- 字体分工：宋体做标题与数字，Consolas 做所有读数，Segoe UI 做正文。
- 线条语言：发丝线、点线引导、斜纹柱状图、印章式日期，没有圆角卡片，也没有数据表格。
- 强调色默认「朱砂」，另有六种上游配色；强调色用于圆环进度、印章、导航下划线与图表。
- 自绘控件：圆环刻度与进度弧、账本行、斜纹柱状图、印章、编号索引都由 QPainter 绘制，窗口缩放时保持清晰。
- 布局在 1040px 以下收起左右两列，只保留圆环与模式胶囊，最小支持 760 × 620。

设计参考：[Folo](https://github.com/RSSNext/Folo)、[Kanri](https://github.com/kanriapp/kanri) 的桌面产品布局与低干扰信息层级，[Catppuccin](https://github.com/catppuccin/palette)、[Dracula](https://github.com/dracula/dracula-theme)、[Nord](https://github.com/nordtheme/nord) 的配色。图标许可见 [第三方声明](THIRD_PARTY_NOTICES.md)。

## 功能特性

- 多模式计时：默认包含“工作”模式，可在设置页新增、编辑、删除模式。
- 累积统计：同一天内同一模式的多段计时会自动累积。
- 统计日口径：一天从 04:00 开始，凌晨 00:00–04:00 仍计入前一天；计时页、日/周/月统计和按任务统计保持一致。
- 历史记录：支持按日、周、月查看不同模式的投入时长。
- 任务统计：在「时间统计 → 按任务」选择任务标签（现有专注模式），查看今日、本周、本月、全部记录或自定义日期范围的专注总量、时段占比、趋势和每日明细；主页「任务统计」可直达当前任务。
- 统计明细：同一天的模式合并日期显示，多模式时增加每日总计与分时段明细。
- 交互图表：周、月柱状图悬浮显示完整日期、星期和累计时长，并提供高亮与生长动效。
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
│       └── style.qss        # 明暗主题与统一控件样式
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
- 没有已选模式时，“开始专注”会启动第一个模式；也可以直接点击模式按钮开始。
- 点击“暂停”可暂停或恢复计时。
- 点击“结束”会保存当前计时段，但不会清空当天累计显示。
- 统计日从 04:00 开始：凌晨 00:00–04:00 的计时仍计入前一天，计时页的日期徽标会标注“统计日至 04:00”，与历史统计、任务统计口径一致。
- 切换模式时，应用会先保存当前模式的本段时间，再开始新模式计时。
- 使用 `Alt + 1 / 2 / 3` 可以切换专注、统计和设置页面；快捷键录入时优先记录组合键。

### 模式管理

在设置页可以新增模式、修改模式名称和颜色。模式颜色会用于主页、历史统计和悬浮球状态显示。

### 按任务查看统计

在「时间统计」切换到「按任务」，选择要查看的任务标签。这里的标签沿用设置中的专注模式，已有记录可直接统计，重命名后仍保留关联。

- 范围支持今日、本周、本月、全部记录和自定义起止日期；左右箭头可翻看相邻时段，「回到本期」回到当前日期。
- 汇总展示累计专注、专注天数、专注日均和单日最高；专注日均只计算有专注记录的日期。
- 上午为 04:00–12:00，下午为 12:00–18:00，晚上为 18:00–次日 04:00。凌晨 4 点前属于前一天，跨时段记录自动拆分，暂停时间不计入。
- 趋势图随范围自动按日、周、月或年汇总，空档保留，悬浮可看精确日期与时长。每日明细按日期倒序，双击可回看当天全部任务。
- 统计读取已保存记录，计时中约每 30 秒自动更新；也可以手动刷新。切换统计范围不会影响计时。

### 外观主题

在 **偏好设置 → 外观** 中选择“浅色 · 清透”或“深色 · 静谧”，也可以用侧栏底部的太阳/月亮按钮快速切换。强调色与明暗模式独立选择，点击即生效并自动保存，登录页也会恢复上次的选择。首次使用仍默认深色与原版薄荷绿。

| 主题色 | 主色值 | 色板来源 |
| --- | --- | --- |
| 明亮蓝 | `#89B4FA` | Catppuccin Mocha · Blue |
| Dracula 紫 | `#BD93F9` | Dracula · Purple |
| Nord 冰青 | `#88C0D0` | Nord · Frost / nord8 |
| 蜜桃橙 | `#FAB387` | Catppuccin Mocha · Peach |
| 玫瑰粉 | `#F5C2E7` | Catppuccin Mocha · Pink |
| 清新绿 | `#A6E3A1` | Catppuccin Mocha · Green |
| 原版薄荷绿 | `#A8D5BA` | Tomato 原有配色 |

参考上游：[Catppuccin 色板](https://github.com/catppuccin/palette/blob/main/palette.json)、[Dracula 色板](https://github.com/dracula/dracula-theme#color-palette-oss)、[Nord 色板](https://github.com/nordtheme/nord/blob/develop/src/nord.styl)。使用上游强调色并适配本项目的明暗模式、悬停、选中、焦点和原生弹窗配色。浅色使用 Latte/Alucard 或相同色相的可读深色版本；模式原始颜色继续保留，显示时自动适配对比度。

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

界面回归测试还覆盖真实 Qt 按钮操作、登录注册、自动保存防重复累计、模式重命名、记录管理、每日图表数据、窄窗口和长模式名、悬浮窗恢复，以及独立进程中的完整启动与退出。Qt 界面测试使用离屏平台；系统级快捷键注册、系统托盘菜单与多屏拖动仍需要在目标系统上人工验证。

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
