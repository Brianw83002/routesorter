import smtplib

from flask import Flask, jsonify, request, send_file

import Email
from cdvToText import buildText, formatRow, processCsv

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB upload limit


@app.get("/")
def index():
    return send_file("index.html")


@app.post("/upload")
def upload():
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

    try:
        Email.sendEmail("Route summary", buildText(vans, trucks))
    except smtplib.SMTPAuthenticationError:
        return jsonify(error="Gmail rejected the login. Check your app password."), 500
    except Exception as e:
        return jsonify(error=f"Couldn't send the email: {e}"), 500

    return jsonify(
        vans=[formatRow(r) for r in vans],
        trucks=[formatRow(r) for r in trucks],
        emailed_to=Email.sendToAdress,
    )


if __name__ == "__main__":
    app.run(debug=True)
