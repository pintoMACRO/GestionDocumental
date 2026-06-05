import io
import json
import mimetypes
from functools import lru_cache
from pathlib import Path
import os
import time

# Workarounds for occasional TensorFlow native crashes on some systems:
# - disable oneDNN optimizations which can cause segfaults with certain CPU/lib combinations
# - limit OpenMP threads to reduce contention
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import tensorflow as tf
from PIL import Image
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "modelo"
MODEL_PATH = MODEL_DIR / "modelo_resnet50.keras"
CONFIG_PATH = MODEL_DIR / "config.json"
INDEX_PATH = BASE_DIR / "index.html"
MAX_UPLOADS = 20
MODEL_THRESHOLD = 65


def log_message(message: str) -> None:
    print(f"[predict] {message}", flush=True)


@lru_cache(maxsize=1)
def load_model_and_classes():
    model = tf.keras.models.load_model(MODEL_PATH)

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    classes = config["clases"]

    # config['img_size'] viene como [alto, ancho] — Pillow espera (ancho, alto)
    img_size = config.get("img_size", [160, 160])
    target_size = (int(img_size[1]), int(img_size[0]))

    return model, classes, target_size


def load_config_only():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    classes = config.get("clases", [])
    img_size = config.get("img_size", [160, 160])
    target_size = (int(img_size[1]), int(img_size[0]))
    return classes, target_size


def preprocess_image(image: Image.Image, target_size: tuple[int, int]) -> np.ndarray:
    image = image.convert("RGB")
    image = image.resize(target_size)
    image_array = tf.keras.preprocessing.image.img_to_array(image)
    image_array = np.expand_dims(image_array, axis=0)
    return image_array


def resolve_class_name(classes, index: int) -> str:
    if isinstance(classes, dict):
        return str(classes.get(str(index), classes.get(index, index)))
    return str(classes[index])


def render_document_preview(document_bytes: bytes, filename: str = "") -> Image.Image:
    filename_lower = filename.lower()
    content_is_pdf = filename_lower.endswith(".pdf")

    if content_is_pdf:
        try:
            import fitz
        except Exception as exc:
            raise ValueError("Se recibió un PDF, pero el servidor no tiene soporte para convertirlo a imagen.") from exc

        pdf_document = fitz.open(stream=document_bytes, filetype="pdf")
        if pdf_document.page_count == 0:
            pdf_document.close()
            raise ValueError("El PDF no contiene páginas.")

        page = pdf_document.load_page(0)
        pixmap = page.get_pixmap(alpha=False)
        mode = "RGB" if pixmap.n < 4 else "RGBA"
        image = Image.frombytes(mode, [pixmap.width, pixmap.height], pixmap.samples)
        pdf_document.close()
        return image.convert("RGB")

    image = Image.open(io.BytesIO(document_bytes))
    image.load()
    return image.convert("RGB")


async def read_uploaded_document(uploaded_file):
    document_bytes = await uploaded_file.read()
    filename = Path(getattr(uploaded_file, "filename", "") or "documento").name
    image = render_document_preview(document_bytes, filename)
    return image, document_bytes, filename


def classify_image(model, image: Image.Image, classes, target_size: tuple[int, int]):
    started_at = time.perf_counter()
    try:
        log_message(f"Ejecutando inferencia directa con modelo {MODEL_PATH}")
        if model is None:
            model, classes, target_size = load_model_and_classes()

        image_array = preprocess_image(image, target_size)
        predictions = model.predict(image_array, verbose=0)[0]
        elapsed = time.perf_counter() - started_at
        log_message(f"Inferencia completada en {elapsed:.2f}s")
    except Exception as exc:
        log_message(f"La inferencia directa falló: {exc}")
        raise

    predicted_index = int(np.argmax(predictions))
    confidence = float(np.max(predictions)) * 100
    predicted_label = resolve_class_name(classes, predicted_index)
    warning_message = None

    if confidence <= MODEL_THRESHOLD:
        predicted_label = "Otros"
        warning_message = "La confianza es baja. Tome bien la foto y vuelva a intentar para obtener una mejor clasificación."

    log_message(f"Resultado: {predicted_label} ({confidence:.2f}%)")

    probabilities = []
    for index, probability in enumerate(predictions):
        probabilities.append(
            {
                "index": index,
                "label": resolve_class_name(classes, index),
                "probability": float(probability),
            }
        )

    return {
        "predicted_label": predicted_label,
        "confidence": confidence,
        "predicted_index": predicted_index,
        "probabilities": probabilities,
        "warning_message": warning_message,
        "method": f"ResNet50 ({confidence:.2f}%)",
    }


