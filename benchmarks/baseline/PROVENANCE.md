# Frozen test fixtures, not current implementations

`pagezip.c`, `pz01.c`, `checksum.c`, `README-original.md` are exact bytes from
awesomejiy67-source/pz01-pz02-alpha-mini at
`d0064614808f24fdd4fab5722f789f7ffc8f0e7c` (branch Main).

`udict.py` is exact code from the supplied
PZ03-ALFA-v0.2-UDICT-RESEARCH-SOURCE.zip, SHA-256
`5cc961e6a12fb282d0bf92c907cfe2bfc1e4667f49f6ca379336cf34af7c0ae6`.
That implementation was distributed under the same project's GPL terms.
It intentionally retains defects to reproduce before/after audits.
Do not use it to handle untrusted or changing input.

The copied historical UDICT benchmark reports under experimental/udict are
original records, not results for the new native engine. Current evidence is
under evidence/. All tests generate disposable input in temporary directories.
