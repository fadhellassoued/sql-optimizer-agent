from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(title="SQL Optimizer AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "SQL Optimization Agent is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

#@app.get("/ping")
#async def ping():
#    return {"ping": "pong"}