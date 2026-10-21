# Подключаю библиотеки.
# FastAPI — сам фреймворк: он принимает запросы от браузера и решает, какую функцию вызвать.
# Request — объект запроса, он нужен мне там, где я читаю данные из формы или адресной строки.
from fastapi import FastAPI, Request
# RedirectResponse — перенаправление браузера на другой адрес (после сохранения заявки).
# HTMLResponse — ответ в формате HTML. Без неё FastAPI отдал бы строку как обычный текст,
# и браузер показал бы код страницы вместо самой страницы.
from fastapi.responses import RedirectResponse, HTMLResponse
# uvicorn — сервер, который на самом деле «включает» моё приложение и слушает порт.
import uvicorn
# aiosqlite — асинхронная работа с базой SQLite. Обычный sqlite3 с async/await не совместим.
import aiosqlite
# datetime — работа с датой и временем. Новое подключение ради красивого форматирования даты.
from datetime import datetime

# Создаю приложение. Все декораторы @app... ниже «вешают» мои функции именно на этот объект.
app = FastAPI(
    title="MVP: Заявки на выезд мастера",
    description="Простой сервис для приёма и отслеживания заявок.",
    version="1.0.0"
)

# Имя файла базы данных. SQLite хранит всю базу в одном файле рядом с кодом.
# Если файла нет — он создастся сам при первом запуске.
DB_NAME = "requests.db"

# Словарь-переводчик: статус из базы превращаю в короткое имя класса для CSS.
# Зачем это нужно: в базе статусы на русском («Новая», «В работе»),
# а классы принято писать латиницей — так CSS надёжнее и понятнее.
# Ключ — как в базе, значение — как будет выглядеть class="..." в HTML.
STATUS_TO_CLASS = {
    "Новая": "new",
    "В работе": "in-work",
    "Готово": "done"
}


def format_date(raw):
    # Превращаю дату из базы в красивый человеческий вид.
    # Из базы приходит строка вида "2026-10-21 17:23:23".
    # strptime читает эту строку ПО ИЗВЕСТНОМУ ШАБЛОНУ и делает из неё объект datetime —
    # с ним можно работать как с датой, а не как с текстом.
    # Шаблон %Y-%m-%d %H:%M:%S расшифровывается так:
    #   %Y — год (4 цифры), %m — месяц (01–12), %d — день,
    #   %H — часы, %M — минуты, %S — секунды.
    # Важно: шаблон должен совпадать с реальным содержимым строки посимвольно,
    # иначе будет ValueError — если однажды увидишь такую ошибку, начинай проверку отсюда.
    dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    # strftime — обратная операция: превращаю объект datetime обратно в строку,
    # но уже в том виде, в котором хочу показать человеку.
    # %d.%m.%Y — день.месяц.год (как принято в России),
    # %H:%M — часы и минуты. Секунды не показываю — они не нужны.
    return dt.strftime("%d.%m.%Y %H:%M")


async def init_db():
    # Эта функция запускается один раз при старте сервера.
    # Задача — убедиться, что таблица requests существует, и создать её, если её нет.
    # Страховка: могу удалить файл базы или прийти на новый компьютер —
    # при запуске всё создастся заново без ошибок. Данные она не стирает.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        create_table_query = """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'Новая',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        # created_at — дата и время создания заявки.
        # DEFAULT CURRENT_TIMESTAMP — база сама запишет текущий момент при добавлении строки.
        # Мне не нужно вычислять дату в Python и передавать её руками.
        # NOT NULL — поле обязательно. DEFAULT — если значение не указано, подставится это.
        # Внутри SQL-строки никаких комментариев # писать нельзя — SQL не понимает решётку.
        await cursor.execute(create_table_query)
        # commit — «сохранить» изменения в базе. Без него таблица не зафиксируется.
        await db.commit()
        print("✅ База данных инициализирована.")


async def get_all_requests(status=None):
    # Достаю заявки из базы. Необязательный параметр status — это фильтр.
    # Если фильтр не передан (None), возвращаю все заявки.
    async with aiosqlite.connect(DB_NAME) as db:
        # row_factory = aiosqlite.Row — доступ к колонкам по имени: req['name'], а не req[1].
        db.row_factory = aiosqlite.Row

        # Базовый запрос: выбрать всё, потом отсортировать.
        query = "SELECT * FROM requests"
        params = []

        # Если фильтр передан — добавляю условие WHERE.
        # Параметры всегда передаю отдельным списком через плейсхолдеры:
        # это защита от SQL-инъекций, даже когда параметров несколько.
        if status:
            query += " WHERE status = ?"
            params.append(status)

        # ORDER BY id DESC — новые заявки сверху: самый большой id первым.
        query += " ORDER BY id DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_new_request(name, phone, description):
    # Сохраняю новую заявку в базу. Вызывается из обработчика формы /create.
    # Дату не передаю — её база проставит сама через DEFAULT CURRENT_TIMESTAMP.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        insert_query = "INSERT INTO requests (name, phone, description, status) VALUES (?, ?, ?, ?)"
        # Знаки вопроса — плейсхолдеры: данные идут отдельно от запроса.
        await cursor.execute(insert_query, (name, phone, description, "Новая"))
        await db.commit()


