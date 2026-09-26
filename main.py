import os
import tkinter as tk
from tkinter import ttk, messagebox


class ExpertSystemToken:
    """Элемент рабочей памяти: Объект = Значение"""

    def __init__(self, obj: str, value: str):
        self.object = obj.strip()
        self.value = value.strip()


class ConditionItem:
    """Одно атомарное условие из правила"""

    def __init__(self, obj: str, value: str):
        self.object = obj.strip()
        self.value = value.strip()
        self.is_checked = False

    def fit(self, token: ExpertSystemToken) -> bool:
        """Проверяет совпадение условия с фактом из рабочей памяти"""
        if self.is_checked:
            return True
        if self.object.lower() == token.object.lower() and self.value.lower() == token.value.lower():
            self.is_checked = True
            return True
        return False


class ConditionSequence:
    """Правило: Набор входных условий (Input) => Результат (Output)"""

    def __init__(self, input_items: list[ConditionItem], output_item: ConditionItem):
        self.input = input_items
        self.output = output_item

    def try_fit(self, tokens: list[ExpertSystemToken]):
        """Проверяет, выполняются ли все условия для срабатывания правила"""
        for token in tokens:
            for item in self.input:
                if not item.is_checked:
                    item.fit(token)

        # Если все условия отмечены истинными
        if all(item.is_checked for item in self.input):
            return self.output
        return None


# ==============================================================================
# ЯДРО ЭКСПЕРТНОЙ СИСТЕМЫ
# ==============================================================================

class ExpertSystemVerdict:
    def __init__(self, is_success: bool, result: str):
        self.is_success = is_success
        self.result = result


class ExpertSystem:
    def __init__(self):
        self._tokens: list[ExpertSystemToken] = []
        self._conditions: list[ConditionSequence] = []

    def add_token(self, text: str):
        """Добавляет новый факт в начальное состояние"""
        text = text.strip()
        if not text or text.startswith("#"):
            return

        parts = text.split("=", 1)
        obj = parts[0].strip()
        val = parts[1].strip() if len(parts) > 1 else "да"
        self._tokens.append(ExpertSystemToken(obj, val))

    def load_rules(self, raw_text: str):
        """Разбирает правила из текста"""
        self._conditions.clear()
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue

            # Разделяем на результат и условия: (вывод) => (условие1) И (условие2)
            rule_parts = line.split("=>", 1)

            # Парсим выходной результат (Output)
            out_str = rule_parts[0].replace("(", "").replace(")", "").strip()
            if "=" not in out_str:
                continue
            out_obj, out_val = out_str.split("=", 1)
            output_item = ConditionItem(out_obj, out_val)

            # Парсим список условий (Input)
            in_conditions = []
            cond_parts = rule_parts[1].split(" И ")
            for cond in cond_parts:
                cond_str = cond.replace("(", "").replace(")", "").strip()
                if "=" in cond_str:
                    c_obj, c_val = cond_str.split("=", 1)
                    in_conditions.append(ConditionItem(c_obj, c_val))

            self._conditions.append(ConditionSequence(in_conditions, output_item))

    def get_result(self) -> ExpertSystemVerdict:
        """Алгоритм прямого вывода"""
        flag = True
        tokens = list(self._tokens)
        conditions = list(self._conditions)

        while flag:
            flag = False
            i = 0
            while i < len(conditions):
                new_item = conditions[i].try_fit(tokens)
                if new_item is not None:
                    # Если правило сработало, выводим новый факт
                    conditions.pop(i)
                    tokens.append(ExpertSystemToken(new_item.object, new_item.value))
                    flag = True
                    # Перезапускаем проход, так как появился новый факт
                    break
                else:
                    i += 1

        # Ищем все выведенные растения
        plants = [t.value for t in tokens if t.object.lower() == "растение"]

        # Удаляем дубликаты
        unique_plants = list(dict.fromkeys(plants))

        if unique_plants:
            return ExpertSystemVerdict(True, ", ".join(unique_plants))
        else:
            return ExpertSystemVerdict(False, "Предоставьте дополнительные факты.")


# ==============================================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (Tkinter в стиле WPF окна одногруппника)
# ==============================================================================

class MainWindow:
    RULES_FILE = "rules.txt"

    def __init__(self, root):
        self.root = root
        self.root.title("Экспертная система")
        self.root.geometry("850x650")

        self.build_ui()
        self.load_rules_from_file()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # 1. Поле правил
        lbl_rules = ttk.LabelFrame(main, text="Правила", padding=5)
        lbl_rules.pack(fill="both", expand=True, pady=5)

        self.txt_rules = tk.Text(lbl_rules, font=("Consolas", 10), wrap="none", height=12)
        self.txt_rules.pack(fill="both", expand=True)

        # Кнопки для файла
        btn_frame_1 = ttk.Frame(main)
        btn_frame_1.pack(fill="x", pady=3)
        ttk.Button(btn_frame_1, text="Сохранить файл", command=self.save_rules_to_file).pack(side="left", padx=3)
        ttk.Button(btn_frame_1, text="Перечитать файл", command=self.load_rules_from_file).pack(side="left", padx=3)

        # 2. Поле начального состояния
        lbl_init = ttk.LabelFrame(main, text="Начальное состояние (каждое условие с новой строки)", padding=5)
        lbl_init.pack(fill="both", expand=True, pady=5)

        self.txt_init = tk.Text(lbl_init, font=("Consolas", 10), wrap="none", height=4)
        self.txt_init.pack(fill="both", expand=True)
        self.txt_init.insert("1.0", "освещение = яркое\nполив = редкий")

        # Кнопка запуска
        btn_frame_2 = ttk.Frame(main)
        btn_frame_2.pack(fill="x", pady=5)
        ttk.Button(btn_frame_2, text="Получить результат", command=self.run_expert_system).pack(side="left")

        # 3. Поле результата
        lbl_res = ttk.LabelFrame(main, text="Результат", padding=5)
        lbl_res.pack(fill="both", expand=True, pady=5)

        self.txt_res = tk.Text(lbl_res, font=("Consolas", 11, "bold"), height=3)
        self.txt_res.pack(fill="both", expand=True)

    def load_rules_from_file(self):
        if os.path.exists(self.RULES_FILE):
            with open(self.RULES_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            self.txt_rules.delete("1.0", "end")
            self.txt_rules.insert("1.0", content)

    def save_rules_to_file(self):
        content = self.txt_rules.get("1.0", "end").strip()
        with open(self.RULES_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Успех", "Правила успешно сохранены в файл.")

    def run_expert_system(self):
        es = ExpertSystem()

        # 1. Загружаем правила из текстового поля
        raw_rules = self.txt_rules.get("1.0", "end")
        es.load_rules(raw_rules)

        # 2. Загружаем факты из начального состояния
        raw_facts = self.txt_init.get("1.0", "end")
        for line in raw_facts.splitlines():
            es.add_token(line)

        # 3. Запускаем прямой вывод
        verdict = es.get_result()

        # 4. Выводим ответ
        self.txt_res.delete("1.0", "end")
        self.txt_res.insert("1.0", f"Результат: {verdict.result}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()