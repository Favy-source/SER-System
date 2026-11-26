"""
Shared record schema and cached HTTP layer for every bibliographic source.

TWO DESIGN COMMITMENTS
    1. ONE normalised Record. OpenAlex, Crossref, PubMed and arXiv each return a
       different shape. Every adapter's job is to flatten its source into this
       schema so dedupe, screening and export never contain per-source special
       cases.

    2. EVERY response is cached to disk. A systematic review must be repeatable,
       but bibliographic APIs are living databases — re-running next month gives
       different counts. Caching the raw JSON/XML means the exact corpus behind
       the reported PRISMA numbers is preserved and inspectable. Delete the cache
       to deliberately refresh; otherwise the review is frozen and reproducible.

       This is also why the cache is gitignored but the DERIVED csv/json outputs
       are committed: the outputs are the evidence, the cache is the raw material.
"""
import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# The polite-pool identifier OpenAlex, Crossref, and Unpaywall ask for. It buys
# a faster, more reliable rate limit. Set SLR_CONTACT_EMAIL in your environment
# before running live API queries so no personal address is hardcoded in git.
CONTACT_EMAIL = os.environ.get("SLR_CONTACT_EMAIL", "ser-slr-research@example.org")
USER_AGENT = f"SER-System-SLR/1.0 (mailto:{CONTACT_EMAIL})"

# Per-host courtesy delay in seconds. Deliberately conservative: this review is
# a guest on free public infrastructure.
RATE_LIMIT = {
    "api.openalex.org": 0.12,
    "api.crossref.org": 0.25,
    "eutils.ncbi.nlm.nih.gov": 0.40,   # NCBI: max 3 req/s without an API key
    # arXiv asks for 3 s between calls and enforces it with 429s. Raised above
    # the documented minimum after a test run tripped the limit: being throttled
    # mid-review is far more expensive than the extra seconds.
    "export.arxiv.org": 4.00,
}
_last_call: Dict[str, float] = {}


# ── the normalised record ──────────────────────────────────

@dataclass
class Record:
    """One candidate paper, source-agnostic.

    Fields left empty rather than guessed. "Not reported" is itself a finding in
    this review (see the NR counts in the Synthesis sheet), so a field must never
    be filled in with a plausible default — that would manufacture data.
    """
    source: str                      # openalex | crossref | pubmed | arxiv
    source_id: str                   # the source's own identifier
    title: str = ""
    abstract: str = ""
    year: Optional[int] = None
    doi: str = ""
    authors: List[str] = field(default_factory=list)
    venue: str = ""
    venue_type: str = ""             # journal | conference | preprint | book | ""
    language: str = ""
    oa_status: str = ""              # gold | green | hybrid | bronze | closed | ""
    pdf_url: str = ""
    cited_by_count: int = 0
    referenced_works: List[str] = field(default_factory=list)  # OpenAlex IDs
    is_preprint: bool = False
    matched_strings: List[str] = field(default_factory=list)   # e.g. ["S1", "S6"]
    found_via: List[str] = field(default_factory=list)         # search | forward-cite | backward-cite
    raw_url: str = ""                # provenance: where this record came from

    # ── derived keys used by dedupe ──
    def norm_doi(self) -> str:
        if not self.doi:
            return ""
        d = self.doi.strip().lower()
        d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d)
        return d

    def norm_title(self) -> str:
        """Aggressively normalised title for fuzzy duplicate detection.

        Strips accents, punctuation, case and whitespace. Two records whose
        normalised titles AND years agree are treated as the same work even
        without a shared DOI — which is exactly the arXiv-vs-published case.
        """
        t = unicodedata.normalize("NFKD", self.title or "")
        t = "".join(c for c in t if not unicodedata.combining(c))
        t = t.lower()
        t = re.sub(r"[^a-z0-9]+", " ", t)
        return " ".join(t.split())

    def searchable(self) -> str:
        return f"{self.title}\n{self.abstract}"

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("authors", "referenced_works", "matched_strings", "found_via"):
            d[k] = "; ".join(str(x) for x in d[k])
        return d


# ── cached, rate-limited, retrying HTTP ────────────────────

class SourceError(RuntimeError):
    pass


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:32]
    host = re.sub(r"[^a-z0-9]+", "-", url.split("/")[2].lower())
    return CACHE_DIR / host / f"{h}.json"


def fetch(url: str, params: dict = None, *, parse: str = "json",
          use_cache: bool = True, timeout: int = 60, max_retries: int = 4):
    """GET with disk cache, per-host rate limiting and exponential backoff.

    `parse="json"` returns the decoded object; `parse="text"` returns the body
    (arXiv and PubMed efetch are XML). Cached either way — text is wrapped so
    one cache format covers both.
    """
    if params:
        url = f"{url}?{urlencode(params)}"

    cp = _cache_path(url)
    if use_cache and cp.exists():
        try:
            blob = json.loads(cp.read_text())
            return blob["body"] if parse == "text" else blob
        except (json.JSONDecodeError, KeyError):
            cp.unlink()   # corrupt cache entry — refetch rather than crash

    host = url.split("/")[2]
    delay = RATE_LIMIT.get(host, 1.0)
    since = time.time() - _last_call.get(host, 0.0)
    if since < delay:
        time.sleep(delay - since)

    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT,
                                           "Accept": "application/json, text/xml, */*"},
                             timeout=timeout)
            _last_call[host] = time.time()
            if r.status_code == 429 or r.status_code >= 500:
                raise SourceError(f"HTTP {r.status_code}")
            r.raise_for_status()
            body = r.json() if parse == "json" else r.text
            break
        except Exception as e:                       # noqa: BLE001 — retry anything transient
            last_err = e
            if attempt == max_retries - 1:
                raise SourceError(f"{url} failed after {max_retries} attempts: {e}") from e
            # 2, 4, 8, 16 s — the arXiv and NCBI docs both recommend backing off
            # rather than hammering, and a 429 here can get the review IP blocked.
            time.sleep(2 ** (attempt + 1))
    else:                                            # pragma: no cover
        raise SourceError(str(last_err))

    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"body": body} if parse == "text" else body))
    return body


def clear_cache():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)


def cache_stats() -> dict:
    if not CACHE_DIR.exists():
        return {"entries": 0, "bytes": 0}
    files = list(CACHE_DIR.rglob("*.json"))
    return {"entries": len(files), "bytes": sum(f.stat().st_size for f in files)}


# ── shared helpers used by more than one adapter ───────────

def strip_jats(text: str) -> str:
    """Crossref abstracts arrive as JATS XML fragments; PubMed sometimes too."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    return " ".join(text.split())


def classify_venue(name: str, type_hint: str = "") -> str:
    """Journal / conference / preprint / book, from whatever the source gives.

    Feeds IC3 (peer-reviewed venue) and EC4 (prefer the published version over
    the preprint), so it must not silently mislabel: anything unrecognised
    returns "" and reaches the human screener undecided.
    """
    t = (type_hint or "").lower()
    n = (name or "").lower()
    if "preprint" in t or "posted-content" in t or "arxiv" in n or "biorxiv" in n:
        return "preprint"
    if any(k in n for k in ("conference", "proceedings", "symposium", "workshop",
                            "congress", "icassp", "interspeech", "acm mm", "cvpr")):
        return "conference"
    if "book" in t or "chapter" in t:
        return "book"
    if "journal" in t or "journal" in n or "transactions" in n or t == "article":
        return "journal"
    return ""
