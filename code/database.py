
import pyodbc

def get_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=DESKTOP-1CQ6CT3\\SQLEXPRESS;"
            "DATABASE=leaveagent;"
            "Trusted_Connection=yes;"
        )
        return conn
    except pyodbc.Error as err:
        print("Database connection error:", err)
        return None