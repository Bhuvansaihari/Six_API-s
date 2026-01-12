"""
Test script to analyze the stored procedure's result sets.

This script helps identify how many result sets the SP returns and their structure.
"""

import pyodbc
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import get_settings


def analyze_sp_resultsets():
    """Analyze the stored procedure's result sets."""
    print("=" * 60)
    print("Analyzing Stored Procedure Result Sets")
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
        
        print("\n[Executing stored procedure...]")
        cursor.execute("""
            EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobList]
                @CandidateID = ?
        """, (3044,))
        
        result_set_num = 1
        total_rows = 0
        
        while True:
            print(f"\n--- Result Set {result_set_num} ---")
            
            if cursor.description:
                # Print column information
                columns = [col[0] for col in cursor.description]
                print(f"Columns ({len(columns)}): {', '.join(columns)}")
                
                # Fetch rows WITHOUT processing them
                try:
                    rows = cursor.fetchall()
                    print(f"Rows: {len(rows)}")
                    total_rows += len(rows)
                    
                    # Show first row as sample
                    if rows:
                        print(f"Sample row: {dict(zip(columns, rows[0]))}")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to fetch rows: {e}")
                    print(f"Error type: {type(e).__name__}")
                    print(f"Error args: {e.args}")
                    break
            else:
                print("No description (no result set)")
            
            # Try to move to next result set
            try:
                has_more = cursor.nextset()
                if not has_more:
                    print(f"\n[No more result sets]")
                    break
                result_set_num += 1
            except Exception as e:
                print(f"\n[ERROR] Failed on nextset(): {e}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error args: {e.args}")
                break
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print(f"[SUCCESS] Analyzed {result_set_num} result set(s)")
        print(f"Total rows across all sets: {total_rows}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Full exception: {repr(e)}")
        sys.exit(1)


if __name__ == "__main__":
    analyze_sp_resultsets()
