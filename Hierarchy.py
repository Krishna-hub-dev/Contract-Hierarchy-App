import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Contract Hierarchy Builder – Detect Subchild Parents", layout="wide")
st.title("📁 Contract Hierarchy Builder — Promote Parents of Subchildren")

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

# Helper: normalize text for matching
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

# Precompute textual tokens for each contract (name + effective date variants)
def date_variants(dt):
    if pd.isna(dt):
        return []
    variants = []
    try:
        d = pd.to_datetime(dt)
        variants.append(d.strftime("%-m/%-d/%Y"))      # 6/22/2020
        variants.append(d.strftime("%m/%d/%Y"))        # 06/22/2020
        variants.append(d.strftime("%b %d, %Y"))       # Jun 22, 2020
        variants.append(d.strftime("%B %d, %Y"))       # June 22, 2020
        variants.append(d.strftime("%Y-%m-%d"))        # 2020-06-22
    except Exception:
        pass
    return list(set(variants))

# Output columns
OUTPUT_COLS = ["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"]

final_rows = []

# Process per vendor
group_by_cols = ["Supplier Legal Entity (Contracts)", "Ariba Supplier Name"]
grouped = df.groupby(group_by_cols, dropna=False)

for (party_name, ariba_name), group in grouped:
    group = group.reset_index(drop=True)

    # Build lookup maps
    contract_search_tokens = {}
    for i, row in group.iterrows():
        tokens = set()
        tokens.add(norm(row["Original Name"]))
        for dv in date_variants(row["Effective Date"]):
            tokens.add(dv.lower())
        # name fragments
        name_fragments = re.split(r"[^a-z0-9]+", norm(row["Original Name"]))
        for frag in name_fragments:
            if len(frag) >= 4:
                tokens.add(frag)
        contract_search_tokens[i] = tokens

    # Step A: initial classification
    hierarchy = {i: "Child" for i in group.index}
    parent_mask = group["Contract Type"].str.contains(r"\b(MSA|Master Services Agreement|Service Agreement|Technology Agreement|Product and Service Agreement)\b", case=False, na=False)
    for i in group[parent_mask].index:
        hierarchy[i] = "Parent"

    # Step B: Build references maps
    references_map = {i: set() for i in group.index}
    referenced_by_map = {i: set() for i in group.index}
    for i, row in group.iterrows():
        link_text = norm(row["Supplier Parent Child agreement links"])
        if not link_text:
            continue
        for j, tokens in contract_search_tokens.items():
            if i == j:
                continue
            matched = False
            for tok in tokens:
                if not tok:
                    continue
                if re.search(r"\b" + re.escape(tok) + r"\b", link_text):
                    matched = True
                    break
                if len(tok) <= 6 and tok.isdigit() and tok in link_text:
                    matched = True
                    break
                if len(tok) >= 4 and tok in link_text:
                    matched = True
                    break
            if matched:
                references_map[i].add(j)
                referenced_by_map[j].add(i)

    # Step C: Promote contracts that are referenced by others
    for j in group.index:
        if hierarchy[j] != "Parent" and referenced_by_map.get(j):
            hierarchy[j] = "Child/Parent"

    # Step D: Correct Subchild/Child based on references
    for i in group.index:
        if hierarchy[i] == "Child":
            refs = references_map[i]
            has_parent_ref = any(hierarchy[r]=="Parent" for r in refs)
            has_child_ref = any(hierarchy[r]=="Child" or hierarchy[r]=="Child/Parent" for r in refs)
            
            if has_parent_ref and not has_child_ref:
                hierarchy[i] = "Child"
            elif has_child_ref:
                hierarchy[i] = "Subchild"

    # Step E: Ensure ordering Parent -> Child -> Child/Parent -> Subchild
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

    parents_idx = [i for i in group.index if hierarchy[i] == "Parent"]
    for p_idx in parents_idx:
        append_row(p_idx, "Parent")
        direct_children = sorted(list(referenced_by_map.get(p_idx, set())), key=lambda x: group.index.get_loc(x))
        for c_idx in direct_children:
            if c_idx in added:
                continue
            rel = hierarchy.get(c_idx, "Child")
            append_row(c_idx, rel)
            subkids = sorted(list(referenced_by_map.get(c_idx, set())), key=lambda x: group.index.get_loc(x))
            for s_idx in subkids:
                if s_idx in added:
                    continue
                append_row(s_idx, "Subchild")

    # Add any remaining contracts
    for i, row in group.iterrows():
        if i in added:
            continue
        rel = hierarchy.get(i, "Child")
        append_row(i, rel)

# Build final DataFrame
out_df = pd.DataFrame(final_rows, columns=OUTPUT_COLS)

st.subheader("Generated Hierarchy (Parent → Child → Child/Parent → Subchild)")
st.dataframe(out_df, use_container_width=True)

# Download as Excel
to_download = io.BytesIO()
with pd.ExcelWriter(to_download, engine="openpyxl") as writer:
    out_df.to_excel(writer, index=False, sheet_name="Hierarchy_Output")
to_download.seek(0)

st.download_button("⬇️ Download Hierarchy Excel", data=to_download, file_name="Contract_Hierarchy_Output.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
