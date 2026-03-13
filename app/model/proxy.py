from sqlalchemy import Column, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


class Proxy(Base):
    __tablename__ = 'proxy'

    id = Column(Integer, primary_key=True, autoincrement=True)
    server = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    secret = Column(String(255), nullable=False)
    ip = Column(Integer, nullable=True)
    connect = Column(Boolean, nullable=True)
    country = Column(String(2), nullable=True)

    # foreign key 1 to many
    ping_reports = relationship(
        'PingReport', back_populates='proxy', cascade='all, delete-orphan')
    speed_reports = relationship(
        'SpeedReport', back_populates='proxy', cascade='all, delete-orphan')

    # constrian
    __table_args__ = (UniqueConstraint('server', 'port', 'secret'),)
