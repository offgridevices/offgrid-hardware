# Ridge 3: the datasheets `verify.py` reads

`../src/verify.py` checks the figures and pin tables copied into the design
against the makers' own documents, read from a folder that the environment
variable `RIDGE3_DATASHEETS` names.  The datasheets are not in this
repository: downloaded datasheets are not committed.  Without the folder
those checks SKIP; with it, each file below must be there under exactly
this name.

```
RIDGE3_DATASHEETS=/path/to/datasheets python3.12 src/verify.py     # from ridge-3/
```

## The files

Each is the maker's document as named below, saved as a PDF, with its text
beside it as `.txt`.  `verify.py` reads only the `.txt`, except for the
Artery datasheet, whose pin table it reads from the PDF itself; keep the
other PDFs beside their text to make it again.  The
document numbers and revisions are the ones `verify.py` (or `src/parts.py`,
`sim/data.py`) quotes; where none is quoted, the column says so.

| File | Part | Document, as the code quotes it | What `verify.py` takes from it |
|---|---|---|---|
| `artery_AT32F421.pdf`, `artery_AT32F421.txt` | Artery AT32F421G8U7 (ESC MCUs) | Datasheet v2.02 (2023.10.17) | QFN-28 pin table (table 5), VDD range (table 11), supply current (table 19), FTa pins |
| `diodes_BSS138DW.txt` | Diodes BSS138DW (FC thermostat) | DS30203 rev 16-2 | SOT-363 pinout |
| `ifx_ISZ023N06LM6.txt` | Infineon ISZ023N06LM6 (ESC FETs) | Rev 2.0 (2024-05-06, `parts.py`) | V(BR)DSS, VGS, RDS(on) at 10 V and 4.5 V, Qg |
| `ifx_S25FL128L.txt` | Infineon S25FL128L (blackbox flash) | 002-00124 rev *L | WSON pinout (figure 3), JEDEC ID (table 51) |
| `lcsc_NDK_NX3225GD_STD_CRA_3.txt` | NDK NX3225GD-8MHZ-STD-CRA-3 (FC crystal), as LCSC serves it | not quoted | Load capacitance |
| `murata_BLM03AX601SN1D.txt` | Murata BLM03AX601SN1D (ESC channel beads) | JENF243A-0020AD-01 | Impedance, current rating, resistance |
| `murata_NCU15XH103F60RC.txt` | Murata NCU15XH103F60RC (ESC FET thermistors) | NTC catalogue R44E | B constants; the XH103 resistance-temperature table the AM32 `NTC_table` is built on |
| `tdk_ICM-42688-P.txt` | TDK ICM-42688-P (the gyro's same-pad second source) | DS-000347 | WHO_AM_I, unused-pin rules (table 10) |
| `tdk_IIM-42652.txt` | TDK IIM-42652 (FC gyro) | DS-000440 | WHO_AM_I, full scales (tables 1-2), anti-alias filter (section 5.3), unused-pin rules (table 10) |
| `tdk_SPM6530T-HZ_lcsc.txt` | TDK SPM6530T-150M-HZ (FC 5 V and 9 V inductors), as LCSC serves it | not quoted | Saturation and temperature-rise currents |
| `tdk_TFM252012ALMA.txt` | TDK TFM252012ALMAR47MTAA (FC 3.3 V inductor) | not quoted | Saturation current |
| `ti_drv8320.txt` | TI DRV8320H (ESC gate drivers) | SLVSDJ3D (March 2022, `sim/data.py`) | Pin table (table 6-1), VM, logic levels, DVDD, gate drive, IDRIVE levels, VDS trip, dead time |
| `ti_ina186.txt` | TI INA186A3 (ESC current sense) | SBOS318B | Pin table (table 5-1), gains, supply current and range |
| `ti_lmr38020.txt` | TI LMR38020F (FC 5 V and 9 V supplies) | SNVSC40E | Pin table (table 6-1), VREF, enable thresholds, current limit, input range, RT equation |
| `ti_tmp390.txt` | TI TMP390A2 (video-supply thermostat) | SBOS904A | Pin functions, SETA trip points (table 7-1), hysteresis |
| `ti_tps628501.txt` | TI TPS628501 (FC 3.3 V buck) | SLUSEC8C | Pin table (table 5-1), VFB and its accuracy, output current, current limit |

No download address is recorded for these files.  The one maker's link
to any of them in this repository is
<https://www.ti.com/lit/ds/symlink/lmr38020.pdf> (in `research/`); whether
it still serves revision SNVSC40E was not checked.

## How the `.txt` files were made

Twelve are `pdftotext -layout` output (poppler-utils 24.02.0):

```
pdftotext -layout NAME.pdf NAME.txt
```

`ti_lmr38020.txt`, `ti_tmp390.txt`, `ti_tps628501.txt` and
`tdk_TFM252012ALMA.txt` are not: `verify.py`'s patterns for them expect one
table cell per line.  They are PyMuPDF's text (PyMuPDF 1.28.2, as pinned in
`../requirements.txt`), each page's `get_text()` joined with a newline,
which reproduces the local copies byte for byte:

```
python3.12 -c "import sys, pymupdf; d = pymupdf.open(sys.argv[1]); \
  open(sys.argv[2], 'w').write('\n'.join(p.get_text() for p in d))" NAME.pdf NAME.txt
```

