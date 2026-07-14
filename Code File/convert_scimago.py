import csv
import json

csv_file = r'd:\Website\Life OS\Oppurtunity\Google Scholar Data\Assets\scimagojr 2025.csv'
json_file = r'd:\Website\Life OS\Oppurtunity\Google Scholar Data\Assets\scimagojr_2025.json'

scimago_dict = {}

with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        # Save exact title, but use lowercase stripped title as key
        # Handle cases where multiple journals might have similar names by keeping the first/highest ranked one
        key = row['Title'].strip().lower()
        if key not in scimago_dict:
            scimago_dict[key] = {
                'Title': row['Title'].strip(),
                'Quartile': row.get('SJR Best Quartile', ''),
                'H-index': row.get('H index', ''),
                'SJR': row.get('SJR', ''),
                'Categories': row.get('Categories', ''),
                'Areas': row.get('Areas', ''),
                'Country': row.get('Country', '')
            }

with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(scimago_dict, f, indent=2)

print(f"Successfully converted {len(scimago_dict)} journals to JSON at {json_file}")
