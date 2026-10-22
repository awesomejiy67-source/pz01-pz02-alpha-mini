The opt-in adaptive solid router retains the balanced prefix winner and tests a second
candidate selected from separated windows. See [ROUTER-REPORT.md](ROUTER-REPORT.md)
for old/new measurements, latency costs and the remaining losses to7-Zip.

Current jury audit: [JURY-REPORT.md](JURY-REPORT.md). New tests reproduce a
post-publication cleanup defect and verify preservation after injected I/O
failures. `make test-jury` and `make sanitize-host` exercise these cases.
`lightning` is an opt-in sampling profile with a measured compression loss on
adversarial input; choose `balanced` when that tradeoff is unsuitable.

# Audited research branch: PZ03 pages + solid host engine

Current results and limitations: [AUDIT-REPORT.md](AUDIT-REPORT.md).
Format boundaries: [PZ03-FORMATS.md](PZ03-FORMATS.md). Original page API stays
PZ02; opt-in predictor API is `src/pz03_page.h`. The Linux solid CLI is a
separate experimental archiver and uses zlib/OpenSSL; it is not the no-heap
2048-byte UEFI codec. Historical mini-release documentation follows below.

```sh
make all test example
make test-host             # Python3, zlib and OpenSSL development packages
make sanitize sanitize-host
./build/solid-native pack balanced sample.pzs input1.txt input2.bin
./build/solid-native verify sample.pzs
./build/solid-native unpack sample.pzs new-output-directory
make benchmark             # also needs liblz4/libzstd development headers
python3 tools/bench_archives.py  # set PZ_7ZIP=/path/to/7zz if not on PATH
python3 tools/report_results.py
```

The native solid CLI currently accepts flat ASCII names only. It refuses
existing outputs and symlinks; raw files are capped at256MiB in total.
Python `experimental/solid.py` supports UTF8 names. See the format document
for integrity, durability and metadata limits. The report preserves measured
losses versus 7-Zip/Zstd/LZ4, rather than claiming a universal win.

---

<div align="center">

# ⚡ PZ01 × PZ02
### ✦ ALPHA MINI • N.A.N.O. BOOT TECH ✦

**Tiny Codecs. Big Ambitions.**  
*Миниатюрные алгоритмы. Большие амбиции.*

