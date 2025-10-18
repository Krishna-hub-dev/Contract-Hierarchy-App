import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")

st.title("📁 Contract Hierarchy Generator")
st.write("Upload your Excel file to automatically generate a master–child contract hierarchy.")

# Expected columns based on your format
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

uploaded_file = st.file_uploader("Upload Contract Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.subheader("✅ Uploaded Data Preview")
        st.dataframe(df.head())

        # Check for required columns
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            st.error(f"Missing columns in Excel: {', '.join(missing)}")
        else:
            st.success("All required columns found ✔️")

            # Build hierarchy
            st.subheader("📊 Generated Contract Hierarchy")

            # Create hierarchy representation
            hierarchy_data = []

            def build_hierarchy(parent_id, level=0):
                children = df[df["Parent_Child"] == parent_id]
                for _, row in children.iterrows():
                    hierarchy_data.append({
                        "Level": level + 1,
                        "Contract ID": row["ID"],
                        "Contract Type": row["Contract Type"],
                        "Supplier": row["Supplier Legal Entity (Contracts)"],
                        "Workspace ID": row["Workspace ID"],
                        "Parent": parent_id
                    })
                    # Recursive call to find deeper levels
                    build_hierarchy(row["ID"], level + 1)

            # Identify top-level (no parent)
            top_level = df[df["Parent_Child"].isna() | (df["Parent_Child"] == "")]
            for _, row in top_level.iterrows():
                hierarchy_data.append({
                    "Level": 0,
                    "Contract ID": row["ID"],
                    "Contract Type": row["Contract Type"],
                    "Supplier": row["Supplier Legal Entity (Contracts)"],
                    "Workspace ID": row["Workspace ID"],
                    "Parent": None
                })
                build_hierarchy(row["ID"])

            hierarchy_df = pd.DataFrame(hierarchy_data)
            st.dataframe(hierarchy_df)

            # Download button
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                hierarchy_df.to_excel(writer, index=False, sheet_name='Hierarchy')
            buffer.seek(0)

            st.download_button(
                label="⬇️ Download Hierarchy Excel",
                data=buffer,
                file_name="Contract_Hierarchy_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
else:
    st.info("Please upload an Excel file to begin.")
