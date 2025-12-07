"""
Template generator for context-based forms.
Detects event/task type and generates appropriate form structure.
"""

def detect_template_type(item_data):
    """
    Detects the appropriate template based on event/task content.
    
    Args:
        item_data: Dict with 'summary' or 'content_text'
    
    Returns:
        Template type string
    """
    text = (item_data.get('summary') or item_data.get('content_text') or '').lower()
    
    # Meeting patterns
    if any(word in text for word in ['meeting', 'standup', 'sync', 'call', 'review', '1:1', 'interview']):
        return 'meeting'
    
    # Workout patterns
    if any(word in text for word in ['gym', 'workout', 'exercise', 'training', 'run', 'yoga', 'fitness']):
        return 'workout'
    
    # Food patterns
    if any(word in text for word in ['lunch', 'dinner', 'breakfast', 'brunch', 'meal', 'eat', 'food']):
        return 'food'
    
    # Default
    return 'notes'

def generate_template_widget(template_type, item_data):
    """
    Generates a form widget structure based on template type.
    
    Returns:
        Dict with widget type and fields
    """
    if template_type == 'meeting':
        return {
            "type": "form",
            "title": f"Meeting Notes: {item_data.get('summary', 'Event')}",
            "fields": [
                {"name": "attendees", "label": "Attendees", "type": "text", "placeholder": "John, Sarah, team@company.com"},
                {"name": "key_points", "label": "Key Discussion Points", "type": "textarea", "placeholder": "What was discussed?"},
                {"name": "decisions", "label": "Decisions Made", "type": "textarea", "placeholder": "What was decided?"},
                {"name": "action_items", "label": "Action Items", "type": "textarea", "placeholder": "Who needs to do what?"},
                {"name": "next_steps", "label": "Next Steps", "type": "text", "placeholder": "Follow-up meeting, deadlines, etc."}
            ]
        }
    
    elif template_type == 'workout':
        return {
            "type": "form",
            "title": f"Workout Log: {item_data.get('summary', 'Session')}",
            "fields": [
                {"name": "exercises", "label": "Exercises", "type": "textarea", "placeholder": "Bench press, squats, deadlifts..."},
                {"name": "sets_reps", "label": "Sets x Reps", "type": "textarea", "placeholder": "3x10, 4x8, etc."},
                {"name": "weight", "label": "Weight Used", "type": "text", "placeholder": "185lbs, 225lbs, etc."},
                {"name": "duration", "label": "Duration", "type": "text", "placeholder": "45 min"},
                {"name": "notes", "label": "Notes", "type": "textarea", "placeholder": "How did you feel? PRs?"}
            ]
        }
    
    elif template_type == 'food':
        return {
            "type": "form",
            "title": f"Food Log: {item_data.get('summary', 'Meal')}",
            "fields": [
                {"name": "meal", "label": "What did you eat?", "type": "textarea", "placeholder": "Chicken salad, brown rice, veggies..."},
                {"name": "calories", "label": "Estimated Calories", "type": "text", "placeholder": "~500 cal"},
                {"name": "protein", "label": "Protein (g)", "type": "text", "placeholder": "40g"},
                {"name": "notes", "label": "Notes", "type": "textarea", "placeholder": "How did you feel? Energy level?"}
            ]
        }
    
    else:  # Generic notes
        return {
            "type": "form",
            "title": f"Notes: {item_data.get('summary') or item_data.get('content_text', 'Item')}",
            "fields": [
                {"name": "notes", "label": "Notes", "type": "textarea", "placeholder": "Add your notes here..."},
                {"name": "tags", "label": "Tags", "type": "text", "placeholder": "important, follow-up, etc."}
            ]
        }
