import csv
import io
import re

# --- Route sorter format (Vans/Truck split by CP/XL in Route Code) ---

ROUTE_REQUIRED = ["Name", "Route Code", "Stops Left", "Stops per hour"]


def routeRowsToGroups(rows):
    """Split rows into vans (CP) and trucks (XL)."""
    vans = []
    trucks = []
    for row in rows:
        code = (row.get("Route Code") or "").upper()
        if "CP" in code:
            vans.append(row)
        elif "XL" in code:
            trucks.append(row)
    return vans, trucks


def formatRouteRow(r):
    return f'{r["Name"]} Stops: {r["Stops Left"]} | {r["Stops per hour"]} per/h'


def formatRouteRows(rows):
    """Format a whole group at once so the numbers line up in columns,
    and keep each line short enough to read comfortably in a text message."""
    if not rows:
        return []
    width = max(len(r["Name"]) for r in rows)
    lines = []
    for r in rows:
        name = r["Name"].ljust(width)
        stops = str(r["Stops Left"]).rjust(3)
        pace = str(r["Stops per hour"]).rjust(2)
        lines.append(f"{name} {stops} {pace}/h")
    return lines


def buildTextFromLines(vanLines, truckLines):
    lines = ["Vans"]
    lines += vanLines
    lines += ["", "Truck"]
    lines += truckLines
    return "\n".join(lines)


def buildText(vans, trucks):
    return buildTextFromLines(
        [formatRouteRow(r) for r in vans],
        [formatRouteRow(r) for r in trucks],
    )


# --- DCX2 format (route report export; Vans only, no Truck split) ---

DCX2_REQUIRED = ["Driver name", "not started stops", "cortex_avg_pace_stops_per_hour"]


# First names swapped for their common nickname before we take the last-name
# initial. Names not in this table are left as-is. Exact Title Case match.
NICKNAMES = {
    "Christopher": "Chris",
    "Alexander": "Alex",
    "Matthew": "Matt",
    "Benjamin": "Ben",
    "William": "Will",
    "Mac Kevin" : "Mac"
}


def shortDriverName(fullName):
    """'Israel,Ruiz' -> 'Israel R.'; 'Eliseo,Soria Rodriguez' -> 'Eliseo R.' (last word's initial)."""
    first, _, last = fullName.partition(",")
    first = NICKNAMES.get(first.strip(), first.strip())
    lastWords = last.split()
    initial = lastWords[-1][0].upper() if lastWords else ""
    return f"{first} {initial}." if initial else first


def formatDcx2Row(r):
    return (
        f'{shortDriverName(r["Driver name"])} Stops: {r["not started stops"]} '
        f'| {r["cortex_avg_pace_stops_per_hour"]} per/h'
    )


NAME_COLUMN_WIDTH = 15


def formatDcx2Rows(rows):
    """Format a whole group at once. The name column is a fixed 15 chars
    (truncated if longer) followed by a literal '|' -- padding alone doesn't
    line up in the proportional font iMessage uses, but a '|' still anchors
    visually no matter the font."""
    if not rows:
        return []
    lines = []
    for r in rows:
        name = shortDriverName(r["Driver name"])[:NAME_COLUMN_WIDTH].ljust(NAME_COLUMN_WIDTH)
        stops = str(r["not started stops"]).rjust(3)
        pace = str(r["cortex_avg_pace_stops_per_hour"]).rjust(2)
        lines.append(f"{name}| {stops}  {pace}/h")
    return lines


def buildDcx2Text(vanLines, header="Vans"):
    return "\n".join([header] + vanLines)


# --- HLX1 format (route report export; split into 5 sections by Delivery Service Type) ---

HLX1_REQUIRED = ["Driver name", "Delivery Service Type", "App sign in:", "not started stops", "cortex_avg_pace_stops_per_hour"]

# Display order for the 6 sections, and which "Delivery Service Type" value goes in each.
# Trucks are further split into waves below, based on "App sign in".
HLX1_SECTIONS = ["MA", "UB", "Trucks 1st wave", "Trucks 2nd wave", "Vans", "Backup"]

