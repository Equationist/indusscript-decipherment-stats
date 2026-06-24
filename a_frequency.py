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
  python3 a_frequency.py        # one self-contained script. Downloads the Vedic
                                # corpora (~3 MB, urllib) and the DHARMA Sanskrit
                                # epigraphy corpora (git clone), reads
                                # readings_slp1.txt from this folder, and prints:
                                #   - per-corpus Sanskrit epigraphy table
                                #   - a+ā|vowels for Vedic literary vs Sanskrit
                                #     epigraphy (all/short/seals) vs the IVC
                                #     readings (all/unique/unique & >=8 syll)
  Options: --ivc FILE  --data DIR  --dharma DIR  --refresh  --no-fetch  --no-epi

Requirements: indic_transliteration (pip) and, for the epigraphy comparison, the
system `git` tool. Use --no-epi to skip the epigraphy download entirely.
Corpora are cached locally (./DharmicData, ./dharma_cache) and reused.

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
import io, zipfile, shutil, urllib.request, urllib.error, subprocess
import xml.etree.ElementTree as ET
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


# ---------------------------------------------------------------------------
# Sanskrit EPIGRAPHY comparison (DHARMA project EpiDoc corpora).
# Tests whether the IVC decipherment's extreme a+ā-vowel share is just a
# *register* effect: the Vedic rows are running literary text, whereas IVC seals
# are short, name/title-heavy inscriptions. We compare against real Sanskrit
# epigraphy, including its short SEAL legends -- the closest analog to IVC seals.
# (Coin legends would be ideal but no machine-readable coin-legend *text* corpus
# is openly available; the numismatic datasets are coin *images* for ML.)
# Needs the system `git` tool to clone the corpora.
# ---------------------------------------------------------------------------
DHARMA_CORPORA = [   # (label, erc-dharma repo, glob of edition XML inside the repo)
    ("Daksina Kosala",     "tfb-daksinakosala-epigraphy", "workflow-output/editedxml/EDITED_*.xml"),
    ("Maitraka (Valabhi)", "tfb-maitraka-epigraphy",      "workflow-output/editedxml/EDITED_*.xml"),
    ("Badami Calukya",     "tfb-badamicalukya-epigraphy", "workflow-output/editedxml/EDITED_*.xml"),
    ("Kalyana Calukya",    "tfb-kalyanacalukya-epigraphy","workflow-output/editedxml/EDITED_*.xml"),
    ("Bhaumakara",         "tfb-bhaumakara-epigraphy",    "workflow-output/editedxml/EDITED_*.xml"),
    ("Eastern Calukya",    "tfb-vengicalukya-epigraphy",  "workflow-output/editedxml/EDITED_*.xml"),
    ("Somavamsin",         "tfb-somavamsin-epigraphy",    "workflow-output/editedxml/EDITED_*.xml"),
    ("Bengal charters",    "tfb-bengalcharters-epigraphy","texts/DHARMA_INS*.xml"),
    ("Bengal dedications", "tfb-bengalded-epigraphy",     "texts/xml/DHARMA_INS*.xml"),
    ("Early Andhra (Skt)", "tfb-eiad-epigraphy",          "texts/xml/DHARMA_INS*.xml"),
    ("Arakan",             "tfb-arakan-epigraphy",        "xml-provisional/DHARMA_INS*.xml"),
    ("Pallava",            "tfa-pallava-epigraphy",       "DHARMA_INS*.xml"),
    ("Khmer (SE Asia)",    "tfc-khmer-epigraphy",         "texts/xml/DHARMA_INS*.xml"),
    ("Nusantara (SE Asia)","tfc-nusantara-epigraphy",     "xml/DHARMA_INS*.xml"),
    ("Campa (SE Asia)",    "tfc-campa-epigraphy",         "xml/DHARMA_INSCIC*.xml"),
]
# Same project, but a Middle Indo-Aryan (Prakrit) corpus: the Early Andhra
# Buddhist *donative* inscriptions (Amaravati, Nagarjunakonda...) -- short,
# name-heavy gift records, the closest large clean analog to IVC seals.
DHARMA_PRAKRIT = [("Early Andhra donatives", "tfb-eiad-epigraphy", "texts/xml/DHARMA_INS*.xml")]
SHORT_MAX_VOWELS = 60        # "short inscription" = edition with <= this many vowels

_XMLLANG = "{http://www.w3.org/XML/1998/namespace}lang"
_EPI_SKIP = {"note","gap","orig","abbr","rdg","g","space","milestone","certainty",
             "witDetail","head","surplus","del","teiHeader","desc","figure","lacunaEnd"}
_EPI_BREAK = {"lb","pb","l","p","lg","div","ab","seg"}