def get_uploaded_files(form):
    uploaded_files = []
    for field_name in ("documents", "images", "document", "image", "files"):
        if hasattr(form, "getlist"):
            field_files = form.getlist(field_name) or []
            if field_files:
                uploaded_files.extend(field_files)
                break
        else:
            uploaded_file = form.get(field_name)
            if uploaded_file is not None:
                uploaded_files.append(uploaded_file)
                break

    return uploaded_files


async def homepage(request):
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return HTMLResponse("<h1>Falta index.html</h1>", status_code=404)


async def predict(request):
    form = await request.form()
    uploaded_files = get_uploaded_files(form)

    log_message(f"Solicitud /predict recibida con {len(uploaded_files)} archivo(s)")

    if not uploaded_files:
        return JSONResponse(
            {"error": "Debes enviar al menos un documento en el campo 'documents' o 'document'."},
            status_code=400,
        )

    if len(uploaded_files) > MAX_UPLOADS:
        return JSONResponse({"error": f"Solo se permiten hasta {MAX_UPLOADS} documentos por solicitud."}, status_code=400)

    classes, target_size = load_config_only()

    results = []
    for uploaded_file in uploaded_files:
        try:
            image, _, filename = await read_uploaded_document(uploaded_file)
        except Exception as exc:
            return JSONResponse({"error": f"No se pudo leer el documento {uploaded_file.filename}: {exc}"}, status_code=400)

        log_message(f"Procesando archivo {filename}")
        result = classify_image(None, image, classes, target_size)
        result["filename"] = filename
        results.append(result)

    log_message(f"Lote completado con {len(results)} resultado(s)")

    return JSONResponse(
        {
            "count": len(results),
            "results": results,
            "download_hint": "Usa el botón de descarga de cada tipo para obtener los documentos organizados.",
        }
    )


async def download(request):
    form = await request.form()
    uploaded_files = get_uploaded_files(form)

    if not uploaded_files:
        return JSONResponse({"error": "Debes enviar al menos un documento."}, status_code=400)

    if len(uploaded_files) != 1:
        return JSONResponse({"error": "La descarga ahora es individual. Selecciona un solo documento por vez."}, status_code=400)

    try:
        uploaded_file = uploaded_files[0]
        document_bytes = await uploaded_file.read()
        filename = Path(getattr(uploaded_file, "filename", "documento")).name
    except Exception as exc:
        return JSONResponse({"error": f"No se pudo procesar el documento: {exc}"}, status_code=400)

    content_type = getattr(uploaded_file, "content_type", None) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(document_bytes), media_type=content_type, headers=headers)


async def preview(request):
    form = await request.form()
    uploaded_files = get_uploaded_files(form)

    if not uploaded_files:
        return JSONResponse({"error": "Debes enviar un documento para previsualizarlo."}, status_code=400)

    uploaded_file = uploaded_files[0]

    try:
        document_bytes = await uploaded_file.read()
        filename = Path(getattr(uploaded_file, "filename", "documento")).name
    except Exception as exc:
        return JSONResponse({"error": f"No se pudo generar la vista previa: {exc}"}, status_code=400)

    content_type = getattr(uploaded_file, "content_type", None) or mimetypes.guess_type(filename)[0]
    if not content_type:
        if filename.lower().endswith(".pdf"):
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"

    preview_buffer = io.BytesIO(document_bytes)
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    return StreamingResponse(preview_buffer, media_type=content_type, headers=headers)


routes = [
    Route("/", homepage, methods=["GET"]),
    Route("/predict", predict, methods=["POST"]),
    Route("/download", download, methods=["POST"]),
    Route("/preview", preview, methods=["POST"]),
]


app = Starlette(debug=True, routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)