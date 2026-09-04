import asyncio
import streetlevel.streetview as sv
import time

async def main():
    print("Obteniendo tile...")
    start = time.time()
    panos = sv.get_coverage_tile_by_latlon(-12.137248, -77.020423)
    print(f"Tile obtenido en {time.time() - start:.2f}s, {len(panos)} panos.")
    
    start = time.time()
    async with sv.ClientSession() as session:
        tasks = [sv.find_panorama_by_id_async(p.id, session) for p in panos[:100]]
        results = await asyncio.gather(*tasks)
    print(f"100 metadatos obtenidos en {time.time() - start:.2f}s.")
    
    # Contar cuantos son de 2022
    count_2022 = sum(1 for r in results if r and r.date and r.date.year == 2022)
    print(f"Panos de 2022: {count_2022}")

asyncio.run(main())
