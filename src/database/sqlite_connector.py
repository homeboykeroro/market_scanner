# dbutil.py
import sqlite3
from typing import Any, List, Optional, Tuple
import os

# Replace with the actual path to your .sqlite file
DATABASE_PATH = "C:/Users/John/Downloads/workspace/market_scanner/market_scanner.sqlite"  # <-- CHANGE THIS TO YOUR DB FILE PATH

def get_connection() -> sqlite3.Connection:
    """Create and return a new database connection."""
    if not os.path.exists(DATABASE_PATH):
        raise FileNotFoundError(f"Database file not found: {DATABASE_PATH}")
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Optional: makes rows behave like dictionaries
    return conn

def execute_in_transaction(query: str, params: Tuple[Any, ...] | List[Any] = ()) -> List[sqlite3.Row]:
    """
    Execute a single query (or multiple queries) inside a transaction.
    
    - For SELECT queries: returns list of rows
    - For INSERT/UPDATE/DELETE: returns empty list (commit happens automatically)
    - Automatically commits on success, rolls back on error
    
    Args:
        query: SQL query string (can contain multiple statements if needed)
        params: Tuple or list of parameters (use ? placeholders)
    
    Example:
        execute_in_transaction("SELECT * FROM PATTERN_ANALYSIS WHERE TICKER = ?", ("AAPL",))
        execute_in_transaction("INSERT INTO PATTERN_ANALYSIS (...) VALUES (?, ?, ?, ?)", 
                              ("TSLA", "2025-12-20 10:00:00", "Double Bottom", "1D"))
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        # If it's a SELECT-like query, fetch results
        if query.strip().upper().startswith(("SELECT", "PRAGMA")):
            results = cursor.fetchall()
            conn.commit()  # Still commit for consistency
            return results
        else:
            conn.commit()
            return []  # No rows to return for INSERT/UPDATE/DELETE
    
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f"Database error: {e}")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Unexpected error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def executemany_in_transaction(query: str, params_list: List[Tuple[Any, ...]]) -> None:
    """
    Execute the same query with multiple sets of parameters (efficient for bulk inserts).
    
    Example:
        data = [("AAPL", "2025-12-20 09:00:00", "Bull Flag", "1H"),
                ("GOOG", "2025-12-20 10:00:00", "Cup and Handle", "1D")]
        executemany_in_transaction("INSERT INTO PATTERN_ANALYSIS VALUES (?, ?, ?, ?)", data)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()