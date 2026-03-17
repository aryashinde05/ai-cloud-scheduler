from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.session import Base

class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    aws_account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=False, index=True)

    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)  # e.g. "ec2_instance", "ebs_volume"

    # Common fields
    region = Column(String(50), nullable=True)
    name = Column(String(255), nullable=True)
    state = Column(String(50), nullable=True)  # "running", "stopped", "in-use", "available"
    launch_time = Column(DateTime, nullable=True)

    # EC2 specifics
    instance_type = Column(String(50), nullable=True)
    cpu_utilization = Column(Float, nullable=True)  # 24h avg

    # EBS specifics
    volume_size = Column(Integer, nullable=True)   # in GB
    volume_type = Column(String(50), nullable=True) # gp2, gp3, io1...
    iops = Column(Integer, nullable=True)

    # Optimization Flags
    is_idle = Column(Boolean, default=False)
    is_oversized = Column(Boolean, default=False)
    is_unattached = Column(Boolean, default=False)  # mainly for volumes

    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    # aws_account = relationship("AwsAccount", back_populates="resources")
