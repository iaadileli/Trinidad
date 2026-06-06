#!/usr/bin/env python3
"""
Descarga el catálogo completo de BEDCA y lo guarda en bedca_completo.csv
Uso: python3 fetch_bedca.py

Requiere: pip install requests
"""

import csv
import json
import time
import sys

try:
    import requests
except ImportError:
    sys.exit("Instala requests: pip install requests")

BASE = "https://www.bedca.net/bdpub/procquery.php"
LANG = "es"

# BEDCA usa peticiones POST con cuerpo XML
HEADERS = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}

def xml_food_list():
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soapenv:Body>"
        '<v1:foodlistsearch xmlns:v1="http://www.bedca.net/bdpub/v1">'
        f"<language>{LANG}</language>"
        "<food_name></food_name>"
        "</v1:foodlistsearch>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )

def xml_food_detail(food_id):
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soapenv:Body>"
        '<v1:foodvaluesbyid xmlns:v1="http://www.bedca.net/bdpub/v1">'
        f"<language>{LANG}</language>"
        f"<food_id>{food_id}</food_id>"
        "</v1:foodvaluesbyid>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )

# Nutrientes que nos interesan (IDs BEDCA)
# 1=Energía kcal, 2=Energía kJ, 3=Agua, 4=Proteínas, 5=Lípidos, 6=Carbohidratos disponibles
NUTRIENTES = {
    "1": "energia_kcal",
    "3": "agua_g",
    "4": "proteinas_g",
    "5": "lipidos_g",
    "6": "hidratos_g",
    "7": "fibra_g",
}

def get_food_list():
    """Devuelve lista de (food_id, food_name)."""
    # Intento 1: SOAP
    try:
        r = requests.post(BASE, data=xml_food_list(), headers=HEADERS, timeout=15)
        if r.status_code == 200 and "<food_id>" in r.text:
            import re
            ids   = re.findall(r"<food_id>(\d+)</food_id>", r.text)
            names = re.findall(r"<food_name>(.*?)</food_name>", r.text)
            return list(zip(ids, names))
    except Exception as e:
        print(f"  SOAP falló: {e}")

    # Intento 2: REST JSON
    try:
        url = f"https://www.bedca.net/bdpub/procquery.php?request=foodlistsearch&lang={LANG}&food_name="
        r = requests.get(url, timeout=15)
        data = r.json()
        if isinstance(data, list):
            return [(str(f.get("food_id", f.get("id", ""))), f.get("food_name", f.get("nombre", ""))) for f in data]
        if "foods" in data:
            return [(str(f["food_id"]), f["food_name"]) for f in data["foods"]]
    except Exception as e:
        print(f"  REST JSON falló: {e}")

    return []

def get_nutrientes(food_id):
    """Devuelve dict con valores nutricionales para un food_id."""
    try:
        r = requests.post(BASE, data=xml_food_detail(food_id), headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        import re
        result = {}
        # Busca bloques <component><c_class_id>N</c_class_id><c_value>V</c_value>
        blocks = re.findall(
            r"<c_class_id>(\d+)</c_class_id>.*?<c_value>([\d.,-]*)</c_value>",
            r.text, re.DOTALL
        )
        for cid, val in blocks:
            if cid in NUTRIENTES:
                try:
                    result[NUTRIENTES[cid]] = float(val.replace(",", "."))
                except ValueError:
                    result[NUTRIENTES[cid]] = ""
        return result
    except Exception:
        return {}

def main():
    print("Conectando con BEDCA...")
    foods = get_food_list()
    if not foods:
        sys.exit(
            "\n❌ No se pudo obtener la lista de alimentos.\n"
            "Comprueba tu conexión o que bedca.net esté accesible.\n"
            "También puedes descargar el Excel oficial en:\n"
            "  https://www.bedca.net/bdpub/index.php"
        )

    print(f"  {len(foods)} alimentos encontrados. Descargando valores nutricionales...")

    rows = []
    for i, (fid, fname) in enumerate(foods, 1):
        nut = get_nutrientes(fid)
        rows.append({
            "food_id": fid,
            "nombre": fname,
            "energia_kcal": nut.get("energia_kcal", ""),
            "proteinas_g": nut.get("proteinas_g", ""),
            "lipidos_g": nut.get("lipidos_g", ""),
            "hidratos_g": nut.get("hidratos_g", ""),
            "fibra_g": nut.get("fibra_g", ""),
            "agua_g": nut.get("agua_g", ""),
        })
        if i % 50 == 0:
            print(f"  {i}/{len(foods)}...")
        time.sleep(0.15)  # no saturar el servidor

    out = "bedca_completo.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Guardado en {out}  ({len(rows)} alimentos)")

if __name__ == "__main__":
    main()
