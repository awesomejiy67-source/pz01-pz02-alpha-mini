"""Generate auditable comparison tables; no timing values are hand-written."""
import csv,json,math,pathlib,statistics
import audit_windows as a
def med(x):return statistics.median(x)
def write_csv(name,rows):
    with (a.E/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def section(text,prefix):
    return sum(int(line.split()[1]) for line in text.splitlines() if line.startswith(prefix+' '))
def main():
    result=json.loads((a.E/'final-benchmark.json').read_text());data=result['rows']
    resources=json.loads((a.E/'final-resources.json').read_text());memory={(x['case'],x['codec']):x for x in resources['memory']}
    index={(x['case'],x['codec'],x['variant']):x for x in data};rows=[];regressions=[]
    for after in data:
        if after['variant']!='final':continue
        before=index[after['case'],after['codec'],'baseline'];assert all(len(after[k])==5 for k in ['encode_ns','decode_ns'])
        row=dict(case=after['case'],split=after['split'],codec=after['codec'],raw_bytes=after['raw_bytes'],pages=after['pages'],before_bytes=before['packed_bytes'],after_bytes=after['packed_bytes'],wire_identical=before['wire_sha256']==after['wire_sha256'])
        for direction in ['encode','decode']:
            for label,variant in [('before',before),('after',after)]:
                values=variant[direction+'_ns'];row[direction+'_'+label+'_us']=med(values)/1000;row[direction+'_'+label+'_min_us']=min(values)/1000;row[direction+'_'+label+'_max_us']=max(values)/1000
            change=(row[direction+'_after_us']/row[direction+'_before_us']-1)*100
            row[direction+'_change_percent']=change
            if change>0:regressions.append(dict(case=row['case'],split=row['split'],codec=row['codec'],direction=direction,change_percent=change,before_us=row[direction+'_before_us'],after_us=row[direction+'_after_us']))
        for label,variant in [('before','baseline'),('after','final')]:
            for field in ['peak_working_set','private_bytes']:
                values=[v[field] for v in memory[row['case'],row['codec']]['samples'][variant]]
                row[field+'_'+label]=med(values);row[field+'_'+label+'_min']=min(values);row[field+'_'+label+'_max']=max(values)
        rows.append(row)
    assert len(rows)==len(json.loads((a.E/'corpus.json').read_text()))*9
    write_csv('comparison.csv',rows);write_csv('all-time-regressions.csv',regressions)
    pza=[r for r in rows if r['codec'].startswith('pza-')];validation=[r for r in pza if r['split']=='validation']
    geom=math.exp(sum(math.log(1+r['encode_change_percent']/100) for r in validation)/len(validation))
    code={label:section(r['sections'],'.text') for label,r in resources['objects'].items()}
    frames={label:r['stack_frames'] for label,r in resources['objects'].items()}
    growth=max(frames['final'][fn]['bytes']-v['bytes'] for fn,v in frames['baseline'].items())
    decision=dict(wire_identical=all(r['wire_identical'] for r in rows),size_regressions=[r for r in rows if r['after_bytes']>r['before_bytes']],pza_validation_encode_geomean_ratio=geom,
        pza_worst_encode_regression_percent=max(r['encode_change_percent'] for r in pza),pza_worst_decode_regression_percent=max(r['decode_change_percent'] for r in pza),
        pza_best_encode_change_percent=min(r['encode_change_percent'] for r in pza),code_text_bytes=code,max_frame_growth=growth)
    decision['performance_accept']=decision['wire_identical'] and not decision['size_regressions'] and geom<=1.05 and max(decision['pza_worst_encode_regression_percent'],decision['pza_worst_decode_regression_percent'])<=20 and decision['pza_best_encode_change_percent']<=-10 and code['final']-code['baseline']<=512 and growth<=256
    a.save(a.E/'decision.json',decision)
    lookup={(r['case'],r['codec']):r for r in rows};lines=['# Все размеры и времена текущего прогона','',
        'Время: микросекунды за все страницы набора, медиана пяти батчей. `[min; max]` — разброс, не доверительный интервал. Полные размеры включают wire-метаданные соответствующего кодека; framing/checksum у конкурентов различаются.','']
    for case in dict.fromkeys(r['case'] for r in rows):
        lines += ['## '+case,'','| Кодек | Б до → после | Упаковка до → после, мкс | Распаковка до → после, мкс |','|---|---:|---:|---:|']
        for r in rows:
            if r['case']!=case:continue
            def timing(direction,label):return f"{r[direction+'_'+label+'_us']:.1f} [{r[direction+'_'+label+'_min_us']:.1f}; {r[direction+'_'+label+'_max_us']:.1f}]"
            lines.append(f"| {r['codec']} | {r['before_bytes']} → {r['after_bytes']} | {timing('encode','before')} → {timing('encode','after')} | {timing('decode','before')} → {timing('decode','after')} |")
        lines.append('')
    (a.E/'comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    lines=['| Набор | Raw | PZ01 | PZ02 | PZ03-max | PZA до → после | LZ4 | Zstd1 | zlib1 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in pza:
        case=r['case'];values=[str(lookup[case,c]['after_bytes']) for c in ['pz01','pz02','pz03-max']]
        values += [str(r['before_bytes'])+' → '+str(r['after_bytes'])]
        values += [str(lookup[case,c]['after_bytes']) for c in ['lz4','zstd1','zlib1']]
        lines.append('| '+case+' | '+str(r['raw_bytes'])+' | '+' | '.join(values)+' |')
    (a.E/'sizes-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(decision,indent=2))
if __name__=='__main__':main()
