"""Database — SQLite wrapper composed from focused mix-ins.

Split:
  data/task_db.py       — task, subtask, reminder, deadline, archive, tag, ordering
  data/category_db.py   — category CRUD and task-category assignment
  data/analytics_db.py  — read-only aggregate/analytics queries
"""
import sqlite3
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from entities.task.repository import TaskDbMixin
from entities.category.repository import CategoryDbMixin
from entities.analytics.repository import AnalyticsDbMixin
from entities.finance.repository import FinanceDbMixin


def _get_db_path() -> Path:
    """Return path to DB in %APPDATA%/todo_app/tasks.sqlite."""
    app_data = os.getenv("APPDATA")
    if app_data:
        db_dir = Path(app_data) / "todo_app"
    else:
        db_dir = Path.home() / ".todo_app"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "tasks.sqlite"


def _migrate_old_db(new_path: Path) -> None:
    """Move legacy DB from data/ to new location if needed."""
    old_path = Path(__file__).resolve().parent / "tasks.sqlite"
    if old_path.exists() and not new_path.exists():
        shutil.move(str(old_path), str(new_path))


DB_PATH = _get_db_path()
_migrate_old_db(DB_PATH)

# Column lists (authoritative copies; mixins keep local copies for standalone use)
_TASK_COLS = "id, title, description, is_done, created_at, completed_at, updated_at, priority, category_id, remind_at, remind_shown, deadline_at, deadline_notified, is_pinned, recurrence, tags, sort_order, is_archived"
_CATEGORY_COLS = "id, name, color, sort_order, created_at"


