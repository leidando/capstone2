import os

path = r'c:\Users\ashle\Downloads\cswdo_capstone_system\cswdo_capstone_system\core\templates\beneficiary_list.html'
try:
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Replace any stringformat variations
    c = c.replace('selected_barangay==b.id|stringformat:"d"', 'selected_barangay == b.id')
    c = c.replace('selected_program==p.id|stringformat:"d"', 'selected_program == p.id')
    
    # Replace any variations without spaces that might have been left
    c = c.replace('selected_barangay==b.id', 'selected_barangay == b.id')
    c = c.replace('selected_program==p.id', 'selected_program == p.id')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("Fixed beneficiary_list.html")
except Exception as e:
    print(f"Error: {e}")
