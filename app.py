import pandas as pd
import streamlit as st
from datetime import datetime
import io

st.set_page_config(
    page_title="Credit Card Statement Allocator", 
    page_icon="💳", 
    layout="wide"
)

st.title("💳 Credit Card Statement Allocator")
st.markdown("Allocate credit card transactions across multiple entities with built-in validation")

# Define the 6 entities
ENTITIES = [
    "Panola Holdings LLC",
    "Robert Dow (Personal)", 
    "RLV22 LLC",
    "CSD Van Zandt LLC",
    "Goodfire Realty LLC",
    "NDRE III LLC"
]

def detect_amount_column(df):
    """Detect the amount column from common variations"""
    possible_amount_columns = [
        'Amount', 'amount', 'AMOUNT',
        'Transaction Amount', 'Trans Amount', 'Trans. Amount',
        'Debit', 'Credit', 'Balance', 'Value',
        'Purchase Amount', 'Charge Amount'
    ]
    
    for col in possible_amount_columns:
        if col in df.columns:
            return col
    
    # Look for columns with numeric data that might be amounts
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64'] or col.lower().find('amount') != -1:
            return col
    
    return None

def process_credit_card_data(df, amount_column):
    """Process the credit card data and add allocation columns"""
    
    # Create a copy to avoid modifying the original
    processed_df = df.copy()
    
    # Ensure the amount column is numeric
    try:
        processed_df[amount_column] = pd.to_numeric(processed_df[amount_column], errors='coerce')
        processed_df[amount_column] = processed_df[amount_column].fillna(0)
    except:
        st.warning(f"Could not convert {amount_column} to numeric. Using values as-is.")
    
    # Add allocation columns for each entity (initialized to 0)
    for entity in ENTITIES:
        processed_df[entity] = 0.0
    
    # DEFAULT ALLOCATION: All amounts go to Panola Holdings LLC
    processed_df['Panola Holdings LLC'] = processed_df[amount_column]
    
    # Add validation columns
    processed_df['Total_Allocated'] = processed_df[ENTITIES].sum(axis=1)
    processed_df['Allocation_Check'] = processed_df[amount_column] - processed_df['Total_Allocated']
    processed_df['Allocation_Status'] = processed_df['Allocation_Check'].apply(
        lambda x: '✅ Balanced' if abs(x) < 0.01 else f'❌ Off by ${x:.2f}'
    )
    
    return processed_df

def validate_allocations(df, amount_column):
    """Validate that all transactions are properly allocated"""
    
    validation_results = {}
    
    # Check for unallocated amounts
    unbalanced = df[abs(df['Allocation_Check']) >= 0.01]
    validation_results['unbalanced_count'] = len(unbalanced)
    validation_results['total_unallocated'] = unbalanced['Allocation_Check'].sum()
    
    # Entity totals
    entity_totals = {}
    for entity in ENTITIES:
        entity_totals[entity] = df[entity].sum()
    validation_results['entity_totals'] = entity_totals
    
    # Overall totals
    validation_results['total_transactions'] = df[amount_column].sum()
    validation_results['total_allocated'] = df['Total_Allocated'].sum()
    validation_results['grand_total_check'] = validation_results['total_transactions'] - validation_results['total_allocated']
    
    return validation_results

# File upload
uploaded_file = st.file_uploader("Upload your credit card statement CSV", type=['csv'])

