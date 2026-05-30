#!/usr/bin/env python3
import sys
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Dict

from core.llm_connector import LLMConfig
from core.autonomous_agent import TUGUMIAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TUGUMIInterface:
    def __init__(self):
        self.agent = None
        self.config_file = Path("tugumi_config.json")
        self.load_config()
        
    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    llm_config = LLMConfig(**config_data)
            else:
                llm_config = LLMConfig()
            self.agent = TUGUMIAgent(llm_config)
            logger.info("✓ TUGUMI エージェント初期化完了")
        except Exception as e:
            logger.error(f"❌ 設定読み込みエラー: {e}")
            self.agent = TUGUMIAgent()
            
    def save_config(self, config: LLMConfig):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "api_key": config.api_key,
                    "model": config.model,
                    "base_url": config.base_url,
                    "timeout": config.timeout
                }, f, indent=2)
            logger.info(f"✓ 設定保存: {self.config_file}")
        except Exception as e:
            logger.error(f"❌ 設定保存失敗: {e}")
            
    def execute_task(self, task: str) -> Dict:
        if not self.agent:
            return {"status": "error", "message": "Agent not initialized"}
        logger.info(f"\n{'='*70}")
        logger.info("🚀 タスク実行開始")
        logger.info(f"{'='*70}\n")
        result = self.agent.process_task(task)
        logger.info(f"\n{'='*70}")
        logger.info("✓ タスク完了")
        logger.info(f"{'='*70}\n")
        return result
        
    def interactive_mode(self):
        logger.info("""
╔════════════════════════════════════════════════════════════╗
║         AutoTUGUMI - Multi-Autonomous AI Agent            ║
║                                                            ║
║ コマンド:                                                   ║
║   task <タスク>       : タスク実行                          ║
║   health              : 健全性確認                        ║
║   help                : ヘルプ                            ║
║   exit                : 終了                              ║
╚════════════════════════════════════════════════════════════╝
""")
        
        while True:
            try:
                user_input = input("\n🤖 TUGUMI> ").strip()
                
                if not user_input:
                    continue
                elif user_input == "exit":
                    logger.info("👋 さようなら！")
                    break
                elif user_input == "health":
                    status = self.agent.get_health_status()
                    logger.info(f"\n✓ 健全性ステータス:\n{json.dumps(status, indent=2, ensure_ascii=False)}")
                elif user_input == "help":
                    logger.info("""
📚 使用方法:
  1. タスク実行: task 調べたい内容
  2. 健全性確認: health
  3. 終了: exit
""")
                elif user_input.startswith("task "):
                    task = user_input[5:].strip()
                    result = self.execute_task(task)
                    logger.info(f"\n📋 実行結果: {result.get('status')}")
                    if result.get('status') == 'success':
                        logger.info(f"✓ 実行ステップ: {result.get('execution_steps')}")
                else:
                    logger.info("❓ 不明なコマンドです。'help' で使用方法を確認してください。")
            except KeyboardInterrupt:
                logger.info("\n👋 中断されました")
                break
            except Exception as e:
                logger.error(f"❌ エラー: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="AutoTUGUMI - Multi-Autonomous AI Agent"
    )
    parser.add_argument("--task", type=str, help="実行するタスク")
    parser.add_argument("--interactive", "-i", action="store_true", help="対話モード")
    parser.add_argument("--health", action="store_true", help="健全性確認")
    
    args = parser.parse_args()
    interface = TUGUMIInterface()
    
    if args.task:
        result = interface.execute_task(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.health:
        status = interface.agent.get_health_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    elif args.interactive or len(sys.argv) == 1:
        interface.interactive_mode()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
