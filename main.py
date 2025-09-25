import sys
from downloadCT import CT, CT_Gold, CT_Error
from tkinter.filedialog import askdirectory


print("Napiš url:")
URL: str = input()

print("Napiš jméno nebo potvrď prázdné a vybere se jméno z portálu ČT:")
NAME: str | None = input()

if NAME == " " or NAME == "":
    NAME = None

print("Vyber výstupovou složku:")
DIRECTORY: str = askdirectory()

SUBS: bool = False
print("Stáhnout titulky? Y/N")
if input().upper() == "Y":
    SUBS = True

if DIRECTORY == "":
    print("Špatná složka!")
    input()
    sys.exit()

if URL.startswith("https://www.ceskatelevize.cz"):  # NORMAL
    ct: CT = CT(url=URL, directory=DIRECTORY, name=NAME)

elif URL.startswith("https://zlatapraha.ceskatelevize.cz/"):  # GOLD
    ct: CT_Gold = CT_Gold(url=URL, directory=DIRECTORY, name=NAME)

ct.displayInfo(clear_terminal=True)

try:
    ct.download(subs=SUBS)
except CT_Error as e:
    print(f"Nastala očekávaná chyba!\n{e}\nDetail: {e.details}\n\nZavolej Honzu!")
except Exception as e:
    print(f"Nastala neočekávaná chyba!\n{e}\nDetail: {e.details}\n\nZavolej Honzu!")
input()
