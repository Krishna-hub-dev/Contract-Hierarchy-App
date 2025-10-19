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
