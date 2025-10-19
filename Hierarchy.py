import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Generalized Contract Hierarchy Builder", layout="wide")
st.title("📁 Generalized Contract Hierarchy Generator")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Normalize columns
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()

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
            
            # Step 2: Identify Parentable Contracts (TOs, SOWs, etc.)
            parentable_contracts = group[~group["Contract Type"].str.contains("MSA", case=False, na=False)]
            
            # Track all processed sub-child IDs to avoid duplication
            processed_subchild_ids = set()
            
            for _, contract in parentable_contracts.iterrows():
                
                # Step 2a: Find related subcontracts using name prefix
                base_prefix = re.sub(r"-(CO|AM|AMD|SOW).*", "", contract["Original Name"], flags=re.IGNORECASE)
                
                related_subs = group[
                    group["ID"] != contract["ID"]  # Exclude self
                    & group["Original Name"].str.startswith(base_prefix)
                    & ~group["ID"].isin(processed_subchild_ids)
                    & group["Contract Type"].str.contains("Change|Amend|CO|AMD|SOW", case=False, na=False)
                ]
                
                # Step 2b: Check metadata parent-child info
                # If there is info linking this contract as a parent, we treat as Child/Parent
                metadata_linked_subs = group[
                    group["Supplier Parent Child Link Info"].astype(str).str.contains(contract["Original Name"], case=False, na=False)
                    & ~group["ID"].isin(processed_subchild_ids)
                ]
                
                # Combine both sources
                total_subs = pd.concat([related_subs, metadata_linked_subs]).drop_duplicates("ID")
                
                relation_type = "Child/Parent" if not total_subs.empty else "Child"
                
                # Add the parentable contract
                output_rows.append({
                    "FileName": contract["Original Name"],
                    "ContractID": contract["ID"],
                    "Parent_Child": relation_type,
                    "ContractType": contract["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": contract["Ariba Supplier Name"]
                })
                
                # Step 3: Add Sub Child contracts
                for _, sub in total_subs.iterrows():
                    output_rows.append({
                        "FileName": sub["Original Name"],
                        "ContractID": sub["ID"],
                        "Parent_Child": "Sub Child",
                        "ContractType": sub["Contract Type"],
                        "PartyName": supplier,
                        "Ariba Supplier Name": sub["Ariba Supplier Name"]
                    })
                    processed_subchild_ids.add(sub["ID"])
            
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
