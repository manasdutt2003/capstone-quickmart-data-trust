import hashlib

note = 'Call before, no bell'
h = hashlib.sha256(note.encode('utf-8')).hexdigest()
print(f'Hash of "{note}": {h}')
print(f'Contains 0741763684: {"0741763684" in h}')