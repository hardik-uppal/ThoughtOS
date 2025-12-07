from logic.sql_engine import get_transactions, get_events, add_rule, set_preference, get_preference
from collections import Counter
import json

class OnboardingAgent:
    def __init__(self):
        self.name = "Onboarding Agent"

    def generate_financial_questions(self):
        """
        Analyzes transaction history to find ambiguous merchants and generates
        calibration questions for the user.
        """
        transactions = get_transactions(limit=500)
        if not transactions:
            return []

        # 1. Aggregate spending by merchant
        merchant_spend = {}
        merchant_counts = Counter()
        
        for txn in transactions:
            merchant = txn['merchant_name']
            amount = float(txn['amount'])
            if amount > 0: # Only consider spending
                merchant_spend[merchant] = merchant_spend.get(merchant, 0) + amount
                merchant_counts[merchant] += 1

        # 2. Identify "Ambiguous" High Spenders
        # Logic: High spend (> $100 total) AND Frequent (> 2 times)
        questions = []
        
        # Known categories to skip (Mock logic for now, could be smarter)
        skip_keywords = ['uber', 'lyft', 'doordash', 'amazon'] 

        for merchant, total_spend in merchant_spend.items():
            if total_spend > 100 and merchant_counts[merchant] >= 2:
                # Skip if it looks obvious (simple heuristic)
                if any(k in merchant.lower() for k in skip_keywords):
                    continue
                    
                questions.append({
                    "id": f"rule_{merchant}",
                    "type": "category_rule",
                    "merchant": merchant,
                    "total_spend": round(total_spend, 2),
                    "question": f"I see you spent ${round(total_spend)} at {merchant}. How should I categorize this?",
                    "question": f"I see you spent ${round(total_spend)} at {merchant}. How should I categorize this?",
                    "options": self._suggest_categories(merchant)
                })

        # Limit to top 5 most impactful questions
        return sorted(questions, key=lambda x: x['total_spend'], reverse=True)[:5]

    def _suggest_categories(self, merchant):
        """
        Returns a list of category options, prioritized by merchant keywords.
        """
        merchant_lower = merchant.lower()
        
        # Standard set of categories
        base_categories = [
            "Groceries", "Dining", "Shopping", "Bills", "Entertainment", 
            "Investment", "Transfer", "Rent", "Mortgage", "Utilities", 
            "Transport", "Health", "Income", "Salary", "Services", 
            "Credit Card Payment", "Loan Repayment", "Insurance"
        ]
        
        # Keyword mappings for prioritization
        priorities = []
        
        # Housing
        if any(k in merchant_lower for k in ['mortgage', 'housing loan']):
            priorities.append("Mortgage")
            priorities.append("Loan Repayment")
        if any(k in merchant_lower for k in ['property', 'realty', 'rent', 'lease', 'birds nest']):
            priorities.append("Rent")
            priorities.append("Mortgage") # Ambiguous, could be either
            
        # Utilities
        if any(k in merchant_lower for k in ['hydro', 'power', 'energy', 'internet', 'wifi', 'mobile', 'telus', 'rogers', 'bell']):
            priorities.append("Utilities")
            priorities.append("Bills")
            
        # Food
        if any(k in merchant_lower for k in ['market', 'superstore', 'loblaws', 'whole foods', 'save-on', 'walmart']):
            priorities.append("Groceries")
        if any(k in merchant_lower for k in ['restaurant', 'cafe', 'coffee', 'bistro', 'pizza', 'sushi', 'burger']):
            priorities.append("Dining")
            
        # Finance / Loans
        if any(k in merchant_lower for k in ['wealthsimple', 'questrade', 'invest', 'savings']):
            priorities.append("Investment")
            priorities.append("Transfer")
        if any(k in merchant_lower for k in ['loan', 'finance', 'lending', 'honda', 'toyota', 'ford', 'auto finance']):
            priorities.append("Loan Repayment")
            priorities.append("Bills")
        if any(k in merchant_lower for k in ['insurance', 'assurance', 'life', 'auto']):
            priorities.append("Insurance")
            priorities.append("Bills")
        if any(k in merchant_lower for k in ['credit card', 'visa', 'mastercard', 'amex', 'bill payment', 'crd. card', 'card']):
            priorities.append("Credit Card Payment")
            priorities.append("Transfer")
            priorities.append("Bills")
            
        # Combine priorities with base categories (removing duplicates)
        final_options = priorities + [c for c in base_categories if c not in priorities]
        
        # Return top 8 options to keep UI clean
        return final_options[:8]

    def set_productivity_defaults(self):
        """
        Analyzes calendar density to set energy thresholds.
        """
        events = get_events(limit=100) # Look at recent history
        if not events:
            # Default fallback
            set_preference("energy_threshold_meetings", 4)
            set_preference("merciful_mode", "true")
            return {
                "energy_threshold_meetings": 4,
                "merciful_mode": True,
                "status": "defaults_set"
            }

        # Calculate average meeting hours per day
        # (Simplified logic: just count total duration / unique days)
        total_duration_hours = 0
        unique_days = set()
        
        for event in events:
            # Assume 1 hour if duration missing (mock)
            duration = 1.0 
            if 'start_iso' in event and 'end_iso' in event:
                # TODO: Parse ISO dates to get real duration
                pass
            
            total_duration_hours += duration
            if 'start_iso' in event:
                unique_days.add(event['start_iso'][:10]) # YYYY-MM-DD

        days_count = len(unique_days) if unique_days else 1
        avg_hours = total_duration_hours / days_count

        # Set Thresholds
        threshold = 4
        if avg_hours > 5:
            threshold = 6 # High tolerance
        elif avg_hours < 2:
            threshold = 3 # Low tolerance

        set_preference("energy_threshold_meetings", threshold)
        set_preference("merciful_mode", "true")

        return {
            "energy_threshold_meetings": threshold,
            "merciful_mode": True,
            "avg_meeting_hours": round(avg_hours, 1)
        }

    def save_rule(self, merchant, category):
        """Saves a user rule."""
        return add_rule(merchant, category)

    def complete_onboarding(self):
        """Marks onboarding as complete."""
        set_preference("onboarding_complete", "true")
        return True

    def check_status(self):
        """Checks if onboarding is complete."""
        status = get_preference("onboarding_complete")
        return status == "true"
