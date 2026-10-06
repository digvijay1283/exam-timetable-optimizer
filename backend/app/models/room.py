from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Room(Base):
    __tablename__ = "room"
    __table_args__ = (UniqueConstraint("session_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str]  # room_id from the CSV
    room_code: Mapped[str]
    building: Mapped[str] = mapped_column(default="")
    capacity: Mapped[int]
    room_type: Mapped[str] = mapped_column(default="classroom")
    available: Mapped[bool] = mapped_column(default=True)
