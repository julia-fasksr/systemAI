"""
Лабораторная работа № 3. Нечёткие системы логического вывода.
Предметная область: подбор комнатных растений по условиям помещения.

Запуск:
    pip install matplotlib
    python lab3_gui.py

Рядом с программой должны находиться rules_single.txt и rules_multi.txt.
"""

from __future__ import annotations

import math
import os
import shlex
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ---------------------------------------------------------------------
# Функции принадлежности
# ---------------------------------------------------------------------

def triangular(a: float, b: float, c: float):
    """Треугольная функция принадлежности."""
    if not a <= b <= c or a == c:
        raise ValueError("Для треугольной функции требуется a <= b <= c и a < c.")

    def membership(x: float) -> float:
        if x < a or x > c:
            return 0.0
        if x == b:
            return 1.0
        if x < b:
            return (x - a) / (b - a) if b != a else 1.0
        return (c - x) / (c - b) if c != b else 1.0

    return membership


def trapezoidal(a: float, b: float, c: float, d: float):
    """Трапециевидная функция принадлежности."""
    if not a <= b <= c <= d or a == d:
        raise ValueError("Для трапециевидной функции требуется a <= b <= c <= d и a < d.")

    def membership(x: float) -> float:
        if x < a or x > d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if x < b:
            return (x - a) / (b - a) if b != a else 1.0
        return (d - x) / (d - c) if d != c else 1.0

    return membership


# ---------------------------------------------------------------------
# Нечёткие операторы
# ---------------------------------------------------------------------

IMPLICATIONS = {
    "Мамдани": lambda alpha, beta: min(alpha, beta),
    "Ларсен": lambda alpha, beta: alpha * beta,
}

AGGREGATIONS = {
    "Максимум": max,
    "Ограниченная сумма": lambda a, b: min(1.0, a + b),
    "Вероятностная сумма": lambda a, b: a + b - a * b,
}

DEFAULT_AGGREGATION = "Максимум"


def numerical_grid(lower: float, upper: float, points: int = 201) -> list[float]:
    """Равномерная сетка значений универсального множества."""
    if points < 2:
        raise ValueError("Количество точек сетки должно быть не меньше двух.")
    return [
        lower + (upper - lower) * index / (points - 1)
        for index in range(points)
    ]


def centroid(values: list[float], membership_values: list[float]):
    """Дефаззификация методом центра тяжести для дискретной сетки."""
    denominator = sum(membership_values)
    if denominator <= 1e-12:
        return None
    numerator = sum(x * degree for x, degree in zip(values, membership_values))
    return numerator / denominator


# ---------------------------------------------------------------------
# Загрузка базы знаний из отдельного текстового файла
# ---------------------------------------------------------------------

