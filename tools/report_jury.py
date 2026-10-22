# SPDX-License-Identifier: GPL-3.0-only
"""Verdict links each architectural fix to before/after evidence and losses."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
def rd(n):return json.loads((R/'evidence'/n).read_text())
def main():
 b=rd('jury-before.json');a=rd('jury-after.json');pub=rd('publish-before-after.json');bench=rd('archive-benchmark.json');semantic=rd('jury-semantic-count.json');counter=rd('lightning-counterexample.json')
 assert b['dictionary_mode_without_dictionary_stream_python_accepted'] and not a['dictionary_mode_without_dictionary_stream_python_accepted']
 assert b['dictionary_mode_without_dictionary_stream_native_accepted'] and not a['dictionary_mode_without_dictionary_stream_native_accepted']
 assert b['training_chunks_consumed_for_one_sample_budget']==32 and a['training_chunks_consumed_for_one_sample_budget']==1
 assert not pub['cases']['before']['bytes_preserved'] and pub['cases']['after']['bytes_preserved']
 assert bench['status']=='PASS' and len(bench['rows'])==77
 for n in ['jury-regression.log','jury-sanitize.log','jury-tests.log']:assert 'OK' in (R/'evidence'/n).read_text() and 'FAILED' not in (R/'evidence'/n).read_text()
 def row(case,codec):
  x=next(x for x in bench['rows'] if x['case']==case and x['codec']==codec);return f"| {case} | {codec} | {x['archive_bytes']} | {x['pack_ms']:.2f} | {x['unpack_ms']:.2f} |"
 table='\n'.join(row(c,k) for c in ['noise_1MiB','mixed_files','lattice_1MiB'] for k in ['native-fast','native-balanced','native-lightning','7z-fast-1MiB'])
 text=f'''# PZ: строгий архитектурный аудит, 2026-10-22

Вердикт: экспериментальный архиватор с подтверждёнными исправлениями. Для
безусловной замены7-Zip доказательств нет. Все найденные дефекты этого этапа
имеют воспроизведение; отсутствие любых других дефектов не доказано.

## Критическое исправление: владение опубликованными файлами

До исправления успешный rename папки и последующий EIO на fsync родителя
оставляли флаг временной папки активным. Очистка через её открытый fd удаляла
файлы уже из опубликованного результата. Тест на версии0897e2d подтверждает:
видимая папка существует, но файлов нет. Новый код передаёт владение сразу
после rename; тот же EIO возвращает ошибку долговечности и сохраняет байты.
Исходный архив и файлы пользователя в тесте не затрагиваются: временные fixtures.

Python-декодеры также освобождают старый путь staging после публикации и
возвращают PublicationError вместо маскирующего FileNotFoundError при очистке.
Проверены реальные EIO на fwrite/write/fsync/linkat/renameat2: до публикации
нет конечного результата; после публикации все проверенные байты сохраняются.
Журнал восстановления после потери питания не добавлен; orphan temp остаётся
известным пределом. Ошибка fsync после публикации не означает, что цели нет.

## Другие исправления

- Режим preset dictionary требует FDICT/реального запроса словаря, а не только
  поля mode6. Оба декодера прежде принимали обычный поток; теперь отклоняют.
  Воспроизведения имеют корректные SHA/CRC, поэтому проверяют семантику парсера.
- Обучение раньше объединяло32 фрагмента, прежде чем обрезать до256КиБ.
  Теперь читает только необходимый первый фрагмент. Результат того же префикса
  совпадает; промежуточное объединение сверх лимита устранено.
- Добавлено{semantic['rehashed_structural_cases']} пересчитанных структурных
  атак, C/Python differential checks и сбои публикации с сохранением результата.

## Скорость и размер

Байты включают контейнер, имена и проверки. Время — медиана3 CLI-запусков, мс.

| Данные | Режим | Архив, Б | Упаковка | Распаковка |
|---|---|---:|---:|---:|
{table}

77 комбинаций,231 распаковка с точным набором имён/SHA256. Имена, исходные
байты, базовые версии и пробы находятся в archive-benchmark.json. Синтетические
и проектные данные не являются независимым общим чемпионатом. Условия fsync
различаются; RSS имеет launcher floor. Минимальные требования всего host
процесса не выводятся из размера статических буферов.

LIGHTNING — новый явный opt-in, без изменения default balanced/старого fast.
Гистограмма всего блока отсеивает смещённое распределение; четыре разнесённые
пробы позволяют пропускать полный поиск на вероятном шуме. Это эвристика.
Специально построенный контрпример: balanced/fast{counter['archive_bytes']['balanced']}Б,
LIGHTNING{counter['archive_bytes']['lightning']}Б. Скрывать этот проигрыш нельзя.
Пропуск сжатия сохраняет все исходные байты; полный профиль остаётся доступен.

## Фактически выполнено

- Новая полная регрессия: прежний C codec,24 UDICT,15 Python solid,9 native
  групп;120 cross-language corpora;1200 native random corruptions.
-5 дополнительных jury-групп: rehashed поля, dictionary semantics, генератор
  обучения, post-publish Python failure, counterexample LIGHTNING.
-4 native I/O-группы, включая10 сценариев до/после публикации; отдельное
  воспроизведение дефектного исходника и исправленной версии.
- Native9+jury5+I/O4 групп реально запущены под ASan/UBSan; логи сохранены.
- PZ02/PZ03 page codec в этом этапе не менялся: прежние72 измерения и
  sanitizer evidence сохраняются с совпадающими source hashes.

## Оставшиеся слабые места

| Область | Ограничение |
|---|---|
| Сжатие смешанных файлов | 7-Zip в этом наборе компактнее |
| Быстрый выбор алгоритма | LIGHTNING может сильно проиграть по размеру |
| Мелкие файлы | Индивидуальные fsync замедляют извлечение |
| Метаданные | Только плоские regular files; без дерева/permissions/timestamps |
| Native имена | ASCII; Python допускает UTF8 |
| Доверие | SHA/CRC не аутентифицируют автора архива |
| Обучение | Ограниченный префикс и эвристика словаря; смещение выборки остаётся |
| Ресурсы | Лимиты256МиБ raw/512МиБ archive; no unlimited archives |
| Алгоритмы | zlib/OMEGA, без нового entropy coder, SIMD или доказанного Pareto-router |

Никакого500% общего превосходства, нулевых недостатков или гарантии отсутствия
ошибок не заявлено. GPL/BSD notices сохранены. Main не меняется этим черновиком.
'''
 (R/'JURY-REPORT.md').write_text(text);print('PASS jury report evidence gate')
if __name__=='__main__':main()
