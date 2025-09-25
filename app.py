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

def process_credit_card_data(df):
    """Process the credit card data and add allocation columns"""
    
    # Create a copy to avoid modifying the original
    processed_df = df.copy()
    
    # Add allocation columns for each entity (initialized to 0)
    for entity in ENTITIES:
        processed_df[entity] = 0.0
    
    # DEFAULT ALLOCATION: All amounts go to Panola Holdings LLC
    if 'Amount' in processed_df.columns:
        processed_df['Panola Holdings LLC'] = processed_df['Amount']
    
    # Add validation columns
    processed_df['Total_Allocated'] = processed_df[ENTITIES].sum(axis=1)
    processed_df['Allocation_Check'] = processed_df['Amount'] - processed_df['Total_Allocated']
    processed_df['Allocation_Status'] = processed_df['Allocation_Check'].apply(
        lambda x: '✅ Balanced' if abs(x) < 0.01 else f'❌ Off by ${x:.2f}'
    )
    
    return processed_df

def validate_allocations(df):
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
    validation_results['total_transactions'] = df['Amount'].sum()
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
        
        # Check for required columns
        if 'Amount' not in df.columns:
            st.error("❌ 'Amount' column not found. Please ensure your CSV has an 'Amount' column.")
            st.stop()
        
        # Process the data
        with st.spinner("Processing allocations..."):
            processed_df = process_credit_card_data(df)
        
        st.success("✅ Processing complete! All transactions defaulted to Panola Holdings LLC")
        
        # Display processed data
        st.subheader("💰 Allocation Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Transactions", f"{len(processed_df):,}")
        
        with col2:
            total_amount = processed_df['Amount'].sum()
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
        
        # Reorder columns for better display
        display_columns = ['Trans. date', 'Post date', 'Description', 'Amount'] + ENTITIES + ['Total_Allocated', 'Allocation_Check', 'Allocation_Status']
        available_columns = [col for col in display_columns if col in processed_df.columns]
        
        if len(available_columns) < len(display_columns):
            st.info("💡 Some expected columns not found. Displaying available columns.")
        
        st.dataframe(processed_df[available_columns], use_container_width=True)
        
        # Validation results
        validation = validate_allocations(processed_df)
        
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
                {'Metric': 'Unbalanced Transactions', 'Value': validation['unbalanced_count']}
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
        
        # Instructions
        with st.expander("📖 How to Use This Tool"):
            st.markdown("""
            ### Default Allocation Strategy:
            - **All transactions are initially allocated to Panola Holdings LLC**
            - You can manually edit the Excel file to redistribute amounts across entities
            
            ### Excel File Structure:
            - **Allocations Sheet:** Full transaction data with allocation columns
            - **Summary Sheet:** Overall metrics and validation results  
            - **Entity_Totals Sheet:** Summary by entity
            
            ### Manual Allocation Steps:
            1. Open the downloaded Excel file
            2. Edit the entity columns (Panola Holdings LLC, Robert Dow Personal, etc.)
            3. Ensure each row's entity columns sum to the Amount column
            4. Use the Allocation_Check column to verify your edits
            5. The Allocation_Status column will show ✅ Balanced or ❌ Off by $X.XX
            
            ### Validation Rules:
            - Each transaction's entity allocations must sum to the Amount
            - The Allocation_Check column should be $0.00 for balanced transactions
            - Total allocated across all entities should equal total transaction amounts
            """)

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.write("Please ensure your CSV file has the expected format with transaction data.")

else:
    st.info("👆 Upload your credit card statement CSV to begin allocation")
    
    # Sample format guide
    st.markdown("""
    ### 📋 Expected CSV Format:
    Your CSV should contain columns like:
    - **Trans. date** - Transaction date
    - **Post date** - Posting date  
    - **Description** - Transaction description
    - **Amount** - Transaction amount (positive for charges, negative for payments)
    
    ### 🏢 Entity Allocation:
    The tool will create allocation columns for:
    - Panola Holdings LLC *(default allocation)*
    - Robert Dow (Personal)
    - RLV22 LLC
    - CSD Van Zandt LLC  
    - Goodfire Realty LLC
    - NDRE III LLC
    
    ### ✅ Built-in Validation:
    - Automatic allocation verification
    - Check totals to ensure 100% allocation
    - Balance validation for each transaction
    """)