async def update_request_status(request_id, new_status):
    # Меняю статус одной заявки по её id: например, «Новая» становится «В работе».
    # WHERE id = ? — обновляю только нужную строку, а не всю таблицу.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        update_query = "UPDATE requests SET status = ? WHERE id = ?"
        await cursor.execute(update_query, (new_status, request_id))
        await db.commit()


# Строки с @ называются декораторами.
# @app.get("/") читается так: «функцию ниже запускай, когда придёт GET-запрос на такой адрес».
# GET — браузер просто открывает страницу. POST — что-то отправляет (например, форму).


@app.get("/")
async def read_root():
    # Главная страница: отдаю HTML-файл с формой заявки.
    # HTMLResponse превращает строку в настоящую страницу, которую браузер рисует.
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/create")
async def handle_create(request: Request):
    # Обрабатываю отправку формы. Браузер делает POST-запрос на /create и несёт в нём данные полей.
    # Имена полей должны совпадать с name="..." в HTML, иначе будет KeyError.
    form_data = await request.form()
    await create_new_request(
        name=form_data["name"],
        phone=form_data["phone"],
        description=form_data["description"]
    )
    # Редирект на /list с кодом 303: без него обновление страницы отправило бы форму второй раз
    # и появились бы заявки-дубли.
    return RedirectResponse(url="/list", status_code=303)


@app.get("/list")
async def show_list(request: Request):
    # Страница списка. Умеет принимать фильтр из адреса:
    # /list — все заявки, /list?status=Новая — только новые, и так далее.
    # Если параметра в адресе нет, get вернёт None — и фильтр не применится.
    status_filter = request.query_params.get("status")
    requests = await get_all_requests(status=status_filter)

    with open("templates/list.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # rows_html — сюда я накапливаю HTML всех строк таблицы, по одной на заявку.
    rows_html = ""
    for req in requests:
        # По статусу из базы достаю имя класса из словаря STATUS_TO_CLASS.
        # .get() со вторым аргументом — страховка: если вдруг в базе окажется статус,
        # которого нет в словаре, вместо ошибки класс просто будет пустым.
        status_class = STATUS_TO_CLASS.get(req['status'], "")

        # Красивая дата: беру сырую строку из базы и прогоняю через format_date.
        # В базе хранить остаётся как раньше (это удобно для сортировки),
        # красивый вид — только на экране.
        pretty_date = format_date(req['created_at'])

        # class="status ..." — именно на эту метку CSS из list.html навешивает цвет.
        # Каждый req становится одной строкой <tr>...</tr> с ячейками <td>.
        rows_html += f"""
            <tr>
                <td>{req['id']}</td>
                <td>{req['name']}</td>
                <td>{req['phone']}</td>
                <td>{req['description']}</td>
                <td class="status {status_class}">{req['status']}</td>
                <td>{pretty_date}</td>
                <td>
                    <a href="/set_status?id={req['id']}&status=В работе"><button>В работу</button></a>
                    <a href="/set_status?id={req['id']}&status=Готово"><button>Готово</button></a>
                </td>
            </tr>
        """

    # Метка <!-- REPEAT --> в шаблоне — место, куда вставляются собранные строки.
    final_html = html_content.replace("<!-- REPEAT -->", rows_html)
    return HTMLResponse(content=final_html)


@app.get("/set_status")
async def set_status(request: Request):
    # Смена статуса. Кнопка в таблице ведёт на адрес вида /set_status?id=5&status=Готово.
    # Всё, что после ?, называется query-параметрами — я их отсюда и достаю.
    query_params = request.query_params
    req_id = int(query_params.get("id", 0))
    new_status = query_params.get("status", "")

    # Меняю базу только если id выглядит нормально и статус реально передан.
    if req_id > 0 and new_status:
        await update_request_status(req_id, new_status)

    return RedirectResponse(url="/list", status_code=303)


# Блок запуска. if __name__ == "__main__" — код внутри выполняется,
# только если файл запустили напрямую командой python web_service.py.
if __name__ == "__main__":
    import asyncio
    # asyncio.run() — способ вызвать асинхронную функцию из обычного кода.
    # Сначала один раз готовлю базу, потом поднимаю сервер.
    asyncio.run(init_db())
    print("🚀 Сервер запускается на http://127.0.0.1:8000")
    # host="0.0.0.0" — слушать все сетевые интерфейсы: сайт доступен и с localhost,
    # и с другого устройства в той же сети.
    uvicorn.run(app, host="0.0.0.0", port=8000)
