# ThoughtOS User Journeys

**Date:** December 11, 2024  
**Version:** 1.0 (Current State Analysis)

This document outlines all user journeys currently supported by the ThoughtOS application based on the existing codebase implementation.

---

## Table of Contents

1. [Authentication & Access](#1-authentication--access)
2. [Onboarding Flow](#2-onboarding-flow)
3. [Main Chat Experience](#3-main-chat-experience)
4. [Context Rail Interactions](#4-context-rail-interactions)
5. [Graph Operations](#5-graph-operations)
6. [Transaction Tagging & Enrichment](#6-transaction-tagging--enrichment)
7. [Data Sync & Backfill](#7-data-sync--backfill)
8. [Admin Panel Operations](#8-admin-panel-operations)

---

## 1. Authentication & Access

### Journey: Google Sign-In

**Entry Point:** Application launch (unauthenticated state)

**Flow:**
1. User lands on the Login page displaying the animated "ThoughtOS" logo
2. User clicks "Authenticate with Google" button
3. Google OAuth popup appears requesting Calendar access permissions
4. User grants access → Auth code exchanged via `/api/auth/google/login`
5. User session stored in `localStorage`
6. User redirected to main application

**Technical Components:**
- `Login.tsx` - Login UI component
- `POST /api/auth/google/login` - Token exchange endpoint
- `@react-oauth/google` - OAuth library

**Post-Condition:** User authenticated, JWT stored, API requests include Bearer token

---

### Journey: Sign Out

**Entry Point:** Header "Sign Out" button (authenticated state)

**Flow:**
1. User clicks "Sign Out" in the header
2. LocalStorage cleared
3. Page reloads → User returned to Login screen

---

## 2. Onboarding Flow

### Journey: New User Setup

**Entry Point:** First login (when `onboarding_complete` flag is false)

**Flow:**

#### Step 1: Connect Data Sources
1. Onboarding wizard modal appears
2. User sees options to connect:
   - **Bank Account (Plaid)**: Click "Connect" → Plaid Link modal → Select bank → Enter credentials → Account linked
   - **Google Calendar**: Already connected via login OAuth (status shown)
3. User clicks "Continue"

#### Step 2: Financial Calibration
1. System fetches ambiguous transactions via `/api/onboarding/calibrate/finance`
2. For each transaction displayed:
   - Merchant name and total spend shown
   - Question asks for categorization
   - Multiple category options displayed (grid of buttons)
   - User can click option OR type custom category
3. Rule saved to backend via `/api/onboarding/rules`
4. Repeat until all questions answered
5. Automatic progression if no ambiguous transactions exist

#### Step 3: Fresh Start
1. User prompted: "What is the one thing you must do tomorrow?"
2. User types their first task
3. Task sent to `/api/chat` to create initial entry
4. Click "Finish Setup" → `/api/onboarding/complete` called
5. Onboarding modal closes → Main app revealed

**Technical Components:**
- `OnboardingWizard.tsx` - Wizard container
- `ConnectStep.tsx` - Plaid/Google connection
- `CalibrationStep.tsx` - Transaction categorization
- `FreshStartStep.tsx` - Initial task capture

---

## 3. Main Chat Experience

### Journey: Send a Text Message

**Entry Point:** Chat input field

**Flow:**
1. User types message in input field
2. User presses Enter or clicks "Send"
3. Message sent to `/api/chat` with:
   - Message text
   - Optional image (base64)
   - Thread ID (for conversation context)
   - Active context (if set)
4. AI processes through Agent routing:
   - Template detection
   - Command handling
   - Reasoning Engine (Graph-RAG)
5. Response rendered in chat with optional widgets

**Response Types:**
- `chat` - Plain text/markdown response
- `form` - Dynamic form widget
- `tag_selector` - Transaction categorization widget
- `chart` - Data visualization
- `stat` - Single metric display
- `list` - List items

---

### Journey: Send a Message with Image

**Entry Point:** Camera icon button

**Flow:**
1. User clicks camera icon
2. File picker opens (image files only)
3. Selected image shows as preview above input
4. User types optional message and sends
5. Image converted to base64 and sent to backend
6. AI processes image (Gemini Vision) and responds

**Technical Components:**
- `handleImageSelect()` in `App.tsx`
- File input with `accept="image/*"`
- Base64 conversion via FileReader

---

### Journey: Ask About Spending/Finances

**Entry Point:** Chat input with financial question

**Example Queries:**
- "How much did I spend on food this month?"
- "What are my top merchants?"
- "Show me my spending by category"

**Flow:**
1. Query sent to Reasoning Engine
2. Reasoning Engine:
   - Classifies intent
   - Retrieves relevant data from Neo4j Graph
   - May execute SQL queries
3. Response returns with:
   - Natural language answer
   - Optional `chart` widget with visualization

---

### Journey: Log Something (via Command)

**Entry Point:** Chat with "log", "record", "add", or "note" keywords

**Flow:**
1. User types: "Log my workout"
2. Agent detects template intent
3. If context is set:
   - Template generated based on context type
   - Form widget returned
4. User fills form and submits
5. Data saved to appropriate database table

---

## 4. Context Rail Interactions

### Journey: View Context Rail

**Entry Point:** Sidebar (always visible)

**Flow:**
1. Sidebar automatically fetches `/api/context`
2. Three sections displayed:
   - **Upcoming Events** - Google Calendar events
   - **Smart Tasks** - Tasks created in chat
   - **Log Stream** - Recent transactions, events, thoughts
3. Data refreshes every 60 seconds

---

### Journey: Set Active Context

**Entry Point:** Click on any event or task in sidebar

**Flow:**
1. User clicks an event (e.g., "Meeting with John")
2. Context banner appears showing linked context
3. Automatic form generated based on context type
4. Form widget appears in chat
5. User can fill form with notes/details
6. Submit saves via `/api/context/submit`

**Use Case:** Logging meeting notes, annotating calendar events

---

### Journey: Clear Active Context

**Entry Point:** "Clear" button on context banner

**Flow:**
1. User clicks "Clear" button
2. Context banner disappears
3. Associated form widget removed from chat
4. Chat returns to standard mode

---

## 5. Graph Operations

### Journey: Save Message to Graph

**Entry Point:** "Save to Graph" button on user messages

**Flow:**
1. User sends a message in chat
2. Under user message, "Save to Graph" button appears
3. User clicks button
4. **Link Suggester Modal** opens:
   - AI analyzes text for entity links
   - Suggests connections to existing nodes (people, merchants, events)
   - User can select/deselect suggestions
   - User can add custom links
5. User clicks "Confirm"
6. Data saved via `/api/graph/save` with text + links
7. Chat resets to fresh "scratchpad" state

**Technical Components:**
- `LinkSuggester.tsx` - Modal for link selection
- `POST /api/graph/analyze` - Entity extraction
- `POST /api/graph/save` - Persist to Neo4j

---

### Journey: Archive Message

**Entry Point:** "Archive" button on user messages

**Flow:**
1. User clicks "Archive" under their message
2. Message saved via `/api/graph/archive` (passive storage)
3. Chat resets to fresh state
4. Message preserved but not actively linked

**Use Case:** Quick capture without categorization

---

## 6. Transaction Tagging & Enrichment

### Journey: Conversational Transaction Tagging

**Entry Point:** Empty chat without context or command (passive trigger)

**Flow:**
1. User opens chat with no specific intent
2. Agent checks enrichment queue (`get_needs_user_review`)
3. If pending transactions exist:
   - Tag Selector widget appears automatically
   - Shows transaction details (merchant, amount, date)
   - Multiple category options displayed
   - "Other" option always available
4. User clicks category
5. Rule saved via backend
6. Next pending transaction shown
7. Repeat until queue empty

**Technical Components:**
- `TagSelector.tsx` - Widget component
- `_check_enrichment_queue()` in `agent.py`
- `/api/curator/apply` - Apply tag endpoint

---

## 7. Data Sync & Backfill

### Journey: Manual Data Sync

**Entry Point:** "SYNC DATA" button in sidebar

**Flow:**
1. User clicks "SYNC DATA" button
2. Button state changes to "SYNCING..."
3. Backend (`/api/sync`) triggers:
   - Plaid transaction fetch
   - Google Calendar event fetch
   - SQLite upserts
   - Neo4j graph sync
   - Enrichment pass
4. Alert shows "SYNC COMPLETE" or "SYNC FAILED"

---

### Journey: Backfill Historical Data

**Entry Point:** Chat command "backfill" or "fetch history"

**Example Queries:**
- "Backfill my transactions"
- "Load 365 days of history"
- "Fetch my 90 day history"

**Flow:**
1. User types backfill command
2. Agent detects command pattern
3. Response: "Starting backfill for the last X days..."
4. Background task triggered via `/api/action/backfill`
5. Data fetched and synced asynchronously

---

## 8. Admin Panel Operations

### Journey: Open Admin Panel

**Entry Point:** Header "Admin" button (gear icon)

**Flow:**
1. User clicks Admin button
2. Full-screen modal opens with tabs:
   - **Auth** - Connect Plaid/Google
   - **Curator** - Transaction review queue
   - **Logs** - System logs
   - **Analysis** - Causal analysis

---

### Journey: Curator - Review Transactions

**Entry Point:** Admin Panel → Curator tab

**Flow:**
1. User navigates to Curator tab
2. List of transactions needing review displayed
3. For each transaction:
   - Click to select
   - Choose category from dropdown
   - Click "Apply"
4. Optional actions:
   - "Run Auto-Tagger" - AI categorizes batch
   - "Reset All" - Clear enrichment status

**Technical Components:**
- `/api/curator/review` - Get review items
- `/api/curator/apply` - Apply single tag
- `/api/curator/auto` - Run auto-tagger
- `/api/curator/reset` - Reset enrichment

---

### Journey: View System Logs

**Entry Point:** Admin Panel → Logs tab

**Flow:**
1. User navigates to Logs tab
2. Recent logs fetched from `/api/admin/logs`
3. Logs displayed with timestamp formatting
4. "Clear Logs" button available

---

### Journey: Run Causal Analysis

**Entry Point:** Admin Panel → Analysis tab

**Flow:**
1. User navigates to Analysis tab
2. Clicks "Run Analysis"
3. Backend executes `analyze_stress_spending()`
4. Results displayed in panel

---

## Journey Summary Table

| Journey | Trigger | Key Endpoint |
|---------|---------|--------------|
| Google Sign-In | App launch | `POST /api/auth/google/login` |
| Onboarding | First login | `/api/onboarding/*` |
| Send Chat | Enter key | `POST /api/chat` |
| Image Upload | Camera button | `POST /api/chat` (with base64) |
| Set Context | Sidebar click | Local state |
| Save to Graph | Button click | `POST /api/graph/save` |
| Archive | Button click | `POST /api/graph/archive` |
| Tag Transaction | Widget selection | `POST /api/curator/apply` |
| Sync Data | Sidebar button | `POST /api/sync` |
| Backfill | Chat command | `POST /api/action/backfill` |
| Admin Operations | Panel navigation | `/api/admin/*`, `/api/curator/*` |

---

## Known Gaps & Missing Journeys

Based on code analysis, the following features appear incomplete or unavailable:

1. **No explicit task completion** - Smart Tasks visible but no "mark complete" action
2. **No edit/undo for graph entries** - Once saved, no modification UI
3. **No notification system** - Real-time updates require manual sync
4. **No mobile-specific flows** - No PWA or responsive optimizations detected
5. **No search functionality** - Cannot search historical chat or graph
6. **No export/share** - Cannot export graph/insights data

---

*Generated from ThoughtOS codebase analysis - December 2024*
