# Подключаю библиотеки.
# FastAPI — сам фреймворк: он принимает запросы от браузера и решает, какую функцию вызвать.
# Request — объект запроса, он нужен мне там, где я читаю данные из формы.
from fastapi import FastAPI, Request
# RedirectResponse — перенаправление браузера на другой адрес (использую после сохранения заявки).
# HTMLResponse — ответ в формате HTML. Без неё FastAPI отдал бы строку как обычный текст,
# и браузер показал бы код страницы вместо самой страницы.
from fastapi.responses import RedirectResponse, HTMLResponse
# uvicorn — сервер, который на самом деле «включает» моё приложение и слушает порт.
import uvicorn
# aiosqlite — асинхронная работа с базой SQLite. Обычный sqlite3 с async/await не совместим.
import aiosqlite

# Создаю приложение. Пока файл запускается, этот объект живёт в памяти,
# и все декораторы @app... ниже «вешают» мои функции именно на него.
app = FastAPI(
    title="MVP: Заявки на выезд мастера",
    description="Простой сервис для приёма и отслеживания заявок.",
    version="1.0.0"
)

# Имя файла базы данных. SQLite хранит всю базу в одном файле рядом с кодом.
# Если его нет — он создастся сам при первом запуске.
DB_NAME = "requests.db"


