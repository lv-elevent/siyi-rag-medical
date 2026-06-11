"""
医疗问句分类器
职责：将用户问题分类为 medical / knowledge / other 三类
实现：基于关键词词典 + 正则规则 + 轻量打分的混合分类器
说明：
1. medical：偏问诊 / 症状 / 疾病处理 / 用药 / 检查 / 风险判断 / 防治建议
2. knowledge：偏定义 / 概念 / 要素 / 原理 / 机制 / 分类 / 区别 / 作用 / 危害
3. other：非医疗问题
"""

import re
import logging
from typing import List, Set, Tuple

from backend.core.medical_terms import (
    SYMPTOM,
    DISEASE,
    DRUG,
    MEDICAL_ACTION,
    KNOWLEDGE_QUERY,
    ANATOMY,
    NON_MEDICAL,
    SUBJECT,
)

logger = logging.getLogger(__name__)

# 向后兼容别名（与统一词表保持一致）
SYMPTOM_KEYWORDS = SYMPTOM
DISEASE_KEYWORDS = DISEASE
DRUG_KEYWORDS = DRUG
MEDICAL_ACTION_KEYWORDS = MEDICAL_ACTION
KNOWLEDGE_QUERY_KEYWORDS = KNOWLEDGE_QUERY
ANATOMY_KNOWLEDGE_KEYWORDS = ANATOMY
NON_MEDICAL_HINTS = NON_MEDICAL
SUBJECT_TERMS = SUBJECT


# =========================================================
# 规则定义
# =========================================================

MEDICAL_RULES: List[str] = [
    # 症状处理类
    r'.*(?:症状|不舒服|难受).*(?:怎么办|怎么处理|怎么治|怎么缓解)',
    r'.*(?:疼|痛|痒|酸|麻|胀).*(?:怎么办|怎么治|怎么处理|要紧吗|严重吗)',
    r'.*(?:发烧|发热|咳嗽|腹泻|胸闷|呼吸困难).*(?:怎么办|要不要去医院|严重吗)',

    # 就医建议类
    r'.*(?:要不要|要不要紧|是不是|应该).*(?:去医院|看医生|挂科|挂号)',
    r'.*(?:挂什么科|看什么科|去哪个科)',

    # 药物咨询类
    r'.*(?:吃什么|吃啥).*(?:药|片|胶囊)',
    r'.*(?:能不能|可以|可不可以).*(?:吃|服用).*(?:药)',
    r'.*(?:药).*(?:副作用|不良反应|禁忌|注意事项)',

    # 检查结果类
    r'.*(?:体检|检查|化验|检验|结果).*(?:高|低|异常|阳性|阴性)',
    r'.*(?:指标).*(?:高|低|异常)',

    # 严重程度类
    r'.*(?:要紧|严重|危险|紧急|危急|需不需要|是不是)',

    # 疾病处理类
    r'.*(?:得了|患有|确诊).*(?:怎么办|怎么治|如何治疗|如何处理)',
    r'.*(?:高血压|糖尿病|肺结核|胃炎|肺炎).*(?:如何防范|怎么预防|怎么治疗)',
]

KNOWLEDGE_RULES: List[str] = [
    # 定义类
    r'^什么是',
    r'^什么叫',
    r'^什么意思',
    r'.*是什么意思',
    r'.*是什么',

    # 要素 / 作用 / 危害 / 影响
    r'.*的要素(?:是什么|有哪些)?',
    r'.*的危害(?:是什么|有哪些)?',
    r'.*的影响(?:是什么|有哪些)?',
    r'.*的作用(?:是什么|有哪些)?',
    r'.*的特点(?:是什么|有哪些)?',
    r'.*的特征(?:是什么|有哪些)?',

    # 原理机制类
    r'.*(?:原理|机制|病因|病机).*(?:是什么|怎么样|如何)?',
    r'.*(?:发病机制|发病原因).*(?:是什么|怎么样|如何)?',

    # 区别比较类
    r'.*(?:和|与|跟).*(?:区别|差异|不同|区别是什么)',

    # 分类分型类
    r'.*(?:分型|分类|类型|种类).*(?:有哪些|包括|划分)',
    r'.*分(?:哪)?几型',
    r'.*分(?:哪)?几种',
    r'.*有哪些组成',
    r'.*由什么构成',

    # 概念解释类
    r'.*(?:定义|概念).*(?:是什么|怎么样)?',
    r'.*(?:解释|说明|介绍|描述)(?:一下)?',
]


# =========================================================
# 工具函数
# =========================================================

