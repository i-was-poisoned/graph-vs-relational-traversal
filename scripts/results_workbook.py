"""Write the results of one measurement to an Excel file (.xlsx), and read it back.

Used by measure.py; it isn't run by itself. Every measurement (every analysis)
writes ONE file, results/<database>_<date>_<time>.xlsx, with one sheet per
Cypher version ("levels", "paths"). Every sheet looks like this:

    | Analysis information |   | PostgreSQL              |   | Neo4j                   |
    | Database      | ...  |   | Group | Rank | Actor ...|   | Group | Rank | Actor ...|
    | Data from     | ...  |   | top   | 1    | ...      |   | top   | 1    | ...      |
    | ...           | ...  |   | ...                     |   | ...                     |

    * the information about the analysis (the data, its dates and hours, the
      number of rows / nodes, ...) appears ONCE, in the first two columns;
    * then two separate tables, one per database, side by side with one empty
      column between them, with exactly the same columns: the same line of
      both tables is the same question (same starting actor, same depth);
    * headers in a strong blue, lines in two light blues, one after the other.

A last sheet, "Starting actors", lists the 20 actors, so that a measurement
repeated another day can reuse them. Every column is explained in the README.
"""

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

STRONG_BLUE = "1F4E79"
LIGHT_BLUES = ("DDEBF7", "EEF5FB")   # the lines alternate between these two
WHITE = "FFFFFF"
STARTS_SHEET = "Starting actors"

# The columns of each database's table: (header, key in the figures of one line).
# "joins_or_hops" is called "JOINs" in PostgreSQL and "Hops" in Neo4j.
TABLE_COLUMNS = [
    ("Group", "group"),
    ("Rank", "rank"),
    ("Actor", "login"),
    ("Depth", "depth"),
    ("Actors reached", "actors_reached"),
    ("{steps}", "joins_or_hops"),
    ("Status", "status"),
    ("Time (s)", "time_s"),
    ("First run (s)", "first_run_s"),
    ("Data processed (MB)", "data_processed_mb"),
    ("From disk (MB)", "data_from_disk_mb"),
    ("Memory (MB)", "memory_mb"),
    ("Temp disk (MB)", "temp_disk_mb"),
    ("CPU (s)", "cpu_s"),
    ("Cores used", "cores_used"),
    ("Reliable", "reliable"),
]
STEPS_NAME = {"postgresql": "JOINs", "neo4j": "Hops"}
STARTS_COLUMNS = ["group", "rank", "actor_id", "login", "reached"]

_thin = Side(style="thin", color="9BC2E6")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _header(cell, text) -> None:
    cell.value = text
    cell.font = Font(bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=STRONG_BLUE)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def _body(cell, value, line_number: int) -> None:
    cell.value = value
    cell.fill = PatternFill("solid", fgColor=LIGHT_BLUES[line_number % 2])
    cell.border = BORDER


def _title(sheet, row: int, first_col: int, last_col: int, text: str) -> None:
    # A title over a whole table: one cell stretched (merged) over all its columns.
    sheet.merge_cells(start_row=row, start_column=first_col, end_row=row, end_column=last_col)
    _header(sheet.cell(row=row, column=first_col), text)
    sheet.cell(row=row, column=first_col).font = Font(bold=True, color=WHITE, size=13)


def table_positions() -> dict[str, int]:
    # Column where each part starts: information in A-B, an empty column, PostgreSQL's
    # table, one empty column, Neo4j's table.
    postgresql = 4
    return {"information": 1, "postgresql": postgresql, "neo4j": postgresql + len(TABLE_COLUMNS) + 1}


def write_sheet(sheet, information: list[tuple[str, object]], lines: list[dict]) -> None:
    # information: (label, value) pairs, written once. lines: one per starting actor and
    # depth, each with "postgresql" and "neo4j" figures.
    where = table_positions()

    _title(sheet, 1, where["information"], where["information"] + 1, "Analysis information")
    for number, (label, value) in enumerate(information):
        _body(sheet.cell(row=2 + number, column=1), label, number)
        sheet.cell(row=2 + number, column=1).font = Font(bold=True)
        _body(sheet.cell(row=2 + number, column=2), value, number)

    for system in ("postgresql", "neo4j"):
        first = where[system]
        _title(sheet, 1, first, first + len(TABLE_COLUMNS) - 1, "PostgreSQL" if system == "postgresql" else "Neo4j")
        for offset, (name, _) in enumerate(TABLE_COLUMNS):
            _header(sheet.cell(row=2, column=first + offset), name.format(steps=STEPS_NAME[system]))
        for number, line in enumerate(lines):
            figures = {**line, **line[system]}
            for offset, (_, key) in enumerate(TABLE_COLUMNS):
                value = figures.get(key)
                _body(sheet.cell(row=3 + number, column=first + offset), "" if value is None else value, number)

    # Column widths: wide enough for the labels; the empty separator columns stay narrow.
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 26
    for separator in (where["postgresql"] - 1, where["neo4j"] - 1):
        sheet.column_dimensions[get_column_letter(separator)].width = 3
    for system in ("postgresql", "neo4j"):
        for offset, (name, _) in enumerate(TABLE_COLUMNS):
            width = 22 if name == "Actor" else max(9, min(len(name) + 2, 14))
            sheet.column_dimensions[get_column_letter(where[system] + offset)].width = width
    sheet.row_dimensions[2].height = 32
    sheet.freeze_panes = sheet.cell(row=3, column=1)


def write_workbook(path: Path, sheets: dict[str, tuple[list, list]], starts: list[dict]) -> None:
    # sheets: sheet name -> (information, lines). Saved again after every actor, so a
    # measurement that stops half-way keeps what it already measured.
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, (information, lines) in sheets.items():
        write_sheet(workbook.create_sheet(name), information, lines)
    sheet = workbook.create_sheet(STARTS_SHEET)
    for offset, column in enumerate(STARTS_COLUMNS):
        _header(sheet.cell(row=1, column=1 + offset), column)
        sheet.column_dimensions[get_column_letter(1 + offset)].width = 22 if column == "login" else 12
    for number, actor in enumerate(starts):
        for offset, column in enumerate(STARTS_COLUMNS):
            _body(sheet.cell(row=2 + number, column=1 + offset), actor[column], number)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def read_starts(path: Path) -> list[dict]:
    # The starting actors of an earlier measurement (its "Starting actors" sheet).
    sheet = load_workbook(path, read_only=True)[STARTS_SHEET]
    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    actors = [dict(zip(STARTS_COLUMNS, row)) for row in rows if row and row[0] is not None]
    for actor in actors:
        actor["rank"], actor["actor_id"], actor["reached"] = int(actor["rank"]), int(actor["actor_id"]), int(actor["reached"])
    return actors
