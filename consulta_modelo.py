import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "modelo"
MODEL_PATH = MODEL_DIR / "modelo_resnet50.keras"
CONFIG_PATH = MODEL_DIR / "config.json"


with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    CONFIG = json.load(file)

CLASES = CONFIG["clases"]

modelo = tf.keras.models.load_model(MODEL_PATH)

# config.json stores [height, width]; Pillow expects (width, height)
img_size = CONFIG.get("img_size", [160, 160])
IMG_SIZE = (int(img_size[1]), int(img_size[0]))
THRESHOLD = float(CONFIG.get("confidence_threshold", 0.65))

print(f"Modelo cargado — Clases: {CLASES}")
print(f"Entrada del modelo: {IMG_SIZE}")


def predecir(ruta_imagen, threshold=THRESHOLD):
    imagen = Image.open(ruta_imagen).convert("RGB")
    imagen = imagen.resize(IMG_SIZE)
    arr = tf.keras.preprocessing.image.img_to_array(imagen)
    arr = np.expand_dims(arr, axis=0)

    probs = modelo.predict(arr, verbose=0)[0]
    confianza = float(np.max(probs))
    indice = int(np.argmax(probs))
    clase = CLASES[indice] if confianza >= threshold else "RECHAZADO"

    return {
        "clase": clase,
        "confianza": round(confianza, 4),
        "valida": confianza >= threshold,
        "probabilidades": {CLASES[i]: round(float(probs[i]), 4) for i in range(len(CLASES))},
    }


if __name__ == "__main__":
    resultado = predecir("/ruta/a/tu/documento.jpg")

    print(f"\nClase     : {resultado['clase']}")
    print(f"Confianza : {resultado['confianza']}")
    print(f"Válida    : {resultado['valida']}")
    print("\nTodas las probabilidades:")
    for clase, prob in resultado["probabilidades"].items():
        print(f"  {clase}: {prob}")