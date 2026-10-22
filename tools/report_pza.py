# SPDX-License-Identifier: GPL-3.0-only
"""Publish only source-linked PZA measurements; disclose every measured loss."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
def main():
 b=json.loads((R/'evidence/pza-benchmark.json').read_text());assert b['status']=='PASS' and len(b['rows'])==60
 for n,h in b['source_sha256'].items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h,n
 for n in ['pza-regression.log','pza-sanitize.log']:
  t=(R/'evidence'/n).read_text();assert 'FAILED' not in t and 'PASS PZA: roundtrips=20000 mutations=60000' in t and 'OK' in t,n
 t=(R/'evidence/pza-assets-python.log').read_text();assert 'Ran 8 tests' in t and 'OK' in t and 'FAILED' not in t
 rows=[]
 for case in sorted({x['case'] for x in b['rows']}):
  for codec in ['pz02','pz03-max','pza-code','pza-x86','pza-bgra','lz4','zstd1','zlib1']:
   for x in b['rows']:
    if (x['case'],x['codec'])==(case,codec):rows.append(f"| {case} | {codec} | {x['raw_bytes']} | {x['packed_bytes']} | {x['encode_ns']/1000:.1f} | {x['decode_ns']/1000:.1f} |")
 table='\n'.join(rows)
 text=f'''# PZA: код и BGRA-снимки, измерения

2026-10-22. Новый профиль без потерь, встроенный в Atomv0.13. C11, no heap,
2048Б pages, фиксированные токены исходников, обратимая нормализация E8/E9,
цветовая декорреляция и planar delta. Составленные из известных методов
фильтры; нет заявления о новом математическом примитиве или правовой новизне.
Спецификация, ограничения и команды — в PZA-ASSETS.md.

## Сравнение

Время в мкс за весь набор страниц.5 батчей,5 encode/101 decode повторов,
медиана в одном native C process. Каждый исходный byte первоначально сравнен.
До2048Б на страницу, без общего словаря/solid между страницами. PZ включает
FNV32, zlib Adler32; zstd checksum отключён, raw LZ4 checksum не имеет. Это
неравные расходы на целостность, не готовые файловые архиваторы.

| Набор | Кодек | Raw, Б | Packed, Б | Encode, мкс | Decode, мкс |
|---|---|---:|---:|---:|---:|
{table}

На gradient BGRA:22758Б PZ02 →1860Б PZA; PZ03 max2429Б. На sensor BGRA:
36687→13865Б; PZ03 max19379Б. Эти данные синтетические. На исходниках выигрыш
скромнее:4359→4206Б и8396→8218Б. На128КиБ готового AtomEFI:98993→98642Б.
На искусственных повторных x86 calls выигрыш намного выше; это узкий шаблон,
не оценка обычных binaries. Нельзя распространять его коэффициент на весь код.

PZA часто упаковывает быстрее PZ03 max и компактнее него на выбранных
изображениях, но PZ02 обычно быстрее. PZA decode некоторых source/frame
наборов медленнее PZ02. LZ4/Zstd остаются сильнее по скорости, Zstd часто
компактнее на коде. PNG-поток не улучшается. Никакого общего превосходства по
скорости/размеру/RAM, максимальной возможной компрессии или500% гарантии нет.

Корпус: исходники проекта, generated C, generated x86, gradient/sensor/noise,
PNG и собственный GOP screenshot. Нет реальных фотографий с камеры или
независимого стандартного набора; результат на них пока не установлен.
Хэши входов включены в pza-corpus.json; генератор — tools/bench_pza.py. EFI берётся из
Atomv0.12.zip, SHA указан в input_provenance. Сжатый размер включает page
headers, не host-файл и не фиксированный словарь в коде. Контексты не равны
всему process RAM. Bench decoder проверяет integrity каждый раз.

## Проверки, реально выполненные

-20000 C roundtrips всех kind0..4,60000 повреждений под ASan/UBSan,
  короткие/нулевые буферы, truncation, bounds. Один альтернативный wire-вариант
  принят с теми же raw байтами; изменённого output в этих пробах не принято.
- Независимые Python-эталоны цветовых и x86 преобразований, прямой token fixture,
  случайные byte/frame контейнеры, все truncations, rehashed structural faults.
-8 Python-групп: exact PNG file roundtrip и exact RGBA8 pixel roundtrip,
  отказ от перезаписи, FIFO/symlinks/лимиты, max≤fast;16битная квантизация и
  потеря анимации предотвращены явным отказом frame. Pillow проверен локально;
  при отсутствии Pillow в CI две adapter-группы помечаются skipped.
- Полная прежняя page/host/jury/router/I/O регрессия и санитайзеры пройдены на
  текущем C-коде; результаты в pza-regression.log/pza-sanitize.log. Старые host
  solid-измерения84 сочетаний не повторялись: solid-код не менялся, их отчёты
  относятся к предыдущему этапу. Новые60 сравнений — только PZA pages.

Fast runtime сравнивает PZ02 с одним профильным кандидатом; прямой transformed
payload или PZ02 после фильтра выбираются по фактическому числу байтов. Дополнительный
host `--effort max` пробует также прежний PZ03 max; его поиск медленнее, а
декодер только исполняет сохранённый вариант. Словарь64 идентификатора заморожен;
его192Б hash/length accelerator не меняет формат.

GOP-capture, отдельный65536Б RAM store и дальнейшая EFI-регрессия относятся к
сборке Atom; см. её REPORT.md. PZAF0001 host wrapper не загружается с диска вEFI.
Стабильные PZ02/PZ03 wire и прежние host profiles не изменены. FNV/SHA —
обнаружение порчи, не authentication. Finite tests не доказывают отсутствие
любых ошибок. GPL/BSD attribution сохранены; внешний software не включён вEFI.
'''
 (R/'PZA-REPORT.md').write_text(text);print('PASS source-linked PZA report with speed/ratio limits')
if __name__=='__main__':main()
