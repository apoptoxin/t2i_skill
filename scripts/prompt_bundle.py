#!/usr/bin/env python3
"""Validate cover variables and write a complete fallback prompt bundle."""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List


LAYOUT_TYPES = {"process", "comparison", "evidence"}
BRAND_MODES = {"text", "none"}
REQUIRED_FIELDS = {
    "layout_type",
    "top_label",
    "title_line_1",
    "title_line_2",
    "highlight_phrase",
    "evidence_a",
    "evidence_b",
    "evidence_c",
    "result_label",
    "result_value",
    "bottom_summary",
    "background_objects",
    "accent_color",
    "brand_mode",
    "brand_name",
}
DEMO_LEAKAGE_TERMS = {
    "小刘学AI",
    "45%",
    "32%",
    "8%",
    "新旧封面对比",
    "五类信息检查法",
}
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")

COMMON_STYLE = """
做成有手工痕迹的中文独立杂志封面：暖米白纸张、炭黑撕纸、珊瑚橙、
芥末黄与少量灰青。必须看见纸纤维、复印颗粒、丝网印刷网点、油墨擦痕、
轻微套印偏差、胶带、卷边和分层阴影。画面要有编辑设计感，不像海报模板。
用大小反差、错位、旋转、遮叠、局部出框和不等宽元素制造节奏。
禁止把元素排成等宽、等高、等距的整齐网格。
""".strip()

LAYOUT_PROMPTS = {
    "process": """
这是“混乱输入变成清晰方法”的流程封面。上方约 34% 留出参差但安静的标题区，
不要画规整矩形。中下部左侧放 3 至 5 条宽度不同的米白纸条，旋转角度在
-8° 到 +7° 之间，互相压住，缠着黑色线绳并贴两小段美纹纸胶带；右侧放
3 至 5 张不等宽的票据纸条，间距不等、轻微交替倾斜，索引色块使用灰青、
芥末黄和珊瑚橙。一个粗重的手刷珊瑚橙箭头斜向扫过两组元素，并同时压住
它们。右下放一块倾斜的黑色撕纸结果牌。允许少量元素被画面边缘裁掉。
画面重心故意不均衡，不要做左右等分。
""".strip(),
    "comparison": """
这是“旧版与新版”的对比封面。上方约 38% 是夸张标题区，边缘由撕纸、
笔刷和局部裁切组成。下方左侧放一个较窄、略向左倾斜的旧方案画框，
右侧放一个更大、略向右抬起的新版画框；两个画框的尺寸、角度、边框和
内部材质必须明显不同，不能做成对称双卡。画框可局部越出边界。
一枚粗大的手绘珊瑚橙箭头从左下扫向右上，压住两侧画框。
底部用一条斜着撕开的芥末黄纸带作为结论区，旁边点缀一小块紫色或灰青纸。
视觉上先看到新旧差异，再看到结论，不要画中规中矩的左右分栏。
""".strip(),
    "evidence": """
这是“三组证据指向一个结论”的证据封面。背景是暗色数据墙和旧表格纸，
上方约 35% 留给大标题。中部放三张纸质报告，宽度和高度略有差异，
角度分别接近 -5°、+2°、-3°，前后压住而非整齐并列。三张纸下方用
三枚粗手绘箭头汇聚到一块大型珊瑚橙结论牌。左下让放大镜压住一角数据纸，
右下放一张倾斜的检查清单碎纸，最底部是一条不规则芥末黄总结纸带。
画面要像调查档案墙和杂志拼贴的结合，不像三栏数据仪表盘。
""".strip(),
}


def _text_fields(variables: Dict) -> Iterable:
    for key, value in variables.items():
        if key == "brand_name":
            continue
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield key, item


def _visible_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _select_layout_context(layout_text: str, layout_type: str) -> str:
    """Return only the matching Markdown layout section when possible."""
    heading = layout_type.capitalize()
    pattern = re.compile(
        r"^##\s+{}\s*$([\s\S]*?)(?=^##\s+|\Z)".format(
            re.escape(heading)
        ),
        re.MULTILINE,
    )
    match = pattern.search(layout_text)
    return match.group(1).strip() if match else layout_text.strip()


