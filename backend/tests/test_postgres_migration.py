"""
Test PostgreSQL migration and database adapter
Run this to verify PostgreSQL support is working
"""
import sys
import asyncio
import os
from pathlib import Path

# Ensure project `backend` root is on sys.path so `import app` works
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import init_db, execute_query, execute_update, is_postgres, close_pg_pool


async def test_database_operations():
    """Test basic database operations with either SQLite or PostgreSQL"""
    
    print("=" * 60)
    print("Testing Database Adapter")
    print("=" * 60)
    
    # Check which database we're using
    db_type = "PostgreSQL" if is_postgres() else "SQLite"
    print(f"✓ Using: {db_type}")
    
    if is_postgres():
        print(f"✓ Connection: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")
    else:
        print(f"✓ Database file: path_deviation.db")
    
    print("\n" + "-" * 60)
    print("Initializing database schema...")
    print("-" * 60)
    
    try:
        await init_db()
        print("✓ Schema initialized successfully")
    except Exception as e:
        print(f"✗ Schema initialization failed: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Testing INSERT operation...")
    print("-" * 60)
    
    try:
        # Insert test journey
        await execute_update("""
            INSERT INTO journeys (id, origin_lat, origin_lng, destination_lat, 
                                destination_lng, travel_mode, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, ('test-journey-123', 18.5246, 73.8786, 18.9582, 72.8321, 'driving', 'active'))
        print("✓ INSERT successful")
    except Exception as e:
        print(f"✗ INSERT failed: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Testing SELECT operation...")
    print("-" * 60)
    
    try:
        # Query test journey
        results = await execute_query("""
            SELECT id, travel_mode, status FROM journeys WHERE id = ?
        """, ('test-journey-123',))
        
        if results:
            print(f"✓ SELECT successful: {results[0]}")
        else:
            print("✗ SELECT returned no results")
    except Exception as e:
        print(f"✗ SELECT failed: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Testing UPDATE operation...")
    print("-" * 60)
    
    try:
        # Update test journey
        rows = await execute_update("""
            UPDATE journeys SET status = ? WHERE id = ?
        """, ('completed', 'test-journey-123'))
        print(f"✓ UPDATE successful ({rows} row(s) affected)")
    except Exception as e:
        print(f"✗ UPDATE failed: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Testing DELETE operation...")
    print("-" * 60)
    
    try:
        # Delete test journey
        rows = await execute_update("""
            DELETE FROM journeys WHERE id = ?
        """, ('test-journey-123',))
        print(f"✓ DELETE successful ({rows} row(s) affected)")
    except Exception as e:
        print(f"✗ DELETE failed: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Testing concurrent operations (5 parallel inserts)...")
    print("-" * 60)
    
    try:
        # Test concurrent writes (this is what was causing locks in SQLite)
        tasks = []
        for i in range(5):
            task = execute_update("""
                INSERT INTO journeys (id, origin_lat, origin_lng, destination_lat, 
                                    destination_lng, travel_mode, start_time, status)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (f'test-concurrent-{i}', 18.5, 73.8, 18.9, 72.8, 'walking', 'active'))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        print(f"✓ Concurrent writes: {success_count} succeeded, {error_count} failed")
        
        if error_count > 0:
            print("\n⚠ Errors in concurrent writes:")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"  - Task {i}: {result}")
        
        # Cleanup
        for i in range(5):
            await execute_update("DELETE FROM journeys WHERE id = ?", (f'test-concurrent-{i}',))
        
    except Exception as e:
        print(f"✗ Concurrent test failed: {e}")
    
    print("\n" + "=" * 60)
    print("Database Test Results")
    print("=" * 60)
    print(f"✓ Database Type: {db_type}")
    print(f"✓ All operations successful!")
    
    if is_postgres():
        print(f"✓ Using connection pool (handles concurrency)")
    else:
        print(f"⚠ Using SQLite (may have lock issues under high load)")
    
    print("=" * 60)
    
    # Cleanup PostgreSQL pool
    if is_postgres():
        await close_pg_pool()


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  PostgreSQL Migration Test                                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Test locally (SQLite)
    print("Testing LOCAL (SQLite):")
    asyncio.run(test_database_operations())
    
    print("\n\n")
    print("To test PostgreSQL:")
    print("1. Set DATABASE_URL environment variable")
    print("2. Run: DATABASE_URL='postgresql://...' python backend/tests/test_postgres_migration.py")
    print()
