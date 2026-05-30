import streamlit as st
import math
import pandas as pd
import io

# ==========================================
# 1. Streamlit Page Configuration
# ==========================================
st.set_page_config(page_title="Advanced BEMS Simulator", layout="wide", page_icon="🏢")
st.title("🏢 Advanced Building Energy Management System (BEMS)")
st.markdown("Optimize a multi-zone commercial building with Smart Battery Arbitrage and Solar PV.")

# ==========================================
# 2. The GUI Sidebar (User Inputs)
# ==========================================
st.sidebar.header("Architecture (Multi-Zone)")
office_r = st.sidebar.slider("Office Insulation (R-Value)", 1.5, 10.0, 3.5, 0.5)
server_r = st.sidebar.slider("Server Room Insulation", 1.5, 10.0, 6.0, 0.5)

st.sidebar.header("Mechanical Systems")
hvac_cop = st.sidebar.slider("HVAC Efficiency (COP)", 1.0, 5.0, 3.5, 0.5)

st.sidebar.header("Smart Grid & Renewables")
pv_area = st.sidebar.slider("Solar PV Area (m²)", 0, 200, 50, 10)
battery_size = st.sidebar.slider("Tesla Powerwall (kWh)", 0, 100, 14, 2)

# ==========================================
# 3. The Core Physics Engine
# ==========================================
@st.cache_data
def run_master_simulation(r_office, r_server, cop, pv_m2, batt_capacity):
    # Data Storage
    hourly_data = {"Hour": [], "Office Temp (°C)": [], "Server Temp (°C)": [], 
                   "Net Grid Load (kWh)": [], "Battery Level (kWh)": [], "Cost ($)": []}
    
    monthly_costs = [0.0] * 12
    
    # Starting States
    t_office = 21.0
    t_server = 21.0
    current_batt = 0.0
    
    # TOU Rates
    rate_peak = 0.35  # 4 PM - 9 PM
    rate_off = 0.05   # Midnight - 6 AM
    rate_std = 0.15
    rate_exp = 0.08
    
    for h in range(8760):
        month = (h // 24) // 31
        if month > 11: month = 11
        hour_of_day = h % 24
        
        # Weather
        t_out = 15 + -12 * math.cos(2 * math.pi * ((h//24) - 15) / 365) + 6 * math.sin((hour_of_day - 9) * math.pi / 12)
        solar_w = max(0, math.sin((hour_of_day - 6) * math.pi / 12)) * 600
        
        # --- MULTI-ZONE PHYSICS ---
        # Office (People 9-5)
        office_internal = 2.0 if 8 <= hour_of_day <= 18 else 0.2
        heat_transfer_office = (t_out - t_office) / r_office
        heat_from_server = (t_server - t_office) * 1.0  # Heat bleeds through the wall!
        t_office += (heat_transfer_office + (solar_w/100)*1.5 + office_internal + heat_from_server) / 25.0
        
        # Server Room (Runs 24/7)
        server_internal = 5.0
        heat_transfer_server = (t_out - t_server) / r_server
        heat_loss_to_office = (t_office - t_server) * 1.0
        t_server += (heat_transfer_server + server_internal + heat_loss_to_office) / 40.0
        
        # --- HVAC LOGIC ---
        hvac_kwh = 0.0
        if t_office > 24.0: hvac_kwh += ((t_office - 24.0) * 25.0 * 0.28) / cop; t_office = 24.0
        elif t_office < 20.0: hvac_kwh += ((20.0 - t_office) * 25.0 * 0.28) / 2.5; t_office = 20.0
            
        if t_server > 22.0: hvac_kwh += ((t_server - 22.0) * 40.0 * 0.28) / cop; t_server = 22.0
            
        # --- SMART BATTERY & SOLAR ---
        pv_kwh = (solar_w * pv_m2 * 0.20) / 1000.0
        net_load = hvac_kwh - pv_kwh
        
        # Determine Current Rate
        current_rate = rate_std
        if 16 <= hour_of_day <= 21: current_rate = rate_peak
        elif 0 <= hour_of_day <= 6: current_rate = rate_off
            
        # Battery Arbitrage
        if net_load < 0: # Charge from excess solar
            charge = min(abs(net_load), 5.0, batt_capacity - current_batt)
            current_batt += charge; net_load += charge
        elif net_load > 0 and current_rate == rate_peak: # Discharge to avoid peak rates
            discharge = min(net_load, 5.0, current_batt)
            current_batt -= discharge; net_load -= discharge
        elif current_rate == rate_off and current_batt < batt_capacity: # Force charge at night
            charge = min(batt_capacity - current_batt, 5.0)
            current_batt += charge; net_load += charge
            
        # Billing
        cost = net_load * current_rate if net_load > 0 else net_load * rate_exp
        monthly_costs[month] += cost
        
        # Store Data
        hourly_data["Hour"].append(h)
        hourly_data["Office Temp (°C)"].append(round(t_office, 2))
        hourly_data["Server Temp (°C)"].append(round(t_server, 2))
        hourly_data["Net Grid Load (kWh)"].append(round(net_load, 2))
        hourly_data["Battery Level (kWh)"].append(round(current_batt, 2))
        hourly_data["Cost ($)"].append(round(cost, 2))
        
    return monthly_costs, hourly_data

# ==========================================
# 4. Render the Dashboard
# ==========================================
monthly_costs, hourly_data = run_master_simulation(office_r, server_r, hvac_cop, pv_area, battery_size)
total_annual_bill = sum(monthly_costs)
upfront_cost = (office_r * 2000) + (server_r * 1500) + (hvac_cop * 3000) + (pv_area * 300) + (battery_size * 500)

# Top KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Annual Utility Bill", f"${total_annual_bill:,.2f}")
col2.metric("Estimated Upfront Cost", f"${upfront_cost:,.2f}")
col3.metric("15-Year Payback (ROI)", f"${upfront_cost + (total_annual_bill * 15):,.2f}")

st.divider()

# Charts Side-by-Side
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("Monthly Electricity Cost ($)")
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    st.bar_chart(pd.DataFrame({"Month": months, "Net Cost ($)": monthly_costs}).set_index("Month"))

with col_chart2:
    st.subheader("Battery Profile (First Summer Week)")
    # Plot hours 4000 to 4168 to show the battery charging and discharging
    df_batt = pd.DataFrame({
        "Hour": hourly_data["Hour"][4000:4168], 
        "Battery Level (kWh)": hourly_data["Battery Level (kWh)"][4000:4168]
    }).set_index("Hour")
    st.line_chart(df_batt, color="#28a745")

st.divider()

# ==========================================
# 5. The Download Button!
# ==========================================
st.subheader("Data Export")
st.write("Download the full 8,760-hour simulation dataset for use in Excel, Python, or Tableau.")

# Convert Python dictionary to a Pandas DataFrame, then to CSV
df_export = pd.DataFrame(hourly_data)
csv_data = df_export.to_csv(index=False).encode('utf-8')

st.download_button(
    label="📥 Download 8760 Hourly Data (CSV)",
    data=csv_data,
    file_name="BEMS_Simulation_Data.csv",
    mime="text/csv"
)