## The local copies

The copies `VERIFICATION.md` was made with, by SHA-256.  A newer revision
of a datasheet gives other hashes and may move a figure a pattern looks
for; then `verify.py` fails that check rather than skipping it, and the
pattern (or the design) is updated from the new document.  From inside the
folder, `sha256sum -c` checks a copy against these lines.

```
549f03d7f8d31eb7b51fa9ffd782a8e8ac2b2aa9a5c0e130bed852370ee1b3ed  artery_AT32F421.pdf
873d985eb2d4f00d3659d5b62c9640807b3824b3dd597d00cfa3a3929fac2be1  artery_AT32F421.txt
f5b0b172378a1acc517e17be751e1f540b228a302054f42da0fc1eaf772f84e9  diodes_BSS138DW.pdf
516d9a48b4a628da96c050ae9fd99772209731ba95e60e4ac61ded81dd35f7c2  diodes_BSS138DW.txt
0aea767a17af6fd0f4abc3dedde66d3ed128073fb2ad05b7e3786b298cc0ba0e  ifx_ISZ023N06LM6.pdf
edcd8488fdeea91efc172d893ac36871d6970ae90b9f28fc6d1f672851fb7102  ifx_ISZ023N06LM6.txt
70f250f6e6fc197ebf9b3ca676ecc73d5ca9b8c896b216c0e81afa575e0877bb  ifx_S25FL128L.pdf
d6133670d122657aeb4a4a105205bbe4d023eacddb3000441eddeabc702d049d  ifx_S25FL128L.txt
0bcc150e366d3b1b2394f5380e4ae4efcc23a40ecaf5f5c4b11960af42becb38  lcsc_NDK_NX3225GD_STD_CRA_3.pdf
74be3ad6b54833b5cfa01441163d06a4c6c5a7a0aad3d008f197de77f4687bfe  lcsc_NDK_NX3225GD_STD_CRA_3.txt
572316bb5fcf00e736c3c9f4388462911f99e78e056a6fa6a52dd351a91b4caf  murata_BLM03AX601SN1D.pdf
e648c168811b764bab0425227068a1d6f0d56b8114deba31a4909936671874ab  murata_BLM03AX601SN1D.txt
db57b5de9d314819fdd0063ca6c20d7e53151c2aa6520806f410b01ad89c9ceb  murata_NCU15XH103F60RC.pdf
7e569597ca84b2fbaa3d1a03133347b42b6c8c1d236a33d1e99626a2183356d6  murata_NCU15XH103F60RC.txt
9c6b57b0a2e45cf0251dd2423878573bd4da46e0cc2faa93dc558c28af51300a  tdk_ICM-42688-P.pdf
df4396f5b45e2032025e746efb0abd7acf3c6f8fd21f8e31c95eb084395a9e00  tdk_ICM-42688-P.txt
88aedb9e2604f8adb6421a057ee4922b484b3464ca4c0ea3edaf5fa48f782615  tdk_IIM-42652.pdf
bc0e1661d48b72c2124788193589236ee0501a5c82905b238af94c0a3f558fc0  tdk_IIM-42652.txt
f615575152a649c309003fd1e0e86b522b38c167e5f3377354b1e75c4e1fb37d  tdk_SPM6530T-HZ_lcsc.pdf
05e1d77c3e677e09d3afc1794599206c820c40e006ceefb999f5fc027ccaa2ac  tdk_SPM6530T-HZ_lcsc.txt
759ed45e7c629ad40577632e73de9a06b0c4f44c0dd36746a4233ff48ee46276  tdk_TFM252012ALMA.pdf
2e363ad464cc1a2816c4b0f2a0f293dce96b0d66de49a715871d047b89cbf136  tdk_TFM252012ALMA.txt
dd8386c972e8d0a57278e432da6e9d8b2bc2f73768dd97eac69594da20d24208  ti_drv8320.pdf
e9fc1e9f6f2933fdb2c20abbc1ff72bea9de2f427f3cc22a88cf40a92a603f49  ti_drv8320.txt
9a3502cad52a61125f7da8da07b0794795eab0c9563fb01db6df22ccfc5aebe6  ti_ina186.pdf
7f85aaa18f4870f2a22d6a82bbc488a12ea5dc6668f485c0a6c01ecfad792f2f  ti_ina186.txt
da2ed000a8525ec9794e943e4cda8e6e3433515b2be24d5ead1d4478916b1585  ti_lmr38020.pdf
a5341fb6a4e15084bb24f3b81d96fe3177dedb955e70cca919480a80040d75fe  ti_lmr38020.txt
49bba45b91c8e4671d75692696c183eebd4f075ee674be362d84286b41389a95  ti_tmp390.pdf
54f5cddfc464e7dc6d7a721a773999a91adaa5176cd7993c732bfe749ae3e686  ti_tmp390.txt
640e5bca2f5a0382ac9237f1952e9666a21c09215dc7a4595f355af2f1464930  ti_tps628501.pdf
a54fa37bff5c0835231f3985ed44e9f0200d863edfda869afef038bcf589d364  ti_tps628501.txt
```

A new part whose figures `verify.py` checks adds its file here: the name
`verify.py` uses, the document and its revision, how its text was made, and
the hashes ([`CHANGING.md`](CHANGING.md), the loop's step 3).
