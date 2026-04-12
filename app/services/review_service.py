from app.models.schemas import ContentItem, ContentReview, ReviewDimension

RISK_KEYWORDS = [
    "最安全",
    "保证",
    "稳赚",
    "包过",
    "治愈",
    "疗效",
    "医美",
    "处方",
    "减肥药",
    "加微信",
    "私信领",
]


def _bounded_score(value: int) -> int:
    return max(0, min(100, value))


def review_content(content: ContentItem) -> ContentReview:
    title = content.title.strip()
    body = content.body.strip()
    cta = content.cta.strip()
    image_suggestion = content.image_suggestion.strip()
    hashtags = [tag.strip() for tag in content.hashtags if tag.strip()]
    combined_text = " ".join([title, body, cta, image_suggestion, " ".join(hashtags)])

    title_len = len(title)
    body_len = len(body)
    hashtag_count = len(hashtags)
    unique_hashtags = len({tag.lstrip("#") for tag in hashtags})

    title_score = 55
    if 8 <= title_len <= 18:
        title_score = 90
    elif 6 <= title_len <= 22:
        title_score = 78
    elif title_len > 0:
        title_score = 60
    if any(char.isdigit() for char in title):
        title_score += 5
    if "?" in title or "？" in title:
        title_score += 5
    title_score = _bounded_score(title_score)

    structure_score = 40
    if body_len >= 80:
        structure_score += 25
    if body_len >= 160:
        structure_score += 10
    if cta:
        structure_score += 15
    if "\n" in body:
        structure_score += 10
    structure_score = _bounded_score(structure_score)

    hashtag_score = 45
    if 3 <= hashtag_count <= 6:
        hashtag_score = 90
    elif 1 <= hashtag_count <= 8:
        hashtag_score = 75
    if unique_hashtags != hashtag_count:
        hashtag_score -= 15
    hashtag_score = _bounded_score(hashtag_score)

    image_score = 35
    if image_suggestion:
        image_score += 35
    if len(image_suggestion) >= 12:
        image_score += 15
    if any(keyword in image_suggestion for keyword in ["场景", "特写", "光线", "构图", "穿搭", "桌面"]):
        image_score += 15
    image_score = _bounded_score(image_score)

    compliance_score = 95
    risk_flags: list[str] = []
    for keyword in RISK_KEYWORDS:
        if keyword in combined_text:
            compliance_score -= 12
            risk_flags.append(f"命中风险词: {keyword}")
    if title_len > 20:
        compliance_score -= 10
        risk_flags.append("标题可能超过平台推荐长度")
    if hashtag_count > 10:
        compliance_score -= 15
        risk_flags.append("话题标签数量偏多")
    compliance_score = _bounded_score(compliance_score)

    dimensions = [
        ReviewDimension(name="标题吸引力", score=title_score, comment="基于标题长度、数字/疑问句等元素评估。"),
        ReviewDimension(name="内容结构", score=structure_score, comment="基于正文长度、分段和 CTA 完整度评估。"),
        ReviewDimension(name="标签质量", score=hashtag_score, comment="基于标签数量与去重情况评估。"),
        ReviewDimension(name="配图可执行性", score=image_score, comment="基于图片描述是否具体、是否具备场景信息评估。"),
        ReviewDimension(name="合规风险", score=compliance_score, comment="基于风险词和平台发布约束进行检查。"),
    ]

    total_score = round(
        title_score * 0.24
        + structure_score * 0.24
        + hashtag_score * 0.16
        + image_score * 0.16
        + compliance_score * 0.20
    )

    suggestions: list[str] = []
    if title_score < 75:
        suggestions.append("优化标题长度，尽量控制在 8-18 字，并加入更明确的利益点。")
    if structure_score < 75:
        suggestions.append("补充更完整的正文结构，增加分段和更自然的互动引导。")
    if hashtag_score < 75:
        suggestions.append("将标签数量控制在 3-6 个，并避免重复或过泛标签。")
    if image_score < 75:
        suggestions.append("细化配图描述，加入场景、主体、构图或光线信息。")
    if compliance_score < 80:
        suggestions.append("删除风险词或过度承诺表达，降低平台审核风险。")
    if not suggestions:
        suggestions.append("内容整体可发布，建议结合账号调性做少量个性化润色。")

    if compliance_score < 60 or len(risk_flags) >= 3:
        risk_level = "high"
    elif compliance_score < 80 or len(risk_flags) >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    publish_ready = total_score >= 75 and risk_level != "high"
    summary = (
        f"综合得分 {total_score} 分，"
        f"{'可以直接进入发布预览' if publish_ready else '建议修改后再发布'}，"
        f"当前风险等级为 {risk_level}。"
    )

    return ContentReview(
        total_score=total_score,
        publish_ready=publish_ready,
        risk_level=risk_level,
        dimensions=dimensions,
        suggestions=suggestions,
        risk_flags=risk_flags,
        summary=summary,
    )


def attach_reviews(contents: list[ContentItem]) -> list[ContentItem]:
    for content in contents:
        content.review = review_content(content)
    return contents
