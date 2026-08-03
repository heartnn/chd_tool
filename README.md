# 🚀 CHD 智能全能转换工具 (Smart CHD Tool)

**专门解决 Windows 环境下 `chdman` 中文路径报错、乱码，以及智能识别镜像格式（区分 CD/DVD）的终极单文件工具。**

---

## 🌟 为什么需要这个工具？

原生 MAME 的 `chdman` 命令行工具在 Windows 环境下存在若干痛点：

1. **中文路径/文件名报错**：当路径或文件名包含中文、特殊字符或空格时，极易报 `No such file or directory` 错误。
2. **CUE 内部关联断裂**：即便处理 `.cue` 文件，若内部引用的 `.bin` 为中文路径，`chdman` 依然无法读取。
3. **格式盲目误判**：很多老游戏镜像（如 PS1）虽然后缀是 `.iso`，但本质上是 **CD 格式（2352 扇区）**，直接用 `createdvd` 压缩会导致报错或生成的 CHD 无法运行。

**本工具通过 Windows API 宽字符传递 + 绝不翻车的全链路“临时英文映射”机制，彻底解决了以上所有问题！**

---

## ✨ 核心特性

* **🔍 智能二进制内容识别（不看后缀看结构）**：
    * **压缩**：自动嗅探文件二进制头（如 ISO 9660 `CD001` 标记）及 2352 扇区倍数。即使文件后缀叫 `.iso`，只要识别为 CD（如 PS1 镜像），就会自动调用 `createcd` 模式；DVD 镜像则调用 `createdvd` 。
    * **解压**：自动解析 CHD 内部的 `Tag` 元数据 。PS2/PSP/Wii 等 DVD 格式自动解压为 `.iso`；PS1/DC/SS 等 CD 格式自动解压为 **完整的 `.cue` + `.bin**` 轨数据。
* **🔤 100% 路径中文免疫**：
    * **API 级 Unicode 捕获**：使用 `GetCommandLineW` 调用 Windows 内核 API，彻底规避 CMD 拖放乱码 。
    * **双重临时映射**：转换时自动将文件及 `.cue` 内部引用的所有文件临时映射为纯英文名字，转换完成后**安全还原现场** 。
* **📂 全自动 CUE 文本指针修复**：
    * 提取 CHD 为 `.cue + .bin` 时，自动解析并修正 `.cue` 中的 `FILE "xxx.bin"` 文件名指针，确保解压后即使是中文名的 `.cue` 和 `.bin` 也能完美匹配 。
* **📦 真正的单文件可执行程序**：
    * 支持将 `chdman.exe` 打包进 EXE 内部（依赖 PyInstaller），单文件随携随用 。

---

## 🛠️ 使用方法

### 方式 A：拖放操作（推荐）

将一个或多个**镜像文件**（`.iso`、`.cue`、`.bin`、`.img`、`.gdi`、`.chd`）或整个**文件夹**，直接拖拽到 `chd_tool.exe`（或 Python 脚本）图标上：

* **输入压缩镜像** $\rightarrow$ 自动识别 CD/DVD 并压缩为 `.chd` 。
* **输入 `.chd` 文件** $\rightarrow$ PS1 智能还原为 `.cue + .bin` ，PS2 智能还原为 `.iso` 。

### 方式 B：批量自动化递归

把 `chd_tool.exe` 放到你的游戏库根目录下直接**双击运行**。它会自动扫描当前目录及其所有子目录，把未转换的镜像批量处理掉 。

---

## 🔨 打包为单文件 EXE（开发者指引）

本项目代码支持 PyInstaller 单文件打包模式，并内置了 `_MEIPASS` 临时资源定位逻辑 。

1. **环境准备**：  
确保安装了 Python 3.8+ 及 PyInstaller：  
```bash
pip install pyinstaller
```
2. **放置依赖**：  
将 `chd_tool.py` 与 `chdman.exe` 放在同一目录 。
3. **执行一键打包**：  
```bash
pyinstaller -F -c --add-data "chdman.exe;." chd_tool.py
```
*打包完成后，在 `dist/` 文件夹下生成的 `chd_tool.exe` 即为不依赖外部任何文件的终极便携版！* 

---

## 📝 流程图解（CUE/BIN 处理机制）

```text
[用户拖入: 三国志.cue]
       │
       ▼
[读取 CUE 内容并提取内部引用的中文 "三国志.bin"]
       │
       ▼
[双重映射: 三国志.cue -> t_xxxx.cue | 三国志.bin -> t_xxxx_0.bin]
       │
       ▼
[修改 t_xxxx.cue 内部指针指向 -> t_xxxx_0.bin]
       │
       ▼
[调用 chdman (纯英文链路，零报错)]
       │
       ▼
[恢复现场: 生成 三国志.chd，同时恢复原有 CUE 和 BIN 文件名]
```

---

## ⚠️ 注意事项

* 对于原本就存在损坏或引用的 `.bin` 文件丢失的 `.cue` 文件，工具无法挽救，请确保镜像源文件本身完整。
* 本工具适配 MAME `chdman 0.289` 及以上版本 。
* `chdman` 核心程序版权归 MAME 开发团队所有。