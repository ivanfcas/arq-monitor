import json
from datetime import datetime

POSICIONES_FILE = "posiciones.json"

def abrir_posicion(ticker, entry_price, sl, tp):
    pos = {
        "ticker": ticker,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "fecha_apertura": datetime.now().isoformat()
    }
    with open(POSICIONES_FILE, "w") as f:
        json.dump(pos, f)

def cerrar_posicion(precio_actual):
    with open(POSICIONES_FILE, "r") as f:
        pos = json.load(f)
    
    if precio_actual <= pos["sl"]:
        print(f"❌ STOP LOSS alcanzado en {pos['ticker']}")
    elif precio_actual >= pos["tp"]:
        print(f"✅ TAKE PROFIT alcanzado en {pos['ticker']}")
    else:
        return
    
    # Cerrar y eliminar
    os.remove(POSICIONES_FILE)