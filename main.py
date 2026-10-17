
import os
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """Факт вида объект = значение."""
    obj: str
    value: str

    def __post_init__(self):
        object.__setattr__(self, "obj", self.obj.strip())
        object.__setattr__(self, "value", self.value.strip())

    def __str__(self):
        return f"{self.obj} = {self.value}"

    def matches(self, other):
        return (
            self.obj.casefold() == other.obj.casefold()
            and self.value.casefold() == other.value.casefold()
        )


@dataclass
class Rule:
    """Правило: заключение => условия."""
    conclusion: Fact
    premises: list


class ExpertSystem:
    def __init__(self):
        self.facts = []
        self.rules = []
        self.log = []
        self.depth = 0
        self.max_depth = 100

    def add_fact(self, text):
        text = text.strip()
        if not text or text.startswith("#"):
            return

        if "=" in text:
            obj, value = text.split("=", 1)
            fact = Fact(obj, value)
        else:
            fact = Fact(text, "да")

        if not any(fact.matches(f) for f in self.facts):
            self.facts.append(fact)

    def load_rules(self, raw_text):
        self.rules.clear()

        for line_no, line in enumerate(raw_text.splitlines(), 1):
            line = line.strip()

            if not line or line.startswith("#") or "=>" not in line:
                continue

            try:
                left, right = line.split("=>", 1)
                conclusion = self.parse_fact(left)
                premises = [
                    self.parse_fact(part)
                    for part in right.split(" И ")
                ]

                if not conclusion or not premises:
                    raise ValueError("пустое заключение или условие")

                self.rules.append(Rule(conclusion, premises))

            except ValueError as error:
                raise ValueError(
                    f"Ошибка в правиле, строка {line_no}: {error}"
                ) from error

    @staticmethod
    def parse_fact(text):
        text = text.strip().replace("(", "").replace(")", "")

        if "=" not in text:
            raise ValueError(f"ожидался факт вида объект = значение: {text}")

        obj, value = text.split("=", 1)
        if not obj.strip() or not value.strip():
            raise ValueError(f"неполный факт: {text}")

        return Fact(obj, value)

    def prove(self, goal, depth=0, path=None):
        """Обратный вывод: доказываем цель через её предпосылки."""
        if path is None:
            path = []

        indent = "  " * depth
        self.log.append(f"{indent}Цель: {goal}")

        if depth > self.max_depth:
            self.log.append(
                f"{indent}Превышена максимальная глубина поиска."
            )
            return False

        # Сначала проверяем, известен ли факт изначально.
        if any(goal.matches(fact) for fact in self.facts):
            self.log.append(f"{indent}Факт найден в рабочей памяти.")
            return True

        # Защита от циклических зависимостей.
        if any(goal.matches(item) for item in path):
            self.log.append(f"{indent}Обнаружен цикл. Ветка отклонена.")
            return False

        # Ищем правила, заключение которых совпадает с целью.
        matching_rules = [
            rule for rule in self.rules
            if goal.matches(rule.conclusion)
        ]

        if not matching_rules:
            self.log.append(
                f"{indent}Нет факта и правил для доказательства цели."
            )
            return False

        for number, rule in enumerate(matching_rules, 1):
            self.log.append(
                f"{indent}Проверяем правило {number}: "
                f"{rule.conclusion} <= "
                + " И ".join(str(p) for p in rule.premises)
            )

            all_proved = True
            next_path = path + [goal]

            for premise in rule.premises:
                if not self.prove(premise, depth + 1, next_path):
                    all_proved = False
                    self.log.append(
                        f"{indent}Условие не доказано: {premise}"
                    )
                    break

            if all_proved:
                self.log.append(
                    f"{indent}Цель доказана: {goal}"
                )
                return True

        self.log.append(f"{indent}Цель не доказана: {goal}")
        return False

    def run(self, goal_text):
        self.log.clear()

        try:
            goal = self.parse_fact(goal_text)
        except ValueError as error:
            return False, str(error), ""

        result = self.prove(goal)

        if result:
            verdict = f"ЦЕЛЬ ДОКАЗАНА: {goal}"
        else:
            verdict = f"ЦЕЛЬ НЕ ДОКАЗАНА: {goal}"

        return result, verdict, "\n".join(self.log)