def load_knowledge_base(file_path: str) -> dict:
    """
    Формат базы знаний:
      VAR имя IN/OUT минимум максимум "Отображаемое название"
      SET переменная термин tri/trap параметры...
      RULE IF переменная IS термин AND ... THEN выход IS термин
      PLANT числовой_центр "Названия растений"
      CASE переменная=значение ...
    """
    model = {
        "variables": {},
        "sets": {},
        "rules": [],
        "plants": [],
        "test_cases": [],
        "source": file_path,
    }

    with open(file_path, "r", encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            try:
                parts = shlex.split(line)
                command = parts[0].upper()

                if command == "VAR":
                    name, kind = parts[1], parts[2].upper()
                    lower, upper = float(parts[3]), float(parts[4])
                    display_name = parts[5] if len(parts) > 5 else name
                    if kind not in ("IN", "OUT") or lower >= upper:
                        raise ValueError("неверное описание переменной")
                    model["variables"][name] = {
                        "kind": kind,
                        "min": lower,
                        "max": upper,
                        "label": display_name,
                    }

                elif command == "SET":
                    variable, term, shape = parts[1], parts[2], parts[3].lower()
                    parameters = [float(value) for value in parts[4:]]
                    if shape == "tri" and len(parameters) == 3:
                        function = triangular(*parameters)
                    elif shape == "trap" and len(parameters) == 4:
                        function = trapezoidal(*parameters)
                    else:
                        raise ValueError("неверный тип или количество параметров функции принадлежности")
                    model["sets"][(variable, term)] = function

                elif command == "RULE":
                    rule_text = line[4:].strip()
                    if not rule_text.upper().startswith("IF "):
                        raise ValueError("правило должно начинаться с IF")
                    premise, conclusion = rule_text[3:].split(" THEN ", 1)
                    conditions = []
                    for condition in premise.split(" AND "):
                        variable, term = condition.strip().split(" IS ", 1)
                        conditions.append((variable.strip(), term.strip()))
                    output_variable, output_term = conclusion.strip().split(" IS ", 1)
                    model["rules"].append({
                        "conditions": conditions,
                        "output": (output_variable.strip(), output_term.strip()),
                    })

                elif command == "PLANT":
                    model["plants"].append((float(parts[1]), parts[2]))

                elif command == "CASE":
                    test_case = {}
                    for item in parts[1:]:
                        variable, value = item.split("=", 1)
                        test_case[variable] = float(value)
                    model["test_cases"].append(test_case)

                else:
                    raise ValueError(f"неизвестная команда {command}")

            except Exception as error:
                raise ValueError(
                    f"Ошибка в файле {os.path.basename(file_path)}, строка {line_number}: {error}"
                ) from error

    validate_knowledge_base(model)
    return model


def validate_knowledge_base(model: dict) -> None:
    input_variables = [
        name for name, info in model["variables"].items()
        if info["kind"] == "IN"
    ]
    output_variables = [
        name for name, info in model["variables"].items()
        if info["kind"] == "OUT"
    ]

    if not input_variables or len(output_variables) != 1:
        raise ValueError("База должна содержать входные переменные и ровно одну выходную переменную.")
    if not model["rules"]:
        raise ValueError("В базе знаний нет правил.")
    if not model["plants"]:
        raise ValueError("В базе знаний нет списка рекомендуемых растений.")

    output_name = output_variables[0]
    for rule_number, rule in enumerate(model["rules"], start=1):
        if rule["output"][0] != output_name:
            raise ValueError(f"Правило {rule_number}: используется неизвестная выходная переменная.")
        for variable, term in rule["conditions"]:
            if variable not in input_variables:
                raise ValueError(f"Правило {rule_number}: неизвестная входная переменная {variable}.")
            if (variable, term) not in model["sets"]:
                raise ValueError(f"Правило {rule_number}: не найден термин {term} переменной {variable}.")
        if (output_name, rule["output"][1]) not in model["sets"]:
            raise ValueError(f"Правило {rule_number}: не найден выходной термин {rule['output'][1]}.")

    for case in model["test_cases"]:
        for variable in input_variables:
            if variable not in case:
                raise ValueError(f"В тестовом наборе отсутствует значение переменной {variable}.")


def input_variables(model: dict) -> list[str]:
    return [
        name for name, info in model["variables"].items()
        if info["kind"] == "IN"
    ]


def output_variable(model: dict) -> str:
    return next(
        name for name, info in model["variables"].items()
        if info["kind"] == "OUT"
    )


def recommended_plant(model: dict, crisp_result: float) -> str:
    """Выбирает группу растений с ближайшим к результату числовым центром."""
    return min(model["plants"], key=lambda item: abs(item[0] - crisp_result))[1]


# ---------------------------------------------------------------------
# Фаззификация входа и вычисление уровней истинности
# ---------------------------------------------------------------------

INPUT_GRID_POINTS = 201


def fuzzy_input_function(lower: float, upper: float,
                         crisp_value: float, uncertainty: float):
    """Нечёткое число «около x»: треугольник шириной ±uncertainty."""
    return triangular(
        max(lower, crisp_value - uncertainty),
        crisp_value,
        min(upper, crisp_value + uncertainty),
    )


def input_memberships_on_grid(input_values: list[float], lower: float,
                              upper: float, crisp_value: float,
                              uncertainty: float) -> list[float]:
    """
    Функция принадлежности входа A'(x) на сетке.
    uncertainty = 0 — синглетон (1 в ближайшем к x0 узле сетки, иначе 0).
    """
    if uncertainty <= 0:
        nearest = min(range(len(input_values)),
                      key=lambda i: abs(input_values[i] - crisp_value))
        return [1.0 if i == nearest else 0.0 for i in range(len(input_values))]
    fuzzy_input = fuzzy_input_function(lower, upper, crisp_value, uncertainty)
    return [fuzzy_input(value) for value in input_values]


def input_membership(model: dict, variable: str, term: str,
                     crisp_value: float, uncertainty: float) -> float:
    """
    Степень совпадения входного нечёткого числа с термом.
    При uncertainty=0 используется синглетон, то есть точное значение.
    """
    term_function = model["sets"][(variable, term)]

    if uncertainty <= 0:
        return term_function(crisp_value)

    lower = model["variables"][variable]["min"]
    upper = model["variables"][variable]["max"]
    fuzzy_input = fuzzy_input_function(lower, upper, crisp_value, uncertainty)
    # Узел x0 добавлен явно, чтобы вершина нечёткого входа попала на сетку.
    values = numerical_grid(lower, upper, INPUT_GRID_POINTS) + [crisp_value]
    return max(
        min(fuzzy_input(value), term_function(value))
        for value in values
    )


def rule_firing_level(model: dict, rule: dict, inputs: dict[str, float],
                      uncertainty: float = 0.0) -> float:
    """Уровень истинности предпосылки правила: AND реализован через min."""
    degrees = [
        input_membership(model, variable, term, inputs[variable], uncertainty)
        for variable, term in rule["conditions"]
    ]
    return min(degrees)


# ---------------------------------------------------------------------
# Механизм вывода по уровням истинности предпосылок (лекция, алгоритм 3)
# ---------------------------------------------------------------------

def infer_by_firing_levels(model: dict, inputs: dict[str, float],
                           implication: str = "Мамдани",
                           aggregation: str = DEFAULT_AGGREGATION,
                           uncertainty: float = 0.0) -> tuple[list[float], list[float]]:
    """Алгоритм 3 лекции: уровни истинности → импликация → агрегация."""
    output_name = output_variable(model)
    output_info = model["variables"][output_name]
    output_values = numerical_grid(output_info["min"], output_info["max"])
    implication_function = IMPLICATIONS[implication]
    aggregation_function = AGGREGATIONS[aggregation]

    aggregated_output = None

    for rule in model["rules"]:
        firing_level = rule_firing_level(model, rule, inputs, uncertainty)
        _, output_term = rule["output"]
        output_function = model["sets"][(output_name, output_term)]

        rule_output = [
            implication_function(firing_level, output_function(value))
            for value in output_values
        ]
        if aggregated_output is None:
            aggregated_output = rule_output
        else:
            aggregated_output = [
                aggregation_function(current, new)
                for current, new in zip(aggregated_output, rule_output)
            ]

    return output_values, aggregated_output


# ---------------------------------------------------------------------
# Композиционные механизмы для задачи с одной входной переменной
# ---------------------------------------------------------------------

def build_fuzzy_relation(model: dict, input_name: str, implication: str,
                         aggregation: str) -> tuple[list[float], list[float], list[list[float]]]:
    """Строит нечёткое отношение R(x,y) для всех правил базы знаний."""
    output_name = output_variable(model)
    input_info = model["variables"][input_name]
    output_info = model["variables"][output_name]
    input_values = numerical_grid(input_info["min"], input_info["max"], INPUT_GRID_POINTS)
    output_values = numerical_grid(output_info["min"], output_info["max"])

    implication_function = IMPLICATIONS[implication]
    aggregation_function = AGGREGATIONS[aggregation]
    relation = []

    for x_value in input_values:
        row = []
        for y_value in output_values:
            rule_values = []
            for rule in model["rules"]:
                # Композиционный вывод используется только для базы с одним входом.
                variable, term = rule["conditions"][0]
                premise_degree = model["sets"][(variable, term)](x_value)
                output_term = rule["output"][1]
                conclusion_degree = model["sets"][(output_name, output_term)](y_value)
                rule_values.append(
                    implication_function(premise_degree, conclusion_degree)
                )

            combined = rule_values[0]
            for value in rule_values[1:]:
                combined = aggregation_function(combined, value)
            row.append(combined)
        relation.append(row)

    return input_values, output_values, relation


def compose_input_with_relation(input_values: list[float],
                                output_values: list[float],
                                relation: list[list[float]],
                                crisp_input: float,
                                uncertainty: float,
                                input_min: float,
                                input_max: float) -> list[float]:
    """Max-min композиция B'(y)=max_x min(A'(x), R(x,y))."""
    input_memberships = input_memberships_on_grid(
        input_values, input_min, input_max, crisp_input, uncertainty
    )

    result = []
    for column in range(len(output_values)):
        result.append(max(
            min(input_memberships[row], relation[row][column])
            for row in range(len(input_values))
        ))
    return result


def infer_composition_individual(model: dict, input_name: str,
                                 crisp_input: float, uncertainty: float,
                                 implication: str,
                                 aggregation: str) -> tuple[list[float], list[float]]:
    """
    Композиционный алгоритм 1 из лекции:
    сначала вычисляются выходы отдельных правил, затем они агрегируются.
    """
    output_name = output_variable(model)
    input_info = model["variables"][input_name]
    output_info = model["variables"][output_name]
    input_values = numerical_grid(input_info["min"], input_info["max"], INPUT_GRID_POINTS)
    output_values = numerical_grid(output_info["min"], output_info["max"])
    implication_function = IMPLICATIONS[implication]
    aggregation_function = AGGREGATIONS[aggregation]

    input_memberships = input_memberships_on_grid(
        input_values, input_info["min"], input_info["max"],
        crisp_input, uncertainty
    )

    individual_outputs = []

    for rule in model["rules"]:
        variable, premise_term = rule["conditions"][0]
        output_term = rule["output"][1]
        premise_function = model["sets"][(variable, premise_term)]
        conclusion_function = model["sets"][(output_name, output_term)]

        relation = [
            [
                implication_function(premise_function(x), conclusion_function(y))
                for y in output_values
            ]
            for x in input_values
        ]

        rule_output = [
            max(
                min(input_memberships[index], relation[index][column])
                for index in range(len(input_values))
            )
            for column in range(len(output_values))
        ]
        individual_outputs.append(rule_output)

    aggregated_output = individual_outputs[0][:]
    for rule_output in individual_outputs[1:]:
        aggregated_output = [
            aggregation_function(a, b)
            for a, b in zip(aggregated_output, rule_output)
        ]

    return output_values, aggregated_output


def infer_composition_aggregated(model: dict, input_name: str,
                                 crisp_input: float, uncertainty: float,
                                 implication: str,
                                 aggregation: str) -> tuple[list[float], list[float]]:
    """
    Композиционный алгоритм 2 из лекции:
    сначала агрегируются отношения правил, затем выполняется композиция.
    """
    input_values, output_values, relation = build_fuzzy_relation(
        model, input_name, implication, aggregation
    )
    input_info = model["variables"][input_name]
    result = compose_input_with_relation(
        input_values, output_values, relation, crisp_input, uncertainty,
        input_info["min"], input_info["max"]
    )
    return output_values, result


# ---------------------------------------------------------------------
# Выбор механизма и графический интерфейс
# ---------------------------------------------------------------------

MECHANISMS_SINGLE = {
    "По уровням истинности предпосылок": "firing",
    "Композиционный: сначала выводы правил": "composition_individual",
    "Композиционный: сначала агрегация правил": "composition_aggregated",
}

MECHANISMS_MULTI = {
    "По уровням истинности предпосылок": "firing",
}


class PlantRecommendationApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Подбор комнатных растений — нечёткая система вывода")
        self.root.geometry("1180x760")
        self.root.minsize(980, 650)

        self.model = None
        self.input_scales = {}
        self.current_file = None

        self._build_interface()
        self.load_file("rules_single.txt")

    def _build_interface(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        control_panel = ttk.Frame(main, width=340)
        control_panel.pack(side="left", fill="y", padx=(0, 12))
        control_panel.pack_propagate(False)

        result_panel = ttk.Frame(main)
        result_panel.pack(side="right", fill="both", expand=True)

        ttk.Label(
            control_panel,
            text="Подбор комнатных растений",
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w", pady=(0, 8))

        database_box = ttk.LabelFrame(control_panel, text="Предметная задача", padding=8)
        database_box.pack(fill="x", pady=(0, 8))

        ttk.Button(
            database_box,
            text="Задача 1 — освещённость",
            command=lambda: self.load_file("rules_single.txt")
        ).pack(fill="x", pady=2)

        ttk.Button(
            database_box,
            text="Задача 2 — условия помещения",
            command=lambda: self.load_file("rules_multi.txt")
        ).pack(fill="x", pady=2)

        ttk.Button(
            database_box,
            text="Открыть другую базу правил…",
            command=self.open_file
        ).pack(fill="x", pady=2)

        self.file_label = ttk.Label(database_box, text="База не загружена", wraplength=300)
        self.file_label.pack(anchor="w", pady=(5, 0))

        self.inputs_box = ttk.LabelFrame(
            control_panel, text="Параметры помещения", padding=8
        )
        self.inputs_box.pack(fill="x", pady=(0, 8))

        settings_box = ttk.LabelFrame(
            control_panel, text="Параметры нечёткого вывода", padding=8
        )
        settings_box.pack(fill="x", pady=(0, 8))

        ttk.Label(settings_box, text="Механизм вывода").pack(anchor="w")
        self.mechanism_combo = ttk.Combobox(
            settings_box, state="readonly", width=38
        )
        self.mechanism_combo.pack(fill="x", pady=(0, 6))

        ttk.Label(settings_box, text="Тип импликации").pack(anchor="w")
        self.implication_combo = ttk.Combobox(
            settings_box, state="readonly",
            values=list(IMPLICATIONS.keys())
        )
        self.implication_combo.current(0)
        self.implication_combo.pack(fill="x", pady=(0, 6))

        ttk.Label(settings_box, text="Оператор агрегации").pack(anchor="w")
        self.aggregation_combo = ttk.Combobox(
            settings_box, state="readonly",
            values=list(AGGREGATIONS.keys())
        )
        self.aggregation_combo.set(DEFAULT_AGGREGATION)
        self.aggregation_combo.pack(fill="x", pady=(0, 6))

        self.uncertainty_label = ttk.Label(
            settings_box, text="Неопределённость входа (±)"
        )
        self.uncertainty_label.pack(anchor="w")
        self.uncertainty_entry = ttk.Entry(settings_box)
        self.uncertainty_entry.insert(0, "5")
        self.uncertainty_entry.pack(fill="x")

        actions_box = ttk.LabelFrame(control_panel, text="Действия", padding=8)
        actions_box.pack(fill="x", pady=(0, 8))

        ttk.Button(
            actions_box, text="Рассчитать рекомендацию",
            command=self.calculate
        ).pack(fill="x", pady=2)

        ttk.Button(
            actions_box, text="Сравнить механизмы вывода",
            command=self.compare_mechanisms
        ).pack(fill="x", pady=2)

        ttk.Button(
            actions_box, text="Сравнить импликации",
            command=self.compare_implications
        ).pack(fill="x", pady=2)

        ttk.Button(
            actions_box, text="Показать функции принадлежности",
            command=self.show_membership_functions
        ).pack(fill="x", pady=2)

        ttk.Button(
            actions_box, text="Таблица результатов для тестов",
            command=self.show_test_table
        ).pack(fill="x", pady=2)

        result_box = ttk.LabelFrame(
            control_panel, text="Результат расчёта", padding=6
        )
        result_box.pack(fill="both", expand=True)

        self.result_text = tk.Text(
            result_box, height=10, wrap="word",
            font=("Segoe UI", 9), state="disabled"
        )
        self.result_text.pack(fill="both", expand=True)

        graph_box = ttk.LabelFrame(result_panel, text="График выходного нечёткого множества", padding=6)
        graph_box.pack(fill="both", expand=True)

        self.figure = Figure(figsize=(7, 5), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_box)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.status_label = ttk.Label(
            result_panel, text="Выберите параметры помещения и нажмите «Рассчитать рекомендацию».",
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=(6, 0))

    def _reset_axes(self):
        """Очищает фигуру и создаёт одни оси (после show_membership_functions
        в фигуре могло остаться несколько подграфиков)."""
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

    def _set_result_text(self, content: str):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", content)
        self.result_text.configure(state="disabled")

    def _clear_input_controls(self):
        for widget in self.inputs_box.winfo_children():
            widget.destroy()
        self.input_scales.clear()

    def load_file(self, file_path: str):
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)

        try:
            new_model = load_knowledge_base(file_path)
        except Exception as error:
            messagebox.showerror("Ошибка загрузки базы правил", str(error))
            return

        self.model = new_model
        self.current_file = file_path
        self.file_label.config(
            text=f"Загружена база: {os.path.basename(file_path)}\n"
                 f"Количество правил: {len(self.model['rules'])}"
        )

        self._clear_input_controls()

        for variable in input_variables(self.model):
            info = self.model["variables"][variable]
            row = ttk.Frame(self.inputs_box)
            row.pack(fill="x", pady=4)

            ttk.Label(
                row, text=f"{info['label']} ({info['min']:g}–{info['max']:g})",
                wraplength=290
            ).pack(anchor="w")

            scale = tk.Scale(
                row, from_=info["min"], to=info["max"],
                orient="horizontal", resolution=1,
                length=290, showvalue=True
            )
            scale.set((info["min"] + info["max"]) / 2)
            scale.pack(fill="x")
            self.input_scales[variable] = scale

        if len(input_variables(self.model)) == 1:
            self.mechanism_combo.configure(values=list(MECHANISMS_SINGLE.keys()))
            self.mechanism_combo.current(0)
            self.uncertainty_label.pack(anchor="w")
            self.uncertainty_entry.pack(fill="x")
        else:
            self.mechanism_combo.configure(values=list(MECHANISMS_MULTI.keys()))
            self.mechanism_combo.current(0)
            self.uncertainty_label.pack_forget()
            self.uncertainty_entry.pack_forget()

        self._set_result_text(
            "База знаний загружена.\n"
            f"Входных переменных: {len(input_variables(self.model))}\n"
            f"Правил: {len(self.model['rules'])}\n"
            "Задайте параметры помещения и выполните расчёт."
        )
        self._reset_axes()
        self.axes.set_title("Выходное нечёткое множество")
        self.canvas.draw()
        self.status_label.config(text="База правил успешно загружена.")

    def open_file(self):
        selected = filedialog.askopenfilename(
            title="Выберите текстовый файл с базой правил",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if selected:
            self.load_file(selected)

    def _read_parameters(self):
        if self.model is None:
            return None

        inputs = {
            variable: float(scale.get())
            for variable, scale in self.input_scales.items()
        }

        uncertainty = 0.0
        if len(inputs) == 1:
            try:
                uncertainty = float(self.uncertainty_entry.get().replace(",", "."))
            except ValueError:
                messagebox.showerror(
                    "Некорректное значение",
                    "Неопределённость входа должна быть числом."
                )
                return None
            if uncertainty < 0:
                messagebox.showerror(
                    "Некорректное значение",
                    "Неопределённость не может быть отрицательной."
                )
                return None

        return inputs, uncertainty

    def _run_inference(self, mechanism: str, inputs: dict,
                       uncertainty: float, implication: str,
                       aggregation: str):
        if mechanism == "firing":
            return infer_by_firing_levels(
                self.model, inputs, implication, aggregation, uncertainty
            )

        input_name = input_variables(self.model)[0]
        crisp_value = inputs[input_name]

        if mechanism == "composition_individual":
            return infer_composition_individual(
                self.model, input_name, crisp_value, uncertainty,
                implication, aggregation
            )

        if mechanism == "composition_aggregated":
            return infer_composition_aggregated(
                self.model, input_name, crisp_value, uncertainty,
                implication, aggregation
            )

        raise ValueError("Неизвестный механизм логического вывода.")

    def _draw_output(self, values: list[float], degrees: list[float],
                     crisp_value: float | None, title: str):
        self._reset_axes()
        self.axes.plot(values, degrees, linewidth=2, label="Итоговая функция принадлежности")
        self.axes.fill_between(values, degrees, alpha=0.2)

        if crisp_value is not None:
            self.axes.axvline(
                crisp_value, linestyle="--", linewidth=1.5,
                label=f"Центр тяжести: {crisp_value:.2f}"
            )

        output_name = output_variable(self.model)
        self.axes.set_title(title)
        self.axes.set_xlabel(self.model["variables"][output_name]["label"])
        self.axes.set_ylabel("Степень принадлежности")
        self.axes.set_ylim(-0.03, 1.05)
        self.axes.grid(True, alpha=0.25)
        self.axes.legend(loc="best", fontsize=8)
        self.figure.tight_layout()
        self.canvas.draw()

    def calculate(self):
        parameters = self._read_parameters()
        if parameters is None:
            return

        inputs, uncertainty = parameters
        mechanism_label = self.mechanism_combo.get()
        mechanism = (
            MECHANISMS_SINGLE[mechanism_label]
            if len(inputs) == 1
            else MECHANISMS_MULTI[mechanism_label]
        )
        implication = self.implication_combo.get()
        aggregation = self.aggregation_combo.get()

        try:
            values, degrees = self._run_inference(
                mechanism, inputs, uncertainty, implication, aggregation
            )
        except Exception as error:
            messagebox.showerror("Ошибка вычисления", str(error))
            return

        result = centroid(values, degrees)
        lines = [
            "ВХОДНЫЕ ПАРАМЕТРЫ",
            *[
                f"• {self.model['variables'][name]['label']}: {value:g}"
                for name, value in inputs.items()
            ],
            "",
            "НАСТРОЙКИ ВЫВОДА",
            f"Механизм: {mechanism_label}",
            f"Импликация: {implication}",
            f"Агрегация: {aggregation}",
            "",
        ]

        if result is None:
            lines.append("Результат: выходное нечёткое множество пусто.")
        else:
            lines.extend([
                f"Чёткое значение (центр тяжести): {result:.2f}",
                f"Рекомендуемая группа растений: {recommended_plant(self.model, result)}",
            ])

        self._set_result_text("\n".join(lines))
        self._draw_output(values, degrees, result, "Результат нечёткого логического вывода")
        self.status_label.config(text="Расчёт завершён.")

    def compare_mechanisms(self):
        if len(input_variables(self.model)) != 1:
            messagebox.showinfo(
                "Сравнение механизмов",
                "Композиционные механизмы предусмотрены для задачи с одной входной переменной."
            )
            return

        parameters = self._read_parameters()
        if parameters is None:
            return
        inputs, uncertainty = parameters

        aggregation = self.aggregation_combo.get()
        implication = self.implication_combo.get()
        self._reset_axes()
        report = ["СРАВНЕНИЕ ТРЁХ МЕХАНИЗМОВ ВЫВОДА", ""]

        for label, mechanism in MECHANISMS_SINGLE.items():
            try:
                values, degrees = self._run_inference(
                    mechanism, inputs, uncertainty, implication, aggregation
                )
            except Exception as error:
                messagebox.showerror("Ошибка вычисления", str(error))
                return
            result = centroid(values, degrees)
            self.axes.plot(values, degrees, label=label)

            if result is None:
                report.append(f"{label}: пустое выходное множество")
            else:
                report.append(
                    f"{label}: {result:.2f} — {recommended_plant(self.model, result)}"
                )

        self.axes.set_title("Сравнение механизмов логического вывода")
        self.axes.set_xlabel(self.model["variables"][output_variable(self.model)]["label"])
        self.axes.set_ylabel("Степень принадлежности")
        self.axes.set_ylim(-0.03, 1.05)
        self.axes.grid(True, alpha=0.25)
        self.axes.legend(fontsize=8)
        self.figure.tight_layout()
        self.canvas.draw()
        self._set_result_text("\n".join(report))
        self.status_label.config(text="Сравнение механизмов выполнено.")

    def compare_implications(self):
        parameters = self._read_parameters()
        if parameters is None:
            return
        inputs, uncertainty = parameters

        mechanism_label = self.mechanism_combo.get()
        mechanism = (
            MECHANISMS_SINGLE[mechanism_label]
            if len(inputs) == 1
            else MECHANISMS_MULTI[mechanism_label]
        )
        aggregation = self.aggregation_combo.get()

        self._reset_axes()
        report = ["СРАВНЕНИЕ ТИПОВ ИМПЛИКАЦИИ", ""]

        for implication in IMPLICATIONS:
            try:
                values, degrees = self._run_inference(
                    mechanism, inputs, uncertainty, implication, aggregation
                )
            except Exception as error:
                messagebox.showerror("Ошибка вычисления", str(error))
                return
            result = centroid(values, degrees)
            self.axes.plot(values, degrees, label=implication)

            if result is None:
                report.append(f"{implication}: пустое выходное множество")
            else:
                report.append(
                    f"{implication}: {result:.2f} — {recommended_plant(self.model, result)}"
                )

        self.axes.set_title("Влияние типа импликации на результат")
        self.axes.set_xlabel(self.model["variables"][output_variable(self.model)]["label"])
        self.axes.set_ylabel("Степень принадлежности")
        self.axes.set_ylim(-0.03, 1.05)
        self.axes.grid(True, alpha=0.25)
        self.axes.legend()
        self.figure.tight_layout()
        self.canvas.draw()
        self._set_result_text("\n".join(report))
        self.status_label.config(text="Сравнение импликаций выполнено.")

    def show_membership_functions(self):
        variable_names = list(self.model["variables"])
        columns = 2 if len(variable_names) > 1 else 1
        rows = math.ceil(len(variable_names) / columns)

        self.figure.clear()
        for index, variable in enumerate(variable_names, start=1):
            axis = self.figure.add_subplot(rows, columns, index)
            info = self.model["variables"][variable]
            values = numerical_grid(info["min"], info["max"], 301)

            for (set_variable, term), function in self.model["sets"].items():
                if set_variable == variable:
                    axis.plot(values, [function(value) for value in values], label=term)

            axis.set_title(info["label"])
            axis.set_xlabel("Значение")
            axis.set_ylabel("Степень принадлежности")
            axis.set_ylim(-0.03, 1.05)
            axis.grid(True, alpha=0.2)
            axis.legend(fontsize=8)

        self.figure.tight_layout()
        self.canvas.draw()
        self._set_result_text("Показаны функции принадлежности всех переменных базы знаний.")
        self.status_label.config(text="Функции принадлежности построены.")

    def show_test_table(self):
        if not self.model["test_cases"]:
            messagebox.showinfo(
                "Тестовые наборы",
                "В текущей базе знаний нет тестовых наборов CASE."
            )
            return

        parameters = self._read_parameters()
        if parameters is None:
            return
        table_uncertainty = parameters[1]

        single_input = len(input_variables(self.model)) == 1
        if single_input:
            mechanisms = MECHANISMS_SINGLE
        else:
            mechanisms = MECHANISMS_MULTI

        window = tk.Toplevel(self.root)
        window.title("Таблица результатов для тестовых наборов")
        window.geometry("900x420")

        frame = ttk.Frame(window, padding=8)
        frame.pack(fill="both", expand=True)

        columns = ["test"] + input_variables(self.model) + ["implication", "mechanism", "centroid", "plant"]
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)

        headings = {
            "test": "№",
            "implication": "Импликация",
            "mechanism": "Механизм вывода",
            "centroid": "Центр тяжести",
            "plant": "Рекомендация",
        }
        for column in columns:
            if column in self.model["variables"]:
                heading = self.model["variables"][column]["label"]
            else:
                heading = headings[column]
            tree.heading(column, text=heading)
            tree.column(column, width=125, anchor="center")

        for test_index, test_case in enumerate(self.model["test_cases"], start=1):
            for implication in IMPLICATIONS:
                for mechanism_label, mechanism in mechanisms.items():
                    values, degrees = self._run_inference(
                        mechanism, test_case, table_uncertainty,
                        implication, DEFAULT_AGGREGATION
                    )
                    result = centroid(values, degrees)
                    row = [test_index]
                    row.extend(f"{test_case[name]:g}" for name in input_variables(self.model))
                    row.extend([
                        implication,
                        mechanism_label,
                        "—" if result is None else f"{result:.2f}",
                        "—" if result is None else recommended_plant(self.model, result),
                    ])
                    tree.insert("", "end", values=row)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


def main():
    root = tk.Tk()
    PlantRecommendationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()