"""End-to-end tests against a real MySQL database (fileportal_test).

Run:  pytest -q      (needs MySQL; see README)
"""
import io
import re
import struct
import zlib

import pytest

from app import create_app

PNG = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
       + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0) + b"\x00" * 4)
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture()
def app(tmp_path):
    import os
    from app.config import Config
    test_db = {**Config.DB, "database": os.getenv("TEST_DB_NAME", "fileportal_test")}
    cfg = {"TESTING": True, "DB": test_db, "UPLOAD_DIR": tmp_path / "uploads", "SESSION_COOKIE_SECURE": False,
           "MAX_UPLOAD_MB": 1, "MAX_CONTENT_LENGTH": 2 * 1024 * 1024}
    app = create_app(cfg)
    from app import db
    conn = db._connect(app.config["DB"])
    with conn.cursor() as cur:
        cur.execute("DELETE FROM uploaded_files"); cur.execute("DELETE FROM users")
    conn.close()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def token(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def user_form(**over):
    d = {"name": "Jayasurya", "age": "25", "address": "12 Main Street, Chennai",
         "email": "jaya@example.com", "mobile": "+919876543210", "password": "Secret123"}
    d.update(over)
    return d


def signup(client, **over):
    return client.post("/signup", data={**user_form(**over), "csrf_token": token(client, "/signup")})


def login(client, email="jaya@example.com", password="Secret123"):
    return client.post("/login", data={"email": email, "password": password,
                                       "csrf_token": token(client, "/login")})


def upload(client, slot, name, data):
    t = token(client, "/dashboard")
    return client.post(f"/upload/{slot}", data={"csrf_token": t, f"file{slot}": (io.BytesIO(data), name)},
                       content_type="multipart/form-data", follow_redirects=True)


def test_signup_redirects_to_login_and_hashes_password(client, app):
    r = signup(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    from app import db
    with app.app_context():
        row = db.query_one("SELECT * FROM users WHERE email=%s", ("jaya@example.com",))
    assert row["name"] == "Jayasurya" and row["age"] == 25
    assert row["password_hash"] != "Secret123" and row["password_hash"].startswith(("scrypt:", "pbkdf2:"))


@pytest.mark.parametrize("field,value", [
    ("name", "1234"), ("age", "abc"), ("age", "0"), ("age", "200"), ("address", "x"),
    ("email", "not-an-email"), ("mobile", "12"), ("password", "short1"), ("password", "allletters"),
])
def test_signup_validation_errors(client, field, value):
    r = signup(client, **{field: value})
    assert r.status_code == 200 and "field-error" in r.get_data(as_text=True)


def test_duplicate_email_rejected(client):
    signup(client)
    r = signup(client)
    assert r.status_code == 200 and "already exists" in r.get_data(as_text=True)


def test_sql_injection_attempt_is_harmless(client):
    signup(client)
    r = login(client, email="' OR 1=1 --", password="x")
    assert r.status_code == 200 and "Invalid email or password" in r.get_data(as_text=True)


def test_login_flow(client):
    signup(client)
    bad = login(client, password="wrongpass1")
    assert bad.status_code == 200 and "Invalid email or password" in bad.get_data(as_text=True)
    ok = login(client)
    assert ok.status_code == 302 and ok.headers["Location"].endswith("/dashboard")
    assert "Dashboard" in client.get("/dashboard").get_data(as_text=True)


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_csrf_enforced(client):
    r = client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert r.status_code == 400


def test_upload_valid_types_and_naming(client, app):
    signup(client); login(client)
    for slot, name, data, kind in [(1, "pic.png", PNG, "PNG"), (2, "doc.pdf", PDF, "PDF")]:
        r = upload(client, slot, name, data)
        assert "uploaded as Jayasurya_file%d_" % slot in r.get_data(as_text=True)
    r = upload(client, 1, "photo.JPG", JPG)
    assert "JPEG" in r.get_data(as_text=True)
    from app import db
    with app.app_context():
        rows = db.query_all("SELECT * FROM uploaded_files ORDER BY id")
    assert [x["file_type"] for x in rows] == ["PNG", "PDF", "JPEG"]
    assert all("Jayasurya" in x["stored_filename"] for x in rows)
    assert all((app.config["UPLOAD_DIR"] / x["stored_filename"]).is_file() for x in rows)
    assert all(x["uploaded_at"] and x["user_id"] for x in rows)


@pytest.mark.parametrize("name,data,msg", [
    ("notes.txt", b"hello", "Only PDF, PNG or JPEG"),
    ("evil.exe", b"MZ....", "Only PDF, PNG or JPEG"),
    ("fake.png", b"this is not a png", "not a valid PNG"),
    ("fake.pdf", PNG, "not a valid PDF"),
    ("empty.pdf", b"", "not a valid PDF"),
])
def test_upload_rejects_bad_files(client, app, name, data, msg):
    signup(client); login(client)
    r = upload(client, 1, name, data)
    assert msg.lower() in r.get_data(as_text=True).lower()
    from app import db
    with app.app_context():
        assert db.query_one("SELECT COUNT(*) c FROM uploaded_files")["c"] == 0


def test_upload_too_large(client):
    signup(client); login(client)
    r = upload(client, 1, "big.pdf", PDF + b"0" * (1024 * 1024 + 10))
    assert "too large" in r.get_data(as_text=True).lower()


def test_download_and_isolation_between_users(client, app):
    signup(client); login(client)
    upload(client, 1, "pic.png", PNG)
    from app import db
    with app.app_context():
        fid = db.query_one("SELECT id FROM uploaded_files")["id"]
    ok = client.get(f"/files/{fid}/download")
    assert ok.status_code == 200 and ok.data == PNG
    assert "attachment" in ok.headers["Content-Disposition"]

    other = app.test_client()
    signup(other, name="Bob", email="bob@example.com"); login(other, email="bob@example.com")
    assert other.get(f"/files/{fid}/download").status_code == 404
    t = token(other, "/dashboard")
    assert other.post(f"/files/{fid}/delete", data={"csrf_token": t}).status_code == 404


def test_delete_file(client, app):
    signup(client); login(client)
    upload(client, 2, "doc.pdf", PDF)
    from app import db
    with app.app_context():
        row = db.query_one("SELECT * FROM uploaded_files")
    r = client.post(f"/files/{row['id']}/delete", data={"csrf_token": token(client, "/dashboard")})
    assert r.status_code == 302
    assert not (app.config["UPLOAD_DIR"] / row["stored_filename"]).exists()


def test_test_file_download_is_valid_pdf(client):
    signup(client); login(client)
    r = client.get("/download/test-file")
    assert r.status_code == 200 and r.data.startswith(b"%PDF-") and b"Jayasurya" in r.data
    assert "attachment" in r.headers["Content-Disposition"]


def test_my_files_page_and_logout(client):
    signup(client); login(client)
    upload(client, 1, "pic.png", PNG)
    assert "Jayasurya_file1_" in client.get("/my-files").get_data(as_text=True)
    client.post("/logout", data={"csrf_token": token(client, "/dashboard")})
    assert client.get("/dashboard").status_code == 302


def test_404_page(client):
    assert client.get("/nope").status_code == 404
