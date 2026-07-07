from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element, SubElement, ElementTree

import pandas as pd


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _num_text(value: Any) -> str:
    text = _safe_text(value).replace(" ", "").replace(",", ".")
    return text or "0"


def generate_nav_xml(
    df: pd.DataFrame,
    output_path: str,
    mapping_dict: dict[str, str],
    tax_number: str,
    declaration_metadata: dict[str, Any] | None = None,
) -> bool:
    try:
        declaration_metadata = declaration_metadata or {}
        root = Element("eAfaBevallas")
        head = SubElement(root, "Fejlec")
        SubElement(head, "Adoszam").text = tax_number
        for key, value in declaration_metadata.items():
            if value is None:
                continue
            SubElement(head, str(key)).text = _safe_text(value)

        lines = SubElement(root, "AnalitikaTetelek")
        for _, row in df.iterrows():
            item = SubElement(lines, "Tetel")
            SubElement(item, "sourceDocumentId").text = _safe_text(row.get("Szamlaszam"))
            SubElement(item, "taxpointDate").text = _safe_text(row.get("Teljesites_Datuma"))
            SubElement(item, "taxNumber").text = _safe_text(row.get("Partner_Adoszam"))
            sap_kod = _safe_text(row.get("SAP_Ado_Kod"))
            SubElement(item, "standardTaxCode").text = mapping_dict.get(sap_kod, sap_kod)
            SubElement(item, "taxBase").text = _num_text(row.get("Netto_Ertek"))
            SubElement(item, "taxAmount").text = _num_text(row.get("Afa_Ertek"))

        ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False
