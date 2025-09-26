import os
import re
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

# =========================
#  Configuración Tesseract
# =========================
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_PATH  = r"C:\Program Files\Tesseract-OCR\tessdata"

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
if os.path.isdir(TESSDATA_PATH):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_PATH

# =========================
#  Carpetas de entrada
# =========================
CARPETA_FACTURAS        = r"C:\PruebaConocimientos\PruebaFacturas"     # aquí tus facturas
CARPETA_CALIFICACIONES  = r"C:\PruebaConocimientos\PruebaCalificaciones"    # aquí tus boletines de notas (imagen como la que enviaste)

# =========================
#  OCR settings
# =========================
OCR_LANG   = "eng+spa"
OCR_CONFIG = "--oem 3 --psm 6"

# Palabras clave de TOTAL más amplias (facturas)
TOTAL_PATTERNS = (
    "TOTAL", "Total", "Amount Due", "AMOUNT DUE", "Grand Total", "GRAND TOTAL",
    "Importe Total", "IMPORTE TOTAL", "Total a pagar", "TOTAL A PAGAR"
)

# =========================
#  Utilidades comunes
# =========================
def preprocesar_imagen(ruta: str):
    """Aplica filtros para mejorar la lectura OCR."""
    img = Image.open(ruta).convert("L")
    w, h = img.size
    if max(w, h) < 1600:
        img = img.resize((int(w * 1.6), int(h * 1.6)), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.6)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img

def extraer_texto(ruta: str) -> str:
    """Ejecuta OCR sobre la imagen dada."""
    img = preprocesar_imagen(ruta)
    return pytesseract.image_to_string(img, lang=OCR_LANG, config=OCR_CONFIG)

def _normaliza_num(s: str):
    """Convierte '1.234,56' o '1,234.56' a float 1234.56 si es posible."""
    s = s.strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        if "," in s and s.count(",") == 1:
            s = s.replace(",", ".")
        elif s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(s)
    except ValueError:
        return None

# =========================
#  BLOQUE FACTURAS
# =========================
def buscar_montos(texto: str):
    """Encuentra valores numéricos con formato de dinero."""
    patron = r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2})"
    brutos = re.findall(patron, texto)
    vistos = set()
    montos = []
    for b in brutos:
        val = _normaliza_num(b)
        if val is None:
            continue
        if val not in vistos:
            vistos.add(val)
            montos.append(val)
    montos.sort()
    return montos

def _hay_total(texto: str) -> bool:
    t = texto.upper()
    return any(p.upper() in t for p in TOTAL_PATTERNS)

def procesar_factura(ruta: str):
    """Procesa una factura e imprime resultados (idéntico flujo al tuyo, con mejoras)."""
    try:
        texto = extraer_texto(ruta).strip()

        print(f"\n📑 Analizando FACTURA: {os.path.basename(ruta)}")
        print("-" * 72)
        # print(texto)  # descomenta si quieres ver el OCR crudo

        montos = buscar_montos(texto)

        if _hay_total(texto) and montos:
            print("✔️ Se localizó una referencia a TOTAL junto con valores.")
            vista = ", ".join(f"{m:,.2f}" for m in montos[:15])
            print("💰 Cantidades (normalizadas):", vista + (" ..." if len(montos) > 15 else ""))
            print(f"🧮 Candidato a Total (mayor detectado): {montos[-1]:,.2f}")
        elif montos:
            print("ℹ️ Se identificaron cifras numéricas, pero no aparece una palabra de TOTAL.")
            print("💰 Cantidades (normalizadas):", ", ".join(f"{m:,.2f}" for m in montos[:15]))
        else:
            print("⚠️ No se hallaron montos ni referencias a un total.")

    except Exception as e:
        print(f"❌ Ocurrió un problema procesando {ruta}: {e}")

def correr_facturas():
    print("\n🔎 Revisando imágenes de FACTURAS en:", CARPETA_FACTURAS)
    try:
        archivos = [a for a in os.listdir(CARPETA_FACTURAS) if a.lower().endswith((".png", ".jpg", ".jpeg"))]
    except FileNotFoundError:
        print("🚫 La carpeta de FACTURAS no existe. Verifica CARPETA_FACTURAS.")
        return

    if not archivos:
        print("🚫 No se encontraron imágenes de facturas.")
        return

    for archivo in archivos:
        procesar_factura(os.path.join(CARPETA_FACTURAS, archivo))

# =========================
#  BLOQUE CALIFICACIONES
# =========================
# Claves para detectar el bloque de notas finales
NOTA_FINAL_KEYS = (
    "NOTA FINAL", "Nota Final", "Nota final", "NOTA  FINAL",  # variaciones
    "FINAL", "N. FINAL"  # fallback en OCR
)

