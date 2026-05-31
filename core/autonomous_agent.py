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
from core.utils import savetextto_documents

logger = logging.getLogger(name)


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
    def init(self, llm_config: Optional[LLMConfig] = None):
        self.llmconfig = llmconfig or LLMConfig()
        self.llm = LLMConnector(self.llm_config)
        self.tools = ToolRegistry()
        self.memory = []
        self.task_history = {}
        self.logger = self.setuplogger()

    def setuplogger(self) -> logging.Logger:
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

    def processtask(self, userinstruction: str) -> Dict[str, Any]:
        taskid = self.generatetaskid()
        context = TaskContext(
            taskid=taskid,
            userinstruction=userinstruction,
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
            self.stepunderstanding(context)
            self.stepplanning(context)

            max_iterations = 10
            iteration = 0
            while iteration < maxiterations and context.attemptcount < context.max_attempts:
                iteration += 1
                self.logger.info(f"\n[実行ループ {iteration}/{max_iterations}]")

                self.stepexecuting(context)

                if context.state == AgentState.COMPLETE:
                    break

                self.stepevaluating(context)

                if context.state == AgentState.COMPLETE:
                    break
                elif context.state == AgentState.ERROR:
                    if context.attemptcount < context.maxattempts:
                        self.logger.warning(f"⚠ エラーから自動復旧: 試行 {context.attemptcount + 1}/{context.maxattempts}")
                        context.attempt_count += 1
                        context.state = AgentState.PLANNING
                        self.stepplanning(context)
                    else:
                        break

            context.state = AgentState.COMPLETE
            context.updated_at = datetime.now().isoformat()

            result = self.formatfinal_result(context)

            # --- ここでタスク要約とログを保存（コードB の統合部分） ---
            try:
                savetexttodocuments("tasksummary", result.get("summary", "NoSummary"))
            except Exception as e:
                self.logger.error(f"savetexttodocuments(tasksummary) エラー: {e}")

            try:
                savetexttodocuments("tasklog", json.dumps(result, ensure_ascii=False, indent=2))
            except Exception as e:
                self.logger.error(f"savetexttodocuments(tasklog) エラー: {e}")
            # ----------------------------------------------------------------

            self.taskhistory[taskid] = context
            self.memory.append({
                "taskid": taskid,
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
                "taskid": taskid,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    def stepunderstanding(self, context: TaskContext):
        self.logger.info("🧠 ステップ1: 目標理解")
        context.state = AgentState.UNDERSTANDING

        prompt = (
            f'ユーザーの指示を分析し、達成すべき目標を明確に定義してください。\n'
            f'ユーザー指示: "{context.user_instruction}"\n'
            f'以下をJSON形式で出力: {{"goal": "目標", "subgoals": ["小目標"], "requiredinformation": ["情報"], "success_criteria": "基準"}}'
        )

        try:
            response = self.llm.generate(prompt, max_tokens=1024)
            result = self.parsejson(response)
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

    def stepplanning(self, context: TaskContext):
        self.logger.info("📋 ステップ2: 計画立案")
        context.state = AgentState.PLANNING
        availabletools = self.tools.listtools()

        prompt = (
            f'目標を達成するための具体的なアクション計画を立ててください。\n'
            f'目標: {context.goal}\n'
            f'利用可能なツール: {", ".join(available_tools)}'
        )

        try:
            response = self.llm.generate(prompt, max_tokens=2048, temperature=0.5)
            result = self.parsejson(response)
            # result.get("plan", []) は LLM が返す想定の構造に依存
            context.plan = [step.get("action") for step in result.get("plan", [])] if isinstance(result.get("plan", []), list) else []
            context.execution_log.append({
                "step": "planning",
                "timestamp": datetime.now().isoformat(),
                "plan": result
            })
            self.logger.info(f"✓ 計画: {len(context.plan)}ステップ")
        except Exception as e:
            self.logger.error(f"❌ 計画立案失敗: {e}")
            context.plan = ["web_search"]

    def stepexecuting(self, context: TaskContext):
        self.logger.info("⚙️  ステップ3: 実行中...")
        context.state = AgentState.EXECUTING

        plan_preview = ", ".join(context.plan[:3]) if context.plan else context.goal
        analysis_prompt = (
            f'目標: {context.goal}\n'
            f'計画: {plan_preview}\n'
            f'次のアクションをJSON形式で出力: {{"tool": "ツール", "input": "入力"}}'
        )

        try:
            response = self.llm.generate(analysisprompt, maxtokens=1024)
            actionplan = self.parse_json(response)
            toolname = actionplan.get("tool", "websearch") if isinstance(actionplan, dict) else "web_search"
            toolinput = actionplan.get("input", context.goal) if isinstance(action_plan, dict) else context.goal
            result = self.executetool(toolname, toolinput)

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

    def stepevaluating(self, context: TaskContext):
        self.logger.info("📊 ステップ4: 結果評価")
        context.state = AgentState.EVALUATING

        eval_prompt = (
            f'進捗を評価し、次のステップを判断してください。目標: {context.goal}\n'
            f'JSON形式: {{"progress": "進捗", "is_complete": true/false, "confidence": 0.0-1.0}}'
        )

        try:
            response = self.llm.generate(evalprompt, maxtokens=512)
            evaluation = self.parsejson(response)
            progress = evaluation.get("progress", "50") if isinstance(evaluation, dict) else "50"
            iscomplete = evaluation.get("iscomplete", False) if isinstance(evaluation, dict) else False

            self.logger.info(f"✓ 進捗: {progress}%")

            if is_complete or evaluation.get("confidence", 0) < 0.1:
                context.state = AgentState.COMPLETE
                self.logger.info("✓ タスク完了")
            else:
                context.state = AgentState.PLANNING
        except Exception as e:
            self.logger.error(f"❌ 評価エラー: {e}")
            context.state = AgentState.COMPLETE

    def executetool(self, toolname: str, toolinput: str) -> Any:
        self.logger.info(f"  → ツール実行: {tool_name}")
        try:
            if toolname == "websearch":
                return json.loads(self.tools.toolwebsearch(toolinput, num_results=5))
            elif toolname == "webscrape":
                return json.loads(self.tools.toolwebscrape(toolinput))
            elif tool_name == "summarize":
                return self.tools.toolsummarize(tool_input)
            elif toolname == "extractpoints":
                return self.tools.toolextractpoints(toolinput)
            else:
                return json.loads(self.tools.toolwebsearch(toolinput))
        except Exception as e:
            self.logger.error(f"  ❌ ツール実行エラー: {e}")
            return {"error": str(e), "tool": tool_name}

    def parsejson(self, text: str) -> Dict[str, Any]:
        try:
            if not isinstance(text, str):
                return {"raw": text}
            if "`json" in text:
                json_str = text.split("json")[1].split("")[0]
            elif "`" in text:
                json_str = text.split("")[1].split("")[0]
            else:
                json_str = text
            return json.loads(json_str)
        except Exception:
            return {"raw": text}

    def generatetask_id(self) -> str:
        return f"task_{int(time.time() * 1000)}"

    def formatfinal_result(self, context: TaskContext) -> Dict[str, Any]:
        return {
            "status": "success",
            "taskid": context.taskid,
            "instruction": context.user_instruction,
            "goal": context.goal,
            "summary": "タスク完了",
            "executionsteps": len(context.executionlog),
            "results": context.results,
            "timestamp": datetime.now().isoformat()
        }

    def gethealthstatus(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "llm": self.llm.gethealthstatus(),
            "toolsavailable": self.tools.listtools(),
            "memory_size": len(self.memory),
            "timestamp": datetime.now().isoformat()
        }
