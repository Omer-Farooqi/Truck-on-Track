import csv
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

# Data validation functions
def validate_truck_number(truck_num: str) -> bool:
    """Validate truck number: non-empty, alphanumeric, max 20 chars."""
    return bool(truck_num) and truck_num.isalnum() and len(truck_num) <= 20

def validate_positive_float(value: str, field_name: str) -> Optional[float]:
    """Validate positive float input."""
    try:
        val = float(value)
        if val < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return val
    except ValueError:
        return None

def get_week_key(date_str: Optional[str] = None) -> str:
    """Get ISO week key from date or current date."""
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        date = datetime.now()
    return date.strftime('%Y-W%U')

class TruckOnTrack:
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.trucks_file = os.path.join(data_dir, 'trucks.csv')
        self.expenses_file = os.path.join(data_dir, 'expenses.csv')
        self.income_file = os.path.join(data_dir, 'income.csv')
        os.makedirs(data_dir, exist_ok=True)
        self.trucks: List[str] = []
        self.expenses: Dict[str, Dict] = {}
        self.income: Dict[str, Dict] = {}
        self.load_all_data()

    def load_all_data(self):
        """Load all CSV data on startup."""
        self.trucks = self._load_trucks()
        self.expenses = self._load_csv_dict(self.expenses_file)
        self.income = self._load_csv_dict(self.income_file)

    def _load_trucks(self) -> List[str]:
        if not os.path.exists(self.trucks_file):
            return []
        with open(self.trucks_file, 'r') as f:
            return [row[0] for row in csv.reader(f) if row]

    def _load_csv_dict(self, filename: str) -> Dict[str, Dict]:
        data = {}
        if not os.path.exists(filename):
            return data
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row['truck']}_{row['week']}"
                data[key] = {k: float(v) if v else 0.0
                             for k, v in row.items()
                             if k not in ('truck', 'week')}
        return data

    def _save_trucks(self):
        with open(self.trucks_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['truck_number'])
            writer.writerows([[truck] for truck in self.trucks])

    def _save_dict_to_csv(self, data: Dict[str, Dict], filename: str, fieldnames: List[str]):
        all_fields = ['truck', 'week'] + fieldnames
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_fields)
            writer.writeheader()
            for key, values in data.items():
                parts = key.split('_', 1)
                row = {'truck': parts[0], 'week': parts[1]}
                for field in fieldnames:
                    row[field] = values.get(field, 0.0)
                writer.writerow(row)

    def add_truck(self, truck_num: str) -> Dict[str, str]:
        """Add truck with validation. Returns success message or error."""
        if not validate_truck_number(truck_num):
            return {"success": False, "message": "Invalid truck number (alphanumeric, max 20 chars)"}
        
        if truck_num in self.trucks:
            return {"success": False, "message": "Truck already exists"}
        
        self.trucks.append(truck_num)
        self._save_trucks()
        return {"success": True, "message": f"Truck {truck_num} added successfully"}

    def get_trucks(self) -> List[str]:
        """Get list of available trucks."""
        return sorted(self.trucks)

    def enter_expenses(self, truck: str, week: str, expenses: Dict[str, str]) -> Dict[str, any]:
        """Enter weekly expenses with validation."""
        if truck not in self.trucks:
            return {"success": False, "message": "Truck not found"}
        
        validated = {}
        for field, value in expenses.items():
            val = validate_positive_float(value, field)
            if val is None:
                return {"success": False, "message": f"Invalid {field}: must be positive number"}
            validated[field] = val
        
        # Auto-calculate total
        validated['total_expenses'] = sum(validated.values())
        
        key = f"{truck}_{week}"
        self.expenses[key] = validated
        self._save_dict_to_csv(self.expenses, self.expenses_file, 
                             ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other', 'total_expenses'])
        return {"success": True, "data": validated, "message": "Expenses saved"}

    def enter_income(self, truck: str, week: str, income: float) -> Dict[str, any]:
        """Enter weekly income with validation."""
        if truck not in self.trucks:
            return {"success": False, "message": "Truck not found"}
        
        if not validate_positive_float(str(income), 'income'):
            return {"success": False, "message": "Income must be positive number"}
        
        key = f"{truck}_{week}"
        self.income[key] = {'income': float(income)}
        self._save_dict_to_csv(self.income, self.income_file, ['income'])
        return {"success": True, "data": self.income[key], "message": "Income saved"}

    def get_weekly_summary(self, truck: str, week: str) -> Dict[str, any]:
        """Get complete weekly summary with profit calculation."""
        if truck not in self.trucks:
            return {"success": False, "message": "Truck not found"}
        
        key = f"{truck}_{week}"
        expenses = self.expenses.get(key, {})
        income_data = self.income.get(key, {})
        income_total = income_data.get('income', 0.0)
        total_expenses = expenses.get('total_expenses', 0.0)
        profit = income_total - total_expenses
        
        summary = {
            "truck": truck,
            "week": week,
            "expenses": expenses,
            "income": income_total,
            "total_expenses": total_expenses,
            "profit": profit,
            "status": "profit" if profit > 0 else "loss"
        }
        return {"success": True, "data": summary}

    def generate_weekly_pdf(self, truck: str, week: str, output_dir: str = '.') -> Dict[str, any]:
        """Generate a PDF report for the weekly summary of a truck."""
        summary_result = self.get_weekly_summary(truck, week)
        if not summary_result["success"]:
            return summary_result

        data = summary_result["data"]
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"weekly_report_{truck}_{week}.pdf")

        doc = SimpleDocTemplate(filename, pagesize=letter,
                                rightMargin=0.75*inch, leftMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        # Title style
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                     fontSize=20, textColor=colors.HexColor('#1a1a2e'), spaceAfter=4)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                        fontSize=11, textColor=colors.HexColor('#555555'), spaceAfter=16)
        section_style = ParagraphStyle('Section', parent=styles['Heading2'],
                                       fontSize=13, textColor=colors.HexColor('#1a1a2e'),
                                       spaceBefore=14, spaceAfter=6)
        label_style = ParagraphStyle('Label', parent=styles['Normal'],
                                     fontSize=10, textColor=colors.HexColor('#333333'))

        # Header
        story.append(Paragraph("Truck on Track", title_style))
        story.append(Paragraph(f"Weekly Summary Report &mdash; Truck <b>{data['truck']}</b> &mdash; Week <b>{data['week']}</b>", subtitle_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", label_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a1a2e'), spaceAfter=14))

        # Expenses breakdown
        story.append(Paragraph("Expense Breakdown", section_style))
        expense_fields = ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other']
        expense_labels = ['Fuel', 'Repair', 'Tolls', 'Insurance', 'Driver Pay', 'Other']
        expense_rows = [['Category', 'Amount']]
        for field, label in zip(expense_fields, expense_labels):
            val = data['expenses'].get(field, 0.0)
            expense_rows.append([label, f"${val:,.2f}"])
        expense_rows.append(['TOTAL EXPENSES', f"${data['total_expenses']:,.2f}"])

        expense_table = Table(expense_rows, colWidths=[3.5*inch, 2.5*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#f5f5f5'), colors.white]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8e8e8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(expense_table)

        # Financial summary
        story.append(Paragraph("Financial Summary", section_style))
        profit_color = colors.HexColor('#1a7a1a') if data['profit'] >= 0 else colors.HexColor('#cc0000')
        status_label = 'NET PROFIT' if data['profit'] >= 0 else 'NET LOSS'

        summary_rows = [
            ['Total Income', f"${data['income']:,.2f}"],
            ['Total Expenses', f"${data['total_expenses']:,.2f}"],
            [status_label, f"${abs(data['profit']):,.2f}"],
        ]
        summary_table = Table(summary_rows, colWidths=[3.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 0), (-1, -2), [colors.HexColor('#f5f5f5'), colors.white]),
            ('BACKGROUND', (0, -1), (-1, -1), profit_color),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(summary_table)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=6))
        story.append(Paragraph("Truck on Track &mdash; Confidential", 
                                ParagraphStyle('Footer', parent=styles['Normal'],
                                               fontSize=8, textColor=colors.HexColor('#999999'))))

        doc.build(story)
        return {"success": True, "filename": filename, "message": f"PDF saved to {filename}"}

    def generate_error_report_pdf(self, truck: str, week: str,
                                   reporter_name: str, reporter_email: str,
                                   description: str, output_dir: str = '.') -> Dict[str, any]:
        """Generate an error/issue report PDF including the weekly summary."""
        summary_result = self.get_weekly_summary(truck, week)
        if not summary_result["success"]:
            return summary_result

        data = summary_result["data"]
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f"error_report_{truck}_{week}_{timestamp}.pdf")

        doc = SimpleDocTemplate(filename, pagesize=letter,
                                rightMargin=0.75*inch, leftMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                     fontSize=20, textColor=colors.HexColor('#8b0000'), spaceAfter=4)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                        fontSize=11, textColor=colors.HexColor('#555555'), spaceAfter=16)
        section_style = ParagraphStyle('Section', parent=styles['Heading2'],
                                       fontSize=13, textColor=colors.HexColor('#1a1a2e'),
                                       spaceBefore=14, spaceAfter=6)
        body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                    fontSize=10, leading=16, textColor=colors.HexColor('#333333'))
        label_style = ParagraphStyle('Label', parent=styles['Normal'],
                                     fontSize=10, textColor=colors.HexColor('#333333'))

        # Header
        story.append(Paragraph("Truck on Track &mdash; Error / Issue Report", title_style))
        story.append(Paragraph(f"Truck <b>{truck}</b> &mdash; Week <b>{week}</b>", subtitle_style))
        story.append(Paragraph(f"Submitted: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", label_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#8b0000'), spaceAfter=14))

        # Reporter info
        story.append(Paragraph("Reporter Information", section_style))
        reporter_rows = [
            ['Name', reporter_name],
            ['Email', reporter_email],
        ]
        reporter_table = Table(reporter_rows, colWidths=[1.5*inch, 4.5*inch])
        reporter_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('ROWBACKGROUNDS', (1, 0), (1, -1), [colors.white, colors.HexColor('#fafafa')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(reporter_table)

        # Issue description
        story.append(Paragraph("Issue Description", section_style))
        desc_table = Table([[description]], colWidths=[6.5*inch])
        desc_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff8f8')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#8b0000')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(desc_table)

        # Weekly summary section
        story.append(Paragraph("Associated Weekly Summary", section_style))

        expense_fields = ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other']
        expense_labels = ['Fuel', 'Repair', 'Tolls', 'Insurance', 'Driver Pay', 'Other']
        expense_rows = [['Category', 'Amount']]
        for field, label in zip(expense_fields, expense_labels):
            val = data['expenses'].get(field, 0.0)
            expense_rows.append([label, f"${val:,.2f}"])
        expense_rows.append(['TOTAL EXPENSES', f"${data['total_expenses']:,.2f}"])

        expense_table = Table(expense_rows, colWidths=[3.5*inch, 2.5*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#f5f5f5'), colors.white]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8e8e8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(expense_table)
        story.append(Spacer(1, 8))

        profit_color = colors.HexColor('#1a7a1a') if data['profit'] >= 0 else colors.HexColor('#cc0000')
        status_label = 'NET PROFIT' if data['profit'] >= 0 else 'NET LOSS'
        summary_rows = [
            ['Total Income', f"${data['income']:,.2f}"],
            ['Total Expenses', f"${data['total_expenses']:,.2f}"],
            [status_label, f"${abs(data['profit']):,.2f}"],
        ]
        summary_table = Table(summary_rows, colWidths=[3.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 0), (-1, -2), [colors.HexColor('#f5f5f5'), colors.white]),
            ('BACKGROUND', (0, -1), (-1, -1), profit_color),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        story.append(summary_table)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=6))
        story.append(Paragraph("Truck on Track &mdash; Confidential Issue Report",
                                ParagraphStyle('Footer', parent=styles['Normal'],
                                               fontSize=8, textColor=colors.HexColor('#999999'))))

        doc.build(story)
        return {"success": True, "filename": filename, "message": f"Error report saved to {filename}"}


# Demo usage and simple CLI interface
def main():
    fleet = TruckOnTrack()
    
    while True:
        print("\n=== Truck on Track ===")
        print("1. List trucks")
        print("2. Add truck")
        print("3. Enter expenses")
        print("4. Enter income")
        print("5. View weekly summary")
        print("6. Generate weekly PDF report")
        print("7. Report an error")
        print("8. Exit")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            trucks = fleet.get_trucks()
            print("Available trucks:", trucks if trucks else "None")
            
        elif choice == '2':
            truck_num = input("Enter truck number: ").strip()
            result = fleet.add_truck(truck_num)
            print(result['message'])
            
        elif choice == '3':
            trucks = fleet.get_trucks()
            if not trucks:
                print("No trucks available. Add one first.")
                continue
            print("Trucks:", trucks)
            truck = input("Select truck: ").strip()
            week = input("Enter week (YYYY-WWW or Enter for current): ").strip() or get_week_key()
            
            expenses = {}
            for field in ['fuel', 'repair', 'tolls', 'insurance', 'driver_pay', 'other']:
                expenses[field] = input(f"Enter {field} ($): ").strip()
            
            result = fleet.enter_expenses(truck, week, expenses)
            if result['success']:
                print(f"Total expenses: ${result['data']['total_expenses']:.2f}")
            print(result['message'])
            
        elif choice == '4':
            trucks = fleet.get_trucks()
            if not trucks:
                print("No trucks available.")
                continue
            print("Trucks:", trucks)
            truck = input("Select truck: ").strip()
            week = input("Enter week (YYYY-WWW or Enter for current): ").strip() or get_week_key()
            income_str = input("Enter weekly income ($): ").strip()
            result = fleet.enter_income(truck, week, float(income_str or 0))
            print(result['message'])
            
        elif choice == '5':
            trucks = fleet.get_trucks()
            if not trucks:
                print("No trucks available.")
                continue
            print("Trucks:", trucks)
            truck = input("Select truck: ").strip()
            week = input("Enter week (YYYY-WWW): ").strip() or get_week_key()
            summary = fleet.get_weekly_summary(truck, week)
            if summary['success']:
                data = summary['data']
                print(f"\nWeekly Summary - Truck {data['truck']} (Week {data['week']}):")
                print(f"Income: ${data['income']:.2f}")
                print(f"Total Expenses: ${data['total_expenses']:.2f}")
                print(f"Profit/Loss: ${data['profit']:.2f} ({data['status'].upper()})")
            else:
                print(summary['message'])

        elif choice == '6':
            trucks = fleet.get_trucks()
            if not trucks:
                print("No trucks available.")
                continue
            print("Trucks:", trucks)
            truck = input("Select truck: ").strip()
            week = input("Enter week (YYYY-WWW or Enter for current): ").strip() or get_week_key()
            result = fleet.generate_weekly_pdf(truck, week, output_dir='reports')
            print(result['message'])

        elif choice == '7':
            trucks = fleet.get_trucks()
            if not trucks:
                print("No trucks available.")
                continue
            print("Trucks:", trucks)
            truck = input("Select truck: ").strip()
            week = input("Enter week (YYYY-WWW or Enter for current): ").strip() or get_week_key()
            print("\n--- Reporter Details ---")
            name = input("Your name: ").strip()
            email = input("Your email: ").strip()
            description = input("Describe the error/issue: ").strip()
            if not name or not email or not description:
                print("Name, email, and description are all required.")
                continue
            result = fleet.generate_error_report_pdf(truck, week, name, email, description, output_dir='reports')
            print(result['message'])
                
        elif choice == '8':
            break

if __name__ == "__main__":
    main()