def _preprocess_query(query: str) -> str:
    text = query.strip()
    text = text.replace("？", "?")
    text = text.replace("　", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", "", text)
    return text


def _contains_any(query: str, words: Set[str]) -> bool:
    return any(word in query for word in words)


def _check_rules(query: str, rules: List[str]) -> bool:
    for rule in rules:
        if re.search(rule, query, re.IGNORECASE):
            return True
    return False


def _count_hits(query: str, words: Set[str], weight: int = 1) -> int:
    score = 0
    for word in words:
        if word in query:
            score += weight
    return score


def _score_medical(query: str) -> int:
    score = 0
    score += _count_hits(query, SYMPTOM_KEYWORDS, 2)
    score += _count_hits(query, DISEASE_KEYWORDS, 3)
    score += _count_hits(query, DRUG_KEYWORDS, 3)
    score += _count_hits(query, MEDICAL_ACTION_KEYWORDS, 2)

    # 处理型 / 问诊型强提示
    if any(x in query for x in ["怎么办", "怎么治", "如何治疗", "如何处理", "怎么预防", "如何防范"]):
        score += 3

    if any(x in query for x in ["严重吗", "危险吗", "要不要去医院", "挂什么科"]):
        score += 3

    return score


def _score_knowledge(query: str) -> int:
    score = 0
    score += _count_hits(query, KNOWLEDGE_QUERY_KEYWORDS, 2)
    score += _count_hits(query, ANATOMY_KNOWLEDGE_KEYWORDS, 2)
    score += _count_hits(query, DISEASE_KEYWORDS, 1)
    score += _count_hits(query, DRUG_KEYWORDS, 1)

    # 明显知识问法加权
    if any(x in query for x in ["是什么", "什么意思", "什么叫", "概念", "定义", "解释", "介绍", "说明"]):
        score += 3

    if any(x in query for x in ["要素", "组成", "构成", "分类", "分型", "有哪些", "区别", "危害", "影响", "作用"]):
        score += 3

    return score


def _looks_non_medical(query: str) -> bool:
    if _contains_any(query.lower(), NON_MEDICAL_HINTS):
        return True
    return False


# =========================================================
# 主分类函数
# =========================================================

def classify_medical_question(query: str) -> str:
    """
    返回：
    - medical：问诊 / 症状 / 用药 / 检查 / 风险判断 / 处理建议
    - knowledge：医学知识问答 / 概念 / 定义 / 原理 / 分类 / 要素 / 影响
    - other：非医疗问题
    """
    if not query or not query.strip():
        logger.info("[classifier] 空问题 -> other")
        return "other"

    original_query = query
    query = _preprocess_query(query)

    logger.debug("[classifier] 原始查询: %s", original_query)
    logger.debug("[classifier] 预处理后: %s", query)

    if _looks_non_medical(query):
        logger.info("[classifier] 命中非医疗提示 -> other: %s", original_query)
        return "other"

    # -----------------------------------------------------
    # 0. 医学学科术语优先 knowledge（高优先级）
    # -----------------------------------------------------
    if query in SUBJECT_TERMS:
        logger.info("[classifier] 学科术语精确命中 -> knowledge: %s", original_query)
        logger.info("[classifier] FINAL -> knowledge | question=%s", original_query)
        return "knowledge"

    has_subject_term = _contains_any(query, SUBJECT_TERMS)
    has_knowledge_ask = any(
        x in query for x in [
            "包括什么", "包含什么", "有哪些", "组成", "构成", "分类", "分型",
            "定义", "概念", "是什么",
        ]
    )
    if has_subject_term and has_knowledge_ask:
        logger.info("[classifier] 学科词 + 知识问法 -> knowledge: %s", original_query)
        logger.info("[classifier] FINAL -> knowledge | question=%s", original_query)
        return "knowledge"

    if has_subject_term and len(query) <= 8:
        logger.info("[classifier] 学科术语 + 短query -> knowledge: %s", original_query)
        logger.info("[classifier] FINAL -> knowledge | question=%s", original_query)
        return "knowledge"

    # -----------------------------------------------------
    # 1. 强规则优先
    # -----------------------------------------------------
    if _check_rules(query, MEDICAL_RULES):
        logger.info("[classifier] 规则匹配 -> medical: %s", original_query)
        logger.info("[classifier] FINAL -> medical | question=%s", original_query)
        return "medical"

    if _check_rules(query, KNOWLEDGE_RULES):
        logger.info("[classifier] 规则匹配 -> knowledge: %s", original_query)
        logger.info("[classifier] FINAL -> knowledge | question=%s", original_query)
        return "knowledge"

    # -----------------------------------------------------
    # 2. 评分判定
    # -----------------------------------------------------
    medical_score = _score_medical(query)
    knowledge_score = _score_knowledge(query)

    logger.info(
        "[classifier] score | question=%s | medical_score=%s | knowledge_score=%s",
        original_query,
        medical_score,
        knowledge_score
    )

    # 明显知识型问法优先落 knowledge
    if knowledge_score >= 4 and knowledge_score >= medical_score:
        logger.info("[classifier] 分数匹配 -> knowledge: %s", original_query)
        logger.info(
            "[classifier] FINAL -> knowledge | question=%s | medical_score=%s | knowledge_score=%s",
            original_query, medical_score, knowledge_score
        )
        return "knowledge"

    # 明显问诊 / 处理型落 medical
    if medical_score >= 4:
        logger.info("[classifier] 分数匹配 -> medical: %s", original_query)
        logger.info(
            "[classifier] FINAL -> medical | question=%s | medical_score=%s | knowledge_score=%s",
            original_query, medical_score, knowledge_score
        )
        return "medical"

    # 医学学科词 + 知识问法，优先 knowledge
    if _contains_any(query, ANATOMY_KNOWLEDGE_KEYWORDS | DISEASE_KEYWORDS | DRUG_KEYWORDS):
        if any(x in query for x in ["概念", "定义", "是什么", "什么意思", "解释", "说明", "要素", "组成", "危害", "影响"]):
            logger.info("[classifier] 学科/疾病/药物 + 知识问法 -> knowledge: %s", original_query)
            logger.info(
                "[classifier] FINAL -> knowledge | question=%s | medical_score=%s | knowledge_score=%s",
                original_query, medical_score, knowledge_score
            )
            return "knowledge"

    # 症状 / 疾病 / 药物单独出现时，偏 medical
    if _contains_any(query, SYMPTOM_KEYWORDS | DISEASE_KEYWORDS | DRUG_KEYWORDS):
        logger.info("[classifier] 命中医疗实体 -> medical: %s", original_query)
        logger.info(
            "[classifier] FINAL -> medical | question=%s | medical_score=%s | knowledge_score=%s",
            original_query, medical_score, knowledge_score
        )
        return "medical"

    logger.info(
        "[classifier] FINAL -> other | question=%s | medical_score=%s | knowledge_score=%s",
        original_query, medical_score, knowledge_score
    )
    return "other"


# =========================================================
# 测试函数
# =========================================================

def _demo_test_cases() -> Tuple[int, int]:
    test_cases = [
        # medical
        ("头疼怎么办", "medical"),
        ("我发烧了要不要去医院", "medical"),
        ("咳嗽三天了吃什么药", "medical"),
        ("高血压能不能吃布洛芬", "medical"),
        ("体检说转氨酶高严重吗", "medical"),
        ("胸口疼是不是心脏病", "medical"),
        ("孩子拉肚子怎么处理", "medical"),
        ("感冒了要不要紧", "medical"),
        ("高血压如何防范", "medical"),

        # knowledge
        ("什么是高血压", "knowledge"),
        ("糖尿病分哪几型", "knowledge"),
        ("胰岛素的作用机制", "knowledge"),
        ("流感和普通感冒的区别", "knowledge"),
        ("肺炎的定义是什么", "knowledge"),
        ("什么叫甲状腺功能减退", "knowledge"),
        ("胃溃疡的发病机制", "knowledge"),
        ("药理学是什么意思", "knowledge"),
        ("药理学的要素", "knowledge"),
        ("结核病的危害", "knowledge"),
        ("解剖学的概念", "knowledge"),
        ("局部解剖学是什么意思", "knowledge"),
        ("解剖学", "knowledge"),
        ("局部解剖学", "knowledge"),
        ("药理学", "knowledge"),
        ("病理学", "knowledge"),
        ("传染病学包括什么", "knowledge"),
        ("传染病学有哪些内容", "knowledge"),

        # other
        ("今天天气怎么样", "other"),
        ("帮我写个周报", "other"),
        ("你好", "other"),
        ("介绍一下这个项目", "other"),
        ("Python 怎么读取 json", "other"),
        ("你是谁", "other"),
        ("如何学习编程", "other"),
        ("北京有什么好玩的地方", "other"),
    ]

    correct = 0
    total = len(test_cases)

    for query, expected_label in test_cases:
        result = classify_medical_question(query)
        if result == expected_label:
            correct += 1
        print(f"{query} -> {result} (expected={expected_label})")

    return correct, total


if __name__ == "__main__":
    correct, total = _demo_test_cases()
    print(f"accuracy: {correct}/{total}")