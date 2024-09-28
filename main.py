import sys
from downloadCT import CT, CT_Gold, CT_Error
from tkinter.filedialog import askdirectory


print("Napiš url:")
URL:str = input()

print("Napiš jméno nebo potvrď prázdné a vyberese jméno z portálu ČT:")
NAME:str | None = input()

if NAME == " " or NAME == "":
    NAME = None

print("Vyber výstupovou složku:")
DIRECTORY:str = askdirectory()

CONVERT:bool = False
print("Konvertovat z .ts do .mp4? Oba formáty jsou podporovány základními přehrávači. U velkých souborů to může trvat i několik minut. Y/N")
if input().upper() == "Y":
    CONVERT = True

SUBS:bool = False
print("Stáhnout titulky? Y/N")
if input().upper() == "Y":
    SUBS = True

if DIRECTORY=="":
    print("Špatná složka!")
    input()	
    sys.exit()

if URL.startswith("https://www.ceskatelevize.cz"): #NORMAL
    ct:CT = CT(url=URL, directory=DIRECTORY, name=NAME)

elif URL.startswith("https://zlatapraha.ceskatelevize.cz/"): #GOLD
    ct:CT_Gold = CT_Gold(url=URL, directory=DIRECTORY, name=NAME)

ct.displayInfo()

try:
    ct.download(subs=SUBS, convert=CONVERT)
except CT_Error as e:
    print(f"Nastala chyba!\n{e}\nDetail: {e.details}\n\nZavolej Honzu!")
input()
