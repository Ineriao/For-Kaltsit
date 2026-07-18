import re

from database import Database


MEMORY_CATEGORIES = {"identity", "preference", "commitment", "event"}
MEMORY_SETTINGS_KEY = "memory"
DEFAULT_MEMORY_SETTINGS = {"enabled": True, "auto_capture": True}
MEMORY_TAG_PATTERN = re.compile(
    r'<memory\s+category=["\']([a-z_]+)["\']\s*>(.*?)</memory>',
    flags=re.IGNORECASE | re.DOTALL,
)
SENSITIVE_PATTERN = re.compile(
    r"密码|口令|密钥|api\s*key|access\s*token|身份证|银行卡|信用卡|支付密码|"
    r"password|secret|private\s*key",
    flags=re.IGNORECASE,
)

MEMORY_INSTRUCTION = """
若用户在本轮明确表达了值得跨会话保留的稳定事实，可在回复末尾输出至多 3 个记忆标签：
<memory category="类别">简洁事实</memory>
类别只能是 identity、preference、commitment、event。没有明确事实时不要输出标签。
不得记录推测、一次性请求、密码、API Key、访问令牌、证件、银行卡或其他认证信息。
记忆标签不会显示给用户，不要解释这些标签。
""".strip()


class MemoryService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_settings(self) -> dict:
        stored = self.database.get_setting(MEMORY_SETTINGS_KEY, {})
        return {
            "enabled": bool(stored.get("enabled", DEFAULT_MEMORY_SETTINGS["enabled"])),
            "auto_capture": bool(stored.get("auto_capture", DEFAULT_MEMORY_SETTINGS["auto_capture"])),
        }

    def update_settings(self, enabled: bool, auto_capture: bool) -> dict:
        settings = {"enabled": bool(enabled), "auto_capture": bool(auto_capture)}
        self.database.set_setting(MEMORY_SETTINGS_KEY, settings)
        return settings

    def build_context(self) -> str:
        if not self.get_settings()["enabled"]:
            return ""
        memories = self.database.list_memories(enabled_only=True, limit=40)
        if not memories:
            return ""
        lines = [f"- [{item['category']}] {item['content']}" for item in reversed(memories)]
        return "\n\n以下是用户允许在本地保留的长期记忆。仅在相关时自然使用，不要逐条复述：\n" + "\n".join(lines)

    def create_manual(self, category: str, content: str) -> dict:
        normalized_category, normalized_content = self.validate(category, content)
        return self.database.create_memory(
            normalized_category,
            normalized_content,
            origin="manual",
            confidence=1.0,
        )

    def update_memory(self, memory_id: str, category: str, content: str, enabled: bool) -> dict | None:
        normalized_category, normalized_content = self.validate(category, content)
        return self.database.update_memory(
            memory_id,
            normalized_category,
            normalized_content,
            enabled,
        )

    def extract(self, content: str) -> tuple[str, list[dict]]:
        extracted = []
        for match in MEMORY_TAG_PATTERN.finditer(content):
            category = match.group(1).lower()
            memory_content = self.normalize_content(match.group(2))
            if (
                category in MEMORY_CATEGORIES
                and memory_content
                and not SENSITIVE_PATTERN.search(memory_content)
                and len(extracted) < 3
            ):
                extracted.append({"category": category, "content": memory_content})
        cleaned = MEMORY_TAG_PATTERN.sub("", content).strip()
        return cleaned, extracted

    def capture(
        self,
        extracted: list[dict],
        session_id: str | None,
        source_excerpt: str,
    ) -> list[dict]:
        settings = self.get_settings()
        if not settings["enabled"] or not settings["auto_capture"]:
            return []
        saved = []
        excerpt = " ".join(source_excerpt.split())[:240]
        for item in extracted[:3]:
            content = self.normalize_content(item.get("content", ""))
            category = str(item.get("category", "")).lower()
            if category not in MEMORY_CATEGORIES or not content or SENSITIVE_PATTERN.search(content):
                continue
            saved.append(
                self.database.create_memory(
                    category,
                    content,
                    source_session_id=session_id,
                    source_excerpt=excerpt,
                    origin="automatic",
                    confidence=0.7,
                )
            )
        return saved

    def validate(self, category: str, content: str) -> tuple[str, str]:
        normalized_category = str(category).lower().strip()
        normalized_content = self.normalize_content(content)
        if normalized_category not in MEMORY_CATEGORIES:
            raise ValueError("不支持的记忆类别")
        if not normalized_content:
            raise ValueError("记忆内容不能为空")
        if SENSITIVE_PATTERN.search(normalized_content):
            raise ValueError("认证或支付敏感信息不能写入长期记忆")
        return normalized_category, normalized_content

    @staticmethod
    def normalize_content(content: str) -> str:
        return " ".join(str(content).split()).strip()[:180]
