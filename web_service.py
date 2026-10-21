from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import aiosqlite
import os

DB_PATH = "requests.db"
app = FastAPI()

async def init_db():
    """Создаёт таблицу, если её нет. Вызывается при старте."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                problem TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Заявка на выезд мастера</title></head>
    <body>
      <h1>Заявка на выезд мастера</h1>
      <form action="/submit" method="post">
        <label>Ваше имя: <input name="name" required></label><br><br>
        <label>Телефон: <input name="phone" required></label><br><br>
        <label>Проблема: <textarea name="problem" required></textarea></label><br><br>
        <button type="submit">Отправить заявку</button>
      </form>
      <p><a href="/list">Список всех заявок</a></p>
    </body>
    </html>
    """
    return html

@app.post("/submit")
async def submit(name: str = Form(...), phone: str = Form(...), problem: str = Form(...)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (name, phone, problem) VALUES (?, ?, ?)",
            (name, phone, problem),
        )
        await db.commit()
    # Редирект на список заявок
    return RedirectResponse(url="/list", status_code=303)

@app.get("/list", response_class=HTMLResponse)
async def list_requests():
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute("SELECT * FROM requests ORDER BY created_at DESC")
        data = await rows.fetchall()
        # Важно: приводим имена колонок к нижнему регистру, чтобы item["id"] работал
        columns = [desc[0].lower() for desc in rows.description]
        items = [dict(zip(columns, row)) for row in data]

    rows_html = ""
    for item in items:
        # Формы используют method="post", так как браузеры не умеют делать PUT через форму
        rows_html += f"""
        <tr>
          <td>{item["id"]}</td>
          <td>{item["name"]}</td>
          <td>{item["phone"]}</td>
          <td>{item["problem"]}</td>
          <td>{item["status"]}</td>
          <td>{item["created_at"]}</td>
          <td>
            <!-- Кнопка "В работе" -->
            <form action="/status/{item["id"]}" method="post" style="display:inline;">
              <input type="hidden" name="status" value="in_progress">
              <button type="submit" style="background:#ffca28;border:none;padding:4px 8px;cursor:pointer;">В работе</button>
            </form>
            <!-- Кнопка "Готово" -->
            <form action="/status/{item["id"]}" method="post" style="display:inline; margin-left:5px;">
              <input type="hidden" name="status" value="done">
              <button type="submit" style="background:#4caf50;color:white;border:none;padding:4px 8px;cursor:pointer;">Готово</button>
            </form>
          </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Список заявок</title></head>
    <body>
      <h1>Заявки</h1>
      <table border="1" cellpadding="8" style="border-collapse:collapse; width:100%;">
        <thead>
          <tr style="background:#f5f5f5;">
            <th>ID</th><th>Имя</th><th>Телефон</th><th>Проблема</th>
            <th>Статус</th><th>Дата</th><th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
      <p><a href="/">Подать новую заявку</a></p>
    </body>
    </html>
    """
    return html

# Эндпоинт для обновления статуса. Принимает POST, как и форма.
@app.post("/status/{req_id}")
async def update_status(req_id: int, status: str = Form(...)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE requests SET status = ? WHERE id = ?",
            (status, req_id),
        )
        await db.commit()
    # После обновления сразу возвращаем пользователя на список
    return RedirectResponse(url="/list", status_code=303)
