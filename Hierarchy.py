import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Contract Hierarchy Builder – Detect Subchild Parents", layout="wide")
st.title("📁 Contract Hierarchy Builder — Parent / Child / Subchild Hierarchy")

# --- File upload ---
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
if not uploaded_file:
    st.info("Please upload your Excel file (must contain the specified columns).")
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

# Normalize columns and types
df["Original Name"] = df["Original Name"].astype(str).str.strip()
df["ID"] = df["ID"].astype(str)
df["Contract Type"] = df["Contract Type"].astype(str).str.strip()
df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].astype(str).str.strip()
df["Ariba Supplier Name"] = df["Ariba Supplier Name"].astype(str).str.strip()
df["Workspace ID"] = df["Workspace ID"].astype(str).str.strip()
df["Supplier Parent Child agreement links"] = df["Supplier Parent Child agreement links"].fillna("").astype(str)
df["Effective Date"] = pd.to_datetime(df["Effective Date"], errors="coerce")

st.subheader("Uploaded Data (preview)")
st.dataframe(df.head())

# Helper functions
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def date_variants(dt):
    if pd.isna(dt):
        return []
    variants = []
    try:
        d = pd.to_datetime(dt)
        variants.append(d.strftime("%-m/%-d/%Y"))
        variants.append(d.strftime("%m/%d/%Y"))
        variants.append(d.strftime("%b %d, %Y"))
        variants.append(d.strftime("%B %d, %Y"))
        variants.append(d.strftime("%Y-%m-%d"))
    except Exception:
        pass
    return list(set(variants))

OUTPUT_COLS = ["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"]

final_rows = []

# Process per vendor
group_by_cols = ["Supplier Legal Entity (Contracts)", "Ariba Supplier Name"]
grouped = df.groupby(group_by_cols, dropna=False)

for (party_name, ariba_name), group in grouped:
    group = group.reset_index(drop=True)
    
    # Lookup maps
    contract_search_tokens = {}
    for i, row in group.iterrows():
        tokens = set()
        tokens.add(norm(row["Original Name"]))
        for dv in date_variants(row["Effective Date"]):
            tokens.add(dv.lower())
        name_fragments = re.split(r"[^a-z0-9]+", norm(row["Original Name"]))
        for frag in name_fragments:
            if len(frag) >= 4:
                tokens.add(frag)
        contract_search_tokens[i] = tokens

    # Step 1: classify initial Parents (Master / MSA)
    hierarchy = {i: "Child" for i in group.index}
    parent_mask = group["Contract Type"].str.contains(r"\b(MSA|Master Services Agreement|Service Agreement|Technology Agreement|Product and Service Agreement)\b", case=False, na=False)
    for i in group[parent_mask].index:
        hierarchy[i] = "Parent"

    # Step 2: references mapping
    references_map = {i: set() for i in group.index}       # contracts this contract references
    referenced_by_map = {i: set() for i in group.index}   # contracts referencing this contract
    
    for i, row in group.iterrows():
        link_text = norm(row["Supplier Parent Child agreement links"])
        if not link_text:
            continue
        for j, tokens in contract_search_tokens.items():
            if i == j:
                continue
            for tok in tokens:
                if not tok:
                    continue
                if re.search(r"\b" + re.escape(tok) + r"\b", link_text) or (len(tok)>=4 and tok in link_text):
                    references_map[i].add(j)
                    referenced_by_map[j].add(i)
                    break

    # Step 3: Promote any contract referenced by others to Child/Parent unless already Parent
    for j in group.index:
        if hierarchy[j] != "Parent" and referenced_by_map.get(j):
            hierarchy[j] = "Child/Parent"

    # Step 4: Determine Subchilds based on links to other Child/Parent
    for i in group.index:
        if hierarchy[i] == "Child" and references_map[i]:
            hierarchy[i] = "Subchild"
            for ref in references_map[i]:
                if hierarchy[ref] != "Parent":
                    hierarchy[ref] = "Child/Parent"

    # Step 5: recursive promotion for subchilds’ parents
    def promote_parents(idx):
        for ref in references_map[idx]:
            if hierarchy[ref] != "Parent":
                hierarchy[ref] = "Child/Parent"
                promote_parents(ref)
    for i in group.index:
        if hierarchy[i] == "Subchild":
            promote_parents(i)

    # Step 6: Output in order Parent → Child → Child/Parent → Subchild
    added = set()
    def append_row(idx, rel_type):
        row = group.loc[idx]
        final_rows.append({
            "FileName": row["Original Name"],
            "ContractID": row["ID"],
            "Parent_Child": rel_type,
            "ContractType": row["Contract Type"],
            "PartyName": party_name,
            "Ariba Supplier Name": ariba_name,
            "Workspace ID": row["Workspace ID"]
        })
        added.add(idx)

    # Add hierarchy recursively
    def add_hierarchy(idx):
        if idx in added:
            return
        rel_type = hierarchy[idx]
        append_row(idx, rel_type)
        for child_idx in sorted(referenced_by_map.get(idx, []), key=lambda x: group.index.get_loc(x)):
            add_hierarchy(child_idx)
    for p_idx in [i for i in group.index if hierarchy[i]=="Parent"]:
        add_hierarchy(p_idx)
    # add any remaining
    for i in group.index:
        if i not in added:
            append_row(i, hierarchy[i])

# Build final DataFrame
out_df = pd.DataFrame(final_rows, columns=OUTPUT_COLS)

st.subheader("Generated Hierarchy (Parent → Child → Child/Parent → Subchild)")
st.dataframe(out_df, use_container_width=True)

# Download Excel
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
