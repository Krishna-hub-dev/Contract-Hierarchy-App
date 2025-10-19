import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Generator – Full Hierarchy with Subchilds")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()
        df["Supplier Parent Child Link"] = df.get("Supplier Parent Child Link", "").astype(str)

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Process by supplier
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):

            # Maintain original file order
            group = group.reset_index(drop=True)

            # Identify Parent Contracts
            parent_keywords = ["MSA", "SERVICE AGREEMENT", "TECHNOLOGY AGREEMENT", "PRODUCT AND SERVICE AGREEMENT"]
            parents = group[group["Contract Type"].str.contains('|'.join(parent_keywords), case=False, na=False)]

            # Keep track of contracts that are already added
            added_contracts = set()

            for _, parent in parents.iterrows():
                output_rows.append({
                    "FileName": parent["Original Name"],
                    "ContractID": parent["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": parent["Contract Type"],
                    "PartyName": parent["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": parent["Ariba Supplier Name"]
                })
                added_contracts.add(parent["Original Name"])

                # Get all children (any contract mentioning this parent in Supplier Parent Child Link)
                children = group[group["Supplier Parent Child Link"].str.contains(parent["Original Name"], na=False)]
                # Sort children by original order
                children = children.reset_index(drop=True)

                for _, child in children.iterrows():
                    if child["Original Name"] in added_contracts:
                        continue

                    # Check if this child itself has children
                    subchildren = group[group["Supplier Parent Child Link"].str.contains(child["Original Name"], na=False)]
                    relation_type = "Child/Parent" if not subchildren.empty else "Child"

                    output_rows.append({
                        "FileName": child["Original Name"],
                        "ContractID": child["ID"],
                        "Parent_Child": relation_type,
                        "ContractType": child["Contract Type"],
                        "PartyName": child["Supplier Legal Entity (Contracts)"],
                        "Ariba Supplier Name": child["Ariba Supplier Name"]
                    })
                    added_contracts.add(child["Original Name"])

                    # Add subchildren
                    for _, sub in subchildren.iterrows():
                        if sub["Original Name"] in added_contracts:
                            continue
                        output_rows.append({
                            "FileName": sub["Original Name"],
                            "ContractID": sub["ID"],
                            "Parent_Child": "Subchild",
                            "ContractType": sub["Contract Type"],
                            "PartyName": sub["Supplier Legal Entity (Contracts)"],
                            "Ariba Supplier Name": sub["Ariba Supplier Name"]
                        })
                        added_contracts.add(sub["Original Name"])

            # Handle orphan contracts (not linked to any Parent)
            orphans = group[~group["Original Name"].isin(added_contracts)]
            for _, orphan in orphans.iterrows():
                output_rows.append({
                    "FileName": orphan["Original Name"],
                    "ContractID": orphan["ID"],
                    "Parent_Child": "Child",  # Direct child of supplier Parent
                    "ContractType": orphan["Contract Type"],
                    "PartyName": orphan["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": orphan["Ariba Supplier Name"]
                })
                added_contracts.add(orphan["Original Name"])

        # Final output
        output_df = pd.DataFrame(output_rows)

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
