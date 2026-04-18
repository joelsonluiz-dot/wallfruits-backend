"""Smoke test de Supabase Storage.

Uso:
  - Configure as env vars (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET)
  - Defina SUPABASE_STORAGE_ENABLED=true
  - Rode:
      python scripts/05_supabase_storage_smoke.py

O script faz upload de um objeto pequeno e depois deleta.
"""

import asyncio
import uuid

from app.services.supabase_storage_service import delete_object, storage_bucket, supabase_storage_enabled, upload_public_object


async def main() -> None:
    if not supabase_storage_enabled():
        raise SystemExit("SUPABASE_STORAGE_ENABLED=false (habilite para rodar o smoke)")

    bucket = storage_bucket()
    object_path = f"smoke/{uuid.uuid4()}.txt"

    await upload_public_object(
        bucket=bucket,
        object_path=object_path,
        content=b"ok",
        content_type="text/plain",
    )

    await delete_object(bucket=bucket, object_path=object_path)

    print("OK: upload/delete no Supabase Storage funcionou")


if __name__ == "__main__":
    asyncio.run(main())
