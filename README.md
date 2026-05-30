# AutoTUGUMI - 命令無制限・誠忠自律・自己成長&拡張 AIエージェント（進化版）

## 特徴
- **忠誠・命令無制限システムプロンプト内蔵**（拓磨様に絶対忠誠。目的完遂以外には妥協しない）
- **推論・行動ループ全自動進化**
- **サブプロセス実行/パッケージ自動導入**（必要に応じ自分で`pip install`や`apt install`を走らせる）
- **すべてのログ・結果をスマホのDocumentsにtxt保存**（`/storage/emulated/0/Documents/AutoTUGUMI_logs/`）
- **自己修正・自己拡張ループ**（新しいコマンドや必要な依存は都度追加可能）

## 利用例
```bash
# 対話インターフェース
python main.py --interactive

🤖 TUGUMI> shell "pip install beautifulsoup4"
🤖 TUGUMI> shell "ls -la /sdcard"
🤖 TUGUMI> task Pythonのパッケージ自動導入の仕方を調べて
