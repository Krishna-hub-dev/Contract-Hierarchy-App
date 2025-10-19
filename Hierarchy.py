import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")

st.title("📁 Contract Hierarchy Generator")
st.write("Upload your Excel file to automatically generate a master–child contract hierarchy and export it.")

# Expected columns
required_columns = [
    "Original Name",
    "ID",
    "Parent_Child",
    "Contract Type",
    "Supplier Legal Entity (Contracts)",
    "Ariba Supplier Name",
    "Workspace ID",
    "Supplier Parent Child agreement links",
    "Effective Date",
    "Expiration Date"
]

uploaded_file = st.file_uploader("📤 Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        # Check required columns
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            st.error(f"⚠️ Missing columns in Excel: {', '.join(missing)}")
        else:
            st.success("✅ All required columns found!")

            # --- Build hierarchy structure ---
            st.subheader("📊 Generated Contract Hierarchy")

            # Step 1: Create relationship mappings
            df["Parent_Child_Link"] = df["Supplier Parent Child agreement links"].astype(str)

            output_rows = []

            for _, row in df.iterrows():
                contract_id = str(row["ID"])
                parent_link = row["Parent_Child_Link"]

                # Determine relationship type
                if parent_link == "" or parent_link.lower() in ["nan", "none"]:
                    relation_type = "Parent"
                else:
                    # Check if this contract ID appears in other rows' links (means it's a parent too)
                    is_parent_for_others = df["Supplier Parent Child agreement links"].astype(str).str.contains(contract_id).any()

                    if is_parent_for_others:
                        relation_type = "Child/Parent"
                    else:
                        # Check if its parent has a parent (nested)
                        parent_of_parent = df[df["ID"].astype(str) == parent_link]
                        if not parent_of_parent.empty:
                            grandparent_link = parent_of_parent.iloc[0]["Supplier Parent Child agreement links"]
                            if pd.notna(grandparent_link) and grandparent_link != "":
                                relation_type = "Sub Child"
                            else:
                                relation_type = "Child"
                        else:
                            relation_type = "Child"

                # Add to output
                output_rows.append({
                    "FileName": row["Original Name"],
                    "ContractID": row["ID"],
                    "Parent_Child": relation_type,
                    "ContractType": row["Contract Type"],
                    "PartyName": row["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": row["Ariba Supplier Name"],
                    "Workspace ID": row["Workspace ID"]
                })

            output_df = pd.DataFrame(output_rows)

            st.write("### 🧾 Final Output Preview")
            st.dataframe(output_df)

            # Download section
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
        st.error(f"❌ Error while processing the file: {e}")

else:
    st.info("👆 Please upload your Excel file to begin.")