def _ln(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else tag


def _lang_ok(lang, want):
    return lang is None or lang.lower().startswith(want)


def _epi_text(elem, want="san"):
    """Recursively collect `want`-language text from an EpiDoc element (drops
    apparatus, notes, heads, lost text; keeps regularized readings; skips
    subtrees explicitly tagged as a different language)."""
    if _ln(elem.tag) in _EPI_SKIP or not _lang_ok(elem.attrib.get(_XMLLANG), want):
        return ""
    parts = [elem.text or ""]
    for ch in elem:
        parts.append(_epi_text(ch, want)); parts.append(ch.tail or "")
    t = "".join(parts)
    return t + " " if _ln(elem.tag) in _EPI_BREAK else t


def _head_label(div):
    h = div.find("{*}head")
    return "".join(h.itertext()).strip().lower() if h is not None else ""


def epidoc_extract(path, want="san"):
    """Return (full_edition_text, seal_legend_text) in language `want` (a BCP-47
    prefix such as 'san' or 'pra') for one EpiDoc file. Inscriptions whose edition
    is in another language are skipped; foreign-language segments inside a matching
    edition are dropped."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return "", ""
    ed = next((d for d in root.iter()
               if _ln(d.tag) == "div" and d.attrib.get("type") == "edition"), None)
    if ed is None or not _lang_ok(ed.attrib.get(_XMLLANG), want):
        return "", ""
    seals = [_epi_text(d, want) for d in ed.iter()
             if _ln(d.tag) == "div" and d.attrib.get("type") == "textpart"
             and "seal" in _head_label(d)]
    return _epi_text(ed, want), " ".join(seals)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def dharma_download(repo, cache):
    """git clone --depth 1 a DHARMA repo into the cache; return its path or None."""
    dest = os.path.join(cache, repo)
    if os.path.isdir(dest):
        return dest
    os.makedirs(cache, exist_ok=True)
    print(f"[fetch] cloning {repo} ...", file=sys.stderr)
    r = subprocess.run(["git", "clone", "--depth", "1",
                        f"https://github.com/erc-dharma/{repo}.git", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest if r.returncode == 0 else None


# ---------------------------------------------------------------------------
# Rigveda BY PART OF SPEECH (UD_Sanskrit-Vedic, the Treebank of Vedic Sanskrit).
# Tests the hypothesis that verbs (-ti etc.) depress the a+ā share and that a
# names/epithets-only text (like a seal) would be far higher. We split the RV
# tokens into nominal (NOUN/PROPN/ADJ = names + epithets) vs finite VERB and
# score each with the same metric. Surface forms are in IAST.
# ---------------------------------------------------------------------------
def udvedic_download(cache):
    """git clone --depth 1 the UD Vedic treebank; return its path or None."""
    if os.path.isdir(cache):
        return cache
    print("[fetch] cloning UD_Sanskrit-Vedic ...", file=sys.stderr)
    r = subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/UniversalDependencies/UD_Sanskrit-Vedic.git", cache],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cache if r.returncode == 0 else None


def rv_pos_forms(path, source="ṚV"):
    """Return {UPOS: [surface form, ...]} for one Vedic text (by citation_text)."""
    out = {}
    for fn in glob.glob(os.path.join(path, "*.conllu")):
        cit, keep = None, False
        for ln in open(fn, encoding="utf-8"):
            if ln.startswith("# citation_text="):
                cit = ln.split("=", 1)[1].strip(); keep = (cit == source)
            elif ln and ln[0] != "#":
                c = ln.rstrip("\n").split("\t")
                if keep and len(c) > 3 and "-" not in c[0] and "." not in c[0]:
                    out.setdefault(c[3], []).append(c[1])
    return out


def aav(text, scheme):
    """(a+ā count, vowel count) for one text string."""
    m = count(to_slp1(text, scheme))
    return (m["a"] + m["aa"], m["vowels"]) if m else (0, 0)


def _aav_pct(pairs):
    aa = sum(p[0] for p in pairs); nv = sum(p[1] for p in pairs)
    return (100 * aa / nv if nv else float("nan")), nv


def _default_ivc_path():
    """readings_slp1.txt beside this script, else in the current directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "readings_slp1.txt"), "readings_slp1.txt"):
        if os.path.isfile(cand):
            return cand
    return os.path.join(here, "readings_slp1.txt")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="a+ā as % of vowels: Vedic literary vs Sanskrit epigraphy vs IVC decipherment")
    ap.add_argument("--ivc", metavar="FILE", default=_default_ivc_path(),
                    help="IVC readings, one per line (default: readings_slp1.txt beside this script)")
    ap.add_argument("--data", default=os.path.join(here, "DharmicData"),
                    help="cache dir for the Vedic corpora (auto-downloaded here if absent)")
    ap.add_argument("--dharma", default=os.path.join(here, "dharma_cache"),
                    help="cache dir for the DHARMA epigraphy repos (git-cloned here)")
    ap.add_argument("--refresh", action="store_true", help="re-download the Vedic corpora")
    ap.add_argument("--no-fetch", action="store_true", help="don't download Vedic; use baked-in baselines")
    ap.add_argument("--no-epi", action="store_true", help="skip the Sanskrit-epigraphy download/comparison")
    ap.add_argument("--udvedic", metavar="DIR", default=os.path.join(here, "UD_Sanskrit-Vedic"),
                    help="cache dir for the UD Vedic treebank (git-cloned here) for the "
                         "Rigveda by-part-of-speech breakdown")
    ap.add_argument("--extra", metavar="DIR", default=os.path.join(here, "extra_corpora"),
                    help="folder of extra corpora to score: each *.txt = one corpus "
                         "(one inscription per line, scheme auto-detected); *.xml = EpiDoc, "
                         "all pooled as one corpus. Drop e.g. donative/coin-legend files here.")
    args = ap.parse_args()
    IAST = sanscript.IAST

    # 1) Vedic LITERARY rows (live download; baked-in baselines if offline) --------
    vedic = []
    D = ensure_corpora(args.data, refresh=args.refresh, allow_fetch=not args.no_fetch)
    vcorp = [("Rigveda", os.path.join(D, "Rigveda")),
             ("Atharvaveda", os.path.join(D, "AtharvaVeda")),
             ("Yajurveda", os.path.join(D, "Yajurveda", "vajasneyi_madhyadina_samhita.json"))] if D else []
    if vcorp:
        for name, path in vcorp:
            if os.path.exists(path):
                vedic.append((name, corpus_a_aa_vow_pct(load_veda(path))))
    else:
        for name, (agg, _m, _s) in BASELINES.items():
            vedic.append((name.split(" (")[0], agg))

    # 1b) Rigveda BY PART OF SPEECH (UD Vedic treebank) ---------------------------
    #     Does dropping verbs and keeping only names/epithets raise the a+ā share?
    rvpos, rv_nominal_pct = [], None
    up = args.udvedic if os.path.isdir(args.udvedic) else (
         None if args.no_fetch else udvedic_download(args.udvedic))
    forms = rv_pos_forms(up) if up else {}
    if forms:
        grab = lambda keys: [f for k in keys for f in forms.get(k, [])]
        cuts = [("RV — all tokens", list(forms)),
                ("RV — nominal (NOUN+PROPN+ADJ)", ["NOUN", "PROPN", "ADJ"]),
                ("RV — NOUN (incl. theonyms)", ["NOUN"]),
                ("RV — ADJ (epithets)", ["ADJ"]),
                ("RV — VERB (finite)", ["VERB"]),
                ("RV — PRON", ["PRON"])]
        for lab, keys in cuts:
            p, v = _aav_pct([aav(w, IAST) for w in grab(keys)])
            rvpos.append((lab, len(grab(keys)), v, p))
        rv_nominal_pct = rvpos[1][3]

    # 2) Sanskrit EPIGRAPHY (DHARMA), per-corpus + pooled cuts --------------------
    per_corpus, full_pairs, short_pairs, seal_texts, prakrit_pairs = [], [], [], [], []
    if not args.no_epi:
        for label, repo, pat in DHARMA_CORPORA:
            path = dharma_download(repo, args.dharma)
            if not path:
                print(f"[skip] {label}: clone failed (is git installed?)", file=sys.stderr); continue
            cf, cs, ci = [], 0, 0
            for f in sorted(glob.glob(os.path.join(path, pat))):
                full, seal = epidoc_extract(f); full = norm(full); seal = norm(seal)
                if not full:
                    continue
                ci += 1
                p = aav(full, IAST); cf.append(p); full_pairs.append(p)
                if p[1] <= SHORT_MAX_VOWELS:
                    short_pairs.append(p)
                if seal:
                    cs += 1; seal_texts.append(seal)
            if cf:
                cp, nv = _aav_pct(cf)
                per_corpus.append((label, ci, cs, nv, cp))
        # 2b) Prakrit (Middle Indo-Aryan) donative register, same project --------
        for _pl, prepo, ppat in DHARMA_PRAKRIT:
            ppath = dharma_download(prepo, args.dharma)
            if not ppath:
                continue
            for f in sorted(glob.glob(os.path.join(ppath, ppat))):
                full, _s = epidoc_extract(f, want="pra"); full = norm(full)
                if full:
                    prakrit_pairs.append(aav(full, IAST))

    # 4) Extra user-supplied corpora (donatives, coin legends, READ TEI exports...) -
    #    each *.txt = one corpus (one inscription per line); *.xml pooled as EpiDoc.
    extra = []
    if os.path.isdir(args.extra):
        for fp in sorted(glob.glob(os.path.join(args.extra, "*.txt"))):
            lines = [ln.strip() for ln in open(fp, encoding="utf-8") if ln.strip()]
            p, v = _aav_pct([aav(ln, None) for ln in lines])     # scheme auto-detected
            if v:
                extra.append((os.path.splitext(os.path.basename(fp))[0], len(lines), v, p))
        xmls = sorted(glob.glob(os.path.join(args.extra, "*.xml")))
        if xmls:
            pairs, n = [], 0
            for fp in xmls:
                full, _seal = epidoc_extract(fp)
                full = norm(full)
                if full:
                    n += 1; pairs.append(aav(full, IAST))
            p, v = _aav_pct(pairs)
            if v:
                extra.append((f"{os.path.basename(args.extra)}/EpiDoc", n, v, p))

    # 3) IVC decipherment cuts ----------------------------------------------------
    ivc = []
    if os.path.isfile(args.ivc):
        recs = read_reading_records(args.ivc, scheme=sanscript.SLP1)
        uniq = unique_records(recs); uniq8 = [r for r in uniq if r["vowels"] >= 8]
        for lab, rs in [("IVC \u2014 all", recs), ("IVC \u2014 unique", uniq),
                        ("IVC \u2014 unique, \u22658 syll", uniq8)]:
            g = agg_records(rs); ivc.append((lab, g["a_aa_vow_pct"], g["vowels"]))
    else:
        print(f"[note] {args.ivc} not found; skipping IVC rows", file=sys.stderr)

    # ---- Output -----------------------------------------------------------------
    if rvpos:
        print_table("Rigveda by part of speech (UD Vedic Treebank) — a+ā|vowels",
                    ["RV token class", "tokens", "vowels", "a+ā|vow"],
                    [[lab, f"{nt:,}", f"{nv:,}", f"{p:.2f}%"] for lab, nt, nv, p in rvpos],
                    aligns=["<", ">", ">", ">"])

    if per_corpus:
        print_table("Per-corpus Sanskrit epigraphy (full editions) — a+ā|vowels",
                    ["corpus", "inscr", "seals", "vowels", "a+ā|vow"],
                    [[lab, str(ni), str(ns), f"{nv:,}", f"{cp:.2f}%"]
                     for lab, ni, ns, nv, cp in per_corpus],
                    aligns=["<", ">", ">", ">", ">"])

    rows = [[name + " (literary)", "", f"{p:.2f}%"] for name, p in vedic]
    if rv_nominal_pct is not None:
        rows.append(["Rigveda \u2014 names/epithets only (nominal)", "", f"{rv_nominal_pct:.2f}%"])
    if full_pairs:
        rows.append("SEP")
        ea, ev = _aav_pct(full_pairs)
        rows.append([f"Sanskrit epigraphy — all ({len(full_pairs)} inscr)", f"{ev:,} vow", f"{ea:.2f}%"])
        if short_pairs:
            sa, sv = _aav_pct(short_pairs)
            rows.append([f"Sanskrit epigraphy — short (\u2264{SHORT_MAX_VOWELS} vow, {len(short_pairs)})",
                         f"{sv:,} vow", f"{sa:.2f}%"])
        seal_unique = list(dict.fromkeys(seal_texts))
        if seal_unique:
            za, zv = _aav_pct([aav(s, IAST) for s in seal_unique])
            rows.append([f"Sanskrit epigraphy — seal legends ({len(seal_unique)} uniq)",
                         f"{zv:,} vow", f"{za:.2f}%"])
    if prakrit_pairs:
        pa, pv = _aav_pct(prakrit_pairs)
        rows.append([f"Prakrit donatives — Early Andhra ({len(prakrit_pairs)} inscr)",
                     f"{pv:,} vow", f"{pa:.2f}%"])
    if extra:
        rows.append("SEP")
        for lab, n, v, p in extra:
            rows.append([f"[extra] {lab} ({n} inscr)", f"{v:,} vow", f"{p:.2f}%"])
    if ivc:
        rows.append("SEP")
        for lab, p, v in ivc:
            rows.append([lab, f"{v:,} vow", f"{p:.2f}%"])

    print_table("a+ā as % of vowels — literary vs epigraphic vs IVC",
                ["corpus / cut", "sample", "a+ā|vow"], rows, aligns=["<", ">", ">"])


if __name__ == "__main__":
    main()
