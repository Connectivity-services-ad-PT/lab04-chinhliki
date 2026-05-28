import http
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "core-business")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token-real")

app = FastAPI(
    title="FIT4110 Lab 04 - Core Business Service",
    version=SERVICE_VERSION,
    description="Dockerized Core Business Policy Engine API aligned with Lab 03/04 OpenAPI/Postman contracts.",
)

# ----------------- Models -----------------

class HealthResponse(BaseModel):
    status: str
    timestamp: str

class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None

class AccessEventRequest(BaseModel):
    event_type: str = Field(..., examples=["access_event"])
    timestamp: str = Field(..., examples=["2026-05-18T08:30:00Z"])
    card_id: str = Field(..., examples=["RFID-2026-9999"])
    gate_id: str = Field(..., examples=["gate-lib-01"])
    direction: str = Field(..., examples=["IN"])

class AccessEventResponse(BaseModel):
    access_granted: bool
    reason: str
    person_id: str

class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class Alert(BaseModel):
    alert_id: str
    type: str
    severity: AlertSeverity
    message: str
    created_at: str
    resolved_at: Optional[str] = None

class PaginationInfo(BaseModel):
    next_cursor: Optional[str] = None
    has_more: bool

class AlertListResponse(BaseModel):
    status: str
    data: List[Alert]
    pagination: PaginationInfo

class AccessEventHistoryItem(BaseModel):
    event_id: str
    card_id: str
    gate_id: str
    direction: str
    timestamp: str
    access_granted: bool
    reason: str

class AccessEventHistoryResponse(BaseModel):
    status: str
    data: List[AccessEventHistoryItem]
    pagination: PaginationInfo

# ----------------- Database / Mock Data -----------------

ALERTS_DB: List[Alert] = [
    Alert(
        alert_id="ALT-B6-20260518-001",
        type="suspicious_card_activity",
        severity=AlertSeverity.medium,
        message="Cảnh báo: Thẻ RFID-2026-9999 được quẹt liên tiếp tại 2 cổng khác nhau trong vòng dưới 30 giây.",
        created_at="2026-05-18T08:30:15Z",
        resolved_at=None
    )
]

ACCESS_EVENTS_DB: List[AccessEventHistoryItem] = []

# ----------------- Helpers -----------------

def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem

# ----------------- Exception Handlers -----------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=http.client.responses.get(exc.status_code, "HTTP Error"),
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", http.client.responses.get(exc.status_code, "HTTP Error"))
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smartcampus.dnu.edu.vn/probs/bad-request",
        ),
        media_type="application/problem+json",
    )

# ----------------- Auth Dependency -----------------

def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized Access",
                detail="Missing Authorization header",
                problem_type="https://smartcampus.dnu.edu.vn/probs/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized Access",
                detail="Invalid bearer token",
                problem_type="https://smartcampus.dnu.edu.vn/probs/unauthorized",
            ),
        )

# ----------------- Endpoints -----------------

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="UP",
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

@app.post(
    "/api/v1/events/access",
    response_model=AccessEventResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        400: {"model": ProblemDetails},
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
def process_access_event(
    payload: AccessEventRequest,
    request: Request,
    prefer: Optional[str] = Header(default=None)
) -> AccessEventResponse:
    # Handle Prefer header or blacklist card to test business rule violations
    if (prefer and "code=422" in prefer) or "BLACKLIST" in payload.card_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Business Rule Violation",
                detail="Thẻ nằm trong danh sách đen bị khóa hoặc vi phạm quy tắc an ninh.",
                instance=str(request.url.path),
                problem_type="https://smartcampus.dnu.edu.vn/probs/business-rule-violation",
            ),
        )

    # Simple business rules
    access_granted = True
    reason = "Thẻ sinh viên hợp lệ và còn thời hạn truy cập"
    person_id = "SV00123"

    if payload.card_id == "RFID-DENY":
        access_granted = False
        reason = "Thẻ không có quyền truy cập vào cổng này"
        person_id = "SV00000"

    # Add to DB history
    event_id = f"acc-uuid-2026-{len(ACCESS_EVENTS_DB) + 1:04d}"
    history_item = AccessEventHistoryItem(
        event_id=event_id,
        card_id=payload.card_id,
        gate_id=payload.gate_id,
        direction=payload.direction,
        timestamp=payload.timestamp,
        access_granted=access_granted,
        reason=reason
    )
    ACCESS_EVENTS_DB.append(history_item)

    return AccessEventResponse(
        access_granted=access_granted,
        reason=reason,
        person_id=person_id
    )

@app.get(
    "/api/v1/alerts",
    response_model=AlertListResponse,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}},
)
def list_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None)
) -> AlertListResponse:
    data = ALERTS_DB
    return AlertListResponse(
        status="success",
        data=data[:limit],
        pagination=PaginationInfo(next_cursor=None, has_more=False)
    )

@app.get(
    "/api/v1/alerts/{id}",
    response_model=Alert,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def get_alert_by_id(
    id: str,
    request: Request,
    prefer: Optional[str] = Header(default=None)
) -> Alert:
    if (prefer and "code=404" in prefer) or id == "ALT-NOT-FOUND-999":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Resource Not Found",
                detail=f"Không tìm thấy mã Alert yêu cầu: {id}",
                instance=str(request.url.path),
                problem_type="https://smartcampus.dnu.edu.vn/probs/not-found",
            ),
        )

    for alert in ALERTS_DB:
        if alert.alert_id == id:
            return alert

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=build_problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Resource Not Found",
            detail=f"Không tìm thấy mã Alert yêu cầu: {id}",
            instance=str(request.url.path),
            problem_type="https://smartcampus.dnu.edu.vn/probs/not-found",
        ),
    )

@app.get(
    "/api/v1/events/access",
    response_model=AccessEventHistoryResponse,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}},
)
def list_access_events(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None)
) -> AccessEventHistoryResponse:
    data = ACCESS_EVENTS_DB
    return AccessEventHistoryResponse(
        status="success",
        data=data[:limit],
        pagination=PaginationInfo(next_cursor=None, has_more=False)
    )