def _es_linea_cabecera_notas(ln: str) -> bool:
    up = ln.upper()
    return any(k in up for k in NOTA_FINAL_KEYS)

def _extrae_ult_num_0_100(ln: str):
    """
    Toma el último número (0-100) de la línea. Soporta 97, 100, 98.0, 98,0, etc.
    Evita capturar otras cifras (años, códigos) por el rango.
    """
    # Busca números con decimales opcionales usando . o ,
    numeros = re.findall(r"(?:\d{1,3}(?:[.,]\d{1,2})?)", ln)
    if not numeros:
        return None
    # Último número en la línea suele ser la nota final
    for num in reversed(numeros):
        val = _normaliza_num(num)
        if val is None:
            continue
        if 0.0 <= val <= 100.0:
            return val
    return None

def buscar_notas_finales(texto: str):
    """
    Heurística:
    1) Localiza la línea que parece ser la cabecera con 'NOTA FINAL'.
    2) Desde ahí hacia abajo, toma por cada línea no vacía el último número 0..100.
    3) Se detiene cuando encuentra un separador grande o una sección de observaciones.
    """
    lineas = [ln for ln in texto.splitlines()]
    if not lineas:
        return []

    # 1) Encuentra el índice de cabecera 'NOTA FINAL'
    start_idx = None
    for i, ln in enumerate(lineas):
        if _es_linea_cabecera_notas(ln):
            start_idx = i
            break

    # Si no encontramos cabecera, fallback: escanear todas las líneas buscando patrones de materias + último número
    notas = []
    if start_idx is None:
        for ln in lineas:
            ln_strip = ln.strip()
            if not ln_strip:
                continue
            if "OBSERVACIONES" in ln_strip.upper():
                break
            v = _extrae_ult_num_0_100(ln_strip)
            if v is not None:
                notas.append(v)
        # Filtra ruido: muchas líneas traen varios números; nos quedamos con valores típicos de notas
        return [n for n in notas if 30.0 <= n <= 100.0]

    # 2) Recorre desde la cabecera hacia abajo
    for ln in lineas[start_idx + 1:]:
        s = ln.strip()
        if not s:
            continue
        # Corta si llegamos a una sección de "Observaciones"
        if "OBSERVACIONES" in s.upper():
            break
        v = _extrae_ult_num_0_100(s)
        if v is not None:
            notas.append(v)

    # 3) Limpieza: mantén sólo valores razonables de notas
    notas = [n for n in notas if 30.0 <= n <= 100.0]
    # Quita duplicados conservando orden (por si el OCR duplica líneas)
    vistos = set()
    limpias = []
    for n in notas:
        key = round(n, 2)
        if key not in vistos:
            vistos.add(key)
            limpias.append(n)
    return limpias

def procesar_boletin(ruta: str):
    """Procesa un boletín de calificaciones: extrae notas finales y calcula promedio."""
    try:
        texto = extraer_texto(ruta)
        print(f"\n🎓 Analizando BOLETÍN: {os.path.basename(ruta)}")
        print("-" * 72)
        # print(texto)  # descomenta para ver el OCR crudo

        notas = buscar_notas_finales(texto)
        if notas:
            prom = sum(notas) / len(notas)
            listado = ", ".join(f"{n:,.2f}" for n in notas)
            print(f"📋 Notas finales detectadas ({len(notas)}): {listado}")
            print(f"📈 Promedio de NOTA FINAL: {prom:,.2f}")
        else:
            print("⚠️ No se detectaron notas finales. Verifica la calidad de la imagen o la cabecera 'NOTA FINAL'.")

    except Exception as e:
        print(f"❌ Error procesando boletín {os.path.basename(ruta)}: {e}")

def correr_calificaciones():
    print("\n🔎 Revisando imágenes de CALIFICACIONES en:", CARPETA_CALIFICACIONES)
    try:
        archivos = [a for a in os.listdir(CARPETA_CALIFICACIONES) if a.lower().endswith((".png", ".jpg", ".jpeg"))]
    except FileNotFoundError:
        print("🚫 La carpeta de CALIFICACIONES no existe. Verifica CARPETA_CALIFICACIONES.")
        return

    if not archivos:
        print("🚫 No se encontraron imágenes de calificaciones.")
        return

    for archivo in archivos:
        procesar_boletin(os.path.join(CARPETA_CALIFICACIONES, archivo))

# =========================
#  MAIN
# =========================
def main():
    # Ejecuta ambos flujos: facturas y calificaciones
    correr_facturas()
    correr_calificaciones()

if __name__ == "__main__":
    main()
