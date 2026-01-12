"""
Test script to verify database connectivity for Recommendations API.

This script tests the connection to the SQL Server database used by the
Recommendations API to help diagnose connection issues.
"""

import pyodbc
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings


def test_connection():
    """Test basic database connectivity."""
    print("=" * 60)
    print("Recommendations API Database Connection Test")
    print("=" * 60)
    
    settings = get_settings()
    
    # Display connection parameters (without password)
    print("\n[Connection Parameters]")
    print(f"  Server: {settings.recommendations_db_server}")
    print(f"  Database: {settings.recommendations_db_database}")
    print(f"  Username: {settings.recommendations_db_username}")
    print(f"  Driver: {settings.recommendations_db_driver}")
    print(f"  Encrypt: {settings.recommendations_db_encrypt}")
    print(f"  Trust Certificate: {settings.recommendations_db_trust_server_certificate}")
    
    # Build connection string
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
    
    print("\n[Testing connection...]")
    
    try:
        # Test connection
        conn = pyodbc.connect(conn_str, timeout=30)
        print("[SUCCESS] Connection successful!")
        
        # Test basic query
        print("\n[Testing basic query (SELECT @@VERSION)...]")
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"[SUCCESS] Query successful!")
        print(f"\n[SQL Server Version]")
        print(f"  {version.split(chr(10))[0]}")
        
        # Test stored procedure existence
        print("\n[Checking if stored procedure exists...]")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM sys.procedures 
            WHERE name = 'USP_AI_Get_JobSeekerRecommenededJobList'
        """)
        sp_exists = cursor.fetchone()[0]
        
        if sp_exists:
            print("[SUCCESS] Stored procedure 'USP_AI_Get_JobSeekerRecommenededJobList' exists!")
        else:
            print("[ERROR] Stored procedure 'USP_AI_Get_JobSeekerRecommenededJobList' NOT FOUND!")
            print("   This could be the cause of the error.")
        
        # Test stored procedure with sample candidate_id
        if sp_exists:
            print("\n[Testing stored procedure execution with candidate_id=3044...]")
            try:
                cursor.execute("""
                    EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobList]
                        @CandidateID = ?
                """, (3044,))
                
                # Count results
                result_count = 0
                while True:
                    if cursor.description:
                        rows = cursor.fetchall()
                        result_count += len(rows)
                        print(f"  Result set: {len(rows)} rows")
                    
                    if not cursor.nextset():
                        break
                
                print(f"[SUCCESS] Stored procedure executed successfully!")
                print(f"   Total records returned: {result_count}")
                
            except pyodbc.Error as e:
                error_code = e.args[0] if e.args else 'UNKNOWN'
                error_msg = e.args[1] if len(e.args) > 1 else str(e)
                print(f"[ERROR] Stored procedure execution failed!")
                print(f"   Error Code: {error_code}")
                print(f"   Error Message: {error_msg}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests completed successfully!")
        print("=" * 60)
        
    except pyodbc.Error as e:
        error_code = e.args[0] if e.args else 'UNKNOWN'
        error_msg = e.args[1] if len(e.args) > 1 else str(e)
        print(f"\n[ERROR] Connection failed!")
        print(f"\n[Error Details]")
        print(f"   Error Code: {error_code}")
        print(f"   Error Message: {error_msg}")
        print(f"   Full Exception: {repr(e)}")
        
        print("\n[Troubleshooting Tips]")
        print("   1. Verify SQL Server is running and accessible")
        print("   2. Check firewall settings (port 1433)")
        print("   3. Verify username and password are correct")
        print("   4. Ensure ODBC Driver 18 is installed")
        print("   5. Check if database exists and user has permissions")
        
        print("\n" + "=" * 60)
        sys.exit(1)
    
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        print(f"   Exception type: {type(e).__name__}")
        print(f"   Full exception: {repr(e)}")
        print("\n" + "=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    test_connection()

