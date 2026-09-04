import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/draw_mask.py', 'r') as f:
    code = f.read()

old_logic = "pts_list.append((w-1, pts_list[-1][1]))"
new_logic = "pts_list.append((w-1, pts_list[0][1])) # Obliga a que la costura der/izq coincida perfectamente en Y"

if old_logic in code:
    code = code.replace(old_logic, new_logic)
    with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/draw_mask.py', 'w') as f:
        f.write(code)
    print("Mask logic fixed!")
else:
    print("Could not find logic to replace")
