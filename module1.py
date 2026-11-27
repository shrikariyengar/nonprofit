#Import neccessary tools and libraries
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
import pandas as pd
import numpy as np
import folium

#OR-tools needs to keep fractional miles
SCALE = 10000
#Bundles all the rules and matrix into the function create_model
def create_model(csv_path = "stops.csv", num_vehicles = 1, vehicle_capacity = 5):
    data = {}
    #Read the actual csv of locations
    df = pd.read_csv(csv_path)
    #Normalizing columns headers and flagging missing columns
    df.columns = df.columns.str.strip().str.lower()
    required = {"demand", "latitude", "longitude"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"Stops CSV is missing required columns. Needs: {required}"
        )

    data["demands"] = df["Demand"].tolist()

    #Extract the latitude and longitude for distances
    latitudes = df["Latitude"].values
    longitudes = df["Longitude"].values

    #Create coordinate array for calculation
    coords = np.column_stack((latitudes, longitudes))
    num_locations = len(df)
    matrix = np.zeros((num_locations, num_locations))

    for i in range(num_locations):
        for j in range(num_locations):
            #Calculate Distance between the two distances (* 69 because 69 miles for every degree of latitude)
            dist = np.linalg.norm(coords[i] - coords[j]) * 69
            matrix[i][j] = round(dist, 5)

    data["distance_matrix"] = matrix.tolist()

    #Fleet Constraints
    data["vehicle_capacity"] = [vehicle_capacity] * num_vehicles
    data["num_vehicles"] = num_vehicles
    return df, data

#Mapping Function, to create the actual map
def plot_route(df, all_routes, output_path = "route_map.html"):
    #Get the coordinates of the starting depot (first stop)
    depot_idx = all_routes[0][0]
    depot_lat = df.loc[depot_idx, "Latitude"]
    depot_lon = df.loc[depot_idx, "Longitude"]

    #Initalize folium map (centered around the first place - depot)
    route_map = folium.Map(location=[depot_lat, depot_lon], zoom_start = 15, tiles = "Esri.WorldStreetMap")
    colors = ["purple", "blue", "green", "orange", "red"]

    for v_id, route_indices in enumerate(all_routes):
        #Declare list that will actually hold coordinate for the path line
        route_coords = []
        line_color = colors[v_id % len(colors)]
        #Loop through all the stops in the optimized route
        for idx in route_indices:
            lat = df.loc[idx, "Latitude"]
            lon = df.loc[idx, "Longitude"]
            name = df.loc[idx, "Location_Name"]
            demand = df.loc[idx, "Demand"]

            route_coords.append([lat, lon])
            #Colors the depot marker blue and the delivery as red
            marker_color = "blue" if idx == depot_idx else "red"

            #Marker for each stop
            folium.Marker(
                location = [lat, lon],
                popup = f"<b>{name}</b><br>Demand: {demand}",
                icon = folium.Icon(color = marker_color, icon = "info-sign")
            ).add_to(route_map)

        #Drawing actual line of the vehicle's path
        folium.PolyLine(route_coords, color = line_color, weight = 3.5, opacity = 0.75).add_to(route_map)

    #Save the map as an interactive HTML file
    route_map.save(output_path)
    return output_path

