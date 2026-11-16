# FilePortal

A small full-stack web app: **sign up → log in → upload / download files**.

| Layer     | Technology                                               |
|-----------|----------------------------------------------------------|
| Backend   | Python 3.12+ · Flask · PyMySQL · Gunicorn                |
| Database  | MySQL 8 (InnoDB, utf8mb4)                                |
| Frontend  | Server-rendered Jinja templates + plain CSS/JS           |
| Hosting   | Railway (app + MySQL plugin + persistent volume)         |

- **Live app:** https://fileportal-production.up.railway.app
- **Repository:** https://github.com/jayasuryaio/fileportal

---

## Features (mapped to the assessment)

| Requirement | Implementation |
|---|---|
| Sign-up with Name, Age, Address, Email, Mobile, Password → stored in MySQL → redirect to login | `app/auth.py` `signup()` |
| Login validated against MySQL → redirect to dashboard | `app/auth.py` `login()` |
| Two upload fields (PDF / PNG / JPEG only) | `app/files.py` `upload()` — "Upload File 1" and "Upload File 2" |
| Files stored in a server directory, filename includes the user's name | `UPLOAD_DIR`, e.g. `Jayasurya_file1_20261116062252_6191f2.png` |
| Metadata in MySQL (filename, type, timestamp, user) | table `uploaded_files` |
| Test file download | `GET /download/test-file` (a generated PDF) |
| Error handling, hashing, validation | see [Security](#security) |

Extras: "My Files" page, per-file Download / Delete menu, logout, drag-and-drop, responsive layout, `/health` endpoint, 27 automated tests.

---

## Project structure

```
fileportal/
├── app/
│   ├── __init__.py      # app factory, error pages, security headers
│   ├── config.py        # env-based settings (works locally + Railway)
│   ├── db.py            # PyMySQL helpers, auto schema init
│   ├── security.py      # CSRF, login_required, current-user loader
│   ├── validators.py    # sign-up validation, upload type/magic-byte checks
│   ├── auth.py          # /signup /login /logout
│   ├── files.py         # /dashboard /my-files /upload /download ...
│   ├── templates/       # Jinja pages (signup, login, dashboard, my_files, error)
│   └── static/          # css/style.css, js/app.js
├── tests/test_app.py    # end-to-end tests (real MySQL)
├── schema.sql           # database schema
├── wsgi.py              # gunicorn entry point
├── railway.json  Procfile  .python-version
├── requirements.txt  requirements-dev.txt  .env.example
```

---

## Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET/POST | `/signup` | – | Create account, then redirect to `/login` |
| GET/POST | `/login` | – | Log in, then redirect to `/dashboard` |
| POST | `/logout` | ✔ | End session |
| GET | `/dashboard` | ✔ | Upload cards, test-file button, recent uploads |
| GET | `/my-files` | ✔ | All uploaded files |
| POST | `/upload/<1\|2>` | ✔ | Upload to slot 1 or 2 |
| GET | `/files/<id>/download` | ✔ owner | Download one of your files |
| POST | `/files/<id>/delete` | ✔ owner | Delete one of your files |
| GET | `/download/test-file` | ✔ | Download the generated test PDF |
| GET | `/health` | – | Health check (used by Railway) |

---

## Database

Schema: [`schema.sql`](schema.sql). The app runs it automatically at startup (it uses `CREATE TABLE IF NOT EXISTS`, so it is safe to repeat).

```
users                              uploaded_files
-----                              --------------
id (PK)                            id (PK)
name, age, address                 user_id  (FK → users.id, ON DELETE CASCADE)
email (UNIQUE)                     slot (1 or 2)
mobile                             original_filename   (name on user's computer)
password_hash  (never plain text)  stored_filename     (name on server, includes user's name)
created_at                         file_type (PDF/PNG/JPEG), file_size
                                   uploaded_at
```

Timestamps are stored in **UTC** (the connection sets `time_zone='+00:00'`) and displayed in `APP_TIMEZONE` (default `Asia/Kolkata`).

### Manual DB setup (optional)

```sql
CREATE DATABASE fileportal CHARACTER SET utf8mb4;
CREATE USER 'fileportal'@'%' IDENTIFIED BY 'fileportal';
GRANT ALL ON fileportal.* TO 'fileportal'@'%';
```
then `mysql -u fileportal -p fileportal < schema.sql` (or just start the app).

---

## Local setup

**Prerequisites:** Python 3.12+ and a MySQL 8 server (`brew install mysql@8.4`, Docker, or any instance).

```bash
git clone https://github.com/jayasuryaio/fileportal && cd fileportal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit values (SECRET_KEY, DB_*)
# create the database/user (see "Manual DB setup" above)

python wsgi.py                # http://localhost:5000
```

Quick MySQL with Docker:

```bash
docker run -d --name fp-mysql -p 3306:3306 \
  -e MYSQL_DATABASE=fileportal -e MYSQL_USER=fileportal \
  -e MYSQL_PASSWORD=fileportal -e MYSQL_ROOT_PASSWORD=root mysql:8.4
```

### Run the tests

```bash
pip install -r requirements-dev.txt
# needs a second database for tests:
mysql -uroot -e "CREATE DATABASE fileportal_test; GRANT ALL ON fileportal_test.* TO 'fileportal'@'%';"
pytest -q          # 27 tests
```
The tests wipe the tables in `fileportal_test` only (override with `TEST_DB_NAME`).

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | dev key | **Required in production.** Signs session cookies. |
| `DATABASE_URL` / `MYSQL_URL` | – | `mysql://user:pass@host:port/db` (takes priority) |
| `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` | localhost / 3306 / root / – / fileportal | Individual DB settings (Railway's `MYSQLHOST` etc. also work) |
| `UPLOAD_DIR` | `./uploads` | Server directory for uploaded files |
| `MAX_UPLOAD_MB` | `5` | Max size per file |
| `APP_TIMEZONE` | `Asia/Kolkata` | Display timezone |
| `FLASK_ENV` | production | Set `development` locally (allows non-HTTPS cookies) |

---

## Hosting (Railway)

**Platform:** [Railway](https://railway.com) — one project with three pieces:

1. **App service** – built from this repo (Railpack detects Python; `railway.json` sets the start command + health check).
2. **MySQL service** – Railway's MySQL database.
3. **Volume** – mounted at `/data` on the app service so uploads survive redeploys.

App service variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{MySQL.MYSQL_URL}}` (reference to the MySQL service) |
| `SECRET_KEY` | long random string |
| `UPLOAD_DIR` | `/data/uploads` |

Deploy with the CLI:

```bash
npm i -g @railway/cli      # or: brew install railway
railway login
railway init               # create project
railway add --database mysql
railway add --service fileportal
railway volume add --mount-path /data      # on the app service
railway variables --set 'DATABASE_URL=${{MySQL.MYSQL_URL}}' \
  --set "SECRET_KEY=$(openssl rand -hex 32)" --set UPLOAD_DIR=/data/uploads
railway up
railway domain             # public URL
```
Or connect the GitHub repo in the Railway dashboard so every push redeploys.

---

## Security

- **Passwords** hashed with Werkzeug (`scrypt`, salted); never stored or logged in plain text.
- **SQL injection:** every query is parameterised.
- **Input validation** (server-side, mirrored client-side): name, age 1–120, address length, email format, mobile (7–15 digits), password ≥ 8 chars with letters and numbers; unique email.
- **Uploads:** extension allow-list (`pdf/png/jpg/jpeg`) **and** file-signature (magic bytes) check, size limit, empty-file check, server-generated filenames (user-supplied names are never used on disk → no path traversal), files only downloadable by their owner.
- **CSRF** token on every POST; **session** cookie is `HttpOnly`, `SameSite=Lax`, `Secure` in production; session reset on login.
- Login errors are generic ("Invalid email or password") and timing-equalised to avoid user enumeration.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
- Friendly error pages for 400 / 404 / 413 / 500.

## Assumptions

- "Filename includes the user's name" → stored as `<Name>_file<slot>_<UTC timestamp>_<random>.<ext>`; the original name is kept in the DB.
- Each upload creates a new record (history is kept); users can delete files.
- Email is the login identifier and must be unique.
- Age is a whole number (1–120); mobile accepts an optional leading `+`.
- Test file = a small PDF generated on the fly, personalised with the user's name (so it can be re-uploaded).
- Max 5 MB per file.
- Uploaded files live on the server's disk (Railway volume), as the assessment requires, not in cloud object storage.
