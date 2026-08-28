from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import tensorflow as tf
import numpy as np
from PIL import Image

app = Flask(__name__)
CORS(app)

MODEL_PATH = "/content/drive/MyDrive/OncoLens_AI/models/OncoLens_Efficientnet_corrected.keras"

print("Loading OncoLens AI model...")

try:
    model = tf.keras.models.load_model(MODEL_PATH)
    print("MODEL LOADED SUCCESSFULLY")
except Exception as e:
    model = None
    print("MODEL ERROR:", e)


@app.route("/")
def home():
    return send_from_directory(
        "/content/OncoLens_Backend",
        "index.html"
    )


@app.route("/health")
def health():
    return jsonify({
        "status": "OncoLens Backend is running",
        "model_loaded": model is not None
    })


@app.route("/predict", methods=["POST"])
def predict():

    if model is None:
        return jsonify({
            "error": "Model is not loaded"
        }), 500

    if "file" not in request.files:
        return jsonify({
            "error": "No image uploaded"
        }), 400

    file = request.files["file"]

    try:
        image = Image.open(file).convert("RGB")
        image = image.resize((224, 224))

        image_array = np.array(image)
        image_array = image_array / 255.0
        image_array = np.expand_dims(image_array, axis=0)

        prediction = model.predict(
            image_array,
            verbose=0
        )

        probability = float(np.max(prediction))
        predicted_class = int(np.argmax(prediction))

        if predicted_class == 1:
            result = "Cancerous"
        else:
            result = "Non-Cancerous"

        if result == "Cancerous":
            biomarker = "HER2 and Ki-67 recommended for further evaluation."
        else:
            biomarker = "No immediate biomarker recommendation."

        return jsonify({
            "prediction": result,
            "probability": round(probability * 100, 2),
            "biomarker_recommendation": biomarker
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    print("Starting OncoLens AI Backend...")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