def validate_variables(variables: Dict, source_script: str) -> List[str]:
    """Return blocking validation errors without mutating the input."""
    errors = []
    missing = sorted(REQUIRED_FIELDS - set(variables))
    if missing:
        errors.append("Missing required fields: {}".format(", ".join(missing)))
        return errors

    if variables["layout_type"] not in LAYOUT_TYPES:
        errors.append(
            "layout_type must be process, comparison, or evidence"
        )
    if variables["brand_mode"] not in BRAND_MODES:
        errors.append("brand_mode must be text or none")
    if variables["brand_mode"] == "none" and variables["brand_name"]:
        errors.append("brand_name must be empty when brand_mode is none")
    if variables["brand_mode"] == "text" and not variables["brand_name"].strip():
        errors.append("brand_name is required when brand_mode is text")

    if not variables["title_line_1"].strip():
        errors.append("title_line_1 must not be empty")
    for field in ("title_line_1", "title_line_2"):
        if _visible_length(variables[field]) > 14:
            errors.append(
                "{} exceeds the 14-character hard limit".format(field)
            )
    if _visible_length(variables["top_label"]) > 8:
        errors.append("top_label exceeds the 8-character hard limit")
    if not isinstance(variables["background_objects"], list):
        errors.append("background_objects must be a list of short strings")

    source_numbers = set(NUMBER_PATTERN.findall(source_script))
    for field, text in _text_fields(variables):
        for number in NUMBER_PATTERN.findall(text):
            if number not in source_numbers:
                errors.append(
                    "{} contains unbacked number {}".format(field, number)
                )

    joined = "\n".join(value for _, value in _text_fields(variables))
    for term in sorted(DEMO_LEAKAGE_TERMS):
        if term in joined and term not in source_script:
            errors.append(
                "Possible Demo leakage: {!r} is absent from source".format(term)
            )
    return errors


def _text_inventory(variables: Dict) -> str:
    rows = [
        ("顶部标签", variables["top_label"]),
        ("主标题第一行", variables["title_line_1"]),
        ("主标题第二行", variables["title_line_2"]),
        ("强调短语", variables["highlight_phrase"]),
        ("证据 A", variables["evidence_a"]),
        ("证据 B", variables["evidence_b"]),
        ("证据 C", variables["evidence_c"]),
        ("结果标签", variables["result_label"]),
        ("结果值", variables["result_value"]),
        ("底部总结", variables["bottom_summary"]),
    ]
    if variables["brand_mode"] == "text":
        rows.append(("右上角账号名", variables["brand_name"]))
    return "\n".join("- {}：{}".format(label, text) for label, text in rows if text)


def build_positive_prompt(
    variables: Dict,
    style_text: str,
    layout_text: str,
    text_mode: str = "full_cover",
) -> str:
    """Build a prompt usable by an external image-generation product."""
    if text_mode not in {"full_cover", "background_only"}:
        raise ValueError("text_mode must be full_cover or background_only")

    objects = "、".join(variables["background_objects"]) or "纸张碎片"
    if text_mode == "full_cover":
        text_instruction = (
            "生成完整中文封面。指定中文必须逐字准确，不得改写、增删、"
            "翻译或产生乱码：\n{}".format(_text_inventory(variables))
        )
    else:
        text_instruction = (
            "只生成无字视觉背景、卡片、箭头和装饰。不要生成主标题、"
            "账号名、数字、标签或任何可读文字，保留明确排版留白。"
        )

    selected_layout = LAYOUT_PROMPTS[variables["layout_type"]]
    supplemental_layout = _select_layout_context(
        layout_text, variables["layout_type"]
    )
    return (
        "用途：抖音短视频封面。画布 1080×1440，比例 3:4。\n"
        "输入参考图：只把与当前布局类型匹配的那一张作为构图与材质参考；"
        "其他参考图只用于理解共同视觉家族，不要把三张图平均融合。\n"
        "布局类型：{layout_type}。\n"
        "本布局的硬性构图：{selected_layout}\n"
        "项目补充构图：{supplemental_layout}\n"
        "共同视觉系统：{common_style}\n"
        "项目补充风格：{style_text}\n"
        "可使用的主题物件：{objects}。物件必须变成有层次的实体拼贴，"
        "不能变成 UI 图标或规则信息卡。\n"
        "主强调色：{accent}。建议色彩占比约为暖米白 52%、炭黑 25%、"
        "珊瑚橙 12%、芥末黄 7%、灰青或紫色 4%。\n"
        "{text_instruction}\n"
        "关键限制：缩小成主页缩略图时只读到一个核心冲突；"
        "主标题最多两行；右侧 12% 不放标题、数字和关键证据；"
        "元素边缘允许粗糙、倾斜和局部裁切，但信息阅读顺序必须清楚。"
        "参考图只学习层级、色彩、构图张力、拼贴质感和阅读顺序，"
        "禁止复制参考图文字、数字、账号名、商标和具体内容。\n"
        "避免：整齐网格、等距卡片、圆角 UI、PPT、公司信息图、"
        "扁平矢量、蓝紫霓虹、赛博朋克、机器人、AI 大脑、芯片、"
        "玻璃拟态、居中对称、相同矩形、细线连接箭头。"
    ).format(
        layout_type=variables["layout_type"],
        selected_layout=selected_layout,
        supplemental_layout=supplemental_layout,
        common_style=COMMON_STYLE,
        style_text=style_text.strip(),
        objects=objects,
        accent=variables["accent_color"],
        text_instruction=text_instruction,
    )


