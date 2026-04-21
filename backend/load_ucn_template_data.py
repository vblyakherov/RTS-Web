"""
Импорт данных нового шаблона UCN 2.0 в проект `ucn-2026`.

Использование:
  python load_ucn_template_data.py /path/to/template.xlsx --clear

Скрипт:
  - находит проект `ucn-2026`;
  - при `--clear` удаляет старые sites/site_history этого проекта;
  - читает Excel новым import-парсером;
  - выполняет bulk upsert и печатает результат.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.crud.site import bulk_upsert_sites
from app.crud.site_history import make_history_batch_id
from app.models.project import Project
from app.models.site import Site
from app.models.site_history import SiteHistory
from app.services.excel import parse_excel_import


async def main(filepath: str, clear: bool) -> None:
    excel_path = Path(filepath)
    if not excel_path.exists():
        raise SystemExit(f"Файл не найден: {excel_path}")

    raw = excel_path.read_bytes()
    rows, parse_errors = parse_excel_import(raw)
    if parse_errors:
        print(f"Предупреждений/ошибок парсинга: {len(parse_errors)}")
        for item in parse_errors[:20]:
            print(f"  - {item}")

    if not rows:
        raise SystemExit("После парсинга не осталось валидных строк для импорта")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        project = (
            await session.execute(
                select(Project).where(Project.code == "ucn-2026").limit(1)
            )
        ).scalar_one_or_none()
        if project is None:
            raise SystemExit("Проект `ucn-2026` не найден")

        if clear:
            site_ids = list(
                (
                    await session.execute(
                        select(Site.id).where(Site.project_id == project.id)
                    )
                ).scalars().all()
            )
            if site_ids:
                await session.execute(delete(SiteHistory).where(SiteHistory.site_id.in_(site_ids)))
                await session.execute(delete(Site).where(Site.project_id == project.id))
                await session.flush()
                print(f"Удалено старых объектов UCN: {len(site_ids)}")
            else:
                print("Старых объектов UCN для удаления не найдено")

        history_batch_id = make_history_batch_id("excel-import")
        created, updated, upsert_errors = await bulk_upsert_sites(
            session,
            rows,
            project_id=project.id,
            user_id=None,
            history_batch_id=history_batch_id,
        )
        await session.commit()

    await engine.dispose()

    print(f"Импорт завершён: created={created}, updated={updated}, total={created + updated}")
    if upsert_errors:
        print(f"Ошибок upsert: {len(upsert_errors)}")
        for item in upsert_errors[:20]:
            print(f"  - {item}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath", help="Путь до xlsx/xlsm файла нового шаблона")
    parser.add_argument("--clear", action="store_true", help="Очистить старые объекты UCN перед импортом")
    args = parser.parse_args()
    asyncio.run(main(args.filepath, args.clear))
