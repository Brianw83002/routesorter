import smtplib

from flask import Flask, jsonify, request, send_from_directory

import Email
from Email import EMAIL_RE
from cdvToText import (
    DCX2_REQUIRED,
    HLX1_REQUIRED,
    HLX1_SECTIONS,
    ROUTE_REQUIRED,
    formatDcx2Rows,
    formatHlx1Rows,
    formatRouteRows,
    hlx1RowsToGroups,
    readCsvRows,
    readXlsxRows,
    routeRowsToGroups,
)

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB upload limit

MAX_LINES = 500
MAX_LINE_LENGTH = 200
MAX_GROUPS = 10

# Which columns each format needs, keyed by the id the page sends.
FORMAT_COLUMNS = {
    "route": ROUTE_REQUIRED,
    "dcx2": DCX2_REQUIRED,
    "hlx1": HLX1_REQUIRED,
}


@app.get("/")
def index():
    return send_from_directory("public", "index.html")


def _readRows(file, required, formatLabel):
    name = file.filename.lower()
    if name.endswith(".csv"):
        try:
            text = file.read().decode("utf-8-sig")  # also handles Excel's BOM
        except UnicodeDecodeError:
            raise ValueError("Couldn't read the file. Save it as UTF-8 CSV.")
        return readCsvRows(text, required, formatLabel)
    elif name.endswith(".xlsx"):
        return readXlsxRows(file.stream, required, formatLabel)
    else:
        raise ValueError("That isn't a .csv or .xlsx file.")


@app.post("/upload")
def upload():
    """Read the file and return the sorted groups. Nothing is emailed yet."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="No file was uploaded."), 400

    fmt = request.form.get("format", "route")
    if fmt not in FORMAT_COLUMNS:
        return jsonify(error="Unknown format."), 400

    try:
        rows = _readRows(file, FORMAT_COLUMNS[fmt], fmt.upper())
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        return jsonify(error="Couldn't read that file."), 400

    if fmt == "dcx2":
        groups = [{"key": "vans", "label": "DCX2", "lines": formatDcx2Rows(rows)}]
    elif fmt == "hlx1":
        byLabel = hlx1RowsToGroups(rows)
        groups = [
            {"key": label.lower(), "label": label, "lines": formatHlx1Rows(byLabel[label])}
            for label in HLX1_SECTIONS
        ]
    else:
        vans, trucks = routeRowsToGroups(rows)
        groups = [
            {"key": "vans", "label": "Vans", "lines": formatRouteRows(vans)},
            {"key": "trucks", "label": "Truck", "lines": formatRouteRows(trucks)},
        ]

    return jsonify(format=fmt, groups=groups)


def clean_groups(value):
    """Accept only a list of {label, lines} groups with short string lines."""
    if not isinstance(value, list) or len(value) > MAX_GROUPS:
        return None
    cleaned = []
    for g in value:
        if not isinstance(g, dict):
            return None
        label = g.get("label")
        lines = g.get("lines")
        if not isinstance(label, str) or not label.strip():
            return None
        if not isinstance(lines, list) or len(lines) > MAX_LINES:
            return None
        if not all(isinstance(x, str) and len(x) <= MAX_LINE_LENGTH for x in lines):
            return None
        cleaned.append((label.strip(), [x.strip() for x in lines if x.strip()]))
    return cleaned


@app.post("/send")
def send():
    """Email whatever is left after the user removed people in the page."""
    data = request.get_json(silent=True) or {}
    groups = clean_groups(data.get("groups"))
    if groups is None:
        return jsonify(error="Invalid data."), 400
    if not any(lines for _, lines in groups):
        return jsonify(error="Nothing to send."), 400

    toAddress = (data.get("to") or "").strip()
    if not EMAIL_RE.match(toAddress):
        return jsonify(error="Enter a valid email address."), 400

    body = "\n\n".join("\n".join([label] + lines) for label, lines in groups)

    try:
        Email.sendEmail("Route summary", body, toAddress)
    except smtplib.SMTPAuthenticationError:
        return jsonify(error="Gmail rejected the login. Check your app password."), 500
    except Exception as e:
        return jsonify(error=f"Couldn't send the email: {e}"), 500

    return jsonify(emailed_to=toAddress)


if __name__ == "__main__":
    app.run(debug=True)