from __future__ import annotations

import datetime
import os
import threading
import traceback
from typing import Any

import pandas as pd

from config import *
from nav.eafa_api import EafaApiClient, extract_first_tag_value
from nav.validators import validate_user_config, validate_xml_with_xsd
from nav.xml_generator import generate_nav_xml
from core.file_watcher import legujabb_fajl_keresese
from core.analitika import *
from utils.logger import logger
from services.nav_session import *
from gui import previews

def kapcsolat_teszt_a_hatterben(tech_user: str, password: str, sign_key: str, exchange_key: str, tax_number: str, environment: str, allapot_uzenet: Any, show_error_popup: Any) -> None:
    try:
        logger.info("")
        logger.divider()
        logger.info("[Kapcsolat teszt] eÁFA M2M kapcsolat előellenőrzés indítása...")

        config = nav_config_osszeallitasa(tech_user, password, sign_key, exchange_key, tax_number, environment)
        config_hiba = validate_user_config(config)
        if config_hiba:
            logger.info(f"❌ [KONFIG HIBA] {config_hiba}")
            allapot_uzenet("Állapot: Hibás NAV konfiguráció", "#FF5555")
            show_error_popup("Konfigurációs hiba", config_hiba)
            return

        logger.info(f"[Környezet] Aktív környezet: {config.environment}")
        logger.info(f"[Adószám] {config.tax_number}")
        logger.info("[Kapcsolat teszt] eÁFA v2 QueryTaxCodeCatalog request előállítása...")

        client = EafaApiClient(config)
        taxpoint_date = datetime.datetime.now().strftime("%Y-%m-%d")
        request_xml = client.build_query_tax_code_catalog_xml(taxpoint_date).decode("utf-8", errors="ignore")

        logger.info("✅ [Kapcsolat teszt] eÁFA request sikeresen legenerálva.")
        logger.info(f"[eÁFA URL] {client.base_url}/analyticsService/v1/queryTaxCodeCatalog")
        logger.info(f"[XML minta] {biztonsagos_xml_minta(request_xml)}")

        if not van_valodi_nav_hitelesites(config):
            logger.info("ℹ️ [Kapcsolat teszt] Valódi NAV kulcsok még nincsenek megadva.")
            logger.info("ℹ️ [Kapcsolat teszt] A valódi eÁFA hívás kihagyva, csak előellenőrzés történt.")
            allapot_uzenet("Állapot: Kapcsolat teszt kész (előellenőrzés)", "#F1C40F")
            return

        logger.info("[Kapcsolat teszt] Valódi eÁFA adókód katalógus lekérdezés indítása...")
        result = client.query_tax_code_catalog(taxpoint_date)

        if result.get("success"):
            logger.info("✅ [eÁFA] queryTaxCodeCatalog HTTP szinten sikeres.")
            logger.info(f"[HTTP] {result.get('status_code')}")
            logger.info(f"[Válasz] {str(result.get('text', ''))[:1200]}")
            allapot_uzenet("Állapot: eÁFA kapcsolat rendben", "#00FF88")
        else:
            logger.info("❌ [eÁFA] queryTaxCodeCatalog hiba.")
            logger.info(f"[HTTP] {result.get('status_code')}")
            logger.info(f"[Válasz] {str(result.get('text', ''))[:1200]}")
            allapot_uzenet("Állapot: eÁFA kapcsolat hiba", "#FF5555")
            show_error_popup(
                "eÁFA kapcsolat hiba",
                f"HTTP: {result.get('status_code')}\n\n{str(result.get('text', ''))[:900]}"
            )

    except Exception as e:
        logger.info(f"❌ [KAPCSOLAT TESZT HIBA] {str(e)}")
        logger.info(traceback.format_exc()[:2500])
        allapot_uzenet("Állapot: Kapcsolat teszt hiba", "#FF5555")
        show_error_popup("Kapcsolat teszt hiba", str(e))

    finally:
        pass


