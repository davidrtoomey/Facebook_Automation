import sqlite3
import os

DB_PATH = "marketplace_automation.db"


def reset_messaged_status():
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Update all listings to messaged=False
            cursor.execute("UPDATE listings SET messaged = FALSE")
            count = cursor.rowcount

            conn.commit()
            conn.close()
            print(f"✅ Reset 'messaged' status for {count} listings in {DB_PATH}")

            # Also update the export to listings.json to reflect this
            from utils.sqlite_manager import SQLiteStateManager

            manager = SQLiteStateManager(DB_PATH)
            manager.export_to_json()
            print("✅ Exported updated listings to listings.json")

        except Exception as e:
            print(f"❌ Error resetting messaged status: {e}")
    else:
        print(f"⚠️ {DB_PATH} not found.")


if __name__ == "__main__":
    reset_messaged_status()
