from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from backend.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(100), unique=True, nullable=False, index=True)
    description: str = Column(Text, nullable=True)
    default_ticker: str = Column(String(20), nullable=False, default="SPY")
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: int = Column(Integer, primary_key=True, index=True)
    strategy_name: str = Column(String(100), nullable=False, index=True)
    ticker: str = Column(String(20), nullable=False)
    short_window: int = Column(Integer, nullable=False)
    long_window: int = Column(Integer, nullable=False)
    start_date: str = Column(String(20), nullable=False)
    end_date: str = Column(String(20), nullable=False)
    total_return: float = Column(Float, nullable=True)
    sharpe_ratio: float = Column(Float, nullable=True)
    max_drawdown: float = Column(Float, nullable=True)
    num_trades: int = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
