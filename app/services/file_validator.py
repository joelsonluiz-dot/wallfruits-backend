"""
Validação profunda de arquivos carregados.
- Verifica magic bytes (assinatura real do arquivo)
- Impede upload de arquivos disfarçados (ex: .exe renomeado para .pdf)
"""

# Mapeamento de extensão → magic bytes esperados
# Cada entrada é: extensão → lista de (offset, bytes_esperados)
_MAGIC_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    ".pdf": [(0, b"%PDF")],
    ".doc": [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")],  # OLE2 Compound
    ".docx": [(0, b"PK\x03\x04")],  # ZIP (Office Open XML)
    ".png": [(0, b"\x89PNG\r\n\x1a\n")],
    ".jpg": [(0, b"\xff\xd8\xff")],
    ".jpeg": [(0, b"\xff\xd8\xff")],
}

# Extensões que não precisam de validação de magic bytes (fallback seguro)
_SKIP_MAGIC_EXTENSIONS: set[str] = set()


def validate_file_content(file_bytes: bytes, extension: str) -> bool:
    """
    Verifica se os primeiros bytes do arquivo correspondem à extensão declarada.

    Retorna True se válido, False se os magic bytes não correspondem.
    Se a extensão não possui assinatura conhecida, retorna True (permite).
    """
    ext = extension.lower()
    if ext in _SKIP_MAGIC_EXTENSIONS:
        return True

    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        # Extensão sem assinatura conhecida — aceita
        return True

    for offset, expected in signatures:
        if len(file_bytes) < offset + len(expected):
            return False
        if file_bytes[offset : offset + len(expected)] == expected:
            return True

    return False
