"""Download the public Cookie Cats A/B test dataset into data/cookie_cats.csv."""
import hashlib
import pathlib
import urllib.request

URL = ("https://raw.githubusercontent.com/ryanschaub/"
       "Mobile-Games-A-B-Testing-with-Cookie-Cats/master/cookie_cats.csv")
EXPECTED_MD5 = "99b48ea3d4a552fa6b27aac60a8cfddf"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "cookie_cats.csv"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUT.exists():
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, OUT)
    md5 = hashlib.md5(OUT.read_bytes()).hexdigest()
    status = "OK" if md5 == EXPECTED_MD5 else f"WARNING: md5 {md5} != expected {EXPECTED_MD5}"
    print(f"{OUT} ({OUT.stat().st_size:,} bytes) checksum {status}")


if __name__ == "__main__":
    main()
