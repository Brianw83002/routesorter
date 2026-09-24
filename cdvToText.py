import csv
import io

REQUIRED = ["Name", "Route Code", "Stops Left", "Stops per hour"]


def processCsv(text):
    """Split CSV rows into vans (CP) and trucks (XL)."""
    vans = []
    trucks = []

    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]

    missing = [c for c in REQUIRED if c not in reader.fieldnames]
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(missing))

    for row in reader:
        code = row["Route Code"].upper()
        if "CP" in code:
            vans.append(row)
        elif "XL" in code:
            trucks.append(row)

    return vans, trucks


def formatRow(r):
    return f'{r["Name"]} Stops: {r["Stops Left"]} | {r["Stops per hour"]} per/h'


def buildText(vans, trucks):
    lines = ["Vans"]
    lines += [formatRow(r) for r in vans]
    lines += ["", "Truck"]
    lines += [formatRow(r) for r in trucks]
    return "\n".join(lines)


if __name__ == "__main__":
    with open("TestSheet1.csv", newline="", encoding="utf-8-sig") as f:
        vans, trucks = processCsv(f.read())
    print(buildText(vans, trucks))
