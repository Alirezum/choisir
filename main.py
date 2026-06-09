import os
import random
import sys
from datetime import datetime

def get_logged_items(log_file="selected_items.txt"):
    if not os.path.exists(log_file):
        return set()
    with open(log_file, "r", encoding="utf-8") as f:
        items = set()
        for line in f:
            line = line.strip()
            if not line:
                continue
            if " - " in line:
                item = line.split(" - ", 1)[1]
            else:
                item = line
            items.add(item)
        return items

def log_selection(item, log_file="selected_items.txt"):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {item}\n")

def get_unselected_item(directory, log_file="selected_items.txt"):
    all_items = set(os.listdir(directory))
    if not all_items:
        return None  

    logged_items = get_logged_items(log_file)
    available_items = list(all_items - logged_items)

    if not available_items:
        return None 
    return random.choice(available_items)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        dir_path = sys.argv[1]
    else:
        dir_path = input("Enter Path: ")

    if not os.path.isdir(dir_path):
        print("Invalid Path.")
    else:
        random_item = get_unselected_item(dir_path)
        if random_item is None:
            all_items = os.listdir(dir_path)
            if not all_items:
                print("Path Empty.")
            else:
                print("All choices have been selected. Delete log to reset.")
        else:
            print(f"The choice: {random_item}")
            log_selection(random_item)
            print(f"Added in selected_items.txt with timestamp.\n")
