import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder – Tree Logic", layout="wide")
st.title("📁 Contract Hierarchy Builder – Parent/Child/Subchild Tree")

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

            # Build lookup dictionaries
            name_to_row = {row["Original Name"].strip(): row for idx, row in group.iterrows()}

            # Build parent-child mapping using Supplier Parent Child Link Info
            tree_map = {}  # parent_name -> list of child names
            referenced_by_map = {}  # contract_name -> list of contracts referencing it

            for idx, row in group.iterrows():
                name = row["Original Name"].strip()
                link_info = str(row.get("Supplier Parent Child Link Info", "")).upper()
                if link_info:
                    for ref in link_info.split(';'):
                        ref = ref.strip()
                        if not ref:
                            continue
                        tree_map.setdefault(ref, []).append(name)
                        referenced_by_map.setdefault(name, []).append(ref)

            # Identify Parent contracts (MSA, Service Agreement, Technology Agreement, Product & Service Agreement)
            parent_mask = group["Contract Type"].str.contains(
                "MSA|Service Agreement|Technology Agreement|Product and Service Agreement", case=False, na=False)
            parents = [row["Original Name"].strip() for idx, row in group[parent_mask].iterrows()]

            # Recursive function to traverse hierarchy
            def traverse(contract_name, hierarchy_type):
                row = name_to_row[contract_name]
                output_rows.append({
                    "FileName": contract_name,
                    "ContractID": row["ID"],
                    "Parent_Child": hierarchy_type,
                    "ContractType": row["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": row.get("Ariba Supplier Name", "")
                })
                # Process children
                children = tree_map.get(contract_name, [])
                for child_name in children:
                    # Determine child type
                    if child_name in tree_map:  # this child has its own children → Child/Parent
                        traverse(child_name, "Child/Parent")
                    else:
                        # Check if child references any Child/Parent to become Subchild
                        links = referenced_by_map.get(child_name, [])
                        if any(l in tree_map for l in links):
                            traverse(child_name, "Subchild")
                        else:
                            traverse(child_name, "Child")

            # Traverse all Parent contracts first
            for p in parents:
                traverse(p, "Parent")

            # Add remaining contracts not linked anywhere (orphans)
            all_added = set([row["FileName"] for row in output_rows])
            for idx, row in group.iterrows():
                name = row["Original Name"].strip()
                if name not in all_added:
                    traverse(name, "Child")

        # Convert output to DataFrame
        output_df = pd.DataFrame(output_rows)

        st.subheader("📊 Generated Contract Hierarchy (Tree Order)")
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
