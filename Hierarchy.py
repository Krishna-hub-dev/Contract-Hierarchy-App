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

# Precompute searchable tokens for each contract (name + effective date variants)
def date_variants(dt):
    """Return multiple textual formats of a date to match mention in text."""
    if pd.isna(dt):
        return []
    variants = []
    try:
        d = pd.to_datetime(dt)
        variants.append(d.strftime("%-m/%-d/%Y"))      # 6/22/2020 or platform dependent (without leading zeros)
        variants.append(d.strftime("%m/%d/%Y"))        # 06/22/2020
        variants.append(d.strftime("%b %d, %Y"))       # Jun 22, 2020
        variants.append(d.strftime("%B %d, %Y"))       # June 22, 2020
        variants.append(d.strftime("%Y-%m-%d"))        # 2020-06-22
    except Exception:
        pass
    return list(set(variants))

# We'll output only these columns in the requested order
OUTPUT_COLS = ["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"]

final_rows = []

# Process per vendor (grouping by Ariba Supplier Name and Supplier Legal Entity)
group_by_cols = ["Supplier Legal Entity (Contracts)", "Ariba Supplier Name"]
grouped = df.groupby(group_by_cols, dropna=False)

for (party_name, ariba_name), group in grouped:
    # Keep original order as in file
    group = group.reset_index(drop=True)

    # Build lookup maps
    name_to_idx = {norm(r["Original Name"]): i for i, r in group.iterrows()}
    idx_to_name = {i: r["Original Name"] for i, r in group.iterrows()}

    # Precompute textual tokens per contract for robust matching:
    # - normalized original name
    # - effective date variants
    contract_search_tokens = {}
    for i, row in group.iterrows():
        tokens = set()
        tokens.add(norm(row["Original Name"]))
        for dv in date_variants(row["Effective Date"]):
            tokens.add(dv.lower())
        # Also include short name fragments (first 4-6 chars segments separated by non-alphanumeric)
        name_fragments = re.split(r"[^a-z0-9]+", norm(row["Original Name"]))
        for frag in name_fragments:
            if len(frag) >= 4:
                tokens.add(frag)
        contract_search_tokens[i] = tokens

    # Step A: initial classification using earlier rules
    # Default = Child
    hierarchy = {i: "Child" for i in group.index}

    # Identify Parent (Master/MSA etc.)
    parent_mask = group["Contract Type"].str.contains(r"\b(MSA|Master Services Agreement|Service Agreement|Technology Agreement|Product and Service Agreement)\b", case=False, na=False)
    for i in group[parent_mask].index:
        hierarchy[i] = "Parent"

    # Rough classify Subchilds and Child/Parent based on link text heuristics
    # We'll refine after building reference maps
    for i, row in group.iterrows():
        link_text = norm(row["Supplier Parent Child agreement links"])
        ctype = row["Contract Type"].lower()
        # Heuristics:
        if "change" in ctype or "amend" in ctype or re.search(r"\bco\b", row["Original Name"], flags=re.IGNORECASE):
            # If text mentions a "task order" or refers to another contract -> mark subchild tentatively
            if "task order" in link_text or "task" in link_text or "order dated" in link_text:
                hierarchy[i] = "Subchild"
            else:
                # still could be a Subchild if text contains a date matching a TO or references a contract
                hierarchy[i] = "Subchild"
        elif "task order" in ctype or "sow" in ctype or "statement of work" in ctype:
            # If it mentions Master in link text -> it's at least Child/Parent if it has children later
            if "master" in link_text or "msa" in link_text:
                hierarchy[i] = "Child/Parent"  # tentatively; will be demoted/promoted in next pass
            else:
                hierarchy[i] = "Child"

    # Step B: Build reference maps: which contract references which other contracts by name or date token
    # references_map[i] = set of indices that contract i references (textually)
    references_map = {i: set() for i in group.index}
    referenced_by_map = {i: set() for i in group.index}

    # For each contract, check link_text tokens against other contract tokens
    for i, row in group.iterrows():
        link_text = norm(row["Supplier Parent Child agreement links"])
        if not link_text:
            continue
        # check all other contracts for presence of their name or date tokens
        for j, tokens in contract_search_tokens.items():
            if i == j:
                continue
            # if any token of contract j appears in link_text, treat as a reference
            matched = False
            for tok in tokens:
                if not tok:
                    continue
                # use word-boundary match for longer tokens, substring for date formats and fragments
                if re.search(r"\b" + re.escape(tok) + r"\b", link_text):
                    matched = True
                    break
                # allow date formats or numeric fragments to match by substring
                if len(tok) <= 6 and tok.isdigit():
                    if tok in link_text:
                        matched = True
                        break
                if len(tok) >= 4 and tok in link_text:
                    # avoid accidental small matches; this is a fallback
                    matched = True
                    break
            if matched:
                references_map[i].add(j)
                referenced_by_map[j].add(i)

    # Step C: Promote any contract that is referenced by others to Child/Parent (unless it is Parent already)
    for j in group.index:
        if hierarchy[j] != "Parent" and referenced_by_map.get(j):
            hierarchy[j] = "Child/Parent"

    # Step D: For each contract classified as Subchild, find which contract(s) it references.
    # If it references some contract X, ensure X is Child/Parent (unless X is Parent)
    for i in group.index:
        if hierarchy[i] == "Subchild":
            referenced = references_map.get(i, set())
            # If it references an index j, promote j to Child/Parent unless it's Parent
            for j in referenced:
                if hierarchy[j] != "Parent":
                    hierarchy[j] = "Child/Parent"

    # Step E: After promotions, we may want to ensure ordering: Parent -> Child -> Child/Parent -> Subchild
    # But we must output in a traversal that places children under their parents when possible.
    # We'll try to build a simple tree: for each Parent, gather direct children (contracts that reference the parent),
    # then for each child gather its subchildren (contracts that reference the child).
    added = set()
    # map normalized name to index for quick lookup
    normname_to_idx = {}
    for i, row in group.iterrows():
        normname_to_idx[norm(row["Original Name"])] = i

    # Helper to add a contract row to final_rows
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

    # For each Parent, add parent then its children and subchildren
    parents_idx = [i for i in group.index if hierarchy[i] == "Parent"]
    # If no explicit Parent, we will later add orphans
    for p_idx in parents_idx:
        append_row(p_idx, "Parent")
        # children: contracts that reference this parent directly
        direct_children = sorted(list(referenced_by_map.get(p_idx, set())), key=lambda x: group.index.get_loc(x))
        for c_idx in direct_children:
            if c_idx in added:
                continue
            # Determine relation type (if c_idx itself has children -> Child/Parent)
            rel = hierarchy.get(c_idx, "Child")
            append_row(c_idx, rel if rel != "Subchild" else "Subchild")  # normally Child or Child/Parent or Subchild
            # add subchildren that reference this child
            subkids = sorted(list(referenced_by_map.get(c_idx, set())), key=lambda x: group.index.get_loc(x))
            for s_idx in subkids:
                if s_idx in added:
                    continue
                append_row(s_idx, "Subchild")

    # Add any remaining contracts in original order, respecting their final hierarchy type
    for i, row in group.iterrows():
        if i in added:
            continue
        rel = hierarchy.get(i, "Child")
        append_row(i, rel)

# Build final DataFrame
out_df = pd.DataFrame(final_rows, columns=["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"])

st.subheader("Generated Hierarchy (Parent → Child → Child/Parent → Subchild)")
st.dataframe(out_df, use_container_width=True)

# Download as Excel
to_download = io.BytesIO()
with pd.ExcelWriter(to_download, engine="openpyxl") as writer:
    out_df.to_excel(writer, index=False, sheet_name="Hierarchy_Output")
to_download.seek(0)

st.download_button("⬇️ Download Hierarchy Excel", data=to_download, file_name="Contract_Hierarchy_Output.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
