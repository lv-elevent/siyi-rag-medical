def generate_answer(question: str, context: str) -> str:
    lines = [line.strip() for line in context.splitlines() if line.strip()]

    if any(k in question for k in ["学校", "毕业", "院校"]):
        for line in lines:
            if "大学" in line or "学院" in line:
                return f"该人的学校是：{line}"

    if any(k in question for k in ["技能", "技术", "会什么", "擅长"]):
        matched_lines = [
            line for line in lines
            if any(word in line for word in [
                "Java", "Python", "Spring", "SpringBoot", "MySQL",
                "Redis", "Vue", "Linux", "Docker", "Git"
            ])
        ]
        if matched_lines:
            return "根据知识库内容，该人的技能包括：\n" + "\n".join(matched_lines[:5])

    if any(k in question for k in ["工作经历", "经历", "项目", "做过什么"]):
        matched_lines = [
            line for line in lines
            if any(word in line for word in [
                "公司", "项目", "系统", "开发", "实习", "负责"
            ])
        ]
        if matched_lines:
            return "根据知识库内容，该人的相关经历包括：\n" + "\n".join(matched_lines[:6])

    if any(k in question for k in ["姓名", "名字"]):
        for line in lines[:10]:
            if 2 <= len(line) <= 10:
                return f"知识库中可能提到的姓名是：{line}"

    return f"根据知识库内容，找到以下相关信息：\n{context[:200]}"