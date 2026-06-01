import os

def create_mock_files():
    # 1. Create a mock bank report in CSV format
    csv_content = """Txn Date,Amount,Payee,Type,Clear Date
2026-05-01,1250.00,Acme Corp,ACH,2026-05-03
2026-05-10,4500.00,Globex Corp,Wire,2026-05-15
2026-05-15,80.00,Local Diner,Card,2026-05-16
"""
    with open("mock_bank_report.csv", "w", encoding="utf-8") as f:
        f.write(csv_content)
    print("Created mock_bank_report.csv")

    # 2. Create sample EML files
    eml_acme = """From: billing@acme.com
To: finance@client.com
Subject: Remittance Advice for Acme Corp
Date: Fri, 1 May 2026 09:15:00 -0400
Content-Type: text/plain

Hello, this is the remittance advice for Acme Corp.
"""
    with open("acme_remit.eml", "w", encoding="utf-8") as f:
        f.write(eml_acme)
    print("Created acme_remit.eml")

    eml_globex = """From: treasury@globex.com
To: collections@client.com
Subject: Wire Remittance advice
Date: Sun, 10 May 2026 14:30:00 +0000
Content-Type: text/plain

Wire sent today.
"""
    with open("globex_remit.eml", "w", encoding="utf-8") as f:
        f.write(eml_globex)
    print("Created globex_remit.eml")

    eml_diner = """From: customer@diner.com
To: payees@client.com
Subject: Bill paid
Date: Thu, 15 May 2026 18:22:11 -0700
Content-Type: text/plain

Payment receipt enclosed.
"""
    with open("diner_remit.eml", "w", encoding="utf-8") as f:
        f.write(eml_diner)
    print("Created diner_remit.eml")

if __name__ == "__main__":
    create_mock_files()
