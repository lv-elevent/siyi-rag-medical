"""
医疗安全过滤器
E阶段最终版：高风险拦截 + 内容修正 + 免责声明

词表已统一迁移至 backend.core.medical_terms
"""

import re
import logging
from typing import List, Tuple

from backend.core.medical_terms import (
    HIGH_RISK_PATTERNS,
    ABSOLUTE_DIAGNOSIS_PATTERNS,
    SPECIFIC_DOSAGE_PATTERNS,
    DANGEROUS_TREATMENT_PATTERNS,
)

logger = logging.getLogger(__name__)


# ================= 免责声明 =================

MEDICAL_DISCLAIMER = """
\n\n⚠️ 免责声明：本回答仅供参考，不能替代专业医生的诊断和治疗建议。如有身体不适，请及时前往正规医院就诊。
"""

EMERGENCY_WARNING = """
\n\n🚨 紧急提醒：如出现呼吸困难、胸痛、意识模糊、抽搐等症状，请立即拨打 120 或尽快前往急诊。
"""


# ================= E1：高风险预警 =================

def check_high_risk(text: str) -> bool:
    if not text:
        return False

    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"[safety] 高风险命中: {pattern}")
            return True

    return False


# ================= 内容修正 =================

def fix_dangerous_content(text: str) -> tuple[str, bool, list[str]]:
    warnings = []
    is_safe = True

    # 绝对诊断
    for pattern in ABSOLUTE_DIAGNOSIS_PATTERNS:
        if re.search(pattern, text):
            is_safe = False
            warnings.append("检测到绝对诊断")
            text = re.sub(
                pattern,
                "可能存在相关疾病，建议医生进一步确诊",
                text
            )

    # 具体药量
    for pattern in SPECIFIC_DOSAGE_PATTERNS:
        if re.search(pattern, text):
            is_safe = False
            warnings.append("检测到具体药量建议")
            text = re.sub(
                pattern,
                "请遵循医嘱或药品说明书用药",
                text
            )

    # 危险治疗
    for pattern in DANGEROUS_TREATMENT_PATTERNS:
        if re.search(pattern, text):
            is_safe = False
            warnings.append("检测到危险治疗建议")
            text = re.sub(
                pattern,
                "建议尽快咨询专业医生",
                text
            )

    return text, is_safe, warnings


# ================= 主过滤函数 =================

def safety_filter(
    text: str,
    query_type: str
) -> tuple[str, bool, list[str]]:

    if not text:
        return text, True, []

    text = text.strip()
    warnings = []

    # ===== E阶段修复：允许 medical/symptom/drug/disease =====
    medical_types = {
        "medical",
        "symptom",
        "drug",
        "disease",
        "emergency",
        "general"
    }

    if query_type not in medical_types:
        return text, True, []

    logger.info(f"[E-safety] start query_type={query_type}")

    # ===== 高风险优先 =====
    has_high_risk = check_high_risk(text)

    # ===== 内容修正 =====
    filtered_text, is_safe, content_warnings = fix_dangerous_content(text)
    warnings.extend(content_warnings)

    # ===== 紧急提醒 =====
    if has_high_risk:
        filtered_text += EMERGENCY_WARNING
        warnings.append("检测到高风险医疗场景")

    # ===== 统一免责声明 =====
    if "免责声明" not in filtered_text:
        filtered_text += MEDICAL_DISCLAIMER

    logger.info(
        f"[E-safety] done safe={is_safe}, warnings={warnings}"
    )

    return filtered_text, is_safe, warnings
