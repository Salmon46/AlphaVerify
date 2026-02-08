from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AlphaVerify SuperApp",
    description="Unified API for AlphaVerify tools",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AlphaVerify SuperApp API is running"}

from routers.wfa.router import router as wfa_router
app.include_router(wfa_router)

from routers.sensitivity.router import router as sensitivity_router
app.include_router(sensitivity_router)

from routers.mcs.router import router as mcs_router
app.include_router(mcs_router)

from routers.perm_tests.router import router as perm_tests_router
app.include_router(perm_tests_router)

from routers.backtest.router import router as backtest_router
app.include_router(backtest_router)
