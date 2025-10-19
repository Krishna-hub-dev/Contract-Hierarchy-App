import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder – Correct Subchild Logic", layout="wide")
st.title("📁 Contract Hierarchy Builder – Parent/Child/Subchild Logic")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Standardize columns
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()
        if "Supplier Parent Child Link Info" not in df.columns:
            df["Supplier Parent Child Link Info"] = ""

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Process each supplier separately
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):
            group = group.reset_index(drop=True)

            # Build name -> row map
            name_to_row = {row["Original Name"].strip(): row for idx, row in group.iterrows()}

            # Build reference maps
            # referenced_by_map: contract_name -> list of contracts referencing it
            referenced_by_map = {}
            # references_map: contract_name -> list of contracts it references
            references_map = {}

            for idx, row in group.iterrows():
                name = row["Original Name"].strip()
                link_info = str(row.get("Supplier Parent Child Link Info", "")).upper()
                references = [l.strip() for l in link_info.split(';') if l.strip()]
                references_map[name] = references
                for ref in references:
                    referenced_by_map.setdefault(ref, []).append(name)

            # Identify Parents (MSA, Service Agreement, Technology Agreement, Product & Service Agreement)
            parent_mask = group["Contract Type"].str.contains(
                "MSA|Service Agreement|Technology Agreement|Product and Service Agreement", case=False, na=False)
            parents = [row["Original Name"].strip() for idx, row in group[parent_mask].iterrows()]

            added_contracts = set()

            # Recursive function to traverse hierarchy
            def traverse(contract_name, hierarchy_type):
                if contract_name in added_contracts:
                    return
                row = name_to_row[contract_name]
                output_rows.append({
                    "FileName": contract_name,
                    "ContractID": row["ID"],
                    "Parent_Child": hierarchy_type,
                    "ContractType": row["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": row.get("Ariba Supplier Name", "")
                })
                added_contracts.add(contract_name)

                # Determine children
                for child_name in referenced_by_map.get(contract_name, []):
                    # Child/Parent if it has its own children
                    if referenced_by_map.get(child_name):
                        traverse(child_name, "Child/Parent")
                    else:
                        # Subchild if it references a Child/Parent
                        refs = references_map.get(child_name, [])
                        if any(r in referenced_by_map for r in refs):
                            traverse(child_name, "Subchild")
                        else:
                            traverse(child_name, "Child")

            # First, traverse all Parents
            for p in parents:
                traverse(p, "Parent")

            # Then, traverse remaining contracts not yet added
            for idx, row in group.iterrows():
                name = row["Original Name"].strip()
                if name not in added_contracts:
                    # Determine type
                    if referenced_by_map.get(name):
                        traverse(name, "Child/Parent")
                    elif any(r in referenced_by_map for r in references_map.get(name, [])):
                        traverse(name, "Subchild")
                    else:
                        traverse(name, "Child")

        # Convert output to DataFrame
        output_df = pd.DataFrame(output_rows)

        st.subheader("📊 Generated Contract Hierarchy (Parent → Child → Child/Parent → Subchild)")
        st.dataframe(output_df)

        # Excel download
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
