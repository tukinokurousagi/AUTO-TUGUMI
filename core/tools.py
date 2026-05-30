"""
自律型エージェント用ツール集（統合版）
- Web検索、RSS、スクレイピング、データ処理、サブプロセス実行ツールを含む
"""

import requests
import json
from bs4 import BeautifulSoup
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import time
from urllib.parse import urljoin, urlparse
import validators

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


class WebSearchTool:
    """Web検索ツール（DuckDuckGo HTML + RSS）"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
        })

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """複数ソースから検索結果を収集して返す"""
        logger.info(f"🔍 検索開始: {query}")
        results: List[Dict[str, Any]] = []

        try:
            results.extend(self._search_duckduckgo(query, num_results))
        except Exception as e:
            logger.warning(f"⚠ DuckDuckGo検索失敗: {e}")

        try:
            results.extend(self._search_rss(query, num_results))
        except Exception as e:
            logger.warning(f"⚠ RSS検索失敗: {e}")

        logger.info(f"✓ 検索完了: {len(results)}件取得")
        return results[:num_results]

    def _search_duckduckgo(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """DuckDuckGo HTMLをスクレイピングして結果を抽出（認証不要）"""
        try:
            url = "https://html.duckduckgo.com/html"
            params = {"q": query}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            results: List[Dict[str, Any]] = []

            # DuckDuckGoのHTML構造は変わる可能性があるため、複数セレクタを試す
            items = soup.select('div.result') or soup.select('article') or soup.select('.results_links_deep')
            for item in items[:num_results]:
                try:
                    title_elem = item.select_one('a.result__a') or item.select_one('a')
                    link_elem = item.select_one('a.result__a') or item.select_one('a')
                    snippet_elem = item.select_one('.result__snippet') or item.select_one('.snippet') or item.select_one('a')

                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        # DuckDuckGo may return redirect links; keep as-is
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": href,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                            "source": "DuckDuckGo"
                        })
                except Exception as e:
                    logger.debug(f"個別結果解析失敗: {e}")
                    continue

            return results
        except Exception as e:
            logger.debug(f"DuckDuckGo検索エラー: {e}")
            return []

    def _search_rss(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """RSS/ニュースフィードから関連エントリを抽出"""
        rss_urls = [
            "http://feeds.reuters.com/reuters/topNews",
            "http://feeds.bbci.co.uk/news/rss.xml",
        ]

        results: List[Dict[str, Any]] = []
        q_lower = query.lower()
        for rss_url in rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:num_results]:
                    title = entry.get('title', '')
                    summary = entry.get('summary', '') or entry.get('description', '')
                    if q_lower in title.lower() or q_lower in summary.lower():
                        results.append({
                            "title": title,
                            "url": entry.get('link', ''),
                            "snippet": summary[:200],
                            "source": "RSS",
                            "published": entry.get('published', '')
                        })
            except Exception as e:
                logger.debug(f"RSS解析失敗 ({rss_url}): {e}")

        return results[:num_results]


class WebScraperTool:
    """Webスクレイパーツール"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
        })

    def scrape_content(self, url: str, extract_type: str = "text") -> Dict[str, Any]:
        """ページコンテンツを取得して抽出する"""
        logger.info(f"📄 スクレイピング: {url}")

        try:
            if not validators.url(url):
                logger.warning(f"⚠ 無効なURL: {url}")
                return {"error": "Invalid URL", "url": url}

            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            result: Dict[str, Any] = {
                "url": url,
                "title": soup.title.string if soup.title else "No title",
                "scraped_at": datetime.now().isoformat()
            }

            if extract_type == "text":
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator='\n', strip=True)
                result["content"] = text[:5000]

            elif extract_type == "links":
                links = []
                for link in soup.find_all('a', href=True)[:50]:
                    href = link['href']
                    # 相対パスを絶対URLに変換
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    if href.startswith('http'):
                        links.append({"text": link.get_text(strip=True), "url": href})
                result["links"] = links

            elif extract_type == "structured":
                result["headings"] = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:20]]
                result["paragraphs"] = [p.get_text(strip=True) for p in soup.find_all('p')[:10]]

            logger.info("✓ スクレイピング完了")
            return result

        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
            return {"error": str(e), "url": url}


