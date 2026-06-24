#!/usr/bin/env python3
"""
a_frequency.py
==============
Quantify the frequency of short /a/ and long /ā/ in romanizable Sanskrit text,
to test the claim that Yajnadevam's Indus-script decipherment produces /a/ and
/ā/ at frequencies implausibly high for real Sanskrit.

Why SLP1?
---------
Counting "how often is the vowel a?" in transliterated Sanskrit is error-prone:
 * IAST/HK write aspirates as digraphs (kh, gh, ...), so naive char counts
   double-count consonants and skew every ratio.
 * Devanagari is an abugida: the inherent vowel /a/ is *not written* after a bare
   consonant, so counting Devanagari signs *undercounts* /a/.
SLP1 sidesteps both: every Sanskrit phoneme -- including every long vowel,
diphthong, aspirate and the inherent a -- is written as exactly ONE ASCII
character. So after converting any input to SLP1, phoneme counting is a trivial,
exact character tally, and the decipherment and the Vedic corpora are processed
by an identical, script-neutral pipeline. That is the whole point: a fair,
apples-to-apples comparison.

Metrics reported (per corpus, aggregate + per-hymn distribution):
  a%      short a as a share of ALL phonemes
  aa%     long ā as a share of ALL phonemes
  (a+ā)%  combined, as a share of ALL phonemes
  a|V%    short a as a share of VOWELS only
  (a+ā)|V% combined, as a share of vowels
  V%      vowels as a share of all phonemes
  a:ā     ratio of short to long a

Headline metric:
  (a+ā) as a percentage of VOWELS  -- i.e. of all syllable nuclei, what share is
  a-quality. This factors out consonant density, so it is not affected by how
  many consonants a reading packs in; it isolates skew in the vowel system
  itself. The (a+ā)/all-phonemes figure is still reported alongside it.

Usage:
  python3 a_frequency.py        # downloads the Vedic corpora (first run), reads
                                # readings_slp1.txt from this folder, and prints
                                # one table: a+ā as % of vowels for Rigveda,
                                # Atharvaveda, Yajurveda and three cuts of the IVC
                                # readings (all / unique / unique & >=8 syllables)
  Options: --ivc FILE  --data DIR  --refresh  --no-fetch

On first run the needed Vedic texts (~3 MB) are downloaded from GitHub into a
local cache dir (default: ./DharmicData beside this script; set with --data) and
reused afterwards. No manual `git clone` required.

============================================================================
DATA SOURCES & PROVENANCE
============================================================================
Vedic baseline texts (Devanagari with Vedic svara/accent marks):
  * Editorial source : Vedic Heritage Portal, https://vedicheritage.gov.in/
                       (IGNCA / Ministry of Culture, Government of India).
  * Redistributed via: bhavykhatri/DharmicData on GitHub,
                       https://github.com/bhavykhatri/DharmicData
                       License: Open Database License (ODbL).
  * Texts actually used in the baselines below:
      - Rigveda Samhita .......... all 10 mandalas        (Rigveda/*.json)
      - Atharvaveda (Saunaka) .... all 20 kandas          (AtharvaVeda/*.json)
      - Yajurveda, Shukla, Vajasaneyi-Madhyandina Samhita, 40 adhyayas
                                                          (Yajurveda/vajasneyi_madhyadina_samhita.json)
    (The Kanva-Samhita file and the repo's classical/epic texts are NOT used.)
  * Per-sukta editorial metadata (rishi/devata/chandas) is stripped before
    counting; Vedic accent marks are stripped; verse-number markers and
    punctuation are excluded from the phoneme tally.

Transliteration:
  * indic_transliteration (sanscript), Devanagari -> SLP1.
    https://pypi.org/project/indic-transliteration/

The decipherment readings are NOT bundled: Yajnadevam's repos
(github.com/yajnadevam, e.g. SSC, indus-website) store inscriptions only as
sign-code sequences (e.g. "+410-017+"); the Sanskrit output is generated from
his sign->value key and served from the indusscript.net database. Supply those
readings as a FILE argument to complete the comparison.
"""

import sys, os, re, glob, json, argparse, unicodedata, statistics
import io, zipfile, shutil, urllib.request, urllib.error
from collections import Counter
from indic_transliteration import sanscript

