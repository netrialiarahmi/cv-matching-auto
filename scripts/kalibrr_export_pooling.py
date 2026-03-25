#!/usr/bin/env python3
"""
Kalibrr Export — Pooling Positions Only

Exports candidate CSVs from Kalibrr ATS for positions that have
Pooling Status == "Pooled" in job_positions.csv.

Skips positions without a valid Job ID.
Updates sheet_positions.csv with the new File Storage URLs.

No Google Sheets interaction — source of truth is job_positions.csv.
"""

import os
import sys
import asyncio

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.kalibrr_core import (
    load_positions_from_job_csv,
    load_existing_file_storage,
    update_sheet_positions_csv,
    export_position,
)
from playwright.async_api import async_playwright

# ======================================
# ENV
# ======================================
KAID = os.getenv("KAID")
KB = os.getenv("KB")

if not KAID or not KB:
    print("❌ KAID atau KB tidak ditemukan di environment / .env")
    sys.exit(1)


async def main():
    # 1. Load pooled positions from job_positions.csv
    positions = load_positions_from_job_csv(filter_pooling="pooled")

    if not positions:
        print("\n✅ Tidak ada posisi pooling dengan Job ID. Selesai.")
        return

    print(f"\n📋 Ditemukan {len(positions)} posisi pooling:")
    for p in positions:
        print(f"   - {p['name']}: {p['job_id']}")

    # 2. Check existing File Storage URLs
    existing_fs = load_existing_file_storage()
    force_export = os.getenv("FORCE_EXPORT", "false").lower() == "true"

    positions_to_export = []
    for p in positions:
        if not force_export and p["name"] in existing_fs and existing_fs[p["name"]]:
            print(f"   ⏭️ Skip (sudah ada File Storage): {p['name']}")
        else:
            positions_to_export.append(p)

    if not positions_to_export:
        print("\n✅ Semua posisi pooling sudah memiliki File Storage. Tidak ada yang perlu di-export.")
        return

    reason = "semua (force export)" if force_export else f"{len(positions_to_export)} posisi"
    print(f"\n🔄 Akan meng-export {reason}:")
    for p in positions_to_export:
        print(f"   📤 {p['name']}: {p['job_id']}")

    # 3. Export via Playwright
    export_results = []

    async with async_playwright() as pw:
        for p in positions_to_export:
            count, csv_path = await export_position(
                pw, p["name"], p["job_id"], KAID, KB
            )
            if count and csv_path:
                export_results.append([
                    p["name"],
                    str(p["job_id"]),
                    str(count),
                    csv_path,
                ])

    if not export_results:
        print("\n⚠️  Tidak ada data yang berhasil di-export.")
        return

    # 4. Update sheet_positions.csv (upsert)
    update_sheet_positions_csv(export_results)

    print(f"\n✅ Selesai. {len(export_results)} posisi pooling berhasil di-export.")


if __name__ == "__main__":
    asyncio.run(main())
