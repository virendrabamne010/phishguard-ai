import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime
from app.database import Base

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class EmailRecord(Base):
    __tablename__ = "emails"

    id = Column(String, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    snippet = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    risk_score = Column(Integer, nullable=False)
    label = Column(String)  # 'phishing', 'suspicious', 'legitimate'
    flagged_reasons_json = Column(Text, nullable=True)
    suspicious_keywords_json = Column(Text, nullable=True)
    reported = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    
    @property
    def flagged_reasons(self):
        return json.loads(self.flagged_reasons_json) if self.flagged_reasons_json else []
        
    @flagged_reasons.setter
    def flagged_reasons(self, value):
        self.flagged_reasons_json = json.dumps(value)

    @property
    def suspicious_keywords(self):
        return json.loads(self.suspicious_keywords_json) if self.suspicious_keywords_json else []
        
    @suspicious_keywords.setter
    def suspicious_keywords(self, value):
        self.suspicious_keywords_json = json.dumps(value)

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    mode = Column(String, default="disconnected")
    global_scanned = Column(Integer, default=0)
    global_phishing = Column(Integer, default=0)
    global_suspicious = Column(Integer, default=0)


class AuditLog(Base):
    """Records all admin actions for security auditing."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    admin_username = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)          # e.g. "login", "report_email", "delete_email"
    resource_id = Column(String, nullable=True)       # e.g. email ID
    detail = Column(Text, nullable=True)              # extra context
    ip_address = Column(String, nullable=True)