# ---------------------------------------------------------------------------
# Corpus auto-download (no manual `git clone` needed)
# ---------------------------------------------------------------------------
REPO   = "bhavykhatri/DharmicData"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
ZIP_URL  = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"

# Exactly the files used for the baselines (relative paths inside the repo).
NEEDED = (
    [f"Rigveda/rigveda_mandala_{i}.json" for i in range(1, 11)] +
    [f"AtharvaVeda/atharvaveda_kaanda_{i}.json" for i in range(1, 21)] +
    ["Yajurveda/vajasneyi_madhyadina_samhita.json"]
)


def _http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "a-frequency/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _have_all(cache_dir):
    return all(os.path.isfile(os.path.join(cache_dir, p)) for p in NEEDED)


def _fetch_raw(cache_dir):
    """Download just the needed JSON files (~3 MB). Returns True on full success."""
    for p in NEEDED:
        dest = os.path.join(cache_dir, p)
        if os.path.isfile(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        data = _http_get(RAW_BASE + p)
        with open(dest, "wb") as f:
            f.write(data)
    return _have_all(cache_dir)


def _fetch_zip(cache_dir):
    """Fallback: download the repo zipball (~31 MB) and extract the needed files."""
    blob = _http_get(ZIP_URL, timeout=180)
    z = zipfile.ZipFile(io.BytesIO(blob))
    root = z.namelist()[0].split("/")[0]          # e.g. "DharmicData-main"
    for p in NEEDED:
        member = f"{root}/{p}"
        dest = os.path.join(cache_dir, p)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with z.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
    return _have_all(cache_dir)


def ensure_corpora(cache_dir, refresh=False, allow_fetch=True):
    """Make sure the Vedic texts are present in cache_dir, downloading if needed.

    Returns cache_dir if the corpora are available, else None (caller then falls
    back to the baked-in baselines so the script still works offline).
    """
    if refresh:
        for sub in ("Rigveda", "AtharvaVeda", "Yajurveda"):
            shutil.rmtree(os.path.join(cache_dir, sub), ignore_errors=True)
    if _have_all(cache_dir):
        return cache_dir
    if not allow_fetch:
        return cache_dir if _have_all(cache_dir) else None
    os.makedirs(cache_dir, exist_ok=True)
    print(f"[fetch] downloading Vedic corpora -> {cache_dir}", file=sys.stderr)
    try:
        if _fetch_raw(cache_dir):
            print("[fetch] done (raw files).", file=sys.stderr)
            return cache_dir
    except (urllib.error.URLError, OSError) as e:
        print(f"[fetch] raw download failed ({e}); trying zipball...", file=sys.stderr)
    try:
        if _fetch_zip(cache_dir):
            print("[fetch] done (zipball).", file=sys.stderr)
            return cache_dir
    except (urllib.error.URLError, OSError, zipfile.BadZipFile) as e:
        print(f"[fetch] zipball download failed ({e}).", file=sys.stderr)
    print("[fetch] could not obtain corpora; using baked-in baselines.", file=sys.stderr)
    return None

# ---------------------------------------------------------------------------
# Baked-in baselines, computed by this script over full Saṃhitā texts
# (sources documented in the header above). Lets you test a decipherment file
# WITHOUT re-downloading the ~30 MB corpora. Re-derive with --data <dir>.
# HEADLINE METRIC = (a+ā) as a percentage of VOWELS.
# Format: name -> (aggregate a+ā|vowels %, per-hymn mean, per-hymn SD)
# ---------------------------------------------------------------------------
BASELINES = {
    "Rigveda (early Vedic)":      (60.65, 60.61, 3.63),
    "Atharvaveda (later Vedic)":  (62.34, 62.19, 5.46),
    "Yajurveda VS (later Vedic)": (62.04, 62.40, 2.70),
}

# ---------------------------------------------------------------------------
# SLP1 phoneme inventory (each is exactly one character)
# ---------------------------------------------------------------------------
VOWELS      = set("aAiIuUfFxXeEoO")          # a ā i ī u ū ṛ ṝ ḷ ḹ e ai o au
CONSONANTS  = set("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvLSzsh")  # incl. L = Vedic ḷa (ळ)
NASAL_VIS   = set("MH")                       # anusvāra (ṃ) , visarga (ḥ)
PHONEMES    = VOWELS | CONSONANTS | NASAL_VIS
SHORT_A, LONG_A = "a", "A"

# Vedic accent / tone combining marks to drop before transliteration.
SVARA_RE = re.compile("[\u0951\u0952\u0953\u0954\u1CD0-\u1CFF\uA8E0-\uA8FF\u0900\u0901]")
DEVANAGARI_RE = re.compile("[\u0900-\u097F]")
IAST_DIACRITIC_RE = re.compile("[āīūṛṝḷḹṅñṭḍṇśṣṃḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂḤ]")


def detect_scheme(text):
    if DEVANAGARI_RE.search(text):
        return sanscript.DEVANAGARI
    if IAST_DIACRITIC_RE.search(text):
        return sanscript.IAST
    return sanscript.HK  # plausible ASCII default; pass --scheme to override


def to_slp1(text, scheme=None):
    text = unicodedata.normalize("NFC", text)
    if scheme is None:
        scheme = detect_scheme(text)
    if scheme == sanscript.SLP1:
        return text                      # already SLP1; no transliteration needed
    if scheme == sanscript.DEVANAGARI:
        text = SVARA_RE.sub("", text)
    return sanscript.transliterate(text, scheme, sanscript.SLP1)


def count(slp1):
    """Return phoneme counts and derived metrics for one SLP1 string."""
    c = Counter(ch for ch in slp1 if ch in PHONEMES)
    total   = sum(c.values())
    nvow    = sum(c[v] for v in VOWELS)
    a, aa   = c[SHORT_A], c[LONG_A]
    if total == 0:
        return None
    return {
        "phonemes": total,
        "vowels": nvow,
        "a": a, "aa": aa,
        "a_pct":      100*a/total,
        "aa_pct":     100*aa/total,
        "a_aa_pct":   100*(a+aa)/total,
        "a_vow_pct":  100*a/nvow if nvow else 0.0,
        "a_aa_vow_pct": 100*(a+aa)/nvow if nvow else 0.0,
        "vow_pct":    100*nvow/total,
        "a_to_aa":    (a/aa if aa else float("inf")),
    }


# ---------------------------------------------------------------------------
# Corpus loaders -> list of (segment_label, devanagari_text) at hymn granularity
# ---------------------------------------------------------------------------
def _strip_meta_and_markers(dev_text, meta_lines=1):
    """Drop leading editorial line(s) (rishi/devata/chandas) and verse numbers."""
    lines = dev_text.split("\n")
    body = "\n".join(lines[meta_lines:]) if len(lines) > meta_lines else dev_text
    return body


def load_veda(path, text_key="text", meta_lines=1, label_keys=()):
    segs = []
    pattern = os.path.join(path, "*.json") if os.path.isdir(path) else path
    for fp in sorted(glob.glob(pattern)):
        data = json.load(open(fp, encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict) or text_key not in it:
                continue
            body = _strip_meta_and_markers(it[text_key], meta_lines)
            label = "/".join(str(it.get(k, "?")) for k in label_keys) or os.path.basename(fp)
            segs.append((label, body))
    return segs


def corpus_a_aa_vow_pct(segments, scheme=sanscript.DEVANAGARI):
    """Aggregate (a+ā) as a percentage of vowels over all segments of a corpus."""
    agg = Counter()
    for _, dev in segments:
        agg.update(ch for ch in to_slp1(dev, scheme) if ch in PHONEMES)
    nv = sum(agg[v] for v in VOWELS)
    a, aa = agg[SHORT_A], agg[LONG_A]
    return 100 * (a + aa) / nv if nv else float("nan")


# ---------------------------------------------------------------------------
# Per-reading analysis (for the IVC decipherment list: one reading per line)
# ---------------------------------------------------------------------------
def read_reading_records(path, scheme=None):
    """One dict per non-empty line: {slp, phonemes, vowels, a, aa}."""
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            slp = to_slp1(line, scheme)
            c = Counter(ch for ch in slp if ch in PHONEMES)
            nv = sum(c[v] for v in VOWELS)
            if nv == 0:
                continue
            recs.append({"slp": slp, "phonemes": sum(c.values()), "vowels": nv,
                         "a": c[SHORT_A], "aa": c[LONG_A]})
    return recs


def agg_records(recs):
    a  = sum(r["a"] for r in recs);  aa = sum(r["aa"] for r in recs)
    nv = sum(r["vowels"] for r in recs); tot = sum(r["phonemes"] for r in recs)
    return {"n": len(recs), "phonemes": tot, "vowels": nv, "a": a, "aa": aa,
            "a_aa_vow_pct": 100*(a+aa)/nv if nv else float("nan"),
            "a_vow_pct":    100*a/nv if nv else float("nan"),
            "a_to_aa":      (a/aa if aa else float("inf"))}


def unique_records(recs):
    seen, out = set(), []
    for r in recs:                      # dedup on the SLP1 reading string
        if r["slp"] in seen:
            continue
        seen.add(r["slp"]); out.append(r)
    return out


def print_table(title, headers, rows, aligns=None):
    cols = len(headers)
    aligns = aligns or ["<"] * cols
    body = [r for r in rows if r != "SEP"]
    widths = [len(str(h)) for h in headers]
    for r in body:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))
    rule = "─" * (sum(widths) + 2 * (cols - 1))
    def line(cells):
        return "  ".join(f"{str(c):{a}{w}}" for c, w, a in zip(cells, widths, aligns))
    print()
    if title:
        print(title)
    print(rule); print(line(headers)); print(rule)
    for r in rows:
        print(rule if r == "SEP" else line(r))
    print(rule)


