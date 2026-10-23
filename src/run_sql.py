"""Execute every query in sql/ with DuckDB against data/cookie_cats.csv.

Outputs are printed and saved to results/sql_<name>.csv.
"""
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "cookie_cats.csv"
RESULTS = ROOT / "results"


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW cookie_cats AS SELECT * FROM read_csv_auto('{DATA.as_posix()}')")
    for path in sorted((ROOT / "sql").glob("*.sql")):
        df = con.execute(path.read_text()).df()
        df.to_csv(RESULTS / f"sql_{path.stem}.csv", index=False)
        print(f"\n=== {path.name} ===")
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
