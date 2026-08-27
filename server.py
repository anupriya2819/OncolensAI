"""
OncoLens Insight Compass — FastAPI backend
Prototype / hackathon decision-support service.

Architecture
------------
1) H&E image -> 224x224 tiles
2) owkin/phikon-v2 -> 1024-dim CLS features
3) Attention-MIL head -> slide-level malignancy probability (ONLY when a trained checkpoint exists)
4) Patch attention -> OpenCV JET heatmap overlay
5) Rule-based reflex biomarker prioritization
6) Optional local LLM narrative synthesis, with deterministic safe template fallback

IMPORTANT
---------
- Phikon-v2 is a feature extractor. It is NOT, by itself, a trained breast-cancer classifier.
- If no trained MIL checkpoint is present, this server uses a clearly labeled deterministic DEMO score
  so the end-to-end UI can be demonstrated. DEMO scores are not medical predictions.
- Never use this prototype for patient care without proper training, calibration, external validation,
  clinical governance, security, and regulatory review.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from transformers import AutoImageProcessor, AutoModel


# -----------------------------
# Configuration
# -----------------------------
MODEL_NAME = os.getenv("PHIKON_MODEL", "owkin/phikon-v2")
MIL_CHECKPOINT = os.getenv("MIL_CHECKPOINT", "mil_head.pt")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_PATCHES = int(os.getenv("MAX_PATCHES", "64"))
TILE_SIZE = int(os.getenv("TILE_SIZE", "224"))
STRIDE = int(os.getenv("TILE_STRIDE", "168"))
PHIKON_BATCH_SIZE = int(os.getenv("PHIKON_BATCH_SIZE", "2"))
ENABLE_LOCAL_LLM = os.getenv("ENABLE_LOCAL_LLM", "0") == "1"
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "google/flan-t5-small")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# -----------------------------
# FastAPI app + permissive CORS
# -----------------------------
app = FastAPI(
    title="OncoLens Insight Compass API",
    version="0.1.0",
    description="Hackathon prototype API for AI-assisted pathology review.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Attention-MIL model
# -----------------------------
class AttentionMIL(nn.Module):
    """
    Gated-ish attention MIL head for a bag of tile features.

    Input:
        x: [N_tiles, in_dim]
    Output:
        logit: scalar slide-level logit
        attention: [N_tiles] normalized attention weights
    """

    def __init__(
        self,
        in_dim: int = 1024,
        hidden_dim: int = 256,
        attention_dim: int = 128,
        dropout: float = 0.20,
    ):
        super().__init__()
        self.proj = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )
        self.attention_v = nn.Sequential(
            nn.Linear(hidden_dim, attention_dim),
            nn.Tanh(),
        )
        self.attention_u = nn.Sequential(
            nn.Linear(hidden_dim, attention_dim),
            nn.Sigmoid(),
        )
        self.attention_w = nn.Linear(attention_dim, 1)
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h = self.proj(x)                              # [N, H]
        a = self.attention_v(h) * self.attention_u(h)
        a = self.attention_w(a).squeeze(-1)          # [N]
        a = torch.softmax(a, dim=0)
        bag = torch.sum(a.unsqueeze(-1) * h, dim=0)  # [H]
        logit = self.classifier(bag).squeeze(-1)
        return logit, a


class ModelManager:
    def __init__(self):
        self.processor: Optional[AutoImageProcessor] = None
        self.phikon: Optional[AutoModel] = None
        self.phikon_ready = False

        self.mil = AttentionMIL().to(DEVICE)
        self.mil.eval()
        self.checkpoint_loaded = False

        self._local_llm = None
        self._load_mil_checkpoint_if_available()

    def _load_mil_checkpoint_if_available(self) -> None:
        ckpt = Path(MIL_CHECKPOINT)
        if not ckpt.exists():
            print(f"[OncoLens] MIL checkpoint not found at: {ckpt.resolve()}")
            print("[OncoLens] Server will run in DEMO_UNVALIDATED mode.")
            return

        try:
            state = torch.load(str(ckpt), map_location=DEVICE)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]

            # Allow checkpoints saved with a "mil." prefix.
            if isinstance(state, dict):
                cleaned = {}
                for key, value in state.items():
                    cleaned[key.removeprefix("mil.")] = value
                state = cleaned

            self.mil.load_state_dict(state, strict=True)
            self.mil.eval()
            self.checkpoint_loaded = True
            print(f"[OncoLens] Loaded trained MIL checkpoint: {ckpt.resolve()}")
        except Exception as exc:
            print(f"[OncoLens] Could not load MIL checkpoint: {exc}")
            print("[OncoLens] Falling back to DEMO_UNVALIDATED mode.")
            self.checkpoint_loaded = False

    def load_phikon(self) -> bool:
        if self.phikon_ready:
            return True

        try:
            print(f"[OncoLens] Loading {MODEL_NAME} on {DEVICE} ...")
            self.processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
            self.phikon = AutoModel.from_pretrained(MODEL_NAME)
            self.phikon.to(DEVICE)
            self.phikon.eval()
            self.phikon_ready = True
            print("[OncoLens] Phikon-v2 ready.")
            return True
        except Exception as exc:
            print(f"[OncoLens] Phikon-v2 unavailable: {exc}")
            print("[OncoLens] Feature extraction will use a deterministic 1024-D fallback.")
            self.phikon_ready = False
            self.processor = None
            self.phikon = None
            return False

    @torch.inference_mode()
    def extract_features(self, patches: Sequence[Image.Image]) -> Tuple[torch.Tensor, str]:
        """
        Returns [N, 1024] tile features and a feature-mode label.
        """
        if self.load_phikon():
            all_features: List[torch.Tensor] = []
            assert self.processor is not None
            assert self.phikon is not None

            for start in range(0, len(patches), PHIKON_BATCH_SIZE):
                batch = patches[start:start + PHIKON_BATCH_SIZE]
                inputs = self.processor(images=list(batch), return_tensors="pt")
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                outputs = self.phikon(**inputs)
                features = outputs.last_hidden_state[:, 0, :]  # CLS token [B,1024]
                all_features.append(features.detach().float().cpu())

            return torch.cat(all_features, dim=0), "PHIKON_V2_CLS_1024"

        # Fast fallback: normalized 32x32 grayscale = 1024 values.
        fallback = []
        for patch in patches:
            arr = np.asarray(patch.resize((32, 32)).convert("L"), dtype=np.float32) / 255.0
            vec = arr.reshape(-1)
            vec = (vec - vec.mean()) / (vec.std() + 1e-6)
            fallback.append(vec.astype(np.float32))

        return torch.from_numpy(np.stack(fallback, axis=0)), "MOCK_FEATURES_1024"

    def get_local_llm(self):
        if not ENABLE_LOCAL_LLM:
            return None
        if self._local_llm is not None:
            return self._local_llm

        try:
            # Imported lazily so the default demo starts faster.
            from transformers import pipeline
            print(f"[OncoLens] Loading local report LLM: {LOCAL_LLM_MODEL}")
            # Keep text generation on CPU by default to avoid competing with Phikon for VRAM.
            self._local_llm = pipeline(
                "text2text-generation",
                model=LOCAL_LLM_MODEL,
                device=-1,
            )
            return self._local_llm
        except Exception as exc:
            print(f"[OncoLens] Local LLM unavailable; using structured template: {exc}")
            return None


manager = ModelManager()


# -----------------------------
# Image helpers
# -----------------------------
def open_rgb_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")

        # Re-materialize pixels into a new image to avoid carrying EXIF/metadata forward.
        arr = np.asarray(image, dtype=np.uint8)
        return Image.fromarray(arr, mode="RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {exc}")


def tissue_fraction(tile_rgb: np.ndarray) -> float:
    """
    Simple background filter:
    counts pixels that are not close to pure white and have some chromatic content.
    """
    if tile_rgb.size == 0:
        return 0.0

    hsv = cv2.cvtColor(tile_rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[..., 1]
    value = hsv[..., 2]

    nonwhite = value < 245
    colored = saturation > 12
    tissue = nonwhite | colored
    return float(tissue.mean())


def extract_patches(
    image: Image.Image,
    tile_size: int = TILE_SIZE,
    stride: int = STRIDE,
    max_patches: int = MAX_PATCHES,
) -> Tuple[List[Image.Image], List[Tuple[int, int, int, int]]]:
    """
    Tiles the uploaded image and keeps tissue-containing regions.
    Positions are (x, y, width, height) in the original image coordinate space.
    """
    width, height = image.size

    # If the image is smaller than one tile, use the whole image as one region.
    if width <= tile_size and height <= tile_size:
        patch = image.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        return [patch], [(0, 0, width, height)]

    xs = list(range(0, max(1, width - tile_size + 1), stride))
    ys = list(range(0, max(1, height - tile_size + 1), stride))

    # Ensure the right/bottom edges are represented.
    if width > tile_size and (not xs or xs[-1] != width - tile_size):
        xs.append(width - tile_size)
    if height > tile_size and (not ys or ys[-1] != height - tile_size):
        ys.append(height - tile_size)

    candidates: List[Tuple[float, Image.Image, Tuple[int, int, int, int]]] = []

    for y in ys:
        for x in xs:
            crop = image.crop((x, y, x + tile_size, y + tile_size)).convert("RGB")
            arr = np.asarray(crop, dtype=np.uint8)
            frac = tissue_fraction(arr)
            if frac >= 0.10:
                candidates.append((frac, crop, (x, y, tile_size, tile_size)))

    # If the tissue filter removed everything, fall back to a center crop / resized full image.
    if not candidates:
        patch = image.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        return [patch], [(0, 0, width, height)]

    # Favor tissue-rich tiles. Then distribute if there are too many.
    candidates.sort(key=lambda item: item[0], reverse=True)
    candidates = candidates[: max(max_patches * 2, max_patches)]

    if len(candidates) > max_patches:
        indices = np.linspace(0, len(candidates) - 1, max_patches).astype(int)
        candidates = [candidates[i] for i in indices]

    patches = [item[1] for item in candidates]
    positions = [item[2] for item in candidates]
    return patches, positions


def encode_rgb_image(image_rgb: np.ndarray, quality: int = 90) -> str:
    bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    ok, buffer = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Could not encode image.")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def encode_pil_image(image: Image.Image, quality: int = 90) -> str:
    arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return encode_rgb_image(arr, quality=quality)


def demo_attention_scores(patches: Sequence[Image.Image]) -> np.ndarray:
    """
    Explainable-ish visual fallback for DEMO mode.
    This is NOT a learned tumor localization method.

    It scores tile texture + saturation so the overlay changes with the image.
    """
    scores = []
    for patch in patches:
        rgb = np.asarray(patch.convert("RGB"), dtype=np.uint8)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

        texture = np.log1p(cv2.Laplacian(gray, cv2.CV_32F).var())
        saturation = float(hsv[..., 1].mean()) / 255.0
        darkness = 1.0 - float(gray.mean()) / 255.0

        score = 0.55 * texture + 0.25 * saturation + 0.20 * darkness
        scores.append(score)

    arr = np.asarray(scores, dtype=np.float32)
    arr -= arr.min()
    arr /= (arr.max() + 1e-6)
    return arr


def create_attention_overlay(
    image: Image.Image,
    positions: Sequence[Tuple[int, int, int, int]],
    attention: Sequence[float],
) -> str:
    """
    Creates an OpenCV JET overlay aligned to original image coordinates.
    """
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]

    heat = np.zeros((height, width), dtype=np.float32)
    count = np.zeros((height, width), dtype=np.float32)

    att = np.asarray(attention, dtype=np.float32).reshape(-1)
    if len(att) != len(positions):
        att = np.ones(len(positions), dtype=np.float32)

    if att.size > 0:
        att = att - att.min()
        denom = float(att.max()) + 1e-6
        att = att / denom

    for (x, y, w, h), score in zip(positions, att):
        x2 = min(width, x + w)
        y2 = min(height, y + h)
        if x >= width or y >= height or x2 <= x or y2 <= y:
            continue
        heat[y:y2, x:x2] += float(score)
        count[y:y2, x:x2] += 1.0

    valid = count > 0
    heat[valid] /= count[valid]

    if heat.max() > 0:
        heat /= heat.max()

    # Smooth tile boundaries.
    sigma = max(7.0, min(width, height) / 60.0)
    heat = cv2.GaussianBlur(heat, ksize=(0, 0), sigmaX=sigma, sigmaY=sigma)
    if heat.max() > 0:
        heat /= heat.max()

    heat_u8 = np.uint8(np.clip(heat * 255.0, 0, 255))
    jet_bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    base_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    overlay_bgr = cv2.addWeighted(base_bgr, 0.62, jet_bgr, 0.38, 0)

    ok, buffer = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Could not encode heatmap overlay.")

    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


# -----------------------------
# Scoring + biomarker logic
# -----------------------------
def deterministic_demo_probability(raw: bytes) -> float:
    """
    Deterministic end-to-end demo score.

    This exists only so the UI remains functional before a trained MIL checkpoint is ready.
    It is intentionally labeled DEMO_UNVALIDATED in the API response.
    """
    digest = hashlib.sha256(raw).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    unit = integer / float(2**64 - 1)

    # Spread demo results across a visually useful range.
    return float(0.28 + 0.64 * unit)


def classify_probability(malignancy_probability: float) -> Tuple[str, float, str]:
    p = float(np.clip(malignancy_probability, 0.0, 1.0))

    # The PDF recommends a low-confidence / review zone around the middle.
    if 0.40 <= p <= 0.60:
        prediction = "Indeterminate — specialist review recommended"
        confidence = (1.0 - abs(0.5 - p) * 2.0) * 50.0
        confidence_band = "Low"
        return prediction, float(confidence), confidence_band

    if p > 0.60:
        prediction = "Likely malignant"
        confidence = p * 100.0
    else:
        prediction = "Likely benign"
        confidence = (1.0 - p) * 100.0

    if confidence >= 90:
        band = "High"
    elif confidence >= 75:
        band = "Moderate"
    else:
        band = "Low"

    return prediction, float(confidence), band


def biomarker_engine(malignancy_probability: float, prediction: str) -> List[Dict[str, str]]:
    """
    Rule-based reflex prioritization only.
    This does not infer actual HER2 / ER / PR / Ki-67 status.
    """
    p = float(malignancy_probability)

    if "indeterminate" in prediction.lower():
        return [
            {
                "name": "ER/PR",
                "priority": "Pathologist review",
                "rationale": "Do not reflex from an indeterminate AI result; confirm morphology and workflow first.",
            },
            {
                "name": "HER2",
                "priority": "Pathologist review",
                "rationale": "Prioritize only if malignancy is confirmed and biomarker testing is indicated by local protocol.",
            },
            {
                "name": "Ki-67",
                "priority": "Pathologist review",
                "rationale": "Use as a follow-up marker only within the appropriate confirmed clinical context.",
            },
        ]

    if p >= 0.75:
        return [
            {
                "name": "ER/PR",
                "priority": "High",
                "rationale": "High-priority confirmatory receptor testing if invasive breast malignancy is confirmed by pathology.",
            },
            {
                "name": "HER2",
                "priority": "High",
                "rationale": "High-priority confirmatory IHC/ISH workflow if invasive malignancy is confirmed.",
            },
            {
                "name": "Ki-67",
                "priority": "Medium",
                "rationale": "Consider proliferative-index testing according to institutional breast pathology workflow.",
            },
        ]

    if p >= 0.60:
        return [
            {
                "name": "ER/PR",
                "priority": "High",
                "rationale": "Prioritize receptor testing after pathologist confirmation of malignancy.",
            },
            {
                "name": "HER2",
                "priority": "Medium",
                "rationale": "Consider confirmatory HER2 testing if morphology and case context support invasive disease.",
            },
            {
                "name": "Ki-67",
                "priority": "Medium",
                "rationale": "Consider according to local protocol after diagnostic confirmation.",
            },
        ]

    return [
        {
            "name": "ER/PR",
            "priority": "Routine / not reflexed",
            "rationale": "The AI workflow does not prioritize receptor testing from this image alone; pathologist judgment governs.",
        },
        {
            "name": "HER2",
            "priority": "Routine / not reflexed",
            "rationale": "No automatic biomarker status is inferred from H&E in this prototype.",
        },
        {
            "name": "Ki-67",
            "priority": "Routine / not reflexed",
            "rationale": "Use only when clinically indicated by the confirmed diagnosis and local protocol.",
        },
    ]


# -----------------------------
# Clinical report synthesis
# -----------------------------
def structured_report(
    patient_id: str,
    prediction: str,
    confidence: float,
    malignancy_probability: float,
    biomarkers: List[Dict[str, str]],
    model_status: str,
) -> str:
    priorities = "; ".join(
        f"{item['name']}: {item['priority']}" for item in biomarkers
    )

    demo_sentence = (
        "This run is in DEMO_UNVALIDATED mode because a trained MIL checkpoint was not loaded. "
        "The displayed score is for software demonstration only and must not be interpreted medically."
        if "DEMO" in model_status
        else
        "The slide-level score was produced by the loaded attention-MIL checkpoint over Phikon-v2 tile features."
    )

    return (
        f"Case {patient_id}. AI-assisted assessment: {prediction}. "
        f"Estimated malignancy probability: {malignancy_probability * 100:.1f}%; "
        f"displayed AI confidence: {confidence:.1f}%. {demo_sentence}\n\n"
        f"Reflex biomarker prioritization: {priorities}. These are workflow priorities for confirmatory testing, "
        f"not predictions of biomarker positivity or negativity.\n\n"
        "The heatmap is an explainability aid showing regions that most influenced the model workflow; "
        "it is not a tumor segmentation or a substitute for microscopic review. "
        "Final interpretation, diagnosis, biomarker ordering, and treatment decisions remain with qualified clinicians."
    )


def generate_report(
    patient_id: str,
    prediction: str,
    confidence: float,
    malignancy_probability: float,
    biomarkers: List[Dict[str, str]],
    model_status: str,
) -> str:
    fallback = structured_report(
        patient_id,
        prediction,
        confidence,
        malignancy_probability,
        biomarkers,
        model_status,
    )

    llm = manager.get_local_llm()
    if llm is None:
        return fallback

    try:
        priority_text = ", ".join(f"{b['name']}={b['priority']}" for b in biomarkers)
        prompt = (
            "Rewrite the following pathology decision-support data into a concise 4-6 sentence clinical summary. "
            "Do not diagnose. Do not invent histologic findings, subtype, grade, stage, treatment, or biomarker status. "
            "State that this is AI-assisted and pathologist confirmation is required. "
            f"Patient ID: {patient_id}. Assessment: {prediction}. "
            f"Malignancy probability: {malignancy_probability * 100:.1f}%. "
            f"AI confidence: {confidence:.1f}%. Biomarker priorities: {priority_text}. "
            f"Model status: {model_status}."
        )

        result = llm(prompt, max_new_tokens=180, do_sample=False)
        generated = str(result[0].get("generated_text", "")).strip()

        if len(generated) < 60:
            return fallback

        # Append mandatory safety language regardless of model output.
        return (
            generated
            + "\n\nAI-assisted decision support only. Pathologist confirmation is required; "
              "this prototype does not establish a definitive diagnosis or biomarker status."
        )
    except Exception as exc:
        print(f"[OncoLens] LLM report generation failed: {exc}")
        return fallback


# -----------------------------
# API routes
# -----------------------------
@app.get("/")
def root() -> Dict[str, str]:
    return {
        "service": "OncoLens Insight Compass API",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "ok",
        "device": str(DEVICE),
        "cudaAvailable": torch.cuda.is_available(),
        "phikonLoaded": manager.phikon_ready,
        "milCheckpointLoaded": manager.checkpoint_loaded,
        "modelStatus": (
            "TRAINED_MIL_READY"
            if manager.checkpoint_loaded
            else "DEMO_UNVALIDATED"
        ),
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    patientId: str = Form("PT-7734"),
):
    if not patientId.strip():
        raise HTTPException(status_code=400, detail="patientId must not be empty.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB.",
        )

    image = open_rgb_image(raw)

    # Avoid unexpectedly huge memory use in a 24-hour MVP.
    max_side = 2400
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        resized = (
            max(1, int(image.width * scale)),
            max(1, int(image.height * scale)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)

    patches, positions = extract_patches(image)

    # Phikon-v2 feature extraction is attempted even before a trained MIL head exists,
    # so the integration can be demonstrated and the exact 1024-D features are ready.
    features, feature_mode = manager.extract_features(patches)

    if manager.checkpoint_loaded and feature_mode == "PHIKON_V2_CLS_1024":
        with torch.inference_mode():
            features_device = features.to(DEVICE)
            logit, attention = manager.mil(features_device)
            malignancy_probability = float(torch.sigmoid(logit).item())
            attention_values = attention.detach().float().cpu().numpy()
        model_status = "PHIKON_V2 + TRAINED_ATTENTION_MIL"
    else:
        malignancy_probability = deterministic_demo_probability(raw)
        attention_values = demo_attention_scores(patches)
        model_status = f"DEMO_UNVALIDATED ({feature_mode}; no compatible trained MIL checkpoint)"

    prediction, confidence, confidence_band = classify_probability(malignancy_probability)
    biomarkers = biomarker_engine(malignancy_probability, prediction)

    original_image = encode_pil_image(image)
    heatmap_image = create_attention_overlay(image, positions, attention_values)

    report = generate_report(
        patient_id=patientId.strip(),
        prediction=prediction,
        confidence=confidence,
        malignancy_probability=malignancy_probability,
        biomarkers=biomarkers,
        model_status=model_status,
    )

    return {
        "patientId": patientId.strip(),
        "prediction": prediction,
        "confidence": round(confidence, 2),
        "malignancyProbability": round(malignancy_probability * 100.0, 2),
        "confidenceBand": confidence_band,
        "biomarkers": biomarkers,
        "originalImage": original_image,
        "heatmapImage": heatmap_image,
        "report": report,
        "modelStatus": model_status,
        "featureExtractor": feature_mode,
        "tileCount": len(patches),
        "disclaimer": (
            "AI-assisted decision support only. Pathologist confirmation is required. "
            "Prototype pending clinical validation; not for patient care."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