if uploaded_file is not None:
    try:
        # Read the CSV file
        df = pd.read_csv(uploaded_file)
        
        st.subheader("📊 Original Data Preview")
        st.write(f"**Loaded:** {len(df):,} transactions")
        st.dataframe(df.head(10), use_container_width=True)
        
        # Detect amount column
        amount_column = detect_amount_column(df)
        
        if amount_column is None:
            st.error("❌ Could not detect an amount column. Please select manually:")
            amount_column = st.selectbox("Select the amount column:", df.columns.tolist())
            
            if st.button("Process with selected column"):
                st.rerun()
        else:
            st.success(f"✅ Detected amount column: **{amount_column}**")
        
        # Allow manual override of amount column
        with st.expander("🔧 Advanced: Manual Column Selection"):
            manual_amount_column = st.selectbox("Override amount column:", 
                                              ['Auto-detect'] + df.columns.tolist())
            if manual_amount_column != 'Auto-detect':
                amount_column = manual_amount_column
                st.info(f"Using manual selection: **{amount_column}**")
        
        if amount_column:
            # Process the data
            with st.spinner("Processing allocations..."):
                processed_df = process_credit_card_data(df, amount_column)
            
            st.success("✅ Processing complete! All transactions defaulted to Panola Holdings LLC")
            
            # Display processed data
            st.subheader("💰 Allocation Results")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Transactions", f"{len(processed_df):,}")
            
            with col2:
                total_amount = processed_df[amount_column].sum()
                st.metric("Total Amount", f"${total_amount:,.2f}")
            
            with col3:
                total_allocated = processed_df['Total_Allocated'].sum()
                st.metric("Total Allocated", f"${total_allocated:,.2f}")
            
            with col4:
                allocation_difference = total_amount - total_allocated
                st.metric("Allocation Check", f"${allocation_difference:,.2f}", 
                         delta_color="inverse" if abs(allocation_difference) > 0.01 else "normal")
            
            # Entity breakdown
            st.subheader("🏢 Entity Allocation Summary")
            entity_summary = []
            for entity in ENTITIES:
                entity_total = processed_df[entity].sum()
                entity_percentage = (entity_total / total_amount * 100) if total_amount != 0 else 0
                entity_summary.append({
                    'Entity': entity,
                    'Total Allocated': f"${entity_total:,.2f}",
                    'Percentage': f"{entity_percentage:.1f}%",
                    'Transaction Count': (processed_df[entity] != 0).sum()
                })
            
            st.dataframe(pd.DataFrame(entity_summary), use_container_width=True)
            
            # Display full allocation table
            st.subheader("📋 Full Allocation Table")
            
            # Reorder columns for better display - put amount column first, then entities, then validation
            amount_and_entity_columns = [amount_column] + ENTITIES + ['Total_Allocated', 'Allocation_Check', 'Allocation_Status']
            other_columns = [col for col in processed_df.columns if col not in amount_and_entity_columns]
            display_columns = other_columns + amount_and_entity_columns
            
            st.dataframe(processed_df[display_columns], use_container_width=True)
            
            # Show unbalanced transactions if any
            unbalanced = processed_df[abs(processed_df['Allocation_Check']) >= 0.01]
            if len(unbalanced) > 0:
                st.subheader("⚠️ Unbalanced Transactions")
                st.dataframe(unbalanced[display_columns], use_container_width=True)
            
            # Validation results
            validation = validate_allocations(processed_df, amount_column)
            
            st.subheader("✅ Validation Summary")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if validation['unbalanced_count'] == 0:
                    st.success(f"🎉 All {len(processed_df):,} transactions are properly allocated!")
                else:
                    st.warning(f"⚠️ {validation['unbalanced_count']} transactions need allocation review")
                
                st.metric("Grand Total Check", f"${validation['grand_total_check']:.2f}")
            
            with col2:
                st.write("**Entity Totals:**")
                for entity, total in validation['entity_totals'].items():
                    st.write(f"• {entity}: ${total:,.2f}")
            
            # Download section
            st.subheader("📥 Download Processed File")
            
            # Create Excel file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main allocation sheet
                processed_df.to_excel(writer, sheet_name='Allocations', index=False)
                
                # Summary sheet
                summary_df = pd.DataFrame([
                    {'Metric': 'Total Transactions', 'Value': len(processed_df)},
                    {'Metric': 'Total Amount', 'Value': f"${total_amount:,.2f}"},
                    {'Metric': 'Total Allocated', 'Value': f"${total_allocated:,.2f}"},
                    {'Metric': 'Allocation Check', 'Value': f"${allocation_difference:.2f}"},
                    {'Metric': 'Unbalanced Transactions', 'Value': validation['unbalanced_count']},
                    {'Metric': 'Amount Column Used', 'Value': amount_column}
                ])
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Entity totals sheet
                entity_df = pd.DataFrame([
                    {'Entity': entity, 'Total': total} 
                    for entity, total in validation['entity_totals'].items()
                ])
                entity_df.to_excel(writer, sheet_name='Entity_Totals', index=False)
            
            output.seek(0)
            
            # Generate filename
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"credit_card_allocations_{current_time}.xlsx"
            
            st.download_button(
                label=f"📄 Download {filename}",
                data=output.getvalue(),
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.write("**Debugging info:**")
        st.write(f"- File name: {uploaded_file.name}")
        st.write(f"- File size: {uploaded_file.size} bytes")
        
        # Try to show column info
        try:
            df_debug = pd.read_csv(uploaded_file)
            st.write(f"- Columns found: {list(df_debug.columns)}")
            st.write(f"- Data types: {dict(df_debug.dtypes)}")
        except:
            st.write("- Could not read file for debugging")

else:
    st.info("👆 Upload your credit card statement CSV to begin allocation")
    
    # Sample format guide
    st.markdown("""
    ### 📋 Flexible CSV Format:
    This tool automatically detects amount columns from common variations:
    - **Amount**, **Transaction Amount**, **Debit**, **Credit**
    - Or any numeric column that might contain transaction amounts
    
    Your CSV can contain any columns - the tool will:
    1. Auto-detect the amount column
    2. Allow manual override if needed
    3. Preserve all original data
    
    ### 🏢 Entity Allocation:
    The tool will create allocation columns for:
    - **Panola Holdings LLC** *(default allocation - all transactions start here)*
    - Robert Dow (Personal)
    - RLV22 LLC
    - CSD Van Zandt LLC  
    - Goodfire Realty LLC
    - NDRE III LLC
    
    ### ✅ Built-in Validation:
    - Automatic allocation verification
    - Check totals to ensure 100% allocation
    - Balance validation for each transaction
    - Highlights any unbalanced transactions
    
    ### 📊 Excel Output:
    - **Allocations Sheet:** Full data with entity columns
    - **Summary Sheet:** Metrics and validation results
    - **Entity_Totals Sheet:** Breakdown by entity
    """)