class DataAnalyzerTool:
    """データ分析・処理ツール"""

    @staticmethod
    def summarize_text(text: str, max_length: int = 500) -> str:
        """簡易テキスト要約"""
        if not text:
            return ""

        # 文を分割して重要そうな文を抽出する簡易ロジック
        sentences = text.replace('。', '。\n').replace('！', '！\n').replace('?', '?\n').split('\n')
        important_sentences: List[str] = []

        for i, sentence in enumerate(sentences):
            s = sentence.strip()
            if len(s) < 10:
                continue
            if i < 2 or i > len(sentences) - 3:
                important_sentences.append(s)
            elif any(keyword in s for keyword in ['重要', '必要', 'について', '方法', '結果']):
                important_sentences.append(s)

            if len(important_sentences) >= 5:
                break

        summary = '。'.join(important_sentences)[:max_length]
        return summary

    @staticmethod
    def extract_key_points(text: str) -> List[str]:
        """キーポイント抽出（箇条書きやマーカーを優先）"""
        if not text:
            return []

        points: List[str] = []
        lines = text.split('\n')

        for line in lines:
            l = line.strip()
            if len(l) > 20 and any(marker in l for marker in ['・', '•', '-', '*']):
                points.append(l.lstrip('・•-* '))

        # 単語ベースの簡易キーワード抽出
        keywords = []
        words = text.split()
        seen = set()
        for word in words:
            w = word.strip().strip('、。,.')
            if len(w) > 3 and w not in ['です', 'ます', 'ある', 'いる', 'する', 'なる'] and w not in seen:
                keywords.append(w)
                seen.add(w)
            if len(keywords) >= 5:
                break

        return points[:10] + keywords[:5]

    @staticmethod
    def format_results(results: List[Dict[str, Any]], format_type: str = "markdown") -> str:
        """検索結果や解析結果をフォーマットして返す"""
        if format_type == "markdown":
            output: List[str] = []
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                url = result.get('url', 'N/A')
                snippet = result.get('snippet') or (result.get('content')[:200] if result.get('content') else '')
                output.append(f"## {i}. {title}")
                output.append(f"📌 **URL**: {url}")
                output.append(f"\n{snippet}")
                output.append("---\n")
            return '\n'.join(output)
        else:
            return json.dumps(results, ensure_ascii=False, indent=2)


# --- 統合された ToolRegistry ---
class ToolRegistry:
    """ツールレジストリ：全ツールを統一管理（web_search, web_scrape, summarize, extract_points, format, shell）"""

    def __init__(self):
        self.web_search = WebSearchTool()
        self.web_scraper = WebScraperTool()
        self.data_analyzer = DataAnalyzerTool()

        # ツール名 -> 呼び出し関数 のマッピング
        self.tools: Dict[str, Any] = {
            "web_search": self._tool_web_search,
            "web_scrape": self._tool_web_scrape,
            "summarize": self._tool_summarize,
            "extract_points": self._tool_extract_points,
            "format": self._tool_format_results,
            "shell": self._tool_shell,  # コードBからの統合
        }

        # サブプロセス実行関数を遅延インポート（存在しない環境でもモジュール読み込み可能にする）
        self._shell_runner = None
        try:
            from core.agent_subproc import run_shell_command_auto  # type: ignore
            self._shell_runner = run_shell_command_auto
        except Exception as e:
            logger.info("サブプロセス実行モジュールが見つかりません。shellツールは実行時にエラーを返します。")

    # --- individual tool wrappers ---
    def _tool_web_search(self, query: str, num_results: int = 5) -> str:
        results = self.web_search.search(query, num_results)
        return json.dumps(results, ensure_ascii=False, indent=2)

    def _tool_web_scrape(self, url: str, extract_type: str = "text") -> str:
        result = self.web_scraper.scrape_content(url, extract_type)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _tool_summarize(self, text: str, max_length: int = 500) -> str:
        summary = self.data_analyzer.summarize_text(text, max_length)
        return summary

    def _tool_extract_points(self, text: str) -> str:
        points = self.data_analyzer.extract_key_points(text)
        return '\n'.join(points)

    def _tool_format_results(self, results_json: str, format_type: str = "markdown") -> str:
        try:
            results = json.loads(results_json)
            formatted = self.data_analyzer.format_results(results, format_type)
            return formatted
        except Exception as e:
            logger.error(f"フォーマットエラー: {e}")
            return results_json

    def _tool_shell(self, cmd: str) -> str:
        """サブプロセス自律実行（core.agent_subproc.run_shell_command_auto を利用）"""
        try:
            if not self._shell_runner:
                raise RuntimeError("run_shell_command_auto is not available in this environment.")
            result = self._shell_runner(cmd, tag="usercmd")
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"shell実行エラー: {e}")
            # エラー情報をJSONで返す（呼び出し側で解釈）
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # --- public API ---
    def get_tool(self, name: str):
        """ツール取得（呼び出し可能な関数を返す）"""
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """利用可能なツール一覧"""
        return list(self.tools.keys())


# --- 簡易デモ / 実行例（モジュールとして読み込まれたときに実行されないように __main__ に格納） ---
if __name__ == "__main__":
    registry = ToolRegistry()
    print("利用可能なツール:", registry.list_tools())

    # 簡単な検索デモ（例）
    try:
        web_search_tool = registry.get_tool("web_search")
        if web_search_tool:
            print("=== Web Search Demo ===")
            print(web_search_tool("Python プログラミング", 3))
    except Exception as e:
        logger.error(f"デモ実行中のエラー: {e}")
