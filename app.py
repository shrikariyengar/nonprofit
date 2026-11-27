import streamlit as st
import pandas as pd
import os
import tempfile
import uuid
from module1 import run_routing
from module2 import run_kitter


#Get exact folder where app.py is saved
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
default_inventory = os.path.join(BASE_DIR, "inventory.csv")
default_stops = os.path.join(BASE_DIR, "stops.csv")

if "session_dir" not in st.session_state:
    st.session_state.session_dir = os.path.join(tempfile.gettempdir(), f"logistics_{uuid.uuid4().hex[:8]}")
    os.makedirs(st.session_state.session_dir, exist_ok = True)
session_dir = st.session_state.session_dir

st.set_page_config(page_title = "Logistics Dashboard", layout = "wide")
st.title("Logistics and Distribution Hub")
st.markdown("Module 1 (Vehicle Routing) and Module 2 (Box Packing Optimization) - MUST FOLLOW GIVEN TEMPLATE FORMAT")
st.divider()

st.sidebar.header("Different Modes and Settings")
app_options = st.sidebar.selectbox("Select Module", ["Module 1: Vehicle Routing", "Module 2: Packing Boxes Efficiently"])
#====================MODULE 1====================
if app_options == "Module 1: Vehicle Routing":
    st.header("Vehicle Routing Optimizer")
    st.markdown("Optimize delivery routes for supplies (factors in vehicle capacities)")
    st.info("What is a unit? Pick one consistent load-unit such as 1 packed box, 1 crate, or " \
    "10 lbs and use that same unit for both 'Demand' and 'Vehicle Capacity' in the CSV sidebar.")
    st.sidebar.subheader("Routing Data Input")
    uploaded_stops = st.sidebar.file_uploader("Upload Custom Stops CSV", type = ["csv"])

    if os.path.exists(default_stops):
        with open(default_stops, "rb") as f:
            stops_bytes = f.read()

        st.sidebar.download_button(
            label = "Download Stops Template",
            data = stops_bytes,
            file_name = "stops_template.csv",
            mime = "text/csv"
        )
    #Sidebar parameters for the routing
    num_vehicles = st.sidebar.number_input("Number of Vehicles", min_value = 1, value = 1)
    vehicle_capacity = st.sidebar.number_input("Vehicle Capacity (Units)", min_value = 1, max_value = 100, value = 5, help = "Max Load one vehicle can carry is measured in the same unit as your CSV's 'Demand Column!")

    if uploaded_stops is not None:
        stops_path = os.path.join(session_dir, "temp_stops.csv")
        with open(stops_path, "wb") as f:
            f.write(uploaded_stops.getbuffer())
    else:
        stops_path = default_stops

    if os.path.exists(stops_path):
        st.subheader("Current Delivery Stops Preview")
        df_stops = pd.read_csv(stops_path)
        st.dataframe(df_stops, use_container_width = True, hide_index = True)

        if st.button("Run Vehicle Routing", type = "primary", use_container_width = True):
            with st.spinner("Calculating optimal delivery route[s]"):

                map_output_path = os.path.join(session_dir, "route_map.html")
                results = run_routing(csv_path = stops_path, num_vehicles = num_vehicles, vehicle_capacity = vehicle_capacity, map_output_path = map_output_path)

                if results.get("status") == "Success":
                    st.success("Routing Optimization Complete!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label = "Total Fleet Distance", value = f"{results.get('total_distance', 0):.2f} miles", border = True)
                    with col2:
                        st.metric(label = "Total Delivered Load", value = f"{results.get('total_load', 0):.2f} units", border = True)

                    st.subheader("Route Details Summary")
                    route_details = results.get("route_details", [])
                    if route_details:
                        df_routes = pd.DataFrame(results.get("route_details")) 
                        st.dataframe(df_routes, use_container_width = True, hide_index = True)

                        #Download button for vehicles
                        route_text = "\n".join([f"Driver {r["Vehicle"]}: \nRoute: {r["Route"]} \nTotal Distance: {r["Distance (miles)"]} miles \n Total Load: {r["Load"]} units"
                        for r in route_details
                        ])
                        st.download_button(
                            label = "Download Driver Route Instruction (TXT)",
                            data = route_text,
                            file_name = "driver_route_instructions.txt",
                            mime = "text/plain"
                        )

                    st.subheader("Interactive Route Map")
                    map_file_path = results.get("map_file")   

                    if map_file_path and os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding = "utf-8") as f:
                            map_html = f.read()
                        st.components.v1.html(map_html, height = 575)
                else:
                    st.error("Routing Infeasible: Check your vehicle capacity limits against stop demands")
    else:
        st.warning("No stops file found. Upload a CSV in sidebar or place 'stops.csv' with columns: 'Location_Name', 'Latitude', 'Longitude', 'Demand'.")


