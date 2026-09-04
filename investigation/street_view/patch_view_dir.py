import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/view_sequence.py', 'r') as f:
    code = f.read()

code = code.replace('data_block', 'data_custom_route')

with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/view_sequence.py', 'w') as f:
    f.write(code)
print("Viewer updated to point to custom route.")