**by [awesomejiy67](https://github.com/awesomejiy67-source)**

`C11` · `No heap allocations` · `2 KiB pages` · `PZ01 backward compatibility` · `GPL-3.0-only`

**[English](#-english) · [Русский](#-русский)**

---

</div>

## 🇬🇧 English

### Two tiny lossless page codecs. One mission: make every byte count.

**PZ01 Alpha Mini** is the original bounded LZ-style page codec from the Atom Lab experiment. **PZ02 Alpha Mini** is its faster-packing successor, featuring bounded hash-chain matching, long-run commands and a packed small-alphabet mode. PZ02 **decodes both PZ01 and PZ02 pages**.

> **N.A.N.O.** = **Next-generation Adaptive Nano Operations** — a proposed expansion of the project brand.

| Feature | PZ01 Alpha Mini | PZ02 Alpha Mini |
| :-- | :-- | :-- |
| Lossless page codec | ✅ | ✅ |
| Maximum raw page | 2,048 bytes | 2,048 bytes |
| Encoding format | `PZ01` | `PZ02` |
| 16-byte header | ✅ | ✅ |
| Output checksum (FNV-1a, non-cryptographic) | ✅ | ✅ |
| Heap-free codec | ✅ | ✅ |
| Bounded hash-chain match search | — | ✅ |
| Long-run and extended-match commands | — | ✅ |
| Bit-packed small alphabets | — | ✅ |
| Decode old PZ01 pages | ✅ | ✅ |

**Measured on the Atom dictionary (20,951 original bytes, 12 pages):**

| Codec | Compressed size | Space saved |
| :-- | --: | --: |
| PZ01 | 12,007 bytes | 42.7% |
| **PZ02** | **10,780 bytes** | **48.5%** |

The measured PZ02 pack time dropped from 6.889 ms to 0.597 ms and unpack time from 0.133 ms to 0.125 ms on one native Linux test run. These are historical project measurements, **not universal guarantees**. The original private Atom corpus is not included; see [benchmark details](docs/BENCHMARKS.md).

### Quick start

Requires a C11 compiler and GNU Make. No external library is needed to build or test the codecs.

```bash
make test              # PZ01 and PZ02 correctness + backward-compatibility checks
make all               # also builds build/libnano_pz.a
make example           # builds and runs a tiny PZ01/PZ02 example
make sanitize          # optional: AddressSanitizer + UndefinedBehaviorSanitizer
```

**APIs:** `pz01_pack()` / `pz01_unpack()` for PZ01 and `page_pack()` / `page_unpack()` for PZ02. See [`src/pz01.h`](src/pz01.h) and [`src/pager.h`](src/pager.h). All I/O buffers are caller-managed, must not overlap, and failed decode output must be discarded.

### ⚠️ Alpha limitations

- Designed for bounded pages, **not** standard `.zip` archives.
- No compression stream API, authentication or tamper-proofing.
- FNV-1a is an **error-detection checksum**, not a cryptographic signature.
- Embedded/UEFI validation is still outstanding; native Linux testing is not a substitute.
- Compression ratio and speed depend on input data and platform.

### Copyright, license & attribution

**Copyright © 2026 awesomejiy67** (public designation supplied by the project owner; legal title to all components has not been independently established). Source is released under **GNU GPL-3.0-only** with reasonable preservation of the attribution notice, as described in [`ATTRIBUTION.md`](ATTRIBUTION.md), where authorized by the rights holder.

You may use and redistribute the code in other applications **subject to GPL-3.0-only obligations**, including credit and applicable source-code requirements. Crediting the author **alone** does not exempt closed-source combined software from GPL. See [`LICENSE`](LICENSE) and [`docs/LICENSING_AND_INTEGRATION.md`](docs/LICENSING_AND_INTEGRATION.md).

---

## 🇷🇺 Русский

### Два миниатюрных алгоритма сжатия без потерь. Одна цель — ценить каждый байт.

**PZ01 Alpha Mini** — исходный постраничный кодек сжатия на основе поиска повторов из лаборатории Atom. **PZ02 Alpha Mini** — улучшенная версия с быстрым ограниченным поиском совпадений, длинными сериями повторений и битовой упаковкой небольших алфавитов. PZ02 **умеет распаковывать страницы обоих форматов**.

**N.A.N.O.** — *Next-generation Adaptive Nano Operations*, «адаптивные нанотехнологии вычислений нового поколения» (предлагаемая расшифровка бренда).

| Возможность | PZ01 Alpha Mini | PZ02 Alpha Mini |
| :-- | :-- | :-- |
| Сжатие без потерь | ✅ | ✅ |
| Максимальная страница | 2048 байт | 2048 байт |
| Заголовок 16 байт | ✅ | ✅ |
| Проверка восстановленных данных FNV-1a | ✅ | ✅ |
| Без выделения памяти в куче | ✅ | ✅ |
| Быстрый поиск повторов | — | ✅ |
| Длинные серии / совпадения | — | ✅ |
| Битовая упаковка малого алфавита | — | ✅ |
| Чтение старых страниц PZ01 | ✅ | ✅ |

**Пример: словарь Atom размером 20 951 байт:**

- **PZ01:** 12 007 байт — экономия 42,7%.
- **PZ02:** 10 780 байт — экономия 48,5%.
- В одном тестовом прогоне упаковка ускорилась примерно в 11,5 раза; распаковка улучшилась незначительно. На других данных выигрыш может быть иным.

### Запуск тестов

```bash
make test
make all
make example
make sanitize          # при наличии ASan/UBSan
```

Устанавливать LZ4, zlib или Zstandard для работы самих кодеков **не требуется**. Они нужны только для дополнительного сравнительного тестирования (`make benchmark`).

### Ограничения альфа-версии

Это **не архиватор ZIP**, а кодеки для небольших страниц данных. Проверка FNV-1a не защищает от злонамеренной подмены. Вход и выход не должны перекрываться; результат неудачной распаковки необходимо отбросить. Новая UEFI-сборка ещё не испытана в QEMU.

### Лицензия и указание автора

Проект распространяется под **GNU GPL-3.0-only**, с условием сохранения разумного уведомления об авторстве из [`ATTRIBUTION.md`](ATTRIBUTION.md) в той мере, в какой правообладатель вправе его установить.

**N.A.N.O. Boot Tech — by awesomejiy67.** Использовать в других программах можно, **если соблюдаются условия GPLv3**. Одного указания автора недостаточно, чтобы обойти обязательства GPL для распространяемой объединённой программы.

---

<div align="center">

**✦ N.A.N.O. BOOT TECH ✦**  
*Small footprint. Carefully measured. Open for research.*  
*Малый размер. Честные измерения. Открыто для исследований.*

</div>
