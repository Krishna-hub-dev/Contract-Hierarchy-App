import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Generator – MSA, Task Order & Change Agreement Logic")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Normalize text
        df.columns = df.columns.str.strip()
        df["Contract Type"] = df["Contract Type"].astype(str)
        df["Original Name"] = df["Original Name"].astype(str)

        # Clean supplier names
        df["Supplier Legal Entity (Contracts)"] = df["Supplier Legal Entity (Contracts)"].str.strip().str.upper()

        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        output_rows = []

        # Process by supplier
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):

            # Find Parent (MSA)
            msa_rows = group[group["Contract Type"].str.contains("MSA", case=False, na=False)]
            if not msa_rows.empty:
                msa = msa_rows.iloc[0]  # Assuming 1 MSA per supplier
                msa_prefix = re.sub(r"[-_].*", "", msa["Original Name"])

                output_rows.append({
                    "FileName": msa["Original Name"],
                    "ContractID": msa["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": msa["Contract Type"],
                    "PartyName": msa["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": msa["Ariba Supplier Name"]
                })
            else:
                msa = None
                msa_prefix = ""

            # Identify Task Orders
            task_orders = group[group["Contract Type"].str.contains("Task Order|SOW", case=False, na=False)]

            for _, task in task_orders.iterrows():
                # Find related Change Agreements
                base_prefix = re.sub(r"[-_](CO|AM|AMD).*", "", task["Original Name"], flags=re.IGNORECASE)
                related_changes = group[
                    group["Contract Type"].str.contains("Change|Amend", case=False, na=False)
                    & group["Original Name"].str.contains(base_prefix.split('-')[0], case=False, na=False)
                ]

                relation_type = "Child/Parent" if not related_changes.empty else "Child"

                output_rows.append({
                    "FileName": task["Original Name"],
                    "ContractID": task["ID"],
                    "Parent_Child": relation_type,
                    "ContractType": task["Contract Type"],
                    "PartyName": task["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": task["Ariba Supplier Name"]
                })

                # Add Change Agreements (Sub Child)
                for _, change in related_changes.iterrows():
                    output_rows.append({
                        "FileName": change["Original Name"],
                        "ContractID": change["ID"],
                        "Parent_Child": "Sub Child",
                        "ContractType": change["Contract Type"],
                        "PartyName": change["Supplier Legal Entity (Contracts)"],
                        "Ariba Supplier Name": change["Ariba Supplier Name"]
                    })

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
