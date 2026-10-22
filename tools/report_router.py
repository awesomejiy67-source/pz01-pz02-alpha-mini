# SPDX-License-Identifier: GPL-3.0-only
"""Evidence gate for the optional adaptive router; keep speed/ratio losses."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
def rd(n):return json.loads((R/'evidence'/n).read_text())
def main():
 t=rd('router-tests.json');b=rd('router-benchmark.json');a=rd('archive-benchmark.json');old=rd('archive-benchmark-v011.json')
 assert t['status']==b['status']==a['status']=='PASS' and t['corpora']==48 and t['regressions']==0
 assert len(a['rows'])==84 and b['verified_extractions']==80
 assert t['current_source_sha256']==hashlib.sha256((R/'experimental/native/solid_native.c').read_bytes()).hexdigest()
 for name,h in b['source_sha256'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h
 for n in ['v012-regression.log','v012-sanitize.log','v012-native-final.log','v012-native-final-sanitize.log']:
  log=(R/'evidence'/n).read_text();assert 'OK' in log and 'FAILED' not in log and 'ERROR: AddressSanitizer' not in log,n
 # Preserve current standard corpus sizes for every previously measured native profile.
 for row in a['rows']:
  if row['codec'] in ['native-fast','native-balanced','native-lightning']:
   before=next(x for x in old['rows'] if (x['case'],x['codec'])==(row['case'],row['codec']))
   assert row['archive_bytes']==before['archive_bytes'] and row['input_sha256']==before['input_sha256']
 table='\n'.join(f"| {x['case']} | {x['archive_bytes']['before']} | {x['archive_bytes']['after']} | {x['pack_ms']['before']:.2f} | {x['pack_ms']['after']:.2f} |" for x in b['rows'])
 comp='\n'.join(f"| {case} | {codec} | {x['archive_bytes']} | {x['pack_ms']:.2f} | {x['unpack_ms']:.2f} |" for case in ['mixed_files','lattice_1MiB','noise_1MiB'] for codec in ['native-balanced','native-adaptive','7z-fast-1MiB'] for x in a['rows'] if (x['case'],x['codec'])==(case,codec))
 text=f'''# PZ: adaptive router, проверенный компромисс

2026-10-22. Исправлено смещение выборки в дополнительном профиле `adaptive`.
Режим по умолчанию `balanced` оставлен прежним: больше анализа стоит времени.
Формат PZ03SL01 и декодер не изменены; новый entropy coder не заявлен.

## Архитектура

Раньше balanced выбирал один predictor по первым4096байтам блока. В adaptive
этот кандидат сохраняется и соперничает с победителем четырёх разнесённых
окон по1024байта. Начала окон выровнены по256байтам; predictor каждого окна
сбрасывается отдельно. Нет ложных переходов через края соединённых окон.
Tie-break одинаков в C/Python. Не более двух полных predictor encodes;
выбор делается по фактическому размеру payload с метаданными.

Сохранение прежнего кандидата означает: каждый блок adaptive не больше
balanced при тех же входных байтах/истории. История зависит от raw, поэтому
свойство распространяется на полный архив. RAW, обычный zlib и словарь также
сохраняются. Это не обещание ускорения и не гарантия выбора лучшего из6фильтров.
Полный max остаётся доступен. В C используются прежние рабочие буферы;
дополнительная постоянная арена не выделяется. Минимальные требования всего
host-процесса и превосходство по RAM из этого не следуют.

## Предыдущий balanced против adaptive

Медиана5 перемешанных CLI-запусков каждой версии,80 извлечений с проверкой
полного набора имён/байтов. Размер включает контейнер и имена. Время, мс.

| Набор | balanced, Б | adaptive, Б | balanced упаковка | adaptive упаковка |
|---|---:|---:|---:|---:|
{table}

Семь обычных проектных/сгенерированных наборов сохранили размер. Специальный
shift64KiB меняет XOR-подобное начало на арифметические строки; это диагностический
синтетический пример, не общий победный коэффициент. Дополнительный поиск
замедляет упаковку и потому не включён в default. Время включает запуск,
I/O и fsync; аппаратная изоляция не обеспечена. QEMU-регрессия могла работать
в фоне. Сырые пробы и хэши входа включены в router-benchmark.json.

## Конкуренты: тот же текущий прогон

Медиана3 CLI-запусков. Разные durability/RSS policies ограничивают сравнение.

| Набор | Кодек | Архив, Б | Упаковка, мс | Распаковка, мс |
|---|---|---:|---:|---:|
{comp}

Смешанные файлы по-прежнему хуже7-Zip по размеру. Линейно изменяющиеся строки
дают узкую победу по размеру. Скорость, объём и аппаратные требования одновременно
на всех типах данных не выиграны. Независимого стандартного корпуса здесь нет.

## Реально выполненные проверки

-48 диагностических/контрольных корпусов: {t['wins']} выигрыша и{t['ties']} равенства,
  ноль увеличений относительно balanced;288 проверенных восстановлений файлов.
- C/Python adaptive archives побайтно совпадают; старый decoder читает новые
  и наоборот. fast/balanced/max/lightning сохранили побайтный fixture output.
- Полная регрессия host и прежнего page codec;120 random C/Python корпусов
  теперь распределены по всем пяти профилям,1200 порченных архивов.
- Native9+jury5+router1+I/O4 группы прошли ASan/UBSan на финальном коде.
  Новые пяти-профильные native tests отдельно повторены под sanitizer.
-84 сочетания кодек/набор,252 распаковки с точными именами/SHA256. Байтовые
  размеры старых native-fast/balanced/lightning совпали с предыдущим прогоном.
- PZ02/PZ03 page-код не менялся: прежние72 измерения сохранены с совпадающими
  хэшами. Host adaptive не встроен в AtomEFI и не применяется к2048Б pages.

Ограничения остаются: ограниченные history/фильтры, эвристика проб, ASCII-имена
native, flat regular files, отсутствие metadata/authentication/crash journal,
fsync-цена мелких файлов. LIGHTNING по-прежнему имеет известный проигрыш на
скрытой между пробами структуре. Никаких «все ошибки устранены» или500% общих
побед не заявлено. GPL-3.0-only и BSD-уведомления сохранены.
'''
 (R/'ROUTER-REPORT.md').write_text(text);print('PASS adaptive router report with measured costs')
if __name__=='__main__':main()
