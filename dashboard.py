import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os
import shutil
    
# Function to load journal entries
def load_journal():
    journal_file = 'trade_journal_copy.txt'
    if os.path.exists(journal_file):
        with open(journal_file, 'r') as f:
            return f.read()
    return "No journal entries found."
   
# Function to plot calendar
def plot_calendar(daily_pnl, year, month):
    fig, ax = plt.subplots(figsize=(12, 8))
    cal = calendar.Calendar(firstweekday=6)
    
    month_days = cal.monthdayscalendar(year, month)
    
    # Define colors
    color_map = {
        'positive': 'green',
        'negative': 'red',
        'neutral': 'white'
    }
    
    # Plot each day
    for week_idx, week in enumerate(month_days):
        for day_idx, day in enumerate(week):
            if day == 0:
                continue  # Skip days outside the current month
            
            date = datetime(year, month, day)
            pnl = daily_pnl.get(date.date(), 0)
            color = color_map['neutral']
            
            if pnl > 0:
                color = color_map['positive']
            elif pnl < 0:
                color = color_map['negative']
            
            # Adjust y-value to align colors correctly
            rect_y = -week_idx - 1  # Shift by 1 to align with the correct row
            
            ax.add_patch(patches.Rectangle(
                (day_idx, rect_y), 1, 1, color=color, alpha=0.5
            ))
            # Add day number
            ax.text(day_idx + 0.5, rect_y + 0.5, str(day),
                    ha='center', va='center', fontsize=12, color='black')
            
            # Add P&L value slightly adjusted up
            pnl_text = f"${pnl:.2f}"
            ax.text(day_idx + 0.5, rect_y + 0.75, pnl_text,
                    ha='center', va='center', fontsize=10, color='black')
    
    ax.set_xlim(0, 7)
    ax.set_ylim(-len(month_days) - 2, 0)  # Adjust ylim to fit P&L text
    ax.set_xticks(np.arange(7) + 0.5)
    ax.set_xticklabels(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
    ax.set_yticks([])
    ax.set_title(f'Calendar for {calendar.month_name[month]} {year}')
    
    plt.grid(False)
    plt.tight_layout()
    return fig

# Function to load and combine data from uploaded files
def load_data(uploaded_files):
    df_list = []
    for uploaded_file in uploaded_files:
        df = pd.read_csv(uploaded_file)
        df_list.append(df)
    #combine all data frames
    df = pd.concat(df_list, ignore_index=True)
    #process data
    df['Avg Price'] = df['Avg Price'].astype(str).str.replace('@', '', regex=False)
    df['Avg Price'] = pd.to_numeric(df['Avg Price'], errors='coerce') * 100
    df['Filled'] = pd.to_numeric(df['Filled'], errors='coerce')
    # Handle Filled Time and strip timezone
    df['Filled Time'] = pd.to_datetime(df['Filled Time'].str.replace(r'\s+EDT$', '', regex=True), errors='coerce')
    df['Date'] = df['Filled Time'].dt.date
    df['Total Qty'] = pd.to_numeric(df['Total Qty'], errors='coerce')
    
    grouped_by_date = df.groupby('Date')
    daily_pnl = {}
    trade_details = {}
    
    for date, group in grouped_by_date:
        details = {}

        for index, row in group.iterrows():
            trade_value = row['Filled'] * row['Avg Price']
            symbol = row['Symbol']
            
            if symbol not in details:
                details[symbol] = {
                    'Buy Total': 0,
                    'Sell Total': 0,
                    'Avg Buy Price': 0,
                    'Avg Sell Price': 0,
                    'Quantity': 0,
                    'Side': row['Side'],
                    'Strike': row['Name'].split(' ')[2],
                    'Type': 'Call' if 'Call' in row['Name'] else 'Put'
                }

            if row['Side'] == 'Buy':
                details[symbol]['Buy Total'] += trade_value
                details[symbol]['Quantity'] += row['Total Qty']
                details[symbol]['Avg Buy Price'] = details[symbol]['Buy Total'] / details[symbol]['Quantity']
            elif row['Side'] == 'Sell':
                details[symbol]['Sell Total'] += trade_value

        for symbol, detail in details.items():
            pnl = detail['Sell Total'] - detail['Buy Total']
            daily_pnl.setdefault(date, 0)
            daily_pnl[date] += pnl
            
            trade_details.setdefault(date, []).append({
                'Symbol': symbol,
                'Avg Buy Price': detail['Avg Buy Price'],
                'Avg Sell Price': detail['Sell Total'] / detail['Quantity'] if detail['Quantity'] > 0 else 0,
                'Quantity': detail['Quantity'],
                'P&L': pnl,
                'Strike': detail['Strike'],
                'Type': detail['Type'],
                'Action': detail['Side']
            })

    return daily_pnl, trade_details

# Function to save a journal entry with structured trade information
def save_journal_entry(date, trade, notes):
    journal_file = 'trade_journal_copy.txt'
    with open(journal_file, 'a') as f:
        entry = (
            f"Date: {date}\n"
            f"Symbol: {trade['Symbol']}\n"
            f"Action: {trade['Action']}\n"
            f"Avg Buy Price: ${trade['Avg Buy Price']:.2f}\n"
            f"Avg Sell Price: ${trade['Avg Sell Price']:.2f}\n"
            f"Quantity: {trade['Quantity']}\n"
            f"P&L: ${trade['P&L']:.2f}\n"
            f"Strike: {trade['Strike']}\n"
            f"Type: {trade['Type']}\n"
            f"Notes: {notes}\n"
            f"{'-'*40}\n"
        )
        f.write(entry)

# Function to handle file upload and save a copy
def handle_file_upload(uploaded_file): 
    if uploaded_file is not None:
        # Save the uploaded file temporarily
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Create a copy in the program folder
        copy_file_path = f"trade_journal_copy.txt"  # Modify this as needed
        shutil.copy(uploaded_file.name, copy_file_path)

        return copy_file_path  # Return the path of the copied file

# Streamlit app
def main():
    st.title('Trading Performance Calendar')

    # Initialize session state for current_date and notes
    if 'current_date' not in st.session_state:
        st.session_state.current_date = datetime.today()  # Default to today

    if 'notes' not in st.session_state:
        st.session_state.notes = {}

    if 'journal_file' not in st.session_state:
        st.session_state.journal_files = None

    # File uploader for multiple CSV files
    uploaded_files = st.file_uploader("Upload your CSV files", type='csv', accept_multiple_files=True)
    
    if uploaded_files:
        daily_pnl, trade_details = load_data(uploaded_files)

        # File uploader for the trading journal
        journal_file = st.file_uploader("Upload your trading journal notes", type='txt')
        if journal_file is not None:
            journal_file_path = handle_file_upload(journal_file)
            st.success('file uploaded and saved successfully')

            
        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 5, 1])
        with col1:
            if st.button("Previous Month"):
                st.session_state.current_date = st.session_state.current_date - timedelta(days=30)
        with col2:
            st.write("###")
        with col3:
            if st.button("Next Month"):
                st.session_state.current_date = st.session_state.current_date + timedelta(days=30)

        current_date = st.session_state.current_date
        year = current_date.year
        month = current_date.month
        
        fig = plot_calendar(daily_pnl, year, month)
        st.pyplot(fig)

        selected_date = st.date_input(
            "Select a date", 
            value=current_date, 
            min_value=datetime(year, month, 1), 
            max_value=datetime(year, month, calendar.monthrange(year, month)[1])
        )
        
        if selected_date in daily_pnl:
            st.write(f"### Profit/Loss for {selected_date}")
            st.write(f"**Profit/Loss for {selected_date}: ${daily_pnl[selected_date]:.2f}**")

            st.write(f"### Trade Details for {selected_date}")
            trades = trade_details[selected_date]

            for trade in trades:
                st.write(f"**Symbol**: {trade['Symbol']}")
                st.write(f"**Type**: {trade['Type']}")
                st.write(f"**Avg Buy Price**: ${trade['Avg Buy Price']:.2f}")
                st.write(f"**Avg Sell Price**: ${trade['Avg Sell Price']:.2f}")
                st.write(f"**Quantity**: {trade['Quantity']}")
                st.write(f"**P&L**: ${trade['P&L']:.2f}")

                # Add note field
                note_input_key = f"{selected_date}_{trade['Symbol']}"
                note_input = st.text_area(f"Notes for {trade['Symbol']}", key=note_input_key)
                if st.button(f"Save Journal Entry for {trade['Symbol']}", key=f"save_{note_input_key}"):
                    save_journal_entry(selected_date, trade, note_input)
                    st.success("Journal entry saved!")
                
                st.write("-----")
        else:
            st.write(f"No trades for {selected_date}")

        # Show previous journal entries
        st.write("### Your Journal Entries")
        journal_entries = load_journal()
        st.text_area("Previous Entries:", value=journal_entries, height=200)

        # Button to download the journal
        st.download_button(
            label="Download Journal",
            data=journal_entries,
            file_name='trading_notes.txt',
            mime='text/plain'
        )




if __name__ == "__main__":
    main()
