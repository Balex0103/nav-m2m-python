from __future__ import annotations

import glob
import os
from typing import Optional

def legujabb_fajl_keresese(megfigyelt_mappa: str) -> Optional[str]:
    """
    Megkeresi a legújabb feldolgozható fájlt a megfigyelt mappában.
    Szűri az ~$ kezdetű fájlokat (Lock fájlok).
    """
    if not os.path.exists(megfigyelt_mappa):
        os.makedirs(megfigyelt_mappa, exist_ok=True)
        return None

    minden_fajl = glob.glob(os.path.join(megfigyelt_mappa, "*.xlsx")) + glob.glob(os.path.join(megfigyelt_mappa, "*.csv"))
    fajlok = [f for f in minden_fajl if not os.path.basename(f).startswith("~$")]

    if not fajlok:
        return None
    return max(fajlok, key=os.path.getmtime)