def build_negative_prompt(variables: Dict) -> str:
    forbidden = sorted(DEMO_LEAKAGE_TERMS - {variables.get("brand_name", "")})
    return (
        "禁止：错别字、乱码、英文替代中文、裁字、文字重叠、内容贴边、"
        "多组并列大标题、密集小字、无意义箭头、平台 Logo、水印、"
        "期数编号、蓝紫霓虹赛博朋克、3D 机器人、AI 大脑、芯片主视觉、"
        "商务 PPT、发布会背景、玻璃拟态、等宽等高卡片、左右完全对称、"
        "三栏仪表盘、规则 UI 网格、细线箭头。不得出现 Demo 内容：{}。"
    ).format("、".join(forbidden))


def build_layout_spec(variables: Dict) -> str:
    layout_notes = {
        "process": (
            "左侧是不等宽、相互遮叠的混乱纸条；右侧是不等宽、轻微旋转的"
            "方法票据；粗手刷箭头跨过两组元素；右下给结果。"
        ),
        "comparison": (
            "左侧旧方案窄且略倾斜，右侧新方案更大且抬起；两框不能对称；"
            "粗手绘箭头压住二者；底部斜撕纸带说明真正变化。"
        ),
        "evidence": (
            "三张证据纸前后遮叠、尺寸与角度不同；三枚粗箭头汇聚到结果牌；"
            "放大镜、检查碎纸和底部纸带构成第二阅读层。"
        ),
    }
    return (
        "# 封面排版说明\n\n"
        "- 画布：1080×1440（3:4）\n"
        "- 安全边距：四周至少 54px\n"
        "- 主标题：最多两行，白/黄/橙实字，黑色粗描边\n"
        "- 布局：{layout}\n"
        "- 骨架：{notes}\n"
        "- 右侧交互区：不放主标题、结果值和关键证据\n\n"
        "## 指定文字\n\n{text}\n"
    ).format(
        layout=variables["layout_type"],
        notes=layout_notes[variables["layout_type"]],
        text=_text_inventory(variables),
    )


def write_prompt_bundle(
    output_dir: Path,
    variables: Dict,
    source_script: str,
    style_text: str,
    layout_text: str,
) -> List[Path]:
    errors = validate_variables(variables, source_script)
    if errors:
        raise ValueError("\n".join(errors))

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "variables": output_dir / "cover-variables.json",
        "prompt": output_dir / "cover-prompt.txt",
        "negative": output_dir / "negative-prompt.txt",
        "layout": output_dir / "layout-spec.md",
    }
    paths["variables"].write_text(
        json.dumps(variables, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    full_prompt = build_positive_prompt(
        variables, style_text, layout_text, text_mode="full_cover"
    )
    background_prompt = build_positive_prompt(
        variables, style_text, layout_text, text_mode="background_only"
    )
    paths["prompt"].write_text(
        "【可直接复制：完整封面】\n"
        + full_prompt
        + "\n\n【两步生成：仅背景】\n"
        + background_prompt
        + "\n",
        encoding="utf-8",
    )
    paths["negative"].write_text(
        build_negative_prompt(variables) + "\n", encoding="utf-8"
    )
    paths["layout"].write_text(
        build_layout_spec(variables), encoding="utf-8"
    )
    return list(paths.values())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-script", required=True, type=Path)
    parser.add_argument("--variables", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--style-file", required=True, type=Path)
    parser.add_argument("--layout-file", required=True, type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    variables = json.loads(args.variables.read_text(encoding="utf-8"))
    paths = write_prompt_bundle(
        args.output,
        variables,
        args.source_script.read_text(encoding="utf-8"),
        args.style_file.read_text(encoding="utf-8"),
        args.layout_file.read_text(encoding="utf-8"),
    )
    print(
        json.dumps(
            {"files": [str(path) for path in paths]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