def _default_ivc_path():
    """readings_slp1.txt beside this script, else in the current directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "readings_slp1.txt"), "readings_slp1.txt"):
        if os.path.isfile(cand):
            return cand
    return os.path.join(here, "readings_slp1.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ivc", metavar="FILE", default=_default_ivc_path(),
                    help="IVC readings, one per line (default: readings_slp1.txt beside this script)")
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "DharmicData"),
                    help="local cache dir for the Vedic corpora (auto-downloaded here if absent)")
    ap.add_argument("--refresh", action="store_true", help="re-download the corpora even if cached")
    ap.add_argument("--no-fetch", action="store_true", help="use cache only; else baked-in baselines")
    args = ap.parse_args()

    rows = []

    # 1) Vedic baselines (downloads the corpora on first run)
    D = ensure_corpora(args.data, refresh=args.refresh, allow_fetch=not args.no_fetch)
    corpora = [
        ("Rigveda",     os.path.join(D, "Rigveda")),
        ("Atharvaveda", os.path.join(D, "AtharvaVeda")),
        ("Yajurveda",   os.path.join(D, "Yajurveda", "vajasneyi_madhyadina_samhita.json")),
    ] if D else []
    if corpora:
        for name, path in corpora:
            if os.path.exists(path):
                rows.append([name, f"{corpus_a_aa_vow_pct(load_veda(path)):.2f}%"])
    else:                                   # offline with no cache -> baked-in numbers
        for name, (agg, _m, _sd) in BASELINES.items():
            rows.append([name.split(" (")[0], f"{agg:.2f}%"])

    # 2) Three cuts of the IVC decipherment readings
    if os.path.isfile(args.ivc):
        recs  = read_reading_records(args.ivc, scheme=sanscript.SLP1)
        uniq  = unique_records(recs)
        uniq8 = [r for r in uniq if r["vowels"] >= 8]      # syllables == vowel nuclei
        if rows:
            rows.append("SEP")
        rows.append(["IVC \u2014 all",                  f"{agg_records(recs)['a_aa_vow_pct']:.2f}%"])
        rows.append(["IVC \u2014 unique",               f"{agg_records(uniq)['a_aa_vow_pct']:.2f}%"])
        rows.append(["IVC \u2014 unique, \u22658 syll", f"{agg_records(uniq8)['a_aa_vow_pct']:.2f}%"])
    else:
        print(f"[note] {args.ivc} not found; printing Vedic rows only", file=sys.stderr)

    print_table("a+ā as % of vowels", ["", "a+ā|vowels"], rows, aligns=["<", ">"])


if __name__ == "__main__":
    main()