class MainWindow:
    RULES_FILE = "rules.txt"

    DEFAULT_FACTS = (
        "освещение = тень\n"
        "уход = простой"
    )

    def __init__(self, root):
        self.root = root
        self.root.title("Экспертная система — обратный вывод")
        self.root.geometry("950x750")
        self.build_ui()
        self.load_rules_from_file()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        rules_frame = ttk.LabelFrame(
            main, text="База правил", padding=5
        )
        rules_frame.pack(fill="both", expand=True, pady=5)

        self.txt_rules = tk.Text(
            rules_frame, font=("Consolas", 10), height=12
        )
        self.txt_rules.pack(fill="both", expand=True)

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=3)

        ttk.Button(
            buttons, text="Сохранить правила",
            command=self.save_rules
        ).pack(side="left", padx=3)

        ttk.Button(
            buttons, text="Загрузить правила",
            command=self.load_rules_from_file
        ).pack(side="left", padx=3)

        facts_frame = ttk.LabelFrame(
            main, text="Начальное состояние рабочей памяти",
            padding=5
        )
        facts_frame.pack(fill="x", pady=5)

        self.txt_facts = tk.Text(
            facts_frame, font=("Consolas", 10), height=3
        )
        self.txt_facts.pack(fill="x")
        self.txt_facts.insert("1.0", self.DEFAULT_FACTS)

        goal_frame = ttk.LabelFrame(
            main, text="Целевая ситуация", padding=5
        )
        goal_frame.pack(fill="x", pady=5)

        self.goal_entry = ttk.Entry(
            goal_frame, font=("Consolas", 11)
        )
        self.goal_entry.pack(fill="x")
        self.goal_entry.insert("0", "растение = Сансевиерия")

        ttk.Button(
            main, text="Проверить достижимость цели",
            command=self.run_system
        ).pack(anchor="w", pady=5)

        result_frame = ttk.LabelFrame(
            main, text="Результат и протокол обратного вывода",
            padding=5
        )
        result_frame.pack(fill="both", expand=True, pady=5)

        self.txt_result = tk.Text(
            result_frame, font=("Consolas", 10), height=14,
            wrap="word"
        )
        self.txt_result.pack(fill="both", expand=True)

    def load_rules_from_file(self):
        if os.path.exists(self.RULES_FILE):
            try:
                with open(self.RULES_FILE, "r", encoding="utf-8") as file:
                    content = file.read()
                self.txt_rules.delete("1.0", "end")
                self.txt_rules.insert("1.0", content)
            except OSError as error:
                messagebox.showerror("Ошибка", str(error))
        else:
            messagebox.showinfo(
                "База правил",
                "Файл rules.txt не найден. Вставьте правила "
                "в поле и сохраните их."
            )

    def save_rules(self):
        try:
            content = self.txt_rules.get("1.0", "end").strip()
            with open(self.RULES_FILE, "w", encoding="utf-8") as file:
                file.write(content)
            messagebox.showinfo("Успех", "Правила сохранены.")
        except OSError as error:
            messagebox.showerror("Ошибка сохранения", str(error))

    def run_system(self):
        system = ExpertSystem()

        try:
            system.load_rules(
                self.txt_rules.get("1.0", "end")
            )

            for line in self.txt_facts.get("1.0", "end").splitlines():
                system.add_fact(line)

            if not system.rules:
                raise ValueError("База правил пуста или правила некорректны.")

            success, verdict, protocol = system.run(
                self.goal_entry.get()
            )

        except ValueError as error:
            messagebox.showerror("Ошибка базы знаний", str(error))
            return

        self.txt_result.delete("1.0", "end")
        self.txt_result.insert(
            "1.0",
            verdict + "\n\n"
            + "Протокол рассуждений:\n"
            + "-" * 45 + "\n"
            + protocol
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()
