import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Contract Hierarchy Builder", layout="wide")

st.title("📄 Contract Hierarchy Builder")
st.write("Upload your Excel file to generate the MSA → SOW → Addendum → Amendment hierarchy")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.write("### Preview of Uploaded Data", df.head())

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

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
    else:
        st.success("✅ All required columns found!")

        results = []
        for supplier, group in df.groupby("Supplier Legal Entity"):
            group = group.sort_values("Effective Date")

            msa_rows = group[group["File Name"].str.contains("MSA", case=False, na=False)]
            for _, msa in msa_rows.iterrows():
                msa_id = msa["Contract ID"]

                amendments = group[group["Supplier Parent Child Relation"].astype(str).str.contains(str(msa_id), na=False) &
                                   group["File Name"].str.contains("Amendment", case=False, na=False)]

                sows = group[group["Supplier Parent Child Relation"].astype(str).str.contains(str(msa_id), na=False) &
                             group["File Name"].str.contains("SOW", case=False, na=False)]

                for _, sow in sows.iterrows():
                    sow_id = sow["Contract ID"]
                    addendums = group[group["Supplier Parent Child Relation"].astype(str).str.contains(str(sow_id), na=False) &
                                      group["File Name"].str.contains("Addendum", case=False, na=False)]

                    results.append({
                        "Supplier Legal Entity": supplier,
                        "Parent Contract (MSA)": msa_id,
                        "Child Contract (SOW)": sow_id,
                        "Sub Child (Addendum)": ", ".join(addendums["Contract ID"].astype(str)),
                        "Amendment(s)": ", ".join(amendments["Contract ID"].astype(str)),
                        "Hierarchy": "MSA → SOW → Addendum + Amendment"
                    })

        if results:
            result_df = pd.DataFrame(results)
            st.write("### 🧾 Contract Hierarchy Output", result_df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                result_df.to_excel(writer, index=False)
            st.download_button(
                label="⬇️ Download Hierarchy Excel",
                data=output.getvalue(),
                file_name="Contract_Hierarchy_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No hierarchy found. Please check your file content.")
