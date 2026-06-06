from datetime import datetime, timezone
from tkinter import CASCADE
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.postgres import Base

class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    player_id:Mapped[str] = mapped_column(  
        String(36), ForeignKey("players.id", ondelete= CASCADE), unique= True, nullable= False
    )
level: Mapped[int] = mapped_column(Integer, default=1)
xp:Mapped[int] = mapped_column(Integer, default=0)
xp_to_next_level: Mapped[int] = mapped_column(Integer, default=100)
    
# Resources
health: Mapped[int] = mapped_column(Integer, default=100)
max_health: Mapped[int] = mapped_column(Integer, default=100)
mana: Mapped[int] = mapped_column(Integer, default=50)
max_mana: Mapped[int] = mapped_column(Integer, default=50)
    
    # Core Stats
strength: Mapped[int] = mapped_column(Integer, default=10)
agility: Mapped[int] = mapped_column(Integer, default=10)
intelligence: Mapped[int] = mapped_column(Integer, default=10)
    
    # Denormalized for Leaderboard efficiency
total_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    
    # Audit timestamps
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
)