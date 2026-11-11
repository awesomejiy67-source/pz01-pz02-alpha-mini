"""Download pinned benchmark-only sources inside build; never linked into pages."""
import hashlib, json, pathlib, urllib.request, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / 'build' / 'audit-deps'
SOURCES = {
    'lz4': ('https://codeload.github.com/lz4/lz4/zip/refs/tags/v1.10.0', 'lz4-1.10.0'),
    'zstd': ('https://codeload.github.com/facebook/zstd/zip/refs/tags/v1.5.7', 'zstd-1.5.7'),
    'zlib': ('https://codeload.github.com/madler/zlib/zip/refs/tags/v1.3.1', 'zlib-1.3.1'),
}
EXPECTED = {
    'lz4':'3224b4c80f351f194984526ef396f6079bd6332dd9825c72ac0d7a37b3cdc565',
    'zstd':'7897bc5d620580d9b7cd3539c44b59d78f3657d33663fe97a145e07b4ebd69a4',
    'zlib':'50b24b47bf19e1f35d2a21ff36d2a366638cdf958219a66f30ce0861201760e6',
}
def main():
    DEST.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, (url, folder) in SOURCES.items():
        archive = DEST / (name + '.zip')
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                archive.write_bytes(response.read())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != EXPECTED[name]:
            raise ValueError('source archive SHA256 mismatch: '+name)
        with zipfile.ZipFile(archive) as z:
            z.extractall(DEST)
        records[name] = dict(url=url, sha256=digest, folder=folder)
        print(name, digest, flush=True)
    (DEST / 'sources.json').write_text(json.dumps(records, indent=2))
if __name__ == '__main__':
    main()
