import logging
import os
from datetime import UTC, datetime
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quant_research.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and seed default strategies if they don't exist."""
    # Import models here to avoid circular imports; Base must see them before create_all
    from backend.models.backtest import BacktestRun, Strategy  # noqa: F401

    Base.metadata.create_all(bind=engine)

    _seed_strategies()


def _seed_strategies() -> None:
    """Insert default strategies on first run (idempotent, race-safe).

    Uses INSERT-or-ignore semantics: each strategy is inserted in its own
    transaction so an IntegrityError (duplicate name) on one row does not
    roll back the others. Safe to call from multiple workers simultaneously.
    """
    from backend.models.backtest import Strategy

    default_strategies = [
        Strategy(
            name="MA Crossover",
            description=(
                "Moving Average Crossover: goes long when the short-period SMA crosses "
                "above the long-period SMA and flat (or short) otherwise. A classic "
                "trend-following signal widely used in systematic equity strategies."
            ),
            default_ticker="SPY",
            created_at=datetime.now(UTC),
        ),
        Strategy(
            name="Momentum",
            description=(
                "12-1 Month Momentum: buys assets that have outperformed over the past "
                "year (excluding the most recent month) as documented by Jegadeesh & "
                "Titman (1993). Implemented here via the MA Crossover engine with "
                "longer lookback windows."
            ),
            default_ticker="QQQ",
            created_at=datetime.now(UTC),
        ),
        Strategy(
            name="Mean Reversion",
            description=(
                "Short-term Mean Reversion: fades recent moves by going long when price "
                "dips below a short rolling average and short when it rises above. "
                "Captures microstructure noise in liquid equity indices."
            ),
            default_ticker="IWM",
            created_at=datetime.now(UTC),
        ),
    ]

    for strategy in default_strategies:
        db = SessionLocal()
        try:
            db.add(strategy)
            db.commit()
        except IntegrityError as exc:
            # Already exists — another worker beat us to it, or it's a re-run.
            db.rollback()
            logger.debug("Strategy '%s' already seeded, skipping: %s", strategy.name, exc)
        finally:
            db.close()
