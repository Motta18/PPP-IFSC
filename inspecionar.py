"""
Inspeciona os arquivos baixados do servidor IFSC.
Lista o conteúdo dos ZIPs e mostra as primeiras linhas do RINEX.
"""

import zipfile
from pathlib import Path

# Pasta onde estão os arquivos
pasta = Path("dados/rbmc")

# Lista tudo que tem na pasta
print("=== Arquivos na pasta dados/rbmc/ ===\n")
for item in sorted(pasta.iterdir()):
    print(f"{item.name}  ({item.stat().st_size / 1024:.1f} KB)")

print("\n=== Conteúdo dos ZIPs ===\n")
for zip_path in sorted(pasta.glob("*.zip")):
    print(f"--- {zip_path.name} ---")
    with zipfile.ZipFile(zip_path, "r") as z:
        for nome in z.namelist():
            print(f"  {nome}")
    """
Inspeciona os arquivos baixados do servidor IFSC.
Cada arquivo de 15 min vira uma pasta com 4 arquivos RINEX.
"""

from pathlib import Path

pasta = Path("dados/rbmc")

print("=== Conteúdo de dados/rbmc/ ===\n")
for item in sorted(pasta.iterdir()):
    if item.is_dir():
        print(f"[PASTA] {item.name}/")
        for sub in sorted(item.iterdir()):
            print(f"   {sub.name}  ({sub.stat().st_size / 1024:.1f} KB)")
    else:
        print(f"[ARQ]   {item.name}  ({item.stat().st_size / 1024:.1f} KB)")
    print()