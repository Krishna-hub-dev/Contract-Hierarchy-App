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

            output_rows = []

            def build_hierarchy(parent_id, parent_type="Parent"):
                """Recursive function to build Parent → Child → Sub Child hierarchy."""
                children = df[df["Parent_Child"] == parent_id]

                for _, row in children.iterrows():
                    output_rows.append({
                        "FileName": row["Original Name"],
                        "ContractID": row["ID"],
                        "Parent_Child": parent_type,
                        "ContractType": row["Contract Type"],
                        "PartyName": row["Supplier Legal Entity (Contracts)"],
                        "Ariba Supplier Name": row["Ariba Supplier Name"],
                        "Workspace ID": row["Workspace ID"]
                    })

                    # Find sub-children of this contract
                    build_hierarchy(row["ID"], "Sub Child")

            # Identify top-level parents (where Parent_Child is empty or NaN)
            top_level_contracts = df[df["Parent_Child"].isna() | (df["Parent_Child"] == "")]
            for _, row in top_level_contracts.iterrows():
                output_rows.append({
                    "FileName": row["Original Name"],
                    "ContractID": row["ID"],
                    "Parent_Child": "Parent",
                    "ContractType": row["Contract Type"],
                    "PartyName": row["Supplier Legal Entity (Contracts)"],
                    "Ariba Supplier Name": row["Ariba Supplier Name"],
                    "Workspace ID": row["Workspace ID"]
                })
                # Build hierarchy for its children
                build_hierarchy(row["ID"], "Child")

            # Create final DataFrame
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
