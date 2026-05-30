"""
LLMコネクター：llama.cppサーバーとの通信を管理
推論状態の監視とタイムアウト対応を含む
"""

import requests
import json
import time
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM設定"""
    api_key: str = "tugumi4ag-0905"
    model: str = "gemma-4-E4B-ag-tgm-Q4KM"
    base_url: str = "http://0.0.0.0:8080"
    timeout: int = 600  # 10分（推論用に長く設定）
    heartbeat_interval: int = 5  # ハートビート間隔
    max_retries: int = 3


class LLMHealthMonitor:
    """LLM健全性監視：推論状態をリアルタイム追跡"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.is_running = False
        self.last_response_time = None
        self.inference_start_time = None
        self.is_inferencing = False
        self.heartbeat_thread = None
        self.log = []
        
    def start_heartbeat(self):
        """ハートビート監視開始"""
        self.is_running = True
        self.heartbeat_thread = threading.Thread(daemon=True, target=self._heartbeat_loop)
        self.heartbeat_thread.start()
        
    def stop_heartbeat(self):
        """ハートビート停止"""
        self.is_running = False
        
    def _heartbeat_loop(self):
        """ハートビートループ"""
        while self.is_running:
            if self.is_inferencing:
                elapsed = time.time() - self.inference_start_time
                status = f"[推論中...] 経過時間: {elapsed:.1f}秒"
                self._log(status)
                logger.info(status)
            time.sleep(self.config.heartbeat_interval)
            
    def mark_inference_start(self):
        """推論開始をマーク"""
        self.is_inferencing = True
        self.inference_start_time = time.time()
        self._log(f"[推論開始] {datetime.now().isoformat()}")
        
    def mark_inference_end(self):
        """推論終了をマーク"""
        if self.is_inferencing:
            elapsed = time.time() - self.inference_start_time
            self.is_inferencing = False
            self.last_response_time = elapsed
            self._log(f"[推論完了] 経過時間: {elapsed:.2f}秒")
            
    def _log(self, message: str):
        """ログに記録"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message
        }
        self.log.append(log_entry)
        
    def get_status(self) -> Dict[str, Any]:
        """健全性ステータス取得"""
        status = {
            "is_running": self.is_running,
            "is_inferencing": self.is_inferencing,
            "last_response_time": self.last_response_time,
            "recent_logs": self.log[-10:]
        }
        return status


class LLMConnector:
    """llama.cppサーバーとの通信を管理"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.monitor = LLMHealthMonitor(self.config)
        self.monitor.start_heartbeat()
        self._verify_connection()
        
    def _verify_connection(self):
        """接続確認"""
        try:
            response = requests.get(
                f"{self.config.base_url}/health",
                timeout=5,
                headers={"X-API-Key": self.config.api_key}
            )
            logger.info(f"✓ LLM接続確認: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠ LLM初期接続: {e}")
            
    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        """テキスト生成"""
        self.monitor.mark_inference_start()
        
        try:
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            headers = {
                "X-API-Key": self.config.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.config.base_url}/v1/completions",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0].get("text", "").strip()
            else:
                text = result.get("text", "").strip()
                
            self.monitor.mark_inference_end()
            logger.info(f"✓ 生成完了: {len(text)} characters")
            return text
            
        except requests.Timeout:
            self.monitor.mark_inference_end()
            error_msg = "LLM推論タイムアウト（推論が長すぎます）"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            self.monitor.mark_inference_end()
            logger.error(f"LLM生成エラー: {e}")
            raise
            
    def chat(self, messages: list, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        """チャット形式での生成"""
        self.monitor.mark_inference_start()
        
        try:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            headers = {
                "X-API-Key": self.config.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0].get("message", {}).get("content", "").strip()
            else:
                text = result.get("text", "").strip()
                
            self.monitor.mark_inference_end()
            return text
            
        except requests.Timeout:
            self.monitor.mark_inference_end()
            raise TimeoutError("チャット推論タイムアウト")
        except Exception as e:
            self.monitor.mark_inference_end()
            logger.error(f"チャット生成エラー: {e}")
            raise
            
    def get_health_status(self) -> Dict[str, Any]:
        """健全性ステータス取得"""
        return self.monitor.get_status()
        
    def __del__(self):
        """クリーンアップ"""
        self.monitor.stop_heartbeat()
