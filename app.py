import smtplib

from flask import Flask, jsonify, request, send_from_directory

import Email
from cdvToText import buildTextFromLines, formatRow, processCsv

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB upload limit

MAX_LINES = 500
MAX_LINE_LENGTH = 200


@app.get("/")
def index():
    return send_from_directory("public", "index.html")


@app.post("/upload")
def upload():
    """Read the CSV and return the sorted lines. Nothing is emailed yet."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="No file was uploaded."), 400
    if not file.filename.lower().endswith(".csv"):
        return jsonify(error="That isn't a .csv file."), 400

    try:
        text = file.read().decode("utf-8-sig")  # also handles Excel's BOM
    except UnicodeDecodeError:
        return jsonify(error="Couldn't read the file. Save it as UTF-8 CSV."), 400

    try:
        vans, trucks = processCsv(text)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    return jsonify(
        vans=[formatRow(r) for r in vans],
        trucks=[formatRow(r) for r in trucks],
    )


def clean_lines(value):
    """Accept only a list of short strings."""
    if not isinstance(value, list) or len(value) > MAX_LINES:
        return None
    if not all(isinstance(x, str) and len(x) <= MAX_LINE_LENGTH for x in value):
        return None
    return [x.strip() for x in value if x.strip()]


@app.post("/send")
def send():
    """Email whatever is left after the user removed people in the page."""
    data = request.get_json(silent=True) or {}
    vans = clean_lines(data.get("vans"))
    trucks = clean_lines(data.get("trucks"))
    if vans is None or trucks is None:
        return jsonify(error="Invalid data."), 400
    if not vans and not trucks:
        return jsonify(error="Nothing to send."), 400

    try:
        Email.sendEmail("Route summary", buildTextFromLines(vans, trucks))
    except smtplib.SMTPAuthenticationError:
        return jsonify(error="Gmail rejected the login. Check your app password."), 500
    except Exception as e:
        return jsonify(error=f"Couldn't send the email: {e}"), 500

    return jsonify(emailed_to=Email.sendToAdress)


if __name__ == "__main__":
    app.run(debug=True)