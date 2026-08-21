"""
schemas.py — Pydantic schemas for request validation and response typing.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class EmailSummary(BaseModel):
    id: str = Field(..., description="Unique email ID")
    subject: str = Field(..., description="Email subject line")
    sender: str = Field(..., description="Sender email address")
    snippet: str = Field(..., description="Short text preview")
    risk_score: int = Field(..., ge=0, le=100, description="Phishing risk score (0-100)")
    label: str = Field(..., description="Category label: legitimate, suspicious, or phishing")
    flagged_reasons: List[str] = Field(default_factory=list, description="Explainable AI triggers")
    suspicious_keywords: List[str] = Field(default_factory=list, description="Extracted TF-IDF keywords")
    reported: bool = Field(False, description="Report status flag")


class EmailDetailResponse(EmailSummary):
    body: str = Field(..., description="Full email body content")


class InboxResponse(BaseModel):
    mode: str = Field(..., description="Current connection mode: disconnected, demo, gmail, or imap")
    emails: List[EmailSummary] = Field(default_factory=list)
    message: Optional[str] = None


class StatusResponse(BaseModel):
    mode: str
    email_count: int
    environment: str = "production"
    connected_email: Optional[str] = None
    provider: Optional[str] = None


class ConnectResponse(BaseModel):
    auth_url: str


class ReportResponse(BaseModel):
    status: str
    email_id: str
    message: str


class ActionStatusResponse(BaseModel):
    status: str
    email_count: int


class CustomAnalyzeRequest(BaseModel):
    subject: str = Field("", description="Subject of the email to analyze")
    body: str = Field(..., description="Body content of the email")
    sender: str = Field("unknown@domain.com", description="Sender email address")


class CustomAnalyzeResponse(BaseModel):
    subject: str
    sender: str
    body: str
    risk_score: float
    label: str
    flagged_reasons: List[str]
    suspicious_keywords: List[str]


class IMAPConnectRequest(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="App password or IMAP password")
    provider: str = Field("gmail", description="Email provider: gmail, outlook, yahoo, hotmail, zoho, or custom")
    imap_host: Optional[str] = Field(None, description="Custom IMAP host (used when provider=custom)")
    imap_port: int = Field(993, description="Custom IMAP port (used when provider=custom)")


class SystemAnalyticsResponse(BaseModel):
    global_scanned: int
    global_phishing: int
    global_suspicious: int
    model_metrics: dict


class DatabaseSettings(BaseModel):
    id: int
    mode: str
    global_scanned: int
    global_phishing: int
    global_suspicious: int


class DatabaseEmail(BaseModel):
    id: str
    subject: str
    sender: str
    risk_score: int
    label: str
    reported: bool


class DatabaseDumpResponse(BaseModel):
    settings: List[DatabaseSettings]
    emails: List[DatabaseEmail]


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenRefresh(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current admin password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class AuditLogEntry(BaseModel):
    id: int
    timestamp: str
    admin_username: str
    action: str
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None


class AuditLogResponse(BaseModel):
    entries: List[AuditLogEntry]
