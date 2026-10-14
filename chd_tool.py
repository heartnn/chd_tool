import os
import sys
import subprocess
import ctypes
import uuid
import re
from pathlib import Path

# 强制控制台输出为 UTF-8，确保中文显示不乱码
os.system("chcp 65001 > nul")

def get_chdman_path():
    """获取 chdman.exe 路径，支持 PyInstaller 单文件模式"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时解压路径
        chdman = os.path.join(sys._MEIPASS, "chdman.exe")
    else:
        # 普通 Python 运行模式，找脚本同目录
        chdman = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chdman.exe")
    
    if not os.path.exists(chdman):
        # 兜底：如果还是找不到，尝试在当前运行目录下找
        chdman = os.path.join(os.getcwd(), "chdman.exe")
        
    return chdman

def get_unicode_args():
    """通过 Windows API 获取原始 Unicode 参数，彻底解决拖放中文乱码"""
    GetCommandLineW = ctypes.windll.kernel32.GetCommandLineW
    GetCommandLineW.restype = ctypes.c_wchar_p
    CommandLineToArgvW = ctypes.windll.shell32.CommandLineToArgvW
    CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argc = ctypes.c_int(0)
    argv = CommandLineToArgvW(GetCommandLineW(), ctypes.byref(argc))
    return [argv[i] for i in range(1, argc.value)]

def identify_format(file_path):
    """基于二进制内容识别镜像格式 (CD 或 DVD)"""
    try:
        size = file_path.stat().st_size
        if size == 0: return "cd"
        # 1. 扇区大小检测 (CD 原始镜像通常能被 2352 整除)
        if size % 2352 == 0: return "cd"
        
        # 2. ISO 9660 幻数检测
        with open(file_path, "rb") as f:
            f.seek(0x8001) # 标准数据模式偏移
            if f.read(5) == b"CD001":
                return "cd" if size < 900 * 1024 * 1024 else "dvd"
            f.seek(0x9311) # Raw 模式偏移
            if f.read(5) == b"CD001": return "cd"
    except Exception:
        pass
    return "dvd" if file_path.suffix.lower() == ".iso" else "cd"

def process_file(file_path, chdman_exe):
    p = Path(file_path).absolute()
    if not p.exists(): return
    
    folder = p.parent
    original_cwd = os.getcwd()
    os.chdir(folder) # 切换工作目录，简化路径复杂度

    ext = p.suffix.lower()
    temp_stem = "t_" + uuid.uuid4().hex[:6] # 纯英文临时文件名
    temp_input = temp_stem + ext
    temp_output = temp_stem + ".chd"
    
    linked_files = [] 
    cue_content_original = None

    try:
        # --- 步骤 1: 准备输入文件 (特殊处理 CUE 及其关联的 BIN) ---
        if ext == ".cue":
            content = ""
            for enc in ['utf-8', 'gbk', 'shift-jis', 'big5']:
                try:
                    with open(p.name, "r", encoding=enc) as f:
                        content = f.read()
                        cue_content_original = content
                        break
                except Exception:
                    continue
            
            if cue_content_original:
                matches = re.findall(r'FILE\s+"(.*?)"', content, re.IGNORECASE)
                new_content = content
                for i, old_bin in enumerate(matches):
                    if os.path.exists(old_bin):
                        bin_ext = Path(old_bin).suffix
                        t_bin_name = f"{temp_stem}_{i}{bin_ext}"
                        os.rename(old_bin, t_bin_name)
                        linked_files.append((old_bin, t_bin_name))
                        new_content = new_content.replace(f'"{old_bin}"', f'"{t_bin_name}"')
                
                with open(temp_input, "w", encoding="utf-8") as f:
                    f.write(new_content)
            else:
                os.rename(p.name, temp_input)
        else:
            os.rename(p.name, temp_input)

        # --- 步骤 2: 执行 CHDMAN 操作 ---
        
        # === 逻辑 A: 解压缩 (CHD 还原为 镜像/CUE+BIN) ===
        if ext == ".chd":
            res = subprocess.run([chdman_exe, "info", "-i", temp_input], capture_output=True, text=True, errors='ignore')
            
            # 通过 track 的 mode 识别，/2048 为 DVD (PS2)，/2352 等为 CD
            is_dvd = bool(re.search(r'TYPE:\s*\w+/2048', res.stdout)) or "Tag: 'DVD '" in res.stdout
            
            if is_dvd:
                mode = "extractdvd"
                temp_extract_out = temp_stem + ".iso"
                real_out = p.stem + ".iso"
                print(f">>> 智能识别 [DVD/PS2], 正在还原 ISO: {p.name}")
            else:
                mode = "extractcd"
                temp_extract_out = temp_stem + ".cue"
                real_out = p.stem + ".cue"
                print(f">>> 智能识别 [CD/PS1], 正在还原 CUE+BIN: {p.name}")
            
            if not Path(real_out).exists():
                subprocess.run([chdman_exe, mode, "-i", temp_input, "-o", temp_extract_out])
                
                if not is_dvd and os.path.exists(temp_extract_out):
                    temp_bin = temp_stem + ".bin"
                    real_bin = p.stem + ".bin"
                    
                    if os.path.exists(temp_bin):
                        os.rename(temp_bin, real_bin)
                    
                    try:
                        with open(temp_extract_out, "r", encoding="utf-8", errors="ignore") as f:
                            cue_text = f.read()
                        cue_text = cue_text.replace(f'"{temp_bin}"', f'"{real_bin}"')
                        with open(temp_extract_out, "w", encoding="utf-8") as f:
                            f.write(cue_text)
                    except Exception:
                        pass
                
                if os.path.exists(temp_extract_out):
                    os.rename(temp_extract_out, real_out)
            else:
                print(f"--- 跳过: {real_out} 已存在")

        # === 逻辑 B: 压缩 (镜像 转为 CHD) ===
        elif ext in [".iso", ".cue", ".bin", ".img", ".gdi"]:
            real_out = p.stem + ".chd"
            if not Path(real_out).exists():
                fmt = identify_format(Path(temp_input))
                mode = "createcd" if fmt == "cd" else "createdvd"
                print(f">>> 智能识别 [{fmt.upper()}], 正在压缩: {p.name}")
                subprocess.run([chdman_exe, mode, "-i", temp_input, "-o", temp_output])
                if os.path.exists(temp_output):
                    os.rename(temp_output, real_out) # 成功重命名为真实的中文名字
            else:
                print(f"--- 跳过: {real_out} 已存在")

    except Exception as e:
        print(f"处理 {p.name} 时出错: {e}")
    finally:
        # --- 步骤 3: 还原现场 ---
        if ext == ".cue" and cue_content_original:
            if os.path.exists(temp_input): 
                os.remove(temp_input)
        elif os.path.exists(temp_input):
            os.rename(temp_input, p.name)

        # 还原被重命名的 BIN 文件
        for old_b, new_b in linked_files:
            if os.path.exists(new_b): 
                os.rename(new_b, old_b)
            
        os.chdir(original_cwd)

def main():
    chdman_exe = get_chdman_path()
    if not chdman_exe or not os.path.exists(chdman_exe):
        print(f"致命错误: 无法定位 chdman.exe\n程序路径: {sys.executable}")
        os.system("pause")
        return

    args = get_unicode_args()
    
    if not args:
        print("未检测到拖放文件，开始递归扫描当前目录...")
        exts = {".chd", ".iso", ".cue", ".bin", ".img", ".gdi"}
        for root, _, files in os.walk("."):
            for f in files:
                if Path(f).suffix.lower() in exts:
                    process_file(Path(root) / f, chdman_exe)
    else:
        for arg in args:
            p = Path(arg)
            if p.is_file():
                process_file(p, chdman_exe)
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.suffix.lower() in {".chd", ".iso", ".cue", ".bin", ".img", ".gdi"}:
                        process_file(f, chdman_exe)

    print("\n[所有任务处理完成]")
    os.system("pause")

if __name__ == "__main__":
    main()
