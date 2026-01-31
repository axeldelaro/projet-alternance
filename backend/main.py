# Point d'entrée FastAPI
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"msg": "ok"}
