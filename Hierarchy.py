import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Generator – Parent / Child / Subchild Logic")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Ensure required columns exist
        required_cols = ["Contract Type", "Original Name", "ID", 
                         "Supplier Legal Entity (Contracts)", "Ariba Supplier Name", "Supplier Parent Child Link"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Convert columns to string safely
        for col in required_cols:
            df[col] = df[col].astype(str)

        # Strip and normalize supplier names
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()
        df["Supplier Parent Child Link"] = df["Supplier Parent Child Link"].str.strip()

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Process by supplier to maintain grouping
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):

            # --- Identify Parents (MSA and similar) ---
            parent_rows = group[group["Contract Type"].str.contains("MSA|Service Agreement|Technology Agreement|Product and Service Agreement", case=False, na=False)]

            for _, parent in parent_rows.iterrows():
                output_rows.append({
                    "FileName": parent["Original Name"],
                    "ContractID": parent["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": parent["Contract Type"],
                    "PartyName": parent["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": parent["Ariba Supplier Name"]
                })

            # Remaining contracts
            remaining = group[~group.index.isin(parent_rows.index)]

            # Maintain order of appearance
            for _, row in remaining.iterrows():
                link_info = row["Supplier Parent Child Link"]

                # Determine relationship based on link info
                if "Parent" in link_info and "Child" in link_info:
                    relation = "Child/Parent"
                elif "Parent" in link_info:
                    relation = "Child"
                elif "Child" in link_info:
                    relation = "Subchild"
                else:
                    # fallback: use contract type logic
                    if "Change" in row["Contract Type"] or "Amend" in row["Contract Type"] or "CO" in row["Original Name"]:
                        relation = "Subchild"
                    elif "Task Order" in row["Contract Type"] or "SOW" in row["Contract Type"]:
                        relation = "Child"
                    else:
                        relation = "Child"

                output_rows.append({
                    "FileName": row["Original Name"],
                    "ContractID": row["ID"],
                    "Parent_Child": relation,
                    "ContractType": row["Contract Type"],
                    "PartyName": row["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": row["Ariba Supplier Name"]
                })

        # Convert to DataFrame
        output_df = pd.DataFrame(output_rows)

        # Optional: reorder to have Parent → Child → Child/Parent → Subchild
        relation_order = {"Parent": 0, "Child": 1, "Child/Parent": 2, "Subchild": 3}
        output_df["RelationOrder"] = output_df["Parent_Child"].map(relation_order)
        output_df = output_df.sort_values(by=["RelationOrder"]).drop(columns=["RelationOrder"])

        st.subheader("📊 Generated Contract Hierarchy")
        st.dataframe(output_df)

        # Download Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            output_df.to_excel(writer, index=False, sheet_name="Hierarchy_Output")
        buffer.seek(0)

        st.download_button(
            label="📥 Download Hierarchy Excel",
            data=buffer,
            file_name="Contract_Hierarchy_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
else:
    st.info("👆 Please upload your Excel file to begin.")
