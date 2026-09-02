import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv()

app = Flask(__name__, template_folder="../templates", static_folder="../static")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "product-catalog"})


@app.route("/")
def index():
    return render_template("index.html", service_name="Product Catalog")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
