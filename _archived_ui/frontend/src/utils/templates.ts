/**
 * Template detection and form generation (client-side)
 */

export interface FormField {
    name: string;
    label: string;
    type: 'text' | 'textarea';
    placeholder: string;
}

export interface FormTemplate {
    title: string;
    fields: FormField[];
}

export function detectTemplateType(itemData: any): string {
    const text = (itemData.summary || itemData.content_text || '').toLowerCase();

    // Meeting patterns
    if (/meeting|standup|sync|call|review|1:1|interview/i.test(text)) {
        return 'meeting';
    }

    // Workout patterns
    if (/gym|workout|exercise|training|run|yoga|fitness/i.test(text)) {
        return 'workout';
    }

    // Food patterns
    if (/lunch|dinner|breakfast|brunch|meal|eat|food/i.test(text)) {
        return 'food';
    }

    return 'notes';
}

export function generateTemplate(templateType: string, itemData: any): FormTemplate {
    const itemTitle = itemData.summary || itemData.content_text || 'Item';

    switch (templateType) {
        case 'meeting':
            return {
                title: `Meeting Notes: ${itemTitle}`,
                fields: [
                    { name: 'attendees', label: 'Attendees', type: 'text', placeholder: 'John, Sarah, team@company.com' },
                    { name: 'key_points', label: 'Key Discussion Points', type: 'textarea', placeholder: 'What was discussed?' },
                    { name: 'decisions', label: 'Decisions Made', type: 'textarea', placeholder: 'What was decided?' },
                    { name: 'action_items', label: 'Action Items', type: 'textarea', placeholder: 'Who needs to do what?' },
                    { name: 'next_steps', label: 'Next Steps', type: 'text', placeholder: 'Follow-up meeting, deadlines, etc.' }
                ]
            };

        case 'workout':
            return {
                title: `Workout Log: ${itemTitle}`,
                fields: [
                    { name: 'exercises', label: 'Exercises', type: 'textarea', placeholder: 'Bench press, squats, deadlifts...' },
                    { name: 'sets_reps', label: 'Sets x Reps', type: 'textarea', placeholder: '3x10, 4x8, etc.' },
                    { name: 'weight', label: 'Weight Used', type: 'text', placeholder: '185lbs, 225lbs, etc.' },
                    { name: 'duration', label: 'Duration', type: 'text', placeholder: '45 min' },
                    { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'How did you feel? PRs?' }
                ]
            };

        case 'food':
            return {
                title: `Food Log: ${itemTitle}`,
                fields: [
                    { name: 'meal', label: 'What did you eat?', type: 'textarea', placeholder: 'Chicken salad, brown rice, veggies...' },
                    { name: 'calories', label: 'Estimated Calories', type: 'text', placeholder: '~500 cal' },
                    { name: 'protein', label: 'Protein (g)', type: 'text', placeholder: '40g' },
                    { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'How did you feel? Energy level?' }
                ]
            };

        default:
            return {
                title: `Notes: ${itemTitle}`,
                fields: [
                    { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Add your notes here...' },
                    { name: 'tags', label: 'Tags', type: 'text', placeholder: 'important, follow-up, etc.' }
                ]
            };
    }
}
