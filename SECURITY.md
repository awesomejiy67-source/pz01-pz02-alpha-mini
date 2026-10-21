# Security / Безопасность

PZ01/PZ02 are experimental bounded page codecs. Their FNV-1a checksum detects accidental corruption but is **not cryptographic**, does **not** provide authenticity and must never be trusted as proof that data came from a particular author.

- Page size is limited to 2,048 decoded bytes. The caller provides output and compressed input buffers.
- Input/output buffers must not overlap.
- A failed decode may have written a partial output: always discard it.
- Validate external framing lengths before passing data to the decoder.
- Use cryptographic signatures or authenticated transport for security-sensitive downloads.
- Native tests include truncation, mutation and sanitizers, but are **not a proof of absence of vulnerabilities**.

## Русский

Это экспериментальные кодеки. FNV-1a проверяет случайные повреждения, но не защищает от подделки. Не используйте его вместо цифровой подписи. При ошибке распаковки полностью отбросьте выходной буфер. Для недоверенных файлов проводите дополнительные проверки и фаззинг.
