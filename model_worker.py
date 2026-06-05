import json
import os
import sys
from pathlib import Path

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "modelo"
MODEL_PATH = MODEL_DIR / "modelo_resnet50.keras"
CONFIG_PATH = MODEL_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def predict(image_path: str):
    config = load_config()
    img_size = config.get("img_size", [160, 160])
    target_size = (int(img_size[1]), int(img_size[0]))

    model = tf.keras.models.load_model(MODEL_PATH)

    image = Image.open(image_path).convert("RGB")
    image = image.resize(target_size)
    arr = tf.keras.preprocessing.image.img_to_array(image)
    arr = np.expand_dims(arr, 0)

    probs = model.predict(arr, verbose=0)[0]

    print(json.dumps({"probabilities": probs.tolist()}))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: model_worker.py <image_path>", file=sys.stderr)
        sys.exit(2)
    predict(sys.argv[1])
