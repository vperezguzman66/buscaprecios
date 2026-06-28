"""
BuscaPrecios — punto de entrada para el ejecutable Windows (.exe).
Arranca el servidor FastAPI en un puerto libre y abre el navegador.
"""
import os
import sys
import socket
import threading
import time
import webbrowser

# ── Resolver rutas cuando está empaquetado por PyInstaller ───────────────────

def _base():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE = _base()
os.environ.setdefault("BUSCAPRECIOS_BASE", BASE)
sys.path.insert(0, os.path.join(BASE, "backend"))

# ── Encontrar puerto libre ────────────────────────────────────────────────────

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

PORT = _free_port()
URL  = f"http://127.0.0.1:{PORT}"

# ── Abrir navegador tras breve espera ─────────────────────────────────────────

def _open_browser():
    time.sleep(2)
    webbrowser.open(URL)

threading.Thread(target=_open_browser, daemon=True).start()

# ── Mensaje en consola ────────────────────────────────────────────────────────

print("=" * 55)
print("  BuscaPrecios")
print(f"  Servidor corriendo en {URL}")
print("  Cierra esta ventana para salir.")
print("=" * 55)

# ── Arrancar servidor ─────────────────────────────────────────────────────────

import uvicorn

uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=PORT,
    log_level="warning",
)
