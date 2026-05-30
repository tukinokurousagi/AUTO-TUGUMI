import subprocess
from core.utils import save_text_to_documents
import re

def run_shell_command_auto(cmd: str, tag: str = "shell", max_retry: int = 2) -> dict:
    """
    サブプロセス実行・必要ならパッケージ自動導入も試みる（pip/apt）
    結果はDocumentsに自動保存
    """
    for i in range(max_retry):
        try:
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
            stdout, stderr = completed.stdout, completed.stderr
            log = f"CMD: {cmd}\n==========STDOUT==========\n{stdout}\n==========STDERR==========\n{stderr}\n"
            save_text_to_documents(f"subproc_{tag}", log)
            # 必要パッケージ自己導入ルーチン
            if completed.returncode != 0:
                miss = _analyze_missing_package(stderr)
                if miss and i+1 < max_retry:
                    _try_auto_install(miss)
                    continue
            return {"stdout": stdout, "stderr": stderr, "returncode": completed.returncode}
        except Exception as e:
            save_text_to_documents(f"subproc_{tag}_error", str(e))
            return {"error": str(e)}
    return {"fatal_error": f"コマンド失敗: {cmd}"}

def _analyze_missing_package(stderr:str):
    """欠落ライブラリ推定（pip用）"""
    # Python: No module named 'xxx'
    m = re.search(r"No module named '(.*?)'", stderr)
    if m:
        return m.group(1)
    m2 = re.search(r"ModuleNotFoundError: No module named '(.*?)'", stderr)
    if m2:
        return m2.group(1)
    # Linuxコマンド： not found
    m3 = re.search(r"command not found: ([^\n ]+)", stderr)
    if m3:
        return m3.group(1)
    return None

def _try_auto_install(name:str):
    """
    pip/aptの自動導入
    """
    try:
        subprocess.run(f"pip install {name}", shell=True)
    except:
        try:
            subprocess.run(f"apt install -y {name}", shell=True)
        except:
            pass
