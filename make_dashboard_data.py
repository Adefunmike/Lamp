import csv, json
rows = list(csv.DictReader(open('lamp_demo_reports.csv')))
with open('_data_inline.js', 'w') as f:
    f.write('const FITILA_DATA = ' + json.dumps(rows) + ';')
print('done,', len(rows), 'rows')