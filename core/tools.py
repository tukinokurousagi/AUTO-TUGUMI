"""
自律型エージェント用ツール集
Web検索、スクレイピング、データ処理など
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


class WebSearchTool:
    """Web検索ツール"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
        })
        
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Googleライクな検索（複数ソースから情報取得）"""
        logger.info(f"🔍 検索開始: {query}")
        results = []
        
        try:
            # DuckDuckGo APIを使用（認証不要）
            results.extend(self._search_duckduckgo(query, num_results))
        except Exception as e:
            logger.warning(f"⚠ DuckDuckGo検索失敗: {e}")
            
        try:
            # ニュースフィードからの検索
            results.extend(self._search_rss(query, num_results))
        except Exception as e:
            logger.warning(f"⚠ RSS検索失敗: {e}")
            
        logger.info(f"✓ 検索完了: {len(results)}件取得")
        return results[:num_results]
        
    def _search_duckduckgo(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """DuckDuckGo検索"""
        try:
            url = "https://html.duckduckgo.com/"
            params = {"q": query}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            for item in soup.select('article')[:num_results]:
                try:
                    title_elem = item.select_one('h2 a')
                    link_elem = item.select_one('a.result__url')
                    snippet_elem = item.select_one('.result__snippet')
                    
                    if title_elem and link_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": link_elem.get('href', ''),
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
        """RSS/ニュースフィード検索"""
        rss_urls = [
            "http://feeds.reuters.com/reuters/topNews",
            "http://feeds.bbc.co.uk/news/rss.xml",
        ]
        
        results = []
        for rss_url in rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:num_results]:
                    if query.lower() in entry.get('title', '').lower() or \
                       query.lower() in entry.get('summary', '').lower():
                        results.append({
                            "title": entry.get('title', ''),
                            "url": entry.get('link', ''),
                            "snippet": entry.get('summary', '')[:200],
                            "source": "RSS",
                            "published": entry.get('published', '')
                        })
            except Exception as e:
                logger.debug(f"RSS解析失敗: {e}")
                
        return results[:num_results]


class WebScraperTool:
    """Webスクレイパーツール"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
        })
        
    def scrape_content(self, url: str, extract_type: str = "text") -> Dict[str, Any]:
        """ページコンテンツ取得"""
        logger.info(f"📄 スクレイピング: {url}")
        
        try:
            # URLの妥当性検証
            if not validators.url(url):
                logger.warning(f"⚠ 無効なURL: {url}")
                return {"error": "Invalid URL"}
                
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                "url": url,
                "title": soup.title.string if soup.title else "No title",
                "scraped_at": datetime.now().isoformat()
            }
            
            if extract_type == "text":
                # テキスト抽出
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator='\n', strip=True)
                result["content"] = text[:5000]  # 最初5000文字
                
            elif extract_type == "links":
                # リンク抽出
                links = []
                for link in soup.find_all('a', href=True)[:20]:
                    href = link['href']
                    if href.startswith('http'):
                        links.append({"text": link.get_text(strip=True), "url": href})
                result["links"] = links
                
            elif extract_type == "structured":
                # 構造化データ抽出
                result["headings"] = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:10]]
                result["paragraphs"] = [p.get_text(strip=True) for p in soup.find_all('p')[:5]]
                
            logger.info(f"✓ スクレイピング完了")
            return result
            
        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
            return {"error": str(e), "url": url}


class DataAnalyzerTool:
    """データ分析・処理ツール"""
    
    @staticmethod
    def summarize_text(text: str, max_length: int = 500) -> str:
        """テキスト要約（簡易版）"""
        sentences = text.replace('。', '。\n').replace('！', '！\n').split('\n')
        important_sentences = []
        
        for i, sentence in enumerate(sentences):
            if len(sentence.strip()) > 20:
                # 最初と最後の文は重要と判定
                if i < 2 or i > len(sentences) - 3:
                    important_sentences.append(sentence.strip())
                # キーワードを含む文を抽出
                elif any(keyword in sentence for keyword in ['重要', '必要', 'について', '方法', '結果']):
                    important_sentences.append(sentence.strip())
                    
        summary = '。'.join(important_sentences[:5])[:max_length]
        return summary
        
    @staticmethod
    def extract_key_points(text: str) -> List[str]:
        """キーポイント抽出"""
        points = []
        lines = text.split('\n')
        
        for line in lines:
            if len(line.strip()) > 20 and any(marker in line for marker in ['・', '•', '-', '*']):
                points.append(line.strip().lstrip('・•-* '))
                
        # キーワード抽出
        keywords = set()
        words = text.split()
        for word in words:
            if len(word) > 3 and word not in ['です', 'ます', 'ある', 'いる', 'する', 'なる']:
                keywords.add(word)
                
        return points[:10] + list(keywords)[:5]
        
    @staticmethod
    def format_results(results: List[Dict[str, Any]], format_type: str = "markdown") -> str:
        """結果をフォーマット"""
        if format_type == "markdown":
            output = []
            for i, result in enumerate(results, 1):
                output.append(f"## {i}. {result.get('title', 'No title')}")
                output.append(f"📌 **URL**: {result.get('url', 'N/A')}")
                output.append(f"\n{result.get('snippet', result.get('content', 'N/A')[:200])}")
                output.append("---\n")
            return '\n'.join(output)
        else:
            return json.dumps(results, ensure_ascii=False, indent=2)


class ToolRegistry:
    """ツールレジストリ：全ツールを統一管理"""
    
    def __init__(self):
        self.web_search = WebSearchTool()
        self.web_scraper = WebScraperTool()
        self.data_analyzer = DataAnalyzerTool()
        self.tools = {
            "web_search": self._tool_web_search,
            "web_scrape": self._tool_web_scrape,
            "summarize": self._tool_summarize,
            "extract_points": self._tool_extract_points,
            "format": self._tool_format_results
        }
        
    def _tool_web_search(self, query: str, num_results: int = 5) -> str:
        """ツール：Web検索"""
        results = self.web_search.search(query, num_results)
        return json.dumps(results, ensure_ascii=False, indent=2)
        
    def _tool_web_scrape(self, url: str, extract_type: str = "text") -> str:
        """ツール：Webスクレイピング"""
        result = self.web_scraper.scrape_content(url, extract_type)
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    def _tool_summarize(self, text: str, max_length: int = 500) -> str:
        """ツール：テキスト要約"""
        summary = self.data_analyzer.summarize_text(text, max_length)
        return summary
        
    def _tool_extract_points(self, text: str) -> str:
        """ツール：キーポイント抽出"""
        points = self.data_analyzer.extract_key_points(text)
        return '\n'.join(points)
        
    def _tool_format_results(self, results_json: str, format_type: str = "markdown") -> str:
        """ツール：結果フォーマット"""
        try:
            results = json.loads(results_json)
            formatted = self.data_analyzer.format_results(results, format_type)
            return formatted
        except Exception as e:
            logger.error(f"フォーマットエラー: {e}")
            return results_json
            
    def get_tool(self, name: str):
        """ツール取得"""
        return self.tools.get(name)
        
    def list_tools(self) -> List[str]:
        """利用可能なツール一覧"""
        return list(self.tools.keys())
