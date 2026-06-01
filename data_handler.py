import pandas as pd
import numpy as np
import os
import datetime

# Expected standard fields
FIELD_TX_DATE = "Transaction Date"
FIELD_VALUE = "Value"
FIELD_COUNTERPARTY = "Counterparty"
FIELD_CATEGORY = "Category"
FIELD_CLEAR_DATE = "Bank Clearance Date"

# Guessing maps for auto-mapping
AUTO_MAP_GUESSES = {
    FIELD_TX_DATE: ["transaction date", "tx date", "txn date", "date", "trans date", "booking date"],
    FIELD_VALUE: ["value", "amount", "sum", "total", "val", "amt", "price"],
    FIELD_COUNTERPARTY: ["counterparty", "payee", "vendor", "customer", "name", "description", "recipient"],
    FIELD_CATEGORY: ["category", "type", "method", "class", "transaction type", "txn type"],
    FIELD_CLEAR_DATE: ["bank clearance date", "clearance date", "value date", "cleared date", "clear date", "effective date"]
}

def load_file_columns(file_path):
    """
    Loads a file (CSV or XLSX) and returns a list of its column headers.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext == '.csv':
        df = pd.read_csv(file_path, nrows=0) # Only load headers
        return list(df.columns)
    elif ext in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path, nrows=0) # Only load headers
        return list(df.columns)
    else:
        raise ValueError("Unsupported file format. Please load a .csv or .xlsx file.")

def guess_column_mappings(columns):
    """
    Takes a list of column headers from the loaded file and guesses which map to which expected fields.
    """
    mappings = {
        FIELD_TX_DATE: None,
        FIELD_VALUE: None,
        FIELD_COUNTERPARTY: None,
        FIELD_CATEGORY: None,
        FIELD_CLEAR_DATE: None
    }
    
    used_columns = set()
    
    # Try to find best fit for each expected field
    for field, guesses in AUTO_MAP_GUESSES.items():
        for col in columns:
            col_clean = str(col).strip().lower()
            if col_clean in guesses and col not in used_columns:
                mappings[field] = col
                used_columns.add(col)
                break
                
    # Fallback to fuzzy substring match if exact match not found
    for field, guesses in AUTO_MAP_GUESSES.items():
        if mappings[field] is not None:
            continue
        for col in columns:
            col_clean = str(col).strip().lower()
            if any(guess in col_clean for guess in guesses) and col not in used_columns:
                mappings[field] = col
                used_columns.add(col)
                break
                
    return mappings

def parse_date(val):
    """
    Helper to parse a date from pandas cell.
    Returns datetime.date or None.
    """
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        if isinstance(val, datetime.datetime):
            return val.date()
        return val
    # If string
    s = str(val).strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y"]:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # Try pandas parser as a fallback
    try:
        dt = pd.to_datetime(val)
        if not pd.isna(dt):
            return dt.date()
    except Exception:
        pass
    return None

def process_loaded_dataframe(file_path, mappings):
    """
    Loads the full dataframe from the file, applies the mappings, parses dates,
    and returns a list of dictionaries representing each transaction.
    Each dict has standardized keys + 'OriginalRow' dict of original columns.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext == '.csv':
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
        
    transactions = []
    
    for idx, row in df.iterrows():
        # Extracted values based on mappings
        tx_date_raw = row.get(mappings[FIELD_TX_DATE]) if mappings[FIELD_TX_DATE] else None
        value_raw = row.get(mappings[FIELD_VALUE]) if mappings[FIELD_VALUE] else ""
        counterparty_raw = row.get(mappings[FIELD_COUNTERPARTY]) if mappings[FIELD_COUNTERPARTY] else ""
        category_raw = row.get(mappings[FIELD_CATEGORY]) if mappings[FIELD_CATEGORY] else "Standard"
        clear_date_raw = row.get(mappings[FIELD_CLEAR_DATE]) if mappings[FIELD_CLEAR_DATE] else None
        
        # Clean/Parse
        tx_date = parse_date(tx_date_raw)
        clear_date = parse_date(clear_date_raw)
        
        # Make a dict of the original row data to preserve for export
        original_row_data = {str(k): (v if not pd.isna(v) else "") for k, v in row.items()}
        
        # Convert numeric values cleanly
        if pd.isna(value_raw) or value_raw == "":
            value_str = ""
        else:
            try:
                # Format to 2 decimal places if it's a number
                value_str = f"{float(value_raw):.2f}"
            except ValueError:
                value_str = str(value_raw)

        transactions.append({
            "Id": idx,
            "TransactionDate": tx_date.strftime("%Y-%m-%d") if tx_date else "",
            "Value": value_str,
            "Counterparty": str(counterparty_raw).strip() if not pd.isna(counterparty_raw) else "",
            "Category": str(category_raw).strip() if not pd.isna(category_raw) else "Standard",
            "BankClearanceDate": clear_date.strftime("%Y-%m-%d") if clear_date else "",
            "EmailSentDate": "",
            "DayDelta": "",
            "Status": "Pending", # Pending, Processed
            "OriginalRow": original_row_data
        })
        
    return transactions

def export_transactions(file_path, transactions, original_columns, mappings):
    """
    Exports the updated transactions list back to a CSV or Excel file.
    Adds 'Email Sent Date' and 'Day Delta' to the output.
    """
    # Reconstruct rows
    output_rows = []
    for tx in transactions:
        row_data = dict(tx["OriginalRow"])
        # Add new columns
        row_data["Email Sent Date"] = tx["EmailSentDate"]
        row_data["Day Delta"] = tx["DayDelta"]
        output_rows.append(row_data)
        
    df_out = pd.DataFrame(output_rows)
    
    _, ext = os.path.splitext(file_path.lower())
    if ext == '.csv':
        df_out.to_csv(file_path, index=False)
    else:
        df_out.to_excel(file_path, index=False)
