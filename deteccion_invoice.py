import os
import re
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_PATH = r"C:\Program Files\Tesseract-OCR\tessdata"

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
if os.path.isdir(TESSDATA_PATH):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_PATH

# 📂 Carpeta donde estarán las facturas
CARPETA = r"C:\PruebaConocimientos"

OCR_LANG = "eng+spa"
OCR_CONFIG = "--oem 3 --psm 6"

# Palabras clave de TOTAL más amplias
TOTAL_PATTERNS = (
    "TOTAL", "Total", "Amount Due", "AMOUNT DUE", "Grand Total", "GRAND TOTAL",
    "Importe Total", "IMPORTE TOTAL", "Total a pagar", "TOTAL A PAGAR"
)

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
        # Muchos puntos -> quita miles
        elif s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(s)
    except ValueError:
        return None

def buscar_montos(texto: str):
    """Encuentra valores numéricos con formato de dinero."""
    # Captura 12, 12.34, 1.234,56, etc.
    patron = r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2})"
    brutos = re.findall(patron, texto)
    # Normaliza y quita duplicados conservando orden
    vistos = set()
    montos = []
    for b in brutos:
        val = _normaliza_num(b)
        if val is None:
            continue
        if val not in vistos:
            vistos.add(val)
            montos.append(val)
    # Ordenados (de menor a mayor) para facilitar chequeo visual
    montos.sort()
    return montos

def _hay_total(texto: str) -> bool:
    t = texto.upper()
    return any(p.upper() in t for p in TOTAL_PATTERNS)

def procesar_factura(ruta: str):
    """Procesa una factura e imprime resultados."""
    try:
        texto = extraer_texto(ruta).strip()

        print(f"\n📑 Analizando archivo: {os.path.basename(ruta)}")
        print("-" * 70)
        # Si quieres ver el OCR completo, descomenta:
        # print(texto)

        montos = buscar_montos(texto)

        if _hay_total(texto) and montos:
            print("✔️ Se localizó una referencia a TOTAL junto con valores.")

            vista = ", ".join(f"{m:,.2f}" for m in montos[:15])
            print("💰 Cantidades (normalizadas):", vista + (" ..." if len(montos) > 15 else ""))
            # Hint simple: muestra el mayor como candidato a total
            print(f"🧮 Candidato a Total (mayor detectado): {montos[-1]:,.2f}")
        elif montos:
            print("ℹ️ Se identificaron cifras numéricas, pero no aparece una palabra de TOTAL.")
            print("💰 Cantidades (normalizadas):", ", ".join(f"{m:,.2f}" for m in montos[:15]))
        else:
            print("⚠️ No se hallaron montos ni referencias a un total.")

    except Exception as e:
        print(f"❌ Ocurrió un problema procesando {ruta}: {e}")

def main():
    print("🔎 Revisando imágenes dentro de:", CARPETA)
    try:
        archivos = [a for a in os.listdir(CARPETA) if a.lower().endswith((".png", ".jpg", ".jpeg"))]
    except FileNotFoundError:
        print("🚫 La carpeta no existe. Verifica la ruta en CARPETA.")
        return

    if not archivos:
        print("🚫 No se encontraron imágenes para procesar.")
        return

    for archivo in archivos:
        procesar_factura(os.path.join(CARPETA, archivo))

if __name__ == "__main__":
    main()
