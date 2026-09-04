import asyncio
import streetlevel.streetview as sv
import time

async def main():
    panos = sv.get_coverage_tile_by_latlon(-12.137248, -77.020423)
    
    async with sv.ClientSession() as session:
        tasks = [sv.find_panorama_by_id_async(p.id, session) for p in panos]
        results = await asyncio.gather(*tasks)
    
    valid_2022 = []
    for r in results:
        if not r: continue
        if r.date and r.date.year == 2022:
            valid_2022.append(r)
        else:
            for hist in r.historical:
                if hist.date.year == 2022:
                    valid_2022.append(hist)
                    break # One per location
                    
    print(f"Panos de 2022 totales en el Tile: {len(valid_2022)}")

asyncio.run(main())
