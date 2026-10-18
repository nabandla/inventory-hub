from fastapi import FastAPI

app = FastAPI(title="Inventory Hub")


@app.get("/health")
def health():
    return {"status": "ok"}
