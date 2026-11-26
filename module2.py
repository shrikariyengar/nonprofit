import pandas as pd
import pulp

def run_kitter(csv_path = "inventory.csv", box_volume_limit = 15):
    #Load in inventory.csv
    df = pd.read_csv(csv_path, comment = "#", skipinitialspace = True)
    #Define the problem first
    problem = pulp.LpProblem("Nonprofit_Optimization", pulp.LpMaximize)

    #Fill in missing optional columns with default values
    if "min_per_box" not in df.columns:
        df["min_per_box"] = 0
    else:
        df["min_per_box"] = df["min_per_box"].fillna(0)

    if "max_per_box" not in df.columns:
        df["max_per_box"] = 999999
    else:
        df["max_per_box"] = df["max_per_box"].fillna(999999)

    BOX_VOLUME_LIMIT = box_volume_limit

    #Declare and initalize the variables that the algorithm is allowed to change
    Boxes = problem.add_variable("Total Boxes", lowBound = 0, cat = "Integer")
    items = problem.add_variable_dicts (
        "Items per Box",
        df["item_id"],
        lowBound = 0,
        cat = "Integer"

    )
    #What next? (Step 2) Constraints
    #Actually tell the algorithm now to maximize B
    total_box_space = pulp.lpSum(row["size_units"] * items[row["item_id"]] for index, row in df.iterrows())
    #Tie-Breaker: If two choices are tied, pick the choice that uses more total space (why we multipled by total_box_space)
    #problem += Boxes + 0.00001 * total_box_space, "Maximize_Total_Boxes"
    problem += Boxes, "Maximize_Total_Boxes"
    #Give the capacity constrain of not going past the space
    problem += total_box_space <= Boxes * BOX_VOLUME_LIMIT, "Box_Capacity"

    #Constraints
    for index, row in df.iterrows():
        #We can't multiply two variables together because it needs to be linear, so Boxes is moved up
        item_name = row["item_id"]

        problem += items[item_name] <= row["quantity_available"], f"Inventory_Limit_{item_name}"

        #For Min and Max (Min is >= because it needs to be greater than or equal to constraint)
        problem += items[item_name] >= row["min_per_box"] * Boxes, f"Min_Per_Box{item_name}"

        problem += items[item_name] <= row["max_per_box"] * Boxes, f"Max_Per_Box{item_name}"

    #Finally, Step 3, solving the problem
    stats = problem.solve()
    status_label = getattr(getattr(stats, "status", stats), "name", str(stats))
    has_solution = getattr(stats, "has_solution", status_label == "Optimal")
    print("Optimization Results")

    #Print Status
    print("Status: ", status_label)

    raw_boxes = pulp.value(Boxes)
    total_boxes = int(round(raw_boxes)) if (has_solution and raw_boxes is not None) else 0
    #Print the Answer (Optimizer)
    print(f"Total Boxes to Pack: {total_boxes}")

    #Breakdown across Items for one box
    print(f"Breakdown of items for a single box: ")
    manifest = {}
    for item_name, var in items.items():
        #Divide so it outputs per box (not total boxes)
        raw_qty = pulp.value(var)
        qty_packed = raw_qty if (has_solution and raw_qty is not None) else 0
        per_box = int(qty_packed // total_boxes) if total_boxes > 0 else 0
        print(f"{item_name}: {per_box} units per box")
        manifest[item_name] = per_box


    #Return data to streamlit
    return {
        "status": status_label,
        "total_boxes": total_boxes,
        "manifest": manifest
    }

if __name__ == "__main__":
    print("Running Inventory Optimizer")
    results = run_kitter(csv_path="inventory.csv", box_volume_limit = 15)
    print("Optimization Complete")