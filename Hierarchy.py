import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")

st.title("📑 Contract Hierarchy Builder")
st.write("Upload your Excel file to automatically identify Parent → Child → Subchild relationships.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    st.subheader("📋 Uploaded Data Preview")
    st.dataframe(df.head())

    # --- Clean column names ---
    df.columns = [c.strip() for c in df.columns]

    required_cols = [
        "Original Name",
        "ID",
        "Contract Type",
        "Supplier Legal Entity (Contracts)",
        "Ariba Supplier Name",
        "Workspace ID",
        "Supplier Parent Child agreement links",
        "Effective Date"
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # --- Normalize data ---
    df["Effective Date"] = pd.to_datetime(df["Effective Date"], errors="coerce")
    df["Supplier Parent Child agreement links"] = df["Supplier Parent Child agreement links"].fillna("").astype(str)

    # --- Identify Parent Contracts (Master/MSA) ---
    df["Parent_Child"] = "Child"  # default
    parent_mask = df["Contract Type"].str.contains("Master|MSA", case=False, na=False)
    df.loc[parent_mask, "Parent_Child"] = "Parent"

    # --- Identify Child & Subchild Contracts ---
    def classify_relation(row):
        text = row["Supplier Parent Child agreement links"].lower()

        # Subchild logic (refers to Task Order)
        if "task order" in text and "change" in row["Contract Type"].lower():
            return "Subchild"

        # Child/Parent logic (Task Order with reference to Master)
        if "master" in text and "task" in row["Contract Type"].lower():
            return "Child/Parent"

        # Child logic (if references master agreement)
        if "master" in text or "msa" in text:
            return "Child"

        # Parent logic (if no references)
        if row["Contract Type"].lower() in ["master services agreement", "msa"]:
            return "Parent"

        return row["Parent_Child"]

    df["Parent_Child"] = df.apply(classify_relation, axis=1)

    # --- Group by Supplier to form hierarchy order ---
    result_rows = []
    for vendor, group in df.groupby("Ariba Supplier Name"):
        group_sorted = group.sort_values(by="Effective Date", ascending=True)

        parent_rows = group_sorted[group_sorted["Parent_Child"] == "Parent"]
        child_rows = group_sorted[group_sorted["Parent_Child"] == "Child"]
        child_parent_rows = group_sorted[group_sorted["Parent_Child"] == "Child/Parent"]
        subchild_rows = group_sorted[group_sorted["Parent_Child"] == "Subchild"]

        ordered = pd.concat([parent_rows, child_rows, child_parent_rows, subchild_rows])
        result_rows.append(ordered)

    final_df = pd.concat(result_rows)

    # --- Format Output ---
    output_df = final_df.rename(columns={
        "Original Name": "FileName",
        "ID": "ContractID",
        "Contract Type": "ContractType",
        "Supplier Legal Entity (Contracts)": "PartyName",
    })[
        ["FileName", "ContractID", "Parent_Child", "ContractType", "PartyName", "Ariba Supplier Name", "Workspace ID"]
    ]

    st.subheader("✅ Generated Contract Hierarchy")
    st.dataframe(output_df, use_container_width=True)

    # --- Download Output ---
    output_xlsx = "Contract_Hierarchy_Output.xlsx"
    output_df.to_excel(output_xlsx, index=False)

    with open(output_xlsx, "rb") as f:
        st.download_button(
            label="⬇️ Download Hierarchy Excel",
            data=f,
            file_name=output_xlsx,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Please upload your Excel file to begin.")
