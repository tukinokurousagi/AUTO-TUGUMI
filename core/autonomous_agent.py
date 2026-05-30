import json
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import traceback

from core.llm_connector import LLMConnector, LLMConfig
from core.tools import ToolRegistry

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class TaskContext:
    task_id: str
    user_instruction: str
    goal: str
    plan: List[str]
    execution_log: List[Dict[str, Any]]
    results: Dict[str, Any]
    state: AgentState
    created_at: str
    updated_at: str
    attempt_count: int = 0
    max_attempts: int = 5


class TUGUMIAgent:
    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm_config = llm_config or LLMConfig()
        self.llm = LLMConnector(self.llm_config)
        self.tools = ToolRegistry()
        self.memory = []
        self.task_history = {}
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        logger_obj = logging.getLogger("TUGUMI")
        if not logger_obj.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - TUGUMI - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger_obj.addHandler(handler)
            logger_obj.setLevel(logging.INFO)
        return logger_obj
        
    def process_task(self, user_instruction: str) -> Dict[str, Any]:
        task_id = self._generate_task_id()
        context = TaskContext(
            task_id=task_id,
            user_instruction=user_instruction,
            goal="",
            plan=[],
            execution_log=[],
            results={},
            state=AgentState.IDLE,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🎯 タスク開始: {task_id}")
        self.logger.info(f"📝 指示: {user_instruction}")
        self.logger.info(f"{'='*60}\n")
        
        try:
            self._step_understanding(context)
            self._step_planning(context)
            
            max_iterations = 10
            iteration = 0
            while iteration < max_iterations and context.attempt_count < context.max_attempts:
                iteration += 1
                self.logger.info(f"\n[実行ループ {iteration}/{max_iterations}]")
                
                self._step_executing(context)
                
                if context.state == AgentState.COMPLETE:
                    break
                    
                self._step_evaluating(context)
                
                if context.state == AgentState.COMPLETE:
                    break
                elif context.state == AgentState.ERROR:
                    if context.attempt_count < context.max_attempts:
                        self.logger.warning(f"⚠ エラーから自動復旧: 試行 {context.attempt_count + 1}/{context.max_attempts}")
                        context.attempt_count += 1
                        context.state = AgentState.PLANNING
                        self._step_planning(context)
                    else:
                        break
                        
            context.state = AgentState.COMPLETE
            context.updated_at = datetime.now().isoformat()
            
            result = self._format_final_result(context)
            self.task_history[task_id] = context
            self.memory.append({
                "task_id": task_id,
                "instruction": user_instruction,
                "result_summary": result.get("summary", ""),
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ タスク処理エラー: {e}")
            self.logger.error(traceback.format_exc())
            context.state = AgentState.ERROR
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            
    def _step_understanding(self, context: TaskContext):
        self.logger.info("🧠 ステップ1: 目標理解")
        context.state = AgentState.UNDERSTANDING
        
        prompt = f'ユーザーの指示を分析し、達成すべき目標を明確に定義してください。\nユーザー指示: "{context.user_instruction}"\n以下をJSON形式で出力: {{"goal": "目標", "sub_goals": ["小目標"], "required_information": ["情報"], "success_criteria": "基準"}}'
        
        try:
            response = self.llm.generate(prompt, max_tokens=1024)
            result = self._parse_json(response)
            context.goal = result.get("goal", context.user_instruction)
            context.execution_log.append({
                "step": "understanding",
                "timestamp": datetime.now().isoformat(),
                "result": result
            })
            self.logger.info(f"✓ 目標: {context.goal}")
        except Exception as e:
            self.logger.error(f"❌ 目標理解失敗: {e}")
            context.goal = context.user_instruction
            
    def _step_planning(self, context: TaskContext):
        self.logger.info("📋 ステップ2: 計画立案")
        context.state = AgentState.PLANNING
        available_tools = self.tools.list_tools()
        
        prompt = f'目標を達成するための具体的なアクション計画を立ててください。\n目標: {context.goal}\n利用可能なツール: {", ".join(available_tools)}'
        
        try:
            response = self.llm.generate(prompt, max_tokens=2048, temperature=0.5)
            result = self._parse_json(response)
            context.plan = [step.get("action") for step in result.get("plan", [])]
            context.execution_log.append({
                "step": "planning",
                "timestamp": datetime.now().isoformat(),
                "plan": result
            })
            self.logger.info(f"✓ 計画: {len(context.plan)}ステップ")
        except Exception as e:
            self.logger.error(f"❌ 計画立案失敗: {e}")
            context.plan = ["web_search"]
            
    def _step_executing(self, context: TaskContext):
        self.logger.info("⚙️  ステップ3: 実行中...")
        context.state = AgentState.EXECUTING
        
        analysis_prompt = f'目標: {context.goal}\n計画: {", ".join(context.plan[:3])}\n次のアクションをJSON形式で出力: {{"tool": "ツール", "input": "入力"}}'
        
        try:
            response = self.llm.generate(analysis_prompt, max_tokens=1024)
            action_plan = self._parse_json(response)
            tool_name = action_plan.get("tool", "web_search")
            tool_input = action_plan.get("input", context.goal)
            result = self._execute_tool(tool_name, tool_input)
            
            context.execution_log.append({
                "step": "executing",
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "input": tool_input,
                "result": result if isinstance(result, dict) else {"output": str(result)[:500]}
            })
            
            if tool_name not in context.results:
                context.results[tool_name] = []
            context.results[tool_name].append(result)
            self.logger.info(f"✓ {tool_name} 実行完了")
        except Exception as e:
            self.logger.error(f"❌ 実行エラー: {e}")
            context.state = AgentState.ERROR
            
    def _step_evaluating(self, context: TaskContext):
        self.logger.info("📊 ステップ4: 結果評価")
        context.state = AgentState.EVALUATING
        
        eval_prompt = f'進捗を評価し、次のステップを判断してください��目標: {context.goal}\nJSON形式: {{"progress": "進捗", "is_complete": true/false, "confidence": 0.0-1.0}}'
        
        try:
            response = self.llm.generate(eval_prompt, max_tokens=512)
            evaluation = self._parse_json(response)
            progress = evaluation.get("progress", "50")
            is_complete = evaluation.get("is_complete", False)
            
            self.logger.info(f"✓ 進捗: {progress}%")
            
            if is_complete or evaluation.get("confidence", 0) < 0.1:
                context.state = AgentState.COMPLETE
                self.logger.info("✓ タスク完了")
            else:
                context.state = AgentState.PLANNING
        except Exception as e:
            self.logger.error(f"❌ 評価エラー: {e}")
            context.state = AgentState.COMPLETE
            
    def _execute_tool(self, tool_name: str, tool_input: str) -> Any:
        self.logger.info(f"  → ツール実行: {tool_name}")
        try:
            if tool_name == "web_search":
                return json.loads(self.tools._tool_web_search(tool_input, num_results=5))
            elif tool_name == "web_scrape":
                return json.loads(self.tools._tool_web_scrape(tool_input))
            elif tool_name == "summarize":
                return self.tools._tool_summarize(tool_input)
            elif tool_name == "extract_points":
                return self.tools._tool_extract_points(tool_input)
            else:
                return json.loads(self.tools._tool_web_search(tool_input))
        except Exception as e:
            self.logger.error(f"  ❌ ツール実行エラー: {e}")
            return {"error": str(e), "tool": tool_name}
            
    def _parse_json(self, text: str) -> Dict[str, Any]:
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text
            return json.loads(json_str)
        except:
            return {"raw": text}
            
    def _generate_task_id(self) -> str:
        return f"task_{int(time.time() * 1000)}"
        
    def _format_final_result(self, context: TaskContext) -> Dict[str, Any]:
        return {
            "status": "success",
            "task_id": context.task_id,
            "instruction": context.user_instruction,
            "goal": context.goal,
            "summary": "タスク完了",
            "execution_steps": len(context.execution_log),
            "results": context.results,
            "timestamp": datetime.now().isoformat()
        }
        
    def get_health_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "llm": self.llm.get_health_status(),
            "tools_available": self.tools.list_tools(),
            "memory_size": len(self.memory),
            "timestamp": datetime.now().isoformat()
        }
