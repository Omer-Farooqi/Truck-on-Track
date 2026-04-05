import csv
import os
from typing import Dict, Any

class TruckFleetManager:
    def __init__(self, data_dir: str = 'fleet_data'):
        self.data_dir = data_dir
        self.trucks_file = os.path.join(data_dir, 'trucks.csv')
        self.expenses_file = os.path.join(data_dir, 'expenses.csv')
        self.income_file = os.path.join(data_dir, 'income.csv')
        os.makedirs(data_dir, exist_ok=True)
        self.trucks = []
        self.expenses = {}
        self.income = {}
        self.load_data()

    def load_data(self):
        """Load all data from CSV files."""
        self.trucks = self._load_trucks()
        self.expenses = self._load_records(self.expenses_file)
        self.income = self._load_records(self.income_file)

    def _load_trucks(self) -> list:
        if not os.path.exists(self.trucks_file):
            return []
        with open(self.trucks_file, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            return [row[0] for row in reader if row]

    def _load_records(self, filename: str) -> dict:
        records = {}
        if not os.path.exists(filename):
            return records
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row['truck']}_{row['week']}"
                records[key] = {k: float(v) for k, v in row.items() if k not in ['truck', 'week']}
        return records

    def save_trucks(self):
        with open(self.trucks_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['truck_number'])
            for truck in self.trucks:
                writer.writerow([truck])

    def save_records(self, records: dict, filename: str, fieldnames: list):
        """Save records to CSV with proper field order."""
        all_rows = []
        for key, values in records.items():
            truck, week = key.split('_')
            row = {'truck': truck, 'week': week}
            row.update(values)
            all_rows.append(row)
        
        if all_rows:
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['truck', 'week'] + fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)

    def validate_truck_num(self, truck_num: str) -> tuple[bool, str]:
        if not truck_num or not truck_num.isalnum() or len(truck_num) > 20:
            return False, "Truck number must be alphanumeric (max 20 chars)"
        if truck_num in self.trucks:
            return False, "Truck already exists"
        return True, "Valid"

    def validate_amount(self, amount_str: str) -> tuple[float|None, str]:
        try:
            amount = float(amount_str)
            if amount < 0:
                return None, "Amount cannot be negative"
            return amount, "Valid"
        except ValueError:
            return None, "Enter valid number"

    def add_truck(self):
        print("\n--- ADD TRUCK ---")
        truck_num = input("Enter truck number: ").strip()
        valid, msg = self.validate_truck_num(truck_num)
        if valid:
            self.trucks.append(truck_num)
            self.save_trucks()
            print(f"Truck '{truck_num}' added successfully!")
        else:
            print(f"Error: {msg}")

    def list_trucks(self):
        print("\n--- AVAILABLE TRUCKS ---")
        if not self.trucks:
            print("No trucks added yet.")
        else:
            for i, truck in enumerate(self.trucks, 1):
                print(f"{i}. {truck}")

    def enter_expenses(self):
        self.list_trucks()
        if not self.trucks:
            print("Add a truck first!")
            return
        
        print("\n--- ENTER WEEKLY EXPENSES ---")
        truck = input("Select truck number: ").strip()
        if truck not in self.trucks:
            print("Truck not found!")
            return
        
        week = input("Enter week (YYYY-WWW, e.g., 2026-W14): ").strip()
        if not week:
            print("Week required!")
            return

        expenses = {}
        expense_fields = ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other']
        
        print("\nEnter amounts (or 0 to skip):")
        for field in expense_fields:
            while True:
                amount_str = input(f"{field.replace('_', ' ').title()}: $").strip()
                amount, msg = self.validate_amount(amount_str)
                if amount is not None:
                    expenses[field] = amount
                    break
                print(f"Error: {msg}")
        
        total_expenses = sum(expenses.values())
        expenses['total_expenses'] = total_expenses
        
        key = f"{truck}_{week}"
        self.expenses[key] = expenses
        self.save_records(self.expenses, self.expenses_file, 
                         ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other', 'total_expenses'])
        
        print(f"\nExpenses saved for {truck} - Week {week}")
        print(f"Total Expenses: ${total_expenses:.2f}")

    def enter_income(self):
        self.list_trucks()
        if not self.trucks:
            print("Add a truck first!")
            return
        
        print("\n--- ENTER WEEKLY INCOME ---")
        truck = input("Select truck number: ").strip()
        if truck not in self.trucks:
            print("Truck not found!")
            return
        
        week = input("Enter week (YYYY-WWW): ").strip()
        if not week:
            print("Week required!")
            return
        
        while True:
            income_str = input("Enter weekly income: $").strip()
            income, msg = self.validate_amount(income_str)
            if income is not None:
                break
            print(f"Error: {msg}")
        
        key = f"{truck}_{week}"
        self.income[key] = {'income': income}
        self.save_records(self.income, self.income_file, ['income'])
        
        print(f"\nIncome ${income:.2f} saved for {truck} - Week {week}")

    def view_summary(self):
        self.list_trucks()
        if not self.trucks:
            print("Add a truck first!")
            return
        
        print("\n--- WEEKLY SUMMARY ---")
        truck = input("Select truck number: ").strip()
        if truck not in self.trucks:
            print("Truck not found!")
            return
        
        week = input("Enter week (YYYY-WWW): ").strip()
        if not week:
            print("Week required!")
            return
        
        key = f"{truck}_{week}"
        expenses = self.expenses.get(key, {})
        income_data = self.income.get(key, {})
        
        total_expenses = expenses.get('total_expenses', 0.0)
        income_total = income_data.get('income', 0.0)
        net_profit = income_total - total_expenses
        
        print(f"\n{'='*50}")
        print(f"WEEKLY SUMMARY - {truck.upper()} | Week {week}")
        print(f"{'='*50}")
        print(f"Weekly Income:     ${income_total:>10.2f}")
        print(f"Total Expenses:    ${total_expenses:>10.2f}")
        print(f"{'-'*50}")
        print(f"Net Profit:        ${net_profit:>10.2f}")
        print(f"{'='*50}")
        
        if expenses:
            print("\nExpense Breakdown:")
            for field, amount in expenses.items():
                if field != 'total_expenses':
                    print(f"  {field.replace('_', ' ').title()}: ${amount:>8.2f}")

def main():
    print("TRUCK FLEET MANAGER")
    print("=" * 20)
    manager = TruckFleetManager()
    
    while True:
        print("\nMAIN MENU")
        print("1. Add Truck")
        print("2. List Trucks")
        print("3. Enter Expenses")
        print("4. Enter Income")
        print("5. View Weekly Summary")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            manager.add_truck()
        elif choice == '2':
            manager.list_trucks()
        elif choice == '3':
            manager.enter_expenses()
        elif choice == '4':
            manager.enter_income()
        elif choice == '5':
            manager.view_summary()
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid option! Choose 1-6.")

if __name__ == "__main__":
    main()