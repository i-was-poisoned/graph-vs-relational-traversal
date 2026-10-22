"""Download GH Archive hourly dataset files.

Defaults to this project's fixed benchmark hour (see README.md): downloads it
and decompresses it to plain JSON Lines. Any date/hour can be requested for
exploration. The live pipeline (pipeline.py) uses fetch_gz() to download
hours without decompressing them.

Usage:
    python scripts/download_gharchive.py
    python scripts/download_gharchive.py --date 2026-08-27 --hour 15
"""

import argparse
import gzip
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_DATE = "2026-08-27"
DEFAULT_HOUR = 15

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_gz(date: str, hour: int, data_dir: Path = DATA_DIR, retries: int = 3) -> Path:
    """Download one hour's .json.gz file into data_dir and return its path.

    The file is written to a temporary ".part" name and only renamed once the
    download has finished, so an interrupted download never leaves a broken file
    that looks complete. Network errors are retried; a missing hour (HTTP 404,
    e.g. not published yet) is not.
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    # GH Archive file names use the UTC hour without a leading zero: 2026-08-27-5.json.gz
    filename = f"{date}-{hour}.json.gz"
    url = f"https://data.gharchive.org/{filename}"
    gz_path = data_dir / filename
    part_path = data_dir / (filename + ".part")

    for attempt in range(1, retries + 1):
        print(f"Downloading {url} (attempt {attempt}/{retries}) ...")
        try:
            # GH Archive's server rejects requests whose User-Agent header looks
            # like a script (urllib's default is "Python-urllib/x.y"), so we set
            # a browser-like one explicitly. urlretrieve() doesn't allow custom
            # headers, so we build the request manually with urlopen() instead.
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=120) as response, open(part_path, "wb") as f_out:
                shutil.copyfileobj(response, f_out)
            part_path.replace(gz_path)
            print(f"Saved to {gz_path}")
            return gz_path
        except urllib.error.HTTPError as error:
            part_path.unlink(missing_ok=True)
            if error.code == 404:
                raise FileNotFoundError(f"{url} does not exist (not published yet?)") from error
            if attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            part_path.unlink(missing_ok=True)
            if attempt == retries:
                raise
        time.sleep(10 * attempt)  # wait a bit longer after each failed attempt

    raise RuntimeError("unreachable")


def download(date: str, hour: int, data_dir: Path = DATA_DIR) -> Path:
    gz_path = fetch_gz(date, hour, data_dir)

    json_path = gz_path.with_suffix("")
    print(f"Decompressing to {json_path} ...")
    with gzip.open(gz_path, "rb") as f_in, open(json_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    print(f"Done: {json_path}")

    return json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help=f"Date in YYYY-MM-DD format (default: {DEFAULT_DATE})",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=DEFAULT_HOUR,
        choices=range(0, 24),
        metavar="[0-23]",
        help=f"UTC hour, 0-23 (default: {DEFAULT_HOUR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    download(args.date, args.hour)


if __name__ == "__main__":
    main()
