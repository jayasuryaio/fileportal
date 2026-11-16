"""Dashboard, upload, download and file-listing routes."""
import io
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pymysql
from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, send_file, url_for)

from . import db
from .security import login_required
from .validators import ValidationError, detect_upload_type, safe_name_part

bp = Blueprint("files", __name__)

EXT_FOR_TYPE = {"PDF": "pdf", "PNG": "png", "JPEG": "jpg"}


def _tz():
    try:
        return ZoneInfo(current_app.config["APP_TIMEZONE"])
    except Exception:  # unknown tz name -> fall back to UTC
        return timezone.utc


@bp.app_template_filter("localtime")
def localtime(value):
    """Format a naive-UTC datetime as e.g. '16 Nov 2026, 11:24 AM'."""
    if not value:
        return ""
    return value.replace(tzinfo=timezone.utc).astimezone(_tz()).strftime("%d %b %Y, %I:%M %p")


def _user_files(limit=None):
    sql = ("SELECT id, slot, original_filename, stored_filename, file_type, file_size, "
           "uploaded_at FROM uploaded_files WHERE user_id = %s ORDER BY uploaded_at DESC, id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.query_all(sql, (g.user["id"],))


@bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", files=_user_files(), page="dashboard")


@bp.route("/my-files")
@login_required
def my_files():
    return render_template("my_files.html", files=_user_files(), page="files")


@bp.route("/upload/<int:slot>", methods=["POST"])
@login_required
def upload(slot):
    if slot not in (1, 2):
        abort(404)
    upload_file = request.files.get(f"file{slot}")
    try:
        if upload_file is None or not upload_file.filename:
            raise ValidationError("Please choose a file first.")
        head = upload_file.stream.read(16)
        upload_file.stream.seek(0)
        file_type = detect_upload_type(upload_file.filename, head)

        max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
        data = upload_file.stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValidationError(f"File is too large (max {current_app.config['MAX_UPLOAD_MB']} MB).")
        if not data:
            raise ValidationError("The file is empty.")

        # <UserName>_file<slot>_<timestamp>_<random>.<ext>  -> unique and includes user's name
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        stored = (f"{safe_name_part(g.user['name'])}_file{slot}_{stamp}_"
                  f"{secrets.token_hex(3)}.{EXT_FOR_TYPE[file_type]}")
        upload_dir = current_app.config["UPLOAD_DIR"]
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / stored
        path.write_bytes(data)
        try:
            db.execute(
                "INSERT INTO uploaded_files (user_id, slot, original_filename, stored_filename, "
                "file_type, file_size) VALUES (%s, %s, %s, %s, %s, %s)",
                (g.user["id"], slot, upload_file.filename[:255], stored, file_type, len(data)))
        except pymysql.MySQLError:
            path.unlink(missing_ok=True)  # keep disk and DB consistent
            raise
        flash(f"File {slot} uploaded as {stored}.", "success")
    except ValidationError as err:
        flash(str(err), "error")
    except pymysql.MySQLError:
        flash("Database error while saving the file. Please try again.", "error")
    except OSError:
        flash("Server could not store the file. Please try again.", "error")
    return redirect(url_for("files.dashboard"))


def _owned_file(file_id):
    row = db.query_one(
        "SELECT * FROM uploaded_files WHERE id = %s AND user_id = %s", (file_id, g.user["id"]))
    if row is None:
        abort(404)
    return row


@bp.route("/files/<int:file_id>/download")
@login_required
def download_file(file_id):
    row = _owned_file(file_id)
    path = current_app.config["UPLOAD_DIR"] / row["stored_filename"]
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["stored_filename"])


@bp.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def delete_file(file_id):
    row = _owned_file(file_id)
    (current_app.config["UPLOAD_DIR"] / row["stored_filename"]).unlink(missing_ok=True)
    db.execute("DELETE FROM uploaded_files WHERE id = %s", (row["id"],))
    flash("File deleted.", "success")
    target = "files.my_files" if request.form.get("return_to") == "files" else "files.dashboard"
    return redirect(url_for(target))


def _build_test_pdf(user_name: str) -> bytes:
    """Generate a tiny but valid one-page PDF (no third-party library needed)."""
    text = f"FilePortal test file - generated for {user_name}"
    text = text.replace("\\", "").replace("(", "").replace(")", "")
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1", "replace")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@bp.route("/download/test-file")
@login_required
def download_test_file():
    pdf = _build_test_pdf(g.user["name"])
    return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                     as_attachment=True, download_name="FilePortal_test_file.pdf")
