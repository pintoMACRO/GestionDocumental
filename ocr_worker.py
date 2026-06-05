import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from rapidfuzz import fuzz

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "modelo" / "config.json"

PALABRAS_CLAVE = {
    "CUESTIONARIO DE CAPACIDADES Y DIFICULTADES (SDQ-Cas) M 11-17": ["11-17", "11 17", "M 11"],
    "CUESTIONARIO DE CAPACIDADES Y DIFICULTADES (SDQ-Cas) M 4-17": ["4-17", "4 17", "M 4"],
    "CUESTIONARIO DE COMPORTAMIENTO INFANTIL PARA LA EDAD DE 4 A 16 AÑOS - CBCL": ["CBCL", "COMPORTAMIENTO INFANTIL"],
    "CUESTIONARIO DE ESTILOS EDUCATIVOS PARENTALES - CEEP": ["CEEP", "ESTILOS EDUCATIVOS"],
    "FORMATO EVALUACION RAPIDA DE ESENCIALES PARA LA VIDA": ["ESENCIALES PARA LA VIDA", "EVALUACION RAPIDA"],
}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)
def run_ocr(image_path: str):
    import easyocr

    image = Image.open(image_path).convert("RGB")
    image_array = np.array(image)
    height = image_array.shape[0]
    top_crop = image_array[: max(1, int(height * 0.20)), :, :]

    reader = easyocr.Reader(["es", "en"], gpu=False)
    results = reader.readtext(top_crop)
    text = " ".join(result[1] for result in results).upper().strip()

    best_class = None
    best_score = 0

    for class_name, keywords in PALABRAS_CLAVE.items():
        for keyword in keywords:
            score = fuzz.partial_ratio(keyword.upper(), text)
            if score > best_score:
                best_score = score
                best_class = class_name

    print(json.dumps({"text": text, "score": best_score, "class": best_class}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: ocr_worker.py <image_path>", file=sys.stderr)
        sys.exit(2)

    run_ocr(sys.argv[1])