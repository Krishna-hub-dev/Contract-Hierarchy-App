import pandas as pd
import streamlit as st

st.title("Contract Hierarchy Generator")

# Upload file
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "csv"])

if uploaded_file:
    # Read the file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Ensure required columns exist
    required_cols = ['FileName','ContractID','ContractType','PartyName','Ariba Supplier Name','Workspace ID','Supplier Parent Child agreement links','Effective Date']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Missing columns in input: {missing_cols}")
    else:
        # Initialize Parent_Child column
        df['Parent_Child'] = ''

        # Step 1: Identify MSA as Parent
        df.loc[df['ContractType'].str.contains('MSA|Service Agreement|Technology Agreement|Product and service Agreement', case=False, na=False), 'Parent_Child'] = 'Parent'

        # Step 2: Identify Child / Child-Parent / Subchild
        parent_rows = df[df['Parent_Child'] == 'Parent']

        for idx, parent in parent_rows.iterrows():
            parent_name = parent['FileName']
            parent_effective = str(parent['Effective Date'])
            parent_workspace = parent['Workspace ID']

            # All rows that mention this parent in Supplier Parent Child agreement links
            children_mask = df['Supplier Parent Child agreement links'].str.contains(parent_effective, na=False) | df['Supplier Parent Child agreement links'].str.contains(parent_name, na=False)
            children_mask &= df['Parent_Child'] == ''
            df.loc[children_mask, 'Parent_Child'] = 'Child'

        # Step 3: Identify Subchilds (those referencing a Child)
        child_rows = df[df['Parent_Child'] == 'Child']
        for idx, child in child_rows.iterrows():
            child_name = child['FileName']
            child_effective = str(child['Effective Date'])
            child_workspace = child['Workspace ID']

            subchild_mask = df['Supplier Parent Child agreement links'].str.contains(child_name, na=False) | df['Supplier Parent Child agreement links'].str.contains(child_effective, na=False)
            subchild_mask &= df['Parent_Child'] == ''
            df.loc[subchild_mask, 'Parent_Child'] = 'Sub Child'
            # Mark the parent of subchild as Child/Parent
            df.loc[idx, 'Parent_Child'] = 'Child/Parent'

        # Step 4: Maintain order: Parent first, then Child, Child/Parent, Subchild
        hierarchy_order = ['Parent', 'Child', 'Child/Parent', 'Sub Child']
        df['Hierarchy_Order'] = df['Parent_Child'].apply(lambda x: hierarchy_order.index(x) if x in hierarchy_order else 99)
        df.sort_values(by=['Hierarchy_Order', 'Effective Date'], inplace=True)

        # Step 5: Select output columns
        output_cols = ['FileName','ContractID','Parent_Child','ContractType','PartyName','Ariba Supplier Name','Workspace ID']
        df_output = df[output_cols]

        # Display output
        st.dataframe(df_output)

        # Download option
        output_file = "contract_hierarchy_output.xlsx"
        df_output.to_excel(output_file, index=False)
        st.download_button("Download Excel", data=open(output_file, "rb"), file_name=output_file)
