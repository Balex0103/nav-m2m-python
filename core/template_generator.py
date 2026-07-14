# core/template_generator.py
# Dedikált motor a hivatalos, gyári NAV eÁFA Excel sablon telepítéséhez.

from __future__ import annotations

import os
import shutil
import logging
from config import VDR_MAPPA

logger = logging.getLogger(__name__)


def mentett_mintasablon_gyartasa(target_path: str) -> None:
    """
    Ahelyett, hogy kódból generálnánk egy leegyszerűsített szerkezetet,
    ez a függvény átmásolja a hivatalos, NAV által kiadott összetett 
    01_pelda_fizetendo.xlsx sablonfájlt a szoftver belső vdr/ mappájából 
    közvetlenül a felhasználó Asztalára.
    
    Ez biztosítja, hogy a dolgozók a gyári formátumot, stílust és 
    minden eredeti képletet hiánytalanul megkapjanak.
    """
    # Fontos: Másold be a NAV-tól kapott eredeti '01_példa_fizetendő.xlsx' fájlt 
    # a projekt 'vdr/' mappájába ezen a néven: '01_pelda_fizetendo.xlsx'
    forras_sablon = os.path.join(VDR_MAPPA, "01_pelda_fizetendo.xlsx")
    
    if not os.path.exists(forras_sablon):
        logger.error(f"❌ A hivatalos NAV mintasablon nem található: {forras_sablon}")
        raise FileNotFoundError(
            f"A hivatalos NAV mintasablon nem található a szoftver belső erőforrásai között.\n"
            f"Kérlek győződj meg róla, hogy a '01_pelda_fizetendo.xlsx' fájl be lett másolva a 'vdr/' mappába!"
        )
        
    try:
        shutil.copy(forras_sablon, target_path)
        logger.info(f"✅ Hivatalos NAV Excel sablon sikeresen átmásolva ide: {target_path}")
    except Exception as e:
        logger.error(f"❌ Nem sikerült a sablon fájl másolása: {str(e)}")
        raise e