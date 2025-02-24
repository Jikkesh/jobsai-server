from db import engine, Base  # Make sure engine and Base are correctly imported

# Drop all tables
Base.metadata.drop_all(bind=engine)

# Create all tables based on your new models
Base.metadata.create_all(bind=engine)