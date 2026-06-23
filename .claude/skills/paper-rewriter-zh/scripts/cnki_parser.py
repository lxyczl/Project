"""
知网查重报告解析：HTML 报告 → 结构化数据
支持知网本科/硕博/期刊查重报告（HTML 格式）
用法：$PY cnki_parser.py <报告HTML文件>
"""
import sys
import re
import json
from pathlib import Path
from html.parser import HTMLParser


class CNKIReportParser(HTMLParser):
    """知网查重报告 HTML 解析器"""

    def __init__(self):
        super().__init__()
        self.results = {
            "total_similarity": None,      # 总重复率
            "sections": [],                 # 分段结果
            "red_fragments": [],            # 标红片段（重复内容）
            "sources": [],                  # 来源列表
            "metadata": {}                  # 其他元数据
        }

        # 解析状态
        self._in_red = False       # 是否在标红区域
        self._in_source = False    # 是否在来源区域
        self._current_text = ""
        self._current_source = ""
        self._tag_stack = []

        # 知网报告常见的 CSS class 名
        self.red_classes = {
            "red", "similar", "plagiarism", "repeat",
            "重度", "中度", "轻度", "标红"
        }
        self.source_classes = {
            "source", "reference", "origin", "来源", "文献"
        }

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "").lower()
        style = attrs_dict.get("style", "").lower()

        # 检测标红区域（多种方式）
        is_red = False

        # CSS class 包含红色标记
        if any(cls in class_name for cls in self.red_classes):
            is_red = True

        # style 包含红色
        if "color:red" in style or "color: red" in style:
            is_red = True
        if "background-color:#ff" in style or "background-color: #ff" in style:
            is_red = True
        if "background:red" in style or "background: red" in style:
            is_red = True

        if is_red:
            self._in_red = True
            self._current_text = ""

        self._tag_stack.append(tag)

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        # 标红区域结束
        if self._in_red and self._current_text.strip():
            text = self._current_text.strip()
            if len(text) >= 10:  # 过滤太短的片段
                self.results["red_fragments"].append(text)
            self._current_text = ""
            self._in_red = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        # 提取总重复率
        if self.results["total_similarity"] is None:
            # 匹配 "总文字复制比: 45.2%" 或 "总相似比: 45.2%" 等
            match = re.search(r'(?:总文字复制比|总相似比|总重复率|全文标红比例)[：:]\s*([\d.]+)%', data)
            if match:
                self.results["total_similarity"] = float(match.group(1))

        # 匹配百分比格式
        match = re.search(r'([\d.]+)%', data)
        if match and self.results["total_similarity"] is None:
            percent = float(match.group(1))
            if 0 < percent < 100:
                # 可能是总重复率，暂存
                self.results["metadata"]["possible_similarity"] = percent

        # 收集标红文本
        if self._in_red:
            self._current_text += data

        # 提取来源信息
        if "来源" in data or "相似文献" in data:
            self._in_source = True
        if self._in_source and len(data) > 5:
            self.results["sources"].append(data)

        # 提取章节信息
        section_match = re.match(r'^(第一章|第二章|第三章|第四章|第五章|摘要|引言|结论|参考文献)', data)
        if section_match:
            self.results["sections"].append({
                "name": data[:20],
                "text": ""
            })


def parse_cnki_report(file_path: str) -> dict:
    """解析知网查重报告"""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}

    # 读取 HTML
    try:
        # 知网报告通常是 GBK/GB2312 编码
        for encoding in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                html_content = path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return {"error": "无法解码文件，请检查编码"}
    except Exception as e:
        return {"error": f"读取文件失败: {e}"}

    # 解析
    parser = CNKIReportParser()
    try:
        parser.feed(html_content)
    except Exception as e:
        return {"error": f"解析 HTML 失败: {e}"}

    results = parser.results

    # 后处理
    if results["total_similarity"] is None and "possible_similarity" in results["metadata"]:
        results["total_similarity"] = results["metadata"]["possible_similarity"]

    # 去重
    results["red_fragments"] = list(set(results["red_fragments"]))
    results["sources"] = list(set(results["sources"]))

    # 统计
    results["stats"] = {
        "red_fragment_count": len(results["red_fragments"]),
        "total_red_chars": sum(len(f) for f in results["red_fragments"]),
        "source_count": len(results["sources"])
    }

    return results


def format_cnki_report(results: dict) -> str:
    """格式化解析结果为可读报告"""
    if "error" in results:
        return f"解析失败: {results['error']}"

    lines = []
    lines.append("=" * 60)
    lines.append("知网查重报告解析结果")
    lines.append("=" * 60)

    # 总重复率
    if results["total_similarity"] is not None:
        lines.append(f"\n总文字复制比: {results['total_similarity']}%")
    else:
        lines.append("\n总文字复制比: 未能解析（请检查报告格式）")

    # 统计
    stats = results["stats"]
    lines.append(f"标红片段数: {stats['red_fragment_count']}")
    lines.append(f"重复总字数: {stats['total_red_chars']}")
    lines.append(f"来源文献数: {stats['source_count']}")

    # 标红片段（前20个）
    if results["red_fragments"]:
        lines.append(f"\n{'─' * 60}")
        lines.append("标红片段（重复内容）:")
        lines.append("─" * 60)
        for i, frag in enumerate(results["red_fragments"][:20], 1):
            # 截断过长的片段
            display = frag[:100] + "..." if len(frag) > 100 else frag
            lines.append(f"{i}. [{len(frag)}字] {display}")
        if len(results["red_fragments"]) > 20:
            lines.append(f"... 还有 {len(results['red_fragments']) - 20} 个片段")

    # 来源
    if results["sources"]:
        lines.append(f"\n{'─' * 60}")
        lines.append("来源文献:")
        lines.append("─" * 60)
        for i, src in enumerate(results["sources"][:10], 1):
            lines.append(f"{i}. {src[:80]}")

    return "\n".join(lines)


def extract_hotspots_from_report(results: dict) -> list:
    """从知网报告提取热点句子（供 pipeline 使用）"""
    hotspots = []
    for frag in results.get("red_fragments", []):
        # 按句号分割成句子
        sentences = re.split(r'[。！？]', frag)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) >= 10:
                hotspots.append({
                    "sentence": sent,
                    "source": "cnki_report",
                    "risk": "high"
                })
    return hotspots


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python cnki_parser.py <知网查重报告HTML文件>")
        sys.exit(1)

    file_path = sys.argv[1]
    results = parse_cnki_report(file_path)
    print(format_cnki_report(results))

    # 输出 JSON（可选）
    if "--json" in sys.argv:
        print("\n" + "=" * 60)
        print("JSON 输出:")
        print(json.dumps(results, ensure_ascii=False, indent=2))
