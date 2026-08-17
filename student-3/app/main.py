import os
from flask import Flask, render_template

app = Flask(__name__, template_folder="../templates")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@app.route("/")
def index():
    return render_template("index.html", service_name="Student 3")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
