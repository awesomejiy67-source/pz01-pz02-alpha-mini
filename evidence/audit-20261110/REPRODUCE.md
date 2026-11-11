# Воспроизведение Windows-аудита

Рабочая директория — корень репозитория. Переносные инструменты первоначально
установлены в `../.audit-tools`, внутри предоставленного workspace; системные
настройки и CODEX_HOME не менялись. URL и SHA256 архивов — в
`toolchain-downloads.json`. Нужны Python 3.14 и LLVM/MinGW из этого manifest.
Вместо приведённых путей можно указать собственные абсолютные пути к clang/git.

```powershell
$cc = (Resolve-Path ../.audit-tools/llvm/llvm-mingw-20261104-ucrt-x86_64/bin/clang.exe).Path
$git = (Resolve-Path ../.audit-tools/git/cmd/git.exe).Path
# Новые результаты: опубликованные измерения не перезаписываем.
$env:PZ_AUDIT_EVIDENCE = "$PWD/build/reproduction-20261110"
New-Item -ItemType Directory -Force $env:PZ_AUDIT_EVIDENCE | Out-Null
Copy-Item evidence/audit-20261110/corpus.json,evidence/audit-20261110/inputs.zip $env:PZ_AUDIT_EVIDENCE
python -X utf8 tools/audit_dependencies.py
python -X utf8 tools/audit_windows.py --cc $cc --git $git build --label baseline
python -X utf8 tools/audit_windows.py --cc $cc --git $git build --label final
python -X utf8 tools/audit_checks.py --cc $cc --label final differential
python -X utf8 tools/audit_checks.py --cc $cc --label baseline sanitize
python -X utf8 tools/audit_checks.py --cc $cc --label final sanitize
python -X utf8 tools/audit_checks.py --cc $cc --label final property
python -X utf8 tools/audit_resources.py --cc $cc --label final
# Не запускать одновременно со сборкой, тестами и измерением памяти.
python -X utf8 tools/audit_windows.py --cc $cc --git $git bench --label final --batch-ms 100
python -X utf8 tools/audit_report.py
```

Команды вызывают реальные источники `models/...`, обходя Git symlink stubs на
Windows. Флаги production: `-O2 -std=c11 -Wall -Wextra -Werror
-Wno-misleading-indentation`; sanitizer: `-O1 -g -std=c11
-fsanitize=address,undefined -fno-omit-frame-pointer`. Все команды, return codes,
stdout/stderr сохранены в JSONL. Baseline берётся через `git show` указанного SHA,
не из старых benchmark-fixtures. Адаптер бенчмарка одинаков у обеих версий.

`inputs.zip` содержит ровно проверенные байты; каждый распакованный файл
проверяется по `corpus.json`. Это важно для PE (зависит от компилятора/linker)
и JPEG→BGRA (зависит от декодера). Исходный JPEG — libjpeg-turbo 3.1.2
`testimages/testorig.jpg`, SHA256
`acc6ec555d41d15b368320edaa3b20958ee6fa97cb6e4a18d1213d5ae8bec73b`.
Фото-BGRA — первые 65536 байт декодированных Pillow 12.0.0 пикселей, без
масштабирования. Это один fixture, не репрезентативный фотокорпус.
Лицензии сторонних входов сохранены в `corpus-licenses`; код проекта сохраняет
GPL/attribution. Использование IJG-образца/декодирования основано в том числе на
работе Independent JPEG Group. PE — собственная сборка baseline quickstart,
не выборка сторонних приложений. Внешние библиотеки нужны только измерителю.

Для существующих benchmark-скриптов и переносимых Python data-тестов:

```powershell
New-Item -ItemType Directory -Force build/audit/tmp | Out-Null
$env:TEMP = "$PWD/build/audit/tmp"
$env:TMP = $env:TEMP
python -m pip install --no-cache-dir --target build/audit-deps/python Pillow==12.0.0
python -X utf8 tools/audit_existing.py --cc $cc
```

Полные Python host suites в этой команде **ожидаемо не проходят на Windows**:
нет POSIX O_NOFOLLOW/mkfifo, native host требует sys/syscall.h. Это фиксируется
отдельно от пяти успешно проходящих Python data-групп. `libFuzzer` отклонён
clang для MinGW; `property` — реально выполненный fallback, не coverage-guided
libFuzzer. Для компилятора, поддерживающего его, harness — `tests/fuzz_pages.c`.

Воспроизведение найденного дефекта: собрать `tests/test_pza_transform_bounds.c`
с исходниками baseline из `build/audit/baseline`, как в
`defect-reproduction.jsonl`: ошибка `raw=1025 filtered=2050`. С текущими
исходниками тот же тест проходит. `rejected-palette.patch` — только сохранённый
отклонённый эксперимент; в рабочем коде его нет. Полные промежуточные пробы
сохранены с префиксами palette/identity; concurrent-серия не принималась как
чистое измерение.

Следующий этап в Linux checkout этой ветки, с уже установленными зависимостями
C11/GNU Make, Python, zlib/OpenSSL, LZ4/Zstd и 7-Zip:

```sh
make all test example test-host test-jury
make sanitize sanitize-host
python3 tools/bench_archives.py
```

Последняя команда пока использует исторический режим трёх повторов проекта.
Перед новым host-сравнением нужно отдельно доработать его до пяти повторов с
прогревом, чередованием и сырыми пробами; иначе он не удовлетворяет критериям
этого аудита. Linux, Windows host, UEFI/QEMU и CI этим документом не объявляются
проверенными. Автоматического push/merge не было. Отправка локальной ветки:

```sh
git push -u origin audit/windows-pages-20261110
```
