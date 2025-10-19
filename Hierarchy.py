import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Parent-Child Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Builder – Using Supplier Parent Child Links")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Standardize column names and text
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()
        if "Supplier Parent Child Link Info" not in df.columns:
            df["Supplier Parent Child Link Info"] = ""

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Process supplier by supplier
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):
            # Keep track of added contracts
            added_ids = set()

            # Maintain input order
            group = group.reset_index(drop=True)

            # Step 1: Add Parent contracts first (MSA, Service Agreements, Technology Agreements, Product & Service Agreements)
            parent_mask = group["Contract Type"].str.contains("MSA|Service Agreement|Technology Agreement|Product and Service Agreement", case=False, na=False)
            for idx, parent in group[parent_mask].iterrows():
                output_rows.append({
                    "FileName": parent["Original Name"],
                    "ContractID": parent["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": parent["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": parent.get("Ariba Supplier Name", "")
                })
                added_ids.add(parent["ID"])

            # Step 2: Process remaining contracts in original file order
            remaining = group[~group["ID"].isin(added_ids)]
            for idx, row in remaining.iterrows():
                # Check if this row is linked to any contract already added
                link_info = str(row.get("Supplier Parent Child Link Info", ""))
                linked_parents = [c for c in output_rows if c["FileName"] in link_info]

                if linked_parents:
                    # If linked to an existing parent or Child/Parent, assign accordingly
                    parent_names = [c["FileName"] for c in linked_parents]

                    # Determine type
                    if any(c["Parent_Child"] in ["Child/Parent", "Parent"] for c in linked_parents):
                        relation_type = "Subchild"
                    else:
                        relation_type = "Child"

                    output_rows.append({
                        "FileName": row["Original Name"],
                        "ContractID": row["ID"],
                        "Parent_Child": relation_type,
                        "ContractType": row["Contract Type"],
                        "PartyName": supplier,
                        "Ariba Supplier Name": row.get("Ariba Supplier Name", "")
                    })
                    added_ids.add(row["ID"])

                    # If this row itself is referenced by later rows, mark it as Child/Parent
                    is_parent_of_others = remaining["Supplier Parent Child Link Info"].astype(str).str.contains(row["Original Name"], case=False, na=False).any()
                    if is_parent_of_others and relation_type == "Child":
                        output_rows[-1]["Parent_Child"] = "Child/Parent"
                else:
                    # No link info → direct Child under MSA (or Parent if no MSA)
                    relation_type = "Child"
                    if not parent_mask.any():
                        relation_type = "Parent"

                    output_rows.append({
                        "FileName": row["Original Name"],
                        "ContractID": row["ID"],
                        "Parent_Child": relation_type,
                        "ContractType": row["Contract Type"],
                        "PartyName": supplier,
                        "Ariba Supplier Name": row.get("Ariba Supplier Name", "")
                    })
                    added_ids.add(row["ID"])

        # Create DataFrame
        output_df = pd.DataFrame(output_rows)

        st.subheader("📊 Generated Contract Hierarchy (Ordered & Nested)")
        st.dataframe(output_df)

        # Excel Download
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
