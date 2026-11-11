"""Exercise real incremental Make builds in a private project copy.

This is deliberately not `make -B`: changing an included header must rebuild
objects, the static/shared libraries, and every page test executable.
"""
import argparse, json, os, pathlib, shutil, subprocess, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--make', default='make')
    p.add_argument('--cc', default='cc')
    p.add_argument('--ar', default='ar')
    p.add_argument('--shell')
    p.add_argument('--log', type=pathlib.Path)
    o = p.parse_args()
    parent = (ROOT/'build').resolve(); parent.mkdir(exist_ok=True)
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix='header-deps-', dir=parent)).resolve()
    assert sandbox.is_relative_to(parent)
    for name in ['models', 'src', 'tests', 'examples']:
        shutil.copytree(ROOT/name, sandbox/name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(ROOT/'Makefile', sandbox/'Makefile')
    cmd = [o.make, 'CC='+o.cc, 'AR='+o.ar]
    if o.shell: cmd.append('SHELL='+o.shell)
    names = ['test_codec','test_pz03_page','test_pza','test_pza_transform_bounds','test_page_wire_bounds']
    targets = ['build/libnano_pz.a','build/libnano_pz.so',*['build/'+n for n in names]]
    records = []
    def run(args):
        start = time.perf_counter()
        result = subprocess.run(args, cwd=sandbox, capture_output=True, timeout=120)
        record = dict(command=args, cwd=str(sandbox), returncode=result.returncode,
                      seconds=time.perf_counter()-start,
                      stdout=result.stdout.decode('utf-8','replace'),
                      stderr=result.stderr.decode('utf-8','replace'))
        records.append(record)
        if result.returncode: raise RuntimeError(record)
        return record['stdout']
    def actual(name):
        path = sandbox/name
        return path if path.exists() else path.with_suffix('.exe')
    try:
        run(cmd+targets)
        # On Windows, make recognises executable suffixes; verify the no-op too.
        idle = run(cmd+['-n']+targets)
        idle_compiles = ' -c ' in idle or ' -o ' in idle
        if idle_compiles:
            records.append(dict(status='DEFECT',error='unchanged build compiles again (executable suffix tracking)'))
        watched = ['build/models/pz/pagezip.o','build/models/pz/pz01.o',
                   'build/models/pz/pz03_page.o','build/models/pza/pza.o',*targets]
        before = {name:actual(name).stat().st_mtime_ns for name in watched}
        # Avoid coarse filesystem timestamp equality; no source semantics change.
        time.sleep(1.1)
        header = sandbox/'src/pager.h'
        header.write_bytes(header.read_bytes()+b'\n/* dependency-regression marker */\n')
        incremental = run(cmd+targets)
        unchanged = [name for name in watched if actual(name).stat().st_mtime_ns<=before[name]]
        if unchanged:
            raise AssertionError('header edit left stale artifacts: '+', '.join(unchanged))
        if idle_compiles:
            raise AssertionError('unchanged build compiles again (executable suffix tracking)')
        for name in names: run([str(actual('build/'+name))])
        records.append(dict(status='PASS', rebuilt=watched))
        print('PASS header dependency regression:',len(watched),'fresh artifacts')
    except Exception as error:
        records.append(dict(status='FAIL', error=str(error)))
        raise
    finally:
        if o.log:
            o.log.parent.mkdir(parents=True,exist_ok=True)
            o.log.write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        # Keep the bounded private copy for inspection; never delete user files.

if __name__ == '__main__': main()