#====================MODULE 2====================


if app_options == "Module 2: Packing Boxes Efficiently":
    st.header("Inventory and Box Packing Optimizer")
    st.markdown("This tool helps maximize box capacity while ensuring every box has the necessary items")
    st.info("No exact ruler measurement are needed: assign relative size points in 'size_units'. For example: " \
    "1 = pouch, 3 = standard item, 6 = large blanket. Then, set 'Maximum Box Volume Capacity'.")
    st.sidebar.subheader("Data Input")
    uploaded_file = st.sidebar.file_uploader("Upload Custom Inventory CSV", type = ["csv"])

    if os.path.exists(default_inventory):
        with open(default_inventory, "rb") as f:
            file_bytes = f.read()

        st.sidebar.download_button(
            label = "Download Inventory Template",
            data = file_bytes,
            file_name = "inventory_template.csv",
            mime = "text/csv"
        )

    box_limit = st.sidebar.slider(
        "Maximum Box Volume Capacity",
        min_value = 10,
        max_value = 200,
        value = 15,
        help = "Total size points one box can hold, using the same scale as 'size_units' "
        "in your CSV (e.g., if a box holds 15, it fits 5 3-point items")

    if uploaded_file is not None:
        inventory_path = os.path.join(session_dir, "temp_inventory.csv")
        with open(inventory_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    else:
        inventory_path = default_inventory
    if os.path.exists(inventory_path):
        #Table
        st.subheader("Current Inventory Preview")
        df_preview = pd.read_csv(inventory_path, comment = "#", skipinitialspace = True)
        st.dataframe(df_preview, use_container_width = True, hide_index = True)

        if st.button("Run Optimization", type = "primary", use_container_width = True):
            with st.spinner("Calculating optimal packing arrangement..."):
                #Display Results
                results = run_kitter(csv_path = inventory_path, box_volume_limit = box_limit)
                #Check if the solver failed due to too tight of constraints
                status = results.get("status", "Unknown")
                total_boxes = results.get("total_boxes", 0)

                if status not in ("Optimal", "Feasible", "GapLimit") or total_boxes <= 0:
                    st.error(f"Packing Status ({status}): Check your minimum item requirements against box capacity and inventory.")
                #Otherwise, print success and information
                else:
                    st.success("Optimization Complete!")
                    column1, column2 = st.columns(2)
                    with column1:
                        st.metric(label = "Total Boxes to Pack", value = f"{total_boxes}", border = True)
                    with column2:
                        st.metric(label = "Solver Status", value = status, border = True)

                    st.subheader("Items per Single Box: ")
                    list_df = pd.DataFrame(list(results.get("manifest", {}).items()), columns = ["Items", "Units per Box"])
                    st.dataframe(list_df, use_container_width = True, hide_index = True)

                    #Leftover Inventory Supplies Output
                    st.subheader("Remaining Warehouse Inventory")
                    leftover_df = df_preview[["item_id", "quantity_available"]].copy()
                    leftover_df["Used for Boxes"] = leftover_df["item_id"].map(results.get("manifest", {})) * total_boxes
                    leftover_df["Leftover on Shelf"] = leftover_df["quantity_available"] - leftover_df["Used for Boxes"]
                    st.dataframe(leftover_df, use_container_width = True, hide_index = True)

    else:
        st.warning("No inventory file found. Upload a CSV in sidebar or place 'inventory.csv' with columns: 'item_id', 'size_units', 'quantity_available' (optional: 'min_per_box', 'max_per_box').")