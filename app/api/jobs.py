"""Job endpoints. Fleshed out in a later phase; router exists so the app boots."""

from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])
