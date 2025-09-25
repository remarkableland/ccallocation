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
    
    # DEFAULT ALLOCATION: All amounts (both positive charges AND negative credits) go to Panola Holdings LLC
    # This ensures ALL transactions, including credits/payments, default to Panola
    processed_df['Panola Holdings LLC'] = processed_df[amount_column].copy()
    
    # Add validation columns - but we'll replace these with Excel formulas
    processed_df['Total_Allocated'] = processed_df[ENTITIES].sum(axis=1)
    processed_df['Allocation_Check'] = processed_df[amount_column] - processed_df['Total_Allocated']
    processed_df['Allocation_Status'] = processed_df['Allocation_Check'].apply(
        lambda x: 'Balanced' if abs(x) < 0.01 else f'Off by ${x:.2f}'
    )
    
    # Add Property column at the end
    processed_df['Property'] = ''
    
    return processed_df

def create_excel_with_formulas(df, amount_column):
    """Create CSV content with Excel formula placeholders for the check column and totals"""
    
    # Find the column positions (Excel uses 1-based indexing)
    columns = df.columns.tolist()
    amount_col_idx = columns.index(amount_column) + 1  # Excel column number
    
    # Find entity column positions
    entity_col_positions = {}
    for entity in ENTITIES:
        if entity in columns:
            entity_col_positions[entity] = columns.index(entity) + 1
    
    total_allocated_col_idx = columns.index('Total_Allocated') + 1
    allocation_check_col_idx = columns.index('Allocation_Check') + 1
    property_col_idx = columns.index('Property') + 1
    rlv22_col_idx = columns.index('RLV22 LLC') + 1
    
    # Convert to Excel column letters
    def num_to_excel_col(n):
        result = ""
        while n > 0:
            n -= 1
            result = chr(n % 26 + ord('A')) + result
            n //= 26
        return result
    
    amount_col_letter = num_to_excel_col(amount_col_idx)
    total_allocated_col_letter = num_to_excel_col(total_allocated_col_idx)
    allocation_check_col_letter = num_to_excel_col(allocation_check_col_idx)
    property_col_letter = num_to_excel_col(property_col_idx)
    rlv22_col_letter = num_to_excel_col(rlv22_col_idx)
    
    # Entity column letters
    entity_col_letters = {}
    for entity, pos in entity_col_positions.items():
        entity_col_letters[entity] = num_to_excel_col(pos)
    
    # Create the enhanced DataFrame
    enhanced_df = df.copy()
    
    # Replace the static calculations with formula placeholders
    num_rows = len(df)
    
    # Total_Allocated formulas (sum of entity columns for each row)
    entity_range_start = num_to_excel_col(entity_col_positions[ENTITIES[0]])
    entity_range_end = num_to_excel_col(entity_col_positions[ENTITIES[-1]])
    
    for i in range(num_rows):
        row_num = i + 2  # Excel rows start at 1, plus header row
        # Total_Allocated formula: sum of all entity columns
        enhanced_df.iloc[i, enhanced_df.columns.get_loc('Total_Allocated')] = f"=SUM({entity_range_start}{row_num}:{entity_range_end}{row_num})"
        # Allocation_Check formula: Amount - Total_Allocated
        enhanced_df.iloc[i, enhanced_df.columns.get_loc('Allocation_Check')] = f"={amount_col_letter}{row_num}-{total_allocated_col_letter}{row_num}"
        # Status formula: IF check is nearly zero, show balanced, else show difference (NO EMOJIS)
        enhanced_df.iloc[i, enhanced_df.columns.get_loc('Allocation_Status')] = f'=IF(ABS({allocation_check_col_letter}{row_num})<0.01,"Balanced","Off by $"&ROUND({allocation_check_col_letter}{row_num},2))'
        # Property formula: IF RLV22 LLC has a value, show "Required", else blank
        enhanced_df.iloc[i, enhanced_df.columns.get_loc('Property')] = f'=IF({rlv22_col_letter}{row_num}<>0,"Required","")'
    
    # Add totals row
    totals_row_num = num_rows + 2  # After data rows
    totals_row = {}
    
    # Initialize totals row
    for col in enhanced_df.columns:
        totals_row[col] = ""
    
    # First column gets "TOTALS" label
    first_col = enhanced_df.columns[0]
    totals_row[first_col] = "TOTALS"
    
    # Amount column total
    totals_row[amount_column] = f"=SUM({amount_col_letter}2:{amount_col_letter}{num_rows + 1})"
    
    # Entity column totals
    for entity in ENTITIES:
        if entity in enhanced_df.columns:
            col_letter = entity_col_letters[entity]
            totals_row[entity] = f"=SUM({col_letter}2:{col_letter}{num_rows + 1})"
    
    # Total_Allocated total
    totals_row['Total_Allocated'] = f"=SUM({total_allocated_col_letter}2:{total_allocated_col_letter}{num_rows + 1})"
    
    # Allocation_Check total (should be zero if everything balances)
    totals_row['Allocation_Check'] = f"=SUM({allocation_check_col_letter}2:{allocation_check_col_letter}{num_rows + 1})"
    
    # Status for totals row (NO EMOJIS)
    totals_row['Allocation_Status'] = f'=IF(ABS({allocation_check_col_letter}{totals_row_num})<0.01,"ALL BALANCED","TOTAL OFF by $"&ROUND({allocation_check_col_letter}{totals_row_num},2))'
    
    # Property totals - count how many are "Required"
    totals_row['Property'] = f'=COUNTIF({property_col_letter}2:{property_col_letter}{num_rows + 1},"Required")&" Required"'
    
    # Append totals row
    enhanced_df = pd.concat([enhanced_df, pd.DataFrame([totals_row])], ignore_index=True)
    
    return enhanced_df

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
            
            st.success("✅ Processing complete! All transactions (charges AND credits) defaulted to Panola Holdings LLC")
            
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
            
            # Show credit/debit breakdown
            credits = processed_df[processed_df[amount_column] < 0]
            debits = processed_df[processed_df[amount_column] > 0]
            
            with st.expander("💳 Transaction Breakdown"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Credits (Payments):** {len(credits):,} transactions")
                    st.write(f"**Credit Total:** ${credits[amount_column].sum():,.2f}")
                with col2:
                    st.write(f"**Debits (Charges):** {len(debits):,} transactions")
                    st.write(f"**Debit Total:** ${debits[amount_column].sum():,.2f}")
            
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
            
            # Reorder columns for better display - put amount column first, then entities, then validation, then Property at the end
            amount_and_entity_columns = [amount_column] + ENTITIES + ['Total_Allocated', 'Allocation_Check', 'Allocation_Status', 'Property']
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
            st.subheader("📥 Download Processed Files")
            
            # Generate timestamp for filenames
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create enhanced version with formulas and totals
            with st.spinner("Creating Excel-ready file with formulas..."):
                enhanced_df = create_excel_with_formulas(processed_df, amount_column)
            
            # Main allocation CSV with formulas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**📊 Main Allocation File (with formulas & totals):**")
                enhanced_csv = enhanced_df.to_csv(index=False)
                st.download_button(
                    label="📄 Download Enhanced_Allocations.csv",
                    data=enhanced_csv,
                    file_name=f"enhanced_credit_card_allocations_{current_time}.csv",
                    mime="text/csv"
                )
                st.caption("✅ Includes Excel formulas & totals row")
            
            with col2:
                st.write("**📋 Basic Allocation File:**")
                basic_csv = processed_df.to_csv(index=False)
                st.download_button(
                    label="📄 Download Basic_Allocations.csv",
                    data=basic_csv,
                    file_name=f"basic_credit_card_allocations_{current_time}.csv",
                    mime="text/csv"
                )
                st.caption("Standard CSV without formulas")
            
            with col3:
                st.write("**📊 Summary Report:**")
                summary_df = pd.DataFrame([
                    {'Metric': 'Total Transactions', 'Value': len(processed_df)},
                    {'Metric': 'Total Amount', 'Value': f"${total_amount:,.2f}"},
                    {'Metric': 'Total Credits', 'Value': f"${credits[amount_column].sum():,.2f}"},
                    {'Metric': 'Total Debits', 'Value': f"${debits[amount_column].sum():,.2f}"},
                    {'Metric': 'Total Allocated', 'Value': f"${total_allocated:,.2f}"},
                    {'Metric': 'Allocation Check', 'Value': f"${allocation_difference:.2f}"},
                    {'Metric': 'Unbalanced Transactions', 'Value': validation['unbalanced_count']},
                    {'Metric': 'Amount Column Used', 'Value': amount_column}
                ])
                summary_csv = summary_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download Summary.csv",
                    data=summary_csv,
                    file_name=f"allocation_summary_{current_time}.csv",
                    mime="text/csv"
                )
            
            # Instructions for Excel usage
            with st.expander("📖 Excel Formula Features"):
                st.markdown("""
                ### 🚀 Enhanced CSV Features:
                The **Enhanced Allocations CSV** includes:
                
                **✅ Live Excel Formulas:**
                - **Total_Allocated:** `=SUM(F2:K2)` (automatically sums entity columns)
                - **Allocation_Check:** `=D2-L2` (Amount minus Total_Allocated)
                - **Allocation_Status:** Shows "Balanced" or "Off by $X.XX" (CSV-friendly, no emojis)
                - **Property:** `=IF(J2<>0,"Required","")` (Shows "Required" if RLV22 LLC has value)
                
                **✅ Totals Row at Bottom:**
                - Sums all columns automatically
                - Grand total validation
                - Overall balance check
                - Property count shows how many are "Required"
                
                **✅ Dynamic Updates:**
                - Edit any entity column → formulas update automatically
                - Instant feedback if allocations don't balance
                - Property column updates based on RLV22 LLC values
                - No manual calculations needed!
                
                ### 📋 How to Use in Excel:
                1. **Download Enhanced_Allocations.csv**
                2. **Open in Excel** (formulas will activate)
                3. **Edit entity columns** to redistribute amounts
                4. **Watch formulas update** automatically
                5. **Check totals row** for overall balance
                6. **Property column** shows "Required" when RLV22 LLC has values
                
                ### 💡 Tips:
                - **"Balanced"** = Transaction is properly allocated
                - **"Off by $X"** = Transaction needs adjustment
                - **Totals row** shows if entire statement balances
                - **All credits and debits** start in Panola Holdings LLC
                - **Property column** automatically tracks RLV22 LLC usage
                """)

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
            st.dataframe(df_debug.head(5))
        except Exception as debug_error:
            st.write(f"- Could not read file for debugging: {debug_error}")

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
    - **Excel formulas** for automatic balance checking
    - **Totals row** at bottom of each column
    - **Live updates** when you edit allocations
    - **Credits AND debits** both default to Panola
    
    ### 📊 Enhanced CSV Output:
    - **Enhanced File:** With Excel formulas and totals row
    - **Basic File:** Standard CSV for other uses
    - **Summary Report:** Overall metrics and validation
    
    **Perfect for Excel:** Formulas activate automatically when opened in Excel!
    """)
    
