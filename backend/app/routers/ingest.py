"""Device data in: POST /api/ingest (handoff.md section 6).

Authenticated with the node's API key in the `X-API-Key` header (not a user
login). The body is one reading or a list of readings.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.ingest_service import IngestError, ingest_reading, ingest_readings
from app.models import Node
from app.node_service import hash_api_key
from app.schemas import IngestResult, ReadingIn

router = APIRouter(prefix="/api", tags=["ingest"])

MAX_BATCH = 1000


@router.post("/ingest", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest(
    body: ReadingIn | list[ReadingIn],
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_api_key: Annotated[str | None, Header()] = None,
):
    """Store one reading (or a list) for the node that owns the API key.

    Returns 201 when something was stored, or 200 with `duplicate: true`
    when the reading was already stored.
    """
    payloads = body if isinstance(body, list) else [body]
    if len(payloads) > MAX_BATCH:
        raise HTTPException(status_code=413, detail=f"At most {MAX_BATCH} readings per request")
    if not payloads:
        raise HTTPException(status_code=422, detail="No readings in request")

    # 1. Authenticate the key against the node.
    node = None
    if x_api_key:
        node = db.scalars(select(Node).where(Node.api_key_hash == hash_api_key(x_api_key))).first()
    if node is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if any(p.dev_eui != node.dev_eui for p in payloads):
        raise HTTPException(status_code=401, detail="API key does not match dev_eui")

    try:
        if isinstance(body, list):
            result = ingest_readings(db, node, payloads, utcnow())
        else:
            result = ingest_reading(db, node, body, utcnow())
    except IngestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    if result.stored == 0 and result.rejected and not isinstance(body, list):
        raise HTTPException(status_code=422, detail=result.errors[0])
    if result.stored == 0:
        response.status_code = status.HTTP_200_OK
    return result


def ttn_uplink_to_reading(uplink: dict) -> ReadingIn:
    """Map a The Things Stack (LoRaWAN) v3 uplink webhook message to our ingest schema.

    STUB for later (handoff section 12). Assumes the TTN "payload formatter"
    decodes the device's bytes into fields with the same names as ReadingIn
    (angle_x, acc_x, battery_pct...). Link quality comes from the gateway
    metadata, and the timestamp from the device (if decoded) or from TTN.
    """
    message = uplink.get("uplink_message") or {}
    decoded = dict(message.get("decoded_payload") or {})
    gateways = message.get("rx_metadata") or [{}]
    best = max(gateways, key=lambda g: g.get("rssi", -999))  # strongest gateway
    decoded.setdefault("rssi", best.get("rssi"))
    decoded.setdefault("snr", best.get("snr"))
    decoded.setdefault("seq", message.get("f_cnt"))
    decoded.setdefault("ts", decoded.get("ts") or message.get("received_at") or uplink.get("received_at"))
    decoded["dev_eui"] = (uplink.get("end_device_ids") or {}).get("dev_eui", "")
    return ReadingIn.model_validate(decoded)


@router.post("/ingest/ttn", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest_ttn(
    uplink: dict,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    x_api_key: Annotated[str | None, Header()] = None,
):
    """LoRaWAN webhook (The Things Stack). Set the node's key as an X-API-Key header in the webhook settings.

    Converts the uplink and then uses exactly the same ingest path as /api/ingest.
    """
    try:
        reading = ttn_uplink_to_reading(uplink)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Could not read TTN uplink: {e}")
    return ingest(reading, response, db, x_api_key)
