from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from eyes_of_horus.models import Base, ManagedTrade, SymbolCvdBaseline
from eyes_of_horus.config import DATABASE_URL

# Create the database engine
engine = create_engine(DATABASE_URL, echo=False) # Set echo=True for debugging SQL

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    # This will create the tables defined in models.py
    Base.metadata.create_all(bind=engine)
    print("Database initialized and tables 'managed_trades' and 'symbol_cvd_baselines' created.")

@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    # This allows us to initialize the database from the command line
    # by running: python database.py
    print("Initializing database...")
    init_db()
