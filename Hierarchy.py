import streamlit as st
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")
st.title("📁 Contract Hierarchy Generator by Effective Date Logic")

st.write("Upload your Excel file to generate Parent–Child–Subchild relationships automatically using Effective Date logic.")

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        # Ensure date column is in datetime format
        df["Effective Date"] = pd.to_datetime(df["Effective Date"], errors="coerce")

        # Remove rows without effective date or supplier
        df = df.dropna(subset=["Effective Date", "Supplier Legal Entity (Contracts)"])

        output_rows = []

        # Loop by supplier
        for supplier, group in df.groupby("Supplier Legal Entity (Contracts)"):
            group = group.sort_values(by="Effective Date")

            # Get earliest (MSA) as parent
            if not group.empty:
                parent_row = group.iloc[0]
                parent_id = parent_row["ID"]
                parent_date = parent_row["Effective Date"]

                output_rows.append({
                    "FileName": parent_row["Original Name"],
                    "ContractID": parent_row["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": parent_row["Contract Type"],
                    "PartyName": parent_row["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": parent_row["Ariba Supplier Name"],
                    "Workspace ID": parent_row["Workspace ID"],
                    "Effective Date": parent_row["Effective Date"].date()
                })

                # Find Task Orders (children)
                for _, child_row in group.iloc[1:].iterrows():
                    child_date = child_row["Effective Date"]

                    # Check if child references parent's date (via link text or equal date)
                    ref_text = str(child_row.get("Supplier Parent Child agreement links", ""))
                    if str(parent_date.date()) in ref_text or abs((child_date - parent_date).days) > 0:
                        relation_type = "Child/Parent" if "Task Order" in str(child_row["Contract Type"]) else "Child"

                        output_rows.append({
                            "FileName": child_row["Original Name"],
                            "ContractID": child_row["ID"],
                            "Parent_Child": relation_type,
                            "ContractType": child_row["Contract Type"],
                            "PartyName": child_row["Supplier Legal Entity (Contracts)"],
                            "Ariba Supplier Name": child_row["Ariba Supplier Name"],
                            "Workspace ID": child_row["Workspace ID"],
                            "Effective Date": child_row["Effective Date"].date()
                        })

                        # Now find subchilds (Change Orders) for this Task Order
                        subchildren = group[
                            (group["Effective Date"] > child_row["Effective Date"]) &
                            (group["Contract Type"].str.contains("Change", case=False, na=False))
                        ]
                        for _, sub in subchildren.iterrows():
                            sub_ref_text = str(sub.get("Supplier Parent Child agreement links", ""))
                            if str(child_row["Effective Date"].date()) in sub_ref_text:
                                output_rows.append({
                                    "FileName": sub["Original Name"],
                                    "ContractID": sub["ID"],
                                    "Parent_Child": "Sub Child",
                                    "ContractType": sub["Contract Type"],
                                    "PartyName": sub["Supplier Legal Entity (Contracts)"],
                                    "Ariba Supplier Name": sub["Ariba Supplier Name"],
                                    "Workspace ID": sub["Workspace ID"],
                                    "Effective Date": sub["Effective Date"].date()
                                })

        output_df = pd.DataFrame(output_rows)
        st.write("### 🧾 Generated Hierarchy Result")
        st.dataframe(output_df)

        # Download Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            output_df.to_excel(writer, index=False, sheet_name="Contract_Hierarchy")
        buffer.seek(0)

        st.download_button(
            label="📥 Download Hierarchy Excel",
            data=buffer,
            file_name="Contract_Hierarchy_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Error while processing file: {e}")
else:
    st.info("👆 Please upload your Excel file to begin.")