class Database(TaskDbMixin, CategoryDbMixin, AnalyticsDbMixin, FinanceDbMixin):
    """SQLite database wrapper.  All domain methods live in the mix-ins above."""

    def __init__(self, path: str | None = None):
        self.path = str(DB_PATH if path is None else path)
        self._con = sqlite3.connect(self.path, timeout=10)
        self._init_db()

    # ── schema ───────────────────────────────────────────
    def _init_db(self):
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        self._con.commit()

        # legacy migration: add description column for very old DBs
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "description" not in cols:
            self._con.execute("ALTER TABLE tasks ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            self._con.commit()

        self._run_migrations()

    def _db_version(self) -> int:
        return self._con.execute("PRAGMA user_version").fetchone()[0]

    def _run_migrations(self):
        ver = self._db_version()
        is_fresh = (ver == 0)
        if ver < 1:
            self._migrate_v1()
        if ver < 2:
            self._migrate_v2()
        if ver < 3:
            self._migrate_v3()
        if ver < 4:
            self._migrate_v4()
        if ver < 5:
            self._migrate_v5()
        if ver < 6:
            self._migrate_v6()
        if ver < 7:
            self._migrate_v7()
        if ver < 8:
            self._migrate_v8()
        if ver < 9:
            self._migrate_v9()
        if ver < 10:
            self._migrate_v10()
        if ver < 11:
            if not is_fresh:
                self._migrate_v11()
            else:
                self._con.execute("PRAGMA user_version = 11")
                self._con.commit()
        if ver < 12:
            if not is_fresh:
                self._migrate_v12()
            else:
                self._con.execute("PRAGMA user_version = 12")
                self._con.commit()

    def _migrate_v12(self):
        """v11→v12: add active tasks with deadlines so calendar has data."""
        self._seed_calendar_tasks()
        self._con.execute("PRAGMA user_version = 12")
        self._con.commit()

    def _seed_calendar_tasks(self):
        """Delete old active no-deadline tasks, insert new ones with deadlines."""
        from datetime import date, datetime, timedelta, timezone
        tz = timezone.utc
        today = date.today()
        now_iso = datetime.now(tz).isoformat(timespec="seconds")

        # Remove old active tasks that have no deadline (added by v11)
        self._con.execute(
            "DELETE FROM tasks WHERE is_archived=0 AND tags='' AND deadline_at IS NULL"
        )
        self._con.commit()

        max_order = self._con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM tasks"
        ).fetchone()[0]

        def _dl(offset_days: int) -> str:
            d = today + timedelta(days=offset_days)
            return datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz).isoformat(timespec="seconds")

        # (title, desc, priority, deadline_offset_days, is_done)
        tasks = [
            # Overdue
            ("Сдать отчёт за февраль",           "",                               3, -5,  0),
            ("Оплатить налог",                    "",                               3, -2,  0),
            # Today
            ("Созвон с клиентом",                 "Обсудить требования",            2,  0,  0),
            ("Подготовить презентацию",           "Слайды для стендапа",            3,  0,  0),
            # This week
            ("Провести код-ревью",                "",                               2,  1,  0),
            ("Обновить зависимости проекта",      "",                               1,  2,  0),
            ("Написать тесты",                    "Покрытие > 80%",                 2,  3,  0),
            ("Встреча с командой",                "Подготовить agenda",             1,  4,  0),
            ("Деплой на production",              "",                               3,  5,  0),
            # Next week
            ("Купить подарок на д/р",             "",                               2,  8,  0),
            ("Записаться к стоматологу",          "",                               1,  9,  0),
            ("Ревью архитектуры",                 "Clean Architecture гл.5",        1, 10,  0),
            ("Разобрать входящие письма",         "",                               0, 11,  0),
            ("Изучить Rust",                      "Chapter 3 — ownership",          1, 12,  0),
            # Later this month
            ("Подготовить отчёт за квартал",      "Свести данные из 3 отделов",     3, 15,  0),
            ("Настроить CI/CD",                   "",                               2, 17,  0),
            ("Оптимизировать запросы к БД",       "",                               2, 19,  0),
            # Next month
            ("Квартальный ревью",                 "",                               2, 25,  0),
            ("Обновить roadmap",                  "",                               1, 28,  0),
            ("Написать документацию API",         "",                               1, 32,  0),
            ("Финальный тест курса по дизайну",   "",                               1, 35,  0),
            # Done (show as completed in calendar)
            ("Настроить линтер",                  "",                               1, -8,  1),
            ("Рефакторинг auth модуля",           "",                               2, -6,  1),
            ("Обновить README",                   "",                               0, -4,  1),
            ("Убраться дома",                     "",                               0, -3,  1),
            ("Созвон с ментором",                 "",                               1, -1,  1),
        ]

        rows = []
        for title, desc, pri, dl_off, is_done in tasks:
            max_order += 1
            deadline = _dl(dl_off)
            completed_at = deadline if is_done else None
            rows.append((
                title, desc, is_done, now_iso, completed_at, now_iso,
                pri, None, max_order, 0, "", deadline
            ))

        self._con.executemany(
            "INSERT INTO tasks(title, description, is_done, created_at, completed_at, "
            "updated_at, priority, category_id, sort_order, is_archived, tags, deadline_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        self._con.commit()

    def _migrate_v11(self):
        """v10→v11: seed 90-day task history for analytics demo (non-destructive)."""
        self._seed_task_history()
        self._con.execute("PRAGMA user_version = 11")
        self._con.commit()

    def _seed_tutorial_task(self):
        """Insert a single pinned tutorial task with rich HTML formatting (language-aware)."""
        from datetime import datetime, timezone
        try:
            from shared.i18n import current_language
            lang = current_language()
        except Exception:
            lang = "ru"
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        _BODY = "font-family:'Segoe UI',Arial,sans-serif; font-size:13pt; color:#e8e8ea; margin:0; padding:0;"
        _H1   = "font-size:20pt; font-weight:700; color:#5ea2ff;"
        _SUB  = "color:#8a9ab5; font-size:11pt;"
        _H2b  = "font-size:15pt; font-weight:700; color:#5ea2ff;"
        _H2o  = "font-size:15pt; font-weight:700; color:#ff9f43;"
        _H2g  = "font-size:15pt; font-weight:700; color:#52d38a;"
        _H2p  = "font-size:15pt; font-weight:700; color:#c27cff;"
        _H2r  = "font-size:15pt; font-weight:700; color:#ff6b6b;"
        _H2c  = "font-size:15pt; font-weight:700; color:#64d2ff;"
        _H2y  = "font-size:15pt; font-weight:700; color:#ffd166;"
        _TXT  = "color:#c8d0e0;"
        _KEY  = "color:#ffd166; font-weight:600;"
        _DIM  = "color:#8a9ab5; font-size:10pt;"
        _ACC  = "color:#5ea2ff; font-weight:600; font-size:12pt;"

        if lang == "en":
            title = "👋 Welcome to toXo!"
            body = f"""
<p style="margin:0 0 4px 0;"><span style="{_H1}">👋 Welcome to toXo!</span></p>
<p style="margin:0 0 18px 0; {_SUB}">A quick guide to all features of the app</p>

<p style="margin:0 0 6px 0;"><span style="{_H2b}">✅ Tasks</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Press <span style="{_KEY}">+</span> or <span style="{_KEY}">Ctrl+N</span> to create a new task.</p>
<p style="margin:0 0 4px 0; {_TXT}">Click a task — the editor opens on the right with title and description.</p>
<p style="margin:0 0 16px 0; {_TXT}"><span style="{_KEY}">Ctrl+D</span> — mark done &nbsp;|&nbsp; <span style="{_KEY}">Del</span> — delete</p>

<p style="margin:0 0 6px 0;"><span style="{_H2o}">🎯 Priorities</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Set a priority for each task in the right editor:</p>
<p style="margin:0 0 2px 0; {_TXT}">&nbsp;&nbsp;<span style="color:#8a9ab5;">⬜ None</span> &nbsp; <span style="color:#64d2ff;">🔵 Low</span> &nbsp; <span style="color:#ff9f43;">🟠 Medium</span> &nbsp; <span style="color:#ff6b6b;">🔴 High</span></p>
<p style="margin:0 0 16px 0; {_DIM}">High-priority tasks appear bolder in the list</p>

<p style="margin:0 0 6px 0;"><span style="{_H2g}">🗂 Categories</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Create categories (the color strip under the search bar) to group tasks.</p>
<p style="margin:0 0 16px 0; {_TXT}">Drag tasks directly onto a category icon to assign them.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2p}">🏷 Tags</span></p>
<p style="margin:0 0 4px 0; {_TXT}">In the editor, enter tags separated by commas: <span style="color:#c27cff; font-weight:600;">#work, #ideas</span></p>
<p style="margin:0 0 16px 0; {_TXT}">In search, type <span style="color:#c27cff; font-weight:600;">#tag</span> to filter by it.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2r}">⏰ Deadlines &amp; Reminders</span></p>
<p style="margin:0 0 4px 0; {_TXT}"><span style="color:#ff6b6b; font-weight:600;">🔔 Reminder</span> button in the editor — set a date and time.</p>
<p style="margin:0 0 4px 0; {_TXT}"><span style="color:#ff6b6b; font-weight:600;">📅 Deadline</span> button — the task appears in the calendar on that day.</p>
<p style="margin:0 0 16px 0; {_DIM}">Overdue tasks are highlighted in red</p>

<p style="margin:0 0 6px 0;"><span style="{_H2c}">📊 Analytics</span></p>
<p style="margin:0 0 4px 0; {_TXT}"><span style="color:#64d2ff; font-weight:600;">📈 Analytics</span> button — productivity charts for 7 / 30 / 90 days.</p>
<p style="margin:0 0 16px 0; {_TXT}">Load test data (Settings → Load test data) to see example charts.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2y}">📅 Calendar</span></p>
<p style="margin:0 0 4px 0; {_TXT}"><span style="color:#ffd166; font-weight:600;">📅 Calendar</span> button — tasks with deadlines on a grid.</p>
<p style="margin:0 0 16px 0; {_TXT}">Drag a task from the list onto a calendar day to set a deadline.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2g}">💰 Finance</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Menu (☰) → <span style="color:#52d38a; font-weight:600;">Finance</span> — a dedicated financial workspace.</p>
<p style="margin:0 0 16px 0; {_TXT}">Add accounts, income/expenses, set budgets and savings goals.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2o}">⌨️ Keyboard Shortcuts</span></p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+K</span> — command palette (all actions in one search)</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+Z / Ctrl+Y</span> — undo / redo</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+Shift+D</span> — duplicate task</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+↑/↓</span> — navigate the list</p>
<p style="margin:0 0 20px 0; {_TXT}"><span style="{_KEY}">Ctrl+F</span> — focus search</p>

<p style="margin:0; {_ACC}">🚀 Delete this task once you're ready — let's go!</p>"""
        else:
            title = "👋 Добро пожаловать в toXo!"
            body = f"""
<p style="margin:0 0 4px 0;"><span style="{_H1}">👋 Добро пожаловать в toXo!</span></p>
<p style="margin:0 0 18px 0; {_SUB}">Это краткое руководство по всем возможностям приложения</p>

<p style="margin:0 0 6px 0;"><span style="{_H2b}">✅ Задачи</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Нажми <span style="{_KEY}">+</span> или <span style="{_KEY}">Ctrl+N</span> чтобы создать новую задачу.</p>
<p style="margin:0 0 4px 0; {_TXT}">Кликни на задачу — справа откроется редактор с заголовком и описанием.</p>
<p style="margin:0 0 16px 0; {_TXT}"><span style="{_KEY}">Ctrl+D</span> — отметить выполненной &nbsp;|&nbsp; <span style="{_KEY}">Del</span> — удалить</p>

<p style="margin:0 0 6px 0;"><span style="{_H2o}">🎯 Приоритеты</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Каждой задаче можно задать приоритет в редакторе справа:</p>
<p style="margin:0 0 2px 0; {_TXT}">&nbsp;&nbsp;<span style="color:#8a9ab5;">⬜ Без приоритета</span> &nbsp; <span style="color:#64d2ff;">🔵 Низкий</span> &nbsp; <span style="color:#ff9f43;">🟠 Средний</span> &nbsp; <span style="color:#ff6b6b;">🔴 Высокий</span></p>
<p style="margin:0 0 16px 0; {_DIM}">Задачи с высоким приоритетом отображаются жирнее в списке</p>

<p style="margin:0 0 6px 0;"><span style="{_H2g}">🗂 Категории</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Создавай категории (полоска цветов под поиском) для группировки задач.</p>
<p style="margin:0 0 16px 0; {_TXT}">Задачи можно перетаскивать прямо на значок категории мышью.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2p}">🏷 Теги</span></p>
<p style="margin:0 0 4px 0; {_TXT}">В редакторе введи теги через запятую: <span style="color:#c27cff; font-weight:600;">#работа, #идеи</span></p>
<p style="margin:0 0 16px 0; {_TXT}">В поиске введи <span style="color:#c27cff; font-weight:600;">#тег</span> чтобы фильтровать по нему.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2r}">⏰ Дедлайны и напоминания</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Кнопка <span style="color:#ff6b6b; font-weight:600;">🔔 Напоминание</span> в редакторе — установи дату и время.</p>
<p style="margin:0 0 4px 0; {_TXT}">Кнопка <span style="color:#ff6b6b; font-weight:600;">📅 Дедлайн</span> — задача появится в календаре в нужный день.</p>
<p style="margin:0 0 16px 0; {_DIM}">Просроченные задачи подсвечиваются красным</p>

<p style="margin:0 0 6px 0;"><span style="{_H2c}">📊 Аналитика</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Кнопка <span style="color:#64d2ff; font-weight:600;">📈 Аналитика</span> на панели — графики продуктивности за 7/30/90 дней.</p>
<p style="margin:0 0 16px 0; {_TXT}">Загрузи тестовые данные (Настройки → Загрузить тестовые данные) чтобы увидеть примеры.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2y}">📅 Календарь</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Кнопка <span style="color:#ffd166; font-weight:600;">📅 Календарь</span> — задачи с дедлайнами на сетке.</p>
<p style="margin:0 0 16px 0; {_TXT}">Перетащи задачу из списка прямо на день в календаре чтобы назначить дедлайн.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2g}">💰 Финансы</span></p>
<p style="margin:0 0 4px 0; {_TXT}">Меню (☰) → <span style="color:#52d38a; font-weight:600;">Финансы</span> — отдельное рабочее пространство.</p>
<p style="margin:0 0 16px 0; {_TXT}">Добавляй счета, доходы/расходы, устанавливай бюджеты и цели.</p>

<p style="margin:0 0 6px 0;"><span style="{_H2o}">⌨️ Горячие клавиши</span></p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+K</span> — командная палитра (все действия в одном поиске)</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+Z / Ctrl+Y</span> — отмена / повтор</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+Shift+D</span> — дублировать задачу</p>
<p style="margin:0 0 2px 0; {_TXT}"><span style="{_KEY}">Ctrl+↑/↓</span> — навигация по списку</p>
<p style="margin:0 0 20px 0; {_TXT}"><span style="{_KEY}">Ctrl+F</span> — фокус на поиск</p>

<p style="margin:0; {_ACC}">🚀 Удали эту задачу когда разберёшься — и вперёд!</p>"""

        html = f'<!DOCTYPE HTML><html><body style="{_BODY}">{body}\n</body></html>'
        max_order = self._con.execute("SELECT COALESCE(MAX(sort_order),0) FROM tasks").fetchone()[0]
        self._con.execute(
            "INSERT INTO tasks(title, description, is_done, created_at, completed_at, "
            "updated_at, priority, category_id, sort_order, is_archived, tags, is_pinned) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, html, 0, now, None, now, 0, None, max_order + 1, 0, "tutorial", 1)
        )
        self._con.commit()

    def _seed_task_history(self):
        """Clear all tasks and seed ~300 demo tasks with 90-day history for analytics."""
        import random
        from datetime import date, datetime, timedelta, timezone
        try:
            from shared.i18n import current_language
            lang = current_language()
        except Exception:
            lang = "ru"
        rng = random.Random(7)
        today = date.today()
        tz = timezone.utc

        self._con.execute("DELETE FROM subtasks")
        self._con.execute("DELETE FROM tasks")
        self._con.commit()

        max_order = 0

        if lang == "en":
            task_titles = [
                # Work
                "Prepare presentation", "Reply to emails", "Code review PR",
                "Fix production bug", "Write documentation", "Update dependencies",
                "Team call", "Write unit tests", "Refactor module",
                "Deploy to staging", "Close sprint tasks", "Update roadmap",
                "Design review", "Set up CI/CD", "Optimize DB queries",
                # Personal
                "Go to the gym", "Buy groceries", "Call parents",
                "Read a book chapter", "Schedule doctor visit", "Pay bills",
                "Clean the apartment", "Morning workout", "10-min meditation",
                "Meal prep for the week", "Check email", "Write in journal",
                # Learning
                "Watch Python lecture", "Complete design lesson",
                "Learn new framework", "Finish course assignment",
                "Read article on Dev.to", "Write notes", "Algorithm practice",
            ]
        else:
            task_titles = [
                # Work
                "Подготовить презентацию", "Ответить на письма", "Код-ревью PR",
                "Исправить баг в продакшне", "Написать документацию", "Обновить зависимости",
                "Созвон с командой", "Написать unit-тесты", "Рефакторинг модуля",
                "Задеплоить на staging", "Закрыть задачи спринта", "Обновить roadmap",
                "Ревью дизайна", "Настроить CI/CD", "Оптимизировать запросы к БД",
                # Personal
                "Сходить в спортзал", "Купить продукты", "Позвонить родителям",
                "Прочитать главу книги", "Записаться к врачу", "Оплатить счета",
                "Убраться дома", "Сделать зарядку", "Медитация 10 минут",
                "Приготовить еду на неделю", "Проверить почту", "Написать в дневник",
                # Learning
                "Посмотреть лекцию по Python", "Пройти урок по дизайну",
                "Изучить новый фреймворк", "Сделать задание по курсу",
                "Почитать статью на Habr", "Написать конспект", "Практика алгоритмов",
            ]

        tasks = []
        for offset in range(90, 0, -1):
            d_obj = today - timedelta(days=offset)
            is_wend = d_obj.weekday() >= 5

            # Completions per day: 2–6 weekdays, 1–3 weekends
            n_done = rng.randint(1, 3) if is_wend else rng.randint(2, 6)
            # New active tasks added each day: 1–3
            n_new = rng.randint(1, 3)

            for _ in range(n_done):
                title = rng.choice(task_titles)
                # Task was created 1–5 days before completion
                created_offset = rng.randint(1, 5)
                created_d = d_obj - timedelta(days=created_offset)
                created_h = rng.randint(8, 20)
                created_at = datetime(
                    created_d.year, created_d.month, created_d.day,
                    created_h, rng.randint(0, 59), tzinfo=tz
                ).isoformat(timespec="seconds")
                completed_h = rng.randint(8, 22)
                completed_at = datetime(
                    d_obj.year, d_obj.month, d_obj.day,
                    completed_h, rng.randint(0, 59), tzinfo=tz
                ).isoformat(timespec="seconds")
                priority = rng.choices([0, 1, 2, 3], weights=[50, 25, 15, 10])[0]
                max_order += 1
                tasks.append((
                    title, "", 1, created_at, completed_at, completed_at,
                    priority, None, max_order, 1, "demo"
                ))

            for _ in range(n_new):
                title = rng.choice(task_titles)
                created_h = rng.randint(8, 22)
                created_at = datetime(
                    d_obj.year, d_obj.month, d_obj.day,
                    created_h, rng.randint(0, 59), tzinfo=tz
                ).isoformat(timespec="seconds")
                priority = rng.choices([0, 1, 2, 3], weights=[50, 25, 15, 10])[0]
                max_order += 1
                # Most old "active" tasks are archived so they don't clutter the list
                is_archived = 1 if offset > 7 else 0
                tasks.append((
                    title, "", 0, created_at, None, created_at,
                    priority, None, max_order, is_archived, "demo"
                ))

        # ── Active + calendar tasks (visible in list, with deadlines) ──────────
        now_iso = datetime.now(tz).isoformat(timespec="seconds")

        def _dl(offset_days: int) -> str:
            """Return ISO deadline string at 09:00 UTC offset from today."""
            d = today + timedelta(days=offset_days)
            return datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz).isoformat(timespec="seconds")

        # (title, desc, priority, deadline_offset_days, is_done)
        if lang == "en":
            calendar_tasks = [
                # Overdue
                ("Submit February report",        "",                              3, -5,  0),
                ("Pay tax",                       "",                              3, -2,  0),
                # Today / very soon
                ("Client call",                   "Discuss requirements",          2,  0,  0),
                ("Prepare presentation",          "Slides for standup",            3,  0,  0),
                ("Run code review",               "",                              2,  1,  0),
                # This week
                ("Update project dependencies",   "",                              1,  2,  0),
                ("Write tests",                   "Coverage > 80%",                2,  3,  0),
                ("Team meeting",                  "Prepare agenda",                1,  4,  0),
                ("Deploy to production",          "",                              3,  5,  0),
                # Next week
                ("Buy birthday gift",             "",                              2,  8,  0),
                ("Schedule dentist",              "",                              1,  9,  0),
                ("Architecture review",           "Clean Architecture ch.5",       1, 10,  0),
                ("Process inbox",                 "",                              0, 11,  0),
                ("Learn new tool",                "Rust — chapter 3",              1, 12,  0),
                # Later this month
                ("Prepare quarterly report",      "Consolidate data from 3 teams", 3, 15,  0),
                ("Set up CI/CD",                  "",                              2, 17,  0),
                ("Optimize DB queries",           "",                              2, 19,  0),
                ("30-day workout streak",         "",                              0, 20,  0),
                # Next month
                ("Quarterly review",              "",                              2, 25,  0),
                ("Update roadmap",                "",                              1, 28,  0),
                ("Write documentation",           "API docs",                      1, 32,  0),
                ("Design course — final test",    "",                              1, 35,  0),
                # Already done (shows in calendar as ✓)
                ("Set up linter",                 "",                              1, -8,  1),
                ("Refactor auth module",          "",                              2, -6,  1),
                ("Update README",                 "",                              0, -4,  1),
                ("Clean the apartment",           "",                              0, -3,  1),
                ("Call with mentor",              "",                              1, -1,  1),
            ]
        else:
            calendar_tasks = [
                # Overdue
                ("Сдать отчёт за февраль",          "",                               3, -5,  0),
                ("Оплатить налог",                   "",                               3, -2,  0),
                # Today / very soon
                ("Созвон с клиентом",                "Обсудить требования",            2,  0,  0),
                ("Подготовить презентацию",          "Слайды для стендапа",            3,  0,  0),
                ("Провести код-ревью",               "",                               2,  1,  0),
                # This week
                ("Обновить зависимости проекта",     "",                               1,  2,  0),
                ("Написать тесты",                   "Покрытие > 80%",                 2,  3,  0),
                ("Встреча с командой",               "Подготовить agenda",             1,  4,  0),
                ("Деплой на production",             "",                               3,  5,  0),
                # Next week
                ("Купить подарок на д/р",            "",                               2,  8,  0),
                ("Записаться к стоматологу",         "",                               1,  9,  0),
                ("Ревью архитектуры",                "Clean Architecture гл.5",        1, 10,  0),
                ("Разобрать входящие письма",        "",                               0, 11,  0),
                ("Изучить новый инструмент",         "Rust — chapter 3",               1, 12,  0),
                # Later this month
                ("Подготовить отчёт за квартал",     "Свести данные из 3 отделов",     3, 15,  0),
                ("Настроить CI/CD",                  "",                               2, 17,  0),
                ("Оптимизировать запросы к БД",      "",                               2, 19,  0),
                ("Сделать зарядку 30 дней подряд",   "",                               0, 20,  0),
                # Next month
                ("Квартальный ревью",                "",                               2, 25,  0),
                ("Обновить roadmap",                 "",                               1, 28,  0),
                ("Написать документацию",            "API docs",                       1, 32,  0),
                ("Курс по дизайну — финальный тест", "",                               1, 35,  0),
                # Already done (shows in calendar as ✓)
                ("Настроить линтер",                 "",                               1, -8,  1),
                ("Рефакторинг auth модуля",          "",                               2, -6,  1),
                ("Обновить README",                  "",                               0, -4,  1),
                ("Убраться дома",                    "",                               0, -3,  1),
                ("Созвон с ментором",                "",                               1, -1,  1),
            ]

        for title, desc, pri, dl_offset, is_done in calendar_tasks:
            max_order += 1
            deadline = _dl(dl_offset)
            completed_at = deadline if is_done else None
            tasks.append((
                title, desc, is_done, now_iso, completed_at, now_iso,
                pri, None, max_order, 0, "", deadline
            ))

        # Historical tasks have no deadline — pad with None
        # Rebuild: separate inserts since deadline column differs
        hist_tasks = [t for t in tasks if len(t) == 11]
        cal_tasks  = [t for t in tasks if len(t) == 12]

        self._con.executemany(
            "INSERT INTO tasks(title, description, is_done, created_at, completed_at, "
            "updated_at, priority, category_id, sort_order, is_archived, tags) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            hist_tasks
        )
        self._con.executemany(
            "INSERT INTO tasks(title, description, is_done, created_at, completed_at, "
            "updated_at, priority, category_id, sort_order, is_archived, tags, deadline_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            cal_tasks
        )
        self._con.commit()
        # Pinned tutorial task always appears at the top
        self._seed_tutorial_task()

    def _migrate_v10(self):
        """v9→v10: replace 30-day mock data with 90-day richer dataset."""
        for tbl in ("fin_transactions", "fin_budgets", "fin_goals", "fin_accounts", "fin_categories"):
            self._con.execute(f"DELETE FROM {tbl}")
        self._con.commit()
        self._seed_finance_mock()
        self._con.execute("PRAGMA user_version = 10")
        self._con.commit()

    def _migrate_v9(self):
        """v8→v9: create finance tables; seed mock data on first run."""
        self._init_finance_tables()
        count = self._con.execute("SELECT COUNT(*) FROM fin_accounts").fetchone()[0]
        if count == 0:
            self._seed_finance_mock()
        self._con.execute("PRAGMA user_version = 9")
        self._con.commit()

    def _migrate_v8(self):
        """v7→v8: add is_archived flag to tasks."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "is_archived" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0"
            )
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_archived ON tasks(is_archived)"
        )
        self._con.execute("PRAGMA user_version = 8")
        self._con.commit()

    def _migrate_v7(self):
        """v6→v7: add tags (text) and sort_order (int) to tasks."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "tags" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
            )
        if "sort_order" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
            self._con.execute("UPDATE tasks SET sort_order = id")
        self._con.execute("PRAGMA user_version = 7")
        self._con.commit()

    def _migrate_v1(self):
        """v0→v1: add completed_at, updated_at, priority; create task_events; backfill."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "completed_at" not in cols:
            self._con.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
        if "updated_at" not in cols:
            self._con.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
        if "priority" not in cols:
            self._con.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
        self._con.execute(
            "UPDATE tasks SET completed_at = created_at WHERE is_done = 1 AND completed_at IS NULL"
        )
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                ts TEXT NOT NULL
            )
        """)
        cnt = self._con.execute("SELECT COUNT(*) FROM task_events").fetchone()[0]
        if cnt == 0:
            self._con.execute(
                "INSERT INTO task_events(task_id, event_type, ts) "
                "SELECT id, 'CREATED', created_at FROM tasks"
            )
            self._con.execute(
                "INSERT INTO task_events(task_id, event_type, ts) "
                "SELECT id, 'COMPLETED', completed_at FROM tasks WHERE is_done = 1 AND completed_at IS NOT NULL"
            )
        self._con.execute("PRAGMA user_version = 1")
        self._con.commit()

    def _migrate_v2(self):
        """v1→v2: create categories table; add category_id to tasks."""
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(name)
            )
        """)
        self._con.execute("""
            CREATE INDEX IF NOT EXISTS idx_categories_sort
            ON categories(sort_order)
        """)
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "category_id" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN category_id INTEGER DEFAULT NULL"
            )
        self._con.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_category
            ON tasks(category_id)
        """)
        self._con.execute("PRAGMA user_version = 2")
        self._con.commit()

    def _migrate_v3(self):
        """v2→v3: add remind_at and remind_shown to tasks."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "remind_at" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN remind_at TEXT DEFAULT NULL"
            )
        if "remind_shown" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN remind_shown INTEGER NOT NULL DEFAULT 0"
            )
        self._con.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_remind
            ON tasks(remind_at, remind_shown)
        """)
        self._con.execute("PRAGMA user_version = 3")
        self._con.commit()

    def _migrate_v4(self):
        """v3→v4: add deadline_at and deadline_notified to tasks."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "deadline_at" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN deadline_at TEXT DEFAULT NULL"
            )
        if "deadline_notified" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN deadline_notified INTEGER NOT NULL DEFAULT 0"
            )
        self._con.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_deadline
            ON tasks(deadline_at, deadline_notified)
        """)
        self._con.execute("PRAGMA user_version = 4")
        self._con.commit()

    def _migrate_v5(self):
        """v4→v5: add is_pinned and recurrence to tasks."""
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(tasks)").fetchall()]
        if "is_pinned" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0"
            )
        if "recurrence" not in cols:
            self._con.execute(
                "ALTER TABLE tasks ADD COLUMN recurrence TEXT DEFAULT NULL"
            )
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_pinned ON tasks(is_pinned)"
        )
        self._con.execute("PRAGMA user_version = 5")
        self._con.commit()

    def _migrate_v6(self):
        """v5→v6: create subtasks table."""
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                is_done INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        self._con.execute(
            "CREATE INDEX IF NOT EXISTS idx_subtasks_task ON subtasks(task_id, sort_order)"
        )
        self._con.execute("PRAGMA user_version = 6")
        self._con.commit()

    # ── helpers ──────────────────────────────────────────
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def close(self):
        self._con.close()