#main function
def run_routing(csv_path = "stops.csv", num_vehicles = 1, vehicle_capacity = 5, map_output_path = "route_map.html"):
    #Load the CSV data in again
    df, data = create_model(csv_path, num_vehicles, vehicle_capacity)

    #Create index manager that translates the Python counts into the internal ids that can be solved
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        0
    )

    #Create Routing Model using manager, which will handle all the variables, paths, constraints, etc.
    routing_model = pywrapcp.RoutingModel(manager)

    #Defining call back function, which essentially calculates distance between stops
    def distance_callback(from_place, to_place):
        #Convert internal ID to my index (readable matrix coordinates)
        from_node = manager.IndexToNode(from_place)
        to_node = manager.IndexToNode(to_place)
        #Looks up and returns exact distance between two points on matrix
        return int(round(data["distance_matrix"][from_node][to_node] * SCALE))

    #Registers distance function with solver to show it exists
    transit_index = routing_model.RegisterTransitCallback(distance_callback)
    #Function to basically tell the solver to use the distance call back as the primary cost (distance over time) that its using to minimize for all vehicles
    routing_model.SetArcCostEvaluatorOfAllVehicles(transit_index)

    print("Setup Complete!")

    #Demand callback and capacity constraint (to see at each specfic location, if the capacity constraints of the vehicle are fine)
    def demand_callback(from_place):
        #Convert internal ID to my index (readable matrix coordinates) - Shows what specific location we're talking about
        from_node = manager.IndexToNode(from_place)
        #Returns the specific stop's demand value from the list
        return 0 if from_node == 0 else data["demands"][from_node]

    #Function that essentially registers custom demand function with OR-tools (Single location, Unary)
    demand_callback = routing_model.RegisterUnaryTransitCallback(demand_callback)

    #Creates tracked dimension (weight) and enorces the weight limits across all the possible routes
    routing_model.AddDimensionWithVehicleCapacity(
        #Tells capacity dimension what callback function to use at each stop (set to 0, so vehicles can't temproraily exceed max capacity limit)
        demand_callback,
        0,
        #Passes max weight limit from data dictionary (set to 0 so solver must start route with load of 0)
        data["vehicle_capacity"],
        True,
        #Names this Capacity
        "Capacity"
    )

    print("Constraints Complete!")

    #Finally set the search parameters and actually solve
    search_params = pywrapcp.DefaultRoutingSearchParameters()

    #Use cheapest path as the first starting guess
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    #Now, solve problem with the actual parameters
    optimized_solution = routing_model.SolveWithParameters(search_params)

    if optimized_solution:
        print("Solution found!")

        total_distance = 0.0
        total_load = 0
        all_routes = []
        route_details = []
        #Looping through all the vehicles
        for vehicle_id in range(data["num_vehicles"]):
            #Get route for vehicle
            planned_output = f"Routing for vehicle {vehicle_id}: "
            index = routing_model.Start(vehicle_id)
            route_distance = 0
            route_load = 0

            #List to store route sequence for the map visual
            route_indices = []

            while not routing_model.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += 0 if node_index == 0 else data["demands"][node_index]

                #Save the stop index into the list
                route_indices.append(node_index)
                planned_output += f" ---> {node_index} (Load: {route_load}) --->"

                previous_index = index
                index = optimized_solution.Value(routing_model.NextVar(index))
                route_distance += routing_model.GetArcCostForVehicle(previous_index, index, vehicle_id)

            #Final Return to the place
            node_index = manager.IndexToNode(index)

            route_miles = route_distance / SCALE
            #Add the final depot stop
            route_indices.append(node_index)
            planned_output += f"{node_index} (Load: {route_load})"
            planned_output += f"\nTotal Distance for vehicle {vehicle_id}: {route_miles:.2f} miles"
            planned_output += f"\nTotal Load for vehicle {vehicle_id}: {route_load} units"

            print(planned_output)
            print("-" * 20)

            stop_labels = [
                f"{df.loc[i, 'Location_Name']} ({i})" if "Location_Name" in df.columns else f"Stop {i}"
                for i in route_indices
            ]

            route_details.append({
                "Vehicle": vehicle_id,
                "Route": " -> " .join(stop_labels),
                "Distance (miles)": round(route_miles, 2),
                "Load (units)": route_load,
            })
            #Add vehicle's indices to list
            all_routes.append(route_indices)
            #Call the Mapping function
            #plot_route(df, route_indices)
            total_distance += route_miles
            total_load += route_load

        map_file = plot_route(df, all_routes, output_path = map_output_path)

        print("\nFleet Summary")
        print(f"Total Distance across all vehicles: {total_distance} miles")
        print(f"Total Load delivered across all vehicles {total_load} units")

        return {
            "status": "Success",
            "total_distance": total_distance,
            "total_load": total_load,
            "route_details": route_details,
            "map_file": map_file,
        }
    else:
        print("No solution found successfully")
        return {"status": "Infeasible", "route_details": []}

if __name__ == "__main__":
    run_routing()