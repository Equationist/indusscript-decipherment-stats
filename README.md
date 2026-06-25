# Running
```
pip3 install -r requirements.txt
python3 a_frequency.py
```
# Results
```
Rigveda by part of speech (UD Vedic Treebank) — a+ā|vowels
──────────────────────────────────────────────────────
RV token class                 tokens  vowels  a+ā|vow
──────────────────────────────────────────────────────
RV — all tokens                34,045  77,623   64.25%
RV — nominal (NOUN+PROPN+ADJ)  16,977  43,812   63.30%
RV — NOUN (incl. theonyms)     12,703  31,729   63.31%
RV — ADJ (epithets)             4,274  12,083   63.28%
RV — VERB (finite)              6,472  18,507   63.49%
RV — PRON                       3,650   5,016   74.46%
──────────────────────────────────────────────────────

Per-corpus Sanskrit epigraphy (full editions) — a+ā|vowels
───────────────────────────────────────────────────
corpus               inscr  seals   vowels  a+ā|vow
───────────────────────────────────────────────────
Daksina Kosala          93     75   64,526   66.20%
Maitraka (Valabhi)      85      0  127,113   70.36%
Badami Calukya          18      0   13,282   67.46%
Kalyana Calukya          3      0    1,192   66.36%
Bhaumakara               1      0      721   70.32%
Eastern Calukya        104     88  119,893   67.97%
Somavamsin              39      3   46,783   66.16%
Bengal charters         59     30   92,369   66.07%
Bengal dedications       5      0      444   62.16%
Early Andhra (Skt)      36      0   12,624   68.56%
Arakan                   1      0       65   66.15%
Pallava                 91      5   29,893   66.85%
Khmer (SE Asia)        309      0  200,962   62.34%
Nusantara (SE Asia)     82      0   18,440   61.01%
Campa (SE Asia)         47      0   17,800   61.66%
───────────────────────────────────────────────────

a+ā as % of vowels — literary vs epigraphic vs IVC
─────────────────────────────────────────────────────────────────────
corpus / cut                                          sample  a+ā|vow
─────────────────────────────────────────────────────────────────────
Rigveda (literary)                                             60.65%
Atharvaveda (literary)                                         62.34%
Yajurveda (literary)                                           62.04%
Rigveda — names/epithets only (nominal)                        63.30%
─────────────────────────────────────────────────────────────────────
Mitanni Indo-Aryan superstrate (names/numerals)      329 vow   60.18%
─────────────────────────────────────────────────────────────────────
Sanskrit epigraphy — all (973 inscr)             746,107 vow   65.99%
Sanskrit epigraphy — short (≤60 vow, 227)          3,650 vow   63.34%
Sanskrit epigraphy — seal legends (65 uniq)          898 vow   66.15%
Prakrit donatives — Early Andhra (173 inscr)      17,735 vow   67.68%
─────────────────────────────────────────────────────────────────────
IVC — all                                         11,962 vow   94.98%
IVC — unique                                       7,093 vow   95.35%
IVC — unique, ≥8 syll                                914 vow   97.92%
─────────────────────────────────────────────────────────────────────
```
