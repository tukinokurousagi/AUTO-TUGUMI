import os
import datetime

def save_text_to_documents(filename: str, text: str) -> str:
    """
    AndroidのDocuments（/storage/emulated/0/Documents/AutoTUGUMI_logs）にテキストファイル保存
    """
    base_dir = "/storage/emulated/0/Documents/AutoTUGUMI_logs"
    try:
        os.makedirs(base_dir, exist_ok=True)
        dt = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(base_dir, f"{filename}_{dt}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        return filepath
    except Exception as e:
        return f"[ERROR] ログ保存失敗: {e}"
