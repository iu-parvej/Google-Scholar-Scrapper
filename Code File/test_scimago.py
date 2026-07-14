import csv
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

scimago_data = {}
with open(r'd:\Website\Life OS\Oppurtunity\Google Scholar Data\Assets\scimagojr 2025.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        title = row['Title'].strip().lower()
        scimago_data[title] = {
            'Title': row['Title'],
            'Quartile': row.get('SJR Best Quartile', ''),
            'H-index': row.get('H index', ''),
            'SJR': row.get('SJR', ''),
            'Categories': row.get('Categories', ''),
            'Areas': row.get('Areas', ''),
            'Country': row.get('Country', '')
        }

with open(r'd:\Website\Life OS\Oppurtunity\Google Scholar Data\river_erosion_papers.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        journal_scholar = row.get('Journal/Venue (Scholar)', '').strip()
        search_name = journal_scholar.strip('… ').lower()
        
        match = scimago_data.get(search_name)
        
        if not match:
            for sjr_title, sjr_info in scimago_data.items():
                if search_name == sjr_title or (len(search_name) > 8 and search_name in sjr_title):
                    match = sjr_info
                    break
                    
        print(f"Paper: {row.get('Title', '')[:40]}...")
        print(f"Journal from Scholar: {journal_scholar}")
        if match:
            print(f"  [MATCHED AS]: {match['Title']}")
            print(f"  -> Quartile: {match['Quartile']} | H-index: {match['H-index']} | SJR: {match['SJR']} | Country: {match['Country']}")
            print(f"  -> Areas: {match['Areas']}")
        else:
            print("  [NOT FOUND] in SCImago")
        print('-'*60)
