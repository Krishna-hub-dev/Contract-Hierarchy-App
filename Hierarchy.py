import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Nested Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Generator – Nested & Sequenced")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Normalize columns
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()
        if "Supplier Parent Child Link Info" not in df.columns:
            df["Supplier Parent Child Link Info"] = ""

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Group by supplier
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):
            
            # Step 1: Identify MSA (Parent)
            msa_rows = group[group["Contract Type"].str.contains("MSA", case=False, na=False)]
            msa = None
            if not msa_rows.empty:
                msa = msa_rows.iloc[0]
                output_rows.append({
                    "FileName": msa["Original Name"],
                    "ContractID": msa["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": msa["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": msa["Ariba Supplier Name"]
                })

            # Step 2: Identify non-MSA contracts
            non_msa_contracts = group[~group["Contract Type"].str.contains("MSA", case=False, na=False)]
            processed_ids = set()

            # Helper to get subchildren for a parent contract
            def get_subchildren(contract_row):
                safe_name = re.escape(contract_row["Original Name"])
                
                # Find subchildren by prefix or metadata link
                mask_prefix = (
                    (group["ID"] != contract_row["ID"]) &
                    (~group["ID"].isin(processed_ids)) &
                    (group["Original Name"].str.startswith(contract_row["Original Name"].split("-")[0])) &
                    (group["Contract Type"].str.contains("Change|Amend|CO|AMD|SOW", case=False, na=False))
                )
                mask_metadata = (
                    (~group["ID"].isin(processed_ids)) &
                    group["Supplier Parent Child Link Info"].astype(str).str.contains(safe_name, case=False, na=False)
                )
                subchildren = pd.concat([group[mask_prefix], group[mask_metadata]]).drop_duplicates("ID")
                return subchildren

            # Step 3: Build hierarchy
            for _, contract in non_msa_contracts.iterrows():
                if contract["ID"] in processed_ids:
                    continue

                subchildren = get_subchildren(contract)
                relation_type = "Child/Parent" if not subchildren.empty else "Child"

                # Add main contract
                output_rows.append({
                    "FileName": contract["Original Name"],
                    "ContractID": contract["ID"],
                    "Parent_Child": relation_type,
                    "ContractType": contract["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": contract["Ariba Supplier Name"]
                })
                processed_ids.add(contract["ID"])

                # Add subchildren immediately below
                for _, sub in subchildren.iterrows():
                    output_rows.append({
                        "FileName": sub["Original Name"],
                        "ContractID": sub["ID"],
                        "Parent_Child": "Sub Child",
                        "ContractType": sub["Contract Type"],
                        "PartyName": supplier,
                        "Ariba Supplier Name": sub["Ariba Supplier Name"]
                    })
                    processed_ids.add(sub["ID"])

            # Step 4: Handle orphan contracts (not yet processed)
            remaining = group[~group["ID"].isin([row["ContractID"] for row in output_rows])]
            for _, orphan in remaining.iterrows():
                output_rows.append({
                    "FileName": orphan["Original Name"],
                    "ContractID": orphan["ID"],
                    "Parent_Child": "Child" if msa is not None else "Parent",
                    "ContractType": orphan["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": orphan["Ariba Supplier Name"]
                })

        # Create output DataFrame
        output_df = pd.DataFrame(output_rows)

        st.subheader("📊 Generated Contract Hierarchy (Nested & Sequenced)")
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
