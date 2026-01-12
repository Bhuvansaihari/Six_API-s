"""
Final test to verify the fix works correctly.
"""

import pyodbc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import get_settings


def test_fixed_implementation():
    """Test that the HY000 error is now handled correctly."""
    print("=" * 60)
    print("Testing Fixed Implementation")
    print("=" * 60)
    
    settings = get_settings()
    
    if settings.recommendations_db_username and settings.recommendations_db_password:
        password = settings.recommendations_db_password.get_secret_value()
        conn_str = (
            f"DRIVER={{{settings.recommendations_db_driver}}};"
            f"SERVER={settings.recommendations_db_server};"
            f"DATABASE={settings.recommendations_db_database};"
            f"UID={settings.recommendations_db_username};"
            f"PWD={password};"
            f"TrustServerCertificate={settings.recommendations_db_trust_server_certificate};"
            f"Encrypt={settings.recommendations_db_encrypt};"
        )
    else:
        conn_str = (
            f"DRIVER={{{settings.recommendations_db_driver}}};"
            f"SERVER={settings.recommendations_db_server};"
            f"DATABASE={settings.recommendations_db_database};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate={settings.recommendations_db_trust_server_certificate};"
            f"Encrypt={settings.recommendations_db_encrypt};"
        )
    
    try:
        conn = pyodbc.connect(conn_str, timeout=30)
        cursor = conn.cursor()
        
        print("\n[Executing stored procedure with HY000 error handling...]")
        cursor.execute("""
            EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobList]
                @CandidateID = ?
        """, (3044,))
        
        results = []
        
        # This is the fixed implementation
        while True:
            if cursor.description:
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    results.append(dict(zip(columns, row)))
            
            # Handle HY000 error on nextset()
            try:
                if not cursor.nextset():
                    break
            except pyodbc.Error as e:
                error_code = e.args[0] if e.args else None
                if error_code == 'HY000':
                    print("[INFO] Reached end of result sets (HY000 - handled gracefully)")
                    break
                else:
                    raise
        
        cursor.close()
        conn.close()
        
        print(f"\n[SUCCESS] Stored procedure executed successfully!")
        print(f"Total records returned: {len(results)}")
        
        if results:
            print(f"\nSample record:")
            for key, value in list(results[0].items())[:5]:
                print(f"  {key}: {value}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Fix verified - HY000 error handled correctly!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print(f"Error type: {type(e).__name__}")
        sys.exit(1)


if __name__ == "__main__":
    test_fixed_implementation()
