"""Polite access to the Internet Archive Wayback Machine copies of
www.diputados.gob.mx/LeyesBiblio/ (the origin is not reachable from our network, see README).

All raw files are cached under _raw/mx/ so re-runs do not re-download.
"""
import os
import threading
import time
import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "mx"))
BASE = "www.diputados.gob.mx/LeyesBiblio/"
ORIGIN = "https://" + BASE
DELAY = 1.5  # seconds between requests to archive.org

_s = requests.Session()
_s.headers["User-Agent"] = UA
_last = [0.0]
_lock = threading.Lock()


def _get(url, timeout=180, tries=6):
    err = None
    for i in range(tries):
        with _lock:
            wait = _last[0] + DELAY - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        try:
            r = _s.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return r
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            err = str(e)
        time.sleep(min(120, 5 * 2 ** i))
    raise RuntimeError(f"{url}: {err}")


_origin_ok = [None]


def direct(path):
    """Try the official origin first (works when run from a network that can reach it).
    After the first connection failure the origin is not tried again in this run."""
    if _origin_ok[0] is False:
        return None
    try:
        r = _s.get(ORIGIN + path, timeout=(15, 120))
        _origin_ok[0] = True
        if r.status_code == 200:
            return r.content
    except requests.ConnectionError:
        _origin_ok[0] = False
    except requests.RequestException:
        pass
    return None


def cdx(path, prefix=False, since="2024"):
    """Return {original_url_lower_path: (timestamp, original)} of latest 200 captures."""
    q = {
        "url": "diputados.gob.mx/LeyesBiblio/" + path,
        "filter": "statuscode:200",
        "fl": "original,timestamp,length",
        "from": since,
    }
    if prefix:
        q["matchType"] = "prefix"
    url = "https://web.archive.org/cdx/search/cdx?" + "&".join(f"{k}={v}" for k, v in q.items())
    r = _get(url, timeout=300)
    best = {}
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        orig, ts = parts[0], parts[1]
        p = orig.split("/LeyesBiblio/", 1)[-1].split("?")[0].lower()
        if p not in best or ts > best[p][0]:
            best[p] = (ts, orig)
    return best


def snapshot(ts, orig):
    """Fetch the raw (id_) bytes of a capture."""
    r = _get(f"https://web.archive.org/web/{ts}id_/{orig}")
    if r.status_code != 200:
        raise RuntimeError(f"{orig}@{ts}: HTTP {r.status_code}")
    return r.content


def cached(name, fetch):
    path = os.path.join(ROOT, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            return f.read()
    data = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return data


def all_captures(path):
    """All 200 captures of one file (any year), newest first: [(timestamp, original)]."""
    url = ("https://web.archive.org/cdx/search/cdx?url=diputados.gob.mx/LeyesBiblio/" + path
           + "&filter=statuscode:200&fl=original,timestamp")
    r = _get(url, timeout=300)
    caps = [tuple(reversed(l.split()[:2])) for l in r.text.splitlines() if len(l.split()) >= 2]
    return sorted(caps, reverse=True)
