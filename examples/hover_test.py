"""File di test per verificare gli hover di PyBuddy su ogni tipo di elemento Python."""

import os
from pathlib import Path
from collections import defaultdict

# --- Variabili ---

MAX_RETRIES = 3
nome_utente: str = "PyBuddy"
x, y, z = 1, 2, 3

# --- Funzioni ---


def saluta(nome: str, entusiasmo: int = 1) -> str:
    """Restituisce un saluto con un numero variabile di punti esclamativi."""
    punti = "!" * entusiasmo
    return f"Ciao {nome}{punti}"


async def fetch_data(url: str, timeout: float = 30.0) -> dict:
    """Finge di scaricare dati da un URL."""
    risultato = {"url": url, "status": "ok"}
    return risultato

# --- Classi ---


class AnimaleBase:
    """Classe base per tutti gli animali."""

    specie_count: int = 0

    def __init__(self, nome: str, zampe: int = 4):
        self.nome = nome
        self.zampe = zampe

    def descrivi(self) -> str:
        return f"{self.nome} ha {self.zampe} zampe"


class Gatto(AnimaleBase):
    """Un gatto. Ovviamente superiore."""

    def __init__(self, nome: str, indoor: bool = True):
        super().__init__(nome, zampe=4)
        self.indoor = indoor

    def fai_verso(self) -> str:
        return "Miao!" if self.indoor else "MIIAAAOOO!"

    class Coda:
        """Classe annidata — perché anche le code meritano una classe."""

        def __init__(self, lunghezza: float):
            self.lunghezza = lunghezza

# --- Cicli ---


def elabora_lista(items: list) -> list:
    risultati = []
    for item in items:
        if item > 0:
            risultati.append(item * 2)

    contatore = 10
    while contatore > 0:
        contatore -= 1

    return risultati

# --- Comprehension e generator ---

quadrati = [x**2 for x in range(10)]
mappa_nomi = {k: v for k, v in [("a", 1), ("b", 2)]}
unici = {x % 5 for x in range(20)}
somma_lazy = sum(x for x in range(1000))

# --- Lambda ---

ordina_per_lunghezza = lambda s: len(s)

# --- Context manager ---


def scrivi_file(percorso: str, contenuto: str):
    with open(percorso, "w") as f:
        f.write(contenuto)

# --- Try/Except ---


def dividi_sicuro(a: float, b: float) -> float:
    try:
        return a / b
    except ZeroDivisionError:
        return 0.0
    except:
        return -1.0

# --- Decoratori ---


def log_chiamata(func):
    """Decoratore che logga le chiamate."""
    def wrapper(*args, **kwargs):
        print(f"Chiamata: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper


@log_chiamata
def operazione_importante():
    pass


# --- Async for/with ---

async def processo_stream(stream):
    async for chunk in stream:
        print(chunk)

    async with open("log.txt") as f:
        await f.write("done")
