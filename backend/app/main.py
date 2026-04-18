from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.pro_players import router as pro_players_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.reports import router as reports_router
from app.api.v1.users import router as users_router

app = FastAPI(
    title="TennisCoach AI API",
    version="0.2.0",
    description="Backend API for TennisCoach AI",
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
app.include_router(reports_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
