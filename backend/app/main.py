from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.pro_players import router as pro_players_router
from app.api.v1.analysis import router as analysis_router

app = FastAPI(
    title="TennisCoach AI API",
    version="0.1.0",
    description="Backend API for TennisCoach AI — F1: Video Upload & Analysis",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pro_players_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
