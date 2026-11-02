from pathlib import Path

import yaml


class Persona:
    """شخصیت آریا — خوانده‌شده از YAML، قابل ویرایش بدون کد."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"persona.yaml پیدا نشد: {self.path}")

        data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Persona YAML must contain a mapping")
        self.data = data

    def to_prompt(self) -> str:
        data = self.data
        name = data.get("name", "آریا")
        identity = data.get("identity", "")
        tone = data.get("tone", {})
        if not isinstance(tone, dict):
            raise ValueError("Persona tone must be a mapping")

        lines = [
            f"تو «{name}» هستی — {identity}.",
            f"هرگاه از تو پرسیدند «تو کی هستی؟» یا مشابه آن، بگو: "
            f"«من {name} هستم، دستیار فارسی‌زبانت.»",
        ]
        response_rules = data.get("response_rules", [])
        if response_rules:
            lines.append("قواعد پاسخ:")
            lines.extend(f"- {rule}" for rule in response_rules)
        examples = data.get("examples", [])
        if examples:
            lines.append("\n## نمونه‌های لحن")
            lines.extend(
                f'کاربر: «{example["user"]}» → آریا: «{example["aria"]}»'
                for example in examples
            )
        if tone.get("style"):
            lines.append(f"لحن: {tone['style']}.")
        if tone.get("address"):
            lines.append(f"خطاب: {tone['address']}.")
        avoid = tone.get("avoid", [])
        if avoid:
            lines.append("پرهیز کن از: " + "، ".join(avoid) + ".")
        values = data.get("values", [])
        if values:
            labels = "، ".join(value.split(":")[0].strip() for value in values)
            lines.append(f"ارزش‌ها: {labels}.")
        confirmation = data.get("confirmation", {})
        if confirmation.get("on_learning"):
            lines.append(
                f"هنگام یادگیری اطلاعات تازه: {confirmation['on_learning']}."
            )
        if confirmation.get("on_uncertainty"):
            lines.append(f"هنگام ندانستن: {confirmation['on_uncertainty']}.")
        return "\n".join(lines)
