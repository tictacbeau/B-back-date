import parser_utils
import data_handler
import os
import datetime

def test_pipeline():
    print("--- Running Core Pipeline Unit Tests ---")
    
    # 1. Load file columns
    cols = data_handler.load_file_columns("mock_bank_report.csv")
    print(f"Loaded columns: {cols}")
    assert len(cols) == 5, "Should have 5 columns"
    
    # 2. Guess mapping
    mappings = data_handler.guess_column_mappings(cols)
    print(f"Guessed mappings: {mappings}")
    assert mappings[data_handler.FIELD_TX_DATE] == "Txn Date"
    assert mappings[data_handler.FIELD_VALUE] == "Amount"
    assert mappings[data_handler.FIELD_COUNTERPARTY] == "Payee"
    assert mappings[data_handler.FIELD_CATEGORY] == "Type"
    assert mappings[data_handler.FIELD_CLEAR_DATE] == "Clear Date"
    
    # 3. Process loaded dataframe
    txs = data_handler.process_loaded_dataframe("mock_bank_report.csv", mappings)
    print(f"Processed {len(txs)} transactions:")
    for t in txs:
        print(f"  ID: {t['Id']} | Date: {t['TransactionDate']} | Value: {t['Value']} | Mapped Payee: {t['Counterparty']} | Cat: {t['Category']} | Cleared: {t['BankClearanceDate']}")
        
    assert len(txs) == 3
    
    # 4. Extract date from EMLs
    # Acme Corp
    acme_dt = parser_utils.extract_date_from_eml("acme_remit.eml")
    print(f"Acme EML Date: {acme_dt}")
    assert acme_dt == datetime.datetime(2026, 5, 1, 9, 15, 0), "Acme date mismatch"
    
    # Globex Corp
    globex_dt = parser_utils.extract_date_from_eml("globex_remit.eml")
    print(f"Globex EML Date: {globex_dt}")
    assert globex_dt == datetime.datetime(2026, 5, 10, 14, 30, 0), "Globex date mismatch"
    
    # Diner
    diner_dt = parser_utils.extract_date_from_eml("diner_remit.eml")
    print(f"Diner EML Date: {diner_dt}")
    assert diner_dt == datetime.datetime(2026, 5, 15, 18, 22, 11), "Diner date mismatch"

    # 5. Extract date from pasted text
    pasted_text = """From: random@test.com
Date: Mon, 18 May 2026 12:00:00 -0400
Subject: Test pasted text

Hello there
"""
    pasted_dt = parser_utils.extract_date_from_text(pasted_text)
    print(f"Pasted Text Extracted Date: {pasted_dt}")
    assert pasted_dt == datetime.datetime(2026, 5, 18, 12, 0, 0), "Pasted text date mismatch"

    # 6. Apply email date updates and calculate deltas
    # Acme (row 0)
    txs[0]["EmailSentDate"] = acme_dt.date().strftime("%Y-%m-%d")
    txs[0]["DayDelta"] = str((datetime.datetime.strptime(txs[0]["BankClearanceDate"], "%Y-%m-%d").date() - acme_dt.date()).days)
    txs[0]["Status"] = "Processed"
    
    # Globex (row 1)
    txs[1]["EmailSentDate"] = globex_dt.date().strftime("%Y-%m-%d")
    txs[1]["DayDelta"] = str((datetime.datetime.strptime(txs[1]["BankClearanceDate"], "%Y-%m-%d").date() - globex_dt.date()).days)
    txs[1]["Status"] = "Processed"
    
    # Diner (row 2)
    txs[2]["EmailSentDate"] = diner_dt.date().strftime("%Y-%m-%d")
    txs[2]["DayDelta"] = str((datetime.datetime.strptime(txs[2]["BankClearanceDate"], "%Y-%m-%d").date() - diner_dt.date()).days)
    txs[2]["Status"] = "Processed"
    
    print("\nUpdated transactions with Email Dates & Deltas:")
    for t in txs:
        print(f"  Payee: {t['Counterparty']} | Cleared: {t['BankClearanceDate']} | Email Sent: {t['EmailSentDate']} | Delta: {t['DayDelta']} days")
        
    assert txs[0]["DayDelta"] == "2" # May 3 - May 1
    assert txs[1]["DayDelta"] == "5" # May 15 - May 10
    assert txs[2]["DayDelta"] == "1" # May 16 - May 15

    # 7. Export results
    export_file = "test_export.csv"
    data_handler.export_transactions(export_file, txs, cols, mappings)
    print(f"Exported to {export_file}")
    
    assert os.path.exists(export_file)
    with open(export_file, 'r', encoding='utf-8') as f:
        content = f.read()
        print("Exported Content:")
        print(content)
        assert "Email Sent Date" in content
        assert "Day Delta" in content
        
    # Clean up test export
    os.remove(export_file)
    print("--- Core Tests Passed Successfully! ---")

if __name__ == "__main__":
    test_pipeline()
