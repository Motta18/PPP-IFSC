import gzip
import shutil
from pathlib import Path

origem = Path("dados/rbmc/teste_juncao.rnx")
destino = Path("dados/rbmc/teste_juncao.rnx.gz")

with open(origem, "rb") as f_in:
    with gzip.open(destino, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

print(f"Compactado: {destino}")
print(f"Tamanho original: {origem.stat().st_size / 1024 / 1024:.2f} MB")
print(f"Tamanho compactado: {destino.stat().st_size / 1024 / 1024:.2f} MB")