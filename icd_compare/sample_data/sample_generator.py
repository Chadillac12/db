import csv
import random
import os
import pandas as pd

def generate_sample_data(output_dir="sample_data"):
    os.makedirs(output_dir, exist_ok=True)
    
    # Define columns
    columns = ["id", "name", "category", "price", "stock", "description"]
    
    # Base data
    base_data = []
    for i in range(1, 501):
        base_data.append({
            "id": f"ID_{i:03d}",
            "name": f"Item {i}",
            "category": random.choice(["Electronics", "Home", "Garden", "Toys"]),
            "price": round(random.uniform(10.0, 500.0), 2),
            "stock": random.randint(0, 100),
            "description": f"Description for item {i} with some random text."
        })

    # Left data: Base data
    left_data = [row.copy() for row in base_data]
    
    # Right data: Base data modified
    right_data = []
    
    for i, row in enumerate(base_data):
        new_row = row.copy()
        
        # 1. Identical rows (first 200)
        if i < 200:
            right_data.append(new_row)
            
        # 2. Changed rows (next 200)
        elif i < 400:
            change_type = random.choice(["price", "stock", "name", "multiple"])
            if change_type == "price":
                new_row["price"] = round(new_row["price"] * 1.1, 2)
            elif change_type == "stock":
                new_row["stock"] += 10
            elif change_type == "name":
                new_row["name"] += " (Updated)"
            elif change_type == "multiple":
                new_row["price"] = round(new_row["price"] * 0.9, 2)
                new_row["stock"] = 0
            right_data.append(new_row)
            
        # 3. Left only (next 50 - do not add to right)
        elif i < 450:
            pass
            
        # 4. Right only (last 50 - handled below)
        else:
            # These are in left, but we will replace them with totally new items in right 
            # effectively making the original left items "Left Only" and the new ones "Right Only"
            # Wait, to make "Right Only" distinct from "Left Only", we should just add new items to Right
            pass

    # Add explicit Right Only items
    for i in range(501, 551):
        right_data.append({
            "id": f"ID_{i:03d}",
            "name": f"New Item {i}",
            "category": "New Category",
            "price": 99.99,
            "stock": 50,
            "description": "Brand new item."
        })

    # Write CSVs
    with open(os.path.join(output_dir, "sample_left.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(left_data)
        
    with open(os.path.join(output_dir, "sample_right.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(right_data)

    print(f"Generated sample_left.csv ({len(left_data)} rows) and sample_right.csv ({len(right_data)} rows) in {output_dir}")

    # Write Excel versions
    pd.DataFrame(left_data).to_excel(os.path.join(output_dir, "sample_left.xlsx"), index=False)
    pd.DataFrame(right_data).to_excel(os.path.join(output_dir, "sample_right.xlsx"), index=False)
    print(f"Generated sample_left.xlsx and sample_right.xlsx in {output_dir}")

if __name__ == "__main__":
    generate_sample_data()
