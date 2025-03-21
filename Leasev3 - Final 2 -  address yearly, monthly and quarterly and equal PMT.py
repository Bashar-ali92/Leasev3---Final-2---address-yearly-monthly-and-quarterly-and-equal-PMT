import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Set Streamlit page configuration
st.set_page_config(page_title="IFRS 16 Lease Calculator", layout="wide")

def calculate_lease_schedules(lease_name, region, start_date, payments, payment_frequency, discount_rate, num_periods, num_months):
    discount_rate = discount_rate / 100  # Convert percentage to decimal
    present_value = 0

    # --- Present Value Calculation (Annuity Due Handling) ---
    if payment_frequency == "monthly":
        for i in range(num_periods):
            if i == 0:
                present_value += payments[i]
            else:
                discounted_payment = payments[i] / ((1 + discount_rate / 12) ** i)
                present_value += discounted_payment
    elif payment_frequency == "quarterly":
        for q in range(num_periods):
            if q == 0:
                present_value += payments[q]
            else:
                discounted_payment = payments[q] / ((1 + discount_rate / 4) ** q)
                present_value += discounted_payment
    elif payment_frequency == "yearly":
        for i in range(num_periods):
            if i == 0:
                present_value += payments[i]
            else:
                discounted_payment = payments[i] / ((1 + discount_rate) ** i)
                present_value += discounted_payment

    # Save the present value as the initial liability and ROU asset value
    initial_liability = present_value
    rou_asset = present_value

    # --- Lease Liability Amortization Schedule (Monthly Breakdown) ---
    amortization_schedule = []
    remaining_lease_liability = initial_liability

    for i in range(num_months):
        interest_expense = remaining_lease_liability * (discount_rate / 12)
        current_month = (start_date + pd.DateOffset(months=i)).strftime("%b-%y")

        # Determine payment based on frequency:
        if payment_frequency == "monthly":
            payment = payments[i] if i < len(payments) else payments[-1]
        elif payment_frequency == "quarterly":
            payment = payments[i // 3] if i % 3 == 0 and (i // 3) < len(payments) else 0
        elif payment_frequency == "yearly":
            payment = payments[i // 12] if i % 12 == 0 and (i // 12) < len(payments) else 0
        else:
            payment = 0

        lease_liability = remaining_lease_liability + interest_expense - payment

        # Final adjustment: if this is the last month, set the remaining liability to zero
        if i == num_months - 1:
            lease_liability = 0

        remaining_lease_liability = max(lease_liability, 0)

        amortization_schedule.append({
            "Lease Contract Name": lease_name,
            "Region": region,
            "Month": current_month,
            "Payment": round(payment, 2),
            "Interest Expense": round(interest_expense, 2),
            "Remaining Lease Liability": round(remaining_lease_liability, 2)
        })

    # --- ROU Amortization Schedule (Monthly Breakdown) ---
    rou_schedule = []
    accumulated_depreciation = 0
    monthly_depreciation = rou_asset / num_months  # Evenly spread over all months

    for j in range(num_months):
        current_month = (start_date + pd.DateOffset(months=j)).strftime("%b-%y")
        accumulated_depreciation += monthly_depreciation
        net_rou_value = rou_asset - accumulated_depreciation

        rou_schedule.append({
            "Lease Contract Name": lease_name,
            "Region": region,
            "Month": current_month,
            "ROU Asset Value": round(rou_asset, 2),
            "Depreciation": round(monthly_depreciation, 2),
            "Accumulated Depreciation": round(accumulated_depreciation, 2),
            "Net ROU Value": round(net_rou_value, 2)
        })

    return round(present_value, 2), pd.DataFrame(amortization_schedule), pd.DataFrame(rou_schedule)

# Streamlit User Interface
st.title("\U0001F4CA IFRS 16 Lease Calculator with ROU Amortization & Early Termination")
st.markdown("Upload an **Excel or CSV file** to calculate lease present value, amortization schedule, and ROU asset depreciation.")

uploaded_file = st.file_uploader("\U0001F4C2 Upload an Excel or CSV file", type=["xlsx", "csv"])

if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1]
    df = pd.read_csv(uploaded_file) if file_ext == "csv" else pd.read_excel(uploaded_file)
    st.write("### 🔍 Uploaded Data Preview:")
    st.dataframe(df.head())

    required_columns = ["lease_name", "region", "currency", "start_date", "end_date", "discount_rate", "payment_frequency", "payment_amounts"]
    if all(col in df.columns for col in required_columns):
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"] = pd.to_datetime(df["end_date"])

        results = []
        amortization_schedules = []
        rou_schedules = []

        for index, row in df.iterrows():
            # Calculate the total number of months in the lease term
            num_months = (row["end_date"].year - row["start_date"].year) * 12 + (row["end_date"].month - row["start_date"].month) + 1

            # Determine the number of payment periods based on frequency:
            if row["payment_frequency"] == "yearly":
                num_periods = (row["end_date"].year - row["start_date"].year) + (1 if row["end_date"].month >= row["start_date"].month else 0)
            elif row["payment_frequency"] == "monthly":
                num_periods = num_months
            elif row["payment_frequency"] == "quarterly":
                num_periods = (num_months // 3) if (num_months % 3 == 0) else (num_months // 3 + 1)

            payment_str = str(row["payment_amounts"]).strip()
            if ',' not in payment_str:
                payments = [float(payment_str)] * num_periods
            else:
                payments = [float(x) for x in payment_str.split(",")]

            pv, amort_schedule, rou_schedule = calculate_lease_schedules(
                row["lease_name"],
                row["region"],
                row["start_date"],
                payments,
                row["payment_frequency"],
                row["discount_rate"],
                num_periods,
                num_months
            )

            amortization_schedules.append(amort_schedule)
            rou_schedules.append(rou_schedule)

            results.append({
                "Lease Contract Name": row["lease_name"],
                "Region": row["region"],
                "Currency": row["currency"],
                "Start Date": row["start_date"],
                "End Date": row["end_date"],
                "Discount Rate": row["discount_rate"],
                "Payment Frequency": row["payment_frequency"],
                "Present Value": pv
            })

        result_df = pd.DataFrame(results)
        st.write("### 📊 Calculated Present Values")
        st.dataframe(result_df)

        csv = result_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Present Value Results", data=csv, file_name="lease_present_values.csv", mime="text/csv")

        st.write("### 📅 Consolidated Amortization & ROU Schedules")
        consolidated_amortization = pd.concat(amortization_schedules, ignore_index=True)
        consolidated_rou = pd.concat(rou_schedules, ignore_index=True)

        st.write("#### 📜 Lease Amortization Schedule")
        st.dataframe(consolidated_amortization)

        st.write("#### 🏢 Right-of-Use (ROU) Asset Amortization Schedule")
        st.dataframe(consolidated_rou)
    else:
        st.error(f"❌ Missing required columns. Expected: {required_columns}")
