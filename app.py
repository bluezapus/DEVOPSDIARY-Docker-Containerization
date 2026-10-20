from flask import Flask
import os

app = Flask(__name__)

@app.get("/")
def home():
    return {
        "message": "Docker Containerization v1.0.0",
        "status": "running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}, 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080"))
    )
