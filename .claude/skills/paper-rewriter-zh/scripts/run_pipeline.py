"""
一键分析 pipeline：原文 + 改写文 → 相似度分析 → 热点定位 → 迭代建议
用法：
  $PY run_pipeline.py <原文文件> <改写文件> [学科] [强度] [--project <项目目录>]
  $PY run_pipeline.py --stdin [学科] [强度]  (从 stdin 读取 JSON: {"original": "...", "rewritten": "..."})
  $PY run_pipeline.py --cnki <知网报告HTML> <改写文件> [学科] [强度]  (解析知网报告)
  $PY run_pipeline.py --doc <Word/PDF文件> [学科] [强度]  (解析文档)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from edge_cases import detect_edge_cases, should_skip_rewrite, format_edge_case_report
from reference_loader import load_domains, load_synonyms, get_domain_preserve_terms, get_domain_replacements, get_synonym_suggestions


def check_jieba():
    """检查 jieba 是否可用，不可用时尝试安装"""
    try:
        import jieba
        return True, "ok"
    except ImportError:
        import subprocess
        try:
            py = sys.executable
            subprocess.check_call(
                [py, "-m", "pip", "install", "jieba", "-q"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True, "auto-installed"
        except Exception:
            return False, "install failed"


def run(original: str, rewritten: str, domain: str = "通用",
        intensity: str = "中度", project_dir: Path = None) -> dict:
    """核心 pipeline：输入原文和改写文，返回完整分析结果"""
    from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches
    from feedback_system import FeedbackSystem, evaluate_rewrite_quality, classify_failure

    # jieba 检查
    jieba_ok, jieba_status = check_jieba()

    # 边界情况检测
    edge_issues = detect_edge_cases(original)
    skip = should_skip_rewrite(edge_issues)

    # 相似度计算
    similarity = calculate_similarity(original, rewritten)

    # 反馈系统（数据存项目目录）
    if project_dir:
        feedback_dir = project_dir / ".paper-rewriter"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        fs = FeedbackSystem(feedback_dir)
    else:
        fs = FeedbackSystem()

    # 记录会话
    session = fs.record_rewrite_session(
        original_text=original,
        rewritten_text=rewritten,
        domain=domain,
        intensity=intensity
    )

    # 自动评估
    evaluation = session["auto_evaluation"]

    # 句级热点
    hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)
    for sent in hot_sentences:
        sent["suggested_techniques"] = _suggest_techniques(sent)

    # 是否需要迭代
    needs_iteration = (
        not skip and
        (evaluation["verdict"] == "fail" or
         (evaluation["verdict"] == "warning" and len(hot_sentences) > 0))
    )

    # 获取历史建议
    suggestions = fs.get_rewrite_suggestions(domain, intensity, current_metrics=similarity)

    # 参考文档建议
    domains = load_domains()
    synonyms = load_synonyms()
    preserve_terms = get_domain_preserve_terms(original, domains)
    domain_replacements = get_domain_replacements(original, domains, domain)
    synonym_suggestions = get_synonym_suggestions(original, synonyms)

    # 风险分析引擎
    from analyzer.scorer import analyze_text
    risk_analysis = analyze_text(original)

    # 自动学习
    learn_result = fs.auto_learn(session["session_id"])

    # 报告文本
    report_text = format_report(original, rewritten)

    return {
        "session_id": session["session_id"],
        "similarity": similarity,
        "evaluation": evaluation,
        "hot_sentences": hot_sentences,
        "needs_iteration": needs_iteration,
        "suggestions": suggestions,
        "report": report_text,
        "learn": learn_result,
        "jieba": jieba_status,
        "edge_cases": edge_issues,
        "skip_rewrite": skip,
        "preserve_terms": preserve_terms,
        "domain_replacements": domain_replacements,
        "synonym_suggestions": synonym_suggestions,
        "risk_analysis": risk_analysis,
    }


def _suggest_techniques(sentence_metrics: dict) -> list[str]:
    mc = sentence_metrics.get("max_consecutive", 0)
    tri = sentence_metrics.get("trigram_overlap", 0)

    if mc >= 13:
        return ["句式重组", "拆分长句", "主被动转换"]
    elif mc >= 10:
        return ["句式重组", "同义词替换"]
    elif tri >= 0.25:
        return ["同义词替换", "因果倒置", "条件重组"]
    else:
        return ["同义词替换", "调整语序"]


def format_output(result: dict) -> str:
    """格式化输出给 Claude 看的简洁报告"""
    ev = result["evaluation"]
    sim = result["similarity"]
    hot = result["hot_sentences"]
    sug = result["suggestions"]

    lines = []

    # 边界情况（如果有 error 级别则前置）
    edge_issues = result.get("edge_cases", [])
    if edge_issues:
        lines.append(format_edge_case_report(edge_issues))
        lines.append("")

    if result.get("skip_rewrite"):
        lines.append(">>> 跳过改写（见上方边界情况） <<<")
        return "\n".join(lines)

    # 知网报告数据（如果有）
    cnki = result.get("cnki_report")
    if cnki and cnki.get("total_similarity") is not None:
        lines.append(f"## 知网查重: {cnki['total_similarity']}%")
        stats = cnki.get("stats", {})
        lines.append(f"   标红片段: {stats.get('red_fragment_count', 0)} 个")
        lines.append(f"   重复字数: {stats.get('total_red_chars', 0)} 字")
        lines.append("")

    # 文档信息（如果有）
    doc = result.get("doc_info")
    if doc:
        lines.append(f"## 文档: {doc.get('file', '未知')} ({doc.get('chars', 0)} 字)")
        lines.append("")

    lines.append(f"## 评估: {ev['verdict'].upper()} ({ev['score']}/100)")
    lines.append(f"   {ev['reason']}")
    lines.append("")

    lines.append("## 关键指标")
    lines.append(f"   连续匹配: {sim['max_consecutive']} 字 (阈值 13)")
    lines.append(f"   三元组重叠: {sim['trigram_overlap']:.1%} (阈值 20%)")
    if sim.get("content_word_overlap") is not None:
        lines.append(f"   实词重叠: {sim['content_word_overlap']:.1%}")
    lines.append(f"   分词模式: {sim.get('token_mode', 'char')}")
    lines.append("")

    if hot:
        lines.append(f"## 热点句子 ({len(hot)} 句需重点改写)")
        for i, s in enumerate(hot[:5], 1):
            techniques = ", ".join(s.get("suggested_techniques", []))
            orig = s['original_sentence'][:50]
            lines.append(f"   {i}. {orig}...")
            lines.append(f"      相似度: {s['similarity_score']:.1%}, 连续: {s['max_consecutive']}字")
            lines.append(f"      推荐: {techniques}")
        lines.append("")

    if sug.get("effective_techniques"):
        lines.append("## 历史有效技巧")
        for t in sug["effective_techniques"][:5]:
            lines.append(f"   - {t['technique']} ({t['success_rate']:.0%})")
        lines.append("")

    if sug.get("targeted_advice"):
        lines.append("## 针对建议")
        for a in sug["targeted_advice"]:
            lines.append(f"   - {a}")
        lines.append("")

    # 参考文档建议
    preserve = result.get("preserve_terms", [])
    dom_repl = result.get("domain_replacements", {})
    syn_sug = result.get("synonym_suggestions", {})

    if preserve:
        lines.append("## 保留术语（不可改）")
        lines.append(f"   {', '.join(preserve[:15])}")
        lines.append("")

    if dom_repl:
        lines.append("## 学科替换建议")
        for src, targets in list(dom_repl.items())[:8]:
            lines.append(f"   {src} → {', '.join(targets)}")
        lines.append("")

    if syn_sug:
        lines.append("## 同义词替换建议")
        for src, targets in list(syn_sug.items())[:10]:
            lines.append(f"   {src} → {', '.join(targets[:4])}")
        lines.append("")

    # 风险分析
    risk = result.get("risk_analysis", {})
    if risk and risk.get("overall_risk", 0) > 0:
        lines.append(f"## 风险分析 (综合风险: {risk['overall_risk']:.2f})")
        for ps in risk.get("paragraph_scores", [])[:3]:
            issues = ps.get("issues", [])
            issue_types = [i["detail"] for i in issues[:2]]
            lines.append(f"   段落{ps.get('index', '?')}: 风险={ps['risk']:.2f}, {ps.get('suggestion', '')}")
            for detail in issue_types:
                lines.append(f"      - {detail}")
        lines.append("")

    if result["needs_iteration"]:
        lines.append(">>> 需要迭代改写热点句子 <<<")
    else:
        lines.append(">>> 改写达标，无需迭代 <<<")

    if result["jieba"] != "ok":
        lines.append(f"\n[jieba: {result['jieba']}]")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────

def _parse_common_args(args: list) -> tuple:
    """解析通用参数：--project, domain, intensity"""
    project_dir = None
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_dir = Path(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        else:
            print("错误: --project 需要目录参数")
            sys.exit(1)
    return args, project_dir


def _read_file(path: Path) -> str:
    """读取文件，自动处理编码"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    args, project_dir = _parse_common_args(args)
    domain = "通用"
    intensity = "中度"
    cnki_report_data = None
    doc_info = None

    if args[0] == "--stdin":
        # 从 stdin 读取 JSON
        data = json.loads(sys.stdin.read())
        original = data["original"]
        rewritten = data["rewritten"]
        if len(args) > 1:
            domain = args[1]
        if len(args) > 2:
            intensity = args[2]

    elif args[0] == "--cnki":
        # 知网报告模式：--cnki <报告HTML> <改写文件> [学科] [强度]
        from cnki_parser import parse_cnki_report, format_cnki_report, extract_hotspots_from_report

        if len(args) < 3:
            print("错误: --cnki 需要报告文件和改写文件")
            print("用法: $PY run_pipeline.py --cnki <知网报告HTML> <改写文件> [学科] [强度]")
            sys.exit(1)

        cnki_file = Path(args[1])
        rew_file = Path(args[2])

        if not cnki_file.exists():
            print(f"错误: 知网报告文件不存在: {cnki_file}")
            sys.exit(1)
        if not rew_file.exists():
            print(f"错误: 改写文件不存在: {rew_file}")
            sys.exit(1)

        # 解析知网报告
        cnki_report_data = parse_cnki_report(str(cnki_file))
        if "error" in cnki_report_data:
            print(f"错误: {cnki_report_data['error']}")
            sys.exit(1)

        print(format_cnki_report(cnki_report_data))
        print("\n" + "=" * 60 + "\n")

        # 提取原文（从报告的标红片段重建）和改写文
        # 注意：知网报告可能不包含完整原文，这里用改写文做对比
        rewritten = _read_file(rew_file)

        # 如果有标红片段，用它们作为原文参考
        if cnki_report_data.get("red_fragments"):
            original = "\n".join(cnki_report_data["red_fragments"])
        else:
            print("警告: 未能从报告提取重复片段，请手动提供原文")
            sys.exit(1)

        if len(args) > 3:
            domain = args[3]
        if len(args) > 4:
            intensity = args[4]

    elif args[0] == "--doc":
        # 文档模式：--doc <Word/PDF文件> [学科] [强度]
        from doc_parser import parse_document, clean_extracted_text

        if len(args) < 2:
            print("错误: --doc 需要文件路径")
            print("用法: $PY run_pipeline.py --doc <Word/PDF文件> [学科] [强度]")
            sys.exit(1)

        doc_file = Path(args[1])
        if not doc_file.exists():
            print(f"错误: 文件不存在: {doc_file}")
            sys.exit(1)

        original = parse_document(str(doc_file))
        original = clean_extracted_text(original)
        doc_info = {"file": str(doc_file), "chars": len(original)}

        print(f"文档解析: {doc_file.name} ({len(original)} 字)")
        print("=" * 60 + "\n")

        # 文档模式需要配合改写文，提示用户
        print("注意: 文档模式仅解析原文。请继续提供改写文进行对比分析。")
        print("用法: 将解析结果通过 --stdin 传入，或先保存为 txt 再对比。")
        print("\n提取的原文已输出，请复制使用。")
        sys.exit(0)

    else:
        # 标准模式：<原文文件> <改写文件> [学科] [强度]
        if len(args) < 2:
            print("错误: 需要原文文件和改写文件")
            print("用法: $PY run_pipeline.py <原文文件> <改写文件> [学科] [强度]")
            print("      $PY run_pipeline.py --cnki <知网报告> <改写文件> [学科] [强度]")
            print("      $PY run_pipeline.py --doc <Word/PDF文件> [学科] [强度]")
            sys.exit(1)
        orig_file, rew_file = Path(args[0]), Path(args[1])
        for fpath, label in [(orig_file, "原文"), (rew_file, "改写文")]:
            if not fpath.exists():
                print(f"错误: {label}文件不存在: {fpath}")
                sys.exit(1)
        original = _read_file(orig_file)
        rewritten = _read_file(rew_file)
        if len(args) > 2:
            domain = args[2]
        if len(args) > 3:
            intensity = args[3]

    result = run(original, rewritten, domain, intensity, project_dir)

    # 附加知网报告数据
    if cnki_report_data:
        result["cnki_report"] = cnki_report_data

    # 附加文档信息
    if doc_info:
        result["doc_info"] = doc_info

    # 输出简洁报告
    print(format_output(result))

    # 输出 JSON 到 stderr 供程序化使用
    json_output = {
        "session_id": result["session_id"],
        "verdict": result["evaluation"]["verdict"],
        "score": result["evaluation"]["score"],
        "needs_iteration": result["needs_iteration"],
        "hot_count": len(result["hot_sentences"]),
        "jieba": result["jieba"],
    }
    if cnki_report_data:
        json_output["cnki_similarity"] = cnki_report_data.get("total_similarity")
        json_output["cnki_red_count"] = cnki_report_data.get("stats", {}).get("red_fragment_count", 0)
    print(f"\n[JSON] {json.dumps(json_output, ensure_ascii=False)}", file=sys.stderr)