def feldolgozas_a_hatterben(tech_user: str, password: str, sign_key: str, exchange_key: str, tax_number: str, environment: str, eafa_feltoltes: bool, allapot_uzenet: Any, show_error_popup: Any, ask_yes_no_popup: Any) -> None:

    try:
        logger.info("")
        logger.divider()
        logger.info("[Kezdés] Feldolgozás indítása...")

        config = nav_config_osszeallitasa(tech_user, password, sign_key, exchange_key, tax_number, environment)
        config_hiba = validate_user_config(config)
        if config_hiba:
            logger.info(f"❌ [KONFIG HIBA] {config_hiba}")
            allapot_uzenet("Állapot: Hibás NAV konfiguráció", "#FF5555")
            show_error_popup("Konfigurációs hiba", config_hiba)
            return

        logger.info(f"[Környezet] Aktív környezet: {config.environment}")
        logger.info(f"[Mappa] Figyelt mappa: {MEGFIGYELT_MAPPA}")

        fajl = legujabb_fajl_keresese()
        if not fajl:
            hiba = f"Nincs feldolgozható .xlsx vagy .csv fájl a '{MEGFIGYELT_MAPPA}' mappában."
            logger.info(f"❌ [HIBA] {hiba}")
            allapot_uzenet("Állapot: Nincs új fájl", "#FF5555")
            show_error_popup("Hiányzó forrásfájl", hiba)
            return

        previews.utolso_fajl = fajl
        fajlnev = os.path.basename(fajl)

        logger.info(f"✅ [Fájl] Megtalálva: {fajlnev}")
        logger.info("[Beolvasás] Munkalapok beolvasása a memóriába...")

        lapok_dict = fajl_beolvasasa(fajl)
        previews.utolso_lapok_dict = lapok_dict.copy()
        
        bevallas_fejadatok = peri_fejadatok_kinyerese(lapok_dict)

        matematikai_hibak = matematikai_eloellenorzes(bevallas_fejadatok)
        if matematikai_hibak:
            logger.info("⚠️ [Matematika] Az előellenőrző NAV logikai hibákat talált a fejadatokban:")
            for hiba_msg in matematikai_hibak:
                logger.info(f"  ❌ {hiba_msg}")
            
            if not ask_yes_no_popup(
                "Matematikai / Logikai hiba a Fejadatokban",
                "A program a NAV eÁFA specifikációja alapján logikai/matematikai hibát talált az Excel 'Bevallás Fejadatok' lapján lévő egyenlegekben.\n\n"
                "A NAV szervere nagy eséllyel el fogja utasítani az XML feldolgozását!\n\n"
                "Biztosan folytatod a generálást és a hálózati beküldést?"
            ):
                logger.info("ℹ️ [Megszakítva] A felhasználó a matematikai hiba miatt leállította a folyamatot.")
                allapot_uzenet("Állapot: Megszakítva (Matematikai hiba)", "#F1C40F")
                return

        feldolgozando_df_lista: list[pd.DataFrame] = []

        for lap_nev, lap_df in lapok_dict.items():
            lap_nev_szoveg = str(lap_nev)

            if fejadat_munkalap(lap_df):
                logger.info(f"ℹ️ [Szűrés] '{lap_nev}' munkalap fejadatként kezelve, nem tételes analitika.")
                continue

            if kihagyando_munkalap_nev(lap_nev_szoveg):
                logger.info(f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva (nem áfa analitika).")
                continue

            nav_sablon_df = nav_sablon_analitika_df(lap_df)
            if nav_sablon_df is not None:
                feldolgozando_df_lista.append(nav_sablon_df)
                logger.info(
                    f"✅ [Munkalap] '{lap_nev}' NAV mezőneves analitika sablonként feldolgozva "
                    f"({len(nav_sablon_df)} sor)."
                )
                continue

            tisztitott_lap_df = munkalap_tisztitasa(lap_df)
            if tisztitott_lap_df.empty:
                logger.info(f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva (üres lap).")
                continue

            hianyzo_oszlopok = hianyzo_analitika_oszlopok(tisztitott_lap_df)
            if hianyzo_oszlopok:
                logger.info(
                    f"ℹ️ [Szűrés] '{lap_nev}' munkalap kihagyva, mert nem teljes áfa analitika. "
                    f"Hiányzó oszlopok: {', '.join(sorted(hianyzo_oszlopok))}"
                )
                continue

            feldolgozando_df_lista.append(tisztitott_lap_df)
            logger.info(f"✅ [Munkalap] '{lap_nev}' hozzáadva a feldolgozáshoz ({len(tisztitott_lap_df)} sor).")

        if not feldolgozando_df_lista:
            hiba = "Nincs feldolgozható áfa munkalap az Excelben a szűrés után."
            logger.info(f"❌ [HIBA] {hiba}")
            allapot_uzenet("Állapot: Munkalap hiba", "#FF5555")
            show_error_popup("Adathiba", hiba)
            return

        df = pd.concat(feldolgozando_df_lista, ignore_index=True)
        previews.utolso_flat_dataframe = df.copy()

        # --- OFFLINE ADÓKÓD VALIDÁCIÓ ---
        hivatalos_kodok = hivatalos_adokodok_betoltese()
        if hivatalos_kodok and "SAP_Ado_Kod" in df.columns:
            hasznalt_kodok = set(str(code).strip() for code in df["SAP_Ado_Kod"].dropna().unique())
            hibas_kodok = [code for code in hasznalt_kodok if code not in hivatalos_kodok]

            if hibas_kodok:
                hiba_msg = (
                    "A szoftver érvénytelen (NAV által nem ismert) adókódo(ka)t talált az Excelben:\n\n"
                    f"{', '.join(hibas_kodok)}\n\n"
                    "A generálás biztonsági okokból leállt. Kérlek javítsd az Excel fájlt!"
                )
                logger.info(f"❌ [Adókód Hiba] Érvénytelen kódok a forrásban: {', '.join(hibas_kodok)}")
                allapot_uzenet("Állapot: Érvénytelen adókód", "#FF5555")
                show_error_popup("Érvénytelen Adókód", hiba_msg)
                return
            else:
                logger.info("🟢 [Adókód Validáció] Minden felhasznált adókód szerepel a NAV hivatalos katalógusában.")
        # --------------------------------

        sorok_szama = len(df)
        allapot_uzenet(f"Feldolgozva: {fajlnev} | Számlák: {sorok_szama} db", "#00FF88")
        logger.info(f"📊 [Statisztika] Összesített sorok száma a lapokról: {sorok_szama} db")
        logger.info(f"📑 [Oszlopok] {', '.join(map(str, df.columns.tolist()))}")
        mapping_dict = SAP_NAV_ADOKOD_MAPPING

        for elemzes_uzenet in sap_adokod_elemzes(df, mapping_dict):
            logger.info(f"[Adókód info] {elemzes_uzenet}")

        logger.info("[XML] NAV XML generálása folyamatban...")

        if not generate_nav_xml(
            df,
            KIMENETI_XML,
            mapping_dict,
            tax_number=config.normalized_tax_number(),
            declaration_metadata=bevallas_fejadatok,
        ):
            logger.info("❌ [XML HIBA] A generálás sikertelen.")
            allapot_uzenet("Állapot: XML generálási hiba", "#FF5555")
            show_error_popup("XML generálási hiba", "A NAV XML generálás sikertelen volt.")
            return

        if not os.path.exists(KIMENETI_XML):
            logger.info("❌ [XML HIBA] A generált XML fájl nem található.")
            allapot_uzenet("Állapot: XML fájl hiányzik", "#FF5555")
            show_error_popup("XML hiba", "A generált XML fájl nem található.")
            return

        with open(KIMENETI_XML, "r", encoding="utf-8") as f:
            previews.utolso_xml_tartalom = f.read()

        logger.info(f"✅ [XML] Elkészült: {KIMENETI_XML}")

        valid, valid_msg = validate_xml_with_xsd(KIMENETI_XML, VDR_MAPPA)
        if valid:
            logger.info(f"🟢 [XSD] {valid_msg}")
        else:
            logger.info(f"❌ [XSD HIBA] {valid_msg}")
            allapot_uzenet("Állapot: XSD validációs hiba", "#FF5555")
            show_error_popup("XSD validációs hiba", valid_msg)
            return

        logger.info("[eÁFA] XML API v2 kliens inicializálása...")
        client = EafaApiClient(config)
        upload_plan = client.create_upload_plan(previews.utolso_xml_tartalom)
        upload_request_xml = client.build_manage_declaration_upload_xml(upload_plan).decode("utf-8", errors="ignore")

        logger.info(f"[eÁFA] Cél URL: {client.base_url}/analyticsService/v1/manageDeclarationUpload")
        logger.info(f"[eÁFA] Bevallás mérete: {upload_plan.total_size} byte")
        logger.info(f"[eÁFA] Tömörített feltöltési méret: {upload_plan.upload_size} byte")
        logger.info(f"[eÁFA] Partíciók száma: {upload_plan.partition_count}")
        logger.info(f"[eÁFA] Tartalom SHA3-512: {upload_plan.content_hash}")
        logger.info(f"[eÁFA XML minta] {biztonsagos_xml_minta(upload_request_xml)}")

        if not van_valodi_nav_hitelesites(config):
            logger.info("ℹ️ [eÁFA] Valódi kulcsok hiányoznak, hálózati feltöltés kihagyva.")
            logger.info("ℹ️ [eÁFA] Az alkalmazás jelenleg prototípus / előellenőrzés módban fut.")
            allapot_uzenet("Állapot: eÁFA előellenőrzés kész", "#F1C40F")
        elif not eafa_feltoltes_engedelyezve(config):
            logger.info("ℹ️ [eÁFA] Valódi feltöltés nincs engedélyezve a jelölőnégyzettel.")
            logger.info("ℹ️ [eÁFA] Biztonsági okból PROD környezetben ez a prototípus nem tölt fel automatikusan.")
            allapot_uzenet("Állapot: Diagnosztikai eredmény elkészült", "#F1C40F")
        else:
            if not ask_yes_no_popup(
                "eÁFA TEST feltöltés megerősítése",
                "A valódi eÁFA TEST feltöltés engedélyezve van.\n\n"
                "A program most hálózati kérést küldene a NAV TEST eÁFA rendszerébe. "
                "Biztosan folytatod?",
            ):
                logger.info("ℹ️ [eÁFA] A felhasználó megszakította a valódi TEST feltöltést.")
                allapot_uzenet("Állapot: eÁFA feltöltés megszakítva", "#F1C40F")
                return

            logger.info("[eÁFA] manageDeclarationUpload indítása TEST környezetben...")
            upload_result = client.manage_declaration_upload(upload_plan)
            if not upload_result.get("success"):
                logger.info("❌ [eÁFA] manageDeclarationUpload hiba.")
                logger.info(f"HTTP: {upload_result.get('status_code')}")
                logger.info(f"Válasz: {str(upload_result.get('text', ''))[:1200]}")
                allapot_uzenet("Állapot: eÁFA upload hiba", "#FF5555")
                return

            upload_response = str(upload_result.get("text", ""))
            declaration_upload_id = extract_first_tag_value(upload_response, "declarationUploadId")
            logger.info("✅ [eÁFA] manageDeclarationUpload sikeres.")

            if not declaration_upload_id:
                logger.info("❌ [eÁFA] Nem található declarationUploadId a válaszban.")
                allapot_uzenet("Állapot: eÁFA upload azonosító hiányzik", "#FF5555")
                return

            for index, partition_bytes in enumerate(upload_plan.partitions, start=1):
                logger.info(f"[eÁFA] Partíció feltöltése: {index}/{upload_plan.partition_count}")
                partition_result = client.manage_declaration_partition(
                    declaration_upload_id,
                    index,
                    partition_bytes,
                )
                if not partition_result.get("success"):
                    logger.info("❌ [eÁFA] manageDeclarationPartition hiba.")
                    logger.info(f"HTTP: {partition_result.get('status_code')}")
                    logger.info(f"Válasz: {str(partition_result.get('text', ''))[:1200]}")
                    allapot_uzenet("Állapot: eÁFA partíció hiba", "#FF5555")
                    return

            logger.info("[eÁFA] manageDeclarationFinalize indítása előzetes jóváhagyás nélkül...")
            finalize_result = client.manage_declaration_finalize(
                declaration_upload_id,
                preliminary_confirmation=False,
            )
            if not finalize_result.get("success"):
                logger.info("❌ [eÁFA] manageDeclarationFinalize hiba.")
                logger.info(f"HTTP: {finalize_result.get('status_code')}")
                logger.info(f"Válasz: {str(finalize_result.get('text', ''))[:1200]}")
                allapot_uzenet("Állapot: eÁFA finalize hiba", "#FF5555")
                return

            declaration_processing_id = extract_first_tag_value(
                str(finalize_result.get("text", "")),
                "declarationProcessingId",
            )
            logger.info("✅ [eÁFA] Feldolgozásra átadva.")
            if declaration_processing_id:
                logger.info(f"[eÁFA] declarationProcessingId: {declaration_processing_id}")

            allapot_uzenet("Állapot: eÁFA feltöltés átadva feldolgozásra", "#00FF88")

        logger.divider()
        logger.info("✅ [Siker] Feldolgozás befejezve.")

    except Exception as e:
        logger.info(f"❌ [KRITIKUS HIBA] {str(e)}")
        logger.info(traceback.format_exc()[:2500])
        allapot_uzenet("Állapot: Kritikus hiba", "#FF5555")
        show_error_popup("Kritikus hiba", str(e))

    finally:
        pass


def automatikus_feldolgozas_inditasa(tech_user: str, password: str, sign_key: str, exchange_key: str, tax_number: str, environment: str, eafa_feltoltes: bool, allapot_uzenet: Any, show_error_popup: Any, ask_yes_no_popup: Any, reset_buttons: Any) -> None:
    def _run():
        feldolgozas_a_hatterben(tech_user, password, sign_key, exchange_key, tax_number, environment, eafa_feltoltes, allapot_uzenet, show_error_popup, ask_yes_no_popup)
        if reset_buttons:
            reset_buttons()
    worker = threading.Thread(target=_run, daemon=True)
    worker.start()

def kapcsolat_teszt_inditasa(tech_user: str, password: str, sign_key: str, exchange_key: str, tax_number: str, environment: str, allapot_uzenet: Any, show_error_popup: Any, reset_buttons: Any) -> None:
    def _run():
        kapcsolat_teszt_a_hatterben(tech_user, password, sign_key, exchange_key, tax_number, environment, allapot_uzenet, show_error_popup)
        if reset_buttons:
            reset_buttons()
    worker = threading.Thread(target=_run, daemon=True)
    worker.start()

