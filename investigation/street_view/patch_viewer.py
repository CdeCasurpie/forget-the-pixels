import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/view_sequence.py', 'r') as f:
    code = f.read()

old_logic = "if not os.path.exists(img_path):\n            continue"
new_logic = """if not os.path.exists(img_path):
            continue
        # Evitar mareos: Mostrar solo la vista frontal para simular manejo real
        if 'view0' not in fname:
            continue"""

if old_logic in code:
    code = code.replace(old_logic, new_logic)
    with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/view_sequence.py', 'w') as f:
        f.write(code)
    print("Viewer patched to only show view0.")
else:
    print("Patch logic not found.")