async def init_db():
    # Эта функция запускается один раз при старте сервера.
    # Задача — убедиться, что таблица requests существует, и создать её, если её нет.
    # Так я страхуюсь: могу удалить файл базы или прийти на новый компьютер,
    # и при запуске всё создастся заново без ошибок.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        create_table_query = """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'Новая'
            )
        """
        # CREATE TABLE IF NOT EXISTS — создай таблицу, только если её ещё нет.
        # NOT NULL — значит поле обязательно: база не даст сохранить пустую строку.
        # DEFAULT 'Новая' — если я не укажу статус, он сам станет «Новая».
        # Внутри SQL-строки никаких комментариев # писать нельзя: SQL не понимает решётку.
        await cursor.execute(create_table_query)
        # commit — «сохранить» изменения. Без него таблица не зафиксируется.
        await db.commit()
        print("✅ База данных инициализирована.")


async def get_all_requests():
    # Достаю все заявки из базы и возвращаю списком словарей.
    # Словари удобны тем, что дальше я пишу req['name'], а не req[1] — по имени всегда ясно, что беру.
    async with aiosqlite.connect(DB_NAME) as db:
        # row_factory = aiosqlite.Row — включая доступ к колонкам по имени.
        # Без этой строки каждая строка из базы приходит как кортеж: row[0], row[1] — легко запутаться.
        db.row_factory = aiosqlite.Row
        # ORDER BY id DESC — новые заявки сверху: самый большой id первым.
        cursor = await db.execute("SELECT * FROM requests ORDER BY id DESC")
        rows = await cursor.fetchall()
        # fetchall() забирает все строки сразу; дальше просто превращаю их в обычные словари.
        return [dict(row) for row in rows]


async def create_new_request(name, phone, description):
    # Сохраняю новую заявку в базу. Вызывается из обработчика формы /create.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        insert_query = "INSERT INTO requests (name, phone, description, status) VALUES (?, ?, ?, ?)"
        # Знаки вопроса — плейсхолдеры: данные передаются отдельно от запроса.
        # Это защита от SQL-инъекций: если пользователь впишет в поле кавычки или хитрый текст,
        # база воспримет его как обычную строку, а не как часть SQL-команды.
        # Статус пишу сразу «Новая» — это стартовое состояние любой заявки.
        await cursor.execute(insert_query, (name, phone, description, "Новая"))
        await db.commit()


async def update_request_status(request_id, new_status):
    # Меняю статус одной заявки по её id: например, «Новая» становится «В работе».
    # WHERE id = ? — важно: обновляю только нужную строку, а не всю таблицу.
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.cursor()
        update_query = "UPDATE requests SET status = ? WHERE id = ?"
        await cursor.execute(update_query, (new_status, request_id))
        await db.commit()


# Теперь про строки с @. Они называются декораторами.
# @app.get("/") читается так: «функцию ниже запускай, когда придёт GET-запрос на такой адрес».
# GET — это когда браузер просто открывает страницу. POST — когда что-то отправляет (например, форму).
# @app — это моё приложение из строки app = FastAPI(...), на него и вешаются маршруты.
# Без декоратора FastAPI не знает про функцию: код лежит в файле, но ни на какой адрес не привязан.


@app.get("/")
async def read_root():
    # Главная страница: отдаю HTML-файл с формой заявки.
    # Читаю файл с шаблоном и оборачиваю в HTMLResponse — именно это превращает
    # «строку с кодом» в настоящую страницу, которую браузер рисует.
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/create")
async def handle_create(request: Request):
    # Обрабатываю отправку формы. Когда пользователь жмёт «Отправить»,
    # браузер делает POST-запрос на /create и несёт в нём данные полей.
    # await request.form() — достаю данные формы; обращаюсь к ним по именам полей:
    # form_data["name"], form_data["phone"], form_data["description"].
    # Имена должны совпадать с name="..." в HTML, иначе будет KeyError.
    form_data = await request.form()
    await create_new_request(
        name=form_data["name"],
        phone=form_data["phone"],
        description=form_data["description"]
    )
    # После сохранения делаю редирект на /list. Код 303 означает «данные приняты, смотри на другой адрес».
    # Редирект нужен не для красоты: без него обновление страницы (F5) отправило бы форму второй раз
    # и появились бы заявки-дубли. А так браузер делает свежий GET на /list, и F5 безопасен.
    return RedirectResponse(url="/list", status_code=303)


@app.get("/list")
async def show_list():
    # Страница со списком всех заявок.
    # Схема простая: беру данные из базы, беру шаблон, в цикле собираю строки таблицы,
    # вставляю их в шаблон вместо метки <!-- REPEAT --> и отдаю готовый HTML.
    requests = await get_all_requests()

    with open("templates/list.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # rows_html — сюда я накапливаю HTML всех строк таблицы, по одной на заявку.
    rows_html = ""
    for req in requests:
        # f-строка позволяет вставлять значения прямо в текст.
        # Каждый req становится одной строкой <tr>...</tr> с ячейками <td>.
        # Кнопки — обычные ссылки на /set_status с параметрами id и status в адресе.
        rows_html += f"""
            <tr>
                <td>{req['id']}</td>
                <td>{req['name']}</td>
                <td>{req['phone']}</td>
                <td>{req['description']}</td>
                <td>{req['status']}</td>
                <td>
                    <a href="/set_status?id={req['id']}&status=В работе"><button>В работу</button></a>
                    <a href="/set_status?id={req['id']}&status=Готово"><button>Готово</button></a>
                </td>
            </tr>
        """

    # В шаблоне list.html стоит метка <!-- REPEAT --> — место, куда вставляются строки.
    # replace находит её один раз и подменяет на всё, что я собрал в цикле.
    # Если заявок нет, на месте метки останется пусто — таблица будет просто с шапкой.
    final_html = html_content.replace("<!-- REPEAT -->", rows_html)
    return HTMLResponse(content=final_html)


@app.get("/set_status")
async def set_status(request: Request):
    # Смена статуса. Кнопка в таблице ведёт на адрес вида /set_status?id=5&status=Готово.
    # Всё, что после ?, называется query-параметрами — я их отсюда и достаю.
    query_params = request.query_params
    # .get("id", 0) — если параметра нет, вернётся 0, и код не упадёт.
    req_id = int(query_params.get("id", 0))
    new_status = query_params.get("status", "")

    # Меняю базу только если id выглядит нормально и статус реально передан.
    # Если кто-то вобьёт адрес вручную без параметров — просто вернусь на список без ошибки.
    if req_id > 0 and new_status:
        await update_request_status(req_id, new_status)

    return RedirectResponse(url="/list", status_code=303)


# Блок запуска. Строка if __name__ == "__main__" означает: этот код выполняется,
# только если файл запустили напрямую командой python web_service.py.
# Если файл кто-то импортирует в другой скрипт — сервер сам не стартует и база не тронется.
if __name__ == "__main__":
    import asyncio
    # asyncio.run() — способ вызвать асинхронную функцию из обычного кода.
    # Сначала один раз готовлю базу, потом поднимаю сервер.
    asyncio.run(init_db())
    print("🚀 Сервер запускается на http://127.0.0.1:8000")
    # host="0.0.0.0" — слушать все сетевые интерфейсы: сайт доступен и с localhost,
    # и с другого устройства в той же сети (например, с телефона).
    # port=8000 — порт, на котором висит сайт.
    uvicorn.run(app, host="0.0.0.0", port=8000)
