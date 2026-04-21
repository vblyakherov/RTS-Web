"""
Скрипт импорта тестовых данных из Excel-панели NI.

Использование (на VPS):
  docker exec tracker_backend python load_ni_data.py /data/ni_panel.xlsx

Локально (после rsync):
  Скопировать xlsx на VPS, затем запустить через docker exec.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, date

import openpyxl


TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu',
    'я':'ya',
}

import re
def to_db_name(header):
    s = header.lower()
    result = []
    for c in s:
        if c in TRANSLIT: result.append(TRANSLIT[c])
        elif c.isascii() and (c.isalnum() or c == '_'): result.append(c)
        else: result.append('_')
    name = ''.join(result)
    name = re.sub(r'_+', '_', name).strip('_')
    if len(name) > 63: name = name[:63].rstrip('_')
    return name


# Пропускаем последние 3 формульные колонки
SKIP_LAST = 3


def parse_value(value):
    """Конвертировать значение из Excel в python-тип."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip()
    return s if s else None


async def main(filepath: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from app.config import settings
    from app.models.site import Site, SiteStatus
    import app.models  # noqa

    print(f"Загружаем файл: {filepath}")
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb['Data sheet']
    all_rows = list(ws.iter_rows(min_row=1, values_only=True))
    headers = list(all_rows[0])[:-SKIP_LAST]
    data_rows = all_rows[1:]

    print(f"Колонок: {len(headers)}, Строк данных: {len(data_rows)}")

    # Строим маппинг header → db_name
    # Отслеживаем дубликаты
    seen = set()
    header_map = {}
    for h in headers:
        if h is None:
            continue
        name = to_db_name(str(h))
        if name in seen:
            i = 2
            while f"{name}_{i}" in seen: i += 1
            name = f"{name}_{i}"
        header_map[str(h)] = name
        seen.add(name)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    created = updated = skipped = 0
    errors = []

    async with async_session() as session:
        async with session.begin():
            # Загружаем все существующие site_id
            result = await session.execute(select(Site.site_id))
            existing_ids = {r[0] for r in result.fetchall()}
            print(f"Уже в БД: {len(existing_ids)} объектов")

            for row_idx, row in enumerate(data_rows, start=2):
                row_dict = {}
                for col_idx, header in enumerate(headers):
                    if header is None or col_idx >= len(row):
                        continue
                    db_name = header_map.get(str(header))
                    if db_name is None:
                        continue
                    row_dict[db_name] = parse_value(row[col_idx])

                # site_id = № БС (колонка bs)
                # Формируем site_id из колонки № БС
                bs_num = row_dict.get('bs')
                if not bs_num:
                    skipped += 1
                    continue
                site_id = f"BS-{int(bs_num):06d}"

                # name = адрес или site_id
                name = row_dict.get('adres') or site_id
                region = row_dict.get('region') or ''

                SYSTEM_FIELDS = {'id', 'created_at', 'updated_at', 'region_id', 'contractor_id'}

                if site_id in existing_ids:
                    # UPDATE
                    result = await session.execute(select(Site).where(Site.site_id == site_id))
                    site = result.scalar_one_or_none()
                    if site:
                        for field, value in row_dict.items():
                            if value is not None and hasattr(site, field) and field not in SYSTEM_FIELDS:
                                setattr(site, field, value)
                        site.name = name
                        site.region = region
                        updated += 1
                else:
                    # CREATE
                    site_data = {k: v for k, v in row_dict.items() if v is not None and hasattr(Site, k) and k not in SYSTEM_FIELDS}
                    site_data['site_id'] = site_id
                    site_data['name'] = name
                    site_data['region'] = region
                    site_data['status'] = SiteStatus.planned
                    site = Site(**site_data)
                    session.add(site)
                    existing_ids.add(site_id)
                    created += 1

                if (created + updated) % 100 == 0:
                    print(f"  Обработано {created + updated}...")

    print(f"\n✓ Готово: создано {created}, обновлено {updated}, пропущено {skipped}")
    if errors:
        print(f"Ошибки ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e}")

    await engine.dispose()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python load_ni_data.py <path_to_xlsx>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
