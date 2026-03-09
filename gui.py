import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import shutil
import zipfile
from datetime import datetime
from docxtpl import DocxTemplate
import win32com.client
import threading

#pip install python-docx
#pip install docxtpl
#pip install pywin32

# Константы для темной темы
BG_COLOR = "#2b2b2b"
FG_COLOR = "#ffffff"
ENTRY_BG = "#3c3c3c"
ENTRY_FG = "#ffffff"
PLACEHOLDER_COLOR = "#808080"
BUTTON_BG = "#404040"
BUTTON_FG = "#ffffff"
SELECT_BG = "#4a4a4a"
FRAME_BG = "#333333"
LABEL_FG = "#cccccc"
ERROR_COLOR = "#ff6b6b"
SUCCESS_COLOR = "#6bff6b"


class PlaceholderEntry(tk.Entry):
    """Класс для поля ввода с подсказкой"""

    def __init__(self, master=None, placeholder="", color=PLACEHOLDER_COLOR, format_type=None, *args, **kwargs):
        # Устанавливаем цвета для поля ввода
        kwargs.update({
            'bg': ENTRY_BG,
            'fg': ENTRY_FG,
            'insertbackground': FG_COLOR,
            'relief': tk.FLAT,
            'bd': 2
        })
        super().__init__(master, *args, **kwargs)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = ENTRY_FG
        self.format_type = format_type
        self.old_value = ""

        # Привязываем события
        self.bind("<FocusIn>", self.focus_in)
        self.bind("<FocusOut>", self.focus_out)
        self.bind("<KeyRelease>", self.on_key_release)
        self.bind("<<Paste>>", self.on_paste)
        self.bind("<Control-v>", self.on_paste)
        self.bind("<Button-3>", self.show_context_menu)  # ПКМ для контекстного меню

        self.put_placeholder()

        # Создаем контекстное меню
        self.context_menu = tk.Menu(self, tearoff=0, bg=ENTRY_BG, fg=FG_COLOR,
                                    activebackground=SELECT_BG, activeforeground=FG_COLOR)
        self.context_menu.add_command(label="Копировать", command=self.copy_text)
        self.context_menu.add_command(label="Вставить", command=self.paste_text)
        self.context_menu.add_command(label="Вырезать", command=self.cut_text)

    def show_context_menu(self, event):
        """Показать контекстное меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_text(self):
        """Копировать текст"""
        self.clipboard_clear()
        if self.selection_present():
            text = self.selection_get()
            self.clipboard_append(text)
        else:
            text = self.get()
            if text != self.placeholder:
                self.clipboard_append(text)

    def paste_text(self):
        """Вставить текст"""
        try:
            text = self.clipboard_get()
            self.delete(0, tk.END)
            self.insert(0, text)
            self.configure(foreground=self.default_fg_color)
            # Применяем форматирование если нужно
            self.on_key_release(None)
        except:
            pass

    def cut_text(self):
        """Вырезать текст"""
        self.copy_text()
        self.delete(0, tk.END)
        if not self.focus_get() == self:
            self.put_placeholder()

    def on_paste(self, event):
        """Обработка вставки"""
        self.after(100, self.on_key_release, None)  # Даем время на вставку
        return "break"  # Предотвращаем стандартную вставку

    def put_placeholder(self):
        """Установка текста-подсказки"""
        self.delete(0, tk.END)
        self.insert(0, self.placeholder)
        self.configure(foreground=self.placeholder_color)

    def focus_in(self, *args):
        """При получении фокуса"""
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.configure(foreground=self.default_fg_color)

    def focus_out(self, *args):
        """При потере фокуса"""
        if not self.get():
            self.put_placeholder()

    def on_key_release(self, event):
        """Обработка ввода с клавиатуры"""
        current_value = self.get()

        # Предотвращаем рекурсию
        if current_value == self.old_value:
            return

        self.old_value = current_value

        # Если это поле телефона и есть текст (не плейсхолдер)
        if self.format_type == "phone" and current_value != self.placeholder:
            self.format_phone()
        # Если это поле даты рождения
        elif self.format_type == "date" and current_value != self.placeholder:
            self.format_date()

    def format_phone(self):
        """Автоматическое форматирование номера телефона"""
        # Получаем только цифры из введенного текста
        text = self.get()
        digits = re.sub(r'\D', '', text)

        # Если начинается с 8, заменяем на 7
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        # Если не начинается с 7, добавляем 7
        elif not digits.startswith('7'):
            digits = '7' + digits

        # Ограничиваем до 11 цифр
        digits = digits[:11]

        # Форматируем номер
        if len(digits) > 0:
            formatted = '+' + digits[0]
            if len(digits) > 1:
                formatted += ' (' + digits[1:4]
                if len(digits) > 4:
                    formatted += ') ' + digits[4:7]
                    if len(digits) > 7:
                        formatted += '-' + digits[7:9]
                        if len(digits) > 9:
                            formatted += '-' + digits[9:11]
            else:
                formatted += ' ('
        else:
            formatted = '+7 ('

        # Сохраняем позицию курсора
        cursor_pos = self.index(tk.INSERT)

        # Вставляем отформатированный текст
        self.delete(0, tk.END)
        self.insert(0, formatted)

        # Восстанавливаем позицию курсора примерно
        new_pos = min(cursor_pos, len(formatted))
        self.icursor(new_pos)

    def format_date(self):
        """Автоматическое форматирование даты"""
        # Получаем только цифры из введенного текста
        text = self.get()
        digits = re.sub(r'\D', '', text)

        # Ограничиваем до 8 цифр (ДДММГГГГ)
        digits = digits[:8]

        # Форматируем дату
        formatted = ""
        for i, digit in enumerate(digits):
            if i == 2 or i == 4:  # После дня и месяца добавляем точку
                formatted += '.'
            formatted += digit

        # Сохраняем позицию курсора
        cursor_pos = self.index(tk.INSERT)

        # Вставляем отформатированный текст
        self.delete(0, tk.END)
        self.insert(0, formatted)

        # Восстанавливаем позицию курсора
        new_pos = min(cursor_pos, len(formatted))
        self.icursor(new_pos)

    def get_value(self):
        """Получение значения без плейсхолдера"""
        value = self.get()
        if value == self.placeholder:
            return ""
        return value


class PatentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор документов для патента")
        self.root.geometry("1000x800")
        self.root.configure(bg=BG_COLOR)

        # Настройка стилей для ttk
        self.setup_styles()

        # Переменные для хранения данных
        self.authors = []
        self.source_code_path = None
        self.abstract_path = None
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        self.current_author_count = 0

        # Создание необходимых папок
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs("templates", exist_ok=True)

        # Проверка наличия шаблонов
        self.check_templates()

        # Создание интерфейса
        self.create_widgets()

    def setup_styles(self):
        """Настройка стилей для виджетов"""
        style = ttk.Style()
        style.theme_use('clam')

        # Настройка цветов для ttk виджетов
        style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR, font=('Arial', 10))
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabelframe', background=BG_COLOR, foreground=FG_COLOR, relief=tk.FLAT, bd=2)
        style.configure('TLabelframe.Label', background=BG_COLOR, foreground=FG_COLOR, font=('Arial', 10, 'bold'))
        style.configure('TButton', background=BUTTON_BG, foreground=BUTTON_FG, borderwidth=1, font=('Arial', 10))
        style.map('TButton',
                  background=[('active', SELECT_BG)],
                  foreground=[('active', FG_COLOR)])

    def check_templates(self):
        """Проверка наличия файлов шаблонов"""
        required_templates = [
            "source_code_template.docx",
            "pril1-211-1-1.docx",
            "pril1-211-1-2.docx",
            "pril1-211-2-1.docx",
            "pril1-211-2-2.docx",
            "pril3_211.docx",
            "pril4_211 .docx"
        ]

        missing_templates = []
        for template in required_templates:
            if not os.path.exists(f"templates/{template}"):
                missing_templates.append(template)

        if missing_templates:
            messagebox.showwarning("Предупреждение",
                                   f"Отсутствуют шаблоны:\n{', '.join(missing_templates)}\n\n"
                                   "Поместите их в папку 'templates' перед использованием.")

    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Основной контейнер с прокруткой
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Создаем Canvas для прокрутки
        canvas = tk.Canvas(main_container, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Привязка колесика мыши
        self.bind_mousewheel(canvas)

        # Заголовок
        title_label = ttk.Label(self.scrollable_frame, text="Генерация документов для патента",
                                font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Основная информация
        self.create_main_info_frame()

        # Авторы
        self.create_authors_frame()

        # Файлы
        self.create_files_frame()

        # Кнопки управления
        self.create_control_buttons()

        # Лог
        self.create_log_frame()

    def bind_mousewheel(self, widget):
        """Привязка колесика мыши для прокрутки"""

        def on_mousewheel(event):
            widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind_all("<MouseWheel>", on_mousewheel)

    def create_main_info_frame(self):
        """Фрейм с основной информацией"""
        main_frame = ttk.LabelFrame(self.scrollable_frame, text="Основная информация", padding=10)
        main_frame.pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text="Название программы:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.program_name = PlaceholderEntry(main_frame, placeholder="Введите название программы", width=60)
        self.program_name.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(main_frame, text="Количество авторов:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.author_count = PlaceholderEntry(main_frame, placeholder="Например: 2", width=10)
        self.author_count.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Button(main_frame, text="Обновить", command=self.update_authors).grid(row=1, column=2, padx=5)

        # Подсказка по форматам
        formats_frame = ttk.LabelFrame(main_frame, text="Форматы ввода", padding=5)
        formats_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=10)

        formats_text = """
        • ФИО: Иванов Иван Иванович
        • Адрес: 123456, Москва, ул. Примерная, д. 1
        • Телефон: автоматически форматируется в +7 (985) 346-28-79
        • Email: name@example.com
        • ИНН: 12 цифр
        • СНИЛС: 11 цифр
        • Паспорт: 0000 000000 ГУ МВД по Московской области 01.01.2000
        • Дата рождения: автоматически форматируется в ДД.ММ.ГГГГ
        """

        formats_label = ttk.Label(formats_frame, text=formats_text, justify=tk.LEFT, foreground=LABEL_FG)
        formats_label.pack()

    def create_authors_frame(self):
        """Фрейм для ввода данных авторов"""
        self.authors_frame = ttk.LabelFrame(self.scrollable_frame, text="Данные авторов", padding=10)
        self.authors_frame.pack(fill=tk.X, pady=5)

        # Контейнер для динамического добавления авторов
        self.authors_container = ttk.Frame(self.authors_frame)
        self.authors_container.pack(fill=tk.X, expand=True)

        # Словарь для хранения виджетов авторов
        self.author_frames = {}
        self.author_widgets = {}

    def update_authors(self):
        """Обновление полей для ввода данных авторов"""
        try:
            count_text = self.author_count.get_value()
            if not count_text:
                messagebox.showerror("Ошибка", "Введите количество авторов")
                return

            new_count = int(count_text)
            if new_count <= 0:
                messagebox.showerror("Ошибка", "Количество авторов должно быть положительным числом")
                return

            current_count = len(self.author_frames)

            if new_count > current_count:
                # Добавляем новых авторов
                for i in range(current_count, new_count):
                    self.create_author_fields(i)
            elif new_count < current_count:
                # Удаляем лишних авторов
                for i in range(new_count, current_count):
                    if i in self.author_frames:
                        self.author_frames[i].destroy()
                        del self.author_frames[i]
                        if i in self.author_widgets:
                            del self.author_widgets[i]

            self.current_author_count = new_count

        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное число авторов")

    def create_author_fields(self, index):
        """Создание полей для одного автора"""
        # Создаем фрейм для автора
        frame = ttk.LabelFrame(self.authors_container, text=f"Автор {index + 1}", padding=5)
        frame.pack(fill=tk.X, pady=5, before=None if index == 0 else self.author_frames.get(index - 1))

        # Сохраняем фрейм
        self.author_frames[index] = frame

        # Словарь для хранения виджетов этого автора
        widgets = {}

        # ФИО
        ttk.Label(frame, text="ФИО:").grid(row=0, column=0, sticky=tk.W, pady=2)
        fio_entry = PlaceholderEntry(frame, placeholder="Иванов Иван Иванович", width=50)
        fio_entry.grid(row=0, column=1, padx=5, pady=2, columnspan=3, sticky=tk.W)
        widgets['fio'] = fio_entry

        # Адрес
        ttk.Label(frame, text="Адрес:").grid(row=1, column=0, sticky=tk.W, pady=2)
        address_entry = PlaceholderEntry(frame, placeholder="123456, Москва, ул. Примерная, д. 1", width=70)
        address_entry.grid(row=1, column=1, padx=5, pady=2, columnspan=3, sticky=tk.W)
        widgets['address'] = address_entry

        # Телефон
        ttk.Label(frame, text="Телефон:").grid(row=2, column=0, sticky=tk.W, pady=2)
        phone_entry = PlaceholderEntry(frame, placeholder="+7 (___) ___-__-__", width=20, format_type="phone")
        phone_entry.grid(row=2, column=1, padx=5, pady=2, sticky=tk.W)
        widgets['phone'] = phone_entry

        # Email
        ttk.Label(frame, text="Email:").grid(row=2, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        email_entry = PlaceholderEntry(frame, placeholder="name@example.com", width=30)
        email_entry.grid(row=2, column=3, padx=5, pady=2, sticky=tk.W)
        widgets['email'] = email_entry

        # ИНН
        ttk.Label(frame, text="ИНН:").grid(row=3, column=0, sticky=tk.W, pady=2)
        inn_entry = PlaceholderEntry(frame, placeholder="12 цифр", width=15)
        inn_entry.grid(row=3, column=1, padx=5, pady=2, sticky=tk.W)
        widgets['inn'] = inn_entry

        # СНИЛС
        ttk.Label(frame, text="СНИЛС:").grid(row=3, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        snils_entry = PlaceholderEntry(frame, placeholder="11 цифр", width=15)
        snils_entry.grid(row=3, column=3, padx=5, pady=2, sticky=tk.W)
        widgets['snils'] = snils_entry

        # Паспорт
        ttk.Label(frame, text="Паспортные данные:").grid(row=4, column=0, sticky=tk.W, pady=2)
        passport_entry = PlaceholderEntry(frame, placeholder="0000 000000 ГУ МВД по Московской области 01.01.2000",
                                          width=70)
        passport_entry.grid(row=4, column=1, padx=5, pady=2, columnspan=3, sticky=tk.W)
        widgets['passport'] = passport_entry

        # Дата рождения
        ttk.Label(frame, text="Дата рождения:").grid(row=5, column=0, sticky=tk.W, pady=2)
        birthday_entry = PlaceholderEntry(frame, placeholder="ДД.ММ.ГГГГ", width=15, format_type="date")
        birthday_entry.grid(row=5, column=1, padx=5, pady=2, sticky=tk.W)
        widgets['birthday'] = birthday_entry

        # Творческий вклад
        ttk.Label(frame, text="Творческий вклад:").grid(row=5, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        skill_entry = PlaceholderEntry(frame, placeholder="Краткое описание вклада", width=40)
        skill_entry.grid(row=5, column=3, padx=5, pady=2, sticky=tk.W)
        widgets['skill'] = skill_entry

        # Сохраняем виджеты
        self.author_widgets[index] = widgets

    def create_files_frame(self):
        """Фрейм для выбора файлов"""
        files_frame = ttk.LabelFrame(self.scrollable_frame, text="Файлы", padding=10)
        files_frame.pack(fill=tk.X, pady=5)

        # Исходный код
        ttk.Label(files_frame, text="Файл с исходным кодом:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.source_code_label = ttk.Label(files_frame, text="Файл не выбран", foreground=ERROR_COLOR)
        self.source_code_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(files_frame, text="Выбрать файл",
                   command=self.select_source_code).grid(row=0, column=2, padx=5)

        # Реферат
        ttk.Label(files_frame, text="Файл с рефератом:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.abstract_label = ttk.Label(files_frame, text="Файл не выбран", foreground=ERROR_COLOR)
        self.abstract_label.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Button(files_frame, text="Выбрать файл",
                   command=self.select_abstract).grid(row=1, column=2, padx=5)

    def create_control_buttons(self):
        """Фрейм с кнопками управления"""
        control_frame = ttk.Frame(self.scrollable_frame)
        control_frame.pack(fill=tk.X, pady=10)

        ttk.Button(control_frame, text="Сгенерировать документы",
                   command=self.start_generation,
                   style='TButton').pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Очистить все",
                   command=self.clear_all,
                   style='TButton').pack(side=tk.LEFT, padx=5)

    def create_log_frame(self):
        """Фрейм для лога выполнения"""
        log_frame = ttk.LabelFrame(self.scrollable_frame, text="Лог выполнения", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            bg=ENTRY_BG,
            fg=FG_COLOR,
            insertbackground=FG_COLOR,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, message, is_error=False):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        if is_error:
            self.log_text.tag_add("error", "end-2l", "end-1l")
            self.log_text.tag_config("error", foreground=ERROR_COLOR)
        self.log_text.see(tk.END)
        self.root.update()

    def select_source_code(self):
        """Выбор файла с исходным кодом"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с исходным кодом",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if filename:
            self.source_code_path = filename
            self.source_code_label.config(text=os.path.basename(filename), foreground=SUCCESS_COLOR)

    def select_abstract(self):
        """Выбор файла с рефератом"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с рефератом",
            filetypes=[("Word files", "*.docx"), ("All files", "*.*")]
        )
        if filename:
            self.abstract_path = filename
            self.abstract_label.config(text=os.path.basename(filename), foreground=SUCCESS_COLOR)

    def validate_inputs(self):
        """Проверка введенных данных"""
        if not self.program_name.get_value():
            messagebox.showerror("Ошибка", "Введите название программы")
            return False

        if not self.author_count.get_value():
            messagebox.showerror("Ошибка", "Введите количество авторов")
            return False

        if not self.source_code_path:
            messagebox.showerror("Ошибка", "Выберите файл с исходным кодом")
            return False

        if not self.abstract_path:
            messagebox.showerror("Ошибка", "Выберите файл с рефератом")
            return False

        return True

    def collect_author_data(self):
        """Сбор данных об авторах из полей ввода"""
        authors = []
        for i in range(len(self.author_widgets)):
            widgets = self.author_widgets[i]
            author = {
                "fio": widgets['fio'].get_value(),
                "address": widgets['address'].get_value(),
                "phone": widgets['phone'].get_value(),
                "email": widgets['email'].get_value(),
                "inn": widgets['inn'].get_value(),
                "snils": widgets['snils'].get_value(),
                "passport": widgets['passport'].get_value(),
                "birthday": widgets['birthday'].get_value(),
                "skill": widgets['skill'].get_value()
            }

            # Проверка заполнения всех полей
            empty_fields = [field for field, value in author.items() if not value]
            if empty_fields:
                messagebox.showerror("Ошибка", f"Заполните все поля для автора {i + 1}\n"
                                               f"Не заполнены: {', '.join(empty_fields)}")
                return None

            # Очистка телефона от форматирования для сохранения
            if author["phone"]:
                digits = re.sub(r'[^\d+]', '', author["phone"])
                author["phone"] = digits

            # Очистка даты от форматирования
            if author["birthday"]:
                author["birthday"] = re.sub(r'[^\d.]', '', author["birthday"])

            authors.append(author)

        return authors

    def copy_file_to_output(self, source_path):
        """Копирование файла в папку output"""
        if source_path:
            dest_path = os.path.join(self.output_dir, os.path.basename(source_path))
            shutil.copy2(source_path, dest_path)
            return dest_path
        return None

    def count_pages_exact(self, filepath):
        """Подсчет страниц в Word документе"""
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(os.path.abspath(filepath))
            pages = doc.ComputeStatistics(2)
            doc.Close(False)
            word.Quit()
            return pages
        except Exception as e:
            self.log(f"Ошибка подсчета страниц: {str(e)}", True)
            return 1

    def generate_documents(self):
        """Генерация всех документов"""
        try:
            program_name = self.program_name.get_value()
            authors = self.collect_author_data()
            if not authors:
                return

            quantity = len(authors)
            fio_string = ", ".join(a["fio"] for a in authors)

            source_dest = self.copy_file_to_output(self.source_code_path)
            abstract_dest = self.copy_file_to_output(self.abstract_path)

            self.log("Начало генерации документов...")

            self.log("Генерация документа с исходным кодом...")
            with open(source_dest, "r", encoding="utf-8") as f:
                code = f.read()

            doc = DocxTemplate("templates/source_code_template.docx")
            doc.render({"name": program_name, "fio_of_authors": fio_string, "code": code})
            doc.save(os.path.join(self.output_dir, "source-code.docx"))

            self.log("Подсчет страниц...")
            ns = str(self.count_pages_exact(os.path.join(self.output_dir, "source-code.docx")))
            nr = str(self.count_pages_exact(abstract_dest))

            self.log("Генерация документов для первого автора...")
            self.generate_first_author_docs(program_name, quantity, authors[0], ns, nr)

            if quantity > 1:
                self.log(f"Генерация документов для остальных {quantity - 1} авторов...")
                self.generate_other_authors_docs(program_name, quantity, authors[1:])

            self.log("Генерация приложения 3...")
            self.generate_pril3(program_name, authors)

            self.log("Генерация приложения 4...")
            self.generate_pril4(program_name, authors)

            self.log("Создание архива...")
            self.create_archive()

            self.log("Генерация завершена успешно!")
            messagebox.showinfo("Успех", "Документы успешно сгенерированы и упакованы в архив!")

        except Exception as e:
            self.log(f"Ошибка генерации: {str(e)}", True)
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

    def generate_first_author_docs(self, program_name, quantity, author, ns, nr):
        """Генерация документов для первого автора"""
        passport_parts = author["passport"].split(" ")
        passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"
        day, month, year = author["birthday"].split(".")

        doc = DocxTemplate("templates/pril1-211-1-1.docx")
        context = {
            "name": program_name,
            "fio_author1": author["fio"],
            "quantity_of_authors": quantity,
            "adres_author1": author["address"],
            "phone_author1": author["phone"],
            "email_author1": author["email"],
            "inn_author1": author["inn"],
            "passport_author1": passport_series_number,
            "skils_author1": author["snils"],
        }
        doc.render(context)
        doc.save(os.path.join(self.output_dir, "pril1-211-1-1.docx"))

        doc = DocxTemplate("templates/pril1-211-1-2.docx")
        context = {
            "name": program_name,
            "fio_author1": author["fio"],
            "q": quantity,
            "adres_author1": author["address"],
            "d_a1": day,
            "m_a1": month,
            "y_a1": year,
            "skill_author1": author["skill"],
            "ns": ns,
            "nr": nr,
        }
        doc.render(context)
        doc.save(os.path.join(self.output_dir, "pril1-211-1-2.docx"))

    def generate_other_authors_docs(self, program_name, quantity, authors):
        """Генерация документов для остальных авторов"""
        for idx, author in enumerate(authors, start=2):
            passport_parts = author["passport"].split(" ")
            passport_series_number = f"{passport_parts[0]} {passport_parts[1]}"
            day, month, year = author["birthday"].split(".")

            doc = DocxTemplate("templates/pril1-211-2-1.docx")
            context = {
                "name": program_name,
                "fio_author": author["fio"],
                "quantity_of_authors": quantity,
                "adres_author": author["address"],
                "passport_author": passport_series_number,
                "snils_author": author["snils"],
            }
            doc.render(context)
            doc.save(os.path.join(self.output_dir, f"pril1-211-2-1_author{idx}.docx"))

            doc = DocxTemplate("templates/pril1-211-2-2.docx")
            context = {
                "name": program_name,
                "fio_author": author["fio"],
                "adres_author": author["address"],
                "d_a": day,
                "m_a": month,
                "y_a": year,
                "skill_author": author["skill"],
            }
            doc.render(context)
            doc.save(os.path.join(self.output_dir, f"pril1-211-2-2_author{idx}.docx"))

    def generate_pril3(self, program_name, authors):
        """Генерация приложения 3"""
        if len(authors) == 1:
            doc = DocxTemplate("templates/pril3_211.docx")
            context = {
                "name": program_name,
                "fio_author": authors[0]["fio"],
                "adres_author": authors[0]["address"],
                "passport_author_fully": authors[0]["passport"],
            }
            doc.render(context)
            doc.save(os.path.join(self.output_dir, "pril3_211.docx"))
        else:
            for idx, author in enumerate(authors, start=1):
                doc = DocxTemplate("templates/pril3_211.docx")
                context = {
                    "name": program_name,
                    "fio_author": author["fio"],
                    "adres_author": author["address"],
                    "passport_author_fully": author["passport"],
                }
                doc.render(context)
                doc.save(os.path.join(self.output_dir, f"pril3_211_author{idx}.docx"))

    def generate_pril4(self, program_name, authors):
        """Генерация приложения 4"""
        if len(authors) == 1:
            day, month, year = authors[0]["birthday"].split(".")
            doc = DocxTemplate("templates/pril4_211 .docx")
            context = {
                "name": program_name,
                "fio_author": authors[0]["fio"],
                "adres_author": authors[0]["address"],
                "d_a": day,
                "m_a": month,
                "y_a": year,
            }
            doc.render(context)
            doc.save(os.path.join(self.output_dir, "pril4_211.docx"))
        else:
            for idx, author in enumerate(authors, start=1):
                day, month, year = author["birthday"].split(".")
                doc = DocxTemplate("templates/pril4_211 .docx")
                context = {
                    "name": program_name,
                    "fio_author": author["fio"],
                    "adres_author": author["address"],
                    "d_a": day,
                    "m_a": month,
                    "y_a": year,
                }
                doc.render(context)
                doc.save(os.path.join(self.output_dir, f"pril4_211_author{idx}.docx"))

    def create_archive(self):
        """Создание архива с документами"""
        archive_path = filedialog.asksaveasfilename(
            title="Сохранить архив",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
            initialfile="Документы для патента.zip"
        )

        if archive_path:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.output_dir):
                    for file in files:
                        if file not in [os.path.basename(self.source_code_path),
                                        os.path.basename(self.abstract_path)]:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, os.path.basename(file_path))

            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    if file not in [os.path.basename(self.source_code_path),
                                    os.path.basename(self.abstract_path)]:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass

            self.log(f"Архив сохранен: {archive_path}")
        else:
            self.log("Сохранение архива отменено", True)

    def start_generation(self):
        """Запуск генерации в отдельном потоке"""
        if not self.validate_inputs():
            return

        thread = threading.Thread(target=self.generate_documents)
        thread.daemon = True
        thread.start()

    def clear_all(self):
        """Очистка всех полей"""
        self.program_name.delete(0, tk.END)
        self.program_name.put_placeholder()

        self.author_count.delete(0, tk.END)
        self.author_count.put_placeholder()

        self.source_code_path = None
        self.abstract_path = None
        self.source_code_label.config(text="Файл не выбран", foreground=ERROR_COLOR)
        self.abstract_label.config(text="Файл не выбран", foreground=ERROR_COLOR)
        self.log_text.delete(1.0, tk.END)

        # Очистка полей авторов
        for frame in self.author_frames.values():
            frame.destroy()
        self.author_frames.clear()
        self.author_widgets.clear()
        self.current_author_count = 0

        # Очистка папки output
        for file in os.listdir(self.output_dir):
            file_path = os.path.join(self.output_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = PatentApp(root)
    root.mainloop()