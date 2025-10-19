import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Builder – Two-Pass Accurate Hierarchy")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Standardize columns and text
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
            group = group.reset_index(drop=True)

            # Step 1: Build a reference map from 'Supplier Parent Child Link Info'
            # key = contract name, value = list of contracts that reference it
            reference_map = {}
            name_to_row = {}

            for idx, row in group.iterrows():
                contract_name = row["Original Name"].strip()
                name_to_row[contract_name] = row
                link_info = str(row.get("Supplier Parent Child Link Info", "")).upper()
                if link_info:
                    for ref_name in link_info.split(';'):  # assume multiple references separated by ';'
                        ref_name = ref_name.strip()
                        if ref_name:
                            reference_map.setdefault(ref_name, []).append(contract_name)

            # Step 2: Identify Parent contracts (MSA, Service Agreements, Technology Agreements, Product & Service Agreements)
            parent_mask = group["Contract Type"].str.contains(
                "MSA|Service Agreement|Technology Agreement|Product and Service Agreement", case=False, na=False)
            parents = [row["Original Name"] for idx, row in group[parent_mask].iterrows()]

            # Step 3: Assign hierarchy types
            hierarchy = {}

            # Assign Parent contracts first
            for p in parents:
                hierarchy[p] = "Parent"

            # Assign Child/Subchild/Child-Parent based on references
            for idx, row in group.iterrows():
                contract_name = row["Original Name"].strip()
                if contract_name in hierarchy:
                    continue  # already assigned as Parent

                # Check if this contract references a Parent or Child/Parent
                link_info = str(row.get("Supplier Parent Child Link Info", "")).upper()
                linked_parents = [name for name in parents if name.upper() in link_info]

                # Determine type
                if linked_parents:
                    hierarchy[contract_name] = "Child"
                else:
                    # Check if other contracts reference this one
                    referenced_by = reference_map.get(contract_name, [])
                    if referenced_by:
                        hierarchy[contract_name] = "Child/Parent"
                    else:
                        hierarchy[contract_name] = "Child"

            # Step 4: Adjust Subchilds: any contract that references a Child/Parent becomes Subchild
            for idx, row in group.iterrows():
                contract_name = row["Original Name"].strip()
                if hierarchy[contract_name] == "Child":
                    # Check if it references a Child/Parent
                    link_info = str(row.get("Supplier Parent Child Link Info", "")).upper()
                    child_parent_names = [n for n, t in hierarchy.items() if t == "Child/Parent"]
                    if any(cp.upper() in link_info for cp in child_parent_names):
                        hierarchy[contract_name] = "Subchild"

            # Step 5: Build output rows maintaining original order
            for idx, row in group.iterrows():
                contract_name = row["Original Name"].strip()
                output_rows.append({
                    "FileName": contract_name,
                    "ContractID": row["ID"],
                    "Parent_Child": hierarchy[contract_name],
                    "ContractType": row["Contract Type"],
                    "PartyName": supplier,
                    "Ariba Supplier Name": row.get("Ariba Supplier Name", "")
                })

        # Step 6: Convert to DataFrame
        output_df = pd.DataFrame(output_rows)

        st.subheader("📊 Generated Contract Hierarchy (Ordered & Nested)")
        st.dataframe(output_df)

        # Step 7: Excel Download
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
