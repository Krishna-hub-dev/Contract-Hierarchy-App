import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Builder — Parent/Child/Subchild Mapping")

# --- File upload ---
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
if not uploaded_file:
    st.info("Please upload your Excel file (must contain the required columns).")
    st.stop()

# --- Read and validate ---
df = pd.read_excel(uploaded_file)
df.columns = [c.strip() for c in df.columns]

required_cols = [
    "Original Name", "ID", "Contract Type",
    "Supplier Legal Entity (Contracts)", "Ariba Supplier Name",
    "Workspace ID", "Supplier Parent Child agreement links", "Effective Date"
]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

# Normalize columns
for col in required_cols:
    df[col] = df[col].astype(str).str.strip() if df[col].dtype == object else df[col]

df["Effective Date"] = pd.to_datetime(df["Effective Date"], errors="coerce")
st.subheader("Uploaded Data (preview)")
st.dataframe(df.head())

# --- Helper Functions ---
def norm(text):
    return re.sub(r"\s+", " ", text.lower().strip()) if text else ""

def date_variants(dt):
    if pd.isna(dt):
        return []
    d = pd.to_datetime(dt)
    return list(set([
        d.strftime("%-m/%-d/%Y"),
        d.strftime("%m/%d/%Y"),
        d.strftime("%b %d, %Y"),
        d.strftime("%B %d, %Y"),
        d.strftime("%Y-%m-%d")
    ]))

OUTPUT_COLS = ["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"]
final_rows = []

# --- Process per vendor ---
grouped = df.groupby(["Supplier Legal Entity (Contracts)", "Ariba Supplier Name"], dropna=False)

for (party_name, ariba_name), group in grouped:
    group = group.reset_index(drop=True)
    
    hierarchy = {i: "Child" for i in group.index}
    
    # Identify Parent (Master/MSA)
    parent_mask = group["Contract Type"].str.contains(r"\b(MSA|Master Services Agreement|Service Agreement|Technology Agreement|Product and Service Agreement)\b", case=False, na=False)
    for i in group[parent_mask].index:
        hierarchy[i] = "Parent"

    # Precompute search tokens per contract (names + date variants)
    contract_tokens = {}
    for i, row in group.iterrows():
        tokens = set([norm(row["Original Name"])])
        for dv in date_variants(row["Effective Date"]):
            tokens.add(dv.lower())
        contract_tokens[i] = tokens
    
    # Map references based on Supplier Parent Child links
    references_map = {i: set() for i in group.index}
    referenced_by_map = {i: set() for i in group.index}
    
    for i, row in group.iterrows():
        link_text = norm(row["Supplier Parent Child agreement links"])
        if not link_text:
            continue
        for j, tokens in contract_tokens.items():
            if i == j:
                continue
            if any(tok in link_text for tok in tokens):
                references_map[i].add(j)
                referenced_by_map[j].add(i)
    
    # Promote contracts referenced by others to Child/Parent (unless Parent)
    for j in group.index:
        if hierarchy[j] != "Parent" and referenced_by_map.get(j):
            hierarchy[j] = "Child/Parent"
    
    # Ensure Subchild mapping
    for i in group.index:
        if hierarchy[i] == "Child/Parent" and group.loc[i, "Contract Type"].lower() in ["change agreements", "amendment"]:
            # If it directly references Parent → Child else Subchild
            refs = references_map.get(i, set())
            if any(hierarchy[r] == "Parent" for r in refs):
                hierarchy[i] = "Child"
            else:
                hierarchy[i] = "Subchild"
        elif hierarchy[i] == "Child":
            # Check if referencing only Subchilds → keep as Child
            refs = references_map.get(i, set())
            if all(hierarchy[r] == "Subchild" for r in refs):
                hierarchy[i] = "Child/Parent"
    
    # Helper to append rows
    added = set()
    def append(idx, rel):
        row = group.loc[idx]
        final_rows.append({
            "FileName": row["Original Name"],
            "ContractID": row["ID"],
            "Parent_Child": rel,
            "ContractType": row["Contract Type"],
            "PartyName": party_name,
            "Ariba Supplier Name": ariba_name,
            "Workspace ID": row["Workspace ID"]
        })
        added.add(idx)
    
    # Output ordering: Parent → Child → Child/Parent → Subchild
    for p_idx in [i for i in group.index if hierarchy[i] == "Parent"]:
        append(p_idx, "Parent")
        for c_idx in sorted(referenced_by_map.get(p_idx, set()), key=lambda x: group.index.get_loc(x)):
            if c_idx in added:
                continue
            rel = hierarchy[c_idx]
            append(c_idx, rel)
            for s_idx in sorted(referenced_by_map.get(c_idx, set()), key=lambda x: group.index.get_loc(x)):
                if s_idx in added:
                    continue
                append(s_idx, "Subchild")
    
    # Add any remaining contracts
    for i in group.index:
        if i not in added:
            append(i, hierarchy[i])

# --- Build final DataFrame ---
out_df = pd.DataFrame(final_rows, columns=OUTPUT_COLS)

st.subheader("Generated Hierarchy")
st.dataframe(out_df, use_container_width=True)

# --- Download button ---
to_download = io.BytesIO()
with pd.ExcelWriter(to_download, engine="openpyxl") as writer:
    out_df.to_excel(writer, index=False, sheet_name="Hierarchy_Output")
to_download.seek(0)

st.download_button(
    "⬇️ Download Hierarchy Excel",
    data=to_download,
    file_name="Contract_Hierarchy_Output.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