HLX1_SERVICE_TYPE_BY_SECTION = {
    "UB": "AMXL UDS Commingle",
    "MA": "AMXL MA UDS Commingle",
    "Vans": "AMXL Custom Delivery Van 14ft Single DA",
    "Backup": "DSP Initiated Work (Standard Vehicle)",
}

TRUCK_SERVICE_TYPE = {
    "AMXL Box Truck (Medium) w/ Helper",
    "AMXL Box Truck (Large) w/ Helper",
}
TRUCK_2ND_WAVE_CUTOFF_MINUTES = 8 * 60 + 30  # 8:30 AM

_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?")


def _signInMinutes(value):
    """Parse the 'App sign in' value into minutes since midnight, or None if
    it can't be parsed. Handles a bare time ('8:15', '08:15 AM') as well as
    a time with a date in front of it ('1/15/2025 8:15 AM')."""
    if not value:
        return None
    m = _TIME_RE.search(str(value))
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3)
    if ampm:
        ampm = ampm.upper()
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
    return hour * 60 + minute


def hlx1RowsToGroups(rows):
    """Split rows into MA / UB / Trucks 1st wave / Trucks 2nd wave / Vans /
    Backup by Delivery Service Type. Trucks with an "App sign in" at or after
    8:30 AM are 2nd wave; all other trucks (including ones where the sign-in
    time can't be read) are 1st wave. Rows with a Delivery Service Type that
    doesn't match any of the known values are dropped."""
    groups = {section: [] for section in HLX1_SECTIONS}
    sectionByType = {v: k for k, v in HLX1_SERVICE_TYPE_BY_SECTION.items()}
    for row in rows:
        serviceType = (row.get("Delivery Service Type") or "").strip()
        if serviceType in TRUCK_SERVICE_TYPE:
            minutes = _signInMinutes(row.get("App sign in:"))
            if minutes is not None and minutes >= TRUCK_2ND_WAVE_CUTOFF_MINUTES:
                groups["Trucks 2nd wave"].append(row)
            else:
                groups["Trucks 1st wave"].append(row)
        else:
            section = sectionByType.get(serviceType)
            if section:
                groups[section].append(row)
    return groups


# HLX1 rows carry the same three fields (Driver name, not started stops,
# cortex_avg_pace_stops_per_hour) as DCX2 rows, so the DCX2 formatter is reused.
formatHlx1Row = formatDcx2Row
formatHlx1Rows = formatDcx2Rows


# --- Shared CSV / XLSX readers ---

def _checkHeaders(fieldnames, required, formatLabel):
    if required is None:
        raise ValueError(f"The {formatLabel} format isn't set up yet.")
    fieldnames = [h.strip() if isinstance(h, str) else h for h in (fieldnames or [])]
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(missing))
    return fieldnames


def readCsvRows(text, required, formatLabel):
    """Read CSV or tab-separated text and return a list of row dicts."""
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t") if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    reader.fieldnames = _checkHeaders(reader.fieldnames, required, formatLabel)
    return list(reader)


def readXlsxRows(fileObj, required, formatLabel):
    """Read the first sheet of an .xlsx file and return a list of row dicts."""
    from openpyxl import load_workbook

    wb = load_workbook(fileObj, read_only=True, data_only=True)
    ws = wb.active
    rowsIter = ws.iter_rows(values_only=True)

    try:
        headerRow = next(rowsIter)
    except StopIteration:
        raise ValueError("The spreadsheet is empty.")

    headers = [str(h).strip() if h is not None else "" for h in headerRow]
    _checkHeaders(headers, required, formatLabel)

    rows = []
    for values in rowsIter:
        if values is None or all(v is None for v in values):
            continue
        row = dict(zip(headers, values))
        row = {k: ("" if v is None else str(v)) for k, v in row.items()}
        rows.append(row)
    return rows


# Backwards-compatible names
def processCsv(text):
    return routeRowsToGroups(readCsvRows(text, ROUTE_REQUIRED, "route"))


def processXlsx(fileObj):
    return routeRowsToGroups(readXlsxRows(fileObj, ROUTE_REQUIRED, "route"))


if __name__ == "__main__":
    with open("TestSheet1.csv", newline="", encoding="utf-8-sig") as f:
        vans, trucks = processCsv(f.read())
    print(buildText(vans, trucks))