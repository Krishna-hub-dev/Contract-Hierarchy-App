import pandas as pd
import re

# === CONFIG ===
input_file = "Contracts_Input.xlsx"     # your source Excel file
output_file = "Hierarchy_Output.xlsx"   # name of the output Excel

# === STEP 1: Load the input Excel ===
df = pd.read_excel(input_file)

# Ensure consistent column names
df.columns = df.columns.str.strip().str.lower()

# Example: expected columns might include:
# 'filename', 'workspace id', 'ariba supplier name', 'partyname', 'contract type', 'relation'

# === STEP 2: Initialize output DataFrame ===
output = pd.DataFrame(columns=[
    "FileName",
    "ContractID",
    "Parent_Child",
    "ContractType",
    "PartyName",
    "Ariba Supplier Name",
    "Workspace ID"
])

# === STEP 3: Extract ContractID from filename ===
def extract_contract_id(filename):
    match = re.search(r'CW\d+', str(filename))
    return match.group(0) if match else ""

df["contract_id"] = df["filename"].apply(extract_contract_id)

# === STEP 4: Determine Hierarchy type ===
def classify_relation(row):
    relation = str(row.get("relation", "")).lower()
    if "parent" in relation and "child" in relation:
        return "Child/Parent"
    elif "parent" in relation:
        return "Parent"
    elif "sub" in relation:
        return "Sub Child"
    elif "child" in relation:
        return "Child"
    return "Unknown"

df["Parent_Child"] = df.apply(classify_relation, axis=1)

# === STEP 5: Map to output columns ===
output["FileName"] = df["filename"]
output["ContractID"] = df["contract_id"]
output["Parent_Child"] = df["Parent_Child"]
output["ContractType"] = df["contract type"]
output["PartyName"] = df["partyname"]
output["Ariba Supplier Name"] = df["ariba supplier name"]
output["Workspace ID"] = df["workspace id"]

# === STEP 6: Export to Excel ===
output.to_excel(output_file, index=False)
print(f"✅ Hierarchy Excel generated successfully: {output_file}")
